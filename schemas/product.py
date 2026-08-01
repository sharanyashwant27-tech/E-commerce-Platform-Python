"""Product, category, review schemas."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    image_url: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    image_url: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


class VariantCreate(BaseModel):
    sku: str
    name: str
    attributes_json: Optional[str] = None
    price: Decimal = Field(gt=0)
    compare_at_price: Optional[Decimal] = None
    stock: int = Field(ge=0, default=0)


class VariantOut(BaseModel):
    id: int
    product_id: int
    sku: str
    name: str
    attributes_json: Optional[str] = None
    price: Decimal
    compare_at_price: Optional[Decimal] = None
    stock: int
    is_active: bool

    model_config = {"from_attributes": True}


class ImageOut(BaseModel):
    id: int
    url: str
    alt_text: Optional[str] = None
    sort_order: int
    is_primary: bool

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    description: str
    brand: Optional[str] = None
    category_id: int
    base_price: Decimal = Field(gt=0)
    is_featured: bool = False
    variants: List[VariantCreate] = Field(default_factory=list)
    image_urls: List[str] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    brand: Optional[str] = None
    category_id: Optional[int] = None
    base_price: Optional[Decimal] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None


class SellerStoreOut(BaseModel):
    id: int
    store_name: str
    slug: str
    description: Optional[str] = None
    is_approved: bool

    model_config = {"from_attributes": True}


class ProductOut(BaseModel):
    id: int
    name: str
    slug: str
    description: str
    brand: Optional[str] = None
    category_id: int
    seller_id: int
    store_name: Optional[str] = None
    store_slug: Optional[str] = None
    base_price: Decimal
    is_active: bool
    is_featured: bool
    average_rating: Decimal
    review_count: int
    variants: List[VariantOut] = []
    images: List[ImageOut] = []

    model_config = {"from_attributes": True}


class ProductListItem(BaseModel):
    id: int
    name: str
    slug: str
    brand: Optional[str] = None
    base_price: Decimal
    average_rating: Decimal
    review_count: int
    is_featured: bool
    primary_image: Optional[str] = None
    store_name: Optional[str] = None
    store_slug: Optional[str] = None
    match_score: Optional[float] = None

    model_config = {"from_attributes": True}


class ReviewCreate(BaseModel):
    product_id: int
    rating: int = Field(ge=1, le=5)
    title: Optional[str] = None
    body: Optional[str] = None
    comment: Optional[str] = None  # alias for body


class ReviewOut(BaseModel):
    id: int
    user_id: int
    product_id: int
    rating: int
    title: Optional[str] = None
    body: Optional[str] = None
    is_approved: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class InventoryUpdate(BaseModel):
    stock: int = Field(ge=0)
    reason: str = "manual_adjustment"
