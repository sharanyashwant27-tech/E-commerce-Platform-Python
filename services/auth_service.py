"""Authentication and user management service."""

import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from utils.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from auth.security import (
    create_access_token,
    create_email_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_email_token,
    verify_password,
)
from utils.enums import UserRole
from models.entities import Cart, SellerProfile, User


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text).strip("-")


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(
        self,
        email: str,
        password: str,
        full_name: str,
        phone: Optional[str] = None,
        role: UserRole = UserRole.CUSTOMER,
        store_name: Optional[str] = None,
    ) -> User:
        existing = await self.db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise ConflictError("Email already registered")

        if role == UserRole.ADMIN:
            raise ValidationError("Cannot self-register as admin")

        if role == UserRole.SELLER and not store_name:
            raise ValidationError("store_name is required for seller registration")

        user = User(
            email=email.lower(),
            hashed_password=hash_password(password),
            full_name=full_name,
            phone=phone,
            role=role,
            is_verified=False,
        )
        self.db.add(user)
        await self.db.flush()

        if role == UserRole.CUSTOMER:
            self.db.add(Cart(user_id=user.id))

        if role == UserRole.SELLER and store_name:
            base = slugify(store_name)
            slug = base
            n = 1
            while True:
                check = await self.db.execute(
                    select(SellerProfile).where(SellerProfile.slug == slug)
                )
                if not check.scalar_one_or_none():
                    break
                n += 1
                slug = f"{base}-{n}"
            self.db.add(
                SellerProfile(
                    user_id=user.id,
                    store_name=store_name,
                    slug=slug,
                    is_approved=False,
                )
            )
            self.db.add(Cart(user_id=user.id))

        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> tuple[str, str, User]:
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Incorrect email or password")
        if not user.is_active:
            raise UnauthorizedError("Account is deactivated")
        access = create_access_token(user.id, user.role.value)
        refresh = create_refresh_token(user.id, user.role.value)
        return access, refresh, user

    async def refresh_tokens(self, refresh_token: str) -> tuple[str, str]:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise UnauthorizedError("Invalid refresh token")
            user_id = int(payload["sub"])
        except Exception as exc:
            raise UnauthorizedError("Invalid refresh token") from exc

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise UnauthorizedError("User not found or inactive")
        return (
            create_access_token(user.id, user.role.value),
            create_refresh_token(user.id, user.role.value),
        )

    def verification_token(self, email: str) -> str:
        return create_email_token(email, "verify", hours=48)

    def reset_token(self, email: str) -> str:
        return create_email_token(email, "reset", hours=2)

    async def verify_email(self, token: str) -> User:
        email = verify_email_token(token, "verify")
        if not email:
            raise ValidationError("Invalid or expired verification token")
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User not found")
        user.is_verified = True
        await self.db.flush()
        return user

    async def reset_password(self, token: str, new_password: str) -> User:
        email = verify_email_token(token, "reset")
        if not email:
            raise ValidationError("Invalid or expired reset token")
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User not found")
        user.hashed_password = hash_password(new_password)
        await self.db.flush()
        return user

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_user_with_profile(self, user_id: int) -> User:
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.seller_profile), selectinload(User.addresses))
            .where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User not found")
        return user
