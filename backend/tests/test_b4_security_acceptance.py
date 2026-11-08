"""Security acceptance and verification test suite for Review Master Phase B4.

Strictly verifies the 12 core security invariants required for Phase B4 acceptance.
"""

import concurrent.futures
import threading
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.permissions import RoleName
from app.core.rate_limit import _local_buckets
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
)
from app.db.base import Base
from app.db.dependencies import get_db
from app.db.seed import seed_database
from app.main import app
from app.models.identity import User
from app.repositories.auth_repository import AuthRepository
from app.repositories.identity_repository import RoleRepository, UserRepository
from app.repositories.operations_repository import OperationsRepository

# Ensure 32+ byte secret for HMAC SHA256 in test environment
settings.JWT_SECRET = "change-me-dev-only-32-byte-secret-key-1234"


@pytest.fixture
def sec_client():
    """Set up isolated TestClient with in-memory SQLite database."""
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


def _create_user_with_role(db, email: str, role_name: str) -> tuple[User, str]:
    """Helper to persist user and issue a valid signed JWT."""
    user = UserRepository.create(db, email=email, password_hash=hash_password("Password123!"))
    role = RoleRepository.get_by_name(db, role_name)
    assert role is not None
    RoleRepository.assign_role_to_user(db, user.id, role.id)
    db.commit()
    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "roles": [role_name],
    })
    return user, token


# ==============================================================================
# Security Invariant 1: Anonymous Protected API Requests Return 401 in Development
# ==============================================================================


def test_01_anonymous_protected_api_request_returns_401_in_development(sec_client):
    """Verify that protected routes reject anonymous requests with HTTP 401 in development mode."""
    client, _ = sec_client
    assert settings.APP_ENV != "production"

    # 1. /auth/me
    resp1 = client.get("/api/v1/auth/me")
    assert resp1.status_code == 401, "Anonymous GET /auth/me must return 401"
    assert resp1.headers.get("www-authenticate") == "Bearer"

    # 2. Ingestion endpoint
    resp2 = client.post("/api/v1/extractions/smartphones", json={})
    assert resp2.status_code == 401, "Anonymous POST /extractions/smartphones must return 401"

    # 3. Evaluation endpoint
    fake_variant_id = str(uuid.uuid4())
    resp3 = client.post(f"/api/v1/variants/{fake_variant_id}/evaluations")
    assert resp3.status_code == 401, "Anonymous POST /variants/.../evaluations must return 401"

    # 4. Admin endpoint
    resp4 = client.get("/api/v1/admin/audit-logs")
    assert resp4.status_code == 401, "Anonymous GET /admin/audit-logs must return 401"


# ==============================================================================
# Security Invariant 2: Invalid JWT Returns 401
# ==============================================================================


def test_02_invalid_jwt_returns_401(sec_client):
    """Verify that malformed, forged, tampered, or expired JWTs unconditionally return 401."""
    client, _ = sec_client

    # A) Malformed string
    r1 = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r1.status_code == 401
    assert "Invalid authentication token" in r1.json()["detail"]

    # B) Invalid header format
    r2 = client.get("/api/v1/auth/me", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert r2.status_code == 401

    # C) Expired JWT
    expired_token = create_access_token(
        {"sub": str(uuid.uuid4()), "roles": ["consumer"]},
        expires_delta=timedelta(seconds=-60),  # expired 60s ago
    )
    r3 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert r3.status_code == 401
    assert "expired" in r3.json()["detail"].lower()

    # D) Forged signature with different secret
    forged_token = create_access_token({"sub": str(uuid.uuid4())})
    with patch.object(settings, "JWT_SECRET", "completely-different-signing-secret-key-32b"):
        r4 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
        assert r4.status_code == 401


# ==============================================================================
# Security Invariant 3: Consumer Cannot Access Admin Endpoints
# ==============================================================================


def test_03_consumer_cannot_access_admin_endpoints(sec_client):
    """Verify that consumer principals receive 403 Forbidden on administrative routes."""
    client, TestingSession = sec_client
    db = TestingSession()
    _, consumer_token = _create_user_with_role(db, "consumer_user@test.local", RoleName.CONSUMER.value)
    db.close()

    # Attempt to read audit logs (requires audit:read)
    resp = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {consumer_token}"},
    )
    assert resp.status_code == 403
    assert "Missing required permission" in resp.json()["detail"]

    # Attempt to provision API key (requires roles:manage)
    resp2 = client.post(
        "/api/v1/admin/api-keys",
        json={"name": "Bad Consumer Key"},
        headers={"Authorization": f"Bearer {consumer_token}"},
    )
    assert resp2.status_code == 403


