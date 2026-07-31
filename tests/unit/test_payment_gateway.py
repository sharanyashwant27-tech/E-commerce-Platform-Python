"""Unit tests for payment gateway sandbox mocks."""

from decimal import Decimal

from utils.enums import PaymentProvider
from utils.payment import PaymentGateway


def test_stripe_mock_create():
    gw = PaymentGateway()
    result = gw.create_payment(PaymentProvider.STRIPE, Decimal("100"), "INR", "ORD1")
    assert result["client_secret"]
    assert result["provider_payment_id"].startswith("pi_mock_")


def test_razorpay_mock_create():
    gw = PaymentGateway()
    result = gw.create_payment(PaymentProvider.RAZORPAY, Decimal("100"), "INR", "ORD2")
    assert result["razorpay_order_id"].startswith("order_mock_")


def test_cod_create_and_confirm():
    gw = PaymentGateway()
    created = gw.create_payment(PaymentProvider.COD, Decimal("50"), "INR", "ORD3")
    confirmed = gw.confirm_payment(PaymentProvider.COD, "n/a")
    assert created["provider_order_id"].startswith("cod_")
    assert confirmed["status"] == "authorized"


def test_stripe_mock_confirm():
    gw = PaymentGateway()
    result = gw.confirm_payment(PaymentProvider.STRIPE, "pi_mock_abc")
    assert result["status"] == "captured"
