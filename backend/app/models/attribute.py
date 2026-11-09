"""Normalized catalog attribute models.

Complements existing JSONB configuration in Variant by providing
strongly-typed, queryable, and filterable normalized attribute definitions
and values across categories and variants.
"""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.evidence import Evidence
    from app.models.variant import Variant


class AttributeDefinition(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Specification attribute schema definition (e.g. RAM, Storage, Screen Size)."""

    __tablename__ = "attribute_definitions"

    key: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    data_type: Mapped[str] = mapped_column(
        String(32),
        default="string",
        nullable=False,  # "string", "numeric", "boolean", "json"
    )
    unit: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,  # "GB", "TB", "inches", "mAh"
    )
    canonical_unit: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    validation_rules: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    is_required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="active",
        nullable=False,
    )
    is_filterable: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_searchable: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    category: Mapped["Category | None"] = relationship(
        "Category",
        lazy="joined",
    )
    values: Mapped[list["VariantAttributeValue"]] = relationship(
        "VariantAttributeValue",
        back_populates="attribute_definition",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "category_id",
            "key",
            name="uq_attribute_definitions_category_key",
        ),
    )


class VariantAttributeValue(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Strongly-typed normalized attribute value linked to a specific product variant."""

    __tablename__ = "variant_attribute_values"

    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attribute_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attribute_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    value_text: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    value_numeric: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
    )
    value_boolean: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )
    value_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    raw_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    original_unit: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    canonical_unit: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    validation_status: Mapped[str] = mapped_column(
        String(32),
        default="valid",
        nullable=False,
    )
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    variant: Mapped["Variant"] = relationship(
        "Variant",
        back_populates="attribute_values",
    )
    attribute_definition: Mapped[AttributeDefinition] = relationship(
        "AttributeDefinition",
        back_populates="values",
        lazy="joined",
    )
    evidence: Mapped["Evidence | None"] = relationship("Evidence")

    __table_args__ = (
        UniqueConstraint(
            "variant_id",
            "attribute_id",
            name="uq_variant_attribute_values_variant_attribute",
        ),
    )
