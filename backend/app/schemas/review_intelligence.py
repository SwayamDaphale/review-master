"""Pydantic schemas for Review Intelligence API."""

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class AnalyzeReviewRequest(BaseModel):
    """Payload to request single review analysis."""

    review_text: str = Field(
        min_length=10, max_length=10000, description="Customer review content"
    )
    product_id: uuid.UUID | None = None
    variant_id: uuid.UUID | None = None
    source_evidence_id: uuid.UUID | None = None
    review_source_id: str | None = None
    idempotency_key: str | None = None


class AspectOpinionResponse(BaseModel):
    """Aspect opinion view."""

    aspect_key: str
    polarity: str
    claim: str
    raw_quote: str | None
    confidence: Decimal


class ProConResponse(BaseModel):
    """Pro/con view."""

    item_type: str
    text: str
    aspect_key: str | None


class ReviewAnalysisResponse(BaseModel):
    """Analysis result response."""

    id: uuid.UUID
    product_id: uuid.UUID | None
    variant_id: uuid.UUID | None
    sentiment: str
    sentiment_confidence: Decimal
    provider: str
    model: str
    prompt_version: str
    status: str
    error_message: str | None = None
    aspect_opinions: list[AspectOpinionResponse] = Field(default_factory=list)
    pros_cons: list[ProConResponse] = Field(default_factory=list)
    created_at: str


class ReviewSummaryResponse(BaseModel):
    """Aggregated product review summary."""

    id: uuid.UUID
    product_id: uuid.UUID
    variant_id: uuid.UUID | None
    summary_text: str
    total_reviews_analyzed: int
    sentiment_distribution: dict[str, int]
    aspect_summaries: dict[str, Any]
    key_pros: list[str]
    key_cons: list[str]
    confidence: Decimal
    provider: str
    model: str
    version: int
    created_at: str


class JobStatusResponse(BaseModel):
    """Sanitized, safe status response for background review analysis jobs."""

    job_id: uuid.UUID
    job_type: str
    status: str
    created_at: str | None = None
    completed_at: str | None = None
    error_summary: str | None = None
    result_summary: dict[str, Any] | None = None


class AnalyzeReviewJobResponse(BaseModel):
    """Initial response returned upon accepting an asynchronous review analysis job."""

    job_id: uuid.UUID
    job_type: str = "review_analysis"
    status: str = "pending"
    idempotency_key: str
    created_at: str | None = None
