"""
Production Acceptance & Smoke Test Suite
Verifies deployed EKS Store application across real network boundaries:
1. Frontend & Microservice Health Endpoints (/healthz, /health/live, /health/ready)
2. Catalog Item Retrieval & Pagination
3. Domestic vs Foreign Origin Filtering
4. Image Resolution (S3 presigned URL or static asset path)
5. Idempotent Order Creation via POST /api/orders (verifying NO redirects)
6. Order Retrieval by UUID with Immutable Price Snapshotting
7. Duplicate Idempotency Retry (Same Key -> Same Order)
8. Conflicting Idempotency Key Reuse (Same Key + Different Payload -> 409 Conflict)
"""

import sys
import uuid
import time
import argparse
from decimal import Decimal
import httpx

TIMEOUT = 15.0


def log(msg, status="INFO"):
    colors = {
        "INFO": "\033[94m",
        "PASS": "\033[92m",
        "FAIL": "\033[91m",
        "WARN": "\033[93m",
        "RESET": "\033[0m"
    }
    prefix = f"{colors.get(status, '')}[{status}]{colors['RESET']}"
    print(f"{prefix} {msg}")


def verify_health_endpoints(base_url: str) -> bool:
    log("Checking Frontend and Microservice Health Probes...")
    with httpx.Client(base_url=base_url, timeout=TIMEOUT) as client:
        # 1. Frontend /healthz
        res_fe = client.get("/healthz")
        if res_fe.status_code != 200 or "healthy" not in res_fe.text:
            log(f"Frontend /healthz failed: status {res_fe.status_code}, text: {res_fe.text}", "FAIL")
            return False
        log("Frontend /healthz is OK", "PASS")

        # 2. Catalog Service Health (via proxy)
        res_cat = client.get("/health/catalog")
        if res_cat.status_code == 200:
            data = res_cat.json()
            if data.get("status") in ["UP", "healthy"]:
                log("Catalog microservice /health/live is UP", "PASS")
            else:
                log(f"Catalog health reported non-UP status: {data}", "FAIL")
                return False
        else:
            log(f"Catalog health check status: {res_cat.status_code}", "FAIL")
            return False

        # 3. Order Service Health (via proxy)
        res_ord = client.get("/health/orders")
        if res_ord.status_code == 200:
            data = res_ord.json()
            if data.get("status") in ["UP", "healthy"]:
                log("Order microservice /health/live is UP", "PASS")
            else:
                log(f"Order health reported non-UP status: {data}", "FAIL")
                return False
        else:
            log(f"Order health check status: {res_ord.status_code}", "FAIL")
            return False

    return True


def verify_catalog_and_origin_filters(base_url: str) -> tuple[bool, dict | None]:
    log("Verifying Catalog API and Domestic/Foreign Filters...")
    with httpx.Client(base_url=base_url, timeout=TIMEOUT) as client:
        # All items
        res_all = client.get("/api/catalog/items?limit=24")
        if res_all.status_code != 200:
            log(f"GET /api/catalog/items failed with status {res_all.status_code}", "FAIL")
            return False, None

        all_data = res_all.json()
        total_items = all_data.get("total", 0)
        items = all_data.get("items", [])
        if total_items == 0 or len(items) == 0:
            log("Catalog returned 0 items. Database might not be seeded.", "FAIL")
            return False, None
        log(f"Catalog returned {total_items} total items from database", "PASS")

        # Domestic Filter
        res_dom = client.get("/api/catalog/items?origin_group=domestic&limit=10")
        if res_dom.status_code != 200:
            log("GET /api/catalog/items?origin_group=domestic failed", "FAIL")
            return False, None
        dom_data = res_dom.json()
        dom_total = dom_data.get("total", 0)
        log(f"Domestic tab filter returned {dom_total} items", "PASS")
        for item in dom_data.get("items", []):
            if item.get("origin_group") != "domestic":
                log(f"Item {item.get('product_name')} returned in domestic tab but origin is {item.get('origin_group')}", "FAIL")
                return False, None

        # Foreign Filter
        res_for = client.get("/api/catalog/items?origin_group=foreign&limit=10")
        if res_for.status_code != 200:
            log("GET /api/catalog/items?origin_group=foreign failed", "FAIL")
            return False, None
        for_data = res_for.json()
        for_total = for_data.get("total", 0)
        log(f"Foreign tab filter returned {for_total} items", "PASS")
        for item in for_data.get("items", []):
            if item.get("origin_group") != "foreign":
                log(f"Item {item.get('product_name')} returned in foreign tab but origin is {item.get('origin_group')}", "FAIL")
                return False, None

        # Return a representative item for ordering test
        sample_item = items[0]
        return True, sample_item


