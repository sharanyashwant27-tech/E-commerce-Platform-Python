"""Admin and seller management, analytics, inventory, payments."""

from decimal import Decimal
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth.deps import require_roles
from schemas.auth import MessageOut, UserOut
from schemas.cart import CouponOut
from schemas.order import AnalyticsOut, OrderOut, PaymentOut
from schemas.product import CategoryOut, ProductListItem
from services.order_service import OrderService
from utils.exceptions import NotFoundError
from utils.enums import UserRole
from models.entities import (
    Category,
    Coupon,
    Payment,
    Product,
    ProductVariant,
    SellerProfile,
    User,
)
from models.session import get_db

router = APIRouter()


class SellerOut(BaseModel):
    id: int
    user_id: int
    store_name: str
    slug: str
    is_approved: bool
    email: Optional[str] = None

    model_config = {"from_attributes": True}


class UserStatusUpdate(BaseModel):
    is_active: bool


class InventoryRow(BaseModel):
    variant_id: int
    sku: str
    product_name: str
    stock: int
    price: Decimal


@router.get("/analytics", response_model=AnalyticsOut)
async def admin_analytics(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
):
    data = await OrderService(db).admin_analytics()
    data["recent_orders"] = [OrderOut.model_validate(o) for o in data["recent_orders"]]
    return data


@router.get("/seller/analytics", response_model=AnalyticsOut)
async def seller_analytics(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.SELLER))],
):
    return await OrderService(db).seller_analytics(user)


@router.get("/users", response_model=List[UserOut])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    role: Optional[UserRole] = None,
):
    q = select(User).order_by(User.created_at.desc())
    if role:
        q = q.where(User.role == role)
    return (await db.execute(q)).scalars().all()


@router.patch("/users/{user_id}", response_model=UserOut)
async def set_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
):
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")
    user.is_active = payload.is_active
    await db.flush()
    return user


@router.get("/sellers", response_model=List[SellerOut])
async def list_sellers(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
):
    result = await db.execute(
        select(SellerProfile).options(selectinload(SellerProfile.user)).order_by(SellerProfile.id)
    )
    sellers = result.scalars().all()
    return [
        SellerOut(
            id=s.id,
            user_id=s.user_id,
            store_name=s.store_name,
            slug=s.slug,
            is_approved=s.is_approved,
            email=s.user.email if s.user else None,
        )
        for s in sellers
    ]


@router.post("/sellers/{seller_id}/approve", response_model=MessageOut)
async def approve_seller(
    seller_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
):
    result = await db.execute(select(SellerProfile).where(SellerProfile.id == seller_id))
    seller = result.scalar_one_or_none()
    if not seller:
        raise NotFoundError("Seller not found")
    seller.is_approved = True
    await db.flush()
    return MessageOut(message=f"Seller '{seller.store_name}' approved")


@router.get("/products", response_model=List[ProductListItem])
async def admin_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
):
    result = await db.execute(
        select(Product).options(selectinload(Product.images)).order_by(Product.created_at.desc())
    )
    products = result.scalars().all()
    items = []
    for p in products:
        primary = next((i.url for i in p.images if i.is_primary), None)
        if not primary and p.images:
            primary = p.images[0].url
        items.append(
            ProductListItem(
                id=p.id,
                name=p.name,
                slug=p.slug,
                brand=p.brand,
                base_price=p.base_price,
                average_rating=p.average_rating,
                review_count=p.review_count,
                is_featured=p.is_featured,
                primary_image=primary,
            )
        )
    return items


@router.get("/categories", response_model=List[CategoryOut])
async def admin_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
):
    return (await db.execute(select(Category).order_by(Category.name))).scalars().all()


@router.get("/coupons", response_model=List[CouponOut])
async def admin_coupons(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
):
    return (await db.execute(select(Coupon).order_by(Coupon.created_at.desc()))).scalars().all()


@router.get("/payments", response_model=List[PaymentOut])
async def admin_payments(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
):
    return (
        await db.execute(select(Payment).order_by(Payment.created_at.desc()).limit(100))
    ).scalars().all()


@router.get("/inventory", response_model=List[InventoryRow])
async def admin_inventory(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SELLER))],
    low_stock_only: bool = Query(False),
):
    q = select(ProductVariant, Product).join(Product)
    if user.role == UserRole.SELLER:
        seller = (
            await db.execute(select(SellerProfile).where(SellerProfile.user_id == user.id))
        ).scalar_one_or_none()
        if not seller:
            return []
        q = q.where(Product.seller_id == seller.id)
    if low_stock_only:
        q = q.where(ProductVariant.stock < 5)
    rows = (await db.execute(q.order_by(ProductVariant.stock.asc()))).all()
    return [
        InventoryRow(
            variant_id=v.id,
            sku=v.sku,
            product_name=p.name,
            stock=v.stock,
            price=v.price,
        )
        for v, p in rows
    ]


@router.get("/reports/sales")
async def sales_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SELLER))],
):
    if user.role == UserRole.ADMIN:
        data = await OrderService(db).admin_analytics()
    else:
        data = await OrderService(db).seller_analytics(user)
    return {
        "total_revenue": data["total_revenue"],
        "total_orders": data["total_orders"],
        "sales_by_day": data.get("sales_by_day", []),
        "low_stock_count": data["low_stock_count"],
        "total_products": data["total_products"],
    }
