"""Authentication session repository for refresh token management."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.db.base import utc_now
from app.models.auth_session import AuthSession
from app.models.identity import User


class AuthRepository:
    """Repository handling AuthSession database operations and token family lifecycle."""

    @staticmethod
    def create_session(
        db: Session,
        *,
        user_id: uuid.UUID,
        refresh_token_hash: str,
        expires_at: datetime,
        token_family: uuid.UUID | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthSession:
        """Create and persist a new authentication session with a rotating refresh token."""
        session = AuthSession(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            token_family=token_family or uuid.uuid4(),
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
            is_revoked=False,
        )
        db.add(session)
        db.flush()
        return session

    @staticmethod
    def get_session_by_hash(db: Session, refresh_token_hash: str) -> AuthSession | None:
        """Retrieve an authentication session by refresh token SHA-256 hash."""
        stmt = (
            select(AuthSession)
            .where(AuthSession.refresh_token_hash == refresh_token_hash)
            .options(selectinload(AuthSession.user).selectinload(User.roles))
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_session_by_hash_for_update(
        db: Session, refresh_token_hash: str
    ) -> AuthSession | None:
        """Retrieve session with pessimistic write lock to prevent race conditions during refresh."""
        stmt = (
            select(AuthSession)
            .where(AuthSession.refresh_token_hash == refresh_token_hash)
            .with_for_update()
            .options(selectinload(AuthSession.user).selectinload(User.roles))
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def revoke_session(db: Session, session: AuthSession) -> AuthSession:
        """Revoke a single authentication session."""
        session.is_revoked = True
        session.revoked_at = utc_now()
        db.flush()
        return session

    @staticmethod
    def revoke_family(db: Session, token_family: uuid.UUID) -> int:
        """Revoke all sessions belonging to a token family (triggered when reuse is detected)."""
        now = utc_now()
        stmt = (
            update(AuthSession)
            .where(
                AuthSession.token_family == token_family,
                AuthSession.is_revoked.is_(False),
            )
            .values(
                is_revoked=True,
                revoked_at=now,
                updated_at=now,
            )
        )
        result = db.execute(stmt)
        db.flush()
        rowcount = getattr(result, "rowcount", 0)
        return int(rowcount) if rowcount is not None else 0

    @staticmethod
    def rotate_session(
        db: Session,
        *,
        old_session: AuthSession,
        new_refresh_token_hash: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthSession:
        """Atomically mark old session as rotated/revoked and issue a new session in the same family."""
        now = utc_now()
        old_session.is_revoked = True
        old_session.revoked_at = now
        old_session.rotated_at = now
        old_session.updated_at = now

        new_session = AuthSession(
            user_id=old_session.user_id,
            refresh_token_hash=new_refresh_token_hash,
            token_family=old_session.token_family,
            expires_at=expires_at,
            user_agent=user_agent or old_session.user_agent,
            ip_address=ip_address or old_session.ip_address,
            is_revoked=False,
        )
        db.add(new_session)
        db.flush()
        return new_session

    @staticmethod
    def revoke_all_user_sessions(db: Session, user_id: uuid.UUID) -> int:
        """Revoke all sessions for a given user (security invalidation)."""
        now = utc_now()
        stmt = (
            update(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.is_revoked.is_(False),
            )
            .values(
                is_revoked=True,
                revoked_at=now,
                updated_at=now,
            )
        )
        result = db.execute(stmt)
        db.flush()
        rowcount = getattr(result, "rowcount", 0)
        return int(rowcount) if rowcount is not None else 0
