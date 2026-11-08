"""Identity and Access Management domain models.

Provides database models for users, roles, and user-role assignments.
Authentication workflows (registration, login, JWT issuance, RBAC enforcement)
belong to Phase B4 and are excluded from B3 scope.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.auth_session import AuthSession
    from app.models.comparison import ComparisonSession
    from app.models.operation import ImportToken

# Many-to-many association table between Users and Roles
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "assigned_at",
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    ),
)


class Role(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """System role definition for authorization and permission scoping."""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles",
    )


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Registered user entity."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    display_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    # password_hash is documented and reserved for Phase B4 credential verification
    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    roles: Mapped[list[Role]] = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
    )
    comparison_sessions: Mapped[list["ComparisonSession"]] = relationship(
        "ComparisonSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    import_tokens: Mapped[list["ImportToken"]] = relationship(
        "ImportToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    auth_sessions: Mapped[list["AuthSession"]] = relationship(
        "AuthSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
