import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
    Uuid
)
from sqlalchemy.orm import relationship

from order_app.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    idempotency_key = Column(String(128), unique=True, nullable=False, index=True)
    request_fingerprint = Column(String(64), nullable=False)
    customer_ref = Column(String(128), nullable=False, index=True)
    status = Column(String(32), default="CREATED", nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(8), default="INR", nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Order(id={self.id}, key={self.idempotency_key}, status={self.status}, total={self.total_amount})>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id = Column(Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    catalog_item_id = Column(Uuid, nullable=False)
    product_code = Column(String(64), nullable=False)
    product_name = Column(String(255), nullable=False)
    size_ml = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    line_total = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    order = relationship("Order", back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_order_items_qty_positive"),
        CheckConstraint("unit_price >= 0", name="chk_order_items_price_non_negative"),
    )

    def __repr__(self):
        return f"<OrderItem(product={self.product_name}, qty={self.quantity}, total={self.line_total})>"
