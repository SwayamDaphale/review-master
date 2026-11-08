"""Deterministic evaluation models conforming to ADR-0003 and DATA_MODEL.md."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.variant import Variant


class EvaluationModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Top-level evaluation model definition per product category."""

    __tablename__ = "evaluation_models"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    # Relationships
    category: Mapped["Category"] = relationship("Category")
    versions: Mapped[list["EvaluationModelVersion"]] = relationship(
        "EvaluationModelVersion",
        back_populates="model",
        cascade="all, delete-orphan",
    )


class EvaluationModelVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Specific version of an evaluation model (immutable once published)."""

    __tablename__ = "evaluation_model_versions"

    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="draft",
        nullable=False,
        index=True,
    )
    definition: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    approved_by: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    model: Mapped["EvaluationModel"] = relationship(
        "EvaluationModel", back_populates="versions"
    )

    __table_args__ = (
        UniqueConstraint("model_id", "version", name="uq_eval_model_version"),
    )


class Evaluation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Deterministic evaluation outcome for a canonical variant (append-only)."""

    __tablename__ = "evaluations"

    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_model_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    overall_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    confidence_state: Mapped[str] = mapped_column(
        String(32),
        default="unavailable",
        nullable=False,
    )
    confidence_score: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3),
        nullable=True,
    )
    coverage: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3),
        nullable=True,
    )
    limitations: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    evidence_snapshot_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    # Relationships
    variant: Mapped["Variant"] = relationship("Variant", back_populates="evaluations")
    model_version: Mapped["EvaluationModelVersion | None"] = relationship(
        "EvaluationModelVersion"
    )
    parameter_results: Mapped[list["ParameterResult"]] = relationship(
        "ParameterResult",
        back_populates="evaluation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_evaluations_var_created", "variant_id", "created_at"),)


class ParameterResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Evaluation result for one parameter within an evaluation."""

    __tablename__ = "parameter_results"

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parameter_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="not_scored",
        nullable=False,
    )
    weight: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3),
        nullable=True,
    )
    is_critical: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    evidence_ids: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    explanation_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Relationships
    evaluation: Mapped["Evaluation"] = relationship(
        "Evaluation", back_populates="parameter_results"
    )
