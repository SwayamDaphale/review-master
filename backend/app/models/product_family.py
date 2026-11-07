"""ProductFamily domain model grouping related product generations."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.product import Product


class ProductFamily(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Product family grouping (e.g. 'Galaxy S', 'iPhone', 'ThinkPad X1')."""

    __tablename__ = "product_families"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    manufacturer: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # Relationships
    category: Mapped["Category"] = relationship(
        "Category",
        back_populates="families",
    )
    products: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="family",
    )

    __table_args__ = (Index("ix_product_families_mfr_name", "manufacturer", "name"),)
