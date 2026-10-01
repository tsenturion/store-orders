import logging
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Header, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func, delete, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session as DBSession
from polka.config import settings
from polka.db import session_dependency, engine
from polka.models import User, AuthSession, Product, Order, FulfillmentTask, StockMovement, Notification, Document, SalesFact, now
from polka.schemas import Login, Register, Checkout, ProductInput, PickItem, Transition
from polka.security import authenticate, create_session, hash_password, verify_password, token_hash
from polka.services import product_dict, order_dict, order_query, create_order, get_order, cancel_order, transition
from polka.reports import sales_excel
from polka.logging_config import configure_logging

log = logging.getLogger(__name__)
static = Path(__file__).parent / "static"
DB = Annotated[DBSession, Depends(session_dependency)]
login_attempts = defaultdict(deque)


@asynccontextmanager
async def lifespan(app):
    configure_logging("api")
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    log.info("API магазина запущено")
    yield
    engine.dispose()


app = FastAPI(title="Полка — магазин и склад", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=static), name="static")


@app.middleware("http")
async def security_headers(request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
            return JSONResponse({"detail": "Запрос с другого сайта запрещён"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path == "/":
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def invalid_input(request, error):
    fields = [".".join(str(x) for x in e["loc"][1:]) for e in error.errors()]
    return JSONResponse({"detail": "Проверьте заполнение полей: " + ", ".join(fields)}, status_code=422)


@app.exception_handler(IntegrityError)
async def conflict(request, error):
    log.warning("Конфликт данных: %s", request.url.path)
    return JSONResponse({"detail": "Данные уже существуют или были изменены. Обновите страницу"}, status_code=409)


@app.exception_handler(SQLAlchemyError)
async def database_error(request, error):
    log.error("Ошибка БД: путь=%s тип=%s", request.url.path, type(error).__name__)
    return JSONResponse({"detail": "Сервис временно недоступен. Повторите действие позже"}, status_code=503)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(static / "index.html")


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready(db: DB):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


def user_dict(user):
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role}


def set_cookie(response, token):
    response.set_cookie("polka_session", token, httponly=True, secure=settings().cookie_secure, samesite="strict", max_age=7*86400, path="/")


def login_limit(request):
    key = request.client.host
    queue = login_attempts[key]
    current = time.monotonic()
    while queue and current - queue[0] > 60:
        queue.popleft()
    if len(queue) >= 30:
        raise HTTPException(429, "Слишком много попыток. Подождите минуту")
    queue.append(current)
    if len(login_attempts) > 10000:
        login_attempts.clear()


@app.post("/api/auth/register", status_code=201)
def register(data: Register, request: Request, response: Response, db: DB):
    login_limit(request)
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(409, "Эта почта уже зарегистрирована")
    user = User(email=data.email, name=data.name, password_hash=hash_password(data.password), role="customer")
    db.add(user)
    db.flush()
    token, csrf = create_session(db, user)
    db.commit()
    set_cookie(response, token)
    return {"user": user_dict(user), "csrf": csrf}


@app.post("/api/auth/login")
def login(data: Login, request: Request, response: Response, db: DB):
    login_limit(request)
    user = db.scalar(select(User).where(User.email == data.email))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Неверная почта или пароль")
    prior = request.cookies.get("polka_session")
    if prior:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(prior)))
    db.execute(delete(AuthSession).where(AuthSession.expires_at < now()))
    token, csrf = create_session(db, user)
    db.commit()
    set_cookie(response, token)
    return {"user": user_dict(user), "csrf": csrf}


@app.get("/api/auth/me")
def me(request: Request, db: DB):
    user, auth = authenticate(request, db)
    return {"user": user_dict(user), "csrf": auth.csrf}


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, db: DB):
    _, auth = authenticate(request, db)
    db.delete(auth)
    db.commit()
    response = Response(status_code=204)
    response.delete_cookie("polka_session", path="/")
    return response


