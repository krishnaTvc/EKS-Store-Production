import os
import sys
import tempfile
import yaml
import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root and catalog-service to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from catalog_app.models import CatalogItem, Base
from scripts.import_catalog import import_catalog, load_image_mappings


def test_image_mapping_precedence():
    mappings_content = {
        "brand_mappings": {
            "1139": {"s3_key": "catalog/whisky/blenders-pride.jpeg"}
        },
        "product_overrides": {
            "OVERRIDE_CODE": "catalog/whisky/special-edition.jpeg"
        }
    }
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.dump(mappings_content, f)
        temp_file = f.name

    try:
        from pathlib import Path
        brand_map, prod_overrides = load_image_mappings(Path(temp_file))
        assert brand_map["1139"] == "catalog/whisky/blenders-pride.jpeg"
        assert prod_overrides["OVERRIDE_CODE"] == "catalog/whisky/special-edition.jpeg"
    finally:
        os.unlink(temp_file)


def test_rerunnable_import_and_image_preservation():
    db_file = tempfile.mktemp(".db")
    db_url = f"sqlite:///{db_file}"

    # Initial import
    res1 = import_catalog(csv_path="data/normalized_catalog.csv", db_url=db_url)
    assert res1["inserted"] == 185
    assert res1["updated"] == 0

    # Verify items in DB
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    item = session.query(CatalogItem).filter_by(product_code="1715W1139GNN").first()
    assert item is not None
    assert item.image_key == "catalog/whisky/blenders-pride.jpeg"

    # Second import (safe, repeatable rerun)
    res2 = import_catalog(csv_path="data/normalized_catalog.csv", db_url=db_url)
    assert res2["inserted"] == 0
    assert res2["updated"] == 185

    # Verify existing image mapping is preserved
    item_recheck = session.query(CatalogItem).filter_by(product_code="1715W1139GNN").first()
    assert item_recheck.image_key == "catalog/whisky/blenders-pride.jpeg"

    session.close()
    engine.dispose()
    if os.path.exists(db_file):
        try:
            os.unlink(db_file)
        except OSError:
            pass
