"""Unit tests for repository create and retrieve operations."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base,
    Category,
    EvaluationModel,
    EvaluationModelVersion,
    Marketplace,
    MarketplaceListing,
    Product,
    ProductFamily,
    SellerOffer,
    Variant,
    compute_config_hash,
)
from app.repositories import (
    AttributeRepository,
    ComparisonRepository,
    EvaluationRepository,
    EvidenceRepository,
    MarketplaceRepository,
    OperationsRepository,
    RoleRepository,
    UserRepository,
)


@pytest.fixture
def db():
    """Create isolated SQLite in-memory test session."""
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


def test_user_and_role_repositories(db):
    """Test UserRepository and RoleRepository operations."""
    user = UserRepository.create(db, email="repo_user@example.com", display_name="Repo User")
    assert user.id is not None
    assert UserRepository.get_by_email(db, "repo_user@example.com") is not None
    assert UserRepository.get_by_id(db, user.id) is not None

    role = RoleRepository.create(db, name="reviewer", description="Product Reviewer")
    assert role.id is not None
    assert RoleRepository.get_by_name(db, "reviewer") is not None

    success = RoleRepository.assign_role_to_user(db, user.id, role.id)
    assert success is True

    roles = RoleRepository.get_user_roles(db, user.id)
    assert len(roles) == 1
    assert roles[0].name == "reviewer"


def test_attribute_repository(db):
    """Test AttributeRepository definition and variant value operations."""
    category = Category(key="gadget", name="Gadgets")
    db.add(category)
    db.flush()

    attr = AttributeRepository.create_definition(
        db,
        key="battery_mah",
        name="Battery Capacity",
        category_id=category.id,
        data_type="numeric",
        unit="mAh",
    )
    assert attr.id is not None
    assert AttributeRepository.get_definition_by_key(db, "battery_mah", category.id) is not None

    family = ProductFamily(category_id=category.id, name="Gadget Family", manufacturer="Acme")
    db.add(family)
    db.flush()

    prod = Product(category_id=category.id, family_id=family.id, name="Gizmo", manufacturer="Acme")
    db.add(prod)
    db.flush()

    cfg = {"battery_mah": 5000}
    variant = Variant(
        product_id=prod.id,
        sku_label="Gizmo 5000mAh",
        configuration=cfg,
        config_hash=compute_config_hash(cfg),
    )
    db.add(variant)
    db.flush()

    val = AttributeRepository.set_variant_value(
        db,
        variant_id=variant.id,
        attribute_id=attr.id,
        value_numeric=5000,
        raw_value="5000 mAh",
    )
    assert val.id is not None

    values = AttributeRepository.get_variant_values(db, variant.id)
    assert len(values) == 1
    assert values[0].value_numeric == Decimal(5000)


def test_comparison_repository(db):
    """Test ComparisonRepository sessions and item operations."""
    category = Category(key="monitor", name="Monitors")
    db.add(category)
    db.flush()

    family = ProductFamily(category_id=category.id, name="UltraSharp", manufacturer="Dell")
    db.add(family)
    db.flush()

    prod1 = Product(category_id=category.id, family_id=family.id, name="U2723QE", manufacturer="Dell")
    prod2 = Product(category_id=category.id, family_id=family.id, name="U3223QE", manufacturer="Dell")
    db.add_all([prod1, prod2])
    db.flush()

    session = ComparisonRepository.create_session(
        db,
        anonymous_session_token="anon_compare_999",
        title="Dell Monitors",
        category_id=category.id,
    )
    assert session.id is not None

    item1 = ComparisonRepository.add_item(db, session_id=session.id, product_id=prod1.id, position=0)
    item2 = ComparisonRepository.add_item(db, session_id=session.id, product_id=prod2.id, position=1)

    items = ComparisonRepository.get_session_items(db, session.id)
    assert len(items) == 2

    # Duplicate add returns existing
    dup = ComparisonRepository.add_item(db, session_id=session.id, product_id=prod1.id, position=0)
    assert dup.id == item1.id

    removed = ComparisonRepository.remove_item(db, session.id, item2.id)
    assert removed is True
    assert len(ComparisonRepository.get_session_items(db, session.id)) == 1


def test_operations_repository(db):
    """Test OperationsRepository audit logs and import tokens."""
    log = OperationsRepository.create_audit_log(
        db,
        actor_type="admin",
        action="update_settings",
        target_type="system",
        status="success",
        metadata_payload={"feature_flag": True},
    )
    assert log.id is not None

    logs = OperationsRepository.list_audit_logs(db, target_type="system")
    assert len(logs) >= 1

    expires = datetime.now(UTC) + timedelta(hours=1)
    token = OperationsRepository.create_import_token(
        db,
        token_hash="sha256_mock_hash_abc",
        expires_at=expires,
        context="user_import",
    )
    assert token.id is not None
    assert OperationsRepository.get_import_token(db, "sha256_mock_hash_abc") is not None

    revoked = OperationsRepository.revoke_import_token(db, "sha256_mock_hash_abc")
    assert revoked is True
    reloaded_token = OperationsRepository.get_import_token(db, "sha256_mock_hash_abc")
    assert reloaded_token is not None
    assert reloaded_token.is_revoked is True

    # Test job recording
    job = OperationsRepository.record_job(
        db,
        idempotency_key="job_key_456",
        job_type="evidence_ingestion",
        status="completed",
        payload={"count": 10},
    )
    assert job.id is not None
    assert job.status == "completed"
    assert job.job_type == "evidence_ingestion"


def test_marketplace_repository(db):
    """Test MarketplaceRepository lookup, offer, and price recording."""
    mp = Marketplace(key="amazon_in", name="Amazon India", adapter="amazon_in")
    db.add(mp)
    db.flush()

    assert MarketplaceRepository.get_by_key(db, "amazon_in") is not None

    now = datetime.now(UTC)
    listing = MarketplaceListing(
        marketplace_id=mp.id,
        external_id="B0TEST1234",
        url="https://amazon.in/dp/B0TEST1234",
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(listing)
    db.flush()

    found_listing = MarketplaceRepository.get_listing_by_external_id(db, mp.id, "B0TEST1234")
    assert found_listing is not None

    offer = SellerOffer(
        listing_id=listing.id,
        seller="Appario Retail",
        current_price=Decimal("49999.00"),
        observed_at=datetime.now(UTC),
    )
    db.add(offer)
    db.flush()

    found_offer = MarketplaceRepository.get_offer_by_seller(db, listing.id, "Appario Retail")
    assert found_offer is not None

    price_rec = MarketplaceRepository.record_price(
        db,
        offer_id=offer.id,
        amount=49999.00,
        currency="INR",
    )
    assert price_rec.id is not None
    assert price_rec.price == Decimal(49999)


def test_evidence_and_evaluation_repositories(db):
    """Test EvidenceRepository and EvaluationRepository operations."""
    category = Category(key="tablet", name="Tablets")
    db.add(category)
    db.flush()

    family = ProductFamily(category_id=category.id, name="iPad", manufacturer="Apple")
    db.add(family)
    db.flush()

    prod = Product(category_id=category.id, family_id=family.id, name="iPad Pro", manufacturer="Apple")
    db.add(prod)
    db.flush()

    cfg = {"storage_gb": 256}
    variant = Variant(
        product_id=prod.id,
        sku_label="iPad Pro 256GB",
        configuration=cfg,
        config_hash=compute_config_hash(cfg),
    )
    db.add(variant)
    db.flush()

    evidence = EvidenceRepository.create_evidence(
        db,
        variant_id=variant.id,
        parameter_key="display",
        source_type="marketplace",
    )
    assert evidence.id is not None

    version = EvidenceRepository.add_version(
        db,
        evidence_id=evidence.id,
        value={"inches": 11.0},
    )
    assert version.id is not None
    assert version.version == 1

    ev_list = EvidenceRepository.get_evidence_by_variant(db, variant.id)
    assert len(ev_list) == 1
    assert len(ev_list[0].versions) == 1

    # Evaluation Model & Version
    model = EvaluationModel(category_id=category.id, name="Tablet Evaluation Model")
    db.add(model)
    db.flush()

    model_ver = EvaluationModelVersion(
        model_id=model.id,
        version="1.0.0",
        definition={"parameters": {"display": {"weight": 0.5}}},
    )
    db.add(model_ver)
    db.flush()

    evaluation = EvaluationRepository.create_evaluation(
        db,
        variant_id=variant.id,
        model_version_id=model_ver.id,
        confidence_state="high",
        confidence_score=0.9,
        overall_score=85.5,
    )
    assert evaluation.id is not None

    param_res = EvaluationRepository.add_parameter_result(
        db,
        evaluation_id=evaluation.id,
        parameter_key="display",
        score=88.0,
        weight=0.5,
    )
    assert param_res.id is not None

    latest_eval = EvaluationRepository.get_latest_evaluation(db, variant.id)
    assert latest_eval is not None
    assert latest_eval.overall_score == Decimal("85.50")
