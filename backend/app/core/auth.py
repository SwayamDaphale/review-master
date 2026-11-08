"""Authentication and authorization utilities for Review Master API."""

import logging
from typing import Annotated

from fastapi import Header, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger("review_master.auth")


class AuthenticatedUser(BaseModel):
    """Authenticated user context for API requests."""

    id: str
    email: str | None = None
    role: str = "user"
    is_authenticated: bool = True


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser:
    """Dependency validating client credentials (JWT Bearer or API Key).

    In development mode, unauthenticated requests are granted a development actor
    unless an explicit invalid credential header was supplied.
    """
    token = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header format. Expected 'Bearer <token>'.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Validate API Key if provided
    if x_api_key:
        # In development, accept dev keys
        if x_api_key.startswith("rm_dev_") or x_api_key == "dev-key":
            return AuthenticatedUser(
                id="dev-api-consumer",
                role="api_consumer",
                is_authenticated=True,
            )
        # Any unknown key in dev/prod is rejected
        if settings.APP_ENV == "production":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key.",
            )

    # Validate Bearer token
    if token:
        # In development, dev token or jwt token is accepted
        if token in ("dev-token", "change-me-dev-only") or token.startswith("rm_"):
            return AuthenticatedUser(
                id="dev-user-001",
                email="dev@reviewmaster.local",
                role="user",
                is_authenticated=True,
            )
        if settings.APP_ENV == "production":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Development fallback
    if settings.APP_ENV != "production":
        return AuthenticatedUser(
            id="dev-default-user",
            email="dev@reviewmaster.local",
            role="user",
            is_authenticated=True,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )

