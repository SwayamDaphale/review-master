"""Pydantic schemas for AI-driven structured attribute enrichment and extraction."""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EnrichedAttributeItem(BaseModel):
    """Grounding-backed individual extracted attribute."""

    model_config = ConfigDict(extra="ignore")

    attribute_key: str = Field(description="Canonical attribute identifier, e.g. 'ram', 'battery', 'storage'")
    value: str | float | int | bool = Field(description="Extracted attribute value")
    unit: str | None = Field(default=None, description="Physical unit if applicable, e.g. 'GB', 'mAh', 'inches'")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    source_quote: str = Field(description="Exact snippet or sentence from raw evidence backing this extraction")


class EnrichedProductAttributes(BaseModel):
    """Structured container of extracted product attributes with evidence provenance."""

    model_config = ConfigDict(extra="ignore")

    product_title: str | None = Field(default=None, description="Inferred product title")
    brand: str | None = Field(default=None, description="Inferred brand name")
    model: str | None = Field(default=None, description="Inferred model designation")
    attributes: list[EnrichedAttributeItem] = Field(default_factory=list, description="List of validated attributes")
    summary: str | None = Field(default=None, description="High-level extraction narrative")


class StructuredReviewSummary(BaseModel):
    """Structured synthetic summary extracted from review clusters."""

    model_config = ConfigDict(extra="ignore")

    overall_summary: str = Field(description="Executive summary of user sentiment and experience")
    key_strengths: list[str] = Field(default_factory=list, description="Verified recurring strengths")
    key_drawbacks: list[str] = Field(default_factory=list, description="Verified recurring flaws or drawbacks")
    consensus_verdict: str | None = Field(default=None, description="Overall conclusion")
    buyer_recommendation: str | None = Field(default=None, description="Specific buying guidance")


class AttributeExtractionRequest(BaseModel):
    """Input payload for attribute enrichment background execution."""

    product_id: uuid.UUID | None = None
    variant_id: uuid.UUID | None = None
    source_evidence_id: uuid.UUID | None = None
    raw_text: str = Field(min_length=1, max_length=50000)
    context_metadata: dict[str, Any] = Field(default_factory=dict)

