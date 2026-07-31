"""Checkout, order management, invoices, and analytics."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.cart_service import CartService
from services.discount_service import DiscountService
from utils.exceptions import ForbiddenError, InventoryError, NotFoundError, ValidationError
from utils.enums import (
    OrderStatus,
    PaymentProvider,
    PaymentStatus,
    ShippingStatus,
    UserRole,
)
from models.entities import (
    Address,
    Category,
    InventoryLog,
    Notification,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductVariant,
    User,
)
from utils.payment import PaymentGateway

TAX_RATE = Decimal("0.18")
FREE_SHIPPING_THRESHOLD = Decimal("999")
FLAT_SHIPPING = Decimal("49")


class OrderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cart_service = CartService(db)
        self.discount_service = DiscountService(db)
        self.gateway = PaymentGateway()

    def _order_number(self) -> str:
        return f"SS{datetime.now(timezone.utc).strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"

    def _invoice_number(self) -> str:
        return f"INV-{datetime.now(timezone.utc).strftime('%Y%m')}{uuid.uuid4().hex[:6].upper()}"

    async def checkout(
        self,
        user: User,
        address_id: int,
        payment_provider: PaymentProvider,
        coupon_code: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        cart = await self.cart_service.get_or_create_cart(user)
        if not cart.items:
            raise ValidationError("Cart is empty")

        address = await self.db.get(Address, address_id)
        if not address or address.user_id != user.id:
            raise NotFoundError("Shipping address not found")

        # Validate stock & compute subtotal
        subtotal = Decimal("0")
        line_data = []
        for item in cart.items:
            variant = item.variant
            if variant.stock < item.quantity:
                raise InventoryError(
                    f"Insufficient stock for {variant.product.name} ({variant.name})"
                )
            line_total = variant.price * item.quantity
            subtotal += line_total
            line_data.append((item, variant, line_total))

        discount_amount = Decimal("0")
        coupon = None
        if coupon_code:
            coupon, discount_amount = await self.discount_service.validate(
                coupon_code, subtotal
            )

        shipping = (
            Decimal("0") if subtotal - discount_amount >= FREE_SHIPPING_THRESHOLD else FLAT_SHIPPING
        )
        taxable = max(subtotal - discount_amount, Decimal("0"))
        tax = (taxable * TAX_RATE).quantize(Decimal("0.01"))
        total = (taxable + shipping + tax).quantize(Decimal("0.01"))

        addr_json = json.dumps(
            {
                "full_name": address.full_name,
                "phone": address.phone,
                "line1": address.line1,
                "line2": address.line2,
                "city": address.city,
                "state": address.state,
                "postal_code": address.postal_code,
                "country": address.country,
            }
        )

        order = Order(
            order_number=self._order_number(),
            user_id=user.id,
            status=OrderStatus.PENDING,
            shipping_status=ShippingStatus.NOT_SHIPPED,
            subtotal=subtotal,
            discount_amount=discount_amount,
            shipping_amount=shipping,
            tax_amount=tax,
            total=total,
            coupon_id=coupon.id if coupon else None,
            shipping_address_json=addr_json,
            notes=notes,
            invoice_number=self._invoice_number(),
        )
        self.db.add(order)
        await self.db.flush()

        for item, variant, line_total in line_data:
            self.db.add(
                OrderItem(
                    order_id=order.id,
                    variant_id=variant.id,
                    seller_id=variant.product.seller_id,
                    product_name=variant.product.name,
                    variant_name=variant.name,
                    sku=variant.sku,
                    unit_price=variant.price,
                    quantity=item.quantity,
                    line_total=line_total,
                )
            )
            variant.stock -= item.quantity
            self.db.add(
                InventoryLog(
                    variant_id=variant.id,
                    change=-item.quantity,
                    reason="order_placed",
                    reference=order.order_number,
                )
            )

        if coupon:
            coupon.used_count += 1

        pay_result = self.gateway.create_payment(
            payment_provider, total, "INR", order.order_number
        )
        payment = Payment(
            order_id=order.id,
            provider=payment_provider,
            status=PaymentStatus.PENDING,
            amount=total,
            currency="INR",
            provider_payment_id=pay_result.get("provider_payment_id"),
            provider_order_id=pay_result.get("provider_order_id"),
            raw_response=self.gateway.serialize_raw(pay_result.get("raw")),
        )
        self.db.add(payment)

        await self.cart_service.clear(user)
        await self.db.flush()

        order = await self.get_order(order.id, user)
        return {
            "order": order,
            "client_secret": pay_result.get("client_secret"),
            "razorpay_order_id": pay_result.get("razorpay_order_id"),
            "message": "Order created successfully",
        }

    async def confirm_payment(
        self,
        user: User,
        order_id: int,
        provider_payment_id: str,
        provider_order_id: Optional[str] = None,
    ) -> Order:
        order = await self.get_order(order_id, user)
        if not order.payment:
            raise ValidationError("No payment associated")
        result = self.gateway.confirm_payment(
            order.payment.provider, provider_payment_id, provider_order_id
        )
        order.payment.provider_payment_id = provider_payment_id
        if provider_order_id:
            order.payment.provider_order_id = provider_order_id
        status = result["status"]
        order.payment.status = (
            PaymentStatus.CAPTURED if status == "captured" else PaymentStatus.AUTHORIZED
        )
        order.payment.raw_response = self.gateway.serialize_raw(result.get("raw"))
        order.status = OrderStatus.CONFIRMED
        await self.db.flush()
        return await self.get_order(order_id, user)

    async def get_order(self, order_id: int, user: User) -> Order:
        result = await self.db.execute(
            select(Order)
            .options(
                selectinload(Order.items)
                .selectinload(OrderItem.variant)
                .selectinload(ProductVariant.product),
                selectinload(Order.payment),
            )
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError("Order not found")
        if user.role == UserRole.CUSTOMER and order.user_id != user.id:
            raise ForbiddenError("Not your order")
        if user.role == UserRole.SELLER:
            from models.entities import SellerProfile

            seller = (
                await self.db.execute(
                    select(SellerProfile).where(SellerProfile.user_id == user.id)
                )
            ).scalar_one_or_none()
            if not seller or not any(i.seller_id == seller.id for i in order.items):
                raise ForbiddenError("Not your order")
        return order

    async def list_orders(
        self, user: User, page: int = 1, page_size: int = 20
    ) -> tuple[Sequence[Order], int]:
        q = select(Order).options(selectinload(Order.items), selectinload(Order.payment))
        count_q = select(func.count(Order.id))

        if user.role == UserRole.CUSTOMER:
            q = q.where(Order.user_id == user.id)
            count_q = count_q.where(Order.user_id == user.id)
        elif user.role == UserRole.SELLER:
            from models.entities import SellerProfile

            seller = (
                await self.db.execute(
                    select(SellerProfile).where(SellerProfile.user_id == user.id)
                )
            ).scalar_one_or_none()
            if not seller:
                return [], 0
            q = (
                q.join(OrderItem)
                .where(OrderItem.seller_id == seller.id)
                .distinct()
            )
            count_q = (
                select(func.count(func.distinct(Order.id)))
                .select_from(Order)
                .join(OrderItem)
                .where(OrderItem.seller_id == seller.id)
            )

        total = (await self.db.execute(count_q)).scalar() or 0
        q = q.order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(q)
        return result.scalars().all(), total

    async def cancel_order(self, user: User, order_id: int) -> Order:
        order = await self.get_order(order_id, user)
        if order.status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.REFUNDED):
            raise ValidationError(f"Cannot cancel order in status {order.status.value}")
        if order.status == OrderStatus.CANCELLED:
            return order
        # Restock
        for item in order.items:
            variant = await self.db.get(ProductVariant, item.variant_id)
            if variant:
                variant.stock += item.quantity
                self.db.add(
                    InventoryLog(
                        variant_id=variant.id,
                        change=item.quantity,
                        reason="order_cancelled",
                        reference=order.order_number,
                    )
                )
        order.status = OrderStatus.CANCELLED
        if order.payment and order.payment.status != PaymentStatus.REFUNDED:
            order.payment.status = PaymentStatus.FAILED
        await self.db.flush()
        from services.account_service import AccountService

        await AccountService(self.db).notify(
            order.user_id,
            f"Order {order.order_number} cancelled",
            "Your order has been cancelled.",
            link=f"/orders/{order.id}",
        )
        return await self.get_order(order_id, user)

    async def update_status(
        self,
        user: User,
        order_id: int,
        status: OrderStatus,
        tracking_number: Optional[str] = None,
        shipping_status: Optional[ShippingStatus] = None,
    ) -> Order:
        if user.role not in (UserRole.ADMIN, UserRole.SELLER):
            raise ForbiddenError("Insufficient permissions")
        order = await self.get_order(order_id, user)
        order.status = status
        if tracking_number:
            order.tracking_number = tracking_number
        if shipping_status:
            order.shipping_status = shipping_status
        if status == OrderStatus.SHIPPED and not order.shipping_status:
            order.shipping_status = ShippingStatus.IN_TRANSIT
        if status == OrderStatus.DELIVERED:
            order.shipping_status = ShippingStatus.DELIVERED
        await self.db.flush()

        from services.account_service import AccountService
        from utils.email import send_email
        from app.workers.tasks import notify_order_status

        await AccountService(self.db).notify(
            order.user_id,
            f"Order {order.order_number} updated",
            f"Status is now {status.value}"
            + (f". Tracking: {order.tracking_number}" if order.tracking_number else ""),
            link=f"/orders/{order.id}",
        )
        customer = await self.db.get(User, order.user_id)
        if customer:
            try:
                notify_order_status.delay(customer.email, order.order_number, status.value)
            except Exception:
                send_email(
                    customer.email,
                    f"Order {order.order_number} update",
                    f"<p>Your order status is now <strong>{status.value}</strong>.</p>",
                )

        return await self.get_order(order_id, user)

    async def admin_analytics(self) -> dict:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        today_start = datetime.combine(now.date(), datetime.min.time())
        today_end = datetime.combine(now.date(), datetime.max.time())

        total_orders = (await self.db.execute(select(func.count(Order.id)))).scalar() or 0
        revenue = (
            await self.db.execute(
                select(func.coalesce(func.sum(Order.total), 0)).where(
                    Order.status.notin_([OrderStatus.CANCELLED, OrderStatus.REFUNDED])
                )
            )
        ).scalar() or Decimal("0")
        today_orders = (
            await self.db.execute(
                select(func.count(Order.id)).where(
                    Order.created_at >= today_start, Order.created_at <= today_end
                )
            )
        ).scalar() or 0
        today_revenue = (
            await self.db.execute(
                select(func.coalesce(func.sum(Order.total), 0)).where(
                    Order.created_at >= today_start,
                    Order.created_at <= today_end,
                    Order.status.notin_([OrderStatus.CANCELLED, OrderStatus.REFUNDED]),
                )
            )
        ).scalar() or Decimal("0")
        pending_orders = (
            await self.db.execute(
                select(func.count(Order.id)).where(
                    Order.status.in_([OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PROCESSING])
                )
            )
        ).scalar() or 0
        cancelled_orders = (
            await self.db.execute(
                select(func.count(Order.id)).where(Order.status == OrderStatus.CANCELLED)
            )
        ).scalar() or 0
        total_products = (await self.db.execute(select(func.count(Product.id)))).scalar() or 0
        total_customers = (
            await self.db.execute(
                select(func.count(User.id)).where(User.role == UserRole.CUSTOMER)
            )
        ).scalar() or 0
        low_stock = (
            await self.db.execute(
                select(func.count(ProductVariant.id)).where(ProductVariant.stock < 5)
            )
        ).scalar() or 0

        recent = (
            await self.db.execute(
                select(Order)
                .options(selectinload(Order.items), selectinload(Order.payment))
                .order_by(Order.created_at.desc())
                .limit(10)
            )
        ).scalars().all()

        top_rows = (
            await self.db.execute(
                select(
                    OrderItem.product_name,
                    func.sum(OrderItem.quantity).label("qty"),
                    func.sum(OrderItem.line_total).label("sales"),
                )
                .group_by(OrderItem.product_name)
                .order_by(func.sum(OrderItem.quantity).desc())
                .limit(5)
            )
        ).all()
        top_selling_products = [
            {
                "name": row.product_name,
                "quantity_sold": int(row.qty or 0),
                "sales": float(row.sales or 0),
            }
            for row in top_rows
        ]

        recent_customers = (
            await self.db.execute(
                select(User)
                .where(User.role == UserRole.CUSTOMER)
                .order_by(User.created_at.desc())
                .limit(8)
            )
        ).scalars().all()

        cat_rows = (
            await self.db.execute(
                select(Category.name, func.count(Product.id))
                .outerjoin(Product, Product.category_id == Category.id)
                .group_by(Category.id, Category.name)
                .order_by(func.count(Product.id).desc())
            )
        ).all()
        categories = [{"name": name, "product_count": count} for name, count in cat_rows]

        low_stock_items = (
            await self.db.execute(
                select(ProductVariant, Product)
                .join(Product)
                .where(ProductVariant.stock < 5)
                .order_by(ProductVariant.stock.asc())
                .limit(10)
            )
        ).all()
        low_stock_list = [
            {
                "sku": v.sku,
                "product_name": p.name,
                "stock": v.stock,
            }
            for v, p in low_stock_items
        ]

        notifications = (
            await self.db.execute(
                select(Notification).order_by(Notification.created_at.desc()).limit(12)
            )
        ).scalars().all()

        days = []
        for i in range(6, -1, -1):
            day = (now - timedelta(days=i)).date()
            start = datetime.combine(day, datetime.min.time())
            end = datetime.combine(day, datetime.max.time())
            day_rev = (
                await self.db.execute(
                    select(func.coalesce(func.sum(Order.total), 0)).where(
                        Order.created_at >= start,
                        Order.created_at <= end,
                        Order.status.notin_([OrderStatus.CANCELLED, OrderStatus.REFUNDED]),
                    )
                )
            ).scalar() or Decimal("0")
            day_orders = (
                await self.db.execute(
                    select(func.count(Order.id)).where(
                        Order.created_at >= start, Order.created_at <= end
                    )
                )
            ).scalar() or 0
            days.append(
                {"date": day.isoformat(), "revenue": float(day_rev), "orders": day_orders}
            )

        return {
            "total_orders": total_orders,
            "total_revenue": Decimal(str(revenue)),
            "today_orders": today_orders,
            "today_revenue": Decimal(str(today_revenue)),
            "pending_orders": pending_orders,
            "cancelled_orders": cancelled_orders,
            "total_products": total_products,
            "total_customers": total_customers,
            "low_stock_count": low_stock,
            "low_stock_items": low_stock_list,
            "top_selling_products": top_selling_products,
            "recent_customers": [
                {
                    "id": c.id,
                    "full_name": c.full_name,
                    "email": c.email,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in recent_customers
            ],
            "categories": categories,
            "notifications": [
                {
                    "id": n.id,
                    "title": n.title,
                    "body": n.body,
                    "is_read": n.is_read,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                }
                for n in notifications
            ],
            "recent_orders": recent,
            "sales_by_day": days,
        }

    async def seller_analytics(self, user: User) -> dict:
        from models.entities import SellerProfile

        seller = (
            await self.db.execute(
                select(SellerProfile).where(SellerProfile.user_id == user.id)
            )
        ).scalar_one_or_none()
        if not seller:
            raise ForbiddenError("Seller profile required")

        product_count = (
            await self.db.execute(
                select(func.count(Product.id)).where(Product.seller_id == seller.id)
            )
        ).scalar() or 0

        order_ids = (
            await self.db.execute(
                select(func.distinct(OrderItem.order_id)).where(
                    OrderItem.seller_id == seller.id
                )
            )
        ).scalars().all()

        revenue = Decimal("0")
        if order_ids:
            revenue = (
                await self.db.execute(
                    select(func.coalesce(func.sum(OrderItem.line_total), 0)).where(
                        OrderItem.seller_id == seller.id
                    )
                )
            ).scalar() or Decimal("0")

        low_stock = (
            await self.db.execute(
                select(func.count(ProductVariant.id))
                .join(Product)
                .where(Product.seller_id == seller.id, ProductVariant.stock < 5)
            )
        ).scalar() or 0

        days = []
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for i in range(6, -1, -1):
            day = (now - timedelta(days=i)).date()
            start = datetime.combine(day, datetime.min.time())
            end = datetime.combine(day, datetime.max.time())
            day_rev = (
                await self.db.execute(
                    select(func.coalesce(func.sum(OrderItem.line_total), 0))
                    .join(Order)
                    .where(
                        OrderItem.seller_id == seller.id,
                        Order.created_at >= start,
                        Order.created_at <= end,
                    )
                )
            ).scalar() or Decimal("0")
            day_orders = (
                await self.db.execute(
                    select(func.count(func.distinct(OrderItem.order_id))).where(
                        OrderItem.seller_id == seller.id,
                        OrderItem.order_id.in_(
                            select(Order.id).where(
                                Order.created_at >= start, Order.created_at <= end
                            )
                        ),
                    )
                )
            ).scalar() or 0
            days.append(
                {"date": day.isoformat(), "revenue": float(day_rev), "orders": day_orders}
            )

        recent = []
        if order_ids:
            recent = (
                await self.db.execute(
                    select(Order)
                    .options(selectinload(Order.items), selectinload(Order.payment))
                    .where(Order.id.in_(order_ids))
                    .order_by(Order.created_at.desc())
                    .limit(10)
                )
            ).scalars().all()

        return {
            "total_orders": len(order_ids),
            "total_revenue": Decimal(str(revenue)),
            "total_products": product_count,
            "total_customers": 0,
            "low_stock_count": low_stock,
            "recent_orders": recent,
            "sales_by_day": days,
        }
