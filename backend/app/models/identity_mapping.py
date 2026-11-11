"""External identity mappings and review queue domain models according to ADR-0006 and B8 specs."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.identity import User
    from app.models.marketplace import Marketplace
    from app.models.product import Product
    from app.models.variant import Variant


class ExternalIdentityMapping(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Authoritative mapping between an external marketplace identifier and canonical catalog entity."""

    __tablename__ = "external_identity_mappings"

    marketplace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_id_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="asin",
        index=True,
    )
    external_id_value: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
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
    mapping_status: Mapped[str] = mapped_column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    verification_status: Mapped[str] = mapped_column(
        String(32),
        default="unverified",
        nullable=False,
        index=True,
    )
    confidence_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    provenance: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    marketplace: Mapped["Marketplace"] = relationship("Marketplace")
    product: Mapped["Product | None"] = relationship("Product")
    variant: Mapped["Variant | None"] = relationship("Variant")

    __table_args__ = (
        UniqueConstraint(
            "marketplace_id",
            "external_id_type",
            "external_id_value",
            name="uq_ext_identity_mkt_type_val",
        ),
        Index(
            "ix_ext_identity_mkt_type_val",
            "marketplace_id",
            "external_id_type",
            "external_id_value",
        ),
    )


class IdentityReviewQueue(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Queue for ambiguous or low-confidence identity resolution candidates requiring review."""

    __tablename__ = "identity_review_queue"

    record_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    marketplace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    asin: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    raw_title: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    candidate_product_ids: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    candidate_variant_ids: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    candidate_scores: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    conflicting_attributes: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    matching_reasons: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )
    assigned_reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewer_decision: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    decision_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    marketplace: Mapped["Marketplace | None"] = relationship("Marketplace")
    assigned_reviewer: Mapped["User | None"] = relationship("User")

