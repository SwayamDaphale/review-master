"""Pydantic schemas for Category domain entities."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CategoryResponse(BaseModel):
    """Schema representing a product category."""

    id: UUID
    key: str
    name: str
    schema_version: str
    spec_schema: dict[str, Any] | None = None
    status: str

    model_config = ConfigDict(from_attributes=True)
