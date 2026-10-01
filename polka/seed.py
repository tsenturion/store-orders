from decimal import Decimal
from sqlalchemy import select
from polka.db import Session
from polka.models import User, Product, StockMovement
from polka.security import hash_password


CATALOG = [
    ("LMP-01", "Лампа «Тихий вечер»", "Свет", "lamp", "3890", 18, "Тёплый рассеянный свет, матовая керамика и тканевый абажур. Для чтения и спокойных вечеров."),
    ("VAS-01", "Ваза «Песок»", "Декор", "vase", "1490", 24, "Керамическая ваза с фактурной поверхностью. Хороша с сухоцветами и сама по себе."),
    ("CHR-01", "Стул «Линия»", "Мебель", "chair", "7990", 8, "Массив дерева, мягкое сиденье и простая форма. Для рабочего стола или обеденной зоны."),
    ("BTL-01", "Графин «Утро»", "Кухня", "bottle", "2190", 16, "Графин из прозрачного стекла с деревянной пробкой. Объём 1 литр."),
    ("BKT-01", "Корзина «Порядок»", "Хранение", "basket", "1790", 12, "Плетёная корзина для пледов, журналов и повседневных мелочей. Натуральные материалы."),
    ("CLK-01", "Часы «Круг»", "Декор", "clock", "2590", 10, "Тихий механизм и лаконичный циферблат. Диаметр 28 см."),
    ("BLK-01", "Плед «Облако»", "Текстиль", "blanket", "3290", 20, "Мягкий хлопковый плед в природных оттенках. Размер 140 × 200 см."),
    ("MUG-01", "Чашка «Каждый день»", "Кухня", "mug", "890", 30, "Керамическая чашка с удобной ручкой. Объём 350 мл, можно мыть в посудомоечной машине."),
]


def seed():
    with Session.begin() as db:
        for email, name, role, password in [("customer@polka.local", "Анна Смирнова", "customer", "customer1234"), ("warehouse@polka.local", "Ольга Петрова", "warehouse", "warehouse1234"), ("manager@polka.local", "Илья Волков", "manager", "manager1234")]:
            if not db.scalar(select(User).where(User.email == email)):
                db.add(User(email=email, name=name, role=role, password_hash=hash_password(password)))
        for sku, name, category, image, price, stock, description in CATALOG:
            if not db.scalar(select(Product).where(Product.sku == sku)):
                product = Product(sku=sku, name=name, category=category, image=image, price=Decimal(price), stock=stock, description=description)
                db.add(product)
                db.flush()
                db.add(StockMovement(product_id=product.id, delta=stock, reason="Начальные остатки", actor="Магазин"))
