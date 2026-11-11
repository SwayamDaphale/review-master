"""Pydantic schemas for evidence, provenance, historical versions, conflicts, and verification."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class EvidenceVerifyRequest(BaseModel):
    """Payload to transition evidence verification status."""

    verification_state: str = Field(
        ...,
        description="Target verification state: unverified, verified, rejected, conflicting, superseded",
    )
    reason: str = Field(..., min_length=3, max_length=1000)
    supporting_evidence_id: uuid.UUID | None = None


class EvidenceConflictResponse(BaseModel):
    """Conflicting evidence records item."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parameter_key: str
    existing_value: dict[str, Any]
    conflicting_value: dict[str, Any]
    existing_unit: str | None = None
    conflicting_unit: str | None = None
    existing_evidence_id: uuid.UUID | None = None
    incoming_evidence_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    variant_id: uuid.UUID | None = None
    status: str
    resolved_by: uuid.UUID | None = None
    resolution_decision: str | None = None
    resolution_reason: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class EvidenceConflictListResponse(BaseModel):
    """Collection envelope for evidence conflicts."""

    total: int
    items: list[EvidenceConflictResponse]


class EvidenceConflictResolveRequest(BaseModel):
    """Payload to resolve an open evidence conflict."""

    resolution_decision: str = Field(
        ...,
        description="Resolution decision: accept_incoming, keep_existing, supersede_both",
    )
    resolution_reason: str = Field(..., min_length=3, max_length=1000)


class EvidenceVerificationHistoryResponse(BaseModel):
    """Audit entry for evidence verification lifecycle transition."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evidence_id: uuid.UUID
    previous_status: str
    new_status: str
    actor_id: uuid.UUID | None = None
    actor_role: str
    reason: str
    supporting_evidence_id: uuid.UUID | None = None
    created_at: datetime


class EvidenceVerificationHistoryListResponse(BaseModel):
    """Collection envelope for evidence verification history."""

    total: int
    items: list[EvidenceVerificationHistoryResponse]