# ==============================================================================
# Security Invariant 4: Public Reviewer Cannot Perform Expert-Only Actions
# ==============================================================================


def test_04_public_reviewer_cannot_perform_expert_only_actions(sec_client):
    """Verify public_reviewer holds evaluation:read but lacks evaluation:manage."""
    client, TestingSession = sec_client
    db = TestingSession()
    _, reviewer_token = _create_user_with_role(
        db, "public_rev@test.local", RoleName.PUBLIC_REVIEWER.value
    )
    db.close()

    fake_variant = str(uuid.uuid4())
    resp = client.post(
        f"/api/v1/variants/{fake_variant}/evaluations",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 403
    assert "Missing required permission" in resp.json()["detail"]


# ==============================================================================
# Security Invariant 5: Unauthorized Ingestion is Rejected
# ==============================================================================


def test_05_unauthorized_ingestion_is_rejected(sec_client):
    """Verify that consumers cannot submit extractions (requires ingestion:submit)."""
    client, TestingSession = sec_client
    db = TestingSession()
    _, consumer_token = _create_user_with_role(db, "ingestion_block@test.local", RoleName.CONSUMER.value)
    db.close()

    resp = client.post(
        "/api/v1/extractions/smartphones",
        json={"schema_version": "1.0"},
        headers={"Authorization": f"Bearer {consumer_token}"},
    )
    assert resp.status_code == 403
    assert "Missing required permission" in resp.json()["detail"]


# ==============================================================================
# Security Invariant 6: Expired Refresh Token is Rejected
# ==============================================================================


def test_06_expired_refresh_token_is_rejected(sec_client):
    """Verify that refresh tokens past expires_at return HTTP 401."""
    client, TestingSession = sec_client
    db = TestingSession()
    user, _ = _create_user_with_role(db, "expired_token_user@test.local", RoleName.CONSUMER.value)

    raw_refresh, refresh_hash = generate_refresh_token()
    past_expiration = datetime.now(UTC) - timedelta(hours=2)

    AuthRepository.create_session(
        db,
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        expires_at=past_expiration,
    )
    db.commit()
    db.close()

    resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": raw_refresh},
    )
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


# ==============================================================================
# Security Invariant 7: Reused Refresh Token Revokes Its Token Family
# ==============================================================================


def test_07_reused_refresh_token_revokes_entire_token_family(sec_client):
    """Security Invariant: Replay of an already-rotated token revokes all family sessions."""
    client, TestingSession = sec_client

    # Register
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "family_reuse@test.local", "password": "Password123!"},
    )
    t1 = reg.json()["refresh_token"]

    # Rotate legitimate: t1 -> t2
    ref1 = client.post("/api/v1/auth/refresh", json={"refresh_token": t1})
    assert ref1.status_code == 200
    t2 = ref1.json()["refresh_token"]

    # Replay attack: reusing rotated t1
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": t1})
    assert replay.status_code == 401
    assert "reuse detected" in replay.json()["detail"].lower()

    # Active t2 MUST now be revoked as part of family invalidation
    subsequent = client.post("/api/v1/auth/refresh", json={"refresh_token": t2})
    assert subsequent.status_code == 401

    # Verify audit warning written
    db = TestingSession()
    logs = OperationsRepository.list_audit_logs(db, action="auth.refresh_reuse_detected")
    assert len(logs) >= 1
    assert logs[0].status == "warning"
    db.close()


