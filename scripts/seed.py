"""Seed database with sample users, categories, products, orders, and reviews."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from auth.security import hash_password
from utils.enums import (
    OrderStatus,
    PaymentProvider,
    PaymentStatus,
    ShippingStatus,
    UserRole,
)
from models.entities import (
    Address,
    Cart,
    CartItem,
    Category,
    Coupon,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductImage,
    ProductVariant,
    Review,
    SellerProfile,
    User,
)
from models.session import Base, async_session_factory, engine


SAMPLE_IMAGES = [
    "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1560343090-f0409e92791a?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1585386959984-a4155224a1ad?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1491553895911-0055eca6402d?auto=format&fit=crop&w=600&q=80",
]


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        existing = await db.execute(select(User).where(User.email == "admin@shopsphere.local"))
        if existing.scalar_one_or_none():
            print("Database already seeded. Skipping.")
            return

        admin = User(
            email="admin@shopsphere.local",
            hashed_password=hash_password("Admin@12345"),
            full_name="Platform Admin",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
        )
        seller_user = User(
            email="seller@shopsphere.local",
            hashed_password=hash_password("Seller@12345"),
            full_name="Asha Merchant",
            role=UserRole.SELLER,
            is_active=True,
            is_verified=True,
        )
        customer = User(
            email="customer@shopsphere.local",
            hashed_password=hash_password("Customer@12345"),
            full_name="Rohan Buyer",
            role=UserRole.CUSTOMER,
            is_active=True,
            is_verified=True,
            phone="+919876543210",
        )
        db.add_all([admin, seller_user, customer])
        await db.flush()

        seller = SellerProfile(
            user_id=seller_user.id,
            store_name="Asha Electronics",
            slug="asha-electronics",
            description="Gadgets and lifestyle essentials",
            is_approved=True,
        )
        db.add(seller)
        db.add(Cart(user_id=customer.id))
        db.add(Cart(user_id=seller_user.id))

        addr = Address(
            user_id=customer.id,
            label="Home",
            full_name="Rohan Buyer",
            phone="+919876543210",
            line1="12 MG Road",
            line2="Near Metro",
            city="Bengaluru",
            state="Karnataka",
            postal_code="560001",
            country="India",
            is_default=True,
        )
        db.add(addr)
        await db.flush()

        cats = [
            Category(name="Electronics", slug="electronics", description="Phones, audio, wearables"),
            Category(name="Fashion", slug="fashion", description="Apparel and footwear"),
            Category(name="Home", slug="home", description="Kitchen and living"),
        ]
        db.add_all(cats)
        await db.flush()

        products_data = [
            ("Noise Cancelling Headphones", "headphones", cats[0].id, "SoundMax", Decimal("4999"), True, 40),
            ("Smart Watch Pro", "smart-watch-pro", cats[0].id, "PulseTech", Decimal("7999"), True, 25),
            ("Running Shoes", "running-shoes", cats[1].id, "Stride", Decimal("2999"), True, 50),
            ("Leather Wallet", "leather-wallet", cats[1].id, "CraftHaus", Decimal("999"), False, 80),
            ("Ceramic Cookware Set", "ceramic-cookware", cats[2].id, "HomeNest", Decimal("3499"), True, 15),
            ("Desk Lamp LED", "desk-lamp-led", cats[2].id, "Lumen", Decimal("1299"), False, 60),
        ]

        products = []
        for i, (name, slug, cat_id, brand, price, featured, stock) in enumerate(products_data):
            p = Product(
                seller_id=seller.id,
                category_id=cat_id,
                name=name,
                slug=slug,
                description=f"{name} — premium quality with fast delivery.",
                brand=brand,
                base_price=price,
                is_featured=featured,
                is_active=True,
                average_rating=Decimal("4.20"),
                review_count=1,
            )
            db.add(p)
            await db.flush()
            v = ProductVariant(
                product_id=p.id,
                sku=f"SKU-{slug.upper()[:10]}",
                name="Default",
                price=price,
                compare_at_price=price + Decimal("500"),
                stock=stock,
            )
            db.add(v)
            db.add(
                ProductImage(
                    product_id=p.id,
                    url=SAMPLE_IMAGES[i % len(SAMPLE_IMAGES)],
                    is_primary=True,
                    sort_order=0,
                )
            )
            products.append((p, v))

        coupon = Coupon(
            code="WELCOME10",
            description="10% off first order",
            discount_type="percent",
            discount_value=Decimal("10"),
            min_order_amount=Decimal("500"),
            max_discount=Decimal("500"),
            usage_limit=1000,
            is_active=True,
        )
        db.add(coupon)

        # Cart sample
        cart = (await db.execute(select(Cart).where(Cart.user_id == customer.id))).scalar_one()
        db.add(CartItem(cart_id=cart.id, variant_id=products[0][1].id, quantity=1))

        # Sample order
        p0, v0 = products[1]
        subtotal = v0.price
        tax = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
        total = subtotal + tax
        order = Order(
            order_number="SSDEMO0001",
            user_id=customer.id,
            status=OrderStatus.DELIVERED,
            shipping_status=ShippingStatus.DELIVERED,
            subtotal=subtotal,
            discount_amount=Decimal("0"),
            shipping_amount=Decimal("0"),
            tax_amount=tax,
            total=total,
            shipping_address_json=json.dumps(
                {
                    "full_name": addr.full_name,
                    "phone": addr.phone,
                    "line1": addr.line1,
                    "city": addr.city,
                    "state": addr.state,
                    "postal_code": addr.postal_code,
                    "country": addr.country,
                }
            ),
            invoice_number="INV-DEMO0001",
            tracking_number="TRACK123456",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2),
        )
        db.add(order)
        await db.flush()
        db.add(
            OrderItem(
                order_id=order.id,
                variant_id=v0.id,
                seller_id=seller.id,
                product_name=p0.name,
                variant_name=v0.name,
                sku=v0.sku,
                unit_price=v0.price,
                quantity=1,
                line_total=subtotal,
            )
        )
        db.add(
            Payment(
                order_id=order.id,
                provider=PaymentProvider.STRIPE,
                status=PaymentStatus.CAPTURED,
                amount=total,
                currency="INR",
                provider_payment_id="pi_mock_demo",
            )
        )

        for p, _ in products[:3]:
            db.add(
                Review(
                    user_id=customer.id,
                    product_id=p.id,
                    rating=5 if p.id % 2 else 4,
                    title="Great purchase",
                    body="Quality matches the listing. Fast delivery.",
                    is_approved=True,
                )
            )

        await db.commit()
        print("Seed complete.")
        print("  Admin:    admin@shopsphere.local / Admin@12345")
        print("  Seller:   seller@shopsphere.local / Seller@12345")
        print("  Customer: customer@shopsphere.local / Customer@12345")
        print("  Coupon:   WELCOME10")


if __name__ == "__main__":
    asyncio.run(seed())
