"""Coupon and discount engine."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utils.exceptions import NotFoundError, ValidationError
from models.entities import Coupon


class DiscountService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_code(self, code: str) -> Coupon:
        result = await self.db.execute(
            select(Coupon).where(Coupon.code == code.upper())
        )
        coupon = result.scalar_one_or_none()
        if not coupon:
            raise NotFoundError("Coupon not found")
        return coupon

    def calculate_discount(self, coupon: Coupon, order_amount: Decimal) -> Decimal:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if not coupon.is_active:
            raise ValidationError("Coupon is inactive")
        if coupon.starts_at and now < coupon.starts_at:
            raise ValidationError("Coupon is not yet active")
        if coupon.ends_at and now > coupon.ends_at:
            raise ValidationError("Coupon has expired")
        if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
            raise ValidationError("Coupon usage limit reached")
        if order_amount < coupon.min_order_amount:
            raise ValidationError(
                f"Minimum order amount is {coupon.min_order_amount}"
            )

        if coupon.discount_type == "percent":
            discount = (order_amount * coupon.discount_value) / Decimal("100")
            if coupon.max_discount is not None:
                discount = min(discount, coupon.max_discount)
        else:
            discount = coupon.discount_value

        return min(discount.quantize(Decimal("0.01")), order_amount)

    async def validate(self, code: str, order_amount: Decimal) -> tuple[Coupon, Decimal]:
        coupon = await self.get_by_code(code)
        discount = self.calculate_discount(coupon, order_amount)
        return coupon, discount

    async def create(
        self,
        code: str,
        discount_type: str,
        discount_value: Decimal,
        description: Optional[str] = None,
        min_order_amount: Decimal = Decimal("0"),
        max_discount: Optional[Decimal] = None,
        usage_limit: Optional[int] = None,
        is_active: bool = True,
    ) -> Coupon:
        existing = await self.db.execute(
            select(Coupon).where(Coupon.code == code.upper())
        )
        if existing.scalar_one_or_none():
            raise ValidationError("Coupon code already exists")
        coupon = Coupon(
            code=code.upper(),
            description=description,
            discount_type=discount_type,
            discount_value=discount_value,
            min_order_amount=min_order_amount,
            max_discount=max_discount,
            usage_limit=usage_limit,
            is_active=is_active,
        )
        self.db.add(coupon)
        await self.db.flush()
        await self.db.refresh(coupon)
        return coupon
