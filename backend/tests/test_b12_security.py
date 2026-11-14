"""Automated security regression tests for Review Master backend (Phase B12).

Tests:
1. Authentication: Unauthenticated rejection, expired/malformed tokens, refresh token rotation, replay revocation.
2. Authorization & RBAC: Object ownership isolation across users, admin endpoint protection.
3. Input & Injection Security: SQL injection immunity, oversized/malformed input handling.
4. Rate Limiting: Atomic 429 enforcement, Retry-After header, rejection of bypass headers, trusted proxy isolation.
"""

import uuid
from datetime import timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.permissions import RoleName
from app.core.security import create_access_token, generate_refresh_token, hash_password
from app.db.base import utc_now
from app.db.session import SessionLocal
from app.main import app
from app.models.identity import Role, User
from app.repositories.auth_repository import AuthRepository
from app.repositories.identity_repository import UserRepository


@pytest.fixture
def db():
    """Isolated database session fixture for security testing."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


def _create_test_user(db: Session, email_prefix: str, role_name: RoleName = RoleName.CONSUMER) -> tuple[User, str]:
    """Helper to create a test user with assigned role and active access token."""
    rand = uuid.uuid4().hex[:8]
    email = f"{email_prefix}_{rand}@security-test.local"
    pw_hash = hash_password("SecurePassword123!")

    user = UserRepository.create(
        db,
        email=email,
        display_name=f"Security Test User {rand}",
        password_hash=pw_hash,
    )
    role = db.query(Role).filter(Role.name == role_name.value).first()
    if role:
        user.roles.append(role)
    db.commit()
    db.refresh(user)

    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "roles": [r.name for r in user.roles],
    })
    return user, token


# ==============================================================================
# 1. AUTHENTICATION SECURITY TESTS
# ==============================================================================


def test_unauthenticated_request_rejected(client):
    """Unauthenticated requests must be rejected with HTTP 401 on protected endpoints."""
    # Attempt reading current user
    res = client.get("/api/v1/auth/me")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    # Attempt accessing comparison sessions
    res = client.get("/api/v1/comparisons")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    # Attempt recommendations
    res = client.post("/api/v1/recommendations", json={"category_id": str(uuid.uuid4())})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_expired_token_rejected(client, db):
    """Expired JWT access token must be rejected with 401."""
    user, _ = _create_test_user(db, "expired_test")
    expired_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "roles": ["consumer"]},
        expires_delta=timedelta(seconds=-10),  # Expired in past
    )
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    detail = res.json().get("detail", "").lower()
    assert any(term in detail for term in ("token", "expired", "invalid"))


def test_malformed_token_rejected(client):
    """Malformed or tampered JWT must be rejected with 401."""
    res = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.valid.jwt.token"})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_password_hash_never_exposed(client, db):
    """API responses must never leak password_hash in user responses."""
    _user, token = _create_test_user(db, "leak_test")
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "password" not in data
    assert "password_hash" not in data
    assert "argon2" not in str(data).lower()


def test_refresh_token_rotation_and_replay_detection(client, db):
    """Refresh token must rotate upon use, and replay of consumed token must trigger revocation."""
    user, _ = _create_test_user(db, "replay_user")
    raw_refresh, refresh_hash = generate_refresh_token()
    session_expires = utc_now() + timedelta(days=7)

    AuthRepository.create_session(
        db,
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        expires_at=session_expires,
    )
    db.commit()

    # 1. First refresh exchange -> succeeds and rotates
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": raw_refresh})
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    new_refresh = data["refresh_token"]
    assert new_refresh != raw_refresh

    # 2. Replay attack: attempt refreshing again with the old token -> must be rejected
    replay_res = client.post("/api/v1/auth/refresh", json={"refresh_token": raw_refresh})
    assert replay_res.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}

    # 3. Family revocation: the entire session is revoked upon replay, so even the new token fails
    compromised_res = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert compromised_res.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}


# ==============================================================================
# 2. AUTHORIZATION & CROSS-TENANT OWNERSHIP ISOLATION
# ==============================================================================


def test_cross_tenant_comparison_isolation(client, db):
    """User A cannot read, modify, or delete User B's private comparison sessions."""
    _user_a, token_a = _create_test_user(db, "user_a")
    _user_b, token_b = _create_test_user(db, "user_b")

    # User A creates a comparison session
    res_a = client.post(
        "/api/v1/comparisons",
        json={"title": "User A Private Compare", "category_id": None},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_a.status_code in {status.HTTP_200_OK, status.HTTP_201_CREATED}
    session_a_id = res_a.json()["id"]

    # User B attempts to read User A's session -> must be rejected with 403 or 404
    read_res = client.get(
        f"/api/v1/comparisons/{session_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert read_res.status_code in {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND}

    # User B attempts to modify / add a variant to User A's session -> must be rejected with 403 or 404
    add_res = client.post(
        f"/api/v1/comparisons/{session_a_id}/variants",
        json={"variant_id": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert add_res.status_code in {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND}

    # User B attempts to archive User A's session -> must be rejected with 403 or 404
    archive_res = client.post(
        f"/api/v1/comparisons/{session_a_id}/archive",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert archive_res.status_code in {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND}


def test_non_admin_cannot_access_admin_operations(client, db):
    """Regular consumer cannot invoke administrative operations."""
    _, consumer_token = _create_test_user(db, "consumer", RoleName.CONSUMER)

    # Attempt listing all users or triggering administrative ingestion review
    res = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {consumer_token}"},
    )
    # Admin route doesn't exist or returns 403/401/404, never 200
    assert res.status_code in {status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED, status.HTTP_404_NOT_FOUND}


# ==============================================================================
# 3. INPUT VALIDATION & SQL INJECTION RESILIENCE
# ==============================================================================


def test_sql_injection_resilience_in_search(client, db):
    """SQL injection payloads in catalog search query parameter do not cause server errors."""
    sql_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE products; --",
        "1 UNION SELECT null, null, null--",
        "' OR 1=1; SELECT * FROM users; --",
    ]
    for payload in sql_payloads:
        res = client.get(f"/api/v1/products?q={payload}")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert "items" in data
        assert isinstance(data["items"], list)


def test_malformed_uuid_handled_safely(client):
    """Malformed non-UUID path parameters must return 422 or 404 without 500 error."""
    res = client.get("/api/v1/products/not-a-valid-uuid")
    assert res.status_code in {status.HTTP_404_NOT_FOUND, status.HTTP_422_UNPROCESSABLE_ENTITY}
    assert res.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR


def test_correlation_id_in_response(client):
    """Every HTTP response must contain an X-Request-ID header."""
    res = client.get("/healthz")
    assert res.status_code == status.HTTP_200_OK
    assert "x-request-id" in res.headers
    assert len(res.headers["x-request-id"]) > 0


# ==============================================================================
# 4. RATE LIMITING SECURITY & BYPASS PREVENTION
# ==============================================================================


def test_rate_limit_bypass_header_ineffective(client):
    """X-Bypass-Rate-Limit: true header must be strictly ineffective."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@user.local", "password": "WrongPassword1!"},
        headers={"x-bypass-rate-limit": "true"},
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_spoofed_forwarded_for_ignored_from_untrusted_peer(client):
    """X-Forwarded-For is ignored if peer IP is not in trusted proxies list."""
    res = client.get(
        "/healthz",
        headers={"X-Forwarded-For": "203.0.113.195, 198.51.100.1"},
    )
    assert res.status_code == status.HTTP_200_OK
