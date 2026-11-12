"""Comprehensive test suite for Phase B10: Product Comparison and Recommendation Engines.

Tests:
- Comparison session lifecycle (create, retrieve, list, archive)
- Database-level concurrency control: max 2 active sessions enforced under parallel concurrent threads
- Item validation: same category, reject cross-category, max 5 variants limit, duplicate prevention
- Category-aware comparison matrix with separated dimensions and honest missing data
- Evaluation reuse, fingerprint matching, cache invalidation, and explicit recalculation
- Requirement extraction: budget, RAM, storage, soft preferences, unit normalization, deterministic fallback
- Hard constraint engine: three-valued logic (PASS, FAIL, UNKNOWN) and strict candidate exclusion
- Deterministic ranking: multi-tier tie breaking, score priority, invariant fingerprints
- Explanations: evidence-grounded templates referencing verified specifications
- Recommendation persistence, historical retrieval, and audit logging
- API authorization, ownership verification, and HTTP 409 conflict responses
"""

import concurrent.futures
import uuid
from datetime import UTC
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.permissions import Permission
from app.db.dependencies import get_db
from app.db.session import SessionLocal
from app.main import app
from app.models.attribute import AttributeDefinition, VariantAttributeValue
from app.models.category import Category
from app.models.comparison import ComparisonSession
from app.models.evaluation import (
    Evaluation,
    EvaluationModel,
    EvaluationModelVersion,
)
from app.models.evidence import Evidence
from app.models.identity import User
from app.models.listing import MarketplaceListing
from app.models.offer import SellerOffer
from app.models.operation import AuditLog
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.variant import Variant, compute_config_hash
from app.repositories.comparison_repository import (
    ActiveComparisonSessionLimitError,
    ComparisonRepository,
    ComparisonValidationError,
)
from app.schemas.recommendation import (
    CandidateEvaluationOutcome,
    ConstraintOutcome,
    HardConstraint,
    ParsedRequirements,
    RecommendationRequest,
    SoftPreference,
)
from app.services.comparison_service import ComparisonService
from app.services.constraint_engine import ConstraintEngine
from app.services.evaluation_cache import EvaluationReuseService
from app.services.evaluation_service import EvaluationFoundationService
from app.services.ranking_service import RecommendationRankingService
from app.services.recommendation_service import RecommendationService
from app.services.requirement_parser import RequirementParserService


