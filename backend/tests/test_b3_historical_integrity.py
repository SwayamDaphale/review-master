"""Historical integrity and append-only enforcement tests.

Verifies that price_records, evidence_versions, evaluations, and audit_logs
prevent modification or deletion while permitting new append-only observations.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import engine as pg_engine
from app.models import (
    AuditLog,
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
    EvaluationRepository,
    EvidenceRepository,
    MarketplaceRepository,
    OperationsRepository,
)


@pytest.fixture
def db():
    """Create isolated SQLite in-memory test session with append-only triggers."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    # Attach SQLite append-only triggers to mirror PostgreSQL database triggers
    with engine.connect() as conn:
        for tbl in ["price_records", "evidence_versions", "evaluations", "audit_logs"]:
            conn.execute(
                text(
                    f"CREATE TRIGGER trg_{tbl}_no_update BEFORE UPDATE ON {tbl} "
                    f"BEGIN SELECT RAISE(ABORT, 'Table {tbl} is append-only: updates are prohibited'); END;"
                )
            )
            conn.execute(
                text(
                    f"CREATE TRIGGER trg_{tbl}_no_delete BEFORE DELETE ON {tbl} "
                    f"BEGIN SELECT RAISE(ABORT, 'Table {tbl} is append-only: deletes are prohibited'); END;"
                )
            )
        conn.commit()

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_audit_log_append_only_enforcement(db):
    """Verify audit_logs table prohibits updates and deletes but allows inserts."""
    log = OperationsRepository.create_audit_log(
        db,
        actor_type="user",
        actor_id="user_123",
        action="update_profile",
        target_type="user",
        target_id="user_123",
    )
    db.commit()

    assert log.id is not None

    # Attempt UPDATE via ORM
    with pytest.raises((OperationalError, IntegrityError, DBAPIError)):
        log.status = "tampered"
        db.flush()
    db.rollback()

    # Reload and attempt DELETE
    reloaded = db.get(AuditLog, log.id)
    assert reloaded is not None
    with pytest.raises((OperationalError, IntegrityError, DBAPIError)):
        db.delete(reloaded)
        db.flush()
    db.rollback()

    # Verify original record remains intact
    reloaded2 = db.get(AuditLog, log.id)
    assert reloaded2 is not None
    assert reloaded2.status == "success"

    # Inserting new log must succeed
    new_log = OperationsRepository.create_audit_log(
        db,
        actor_type="system",
        action="audit_check",
        target_type="audit",
    )
    db.commit()
    assert new_log.id is not None


