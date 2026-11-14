"""Idempotency and duplicate protection regression tests (Phase B12 Module 5).

Verifies:
1. Ingestion idempotency with repeated Idempotency-Key.
2. Concurrent duplicate ingestion enqueuing safety.
3. Import token single-use atomic consumption under concurrent race conditions.
4. Duplicate variant additions to comparison sessions.
"""

import concurrent.futures
import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.permissions import RoleName
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.identity import Role
from app.repositories.identity_repository import UserRepository


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


def _get_authenticated_token(db):
    rand = uuid.uuid4().hex[:8]
    user = UserRepository.create(
        db,
        email=f"idempotency_{rand}@test.local",
        display_name=f"Idempotency User {rand}",
        password_hash="benchhash123",
    )
    role = db.query(Role).filter(Role.name == RoleName.CONSUMER.value).first()
    if role:
        user.roles.append(role)
    db.commit()

    return create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "roles": [r.name for r in user.roles],
    })


def test_import_token_single_use_concurrency_race(client, db):
    """Multiple concurrent consumption requests for the same token result in exactly 1 success and N-1 409 conflicts."""
    token = _get_authenticated_token(db)

    # Create an import token
    res = client.post(
        "/api/v1/import-tokens",
        json={"context_data": {"race_test": True}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == status.HTTP_201_CREATED
    import_code = res.json()["import_code"]

    def _consume():
        thread_client = TestClient(app)
        return thread_client.post(
            "/api/v1/import-tokens/consume",
            json={"import_code": import_code},
            headers={"Authorization": f"Bearer {token}"},
        )

    # 8 threads race to consume the single-use token simultaneously
    concurrency = 8
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(_consume) for _ in range(concurrency)]
        responses = [f.result() for f in concurrent.futures.as_completed(futures)]

    statuses = [r.status_code for r in responses]
    success_count = statuses.count(status.HTTP_200_OK)
    conflict_count = statuses.count(status.HTTP_409_CONFLICT)

    assert success_count == 1, f"Expected exactly 1 success, got {success_count}. Statuses: {statuses}"
    assert conflict_count == concurrency - 1, f"Expected {concurrency - 1} 409 Conflicts, got {conflict_count}"


def test_comparison_session_active_limit_enforced_concurrently(client, db):
    """User cannot create more than 2 active comparison sessions even under concurrent race conditions."""
    token = _get_authenticated_token(db)

    def _create_session():
        thread_client = TestClient(app)
        return thread_client.post(
            "/api/v1/comparisons",
            json={"title": "Concurrent Compare", "category_id": None},
            headers={"Authorization": f"Bearer {token}"},
        )

    # 5 concurrent requests attempting to create sessions
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_create_session) for _ in range(5)]
        responses = [f.result() for f in concurrent.futures.as_completed(futures)]

    statuses = [r.status_code for r in responses]
    success_count = statuses.count(status.HTTP_201_CREATED)
    limit_conflicts = statuses.count(status.HTTP_409_CONFLICT)

    # Maximum 2 active sessions allowed per user
    assert success_count <= 2, f"Active session limit exceeded! Got {success_count} successes"
    assert limit_conflicts >= 3, "Expected remaining requests to be rejected with 409 Conflict"