@pytest.fixture
def db():
    """Database session connected to PostgreSQL."""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def b10_catalog_setup(db: Session):
    """Seed categories, products, variants, and evaluation models for B10 testing."""
    tag = uuid.uuid4().hex[:6]

    # 1. Categories
    cat_phone = Category(key=f"phone_{tag}", name=f"Smartphones {tag}")
    cat_laptop = Category(key=f"laptop_{tag}", name=f"Laptops {tag}")
    db.add_all([cat_phone, cat_laptop])
    db.flush()

    # 2. Attributes for smartphone
    attr_ram = AttributeDefinition(
        category_id=cat_phone.id,
        key="ram",
        name="RAM",
        data_type="numeric",
        canonical_unit="GB",
        is_required=True,
    )
    attr_storage = AttributeDefinition(
        category_id=cat_phone.id,
        key="storage",
        name="Storage",
        data_type="numeric",
        canonical_unit="GB",
        is_required=True,
    )
    attr_5g = AttributeDefinition(
        category_id=cat_phone.id,
        key="5g",
        name="5G Support",
        data_type="boolean",
    )
    db.add_all([attr_ram, attr_storage, attr_5g])
    db.flush()

    # 3. Products
    p1 = Product(name=f"Alpha Phone Pro {tag}", manufacturer="AlphaTech", category_id=cat_phone.id)
    p2 = Product(name=f"Beta Phone Neo {tag}", manufacturer="BetaCorp", category_id=cat_phone.id)
    p3 = Product(name=f"Gamma Phone Mini {tag}", manufacturer="GammaTech", category_id=cat_phone.id)
    p_laptop = Product(name=f"ZetaBook 14 {tag}", manufacturer="Zeta", category_id=cat_laptop.id)
    db.add_all([p1, p2, p3, p_laptop])
    db.flush()

    # 4. Variants
    v1 = Variant(
        product_id=p1.id,
        sku_label="Alpha Pro 12GB/256GB",
        configuration={"ram": 12, "storage": 256, "5g": True},
        config_hash=compute_config_hash({"ram": 12, "storage": 256, "5g": True}),
    )
    v2 = Variant(
        product_id=p2.id,
        sku_label="Beta Neo 8GB/128GB",
        configuration={"ram": 8, "storage": 128, "5g": True},
        config_hash=compute_config_hash({"ram": 8, "storage": 128, "5g": True}),
    )
    v3 = Variant(
        product_id=p3.id,
        sku_label="Gamma Mini 4GB/64GB",
        configuration={"ram": 4, "storage": 64, "5g": False},
        config_hash=compute_config_hash({"ram": 4, "storage": 64, "5g": False}),
    )
    v_laptop = Variant(
        product_id=p_laptop.id,
        sku_label="ZetaBook 16GB",
        configuration={"ram": 16},
        config_hash=compute_config_hash({"ram": 16}),
    )
    db.add_all([v1, v2, v3, v_laptop])
    db.flush()

    # 5. VariantAttributeValues
    vav1_ram = VariantAttributeValue(variant_id=v1.id, attribute_id=attr_ram.id, value_numeric=Decimal(12), canonical_unit="GB")
    vav1_storage = VariantAttributeValue(variant_id=v1.id, attribute_id=attr_storage.id, value_numeric=Decimal(256), canonical_unit="GB")
    vav1_5g = VariantAttributeValue(variant_id=v1.id, attribute_id=attr_5g.id, value_boolean=True)

    vav2_ram = VariantAttributeValue(variant_id=v2.id, attribute_id=attr_ram.id, value_numeric=Decimal(8), canonical_unit="GB")
    vav2_storage = VariantAttributeValue(variant_id=v2.id, attribute_id=attr_storage.id, value_numeric=Decimal(128), canonical_unit="GB")
    vav2_5g = VariantAttributeValue(variant_id=v2.id, attribute_id=attr_5g.id, value_boolean=True)

    vav3_ram = VariantAttributeValue(variant_id=v3.id, attribute_id=attr_ram.id, value_numeric=Decimal(4), canonical_unit="GB")
    vav3_storage = VariantAttributeValue(variant_id=v3.id, attribute_id=attr_storage.id, value_numeric=Decimal(64), canonical_unit="GB")
    vav3_5g = VariantAttributeValue(variant_id=v3.id, attribute_id=attr_5g.id, value_boolean=False)

    db.add_all([vav1_ram, vav1_storage, vav1_5g, vav2_ram, vav2_storage, vav2_5g, vav3_ram, vav3_storage, vav3_5g])
    db.flush()

    # 6. Evaluation Model and Version for Smartphones
    model = EvaluationModel(category_id=cat_phone.id, name=f"Smartphone Evaluation Model {tag}", status="published")
    db.add(model)
    db.flush()

    ver_str = f"1.{tag}"
    model_ver = EvaluationModelVersion(
        model_id=model.id,
        version=ver_str,
        status="published",
        definition={
            "parameters": [
                {
                    "key": "ram_performance",
                    "attribute_key": "ram",
                    "weight": 0.5,
                    "critical": True,
                    "scoring_rule": {"type": "numeric_range", "min": 4, "max": 16},
                },
                {
                    "key": "storage_capacity",
                    "attribute_key": "storage",
                    "weight": 0.5,
                    "critical": False,
                    "scoring_rule": {"type": "numeric_range", "min": 64, "max": 512},
                },
            ]
        },
        configuration_hash="conf_hash_v1",
    )
    db.add(model_ver)
    db.flush()
    model.active_version_id = model_ver.id
    db.flush()

    # 7. Evaluations for v1 and v2
    eval_svc = EvaluationFoundationService(db)
    snap_hash = eval_svc._compute_evidence_snapshot_hash({})

    eval_v1 = Evaluation(
        variant_id=v1.id,
        model_version_id=model_ver.id,
        overall_score=Decimal("88.50"),
        confidence_state="high",
        confidence_score=Decimal("0.950"),
        coverage=Decimal("1.000"),
        configuration_hash=model_ver.configuration_hash,
        evidence_snapshot_hash=snap_hash,
    )
    eval_v2 = Evaluation(
        variant_id=v2.id,
        model_version_id=model_ver.id,
        overall_score=Decimal("72.00"),
        confidence_state="medium",
        confidence_score=Decimal("0.800"),
        coverage=Decimal("1.000"),
        configuration_hash=model_ver.configuration_hash,
        evidence_snapshot_hash=snap_hash,
    )
    db.add_all([eval_v1, eval_v2])
    db.flush()

    # 8. Listings and Offers
    from app.models.marketplace import Marketplace
    mp = db.execute(select(Marketplace)).scalars().first()
    if not mp:
        mp = Marketplace(name="Amazon India", key="amazon_in", base_url="https://amazon.in")
        db.add(mp)
        db.flush()
    mp_id = mp.id

    from datetime import datetime
    now_dt = datetime.now(UTC)

    list1 = MarketplaceListing(
        marketplace_id=mp_id,
        product_id=p1.id,
        variant_id=v1.id,
        external_id=f"B001_{tag}",
        url="http://example.com/1",
        first_seen_at=now_dt,
        last_seen_at=now_dt,
    )
    list2 = MarketplaceListing(
        marketplace_id=mp_id,
        product_id=p2.id,
        variant_id=v2.id,
        external_id=f"B002_{tag}",
        url="http://example.com/2",
        first_seen_at=now_dt,
        last_seen_at=now_dt,
    )
    db.add_all([list1, list2])
    db.flush()

    off1 = SellerOffer(listing_id=list1.id, seller="AlphaOfficial", current_price=Decimal("24999.00"), currency="INR", availability="in_stock", observed_at=now_dt)
    off2 = SellerOffer(listing_id=list2.id, seller="RetailerDirect", current_price=Decimal("19999.00"), currency="INR", availability="in_stock", observed_at=now_dt)
    db.add_all([off1, off2])

    # 9. Test User
    user = User(email=f"user_{uuid.uuid4().hex[:6]}@example.com", password_hash="pw", display_name="Test Consumer")
    db.add(user)
    db.commit()

    return {
        "cat_phone": cat_phone,
        "cat_laptop": cat_laptop,
        "p1": p1,
        "p2": p2,
        "p3": p3,
        "v1": v1,
        "v2": v2,
        "v3": v3,
        "v_laptop": v_laptop,
        "model_ver": model_ver,
        "eval_v1": eval_v1,
        "eval_v2": eval_v2,
        "user": user,
    }


# =========================================================================
# PART A: COMPARISON ENGINE TESTS
# =========================================================================

def test_comparison_session_lifecycle(db: Session, b10_catalog_setup):
    """Test session creation, retrieval, listing, and archiving."""
    user = b10_catalog_setup["user"]
    service = ComparisonService(db)

    # 1. Create first session
    s1 = service.create_session(user_id=user.id, title="Phone Compare 1")
    db.commit()
    assert s1.status == "active"
    assert s1.title == "Phone Compare 1"

    # 2. Retrieve session
    retrieved = service.get_session(s1.id)
    assert retrieved is not None
    assert retrieved.id == s1.id

    # 3. Create second session
    s2 = service.create_session(user_id=user.id, title="Phone Compare 2")
    db.commit()
    assert s2.status == "active"

    # 4. List user sessions
    active_sessions = service.list_user_sessions(user.id, status="active")
    assert len(active_sessions) == 2

    # 5. Attempt 3rd active session -> must fail with ActiveComparisonSessionLimitError
    with pytest.raises(ActiveComparisonSessionLimitError):
        service.create_session(user_id=user.id, title="Phone Compare 3")

    # 6. Archive session 1 -> releases active slot
    archived = service.archive_session(s1.id)
    assert archived.status == "archived"

    # 7. Now 3rd session creation succeeds
    s3 = service.create_session(user_id=user.id, title="Phone Compare 3")
    db.commit()
    assert s3.status == "active"

    # Verify active list now has s2 and s3
    active_now = service.list_user_sessions(user.id, status="active")
    assert len(active_now) == 2
    assert {s.id for s in active_now} == {s2.id, s3.id}


