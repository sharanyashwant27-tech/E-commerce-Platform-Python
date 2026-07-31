"""Real-time inventory sync API and publish hooks."""

import asyncio

import pytest
from httpx import AsyncClient

from tests.conftest import login
from utils.inventory_sync import (
    publish_inventory_update,
    register_local_subscriber,
    unregister_local_subscriber,
)


@pytest.mark.asyncio
async def test_inventory_health_and_snapshot(client: AsyncClient, seed_data):
    health = await client.get("/api/v1/inventory/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["channel"] == "shopsphere:inventory"

    variant = seed_data["variant"]
    snap = await client.get(f"/api/v1/inventory/variants/{variant.id}")
    assert snap.status_code == 200
    data = snap.json()
    assert data["variant_id"] == variant.id
    assert data["sku"] == variant.sku
    assert "stock" in data

    product = seed_data["product"]
    plist = await client.get(f"/api/v1/inventory/products/{product.id}")
    assert plist.status_code == 200
    assert any(i["variant_id"] == variant.id for i in plist.json()["items"])


@pytest.mark.asyncio
async def test_inventory_patch_publishes_local_event(client: AsyncClient, seed_data):
    token = await login(client, "seller@test.com", "Seller@12345")
    headers = {"Authorization": f"Bearer {token}"}
    variant = seed_data["variant"]

    queue = register_local_subscriber()
    try:
        resp = await client.patch(
            f"/api/v1/products/variants/{variant.id}/inventory",
            headers=headers,
            json={"stock": 42, "reason": "sync_test"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["stock"] == 42

        event = await asyncio.wait_for(queue.get(), timeout=2.0)
        assert event["variant_id"] == variant.id
        assert event["stock"] == 42
        assert event["reason"] == "sync_test"
        assert event["type"] == "inventory.update"
    finally:
        unregister_local_subscriber(queue)


@pytest.mark.asyncio
async def test_publish_inventory_update_helper():
    queue = register_local_subscriber()
    try:
        event = publish_inventory_update(
            variant_id=99,
            product_id=7,
            sku="TEST-SKU",
            stock=3,
            product_name="Test Item",
            reason="unit",
            change=-1,
        )
        assert event["low_stock"] is True
        got = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert got["sku"] == "TEST-SKU"
        assert got["stock"] == 3
    finally:
        unregister_local_subscriber(queue)


@pytest.mark.asyncio
async def test_inventory_stream_once_probe(client: AsyncClient):
    resp = await client.get("/api/v1/inventory/stream?once=true")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    assert "event: ready" in resp.text

