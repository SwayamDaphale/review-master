"""Operations domain models.

Provides audit logging and browser extension import token persistence.
Audit records are append-only. Import tokens only store cryptographic SHA-256
hashes rather than plaintext credentials.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.identity import User


class AuditLog(Base, UUIDPrimaryKeyMixin):
    """Append-only audit trail recording significant domain events.

    Security rule: Must never contain passwords, password hashes, secrets, or tokens.
    """

    __tablename__ = "audit_logs"

    actor_type: Mapped[str] = mapped_column(
        String(32),
        default="user",
        nullable=False,
    )
    actor_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    target_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    target_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="success",
        nullable=False,
    )
    request_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )
    metadata_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )


class ImportToken(Base, UUIDPrimaryKeyMixin):
    """One-time or bounded token used to authorize browser-extension evidence imports.

    Only stores SHA-256 hash of the generated secret token.
    """

    __tablename__ = "import_tokens"

    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    context: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    user: Mapped["User | None"] = relationship(
        "User",
        back_populates="import_tokens",
    )
