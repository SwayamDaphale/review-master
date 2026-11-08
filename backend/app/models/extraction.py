"""Extraction records and ingestion job tracking models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExtractionRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable audit record of an observed marketplace extraction."""

    __tablename__ = "extraction_records"

    record_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    marketplace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    schema_version: Mapped[str] = mapped_column(
        String(16),
        default="1.0",
        nullable=False,
    )
    asin: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
    )
    product_url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    extraction_method: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    extension_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    normalized_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    validation_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    storage_object_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )


class IngestionJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracking entity for extraction ingestion pipelines."""

    __tablename__ = "ingestion_jobs"

    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )
    record_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="SET NULL"),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

