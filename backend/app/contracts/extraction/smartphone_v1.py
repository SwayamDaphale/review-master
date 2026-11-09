"""Frozen Smartphone V1 Contract Pydantic Schema.

Matches smartphone-extraction-1.0.schema.json strictly with additionalProperties forbidden.
Accepts schema_version '1.0' and '1.0.0'.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SpecificationItem(BaseModel):
    """Raw label/value specification pair extracted from marketplace."""

    model_config = ConfigDict(extra="forbid")

    label: str
    value: str


class RawSmartphoneExtraction(BaseModel):
    """Verbatim text extracted from the Amazon India product listing."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    brand_text: str | None = None
    model_text: str | None = None
    variant_text: str | None = None
    price_text: str | None = None
    rating_text: str | None = None
    review_count_text: str | None = None
    availability_text: str | None = None
    specifications_text: list[SpecificationItem]


class ExtractionSource(BaseModel):
    """Provenance and origin metadata for an extraction."""

    model_config = ConfigDict(extra="forbid")

    marketplace: Literal["amazon.in"]
    product_url: str
    extracted_at: datetime
    extraction_method: Literal["browser_extension_user_initiated"]
    extension_version: str
    page_title: str | None = None
    asin: str | None = Field(default=None, pattern=r"^[A-Z0-9]{10}$")


class NormalizedSmartphone(BaseModel):
    """Normalized technical and commercial specifications."""

    model_config = ConfigDict(extra="forbid")

    category: Literal["smartphone"]
    brand: str | None = None
    model_name: str | None = None
    model_number: str | None = None
    ram_gb: float | None = Field(default=None, gt=0)
    storage_gb: float | None = Field(default=None, gt=0)
    display_size_inches: float | None = Field(default=None, gt=0)
    battery_capacity_mah: int | None = Field(default=None, gt=0)
    operating_system: str | None = None
    processor: str | None = None
    supports_5g: bool | None = None
    price_amount: float | None = Field(default=None, ge=0)
    currency: Literal["INR"] | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    availability: Literal["in_stock", "out_of_stock", "unknown"] | None = None


class ExtractionValidation(BaseModel):
    """Client-side validation assessment and warning diagnostics."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["valid", "needs_review", "invalid"]
    identity_status: Literal["identified", "probable", "ambiguous", "unmatched"]
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class SmartphoneExtractionV1Payload(BaseModel):
    """Top-level frozen contract payload matching smartphone-extraction-1.0.schema.json.

    Supports both '1.0' and '1.0.0' version identifiers.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "1.0.0"]
    record_id: str | None = None
    source: ExtractionSource
    raw_extraction: RawSmartphoneExtraction
    normalized: NormalizedSmartphone
    validation: ExtractionValidation

