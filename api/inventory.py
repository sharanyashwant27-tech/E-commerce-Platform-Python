"""Real-time inventory APIs — stock snapshot + SSE stream."""

from typing import Annotated, List, Optional, Set

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.entities import ProductVariant
from models.session import get_db
from utils.exceptions import NotFoundError
from utils.inventory_sync import (
    LOW_STOCK_THRESHOLD,
    build_inventory_event,
    inventory_event_stream,
)

router = APIRouter(prefix="/inventory", tags=["Inventory"])


class StockSnapshot(BaseModel):
    variant_id: int
    product_id: int
    sku: str
    stock: int
    product_name: str = ""
    low_stock: bool = False
    out_of_stock: bool = False


class StockListOut(BaseModel):
    items: List[StockSnapshot] = Field(default_factory=list)


def _to_snapshot(variant: ProductVariant) -> StockSnapshot:
    product = variant.product
    return StockSnapshot(
        variant_id=variant.id,
        product_id=variant.product_id,
        sku=variant.sku,
        stock=variant.stock,
        product_name=product.name if product else "",
        low_stock=variant.stock < LOW_STOCK_THRESHOLD,
        out_of_stock=variant.stock <= 0,
    )


@router.get("/variants/{variant_id}", response_model=StockSnapshot)
async def get_variant_stock(
    variant_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(ProductVariant)
        .options(selectinload(ProductVariant.product))
        .where(ProductVariant.id == variant_id)
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise NotFoundError("Variant not found")
    return _to_snapshot(variant)


@router.get("/products/{product_id}", response_model=StockListOut)
async def get_product_stock(
    product_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(ProductVariant)
        .options(selectinload(ProductVariant.product))
        .where(ProductVariant.product_id == product_id, ProductVariant.is_active.is_(True))
        .order_by(ProductVariant.id)
    )
    variants = result.scalars().all()
    return StockListOut(items=[_to_snapshot(v) for v in variants])


@router.get("/stream")
async def stream_inventory(
    variant_id: Optional[List[int]] = Query(default=None),
    product_id: Optional[List[int]] = Query(default=None),
    once: bool = Query(
        default=False,
        description="If true, emit ready (+ optional pending events) then close — for probes/tests",
    ),
):
    """Server-Sent Events stream of inventory updates.

    Optional filters: ``variant_id`` / ``product_id`` (repeatable query params).
    Without filters, all catalog stock changes are streamed.
    """
    variant_ids: Optional[Set[int]] = set(variant_id) if variant_id else None
    product_ids: Optional[Set[int]] = set(product_id) if product_id else None

    async def frames():
        if once:
            # Finite probe — avoids hanging HTTP clients/tests
            yield 'event: ready\ndata: {"ok": true, "once": true}\n\n'
            return
        async for chunk in inventory_event_stream(
            variant_ids=variant_ids, product_ids=product_ids
        ):
            yield chunk

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/health")
async def inventory_sync_health():
    """Lightweight probe used by UI/tests — shows channel metadata."""
    sample = build_inventory_event(
        variant_id=0,
        product_id=0,
        sku="PROBE",
        stock=0,
        reason="health",
    )
    return {
        "status": "ok",
        "channel": "shopsphere:inventory",
        "low_stock_threshold": LOW_STOCK_THRESHOLD,
        "sample_event_keys": sorted(sample.keys()),
    }
