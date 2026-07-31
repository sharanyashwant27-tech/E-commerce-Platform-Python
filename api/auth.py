"""Authentication endpoints — register, login, logout, password reset."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from auth.deps import get_current_active_user
from config.settings import settings
from models.entities import User
from models.session import get_db
from schemas.auth import (
    MessageOut,
    PasswordResetConfirm,
    PasswordResetRequest,
    Token,
    TokenRefresh,
    UserOut,
    UserRegister,
    UserLogin,
)
from services.auth_service import AuthService
from utils.email import send_email
from utils.logging import get_logger

router = APIRouter(tags=["Authentication"])
logger = get_logger(__name__)


@router.post("/register", response_model=UserOut, status_code=201)
async def register(
    payload: UserRegister,
    background: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = AuthService(db)
    user = await service.register(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        phone=payload.phone,
        role=payload.role,
        store_name=payload.store_name,
    )
    token = service.verification_token(user.email)
    verify_url = f"{settings.base_url}/verify-email?token={token}"
    background.add_task(
        send_email,
        user.email,
        "Verify your ShopSphere account",
        f"<p>Hi {user.full_name},</p><p>Please verify your email: "
        f'<a href="{verify_url}">Verify Email</a></p>',
    )
    return user


@router.post("/login", response_model=Token)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = AuthService(db)
    access, refresh, _ = await service.authenticate(form.username, form.password)
    return Token(access_token=access, refresh_token=refresh)


@router.post("/login/json", response_model=Token, include_in_schema=False)
async def login_json(payload: UserLogin, db: Annotated[AsyncSession, Depends(get_db)]):
    access, refresh, _ = await AuthService(db).authenticate(payload.email, payload.password)
    return Token(access_token=access, refresh_token=refresh)


@router.post("/logout", response_model=MessageOut)
async def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return MessageOut(message="Logged out successfully")


@router.post("/forgot-password", response_model=MessageOut)
async def forgot_password(
    payload: PasswordResetRequest,
    background: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = AuthService(db)
    user = await service.get_by_email(payload.email)
    if user:
        token = service.reset_token(user.email)
        reset_url = f"{settings.base_url}/reset-password?token={token}"
        background.add_task(
            send_email,
            user.email,
            "Reset your ShopSphere password",
            f'<p>Reset your password: <a href="{reset_url}">Reset Password</a></p>'
            f"<p>This link expires in 2 hours.</p>",
        )
    return MessageOut(message="If the email exists, a reset link has been sent")


@router.post("/reset-password", response_model=MessageOut)
async def reset_password(
    payload: PasswordResetConfirm,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await AuthService(db).reset_password(payload.token, payload.new_password)
    return MessageOut(message="Password updated successfully")


@router.post("/refresh", response_model=Token)
async def refresh(payload: TokenRefresh, db: Annotated[AsyncSession, Depends(get_db)]):
    access, refresh_tok = await AuthService(db).refresh_tokens(payload.refresh_token)
    return Token(access_token=access, refresh_token=refresh_tok)


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_active_user)]):
    return user


@router.post("/verify-email", response_model=MessageOut)
async def verify_email(token: str, db: Annotated[AsyncSession, Depends(get_db)]):
    await AuthService(db).verify_email(token)
    return MessageOut(message="Email verified successfully")
