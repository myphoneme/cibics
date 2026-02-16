import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.config import get_settings

pwd_context = CryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')
settings = get_settings()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if hashed_password.startswith('sha256$'):
        expected = 'sha256$' + hashlib.sha256(plain_password.encode('utf-8')).hexdigest()
        return expected == hashed_password

    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {'sub': subject, 'exp': expire}
    return jwt.encode(payload, settings.secret_key, algorithm='HS256')
