"""B5 Remediation Verification Test Suite.

Covers:
1. Module 1: Secure Review Job Status API (Authentication, RBAC, ownership, schema sanitization, Redis vs DB consistency).
2. Module 2: Background review processing, Celery task execution, bounded retries, and duplicate delivery deduplication.
3. Module 3: Review Pro/Con aspect provenance (identified vs unidentified vs backward compatibility).
4. Module 4: Attribute evidence provenance (evidence-backed vs evidence-free).
"""

import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.dependencies import get_db
from app.db.seed import seed_database
from app.main import app
from app.models.evidence import Evidence
from app.models.product import Product
from app.models.review_intelligence import ReviewProCon
from app.models.variant import Variant
from app.repositories.attribute_repository import AttributeRepository
from app.repositories.identity_repository import RoleRepository, UserRepository
from app.services.async_jobs import AsyncJobManager
from app.services.llm.base import (
    LLMProvider,
    ProviderUsage,
    StructuredOutputResult,
    TextOutputResult,
)
from app.services.llm.orchestrator import InferenceOrchestrator
from app.services.llm.prompts import (
    ExtractedAspectOpinion,
    ExtractedProCon,
    ReviewAnalysisOutput,
)
from app.services.review_intelligence import ReviewIntelligenceService
from app.worker.celery_app import process_review_analysis_task

settings.JWT_SECRET = "change-me-dev-only-32-byte-secret-key-1234"


class MockMemoryRedis:
    """Mock Redis client for test isolation."""

    def __init__(self):
        self._store = {}

    def get(self, key: str):
        return self._store.get(key)

    def set(self, key: str, value: str, ex: int | None = None):
        self._store[key] = value

    def delete(self, key: str):
        self._store.pop(key, None)


@pytest.fixture
def remediation_client():
    """Set up isolated TestClient with in-memory database."""
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
        client.headers.update({"x-bypass-rate-limit": "true"})
        yield client, TestingSession
    app.dependency_overrides.clear()


