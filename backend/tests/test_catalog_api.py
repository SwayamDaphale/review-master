"""Integration tests for catalog REST API endpoints (/api/v1/products)."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.dependencies import get_db
from app.db.seed import seed_database
from app.main import app


@pytest.fixture
def client_with_seeded_db():
    """Create test client with an isolated, seeded in-memory SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Seed data
    db = TestingSessionLocal()
    seed_database(db)
    db.close()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_list_products_returns_all_seeded_products(client_with_seeded_db):
    """GET /api/v1/products returns seeded canonical products."""
    response = client_with_seeded_db.get("/api/v1/products")
    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "next_cursor" in data
    items = data["items"]
    assert len(items) == 4

    names = [p["name"] for p in items]
    assert "Apple iPhone 16 Pro" in names
    assert "Samsung Galaxy S24 Ultra" in names
    assert "Lenovo ThinkPad X1 Carbon Gen 12" in names
    assert "Samsung T7 Shield Portable SSD" in names


def test_category_filtering(client_with_seeded_db):
    """GET /api/v1/products?category=smartphone filters correctly."""
    response = client_with_seeded_db.get("/api/v1/products?category=smartphone")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    for p in data["items"]:
        assert p["category"] == "smartphone"


def test_keyword_search(client_with_seeded_db):
    """GET /api/v1/products?q=carbon searches product name/manufacturer."""
    response = client_with_seeded_db.get("/api/v1/products?q=carbon")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Lenovo ThinkPad X1 Carbon Gen 12"


def test_empty_search_results(client_with_seeded_db):
    """GET /api/v1/products?q=nonexistent returns empty list."""
    response = client_with_seeded_db.get("/api/v1/products?q=nonexistent_xyz")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["next_cursor"] is None


def test_invalid_category_returns_404(client_with_seeded_db):
    """GET /api/v1/products?category=unknown returns 404."""
    response = client_with_seeded_db.get(
        "/api/v1/products?category=nonexistent_category"
    )
    assert response.status_code == 404
    data = response.json()
    assert "Category 'nonexistent_category' not found" in data["detail"]


def test_pagination_limit_and_cursor(client_with_seeded_db):
    """GET /api/v1/products?limit=2 honors page limit and produces next_cursor."""
    response = client_with_seeded_db.get("/api/v1/products?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["next_cursor"] is not None

    # Fetch next page using cursor
    cursor = data["next_cursor"]
    response_page2 = client_with_seeded_db.get(
        f"/api/v1/products?limit=2&cursor={cursor}"
    )
    assert response_page2.status_code == 200
    data_page2 = response_page2.json()
    assert len(data_page2["items"]) == 2


def test_product_detail_success(client_with_seeded_db):
    """GET /api/v1/products/{id} returns product with variants."""
    # List to get an ID
    list_res = client_with_seeded_db.get("/api/v1/products?q=S24")
    assert list_res.status_code == 200
    product_id = list_res.json()["items"][0]["id"]

    detail_res = client_with_seeded_db.get(f"/api/v1/products/{product_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()

    assert "product" in detail
    assert "variants" in detail
    assert detail["product"]["id"] == product_id
    assert detail["product"]["name"] == "Samsung Galaxy S24 Ultra"
    assert len(detail["variants"]) == 2

    # Verify variant schema
    v1 = detail["variants"][0]
    assert "configuration" in v1
    assert "label" in v1
    assert "product_id" in v1
    assert v1["product_id"] == product_id


def test_product_detail_404_for_unknown_id(client_with_seeded_db):
    """GET /api/v1/products/{id} returns 404 when product not found."""
    random_uuid = str(uuid.uuid4())
    res = client_with_seeded_db.get(f"/api/v1/products/{random_uuid}")
    assert res.status_code == 404
    assert f"Product with id '{random_uuid}' was not found" in res.json()["detail"]
