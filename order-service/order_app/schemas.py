import uuid
from datetime import datetime
from decimal import Decimal
from typing import List
from pydantic import BaseModel, ConfigDict, Field


class OrderItemRequest(BaseModel):
    catalog_item_id: uuid.UUID
    quantity: int = Field(gt=0, description="Quantity must be at least 1")


class OrderCreateRequest(BaseModel):
    customer_ref: str = Field(min_length=1, max_length=128, description="Demo customer reference identifier")
    items: List[OrderItemRequest] = Field(min_length=1, description="Order must contain at least one item")


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    catalog_item_id: uuid.UUID
    product_code: str
    product_name: str
    size_ml: int
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    created_at: datetime


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    idempotency_key: str
    customer_ref: str
    status: str
    total_amount: Decimal
    currency: str = "INR"
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse]