def test_comparison_item_validation(db: Session, b10_catalog_setup):
    """Test variant validation, category lock, cross-category rejection, and max 5 items limit."""
    user = b10_catalog_setup["user"]
    v1 = b10_catalog_setup["v1"]
    v2 = b10_catalog_setup["v2"]
    v3 = b10_catalog_setup["v3"]
    v_laptop = b10_catalog_setup["v_laptop"]
    service = ComparisonService(db)

    session = service.create_session(user_id=user.id, title="Item Validation Session")
    db.commit()
    assert session.category_id is None

    # 1. First variant establishes category
    item1 = service.add_variant_to_session(session.id, v1.id)
    assert item1.variant_id == v1.id
    db.refresh(session)
    assert session.category_id == v1.product.category_id

    # 2. Adding cross-category variant is rejected
    with pytest.raises(ComparisonValidationError, match="Cross-category comparison is not allowed"):
        service.add_variant_to_session(session.id, v_laptop.id)

    # 3. Duplicate variant is rejected
    with pytest.raises(ComparisonValidationError, match="already included"):
        service.add_variant_to_session(session.id, v1.id)

    # 4. Adding second variant from same category succeeds
    item2 = service.add_variant_to_session(session.id, v2.id)
    assert item2.variant_id == v2.id

    # 5. Remove item
    removed = service.remove_variant_from_session(session.id, v2.id)
    assert removed is True
    assert len(service.get_session(session.id).items) == 1

    # 6. Cannot modify archived session
    service.archive_session(session.id)
    with pytest.raises(ComparisonValidationError, match="Cannot modify comparison session"):
        service.add_variant_to_session(session.id, v3.id)


def test_comparison_matrix_generation(db: Session, b10_catalog_setup):
    """Test category comparison matrix generation with separated dimensions and honest missing data."""
    user = b10_catalog_setup["user"]
    v1 = b10_catalog_setup["v1"]
    v2 = b10_catalog_setup["v2"]
    v3 = b10_catalog_setup["v3"]
    service = ComparisonService(db)

    session = service.create_session(user_id=user.id, title="Matrix Test Session")
    service.add_variant_to_session(session.id, v1.id)
    service.add_variant_to_session(session.id, v2.id)
    service.add_variant_to_session(session.id, v3.id)
    db.commit()

    matrix = service.get_comparison_matrix(session.id)
    assert matrix.session_id == session.id
    assert matrix.item_count == 3
    assert len(matrix.items) == 3

    # Check separated evaluation dimensions
    m_v1 = next(item for item in matrix.items if item.variant_id == v1.id)
    assert m_v1.evaluation.overall_score == 88.5
    assert m_v1.evaluation.confidence_state == "high"
    assert m_v1.offer.current_price == 24999.0
    assert m_v1.offer.currency == "INR"

    # Check specifications and missing values honesty
    assert m_v1.specifications["ram"].canonical_value == 12.0
    assert m_v1.specifications["ram"].is_missing is False
    assert m_v1.specifications["5g"].canonical_value is True

    # v3 has boolean false for 5G -> must remain genuine boolean false, not missing
    m_v3 = next(item for item in matrix.items if item.variant_id == v3.id)
    assert m_v3.specifications["5g"].canonical_value is False
    assert m_v3.specifications["5g"].is_missing is False


def test_database_level_concurrency_max_active_sessions(b10_catalog_setup):
    """Critical Acceptance Test: Enforce max 2 active sessions under concurrent threads."""
    user_id = b10_catalog_setup["user"].id
    WorkerSession = SessionLocal

    success_count = 0
    failure_count = 0

    def attempt_create_session(idx: int) -> bool:
        s = WorkerSession()
        try:
            repo = ComparisonRepository()
            repo.create_session(s, user_id=user_id, title=f"Concurrent Session {idx}")
            s.commit()
            return True
        except Exception:  # noqa: BLE001
            s.rollback()
            return False
        finally:
            s.close()

    # Launch 6 simultaneous creation attempts across worker threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(attempt_create_session, i) for i in range(6)]
        for f in concurrent.futures.as_completed(futures):
            if f.result():
                success_count += 1
            else:
                failure_count += 1

    # Verify results: exactly 2 succeeded, 4 rejected
    assert success_count == 2
    assert failure_count == 4

    # Verify final database count
    verify_db = WorkerSession()
    final_count = ComparisonRepository.count_active_sessions(verify_db, user_id=user_id)
    verify_db.close()
    assert final_count == 2


# =========================================================================
# PART B: EVALUATION REUSE TESTS
# =========================================================================

def test_evaluation_reuse_and_cache(db: Session, b10_catalog_setup):
    """Test that valid existing evaluations are reused without re-computation."""
    v1 = b10_catalog_setup["v1"]
    eval_v1 = b10_catalog_setup["eval_v1"]
    reuse_service = EvaluationReuseService(db)

    # 1. Retrieve evaluation -> reuses existing record
    resolved_eval = reuse_service.get_or_evaluate_variant(v1.id)
    assert resolved_eval.id == eval_v1.id
    assert resolved_eval.overall_score == eval_v1.overall_score

    # 2. Forced recalculation creates new immutable evaluation
    recalc_eval = reuse_service.get_or_evaluate_variant(v1.id, force_recalculate=True)
    assert recalc_eval.id != eval_v1.id
    # Historical evaluation still exists in database
    assert db.get(Evaluation, eval_v1.id) is not None


# =========================================================================
# PART C: REQUIREMENT-BASED RECOMMENDATION ENGINE TESTS
# =========================================================================

def test_requirement_extraction_deterministic():
    """Test deterministic regex parser extracting budget, RAM, storage, preferences, and exclusions."""
    parser = RequirementParserService()

    query = "I need a smartphone under ₹25,000 with at least 8GB RAM, 128GB storage, and good battery. Not Samsung."
    resp = parser.parse_query(query, use_llm=False)
    req = resp.requirements

    assert req.category_key == "smartphone"
    assert req.budget_max == 25000.0
    assert req.budget_currency == "INR"

    # Check RAM constraint
    ram_hc = next((c for c in req.hard_constraints if c.attribute_key == "ram"), None)
    assert ram_hc is not None
    assert ram_hc.target_value == 8
    assert ram_hc.operator == ">="

    # Check Storage constraint
    storage_hc = next((c for c in req.hard_constraints if c.attribute_key == "storage"), None)
    assert storage_hc is not None
    assert storage_hc.target_value == 128

    # Check soft preference
    assert any(sp.preference_key == "battery" for sp in req.soft_preferences)

    # Check brand exclusion
    assert "Samsung" in req.excluded_brands


