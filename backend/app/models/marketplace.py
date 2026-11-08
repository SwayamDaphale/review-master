"""Marketplace domain model representing external e-commerce platforms."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.listing import MarketplaceListing


class Marketplace(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """External marketplace source (e.g. amazon.in)."""

    __tablename__ = "marketplaces"

    key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    adapter: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="active",
        nullable=False,
    )
    permitted_sources: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Relationships
    listings: Mapped[list["MarketplaceListing"]] = relationship(
        "MarketplaceListing",
        back_populates="marketplace",
        cascade="all, delete-orphan",
    )

