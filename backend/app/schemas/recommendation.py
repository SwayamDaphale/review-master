"""Pydantic v2 schemas for requirement extraction, hard constraints, and recommendations."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConstraintOperator(str, Enum):
    """Supported comparison operators for hard constraints."""

    EQ = "=="
    NE = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    IN = "in"


class ConstraintOutcome(str, Enum):
    """Three-valued constraint validation outcome."""

    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class HardConstraint(BaseModel):
    """Mandatory requirement filter condition."""

    attribute_key: str
    operator: str = ">="
    target_value: Any
    unit: str | None = None
    description: str | None = None


class SoftPreference(BaseModel):
    """Soft preference or usage intent."""

    preference_key: str
    preferred_direction: str = "higher"  # "higher", "lower", "preferred"
    weight: float = 1.0
    description: str | None = None


class ParsedRequirements(BaseModel):
    """Structured, typed requirement contract extracted from user prompt or structured form."""

    raw_query: str | None = None
    category_key: str = "smartphone"  # "smartphone", "laptop", "external_ssd"
    budget_max: float | None = None
    budget_currency: str = "INR"
    hard_constraints: list[HardConstraint] = []
    soft_preferences: list[SoftPreference] = []
    required_attributes: list[str] = []
    excluded_brands: list[str] = []
    ambiguities: list[str] = []
    extraction_confidence: float = 1.0
    parser_version: str = "v1"
    extraction_source: str = "deterministic_fallback"


class RequirementParseRequest(BaseModel):
    """User input for requirement extraction."""

    query: str = Field(min_length=3, max_length=1000)
    category_hint: str | None = None


class RequirementParseResponse(BaseModel):
    """Structured response from requirement parser."""

    requirements: ParsedRequirements
    clarifications_needed: list[str] = []
    unsupported_attributes: list[str] = []


class ConstraintEvaluationDetail(BaseModel):
    """Individual constraint check result for a candidate product."""

    attribute_key: str
    operator: str
    target_value: Any
    actual_value: Any | None = None
    unit: str | None = None
    outcome: ConstraintOutcome
    reason: str


class CandidateEvaluationOutcome(BaseModel):
    """Complete constraint assessment for a candidate product variant."""

    variant_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    sku_label: str
    is_eligible: bool
    constraints: list[ConstraintEvaluationDetail] = []
    exclusion_reasons: list[str] = []


class RecommendedProductItem(BaseModel):
    """Eligible ranked recommendation item with separated dimensions."""

    rank: int
    variant_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    manufacturer: str
    sku_label: str
    overall_score: float | None = None
    confidence_state: str = "unavailable"
    confidence_score: float | None = None
    coverage: float | None = None
    current_price: float | None = None
    currency: str | None = "INR"
    evaluation_id: uuid.UUID | None = None
    model_version_id: uuid.UUID | None = None
    model_version: str | None = None
    explanation: str
    explanation_evidence: dict[str, Any] = {}
    verified_specifications: dict[str, Any] = {}
    community_summary: str | None = None


class ExcludedProductItem(BaseModel):
    """Ineligible candidate excluded from ranking due to FAIL or UNKNOWN constraint."""

    variant_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    sku_label: str
    failed_constraints: list[str] = []
    unknown_constraints: list[str] = []
    reasons: list[str] = []


class RecommendationRequest(BaseModel):
    """Request payload to generate recommendations."""

    query: str | None = None
    requirements: ParsedRequirements | None = None
    category_id: uuid.UUID | None = None
    category_key: str | None = None
    force_recalculate_evaluations: bool = False
    limit: int = Field(default=5, ge=1, le=20)


class RecommendationResponse(BaseModel):
    """Complete recommendation response with ranked results, exclusions, and audit fingerprints."""

    recommendation_id: uuid.UUID
    category_id: uuid.UUID
    category_key: str
    query: str | None = None
    parsed_requirements: ParsedRequirements
    eligible_count: int
    ineligible_count: int
    ranked_recommendations: list[RecommendedProductItem] = []
    excluded_candidates: list[ExcludedProductItem] = []
    ranking_policy_version: str = "v1"
    model_version_id: uuid.UUID | None = None
    model_version: str | None = None
    input_fingerprint: str
    output_fingerprint: str
    created_at: datetime
