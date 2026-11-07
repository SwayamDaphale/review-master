"""Tests for FastAPI entrypoint and health endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app

client = TestClient(app)


def test_healthz_endpoint():
    """Verify /healthz returns 200 and expected status payload."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "review-master-backend"
    assert "environment" in data


def test_production_environment_rejects_insecure_secrets():
    """Verify production environment blocks default dev secrets."""
    with pytest.raises(ValueError, match="JWT_SECRET must be configured"):
        Settings(
            APP_ENV="production",
            JWT_SECRET="change-me-dev-only",
            API_KEY_PEPPER="a" * 32,
            DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
        )

    with pytest.raises(ValueError, match="API_KEY_PEPPER must be configured"):
        Settings(
            APP_ENV="production",
            JWT_SECRET="b" * 32,
            API_KEY_PEPPER="change-me-dev-only",
            DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
        )


def test_production_environment_accepts_strong_secrets():
    """Verify production environment succeeds with custom non-default secrets."""
    s = Settings(
        APP_ENV="production",
        JWT_SECRET="valid_random_jwt_secret_value_12345",
        API_KEY_PEPPER="valid_random_pepper_value_123456",
        DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
    )
    assert s.APP_ENV == "production"
    assert s.JWT_SECRET == "valid_random_jwt_secret_value_12345"


def test_export_openapi_utility(tmp_path):
    """Verify export_openapi writes valid JSON schema."""
    import json

    from app.tools.export_openapi import export_openapi

    target_file = tmp_path / "openapi.json"
    export_openapi(str(target_file))

    assert target_file.exists()
    with open(target_file, encoding="utf-8") as f:
        schema = json.load(f)
    assert schema["openapi"].startswith("3.")
    assert "/api/v1/products" in schema["paths"]
    assert "/readyz" in schema["paths"]
    assert "/healthz" in schema["paths"]