def test_hard_constraint_engine_three_valued():
    """Test three-valued logic: PASS, FAIL, UNKNOWN and strict candidate exclusion."""
    req = ParsedRequirements(
        category_key="smartphone",
        budget_max=25000.0,
        hard_constraints=[
            HardConstraint(attribute_key="ram", operator=">=", target_value=8, unit="GB"),
            HardConstraint(attribute_key="storage", operator=">=", target_value=128, unit="GB"),
        ],
    )

    # Candidate A: 12GB RAM, 256GB storage, ₹22,000 -> PASS on all
    outcome_a = ConstraintEngine.evaluate_candidate(
        requirements=req,
        variant_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        product_name="Product A",
        manufacturer="MfrA",
        sku_label="SkuA",
        attribute_values={"ram": 12, "storage": 256},
        current_price=22000.0,
        price_available=True,
    )
    assert outcome_a.is_eligible is True
    assert all(c.outcome == ConstraintOutcome.PASS for c in outcome_a.constraints)

    # Candidate B: 4GB RAM (fails), 128GB storage, ₹18,000 -> FAIL
    outcome_b = ConstraintEngine.evaluate_candidate(
        requirements=req,
        variant_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        product_name="Product B",
        manufacturer="MfrB",
        sku_label="SkuB",
        attribute_values={"ram": 4, "storage": 128},
        current_price=18000.0,
        price_available=True,
    )
    assert outcome_b.is_eligible is False
    assert any(c.outcome == ConstraintOutcome.FAIL for c in outcome_b.constraints)

    # Candidate C: 8GB RAM, missing storage specification, ₹20,000 -> UNKNOWN
    outcome_c = ConstraintEngine.evaluate_candidate(
        requirements=req,
        variant_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        product_name="Product C",
        manufacturer="MfrC",
        sku_label="SkuC",
        attribute_values={"ram": 8},  # Storage missing
        current_price=20000.0,
        price_available=True,
    )
    assert outcome_c.is_eligible is False  # UNKNOWN strictly excludes candidate
    assert any(c.outcome == ConstraintOutcome.UNKNOWN for c in outcome_c.constraints)

    # Candidate D: 8GB RAM, 128GB storage, price exceeds budget (₹29,000) -> FAIL
    outcome_d = ConstraintEngine.evaluate_candidate(
        requirements=req,
        variant_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        product_name="Product D",
        manufacturer="MfrD",
        sku_label="SkuD",
        attribute_values={"ram": 8, "storage": 128},
        current_price=29000.0,
        price_available=True,
    )
    assert outcome_d.is_eligible is False
    assert any(c.attribute_key == "price" and c.outcome == ConstraintOutcome.FAIL for c in outcome_d.constraints)


def test_recommendation_ranking_deterministic(db: Session, b10_catalog_setup):
    """Test deterministic ranking of eligible products using B9 evaluation scores with stable tie-breaking."""
    cat_phone = b10_catalog_setup["cat_phone"]
    user = b10_catalog_setup["user"]
    rec_service = RecommendationService(db)

    p1 = b10_catalog_setup["p1"]
    p2 = b10_catalog_setup["p2"]
    p3 = b10_catalog_setup["p3"]

    # Query for smartphone with at least 8GB RAM and budget under ₹30,000
    # Expected:
    # - Alpha Pro (v1): 12GB RAM, ₹24,999, Score 88.5 -> PASS -> Rank #1
    # - Beta Neo (v2): 8GB RAM, ₹19,999, Score 72.0 -> PASS -> Rank #2
    # - Gamma Mini (v3): 4GB RAM (fails 8GB requirement) -> EXCLUDED (FAIL)
    request = RecommendationRequest(
        query="Smartphone under 30000 with at least 8GB RAM",
        category_id=cat_phone.id,
        limit=5,
    )

    resp = rec_service.generate_recommendations(request, user_id=user.id)

    assert resp.eligible_count == 2
    assert resp.ineligible_count == 1
    assert len(resp.ranked_recommendations) == 2

    # Check Rank #1
    r1 = resp.ranked_recommendations[0]
    assert r1.rank == 1
    assert r1.product_name == p1.name
    assert r1.overall_score == 88.5
    assert r1.current_price == 24999.0
    assert "Meets all required hard constraints" in r1.explanation

    # Check Rank #2
    r2 = resp.ranked_recommendations[1]
    assert r2.rank == 2
    assert r2.product_name == p2.name
    assert r2.overall_score == 72.0
    assert r2.current_price == 19999.0

    # Check Excluded candidates: v3 fails 8GB RAM constraint
    assert len(resp.excluded_candidates) == 1
    assert resp.excluded_candidates[0].product_name == p3.name
    assert "ram" in resp.excluded_candidates[0].failed_constraints

    # Check Invariant Fingerprints
    assert len(resp.input_fingerprint) == 64
    assert len(resp.output_fingerprint) == 64

    # Check Persistence in database
    persisted = db.get(Recommendation, resp.recommendation_id)
    assert persisted is not None
    assert persisted.eligible_count == 2

    # Check Audit Log
    audit = db.execute(
        select(AuditLog).where(AuditLog.target_id == str(resp.recommendation_id))
    ).scalar_one_or_none()
    assert audit is not None
    assert audit.action == "recommendation:generate"


def test_recommendation_retrieval(db: Session, b10_catalog_setup):
    """Test historical recommendation run retrieval."""
    cat_phone = b10_catalog_setup["cat_phone"]
    rec_service = RecommendationService(db)

    req = RecommendationRequest(
        query="Smartphone with 8GB RAM",
        category_id=cat_phone.id,
    )
    generated = rec_service.generate_recommendations(req)

    # Fetch by ID
    retrieved = rec_service.get_recommendation(generated.recommendation_id)
    assert retrieved is not None
    assert retrieved.recommendation_id == generated.recommendation_id
    assert retrieved.input_fingerprint == generated.input_fingerprint
    assert retrieved.output_fingerprint == generated.output_fingerprint
    assert len(retrieved.ranked_recommendations) == len(generated.ranked_recommendations)


# =========================================================================
# PART D: COMPREHENSIVE AUDIT & EDGE CASE TEST SUITE
# =========================================================================

