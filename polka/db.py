from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from polka.config import settings


class Base(DeclarativeBase):
    metadata = MetaData(schema=settings().database_schema)


engine = create_engine(settings().database_url, pool_pre_ping=True, pool_size=8, max_overflow=8, connect_args={"connect_timeout": 8})
Session = sessionmaker(engine, expire_on_commit=False)


def session_dependency():
    with Session() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
