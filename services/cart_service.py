"""Shopping cart and wishlist services."""

from decimal import Decimal
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from utils.exceptions import InventoryError, NotFoundError, ValidationError
from models.entities import (
    Cart,
    CartItem,
    Product,
    ProductVariant,
    User,
    WishlistItem,
)


class CartService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _load_cart(self, user_id: int, *, refresh: bool = False) -> Cart | None:
        stmt = (
            select(Cart)
            .options(
                selectinload(Cart.items)
                .selectinload(CartItem.variant)
                .selectinload(ProductVariant.product)
                .selectinload(Product.images)
            )
            .where(Cart.user_id == user_id)
        )
        if refresh:
            stmt = stmt.execution_options(populate_existing=True)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_cart(self, user: User) -> Cart:
        user_id = int(user.id)
        cart = await self._load_cart(user_id)
        if not cart:
            cart = Cart(user_id=user_id)
            self.db.add(cart)
            await self.db.flush()
            cart = await self._load_cart(user_id, refresh=True)
        return cart  # type: ignore[return-value]

    async def _reload(self, user_id: int) -> Cart:
        cart = await self._load_cart(user_id, refresh=True)
        assert cart is not None
        return cart

    def serialize(self, cart: Cart) -> dict:
        items = []
        subtotal = Decimal("0")
        for item in cart.items:
            unit = item.variant.price
            line = unit * item.quantity
            subtotal += line
            images = item.variant.product.images
            primary = next((i.url for i in images if i.is_primary), None)
            if not primary and images:
                primary = images[0].url
            items.append(
                {
                    "id": item.id,
                    "variant_id": item.variant_id,
                    "quantity": item.quantity,
                    "product_name": item.variant.product.name,
                    "variant_name": item.variant.name,
                    "unit_price": unit,
                    "line_total": line,
                    "stock": item.variant.stock,
                    "image_url": primary,
                }
            )
        return {
            "id": cart.id,
            "items": items,
            "subtotal": subtotal,
            "item_count": sum(i.quantity for i in cart.items),
        }

    async def add_item(self, user: User, variant_id: int, quantity: int) -> dict:
        user_id = int(user.id)
        variant = await self.db.get(ProductVariant, variant_id)
        if not variant or not variant.is_active:
            raise NotFoundError("Variant not found")
        if variant.stock < quantity:
            raise InventoryError(f"Only {variant.stock} units available")

        cart = await self.get_or_create_cart(user)
        existing = next((i for i in cart.items if i.variant_id == variant_id), None)
        if existing:
            new_qty = existing.quantity + quantity
            if variant.stock < new_qty:
                raise InventoryError(f"Only {variant.stock} units available")
            existing.quantity = new_qty
        else:
            self.db.add(CartItem(cart_id=cart.id, variant_id=variant_id, quantity=quantity))
        await self.db.flush()
        cart = await self._reload(user_id)
        return self.serialize(cart)

    async def update_item(self, user: User, item_id: int, quantity: int) -> dict:
        user_id = int(user.id)
        cart = await self.get_or_create_cart(user)
        item = next((i for i in cart.items if i.id == item_id), None)
        if not item:
            raise NotFoundError("Cart item not found")
        if item.variant.stock < quantity:
            raise InventoryError(f"Only {item.variant.stock} units available")
        item.quantity = quantity
        await self.db.flush()
        cart = await self._reload(user_id)
        return self.serialize(cart)

    async def remove_item(self, user: User, item_id: int) -> dict:
        user_id = int(user.id)
        cart = await self.get_or_create_cart(user)
        item = next((i for i in cart.items if i.id == item_id), None)
        if not item:
            raise NotFoundError("Cart item not found")
        await self.db.delete(item)
        await self.db.flush()
        cart = await self._reload(user_id)
        return self.serialize(cart)

    async def clear(self, user: User) -> None:
        cart = await self.get_or_create_cart(user)
        for item in list(cart.items):
            await self.db.delete(item)
        await self.db.flush()


class WishlistService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_items(self, user: User) -> List[dict]:
        result = await self.db.execute(
            select(WishlistItem)
            .options(selectinload(WishlistItem.product).selectinload(Product.images))
            .where(WishlistItem.user_id == user.id)
        )
        items = result.scalars().all()
        out = []
        for w in items:
            images = w.product.images
            primary = next((i.url for i in images if i.is_primary), None)
            if not primary and images:
                primary = images[0].url
            out.append(
                {
                    "id": w.id,
                    "product_id": w.product_id,
                    "product_name": w.product.name,
                    "slug": w.product.slug,
                    "base_price": w.product.base_price,
                    "image_url": primary,
                }
            )
        return out

    async def add(self, user: User, product_id: int) -> dict:
        product = await self.db.get(Product, product_id)
        if not product:
            raise NotFoundError("Product not found")
        existing = await self.db.execute(
            select(WishlistItem).where(
                WishlistItem.user_id == user.id, WishlistItem.product_id == product_id
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError("Already in wishlist")
        item = WishlistItem(user_id=user.id, product_id=product_id)
        self.db.add(item)
        await self.db.flush()
        items = await self.list_items(user)
        return next(i for i in items if i["product_id"] == product_id)

    async def remove(self, user: User, product_id: int) -> None:
        result = await self.db.execute(
            select(WishlistItem).where(
                WishlistItem.user_id == user.id, WishlistItem.product_id == product_id
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise NotFoundError("Wishlist item not found")
        await self.db.delete(item)
        await self.db.flush()
