import re
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://postgres:admin@192.168.0.33:5432/postgres"
    database_schema: str = "polka"
    kafka_bootstrap_servers: str = "192.168.0.34:9092"
    kafka_topic: str = "polka.orders"
    host: str = "127.0.0.1"
    port: int = 8000
    cookie_secure: bool = False
    seed_demo: bool = True
    log_dir: str = "logs"

    @field_validator("database_schema")
    @classmethod
    def valid_schema(cls, value):
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,50}", value):
            raise ValueError("Недопустимое имя схемы")
        return value


@lru_cache
def settings():
    return Settings()
