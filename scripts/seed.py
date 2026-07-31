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

from sqlalchemy import func, select

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


# Local product photos (same Unsplash shots as the original seed, stored under
# /static so the storefront does not depend on a remote CDN at runtime).
PRODUCT_IMAGES = {
    "headphones": "/static/images/headphones.jpg",
    "smart-watch-pro": "/static/images/smart-watch.jpg",
    "running-shoes": "/static/images/running-shoes.jpg",
    "leather-wallet": "/static/images/leather-wallet.jpg",
    "ceramic-cookware": "/static/images/cookware.jpg",
    "desk-lamp-led": "/static/images/desk-lamp.jpg",
}
SAMPLE_IMAGES = list(PRODUCT_IMAGES.values())


async def _ensure_extra_sellers(db) -> bool:
    """Upgrade an older single-seller seed to a multi-seller marketplace."""
    count = (await db.execute(select(func.count(SellerProfile.id)))).scalar() or 0
    if count >= 3:
        return False

    async def ensure_seller(email: str, full_name: str, store_name: str, slug: str, description: str):
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if not user:
            user = User(
                email=email,
                hashed_password=hash_password("Seller@12345"),
                full_name=full_name,
                role=UserRole.SELLER,
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            await db.flush()
            db.add(Cart(user_id=user.id))
        profile = (
            await db.execute(select(SellerProfile).where(SellerProfile.user_id == user.id))
        ).scalar_one_or_none()
        if not profile:
            profile = SellerProfile(
                user_id=user.id,
                store_name=store_name,
                slug=slug,
                description=description,
                is_approved=True,
            )
            db.add(profile)
            await db.flush()
        return profile

    fashion = await ensure_seller(
        "seller2@shopsphere.local",
        "Priya Fashion",
        "CraftHaus Fashion",
        "crafthaus-fashion",
        "Apparel, footwear, and accessories",
    )
    home = await ensure_seller(
        "seller3@shopsphere.local",
        "Vikram Home",
        "HomeNest Living",
        "homenest-living",
        "Kitchen and home essentials",
    )
    asha = (
        await db.execute(select(SellerProfile).where(SellerProfile.slug == "asha-electronics"))
    ).scalar_one_or_none()

    # Reassign catalog by category slug / product slug
    products = (await db.execute(select(Product))).scalars().all()
    for p in products:
        if p.slug in ("running-shoes", "leather-wallet") and fashion:
            p.seller_id = fashion.id
        elif p.slug in ("ceramic-cookware", "desk-lamp-led") and home:
            p.seller_id = home.id
        elif asha:
            p.seller_id = asha.id

    await _sync_product_images(db)
    await db.commit()
    print("Marketplace upgrade complete — multiple sellers ready.")
    print("  Seller 1: seller@shopsphere.local / Seller@12345 (Asha Electronics)")
    print("  Seller 2: seller2@shopsphere.local / Seller@12345 (CraftHaus Fashion)")
    print("  Seller 3: seller3@shopsphere.local / Seller@12345 (HomeNest Living)")
    return True


async def _sync_product_images(db) -> int:
    """Point every product image at its local labeled PNG."""
    rows = (
        await db.execute(
            select(ProductImage, Product)
            .join(Product, Product.id == ProductImage.product_id)
            .order_by(Product.id, ProductImage.id)
        )
    ).all()
    changed = 0
    for i, (img, product) in enumerate(rows):
        target = PRODUCT_IMAGES.get(product.slug) or SAMPLE_IMAGES[i % len(SAMPLE_IMAGES)]
        if img.url != target:
            img.url = target
            changed += 1
    return changed


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        existing = await db.execute(select(User).where(User.email == "admin@shopsphere.local"))
        if existing.scalar_one_or_none():
            upgraded = await _ensure_extra_sellers(db)
            if not upgraded:
                changed = await _sync_product_images(db)
                if changed:
                    await db.commit()
                    print(f"Updated {changed} product images to local photo assets.")
                else:
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
        seller_users = [
            User(
                email="seller@shopsphere.local",
                hashed_password=hash_password("Seller@12345"),
                full_name="Asha Merchant",
                role=UserRole.SELLER,
                is_active=True,
                is_verified=True,
            ),
            User(
                email="seller2@shopsphere.local",
                hashed_password=hash_password("Seller@12345"),
                full_name="Priya Fashion",
                role=UserRole.SELLER,
                is_active=True,
                is_verified=True,
            ),
            User(
                email="seller3@shopsphere.local",
                hashed_password=hash_password("Seller@12345"),
                full_name="Vikram Home",
                role=UserRole.SELLER,
                is_active=True,
                is_verified=True,
            ),
        ]
        customer = User(
            email="customer@shopsphere.local",
            hashed_password=hash_password("Customer@12345"),
            full_name="Rohan Buyer",
            role=UserRole.CUSTOMER,
            is_active=True,
            is_verified=True,
            phone="+919876543210",
        )
        db.add_all([admin, *seller_users, customer])
        await db.flush()

        sellers = [
            SellerProfile(
                user_id=seller_users[0].id,
                store_name="Asha Electronics",
                slug="asha-electronics",
                description="Gadgets and lifestyle essentials",
                is_approved=True,
            ),
            SellerProfile(
                user_id=seller_users[1].id,
                store_name="CraftHaus Fashion",
                slug="crafthaus-fashion",
                description="Apparel, footwear, and accessories",
                is_approved=True,
            ),
            SellerProfile(
                user_id=seller_users[2].id,
                store_name="HomeNest Living",
                slug="homenest-living",
                description="Kitchen and home essentials",
                is_approved=True,
            ),
        ]
        db.add_all(sellers)
        db.add(Cart(user_id=customer.id))
        for su in seller_users:
            db.add(Cart(user_id=su.id))

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

        # name, slug, category_idx, seller_idx, brand, price, featured, stock
        products_data = [
            ("Noise Cancelling Headphones", "headphones", 0, 0, "SoundMax", Decimal("4999"), True, 40),
            ("Smart Watch Pro", "smart-watch-pro", 0, 0, "PulseTech", Decimal("7999"), True, 25),
            ("Running Shoes", "running-shoes", 1, 1, "Stride", Decimal("2999"), True, 50),
            ("Leather Wallet", "leather-wallet", 1, 1, "CraftHaus", Decimal("999"), False, 80),
            ("Ceramic Cookware Set", "ceramic-cookware", 2, 2, "HomeNest", Decimal("3499"), True, 15),
            ("Desk Lamp LED", "desk-lamp-led", 2, 2, "Lumen", Decimal("1299"), False, 60),
        ]

        products = []
        for i, (name, slug, cat_i, seller_i, brand, price, featured, stock) in enumerate(
            products_data
        ):
            p = Product(
                seller_id=sellers[seller_i].id,
                category_id=cats[cat_i].id,
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
                    url=PRODUCT_IMAGES.get(slug, SAMPLE_IMAGES[i % len(SAMPLE_IMAGES)]),
                    is_primary=True,
                    sort_order=0,
                )
            )
            products.append((p, v, sellers[seller_i]))

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

        cart = (await db.execute(select(Cart).where(Cart.user_id == customer.id))).scalar_one()
        # Multi-seller cart sample (electronics + fashion)
        db.add(CartItem(cart_id=cart.id, variant_id=products[0][1].id, quantity=1))
        db.add(CartItem(cart_id=cart.id, variant_id=products[2][1].id, quantity=1))

        # Multi-seller delivered order
        p0, v0, s0 = products[1]
        p1, v1, s1 = products[2]
        subtotal = v0.price + v1.price
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
                seller_id=s0.id,
                product_name=p0.name,
                variant_name=v0.name,
                sku=v0.sku,
                unit_price=v0.price,
                quantity=1,
                line_total=v0.price,
            )
        )
        db.add(
            OrderItem(
                order_id=order.id,
                variant_id=v1.id,
                seller_id=s1.id,
                product_name=p1.name,
                variant_name=v1.name,
                sku=v1.sku,
                unit_price=v1.price,
                quantity=1,
                line_total=v1.price,
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

        for p, _, _ in products[:3]:
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
        print("Seed complete — multi-seller marketplace.")
        print("  Admin:    admin@shopsphere.local / Admin@12345")
        print("  Seller 1: seller@shopsphere.local / Seller@12345 (Asha Electronics)")
        print("  Seller 2: seller2@shopsphere.local / Seller@12345 (CraftHaus Fashion)")
        print("  Seller 3: seller3@shopsphere.local / Seller@12345 (HomeNest Living)")
        print("  Customer: customer@shopsphere.local / Customer@12345")
        print("  Coupon:   WELCOME10")
        print("  Stores:   /stores/asha-electronics, /stores/crafthaus-fashion, /stores/homenest-living")


if __name__ == "__main__":
    asyncio.run(seed())
