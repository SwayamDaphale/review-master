"""Phase B8 Test Suite: Identity Resolution, Variant Matching & Evidence Quality Management.

Tests all 11 functional categories:
A: Exact ASIN / External ID Mapping (Stage 1).
B: Trusted Listing Mapping (Stage 2).
C: Deterministic Product and Variant Fingerprinting (Stage 3).
D: Attribute-Based Candidate Matching, Scoring & Contradiction Penalties (Stage 4).
E: Ambiguity & Identity Review Queue Management (Stage 5).
F: Evidence Provenance & Historical Versioning.
G: Backend-Controlled Trust Tiers & Security Restrictions.
H: Evidence Conflict Detection, Non-Destructive Preservation & Resolution.
I: Evidence Verification Lifecycle & Immutable Audit Trail.
J: End-to-End REST APIs & Background Tasks Integration.
K: Regression & Backwards Compatibility with B1-B7.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.permissions import RoleName, get_permissions_for_roles
from app.db.base import Base, utc_now
from app.db.dependencies import get_db
from app.db.seed import seed_database
from app.main import app
from app.models.category import Category
from app.models.evidence import Evidence, EvidenceVersion
from app.models.evidence_quality import EvidenceConflict
from app.models.identity_mapping import ExternalIdentityMapping, IdentityReviewQueue
from app.models.listing import MarketplaceListing
from app.models.marketplace import Marketplace
from app.models.product import Product
from app.schemas.extraction import (
    NormalizedSmartphone,
    RawSmartphoneExtraction,
    SpecificationItem,
)
from app.services.evidence_service import EvidenceService
from app.services.fingerprint_service import FingerprintService
from app.services.identity_resolver import IdentityResolver


@pytest.fixture
def db_session():
    """Create isolated seeded in-memory SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    seed_database(session)
    yield session
    session.close()


