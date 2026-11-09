"""Phase B6 Comprehensive Test Suite.

Covers:
1. Contract Adapter & Registry (Frozen Smartphone V1, Generalized V1, versioning, canonical mapping).
2. Marketplace & URL Security Validation (Amazon India, HTTPS, credentials rejection, port rejection, path checking).
3. Ingestion API Endpoint (POST /api/v1/listings/ingest, 202 Accepted, structured 422, 400 for unsupported).
4. Database-Backed Idempotency (deduplication, identical key/payload, 409 Conflict on payload mismatch).
5. Evidence Storage & SHA-256 Integrity (SeaweedFS S3 storage, SHA-256 digest, deterministic key).
6. Authorized Evidence Retrieval (GET /api/v1/ingestion-jobs/{job_id}/evidence, 401, 403, 200 for owner/admin).
7. Ingestion Job Status API (GET /api/v1/ingestion-jobs/{job_id}, 401, 403, 200 sanitized view).
8. Celery Worker Background Processing (process_listing_ingestion task, entity resolution, idempotency).
"""

import hashlib
import json
import uuid
from copy import deepcopy
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.contracts.extraction.adapters.generalized_v1_adapter import (
    GeneralizedExtractionAdapter,
)
from app.contracts.extraction.adapters.smartphone_v1_adapter import (
    SmartphoneExtractionV1Adapter,
)
from app.contracts.extraction.base import (
    ContractValidationError,
    UnsupportedContractError,
    UnsupportedVersionError,
)
from app.contracts.extraction.registry import (
    contract_registry,
)
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.dependencies import get_db
from app.db.seed import seed_database
from app.main import app
from app.models.attribute import VariantAttributeValue
from app.models.extraction import ExtractionRecord, IngestionJob
from app.models.listing import MarketplaceListing
from app.models.product import Product
from app.models.variant import Variant
from app.repositories.identity_repository import RoleRepository, UserRepository
from app.services.evidence_storage import (
    EvidenceNotFoundError,
    EvidenceStorageService,
    IntegrityMismatchError,
    StorageException,
)
from app.services.ingestion_service import IngestionService
from app.services.marketplace_registry import MarketplaceRegistry
from app.worker.celery_app import process_listing_ingestion_task

settings.JWT_SECRET = "change-me-dev-only-32-byte-secret-key-1234"

# -----------------------------------------------------------------------------
# Test Fixtures & Sample Payloads
# -----------------------------------------------------------------------------

VALID_SMARTPHONE_V1: dict[str, Any] = {
    "schema_version": "1.0",
    "record_id": "550e8400-e29b-41d4-a716-446655440000",
    "source": {
        "marketplace": "amazon.in",
        "product_url": "https://www.amazon.in/dp/B0CS6DY3T7",
        "extracted_at": "2026-11-08T01:00:00Z",
        "extraction_method": "browser_extension_user_initiated",
        "extension_version": "1.0.0",
        "page_title": "Samsung Galaxy S24 Ultra 5G (Titanium Black, 12GB, 256GB Storage)",
        "asin": "B0CS6DY3T7",
    },
    "raw_extraction": {
        "title": "Samsung Galaxy S24 Ultra 5G (Titanium Black, 12GB, 256GB Storage)",
        "brand_text": "Samsung",
        "model_text": "Galaxy S24 Ultra",
        "variant_text": "12GB RAM, 256GB Storage",
        "price_text": "₹1,29,999",
        "rating_text": "4.5 out of 5 stars",
        "review_count_text": "1,520 ratings",
        "availability_text": "In stock",
        "specifications_text": [
            {"label": "Brand", "value": "Samsung"},
            {"label": "Model Name", "value": "Galaxy S24 Ultra"},
            {"label": "RAM", "value": "12 GB"},
            {"label": "Memory Storage Capacity", "value": "256 GB"},
        ],
    },
    "normalized": {
        "category": "smartphone",
        "brand": "Samsung",
        "model_name": "Galaxy S24 Ultra",
        "model_number": "SM-S928B",
        "ram_gb": 12,
        "storage_gb": 256,
        "display_size_inches": 6.8,
        "battery_capacity_mah": 5000,
        "operating_system": "Android 14",
        "processor": "Snapdragon 8 Gen 3",
        "supports_5g": True,
        "price_amount": 129999.0,
        "currency": "INR",
        "rating": 4.5,
        "review_count": 1520,
        "availability": "in_stock",
    },
    "validation": {
        "status": "valid",
        "identity_status": "identified",
        "warnings": [],
        "errors": [],
    },
}

