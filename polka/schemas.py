import re
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Введите корректную почту")
        return value.lower()


class Register(Login):
    name: str = Field(min_length=2, max_length=100)


class CartItem(StrictModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=100)


class Checkout(StrictModel):
    items: list[CartItem] = Field(min_length=1, max_length=30)
    recipient: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=7, max_length=30)
    address: str = Field(min_length=8, max_length=300)
    note: str = Field(default="", max_length=500)

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, value):
        digits = re.sub(r"\D", "", value)
        if not 10 <= len(digits) <= 15:
            raise ValueError("Введите телефон с кодом страны или города")
        return value


class ProductInput(StrictModel):
    sku: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=5, max_length=2000)
    category: str = Field(min_length=2, max_length=60)
    image: str = Field(default="vase", pattern=r"^(lamp|vase|chair|bottle|basket|clock|blanket|mug)$")
    price: Decimal = Field(gt=0, le=10000000, max_digits=12, decimal_places=2)
    stock: int = Field(ge=0, le=100000)
    active: bool = True


class PickItem(StrictModel):
    picked: int = Field(ge=0, le=100)


class Transition(StrictModel):
    status: str = Field(pattern=r"^(picking|ready|shipped|delivered)$")
