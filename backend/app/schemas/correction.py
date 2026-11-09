"""Pydantic schemas for Administrative Catalog Corrections."""

import uuid
from typing import Any

from pydantic import BaseModel, Field


class CreateCatalogCorrectionRequest(BaseModel):
    """Payload to record an administrative catalog correction."""

    target_type: str = Field(
        description="'variant_attribute', 'product_identity', 'attribute_definition'"
    )
    target_id: uuid.UUID
    field_name: str
    before_value: dict[str, Any] | None = None
    after_value: dict[str, Any]
    reason: str = Field(
        min_length=5, max_length=1000, description="Audit justification for correction"
    )
    evidence_reference: str | None = None


class CatalogCorrectionResponse(BaseModel):
    """Catalog correction record."""

    id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    field_name: str
    before_value: dict[str, Any] | None
    after_value: dict[str, Any]
    reason: str
    actor_id: str
    evidence_reference: str | None
    created_at: str
