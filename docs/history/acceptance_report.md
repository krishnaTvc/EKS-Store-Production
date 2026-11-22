> Historical, unverified reference. Use README.md and docs/DEPLOYMENT.md for this edition.

# Production Acceptance & Verification Evidence

This document captures the evidence and verification audit trail for the **EKS Beverage Store** platform deployment.

---

## 1. Acceptance Gates Verification Matrix

| Gate | Acceptance Criteria | Verified Status | Verification Evidence / Log |
|---|---|---|---|
| **1. Real Database Integration** | Query live catalog API; verify records in RDS PostgreSQL | **PASS** | `GET /api/catalog/items` returned 185 items from PostgreSQL; no local fallback active |
| **2. Domestic & Foreign Taxonomy** | Separate tabs return reviewed records with country metadata | **PASS** | `origin_group=domestic` returns 153 items; `origin_group=foreign` returns 32 items |
| **3. Private S3 Image Delivery** | Presigned S3 URLs or local paths; unsigned S3 access denied | **PASS** | Workload identity (`catalog-service-sa`) resolves presigned URLs; S3 public access blocked |
| **4. Idempotent Order Creation** | `POST /api/orders` succeeds without 301/302 redirects | **PASS** | Exact `/api/orders` location verified; HTTP 201 response with immutable snapshot |
| **5. Idempotent Retry Safety** | Replaying request with same key returns existing order | **PASS** | Replayed key returns identical UUID; no duplicate records inserted |
| **6. Conflicting Key Rejection** | Same key with differing payload returns HTTP 409 Conflict | **PASS** | Database uniqueness constraint and payload hash catch conflicts |
| **7. Price Snapshotting** | Updating catalog price does not alter existing order total | **PASS** | Unit prices and line totals stored in `order_items` remain frozen |
| **8. Honest Failure Behavior** | Backend disconnect shows error and disables checkout | **PASS** | Offline fallback removed from production mode; UI shows red error banner |
| **9. Least Privilege Security** | Non-root containers, dropped capabilities, read-only FS | **PASS** | Unprivileged Nginx (UID 101), FastAPI (UID 10001), dropped `ALL` capabilities |
| **10. Disposable Cluster Resilience** | Destroying EKS cluster does not erase customer orders | **PASS** | Platform stack destroyed and recreated; order UUID verified via API |

---

## 2. Automated Test Run Output

```text
============================= test session starts =============================
platform win32 -- Python 3.11.0, pytest-9.2.0, pluggy-1.7.0
rootdir: D:\EKS-Store-Production
plugins: anyio-4.16.0
collected 32 items

catalog-service/tests/test_catalog_api.py ..............                 [ 43%]
catalog-service/tests/test_dataset_import.py ..                          [ 50%]
order-service/tests/test_idempotency_and_orders.py ......                [ 68%]
order-service/tests/test_pricing.py .....                                [ 84%]
tests/test_frontend_assets.py ....                                       [ 96%]
tests/test_full_system_flow.py .                                         [100%]

======================== 32 passed, 1 warning in 5.83s ========================
```

---

## 3. Helm Chart Lint & Template Validation

```text
==> Linting helm/eks-store
[INFO] Chart.yaml: icon is recommended
1 chart(s) linted, 0 chart(s) failed

==> Template Rendering
Rendered Deployments (frontend, catalog-service, order-service)
Rendered Services (frontend, catalog-service, order-service)
Rendered Ingress (ALB Controller with SSL redirect)
Rendered NetworkPolicies (Frontend, Catalog, Orders)
Rendered PodDisruptionBudgets (minAvailable: 1)
Rendered Pre-Deploy Jobs (DB Bootstrap, Catalog Migration, Orders Migration, Seed Job)
Rendered SecretProviderClass (AWS Secrets Store CSI ASCP)
```

---

## 4. Terraform Validation Summary

```text
Stack bootstrap:  terraform fmt OK, terraform validate OK
Stack network:    terraform fmt OK, terraform validate OK
Stack data:       terraform fmt OK, terraform validate OK
Stack platform:   terraform fmt OK, terraform validate OK
Stack addons:     terraform fmt OK, terraform validate OK
```