@app.get("/api/products")
def products(db: DB, q: str = Query(default="", max_length=100), category: str = Query(default="", max_length=60)):
    query = select(Product).where(Product.active)
    if q:
        query = query.where(Product.name.icontains(q, autoescape=True))
    if category:
        query = query.where(Product.category == category)
    categories = db.scalars(select(Product.category).where(Product.active).distinct().order_by(Product.category)).all()
    return {"products": [product_dict(p) for p in db.scalars(query.order_by(Product.id).limit(500))], "categories": categories}


@app.post("/api/orders", status_code=201)
def checkout(data: Checkout, request: Request, db: DB, idempotency_key: Annotated[str, Header(min_length=8, max_length=64)]):
    user, _ = authenticate(request, db, ["customer"])
    order = create_order(db, user, data, idempotency_key)
    db.commit()
    return order_dict(db, order)


@app.get("/api/orders")
def orders(request: Request, db: DB):
    user, _ = authenticate(request, db)
    query = order_query()
    if user.role == "customer":
        query = query.where(Order.customer_id == user.id)
    return [order_dict(db, order) for order in db.scalars(query.order_by(Order.id.desc()).limit(200))]


@app.get("/api/orders/{order_id}")
def order_details(order_id: int, request: Request, db: DB):
    user, _ = authenticate(request, db)
    return order_dict(db, get_order(db, order_id, user))


@app.post("/api/orders/{order_id}/cancel")
def cancel(order_id: int, request: Request, db: DB):
    user, _ = authenticate(request, db, ["customer", "manager"])
    order = get_order(db, order_id, user, lock=True)
    cancel_order(db, order, user)
    db.commit()
    return order_dict(db, order)