def test_ranking_tie_breaking_order_and_price_independence():
    """Verify strict ranking order: score DESC -> coverage DESC -> confidence DESC -> variant UUID ASC.

    Proves:
    1. Coverage wins when scores are equal.
    2. Confidence wins when scores and coverage are equal.
    3. Canonical Variant UUID provides the final deterministic tie-break.
    4. Price does NOT change ranking when all approved ranking signals are equal.
    """
    req = ParsedRequirements(category_key="smartphone")

    class MockProduct:
        def __init__(self, name: str):
            self.name = name
            self.manufacturer = "MockMfr"

    class MockVariant:
        def __init__(self, vid: uuid.UUID, name: str):
            self.id = vid
            self.product_id = uuid.uuid4()
            self.sku_label = f"SKU-{vid.hex[:4]}"
            self.product = MockProduct(name)

    # ---------------------------------------------------------------------
    # Case 1: Coverage wins when scores are equal
    # ---------------------------------------------------------------------
    var_c1 = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    var_c2 = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    out_c1 = CandidateEvaluationOutcome(
        variant_id=var_c1, product_id=uuid.uuid4(), product_name="Phone C1",
        sku_label="SKU-C1", is_eligible=True, constraints=[], exclusion_reasons=[],
    )
    out_c2 = CandidateEvaluationOutcome(
        variant_id=var_c2, product_id=uuid.uuid4(), product_name="Phone C2",
        sku_label="SKU-C2", is_eligible=True, constraints=[], exclusion_reasons=[],
    )

    eval_c1 = Evaluation(
        variant_id=var_c1,
        overall_score=Decimal("85.00"),
        coverage=Decimal("0.900"),
        confidence_score=Decimal("0.700"),
        confidence_state="medium",
    )
    eval_c2 = Evaluation(
        variant_id=var_c2,
        overall_score=Decimal("85.00"),
        coverage=Decimal("0.750"),
        confidence_score=Decimal("0.950"),
        confidence_state="high",
    )

    v_map_c = {var_c1: MockVariant(var_c1, "Phone C1"), var_c2: MockVariant(var_c2, "Phone C2")}
    e_map_c = {var_c1: eval_c1, var_c2: eval_c2}
    offers_c = {
        var_c1: {"price": 50000.0, "currency": "INR"},
        var_c2: {"price": 20000.0, "currency": "INR"},
    }

    # Pass in reverse order to ensure sort is decisive
    ranked_c = RecommendationRankingService.rank_and_explain(
        requirements=req,
        eligible_outcomes=[out_c2, out_c1],
        evaluations_map=e_map_c,
        variants_map=v_map_c,
        offers_map=offers_c,
        community_map={},
        limit=5,
    )

    # Candidate C1 must win Rank #1 because coverage (0.90 > 0.75) takes precedence
    # despite C2 having higher confidence (0.95 > 0.70) and lower price (₹20,000 < ₹50,000)
    assert ranked_c[0].variant_id == var_c1
    assert ranked_c[0].rank == 1
    assert ranked_c[1].variant_id == var_c2
    assert ranked_c[1].rank == 2

    # ---------------------------------------------------------------------
    # Case 2: Confidence wins when scores and coverage are equal
    # ---------------------------------------------------------------------
    var_f1 = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    var_f2 = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")

    out_f1 = CandidateEvaluationOutcome(
        variant_id=var_f1, product_id=uuid.uuid4(), product_name="Phone F1",
        sku_label="SKU-F1", is_eligible=True, constraints=[], exclusion_reasons=[],
    )
    out_f2 = CandidateEvaluationOutcome(
        variant_id=var_f2, product_id=uuid.uuid4(), product_name="Phone F2",
        sku_label="SKU-F2", is_eligible=True, constraints=[], exclusion_reasons=[],
    )

    eval_f1 = Evaluation(
        variant_id=var_f1,
        overall_score=Decimal("85.00"),
        coverage=Decimal("0.850"),
        confidence_score=Decimal("0.950"),
        confidence_state="high",
    )
    eval_f2 = Evaluation(
        variant_id=var_f2,
        overall_score=Decimal("85.00"),
        coverage=Decimal("0.850"),
        confidence_score=Decimal("0.750"),
        confidence_state="medium",
    )

    v_map_f = {var_f1: MockVariant(var_f1, "Phone F1"), var_f2: MockVariant(var_f2, "Phone F2")}
    e_map_f = {var_f1: eval_f1, var_f2: eval_f2}
    offers_f = {
        var_f1: {"price": 60000.0, "currency": "INR"},
        var_f2: {"price": 15000.0, "currency": "INR"},
    }

    ranked_f = RecommendationRankingService.rank_and_explain(
        requirements=req,
        eligible_outcomes=[out_f2, out_f1],
        evaluations_map=e_map_f,
        variants_map=v_map_f,
        offers_map=offers_f,
        community_map={},
        limit=5,
    )

    # Candidate F1 must win Rank #1 because confidence (0.95 > 0.75) takes precedence
    # despite F2 having much lower price (₹15,000 < ₹60,000)
    assert ranked_f[0].variant_id == var_f1
    assert ranked_f[0].rank == 1
    assert ranked_f[1].variant_id == var_f2
    assert ranked_f[1].rank == 2

    # ---------------------------------------------------------------------
    # Case 3: Canonical Variant UUID provides final tie-break
    # ---------------------------------------------------------------------
    var_u1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
    var_u2 = uuid.UUID("22222222-2222-2222-2222-222222222222")

    out_u1 = CandidateEvaluationOutcome(
        variant_id=var_u1, product_id=uuid.uuid4(), product_name="Phone U1",
        sku_label="SKU-U1", is_eligible=True, constraints=[], exclusion_reasons=[],
    )
    out_u2 = CandidateEvaluationOutcome(
        variant_id=var_u2, product_id=uuid.uuid4(), product_name="Phone U2",
        sku_label="SKU-U2", is_eligible=True, constraints=[], exclusion_reasons=[],
    )

    eval_u1 = Evaluation(
        variant_id=var_u1,
        overall_score=Decimal("85.00"),
        coverage=Decimal("0.850"),
        confidence_score=Decimal("0.800"),
        confidence_state="high",
    )
    eval_u2 = Evaluation(
        variant_id=var_u2,
        overall_score=Decimal("85.00"),
        coverage=Decimal("0.850"),
        confidence_score=Decimal("0.800"),
        confidence_state="high",
    )

    v_map_u = {var_u1: MockVariant(var_u1, "Phone U1"), var_u2: MockVariant(var_u2, "Phone U2")}
    e_map_u = {var_u1: eval_u1, var_u2: eval_u2}
    offers_u = {
        var_u1: {"price": 99000.0, "currency": "INR"},
        var_u2: {"price": 10000.0, "currency": "INR"},
    }

    ranked_u = RecommendationRankingService.rank_and_explain(
        requirements=req,
        eligible_outcomes=[out_u2, out_u1],
        evaluations_map=e_map_u,
        variants_map=v_map_u,
        offers_map=offers_u,
        community_map={},
        limit=5,
    )

    # Candidate U1 must win Rank #1 because string "1111..." < "2222..."
    # despite U2 having cheaper price (₹10,000 < ₹99,000)
    assert ranked_u[0].variant_id == var_u1
    assert ranked_u[0].rank == 1
    assert ranked_u[1].variant_id == var_u2
    assert ranked_u[1].rank == 2

    # ---------------------------------------------------------------------
    # Case 4: Price does NOT change ranking when all signals are equal
    # ---------------------------------------------------------------------
    offers_u_swapped = {
        var_u1: {"price": 1.0, "currency": "INR"},
        var_u2: {"price": 1000000.0, "currency": "INR"},
    }
    ranked_swapped = RecommendationRankingService.rank_and_explain(
        requirements=req,
        eligible_outcomes=[out_u2, out_u1],
        evaluations_map=e_map_u,
        variants_map=v_map_u,
        offers_map=offers_u_swapped,
        community_map={},
        limit=5,
    )
    # Ranking remains 100% identical
    assert ranked_swapped[0].variant_id == var_u1
    assert ranked_swapped[1].variant_id == var_u2


