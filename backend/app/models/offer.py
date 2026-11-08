"""Seller offer and price history models."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.listing import MarketplaceListing


class SellerOffer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Current commercial offer from a seller on a marketplace listing."""

    __tablename__ = "offers"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seller: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    current_price: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )
    currency: Mapped[str | None] = mapped_column(
        String(3),
        default="INR",
        nullable=True,
    )
    availability: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(64),
        default="browser_extension_user_initiated",
        nullable=False,
    )
    provenance: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Relationships
    listing: Mapped["MarketplaceListing"] = relationship(
        "MarketplaceListing", back_populates="offers"
    )
    price_records: Mapped[list["PriceRecord"]] = relationship(
        "PriceRecord",
        back_populates="offer",
        cascade="all, delete-orphan",
    )


class PriceRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Historical price and availability observation point (append-only)."""

    __tablename__ = "price_records"

    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("offers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )
    currency: Mapped[str | None] = mapped_column(
        String(3),
        default="INR",
        nullable=True,
    )
    availability: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    provenance: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Relationships
    offer: Mapped["SellerOffer"] = relationship(
        "SellerOffer", back_populates="price_records"
    )

    __table_args__ = (Index("ix_price_records_offer_obs", "offer_id", "observed_at"),)