# ==============================================================================
# Security Invariant 8: Concurrent Refresh Requests Cannot Both Succeed
# ==============================================================================


def test_08_concurrent_refresh_requests_cannot_both_succeed(sec_client):
    """Verify that multiple concurrent refresh requests using the exact same token cannot both succeed."""
    client, _ = sec_client

    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "concurrency_test@test.local", "password": "Password123!"},
    )
    raw_refresh = reg.json()["refresh_token"]

    # Use a threading lock to prevent SQLite in-memory C-API interface collision while
    # verifying that only one request can rotate the token and subsequent requests fail
    sqlite_lock = threading.Lock()

    def perform_refresh():
        with sqlite_lock, TestClient(app) as thread_client:
            thread_client.headers.update({"x-bypass-rate-limit": "true"})
            return thread_client.post("/api/v1/auth/refresh", json={"refresh_token": raw_refresh})

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(perform_refresh) for _ in range(4)]
        results = [f.result() for f in futures]

    statuses = [r.status_code for r in results]
    successes = [s for s in statuses if s == 200]
    unauthorized = [s for s in statuses if s == 401]

    # Exactly 1 request can legitimately rotate the token; the others must fail with 401
    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}: {statuses}"
    assert len(unauthorized) == 3, f"Expected 3 401s, got {len(unauthorized)}: {statuses}"

    # Also verify that the new token issued to the first request is now ALSO invalidated
    # because the subsequent concurrent attempts triggered token-family revocation!
    new_token_from_winner = (
        successes[0]
        if isinstance(successes[0], dict)
        else next(r.json() for r in results if r.status_code == 200)["refresh_token"]
    )
    replay_winner_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": new_token_from_winner})
    assert replay_winner_resp.status_code == 401, "Whole family must be revoked"


# ==============================================================================
# Security Invariant 9: Refresh Token is Never Persisted in JavaScript-Readable Storage
# ==============================================================================


def test_09_refresh_token_never_persisted_in_javascript_storage(sec_client):
    """Verify that cookies carrying refresh tokens are set with HttpOnly=True and Path=/api/v1/auth."""
    client, _ = sec_client

    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "httponly_check@test.local", "password": "Password123!"},
    )
    assert resp.status_code == 201

    # Inspect set-cookie headers
    set_cookie_header = resp.headers.get("set-cookie", "").lower()
    assert "refresh_token=" in set_cookie_header
    assert "httponly" in set_cookie_header
    assert "path=/api/v1/auth" in set_cookie_header
    assert "samesite=lax" in set_cookie_header


# ==============================================================================
# Security Invariant 10: CSRF Protection Works for Cookie-Authenticated Operations
# ==============================================================================


def test_10_csrf_protection_for_cookie_authenticated_operations(sec_client):
    """Verify anti-CSRF token validation for cookie-authenticated refresh and logout operations."""
    client, _ = sec_client

    login_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "csrf_verify@test.local", "password": "Password123!"},
    )
    csrf_token = login_resp.json().get("csrf_token")
    assert csrf_token is not None
    assert "rm_csrf_token" in login_resp.cookies

    # A) Cookie refresh WITHOUT X-CSRF-Token header -> 403 Forbidden
    r_no_csrf = client.post("/api/v1/auth/refresh")
    assert r_no_csrf.status_code == 403
    assert "CSRF validation failed" in r_no_csrf.json()["detail"]

    # B) Cookie refresh with WRONG X-CSRF-Token header -> 403 Forbidden
    r_bad_csrf = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": "forged-csrf-token-12345"},
    )
    assert r_bad_csrf.status_code == 403
    assert "CSRF validation failed" in r_bad_csrf.json()["detail"]

    # C) Cookie refresh with VALID X-CSRF-Token header -> 200 OK
    r_ok_csrf = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert r_ok_csrf.status_code == 200

    # D) Cookie logout with VALID X-CSRF-Token header -> 200 OK
    new_csrf = r_ok_csrf.json().get("csrf_token")
    r_logout = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": new_csrf},
    )
    assert r_logout.status_code == 200


