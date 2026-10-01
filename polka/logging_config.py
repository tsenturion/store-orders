import logging
import os
import time
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from polka.config import settings


def configure_logging(component):
    directory = Path(settings().log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    for old in directory.glob(f"{component}.log*"):
        if old.is_file() and old.stat().st_mtime < time.time() - 30*86400:
            old.unlink()
    handler = TimedRotatingFileHandler(directory / f"{component}.log", when="midnight", backupCount=29, encoding="utf-8", utc=True)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler] if os.environ.get("POLKA_BACKGROUND") == "1" else [handler, console], force=True)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
