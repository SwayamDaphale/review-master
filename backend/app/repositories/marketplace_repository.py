"""Marketplace repository for marketplace, listing, offer, and price persistence."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.base import utc_now
from app.models.listing import MarketplaceListing
from app.models.marketplace import Marketplace
from app.models.offer import PriceRecord, SellerOffer


class MarketplaceRepository:
    """Repository handling marketplaces, external listings, seller offers, and price records."""

    @staticmethod
    def get_by_key(db: Session, key: str) -> Marketplace | None:
        """Lookup marketplace by unique key (e.g. amazon_in)."""
        stmt = select(Marketplace).where(Marketplace.key == key)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_listing_by_external_id(
        db: Session,
        marketplace_id: uuid.UUID,
        external_id: str,
    ) -> MarketplaceListing | None:
        """Lookup listing by external ID (e.g. ASIN) within a marketplace."""
        stmt = (
            select(MarketplaceListing)
            .where(
                MarketplaceListing.marketplace_id == marketplace_id,
                MarketplaceListing.external_id == external_id,
            )
            .options(
                joinedload(MarketplaceListing.product),
                joinedload(MarketplaceListing.variant),
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_offer_by_seller(
        db: Session,
        listing_id: uuid.UUID,
        seller: str,
    ) -> SellerOffer | None:
        """Find offer by seller on a listing."""
        stmt = select(SellerOffer).where(
            SellerOffer.listing_id == listing_id,
            SellerOffer.seller == seller,
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def record_price(
        db: Session,
        *,
        offer_id: uuid.UUID,
        amount: Decimal | float,
        currency: str,
        original_amount: Decimal | float | None = None,
        observed_at: datetime | None = None,
        source: str = "browser_extension_user_initiated",
        provenance: dict[str, Any] | None = None,
    ) -> PriceRecord:
        """Create an append-only price observation record."""
        dec_amount = Decimal(str(amount))
        record = PriceRecord(
            offer_id=offer_id,
            price=dec_amount,
            currency=currency,
            observed_at=observed_at or utc_now(),
            source=source,
            provenance=provenance or {},
        )
        db.add(record)
        db.flush()
        return record
