"""Product catalog endpoints."""

from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth.deps import require_roles
from models.entities import User
from models.session import get_db
from schemas.auth import MessageOut
from schemas.product import (
    InventoryUpdate,
    ProductCreate,
    ProductListItem,
    ProductOut,
    ProductUpdate,
    VariantOut,
)
from services.product_service import ProductService
from utils.enums import UserRole

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=dict)
async def list_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Optional[str] = None,
    category_id: Optional[int] = None,
    featured: Optional[bool] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = ProductService(db)
    products, total = await service.list_products(
        q=q,
        category_id=category_id,
        featured=featured,
        min_price=min_price,
        max_price=max_price,
        page=page,
        page_size=page_size,
    )
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
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/slug/{slug}", response_model=ProductOut)
async def get_by_slug(slug: str, db: Annotated[AsyncSession, Depends(get_db)]):
    return await ProductService(db).get_by_slug(slug)


@router.get("/{id}", response_model=ProductOut)
async def get_product(id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    return await ProductService(db).get_product(id)


@router.post("", response_model=ProductOut, status_code=201)
async def create_product(
    payload: ProductCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.SELLER))],
):
    data = payload.model_dump()
    data["variants"] = [v.model_dump() for v in payload.variants]
    return await ProductService(db).create_product(user, data)


@router.put("/{id}", response_model=ProductOut)
async def update_product(
    id: int,
    payload: ProductUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.SELLER))],
):
    return await ProductService(db).update_product(
        user, id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/{id}", response_model=MessageOut)
async def delete_product(
    id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.SELLER))],
):
    await ProductService(db).delete_product(user, id)
    return MessageOut(message="Product deleted")


@router.patch("/variants/{variant_id}/inventory", response_model=VariantOut)
async def update_inventory(
    variant_id: int,
    payload: InventoryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.SELLER))],
):
    return await ProductService(db).update_inventory(
        user, variant_id, payload.stock, payload.reason
    )
