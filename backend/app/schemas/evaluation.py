"""Pydantic schemas for deterministic evaluation models, versions, and calculation results."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvaluationModelCreateRequest(BaseModel):
    """Payload to create a new category evaluation model in draft status."""

    category_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None


class EvaluationModelVersionCreateRequest(BaseModel):
    """Payload to add a new version to an existing evaluation model."""

    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    definition: dict[str, Any]


class EvaluationModelVersionResponse(BaseModel):
    """Evaluation model version response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    model_id: uuid.UUID
    version: str
    status: str
    definition: dict[str, Any]
    configuration_hash: str | None = None
    approved_by: str | None = None
    published_at: datetime | None = None
    created_at: datetime


class EvaluationModelResponse(BaseModel):
    """Top-level evaluation model response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: str | None = None
    status: str
    active_version_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    versions: list[EvaluationModelVersionResponse] = []


class EvaluationModelListResponse(BaseModel):
    """Collection envelope for evaluation models."""

    total: int
    items: list[EvaluationModelResponse]


class ParameterResultResponse(BaseModel):
    """Parameter-level score outcome."""

    model_config = ConfigDict(from_attributes=True)

    parameter_key: str
    score: Decimal | None = None
    status: str
    weight: Decimal | None = None
    effective_weight: Decimal | None = None
    is_critical: bool = False
    evidence_ids: list[str] = []
    evidence_version_ids: list[str] = []
    raw_input_value: Any | None = None
    normalized_value: Any | None = None
    scoring_rule: str | None = None
    explanation_data: dict[str, Any] | None = None


class EvaluationResponse(BaseModel):
    """Deterministic evaluation outcome envelope."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_id: uuid.UUID
    model_version_id: uuid.UUID | None = None
    overall_score: Decimal | None = None
    confidence_state: str
    confidence_score: Decimal | None = None
    coverage: Decimal | None = None
    limitations: dict[str, Any] | None = None
    evidence_snapshot_hash: str | None = None
    configuration_hash: str | None = None
    input_fingerprint: str | None = None
    output_fingerprint: str | None = None
    calculation_policy_version: str | None = None
    created_at: datetime
    parameter_results: list[ParameterResultResponse] = []


class EvaluationListResponse(BaseModel):
    """Collection envelope for variant evaluation history."""

    total: int
    items: list[EvaluationResponse]

