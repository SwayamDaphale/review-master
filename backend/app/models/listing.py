"""Marketplace listing domain model representing observed products on e-commerce platforms."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.marketplace import Marketplace
    from app.models.offer import SellerOffer
    from app.models.product import Product
    from app.models.variant import Variant


class MarketplaceListing(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Specific product listing on an external marketplace (e.g., an Amazon ASIN)."""

    __tablename__ = "listings"

    marketplace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    match_state: Mapped[str] = mapped_column(
        String(32),
        default="unmatched",
        nullable=False,
        index=True,
    )
    match_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    raw_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Relationships
    marketplace: Mapped["Marketplace"] = relationship(
        "Marketplace", back_populates="listings"
    )
    product: Mapped["Product | None"] = relationship(
        "Product", back_populates="listings"
    )
    variant: Mapped["Variant | None"] = relationship(
        "Variant", back_populates="listings"
    )
    offers: Mapped[list["SellerOffer"]] = relationship(
        "SellerOffer",
        back_populates="listing",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "marketplace_id", "external_id", name="uq_listings_mkt_external_id"
        ),
        Index("ix_listings_mkt_ext", "marketplace_id", "external_id"),
    )
