"""Comparison domain models.

Supports persistent comparison sessions and items for both authenticated
users and guest/anonymous visitors without inventing premature recommendation logic.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.identity import User
    from app.models.product import Product
    from app.models.variant import Variant


class ComparisonSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User or guest session grouping products and variants for comparison."""

    __tablename__ = "comparison_sessions"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    anonymous_session_token: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="active",
        nullable=False,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    user: Mapped["User | None"] = relationship(
        "User",
        back_populates="comparison_sessions",
    )
    category: Mapped["Category | None"] = relationship(
        "Category",
        lazy="joined",
    )
    items: Mapped[list["ComparisonItem"]] = relationship(
        "ComparisonItem",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ComparisonItem.position",
    )


class ComparisonItem(Base, UUIDPrimaryKeyMixin):
    """Individual product or variant entry within a comparison session."""

    __tablename__ = "comparison_items"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comparison_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    session: Mapped[ComparisonSession] = relationship(
        "ComparisonSession",
        back_populates="items",
    )
    product: Mapped["Product"] = relationship(
        "Product",
        lazy="joined",
    )
    variant: Mapped["Variant | None"] = relationship(
        "Variant",
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "product_id",
            "variant_id",
            name="uq_comparison_items_session_product_variant",
        ),
    )
