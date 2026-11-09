"""Canonical internal extraction representation for Review Master.

Provides a unified, contract-agnostic data structure into which all versioned
marketplace extraction payloads (legacy smartphone and generalized) are translated.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class CanonicalExtractedAttribute(BaseModel):
    """Category-independent typed attribute extracted from evidence."""

    attribute_key: str = Field(description="Attribute identifier matching B5 attribute registry")
    value_type: str = Field(default="string", description="Type: numeric, string, boolean, json")
    value: Any = Field(default=None, description="Typed value")
    original_value: str | None = Field(default=None, description="Raw source representation")
    original_unit: str | None = Field(default=None, description="Original observed unit")
    normalized_value: Any = Field(default=None, description="Canonical normalized numeric/string value")
    normalized_unit: str | None = Field(default=None, description="Canonical unit from Pint registry")
    confidence: Decimal | float = Field(default=1.0, description="Extraction confidence score (0.0 to 1.0)")
    source_reference: str | None = Field(default=None, description="Quote or label from raw evidence")


class CanonicalInternalExtraction(BaseModel):
    """Unified internal representation of an ingested marketplace listing snapshot."""

    # Ingestion provenance
    ingestion_record_id: str = Field(description="Unique record identifier")
    source_contract: str = Field(description="Originating contract name, e.g. smartphone_v1, generalized_v1")
    source_schema_version: str = Field(description="Originating schema version string, e.g. 1.0, 1.0.0")

    # Source metadata
    marketplace: str = Field(description="Marketplace identifier, e.g. amazon.in")
    page_type: str = Field(default="product_detail", description="Observed page type")
    product_category: str = Field(description="Product category, e.g. smartphone, laptop")
    product_url: str = Field(description="Target product page URL")
    extraction_method: str = Field(description="Method, e.g. browser_extension_user_initiated")
    extension_version: str = Field(description="Extension or client version")
    extracted_at: datetime = Field(description="Capture timestamp")
    asin: str | None = Field(default=None, description="Marketplace external identifier if available")
    page_title: str | None = Field(default=None, description="Browser tab / page title")

    # Raw evidence snapshot
    raw_title: str | None = None
    raw_brand: str | None = None
    raw_model: str | None = None
    raw_variant: str | None = None
    raw_price_text: str | None = None
    raw_rating_text: str | None = None
    raw_review_count_text: str | None = None
    raw_availability_text: str | None = None
    raw_specifications: list[dict[str, str]] = Field(default_factory=list)

    # Commercial normalized data
    price_amount: Decimal | None = None
    currency: str | None = "INR"
    rating: Decimal | None = None
    review_count: int | None = None
    availability: str | None = None

    # Identity hints
    normalized_brand: str | None = None
    normalized_model_name: str | None = None
    normalized_model_number: str | None = None

    # Typed attributes (category-independent)
    extracted_attributes: list[CanonicalExtractedAttribute] = Field(default_factory=list)

    # Validation diagnostics
    validation_status: str = Field(default="valid", description="valid, needs_review, invalid")
    identity_status: str = Field(default="identified", description="identified, probable, ambiguous, unmatched")
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    # Object storage linkage
    storage_object_key: str | None = None
    sha256_digest: str | None = None

    def get_attribute_value(self, key: str) -> Any:
        """Helper to get normalized value for an attribute key."""
        for attr in self.extracted_attributes:
            if attr.attribute_key == key:
                return attr.normalized_value if attr.normalized_value is not None else attr.value
        return None
