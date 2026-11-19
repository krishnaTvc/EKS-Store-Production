import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class CatalogItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_code: str
    supplier_code: str
    brand_code: str
    product_name: str
    category: str
    subcategory: Optional[str] = None
    size_ml: int
    size_code: str
    mrp: Decimal
    currency: str = "INR"
    image_key: Optional[str] = None
    image_url: str
    origin_group: Optional[str] = None
    country_of_origin: Optional[str] = None
    source_date: date
    source_page: int
    active: bool
    created_at: datetime
    updated_at: datetime


class CatalogItemListResponse(BaseModel):
    items: List[CatalogItemResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class CategoryListResponse(BaseModel):
    categories: List[str]
    count: int


class SizeListResponse(BaseModel):
    category: Optional[str] = None
    sizes: List[int]
    count: int
