"""Generalized Versioned Extraction Contract (Generalized V1).

Category-independent, extensible schema for marketplace product extractions.
Supports arbitrary product categories without hardcoding smartphone-only attributes.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GeneralizedSpecificationItem(BaseModel):
    """Raw label/value specification pair extracted from page DOM."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    value: str


class GeneralizedContractMetadata(BaseModel):
    """Contract versioning and record identity metadata."""

    model_config = ConfigDict(extra="forbid")

    contract_type: Literal["generalized_extraction"] = "generalized_extraction"
    schema_version: Literal["1.0", "1.0.0"] = "1.0"
    record_id: str | None = Field(default=None, description="Client-generated unique UUID")
    captured_at: datetime = Field(description="Capture timestamp in ISO-8601")


class GeneralizedSourceMetadata(BaseModel):
    """Origin, client, and page location provenance."""

    model_config = ConfigDict(extra="forbid")

    marketplace: str = Field(description="Marketplace identifier, e.g. amazon.in")
    page_type: str = Field(default="product_detail", description="Page type, e.g. product_detail")
    product_url: str = Field(description="Normalized product listing URL")
    extraction_method: str = Field(
        default="browser_extension_user_initiated",
        description="Method used for extraction",
    )
    extension_version: str = Field(min_length=1, description="Extension/client release version")
    page_title: str | None = Field(default=None, description="DOM title of the extracted page")


class GeneralizedProductContext(BaseModel):
    """Contextual product hints for catalog identity resolution."""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=2, description="Target product category, e.g. smartphone, laptop")
    external_id: str | None = Field(default=None, description="Marketplace identifier (e.g. ASIN, SKU)")
    brand_hint: str | None = None
    model_hint: str | None = None
    variant_hint: str | None = None


class GeneralizedRawEvidence(BaseModel):
    """Verbatim un-normalized evidence captured from the marketplace page."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    raw_text: str | None = None
    raw_price_text: str | None = None
    raw_rating_text: str | None = None
    raw_review_count_text: str | None = None
    raw_availability_text: str | None = None
    specifications: list[GeneralizedSpecificationItem] = Field(default_factory=list)


class GeneralizedAttributeValue(BaseModel):
    """Category-independent typed attribute extracted from evidence."""

    model_config = ConfigDict(extra="forbid")

    attribute_key: str = Field(min_length=1, description="Registered attribute key")
    value_type: Literal["numeric", "string", "boolean", "json"] = "string"
    value: Any = Field(description="Extracted value matching value_type")
    original_value: str | None = None
    original_unit: str | None = None
    normalized_value: Any = None
    normalized_unit: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_reference: str | None = None


class GeneralizedExtractedData(BaseModel):
    """Extracted commercial data and typed attribute collection."""

    model_config = ConfigDict(extra="forbid")

    price_amount: float | None = Field(default=None, ge=0)
    currency: str | None = "INR"
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    availability: str | None = None
    attributes: list[GeneralizedAttributeValue] = Field(default_factory=list)


class GeneralizedValidationDiagnostics(BaseModel):
    """Diagnostics, warnings, and validation outcome."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["valid", "needs_review", "invalid"]
    identity_status: Literal["identified", "probable", "ambiguous", "unmatched"] = "identified"
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class GeneralizedExtractionV1Payload(BaseModel):
    """Root model for the Generalized Extraction V1 Contract."""

    model_config = ConfigDict(extra="forbid")

    contract: GeneralizedContractMetadata
    source: GeneralizedSourceMetadata
    product_context: GeneralizedProductContext
    raw_evidence: GeneralizedRawEvidence
    extracted_data: GeneralizedExtractedData
    validation: GeneralizedValidationDiagnostics
