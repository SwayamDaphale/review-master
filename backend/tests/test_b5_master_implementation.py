"""Master test suite for Phase B5 — Catalog Intelligence, Unit Conversion, LLM Orchestration & Review Intelligence."""

import json
import uuid
from decimal import Decimal
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.permissions import RoleName
from app.core.security import create_access_token, hash_password
from app.core.units import UnitNormalizer
from app.db.base import Base
from app.db.dependencies import get_db
from app.db.seed import seed_database
from app.main import app
from app.models.category import Category
from app.models.correction import CatalogCorrection
from app.models.product import Product
from app.models.variant import Variant, compute_config_hash
from app.repositories.attribute_repository import AttributeRepository
from app.repositories.identity_repository import RoleRepository, UserRepository
from app.repositories.review_repository import ReviewRepository
from app.services.async_jobs import AsyncJobManager
from app.services.catalog_search import CatalogSearchService, SearchFilters
from app.services.catalog_validation import CatalogValidator
from app.services.llm.base import (
    LLMProvider,
    ProviderUsage,
    StructuredOutputResult,
    TextOutputResult,
)
from app.services.llm.orchestrator import InferenceOrchestrator
from app.services.llm.prompts import (
    ExtractedAspectOpinion,
    ProductReviewSummaryOutput,
    ReviewAnalysisOutput,
)
from app.services.review_intelligence import ReviewIntelligenceService

# Ensure 32-byte secret for JWT HMAC
settings.JWT_SECRET = "change-me-dev-only-32-byte-secret-key-1234"


@pytest.fixture
def b5_client():
    """Set up isolated TestClient with SQLite in-memory database."""
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


def _get_auth_token(db, role_name: str) -> str:
    """Issue a signed JWT for testing."""
    role = RoleRepository.get_by_name(db, role_name)
    user = UserRepository.create(
        db,
        email=f"{role_name}_{uuid.uuid4().hex[:6]}@test.local",
        password_hash=hash_password("Password123!"),
    )
    if role:
        RoleRepository.assign_role_to_user(db, user.id, role.id)
    db.commit()
    return create_access_token(
        {"sub": str(user.id), "email": user.email, "roles": [role_name]}
    )


# ==============================================================================
# 1. Catalog & Attribute Tests
# ==============================================================================


def test_01_distinct_variants_for_different_configs(b5_client):
    """Test that same model with 8GB/128GB and 12GB/256GB produces distinct variants."""
    _, TestingSession = b5_client
    db = TestingSession()

    cat = db.query(Category).filter(Category.key == "smartphone").first()
    product = Product(name="Pixel 9 Pro", manufacturer="Google", category_id=cat.id)
    db.add(product)
    db.flush()

    cfg1 = {"ram_gb": 8, "storage_gb": 128}
    cfg2 = {"ram_gb": 12, "storage_gb": 256}

    v1 = Variant(
        product_id=product.id,
        configuration=cfg1,
        config_hash=compute_config_hash(cfg1),
        sku_label="Pixel 9 Pro (8GB/128GB)",
    )
    v2 = Variant(
        product_id=product.id,
        configuration=cfg2,
        config_hash=compute_config_hash(cfg2),
        sku_label="Pixel 9 Pro (12GB/256GB)",
    )
    db.add_all([v1, v2])
    db.commit()

    assert v1.id != v2.id
    assert v1.config_hash != v2.config_hash
    assert db.query(Variant).filter(Variant.product_id == product.id).count() == 2
    db.close()


def test_02_unit_normalization_equivalences():
    """Verify equivalent physical measurements normalize to the exact same canonical representation."""
    # Storage
    r1 = UnitNormalizer.normalize(1, "TB", "GB")
    r2 = UnitNormalizer.normalize(1000, "GB", "GB")
    assert r1.canonical_value == Decimal(1000)
    assert r2.canonical_value == Decimal(1000)
    assert r1.canonical_value == r2.canonical_value

    # Length (display)
    r3 = UnitNormalizer.normalize(6.7, "inches", "inch")
    r4 = UnitNormalizer.normalize(17.018, "cm", "inch")
    assert r3.canonical_value == Decimal("6.70")
    assert r4.canonical_value == Decimal("6.70")

    # Battery charge
    r5 = UnitNormalizer.normalize(5000, "mAh", "mAh")
    r6 = UnitNormalizer.normalize(5, "Ah", "mAh")
    assert r5.canonical_value == Decimal(5000)
    assert r6.canonical_value == Decimal(5000)

    # Weight
    r7 = UnitNormalizer.normalize(1.5, "kg", "g")
    r8 = UnitNormalizer.normalize(1500, "g", "g")
    assert r7.canonical_value == Decimal(1500)
    assert r8.canonical_value == Decimal(1500)


