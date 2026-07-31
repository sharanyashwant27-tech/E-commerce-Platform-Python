"""Cart, wishlist, coupon schemas."""

from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class CartItemAdd(BaseModel):
    variant_id: int
    quantity: int = Field(ge=1, default=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1)


class CartUpdateRequest(BaseModel):
    item_id: int
    quantity: int = Field(ge=1)


class CartRemoveRequest(BaseModel):
    item_id: int


class CartItemOut(BaseModel):
    id: int
    variant_id: int
    quantity: int
    product_name: str
    variant_name: str
    unit_price: Decimal
    line_total: Decimal
    stock: int
    image_url: Optional[str] = None


class CartOut(BaseModel):
    id: int
    items: List[CartItemOut]
    subtotal: Decimal
    item_count: int


class WishlistAdd(BaseModel):
    product_id: int


class WishlistItemOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    slug: str
    base_price: Decimal
    image_url: Optional[str] = None


class CouponCreate(BaseModel):
    code: str
    description: Optional[str] = None
    discount_type: str = Field(pattern="^(percent|fixed)$")
    discount_value: Decimal = Field(gt=0)
    min_order_amount: Decimal = Decimal("0")
    max_discount: Optional[Decimal] = None
    usage_limit: Optional[int] = None
    is_active: bool = True


class CouponOut(BaseModel):
    id: int
    code: str
    description: Optional[str] = None
    discount_type: str
    discount_value: Decimal
    min_order_amount: Decimal
    max_discount: Optional[Decimal] = None
    usage_limit: Optional[int] = None
    used_count: int
    is_active: bool

    model_config = {"from_attributes": True}


class CouponValidate(BaseModel):
    code: str
    order_amount: Decimal
