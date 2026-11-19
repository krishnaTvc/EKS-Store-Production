"""
End-to-end integration test verifying the complete user workflow:
Catalog browsing -> Filtering -> Cart Snapshot -> Idempotent Checkout -> Order Tracking.
"""

import uuid
import datetime
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from catalog_app.main import app as catalog_app
from catalog_app.database import Base as CatalogBase, get_db as get_catalog_db
from catalog_app.models import CatalogItem

from order_app.main import app as order_app
from order_app.database import Base as OrderBase, get_db as get_order_db
from order_app.clients.catalog_client import catalog_client


@pytest.fixture(scope="function")
def setup_databases(monkeypatch):
    # 1. Setup in-memory catalog database
    catalog_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    CatalogSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=catalog_engine)
    CatalogBase.metadata.create_all(bind=catalog_engine)

    # Seed test items in catalog
    db = CatalogSessionLocal()
    item1 = CatalogItem(
        id=uuid.uuid4(),
        supplier_code="SUP01",
        brand_code="1025",
        product_code="0277",
        product_name="ROYAL RANTHAMBORE HERITAGE COLLECTION-WHISKY",
        category="whisky",
        subcategory="deluxe",
        size_ml=750,
        size_code="B",
        mrp=Decimal("2450.00"),
        source_date=datetime.date(2024, 10, 15),
        source_page=1,
        image_key="catalog/whisky/royal_ranthambore.png"
    )
    item2 = CatalogItem(
        id=uuid.uuid4(),
        supplier_code="SUP01",
        brand_code="1025",
        product_code="0278",
        product_name="ROYAL RANTHAMBORE HERITAGE COLLECTION-WHISKY",
        category="whisky",
        subcategory="deluxe",
        size_ml=375,
        size_code="P",
        mrp=Decimal("1250.00"),
        source_date=datetime.date(2024, 10, 15),
        source_page=1,
        image_key="catalog/whisky/royal_ranthambore.png"
    )
    item3 = CatalogItem(
        id=uuid.uuid4(),
        supplier_code="SUP02",
        brand_code="2030",
        product_code="0904",
        product_name="BUDWEISER MAGNUM PREMIUM BEER",
        category="beer",
        subcategory="premium",
        size_ml=650,
        size_code="B",
        mrp=Decimal("230.00"),
        source_date=datetime.date(2024, 10, 15),
        source_page=2,
        image_key="catalog/beer/budweiser_magnum.png"
    )
    db.add_all([item1, item2, item3])
    db.commit()

    # 2. Setup in-memory order database
    order_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    OrderSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=order_engine)
    OrderBase.metadata.create_all(bind=order_engine)

    def override_catalog_db():
        session = CatalogSessionLocal()
        try:
            yield session
        finally:
            session.close()

    def override_order_db():
        session = OrderSessionLocal()
        try:
            yield session
        finally:
            session.close()

    catalog_app.dependency_overrides[get_catalog_db] = override_catalog_db
    order_app.dependency_overrides[get_order_db] = override_order_db

    catalog_client_inst = TestClient(catalog_app)
    order_client_inst = TestClient(order_app)

    # Mock catalog_client.get_catalog_item in order-service to use catalog TestClient
    def mock_get_catalog_item(catalog_item_id):
        resp = catalog_client_inst.get(f"/api/catalog/items/{catalog_item_id}")
        if resp.status_code == 200:
            return resp.json()
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Item not found")

    def mock_check_health():
        resp = catalog_client_inst.get("/health/live")
        return resp.status_code == 200

    monkeypatch.setattr("order_app.services.order_service.catalog_client.get_catalog_item", mock_get_catalog_item)
    monkeypatch.setattr("order_app.api.health.catalog_client.check_health", mock_check_health)

    yield {
        "catalog_client": catalog_client_inst,
        "order_client": order_client_inst,
        "items": [item1, item2, item3]
    }

    catalog_app.dependency_overrides.clear()
    order_app.dependency_overrides.clear()


def test_full_user_and_order_flow(setup_databases):
    cat_client = setup_databases["catalog_client"]
    ord_client = setup_databases["order_client"]
    items = setup_databases["items"]

    # 1. Browse Categories
    cat_resp = cat_client.get("/api/catalog/categories")
    assert cat_resp.status_code == 200
    categories = cat_resp.json()["categories"]
    assert "whisky" in categories
    assert "beer" in categories

    # 2. Filter by Category and Size
    item_resp = cat_client.get("/api/catalog/items?category=whisky&size_ml=750")
    assert item_resp.status_code == 200
    item_data = item_resp.json()
    assert item_data["total"] == 1
    assert item_data["items"][0]["product_code"] == "0277"
    assert item_data["items"][0]["mrp"] == "2450.00"

    # 3. Add to Cart & Create Order with Idempotency Key
    idempotency_key = str(uuid.uuid4())
    order_payload = {
        "customer_ref": "table_05",
        "items": [
            {"catalog_item_id": str(items[0].id), "quantity": 2},  # 2 x 2450.00 = 4900.00
            {"catalog_item_id": str(items[2].id), "quantity": 3}   # 3 x 230.00 = 690.00
        ]
    }
    # Expected grand total = 4900.00 + 690.00 = 5590.00

    order_resp = ord_client.post(
        "/api/orders",
        json=order_payload,
        headers={"Idempotency-Key": idempotency_key}
    )
    assert order_resp.status_code == 201
    order = order_resp.json()
    assert order["status"] == "CREATED"
    assert order["total_amount"] == "5590.00"
    assert len(order["items"]) == 2

    # Verify item snapshots
    item_snapshots = {i["product_code"]: i for i in order["items"]}
    assert item_snapshots["0277"]["product_name"] == "ROYAL RANTHAMBORE HERITAGE COLLECTION-WHISKY"
    assert item_snapshots["0277"]["unit_price"] == "2450.00"
    assert item_snapshots["0277"]["line_total"] == "4900.00"

    assert item_snapshots["0904"]["product_name"] == "BUDWEISER MAGNUM PREMIUM BEER"
    assert item_snapshots["0904"]["unit_price"] == "230.00"
    assert item_snapshots["0904"]["line_total"] == "690.00"

    # 4. Duplicate Order (Idempotent replay)
    dup_resp = ord_client.post(
        "/api/orders",
        json=order_payload,
        headers={"Idempotency-Key": idempotency_key}
    )
    assert dup_resp.status_code in (200, 201)
    assert dup_resp.json()["id"] == order["id"]
    assert dup_resp.json()["total_amount"] == "5590.00"

    # 5. Order Lookup by UUID (Track Order)
    lookup_resp = ord_client.get(f"/api/orders/{order['id']}")
    assert lookup_resp.status_code == 200
    assert lookup_resp.json()["id"] == order["id"]
    assert lookup_resp.json()["customer_ref"] == "table_05"
    assert lookup_resp.json()["total_amount"] == "5590.00"
