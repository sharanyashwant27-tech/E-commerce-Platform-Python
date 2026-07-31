"""Order and payment schemas."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

from utils.enums import (
    OrderStatus,
    PaymentProvider,
    PaymentStatus,
    ShippingStatus,
)


class CheckoutRequest(BaseModel):
    address_id: int
    coupon_code: Optional[str] = None
    payment_provider: PaymentProvider = PaymentProvider.STRIPE
    notes: Optional[str] = None


class OrderItemOut(BaseModel):
    id: int
    product_name: str
    variant_name: str
    sku: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal

    model_config = {"from_attributes": True}


class PaymentOut(BaseModel):
    id: int
    provider: PaymentProvider
    status: PaymentStatus
    amount: Decimal
    currency: str
    provider_payment_id: Optional[str] = None
    provider_order_id: Optional[str] = None

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: int
    order_number: str
    status: OrderStatus
    shipping_status: ShippingStatus
    subtotal: Decimal
    discount_amount: Decimal
    shipping_amount: Decimal
    tax_amount: Decimal
    total: Decimal
    tracking_number: Optional[str] = None
    invoice_number: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    items: List[OrderItemOut] = []
    payment: Optional[PaymentOut] = None

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    tracking_number: Optional[str] = None
    shipping_status: Optional[ShippingStatus] = None


class OrderCancelRequest(BaseModel):
    order_id: int


class PaymentConfirm(BaseModel):
    provider_payment_id: str
    provider_order_id: Optional[str] = None


class CheckoutResponse(BaseModel):
    order: OrderOut
    client_secret: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    payment_url: Optional[str] = None
    message: str = "Order created"


class AnalyticsOut(BaseModel):
    total_orders: int
    total_revenue: Decimal
    today_orders: int = 0
    today_revenue: Decimal = Decimal("0")
    pending_orders: int = 0
    cancelled_orders: int = 0
    total_products: int
    total_customers: int
    low_stock_count: int
    low_stock_items: List[dict] = Field(default_factory=list)
    top_selling_products: List[dict] = Field(default_factory=list)
    recent_customers: List[dict] = Field(default_factory=list)
    categories: List[dict] = Field(default_factory=list)
    notifications: List[dict] = Field(default_factory=list)
    recent_orders: List[OrderOut] = []
    sales_by_day: List[dict] = Field(default_factory=list)
