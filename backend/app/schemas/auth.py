"""Authentication schemas for request validation and response formatting."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserRegisterRequest(BaseModel):
    """Payload for user self-registration."""

    email: str = Field(min_length=3, max_length=255, description="User email address")
    password: str = Field(min_length=8, max_length=128, description="User password (min 8 chars)")
    display_name: str | None = Field(
        default=None, max_length=255, description="Optional public display name"
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Validate and normalize email address to lowercase stripped."""
        norm = v.strip().lower()
        if not EMAIL_REGEX.match(norm):
            raise ValueError("Invalid email address format.")
        return norm


class UserLoginRequest(BaseModel):
    """Payload for user email and password authentication."""

    email: str = Field(min_length=3, max_length=255, description="Registered email address")
    password: str = Field(min_length=1, max_length=128, description="User password")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Validate and normalize email address to lowercase stripped."""
        norm = v.strip().lower()
        if not EMAIL_REGEX.match(norm):
            raise ValueError("Invalid email address format.")
        return norm


class RefreshTokenRequest(BaseModel):
    """Payload for refresh token exchange when cookie is not used."""

    refresh_token: str | None = Field(
        default=None, description="Opaque refresh token (if not provided via cookie)"
    )


class UserResponse(BaseModel):
    """Safe public representation of user profile and roles."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None = None
    roles: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime


class AuthTokenResponse(BaseModel):
    """Token bundle issued upon successful authentication or refresh."""

    access_token: str = Field(description="Short-lived signed JWT access token")
    refresh_token: str = Field(description="Rotating opaque refresh token")
    csrf_token: str | None = Field(default=None, description="Anti-CSRF token for cookie authentication")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(default=900, description="Access token lifespan in seconds")
    user: UserResponse = Field(description="Authenticated user profile")


class LogoutResponse(BaseModel):
    """Response confirming session revocation."""

    status: str = Field(default="success")
    message: str = Field(default="Successfully logged out")
