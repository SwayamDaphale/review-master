"""Pydantic schemas for Ingestion API and Job Status responses."""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ListingIngestResponse(BaseModel):
    """Response returned upon accepting an extraction payload."""

    model_config = ConfigDict(from_attributes=True)

    ingestion_id: str = Field(description="Extraction record or job tracking identifier")
    job_id: uuid.UUID = Field(description="Asynchronous processing job identifier")
    status: str = Field(default="pending", description="Initial lifecycle status")
    contract_type: str = Field(description="Accepted contract identifier")
    schema_version: str = Field(description="Accepted contract schema version")
    duplicate: bool = Field(default=False, description="Whether this request replayed an existing job")
    created_at: str = Field(description="ISO-8601 creation timestamp")


class IngestionJobStatusResponse(BaseModel):
    """Safe, sanitized ingestion job status view."""

    model_config = ConfigDict(from_attributes=True)

    job_id: str
    job_type: str = "listing_ingestion"
    status: str
    user_id: str | None = None
    contract_type: str | None = None
    schema_version: str | None = None
    created_at: str | None = None
    completed_at: str | None = None
    error_summary: str | None = None
    result_summary: dict[str, Any] | None = None
