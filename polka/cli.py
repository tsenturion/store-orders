import argparse
import logging
import signal
import threading
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from polka.config import settings
from polka.db import engine
from polka.logging_config import configure_logging


def migrate():
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{settings().database_schema}"'))
    config = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    command.upgrade(config, "head")


def main():
    parser = argparse.ArgumentParser(description="Управление магазином «Полка»")
    parser.add_argument("command", choices=["init", "topic", "worker", "serve"])
    parser.add_argument("--handler", choices=["warehouse", "notifications", "analytics", "documents"])
    args = parser.parse_args()
    configure_logging({"worker": "worker", "serve": "api"}.get(args.command, "setup"))
    if args.command == "init":
        migrate()
        if settings().seed_demo:
            from polka.seed import seed
            seed()
        print("Схема магазина подготовлена")
    elif args.command == "topic":
        from polka.events import ensure_topic
        ensure_topic()
        print("Топик заказов готов")
    elif args.command == "worker":
        from polka.events import run_workers
        stop = threading.Event()
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        run_workers(stop, [args.handler] if args.handler else None)
    else:
        import uvicorn
        uvicorn.run("polka.api:app", host=settings().host, port=settings().port, log_config=None, access_log=False)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.getLogger(__name__).exception("Процесс магазина завершился с ошибкой")
        raise SystemExit(1)
