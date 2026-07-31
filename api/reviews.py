"""Product review endpoints."""

from typing import Annotated, List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.deps import get_current_active_user
from models.entities import User
from models.session import get_db
from schemas.product import ReviewCreate, ReviewOut
from services.product_service import ProductService

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post("", response_model=ReviewOut, status_code=201)
async def create_review(
    payload: ReviewCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    body = payload.body or payload.comment
    return await ProductService(db).add_review(
        user, payload.product_id, payload.rating, payload.title, body
    )


@router.get("/{product_id}", response_model=List[ReviewOut])
async def list_reviews(product_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    return await ProductService(db).list_reviews(product_id)
