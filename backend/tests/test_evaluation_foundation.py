"""Tests for evaluation foundation service and endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.dependencies import get_db
from app.db.seed import seed_database
from app.main import app
from app.models.product import Product


@pytest.fixture
def eval_setup():
    """Set up database and test client with StaticPool."""
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
    test_db = TestingSession()
    with TestClient(app) as client:
        yield test_db, client
    test_db.close()
    app.dependency_overrides.clear()


def test_evaluation_foundation_withholds_fabricated_score(eval_setup):
    """Verify that draft model and incomplete evidence strictly yield overall_score=None."""
    db, client = eval_setup

    # Get a smartphone variant
    product = db.query(Product).filter(Product.name.like("%Galaxy S24%")).first()
    assert product is not None
    variant = product.variants[0]

    # POST to trigger evaluation
    resp = client.post(f"/api/v1/variants/{variant.id}/evaluations")
    assert resp.status_code == 201
    data = resp.json()

    assert data["variant_id"] == str(variant.id)
    # Strictly None / null - scores must NEVER be invented
    assert data["overall_score"] is None
    assert data["confidence_state"] in ("unavailable", "limited")
    assert len(data["parameter_results"]) > 0

    for pr in data["parameter_results"]:
        assert pr["score"] is None
        assert pr["status"] == "not_scored"


def test_get_latest_evaluation(eval_setup):
    """Verify retrieving the latest evaluation for a variant."""
    db, client = eval_setup
    product = db.query(Product).filter(Product.name.like("%Galaxy S24%")).first()
    assert product is not None
    variant = product.variants[0]

    # First trigger evaluation so one exists
    post_resp = client.post(f"/api/v1/variants/{variant.id}/evaluations")
    assert post_resp.status_code == 201

    resp = client.get(f"/api/v1/variants/{variant.id}/evaluations/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["variant_id"] == str(variant.id)
    assert data["overall_score"] is None
