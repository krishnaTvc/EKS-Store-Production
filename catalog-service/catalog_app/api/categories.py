from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from catalog_app.database import get_db
from catalog_app.models import CatalogItem
from catalog_app.schemas import CategoryListResponse, SizeListResponse

router = APIRouter(prefix="/api/catalog", tags=["Catalog Metadata"])


@router.get("/categories", response_model=CategoryListResponse, summary="List distinct catalog categories")
def list_categories(db: Session = Depends(get_db)):
    results = (
        db.query(CatalogItem.category)
        .filter(CatalogItem.active.is_(True))
        .distinct()
        .order_by(CatalogItem.category)
        .all()
    )
    categories = [r[0] for r in results]
    return CategoryListResponse(categories=categories, count=len(categories))


@router.get("/sizes", response_model=SizeListResponse, summary="List distinct bottle sizes (in ml)")
def list_sizes(
    category: Optional[str] = Query(None, description="Optional category filter (e.g. whisky)"),
    db: Session = Depends(get_db)
):
    query = db.query(CatalogItem.size_ml).filter(CatalogItem.active.is_(True))

    if category:
        query = query.filter(func.lower(CatalogItem.category) == category.lower().strip())

    results = query.distinct().order_by(CatalogItem.size_ml).all()
    sizes = [r[0] for r in results]
    return SizeListResponse(category=category, sizes=sizes, count=len(sizes))
