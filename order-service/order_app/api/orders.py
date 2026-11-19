import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from order_app.database import get_db
from order_app.schemas import OrderCreateRequest, OrderResponse, OrderItemResponse
from order_app.services import order_service

router = APIRouter(prefix="/api/orders", tags=["Orders"])


def _to_response_order(order) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        idempotency_key=order.idempotency_key,
        customer_ref=order.customer_ref,
        status=order.status,
        total_amount=order.total_amount,
        currency=order.currency,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=[
            OrderItemResponse(
                id=item.id,
                catalog_item_id=item.catalog_item_id,
                product_code=item.product_code,
                product_name=item.product_name,
                size_ml=item.size_ml,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.line_total,
                created_at=item.created_at
            ) for item in order.items
        ]
    )


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED, summary="Create a new beverage order")
def create_order(
    payload: OrderCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", description="Unique client idempotency key"),
    db: Session = Depends(get_db)
):
    """
    Creates an order using transactional snapshots from catalog-service.
    Guarantees idempotency via Idempotency-Key header and request fingerprint.
    """
    order = order_service.create_order(payload, idempotency_key, db)
    return _to_response_order(order)


@router.get("/{order_id}", response_model=OrderResponse, summary="Retrieve order by UUID")
def get_order(order_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieves order with historical item snapshots preserved."""
    order = order_service.get_order_by_id(order_id, db)
    return _to_response_order(order)
