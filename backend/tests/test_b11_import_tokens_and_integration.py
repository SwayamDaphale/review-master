"""Tests for Phase B11 Module 13: Secure Single-Use Import-Code Handoff."""

import hashlib
import threading
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.import_tokens import get_optional_user
from app.core.auth import AuthenticatedUser
from app.db.base import utc_now
from app.db.session import SessionLocal
from app.main import app
from app.models.identity import User
from app.models.operation import ImportToken


@pytest.fixture
def db():
    """Database session connected to PostgreSQL."""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_import_token_creation_and_single_use_consumption(client: TestClient, db: Session):
    """Verify high-entropy token generation and strict single-use atomic consumption."""
    # 1. Create import token
    resp = client.post(
        "/api/v1/import-tokens",
        json={"context_data": {"source": "amazon_in", "asin": "B0TEST001"}},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    raw_code = data["import_code"]
    assert raw_code and len(raw_code) > 20
    assert "expires_at" in data

    # Verify only hash is stored in database
    token_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
    stmt = select(ImportToken).where(ImportToken.token_hash == token_hash)
    db_token = db.execute(stmt).scalar_one_or_none()
    assert db_token is not None
    assert db_token.used_at is None
    assert db_token.is_revoked is False
    assert raw_code not in db_token.token_hash

    # 2. First consumption: must succeed
    consume_resp = client.post(
        "/api/v1/import-tokens/consume",
        json={"import_code": raw_code},
    )
    assert consume_resp.status_code == 200, consume_resp.text
    consume_data = consume_resp.json()
    assert consume_data["status"] == "consumed"
    assert "consumed_at" in consume_data

    # Verify token is marked consumed in DB
    db.expire_all()
    db_token = db.execute(stmt).scalar_one()
    assert db_token.used_at is not None

    # 3. Second consumption (replay attack): must be strictly rejected with HTTP 409
    replay_resp = client.post(
        "/api/v1/import-tokens/consume",
        json={"import_code": raw_code},
    )
    assert replay_resp.status_code == 409, replay_resp.text
    assert "already been consumed" in replay_resp.json()["detail"].lower()


def test_import_token_expired_rejected(client: TestClient, db: Session):
    """Verify expired token is rejected."""
    raw_code = f"test_expired_{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
    past_time = utc_now() - timedelta(minutes=20)

    token = ImportToken(
        token_hash=token_hash,
        expires_at=past_time,
        is_revoked=False,
        used_at=None,
    )
    db.add(token)
    db.commit()

    resp = client.post(
        "/api/v1/import-tokens/consume",
        json={"import_code": raw_code},
    )
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


def test_import_token_revoked_rejected(client: TestClient, db: Session):
    """Verify revoked token is rejected."""
    raw_code = f"test_revoked_{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
    future_time = utc_now() + timedelta(minutes=15)

    token = ImportToken(
        token_hash=token_hash,
        expires_at=future_time,
        is_revoked=True,
        used_at=None,
    )
    db.add(token)
    db.commit()

    resp = client.post(
        "/api/v1/import-tokens/consume",
        json={"import_code": raw_code},
    )
    assert resp.status_code == 400
    assert "revoked" in resp.json()["detail"].lower()


def test_import_token_user_ownership_binding(client: TestClient, db: Session):
    """Verify token bound to user A cannot be consumed by user B."""
    tag = uuid.uuid4().hex[:6]
    user_a = User(
        id=uuid.uuid4(),
        email=f"user_a_{tag}@test.local",
        password_hash="mock_hash",
        display_name="User A",
    )
    user_b = User(
        id=uuid.uuid4(),
        email=f"user_b_{tag}@test.local",
        password_hash="mock_hash",
        display_name="User B",
    )
    db.add_all([user_a, user_b])
    db.commit()

    raw_code = f"test_user_bound_{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()

    token = ImportToken(
        token_hash=token_hash,
        user_id=user_a.id,
        expires_at=utc_now() + timedelta(minutes=15),
        is_revoked=False,
        used_at=None,
    )
    db.add(token)
    db.commit()

    # Attempt to consume without authentication -> 401
    anon_resp = client.post(
        "/api/v1/import-tokens/consume",
        json={"import_code": raw_code},
    )
    assert anon_resp.status_code == 401

    # Attempt to consume as user B -> 403 Forbidden
    app.dependency_overrides[get_optional_user] = lambda: AuthenticatedUser(
        id=str(user_b.id),
        email=user_b.email,
        roles=["consumer"],
        permissions={"catalog:read"},
        is_authenticated=True,
    )
    try:
        wrong_user_resp = client.post(
            "/api/v1/import-tokens/consume",
            json={"import_code": raw_code},
            headers={"Authorization": "Bearer mock_token_b"},
        )
        assert wrong_user_resp.status_code == 403
        assert "different user" in wrong_user_resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_optional_user, None)

    # Attempt to consume as user A -> 200 OK
    app.dependency_overrides[get_optional_user] = lambda: AuthenticatedUser(
        id=str(user_a.id),
        email=user_a.email,
        roles=["consumer"],
        permissions={"catalog:read"},
        is_authenticated=True,
    )
    try:
        right_user_resp = client.post(
            "/api/v1/import-tokens/consume",
            json={"import_code": raw_code},
            headers={"Authorization": "Bearer mock_token_a"},
        )
        assert right_user_resp.status_code == 200
        assert right_user_resp.json()["status"] == "consumed"
    finally:
        app.dependency_overrides.pop(get_optional_user, None)


def test_import_token_concurrent_consumption(client: TestClient, db: Session):
    """Verify that under simultaneous parallel requests, exactly one succeeds and all others fail."""
    resp = client.post("/api/v1/import-tokens", json={})
    assert resp.status_code == 201
    raw_code = resp.json()["import_code"]

    results = []
    threads = []
    num_threads = 6

    def try_consume():
        # Fresh test client per thread to simulate independent concurrent callers
        c = TestClient(app)
        res = c.post("/api/v1/import-tokens/consume", json={"import_code": raw_code})
        results.append(res.status_code)

    for _ in range(num_threads):
        t = threading.Thread(target=try_consume)
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one request must receive 200 OK
    assert results.count(200) == 1, f"Expected exactly one 200, got: {results}"
    # All other concurrent requests must receive 409 Conflict
    assert results.count(409) == num_threads - 1, f"Expected {num_threads - 1} 409s, got: {results}"
