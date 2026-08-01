"""Integration tests for image-based product search."""

from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.entities import Product, ProductImage, ProductVariant


@pytest.mark.asyncio
async def test_search_by_image_api_and_web(client: AsyncClient, db_session: AsyncSession, seed_data):
    image_path = Path(__file__).resolve().parents[2] / "static" / "images" / "headphones.jpg"
    assert image_path.is_file(), "seed catalog image missing"

    product = Product(
        seller_id=seed_data["seller"].id,
        category_id=seed_data["category"].id,
        name="Noise Cancelling Headphones",
        slug="noise-cancelling-headphones",
        description="Over-ear headphones for visual search test",
        brand="AudioLab",
        base_price=Decimal("4999"),
        is_active=True,
    )
    db_session.add(product)
    await db_session.flush()
    db_session.add(
        ProductVariant(
            product_id=product.id,
            sku="HP-IMG-1",
            name="Black",
            price=Decimal("4999"),
            stock=5,
        )
    )
    db_session.add(
        ProductImage(
            product_id=product.id,
            url="/static/images/headphones.jpg",
            is_primary=True,
        )
    )
    await db_session.commit()

    data = image_path.read_bytes()
    api = await client.post(
        "/api/v1/products/search-by-image",
        files={"file": ("headphones.jpg", data, "image/jpeg")},
    )
    assert api.status_code == 200, api.text
    body = api.json()
    assert body["search_type"] == "image"
    assert body["total"] >= 1
    slugs = [item["slug"] for item in body["items"]]
    assert "noise-cancelling-headphones" in slugs
    top = next(i for i in body["items"] if i["slug"] == "noise-cancelling-headphones")
    assert top["match_score"] is not None
    assert top["match_score"] >= 0.9

    web = await client.post(
        "/products/search-by-image",
        files={"file": ("headphones.jpg", data, "image/jpeg")},
    )
    assert web.status_code == 200, web.text
    assert "Image search results" in web.text
    assert "Noise Cancelling Headphones" in web.text


@pytest.mark.asyncio
async def test_search_by_image_rejects_bad_file(client: AsyncClient, seed_data):
    _ = seed_data
    resp = await client.post(
        "/api/v1/products/search-by-image",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 422
