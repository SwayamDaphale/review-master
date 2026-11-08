"""Integration tests for smartphone extraction ingestion API endpoints."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.dependencies import get_db
from app.db.seed import seed_database
from app.main import app

CLIENT_PAYLOAD: dict[str, Any] = {
    "schema_version": "1.0",
    "record_id": "test-rec-uuid-001",
    "source": {
        "marketplace": "amazon.in",
        "product_url": "https://www.amazon.in/dp/B0CS6DY3T7",
        "extracted_at": "2026-11-08T01:00:00Z",
        "extraction_method": "browser_extension_user_initiated",
        "extension_version": "1.0.0",
        "page_title": "Samsung Galaxy S24 Ultra 5G (Titanium Black, 12GB, 256GB)",
        "asin": "B0CS6DY3T7",
    },
    "raw_extraction": {
        "title": "Samsung Galaxy S24 Ultra 5G (Titanium Black, 12GB, 256GB)",
        "brand_text": "Samsung",
        "model_text": "Galaxy S24 Ultra",
        "variant_text": "12GB RAM, 256GB",
        "price_text": "₹1,29,999",
        "rating_text": "4.5 out of 5 stars",
        "review_count_text": "1,520 ratings",
        "availability_text": "In stock",
        "specifications_text": [
            {"label": "RAM", "value": "12 GB"},
            {"label": "Memory Storage Capacity", "value": "256 GB"},
            {"label": "Battery Capacity", "value": "5000 mAh"},
        ],
    },
    "normalized": {
        "category": "smartphone",
        "brand": "Samsung",
        "model_name": "Galaxy S24 Ultra",
        "model_number": "SM-S928B",
        "ram_gb": 12,
        "storage_gb": 256,
        "display_size_inches": 6.8,
        "battery_capacity_mah": 5000,
        "operating_system": "Android 14",
        "processor": "Snapdragon 8 Gen 3",
        "supports_5g": True,
        "price_amount": 129999.0,
        "currency": "INR",
        "rating": 4.5,
        "review_count": 1520,
        "availability": "in_stock",
    },
    "validation": {
        "status": "valid",
        "identity_status": "identified",
        "warnings": [],
        "errors": [],
    },
}


@pytest.fixture
def test_client():
    """Set up TestClient with SQLite in-memory database using StaticPool."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    seed_database(db)
    db.close()

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_submit_smartphone_extraction_success(test_client: TestClient):
    """Test successful POST /api/v1/extractions/smartphones."""
    resp = test_client.post(
        "/api/v1/extractions/smartphones",
        json=CLIENT_PAYLOAD,
        headers={"Idempotency-Key": "test-key-001"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert data["match_state"] == "confirmed"
    assert data["record_id"] == "test-rec-uuid-001"
    assert data["asin"] == "B0CS6DY3T7"
    assert data["created"] is True
    assert data["evidence_count"] > 0
    assert data["product_id"] is not None
    assert data["variant_id"] is not None


def test_submit_smartphone_extraction_idempotent(test_client: TestClient):
    """Submitting the same record_id returns HTTP 200 and created=False."""
    # First submission
    resp1 = test_client.post("/api/v1/extractions/smartphones", json=CLIENT_PAYLOAD)
    assert resp1.status_code == 201

    # Second submission with same record_id
    resp2 = test_client.post("/api/v1/extractions/smartphones", json=CLIENT_PAYLOAD)
    assert resp2.status_code == 200, resp2.text
    data = resp2.json()
    assert data["created"] is False
    assert data["record_id"] == "test-rec-uuid-001"


def test_get_extraction_record(test_client: TestClient):
    """Retrieve stored extraction snapshot."""
    test_client.post("/api/v1/extractions/smartphones", json=CLIENT_PAYLOAD)
    resp = test_client.get("/api/v1/extractions/test-rec-uuid-001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["record_id"] == "test-rec-uuid-001"
    assert data["asin"] == "B0CS6DY3T7"
    assert data["raw_payload"]["brand_text"] == "Samsung"
    assert data["normalized_payload"]["ram_gb"] == 12


def test_get_extraction_record_not_found(test_client: TestClient):
    """Unknown record_id returns 404."""
    resp = test_client.get("/api/v1/extractions/non-existent-rec")
    assert resp.status_code == 404


def test_get_listing_detail(test_client: TestClient):
    """Verify listing and seller offers retrieval."""
    ingest_resp = test_client.post(
        "/api/v1/extractions/smartphones", json=CLIENT_PAYLOAD
    )
    listing_id = ingest_resp.json()["listing_id"]

    resp = test_client.get(f"/api/v1/listings/{listing_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == listing_id
    assert data["external_id"] == "B0CS6DY3T7"
    assert len(data["offers"]) > 0
    assert float(data["offers"][0]["current_price"]) == 129999.0


def test_get_evidence_by_variant(test_client: TestClient):
    """Verify evidence retrieval and trust tier classification."""
    ingest_resp = test_client.post(
        "/api/v1/extractions/smartphones", json=CLIENT_PAYLOAD
    )
    var_id = ingest_resp.json()["variant_id"]

    resp = test_client.get(f"/api/v1/evidence?variant_id={var_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0
    for item in data["items"]:
        # ADR-0007 invariant: Marketplace extraction evidence must have trust_tier=2
        assert item["trust_tier"] == 2
        assert item["source_type"] == "marketplace"
        assert len(item["versions"]) > 0
        assert item["versions"][0]["verification_state"] == "unverified"


def test_invalid_contract_rejected_with_422(test_client: TestClient):
    """Submitting malformed payload returns 422 with structured validation errors."""
    invalid = dict(CLIENT_PAYLOAD)
    invalid["schema_version"] = "99.0"  # Invalid version
    resp = test_client.post("/api/v1/extractions/smartphones", json=invalid)
    assert resp.status_code == 422
    data = resp.json()
    assert "detail" in data