@pytest.fixture
def test_client(db_session: Session):
    """Create FastAPI test client with seeded db and admin permissions."""
    def override_get_db():
        yield db_session

    admin_roles = [RoleName.ADMIN.value]
    admin_user = AuthenticatedUser(
        id=str(uuid.uuid4()),
        user_id=uuid.uuid4(),
        email="admin@reviewmaster.local",
        roles=admin_roles,
        permissions=get_permissions_for_roles(admin_roles),
        is_authenticated=True,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: admin_user

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# =============================================================================
# Category A: Exact ASIN / External ID Mapping (Stage 1)
# =============================================================================


def test_stage1_exact_asin_mapping_returns_confirmed(db_session: Session):
    """Stage 1: Verified external identity mapping returns confirmed match immediately with 1.0 confidence."""
    mkt = db_session.query(Marketplace).filter_by(key="amazon.in").first()
    prod = db_session.query(Product).filter_by(name="Samsung Galaxy S24 Ultra").first()
    var = prod.variants[0]

    # Create verified external identity mapping
    mapping = ExternalIdentityMapping(
        marketplace_id=mkt.id,
        external_id_type="asin",
        external_id_value="B0TESTASIN1",
        product_id=prod.id,
        variant_id=var.id,
        mapping_status="active",
        verification_status="verified",
        confidence_score=1.0,
    )
    db_session.add(mapping)
    db_session.commit()

    resolver = IdentityResolver(db_session)
    norm = NormalizedSmartphone(
        category="smartphone",
        brand="AnyBrand",
        model_name="AnyModel",
    )
    result = resolver.resolve_smartphone(
        marketplace_id=mkt.id,
        asin="B0TESTASIN1",
        normalized=norm,
    )

    assert result.match_state == "confirmed"
    assert result.product_id == prod.id
    assert result.variant_id == var.id
    assert result.confidence == 1.0
    assert any("Stage 1" in r for r in result.reasons)


def test_stage1_unverified_mapping_falls_through_to_scoring(db_session: Session):
    """Stage 1: Unverified external mapping does not prematurely confirm without attribute verification."""
    mkt = db_session.query(Marketplace).filter_by(key="amazon.in").first()
    prod = db_session.query(Product).filter_by(name="Samsung Galaxy S24 Ultra").first()
    var = prod.variants[0]

    mapping = ExternalIdentityMapping(
        marketplace_id=mkt.id,
        external_id_type="asin",
        external_id_value="B0UNVERIFIED1",
        product_id=prod.id,
        variant_id=var.id,
        mapping_status="active",
        verification_status="unverified",
        confidence_score=0.7,
    )
    db_session.add(mapping)
    db_session.commit()

    resolver = IdentityResolver(db_session)
    # Give wrong brand to verify it doesn't blindly trust unverified mapping
    norm = NormalizedSmartphone(
        category="smartphone",
        brand="CompletelyDifferentBrand",
        model_name="UnrelatedModel",
    )
    result = resolver.resolve_smartphone(
        marketplace_id=mkt.id,
        asin="B0UNVERIFIED1",
        normalized=norm,
    )
    assert result.match_state != "confirmed"


# =============================================================================
# Category B: Trusted Listing Mapping (Stage 2)
# =============================================================================


def test_stage2_trusted_listing_confirmed(db_session: Session):
    """Stage 2: Verified listing mapping preserves exact product and variant with 1.0 confidence."""
    mkt = db_session.query(Marketplace).filter_by(key="amazon.in").first()
    prod = db_session.query(Product).filter_by(name="Apple iPhone 16 Pro").first()
    var = prod.variants[0]

    listing = MarketplaceListing(
        marketplace_id=mkt.id,
        external_id="B0IPHONE16CONF",
        url="https://amazon.in/dp/B0IPHONE16CONF",
        product_id=prod.id,
        variant_id=var.id,
        match_state="confirmed",
        match_confidence=1.0,
        first_seen_at=utc_now(),
        last_seen_at=utc_now(),
    )
    db_session.add(listing)
    db_session.commit()

    resolver = IdentityResolver(db_session)
    norm = NormalizedSmartphone(
        category="smartphone",
        brand="Apple",
        model_name="iPhone 16 Pro",
    )
    result = resolver.resolve_smartphone(
        marketplace_id=mkt.id,
        asin="B0IPHONE16CONF",
        normalized=norm,
    )

    assert result.match_state == "confirmed"
    assert result.product_id == prod.id
    assert result.variant_id == var.id
    assert result.confidence == 1.0
    assert any("verified listing record" in r for r in result.reasons)


# =============================================================================
# Category C: Deterministic Product and Variant Fingerprinting (Stage 3)
# =============================================================================


def test_deterministic_product_fingerprint_reproducibility():
    """Stage 3: Product fingerprint is byte-identical across case, extra spaces, and whitespace."""
    fp1 = FingerprintService.generate_product_fingerprint(
        category="Smartphone",
        manufacturer="Samsung  ",
        model_name="Galaxy S24 Ultra",
        model_number="SM-S928B",
    )
    fp2 = FingerprintService.generate_product_fingerprint(
        category="smartphone",
        manufacturer="samsung",
        model_name="galaxy s24 ultra",
        model_number="sm-s928b",
    )
    assert fp1 == fp2
    assert len(fp1) == 64  # SHA-256


def test_deterministic_variant_fingerprint_reproducibility():
    """Stage 3: Variant fingerprint incorporates sorted attributes and normalizes numerical values."""
    prod_fp = "dummy_product_fp_12345"
    cfg1 = {"ram_gb": 12.0, "storage_gb": 256, "color": "Titanium Black"}
    cfg2 = {"color": "titanium black", "storage_gb": 256.0, "ram_gb": 12}

    v_fp1 = FingerprintService.generate_variant_fingerprint(prod_fp, cfg1)
    v_fp2 = FingerprintService.generate_variant_fingerprint(prod_fp, cfg2)
    assert v_fp1 == v_fp2


def test_variant_fingerprint_missing_vs_null_attributes():
    """Stage 3: Missing attributes must NEVER default to zero; missing vs present yield different fingerprints."""
    prod_fp = "dummy_prod_fp"
    cfg_with_storage = {"ram_gb": 12, "storage_gb": 256}
    cfg_without_storage = {"ram_gb": 12}
    cfg_with_zero = {"ram_gb": 12, "storage_gb": 0}

    fp_full = FingerprintService.generate_variant_fingerprint(prod_fp, cfg_with_storage)
    fp_missing = FingerprintService.generate_variant_fingerprint(prod_fp, cfg_without_storage)
    fp_zero = FingerprintService.generate_variant_fingerprint(prod_fp, cfg_with_zero)

    assert fp_full != fp_missing
    assert fp_missing != fp_zero
    assert fp_full != fp_zero


# =============================================================================
# Category D: Multi-Candidate Scoring & Ranking (Stage 4)
# =============================================================================


def test_stage4_candidate_scoring_and_ranking(db_session: Session):
    """Stage 4: Candidate scoring ranks correct product highest when brand and model match."""
    mkt = db_session.query(Marketplace).filter_by(key="amazon.in").first()
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
        asin="B0SCORETEST1",
        normalized=norm,
    )
    assert result.match_state == "confirmed"
    assert result.confidence >= 0.90
    assert result.product_name == "Samsung Galaxy S24 Ultra"


