"""Product catalog, categories, inventory, and reviews."""

import re
from decimal import Decimal
from typing import List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from utils.exceptions import ForbiddenError, NotFoundError, ValidationError
from models.entities import (
    Category,
    InventoryLog,
    Product,
    ProductImage,
    ProductVariant,
    Review,
    SellerProfile,
    User,
)


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text).strip("-")


class ProductService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _unique_slug(self, base: str) -> str:
        slug = slugify(base)
        candidate = slug
        n = 1
        while True:
            result = await self.db.execute(select(Product).where(Product.slug == candidate))
            if not result.scalar_one_or_none():
                return candidate
            n += 1
            candidate = f"{slug}-{n}"

    async def create_category(
        self,
        name: str,
        slug: Optional[str] = None,
        description: Optional[str] = None,
        parent_id: Optional[int] = None,
        image_url: Optional[str] = None,
    ) -> Category:
        cat_slug = slug or slugify(name)
        cat = Category(
            name=name,
            slug=cat_slug,
            description=description,
            parent_id=parent_id,
            image_url=image_url,
        )
        self.db.add(cat)
        await self.db.flush()
        await self.db.refresh(cat)
        return cat

    async def list_categories(self, active_only: bool = True) -> Sequence[Category]:
        q = select(Category)
        if active_only:
            q = q.where(Category.is_active.is_(True))
        q = q.order_by(Category.name)
        result = await self.db.execute(q)
        return result.scalars().all()

    async def get_seller_profile(self, user: User) -> SellerProfile:
        result = await self.db.execute(
            select(SellerProfile).where(SellerProfile.user_id == user.id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise ForbiddenError("Seller profile required")
        return profile

    async def create_product(self, user: User, data: dict) -> Product:
        seller = await self.get_seller_profile(user)
        if not seller.is_approved and user.role.value != "admin":
            raise ForbiddenError("Seller account pending approval")

        slug = data.get("slug") or await self._unique_slug(data["name"])
        product = Product(
            seller_id=seller.id,
            category_id=data["category_id"],
            name=data["name"],
            slug=slug,
            description=data["description"],
            brand=data.get("brand"),
            base_price=data["base_price"],
            is_featured=data.get("is_featured", False),
        )
        self.db.add(product)
        await self.db.flush()

        variants = data.get("variants") or []
        if not variants:
            variants = [
                {
                    "sku": f"{slug.upper()[:12]}-DEF",
                    "name": "Default",
                    "price": data["base_price"],
                    "stock": 10,
                }
            ]
        for v in variants:
            self.db.add(
                ProductVariant(
                    product_id=product.id,
                    sku=v["sku"],
                    name=v["name"],
                    attributes_json=v.get("attributes_json"),
                    price=v["price"],
                    compare_at_price=v.get("compare_at_price"),
                    stock=v.get("stock", 0),
                )
            )

        for i, url in enumerate(data.get("image_urls") or []):
            self.db.add(
                ProductImage(
                    product_id=product.id,
                    url=url,
                    sort_order=i,
                    is_primary=i == 0,
                )
            )

        await self.db.flush()
        return await self.get_product(product.id)

    async def get_product(self, product_id: int) -> Product:
        result = await self.db.execute(
            select(Product)
            .options(
                selectinload(Product.variants),
                selectinload(Product.images),
                selectinload(Product.category),
                selectinload(Product.seller),
            )
            .where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundError("Product not found")
        return product

    async def get_by_slug(self, slug: str, *, require_approved_seller: bool = True) -> Product:
        result = await self.db.execute(
            select(Product)
            .options(
                selectinload(Product.variants),
                selectinload(Product.images),
                selectinload(Product.category),
                selectinload(Product.seller),
            )
            .where(Product.slug == slug)
        )
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundError("Product not found")
        if (
            require_approved_seller
            and product.seller
            and not product.seller.is_approved
        ):
            raise NotFoundError("Product not found")
        return product

    async def get_store_by_slug(self, slug: str) -> SellerProfile:
        result = await self.db.execute(
            select(SellerProfile).where(
                SellerProfile.slug == slug,
                SellerProfile.is_approved.is_(True),
            )
        )
        store = result.scalar_one_or_none()
        if not store:
            raise NotFoundError("Store not found")
        return store

    async def list_stores(self, approved_only: bool = True) -> Sequence[SellerProfile]:
        q = select(SellerProfile).order_by(SellerProfile.store_name)
        if approved_only:
            q = q.where(SellerProfile.is_approved.is_(True))
        result = await self.db.execute(q)
        return result.scalars().all()

    async def list_products(
        self,
        *,
        q: Optional[str] = None,
        category_id: Optional[int] = None,
        seller_id: Optional[int] = None,
        featured: Optional[bool] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        page: int = 1,
        page_size: int = 20,
        active_only: bool = True,
    ) -> tuple[List[Product], int]:
        query = select(Product).options(
            selectinload(Product.images),
            selectinload(Product.seller),
        )
        count_q = select(func.count(Product.id))

        if active_only:
            query = query.where(Product.is_active.is_(True))
            count_q = count_q.where(Product.is_active.is_(True))
            # Public catalog only shows products from approved marketplace sellers
            query = query.join(SellerProfile, Product.seller_id == SellerProfile.id).where(
                SellerProfile.is_approved.is_(True)
            )
            count_q = count_q.join(SellerProfile, Product.seller_id == SellerProfile.id).where(
                SellerProfile.is_approved.is_(True)
            )
        if q:
            like = f"%{q}%"
            query = query.where(Product.name.ilike(like) | Product.description.ilike(like))
            count_q = count_q.where(Product.name.ilike(like) | Product.description.ilike(like))
        if category_id:
            query = query.where(Product.category_id == category_id)
            count_q = count_q.where(Product.category_id == category_id)
        if seller_id:
            query = query.where(Product.seller_id == seller_id)
            count_q = count_q.where(Product.seller_id == seller_id)
        if featured is not None:
            query = query.where(Product.is_featured.is_(featured))
            count_q = count_q.where(Product.is_featured.is_(featured))
        if min_price is not None:
            query = query.where(Product.base_price >= min_price)
            count_q = count_q.where(Product.base_price >= min_price)
        if max_price is not None:
            query = query.where(Product.base_price <= max_price)
            count_q = count_q.where(Product.base_price <= max_price)

        total = (await self.db.execute(count_q)).scalar() or 0
        query = (
            query.order_by(Product.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def update_product(self, user: User, product_id: int, data: dict) -> Product:
        product = await self.get_product(product_id)
        seller = await self.get_seller_profile(user) if user.role.value != "admin" else None
        if seller and product.seller_id != seller.id:
            raise ForbiddenError("Not your product")
        for key, value in data.items():
            if value is not None and hasattr(product, key):
                setattr(product, key, value)
        await self.db.flush()
        return await self.get_product(product_id)

    async def delete_product(self, user: User, product_id: int) -> None:
        product = await self.get_product(product_id)
        if user.role.value != "admin":
            seller = await self.get_seller_profile(user)
            if product.seller_id != seller.id:
                raise ForbiddenError("Not your product")
        product.is_active = False
        await self.db.flush()

    async def update_category(self, category_id: int, data: dict) -> Category:
        cat = await self.db.get(Category, category_id)
        if not cat:
            raise NotFoundError("Category not found")
        for key, value in data.items():
            if value is not None and hasattr(cat, key):
                setattr(cat, key, value)
        await self.db.flush()
        await self.db.refresh(cat)
        return cat

    async def delete_category(self, category_id: int) -> None:
        cat = await self.db.get(Category, category_id)
        if not cat:
            raise NotFoundError("Category not found")
        cat.is_active = False
        await self.db.flush()

    async def update_inventory(
        self, user: User, variant_id: int, stock: int, reason: str
    ) -> ProductVariant:
        result = await self.db.execute(
            select(ProductVariant)
            .options(selectinload(ProductVariant.product))
            .where(ProductVariant.id == variant_id)
        )
        variant = result.scalar_one_or_none()
        if not variant:
            raise NotFoundError("Variant not found")
        if user.role.value != "admin":
            seller = await self.get_seller_profile(user)
            if variant.product.seller_id != seller.id:
                raise ForbiddenError("Not your inventory")
        change = stock - variant.stock
        variant.stock = stock
        self.db.add(
            InventoryLog(
                variant_id=variant.id,
                change=change,
                reason=reason,
            )
        )
        await self.db.flush()
        from utils.inventory_sync import publish_inventory_update

        publish_inventory_update(
            variant_id=variant.id,
            product_id=variant.product_id,
            sku=variant.sku,
            stock=variant.stock,
            product_name=variant.product.name if variant.product else "",
            reason=reason,
            change=change,
        )
        return variant

    async def add_review(
        self, user: User, product_id: int, rating: int, title: Optional[str], body: Optional[str]
    ) -> Review:
        await self.get_product(product_id)
        existing = await self.db.execute(
            select(Review).where(Review.user_id == user.id, Review.product_id == product_id)
        )
        if existing.scalar_one_or_none():
            raise ValidationError("You already reviewed this product")
        review = Review(
            user_id=user.id,
            product_id=product_id,
            rating=rating,
            title=title,
            body=body,
        )
        self.db.add(review)
        await self.db.flush()
        await self._recalc_rating(product_id)
        await self.db.refresh(review)
        return review

    async def _recalc_rating(self, product_id: int) -> None:
        result = await self.db.execute(
            select(func.avg(Review.rating), func.count(Review.id)).where(
                Review.product_id == product_id, Review.is_approved.is_(True)
            )
        )
        avg, count = result.one()
        product = await self.get_product(product_id)
        product.average_rating = Decimal(str(round(float(avg or 0), 2)))
        product.review_count = count or 0
        await self.db.flush()

    async def list_reviews(self, product_id: int) -> Sequence[Review]:
        result = await self.db.execute(
            select(Review)
            .where(Review.product_id == product_id, Review.is_approved.is_(True))
            .order_by(Review.created_at.desc())
        )
        return result.scalars().all()
