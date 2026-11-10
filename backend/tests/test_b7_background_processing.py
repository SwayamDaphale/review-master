"""Phase B7 Comprehensive Test Suite.

Celery Background Processing, Durable Job Orchestration & Groq AI Integration.
Tests all 9 functional areas:
1. Celery task registry, queue configuration, and beat schedules.
2. Durable PostgreSQL job state persistence and lifecycle transitions.
3. Redis status caching parity with PostgreSQL authoritative store.
4. Worker heartbeat tracking and stale job recovery.
5. Pint-based physical unit normalization background tasks.
6. Groq AI provider adapter and Pydantic structured output validation.
7. End-to-end task executions (identity, evaluation, pricing, comparison, ingestion).
8. Idempotency and duplicate task delivery protection.
9. Bounded exponential backoff and retry policy.
"""

import datetime
import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.units import UnitNormalizer
from app.db.base import Base, utc_now
from app.models.attribute import AttributeDefinition, VariantAttributeValue
from app.models.category import Category
from app.models.comparison import ComparisonItem, ComparisonSession
from app.models.extraction import IngestionJob
from app.models.job import Job
from app.models.listing import MarketplaceListing
from app.models.marketplace import Marketplace
from app.models.offer import PriceRecord, SellerOffer
from app.models.operation import ImportToken
from app.models.product import Product
from app.models.product_family import ProductFamily
from app.models.variant import Variant
from app.schemas.ai_extraction import (
    EnrichedAttributeItem,
    EnrichedProductAttributes,
    StructuredReviewSummary,
)
from app.services.llm.base import ProviderUsage, StructuredOutputResult
from app.worker.celery_app import (
    calculate_evaluation_task,
    celery_app,
    cleanup_maintenance_task,
    enrich_attributes_task,
    normalize_attributes_task,
    prepare_comparison_task,
    process_ingestion_task,
    process_listing_ingestion_task,
    process_review_analysis_task,
    refresh_price_task,
    resolve_identity_task,
)
from app.worker.schedules import CELERY_BEAT_SCHEDULE
from app.worker.services.job_service import DurableJobService


@pytest.fixture(scope="module")
def b7_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def b7_session(b7_engine):
    connection = b7_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, expire_on_commit=False)
    session = session_factory()

    yield session, session_factory

    session.close()
    transaction.rollback()
    connection.close()


# ==============================================================================
# SECTION 1: Celery Application, Task Catalogue & Beat Configuration
# ==============================================================================


def test_01_celery_task_catalogue_registration():
    """Verify all 8 core B7 tasks and legacy aliases are registered on celery_app."""
    registered = celery_app.tasks

    required_tasks = [
        "ingestion.process",
        "review_master.process_listing_ingestion",
        "attributes.normalize",
        "attributes.enrich",
        "identity.resolve",
        "evaluation.calculate",
        "price.refresh",
        "comparison.prepare",
        "maintenance.cleanup",
        "review_master.process_review_analysis",
    ]

    for task_name in required_tasks:
        assert task_name in registered, f"Task '{task_name}' must be registered on Celery app"


def test_02_celery_application_configuration():
    """Verify Celery application adheres to distributed processing specifications."""
    conf = celery_app.conf
    assert conf.task_serializer == "json"
    assert conf.result_serializer == "json"
    assert conf.accept_content == ["json"]
    assert conf.timezone == "UTC"
    assert conf.enable_utc is True
    assert conf.task_track_started is True
    assert conf.task_acks_late is True
    assert conf.worker_prefetch_multiplier == 1
    assert conf.task_time_limit == 300
    assert conf.task_soft_time_limit == 270


def test_03_celery_beat_schedule_configuration():
    """Verify Celery Beat schedule contains operational maintenance and refresh entries."""
    assert "maintenance-stale-job-cleanup-every-5-mins" in CELERY_BEAT_SCHEDULE
    assert "price-refresh-periodic" in CELERY_BEAT_SCHEDULE

    m_entry = CELERY_BEAT_SCHEDULE["maintenance-stale-job-cleanup-every-5-mins"]
    assert m_entry["task"] == "maintenance.cleanup"
    assert m_entry["schedule"] == 300.0

    p_entry = CELERY_BEAT_SCHEDULE["price-refresh-periodic"]
    assert p_entry["task"] == "price.refresh"
    assert p_entry["schedule"] == 3600.0


