import os
import sys

root_dir = os.path.dirname(__file__)
catalog_service_dir = os.path.join(root_dir, "catalog-service")
order_service_dir = os.path.join(root_dir, "order-service")

for p in [root_dir, catalog_service_dir, order_service_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