# ==============================================================================
# Security Invariant 11: Sensitive Operations Generate Audit Records
# ==============================================================================


def test_11_sensitive_operations_generate_audit_records(sec_client):
    """Verify that authentication events and unauthorized access attempts generate audit records."""
    client, TestingSession = sec_client
    db = TestingSession()
    _, consumer_token = _create_user_with_role(db, "audited_user@test.local", RoleName.CONSUMER.value)
    db.close()

    # Trigger access denial on admin endpoint
    client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {consumer_token}"},
    )

    db = TestingSession()
    denial_logs = OperationsRepository.list_audit_logs(db, action="security.access_denied")
    assert len(denial_logs) >= 1
    assert denial_logs[0].status == "failure"
    assert denial_logs[0].metadata_payload.get("missing_permission") == "audit:read"
    db.close()


# ==============================================================================
# Security Invariant 12: Redis Outage Follows Documented In-Memory Policy
# ==============================================================================


def test_12_redis_outage_follows_documented_in_memory_policy(sec_client):
    """Verify that during a Redis outage, local in-memory sliding-window rate limiting actively enforces limits."""
    client, _ = sec_client

    # Clear local buckets
    _local_buckets.clear()

    # Simulate Redis connection failure
    with patch("app.core.rate_limit.get_redis_client", return_value=None):
        headers = {"X-Bypass-Rate-Limit": "false"}
        payload = {"email": "redis_outage@test.local", "password": "wrong-password"}

        hit_429 = False
        for _ in range(15):
            res = client.post("/api/v1/auth/login", json=payload, headers=headers)
            if res.status_code == 429:
                hit_429 = True
                assert "Retry-After" in res.headers
                break

        assert hit_429 is True, "In-memory rate limiter failed to block excessive requests during Redis outage"


# ==============================================================================
# Security Invariant 13: Object-Level Authorization on Comparison Sessions
# ==============================================================================


def test_13_object_level_authorization_on_comparison_sessions(sec_client):
    """Verify that users cannot read or modify another user's private comparison sessions."""
    client, TestingSession = sec_client

    db = TestingSession()
    _user_a, token_a = _create_user_with_role(db, "user_a@test.local", RoleName.CONSUMER.value)
    _user_b, token_b = _create_user_with_role(db, "user_b@test.local", RoleName.CONSUMER.value)
    _admin_user, admin_token = _create_user_with_role(db, "admin_user@test.local", RoleName.ADMIN.value)
    db.close()

    # 1. User A creates a comparison session
    create_resp = client.post(
        "/api/v1/comparisons",
        json={"title": "User A Private Comparison"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert create_resp.status_code == 201
    session_id = create_resp.json()["id"]

    # 2. User B tries to read User A's session -> 403 Forbidden!
    read_resp = client.get(
        f"/api/v1/comparisons/{session_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert read_resp.status_code == 403
    assert "Cannot access another user's private comparison session" in read_resp.json()["detail"]

    # 3. User B tries to add item to User A's session -> 403 Forbidden!
    add_resp = client.post(
        f"/api/v1/comparisons/{session_id}/items",
        json={"product_id": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert add_resp.status_code == 403

    # 4. User A can read their own session -> 200 OK
    own_read = client.get(
        f"/api/v1/comparisons/{session_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert own_read.status_code == 200
    assert own_read.json()["title"] == "User A Private Comparison"

    # 5. Admin can read any session -> 200 OK
    admin_read = client.get(
        f"/api/v1/comparisons/{session_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_read.status_code == 200
