"""Unit tests for catalog database models, constraints, and configuration hashing."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base,
    Category,
    Product,
    ProductFamily,
    Variant,
    compute_config_hash,
)


@pytest.fixture
def db_session():
    """Create an isolated in-memory SQLite session for model testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_deterministic_config_hash():
    """Verify compute_config_hash produces identical hashes regardless of key ordering."""
    cfg1 = {"ram_gb": 8, "storage_gb": 128, "color": "Blue"}
    cfg2 = {"color": "Blue", "storage_gb": 128, "ram_gb": 8}
    cfg3 = {"ram_gb": 8, "storage_gb": 256, "color": "Blue"}

    hash1 = compute_config_hash(cfg1)
    hash2 = compute_config_hash(cfg2)
    hash3 = compute_config_hash(cfg3)

    assert hash1 == hash2, (
        "Identical configurations with different key order must yield identical hashes"
    )
    assert hash1 != hash3, "Different configurations must yield distinct hashes"
    assert len(hash1) == 64, "SHA-256 hash must be 64 characters long"


def test_category_unique_constraint(db_session):
    """Verify category key must be unique."""
    cat1 = Category(key="smartphone", name="Smartphones")
    db_session.add(cat1)
    db_session.commit()

    cat2 = Category(key="smartphone", name="Duplicate Smartphones")
    db_session.add(cat2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_product_and_variant_creation(db_session):
    """Verify creating a product with variants and relationships."""
    cat = Category(key="smartphone", name="Smartphones")
    db_session.add(cat)
    db_session.flush()

    family = ProductFamily(category_id=cat.id, name="Galaxy S", manufacturer="Samsung")
    db_session.add(family)
    db_session.flush()

    product = Product(
        category_id=cat.id,
        family_id=family.id,
        name="Samsung Galaxy S24",
        manufacturer="Samsung",
        mpn="SM-S921B",
    )
    db_session.add(product)
    db_session.flush()

    cfg = {"ram_gb": 8, "storage_gb": 128}
    variant = Variant(
        product_id=product.id,
        configuration=cfg,
        config_hash=compute_config_hash(cfg),
        sku_label="Samsung Galaxy S24 128GB",
    )
    db_session.add(variant)
    db_session.commit()

    # Query back
    fetched_product = db_session.get(Product, product.id)
    assert fetched_product is not None
    assert fetched_product.name == "Samsung Galaxy S24"
    assert fetched_product.category.key == "smartphone"
    assert fetched_product.family.name == "Galaxy S"
    assert len(fetched_product.variants) == 1
    assert fetched_product.variants[0].sku_label == "Samsung Galaxy S24 128GB"


def test_duplicate_variant_prevention(db_session):
    """Verify unique constraint on (product_id, config_hash) prevents duplicate variants."""
    cat = Category(key="smartphone", name="Smartphones")
    db_session.add(cat)
    db_session.flush()

    product = Product(
        category_id=cat.id,
        name="iPhone 16",
        manufacturer="Apple",
    )
    db_session.add(product)
    db_session.flush()

    cfg = {"storage_gb": 128}
    config_hash = compute_config_hash(cfg)

    v1 = Variant(
        product_id=product.id,
        configuration=cfg,
        config_hash=config_hash,
        sku_label="iPhone 16 128GB Black",
    )
    db_session.add(v1)
    db_session.commit()

    v2 = Variant(
        product_id=product.id,
        configuration=cfg,
        config_hash=config_hash,
        sku_label="iPhone 16 128GB White (Same Config)",
    )
    db_session.add(v2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
