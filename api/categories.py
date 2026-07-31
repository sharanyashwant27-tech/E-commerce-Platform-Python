"""Category endpoints."""

from typing import Annotated, List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.deps import require_roles
from models.entities import User
from models.session import get_db
from schemas.auth import MessageOut
from schemas.product import CategoryCreate, CategoryOut, CategoryUpdate
from services.product_service import ProductService
from utils.enums import UserRole

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=List[CategoryOut])
async def list_categories(db: Annotated[AsyncSession, Depends(get_db)]):
    return await ProductService(db).list_categories()


@router.post("", response_model=CategoryOut, status_code=201)
async def create_category(
    payload: CategoryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
):
    return await ProductService(db).create_category(**payload.model_dump())


@router.put("/{id}", response_model=CategoryOut)
async def update_category(
    id: int,
    payload: CategoryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
):
    return await ProductService(db).update_category(id, payload.model_dump(exclude_unset=True))


@router.delete("/{id}", response_model=MessageOut)
async def delete_category(
    id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
):
    await ProductService(db).delete_category(id)
    return MessageOut(message="Category deleted")
