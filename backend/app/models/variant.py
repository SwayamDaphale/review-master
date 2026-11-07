"""Variant domain model representing specific hardware configurations."""

import hashlib
import json
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.product import Product


def compute_config_hash(configuration: dict[str, Any] | None) -> str:
    """Compute deterministic SHA-256 hash of a variant configuration.

    Preserves nulls and sorts keys alphabetically to guarantee byte-identical
    hashes for identical configurations regardless of key ordering.
    """
    if not configuration:
        return hashlib.sha256(b"{}").hexdigest()
    canonical_json = json.dumps(
        configuration,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class Variant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Canonical product variant with a distinct hardware configuration."""

    __tablename__ = "variants"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    config_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    sku_label: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Relationships
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="variants",
    )

    __table_args__ = (
        UniqueConstraint(
            "product_id", "config_hash", name="uq_variants_product_config_hash"
        ),
    )
