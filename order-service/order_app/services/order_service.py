import json
import hashlib
import uuid
import logging
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from order_app.models import Order, OrderItem
from order_app.schemas import OrderCreateRequest, OrderResponse, OrderItemResponse
from order_app.clients.catalog_client import catalog_client
from order_app.services.pricing_service import calculate_line_total, calculate_order_total

logger = logging.getLogger(__name__)


def compute_payload_fingerprint(payload: OrderCreateRequest) -> str:
    """Computes a deterministic SHA256 fingerprint of the request payload."""
    canonical_dict = {
        "customer_ref": payload.customer_ref,
        "items": sorted(
            [{"catalog_item_id": str(i.catalog_item_id), "quantity": i.quantity} for i in payload.items],
            key=lambda x: (x["catalog_item_id"], x["quantity"])
        )
    }
    encoded = json.dumps(canonical_dict, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def create_order(
    payload: OrderCreateRequest,
    idempotency_key: str,
    db: Session
) -> Order:
    key = idempotency_key.strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header 'Idempotency-Key' cannot be empty"
        )

    fingerprint = compute_payload_fingerprint(payload)

    # 1. Check for existing order with this idempotency key
    existing_order = db.query(Order).filter(Order.idempotency_key == key).first()
    if existing_order:
        if existing_order.request_fingerprint == fingerprint:
            logger.info(f"Idempotent hit: returning existing order {existing_order.id} for key '{key}'")
            return existing_order
        else:
            logger.warning(f"Idempotency conflict for key '{key}': different payload fingerprint")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Idempotency key '{key}' was previously used with a conflicting payload"
            )

    # 2. Retrieve catalog item details via catalog HTTP API (never directly from catalog DB)
    order_items_to_create = []
    line_totals = []

    order_id = uuid.uuid4()

    for item_req in payload.items:
        catalog_item = catalog_client.get_catalog_item(item_req.catalog_item_id)

        unit_price = Decimal(str(catalog_item["mrp"]))
        line_total = calculate_line_total(unit_price, item_req.quantity)
        line_totals.append(line_total)

        order_item = OrderItem(
            id=uuid.uuid4(),
            order_id=order_id,
            catalog_item_id=item_req.catalog_item_id,
            product_code=catalog_item["product_code"],
            product_name=catalog_item["product_name"],
            size_ml=catalog_item["size_ml"],
            quantity=item_req.quantity,
            unit_price=unit_price,
            line_total=line_total
        )
        order_items_to_create.append(order_item)

    total_amount = calculate_order_total(line_totals)

    # 3. Create Order entity with initial status CREATED
    new_order = Order(
        id=order_id,
        idempotency_key=key,
        request_fingerprint=fingerprint,
        customer_ref=payload.customer_ref,
        status="CREATED",
        total_amount=total_amount,
        currency="INR",
        items=order_items_to_create
    )

    db.add(new_order)

    try:
        db.commit()
        db.refresh(new_order)
        logger.info(f"Successfully created order {new_order.id} with total {new_order.total_amount} INR")
        return new_order
    except IntegrityError as e:
        db.rollback()
        # Handle concurrent race condition for the same idempotency key
        logger.warning(f"IntegrityError on order commit (likely concurrent duplicate key): {e}")
        existing_concurrent = db.query(Order).filter(Order.idempotency_key == key).first()
        if existing_concurrent:
            if existing_concurrent.request_fingerprint == fingerprint:
                return existing_concurrent
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Idempotency key '{key}' was concurrently used with a different request payload"
                )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save order due to database constraint violation"
        )


def get_order_by_id(order_id: uuid.UUID, db: Session) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID '{order_id}' not found"
        )
    return order
