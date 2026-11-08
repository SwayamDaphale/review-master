"""Marketplace listing endpoints for inspecting observed marketplace items and seller offers."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import AuthenticatedUser, get_current_user
from app.db.dependencies import get_db
from app.models.listing import MarketplaceListing
from app.schemas.listing import (
    MarketplaceListingDetailResponse,
    MarketplaceListingResponse,
)

router = APIRouter(tags=["Marketplace Listings"])


@router.get(
    "/listings/{listing_id}",
    response_model=MarketplaceListingDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get marketplace listing with active seller offers",
    description="Retrieve a marketplace listing, its matching status, and active commercial offers.",
)
def get_listing(
    listing_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> MarketplaceListingDetailResponse:
    """Retrieve marketplace listing by UUID."""
    listing = db.execute(
        select(MarketplaceListing)
        .where(MarketplaceListing.id == listing_id)
        .options(selectinload(MarketplaceListing.offers))
    ).scalar_one_or_none()

    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Marketplace listing '{listing_id}' not found.",
        )

    return MarketplaceListingDetailResponse.model_validate(listing)


@router.get(
    "/products/{product_id}/listings",
    response_model=list[MarketplaceListingResponse],
    status_code=status.HTTP_200_OK,
    summary="Get marketplace listings mapped to a canonical product",
    description="Retrieve all observed external marketplace listings associated with a canonical product.",
)
def get_product_listings(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> list[MarketplaceListingResponse]:
    """Retrieve all marketplace listings for a canonical product."""
    listings = (
        db.execute(
            select(MarketplaceListing).where(
                MarketplaceListing.product_id == product_id
            )
        )
        .scalars()
        .all()
    )

    return [MarketplaceListingResponse.model_validate(item) for item in listings]
