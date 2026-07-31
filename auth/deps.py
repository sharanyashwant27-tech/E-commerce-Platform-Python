"""Authentication and authorization dependencies."""

from typing import Annotated, Callable, Optional

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from utils.exceptions import ForbiddenError, UnauthorizedError
from auth.security import decode_token
from utils.enums import UserRole
from models.entities import User
from models.session import get_db

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_v1_prefix}/login",
    auto_error=False,
)


def _extract_token(request: Request, bearer: Optional[str]) -> Optional[str]:
    if bearer:
        return bearer
    return request.cookies.get("access_token")


async def _load_user(token: str, db: AsyncSession) -> User:
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise UnauthorizedError("Invalid token type")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise UnauthorizedError("Could not validate credentials") from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedError("User not found")
    return user


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    resolved = _extract_token(request, token)
    if not resolved:
        raise UnauthorizedError("Missing authentication token")
    return await _load_user(resolved, db)


async def get_current_active_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not user.is_active:
        raise ForbiddenError("Inactive user account")
    return user


def require_roles(*roles: UserRole) -> Callable:
    async def _checker(
        user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if user.role not in roles and user.role != UserRole.ADMIN:
            allowed = ", ".join(r.value for r in roles)
            raise ForbiddenError(f"Requires one of roles: {allowed}")
        return user

    return _checker


async def get_optional_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    resolved = _extract_token(request, token)
    if not resolved:
        return None
    try:
        return await _load_user(resolved, db)
    except UnauthorizedError:
        return None
