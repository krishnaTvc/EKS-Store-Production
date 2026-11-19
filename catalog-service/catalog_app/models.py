import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
    Date,
    DateTime,
    Index,
    CheckConstraint,
    Uuid
)

from catalog_app.database import Base


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    product_code = Column(String(64), unique=True, nullable=False, index=True)
    supplier_code = Column(String(32), nullable=False)
    brand_code = Column(String(32), nullable=False, index=True)
    product_name = Column(String(255), nullable=False, index=True)
    category = Column(String(64), nullable=False, index=True)
    subcategory = Column(String(64), nullable=True)
    size_ml = Column(Integer, nullable=False)
    size_code = Column(String(16), nullable=False)
    mrp = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(8), default="INR", nullable=False)
    image_key = Column(String(255), nullable=True)
    origin_group = Column(String(32), nullable=True, index=True)
    country_of_origin = Column(String(64), nullable=True)
    source_date = Column(Date, nullable=False, default=date(2024, 10, 15))
    source_page = Column(Integer, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_catalog_category_size", "category", "size_ml"),
        Index("ix_catalog_origin_category_size", "origin_group", "category", "size_ml"),
        CheckConstraint("size_ml > 0", name="chk_catalog_items_size_positive"),
        CheckConstraint("mrp >= 0", name="chk_catalog_items_mrp_non_negative"),
        CheckConstraint("origin_group IS NULL OR origin_group IN ('domestic', 'foreign')", name="chk_catalog_items_origin_group"),
    )

    def __repr__(self):
        return f"<CatalogItem(code={self.product_code}, name={self.product_name}, mrp={self.mrp})>"
