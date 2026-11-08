"""Pydantic response models for marketplace listings and seller offers."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class SellerOfferResponse(BaseModel):
    """Commercial seller offer details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seller: str | None = None
    current_price: Decimal | None = None
    currency: str | None = "INR"
    availability: str | None = None
    observed_at: datetime
    source: str
    provenance: dict[str, Any] = {}


class MarketplaceListingResponse(BaseModel):
    """Summary of a marketplace listing."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    marketplace_id: uuid.UUID
    external_id: str
    url: str
    product_id: uuid.UUID | None = None
    variant_id: uuid.UUID | None = None
    match_state: str
    match_confidence: float | None = None
    first_seen_at: datetime
    last_seen_at: datetime


class MarketplaceListingDetailResponse(MarketplaceListingResponse):
    """Detailed marketplace listing with offers and metadata."""

    raw_metadata: dict[str, Any] | None = None
    offers: list[SellerOfferResponse] = []

