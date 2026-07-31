"""Product data access."""

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.entities import Category, Product
from repository.base import BaseRepository


class ProductRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(db)

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        result = await self.db.execute(
            select(Product)
            .options(selectinload(Product.variants), selectinload(Product.images))
            .where(Product.id == product_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Product]:
        result = await self.db.execute(
            select(Product)
            .options(selectinload(Product.variants), selectinload(Product.images))
            .where(Product.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_categories(self, active_only: bool = True) -> Sequence[Category]:
        q = select(Category)
        if active_only:
            q = q.where(Category.is_active.is_(True))
        return (await self.db.execute(q.order_by(Category.name))).scalars().all()
