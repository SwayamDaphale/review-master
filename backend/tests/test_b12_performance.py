"""Performance and load benchmark suite for Review Master core workflows (Module 8).

Benchmarks latency (p50, p95, p99) under realistic database conditions:
- /healthz and /readyz probes
- Catalog search and product detail
- Deterministic evaluation retrieval (< 2.0s target)
- Natural language requirement parsing
"""

import statistics
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.permissions import RoleName
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.identity import Role
from app.models.product import Product
from app.models.variant import Variant
from app.repositories.identity_repository import UserRepository


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_headers(db):
    rand = uuid.uuid4().hex[:8]
    user = UserRepository.create(
        db,
        email=f"perf_{rand}@benchmark.local",
        display_name=f"Perf Tester {rand}",
        password_hash="benchhash123",
    )
    role = db.query(Role).filter(Role.name == RoleName.CONSUMER.value).first()
    if role:
        user.roles.append(role)
    db.commit()

    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "roles": [r.name for r in user.roles],
    })
    return {"Authorization": f"Bearer {token}"}


def _calc_stats(latencies_ms: list[float]) -> dict[str, float]:
    sorted_lats = sorted(latencies_ms)
    n = len(sorted_lats)
    p50_idx = int(n * 0.50)
    p95_idx = min(int(n * 0.95), n - 1)
    p99_idx = min(int(n * 0.99), n - 1)
    return {
        "count": n,
        "min_ms": round(min(sorted_lats), 2),
        "p50_ms": round(sorted_lats[p50_idx], 2),
        "p95_ms": round(sorted_lats[p95_idx], 2),
        "p99_ms": round(sorted_lats[p99_idx], 2),
        "max_ms": round(max(sorted_lats), 2),
        "mean_ms": round(statistics.mean(sorted_lats), 2),
    }


def test_benchmark_health_and_ready_endpoints(client):
    """Measure liveness and readiness probe response latencies."""
    lats_healthz = []
    lats_readyz = []

    for _ in range(30):
        t0 = time.perf_counter()
        r = client.get("/healthz")
        assert r.status_code == 200
        lats_healthz.append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        r = client.get("/readyz")
        assert r.status_code == 200
        lats_readyz.append((time.perf_counter() - t0) * 1000)

    stats_healthz = _calc_stats(lats_healthz)
    stats_readyz = _calc_stats(lats_readyz)

    print(f"\n[BENCHMARK] /healthz: p50={stats_healthz['p50_ms']}ms, p95={stats_healthz['p95_ms']}ms")
    print(f"[BENCHMARK] /readyz: p50={stats_readyz['p50_ms']}ms, p95={stats_readyz['p95_ms']}ms")

    assert stats_healthz["p95_ms"] < 50.0  # Under 50ms
    assert stats_readyz["p95_ms"] < 100.0  # Under 100ms


def test_benchmark_product_search_and_detail(client, db):
    """Measure catalog search and single-product detail retrieval latencies."""
    prod = db.execute(select(Product)).scalars().first()
    assert prod is not None

    lats_search = []
    lats_detail = []

    for _ in range(25):
        t0 = time.perf_counter()
        r = client.get("/api/v1/products?limit=10")
        assert r.status_code == 200
        lats_search.append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        r = client.get(f"/api/v1/products/{prod.id}")
        assert r.status_code == 200
        lats_detail.append((time.perf_counter() - t0) * 1000)

    stats_search = _calc_stats(lats_search)
    stats_detail = _calc_stats(lats_detail)

    print(f"\n[BENCHMARK] /products (search): p50={stats_search['p50_ms']}ms, p95={stats_search['p95_ms']}ms")
    print(f"[BENCHMARK] /products/{{id}} (detail): p50={stats_detail['p50_ms']}ms, p95={stats_detail['p95_ms']}ms")

    assert stats_search["p95_ms"] < 250.0  # Under 250ms
    assert stats_detail["p95_ms"] < 150.0  # Under 150ms


def test_benchmark_cached_evaluation_retrieval(client, db, auth_headers):
    """Measure cached evaluation retrieval latency against the 2.0s SLA target."""
    variant = db.execute(select(Variant)).scalars().first()
    assert variant is not None

    # Warm-up request
    client.get(f"/api/v1/variants/{variant.id}/evaluations/latest", headers=auth_headers)

    lats_eval = []
    for _ in range(30):
        t0 = time.perf_counter()
        r = client.get(f"/api/v1/variants/{variant.id}/evaluations/latest", headers=auth_headers)
        assert r.status_code in {200, 404}
        lats_eval.append((time.perf_counter() - t0) * 1000)

    stats_eval = _calc_stats(lats_eval)
    print(f"\n[BENCHMARK] /variants/{{id}}/evaluations/latest: p50={stats_eval['p50_ms']}ms, p95={stats_eval['p95_ms']}ms, max={stats_eval['max_ms']}ms")

    assert stats_eval["p95_ms"] < 2000.0, f"Evaluation retrieval exceeded 2000ms SLA: {stats_eval['p95_ms']}ms"
    assert stats_eval["p50_ms"] < 200.0, f"Median evaluation retrieval exceeded 200ms: {stats_eval['p50_ms']}ms"


def test_benchmark_requirement_parse(client, auth_headers):
    """Measure requirement parsing endpoint latency."""
    lats_parse = []
    for _ in range(15):
        t0 = time.perf_counter()
        r = client.post(
            "/api/v1/recommendations/parse",
            json={"query": "lightweight smartphone under 50000 with 256GB storage and great battery", "category_hint": "smartphone"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        lats_parse.append((time.perf_counter() - t0) * 1000)

    stats_parse = _calc_stats(lats_parse)
    print(f"\n[BENCHMARK] /recommendations/parse: p50={stats_parse['p50_ms']}ms, p95={stats_parse['p95_ms']}ms")
    assert stats_parse["p95_ms"] < 1000.0  # Deterministic parse under 1s