def test_03_decimal_vs_binary_storage_distinction():
    """Verify decimal (GB/TB) and binary (GiB/TiB) storage units remain distinct."""
    dec_tb = UnitNormalizer.normalize(1, "TB", "GB")
    bin_tib = UnitNormalizer.normalize(1, "TiB", "GiB")

    assert dec_tb.canonical_unit == "GB"
    assert bin_tib.canonical_unit == "GiB"
    assert dec_tb.canonical_value == Decimal(1000)
    assert bin_tib.canonical_value == Decimal(1024)


def test_04_unknown_attributes_remain_null():
    """Verify unknown attributes remain null/None and are never converted to zero."""
    res = UnitNormalizer.normalize(None, "GB", "GB")
    assert res.canonical_value is None
    assert res.original_value is None
    assert res.is_valid is True


def test_05_incompatible_dimensions_rejected():
    """Verify cross-dimension conversions (e.g. storage to length) are rejected."""
    bad_res = UnitNormalizer.normalize(128, "GB", "inch")
    assert bad_res.is_valid is False
    assert "Incompatible unit dimension" in (bad_res.error or "")


def test_06_category_independent_attribute_registry(b5_client):
    """Verify new categories and attributes are data-driven without modifying schema tables."""
    _, TestingSession = b5_client
    db = TestingSession()

    # Get or create category 'laptop'
    laptop_cat = db.query(Category).filter(Category.key == "laptop").first()
    if not laptop_cat:
        laptop_cat = Category(key="laptop", name="Laptops", schema_version="1.0")
        db.add(laptop_cat)
        db.flush()

    attr_gpu = AttributeRepository.create_definition(
        db,
        key="gpu_model",
        name="Dedicated Graphics",
        category_id=laptop_cat.id,
        data_type="string",
    )
    attr_weight = AttributeRepository.create_definition(
        db,
        key="weight",
        name="Weight",
        category_id=laptop_cat.id,
        data_type="numeric",
        unit="kg",
        canonical_unit="g",
    )
    db.commit()

    assert attr_gpu.id is not None
    assert attr_weight.canonical_unit == "g"
    assert attr_weight.category_id == laptop_cat.id
    db.close()


def test_07_validation_service_enforces_rules(b5_client):
    """Verify catalog validator enforces required fields, numeric ranges, and enum values."""
    _, TestingSession = b5_client
    db = TestingSession()

    cat = db.query(Category).filter(Category.key == "smartphone").first()
    product = Product(name="Test Phone", manufacturer="Test OEM", category_id=cat.id)
    db.add(product)
    db.flush()

    variant = Variant(
        product_id=product.id,
        configuration={"ram_gb": 12},
        config_hash="test-hash-val",
        sku_label="Test Phone SKU",
    )
    db.add(variant)
    db.flush()

    # Attribute with min=1 and max=64
    ram_def = AttributeRepository.get_definition_by_key(db, "ram")
    assert ram_def is not None

    # Assign out-of-range value 128 GB (exceeds max 128 if max set to 64)
    ram_def.validation_rules = {"min": 1, "max": 64}
    db.flush()

    AttributeRepository.set_variant_value(
        db,
        variant_id=variant.id,
        attribute_id=ram_def.id,
        value_numeric=128,
        original_unit="GB",
    )
    db.commit()

    validator = CatalogValidator(db)
    report = validator.validate_variant(variant)

    assert report.is_valid is False
    assert any(i.issue_type == "range_violation" for i in report.issues)
    db.close()