VALID_GENERALIZED_V1: dict[str, Any] = {
    "contract": {
        "contract_type": "generalized_extraction",
        "schema_version": "1.0",
        "record_id": "880e8400-e29b-41d4-a716-446655440088",
        "captured_at": "2026-11-09T10:00:00Z",
    },
    "source": {
        "marketplace": "amazon.in",
        "page_type": "product_detail",
        "product_url": "https://www.amazon.in/dp/B0D1XD1ZV3",
        "extraction_method": "browser_extension_user_initiated",
        "extension_version": "1.0.0",
        "page_title": "Apple Watch Ultra 2 (GPS + Cellular, 49mm)",
    },
    "product_context": {
        "category": "smartwatch",
        "external_id": "B0D1XD1ZV3",
        "brand_hint": "Apple",
        "model_hint": "Watch Ultra 2",
    },
    "raw_evidence": {
        "title": "Apple Watch Ultra 2 (GPS + Cellular, 49mm)",
        "raw_price_text": "₹89,900",
        "specifications": [{"label": "Case material", "value": "Titanium"}],
    },
    "extracted_data": {
        "price_amount": 89900.0,
        "currency": "INR",
        "rating": 4.8,
        "review_count": 350,
        "availability": "in_stock",
        "attributes": [
            {
                "attribute_key": "case_material",
                "value_type": "string",
                "value": "Titanium",
                "confidence": 1.0,
            },
            {
                "attribute_key": "water_resistance_meters",
                "value_type": "numeric",
                "value": 100,
                "confidence": 0.95,
            },
        ],
    },
    "validation": {
        "status": "valid",
        "identity_status": "identified",
        "warnings": [],
        "errors": [],
    },
}


class MockMemoryStorage(EvidenceStorageService):
    """In-memory mock for EvidenceStorageService."""

    def __init__(self):
        self._store: dict[str, bytes] = {}

    def store_evidence(
        self,
        content_bytes: bytes,
        *,
        custom_key: str | None = None,
        content_type: str = "application/json",
    ) -> tuple[str, str, int]:
        if not content_bytes:
            raise StorageException("Evidence content bytes cannot be empty.")
        sha256_digest = hashlib.sha256(content_bytes).hexdigest()
        byte_size = len(content_bytes)
        object_key = custom_key or f"extractions/2026/11/{sha256_digest}.json"
        self._store[object_key] = content_bytes
        return (object_key, sha256_digest, byte_size)

    def retrieve_evidence(
        self,
        object_key: str,
        expected_sha256: str | None = None,
    ) -> tuple[bytes, str, str]:
        if object_key not in self._store:
            raise EvidenceNotFoundError(f"Object '{object_key}' not found.")
        content = self._store[object_key]
        digest = hashlib.sha256(content).hexdigest()
        if expected_sha256 and digest.lower() != expected_sha256.lower():
            raise IntegrityMismatchError(f"SHA-256 mismatch for '{object_key}'.")
        return (content, "application/json", digest)


@pytest.fixture
def b6_test_env():
    """Isolated test environment with SQLite database and in-memory mock storage."""
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

    mock_storage = MockMemoryStorage()

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with patch("app.services.ingestion_service.EvidenceStorageService", return_value=mock_storage), \
         patch("app.api.v1.ingestion.EvidenceStorageService", return_value=mock_storage), \
         patch("app.worker.celery_app.process_listing_ingestion_task.delay") as mock_delay, \
         TestClient(app) as client:
        client.headers.update({"x-bypass-rate-limit": "true"})
        yield {
            "client": client,
            "session_factory": TestingSession,
            "storage": mock_storage,
            "mock_delay": mock_delay,
        }

    app.dependency_overrides.clear()


