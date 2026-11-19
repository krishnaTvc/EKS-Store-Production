#!/usr/bin/env python3
"""
EKS Beverage Store - Unified Local Services Launcher
Spawns and manages catalog-service (:8001), order-service (:8002),
and the Frontend Reverse Proxy (:3000) concurrently with clean shutdown.
Automatically verifies and seeds the catalog database if empty.
"""

import os
import sys
import time
import subprocess
import signal
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def check_and_seed_catalog():
    """Ensures database has the 185 catalog records seeded."""
    sys.path.insert(0, str(ROOT_DIR / "catalog-service"))
    try:
        from catalog_app.database import engine, Base, SessionLocal
        from catalog_app.models import CatalogItem

        # Create tables if not exist
        Base.metadata.create_all(bind=engine)

        with SessionLocal() as db:
            count = db.query(CatalogItem).count()
            if count == 0:
                print("[INIT] Catalog database is empty. Running initial import...")
                from scripts.import_catalog import import_catalog
                import_catalog(
                    csv_path=str(ROOT_DIR / "data" / "normalized_catalog.csv"),
                    mappings_path=str(ROOT_DIR / "config" / "image_mappings.yaml")
                )
            else:
                print(f"[INIT] Catalog database verified with {count} beverage records.")
    except Exception as e:
        print(f"[WARN] Database verification warning: {e}")


def main():
    print("=" * 65)
    print("      EKS BEVERAGE STORE - CLOUD-NATIVE MICROSERVICES")
    print("=" * 65)

    check_and_seed_catalog()

    python_bin = sys.executable
    processes = []

    try:
        # 1. Start Catalog Service (:8001)
        print("[1/3] Starting catalog-service on port 8001...")
        cat_env = os.environ.copy()
        cat_env["PYTHONPATH"] = str(ROOT_DIR / "catalog-service")
        cat_proc = subprocess.Popen(
            [python_bin, "-m", "uvicorn", "catalog_app.main:app", "--host", "0.0.0.0", "--port", "8001"],
            cwd=str(ROOT_DIR / "catalog-service"),
            env=cat_env
        )
        processes.append(("Catalog Service", cat_proc))

        # 2. Start Order Service (:8002)
        print("[2/3] Starting order-service on port 8002...")
        ord_env = os.environ.copy()
        ord_env["PYTHONPATH"] = str(ROOT_DIR / "order-service")
        ord_proc = subprocess.Popen(
            [python_bin, "-m", "uvicorn", "order_app.main:app", "--host", "0.0.0.0", "--port", "8002"],
            cwd=str(ROOT_DIR / "order-service"),
            env=ord_env
        )
        processes.append(("Order Service", ord_proc))

        # Brief delay to allow backend startup
        time.sleep(1.5)

        # 3. Start Frontend Dev Proxy Server (:3000)
        print("[3/3] Starting Frontend Reverse Proxy on port 3000...")
        front_proc = subprocess.Popen(
            [python_bin, str(ROOT_DIR / "scripts" / "dev_server.py")],
            cwd=str(ROOT_DIR)
        )
        processes.append(("Frontend UI", front_proc))

        print("\n" + "=" * 65)
        print(" ALL SERVICES ARE LIVE & OPERATIONAL:")
        print("  * Frontend UI:            http://localhost:3000")
        print("  * Catalog Swagger Docs:   http://localhost:8001/docs")
        print("  * Order Swagger Docs:     http://localhost:8002/docs")
        print("=" * 65)
        print("Press Ctrl+C to terminate all services.\n")

        # Keep parent alive until interrupted
        while True:
            time.sleep(1)
            for name, p in processes:
                if p.poll() is not None:
                    print(f"[EXIT] {name} exited unexpectedly (code {p.returncode})")
                    raise KeyboardInterrupt

    except KeyboardInterrupt:
        print("\nShutting down all services gracefully...")
        for name, p in processes:
            try:
                print(f" - Stopping {name} (PID {p.pid})...")
                p.terminate()
                p.wait(timeout=3)
            except Exception:
                p.kill()
        print("All services stopped.")


if __name__ == "__main__":
    main()
