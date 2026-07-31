"""Repository / data-access layer."""

from repository.base import BaseRepository
from repository.user_repository import UserRepository
from repository.product_repository import ProductRepository

__all__ = ["BaseRepository", "UserRepository", "ProductRepository"]
