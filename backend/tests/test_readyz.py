"""Tests for the readiness probe (/readyz)."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


def test_readyz_when_database_is_healthy():
    """GET /readyz returns 200 OK when database is accessible."""
    with (
        TestClient(app) as client,
        patch("app.main.engine.connect") as mock_connect,
    ):
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn

        response = client.get("/readyz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["checks"]["database"] == "ok"


def test_readyz_when_database_is_unreachable():
    """GET /readyz returns 503 Service Unavailable when database fails."""
    with (
        TestClient(app) as client,
        patch("app.main.engine.connect", side_effect=OSError("Connection refused")),
    ):
        response = client.get("/readyz")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unavailable"
        assert "error: OSError" in data["checks"]["database"]
