"""Comprehensive test suite for Phase B4 — Authentication, Authorization, RBAC, and Token Lifecycle."""

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.permissions import Permission, RoleName, get_permissions_for_roles
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
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
def auth_client():
    """Set up TestClient with SQLite in-memory database."""
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


# ==============================================================================
# 1. Cryptographic Security & Password Hashing Tests
# ==============================================================================


def test_argon2id_password_hashing():
    """Verify Argon2id produces valid hashes and verifies correctly."""
    plain = "SuperSecurePassword123!"
    pw_hash = hash_password(plain)

    # Argon2id identifier
    assert pw_hash.startswith("$argon2id$")
    assert verify_password(plain, pw_hash) is True
    assert verify_password("WrongPassword123!", pw_hash) is False
    assert verify_password("", pw_hash) is False
    assert verify_password(plain, None) is False


def test_jwt_access_token_lifecycle():
    """Verify JWT access token creation, claims, and decoding."""
    user_id = str(uuid.uuid4())
    data = {
        "sub": user_id,
        "email": "tester@reviewmaster.local",
        "roles": [RoleName.CONSUMER.value],
    }

    token = create_access_token(data, expires_delta=timedelta(minutes=15))
    decoded = decode_access_token(token)

    assert decoded["sub"] == user_id
    assert decoded["email"] == "tester@reviewmaster.local"
    assert decoded["roles"] == [RoleName.CONSUMER.value]
    assert "exp" in decoded
    assert "iat" in decoded
    assert "jti" in decoded


def test_refresh_token_entropy_and_hashing():
    """Verify high-entropy opaque refresh token generation and SHA-256 digest."""
    raw1, hash1 = generate_refresh_token()
    raw2, hash2 = generate_refresh_token()

    assert raw1 != raw2
    assert hash1 != hash2
    assert len(hash1) == 64  # SHA-256 hex length
    assert hash_refresh_token(raw1) == hash1


# ==============================================================================
# 2. RBAC Permissions Mapping Tests
# ==============================================================================


def test_role_permissions_resolution():
    """Verify permission resolution across all canonical roles."""
    admin_perms = get_permissions_for_roles([RoleName.ADMIN.value])
    assert Permission.CATALOG_MANAGE.value in admin_perms
    assert Permission.EVALUATION_MANAGE.value in admin_perms
    assert Permission.INGESTION_SUBMIT.value in admin_perms
    assert Permission.AUDIT_READ.value in admin_perms

    consumer_perms = get_permissions_for_roles([RoleName.CONSUMER.value])
    assert Permission.CATALOG_READ.value in consumer_perms
    assert Permission.COMPARISON_READ.value in consumer_perms
    assert Permission.INGESTION_SUBMIT.value not in consumer_perms
    assert Permission.EVALUATION_MANAGE.value not in consumer_perms

    expert_perms = get_permissions_for_roles([RoleName.EXPERT_REVIEWER.value])
    assert Permission.EVALUATION_MANAGE.value in expert_perms
    assert Permission.INGESTION_SUBMIT.value in expert_perms
    assert Permission.ROLES_MANAGE.value not in expert_perms


# ==============================================================================
# 3. Registration Endpoint Tests
# ==============================================================================


