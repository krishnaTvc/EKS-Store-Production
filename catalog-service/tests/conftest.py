import os
import sys
import uuid
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from catalog_app.database import Base, get_db
from catalog_app.models import CatalogItem
from catalog_app.main import app

from sqlalchemy.pool import StaticPool

# SQLite in-memory database with StaticPool so all connections share the memory DB
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return engine

@pytest.fixture
def db_session(engine):
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    # Clear and seed test items
    session.query(CatalogItem).delete()

    sample_items = [
        CatalogItem(
            id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            product_code="1715W1139GNN",
            supplier_code="1715",
            brand_code="1139",
            product_name="SEAGRAM'S BLENDERS PRIDE EXCLUSIVE PREMIUM WHISKY",
            category="whisky",
            size_ml=180,
            size_code="NN",
            mrp=Decimal("360.00"),
            currency="INR",
            image_key="catalog/whisky/blenders-pride.jpeg",
            source_date=date(2024, 10, 15),
            source_page=1,
            origin_group="domestic",
            country_of_origin="India",
            active=True
        ),
        CatalogItem(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            product_code="1715W1139GQQ",
            supplier_code="1715",
            brand_code="1139",
            product_name="SEAGRAM'S BLENDERS PRIDE EXCLUSIVE PREMIUM WHISKY",
            category="whisky",
            size_ml=750,
            size_code="QQ",
            mrp=Decimal("1400.00"),
            currency="INR",
            image_key="catalog/whisky/blenders-pride.jpeg",
            source_date=date(2024, 10, 15),
            source_page=1,
            origin_group="domestic",
            country_of_origin="India",
            active=True
        ),
        CatalogItem(
            id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            product_code="1679B5118GBS",
            supplier_code="1679",
            brand_code="5118",
            product_name="KINGFISHER ULTRA SUPER PREMIUM LAGER BEER",
            category="beer",
            subcategory="lager",
            size_ml=650,
            size_code="BS",
            mrp=Decimal("220.00"),
            currency="INR",
            image_key="catalog/beer/kingfisher-ultra.jpg",
            source_date=date(2024, 10, 15),
            source_page=5,
            origin_group="domestic",
            country_of_origin="India",
            active=True
        ),
        CatalogItem(
            id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
            product_code="1804Y1109GNN",
            supplier_code="1804",
            brand_code="1109",
            product_name="TI MANSION HOUSE RAREST SPIRIT FRENCH BRANDY",
            category="brandy",
            size_ml=180,
            size_code="NN",
            mrp=Decimal("220.00"),
            currency="INR",
            image_key=None,  # Tests unmapped placeholder
            source_date=date(2024, 10, 15),
            source_page=3,
            origin_group="foreign",
            country_of_origin="France",
            active=True
        ),
        CatalogItem(
            id=uuid.UUID("55555555-5555-5555-5555-555555555555"),
            product_code="INACTIVE001",
            supplier_code="9999",
            brand_code="9999",
            product_name="DISCONTINUED PRODUCT",
            category="whisky",
            size_ml=750,
            size_code="QQ",
            mrp=Decimal("500.00"),
            currency="INR",
            image_key=None,
            source_date=date(2024, 10, 15),
            source_page=1,
            active=False  # Inactive item
        ),
    ]

    session.add_all(sample_items)
    session.commit()

    yield session

    session.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
