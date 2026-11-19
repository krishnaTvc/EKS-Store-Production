import uuid
import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, asc, desc

from catalog_app.database import get_db
from catalog_app.models import CatalogItem
from catalog_app.schemas import CatalogItemResponse, CatalogItemListResponse
from catalog_app.services.image_service import image_service

router = APIRouter(prefix="/api/catalog", tags=["Catalog Items"])

SORT_COLUMN_MAPPING = {
    "name": CatalogItem.product_name,
    "size": CatalogItem.size_ml,
    "price": CatalogItem.mrp,
    "created_at": CatalogItem.created_at,
}


def _to_response_item(item: CatalogItem) -> CatalogItemResponse:
    return CatalogItemResponse(
        id=item.id,
        product_code=item.product_code,
        supplier_code=item.supplier_code,
        brand_code=item.brand_code,
        product_name=item.product_name,
        category=item.category,
        subcategory=item.subcategory,
        size_ml=item.size_ml,
        size_code=item.size_code,
        mrp=item.mrp,
        currency=item.currency,
        image_key=item.image_key,
        image_url=image_service.resolve_image_url(item.image_key),
        origin_group=item.origin_group,
        country_of_origin=item.country_of_origin,
        source_date=item.source_date,
        source_page=item.source_page,
        active=item.active,
        created_at=item.created_at,
        updated_at=item.updated_at
    )


@router.get("/items", response_model=CatalogItemListResponse, summary="List catalog items with filtering and pagination")
def list_items(
    category: Optional[str] = Query(None, description="Filter by category (e.g. whisky, brandy, beer)"),
    origin_group: Optional[str] = Query(None, description="Filter by origin group ('domestic' or 'foreign')"),
    size_ml: Optional[int] = Query(None, description="Filter by bottle volume in ml (e.g. 180, 375, 750)"),
    search: Optional[str] = Query(None, description="Search term for product name"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    sort_by: str = Query("name", description="Sort by: 'name', 'size', 'price', or 'created_at'"),
    sort_order: str = Query("asc", description="Sort order: 'asc' or 'desc'"),
    active_only: bool = Query(True, description="Return only active items"),
    db: Session = Depends(get_db)
):
    query = db.query(CatalogItem)

    if active_only:
        query = query.filter(CatalogItem.active.is_(True))

    if origin_group:
        query = query.filter(func.lower(CatalogItem.origin_group) == origin_group.lower().strip())

    if category:
        query = query.filter(func.lower(CatalogItem.category) == category.lower().strip())

    if size_ml is not None:
        query = query.filter(CatalogItem.size_ml == size_ml)

    if search:
        search_pattern = f"%{search.strip().lower()}%"
        query = query.filter(func.lower(CatalogItem.product_name).like(search_pattern))

    total = query.count()

    # Allowlisted sorting
    sort_col = SORT_COLUMN_MAPPING.get(sort_by.lower(), CatalogItem.product_name)
    order_func = desc if sort_order.lower() == "desc" else asc
    query = query.order_by(order_func(sort_col))

    # Bounded pagination
    offset = (page - 1) * limit
    items = query.offset(offset).limit(limit).all()

    total_pages = math.ceil(total / limit) if total > 0 else 1

    return CatalogItemListResponse(
        items=[_to_response_item(i) for i in items],
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages
    )


@router.get("/items/{item_id}", response_model=CatalogItemResponse, summary="Get single catalog item by ID")
def get_item(item_id: uuid.UUID, db: Session = Depends(get_db)):
    item = db.query(CatalogItem).filter(CatalogItem.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Catalog item with ID '{item_id}' not found"
        )
    return _to_response_item(item)
