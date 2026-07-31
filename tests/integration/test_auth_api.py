"""Integration tests for auth API."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register_and_me(client: AsyncClient):
    resp = await client.post(
        "/api/v1/register",
        json={
            "email": "newuser@example.com",
            "password": "Password@123",
            "full_name": "New User",
            "role": "customer",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "newuser@example.com"

    token = await login(client, "newuser@example.com", "Password@123")
    me = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["full_name"] == "New User"


@pytest.mark.asyncio
async def test_login_invalid(client: AsyncClient, seed_data):
    resp = await client.post(
        "/api/v1/login",
        data={"username": "customer@test.com", "password": "wrong"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, seed_data):
    resp = await client.post(
        "/api/v1/login",
        data={"username": "customer@test.com", "password": "Customer@12345"},
    )
    refresh = resp.json()["refresh_token"]
    refreshed = await client.post("/api/v1/refresh", json={"refresh_token": refresh})
    assert refreshed.status_code == 200
    assert "access_token" in refreshed.json()


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, seed_data):
    resp = await client.post("/api/v1/logout")
    assert resp.status_code == 200
    assert "Logged out" in resp.json()["message"]