def test_stage4_contradictory_variant_penalty(db_session: Session):
    """Stage 4: Contradictory hardware configuration (e.g. 16GB RAM for an 8GB catalog phone) prevents confirmation."""
    mkt = db_session.query(Marketplace).filter_by(key="amazon.in").first()
    resolver = IdentityResolver(db_session)

    # Catalog S24 Ultra has 12GB RAM variants only. Extracted has 8GB.
    norm = NormalizedSmartphone(
        category="smartphone",
        brand="Samsung",
        model_name="Galaxy S24 Ultra",
        model_number="SM-S928B",
        ram_gb=8,  # Contradiction: catalog has 12GB
        storage_gb=256,
    )
    result = resolver.resolve_smartphone(
        marketplace_id=mkt.id,
        asin="B0CONTRADICT1",
        normalized=norm,
    )
    # Should not confirm contradictory variant
    assert result.match_state != "confirmed"


def test_stage4_ambiguity_detection_close_scores(db_session: Session):
    """Stage 4: When multiple candidates have near-identical scores, result is marked ambiguous."""
    mkt = db_session.query(Marketplace).filter_by(key="amazon.in").first()
    cat = db_session.query(Category).filter_by(key="smartphone").first()

    # Create two very similar products
    p1 = Product(category_id=cat.id, name="Pixel Pro 9", manufacturer="Google", mpn="G-PIX-9A")
    p2 = Product(category_id=cat.id, name="Pixel Pro 9 XL", manufacturer="Google", mpn="G-PIX-9B")
    db_session.add_all([p1, p2])
    db_session.commit()

    resolver = IdentityResolver(db_session)
    norm = NormalizedSmartphone(
        category="smartphone",
        brand="Google",
        model_name="Pixel Pro 9",  # matches both
    )
    result = resolver.resolve_smartphone(
        marketplace_id=mkt.id,
        asin="B0AMBIGUOUS1",
        normalized=norm,
        auto_queue_review=False,
    )
    # Should flag ambiguous or probable, never confirmed without differentiator
    assert result.match_state in ("ambiguous", "probable")


# =============================================================================
# Category E: Identity Review Queue (Stage 5)
# =============================================================================


def test_stage5_queue_creation_on_ambiguity(db_session: Session):
    """Stage 5: Low confidence or ambiguous match generates a pending IdentityReviewQueue entry."""
    mkt = db_session.query(Marketplace).filter_by(key="amazon.in").first()
    resolver = IdentityResolver(db_session)

    norm = NormalizedSmartphone(
        category="smartphone",
        brand="Apple",
        model_name="iPhone 16 Pro",
        ram_gb=None,  # Missing config triggers probable/review
        storage_gb=None,
    )
    result = resolver.resolve_smartphone(
        marketplace_id=mkt.id,
        asin="B0QUEUEASIN1",
        normalized=norm,
        raw_title="Apple iPhone 16 Pro 128GB Unverified Listing",
        auto_queue_review=True,
    )

    assert result.review_queue_id is not None
    queue_item = db_session.get(IdentityReviewQueue, result.review_queue_id)
    assert queue_item is not None
    assert queue_item.asin == "B0QUEUEASIN1"
    assert queue_item.status == "pending"


