import logging
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from polka.models import User, Product, Order, OrderItem, OrderHistory, StockMovement, FulfillmentTask, OutboxEvent, Document, now

log = logging.getLogger(__name__)
STATUS_LABELS = {"created": "Оформлен", "queued": "Ожидает сборки", "picking": "Собирается", "ready": "Готов к отправке", "shipped": "В доставке", "delivered": "Доставлен", "cancelled": "Отменён"}


def product_dict(product):
    return {"id": product.id, "sku": product.sku, "name": product.name, "description": product.description, "category": product.category, "image": product.image, "price": str(product.price), "stock": product.stock, "reserved": product.reserved, "available": product.stock - product.reserved, "active": product.active}


def order_query():
    return select(Order).options(selectinload(Order.items), selectinload(Order.history))


def order_dict(db, order):
    task = db.scalar(select(FulfillmentTask).where(FulfillmentTask.order_id == order.id))
    return {"id": order.id, "status": order.status, "status_label": STATUS_LABELS[order.status], "total": str(order.total), "recipient": order.recipient, "phone": order.phone, "address": order.address, "note": order.note, "created_at": order.created_at.isoformat(), "assignee_id": task.assignee_id if task else None, "document_ready": db.get(Document, order.id) is not None, "items": [{"id": item.id, "product_id": item.product_id, "name": item.name, "price": str(item.price), "quantity": item.quantity, "picked": item.picked} for item in order.items], "history": [{"status": entry.status, "label": STATUS_LABELS[entry.status], "actor": entry.actor, "created_at": entry.created_at.isoformat()} for entry in order.history]}


def emit(db, order, kind):
    db.add(OutboxEvent(order_id=order.id, kind=kind, payload={"order_id": order.id, "customer_id": order.customer_id, "status": order.status}))


def set_status(db, order, status, actor):
    order.status = status
    order.history.append(OrderHistory(status=status, actor=actor))
    if status == "delivered":
        order.delivered_at = now()
    emit(db, order, f"order.{status}")


def create_order(db, user, data, key):
    # Блокировка покупателя сериализует повторные запросы с одним ключом.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    existing = db.scalar(order_query().where(Order.customer_id == user.id, Order.idempotency_key == key))
    if existing:
        return existing
    quantities = {}
    for item in data.items:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity
    if any(value > 100 for value in quantities.values()):
        raise HTTPException(422, "Не больше 100 единиц одного товара")
    products = db.scalars(select(Product).where(Product.id.in_(sorted(quantities))).order_by(Product.id).with_for_update()).all()
    if len(products) != len(quantities) or any(not p.active for p in products):
        raise HTTPException(409, "Один из товаров больше недоступен")
    for p in products:
        if p.stock - p.reserved < quantities[p.id]:
            raise HTTPException(409, f"Товар «{p.name}»: доступно {p.stock - p.reserved} шт.")
    order = Order(customer_id=user.id, idempotency_key=key, status="created", total=Decimal("0"), recipient=data.recipient, phone=data.phone, address=data.address, note=data.note)
    db.add(order)
    for p in products:
        quantity = quantities[p.id]
        p.reserved += quantity
        order.total += p.price * quantity
        order.items.append(OrderItem(product_id=p.id, name=p.name, price=p.price, quantity=quantity))
    db.flush()
    order.history.append(OrderHistory(status="created", actor=user.name))
    emit(db, order, "order.created")
    log.info("Заказ %s оформлен; покупатель %s; позиций %s", order.id, user.id, len(products))
    return order


def get_order(db, order_id, user, lock=False):
    query = order_query().where(Order.id == order_id)
    if lock:
        query = query.with_for_update()
    order = db.scalar(query)
    if not order or (user.role == "customer" and order.customer_id != user.id):
        raise HTTPException(404, "Заказ не найден")
    return order


def cancel_order(db, order, user):
    if order.status == "cancelled":
        return
    if order.status not in ("created", "queued"):
        raise HTTPException(409, "Заказ уже собирается. Отмена недоступна")
    products = db.scalars(select(Product).where(Product.id.in_([i.product_id for i in order.items])).order_by(Product.id).with_for_update()).all()
    quantities = {item.product_id: item.quantity for item in order.items}
    for p in products:
        p.reserved -= quantities[p.id]
    set_status(db, order, "cancelled", user.name)
    log.info("Заказ %s отменён; резервы освобождены", order.id)


def transition(db, order, user, target):
    if order.status == target:
        return
    allowed = {"queued": "picking", "picking": "ready", "ready": "shipped", "shipped": "delivered"}
    if allowed.get(order.status) != target:
        raise HTTPException(409, "Недопустимый переход статуса")
    if target == "delivered" and user.role != "manager":
        raise HTTPException(403, "Доставку подтверждает менеджер")
    task = db.scalar(select(FulfillmentTask).where(FulfillmentTask.order_id == order.id).with_for_update())
    if not task:
        raise HTTPException(409, "Задание на сборку ещё не создано")
    if task.assignee_id and task.assignee_id != user.id and user.role != "manager":
        raise HTTPException(409, "Заказ собирает другой сотрудник")
    if target == "picking":
        task.assignee_id = user.id
    if target == "ready" and any(i.picked != i.quantity for i in order.items):
        raise HTTPException(409, "Сначала отметьте все товары как собранные")
    if target == "shipped":
        products = db.scalars(select(Product).where(Product.id.in_([i.product_id for i in order.items])).order_by(Product.id).with_for_update()).all()
        quantities = {item.product_id: item.quantity for item in order.items}
        for p in products:
            quantity = quantities[p.id]
            p.stock -= quantity
            p.reserved -= quantity
            db.add(StockMovement(product_id=p.id, delta=-quantity, reason=f"Отправка заказа №{order.id}", actor=user.name))
    set_status(db, order, target, user.name)
    log.info("Заказ %s: %s; сотрудник %s", order.id, target, user.id)
