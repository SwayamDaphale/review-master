"""Centralized configuration module for Review Master backend.

Loads configuration from environment variables and the root .env file
with deliberate path resolution, startup validation, and secret masking.
"""

import re
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Deliberately resolve the repository root and .env path
REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE_PATH = REPO_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings with strict validation and safe representation."""

    # Application & Environment
    APP_ENV: str = Field(
        default="development", description="Environment: development, test, production"
    )
    DEBUG: bool = Field(default=True, description="Debug mode flag")
    LOG_LEVEL: str = Field(
        default="info", description="Logging level: debug, info, warning, error"
    )
    API_BASE_URL: str = Field(
        default="http://localhost:8000", description="Public API base URL"
    )
    CORS_ORIGINS: list[str] | str = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        description="Allowed CORS origins for web and extension clients",
    )

    # Database & Storage
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/reviewmaster",
        description="Durable PostgreSQL database connection string",
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for caching and rate limiting",
    )

    # Core Security Secrets (Required in production)
    JWT_SECRET: str = Field(
        default="change-me-dev-only",
        description="Secret key for JWT token signatures",
    )
    API_KEY_PEPPER: str = Field(
        default="change-me-dev-only",
        description="Cryptographic pepper for API key hashing",
    )

    # Optional AI Provider API Keys (Empty defaults, populated if used)
    GOOGLE_API_KEY: str | None = Field(
        default=None, description="Google Gemini API key"
    )
    GEMINI_API_KEY: str | None = Field(default=None, description="Gemini alias API key")
    OPENAI_API_KEY: str | None = Field(default=None, description="OpenAI API key")
    ANTHROPIC_API_KEY: str | None = Field(default=None, description="Anthropic API key")
    GROQ_API_KEY: str | None = Field(default=None, description="Groq API key")

    # Pydantic Settings Configuration
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH if ENV_FILE_PATH.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @field_validator("CORS_ORIGINS")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Convert comma-separated origin strings into a list."""
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    def safe_database_url(self) -> str:
        """Return DATABASE_URL with user password redacted."""
        return re.sub(r":([^:@]+)@", ":***@", self.DATABASE_URL)

    def safe_summary(self) -> dict:
        """Return non-secret configuration summary suitable for startup logs."""
        return {
            "app_env": self.APP_ENV,
            "debug": self.DEBUG,
            "log_level": self.LOG_LEVEL,
            "api_base_url": self.API_BASE_URL,
            "cors_origins": self.CORS_ORIGINS,
            "database_url": self.safe_database_url(),
            "redis_configured": bool(self.REDIS_URL),
            "jwt_secret_configured": bool(
                self.JWT_SECRET and self.JWT_SECRET != "change-me-dev-only"
            ),
            "has_google_key": bool(self.GOOGLE_API_KEY or self.GEMINI_API_KEY),
            "has_openai_key": bool(self.OPENAI_API_KEY),
            "has_anthropic_key": bool(self.ANTHROPIC_API_KEY),
            "has_groq_key": bool(self.GROQ_API_KEY),
        }

    def __repr__(self) -> str:
        """Mask credentials from string representations."""
        return f"<Settings env={self.APP_ENV} db={self.safe_database_url()}>"


# Global settings singleton
settings = Settings()
