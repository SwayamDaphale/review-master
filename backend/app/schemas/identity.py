"""Pydantic schemas for identity resolution, external mappings, and review queues."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExternalIdentityMappingCreate(BaseModel):
    """Payload to create or link an external identity mapping."""

    marketplace_id: uuid.UUID
    external_id_type: str = Field(default="asin", max_length=32)
    external_id_value: str = Field(max_length=64)
    product_id: uuid.UUID | None = None
    variant_id: uuid.UUID | None = None
    mapping_status: str = Field(default="active", max_length=32)
    verification_status: str = Field(default="verified", max_length=32)
    confidence_score: float | None = Field(default=1.0, ge=0.0, le=1.0)
    provenance: dict[str, Any] | None = None


class ExternalIdentityMappingResponse(BaseModel):
    """External identity mapping response entity."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    marketplace_id: uuid.UUID
    external_id_type: str
    external_id_value: str
    product_id: uuid.UUID | None = None
    variant_id: uuid.UUID | None = None
    mapping_status: str
    verification_status: str
    confidence_score: float | None = None
    provenance: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class ExternalIdentityMappingListResponse(BaseModel):
    """Collection envelope for external identity mappings."""

    total: int
    items: list[ExternalIdentityMappingResponse]


class IdentityReviewQueueResponse(BaseModel):
    """Identity review queue item details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    record_id: str | None = None
    marketplace_id: uuid.UUID | None = None
    asin: str | None = None
    raw_title: str | None = None
    candidate_product_ids: list[str] | None = None
    candidate_variant_ids: list[str] | None = None
    candidate_scores: dict[str, Any] | None = None
    conflicting_attributes: dict[str, Any] | None = None
    matching_reasons: list[str] | None = None
    status: str
    assigned_reviewer_id: uuid.UUID | None = None
    reviewer_decision: str | None = None
    decision_reason: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class IdentityReviewQueueListResponse(BaseModel):
    """Collection envelope for identity review queue."""

    total: int
    items: list[IdentityReviewQueueResponse]


class IdentityReviewApproveRequest(BaseModel):
    """Request payload to approve an identity review item."""

    decision: str = Field(
        ...,
        description="Decision type: link_product, link_variant, create_new",
    )
    product_id: uuid.UUID | None = None
    variant_id: uuid.UUID | None = None
    reason: str = Field(..., min_length=3, max_length=1000)


class IdentityReviewRejectRequest(BaseModel):
    """Request payload to reject an identity review item."""

    reason: str = Field(..., min_length=3, max_length=1000)


class IdentityResolveRequest(BaseModel):
    """Request payload to resolve identity for a listing."""

    marketplace_code: str = Field(default="amazon.in", max_length=64)
    asin: str = Field(max_length=64)
    category: str = Field(default="smartphone", max_length=64)
    title: str | None = None
    brand: str | None = None
    model_name: str | None = None
    model_number: str | None = None
    ram_gb: float | None = None
    storage_gb: float | None = None


class IdentityResolveResponse(BaseModel):
    """Outcome of identity resolution endpoint."""

    match_state: str
    confidence: float
    product_id: uuid.UUID | None = None
    variant_id: uuid.UUID | None = None
    product_name: str | None = None
    variant_label: str | None = None
    reasons: list[str] = []
    review_queue_id: uuid.UUID | None = None
    candidate_scores: dict[str, float] | None = None
    product_fingerprint: str | None = None
    variant_fingerprint: str | None = None