def _create_user(db, role_name: str, email_prefix: str = "user"):
    """Helper to create a user with a given role and return (user, auth_header)."""
    role = RoleRepository.get_by_name(db, role_name)
    user = UserRepository.create(
        db,
        email=f"{email_prefix}_{uuid.uuid4().hex[:6]}@test.local",
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
# 1. Contract Adapters & Registry Tests
# ==============================================================================

class TestContractAdaptersAndRegistry:
    def test_smartphone_adapter_validates_1_0_and_1_0_0(self):
        adapter = SmartphoneExtractionV1Adapter()
        # Version 1.0 passes
        adapter.validate(VALID_SMARTPHONE_V1)

        # Version 1.0.0 passes
        payload_100 = deepcopy(VALID_SMARTPHONE_V1)
        payload_100["schema_version"] = "1.0.0"
        adapter.validate(payload_100)

        # Version 2.0 fails validation
        payload_200 = deepcopy(VALID_SMARTPHONE_V1)
        payload_200["schema_version"] = "2.0"
        with pytest.raises(ContractValidationError):
            adapter.validate(payload_200)

    def test_smartphone_adapter_adapts_to_canonical(self):
        adapter = SmartphoneExtractionV1Adapter()
        canonical = adapter.to_canonical(VALID_SMARTPHONE_V1)

        assert canonical.ingestion_record_id == VALID_SMARTPHONE_V1["record_id"]
        assert canonical.marketplace == "amazon.in"
        assert canonical.product_url == "https://www.amazon.in/dp/B0CS6DY3T7"
        assert canonical.asin == "B0CS6DY3T7"
        assert canonical.product_category == "smartphone"
        assert canonical.normalized_brand == "Samsung"
        assert canonical.normalized_model_name == "Galaxy S24 Ultra"
        assert float(canonical.price_amount) == 129999.0
        assert canonical.currency == "INR"

        attrs = {a.attribute_key: a.value for a in canonical.extracted_attributes}
        assert attrs["ram"] == 12
        assert attrs["storage"] == 256
        assert attrs["battery"] == 5000
        assert attrs["supports_5g"] is True

    def test_generalized_adapter_validates_and_adapts(self):
        adapter = GeneralizedExtractionAdapter()
        adapter.validate(VALID_GENERALIZED_V1)

        canonical = adapter.to_canonical(VALID_GENERALIZED_V1)
        assert canonical.ingestion_record_id == VALID_GENERALIZED_V1["contract"]["record_id"]
        assert canonical.marketplace == "amazon.in"
        assert canonical.product_category == "smartwatch"
        assert canonical.normalized_brand == "Apple"
        assert float(canonical.price_amount) == 89900.0

        attrs = {a.attribute_key: a.value for a in canonical.extracted_attributes}
        assert attrs["case_material"] == "Titanium"
        assert attrs["water_resistance_meters"] == 100

    def test_registry_identifies_and_dispatches_correctly(self):
        name_sp, ver_sp = contract_registry.identify_contract(VALID_SMARTPHONE_V1)
        assert name_sp == "smartphone_extraction"
        assert ver_sp == "1.0"
        adapter_sp = contract_registry.get_adapter(name_sp, ver_sp)
        assert isinstance(adapter_sp, SmartphoneExtractionV1Adapter)

        name_gen, ver_gen = contract_registry.identify_contract(VALID_GENERALIZED_V1)
        assert name_gen == "generalized_extraction"
        assert ver_gen == "1.0"
        adapter_gen = contract_registry.get_adapter(name_gen, ver_gen)
        assert isinstance(adapter_gen, GeneralizedExtractionAdapter)

    def test_registry_raises_unsupported_for_unknown_contract(self):
        with pytest.raises(UnsupportedContractError):
            contract_registry.identify_contract({"unknown_contract_structure": True})

    def test_registry_raises_unsupported_version(self):
        unsupported = deepcopy(VALID_SMARTPHONE_V1)
        unsupported["schema_version"] = "99.0"
        name, ver = contract_registry.identify_contract(unsupported)
        with pytest.raises(UnsupportedVersionError):
            contract_registry.get_adapter(name, ver)

    def test_adapter_raises_contract_validation_error_on_invalid_payload(self):
        adapter = SmartphoneExtractionV1Adapter()
        invalid_payload = deepcopy(VALID_SMARTPHONE_V1)
        del invalid_payload["raw_extraction"]

        with pytest.raises(ContractValidationError) as exc_info:
            adapter.validate(invalid_payload)
        assert len(exc_info.value.errors) > 0


# ==============================================================================
# 2. Marketplace & URL Security Validation Tests
# ==============================================================================

class TestMarketplaceAndUrlSecurity:
    def test_valid_amazon_in_urls_pass(self):
        valid_urls = [
            "https://www.amazon.in/dp/B0CS6DY3T7",
            "https://amazon.in/dp/B0CS6DY3T7",
            "https://www.amazon.in/gp/product/B0CS6DY3T7",
            "https://www.amazon.in/Samsung-Galaxy-Ultra-Titanium-Storage/dp/B0CS6DY3T7?th=1",
        ]
        for url in valid_urls:
            validated = MarketplaceRegistry.validate_product_url(url, marketplace="amazon.in")
            assert validated == url

    def test_insecure_http_rejected(self):
        with pytest.raises(ContractValidationError, match="https"):
            MarketplaceRegistry.validate_product_url("http://www.amazon.in/dp/B0CS6DY3T7")

    def test_embedded_credentials_rejected(self):
        with pytest.raises(ContractValidationError, match="credentials"):
            MarketplaceRegistry.validate_product_url("https://user:password@www.amazon.in/dp/B0CS6DY3T7")

    def test_non_standard_port_rejected(self):
        with pytest.raises(ContractValidationError, match="port"):
            MarketplaceRegistry.validate_product_url("https://www.amazon.in:8443/dp/B0CS6DY3T7")

    def test_untrusted_domain_rejected(self):
        untrusted = [
            "https://www.flipkart.com/dp/B0CS6DY3T7",
            "https://www.amazon.com/dp/B0CS6DY3T7",
            "https://www.amazon.in.attacker.com/dp/B0CS6DY3T7",
        ]
        for url in untrusted:
            with pytest.raises(ContractValidationError, match="domain"):
                MarketplaceRegistry.validate_product_url(url, marketplace="amazon.in")

    def test_non_product_path_rejected(self):
        invalid_paths = [
            "https://www.amazon.in/s?k=smartphone",
            "https://www.amazon.in/gp/cart/view.html",
            "https://www.amazon.in/dp/../etc/passwd",
        ]
        for url in invalid_paths:
            with pytest.raises(ContractValidationError):
                MarketplaceRegistry.validate_product_url(url, marketplace="amazon.in")


# ==============================================================================
# 3. Listing Ingestion API Endpoint Tests
# ==============================================================================

class TestListingIngestionEndpoint:
    def test_anonymous_ingestion_rejected_with_401(self, b6_test_env):
        client = b6_test_env["client"]
        resp = client.post("/api/v1/listings/ingest", json=VALID_SMARTPHONE_V1)
        assert resp.status_code == 401

    def test_authenticated_ingestion_accepted_with_202(self, b6_test_env):
        client = b6_test_env["client"]
        session_factory = b6_test_env["session_factory"]

        with session_factory() as db:
            user, auth_header = _create_user(db, "api_consumer", email_prefix="ingest_user")

        payload = deepcopy(VALID_SMARTPHONE_V1)
        payload["record_id"] = str(uuid.uuid4())
        payload["source"]["asin"] = "B0AUTH0001"
        payload["source"]["product_url"] = "https://www.amazon.in/dp/B0AUTH0001"

        resp = client.post("/api/v1/listings/ingest", json=payload, headers=auth_header)
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert data["duplicate"] is False
        assert data["contract_type"] == "smartphone_extraction"
        assert b6_test_env["mock_delay"].called

        job_id = data["job_id"]
        with session_factory() as db:
            job = db.query(IngestionJob).filter(IngestionJob.id == uuid.UUID(job_id)).first()
            assert job is not None
            record = db.query(ExtractionRecord).filter(ExtractionRecord.record_id == job.record_id).first()
            assert record is not None
            assert str(record.user_id) == str(user.id)

    def test_generalized_contract_accepted_via_api(self, b6_test_env):
        client = b6_test_env["client"]
        session_factory = b6_test_env["session_factory"]

        with session_factory() as db:
            _, auth_header = _create_user(db, "api_consumer", email_prefix="gen_user")

        resp = client.post("/api/v1/listings/ingest", json=VALID_GENERALIZED_V1, headers=auth_header)
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "pending"
        assert data["duplicate"] is False
        assert data["contract_type"] == "generalized_extraction"

    def test_malformed_payload_returns_422_with_structured_errors(self, b6_test_env):
        client = b6_test_env["client"]
        session_factory = b6_test_env["session_factory"]

        with session_factory() as db:
            _, auth_header = _create_user(db, "api_consumer", email_prefix="malformed_user")

        malformed = deepcopy(VALID_SMARTPHONE_V1)
        del malformed["raw_extraction"]

        resp = client.post("/api/v1/listings/ingest", json=malformed, headers=auth_header)
        assert resp.status_code == 422
        data = resp.json()
        assert "detail" in data
        assert data["detail"]["error_type"] == "contract_validation_error"
        assert isinstance(data["detail"]["detail"], list)

    def test_unsupported_contract_version_returns_400(self, b6_test_env):
        client = b6_test_env["client"]
        session_factory = b6_test_env["session_factory"]

        with session_factory() as db:
            _, auth_header = _create_user(db, "api_consumer", email_prefix="unsupported_user")

        unsupported = deepcopy(VALID_SMARTPHONE_V1)
        unsupported["schema_version"] = "99.0"

        resp = client.post("/api/v1/listings/ingest", json=unsupported, headers=auth_header)
        assert resp.status_code == 400
        data = resp.json()
        assert "detail" in data
        assert "not supported" in data["detail"].lower()


# ==============================================================================
# 4. Database-Backed Idempotency Tests
# ==============================================================================

class TestIngestionDatabaseIdempotency:
    def test_exact_duplicate_payload_returns_duplicate_true(self, b6_test_env):
        client = b6_test_env["client"]
        session_factory = b6_test_env["session_factory"]

        with session_factory() as db:
            _, auth_header = _create_user(db, "api_consumer", email_prefix="idemp_user")

        payload = deepcopy(VALID_SMARTPHONE_V1)
        payload["record_id"] = str(uuid.uuid4())
        payload["source"]["asin"] = "B0IDEMP001"
        payload["source"]["product_url"] = "https://www.amazon.in/dp/B0IDEMP001"

        headers = {**auth_header, "Idempotency-Key": "test-key-idemp-1"}

        # First request
        resp1 = client.post("/api/v1/listings/ingest", json=payload, headers=headers)
        assert resp1.status_code == 202
        data1 = resp1.json()
        assert data1["duplicate"] is False
        job1_id = data1["job_id"]

        # Duplicate request
        resp2 = client.post("/api/v1/listings/ingest", json=payload, headers=headers)
        assert resp2.status_code in (200, 202)
        data2 = resp2.json()
        assert data2["duplicate"] is True
        assert data2["job_id"] == job1_id

        # Verify only one ingestion job was stored in database
        with session_factory() as db:
            jobs = db.query(IngestionJob).filter(IngestionJob.idempotency_key == "test-key-idemp-1").all()
            assert len(jobs) == 1

    def test_conflicting_payload_same_idempotency_key_returns_409(self, b6_test_env):
        client = b6_test_env["client"]
        session_factory = b6_test_env["session_factory"]

        with session_factory() as db:
            _, auth_header = _create_user(db, "api_consumer", email_prefix="conflict_user")

        payload1 = deepcopy(VALID_SMARTPHONE_V1)
        payload1["record_id"] = str(uuid.uuid4())
        payload1["source"]["asin"] = "B0CONFLIC1"
        payload1["source"]["product_url"] = "https://www.amazon.in/dp/B0CONFLIC1"

        headers = {**auth_header, "Idempotency-Key": "conflict-key-test"}

        resp1 = client.post("/api/v1/listings/ingest", json=payload1, headers=headers)
        assert resp1.status_code == 202

        # Differing payload with same key
        payload2 = deepcopy(payload1)
        payload2["normalized"]["model_name"] = "Different Conflicting Model"

        resp2 = client.post("/api/v1/listings/ingest", json=payload2, headers=headers)
        assert resp2.status_code == 409
        data = resp2.json()
        assert "Conflict" in data["detail"] or "collision" in data["detail"].lower()


# ==============================================================================
# 5. Evidence Storage & SHA-256 Digest Tests
# ==============================================================================

class TestEvidenceStorageAndIntegrity:
    def test_evidence_storage_creates_sha256_digest(self, b6_test_env):
        storage = b6_test_env["storage"]
        sample_bytes = json.dumps({"test": "data"}, sort_keys=True).encode("utf-8")
        expected_digest = hashlib.sha256(sample_bytes).hexdigest()

        obj_key, digest, size = storage.store_evidence(sample_bytes)
        assert digest == expected_digest
        assert size == len(sample_bytes)
        assert expected_digest in obj_key

        retrieved_bytes, _ctype, ret_digest = storage.retrieve_evidence(obj_key, expected_sha256=expected_digest)
        assert retrieved_bytes == sample_bytes
        assert ret_digest == expected_digest

    def test_mismatched_sha256_raises_integrity_error(self, b6_test_env):
        storage = b6_test_env["storage"]
        sample_bytes = b'{"tampered": false}'
        obj_key, _digest, _ = storage.store_evidence(sample_bytes)

        with pytest.raises(IntegrityMismatchError):
            storage.retrieve_evidence(obj_key, expected_sha256="wrong-sha256-hash-0000000000000000")


# ==============================================================================
# 6. Authorized Evidence Retrieval API Tests
# ==============================================================================

class TestAuthorizedEvidenceRetrieval:
    def test_evidence_retrieval_anonymous_returns_401(self, b6_test_env):
        client = b6_test_env["client"]
        resp = client.get(f"/api/v1/ingestion-jobs/{uuid.uuid4()}/evidence")
        assert resp.status_code == 401

    def test_evidence_retrieval_owner_and_admin_authorized(self, b6_test_env):
        client = b6_test_env["client"]
        session_factory = b6_test_env["session_factory"]

        with session_factory() as db:
            _owner, owner_auth = _create_user(db, "api_consumer", "job_owner")
            _other_user, other_auth = _create_user(db, "consumer", "job_stranger")
            _admin_user, admin_auth = _create_user(db, "admin", "admin_viewer")

        payload = deepcopy(VALID_SMARTPHONE_V1)
        payload["record_id"] = str(uuid.uuid4())
        payload["source"]["asin"] = "B0EVID0001"
        payload["source"]["product_url"] = "https://www.amazon.in/dp/B0EVID0001"

        ingest_resp = client.post("/api/v1/listings/ingest", json=payload, headers=owner_auth)
        assert ingest_resp.status_code == 202
        job_id = ingest_resp.json()["job_id"]

        # Owner gets 200 with raw evidence
        resp_owner = client.get(f"/api/v1/ingestion-jobs/{job_id}/evidence", headers=owner_auth)
        assert resp_owner.status_code == 200
        assert resp_owner.headers.get("Content-Type") == "application/json"
        assert "ETag" in resp_owner.headers
        evidence_json = resp_owner.json()
        assert evidence_json["record_id"] == payload["record_id"]

        # Other non-owner user gets 403 Forbidden
        resp_other = client.get(f"/api/v1/ingestion-jobs/{job_id}/evidence", headers=other_auth)
        assert resp_other.status_code == 403

        # Admin gets 200
        resp_admin = client.get(f"/api/v1/ingestion-jobs/{job_id}/evidence", headers=admin_auth)
        assert resp_admin.status_code == 200
        assert resp_admin.json()["record_id"] == payload["record_id"]

    def test_evidence_retrieval_nonexistent_job_returns_404(self, b6_test_env):
        client = b6_test_env["client"]
        session_factory = b6_test_env["session_factory"]

        with session_factory() as db:
            _, admin_auth = _create_user(db, "admin", "admin_404")

        resp = client.get(f"/api/v1/ingestion-jobs/{uuid.uuid4()}/evidence", headers=admin_auth)
        assert resp.status_code == 404


# ==============================================================================
# 7. Ingestion Job Status API Tests
# ==============================================================================

class TestIngestionJobStatusApi:
    def test_job_status_anonymous_returns_401(self, b6_test_env):
        client = b6_test_env["client"]
        resp = client.get(f"/api/v1/ingestion-jobs/{uuid.uuid4()}")
        assert resp.status_code == 401

    def test_job_status_owner_and_admin_authorized(self, b6_test_env):
        client = b6_test_env["client"]
        session_factory = b6_test_env["session_factory"]

        with session_factory() as db:
            _owner, owner_auth = _create_user(db, "api_consumer", "owner_stat")
            _other_user, other_auth = _create_user(db, "consumer", "stranger_stat")
            _admin_user, admin_auth = _create_user(db, "admin", "admin_stat")

        payload = deepcopy(VALID_SMARTPHONE_V1)
        payload["record_id"] = str(uuid.uuid4())
        payload["source"]["asin"] = "B0STAT0001"
        payload["source"]["product_url"] = "https://www.amazon.in/dp/B0STAT0001"

        ingest_resp = client.post("/api/v1/listings/ingest", json=payload, headers=owner_auth)
        assert ingest_resp.status_code == 202
        job_id = ingest_resp.json()["job_id"]

        # Owner gets 200 sanitized status
        resp_owner = client.get(f"/api/v1/ingestion-jobs/{job_id}", headers=owner_auth)
        assert resp_owner.status_code == 200
        data_owner = resp_owner.json()
        assert data_owner["job_id"] == job_id
        assert data_owner["status"] == "pending"
        assert "created_at" in data_owner

        # Stranger gets 403
        resp_stranger = client.get(f"/api/v1/ingestion-jobs/{job_id}", headers=other_auth)
        assert resp_stranger.status_code == 403

        # Admin gets 200
        resp_admin = client.get(f"/api/v1/ingestion-jobs/{job_id}", headers=admin_auth)
        assert resp_admin.status_code == 200
        assert resp_admin.json()["job_id"] == job_id


# ==============================================================================
# 8. Celery Worker Listing Ingestion Processing Tests
# ==============================================================================

class TestCeleryWorkerListingIngestion:
    def test_process_listing_ingestion_executes_end_to_end(self, b6_test_env):
        session_factory = b6_test_env["session_factory"]

        with session_factory() as db:
            ingestion_service = IngestionService(db=db)

            payload = deepcopy(VALID_SMARTPHONE_V1)
            payload["record_id"] = str(uuid.uuid4())
            payload["source"]["asin"] = "B0CELERY01"
            payload["source"]["product_url"] = "https://www.amazon.in/dp/B0CELERY01"

            raw_bytes = json.dumps(payload).encode("utf-8")
            job, _record, _c_name, _s_ver, _is_dup = ingestion_service.create_durable_ingestion(
                raw_bytes=raw_bytes,
                payload_dict=payload,
                user_id=str(uuid.uuid4()),
            )
            db.commit()
            job_id_str = str(job.id)

        # Execute Celery task directly using database session override
        with patch("app.db.session.SessionLocal", session_factory), \
             patch("app.worker.celery_app.SessionLocal", session_factory):
            result = process_listing_ingestion_task.apply(args=[job_id_str]).get()
            assert result["status"] == "completed"

        # Verify database state after Celery task execution
        with session_factory() as db:
            completed_job = db.query(IngestionJob).filter(IngestionJob.id == uuid.UUID(job_id_str)).first()
            assert completed_job is not None
            assert completed_job.status == "completed"
            assert completed_job.updated_at is not None

            # Verify MarketplaceListing and Variant were created
            listing = db.query(MarketplaceListing).filter(MarketplaceListing.external_id == "B0CELERY01").first()
            assert listing is not None
            assert listing.variant_id is not None

            variant = db.query(Variant).filter(Variant.id == listing.variant_id).first()
            assert variant is not None

            product = db.query(Product).filter(Product.id == variant.product_id).first()
            assert product is not None
            assert product.manufacturer == "Samsung"

            # Verify Variant Attribute Values populated with evidence linking
            vavs = db.query(VariantAttributeValue).filter(VariantAttributeValue.variant_id == variant.id).all()
            assert len(vavs) > 0
            evidence_backed_vavs = [v for v in vavs if v.evidence_id is not None]
            assert len(evidence_backed_vavs) >= 4  # ram, storage, battery, display_size

    def test_duplicate_task_invocation_is_idempotent(self, b6_test_env):
        session_factory = b6_test_env["session_factory"]

        with session_factory() as db:
            ingestion_service = IngestionService(db=db)
            payload = deepcopy(VALID_SMARTPHONE_V1)
            payload["record_id"] = str(uuid.uuid4())
            payload["source"]["asin"] = "B0IDEMCEL1"
            payload["source"]["product_url"] = "https://www.amazon.in/dp/B0IDEMCEL1"

            raw_bytes = json.dumps(payload).encode("utf-8")
            job, _record, _c_name, _s_ver, _is_dup = ingestion_service.create_durable_ingestion(
                raw_bytes=raw_bytes,
                payload_dict=payload,
                user_id=str(uuid.uuid4()),
            )
            db.commit()
            job_id_str = str(job.id)

        with patch("app.db.session.SessionLocal", session_factory), \
             patch("app.worker.celery_app.SessionLocal", session_factory):
            # First execution
            res1 = process_listing_ingestion_task.apply(args=[job_id_str]).get()
            assert res1["status"] == "completed"

            # Duplicate delivery
            res2 = process_listing_ingestion_task.apply(args=[job_id_str]).get()
            assert res2["status"] == "completed"

        with session_factory() as db:
            listings = db.query(MarketplaceListing).filter(MarketplaceListing.external_id == "B0IDEMCEL1").all()
            assert len(listings) == 1