@app.get("/api/orders/{order_id}/document.pdf")
@app.head("/api/orders/{order_id}/document.pdf", include_in_schema=False)
def pdf(order_id: int, request: Request, db: DB):
    user, _ = authenticate(request, db)
    get_order(db, order_id, user)
    document = db.get(Document, order_id)
    if not document:
        raise HTTPException(409, "Документ ещё готовится")
    return Response(document.content if request.method == "GET" else b"", media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="order-{order_id}.pdf"'})


@app.get("/api/warehouse/orders")
def warehouse_orders(request: Request, db: DB):
    authenticate(request, db, ["warehouse", "manager"])
    query = order_query().where(Order.id.in_(select(FulfillmentTask.order_id)), Order.status.in_(["queued", "picking", "ready", "shipped"])).order_by(Order.id).limit(200)
    return [order_dict(db, order) for order in db.scalars(query)]


@app.post("/api/warehouse/orders/{order_id}/status")
def change_status(order_id: int, data: Transition, request: Request, db: DB):
    user, _ = authenticate(request, db, ["warehouse", "manager"])
    order = get_order(db, order_id, user, lock=True)
    transition(db, order, user, data.status)
    db.commit()
    return order_dict(db, order)


@app.post("/api/warehouse/orders/{order_id}/items/{item_id}")
def pick(order_id: int, item_id: int, data: PickItem, request: Request, db: DB):
    user, _ = authenticate(request, db, ["warehouse", "manager"])
    order = get_order(db, order_id, user, lock=True)
    task = db.scalar(select(FulfillmentTask).where(FulfillmentTask.order_id == order.id))
    if order.status != "picking" or not task or (task.assignee_id != user.id and user.role != "manager"):
        raise HTTPException(409, "Сначала возьмите заказ в сборку")
    item = next((i for i in order.items if i.id == item_id), None)
    if not item or data.picked > item.quantity:
        raise HTTPException(422, "Некорректное количество")
    item.picked = data.picked
    db.commit()
    return order_dict(db, order)


@app.get("/api/manager/products")
def manager_products(request: Request, db: DB):
    authenticate(request, db, ["manager"])
    return [product_dict(p) for p in db.scalars(select(Product).order_by(Product.id).limit(1000))]


@app.post("/api/manager/products", status_code=201)
def create_product(data: ProductInput, request: Request, db: DB):
    user, _ = authenticate(request, db, ["manager"])
    product = Product(**data.model_dump())
    db.add(product)
    db.flush()
    db.add(StockMovement(product_id=product.id, delta=product.stock, reason="Начальные остатки", actor=user.name))
    db.commit()
    return product_dict(product)


@app.put("/api/manager/products/{product_id}")
def edit_product(product_id: int, data: ProductInput, request: Request, db: DB):
    user, _ = authenticate(request, db, ["manager"])
    product = db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if not product:
        raise HTTPException(404, "Товар не найден")
    if data.stock < product.reserved:
        raise HTTPException(409, f"Зарезервировано {product.reserved} шт. Остаток не может быть меньше резерва")
    if data.stock != product.stock:
        db.add(StockMovement(product_id=product.id, delta=data.stock-product.stock, reason="Корректировка остатков", actor=user.name))
    for key, value in data.model_dump().items():
        setattr(product, key, value)
    db.commit()
    return product_dict(product)


@app.get("/api/manager/stock-movements")
def movements(request: Request, db: DB):
    authenticate(request, db, ["manager"])
    rows = db.execute(select(StockMovement, Product.name).join(Product, Product.id == StockMovement.product_id).order_by(StockMovement.id.desc()).limit(100)).all()
    return [{"id": row.id, "product": name, "delta": row.delta, "reason": row.reason, "actor": row.actor, "created_at": row.created_at.isoformat()} for row, name in rows]


@app.get("/api/manager/dashboard")
def dashboard(request: Request, db: DB):
    authenticate(request, db, ["manager"])
    counts = dict(db.execute(select(Order.status, func.count()).group_by(Order.status)).all())
    revenue = db.scalar(select(func.coalesce(func.sum(SalesFact.total), 0)))
    day = func.date_trunc("day", SalesFact.delivered_at, "UTC")
    since = now().replace(hour=0, minute=0, second=0, microsecond=0)-timedelta(days=6)
    rows = db.execute(select(day, func.sum(SalesFact.total)).where(SalesFact.delivered_at >= since).group_by(day).order_by(day)).all()
    return {"counts": counts, "revenue": str(revenue), "sales": [{"day": stamp.astimezone(timezone.utc).date().isoformat(), "total": str(total)} for stamp, total in rows], "low_stock": [product_dict(p) for p in db.scalars(select(Product).where(Product.active, Product.stock-Product.reserved < 5))]}


@app.get("/api/manager/reports.xlsx")
@app.head("/api/manager/reports.xlsx", include_in_schema=False)
def excel(request: Request, db: DB, date_from: date | None = None, date_to: date | None = None):
    authenticate(request, db, ["manager"])
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Начало периода позже окончания")
    query = (select(Order.id) if request.method == "HEAD" else order_query()).where(Order.status == "delivered")
    if date_from:
        query = query.where(Order.delivered_at >= datetime.combine(date_from, dt_time.min, timezone.utc))
    if date_to:
        query = query.where(Order.delivered_at < datetime.combine(date_to+timedelta(days=1), dt_time.min, timezone.utc))
    rows = db.scalars(query.order_by(Order.delivered_at).limit(10001)).all()
    if len(rows) > 10000:
        raise HTTPException(422, "Сузьте период: в отчёте больше 10 000 заказов")
    return Response(sales_excel(rows) if request.method == "GET" else b"", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="polka-sales.xlsx"'})


@app.get("/api/notifications")
def notifications(request: Request, db: DB):
    user, _ = authenticate(request, db)
    return [{"id": n.id, "order_id": n.order_id, "text": n.text, "read": n.read, "created_at": n.created_at.isoformat()} for n in db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(50))]


@app.post("/api/notifications/read", status_code=204)
def read_notifications(request: Request, db: DB):
    user, _ = authenticate(request, db)
    for notification in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.read == False)):
        notification.read = True
    db.commit()
    return Response(status_code=204)
