"""Проверки используют отдельную временную схему на настоящем PostgreSQL."""
import os
import uuid
import pytest

TEST_SCHEMA = "polka_test_" + uuid.uuid4().hex[:12]
os.environ["DATABASE_SCHEMA"] = TEST_SCHEMA
os.environ["SEED_DEMO"] = "false"
os.environ["LOG_DIR"] = ".runtime/test-logs"

from sqlalchemy import text, select
from fastapi.testclient import TestClient
from polka.db import engine, Session, Base
from polka.cli import migrate
from polka.api import app
from polka.models import User, Product
from polka.security import hash_password


@pytest.fixture(scope="session", autouse=True)
def schema():
    migrate()
    yield
    assert TEST_SCHEMA.startswith("polka_test_") and len(TEST_SCHEMA) == 23
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA "{TEST_SCHEMA}" CASCADE'))
    engine.dispose()


@pytest.fixture(autouse=True)
def clear_tables(schema):
    tables = ", ".join(f'"{TEST_SCHEMA}"."{table.name}"' for table in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def clients():
    clients = {}
    with Session.begin() as db:
        for role in ("customer", "warehouse", "manager", "other"):
            db.add(User(email=f"{role}@test.local", name=role, role="customer" if role == "other" else role, password_hash=hash_password("password1234")))
        db.add(Product(sku="TEST-01", name="Тестовая ваза", description="Керамическая ваза", category="Декор", image="vase", price="1490.50", stock=3))
    for role in ("customer", "warehouse", "manager", "other"):
        client = TestClient(app)
        response = client.post("/api/auth/login", json={"email": f"{role}@test.local", "password": "password1234"})
        assert response.status_code == 200, response.text
        client.headers["X-CSRF-Token"] = response.json()["csrf"]
        clients[role] = client
    yield clients
    for client in clients.values():
        client.close()


@pytest.fixture
def checkout_payload():
    return {"items": [{"product_id": 1, "quantity": 1}], "recipient": "Тестовый покупатель", "phone": "+7 999 123-45-67", "address": "Екатеринбург, улица Мира, дом 1", "note": ""}