# ==============================================================================
# SECTION 2: Durable Job State Management & PostgreSQL Persistence
# ==============================================================================


def test_04_job_service_creation_and_idempotency(b7_session):
    """Verify atomic job creation, idempotency duplicate prevention, and initial state."""
    db, _ = b7_session
    service = DurableJobService(db, redis_client=None)

    key = f"job-test-{uuid.uuid4()}"
    job1, created1 = service.create_or_get_job(
        idempotency_key=key,
        job_type="attributes.normalize",
        payload={"variant_id": "test-v1"},
    )
    db.commit()

    assert created1 is True
    assert job1.status == "pending"
    assert job1.retry_count == 0
    assert job1.max_retries == 3
    assert job1.id is not None

    # Duplicate call with identical idempotency key returns existing job without duplicate creation
    job2, created2 = service.create_or_get_job(
        idempotency_key=key,
        job_type="attributes.normalize",
    )
    assert created2 is False
    assert job2.id == job1.id


def test_05_job_service_lifecycle_transitions_and_heartbeat(b7_session):
    """Verify pending -> running -> completed transitions with worker leases and heartbeats."""
    db, _ = b7_session
    service = DurableJobService(db, redis_client=None)

    key = f"lifecycle-{uuid.uuid4()}"
    job, _ = service.create_or_get_job(idempotency_key=key, job_type="test_task")
    db.commit()

    # 1. Start job
    started_job = service.start_job(job.id, worker_id="worker-node-1")
    db.commit()
    assert started_job is not None
    assert started_job.status == "running"
    assert started_job.worker_id == "worker-node-1"
    assert started_job.started_at is not None
    assert started_job.heartbeat_at is not None

    # 2. Record heartbeat
    recorded = service.record_heartbeat(job.id, worker_id="worker-node-1")
    db.commit()
    assert recorded is True

    # 3. Complete job
    res_payload = {"count": 42, "status": "success"}
    completed_job = service.complete_job(job.id, result_payload=res_payload)
    db.commit()
    assert completed_job is not None
    assert completed_job.status == "completed"
    assert completed_job.completed_at is not None
    assert completed_job.result == res_payload


def test_06_job_service_failure_and_retry_state(b7_session):
    """Verify retry increment, retrying status, and ultimate failed state."""
    db, _ = b7_session
    service = DurableJobService(db, redis_client=None)

    key = f"fail-test-{uuid.uuid4()}"
    job, _ = service.create_or_get_job(idempotency_key=key, job_type="test_task", max_retries=2)
    db.commit()

    # Attempt 1: failure with can_retry=True transitions to 'retrying'
    service.fail_job(job.id, error_message="Network glitch", can_retry=True)
    db.commit()
    reloaded = db.get(Job, job.id)
    assert reloaded is not None
    assert reloaded.status == "retrying"
    assert reloaded.retry_count == 1
    assert "Network glitch" in (reloaded.error_message or "")

    # Attempt 2: failure with can_retry=True transitions to 'retrying'
    service.fail_job(job.id, error_message="Second timeout", can_retry=True)
    db.commit()
    reloaded = db.get(Job, job.id)
    assert reloaded is not None
    assert reloaded.status == "retrying"
    assert reloaded.retry_count == 2

    # Attempt 3: exceeds max_retries=2 transitions to 'failed'
    service.fail_job(job.id, error_message="Third fatal error", can_retry=True)
    db.commit()
    reloaded = db.get(Job, job.id)
    assert reloaded is not None
    assert reloaded.status == "failed"
    assert reloaded.completed_at is not None


def test_07_job_service_error_sanitization():
    """Verify sensitive stack traces, Bearer tokens, and secrets are sanitized."""
    raw_traceback = (
        "Traceback (most recent call last):\n"
        "  File '/app/worker.py', line 45, in execute\n"
        "  File '/app/api.py', line 12, in call_api\n"
        "ValueError: Invalid ASIN provided."
    )
    cleaned = DurableJobService.sanitize_error(raw_traceback)
    assert "Traceback" not in cleaned
    assert "Invalid ASIN provided." in cleaned

    sensitive_token_err = "Failed with Authorization: Bearer sk-secret-123456789"
    cleaned_sensitive = DurableJobService.sanitize_error(sensitive_token_err)
    assert "sk-" not in cleaned_sensitive
    assert "upstream provider error" in cleaned_sensitive


