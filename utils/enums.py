"""Domain enums for roles, orders, payments, and shipping."""

import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    SELLER = "seller"
    CUSTOMER = "customer"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentProvider(str, enum.Enum):
    STRIPE = "stripe"
    RAZORPAY = "razorpay"
    COD = "cod"


class ShippingStatus(str, enum.Enum):
    NOT_SHIPPED = "not_shipped"
    PACKED = "packed"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    RETURNED = "returned"
