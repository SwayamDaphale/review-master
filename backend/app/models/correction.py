"""Catalog correction audit ledger model according to Phase B5 requirements."""

import uuid
from typing import Any

from sqlalchemy import JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CatalogCorrection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Auditable ledger entry for administrative catalog corrections.

    Preserves full before/after states, actor identity, and correction rationale.
    """

    __tablename__ = "catalog_corrections"

    target_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,  # "variant_attribute", "product_identity", "attribute_definition"
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    before_value: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    after_value: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    actor_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    evidence_reference: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
