from alembic import context
from polka.db import Base, engine
from polka import models
from polka.config import settings


def include_name(name, type_, parent_names):
    return name == settings().database_schema if type_ == "schema" else True


with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, include_schemas=True, include_name=include_name, version_table_schema=settings().database_schema)
    with context.begin_transaction():
        context.run_migrations()
