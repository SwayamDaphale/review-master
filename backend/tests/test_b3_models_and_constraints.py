"""Model and constraint unit tests for B3 completion entities.

Covers Identity, Normalized Attributes, Comparison, Operations, and Jobs.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    AttributeDefinition,
    AuditLog,
    Base,
    Category,
    ComparisonItem,
    ComparisonSession,
    ImportToken,
    IngestionJob,
    Product,
    ProductFamily,
    Role,
    User,
    Variant,
    VariantAttributeValue,
    compute_config_hash,
)


@pytest.fixture
def db():
    """Create an isolated in-memory SQLite session with full schema."""
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


def test_user_creation_and_unique_constraint(db):
    """Verify user creation and duplicate email rejection."""
    user1 = User(email="test@example.com", display_name="Test User", is_active=True)
    db.add(user1)
    db.commit()

    assert user1.id is not None
    assert user1.email == "test@example.com"
    assert user1.is_active is True

    # Duplicate email must raise IntegrityError
    user2 = User(email="test@example.com", display_name="Duplicate User")
    db.add(user2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_role_creation_and_user_assignment(db):
    """Verify role creation, uniqueness, and many-to-many user assignment."""
    role = Role(name="admin", description="Administrator")
    db.add(role)
    db.commit()

    assert role.id is not None
    assert role.name == "admin"

    # Duplicate role name must fail
    dup_role = Role(name="admin")
    db.add(dup_role)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # User assignment
    user = User(email="admin@example.com", display_name="Admin User")
    user.roles.append(role)
    db.add(user)
    db.commit()

    reloaded_user = db.get(User, user.id)
    assert reloaded_user is not None
    assert len(reloaded_user.roles) == 1
    assert reloaded_user.roles[0].name == "admin"


def test_attribute_definitions_and_uniqueness(db):
    """Verify attribute definition creation and category-scoped uniqueness."""
    category = Category(key="smartphone", name="Smartphones")
    db.add(category)
    db.commit()

    attr1 = AttributeDefinition(
        key="ram_gb",
        name="RAM",
        category_id=category.id,
        data_type="numeric",
        unit="GB",
    )
    db.add(attr1)
    db.commit()

    assert attr1.id is not None
    assert attr1.unit == "GB"

    # Duplicate (category_id, key) must fail
    attr2 = AttributeDefinition(
        key="ram_gb",
        name="Duplicate RAM",
        category_id=category.id,
        data_type="numeric",
    )
    db.add(attr2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_variant_attribute_values_and_types(db):
    """Verify strongly typed variant attribute values linked to variants."""
    category = Category(key="laptop", name="Laptops")
    db.add(category)
    db.flush()

    family = ProductFamily(category_id=category.id, name="ThinkPad", manufacturer="Lenovo")
    db.add(family)
    db.flush()

    product = Product(
        category_id=category.id,
        family_id=family.id,
        name="ThinkPad T14",
        manufacturer="Lenovo",
    )
    db.add(product)
    db.flush()

    cfg = {"ram_gb": 16, "storage_gb": 512}
    variant = Variant(
        product_id=product.id,
        sku_label="ThinkPad T14 16GB",
        configuration=cfg,
        config_hash=compute_config_hash(cfg),
    )
    db.add(variant)

    attr_ram = AttributeDefinition(key="ram_gb", name="RAM", data_type="numeric", unit="GB")
    attr_proc = AttributeDefinition(key="processor", name="Processor", data_type="string")
    db.add_all([attr_ram, attr_proc])
    db.flush()

    val_ram = VariantAttributeValue(
        variant_id=variant.id,
        attribute_id=attr_ram.id,
        value_numeric=Decimal(16),
        raw_value="16 GB",
    )
    val_proc = VariantAttributeValue(
        variant_id=variant.id,
        attribute_id=attr_proc.id,
        value_text="Intel Core Ultra 7",
        raw_value="Intel Core Ultra 7 155H",
    )
    db.add_all([val_ram, val_proc])
    db.commit()

    reloaded_variant = db.get(Variant, variant.id)
    assert reloaded_variant is not None
    assert len(reloaded_variant.attribute_values) == 2

    # Duplicate value for same (variant_id, attribute_id) must fail
    dup_val = VariantAttributeValue(
        variant_id=variant.id,
        attribute_id=attr_ram.id,
        value_numeric=Decimal(32),
    )
    db.add(dup_val)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_comparison_sessions_and_items(db):
    """Verify comparison session creation and item uniqueness."""
    category = Category(key="phone", name="Phones")
    db.add(category)
    db.flush()

    family = ProductFamily(category_id=category.id, name="Pixel", manufacturer="Google")
    db.add(family)
    db.flush()

    product1 = Product(category_id=category.id, family_id=family.id, name="Pixel 9", manufacturer="Google")
    product2 = Product(category_id=category.id, family_id=family.id, name="Pixel 9 Pro", manufacturer="Google")
    db.add_all([product1, product2])
    db.flush()

    cfg = {"ram_gb": 12}
    variant1 = Variant(
        product_id=product1.id,
        sku_label="Pixel 9 12GB",
        configuration=cfg,
        config_hash=compute_config_hash(cfg),
    )
    db.add(variant1)
    db.flush()

    session = ComparisonSession(
        title="Pixel 9 vs 9 Pro",
        category_id=category.id,
        anonymous_session_token="anon_token_123",
    )
    db.add(session)
    db.flush()

    item1 = ComparisonItem(session_id=session.id, product_id=product1.id, variant_id=variant1.id, position=0)
    item2 = ComparisonItem(session_id=session.id, product_id=product2.id, position=1)
    db.add_all([item1, item2])
    db.commit()

    reloaded_session = db.get(ComparisonSession, session.id)
    assert reloaded_session is not None
    assert len(reloaded_session.items) == 2
    assert reloaded_session.items[0].product.name == "Pixel 9"

    # Duplicate item in the same session must fail
    dup_item = ComparisonItem(session_id=session.id, product_id=product1.id, variant_id=variant1.id, position=2)
    db.add(dup_item)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_audit_log_creation(db):
    """Verify audit log persistence and metadata serialization."""
    audit = AuditLog(
        actor_type="system",
        actor_id="cron_job",
        action="sync_catalog",
        target_type="product",
        target_id=str(uuid.uuid4()),
        status="success",
        request_id="req_abc123",
        metadata_payload={"processed_count": 42},
    )
    db.add(audit)
    db.commit()

    assert audit.id is not None
    assert audit.created_at is not None
    assert audit.metadata_payload == {"processed_count": 42}


def test_import_token_creation_and_hash_uniqueness(db):
    """Verify import token persistence and unique token_hash constraint."""
    expires = datetime.now(UTC)
    token1 = ImportToken(
        token_hash="hash_value_unique_12345",
        context="amazon_import",
        expires_at=expires,
    )
    db.add(token1)
    db.commit()

    assert token1.id is not None
    assert token1.is_revoked is False

    dup_token = ImportToken(
        token_hash="hash_value_unique_12345",
        context="duplicate",
        expires_at=expires,
    )
    db.add(dup_token)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_ingestion_job_reconciliation_fields(db):
    """Verify ingestion_jobs supports job_type and payload for jobs reconciliation."""
    job = IngestionJob(
        idempotency_key="job_key_test_001",
        job_type="background_sync",
        status="pending",
        payload={"batch_size": 100},
    )
    db.add(job)
    db.commit()

    reloaded = db.get(IngestionJob, job.id)
    assert reloaded is not None
    assert reloaded.job_type == "background_sync"
    assert reloaded.payload == {"batch_size": 100}