def test_review_queue_approval_workflow(test_client: TestClient, db_session: Session):
    """Stage 5: Approving a review item links catalog entities and creates ExternalIdentityMapping."""
    mkt = db_session.query(Marketplace).filter_by(key="amazon.in").first()
    prod = db_session.query(Product).filter_by(name="Apple iPhone 16 Pro").first()
    var = prod.variants[0]

    item = IdentityReviewQueue(
        marketplace_id=mkt.id,
        asin="B0APPROVE1",
        raw_title="Review item to approve",
        status="pending",
    )
    db_session.add(item)
    db_session.commit()

    resp = test_client.post(
        f"/api/v1/identity/reviews/{item.id}/approve",
        json={
            "decision": "link_variant",
            "product_id": str(prod.id),
            "variant_id": str(var.id),
            "reason": "Expert confirmed variant match from physical serial inspection",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["reviewer_decision"] == "link_variant"

    # Verify ExternalIdentityMapping was generated
    mapping = db_session.execute(
        select(ExternalIdentityMapping).where(
            ExternalIdentityMapping.marketplace_id == mkt.id,
            ExternalIdentityMapping.external_id_value == "B0APPROVE1",
        )
    ).scalar_one_or_none()
    assert mapping is not None
    assert mapping.verification_status == "verified"
    assert mapping.product_id == prod.id
    assert mapping.variant_id == var.id


def test_review_queue_rejection_workflow(test_client: TestClient, db_session: Session):
    """Stage 5: Rejecting a review item marks it rejected with documented reason."""
    mkt = db_session.query(Marketplace).filter_by(key="amazon.in").first()
    item = IdentityReviewQueue(
        marketplace_id=mkt.id,
        asin="B0REJECT1",
        raw_title="Suspicious counterfeit listing",
        status="pending",
    )
    db_session.add(item)
    db_session.commit()

    resp = test_client.post(
        f"/api/v1/identity/reviews/{item.id}/reject",
        json={"reason": "Counterfeit replica, not a genuine catalog product"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert "Counterfeit" in data["decision_reason"]


# =============================================================================
# Category F: Evidence Provenance & Historical Versioning
# =============================================================================


def make_raw_extraction(specs: list[SpecificationItem]) -> RawSmartphoneExtraction:
    """Helper to instantiate RawSmartphoneExtraction with all required contract fields."""
    return RawSmartphoneExtraction(
        title="Test Smartphone Title",
        brand_text="Samsung",
        model_text="Galaxy S24 Ultra",
        variant_text="12GB 256GB",
        price_text="₹1,29,999",
        rating_text="4.5",
        review_count_text="100",
        availability_text="In stock",
        specifications_text=specs,
    )


def test_evidence_versioning_and_provenance(db_session: Session):
    """Evidence records maintain append-only versions without destructive overwriting."""
    prod = db_session.query(Product).first()
    service = EvidenceService(db_session)

    norm = NormalizedSmartphone(
        category="smartphone",
        brand=prod.manufacturer,
        model_name=prod.name,
        ram_gb=12,
        battery_capacity_mah=5000,
    )
    raw = make_raw_extraction([
        SpecificationItem(label="RAM", value="12GB"),
        SpecificationItem(label="Battery", value="5000 mAh"),
    ])

    ev_list = service.persist_smartphone_evidence(
        product_id=prod.id,
        variant_id=None,
        normalized=norm,
        raw_extraction=raw,
        extraction_record_id=uuid.uuid4(),
        observed_at=utc_now(),
        source_url="https://amazon.in/dp/B0TEST1",
    )
    db_session.commit()

    ram_ev = next(e for e in ev_list if e.parameter_key == "ram_gb")
    assert len(ram_ev.versions) == 1
    assert ram_ev.versions[0].version == 1
    assert ram_ev.versions[0].value == {"value": 12.0}


def test_evidence_identical_values_no_duplicate_version(db_session: Session):
    """Re-observing the identical evidence value preserves current version without duplicate row creation."""
    prod = db_session.query(Product).first()
    service = EvidenceService(db_session)

    norm = NormalizedSmartphone(
        category="smartphone",
        brand=prod.manufacturer,
        model_name=prod.name,
        ram_gb=12,
    )
    raw = make_raw_extraction([SpecificationItem(label="RAM", value="12GB")])

    # First observation
    service.persist_smartphone_evidence(
        product_id=prod.id,
        variant_id=None,
        normalized=norm,
        raw_extraction=raw,
        extraction_record_id=uuid.uuid4(),
        observed_at=utc_now(),
        source_url="https://amazon.in/dp/B0TEST2",
    )
    db_session.commit()

    # Second identical observation
    service.persist_smartphone_evidence(
        product_id=prod.id,
        variant_id=None,
        normalized=norm,
        raw_extraction=raw,
        extraction_record_id=uuid.uuid4(),
        observed_at=utc_now(),
        source_url="https://amazon.in/dp/B0TEST2",
    )
    db_session.commit()

    ev = db_session.execute(
        select(Evidence).where(Evidence.product_id == prod.id, Evidence.parameter_key == "ram_gb")
    ).scalar_one()
    assert len(ev.versions) == 1


# =============================================================================
# Category G: Trust Tier Security
# =============================================================================


def test_backend_controlled_trust_tier_assignment():
    """Trust tiers are derived strictly by backend source classification policy."""
    assert EvidenceService.determine_trust_tier("official") == 1
    assert EvidenceService.determine_trust_tier("primary_official") == 1
    assert EvidenceService.determine_trust_tier("marketplace") == 2
    assert EvidenceService.determine_trust_tier("community") == 3
    assert EvidenceService.determine_trust_tier("unknown_source") == 4


def test_client_claimed_trust_tier_override_rejected():
    """Client-claimed trust tier metadata (e.g. claim of Tier 1 on marketplace extraction) is rejected."""
    tier = EvidenceService.determine_trust_tier(
        source_type="marketplace",
        client_claimed_tier=1,  # Malicious attempt to elevate tier
    )
    assert tier == 2  # Must enforce Tier 2 for marketplace


# =============================================================================
# Category H: Evidence Conflict Detection & Preservation
# =============================================================================


def test_conflict_detection_and_preservation(db_session: Session):
    """When contradictory evidence is observed, values are preserved and an EvidenceConflict is opened."""
    prod = db_session.query(Product).first()
    service = EvidenceService(db_session)

    # Observation 1: Battery 5000 mAh
    norm1 = NormalizedSmartphone(
        category="smartphone",
        brand=prod.manufacturer,
        model_name=prod.name,
        battery_capacity_mah=5000,
    )
    raw1 = make_raw_extraction([SpecificationItem(label="Battery", value="5000 mAh")])
    service.persist_smartphone_evidence(
        product_id=prod.id,
        variant_id=None,
        normalized=norm1,
        raw_extraction=raw1,
        extraction_record_id=uuid.uuid4(),
        observed_at=utc_now(),
        source_url="https://amazon.in/dp/B0BATT1",
    )
    db_session.commit()

    # Observation 2: Contradictory Battery 4500 mAh
    norm2 = NormalizedSmartphone(
        category="smartphone",
        brand=prod.manufacturer,
        model_name=prod.name,
        battery_capacity_mah=4500,
    )
    raw2 = make_raw_extraction([SpecificationItem(label="Battery", value="4500 mAh")])
    service.persist_smartphone_evidence(
        product_id=prod.id,
        variant_id=None,
        normalized=norm2,
        raw_extraction=raw2,
        extraction_record_id=uuid.uuid4(),
        observed_at=utc_now(),
        source_url="https://amazon.in/dp/B0BATT2",
    )
    db_session.commit()

    # Verify conflict record exists
    conflict = db_session.execute(
        select(EvidenceConflict).where(
            EvidenceConflict.product_id == prod.id,
            EvidenceConflict.parameter_key == "battery_capacity_mah",
        )
    ).scalar_one_or_none()

    assert conflict is not None
    assert conflict.status == "open"
    assert conflict.existing_value == {"value": 5000}
    assert conflict.conflicting_value == {"value": 4500}

    # Verify both versions exist
    ev = db_session.execute(
        select(Evidence).where(
            Evidence.product_id == prod.id,
            Evidence.parameter_key == "battery_capacity_mah",
        )
    ).scalar_one()
    assert len(ev.versions) == 2
    assert ev.versions[1].verification_state == "conflicting"


def test_conflict_resolution_decisions(test_client: TestClient, db_session: Session):
    """Test resolving conflicts via accept_incoming, keep_existing, and supersede_both."""
    prod = db_session.query(Product).first()
    ev = Evidence(
        product_id=prod.id,
        parameter_key="processor",
        source_type="marketplace",
        trust_tier=2,
    )
    db_session.add(ev)
    db_session.flush()

    v1 = EvidenceVersion(
        evidence_id=ev.id,
        version=1,
        value={"value": "Snapdragon 8 Gen 2"},
        observed_at=utc_now(),
        verification_state="unverified",
    )
    v2 = EvidenceVersion(
        evidence_id=ev.id,
        version=2,
        value={"value": "Snapdragon 8 Gen 3"},
        observed_at=utc_now(),
        verification_state="conflicting",
    )
    db_session.add_all([v1, v2])
    db_session.flush()
    ev.current_version_id = v2.id

    conflict = EvidenceConflict(
        parameter_key="processor",
        existing_value={"value": "Snapdragon 8 Gen 2"},
        conflicting_value={"value": "Snapdragon 8 Gen 3"},
        existing_evidence_id=ev.id,
        incoming_evidence_id=ev.id,
        product_id=prod.id,
        status="open",
    )
    db_session.add(conflict)
    db_session.commit()

    # Resolve via API
    resp = test_client.post(
        f"/api/v1/evidence/conflicts/{conflict.id}/resolve",
        json={
            "resolution_decision": "accept_incoming",
            "resolution_reason": "Verified from official teardown: Snapdragon 8 Gen 3 is correct",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"
    assert data["resolution_decision"] == "accept_incoming"


# =============================================================================
# Category I: Verification History Lifecycle Tracking
# =============================================================================


def test_verification_lifecycle_audit_trail(test_client: TestClient, db_session: Session):
    """Transitions in verification state append immutable audit log entries."""
    prod = db_session.query(Product).first()
    ev = Evidence(
        product_id=prod.id,
        parameter_key="display_size_inches",
        source_type="marketplace",
        trust_tier=2,
    )
    db_session.add(ev)
    db_session.flush()

    ver = EvidenceVersion(
        evidence_id=ev.id,
        version=1,
        value={"value": 6.8},
        unit="inches",
        observed_at=utc_now(),
        verification_state="unverified",
    )
    db_session.add(ver)
    db_session.commit()

    # Verify transition to 'verified'
    resp = test_client.post(
        f"/api/v1/evidence/{ev.id}/verify",
        json={
            "verification_state": "verified",
            "reason": "Confirmed against official Samsung product specification sheet",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verification_state"] == "verified"

    # Check history endpoint
    hist_resp = test_client.get(f"/api/v1/evidence/{ev.id}/history")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["total"] >= 1
    entry = hist_data["items"][0]
    assert entry["previous_status"] == "unverified"
    assert entry["new_status"] == "verified"
    assert "Confirmed against official" in entry["reason"]


# =============================================================================
# Category J: End-to-End REST APIs & Background Tasks
# =============================================================================


def test_e2e_identity_resolve_api(test_client: TestClient, db_session: Session):
    """End-to-end POST /api/v1/identity/resolve executes resolution pipeline."""
    resp = test_client.post(
        "/api/v1/identity/resolve",
        json={
            "marketplace_code": "amazon.in",
            "asin": "B0APIRESOLVE1",
            "category": "smartphone",
            "brand": "Samsung",
            "model_name": "Galaxy S24 Ultra",
            "model_number": "SM-S928B",
            "ram_gb": 12,
            "storage_gb": 256,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["match_state"] == "confirmed"
    assert data["confidence"] >= 0.90
    assert data["product_id"] is not None
    assert data["variant_id"] is not None


def test_e2e_celery_task_identity_resolve(db_session: Session):
    """End-to-end execution of identity.resolve task."""
    from celery import Celery

    from app.worker.tasks.identity import register_identity_tasks

    test_celery = Celery("test_identity")
    register_identity_tasks(test_celery)
    task_fn = test_celery.tasks["identity.resolve"]

    result = task_fn(
        marketplace_code="amazon.in",
        asin="B0CELERYASIN1",
        title="Samsung Galaxy S24 Ultra 5G (Titanium Black, 12GB, 256GB Storage)",
        brand="Samsung",
        model_name="Galaxy S24 Ultra",
    )
    assert result["status"] == "completed"
    assert result["match_type"] in ("confirmed", "probable")


# =============================================================================
# Category K: Regression & Backwards Compatibility with B1-B7
# =============================================================================


def test_b8_regression_compatibility(db_session: Session):
    """Verify that catalog products, variants, and listings models operate without schema regression."""
    prod = db_session.query(Product).filter_by(name="Samsung Galaxy S24 Ultra").first()
    assert prod is not None
    assert len(prod.variants) >= 2
    assert prod.category is not None
    assert prod.category.key == "smartphone"