def test_price_records_append_only_enforcement(db):
    """Verify price_records table prohibits updates and deletes."""
    mp = Marketplace(key="amz_test", name="Amazon Test", adapter="amz")
    db.add(mp)
    db.flush()

    now = datetime.now(UTC)
    listing = MarketplaceListing(
        marketplace_id=mp.id,
        external_id="B0PRICE01",
        url="https://amazon.in/dp/B0PRICE01",
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(listing)
    db.flush()

    offer = SellerOffer(
        listing_id=listing.id,
        seller="Retailer",
        current_price=Decimal("1999.00"),
        observed_at=now,
    )
    db.add(offer)
    db.flush()

    price_rec = MarketplaceRepository.record_price(
        db,
        offer_id=offer.id,
        amount=1999.00,
        currency="INR",
    )
    db.commit()

    # Attempt UPDATE
    with pytest.raises((OperationalError, IntegrityError, DBAPIError)):
        price_rec.price = Decimal(999)
        db.flush()
    db.rollback()

    # Attempt DELETE
    reloaded_price = db.get(type(price_rec), price_rec.id)
    assert reloaded_price is not None
    with pytest.raises((OperationalError, IntegrityError, DBAPIError)):
        db.delete(reloaded_price)
        db.flush()
    db.rollback()

    # Inserting a new price observation must succeed
    new_price = MarketplaceRepository.record_price(
        db,
        offer_id=offer.id,
        amount=1899.00,
        currency="INR",
    )
    db.commit()
    assert new_price.id is not None


def test_evidence_versions_append_only_enforcement(db):
    """Verify evidence_versions prohibits modifications while allowing version increments."""
    category = Category(key="cat_ev", name="Evidence Category")
    db.add(category)
    db.flush()

    family = ProductFamily(category_id=category.id, name="Family Ev", manufacturer="Brand")
    db.add(family)
    db.flush()

    prod = Product(category_id=category.id, family_id=family.id, name="Prod Ev", manufacturer="Brand")
    db.add(prod)
    db.flush()

    cfg = {"ram_gb": 8}
    variant = Variant(
        product_id=prod.id,
        sku_label="Variant Ev",
        configuration=cfg,
        config_hash=compute_config_hash(cfg),
    )
    db.add(variant)
    db.flush()

    evidence = EvidenceRepository.create_evidence(
        db,
        variant_id=variant.id,
        parameter_key="battery",
        source_type="marketplace",
    )
    v1 = EvidenceRepository.add_version(
        db,
        evidence_id=evidence.id,
        value={"capacity_mah": 4500},
    )
    db.commit()

    # Attempt UPDATE on version 1
    with pytest.raises((OperationalError, IntegrityError, DBAPIError)):
        v1.raw_source_span = "tampered"
        db.flush()
    db.rollback()

    # Attempt DELETE on version 1
    reloaded_v1 = db.get(type(v1), v1.id)
    assert reloaded_v1 is not None
    with pytest.raises((OperationalError, IntegrityError, DBAPIError)):
        db.delete(reloaded_v1)
        db.flush()
    db.rollback()

    # Append version 2 succeeds
    v2 = EvidenceRepository.add_version(
        db,
        evidence_id=evidence.id,
        value={"capacity_mah": 5000},
    )
    db.commit()
    assert v2.id is not None
    assert v2.version == 2


def test_evaluations_append_only_enforcement(db):
    """Verify evaluations cannot be overwritten or deleted."""
    category = Category(key="cat_eval", name="Eval Cat")
    db.add(category)
    db.flush()

    family = ProductFamily(category_id=category.id, name="Fam Eval", manufacturer="Brand")
    db.add(family)
    db.flush()

    prod = Product(category_id=category.id, family_id=family.id, name="Prod Eval", manufacturer="Brand")
    db.add(prod)
    db.flush()

    cfg = {"storage_gb": 128}
    variant = Variant(
        product_id=prod.id,
        sku_label="Var Eval",
        configuration=cfg,
        config_hash=compute_config_hash(cfg),
    )
    db.add(variant)
    db.flush()

    model = EvaluationModel(category_id=category.id, name="Cat Model")
    db.add(model)
    db.flush()

    model_ver = EvaluationModelVersion(
        model_id=model.id,
        version="1.0.0",
        definition={"parameters": {}},
    )
    db.add(model_ver)
    db.flush()

    eval1 = EvaluationRepository.create_evaluation(
        db,
        variant_id=variant.id,
        model_version_id=model_ver.id,
        confidence_state="high",
        confidence_score=0.9,
        overall_score=80.0,
    )
    db.commit()

    # Attempt UPDATE on evaluation
    with pytest.raises((OperationalError, IntegrityError, DBAPIError)):
        eval1.overall_score = Decimal(99)
        db.flush()
    db.rollback()

    # Attempt DELETE on evaluation
    reloaded_eval1 = db.get(type(eval1), eval1.id)
    assert reloaded_eval1 is not None
    with pytest.raises((OperationalError, IntegrityError, DBAPIError)):
        db.delete(reloaded_eval1)
        db.flush()
    db.rollback()

    # Appending a new evaluation succeeds
    eval2 = EvaluationRepository.create_evaluation(
        db,
        variant_id=variant.id,
        model_version_id=model_ver.id,
        confidence_state="high",
        confidence_score=0.95,
        overall_score=85.0,
    )
    db.commit()
    assert eval2.id is not None


def test_postgresql_database_triggers():
    """Verify PostgreSQL-level append-only triggers directly if connected to PostgreSQL."""
    if pg_engine.dialect.name != "postgresql":
        pytest.skip("Test requires PostgreSQL connection to verify server-side triggers")

    with pg_engine.connect() as conn:
        # Check that trigger function exists
        func_exists = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'prevent_append_only_modification')"
            )
        ).scalar()
        assert func_exists is True, "PostgreSQL trigger function prevent_append_only_modification must exist"

        # Check triggers exist on tables
        for tbl in ["price_records", "evidence_versions", "evaluations", "audit_logs"]:
            trg_exists = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = :tgname)"
                ),
                {"tgname": f"trg_{tbl}_append_only"},
            ).scalar()
            assert trg_exists is True, f"Trigger trg_{tbl}_append_only must exist on {tbl}"
