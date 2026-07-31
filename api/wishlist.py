"""Wishlist endpoints."""

from typing import Annotated, List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.deps import get_current_active_user
from schemas.auth import MessageOut
from schemas.cart import WishlistAdd, WishlistItemOut
from services.cart_service import WishlistService
from models.entities import User
from models.session import get_db

router = APIRouter()


@router.get("", response_model=List[WishlistItemOut])
async def list_wishlist(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    return await WishlistService(db).list_items(user)


@router.post("", response_model=WishlistItemOut, status_code=201)
async def add_wishlist(
    payload: WishlistAdd,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    return await WishlistService(db).add(user, payload.product_id)


@router.delete("/{product_id}", response_model=MessageOut)
async def remove_wishlist(
    product_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    await WishlistService(db).remove(user, product_id)
    return MessageOut(message="Removed from wishlist")
