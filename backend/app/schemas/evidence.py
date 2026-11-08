"""Pydantic schemas for evidence, provenance, and historical versions."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class EvidenceVersionResponse(BaseModel):
    """Historical version of an evidence record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    value: dict[str, Any]
    unit: str | None = None
    observed_at: datetime
    methodology: str | None = None
    verification_state: str
    source_url: str | None = None
    raw_source_span: str | None = None
    extraction_record_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    created_at: datetime
    withdrawn_at: datetime | None = None


class EvidenceResponse(BaseModel):
    """Evidence item attached to a canonical variant or product."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID | None = None
    variant_id: uuid.UUID | None = None
    parameter_key: str
    source_type: str
    trust_tier: int
    visibility: str
    current_version_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    versions: list[EvidenceVersionResponse] = []


class EvidenceListResponse(BaseModel):
    """Collection envelope for evidence queries."""

    total: int
    items: list[EvidenceResponse]

