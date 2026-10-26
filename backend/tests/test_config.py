"""Tests for centralized configuration and secret redaction."""

from app.core.config import Settings


def test_settings_default_values():
    """Verify default configuration values."""
    s = Settings(
        APP_ENV="test",
        DATABASE_URL="postgresql+psycopg://user:super_secret_pw@localhost:5432/testdb",
        JWT_SECRET="my_secret_token",
    )
    assert s.APP_ENV == "test"
    assert s.DEBUG is True
    assert "user" in s.DATABASE_URL


def test_settings_redacts_password_in_safe_url():
    """Ensure safe_database_url redacts passwords."""
    s = Settings(
        DATABASE_URL="postgresql+psycopg://postgres:secret_pass123@postgres:5432/reviewmaster"
    )
    safe = s.safe_database_url()
    assert "secret_pass123" not in safe
    assert ":***@" in safe


def test_settings_repr_does_not_leak_secrets():
    """Ensure string representation masks credentials."""
    s = Settings(
        DATABASE_URL="postgresql+psycopg://admin:very_secret@localhost:5432/db",
        JWT_SECRET="unexposed_jwt_token",
        API_KEY_PEPPER="unexposed_pepper",
    )
    rep = repr(s)
    assert "very_secret" not in rep
    assert "unexposed_jwt_token" not in rep
    assert "unexposed_pepper" not in rep


def test_cors_origins_parsing():
    """Ensure comma-separated string parses into list."""
    s = Settings(CORS_ORIGINS="http://localhost:3000, http://localhost:5173")
    assert s.CORS_ORIGINS == ["http://localhost:3000", "http://localhost:5173"]
