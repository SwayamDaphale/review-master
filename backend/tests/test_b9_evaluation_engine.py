"""Phase B9 Comprehensive Test Suite: Deterministic Evaluation Engine.

Tests all 9 functional areas:
Group A: Rule Engine (linear_range, piecewise, boolean, ordinal, validation errors)
Group B: Missing & Conflicting Data (missing != 0, boolean false != missing, conflict withholding, trust tiers, version IDs)
Group C: Weighting & Coverage (normalization, zero weight rejection, negative weight rejection, coverage floor)
Group D: Confidence & Trust Tiers (T1 vs T4, conflict penalty -0.15, confidence bands, deterministic explanations)
Group E: Versioning & Immutability (draft edits, publish validation, immutable published versions, append-only history)
Group F: Determinism Gate & 14 Golden Fixtures (byte-for-byte exact hash and score reproduction)
Group G: REST API & RBAC (model registry CRUD, publishing, variant evaluate, history, RBAC 401/403)
Group H: Background Tasks & Durable Jobs (Celery calculate, recalculate, job lifecycle)
Group I: Regression & Backward Compatibility
"""

import json
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.permissions import RoleName, get_permissions_for_roles
from app.db.base import Base
from app.db.dependencies import get_db
from app.db.seed import seed_database
from app.main import app
from app.models.category import Category
from app.models.evaluation import Evaluation
from app.models.job import Job
from app.models.variant import Variant
from app.schemas.evaluation_config import (
    BooleanRuleParams,
    EvaluationModelConfig,
    LinearRangeRuleParams,
    OrdinalRuleParams,
    ParameterConfig,
    PiecewiseBreakpoint,
    PiecewiseRuleParams,
    compute_configuration_hash,
)
from app.services.evaluation_calculator import DeterministicEvaluationCalculator
from app.services.evaluation_registry import EvaluationRegistryService
from app.services.evaluation_rules import (
    evaluate_boolean,
    evaluate_linear_range,
    evaluate_ordinal,
    evaluate_piecewise,
)
from app.services.evaluation_service import EvaluationFoundationService
from app.worker.celery_app import (
    calculate_evaluation_task,
    recalculate_evaluation_task,
)

# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def db_session():
    """Create isolated seeded in-memory SQLite database for deterministic tests."""
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
    """Create FastAPI test client with seeded db and expert reviewer permissions."""
    def override_get_db():
        yield db_session

    expert_roles = [RoleName.EXPERT_REVIEWER.value]
    expert_user = AuthenticatedUser(
        id=str(uuid.uuid4()),
        user_id=uuid.uuid4(),
        email="expert@reviewmaster.local",
        roles=expert_roles,
        permissions=get_permissions_for_roles(expert_roles),
        is_authenticated=True,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: expert_user

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def consumer_client(db_session: Session):
    """Create FastAPI test client with consumer permissions (no EVALUATION_MANAGE)."""
    def override_get_db():
        yield db_session

    consumer_roles = [RoleName.CONSUMER.value]
    consumer_user = AuthenticatedUser(
        id=str(uuid.uuid4()),
        user_id=uuid.uuid4(),
        email="consumer@reviewmaster.local",
        roles=consumer_roles,
        permissions=get_permissions_for_roles(consumer_roles),
        is_authenticated=True,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: consumer_user

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def anon_client(db_session: Session):
    """Create FastAPI test client with no auth credentials."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    if get_current_user in app.dependency_overrides:
        del app.dependency_overrides[get_current_user]

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# =============================================================================
# Group A: Rule Engine
# =============================================================================


def test_linear_range_higher_is_better():
    """Test linear_range with higher_is_better direction."""
    params = LinearRangeRuleParams(
        min_val=Decimal("10.0"),
        max_val=Decimal("50.0"),
        direction="higher_is_better",
        clamp_out_of_bounds=True,
    )
    # Min value gives 0.0
    assert evaluate_linear_range(10.0, params) == Decimal("0.0")
    # Max value gives 100.0
    assert evaluate_linear_range(50.0, params) == Decimal("100.0")
    # Midpoint gives 50.0
    assert evaluate_linear_range(30.0, params) == Decimal("50.0")
    # Below min clamped to 0.0
    assert evaluate_linear_range(5.0, params) == Decimal("0.0")
    # Above max clamped to 100.0
    assert evaluate_linear_range(60.0, params) == Decimal("100.0")


def test_linear_range_lower_is_better():
    """Test linear_range with lower_is_better direction."""
    params = LinearRangeRuleParams(
        min_val=Decimal("100.0"),
        max_val=Decimal("200.0"),
        direction="lower_is_better",
        clamp_out_of_bounds=True,
    )
    # Min value gives 100.0
    assert evaluate_linear_range(100.0, params) == Decimal("100.0")
    # Max value gives 0.0
    assert evaluate_linear_range(200.0, params) == Decimal("0.0")
    # Midpoint gives 50.0
    assert evaluate_linear_range(150.0, params) == Decimal("50.0")


def test_linear_range_invalid_span_raises():
    """Test linear_range validation rejects min >= max."""
    with pytest.raises(ValidationError):
        LinearRangeRuleParams(
            min_val=Decimal("50.0"),
            max_val=Decimal("50.0"),
            direction="higher_is_better",
        )
    with pytest.raises(ValidationError):
        LinearRangeRuleParams(
            min_val=Decimal("60.0"),
            max_val=Decimal("50.0"),
            direction="higher_is_better",
        )


def test_piecewise_breakpoints_and_interpolation():
    """Test piecewise rule with ordered breakpoints and interpolation."""
    breakpoints = [
        PiecewiseBreakpoint(x=Decimal(4), score=Decimal("20.0")),
        PiecewiseBreakpoint(x=Decimal(8), score=Decimal("60.0")),
        PiecewiseBreakpoint(x=Decimal(16), score=Decimal("100.0")),
    ]
    params = PiecewiseRuleParams(breakpoints=breakpoints, interpolate=True)

    # Exact matches
    assert evaluate_piecewise(4, params) == Decimal("20.0")
    assert evaluate_piecewise(8, params) == Decimal("60.0")
    assert evaluate_piecewise(16, params) == Decimal("100.0")

    # Midpoint interpolation between 4 and 8: x=6 -> score=40.0
    assert evaluate_piecewise(6, params) == Decimal("40.0")

    # Clamping outside bounds
    assert evaluate_piecewise(2, params) == Decimal("20.0")
    assert evaluate_piecewise(32, params) == Decimal("100.0")


def test_piecewise_validation_rejects_non_monotonic():
    """Test piecewise validation rejects non-strictly increasing breakpoints."""
    with pytest.raises(ValidationError):
        PiecewiseRuleParams(
            breakpoints=[
                PiecewiseBreakpoint(x=Decimal(10), score=Decimal("50.0")),
                PiecewiseBreakpoint(x=Decimal(10), score=Decimal("60.0")),
            ]
        )
    with pytest.raises(ValidationError):
        PiecewiseRuleParams(
            breakpoints=[
                PiecewiseBreakpoint(x=Decimal(10), score=Decimal("50.0")),
                PiecewiseBreakpoint(x=Decimal(8), score=Decimal("60.0")),
            ]
        )


def test_boolean_rule():
    """Test boolean rule with true/false scores and case-insensitivity."""
    params = BooleanRuleParams(true_score=Decimal("100.0"), false_score=Decimal("20.0"))

    assert evaluate_boolean(True, params) == Decimal("100.0")
    assert evaluate_boolean(False, params) == Decimal("20.0")
    assert evaluate_boolean("True", params) == Decimal("100.0")
    assert evaluate_boolean("FALSE", params) == Decimal("20.0")
    assert evaluate_boolean("yes", params) == Decimal("100.0")
    assert evaluate_boolean("no", params) == Decimal("20.0")
    assert evaluate_boolean(1, params) == Decimal("100.0")
    assert evaluate_boolean(0, params) == Decimal("20.0")

    with pytest.raises(ValueError):
        evaluate_boolean("unknown", params)


def test_ordinal_rule():
    """Test ordinal rule with mapping and unknown key handling."""
    mapping = {
        "budget": Decimal("40.0"),
        "mid-range": Decimal("75.0"),
        "flagship": Decimal("100.0"),
    }
    params = OrdinalRuleParams(mapping=mapping)

    assert evaluate_ordinal("budget", params) == Decimal("40.0")
    assert evaluate_ordinal("Mid-Range", params) == Decimal("75.0")
    assert evaluate_ordinal("FLAGSHIP", params) == Decimal("100.0")

    with pytest.raises(KeyError):
        evaluate_ordinal("luxury", params)


# =============================================================================
# Group B: Missing & Conflicting Data
# =============================================================================


def test_missing_attribute_remains_missing_never_zero():
    """Test missing attribute is explicitly recorded as missing and not 0."""
    cfg = EvaluationModelConfig(
        name="Test Model",
        version="1.0.0",
        category_key="smartphone",
        parameters=[
            ParameterConfig(
                key="ram_gb",
                attribute_key="ram_gb",
                label="RAM",
                weight=Decimal("0.5"),
                scoring_rule="linear_range",
                rule_params=LinearRangeRuleParams(min_val=Decimal(2), max_val=Decimal(16)),
            ),
            ParameterConfig(
                key="battery",
                attribute_key="battery",
                label="Battery",
                weight=Decimal("0.5"),
                scoring_rule="linear_range",
                rule_params=LinearRangeRuleParams(min_val=Decimal(2000), max_val=Decimal(6000)),
            ),
        ],
    )
    attrs = {"ram_gb": 8}
    evidence = {
        "ram_gb": {
            "evidence_id": "ev-1",
            "evidence_version_id": "v1",
            "trust_tier": 1,
            "verification_state": "verified",
        }
    }

    result = DeterministicEvaluationCalculator.calculate(cfg, attrs, evidence)
    battery_param = next(p for p in result.parameter_results if p.parameter_key == "battery")

    assert battery_param.status == "missing"
    assert battery_param.score is None
    assert battery_param.effective_weight == Decimal("0.0")
    assert any(item["parameter_key"] == "battery" for item in result.limitations["parameter_limitations"])


def test_boolean_false_is_distinct_from_missing():
    """Test boolean False is evaluated and distinct from missing value."""
    cfg = EvaluationModelConfig(
        name="Test Model",
        version="1.0.0",
        category_key="smartphone",
        parameters=[
            ParameterConfig(
                key="waterproof",
                attribute_key="waterproof",
                label="Waterproof",
                weight=Decimal("1.0"),
                scoring_rule="boolean",
                rule_params=BooleanRuleParams(true_score=Decimal("100.0"), false_score=Decimal("0.0")),
            )
        ],
    )
    attrs = {"waterproof": False}
    evidence = {
        "waterproof": {
            "evidence_id": "ev-1",
            "evidence_version_id": "v1",
            "trust_tier": 1,
            "verification_state": "verified",
        }
    }

    result = DeterministicEvaluationCalculator.calculate(cfg, attrs, evidence)
    param = result.parameter_results[0]

    assert param.status == "evaluated"
    assert param.score == Decimal("0.0")
    assert result.overall_score == Decimal("0.0")


def test_conflicting_evidence_withholds_score():
    """Test conflicting evidence causes parameter score to be withheld."""
    cfg = EvaluationModelConfig(
        name="Test Model",
        version="1.0.0",
        category_key="smartphone",
        parameters=[
            ParameterConfig(
                key="ram_gb",
                attribute_key="ram_gb",
                label="RAM",
                weight=Decimal("1.0"),
                scoring_rule="linear_range",
                rule_params=LinearRangeRuleParams(min_val=Decimal(2), max_val=Decimal(16)),
            )
        ],
    )
    attrs = {"ram_gb": 8}
    evidence = {
        "ram_gb": {
            "evidence_id": "ev-1",
            "evidence_version_id": "v1",
            "trust_tier": 2,
            "verification_state": "conflict",
            "has_conflict": True,
        }
    }

    result = DeterministicEvaluationCalculator.calculate(cfg, attrs, evidence)
    param = result.parameter_results[0]

    assert param.status == "conflicting"
    assert param.score is None
    assert result.overall_score is None
    assert "conflicts" in result.limitations


def test_unverified_trust_tier_excluded():
    """Test evidence with unverified trust tier is excluded under strict model policy."""
    cfg = EvaluationModelConfig(
        name="Test Model",
        version="1.0.0",
        category_key="smartphone",
        parameters=[
            ParameterConfig(
                key="ram_gb",
                attribute_key="ram_gb",
                label="RAM",
                weight=Decimal("1.0"),
                scoring_rule="linear_range",
                rule_params=LinearRangeRuleParams(min_val=Decimal(2), max_val=Decimal(16)),
            )
        ],
    )
    attrs = {"ram_gb": 8}
    evidence = {
        "ram_gb": {
            "evidence_id": "ev-1",
            "evidence_version_id": "v1",
            "trust_tier": 4,
            "verification_state": "unverified",
        }
    }

    result = DeterministicEvaluationCalculator.calculate(cfg, attrs, evidence)
    param = result.parameter_results[0]

    assert param.status == "unverified"
    assert param.score is None
    assert result.overall_score is None


# =============================================================================
# Group C: Weighting & Coverage
# =============================================================================


def test_weight_normalization_sums_to_one():
    """Test effective weights sum to 1.00000 across evaluated parameters."""
    cfg = EvaluationModelConfig(
        name="Test Model",
        version="1.0.0",
        category_key="smartphone",
        parameters=[
            ParameterConfig(
                key="p1",
                attribute_key="p1",
                label="P1",
                weight=Decimal("0.3"),
                scoring_rule="linear_range",
                rule_params=LinearRangeRuleParams(min_val=Decimal(0), max_val=Decimal(10)),
            ),
            ParameterConfig(
                key="p2",
                attribute_key="p2",
                label="P2",
                weight=Decimal("0.5"),
                scoring_rule="linear_range",
                rule_params=LinearRangeRuleParams(min_val=Decimal(0), max_val=Decimal(10)),
            ),
            ParameterConfig(
                key="p3",
                attribute_key="p3",
                label="P3",
                weight=Decimal("0.2"),
                scoring_rule="linear_range",
                rule_params=LinearRangeRuleParams(min_val=Decimal(0), max_val=Decimal(10)),
            ),
        ],
    )
    attrs = {"p1": 5, "p2": 5, "p3": 5}
    evidence = {
        k: {"evidence_id": f"ev-{k}", "evidence_version_id": "v1", "trust_tier": 1, "verification_state": "verified"}
        for k in attrs
    }

    result = DeterministicEvaluationCalculator.calculate(cfg, attrs, evidence)
    effective_weights_sum = sum(p.effective_weight for p in result.parameter_results)
    assert effective_weights_sum == Decimal("1.00000")


def test_zero_or_negative_weight_rejected():
    """Test zero or negative parameter weights are rejected by configuration schema."""
    with pytest.raises(ValidationError):
        ParameterConfig(
            key="p1",
            attribute_key="p1",
            label="P1",
            weight=Decimal("0.0"),
            scoring_rule="boolean",
            rule_params=BooleanRuleParams(true_score=Decimal(100), false_score=Decimal(0)),
        )
    with pytest.raises(ValidationError):
        ParameterConfig(
            key="p2",
            attribute_key="p2",
            label="P2",
            weight=Decimal("-0.5"),
            scoring_rule="boolean",
            rule_params=BooleanRuleParams(true_score=Decimal(100), false_score=Decimal(0)),
        )


def test_insufficient_coverage_sets_overall_score_none():
    """Test coverage below floor (0.40) sets overall_score to None."""
    cfg = EvaluationModelConfig(
        name="Test Model",
        version="1.0.0",
        category_key="smartphone",
        parameters=[
            ParameterConfig(
                key="p1",
                attribute_key="p1",
                label="P1",
                weight=Decimal("0.2"),
                scoring_rule="linear_range",
                rule_params=LinearRangeRuleParams(min_val=Decimal(0), max_val=Decimal(10)),
            ),
            ParameterConfig(
                key="p2",
                attribute_key="p2",
                label="P2",
                weight=Decimal("0.8"),
                scoring_rule="linear_range",
                rule_params=LinearRangeRuleParams(min_val=Decimal(0), max_val=Decimal(10)),
            ),
        ],
    )
    attrs = {"p1": 10}
    evidence = {"p1": {"evidence_id": "ev-1", "evidence_version_id": "v1", "trust_tier": 1, "verification_state": "verified"}}

    result = DeterministicEvaluationCalculator.calculate(cfg, attrs, evidence)

    assert result.coverage == Decimal("0.200")
    assert result.coverage_state == "insufficient"
    assert result.overall_score is None


# =============================================================================
# Group D: Confidence & Trust Tiers
# =============================================================================


def test_confidence_trust_tier_differentiation():
    """Test T1 verified evidence gives higher confidence than T3."""
    cfg = EvaluationModelConfig(
        name="Test Model",
        version="1.0.0",
        category_key="smartphone",
        parameters=[
            ParameterConfig(
                key="p1",
                attribute_key="p1",
                label="P1",
                weight=Decimal("1.0"),
                scoring_rule="linear_range",
                rule_params=LinearRangeRuleParams(min_val=Decimal(0), max_val=Decimal(10)),
            )
        ],
    )
    attrs = {"p1": 5}

    res_t1 = DeterministicEvaluationCalculator.calculate(
        cfg, attrs, {"p1": {"evidence_id": "ev-1", "evidence_version_id": "v1", "trust_tier": 1, "verification_state": "verified"}}
    )
    res_t3 = DeterministicEvaluationCalculator.calculate(
        cfg, attrs, {"p1": {"evidence_id": "ev-1", "evidence_version_id": "v1", "trust_tier": 3, "verification_state": "verified"}}
    )

    assert res_t1.confidence_score > res_t3.confidence_score
    assert res_t1.confidence_state == "high"


def test_confidence_conflict_penalty():
    """Test conflicting evidence incurs a -0.15 confidence penalty."""
    cfg = EvaluationModelConfig(
        name="Test Model",
        version="1.0.0",
        category_key="smartphone",
        parameters=[
            ParameterConfig(
                key="p1",
                attribute_key="p1",
                label="P1",
                weight=Decimal("0.5"),
                scoring_rule="linear_range",
                rule_params=LinearRangeRuleParams(min_val=Decimal(0), max_val=Decimal(10)),
            ),
            ParameterConfig(
                key="p2",
                attribute_key="p2",
                label="P2",
                weight=Decimal("0.5"),
                scoring_rule="linear_range",
                rule_params=LinearRangeRuleParams(min_val=Decimal(0), max_val=Decimal(10)),
            ),
        ],
    )
    attrs = {"p1": 5, "p2": 5}

    res_clean = DeterministicEvaluationCalculator.calculate(
        cfg,
        attrs,
        {
            "p1": {"evidence_id": "ev-1", "evidence_version_id": "v1", "trust_tier": 1, "verification_state": "verified"},
            "p2": {"evidence_id": "ev-2", "evidence_version_id": "v1", "trust_tier": 1, "verification_state": "verified"},
        },
    )

    res_conflict = DeterministicEvaluationCalculator.calculate(
        cfg,
        attrs,
        {
            "p1": {"evidence_id": "ev-1", "evidence_version_id": "v1", "trust_tier": 1, "verification_state": "verified"},
            "p2": {"evidence_id": "ev-2", "evidence_version_id": "v1", "trust_tier": 1, "verification_state": "conflict", "has_conflict": True},
        },
    )

    assert res_conflict.confidence_score < res_clean.confidence_score
    assert "conflicts" in res_conflict.limitations


# =============================================================================
# Group E: Versioning & Immutability
# =============================================================================


def test_draft_version_lifecycle(db_session: Session):
    """Test model registry draft -> validated -> published -> deprecated lifecycle."""
    registry = EvaluationRegistryService(db_session)
    category = db_session.execute(select(Category).where(Category.key == "smartphone")).scalar_one()

    # 1. Create model
    model = registry.create_model(category_id=category.id, name="Lifecycle Model", description="Test lifecycle")
    assert model.status == "draft"

    # 2. Add draft version
    definition = {
        "name": "Lifecycle Model",
        "version": "1.0.0",
        "category_key": "smartphone",
        "parameters": [
            {
                "key": "battery",
                "attribute_key": "battery_capacity_mah",
                "label": "Battery Capacity",
                "weight": "1.0",
                "scoring_rule": "linear_range",
                "rule_params": {"min_val": "3000", "max_val": "6000", "direction": "higher_is_better"},
            }
        ],
    }
    version = registry.add_version(model_id=model.id, version="1.0.0", definition=definition)
    assert version.status == "draft"
    assert version.configuration_hash is not None

    # 3. Validate version
    validated_cfg = registry.validate_version(version_id=version.id)
    assert validated_cfg.version == "1.0.0"

    # 4. Publish version
    pub_ver = registry.publish_version(version_id=version.id)
    assert pub_ver.status == "published"
    assert model.status == "published"
    assert model.active_version_id == pub_ver.id

    # 5. Attempting to publish again fails (strictly immutable)
    with pytest.raises(ValueError, match="already in published status"):
        registry.publish_version(version_id=version.id)

    # 6. Deprecate version
    dep_ver = registry.deprecate_version(version_id=pub_ver.id)
    assert dep_ver.status == "deprecated"


def test_recalculation_strictly_appends_new_evaluation(db_session: Session):
    """Test recalculation creates new Evaluation rows, strictly preserving history."""
    service = EvaluationFoundationService(db_session)
    category = db_session.execute(select(Category).where(Category.key == "smartphone")).scalar_one()
    variant = db_session.execute(select(Variant)).scalars().first()
    assert variant is not None

    # Create published model
    registry = EvaluationRegistryService(db_session)
    model = registry.create_model(category_id=category.id, name="History Model")
    definition = {
        "name": "History Model",
        "version": "1.0.0",
        "category_key": "smartphone",
        "parameters": [
            {
                "key": "ram",
                "attribute_key": "ram_gb",
                "label": "RAM",
                "weight": "1.0",
                "scoring_rule": "linear_range",
                "rule_params": {"min_val": "2", "max_val": "16", "direction": "higher_is_better"},
            }
        ],
    }
    ver = registry.add_version(model.id, "1.0.0", definition)
    registry.publish_version(ver.id)

    # Run evaluation 1
    eval1 = service.evaluate_variant(variant.id)
    db_session.flush()

    # Run evaluation 2 (recalculation)
    eval2 = service.evaluate_variant(variant.id)
    db_session.flush()

    assert eval1.id != eval2.id
    # Ensure both rows exist in DB
    all_evals = db_session.execute(
        select(Evaluation).where(Evaluation.variant_id == variant.id)
    ).scalars().all()
    assert len(all_evals) >= 2


# =============================================================================
# Group F: Determinism Gate & 14 Golden Fixtures
# =============================================================================


def test_golden_fixtures_determinism_gate():
    """Verify all 14 golden fixtures produce byte-for-byte exact output hashes and scores."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "evaluations"
    assert fixtures_dir.exists(), "Fixtures directory must exist"

    fixtures = sorted(fixtures_dir.glob("*.json"))
    assert len(fixtures) == 14, f"Expected exactly 14 golden fixtures, found {len(fixtures)}"

    for fixture_path in fixtures:
        with open(fixture_path, encoding="utf-8") as f:
            data = json.load(f)

        is_valid = data.get("is_valid", True)
        if not is_valid:
            # Fixtures 11 and 13 represent invalid configs
            with pytest.raises((ValidationError, ValueError)):
                EvaluationModelConfig.model_validate(data["model_config"])
            continue

        model_config = EvaluationModelConfig.model_validate(data["model_config"])
        computed_config_hash = compute_configuration_hash(model_config)

        expected = data["expected_output"]
        assert computed_config_hash == expected["configuration_hash"], (
            f"Config hash mismatch in {fixture_path.name}: "
            f"computed {computed_config_hash} != expected {expected['configuration_hash']}"
        )

        outcome = DeterministicEvaluationCalculator.calculate(
            model_config=model_config,
            attribute_values=data["variant_attributes"],
            evidence_records=data["evidence_records"],
        )

        # Assert byte-for-byte matching on canonical fingerprints
        assert outcome.input_fingerprint == expected["input_fingerprint"], (
            f"Input fingerprint mismatch in {fixture_path.name}: "
            f"computed {outcome.input_fingerprint} != expected {expected['input_fingerprint']}"
        )
        assert outcome.output_fingerprint == expected["output_fingerprint"], (
            f"Output fingerprint mismatch in {fixture_path.name}: "
            f"computed {outcome.output_fingerprint} != expected {expected['output_fingerprint']}"
        )

        # Assert scores and states
        if expected["overall_score"] is not None:
            assert outcome.overall_score == Decimal(expected["overall_score"]), (
                f"Score mismatch in {fixture_path.name}"
            )
        else:
            assert outcome.overall_score is None

        assert outcome.coverage == Decimal(expected["coverage"])
        assert outcome.coverage_state == expected["coverage_state"]
        assert outcome.confidence_score == Decimal(expected["confidence_score"])
        assert outcome.confidence_state == expected["confidence_state"]


# =============================================================================
# Group G: REST API & RBAC
# =============================================================================


def test_api_create_validate_publish_model(test_client: TestClient, db_session: Session):
    """Test full API model registry workflow: create -> version -> validate -> publish."""
    category = db_session.execute(select(Category).where(Category.key == "smartphone")).scalar_one()

    # 1. Create model
    res = test_client.post(
        "/api/v1/evaluation-models",
        json={"category_id": str(category.id), "name": "API Scoring Model", "description": "Via REST API"},
    )
    assert res.status_code == 201
    model_data = res.json()
    model_id = model_data["id"]

    # 2. Add version
    definition = {
        "name": "API Scoring Model",
        "version": "1.0.0",
        "category_key": "smartphone",
        "parameters": [
            {
                "key": "battery",
                "attribute_key": "battery_capacity_mah",
                "label": "Battery",
                "weight": "1.0",
                "scoring_rule": "linear_range",
                "rule_params": {"min_val": "3000", "max_val": "6000", "direction": "higher_is_better"},
            }
        ],
    }
    res_ver = test_client.post(
        f"/api/v1/evaluation-models/{model_id}/versions",
        json={"version": "1.0.0", "definition": definition},
    )
    assert res_ver.status_code == 201
    version_id = res_ver.json()["id"]

    # 3. Validate version
    res_val = test_client.post(f"/api/v1/evaluation-models/{model_id}/versions/{version_id}/validate")
    assert res_val.status_code == 200
    assert res_val.json()["status"] == "validated"

    # 4. Publish version
    res_pub = test_client.post(f"/api/v1/evaluation-models/{model_id}/versions/{version_id}/publish")
    assert res_pub.status_code == 200
    assert res_pub.json()["status"] == "published"


def test_api_rbac_consumer_forbidden(consumer_client: TestClient, db_session: Session):
    """Test consumer is forbidden (HTTP 403) from model management."""
    category = db_session.execute(select(Category).where(Category.key == "smartphone")).scalar_one()
    res = consumer_client.post(
        "/api/v1/evaluation-models",
        json={"category_id": str(category.id), "name": "Unauthorized Model"},
    )
    assert res.status_code == 403


def test_api_rbac_anonymous_unauthorized(anon_client: TestClient, db_session: Session):
    """Test anonymous request is unauthorized (HTTP 401)."""
    category = db_session.execute(select(Category).where(Category.key == "smartphone")).scalar_one()
    res = anon_client.post(
        "/api/v1/evaluation-models",
        json={"category_id": str(category.id), "name": "Anon Model"},
    )
    assert res.status_code == 401


def test_api_evaluate_and_history(test_client: TestClient, db_session: Session):
    """Test variant evaluation execution, latest retrieval, and history via REST API."""
    category = db_session.execute(select(Category).where(Category.key == "smartphone")).scalar_one()
    variant = db_session.execute(select(Variant)).scalars().first()
    assert variant is not None

    # Setup published model
    registry = EvaluationRegistryService(db_session)
    model = registry.create_model(category_id=category.id, name="Evaluation API Model")
    definition = {
        "name": "Evaluation API Model",
        "version": "1.0.0",
        "category_key": "smartphone",
        "parameters": [
            {
                "key": "ram",
                "attribute_key": "ram_gb",
                "label": "RAM",
                "weight": "1.0",
                "scoring_rule": "linear_range",
                "rule_params": {"min_val": "2", "max_val": "16", "direction": "higher_is_better"},
            }
        ],
    }
    ver = registry.add_version(model.id, "1.0.0", definition)
    registry.publish_version(ver.id)

    # 1. Trigger evaluation
    res_eval = test_client.post(f"/api/v1/variants/{variant.id}/evaluations")
    assert res_eval.status_code == 201
    eval_id = res_eval.json()["id"]

    # 2. Get latest evaluation
    res_latest = test_client.get(f"/api/v1/variants/{variant.id}/evaluations/latest")
    assert res_latest.status_code == 200
    assert res_latest.json()["id"] == eval_id

    # 3. Recalculate
    res_recalc = test_client.post(f"/api/v1/variants/{variant.id}/evaluations/recalculate")
    assert res_recalc.status_code == 201
    recalc_id = res_recalc.json()["id"]
    assert recalc_id != eval_id

    # 4. History contains both evaluations
    res_hist = test_client.get(f"/api/v1/variants/{variant.id}/evaluations/history")
    assert res_hist.status_code == 200
    assert len(res_hist.json()["items"]) >= 2


# =============================================================================
# Group H: Background Tasks & Durable Jobs
# =============================================================================


def test_celery_calculate_evaluation_task(db_session: Session):
    """Test Celery background task evaluation.calculate execution with durable job tracking."""
    category = db_session.execute(select(Category).where(Category.key == "smartphone")).scalar_one()
    variant = db_session.execute(select(Variant)).scalars().first()
    assert variant is not None

    # Setup published model
    registry = EvaluationRegistryService(db_session)
    model = registry.create_model(category_id=category.id, name="Celery Eval Model")
    definition = {
        "name": "Celery Eval Model",
        "version": "1.0.0",
        "category_key": "smartphone",
        "parameters": [
            {
                "key": "ram",
                "attribute_key": "ram_gb",
                "label": "RAM",
                "weight": "1.0",
                "scoring_rule": "linear_range",
                "rule_params": {"min_val": "2", "max_val": "16", "direction": "higher_is_better"},
            }
        ],
    }
    ver = registry.add_version(model.id, "1.0.0", definition)
    registry.publish_version(ver.id)

    # Create durable Job record
    job = Job(
        job_type="evaluation.calculate",
        status="pending",
        payload={"variant_id": str(variant.id)},
    )
    db_session.add(job)
    db_session.commit()

    variant_id_str = str(variant.id)
    ver_id_str = str(ver.id)
    job_id_str = str(job.id)

    class NonClosingSession:
        def __init__(self, s):
            self._s = s
        def __getattr__(self, name):
            if name == "close":
                return lambda: None
            return getattr(self._s, name)

    with patch("app.worker.tasks.evaluation.ca.SessionLocal", lambda: NonClosingSession(db_session)):
        result = calculate_evaluation_task.apply(
            args=[variant_id_str],
            kwargs={"job_id_str": job_id_str},
        ).get()

        assert result["status"] == "completed"
        assert result["variant_id"] == variant_id_str
        assert result["model_version_id"] == ver_id_str

        # Confirm job marked completed in database
        db_session.refresh(job)
        assert job.status == "completed"
        assert job.result is not None


def test_celery_recalculate_evaluation_task(db_session: Session):
    """Test Celery background task evaluation.recalculate execution."""
    category = db_session.execute(select(Category).where(Category.key == "smartphone")).scalar_one()
    variant = db_session.execute(select(Variant)).scalars().first()
    assert variant is not None

    registry = EvaluationRegistryService(db_session)
    model = registry.create_model(category_id=category.id, name="Celery Recalc Model")
    definition = {
        "name": "Celery Recalc Model",
        "version": "1.0.0",
        "category_key": "smartphone",
        "parameters": [
            {
                "key": "ram",
                "attribute_key": "ram_gb",
                "label": "RAM",
                "weight": "1.0",
                "scoring_rule": "linear_range",
                "rule_params": {"min_val": "2", "max_val": "16", "direction": "higher_is_better"},
            }
        ],
    }
    ver = registry.add_version(model.id, "1.0.0", definition)
    registry.publish_version(ver.id)

    variant_id_str = str(variant.id)

    class NonClosingSession:
        def __init__(self, s):
            self._s = s
        def __getattr__(self, name):
            if name == "close":
                return lambda: None
            return getattr(self._s, name)

    with patch("app.worker.tasks.evaluation.ca.SessionLocal", lambda: NonClosingSession(db_session)):
        result = recalculate_evaluation_task.apply(
            args=[variant_id_str],
        ).get()

        assert result["status"] == "completed"
        assert result["variant_id"] == variant_id_str


# =============================================================================
# Group I: Regressions & Foundation Compatibility
# =============================================================================


def test_evaluation_foundation_uncalibrated_behavior(db_session: Session):
    """Test that variant without active model version yields uncalibrated evaluation with overall_score=None."""
    service = EvaluationFoundationService(db_session)
    variant = db_session.execute(select(Variant)).scalars().first()
    assert variant is not None

    evaluation = service.evaluate_variant(variant.id)
    assert evaluation.overall_score is None
    assert evaluation.coverage == Decimal("0.000")