def test_register_success(auth_client):
    """Test user self-registration with default consumer role and token issuance."""
    client, TestingSession = auth_client

    payload = {
        "email": "  NewUser@Example.Com  ",  # Tests trimming and lowercase normalization
        "password": "SecurePassword123!",
        "display_name": "Test User",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201, resp.text

    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "newuser@example.com"
    assert data["user"]["display_name"] == "Test User"
    assert RoleName.CONSUMER.value in data["user"]["roles"]

    # Verify session persisted in DB
    db = TestingSession()
    user = UserRepository.get_by_email(db, "newuser@example.com")
    assert user is not None
    assert verify_password("SecurePassword123!", user.password_hash) is True

    # Verify audit log
    logs = OperationsRepository.list_audit_logs(db, action="auth.register")
    assert len(logs) >= 1
    assert logs[0].actor_id == str(user.id)
    assert logs[0].status == "success"
    db.close()


def test_register_duplicate_email_fails(auth_client):
    """Test registration with an already registered email returns 400."""
    client, _ = auth_client

    payload = {
        "email": "duplicate@example.com",
        "password": "SecurePassword123!",
    }
    resp1 = client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 400
    assert "already exists" in resp2.json()["detail"]


def test_register_short_password_fails(auth_client):
    """Test registration with password shorter than 8 chars returns 422."""
    client, _ = auth_client

    payload = {
        "email": "shortpw@example.com",
        "password": "short",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 422


# ==============================================================================
# 4. Login Endpoint Tests
# ==============================================================================


def test_login_success_and_cookie(auth_client):
    """Test user login with correct credentials returns tokens and sets cookie."""
    client, TestingSession = auth_client

    # Register user
    client.post(
        "/api/v1/auth/register",
        json={"email": "loginuser@example.com", "password": "Password123!"},
    )

    # Login
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "loginuser@example.com", "password": "Password123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert "refresh_token" in resp.cookies

    # Verify audit log
    db = TestingSession()
    logs = OperationsRepository.list_audit_logs(db, action="auth.login")
    assert len(logs) >= 1
    assert logs[0].status == "success"
    db.close()


def test_login_invalid_password_fails(auth_client):
    """Test login with wrong password returns 401."""
    client, TestingSession = auth_client

    client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpw@example.com", "password": "Password123!"},
    )

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@example.com", "password": "IncorrectPassword!"},
    )
    assert resp.status_code == 401

    db = TestingSession()
    logs = OperationsRepository.list_audit_logs(db, action="auth.login_failed")
    assert len(logs) >= 1
    db.close()


def test_login_unknown_user_fails(auth_client):
    """Test login with non-existent user returns 401."""
    client, _ = auth_client
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nosuchuser@example.com", "password": "Password123!"},
    )
    assert resp.status_code == 401


def test_login_deactivated_user_fails(auth_client):
    """Test login with deactivated account returns 403."""
    client, TestingSession = auth_client

    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "deactivated@example.com", "password": "Password123!"},
    )
    user_id = uuid.UUID(resp.json()["user"]["id"])

    # Deactivate in DB
    db = TestingSession()
    user = db.get(User, user_id)
    assert user is not None
    user.is_active = False
    db.commit()
    db.close()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "deactivated@example.com", "password": "Password123!"},
    )
    assert login_resp.status_code == 403
    assert "deactivated" in login_resp.json()["detail"].lower()


# ==============================================================================
# 5. Token Rotation & Reuse Detection Tests (Security Critical)
# ==============================================================================


def test_refresh_token_rotation_success(auth_client):
    """Test refresh token rotation issues a new token pair and revokes previous session."""
    client, TestingSession = auth_client

    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "refreshuser@example.com", "password": "Password123!"},
    )
    old_refresh = reg_resp.json()["refresh_token"]

    # Call /refresh with the refresh token
    ref_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert ref_resp.status_code == 200
    ref_data = ref_resp.json()
    new_refresh = ref_data["refresh_token"]
    assert new_refresh != old_refresh

    # Verify old session marked rotated/revoked in DB
    db = TestingSession()
    old_hash = hash_refresh_token(old_refresh)
    old_session = AuthRepository.get_session_by_hash(db, old_hash)
    assert old_session is not None
    assert old_session.is_revoked is True
    assert old_session.rotated_at is not None

    # Verify new session is active
    new_hash = hash_refresh_token(new_refresh)
    new_session = AuthRepository.get_session_by_hash(db, new_hash)
    assert new_session is not None
    assert new_session.is_revoked is False
    assert new_session.token_family == old_session.token_family
    db.close()


def test_refresh_token_reuse_detection_revokes_entire_family(auth_client):
    """Security Invariant: Replay of an already-used refresh token revokes the entire family."""
    client, TestingSession = auth_client

    # 1. Register
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "reusedetect@example.com", "password": "Password123!"},
    )
    token_1 = reg_resp.json()["refresh_token"]

    # 2. Legitimate rotation: token_1 -> token_2
    ref_resp_1 = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_1},
    )
    assert ref_resp_1.status_code == 200
    token_2 = ref_resp_1.json()["refresh_token"]

    # 3. Legitimate rotation: token_2 -> token_3
    ref_resp_2 = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_2},
    )
    assert ref_resp_2.status_code == 200
    token_3 = ref_resp_2.json()["refresh_token"]

    # 4. ATTACK SIMULATION: Reusing already rotated token_1!
    replay_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_1},
    )
    assert replay_resp.status_code == 401
    assert "reuse detected" in replay_resp.json()["detail"].lower()

    # 5. VERIFY REPERCUSSION: token_3 (which was active) MUST NOW BE REVOKED!
    subsequent_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_3},
    )
    assert subsequent_resp.status_code == 401

    # Verify audit warning
    db = TestingSession()
    logs = OperationsRepository.list_audit_logs(
        db, action="auth.refresh_reuse_detected"
    )
    assert len(logs) >= 1
    assert logs[0].status == "warning"
    db.close()


