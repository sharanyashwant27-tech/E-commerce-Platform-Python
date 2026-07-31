"""Order and checkout endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from auth.deps import get_current_active_user, require_roles
from models.entities import SellerProfile, User
from models.session import get_db
from schemas.order import (
    CheckoutRequest,
    CheckoutResponse,
    OrderCancelRequest,
    OrderOut,
    OrderStatusUpdate,
    PaymentConfirm,
)
from services.order_service import OrderService
from utils.enums import UserRole
from utils.invoice import build_invoice_pdf

router = APIRouter(tags=["Orders"])


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    payload: CheckoutRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    result = await OrderService(db).checkout(
        user=user,
        address_id=payload.address_id,
        payment_provider=payload.payment_provider,
        coupon_code=payload.coupon_code,
        notes=payload.notes,
    )
    return CheckoutResponse(
        order=result["order"],
        client_secret=result.get("client_secret"),
        razorpay_order_id=result.get("razorpay_order_id"),
        message=result["message"],
    )


@router.get("/orders", response_model=dict)
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    orders, total = await OrderService(db).list_orders(user, page, page_size)
    return {
        "items": [OrderOut.model_validate(o) for o in orders],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.put("/orders/cancel", response_model=OrderOut)
async def cancel_order(
    payload: OrderCancelRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    return await OrderService(db).cancel_order(user, payload.order_id)


@router.get("/orders/{id}", response_model=OrderOut)
async def get_order(
    id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    order = await OrderService(db).get_order(id, user)
    out = OrderOut.model_validate(order)
    if user.role == UserRole.SELLER:
        seller = (
            await db.execute(select(SellerProfile).where(SellerProfile.user_id == user.id))
        ).scalar_one_or_none()
        if seller:
            out.items = [i for i in out.items if i.seller_id == seller.id]
    return out


@router.post("/orders/{id}/confirm-payment", response_model=OrderOut)
async def confirm_payment(
    id: int,
    payload: PaymentConfirm,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    return await OrderService(db).confirm_payment(
        user, id, payload.provider_payment_id, payload.provider_order_id
    )


@router.patch("/orders/{id}/status", response_model=OrderOut)
async def update_status(
    id: int,
    payload: OrderStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.SELLER, UserRole.ADMIN))],
):
    return await OrderService(db).update_status(
        user,
        id,
        payload.status,
        payload.tracking_number,
        payload.shipping_status,
    )


@router.get("/orders/{id}/invoice")
async def download_invoice(
    id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    order = await OrderService(db).get_order(id, user)
    pdf = build_invoice_pdf(order)
    filename = f"{order.invoice_number or order.order_number}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