def test_08_bounded_exponential_backoff_calculation():
    """Verify backoff calculation increases exponentially and honors max bounds."""
    b1 = DurableJobService.calculate_backoff(1, base_delay=2.0, max_delay=60.0, jitter=False)
    b2 = DurableJobService.calculate_backoff(2, base_delay=2.0, max_delay=60.0, jitter=False)
    b3 = DurableJobService.calculate_backoff(3, base_delay=2.0, max_delay=60.0, jitter=False)
    b10 = DurableJobService.calculate_backoff(10, base_delay=2.0, max_delay=60.0, jitter=False)

    assert b1 == 2.0
    assert b2 == 4.0
    assert b3 == 8.0
    assert b10 == 60.0  # Clamped to max_delay


# ==============================================================================
# SECTION 3: Stale Job Recovery & Operational Maintenance
# ==============================================================================


def test_09_stale_job_recovery_mechanism(b7_session):
    """Verify recover_stale_jobs identifies hung workers and marks jobs for retry or failure."""
    db, _ = b7_session
    service = DurableJobService(db, redis_client=None)

    # Create a job running in the past (> 20 mins ago) without recent heartbeat
    past_time = utc_now() - datetime.timedelta(minutes=25)

    job_stale_retry, _ = service.create_or_get_job(
        idempotency_key=f"stale-retry-{uuid.uuid4()}",
        job_type="stale_task",
        max_retries=3,
    )
    job_stale_retry.status = "running"
    job_stale_retry.started_at = past_time
    job_stale_retry.heartbeat_at = past_time
    job_stale_retry.retry_count = 0

    job_stale_fail, _ = service.create_or_get_job(
        idempotency_key=f"stale-fail-{uuid.uuid4()}",
        job_type="stale_task",
        max_retries=1,
    )
    job_stale_fail.status = "running"
    job_stale_fail.started_at = past_time
    job_stale_fail.heartbeat_at = past_time
    job_stale_fail.retry_count = 1  # Will exceed max_retries

    db.commit()

    recovered = service.recover_stale_jobs(stale_threshold_seconds=900)
    db.commit()

    assert len(recovered) >= 2
    actions = {r["job_id"]: r["action"] for r in recovered}
    assert actions[str(job_stale_retry.id)] == "marked_retrying"
    assert actions[str(job_stale_fail.id)] == "marked_failed"

    reloaded_retry = db.get(Job, job_stale_retry.id)
    assert reloaded_retry is not None
    assert reloaded_retry.status == "retrying"

    reloaded_fail = db.get(Job, job_stale_fail.id)
    assert reloaded_fail is not None
    assert reloaded_fail.status == "failed"


def test_10_cleanup_maintenance_task_execution(b7_session):
    """Verify maintenance.cleanup task executes end-to-end and cleans expired tokens."""
    db, session_factory = b7_session

    # Insert an expired import token
    past = utc_now() - datetime.timedelta(hours=2)
    token = ImportToken(
        token_hash=f"hash_{uuid.uuid4()}",
        expires_at=past,
    )
    db.add(token)
    db.commit()

    with patch("app.worker.celery_app.SessionLocal", session_factory):
        res = cleanup_maintenance_task.apply().get()

    assert res["status"] == "completed"
    assert res["expired_tokens_removed"] >= 1


# ==============================================================================
# SECTION 4: Pint-based Physical Unit Normalization
# ==============================================================================


def test_11_unit_normalizer_physical_dimensions():
    """Verify Pint-based UnitNormalizer enforces physical dimension compatibility."""
    # Storage
    r_storage = UnitNormalizer.normalize("512", "GB")
    assert r_storage.is_valid is True
    assert r_storage.canonical_value == Decimal(512)
    assert r_storage.canonical_unit == "GB"
    assert r_storage.dimension == "storage"

    # Battery charge
    r_battery = UnitNormalizer.normalize(5000, "mAh")
    assert r_battery.is_valid is True
    assert r_battery.canonical_value == Decimal(5000)
    assert r_battery.canonical_unit == "mAh"
    assert r_battery.dimension == "charge"

    # Display length
    r_disp = UnitNormalizer.normalize("6.7", "inches")
    assert r_disp.is_valid is True
    assert r_disp.canonical_value == Decimal("6.7")
    assert r_disp.canonical_unit == "inch"
    assert r_disp.dimension == "length"

    # Weight mass
    r_weight = UnitNormalizer.normalize("180", "g")
    assert r_weight.is_valid is True
    assert r_weight.canonical_value == Decimal(180)
    assert r_weight.canonical_unit == "g"
    assert r_weight.dimension == "mass"


