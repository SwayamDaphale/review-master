"""Pydantic schemas for Variant domain entities."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VariantResponse(BaseModel):
    """Schema representing a product variant matching the OpenAPI Variant contract."""

    id: UUID
    product_id: UUID
    configuration: dict[str, Any]
    label: str = Field(
        description="Display label / SKU description of the configuration"
    )

    model_config = ConfigDict(from_attributes=True)
