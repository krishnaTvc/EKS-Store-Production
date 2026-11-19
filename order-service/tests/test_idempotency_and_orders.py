import uuid
from decimal import Decimal
import pytest
from fastapi import HTTPException
from order_app.clients.catalog_client import catalog_client


CATALOG_ITEM_A = {
    "id": "11111111-1111-1111-1111-111111111111",
    "product_code": "1715W1139GNN",
    "product_name": "SEAGRAM'S BLENDERS PRIDE EXCLUSIVE PREMIUM WHISKY",
    "size_ml": 180,
    "mrp": "360.00",
    "active": True
}

CATALOG_ITEM_B = {
    "id": "22222222-2222-2222-2222-222222222222",
    "product_code": "1715W1139GQQ",
    "product_name": "SEAGRAM'S BLENDERS PRIDE EXCLUSIVE PREMIUM WHISKY",
    "size_ml": 750,
    "mrp": "1400.00",
    "active": True
}

CATALOG_ITEM_INACTIVE = {
    "id": "33333333-3333-3333-3333-333333333333",
    "product_code": "INACTIVE_01",
    "product_name": "DISCONTINUED SPIRIT",
    "size_ml": 750,
    "mrp": "500.00",
    "active": False
}


@pytest.fixture(autouse=True)
def mock_catalog_client(monkeypatch):
    catalog_store = {
        uuid.UUID(CATALOG_ITEM_A["id"]): dict(CATALOG_ITEM_A),
        uuid.UUID(CATALOG_ITEM_B["id"]): dict(CATALOG_ITEM_B),
        uuid.UUID(CATALOG_ITEM_INACTIVE["id"]): dict(CATALOG_ITEM_INACTIVE)
    }

    def fake_get_item(item_id: uuid.UUID):
        if item_id in catalog_store:
            item = catalog_store[item_id]
            if not item["active"]:
                raise HTTPException(status_code=400, detail="Item inactive")
            return item
        raise HTTPException(status_code=400, detail="Item not found")

    def fake_check_health():
        return True

    monkeypatch.setattr(catalog_client, "get_catalog_item", fake_get_item)
    monkeypatch.setattr(catalog_client, "check_health", fake_check_health)
    return catalog_store


def test_order_creation_flow(client):
    payload = {
        "customer_ref": "cust_andhra_01",
        "items": [
            {"catalog_item_id": CATALOG_ITEM_A["id"], "quantity": 2},
            {"catalog_item_id": CATALOG_ITEM_B["id"], "quantity": 1}
        ]
    }
    headers = {"Idempotency-Key": "order-key-1001"}

    response = client.post("/api/orders", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()

    assert data["status"] == "CREATED"
    assert data["customer_ref"] == "cust_andhra_01"
    assert data["idempotency_key"] == "order-key-1001"

    # Server-side pricing: (360 * 2) + (1400 * 1) = 720 + 1400 = 2120.00
    assert Decimal(str(data["total_amount"])) == Decimal("2120.00")
    assert len(data["items"]) == 2

    order_id = data["id"]
    get_resp = client.get(f"/api/orders/{order_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["total_amount"] == data["total_amount"]


def test_idempotency_retry_returns_same_order(client):
    payload = {
        "customer_ref": "cust_andhra_02",
        "items": [{"catalog_item_id": CATALOG_ITEM_A["id"], "quantity": 1}]
    }
    headers = {"Idempotency-Key": "order-key-1002"}

    resp1 = client.post("/api/orders", json=payload, headers=headers)
    assert resp1.status_code == 201
    order1 = resp1.json()

    # Retry exact same request with same key
    resp2 = client.post("/api/orders", json=payload, headers=headers)
    assert resp2.status_code in (200, 201)
    order2 = resp2.json()

    assert order1["id"] == order2["id"]
    assert order1["total_amount"] == order2["total_amount"]


def test_idempotency_conflict_detection(client):
    payload1 = {
        "customer_ref": "cust_andhra_03",
        "items": [{"catalog_item_id": CATALOG_ITEM_A["id"], "quantity": 1}]
    }
    headers = {"Idempotency-Key": "order-key-1003"}

    resp1 = client.post("/api/orders", json=payload1, headers=headers)
    assert resp1.status_code == 201

    # Conflict: Reuse same key with different payload
    payload2 = {
        "customer_ref": "cust_andhra_03",
        "items": [{"catalog_item_id": CATALOG_ITEM_A["id"], "quantity": 5}]  # Different quantity!
    }
    resp2 = client.post("/api/orders", json=payload2, headers=headers)
    assert resp2.status_code == 409
    assert "conflicting" in resp2.json()["detail"].lower()


def test_price_snapshot_survives_catalog_change(client, mock_catalog_client):
    payload = {
        "customer_ref": "cust_snapshot_test",
        "items": [{"catalog_item_id": CATALOG_ITEM_A["id"], "quantity": 2}]
    }
    headers = {"Idempotency-Key": "snapshot-key-001"}

    resp = client.post("/api/orders", json=payload, headers=headers)
    assert resp.status_code == 201
    order = resp.json()
    order_id = order["id"]

    # Initial line total was 360 * 2 = 720.00
    assert Decimal(str(order["total_amount"])) == Decimal("720.00")

    # Now simulate future price hike in catalog
    mock_catalog_client[uuid.UUID(CATALOG_ITEM_A["id"])]["mrp"] = "999.00"

    # Query existing order again
    get_resp = client.get(f"/api/orders/{order_id}")
    assert get_resp.status_code == 200
    historical_order = get_resp.json()

    # The order must retain original snapshot price of 360 and total 720, NOT the new 999!
    assert Decimal(str(historical_order["total_amount"])) == Decimal("720.00")
    assert Decimal(str(historical_order["items"][0]["unit_price"])) == Decimal("360.00")
    assert Decimal(str(historical_order["items"][0]["line_total"])) == Decimal("720.00")


def test_inactive_item_rejection(client):
    payload = {
        "customer_ref": "cust_inactive_test",
        "items": [{"catalog_item_id": CATALOG_ITEM_INACTIVE["id"], "quantity": 1}]
    }
    headers = {"Idempotency-Key": "inactive-key-001"}

    resp = client.post("/api/orders", json=payload, headers=headers)
    assert resp.status_code == 400


def test_order_health_and_probes(client):
    live_resp = client.get("/health/live")
    assert live_resp.status_code == 200
    assert live_resp.json()["status"] == "UP"

    ready_resp = client.get("/health/ready")
    assert ready_resp.status_code == 200
    assert ready_resp.json()["status"] == "UP"
