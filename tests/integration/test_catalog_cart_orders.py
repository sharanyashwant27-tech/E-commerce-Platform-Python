"""Integration tests for catalog, cart, coupons, and checkout."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_list_products_and_categories(client: AsyncClient, seed_data):
    cats = await client.get("/api/v1/categories")
    assert cats.status_code == 200
    assert len(cats.json()) >= 1

    products = await client.get("/api/v1/products")
    assert products.status_code == 200
    body = products.json()
    assert body["total"] >= 1
    assert body["items"][0]["name"] == "Test Phone"


@pytest.mark.asyncio
async def test_product_detail(client: AsyncClient, seed_data):
    pid = seed_data["product"].id
    resp = await client.get(f"/api/v1/products/{pid}")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "test-phone"


@pytest.mark.asyncio
async def test_cart_and_checkout_flow(client: AsyncClient, seed_data):
    token = await login(client, "customer@test.com", "Customer@12345")
    headers = {"Authorization": f"Bearer {token}"}

    add = await client.post(
        "/api/v1/cart/add",
        headers=headers,
        json={"variant_id": seed_data["variant"].id, "quantity": 2},
    )
    assert add.status_code == 200
    assert add.json()["item_count"] == 2

    # Coupon as admin
    admin_token = await login(client, "admin@test.com", "Admin@12345")
    coupon = await client.post(
        "/api/v1/coupons",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "code": "TEST10",
            "discount_type": "percent",
            "discount_value": 10,
            "min_order_amount": 0,
        },
    )
    assert coupon.status_code == 201

    checkout = await client.post(
        "/api/v1/checkout",
        headers=headers,
        json={
            "address_id": seed_data["address"].id,
            "coupon_code": "TEST10",
            "payment_provider": "stripe",
        },
    )
    assert checkout.status_code == 200, checkout.text
    order = checkout.json()["order"]
    assert order["status"] == "pending"
    assert checkout.json()["client_secret"]

    confirm = await client.post(
        f"/api/v1/orders/{order['id']}/confirm-payment",
        headers=headers,
        json={"provider_payment_id": checkout.json()["order"]["payment"]["provider_payment_id"]},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"


@pytest.mark.asyncio
async def test_review_and_wishlist(client: AsyncClient, seed_data):
    token = await login(client, "customer@test.com", "Customer@12345")
    headers = {"Authorization": f"Bearer {token}"}
    pid = seed_data["product"].id

    review = await client.post(
        "/api/v1/reviews",
        headers=headers,
        json={"product_id": pid, "rating": 5, "title": "Love it", "comment": "Works well"},
    )
    assert review.status_code == 201

    wish = await client.post(
        "/api/v1/wishlist",
        headers=headers,
        json={"product_id": pid},
    )
    assert wish.status_code == 201
    listed = await client.get("/api/v1/wishlist", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_admin_analytics(client: AsyncClient, seed_data):
    token = await login(client, "admin@test.com", "Admin@12345")
    resp = await client.get(
        "/api/v1/admin/analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "total_products" in resp.json()


@pytest.mark.asyncio
async def test_home_page(client: AsyncClient, seed_data):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert b"ShopSphere" in resp.content or b"shop" in resp.content.lower()