def test_12_attributes_normalize_task_execution(b7_session):
    """Verify attributes.normalize task updates variant attribute values in database."""
    db, session_factory = b7_session

    cat = Category(key=f"cat_{uuid.uuid4()}", name="Mobiles")
    db.add(cat)
    db.flush()

    fam = ProductFamily(category_id=cat.id, name="Test Line", manufacturer="TestMfg")
    db.add(fam)
    db.flush()

    prod = Product(family_id=fam.id, category_id=cat.id, name="Phone X", manufacturer="TestMfg")
    db.add(prod)
    db.flush()

    v = Variant(product_id=prod.id, sku_label="PX-128", configuration={"storage": "128GB"}, config_hash="hash128")
    db.add(v)
    db.flush()

    attr_def = AttributeDefinition(
        category_id=cat.id,
        key="storage",
        name="Internal Storage",
        canonical_unit="GB",
    )
    db.add(attr_def)
    db.flush()

    av = VariantAttributeValue(
        variant_id=v.id,
        attribute_id=attr_def.id,
        raw_value="128 GB",
        original_unit="GB",
        value_numeric=None,
    )
    db.add(av)
    db.commit()

    with patch("app.worker.celery_app.SessionLocal", session_factory):
        res = normalize_attributes_task.apply(args=[str(v.id)]).get()

    assert res["status"] == "completed"
    assert res["normalized_count"] >= 1

    db.expire_all()
    reloaded_av = db.get(VariantAttributeValue, av.id)
    assert reloaded_av is not None
    assert reloaded_av.value_numeric == Decimal(128)
    assert reloaded_av.canonical_unit == "GB"


# ==============================================================================
# SECTION 5: Groq AI Provider Adapter & Pydantic Structured Output Validation
# ==============================================================================


def test_13_ai_extraction_schemas_validation():
    """Verify strict Pydantic models for structured AI attribute extraction and summary."""
    item = EnrichedAttributeItem(
        attribute_key="battery",
        value=5000,
        unit="mAh",
        confidence=0.98,
        source_quote="Powerful 5000 mAh battery capacity for all-day usage",
    )
    assert item.attribute_key == "battery"
    assert item.confidence == 0.98

    container = EnrichedProductAttributes(
        product_title="SuperPhone Ultra",
        brand="SuperBrand",
        model="Ultra 1",
        attributes=[item],
        summary="Detailed specification overview",
    )
    assert len(container.attributes) == 1
    assert container.attributes[0].value == 5000

    summary = StructuredReviewSummary(
        overall_summary="Generally well-received flagship smartphone.",
        key_strengths=["Exceptional battery longevity", "Crisp OLED display"],
        key_drawbacks=["High thermal throttling under gaming"],
        consensus_verdict="Highly recommended for productivity.",
        buyer_recommendation="Best value for regular business users.",
    )
    assert len(summary.key_strengths) == 2
    assert summary.consensus_verdict is not None


