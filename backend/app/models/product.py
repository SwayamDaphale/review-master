"""Product domain model representing canonical base products."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.product_family import ProductFamily
    from app.models.variant import Variant


class Product(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Canonical product independent of marketplace listings."""

    __tablename__ = "products"

    family_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_families.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    manufacturer: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    mpn: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    gtin: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    generation: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="active",
        nullable=False,
    )

    # Relationships
    category: Mapped["Category"] = relationship(
        "Category",
        back_populates="products",
    )
    family: Mapped["ProductFamily | None"] = relationship(
        "ProductFamily",
        back_populates="products",
    )
    variants: Mapped[list["Variant"]] = relationship(
        "Variant",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_products_mfr_mpn", "manufacturer", "mpn"),)
