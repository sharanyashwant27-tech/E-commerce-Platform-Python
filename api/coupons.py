"""Coupon endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.deps import get_current_active_user, require_roles
from models.entities import User
from models.session import get_db
from schemas.cart import CouponCreate, CouponOut, CouponValidate
from services.discount_service import DiscountService
from utils.enums import UserRole

router = APIRouter(tags=["Coupons"])


@router.post("/apply-coupon")
async def apply_coupon(
    payload: CouponValidate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_active_user)],
):
    coupon, discount = await DiscountService(db).validate(
        payload.code, payload.order_amount
    )
    return {
        "code": coupon.code,
        "discount_amount": discount,
        "discount_type": coupon.discount_type,
        "discount_value": coupon.discount_value,
        "message": "Coupon applied successfully",
    }


@router.post("/coupons", response_model=CouponOut, status_code=201)
async def create_coupon(
    payload: CouponCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
):
    return await DiscountService(db).create(**payload.model_dump())