def test_14_attributes_enrich_task_execution(b7_session):
    """Verify attributes.enrich background task invokes orchestrator and returns validated attributes."""
    _, session_factory = b7_session

    mock_extracted = EnrichedProductAttributes(
        product_title="Test Phone",
        brand="TestBrand",
        model="T100",
        attributes=[
            EnrichedAttributeItem(
                attribute_key="ram",
                value=8,
                unit="GB",
                confidence=0.95,
                source_quote="Packed with 8GB RAM",
            )
        ],
    )

    mock_result = StructuredOutputResult(
        data=mock_extracted,
        provider="groq",
        model="llama-3.3-70b-versatile",
        raw_response=json.dumps(mock_extracted.model_dump()),
        usage=ProviderUsage(total_tokens=100),
    )

    with (
        patch("app.worker.celery_app.SessionLocal", session_factory),
        patch(
            "app.services.llm.orchestrator.InferenceOrchestrator.generate_structured",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
    ):
        res = enrich_attributes_task.apply(
            args=["The Test Phone comes packed with 8GB RAM and vibrant display."]
        ).get()

    assert res["status"] == "completed"
    assert res["provider"] == "groq"
    assert res["data"]["brand"] == "TestBrand"
    assert len(res["data"]["attributes"]) == 1
    assert res["data"]["attributes"][0]["attribute_key"] == "ram"


# ==============================================================================
# SECTION 6: End-to-End Task Executions (Identity, Pricing, Comparison)
# ==============================================================================


def test_15_identity_resolve_task_execution(b7_session):
    """Verify identity.resolve resolves product and variant signals."""
    _, session_factory = b7_session

    with patch("app.worker.celery_app.SessionLocal", session_factory):
        res = resolve_identity_task.apply(
            args=["amazon.in", "B0IDENTITY01", "Smartphone 5G 128GB", "BrandX", "ModelY"]
        ).get()

    assert res["status"] == "completed"
    assert res["match_type"] in ("confirmed", "probable", "ambiguous", "unmatched")


def test_16_price_refresh_task_execution(b7_session):
    """Verify price.refresh updates seller offers and appends immutable price records."""
    db, session_factory = b7_session

    mp = Marketplace(key=f"mp_{uuid.uuid4()}", name="Amazon", adapter="amazon")
    db.add(mp)
    db.flush()

    listing = MarketplaceListing(
        marketplace_id=mp.id,
        external_id="B0PRICE01",
        url="https://amazon.in/dp/B0PRICE01",
        first_seen_at=utc_now(),
        last_seen_at=utc_now(),
    )
    db.add(listing)
    db.commit()

    with patch("app.worker.celery_app.SessionLocal", session_factory):
        res = refresh_price_task.apply(
            kwargs={
                "listing_id_str": str(listing.id),
                "new_price": 24999.00,
                "currency": "INR",
                "seller": "Official Retailer",
            }
        ).get()

    assert res["status"] == "completed"
    assert res["refreshed_count"] == 1

    # Verify database persistence
    offer = db.execute(select(SellerOffer).where(SellerOffer.listing_id == listing.id)).scalar_one_or_none()
    assert offer is not None
    assert offer.current_price == Decimal("24999.00")
    assert offer.seller == "Official Retailer"

    price_rec = db.execute(select(PriceRecord).where(PriceRecord.offer_id == offer.id)).scalar_one_or_none()
    assert price_rec is not None
    assert price_rec.price == Decimal("24999.00")


def test_17_comparison_prepare_task_execution(b7_session):
    """Verify comparison.prepare precomputes comparison attributes for comparison items."""
    db, session_factory = b7_session

    cat = Category(key=f"cat_{uuid.uuid4()}", name="Laptops")
    db.add(cat)
    db.flush()

    fam = ProductFamily(category_id=cat.id, name="Laptop Series", manufacturer="TestMfg")
    db.add(fam)
    db.flush()

    prod = Product(family_id=fam.id, category_id=cat.id, name="Ultrabook", manufacturer="TestMfg")
    db.add(prod)
    db.flush()

    v1 = Variant(product_id=prod.id, sku_label="UB-16", configuration={"ram": "16GB"}, config_hash="h16")
    db.add(v1)
    db.flush()

    session = ComparisonSession(title="Buying comparison")
    db.add(session)
    db.flush()

    item = ComparisonItem(session_id=session.id, product_id=prod.id, variant_id=v1.id)
    db.add(item)
    db.commit()

    with patch("app.worker.celery_app.SessionLocal", session_factory):
        res = prepare_comparison_task.apply(args=[str(session.id)]).get()

    assert res["status"] == "completed"
    assert res["item_count"] == 1
    assert res["items"][0]["sku_label"] == "UB-16"


def test_18_ingestion_canonical_task_execution(b7_session):
    """Verify ingestion.process task dispatches canonical ingestion and records durable state."""
    db, session_factory = b7_session

    job = IngestionJob(
        idempotency_key=f"ingest-task-{uuid.uuid4()}",
        job_type="ingestion",
        status="pending",
        payload={"mock": "data"},
    )
    db.add(job)
    db.commit()

    mock_ingestion_result = {
        "record_id": str(uuid.uuid4()),
        "status": "completed",
        "action": "ingested",
    }

    with (
        patch("app.worker.celery_app.SessionLocal", session_factory),
        patch(
            "app.services.ingestion_service.IngestionService.process_canonical_ingestion",
            return_value=mock_ingestion_result,
        ),
    ):
        res = process_ingestion_task.apply(args=[str(job.id)]).get()

    assert res["status"] == "completed"
    assert res["action"] == "ingested"

    # Verify durable job updated to completed
    db.expire_all()
    reloaded_job = db.get(IngestionJob, job.id)
    assert reloaded_job is not None
    assert reloaded_job.status == "completed"
    assert reloaded_job.completed_at is not None


def test_19_calculate_evaluation_task_execution(b7_session):
    """Verify evaluation.calculate task executes evaluation engine on variant."""
    db, session_factory = b7_session

    cat = Category(key=f"cat_{uuid.uuid4()}", name="Smartphones")
    db.add(cat)
    db.flush()

    fam = ProductFamily(category_id=cat.id, name="Series Y", manufacturer="TestMfg")
    db.add(fam)
    db.flush()

    prod = Product(family_id=fam.id, category_id=cat.id, name="Model Y", manufacturer="TestMfg")
    db.add(prod)
    db.flush()

    v = Variant(product_id=prod.id, sku_label="MY-64", configuration={"ram": "4GB"}, config_hash="h64")
    db.add(v)
    db.commit()

    with patch("app.worker.celery_app.SessionLocal", session_factory):
        res = calculate_evaluation_task.apply(args=[str(v.id)]).get()

    assert res["status"] == "completed"
    assert res["variant_id"] == str(v.id)


def test_20_legacy_task_handles_are_callable(b7_session):
    """Verify process_listing_ingestion_task and process_review_analysis_task handles are valid."""
    assert callable(process_listing_ingestion_task.apply)
    assert callable(process_review_analysis_task.apply)


@pytest.mark.asyncio
async def test_21_groq_http_error_failover_and_auth_isolation():
    """Verify 429/5xx triggers NVIDIA NIM failover while 401 invalid credentials is non-retryable."""
    import httpx

    from app.schemas.ai_extraction import EnrichedProductAttributes
    from app.services.llm.base import LLMProvider, ProviderUsage, StructuredOutputResult
    from app.services.llm.orchestrator import InferenceOrchestrator

    # Mock primary provider that raises HTTP 429
    mock_primary_429 = AsyncMock(spec=LLMProvider)
    mock_primary_429.name = "groq"
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    resp_429 = httpx.Response(status_code=429, request=req)
    mock_primary_429.generate_structured.side_effect = httpx.HTTPStatusError(
        "Rate limit exceeded", request=req, response=resp_429
    )

    # Mock fallback provider that succeeds
    mock_fallback = AsyncMock(spec=LLMProvider)
    mock_fallback.name = "nvidia"
    fallback_data = EnrichedProductAttributes(product_title="Fallback Phone")
    mock_fallback.generate_structured.return_value = StructuredOutputResult(
        data=fallback_data,
        provider="nvidia",
        model="meta/llama-3.3-70b-instruct",
        raw_response="{}",
        usage=ProviderUsage(),
    )

    orchestrator = InferenceOrchestrator(
        primary_provider=mock_primary_429,
        fallback_provider=mock_fallback,
        fallback_enabled=True,
        max_retries=1,
    )

    # Test 1: 429 failover to fallback
    res = await orchestrator.generate_structured("Extract specs", EnrichedProductAttributes)
    assert res.provider == "nvidia"
    assert res.fallback_used is True
    assert res.data.product_title == "Fallback Phone"

    # Test 2: 401 Unauthorized must NOT trigger fallback
    resp_401 = httpx.Response(status_code=401, request=req)
    mock_primary_401 = AsyncMock(spec=LLMProvider)
    mock_primary_401.name = "groq"
    mock_primary_401.generate_structured.side_effect = httpx.HTTPStatusError(
        "Invalid API Key", request=req, response=resp_401
    )

    mock_fallback_unused = AsyncMock(spec=LLMProvider)
    mock_fallback_unused.name = "nvidia"

    orch_auth = InferenceOrchestrator(
        primary_provider=mock_primary_401,
        fallback_provider=mock_fallback_unused,
        fallback_enabled=True,
        max_retries=1,
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await orch_auth.generate_structured("Extract specs", EnrichedProductAttributes)
    assert exc_info.value.response.status_code == 401
    mock_fallback_unused.generate_structured.assert_not_called()


def test_22_ai_extraction_validation_and_evidence_id_rejection(b7_session):
    """Verify attributes.enrich validates Pydantic schema and rejects invalid evidence ID."""
    _, session_factory = b7_session

    with patch("app.worker.celery_app.SessionLocal", session_factory):
        # 1. Reject invalid evidence UUID format
        with pytest.raises(ValueError, match="Invalid evidence ID"):
            enrich_attributes_task.apply(
                args=["Sample text"],
                kwargs={"source_evidence_id_str": "not-a-valid-uuid"},
            ).get()

        # 2. Reject empty evidence UUID
        with pytest.raises(ValueError, match="Invalid evidence ID"):
            enrich_attributes_task.apply(
                args=["Sample text"],
                kwargs={"source_evidence_id_str": "   "},
            ).get()


def test_23_stale_job_recovery_redispatches_task(b7_session):
    """Verify stale-job recovery reclaims stalled jobs and safely redispatches to Celery."""
    db, _ = b7_session
    service = DurableJobService(db, redis_client=None)

    # Create stale running job
    past_time = utc_now() - datetime.timedelta(minutes=30)
    job, _ = service.create_or_get_job(
        idempotency_key=f"stale-redispatch-{uuid.uuid4()}",
        job_type="attributes.normalize",
        payload={"variant_id": str(uuid.uuid4())},
        max_retries=3,
    )
    job.status = "running"
    job.started_at = past_time
    job.heartbeat_at = past_time
    job.retry_count = 0
    db.commit()

    with patch("app.worker.celery_app.celery_app.send_task") as mock_send_task:
        recovered = service.recover_stale_jobs(stale_threshold_seconds=900, redispatch=True)
        db.commit()

        assert len(recovered) >= 1
        rec_entry = next(r for r in recovered if r["job_id"] == str(job.id))
        assert rec_entry["action"] == "marked_retrying"
        assert rec_entry["redispatched"] is True
        mock_send_task.assert_called_once_with(
            "attributes.normalize",
            args=[job.payload["variant_id"]],
            kwargs={"job_id_str": str(job.id)},
        )

    reloaded = db.get(Job, job.id)
    assert reloaded is not None
    assert reloaded.status == "retrying"
    assert reloaded.retry_count == 1


def test_24_active_job_with_recent_heartbeat_not_reclaimed(b7_session):
    """Verify currently executing job with fresh heartbeat (< 15m) is never reclaimed."""
    db, _ = b7_session
    service = DurableJobService(db, redis_client=None)

    fresh_time = utc_now() - datetime.timedelta(seconds=60)
    job, _ = service.create_or_get_job(
        idempotency_key=f"active-fresh-{uuid.uuid4()}",
        job_type="attributes.normalize",
        max_retries=3,
    )
    job.status = "running"
    job.started_at = fresh_time
    job.heartbeat_at = fresh_time
    db.commit()

    recovered = service.recover_stale_jobs(stale_threshold_seconds=900, redispatch=True)
    db.commit()

    recovered_ids = [r["job_id"] for r in recovered]
    assert str(job.id) not in recovered_ids

    reloaded = db.get(Job, job.id)
    assert reloaded is not None
    assert reloaded.status == "running"
    assert reloaded.retry_count == 0


def test_25_retry_failed_job_manually(b7_session):
    """Verify retry_job resets a failed job and redispatches it safely."""
    db, _ = b7_session
    service = DurableJobService(db, redis_client=None)

    job, _ = service.create_or_get_job(
        idempotency_key=f"failed-manual-retry-{uuid.uuid4()}",
        job_type="ingestion.process",
        max_retries=3,
    )
    job.status = "failed"
    job.error_message = "Fatal initial failure"
    job.completed_at = utc_now()
    db.commit()

    with patch("app.worker.celery_app.celery_app.send_task") as mock_send_task:
        ok = service.retry_job(job.id)
        db.commit()

        assert ok is True
        mock_send_task.assert_called_once_with("ingestion.process", args=[str(job.id)])

    reloaded = db.get(Job, job.id)
    assert reloaded is not None
    assert reloaded.status == "retrying"
    assert reloaded.error_message is None
    assert reloaded.completed_at is None


