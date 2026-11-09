"""Centralized configuration module for Review Master backend.

Loads configuration from environment variables and the root .env file
with deliberate path resolution, startup validation, and secret masking.
"""

import re
from pathlib import Path

from pydantic import Field, field_validator, model_validator
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
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/1",
        description="Celery message broker URL",
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/2",
        description="Celery task result backend URL",
    )

    # Object Storage (SeaweedFS / S3 Compatible)
    S3_ENDPOINT_URL: str = Field(
        default="http://localhost:8333",
        description="S3 / SeaweedFS endpoint URL",
    )
    S3_REGION: str = Field(
        default="us-east-1",
        description="S3 region identifier",
    )
    S3_BUCKET_EVIDENCE: str = Field(
        default="rm-evidence",
        description="Evidence bucket name",
    )
    S3_ACCESS_KEY: str = Field(
        default="devaccess",
        description="S3 access key",
    )
    S3_SECRET_KEY: str = Field(
        default="devsecret",
        description="S3 secret key",
    )

    # Core Security Secrets (Required in production)
    JWT_SECRET: str = Field(
        default="change-me-dev-only-32-byte-secret-key-1234",
        description="Secret key for JWT token signatures",
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT signing algorithm (HS256 for symmetric key)",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=15,
        description="Access token lifespan in minutes",
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        description="Refresh token lifespan in days",
    )
    API_KEY_PEPPER: str = Field(
        default="change-me-dev-only",
        description="Cryptographic pepper for API key hashing",
    )

    # Optional AI Provider API Keys & LLM Orchestration
    GOOGLE_API_KEY: str | None = Field(
        default=None, description="Google Gemini API key"
    )
    GEMINI_API_KEY: str | None = Field(default=None, description="Gemini alias API key")
    OPENAI_API_KEY: str | None = Field(default=None, description="OpenAI API key")
    ANTHROPIC_API_KEY: str | None = Field(default=None, description="Anthropic API key")
    GROQ_API_KEY: str | None = Field(default=None, description="Groq API key")
    NVIDIA_API_KEY: str | None = Field(default=None, description="NVIDIA NIM API key")

    GROQ_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="Default Groq LLM model identifier",
    )
    NVIDIA_MODEL: str = Field(
        default="meta/llama-3.3-70b-instruct",
        description="Default NVIDIA NIM LLM model identifier",
    )
    LLM_PRIMARY_PROVIDER: str = Field(
        default="groq",
        description="Primary LLM inference provider: 'groq' or 'nvidia'",
    )
    LLM_FALLBACK_ENABLED: bool = Field(
        default=True,
        description="Enable automatic failover to backup provider",
    )
    LLM_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        description="Timeout per LLM request in seconds",
    )
    LLM_MAX_RETRIES: int = Field(
        default=2,
        description="Maximum retry attempts for transient provider failures",
    )

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

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Enforce strong credentials in production environment."""
        if self.APP_ENV == "production":
            insecure_defaults = {
                "change-me-dev-only",
                "change-me-dev-only-32-byte-secret-key-1234",
                "",
                None,
            }
            if self.JWT_SECRET in insecure_defaults:
                raise ValueError(
                    "JWT_SECRET must be configured with a secure random secret in production."
                )
            if self.API_KEY_PEPPER in insecure_defaults:
                raise ValueError(
                    "API_KEY_PEPPER must be configured with a secure random secret in production."
                )
        return self

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
            "has_nvidia_key": bool(self.NVIDIA_API_KEY),
            "primary_provider": self.LLM_PRIMARY_PROVIDER,
            "fallback_enabled": self.LLM_FALLBACK_ENABLED,
        }

    def __repr__(self) -> str:
        """Mask credentials from string representations."""
        return f"<Settings env={self.APP_ENV} db={self.safe_database_url()}>"


# Global settings singleton
settings = Settings()
