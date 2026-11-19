"""
Catalog Import CLI & Seed Pipeline
Reads data/normalized_catalog.csv and config/image_mappings.yaml.
Executes transactional, idempotent upsert into catalog_items table:
  - Upserts by unique product_code
  - Applies image key mappings (product code overrides > brand code mappings)
  - Preserves existing image mappings if new import is null
  - Never erases items missing from newer input
  - Designed for CLI or Kubernetes Job execution
"""

import os
import sys
import csv
import uuid
import yaml
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

# Add catalog-service directory to sys.path
catalog_service_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "catalog-service"))
if catalog_service_path not in sys.path:
    sys.path.insert(0, catalog_service_path)

from catalog_app.models import CatalogItem, Base


def load_image_mappings(mapping_file: Path) -> tuple[dict, dict]:
    """Loads brand mappings and product code overrides from YAML."""
    if not mapping_file.exists():
        print(f"Warning: Image mappings file not found at {mapping_file}")
        return {}, {}

    with open(mapping_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    brand_map = {}
    for code, info in data.get("brand_mappings", {}).items():
        brand_map[str(code).strip()] = info.get("s3_key")

    prod_overrides = {}
    for code, key in data.get("product_overrides", {}).items():
        prod_overrides[str(code).strip()] = key

    return brand_map, prod_overrides


def import_catalog(
    csv_path: str = "data/normalized_catalog.csv",
    mappings_path: str = "config/image_mappings.yaml",
    origins_path: str = "config/origin_mappings.yaml",
    db_url: str | None = None,
    auto_create_schema: bool = False
):
    # Resolve database URL securely from argument, file, or environment
    if not db_url:
        db_url_file = os.getenv("DATABASE_URL_FILE")
        if db_url_file and os.path.isfile(db_url_file):
            with open(db_url_file, "r", encoding="utf-8") as f:
                db_url = f.read().strip()
        elif os.getenv("DATABASE_SECRET_DIR"):
            secret_dir = Path(os.environ["DATABASE_SECRET_DIR"])
            url_file = secret_dir / "DATABASE_URL"
            if url_file.is_file():
                db_url = url_file.read_text(encoding="utf-8").strip()

    db_url = db_url or os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://catalog_user:catalog_pass@localhost:5432/catalog"
    )

    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"Normalized CSV not found at: {csv_path}")

    brand_map, prod_overrides = load_image_mappings(Path(mappings_path))

    # Optional origin mapping fallback
    foreign_origins = {}
    origins_file = Path(origins_path)
    if origins_file.exists():
        with open(origins_file, "r", encoding="utf-8") as f:
            odata = yaml.safe_load(f) or {}
            for b_code, b_info in odata.get("foreign_brands", {}).items():
                foreign_origins[str(b_code).strip()] = (
                    b_info.get("origin_group", "foreign"),
                    b_info.get("country_of_origin", "Scotland")
                )

    engine = create_engine(db_url)
    # Sanitize and hide sensitive credentials in stdout logs
    sanitized_url = engine.url.render_as_string(hide_password=True)
    print(f"Connecting to catalog database at: {sanitized_url}")

    Session = sessionmaker(bind=engine)
    session = Session()

    # In production AWS, migrations own schema creation.
    # Only create tables if explicitly requested or running in-memory sqlite tests.
    if auto_create_schema or db_url.startswith("sqlite"):
        Base.metadata.create_all(engine)

    inserted_count = 0
    updated_count = 0
    skipped_count = 0

    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                prod_code = row["product_code"].strip()
                b_code = row["brand_code"].strip()

                # Determine mapped image key
                mapped_key = None
                if prod_code in prod_overrides:
                    mapped_key = prod_overrides[prod_code]
                elif b_code in brand_map:
                    mapped_key = brand_map[b_code]

                # Determine origin group and country
                origin_grp = row.get("origin_group", "").strip().lower() or None
                country_orig = row.get("country_of_origin", "").strip() or None
                if not origin_grp and b_code in foreign_origins:
                    origin_grp, country_orig = foreign_origins[b_code]
                elif not origin_grp:
                    origin_grp, country_orig = "domestic", "India"

                existing = session.query(CatalogItem).filter_by(product_code=prod_code).first()

                if existing:
                    # Update fields
                    existing.supplier_code = row["supplier_code"].strip()
                    existing.brand_code = b_code
                    existing.product_name = row["product_name"].strip()
                    existing.category = row["category"].strip()
                    existing.subcategory = row["subcategory"].strip() or None
                    existing.size_ml = int(row["size_ml"])
                    existing.size_code = row["size_code"].strip()
                    existing.mrp = Decimal(row["mrp"])
                    existing.currency = row.get("currency", "INR").strip()
                    existing.source_page = int(row["source_page"])
                    existing.active = row.get("active", "True").lower() == "true"
                    existing.origin_group = origin_grp
                    existing.country_of_origin = country_orig
                    existing.updated_at = datetime.utcnow()

                    # Preserve existing image_key if mapped_key is None
                    if mapped_key:
                        existing.image_key = mapped_key

                    updated_count += 1
                else:
                    # Insert new record
                    new_item = CatalogItem(
                        id=uuid.uuid4(),
                        product_code=prod_code,
                        supplier_code=row["supplier_code"].strip(),
                        brand_code=b_code,
                        product_name=row["product_name"].strip(),
                        category=row["category"].strip(),
                        subcategory=row["subcategory"].strip() or None,
                        size_ml=int(row["size_ml"]),
                        size_code=row["size_code"].strip(),
                        mrp=Decimal(row["mrp"]),
                        currency=row.get("currency", "INR").strip(),
                        image_key=mapped_key,
                        origin_group=origin_grp,
                        country_of_origin=country_orig,
                        source_date=date.fromisoformat(row["source_date"].strip()),
                        source_page=int(row["source_page"]),
                        active=row.get("active", "True").lower() == "true",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    session.add(new_item)
                    inserted_count += 1

        session.commit()
        print(f"Catalog import completed successfully!")
        print(f"  Inserted: {inserted_count}")
        print(f"  Updated:  {updated_count}")
        print(f"  Total processed: {inserted_count + updated_count}")
        return {
            "inserted": inserted_count,
            "updated": updated_count,
            "total": inserted_count + updated_count
        }
    except Exception as e:
        session.rollback()
        print(f"Error during catalog import: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    auto_create = "--create-schema" in sys.argv or "--auto-create-schema" in sys.argv
    import_catalog(auto_create_schema=auto_create)
