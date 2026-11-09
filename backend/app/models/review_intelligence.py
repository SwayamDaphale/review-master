"""Review intelligence models conforming to Phase B5 requirements."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.evidence import Evidence
    from app.models.product import Product
    from app.models.variant import Variant


class ReviewAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Analysis record for an individual customer review or evidence text."""

    __tablename__ = "review_analyses"

    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    review_source_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )
    review_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    sentiment: Mapped[str] = mapped_column(
        String(32),
        nullable=False,  # "positive", "negative", "neutral", "mixed"
        index=True,
    )
    sentiment_confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("1.0"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,  # "groq", "nvidia", "mock"
    )
    model: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    prompt_version: Mapped[str] = mapped_column(
        String(32),
        default="1.0",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="completed",
        nullable=False,
        index=True,  # "pending", "completed", "failed"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    product: Mapped["Product | None"] = relationship("Product")
    variant: Mapped["Variant | None"] = relationship("Variant")
    source_evidence: Mapped["Evidence | None"] = relationship("Evidence")
    aspect_opinions: Mapped[list["ReviewAspectOpinion"]] = relationship(
        "ReviewAspectOpinion",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    pros_cons: Mapped[list["ReviewProCon"]] = relationship(
        "ReviewProCon",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )


class ReviewAspectOpinion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Aspect-based opinion extracted from customer review evidence."""

    __tablename__ = "review_aspect_opinions"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    aspect_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,  # "battery", "camera", "display", "performance", "build_quality", etc.
    )
    polarity: Mapped[str] = mapped_column(
        String(32),
        nullable=False,  # "positive", "negative", "neutral"
        index=True,
    )
    claim: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    raw_quote: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("1.0"),
        nullable=False,
    )
    source_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    analysis: Mapped[ReviewAnalysis] = relationship(
        "ReviewAnalysis",
        back_populates="aspect_opinions",
    )


class ReviewProCon(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Structured positive or negative observation extracted from review evidence."""

    __tablename__ = "review_pros_cons"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,  # "pro" | "con"
        index=True,
    )
    text: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    aspect_key: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    source_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    analysis: Mapped[ReviewAnalysis] = relationship(
        "ReviewAnalysis",
        back_populates="pros_cons",
    )


class ReviewSummary(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Aggregated product-level or variant-level review summary synthesized from verified opinions."""

    __tablename__ = "review_summaries"

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
    summary_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    total_reviews_analyzed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    sentiment_distribution: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,  # {"positive": count, "negative": count, "neutral": count, "mixed": count}
    )
    aspect_summaries: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,  # {"battery": {"positive": 12, "negative": 2, "summary": "..."}}
    )
    key_pros: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    key_cons: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("1.0"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product")
    variant: Mapped["Variant | None"] = relationship("Variant")