def test_08_catalog_specification_search(b5_client):
    """Verify specification search supports brand, RAM bounds, and storage bounds."""
    _client, TestingSession = b5_client
    db = TestingSession()

    search_service = CatalogSearchService(db)
    # Search for Galaxy phone with RAM >= 12GB
    filters = SearchFilters(
        brand="Samsung",
        min_ram_gb=12,
        max_ram_gb=16,
    )
    items, total = search_service.search(filters)

    assert total >= 1
    assert any("Samsung Galaxy S24 Ultra" in item.product_name for item in items)
    db.close()


def test_09_administrative_corrections_audit(b5_client):
    """Verify administrative catalog corrections record before/after states and actor identity."""
    client, TestingSession = b5_client
    db = TestingSession()

    admin_token = _get_auth_token(db, RoleName.ADMIN.value)
    var = db.query(Variant).first()
    assert var is not None

    payload = {
        "target_type": "variant",
        "target_id": str(var.id),
        "field_name": "configuration",
        "before_value": var.configuration,
        "after_value": {"ram_gb": 16, "storage_gb": 512},
        "reason": "Manufacturer spec sheet revision verified.",
        "evidence_reference": "https://specs.example.com/s24u-rev2",
    }

    resp = client.post(
        "/api/v1/admin/corrections",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["reason"] == payload["reason"]
    assert data["target_id"] == str(var.id)

    # Check persistence in database
    corr = (
        db.query(CatalogCorrection)
        .filter(CatalogCorrection.id == uuid.UUID(data["id"]))
        .first()
    )
    assert corr is not None
    assert corr.field_name == "configuration"
    db.close()


# ==============================================================================
# 2. LLM Provider & Orchestration Tests
# ==============================================================================


class DummyMockProvider(LLMProvider):
    """Configurable mock provider for failover and error simulation."""

    def __init__(
        self,
        name: str,
        model: str,
        should_fail_with: Exception | None = None,
        return_data: Any = None,
    ):
        self._name = name
        self._model = model
        self.should_fail_with = should_fail_with
        self.return_data = return_data
        self.invoked = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def model_name(self) -> str:
        return self._model

    async def generate_structured(
        self, prompt, schema, system_prompt=None, timeout=30.0
    ):
        self.invoked = True
        if self.should_fail_with:
            raise self.should_fail_with
        return StructuredOutputResult(
            data=self.return_data,
            provider=self.name,
            model=self._model,
            raw_response=json.dumps(self.return_data.model_dump()),
            usage=ProviderUsage(total_tokens=100, latency_ms=12.5),
        )

    async def generate_text(self, prompt, system_prompt=None, timeout=30.0):
        self.invoked = True
        if self.should_fail_with:
            raise self.should_fail_with
        return TextOutputResult(
            text=str(self.return_data),
            provider=self.name,
            model=self._model,
            usage=ProviderUsage(total_tokens=50, latency_ms=10.0),
        )

    async def health_check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_10_orchestrator_selects_groq_primary():
    """Verify Groq is selected first when healthy."""
    sample_output = ReviewAnalysisOutput(
        sentiment="positive",
        sentiment_confidence=0.95,
        aspects=[
            ExtractedAspectOpinion(
                aspect_key="battery", polarity="positive", claim="Battery lasts 2 days."
            )
        ],
        pros=["Great battery life"],
        cons=[],
    )

    groq_mock = DummyMockProvider(
        name="groq", model="llama-3.3-70b-versatile", return_data=sample_output
    )
    nvidia_mock = DummyMockProvider(
        name="nvidia", model="meta/llama-3.3-70b-instruct", return_data=sample_output
    )

    orch = InferenceOrchestrator(
        primary_provider=groq_mock, fallback_provider=nvidia_mock
    )
    result = await orch.generate_structured(
        "Great phone, battery lasts two full days!", ReviewAnalysisOutput
    )

    assert groq_mock.invoked is True
    assert nvidia_mock.invoked is False
    assert result.provider == "groq"
    assert result.fallback_used is False
    assert result.data.sentiment == "positive"


@pytest.mark.asyncio
async def test_11_orchestrator_failover_to_nvidia_on_groq_rate_limit():
    """Verify failover to NVIDIA NIM occurs when Groq returns HTTP 429."""
    sample_output = ReviewAnalysisOutput(
        sentiment="mixed",
        sentiment_confidence=0.8,
        aspects=[
            ExtractedAspectOpinion(
                aspect_key="camera", polarity="positive", claim="Camera is sharp."
            )
        ],
        pros=["Sharp camera"],
        cons=["Slow charging"],
    )

    req = httpx.Request("POST", "https://api.groq.com")
    resp_429 = httpx.Response(status_code=429, request=req)
    groq_429_err = httpx.HTTPStatusError("Rate limited", request=req, response=resp_429)

    groq_mock = DummyMockProvider(
        name="groq", model="llama-3.3-70b-versatile", should_fail_with=groq_429_err
    )
    nvidia_mock = DummyMockProvider(
        name="nvidia", model="meta/llama-3.3-70b-instruct", return_data=sample_output
    )

    orch = InferenceOrchestrator(
        primary_provider=groq_mock,
        fallback_provider=nvidia_mock,
        fallback_enabled=True,
        max_retries=1,
    )
    result = await orch.generate_structured(
        "Camera is sharp but charging takes forever.", ReviewAnalysisOutput
    )

    assert groq_mock.invoked is True
    assert nvidia_mock.invoked is True
    assert result.provider == "nvidia"
    assert result.fallback_used is True
    assert result.data.sentiment == "mixed"


@pytest.mark.asyncio
async def test_12_non_retryable_error_does_not_failover():
    """Verify client-side errors (e.g. HTTP 400 Bad Request) do not trigger backup failover."""
    req = httpx.Request("POST", "https://api.groq.com")
    resp_400 = httpx.Response(status_code=400, request=req)
    groq_400_err = httpx.HTTPStatusError("Bad Request", request=req, response=resp_400)

    groq_mock = DummyMockProvider(
        name="groq", model="llama-3.3-70b-versatile", should_fail_with=groq_400_err
    )
    nvidia_mock = DummyMockProvider(name="nvidia", model="meta/llama-3.3-70b-instruct")

    orch = InferenceOrchestrator(
        primary_provider=groq_mock,
        fallback_provider=nvidia_mock,
        fallback_enabled=True,
        max_retries=1,
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await orch.generate_structured("Test prompt", ReviewAnalysisOutput)

    assert exc_info.value.response.status_code == 400
    assert groq_mock.invoked is True
    assert nvidia_mock.invoked is False  # Fallback was NOT attempted


@pytest.mark.asyncio
async def test_13_both_providers_fail_safely():
    """Verify failure of both providers raises clear error and does not fabricate output."""
    req = httpx.Request("POST", "https://api.example.com")
    resp_503 = httpx.Response(status_code=503, request=req)
    err_503 = httpx.HTTPStatusError(
        "Service Unavailable", request=req, response=resp_503
    )

    groq_mock = DummyMockProvider(
        name="groq", model="llama-3.3-70b-versatile", should_fail_with=err_503
    )
    nvidia_mock = DummyMockProvider(
        name="nvidia", model="meta/llama-3.3-70b-instruct", should_fail_with=err_503
    )

    orch = InferenceOrchestrator(
        primary_provider=groq_mock,
        fallback_provider=nvidia_mock,
        fallback_enabled=True,
        max_retries=1,
    )

    with pytest.raises(RuntimeError) as exc_info:
        await orch.generate_structured("Test prompt", ReviewAnalysisOutput)

    assert "All LLM inference providers failed" in str(exc_info.value)


# ==============================================================================
# 3. Review Intelligence Pipeline & Asynchronous Processing Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_14_review_intelligence_service_flow(b5_client):
    """Verify single-review analysis extracts aspects, links evidence, and persists properly."""
    _, TestingSession = b5_client
    db = TestingSession()

    prod = db.query(Product).first()
    var = db.query(Variant).filter(Variant.product_id == prod.id).first()

    sample_output = ReviewAnalysisOutput(
        sentiment="positive",
        sentiment_confidence=0.92,
        aspects=[
            ExtractedAspectOpinion(
                aspect_key="battery",
                polarity="positive",
                claim="Lasts all day easily.",
                confidence=0.95,
            ),
            ExtractedAspectOpinion(
                aspect_key="display",
                polarity="positive",
                claim="Bright outdoor visibility.",
                confidence=0.90,
            ),
        ],
        pros=["Long battery life", "Vibrant OLED display"],
        cons=["Slow wired charging"],
    )
    mock_provider = DummyMockProvider(
        name="groq", model="llama-3.3-70b-versatile", return_data=sample_output
    )
    orch = InferenceOrchestrator(primary_provider=mock_provider)

    service = ReviewIntelligenceService(db, orchestrator=orch)
    analysis = await service.analyze_review(
        review_text="The battery lasts all day and the display is super bright outdoors. Only wish charging was faster.",
        product_id=prod.id,
        variant_id=var.id,
        review_source_id="amazon_rev_12345",
    )
    db.commit()

    assert analysis.id is not None
    assert analysis.sentiment == "positive"
    assert len(analysis.aspect_opinions) == 2
    assert len(analysis.pros_cons) == 3
    assert any(
        p.item_type == "pro" and "battery" in p.text.lower() for p in analysis.pros_cons
    )
    assert any(
        p.item_type == "con" and "charging" in p.text.lower()
        for p in analysis.pros_cons
    )
    db.close()


@pytest.mark.asyncio
async def test_15_review_summary_aggregation(b5_client):
    """Verify aggregated review summaries synthesize consensus and retain contradictory opinions."""
    _, TestingSession = b5_client
    db = TestingSession()

    prod = db.query(Product).first()

    # Pre-seed 2 analyses: one praising battery, one complaining about battery
    ReviewRepository.create_analysis(
        db,
        product_id=prod.id,
        review_text="Amazing battery life!",
        sentiment="positive",
        provider="groq",
        model="llama-3.3-70b-versatile",
        aspects=[
            {
                "aspect_key": "battery",
                "polarity": "positive",
                "claim": "Battery is outstanding.",
                "confidence": 0.9,
            }
        ],
        pros=["Outstanding battery"],
    )
    ReviewRepository.create_analysis(
        db,
        product_id=prod.id,
        review_text="Battery drains too quickly under heavy load.",
        sentiment="negative",
        provider="groq",
        model="llama-3.3-70b-versatile",
        aspects=[
            {
                "aspect_key": "battery",
                "polarity": "negative",
                "claim": "High battery drain under load.",
                "confidence": 0.85,
            }
        ],
        cons=["Drains fast under load"],
    )
    db.commit()

    summary_output = ProductReviewSummaryOutput(
        summary_text="Users report generally positive impressions, but battery life feedback is mixed: excellent for daily light use, but noticeable drain under gaming loads.",
        aspect_summaries={
            "battery": "Mixed opinions: long idle endurance but higher drain under load."
        },
        key_pros=["Long idle endurance"],
        key_cons=["Battery drain under heavy load"],
        confidence=0.88,
    )
    mock_provider = DummyMockProvider(
        name="groq", model="llama-3.3-70b-versatile", return_data=summary_output
    )
    orch = InferenceOrchestrator(primary_provider=mock_provider)

    service = ReviewIntelligenceService(db, orchestrator=orch)
    summary = await service.summarize_product_reviews(product_id=prod.id)
    db.commit()

    assert summary is not None
    assert summary.total_reviews_analyzed >= 2
    assert summary.sentiment_distribution["positive"] >= 1
    assert summary.sentiment_distribution["negative"] >= 1
    assert "battery" in summary.aspect_summaries
    db.close()


def test_16_async_job_idempotency(b5_client):
    """Verify async job creation is idempotent and prevents duplicate job execution."""
    _, TestingSession = b5_client
    db = TestingSession()

    manager = AsyncJobManager(db)
    idem_key = "review_job_12345678"

    job1, created1 = manager.create_or_get_job(
        idempotency_key=idem_key, job_type="review_analysis"
    )
    db.commit()

    job2, created2 = manager.create_or_get_job(
        idempotency_key=idem_key, job_type="review_analysis"
    )
    db.commit()

    assert created1 is True
    assert created2 is False
    assert job1.id == job2.id
    db.close()
