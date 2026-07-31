"""Service-layer unit/integration tests against in-memory DB."""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth_service import AuthService, slugify
from services.cart_service import CartService, WishlistService
from services.discount_service import DiscountService
from services.order_service import OrderService
from services.product_service import ProductService
from utils.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from auth.security import create_email_token
from utils.enums import OrderStatus, PaymentProvider, UserRole
from utils.cache import cache_delete, cache_get, cache_set, get_redis
from utils.email import send_email
from utils.payment import PaymentGateway


def test_slugify():
    assert slugify("Hello World!") == "hello-world"


@pytest.mark.asyncio
async def test_auth_register_login_verify_reset(db_session: AsyncSession):
    svc = AuthService(db_session)
    user = await svc.register(
        email="u1@example.com",
        password="Password@123",
        full_name="User One",
    )
    assert user.role == UserRole.CUSTOMER

    with pytest.raises(ConflictError):
        await svc.register("u1@example.com", "Password@123", "Dup")

    with pytest.raises(ValidationError):
        await svc.register(
            "admin2@example.com", "Password@123", "X", role=UserRole.ADMIN
        )

    with pytest.raises(ValidationError):
        await svc.register(
            "sellerx@example.com", "Password@123", "X", role=UserRole.SELLER
        )

    seller = await svc.register(
        email="sellerx@example.com",
        password="Password@123",
        full_name="Seller X",
        role=UserRole.SELLER,
        store_name="Store X",
    )
    assert seller.role == UserRole.SELLER

    access, refresh, authed = await svc.authenticate("u1@example.com", "Password@123")
    assert access and refresh and authed.id == user.id

    a2, r2 = await svc.refresh_tokens(refresh)
    assert a2 and r2

    token = svc.verification_token(user.email)
    verified = await svc.verify_email(token)
    assert verified.is_verified

    reset = svc.reset_token(user.email)
    await svc.reset_password(reset, "NewPass@12345")
    await svc.authenticate("u1@example.com", "NewPass@12345")

    profile = await svc.get_user_with_profile(user.id)
    assert profile.email == "u1@example.com"

    with pytest.raises(NotFoundError):
        await svc.get_user_with_profile(99999)


@pytest.mark.asyncio
async def test_product_cart_order_flow(db_session: AsyncSession, seed_data):
    user = seed_data["customer"]
    seller_user = seed_data["seller_user"]
    admin = seed_data["admin"]

    products = ProductService(db_session)
    listed, total = await products.list_products(q="Phone")
    assert total >= 1

    by_slug = await products.get_by_slug("test-phone")
    assert by_slug.id == seed_data["product"].id

    cats = await products.list_categories()
    assert cats

    created = await products.create_product(
        seller_user,
        {
            "name": "Tablet Air",
            "description": "Lightweight tablet",
            "category_id": seed_data["category"].id,
            "base_price": Decimal("15000"),
            "brand": "TabCo",
            "image_urls": ["https://example.com/t.jpg"],
            "variants": [
                {
                    "sku": "TAB-1",
                    "name": "64GB",
                    "price": Decimal("15000"),
                    "stock": 5,
                }
            ],
        },
    )
    assert created.slug.startswith("tablet")

    updated = await products.update_product(
        seller_user, created.id, {"name": "Tablet Air 2"}
    )
    assert updated.name == "Tablet Air 2"

    variant = created.variants[0]
    inv = await products.update_inventory(seller_user, variant.id, 8, "restock")
    assert inv.stock == 8

    review = await products.add_review(user, seed_data["product"].id, 5, "Nice", "Good")
    assert review.rating == 5
    reviews = await products.list_reviews(seed_data["product"].id)
    assert reviews

    cart_svc = CartService(db_session)
    cart = await cart_svc.add_item(user, seed_data["variant"].id, 2)
    assert cart["item_count"] == 2
    item_id = cart["items"][0]["id"]
    cart = await cart_svc.update_item(user, item_id, 1)
    assert cart["item_count"] == 1

    wish = WishlistService(db_session)
    w = await wish.add(user, seed_data["product"].id)
    assert w["product_id"] == seed_data["product"].id
    listed_w = await wish.list_items(user)
    assert listed_w
    await wish.remove(user, seed_data["product"].id)

    discounts = DiscountService(db_session)
    coupon = await discounts.create(
        code="UNIT10",
        discount_type="percent",
        discount_value=Decimal("10"),
        min_order_amount=Decimal("0"),
        max_discount=Decimal("2000"),
    )
    c, amount = await discounts.validate("UNIT10", Decimal("1000"))
    assert c.id == coupon.id
    assert amount == Decimal("100.00")

    orders = OrderService(db_session)
    # ensure cart has items again
    await cart_svc.add_item(user, seed_data["variant"].id, 1)
    result = await orders.checkout(
        user=user,
        address_id=seed_data["address"].id,
        payment_provider=PaymentProvider.STRIPE,
        coupon_code="UNIT10",
    )
    order = result["order"]
    assert order.total > 0
    confirmed = await orders.confirm_payment(
        user, order.id, result["order"].payment.provider_payment_id
    )
    assert confirmed.status == OrderStatus.CONFIRMED

    listed_orders, count = await orders.list_orders(user)
    assert count >= 1

    analytics = await orders.admin_analytics()
    assert analytics["total_orders"] >= 1

    seller_stats = await orders.seller_analytics(seller_user)
    assert seller_stats["total_products"] >= 1

    shipped = await orders.update_status(
        admin, order.id, OrderStatus.SHIPPED, tracking_number="TRK1"
    )
    assert shipped.tracking_number == "TRK1"


def test_send_email_dev_fallback():
    assert send_email("a@b.com", "Hi", "<p>Hello</p>") is True


def test_cache_graceful_without_redis():
    # Redis may be unavailable in CI/local — should not raise
    get_redis()
    cache_set("k", {"a": 1})
    cache_get("k")
    cache_delete("k")


def test_payment_gateway_serialize():
    assert "1" in PaymentGateway.serialize_raw({"x": 1})
    assert PaymentGateway.serialize_raw(object())  # falls back to str