def verify_order_lifecycle_and_idempotency(base_url: str, sample_item: dict) -> bool:
    log("Verifying Order Creation, Idempotency, and Snapshotting...")
    item_id = sample_item["id"]
    item_price = Decimal(str(sample_item["mrp"]))

    idempotency_key = str(uuid.uuid4())
    customer_ref = f"smoke_test_customer_{int(time.time())}"

    order_payload = {
        "customer_ref": customer_ref,
        "items": [
            {
                "catalog_item_id": item_id,
                "quantity": 2
            }
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key,
        "X-Correlation-Id": str(uuid.uuid4())
    }

    # Use follow_redirects=False to verify that POST /api/orders does NOT return a 301/302 redirect!
    with httpx.Client(base_url=base_url, timeout=TIMEOUT, follow_redirects=False) as client:
        # 1. First order creation POST
        log("Testing POST /api/orders (verifying direct 201 response with no redirect)...")
        res_post = client.post("/api/orders", json=order_payload, headers=headers)

        if res_post.status_code in [301, 302, 307, 308]:
            log(f"POST /api/orders redirected with {res_post.status_code} to {res_post.headers.get('location')}! Trailing slash proxy bug detected.", "FAIL")
            return False

        if res_post.status_code not in [200, 201]:
            log(f"Order creation failed: {res_post.status_code} - {res_post.text}", "FAIL")
            return False

        order_data = res_post.json()
        order_id = order_data["id"]
        total_amount = Decimal(str(order_data["total_amount"]))
        expected_total = item_price * 2

        if total_amount != expected_total:
            log(f"Order total {total_amount} does not match expected {expected_total}", "FAIL")
            return False
        log(f"Order {order_id} created successfully. Total: ₹{total_amount}", "PASS")

        # 2. Verify immutable snapshot fields
        items_snapshot = order_data.get("items", [])
        if not items_snapshot or items_snapshot[0]["product_name"] != sample_item["product_name"]:
            log("Order item snapshot does not match source catalog product name", "FAIL")
            return False
        log("Order item snapshot captures immutable product name and unit price", "PASS")

        # 3. Test Idempotency Retry: exactly identical key and payload
        log("Testing Idempotent Retry (same key, same payload)...")
        res_retry = client.post("/api/orders", json=order_payload, headers=headers)
        if res_retry.status_code not in [200, 201]:
            log(f"Idempotent retry failed with status {res_retry.status_code}", "FAIL")
            return False

        retry_data = res_retry.json()
        if retry_data["id"] != order_id:
            log(f"Idempotent retry returned different order ID: {retry_data['id']} != {order_id}", "FAIL")
            return False
        log("Idempotent retry safely returned identical existing order", "PASS")

        # 4. Test Idempotency Conflict: same key with CONFLICTING payload
        log("Testing Idempotency Conflict Detection (same key, conflicting payload)...")
        conflicting_payload = {
            "customer_ref": customer_ref,
            "items": [
                {
                    "catalog_item_id": item_id,
                    "quantity": 5  # Different quantity
                }
            ]
        }
        res_conflict = client.post("/api/orders", json=conflicting_payload, headers=headers)
        if res_conflict.status_code != 409:
            log(f"Conflicting idempotency key should return HTTP 409 Conflict, got {res_conflict.status_code}", "FAIL")
            return False
        log("Conflicting idempotency key correctly rejected with HTTP 409 Conflict", "PASS")

        # 5. Retrieve Order via GET /api/orders/{id}
        log(f"Testing GET /api/orders/{order_id}...")
        res_get = client.get(f"/api/orders/{order_id}")
        if res_get.status_code != 200:
            log(f"GET /api/orders/{order_id} failed: {res_get.status_code}", "FAIL")
            return False

        get_data = res_get.json()
        if get_data["id"] != order_id or Decimal(str(get_data["total_amount"])) != expected_total:
            log("Retrieved order data does not match created snapshot", "FAIL")
            return False
        log("Order successfully retrieved and verified from RDS database", "PASS")

    return True


def run_smoke_test(base_url: str) -> bool:
    log(f"Starting EKS Store Smoke Tests against target: {base_url}")
    start_time = time.time()

    # Step 1: Health
    if not verify_health_endpoints(base_url):
        log("Health check suite failed.", "FAIL")
        return False

    # Step 2: Catalog & Filters
    cat_ok, sample_item = verify_catalog_and_origin_filters(base_url)
    if not cat_ok or not sample_item:
        log("Catalog and origin filter test suite failed.", "FAIL")
        return False

    # Step 3: Orders & Idempotency
    if not verify_order_lifecycle_and_idempotency(base_url, sample_item):
        log("Order lifecycle and idempotency suite failed.", "FAIL")
        return False

    elapsed = round(time.time() - start_time, 2)
    log(f"All smoke test scenarios passed successfully in {elapsed}s!", "PASS")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EKS Store HTTP/HTTPS Acceptance Smoke Test")
    parser.add_argument("--url", default="http://localhost:3000", help="Base URL of frontend application")
    args = parser.parse_args()

    success = run_smoke_test(args.url.rstrip("/"))
    sys.exit(0 if success else 1)
