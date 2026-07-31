"""JWT authentication, password hashing, and token utilities."""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from config.settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(
    subject: str | int,
    role: str,
    expires_delta: Optional[timedelta] = None,
    extra: Optional[dict[str, Any]] = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "exp": expire,
        "type": "access",
        "jti": str(uuid4()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(subject: str | int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload = {
        "sub": str(subject),
        "role": role,
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def create_email_token(email: str, purpose: str, hours: int = 24) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=hours)
    payload = {"sub": email, "purpose": purpose, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def verify_email_token(token: str, purpose: str) -> Optional[str]:
    try:
        payload = decode_token(token)
        if payload.get("purpose") != purpose:
            return None
        return payload.get("sub")
    except JWTError:
        return None
