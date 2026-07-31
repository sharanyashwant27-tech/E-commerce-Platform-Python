"""Additional API/web coverage tests."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_seller_create_product_and_inventory(client: AsyncClient, seed_data):
    token = await login(client, "seller@test.com", "Seller@12345")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Wireless Mouse",
            "description": "Ergonomic mouse",
            "category_id": seed_data["category"].id,
            "base_price": 799,
            "brand": "ClickCo",
            "image_urls": ["https://example.com/m.jpg"],
            "variants": [
                {"sku": "MOUSE-1", "name": "Black", "price": 799, "stock": 12}
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    product = resp.json()
    variant_id = product["variants"][0]["id"]

    inv = await client.patch(
        f"/api/v1/products/variants/{variant_id}/inventory",
        headers=headers,
        json={"stock": 30, "reason": "restock"},
    )
    assert inv.status_code == 200
    assert inv.json()["stock"] == 30

    slug = await client.get(f"/api/v1/products/slug/{product['slug']}")
    assert slug.status_code == 200


@pytest.mark.asyncio
async def test_admin_coupon_validate_and_approve(client: AsyncClient, seed_data):
    admin = await login(client, "admin@test.com", "Admin@12345")
    headers = {"Authorization": f"Bearer {admin}"}
    coupon = await client.post(
        "/api/v1/coupons",
        headers=headers,
        json={
            "code": "SAVE5",
            "discount_type": "fixed",
            "discount_value": 5,
            "min_order_amount": 0,
        },
    )
    assert coupon.status_code == 201

    customer = await login(client, "customer@test.com", "Customer@12345")
    valid = await client.post(
        "/api/v1/apply-coupon",
        headers={"Authorization": f"Bearer {customer}"},
        json={"code": "SAVE5", "order_amount": 100},
    )
    assert valid.status_code == 200
    assert float(valid.json()["discount_amount"]) == 5

    approve = await client.post(
        f"/api/v1/admin/sellers/{seed_data['seller'].id}/approve",
        headers=headers,
    )
    assert approve.status_code == 200

    seller_analytics = await client.get(
        "/api/v1/admin/seller/analytics",
        headers={"Authorization": f"Bearer {await login(client, 'seller@test.com', 'Seller@12345')}"},
    )
    assert seller_analytics.status_code == 200


@pytest.mark.asyncio
async def test_auth_forgot_and_verify_endpoints(client: AsyncClient, seed_data):
    from auth.security import create_email_token

    forgot = await client.post(
        "/api/v1/forgot-password",
        json={"email": "customer@test.com"},
    )
    assert forgot.status_code == 200

    token = create_email_token("customer@test.com", "verify")
    verify = await client.post(f"/api/v1/verify-email?token={token}")
    assert verify.status_code == 200

    reset_token = create_email_token("customer@test.com", "reset")
    reset = await client.post(
        "/api/v1/reset-password",
        json={"token": reset_token, "new_password": "Customer@99999"},
    )
    assert reset.status_code == 200


@pytest.mark.asyncio
async def test_cart_update_remove(client: AsyncClient, seed_data):
    token = await login(client, "customer@test.com", "Customer@12345")
    headers = {"Authorization": f"Bearer {token}"}
    add = await client.post(
        "/api/v1/cart/add",
        headers=headers,
        json={"variant_id": seed_data["variant"].id, "quantity": 1},
    )
    assert add.status_code == 200
    assert add.json()["item_count"] == 1
    item_id = add.json()["items"][0]["id"]

    updated = await client.put(
        "/api/v1/cart/update",
        headers=headers,
        json={"item_id": item_id, "quantity": 3},
    )
    assert updated.status_code == 200
    assert updated.json()["item_count"] == 3

    removed = await client.request(
        "DELETE",
        "/api/v1/cart/remove",
        headers=headers,
        json={"item_id": item_id},
    )
    assert removed.status_code == 200
    assert removed.json()["item_count"] == 0

    cart = await client.get("/api/v1/cart", headers=headers)
    assert cart.status_code == 200


@pytest.mark.asyncio
async def test_create_category_admin(client: AsyncClient, seed_data):
    token = await login(client, "admin@test.com", "Admin@12345")
    resp = await client.post(
        "/api/v1/categories",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Books", "slug": "books"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_orders_list_get_and_cancel(client: AsyncClient, seed_data):
    token = await login(client, "customer@test.com", "Customer@12345")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/v1/cart/add",
        headers=headers,
        json={"variant_id": seed_data["variant"].id, "quantity": 1},
    )
    checkout = await client.post(
        "/api/v1/checkout",
        headers=headers,
        json={
            "address_id": seed_data["address"].id,
            "payment_provider": "cod",
        },
    )
    assert checkout.status_code == 200, checkout.text
    order_id = checkout.json()["order"]["id"]

    listed = await client.get("/api/v1/orders", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    detail = await client.get(f"/api/v1/orders/{order_id}", headers=headers)
    assert detail.status_code == 200

    cancelled = await client.put(
        "/api/v1/orders/cancel",
        headers=headers,
        json={"order_id": order_id},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_wishlist_remove(client: AsyncClient, seed_data):
    token = await login(client, "customer@test.com", "Customer@12345")
    headers = {"Authorization": f"Bearer {token}"}
    pid = seed_data["product"].id
    await client.post("/api/v1/wishlist", headers=headers, json={"product_id": pid})
    deleted = await client.delete(f"/api/v1/wishlist/{pid}", headers=headers)
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_reviews_list(client: AsyncClient, seed_data):
    resp = await client.get(f"/api/v1/reviews/{seed_data['product'].id}")
    assert resp.status_code == 200
