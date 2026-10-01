import json
import logging
import time
import threading
from datetime import timedelta
from confluent_kafka import Producer, Consumer, TopicPartition, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic
from sqlalchemy import select, exists
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased
from polka.config import settings
from polka.db import Session
from polka.models import Order, OutboxEvent, ProcessedEvent, FulfillmentTask, Notification, Document, SalesFact, EventFailure, now
from polka.services import order_query, set_status, STATUS_LABELS
from polka.reports import document_pdf

log = logging.getLogger(__name__)
HANDLERS = ("warehouse", "notifications", "analytics", "documents")


def ensure_topic():
    admin = AdminClient({"bootstrap.servers": settings().kafka_bootstrap_servers})
    futures = admin.create_topics([NewTopic(settings().kafka_topic, num_partitions=3, replication_factor=1, config={"retention.ms": str(7*86400000)})])
    for future in futures.values():
        try:
            future.result(12)
        except KafkaException as error:
            if error.args[0].name() != "TOPIC_ALREADY_EXISTS":
                raise


def publish_one(producer):
    older = aliased(OutboxEvent)
    with Session() as db:
        query = select(OutboxEvent).where(OutboxEvent.published_at.is_(None), OutboxEvent.retry_at <= now(), ~exists(select(older.id).where(older.order_id == OutboxEvent.order_id, older.id < OutboxEvent.id, older.published_at.is_(None)))).order_by(OutboxEvent.id).with_for_update(skip_locked=True).limit(1)
        event = db.scalar(query)
        if not event:
            return False
        envelope = {"event_id": event.event_id, "kind": event.kind, "occurred_at": event.created_at.isoformat(), **event.payload}
        delivered = []
        try:
            producer.produce(settings().kafka_topic, key=str(event.order_id), value=json.dumps(envelope, ensure_ascii=False).encode(), on_delivery=lambda error, message: delivered.append(error))
            remaining = producer.flush(12)
            if remaining or not delivered or delivered[0]:
                raise RuntimeError("Kafka не подтвердила запись события")
            event.published_at = now()
            log.info("Опубликовано событие %s заказа %s", event.kind, event.order_id)
        except Exception as error:
            event.attempts += 1
            event.retry_at = now() + timedelta(seconds=min(60, 2 ** min(event.attempts, 6)))
            log.warning("Отложена публикация события %s: %s", event.event_id, type(error).__name__)
        db.commit()
        return True


def process_event(db, handler, event):
    event_id = event["event_id"]
    if handler not in HANDLERS:
        raise ValueError("Неизвестный обработчик")
    inserted = db.execute(insert(ProcessedEvent).values(handler=handler, event_id=event_id).on_conflict_do_nothing().returning(ProcessedEvent.event_id)).scalar()
    if not inserted:
        return False
    order = db.scalar(order_query().where(Order.id == event["order_id"]).with_for_update())
    if not order:
        raise ValueError("Заказ события не найден")
    kind = event["kind"]
    if handler == "warehouse" and kind == "order.created" and order.status == "created":
        if not db.scalar(select(FulfillmentTask).where(FulfillmentTask.order_id == order.id)):
            db.add(FulfillmentTask(order_id=order.id))
        set_status(db, order, "queued", "Служба склада")
    elif handler == "notifications" and kind.startswith("order."):
        status = event.get("status")
        if status in STATUS_LABELS:
            db.add(Notification(user_id=order.customer_id, order_id=order.id, text=f"Заказ №{order.id:06d}: {STATUS_LABELS[status].lower()}"))
    elif handler == "analytics" and kind == "order.delivered":
        if not order.delivered_at:
            raise ValueError("Не записано время доставки")
        db.execute(insert(SalesFact).values(order_id=order.id, total=order.total, delivered_at=order.delivered_at).on_conflict_do_nothing())
    elif handler == "documents" and kind == "order.delivered":
        if not db.get(Document, order.id):
            db.add(Document(order_id=order.id, content=document_pdf(order)))
    log.info("Обработчик %s: событие %s заказа %s", handler, kind, order.id)
    return True


def consumer_loop(handler, stop):
    consumer = Consumer({"bootstrap.servers": settings().kafka_bootstrap_servers, "group.id": f"polka-{handler}-{settings().database_schema}", "enable.auto.commit": False, "auto.offset.reset": "earliest", "session.timeout.ms": 45000, "max.poll.interval.ms": 300000}, logger=log)
    consumer.subscribe([settings().kafka_topic])
    try:
        while not stop.is_set():
            message = consumer.poll(1)
            if message is None:
                continue
            if message.error():
                log.warning("Kafka: обработчик %s: %s", handler, message.error())
                stop.wait(2)
                continue
            event = {}
            fallback_id = f"{message.topic()}:{message.partition()}:{message.offset()}"
            try:
                event = json.loads(message.value())
                if not isinstance(event, dict):
                    event = {}
                    raise ValueError("Событие должно быть объектом")
                with Session.begin() as db:
                    process_event(db, handler, event)
                consumer.commit(message=message, asynchronous=False)
            except Exception as error:
                log.exception("Ошибка обработки: %s, %s", handler, fallback_id)
                try:
                    with Session.begin() as db:
                        key = str(event.get("event_id", fallback_id))[:120]
                        failure = db.get(EventFailure, (handler, key))
                        if not failure:
                            failure = EventFailure(handler=handler, event_id=key, attempts=0, error="", payload=event)
                            db.add(failure)
                        failure.attempts += 1
                        failure.error = type(error).__name__ + ": " + str(error)[:400]
                        failure.updated_at = now()
                        failure.quarantined = failure.attempts >= 10
                        quarantined = failure.quarantined
                    if quarantined:
                        log.error("Событие помещено в карантин: %s, %s", handler, key)
                        consumer.commit(message=message, asynchronous=False)
                        continue
                except Exception:
                    log.exception("Не удалось сохранить ошибку обработки")
                consumer.seek(TopicPartition(message.topic(), message.partition(), message.offset()))
                stop.wait(2)
    finally:
        consumer.close()


def run_workers(stop, selected=None):
    log.info("Запущены обработчики %s; Kafka: %s", ", ".join(selected or HANDLERS), settings().kafka_bootstrap_servers)
    producer = Producer({"bootstrap.servers": settings().kafka_bootstrap_servers, "enable.idempotence": True, "acks": "all", "message.timeout.ms": 10000}, logger=log)
    threads = [threading.Thread(target=consumer_loop, args=(handler, stop), name=handler) for handler in (selected or HANDLERS)]
    for thread in threads:
        thread.start()
    try:
        while not stop.is_set():
            if any(not thread.is_alive() for thread in threads):
                raise RuntimeError("Один из обработчиков завершился")
            try:
                worked = publish_one(producer)
            except Exception:
                log.exception("Ошибка публикации из outbox")
                worked = False
            if not worked:
                stop.wait(0.5)
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=15)
