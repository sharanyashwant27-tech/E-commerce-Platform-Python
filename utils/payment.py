"""Stripe / Razorpay sandbox payment gateway (graceful without real keys)."""

import json
import logging
import uuid
from decimal import Decimal
from typing import Any, Optional

from config.settings import settings
from utils.exceptions import PaymentError
from utils.enums import PaymentProvider

logger = logging.getLogger(__name__)


class PaymentGateway:
    """Unified payment interface for Stripe and Razorpay sandbox modes."""

    def create_payment(
        self,
        provider: PaymentProvider,
        amount: Decimal,
        currency: str,
        order_number: str,
        metadata: Optional[dict] = None,
    ) -> dict[str, Any]:
        if provider == PaymentProvider.COD:
            return {
                "provider_order_id": f"cod_{order_number}",
                "provider_payment_id": None,
                "client_secret": None,
                "status": "pending",
                "raw": {"mode": "cod"},
            }
        if provider == PaymentProvider.STRIPE:
            return self._stripe_create(amount, currency, order_number, metadata)
        if provider == PaymentProvider.RAZORPAY:
            return self._razorpay_create(amount, currency, order_number, metadata)
        raise PaymentError(f"Unsupported provider: {provider}")

    def confirm_payment(
        self,
        provider: PaymentProvider,
        provider_payment_id: str,
        provider_order_id: Optional[str] = None,
    ) -> dict[str, Any]:
        if provider == PaymentProvider.COD:
            return {"status": "authorized", "raw": {"mode": "cod"}}
        if provider == PaymentProvider.STRIPE:
            return self._stripe_confirm(provider_payment_id)
        if provider == PaymentProvider.RAZORPAY:
            return self._razorpay_confirm(provider_payment_id, provider_order_id)
        raise PaymentError(f"Unsupported provider: {provider}")

    def _stripe_create(
        self, amount: Decimal, currency: str, order_number: str, metadata: Optional[dict]
    ) -> dict[str, Any]:
        if not settings.stripe_secret_key or settings.stripe_secret_key.startswith("sk_test_your"):
            # Sandbox mock when keys are placeholders
            pid = f"pi_mock_{uuid.uuid4().hex[:16]}"
            return {
                "provider_order_id": order_number,
                "provider_payment_id": pid,
                "client_secret": f"{pid}_secret_mock",
                "status": "pending",
                "raw": {"mode": "stripe_mock", "amount": str(amount)},
            }
        try:
            import stripe

            stripe.api_key = settings.stripe_secret_key
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),
                currency=currency.lower(),
                metadata={"order_number": order_number, **(metadata or {})},
                automatic_payment_methods={"enabled": True},
            )
            return {
                "provider_order_id": order_number,
                "provider_payment_id": intent.id,
                "client_secret": intent.client_secret,
                "status": "pending",
                "raw": intent,
            }
        except Exception as exc:
            logger.exception("Stripe payment creation failed")
            raise PaymentError(str(exc)) from exc

    def _stripe_confirm(self, payment_id: str) -> dict[str, Any]:
        if payment_id.startswith("pi_mock_"):
            return {"status": "captured", "raw": {"mode": "stripe_mock", "id": payment_id}}
        try:
            import stripe

            stripe.api_key = settings.stripe_secret_key
            intent = stripe.PaymentIntent.retrieve(payment_id)
            status = "captured" if intent.status == "succeeded" else "authorized"
            return {"status": status, "raw": intent}
        except Exception as exc:
            raise PaymentError(str(exc)) from exc

    def _razorpay_create(
        self, amount: Decimal, currency: str, order_number: str, metadata: Optional[dict]
    ) -> dict[str, Any]:
        if (
            not settings.razorpay_key_id
            or settings.razorpay_key_id.startswith("rzp_test_your")
        ):
            oid = f"order_mock_{uuid.uuid4().hex[:14]}"
            return {
                "provider_order_id": oid,
                "provider_payment_id": None,
                "client_secret": None,
                "razorpay_order_id": oid,
                "status": "pending",
                "raw": {"mode": "razorpay_mock", "amount": str(amount), "receipt": order_number},
            }
        try:
            import razorpay

            client = razorpay.Client(
                auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
            )
            order = client.order.create(
                {
                    "amount": int(amount * 100),
                    "currency": currency.upper(),
                    "receipt": order_number,
                    "notes": metadata or {},
                }
            )
            return {
                "provider_order_id": order["id"],
                "provider_payment_id": None,
                "client_secret": None,
                "razorpay_order_id": order["id"],
                "status": "pending",
                "raw": order,
            }
        except Exception as exc:
            logger.exception("Razorpay order creation failed")
            raise PaymentError(str(exc)) from exc

    def _razorpay_confirm(
        self, payment_id: str, order_id: Optional[str]
    ) -> dict[str, Any]:
        if payment_id.startswith("pay_mock_") or (order_id and order_id.startswith("order_mock_")):
            return {
                "status": "captured",
                "raw": {"mode": "razorpay_mock", "payment_id": payment_id},
            }
        try:
            import razorpay

            client = razorpay.Client(
                auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
            )
            payment = client.payment.fetch(payment_id)
            status = "captured" if payment.get("status") == "captured" else "authorized"
            return {"status": status, "raw": payment}
        except Exception as exc:
            raise PaymentError(str(exc)) from exc

    @staticmethod
    def serialize_raw(raw: Any) -> str:
        try:
            return json.dumps(raw, default=str)
        except Exception:
            return str(raw)
