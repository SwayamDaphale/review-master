"""Unit tests for deterministic canonical identity and variant resolution."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.seed import seed_database
from app.models.marketplace import Marketplace
from app.schemas.extraction import NormalizedSmartphone
from app.services.identity_resolver import IdentityResolver


@pytest.fixture
def db_session():
    """Create in-memory SQLite engine with StaticPool for isolated identity resolver testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    seed_database(db)
    yield db
    db.close()


def test_exact_product_and_variant_resolution(db_session: Session):
    """Verify exact match for Samsung Galaxy S24 Ultra (12GB/256GB)."""
    mkt = db_session.query(Marketplace).filter_by(key="amazon.in").first()
    assert mkt is not None

    resolver = IdentityResolver(db_session)
    norm = NormalizedSmartphone(
        category="smartphone",
        brand="Samsung",
        model_name="Galaxy S24 Ultra",
        model_number="SM-S928B",
        ram_gb=12,
        storage_gb=256,
    )

    result = resolver.resolve_smartphone(
        marketplace_id=mkt.id,
        asin="B0CS6DY3T7",
        normalized=norm,
        raw_title="Samsung Galaxy S24 Ultra 5G (Titanium Black, 12GB, 256GB Storage)",
    )

    assert result.match_state == "confirmed"
    assert result.product_id is not None
    assert result.variant_id is not None
    assert "Samsung Galaxy S24 Ultra" in (result.product_name or "")
    assert "256GB" in (result.variant_label or "")
    assert result.confidence >= 0.90


def test_distinct_variant_resolution(db_session: Session):
    """Verify different storage configuration matches the distinct 512GB variant."""
    mkt = db_session.query(Marketplace).filter_by(key="amazon.in").first()
    assert mkt is not None

    resolver = IdentityResolver(db_session)
    norm = NormalizedSmartphone(
        category="smartphone",
        brand="Samsung",
        model_name="Galaxy S24 Ultra",
        model_number=None,
        ram_gb=12,
        storage_gb=512,
    )

    result = resolver.resolve_smartphone(
        marketplace_id=mkt.id,
        asin="B0CS6DY3T8",
        normalized=norm,
        raw_title="Samsung Galaxy S24 Ultra 5G (Titanium Gray, 12GB, 512GB Storage)",
    )

    assert result.match_state == "confirmed"
    assert result.variant_id is not None
    assert "512GB" in (result.variant_label or "")


def test_missing_hardware_configuration_yields_probable_match(db_session: Session):
    """When RAM and storage cannot be identified, product is matched but variant remains unresolved."""
    mkt = db_session.query(Marketplace).filter_by(key="amazon.in").first()
    assert mkt is not None

    resolver = IdentityResolver(db_session)
    norm = NormalizedSmartphone(
        category="smartphone",
        brand="Apple",
        model_name="iPhone 16 Pro",
        ram_gb=None,
        storage_gb=None,
    )

    result = resolver.resolve_smartphone(
        marketplace_id=mkt.id,
        asin="B0ABC12345",
        normalized=norm,
        raw_title="Apple iPhone 16 Pro (Natural Titanium)",
    )

    assert result.match_state == "probable"
    assert result.product_id is not None
    assert result.variant_id is None
    assert result.confidence < 0.90


def test_unknown_brand_or_model_yields_unmatched(db_session: Session):
    """Unknown product returns unmatched without guessing."""
    mkt = db_session.query(Marketplace).filter_by(key="amazon.in").first()
    assert mkt is not None

    resolver = IdentityResolver(db_session)
    norm = NormalizedSmartphone(
        category="smartphone",
        brand="UnknownManufacturerX",
        model_name="MysteryPhone 9000",
    )

    result = resolver.resolve_smartphone(
        marketplace_id=mkt.id,
        asin="B0UNKNOWN01",
        normalized=norm,
    )

    assert result.match_state == "unmatched"
    assert result.product_id is None
    assert result.variant_id is None
    assert result.confidence == 0.0