# ==============================================================================
# 6. Logout & Session Invalidation Tests
# ==============================================================================


def test_logout_revokes_session(auth_client):
    """Test logout invalidates the session and subsequent refresh fails."""
    client, _ = auth_client

    login_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "logoutuser@example.com", "password": "Password123!"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Logout
    logout_resp = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_resp.status_code == 200

    # Subsequent refresh should fail
    ref_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert ref_resp.status_code == 401


# ==============================================================================
# 7. Current User (/me) & RBAC Route Protection Tests
# ==============================================================================


def test_get_me_endpoint(auth_client):
    """Test GET /api/v1/auth/me returns current user profile."""
    client, _ = auth_client

    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "me_user@example.com", "password": "Password123!", "display_name": "Me Profile"},
    )
    access_token = reg_resp.json()["access_token"]

    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 200
    me_data = resp.json()
    assert me_data["email"] == "me_user@example.com"
    assert me_data["display_name"] == "Me Profile"


def test_unauthenticated_request_fails_when_strict_auth_enforced(auth_client):
    """Test that requests with invalid credentials or X-Force-Auth return 401."""
    client, _ = auth_client

    # 1. Invalid Bearer token
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer completely-invalid-token"},
    )
    assert resp.status_code == 401

    # 2. Force auth header without credentials
    resp2 = client.get(
        "/api/v1/auth/me",
        headers={"X-Force-Auth": "true"},
    )
    assert resp2.status_code == 401


def test_rbac_consumer_forbidden_from_evaluations(auth_client):
    """Test that a user with only consumer role cannot trigger variant evaluations."""
    client, _ = auth_client

    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "consumer_only@example.com", "password": "Password123!"},
    )
    consumer_token = reg_resp.json()["access_token"]

    random_variant_id = str(uuid.uuid4())
    resp = client.post(
        f"/api/v1/variants/{random_variant_id}/evaluations",
        headers={"Authorization": f"Bearer {consumer_token}"},
    )
    # Consumer lacks evaluation:manage permission -> 403 Forbidden
    assert resp.status_code == 403
    assert "Missing required permission" in resp.json()["detail"]


def test_rbac_admin_authorized_for_evaluations(auth_client):
    """Test that an admin user passes the permission gate for variant evaluations."""
    client, TestingSession = auth_client

    # Create admin user
    db = TestingSession()
    admin_user = UserRepository.create(db, email="admin@test.local", password_hash=hash_password("admin123"))
    admin_role = RoleRepository.get_by_name(db, RoleName.ADMIN.value)
    assert admin_role is not None
    RoleRepository.assign_role_to_user(db, admin_user.id, admin_role.id)
    admin_id = str(admin_user.id)
    admin_email = admin_user.email
    db.commit()
    db.close()

    admin_token = create_access_token({
        "sub": admin_id,
        "email": admin_email,
        "roles": [RoleName.ADMIN.value],
    })

    random_variant_id = str(uuid.uuid4())
    resp = client.post(
        f"/api/v1/variants/{random_variant_id}/evaluations",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Passes authorization check (404 because random variant doesn't exist, not 403!)
    assert resp.status_code == 404


def test_rate_limiting_blocks_excessive_requests(auth_client):
    """Test that Redis rate limiting triggers HTTP 429 after exceeding max requests."""
    client, _ = auth_client

    # Request without bypass header
    headers = {"X-Bypass-Rate-Limit": "false"}
    login_payload = {"email": "ratelimit_test@example.com", "password": "WrongPassword!"}

    hit_429 = False
    for _ in range(15):
        resp = client.post("/api/v1/auth/login", json=login_payload, headers=headers)
        if resp.status_code == 429:
            hit_429 = True
            assert "Retry-After" in resp.headers
            break

    assert hit_429 is True, "Rate limiter did not trigger 429 on excessive requests"
