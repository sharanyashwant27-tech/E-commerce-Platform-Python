"""Public seller storefront endpoints."""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models.session import get_db
from schemas.product import ProductListItem, SellerStoreOut
from services.product_service import ProductService

router = APIRouter(prefix="/stores", tags=["Marketplace Stores"])


@router.get("", response_model=List[SellerStoreOut])
async def list_stores(db: Annotated[AsyncSession, Depends(get_db)]):
    return await ProductService(db).list_stores()


@router.get("/{slug}", response_model=dict)
async def get_store(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = ProductService(db)
    store = await service.get_store_by_slug(slug)
    products, total = await service.list_products(
        seller_id=store.id, page=page, page_size=page_size
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
                store_name=p.store_name,
                store_slug=p.store_slug,
            )
        )
    return {
        "store": SellerStoreOut.model_validate(store),
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
