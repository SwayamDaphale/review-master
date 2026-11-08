"""Evidence and evidence versions models according to ADR-0007."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.variant import Variant


class Evidence(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Specification or evaluation evidence item attached to a variant or product."""

    __tablename__ = "evidence"

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
    parameter_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    trust_tier: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    visibility: Mapped[str] = mapped_column(
        String(32),
        default="public",
        nullable=False,
    )

    # Relationships
    product: Mapped["Product | None"] = relationship(
        "Product", back_populates="evidence"
    )
    variant: Mapped["Variant | None"] = relationship(
        "Variant", back_populates="evidence"
    )
    versions: Mapped[list["EvidenceVersion"]] = relationship(
        "EvidenceVersion",
        back_populates="evidence",
        cascade="all, delete-orphan",
    )


class EvidenceVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Append-only version of an evidence record."""

    __tablename__ = "evidence_versions"

    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    value: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    unit: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    methodology: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    verification_state: Mapped[str] = mapped_column(
        String(32),
        default="unverified",
        nullable=False,
    )
    source_url: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )
    raw_source_span: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )
    extraction_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("extraction_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    evidence: Mapped["Evidence"] = relationship("Evidence", back_populates="versions")

    __table_args__ = (Index("ix_evidence_versions_ev_ver", "evidence_id", "version"),)
