import hashlib
import hmac
import secrets
from datetime import timedelta
from fastapi import HTTPException, Request
from sqlalchemy import select
from polka.models import AuthSession, User, now


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password, encoded):
    try:
        _, salt, expected = encoded.split("$")
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db, user):
    token = secrets.token_urlsafe(32)
    session = AuthSession(token_hash=token_hash(token), csrf=secrets.token_urlsafe(24), user_id=user.id, expires_at=now() + timedelta(days=7))
    db.add(session)
    return token, session.csrf


def authenticate(request: Request, db, roles=None):
    token = request.cookies.get("polka_session", "")
    auth = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token), AuthSession.expires_at > now())) if token else None
    if not auth:
        raise HTTPException(401, "Войдите в аккаунт")
    user = db.get(User, auth.user_id)
    if roles and user.role not in roles:
        raise HTTPException(403, "Недостаточно прав")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        csrf = request.headers.get("X-CSRF-Token", "")
        if not csrf or not hmac.compare_digest(csrf, auth.csrf):
            raise HTTPException(403, "Обновите страницу и повторите действие")
    return user, auth
