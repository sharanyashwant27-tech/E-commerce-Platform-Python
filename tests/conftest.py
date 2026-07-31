"""Shared pytest fixtures using an isolated SQLite database."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from auth.security import hash_password
from utils.enums import UserRole
from models.entities import (
    Address,
    Cart,
    Category,
    Product,
    ProductImage,
    ProductVariant,
    SellerProfile,
    User,
)
from models.session import Base, get_db
from main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session", autouse=True)
def _celery_eager_mode():
    """Run Celery tasks inline during tests — no Redis broker required."""
    from app.workers.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        TEST_DB_URL,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_data(db_session: AsyncSession):
    admin = User(
        email="admin@test.com",
        hashed_password=hash_password("Admin@12345"),
        full_name="Admin",
        role=UserRole.ADMIN,
        is_verified=True,
    )
    seller_user = User(
        email="seller@test.com",
        hashed_password=hash_password("Seller@12345"),
        full_name="Seller",
        role=UserRole.SELLER,
        is_verified=True,
    )
    customer = User(
        email="customer@test.com",
        hashed_password=hash_password("Customer@12345"),
        full_name="Customer",
        role=UserRole.CUSTOMER,
        is_verified=True,
    )
    db_session.add_all([admin, seller_user, customer])
    await db_session.flush()

    seller = SellerProfile(
        user_id=seller_user.id,
        store_name="Test Store",
        slug="test-store",
        is_approved=True,
    )
    db_session.add(seller)
    db_session.add(Cart(user_id=customer.id))
    cat = Category(name="Gadgets", slug="gadgets")
    db_session.add(cat)
    await db_session.flush()

    product = Product(
        seller_id=seller.id,
        category_id=cat.id,
        name="Test Phone",
        slug="test-phone",
        description="A test smartphone",
        brand="TestBrand",
        base_price=Decimal("10000"),
        is_active=True,
        is_featured=True,
    )
    db_session.add(product)
    await db_session.flush()
    variant = ProductVariant(
        product_id=product.id,
        sku="TEST-PHONE-1",
        name="Black",
        price=Decimal("10000"),
        stock=20,
    )
    db_session.add(variant)
    db_session.add(
        ProductImage(product_id=product.id, url="https://example.com/p.jpg", is_primary=True)
    )
    addr = Address(
        user_id=customer.id,
        full_name="Customer",
        phone="9999999999",
        line1="1 Test Street",
        city="Mumbai",
        state="MH",
        postal_code="400001",
        is_default=True,
    )
    db_session.add(addr)
    await db_session.commit()
    return {
        "admin": admin,
        "seller_user": seller_user,
        "customer": customer,
        "seller": seller,
        "category": cat,
        "product": product,
        "variant": variant,
        "address": addr,
    }


async def login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/login",
        data={"username": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]
