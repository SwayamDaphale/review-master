"""Category domain model for canonical product taxonomy."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.product_family import ProductFamily


class Category(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Canonical product category definition."""

    __tablename__ = "categories"

    key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    schema_version: Mapped[str] = mapped_column(
        String(32),
        default="1.0.0",
        nullable=False,
    )
    spec_schema: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="active",
        nullable=False,
    )

    # Relationships
    families: Mapped[list["ProductFamily"]] = relationship(
        "ProductFamily",
        back_populates="category",
        cascade="all, delete-orphan",
    )
    products: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="category",
        cascade="all, delete-orphan",
    )
