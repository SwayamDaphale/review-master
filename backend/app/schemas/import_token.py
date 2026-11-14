"""Pydantic schemas for secure single-use import handoff tokens."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ImportTokenCreateRequest(BaseModel):
    """Request to generate a secure single-use import handoff code."""

    job_id: uuid.UUID | None = Field(
        default=None, description="Ingestion job ID associated with this handoff"
    )
    listing_id: uuid.UUID | None = Field(
        default=None, description="Listing ID associated with this handoff"
    )
    context_data: dict[str, Any] | None = Field(
        default=None, description="Optional lightweight metadata to bind to the handoff token"
    )


class ImportTokenCreateResponse(BaseModel):
    """Response containing the high-entropy single-use import token."""

    import_code: str = Field(
        description="High-entropy raw token for one-time exchange. Never persisted plain."
    )
    expires_at: datetime = Field(
        description="Expiration timestamp (short-lived, 15 minutes)"
    )


class ImportTokenConsumeRequest(BaseModel):
    """Request to consume a single-use import handoff code."""

    import_code: str = Field(
        min_length=16,
        max_length=128,
        description="The raw single-use import token to exchange"
    )


class ImportTokenConsumeResponse(BaseModel):
    """Outcome of successful atomic token consumption."""

    model_config = ConfigDict(from_attributes=True)

    status: str = "consumed"
    job_id: str | None = None
    listing_id: str | None = None
    context: str | None = None
    job_status: str | None = None
    payload: dict[str, Any] | None = None
    consumed_at: datetime