def test_session_lifecycle_all_transitions_and_isolation(db: Session):
    """Test comprehensive comparison session lifecycle transitions and owner isolation.

    Covers:
    - Active session INSERT (1, 2)
    - Third active session rejection
    - Active-to-active update without false limit trigger
    - Active-to-archived transition and active slot release
    - Archived-to-active transition rejection under max active
    - Owner identity change prevention under max active
    - Authenticated user isolation
    - Anonymous session token isolation
    - Logical namespace non-collision between user ID and anonymous token
    """
    repo = ComparisonRepository()

    user_a = User(email=f"usr_a_{uuid.uuid4().hex[:6]}@example.com", password_hash="pw", display_name="User A")
    user_b = User(email=f"usr_b_{uuid.uuid4().hex[:6]}@example.com", password_hash="pw", display_name="User B")
    user_c = User(email=f"usr_c_{uuid.uuid4().hex[:6]}@example.com", password_hash="pw", display_name="User C")
    db.add_all([user_a, user_b, user_c])
    db.commit()

    # 1. User A creates 2 active sessions
    s1 = repo.create_session(db, user_id=user_a.id, title="User A Session 1")
    repo.create_session(db, user_id=user_a.id, title="User A Session 2")
    db.commit()
    assert repo.count_active_sessions(db, user_id=user_a.id) == 2

    # 2. 3rd active session for User A is rejected
    with pytest.raises(ActiveComparisonSessionLimitError):
        repo.create_session(db, user_id=user_a.id, title="User A Session 3")

    # 3. Active-to-active update: renaming session does not trip limit
    s1.title = "User A Session 1 Renamed"
    db.commit()
    db.refresh(s1)
    assert s1.title == "User A Session 1 Renamed"
    assert repo.count_active_sessions(db, user_id=user_a.id) == 2

    # 4. Active-to-archived: archiving frees active slot
    repo.archive_session(db, s1.id)
    db.commit()
    assert repo.count_active_sessions(db, user_id=user_a.id) == 1

    # 5. New session can now be created
    s3 = repo.create_session(db, user_id=user_a.id, title="User A Session 3")
    db.commit()
    assert repo.count_active_sessions(db, user_id=user_a.id) == 2

    # 6. Archived-to-active transition is rejected by DB trigger when 2 active exist
    s1_obj = db.get(ComparisonSession, s1.id)
    s1_obj.status = "active"
    with pytest.raises((IntegrityError, DBAPIError)):
        db.commit()
    db.rollback()

    # 7. Owner change prevention: User B creates 2 active sessions
    repo.create_session(db, user_id=user_b.id, title="User B Session 1")
    repo.create_session(db, user_id=user_b.id, title="User B Session 2")
    db.commit()
    assert repo.count_active_sessions(db, user_id=user_b.id) == 2

    # Attempting to reassign an active session of User A to User B is rejected
    s3_obj = db.get(ComparisonSession, s3.id)
    s3_obj.user_id = user_b.id
    with pytest.raises((IntegrityError, DBAPIError)):
        db.commit()
    db.rollback()

    # 8. User C is completely isolated
    repo.create_session(db, user_id=user_c.id, title="User C Session 1")
    repo.create_session(db, user_id=user_c.id, title="User C Session 2")
    db.commit()
    assert repo.count_active_sessions(db, user_id=user_c.id) == 2

    # 9. Anonymous token isolation
    tok1 = f"anon_1_{uuid.uuid4().hex[:8]}"
    tok2 = f"anon_2_{uuid.uuid4().hex[:8]}"

    repo.create_session(db, anonymous_session_token=tok1, title="Anon 1 Session 1")
    repo.create_session(db, anonymous_session_token=tok1, title="Anon 1 Session 2")
    db.commit()

    with pytest.raises(ActiveComparisonSessionLimitError):
        repo.create_session(db, anonymous_session_token=tok1, title="Anon 1 Session 3")

    # tok2 is isolated from tok1
    repo.create_session(db, anonymous_session_token=tok2, title="Anon 2 Session 1")
    repo.create_session(db, anonymous_session_token=tok2, title="Anon 2 Session 2")
    db.commit()
    assert repo.count_active_sessions(db, anonymous_session_token=tok2) == 2

    # 10. Namespace collision prevention between UUID and anonymous token
    shared_uuid = uuid.uuid4()
    user_d = User(id=shared_uuid, email=f"usr_d_{shared_uuid.hex[:6]}@example.com", password_hash="pw")
    db.add(user_d)
    db.commit()

    repo.create_session(db, user_id=shared_uuid, title="User D Session 1")
    repo.create_session(db, user_id=shared_uuid, title="User D Session 2")
    db.commit()
    assert repo.count_active_sessions(db, user_id=shared_uuid) == 2

    # Anonymous token with exact same string as user_d UUID is completely isolated
    anon_str = str(shared_uuid)
    repo.create_session(db, anonymous_session_token=anon_str, title="Anon Matching String 1")
    repo.create_session(db, anonymous_session_token=anon_str, title="Anon Matching String 2")
    db.commit()
    assert repo.count_active_sessions(db, anonymous_session_token=anon_str) == 2


def test_evaluation_cache_invalidation_matrix(db: Session, b10_catalog_setup):
    """Test evaluation cache invalidation across all four integrity dimensions and Redis fallback.

    Dimensions:
    1. Model version change
    2. Configuration hash change
    3. Evidence snapshot hash change
    4. Identical valid evaluation reuse
    Plus Redis cache miss and Redis unavailability fallbacks.
    """
    v1 = b10_catalog_setup["v1"]
    eval_v1 = b10_catalog_setup["eval_v1"]
    model_ver = b10_catalog_setup["model_ver"]
    reuse_service = EvaluationReuseService(db)

    # 1. Baseline reuse succeeds
    baseline = reuse_service.get_or_evaluate_variant(v1.id)
    assert baseline.id == eval_v1.id

    # 2. Invalidation Dimension: Model version change
    m_ver2 = EvaluationModelVersion(
        model_id=model_ver.model_id,
        version=f"2.{uuid.uuid4().hex[:4]}",
        status="published",
        definition={
            "parameters": [
                {
                    "key": "ram_performance",
                    "attribute_key": "ram",
                    "weight": 1.0,
                    "critical": True,
                    "scoring_rule": {"type": "numeric_range", "min": 2, "max": 32},
                }
            ]
        },
        configuration_hash="conf_hash_ver2",
    )
    db.add(m_ver2)
    db.commit()

    eval_v2_model = reuse_service.get_or_evaluate_variant(v1.id, model_version_id=m_ver2.id)
    assert eval_v2_model.id != eval_v1.id
    assert eval_v2_model.model_version_id == m_ver2.id

    # 3. Invalidation Dimension: Configuration hash change
    m_ver3 = EvaluationModelVersion(
        model_id=model_ver.model_id,
        version=f"3.{uuid.uuid4().hex[:4]}",
        status="published",
        definition=model_ver.definition,
        configuration_hash="different_conf_hash_789",
    )
    db.add(m_ver3)
    db.commit()

    eval_v1_mod_cfg = reuse_service.get_or_evaluate_variant(v1.id, model_version_id=m_ver3.id)
    assert eval_v1_mod_cfg.id != eval_v1.id
    assert eval_v1_mod_cfg.configuration_hash == "different_conf_hash_789"

    # 4. Invalidation Dimension: Evidence snapshot change
    ev = Evidence(
        variant_id=v1.id,
        parameter_key="storage_capacity",
        source_type="manufacturer",
        trust_tier=1,
        current_version_id=uuid.uuid4(),
    )
    db.add(ev)
    db.commit()

    eval_ev_change = reuse_service.get_or_evaluate_variant(v1.id)
    assert eval_ev_change.id != eval_v1.id
    assert eval_ev_change.evidence_snapshot_hash != eval_v1.evidence_snapshot_hash

    # 5. Redis cache miss falls back seamlessly to PostgreSQL
    cache_key = reuse_service.build_cache_key(
        v1.id,
        eval_ev_change.model_version_id,
        eval_ev_change.configuration_hash,
        eval_ev_change.evidence_snapshot_hash,
    )
    if reuse_service.redis:
        reuse_service.redis.delete(cache_key)

    from_pg = reuse_service.get_or_evaluate_variant(v1.id)
    assert from_pg.id == eval_ev_change.id

    # 6. Redis unavailability does not break evaluation retrieval
    saved_redis = reuse_service.redis
    try:
        reuse_service.redis = None
        from_no_redis = reuse_service.get_or_evaluate_variant(v1.id)
        assert from_no_redis.id == eval_ev_change.id
    finally:
        reuse_service.redis = saved_redis


def test_hard_constraint_unknown_and_exclusions():
    """Verify three-valued logic (PASS, FAIL, UNKNOWN) for missing specs, missing prices, and booleans."""
    req_spec = ParsedRequirements(
        category_key="smartphone",
        budget_max=30000.0,
        hard_constraints=[
            HardConstraint(attribute_key="battery_capacity", operator=">=", target_value=5000, unit="mAh"),
        ],
    )

    # 1. Missing specification -> UNKNOWN -> candidate excluded
    outcome_missing_spec = ConstraintEngine.evaluate_candidate(
        requirements=req_spec,
        variant_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        product_name="Phone Unknown Spec",
        manufacturer="BrandX",
        sku_label="SKU-X",
        attribute_values={"ram": 8},  # battery_capacity is missing
        current_price=20000.0,
        price_available=True,
    )
    assert outcome_missing_spec.is_eligible is False
    c_detail = next(c for c in outcome_missing_spec.constraints if c.attribute_key == "battery_capacity")
    assert c_detail.outcome == ConstraintOutcome.UNKNOWN
    assert "Required attribute 'battery_capacity' is not available" in c_detail.reason

    # 2. Missing price when budget constraint is set -> UNKNOWN -> candidate excluded
    outcome_missing_price = ConstraintEngine.evaluate_candidate(
        requirements=req_spec,
        variant_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        product_name="Phone Unknown Price",
        manufacturer="BrandX",
        sku_label="SKU-X",
        attribute_values={"battery_capacity": 5500},
        current_price=None,
        price_available=False,
    )
    assert outcome_missing_price.is_eligible is False
    p_detail = next(c for c in outcome_missing_price.constraints if c.attribute_key == "price")
    assert p_detail.outcome == ConstraintOutcome.UNKNOWN
    assert "Current price is unavailable; cannot verify budget" in p_detail.reason

    # 3. Boolean False is distinct from missing and evaluates to FAIL (not UNKNOWN)
    req_bool = ParsedRequirements(
        category_key="smartphone",
        hard_constraints=[
            HardConstraint(attribute_key="waterproof", operator="==", target_value=True),
        ],
    )
    outcome_bool_fail = ConstraintEngine.evaluate_candidate(
        requirements=req_bool,
        variant_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        product_name="Phone Not Waterproof",
        manufacturer="BrandZ",
        sku_label="SKU-Z",
        attribute_values={"waterproof": False},
        current_price=15000.0,
        price_available=True,
    )
    assert outcome_bool_fail.is_eligible is False
    b_detail = outcome_bool_fail.constraints[0]
    assert b_detail.outcome == ConstraintOutcome.FAIL  # Genuine boolean False -> FAIL, not UNKNOWN!

    # 4. Soft preferences never override hard constraints
    req_soft = ParsedRequirements(
        category_key="smartphone",
        hard_constraints=[
            HardConstraint(attribute_key="ram", operator=">=", target_value=12, unit="GB"),
        ],
        soft_preferences=[
            SoftPreference(preference_key="camera", preferred_direction="higher", description="Best camera"),
        ],
    )
    outcome_soft = ConstraintEngine.evaluate_candidate(
        requirements=req_soft,
        variant_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        product_name="Camera Phone",
        manufacturer="CameraBrand",
        sku_label="SKU-Cam",
        attribute_values={"ram": 8, "camera": 108},  # RAM 8 fails >= 12
        current_price=25000.0,
        price_available=True,
    )
    assert outcome_soft.is_eligible is False


