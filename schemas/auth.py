"""Auth-related Pydantic schemas."""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from utils.enums import UserRole


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)
    phone: Optional[str] = None
    role: UserRole = UserRole.CUSTOMER
    store_name: Optional[str] = None  # required when role=seller


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    role: UserRole
    is_active: bool
    is_verified: bool
    avatar_url: Optional[str] = None

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    message: str
