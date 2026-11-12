"""Comparison schemas for sessions, item management, and category comparison matrices."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateComparisonSessionRequest(BaseModel):
    """Payload to create comparison session."""

    title: str | None = Field(default=None, max_length=255)
    category_id: uuid.UUID | None = None


class AddComparisonVariantRequest(BaseModel):
    """Payload to add a variant to a comparison session."""

    variant_id: uuid.UUID
    position: int | None = None


class ComparisonItemSchema(BaseModel):
    """Comparison item representation."""

    id: uuid.UUID
    session_id: uuid.UUID
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    position: int
    created_at: datetime
    product_name: str | None = None
    sku_label: str | None = None


class ComparisonSessionSchema(BaseModel):
    """Comparison session representation."""

    id: uuid.UUID
    user_id: uuid.UUID | None = None
    anonymous_session_token: str | None = None
    title: str | None = None
    status: str
    category_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    items: list[ComparisonItemSchema] = []


class ComparisonSpecificationRow(BaseModel):
    """Attribute specification value for a product variant."""

    key: str
    display_label: str
    raw_value: Any | None = None
    canonical_value: Any | None = None
    unit: str | None = None
    is_missing: bool = False


class ComparisonEvaluationParameter(BaseModel):
    """Parameter score from persisted evaluation."""

    key: str
    name: str
    score: float | None = None
    status: str
    weight: float | None = None
    is_critical: bool = False
    trust_tier: str | None = None
    limitations: dict[str, Any] | None = None


class ComparisonEvaluationSummary(BaseModel):
    """Separated evaluation quality dimension."""

    evaluation_id: uuid.UUID | None = None
    model_version_id: uuid.UUID | None = None
    model_version: str | None = None
    overall_score: float | None = None
    confidence_state: str = "unavailable"
    confidence_score: float | None = None
    coverage: float | None = None
    limitations: dict[str, Any] | None = None
    parameters: list[ComparisonEvaluationParameter] = []


class ComparisonOfferSummary(BaseModel):
    """Separated commercial offer and pricing dimension."""

    current_price: float | None = None
    currency: str | None = "INR"
    seller: str | None = None
    availability: str | None = None
    observed_at: datetime | None = None
    is_stale: bool = False
    is_available: bool = False


class ComparisonCommunitySummary(BaseModel):
    """Separated community and review intelligence dimension."""

    total_reviews_analyzed: int = 0
    sentiment_distribution: dict[str, int] = {}
    key_pros: list[str] = []
    key_cons: list[str] = []
    summary_text: str | None = None


class ComparisonMatrixItem(BaseModel):
    """Side-by-side variant column in the comparison matrix."""

    variant_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    manufacturer: str
    sku_label: str
    position: int
    specifications: dict[str, ComparisonSpecificationRow] = {}
    evaluation: ComparisonEvaluationSummary
    offer: ComparisonOfferSummary
    community: ComparisonCommunitySummary


class ComparisonMatrixResponse(BaseModel):
    """Complete category-aware comparison matrix response."""

    session_id: uuid.UUID
    title: str | None = None
    status: str
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    category_key: str | None = None
    item_count: int
    specification_keys: list[dict[str, str]] = []  # [{"key": "ram", "label": "RAM"}]
    items: list[ComparisonMatrixItem] = []