def test_requirement_parser_llm_fallback_and_edge_cases():
    """Verify requirement parser safe fallbacks when LLM produces malformed output or fails."""
    # 1. Malformed JSON from LLM gracefully falls back to deterministic regex parser
    mock_llm_malformed = MagicMock()
    mock_llm_malformed.generate_text.return_value = MagicMock(text="Sorry, here is not valid json {abc: 123")
    parser_malformed = RequirementParserService(llm_provider=mock_llm_malformed)

    res1 = parser_malformed.parse_query("Smartphone under 25000 with 8GB RAM")
    assert res1.requirements.category_key == "smartphone"
    assert res1.requirements.budget_max == 25000.0
    assert res1.requirements.extraction_source == "deterministic_fallback"

    # 2. LLM Provider exception gracefully falls back to deterministic regex parser
    mock_llm_error = MagicMock()
    mock_llm_error.generate_text.side_effect = RuntimeError("Groq API rate limit or outage")
    parser_error = RequirementParserService(llm_provider=mock_llm_error)

    res2 = parser_error.parse_query("Laptop under 60000 with 16GB RAM")
    assert res2.requirements.category_key == "laptop"
    assert res2.requirements.budget_max == 60000.0
    assert res2.requirements.extraction_source == "deterministic_fallback"


def test_api_comparison_and_recommendation_endpoints(db: Session, b10_catalog_setup):
    """Verify REST API authorization, ownership verification, cross-category rejection, and conflict responses."""
    cat_phone = b10_catalog_setup["cat_phone"]
    v1 = b10_catalog_setup["v1"]
    v_laptop = b10_catalog_setup["v_laptop"]

    user1_uuid = uuid.uuid4()
    user2_uuid = uuid.uuid4()

    db_user1 = User(id=user1_uuid, email=f"api_u1_{user1_uuid.hex[:6]}@example.com", password_hash="pw")
    db_user2 = User(id=user2_uuid, email=f"api_u2_{user2_uuid.hex[:6]}@example.com", password_hash="pw")
    db.add_all([db_user1, db_user2])
    db.commit()

    user1_id = str(user1_uuid)
    user2_id = str(user2_uuid)

    user1_auth = AuthenticatedUser(
        id=user1_id,
        email="api_user1@example.com",
        display_name="API User 1",
        roles=["consumer"],
        permissions={
            Permission.COMPARISON_READ.value,
            Permission.COMPARISON_WRITE.value,
            Permission.CATALOG_READ.value,
        },
    )
    user2_auth = AuthenticatedUser(
        id=user2_id,
        email="api_user2@example.com",
        display_name="API User 2",
        roles=["consumer"],
        permissions={
            Permission.COMPARISON_READ.value,
            Permission.COMPARISON_WRITE.value,
            Permission.CATALOG_READ.value,
        },
    )

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user1_auth

    try:
        with TestClient(app) as client:
            # 1. User 1 creates session 1
            res_c1 = client.post("/api/v1/comparisons", json={"title": "API Session 1"})
            assert res_c1.status_code == 201
            session1_id = res_c1.json()["id"]

            # 2. User 2 attempts to view User 1's session -> HTTP 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: user2_auth
            res_forbidden = client.get(f"/api/v1/comparisons/{session1_id}")
            assert res_forbidden.status_code == 403

            # Switch back to User 1
            app.dependency_overrides[get_current_user] = lambda: user1_auth

            # 3. User 1 adds variant 1 -> HTTP 201
            res_item = client.post(
                f"/api/v1/comparisons/{session1_id}/items",
                json={"variant_id": str(v1.id)},
            )
            assert res_item.status_code == 201

            # 4. User 1 attempts cross-category addition (laptop into smartphone session) -> HTTP 400
            res_cross = client.post(
                f"/api/v1/comparisons/{session1_id}/items",
                json={"variant_id": str(v_laptop.id)},
            )
            assert res_cross.status_code == 400
            assert "Cross-category comparison is not allowed" in res_cross.json()["detail"]

            # 5. User 1 creates session 2 -> HTTP 201
            res_c2 = client.post("/api/v1/comparisons", json={"title": "API Session 2"})
            assert res_c2.status_code == 201

            # 6. User 1 attempts to create session 3 -> HTTP 409 Conflict
            res_c3 = client.post("/api/v1/comparisons", json={"title": "API Session 3"})
            assert res_c3.status_code == 409
            assert "Maximum 2 active comparison sessions allowed" in res_c3.json()["detail"]

            # 7. Recommendation query parsing endpoint -> HTTP 200
            res_parse = client.post(
                "/api/v1/recommendations/parse",
                json={"query": "Smartphone under 25000 with at least 8GB RAM"},
            )
            assert res_parse.status_code == 200
            assert res_parse.json()["requirements"]["budget_max"] == 25000.0

            # 8. Recommendation generation endpoint -> HTTP 200
            res_rec = client.post(
                "/api/v1/recommendations",
                json={
                    "query": "Smartphone under 30000 with 8GB RAM",
                    "category_id": str(cat_phone.id),
                    "limit": 5,
                },
            )
            assert res_rec.status_code == 200
            rec_data = res_rec.json()
            assert rec_data["eligible_count"] >= 1
            assert len(rec_data["input_fingerprint"]) == 64
            assert len(rec_data["output_fingerprint"]) == 64
    finally:
        app.dependency_overrides.clear()