def _create_user_with_role(db, role_name: str):
    """Create user and return (user, auth_header)."""
    role = RoleRepository.get_by_name(db, role_name)
    user = UserRepository.create(
        db,
        email=f"{role_name}_{uuid.uuid4().hex[:6]}@test.local",
        password_hash=hash_password("Password123!"),
    )
    if role:
        RoleRepository.assign_role_to_user(db, user.id, role.id)
    db.commit()
    token = create_access_token(
        {"sub": str(user.id), "email": user.email, "roles": [role_name]}
    )
    return user, {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Module 1: Safe Job-Status API & Authorization Tests
# ==============================================================================


def test_01_job_status_anonymous_access_rejected(remediation_client):
    """Anonymous request to job status endpoint must receive 401."""
    client, _ = remediation_client
    resp = client.get(f"/api/v1/reviews/jobs/{uuid.uuid4()}")
    assert resp.status_code == 401


def test_02_job_status_owner_access_allowed_and_sanitized(remediation_client):
    """Job owner can view status and response is sanitized without internal payloads or secrets."""
    client, TestingSession = remediation_client
    db = TestingSession()
    owner, owner_headers = _create_user_with_role(db, "consumer")

    manager = AsyncJobManager(db)
    job, _ = manager.create_or_get_job(
        idempotency_key=f"test-owner-{uuid.uuid4()}",
        job_type="review_analysis",
        payload={
            "sensitive_prompt": "SECRET_INTERNAL_PROMPT_DO_NOT_LEAK",
            "review_text": "Private text",
            "api_key": "sk-secret-12345",
        },
        user_id=owner.id,
    )
    manager.update_job_status(
        job.id,
        status="completed",
        result_payload={
            "analysis_id": str(uuid.uuid4()),
            "status": "completed",
            "raw_llm_dump": "UNFILTERED",
        },
    )
    db.commit()

    resp = client.get(f"/api/v1/reviews/jobs/{job.id}", headers=owner_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Required sanitized fields
    assert data["job_id"] == str(job.id)
    assert data["job_type"] == "review_analysis"
    assert data["status"] == "completed"
    assert "result_summary" in data

    # Strict exclusion of internal/sensitive payloads
    assert "payload" not in data
    assert "sensitive_prompt" not in str(data)
    assert "sk-secret-12345" not in str(data)
    assert "UNFILTERED" not in str(data)
    assert "raw_llm_dump" not in str(data)


def test_03_job_status_unauthorized_user_forbidden(remediation_client):
    """A non-owner non-admin user receives 403 Forbidden."""
    client, TestingSession = remediation_client
    db = TestingSession()
    owner, _ = _create_user_with_role(db, "consumer")
    _other_user, other_headers = _create_user_with_role(db, "consumer")

    manager = AsyncJobManager(db)
    job, _ = manager.create_or_get_job(
        idempotency_key=f"test-forbidden-{uuid.uuid4()}",
        user_id=owner.id,
    )
    db.commit()

    resp = client.get(f"/api/v1/reviews/jobs/{job.id}", headers=other_headers)
    assert resp.status_code == 403
    assert "forbidden" in resp.json()["detail"].lower()


def test_04_job_status_admin_access_allowed(remediation_client):
    """An administrator can inspect any user's job status."""
    client, TestingSession = remediation_client
    db = TestingSession()
    owner, _ = _create_user_with_role(db, "consumer")
    _admin, admin_headers = _create_user_with_role(db, "admin")

    manager = AsyncJobManager(db)
    job, _ = manager.create_or_get_job(
        idempotency_key=f"test-admin-{uuid.uuid4()}",
        user_id=owner.id,
    )
    db.commit()

    resp = client.get(f"/api/v1/reviews/jobs/{job.id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["job_id"] == str(job.id)


def test_05_job_status_redis_and_postgres_exact_same_structure(remediation_client):
    """Redis cache and PostgreSQL fallback must return identical sanitized response schema."""
    _, TestingSession = remediation_client
    db = TestingSession()
    mock_redis = MockMemoryRedis()

    manager = AsyncJobManager(db, redis_client=mock_redis)
    user_id = uuid.uuid4()
    job, _ = manager.create_or_get_job(
        idempotency_key=f"test-struct-{uuid.uuid4()}",
        payload={"secret": "HIDE_ME"},
        user_id=user_id,
    )
    manager.update_job_status(
        job.id,
        status="failed",
        error_message="Traceback (most recent call last):\n  File 'worker.py', line 12\nValueError: Rate limit exceeded",
    )
    db.commit()

    # 1. Fetch via Redis cache
    redis_status = manager.get_job_status(job.id)

    # 2. Invalidate Redis to force PostgreSQL DB fallback
    mock_redis.delete(f"job:{job.id}")
    db_status = manager.get_job_status(job.id)

    # Assert identical keys
    assert set(redis_status.keys()) == set(db_status.keys())
    assert redis_status["job_id"] == db_status["job_id"]
    assert redis_status["job_type"] == db_status["job_type"]
    assert redis_status["status"] == db_status["status"]
    assert redis_status["user_id"] == db_status["user_id"]

    # Assert tracebacks are sanitized in both paths
    assert "Traceback" not in redis_status["error_summary"]
    assert "Traceback" not in db_status["error_summary"]
    assert "Rate limit exceeded" in redis_status["error_summary"]
    assert "Rate limit exceeded" in db_status["error_summary"]


# ==============================================================================
# Module 2: Background Processing & Celery Worker Tests
# ==============================================================================


def test_06_review_analyze_enqueues_background_job_and_returns_202(remediation_client):
    """POST /api/v1/reviews/analyze returns 202 Accepted with job ID without waiting for inference."""
    client, TestingSession = remediation_client
    db = TestingSession()
    _ingest_user, ingest_headers = _create_user_with_role(db, "admin")

    prod = db.query(Product).first()

    with patch(
        "app.worker.celery_app.process_review_analysis_task.delay"
    ) as mock_delay:
        resp = client.post(
            "/api/v1/reviews/analyze",
            headers=ingest_headers,
            json={
                "product_id": str(prod.id),
                "review_text": "This phone has exceptional battery life and very fast processing speed.",
                "review_source_id": "AMZ_REV_12345",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert "idempotency_key" in data
        mock_delay.assert_called_once()


def test_07_celery_worker_execution_flow(remediation_client):
    """Worker task execution transitions job pending -> running -> completed and records analysis."""
    _, TestingSession = remediation_client
    db = TestingSession()
    prod = db.query(Product).first()

    manager = AsyncJobManager(db)
    job, _ = manager.create_or_get_job(
        idempotency_key=f"worker-test-{uuid.uuid4()}",
        user_id=uuid.uuid4(),
    )
    db.commit()

    sample_output = ReviewAnalysisOutput(
        sentiment="positive",
        sentiment_confidence=0.96,
        aspects=[
            ExtractedAspectOpinion(
                aspect_key="battery",
                polarity="positive",
                claim="Battery endurance is outstanding.",
                confidence=0.95,
            )
        ],
        pros_cons=[
            ExtractedProCon(
                item_type="pro",
                text="Long lasting battery",
                aspect_key="battery",
                confidence=0.92,
            )
        ],
    )

    class MockProvider(LLMProvider):
        name = "groq"
        model_name = "llama-3.3-70b-versatile"

        async def generate_structured(
            self, prompt, schema, system_prompt=None, timeout=30.0
        ):
            return StructuredOutputResult(
                data=sample_output,
                provider="groq",
                model="llama-3.3-70b-versatile",
                raw_response="{}",
                usage=ProviderUsage(10, 10, 20, 50.0),
            )

        async def generate_text(self, prompt, system_prompt=None, timeout=30.0):
            return TextOutputResult("text", "groq", "llama-3.3-70b-versatile")

        async def health_check(self):
            return True

    orch = InferenceOrchestrator(primary_provider=MockProvider())

    with (
        patch(
            "app.services.review_intelligence.InferenceOrchestrator", return_value=orch
        ),
        patch("app.worker.celery_app.SessionLocal", TestingSession),
    ):
        result = process_review_analysis_task(
            job_id_str=str(job.id),
            review_text="Battery lasts 2 full days under normal use.",
            product_id_str=str(prod.id),
        )

    assert result["status"] == "completed"
    assert "analysis_id" in result

    # Verify status in database
    updated_job = manager.get_job_status(job.id)
    assert updated_job["status"] == "completed"
    assert updated_job["result_summary"]["status"] == "completed"


def test_08_celery_worker_duplicate_task_delivery_idempotent(remediation_client):
    """Duplicate Celery task delivery for an already completed job returns without re-executing."""
    _, TestingSession = remediation_client
    db = TestingSession()

    manager = AsyncJobManager(db)
    job, _ = manager.create_or_get_job(
        idempotency_key=f"worker-dup-{uuid.uuid4()}",
    )
    manager.update_job_status(
        job.id,
        status="completed",
        result_payload={"analysis_id": "test-123", "status": "completed"},
    )
    db.commit()

    with (
        patch("app.worker.celery_app.SessionLocal", TestingSession),
        patch(
            "app.services.review_intelligence.ReviewIntelligenceService.analyze_review"
        ) as mock_analyze,
    ):
        result = process_review_analysis_task(
            job_id_str=str(job.id),
            review_text="Some text",
        )
        assert result["status"] == "completed"
        mock_analyze.assert_not_called()


# ==============================================================================
# Module 3: Review Pro/Con Aspect Provenance Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_09_pro_con_aspect_provenance_identified(remediation_client):
    """Pros/cons with identifiable aspect keys persist aspect_key on ReviewProCon."""
    _, TestingSession = remediation_client
    db = TestingSession()
    prod = db.query(Product).first()

    sample_output = ReviewAnalysisOutput(
        sentiment="positive",
        aspects=[
            ExtractedAspectOpinion(
                aspect_key="camera",
                polarity="positive",
                claim="Crisp zoom photos.",
                confidence=0.9,
            )
        ],
        pros_cons=[
            ExtractedProCon(
                item_type="pro",
                text="Sharp 5x telephoto lens",
                aspect_key="camera",
                confidence=0.95,
                source_reference="Zoom photos are very crisp",
            ),
            ExtractedProCon(
                item_type="con",
                text="Heavy thermal throttling during 4K video",
                aspect_key="performance",
                confidence=0.88,
            ),
        ],
    )

    class DummyProvider(LLMProvider):
        name = "mock"
        model_name = "mock"

        async def generate_structured(
            self, prompt, schema, system_prompt=None, timeout=30.0
        ):
            return StructuredOutputResult(
                sample_output, "mock", "mock", "{}", ProviderUsage(0, 0, 0, 0)
            )

        async def generate_text(self, prompt, system_prompt=None, timeout=30.0):
            return TextOutputResult("text", "mock", "mock")

        async def health_check(self):
            return True

    service = ReviewIntelligenceService(
        db, orchestrator=InferenceOrchestrator(primary_provider=DummyProvider())
    )
    analysis = await service.analyze_review(
        review_text="Camera is great but it throttles when recording 4k.",
        product_id=prod.id,
    )
    db.commit()

    pcs = db.query(ReviewProCon).filter(ReviewProCon.analysis_id == analysis.id).all()
    assert len(pcs) == 2

    pro_item = next(p for p in pcs if p.item_type == "pro")
    assert pro_item.aspect_key == "camera"
    assert "telephoto" in pro_item.text

    con_item = next(p for p in pcs if p.item_type == "con")
    assert con_item.aspect_key == "performance"
    assert "throttling" in con_item.text


@pytest.mark.asyncio
async def test_10_pro_con_aspect_provenance_unidentified_remains_null(
    remediation_client,
):
    """When the aspect key cannot be identified with confidence, aspect_key remains NULL."""
    _, TestingSession = remediation_client
    db = TestingSession()
    prod = db.query(Product).first()

    sample_output = ReviewAnalysisOutput(
        sentiment="neutral",
        aspects=[],
        pros_cons=[
            ExtractedProCon(
                item_type="con",
                text="The retail box arrived crushed",
                aspect_key=None,
            )
        ],
    )

    class DummyProvider(LLMProvider):
        name = "mock"
        model_name = "mock"

        async def generate_structured(
            self, prompt, schema, system_prompt=None, timeout=30.0
        ):
            return StructuredOutputResult(
                sample_output, "mock", "mock", "{}", ProviderUsage(0, 0, 0, 0)
            )

        async def generate_text(self, prompt, system_prompt=None, timeout=30.0):
            return TextOutputResult("text", "mock", "mock")

        async def health_check(self):
            return True

    service = ReviewIntelligenceService(
        db, orchestrator=InferenceOrchestrator(primary_provider=DummyProvider())
    )
    analysis = await service.analyze_review(
        review_text="Retail box arrived crushed.",
        product_id=prod.id,
    )
    db.commit()

    pcs = db.query(ReviewProCon).filter(ReviewProCon.analysis_id == analysis.id).all()
    assert len(pcs) == 1
    assert pcs[0].aspect_key is None
    assert "box arrived crushed" in pcs[0].text


@pytest.mark.asyncio
async def test_11_pro_con_legacy_string_backward_compatibility(remediation_client):
    """Legacy plain string lists for pros and cons continue to work with aspect_key=None."""
    _, TestingSession = remediation_client
    db = TestingSession()
    prod = db.query(Product).first()

    sample_output = ReviewAnalysisOutput(
        sentiment="positive",
        aspects=[],
        pros=["Great display brightness", "Smooth animations"],
        cons=["No headphone jack"],
    )

    class DummyProvider(LLMProvider):
        name = "mock"
        model_name = "mock"

        async def generate_structured(
            self, prompt, schema, system_prompt=None, timeout=30.0
        ):
            return StructuredOutputResult(
                sample_output, "mock", "mock", "{}", ProviderUsage(0, 0, 0, 0)
            )

        async def generate_text(self, prompt, system_prompt=None, timeout=30.0):
            return TextOutputResult("text", "mock", "mock")

        async def health_check(self):
            return True

    service = ReviewIntelligenceService(
        db, orchestrator=InferenceOrchestrator(primary_provider=DummyProvider())
    )
    analysis = await service.analyze_review(
        review_text="Great display and animations, but no headphone jack.",
        product_id=prod.id,
    )
    db.commit()

    pcs = db.query(ReviewProCon).filter(ReviewProCon.analysis_id == analysis.id).all()
    assert len(pcs) == 3
    for p in pcs:
        assert p.aspect_key is None


# ==============================================================================
# Module 4: Attribute Evidence Provenance Tests
# ==============================================================================


def test_12_attribute_evidence_provenance_with_genuine_evidence(remediation_client):
    """Setting variant attribute backed by real source evidence preserves the evidence_id FK."""
    _, TestingSession = remediation_client
    db = TestingSession()
    var = db.query(Variant).first()

    # Create real evidence record
    evidence = Evidence(
        parameter_key="ram",
        source_type="marketplace_listing",
        trust_tier=1,
    )
    db.add(evidence)
    db.flush()

    # Attribute definition
    attr_def = AttributeRepository.get_definition_by_key(db, "ram")
    assert attr_def is not None

    vav = AttributeRepository.set_variant_value(
        db,
        variant_id=var.id,
        attribute_id=attr_def.id,
        value_numeric=Decimal(12),
        original_unit="GB",
        evidence_id=evidence.id,
    )
    db.commit()

    assert vav.evidence_id == evidence.id
    assert vav.canonical_unit == "GB"


def test_13_attribute_evidence_provenance_without_evidence_remains_null(
    remediation_client,
):
    """Static seed attributes without marketplace evidence retain evidence_id=NULL without synthetic records."""
    _, TestingSession = remediation_client
    db = TestingSession()
    var = db.query(Variant).first()

    attr_def = AttributeRepository.get_definition_by_key(db, "color")
    assert attr_def is not None

    vav = AttributeRepository.set_variant_value(
        db,
        variant_id=var.id,
        attribute_id=attr_def.id,
        value_text="Phantom Black",
        evidence_id=None,
    )
    db.commit()

    assert vav.evidence_id is None
    assert vav.value_text == "Phantom Black"
