"""Shopping cart endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.deps import get_current_active_user
from models.entities import User
from models.session import get_db
from schemas.cart import CartItemAdd, CartOut, CartRemoveRequest, CartUpdateRequest
from services.cart_service import CartService

router = APIRouter(prefix="/cart", tags=["Cart"])


@router.get("", response_model=CartOut)
async def get_cart(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    service = CartService(db)
    cart = await service.get_or_create_cart(user)
    return service.serialize(cart)


@router.post("/add", response_model=CartOut)
async def add_to_cart(
    payload: CartItemAdd,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    return await CartService(db).add_item(user, payload.variant_id, payload.quantity)


@router.put("/update", response_model=CartOut)
async def update_cart(
    payload: CartUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    return await CartService(db).update_item(user, payload.item_id, payload.quantity)


@router.delete("/remove", response_model=CartOut)
async def remove_from_cart(
    payload: CartRemoveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    return await CartService(db).remove_item(user, payload.item_id)
