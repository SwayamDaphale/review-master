"""Evidence quality, conflict tracking, and verification history domain models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.evidence import Evidence
    from app.models.identity import User
    from app.models.product import Product
    from app.models.variant import Variant


class EvidenceConflict(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks conflicting evidence values detected between different sources or extractions."""

    __tablename__ = "evidence_conflicts"

    parameter_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    existing_value: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    conflicting_value: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    existing_unit: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    conflicting_unit: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    existing_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    incoming_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="open",
        nullable=False,
        index=True,
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resolution_decision: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    resolution_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    existing_evidence: Mapped["Evidence | None"] = relationship(
        "Evidence", foreign_keys=[existing_evidence_id]
    )
    incoming_evidence: Mapped["Evidence | None"] = relationship(
        "Evidence", foreign_keys=[incoming_evidence_id]
    )
    product: Mapped["Product | None"] = relationship("Product")
    variant: Mapped["Variant | None"] = relationship("Variant")
    resolver: Mapped["User | None"] = relationship("User")

    __table_args__ = (
        Index("ix_evidence_conflicts_param_status", "parameter_key", "status"),
        Index("ix_evidence_conflicts_prod_var", "product_id", "variant_id"),
    )


class EvidenceVerificationHistory(Base, UUIDPrimaryKeyMixin):
    """Immutable audit log of verification status transitions on evidence records."""

    __tablename__ = "evidence_verification_history"

    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    new_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    supporting_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    # Relationships
    evidence: Mapped["Evidence"] = relationship("Evidence", foreign_keys=[evidence_id])
    actor: Mapped["User | None"] = relationship("User")

    __table_args__ = (
        Index("ix_ev_ver_hist_ev_created", "evidence_id", "created_at"),
    )

