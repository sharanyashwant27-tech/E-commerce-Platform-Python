"""Unit tests for security helpers and discount engine."""

from decimal import Decimal

import pytest

from services.discount_service import DiscountService
from auth.security import (
    create_access_token,
    create_email_token,
    decode_token,
    hash_password,
    verify_email_token,
    verify_password,
)
from models.entities import Coupon


def test_password_hash_roundtrip():
    hashed = hash_password("Secret@12345")
    assert verify_password("Secret@12345", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_contains_claims():
    token = create_access_token(42, "customer")
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "customer"
    assert payload["type"] == "access"


def test_email_token_purpose():
    token = create_email_token("a@b.com", "verify")
    assert verify_email_token(token, "verify") == "a@b.com"
    assert verify_email_token(token, "reset") is None


def test_discount_percent_with_cap():
    coupon = Coupon(
        code="SAVE20",
        discount_type="percent",
        discount_value=Decimal("20"),
        min_order_amount=Decimal("0"),
        max_discount=Decimal("100"),
        is_active=True,
        used_count=0,
    )
    svc = DiscountService(db=None)  # type: ignore[arg-type]
    discount = svc.calculate_discount(coupon, Decimal("1000"))
    assert discount == Decimal("100.00")


def test_discount_fixed():
    coupon = Coupon(
        code="FLAT50",
        discount_type="fixed",
        discount_value=Decimal("50"),
        min_order_amount=Decimal("0"),
        is_active=True,
        used_count=0,
    )
    svc = DiscountService(db=None)  # type: ignore[arg-type]
    assert svc.calculate_discount(coupon, Decimal("40")) == Decimal("40")


def test_discount_inactive_raises():
    coupon = Coupon(
        code="DEAD",
        discount_type="fixed",
        discount_value=Decimal("10"),
        min_order_amount=Decimal("0"),
        is_active=False,
        used_count=0,
    )
    svc = DiscountService(db=None)  # type: ignore[arg-type]
    with pytest.raises(Exception):
        svc.calculate_discount(coupon, Decimal("100"))
