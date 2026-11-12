"""Recommendation domain models for B10.

Persists recommendation requests, structured requirement snapshots,
hard-constraint outcomes, deterministic rankings, and audit references.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.evaluation import EvaluationModelVersion
    from app.models.identity import User


class Recommendation(Base, UUIDPrimaryKeyMixin):
    """Immutable recommendation run record."""

    __tablename__ = "recommendations"

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
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    raw_query: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    parsed_requirements: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    parser_version: Mapped[str] = mapped_column(
        String(32),
        default="v1",
        nullable=False,
    )
    ranking_policy_version: Mapped[str] = mapped_column(
        String(32),
        default="v1",
        nullable=False,
    )
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_model_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    eligible_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    ineligible_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    hard_constraint_results: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    ranked_results: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
    )
    rejected_results: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
    )
    input_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    output_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped["User | None"] = relationship("User")
    category: Mapped["Category"] = relationship("Category")
    model_version: Mapped["EvaluationModelVersion | None"] = relationship("EvaluationModelVersion")

