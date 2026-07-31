"""Multi-seller marketplace: stores, cart groups, seller isolation."""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import hash_password
from models.entities import (
    Cart,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    SellerProfile,
    User,
)
from tests.conftest import login
from utils.enums import OrderStatus, ShippingStatus, UserRole


async def _second_seller(db: AsyncSession, category_id: int) -> dict:
    user = User(
        email="seller2@test.com",
        hashed_password=hash_password("Seller@12345"),
        full_name="Second Seller",
        role=UserRole.SELLER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    db.add(Cart(user_id=user.id))
    profile = SellerProfile(
        user_id=user.id,
        store_name="Second Store",
        slug="second-store",
        description="Fashion booth",
        is_approved=True,
    )
    db.add(profile)
    await db.flush()
    product = Product(
        seller_id=profile.id,
        category_id=category_id,
        name="Canvas Tote",
        slug="canvas-tote",
        description="Reusable tote",
        brand="BagCo",
        base_price=Decimal("499.00"),
        is_active=True,
    )
    db.add(product)
    await db.flush()
    variant = ProductVariant(
        product_id=product.id,
        sku="TOTE-1",
        name="Natural",
        price=Decimal("499.00"),
        stock=20,
    )
    db.add(variant)
    await db.flush()
    return {
        "user": user,
        "seller": profile,
        "product": product,
        "variant": variant,
    }


@pytest.mark.asyncio
async def test_stores_api_lists_approved_sellers(client: AsyncClient, seed_data):
    resp = await client.get("/api/v1/stores")
    assert resp.status_code == 200
    stores = resp.json()
    assert any(s["slug"] == "test-store" for s in stores)

    detail = await client.get("/api/v1/stores/test-store")
    assert detail.status_code == 200
    body = detail.json()
    assert body["store"]["store_name"] == "Test Store"
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_cart_includes_seller_groups(client: AsyncClient, seed_data, db_session):
    other = await _second_seller(db_session, seed_data["category"].id)
    await db_session.commit()

    token = await login(client, "customer@test.com", "Customer@12345")
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/api/v1/cart/add",
        headers=headers,
        json={"variant_id": seed_data["variant"].id, "quantity": 1},
    )
    await client.post(
        "/api/v1/cart/add",
        headers=headers,
        json={"variant_id": other["variant"].id, "quantity": 1},
    )
    cart = await client.get("/api/v1/cart", headers=headers)
    assert cart.status_code == 200
    data = cart.json()
    assert "seller_groups" in data
    assert len(data["seller_groups"]) >= 2
    slugs = {g["store_slug"] for g in data["seller_groups"]}
    assert "test-store" in slugs
    assert "second-store" in slugs


@pytest.mark.asyncio
async def test_seller_cannot_cancel_multi_seller_order(
    client: AsyncClient, seed_data, db_session
):
    other = await _second_seller(db_session, seed_data["category"].id)
    customer = seed_data["customer"]
    address = seed_data["address"]

    order = Order(
        order_number="SS-MULTI-1",
        user_id=customer.id,
        status=OrderStatus.PENDING,
        shipping_status=ShippingStatus.NOT_SHIPPED,
        subtotal=Decimal("1000"),
        discount_amount=Decimal("0"),
        shipping_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        total=Decimal("1000"),
        shipping_address_json="{}",
        invoice_number="INV-MULTI-1",
    )
    db_session.add(order)
    await db_session.flush()
    db_session.add_all(
        [
            OrderItem(
                order_id=order.id,
                variant_id=seed_data["variant"].id,
                seller_id=seed_data["seller"].id,
                product_name="P1",
                variant_name="Default",
                sku="S1",
                unit_price=Decimal("500"),
                quantity=1,
                line_total=Decimal("500"),
            ),
            OrderItem(
                order_id=order.id,
                variant_id=other["variant"].id,
                seller_id=other["seller"].id,
                product_name="P2",
                variant_name="Default",
                sku="S2",
                unit_price=Decimal("500"),
                quantity=1,
                line_total=Decimal("500"),
            ),
        ]
    )
    await db_session.commit()

    seller_tok = await login(client, "seller@test.com", "Seller@12345")
    headers = {"Authorization": f"Bearer {seller_tok}"}

    detail = await client.get(f"/api/v1/orders/{order.id}", headers=headers)
    assert detail.status_code == 200
    assert len(detail.json()["items"]) == 1
    assert detail.json()["items"][0]["seller_id"] == seed_data["seller"].id

    cancel = await client.put(
        "/api/v1/orders/cancel",
        headers=headers,
        json={"order_id": order.id},
    )
    assert cancel.status_code == 403

    status = await client.patch(
        f"/api/v1/orders/{order.id}/status",
        headers=headers,
        json={"status": "shipped"},
    )
    assert status.status_code == 403

    # Customer can still cancel the full marketplace order
    cust = await login(client, "customer@test.com", "Customer@12345")
    ok = await client.put(
        "/api/v1/orders/cancel",
        headers={"Authorization": f"Bearer {cust}"},
        json={"order_id": order.id},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "cancelled"
    # Customer sees both sellers' lines
    assert len(ok.json()["items"]) == 2


@pytest.mark.asyncio
async def test_unapproved_seller_hidden_from_catalog(
    client: AsyncClient, seed_data, db_session
):
    other = await _second_seller(db_session, seed_data["category"].id)
    other["seller"].is_approved = False
    await db_session.commit()

    stores = await client.get("/api/v1/stores")
    assert all(s["slug"] != "second-store" for s in stores.json())

    missing = await client.get("/api/v1/stores/second-store")
    assert missing.status_code == 404

    products = await client.get("/api/v1/products")
    slugs = [p["slug"] for p in products.json()["items"]]
    assert "canvas-tote" not in slugs
