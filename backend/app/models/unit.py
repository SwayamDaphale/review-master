"""Unit domain model for PostgreSQL domain unit registry."""

from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class UnitDefinition(Base, TimestampMixin):
    """Domain unit definition for physical attribute measurements."""

    __tablename__ = "units"

    key: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    dimension: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    canonical_unit: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    conversion_factor: Mapped[Decimal] = mapped_column(
        Numeric(24, 12),
        nullable=False,
    )
    is_binary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
