"""Pydantic schemas for Catalog Intelligence and Attribute Registry."""

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class UnitResponse(BaseModel):
    """Domain unit definition response."""

    key: str
    name: str
    symbol: str
    dimension: str
    canonical_unit: str
    conversion_factor: Decimal
    is_binary: bool
    is_active: bool


class AttributeDefinitionCreate(BaseModel):
    """Payload to define a new attribute in the registry."""

    key: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=128)
    category_id: uuid.UUID | None = None
    data_type: str = Field(
        default="string", description="string, numeric, boolean, json"
    )
    unit: str | None = None
    canonical_unit: str | None = None
    validation_rules: dict[str, Any] = Field(default_factory=dict)
    is_required: bool = False
    is_filterable: bool = True
    is_searchable: bool = False


class AttributeDefinitionResponse(BaseModel):
    """Attribute definition item."""

    id: uuid.UUID
    key: str
    name: str
    category_id: uuid.UUID | None
    data_type: str
    unit: str | None
    canonical_unit: str | None
    validation_rules: dict[str, Any]
    is_required: bool
    is_filterable: bool
    is_searchable: bool
    status: str


class SetVariantAttributeRequest(BaseModel):
    """Payload to assign a normalized attribute value to a variant."""

    attribute_id: uuid.UUID
    value_text: str | None = None
    value_numeric: Decimal | float | None = None
    value_boolean: bool | None = None
    value_json: dict[str, Any] | None = None
    original_unit: str | None = None
    canonical_unit: str | None = None
    confidence: Decimal | float | None = None
    evidence_id: uuid.UUID | None = None


class VariantAttributeValueResponse(BaseModel):
    """Normalized attribute value response."""

    id: uuid.UUID
    variant_id: uuid.UUID
    attribute_id: uuid.UUID
    attribute_key: str
    attribute_name: str
    value_text: str | None
    value_numeric: Decimal | None
    value_boolean: bool | None
    value_json: dict[str, Any] | None
    raw_value: str | None
    original_unit: str | None
    canonical_unit: str | None
    confidence: Decimal | None
    validation_status: str


class SpecificationSearchRequest(BaseModel):
    """Search request with specification and brand/category filters."""

    category_key: str | None = None
    brand: str | None = None
    query: str | None = None
    min_ram_gb: Decimal | float | None = None
    max_ram_gb: Decimal | float | None = None
    min_storage_gb: Decimal | float | None = None
    max_storage_gb: Decimal | float | None = None
    min_display_inch: Decimal | float | None = None
    max_display_inch: Decimal | float | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SearchVariantItem(BaseModel):
    """Variant in search results."""

    id: str
    sku_label: str
    configuration: dict[str, Any]
    config_hash: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class SearchProductResult(BaseModel):
    """Product in search results."""

    product_id: uuid.UUID
    product_name: str
    manufacturer: str
    category_key: str
    generation: str | None = None
    variants: list[SearchVariantItem] = Field(default_factory=list)


class SpecificationSearchResponse(BaseModel):
    """Search outcome with metadata."""

    total: int
    items: list[SearchProductResult]
    limit: int
    offset: int


class ValidationIssueResponse(BaseModel):
    """Itemized validation issue."""

    attribute_key: str
    issue_type: str
    message: str
    severity: str


class ValidationResponse(BaseModel):
    """Product or variant validation outcome."""

    target_id: uuid.UUID
    target_type: str
    status: str
    is_valid: bool
    issues: list[ValidationIssueResponse] = Field(default_factory=list)
    validated_attributes: dict[str, Any] = Field(default_factory=dict)
