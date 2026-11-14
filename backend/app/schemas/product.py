"""Pydantic schemas for Product catalog listings and details."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.variant import VariantResponse


class ProductResponse(BaseModel):
    """Schema representing a canonical product matching the OpenAPI Product contract."""

    id: UUID
    name: str
    manufacturer: str
    category: str = Field(description="Category key identifier, e.g. 'smartphone'")
    generation: str | None = None
    mpn: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ProductDetailResponse(BaseModel):
    """Detailed canonical product representation with attached variants."""

    product: ProductResponse
    variants: list[VariantResponse]

    model_config = ConfigDict(from_attributes=True)


class VariantDetailResponse(BaseModel):
    """Canonical variant and its parent product."""

    variant: VariantResponse
    product: ProductResponse

    model_config = ConfigDict(from_attributes=True)


class ProductSearchResult(BaseModel):
    """Paginated product search result matching the OpenAPI ProductSearchResult contract."""

    items: list[ProductResponse]
    next_cursor: str | None = None

    model_config = ConfigDict(from_attributes=True)
