"""Comparison repository for sessions and item management."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.comparison import ComparisonItem, ComparisonSession


class ComparisonRepository:
    """Repository handling persistent comparison sessions and items."""

    @staticmethod
    def create_session(
        db: Session,
        *,
        user_id: uuid.UUID | None = None,
        anonymous_session_token: str | None = None,
        title: str | None = None,
        category_id: uuid.UUID | None = None,
    ) -> ComparisonSession:
        """Create a new comparison session for a user or anonymous visitor."""
        session = ComparisonSession(
            user_id=user_id,
            anonymous_session_token=anonymous_session_token,
            title=title,
            category_id=category_id,
        )
        db.add(session)
        db.flush()
        return session

    @staticmethod
    def get_session_by_id(
        db: Session,
        session_id: uuid.UUID,
    ) -> ComparisonSession | None:
        """Retrieve comparison session with items eagerly loaded."""
        stmt = (
            select(ComparisonSession)
            .where(ComparisonSession.id == session_id)
            .options(
                selectinload(ComparisonSession.items).joinedload(ComparisonItem.product),
                selectinload(ComparisonSession.items).joinedload(ComparisonItem.variant),
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_sessions_by_user(
        db: Session,
        user_id: uuid.UUID,
    ) -> list[ComparisonSession]:
        """List active comparison sessions belonging to an authenticated user."""
        stmt = (
            select(ComparisonSession)
            .where(
                ComparisonSession.user_id == user_id,
                ComparisonSession.status == "active",
            )
            .order_by(ComparisonSession.updated_at.desc())
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_session_by_token(
        db: Session,
        token: str,
    ) -> ComparisonSession | None:
        """Lookup comparison session by anonymous session token."""
        stmt = (
            select(ComparisonSession)
            .where(
                ComparisonSession.anonymous_session_token == token,
                ComparisonSession.status == "active",
            )
            .options(
                selectinload(ComparisonSession.items).joinedload(ComparisonItem.product),
                selectinload(ComparisonSession.items).joinedload(ComparisonItem.variant),
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def add_item(
        db: Session,
        *,
        session_id: uuid.UUID,
        product_id: uuid.UUID,
        variant_id: uuid.UUID | None = None,
        position: int = 0,
    ) -> ComparisonItem:
        """Add a product/variant item to a comparison session."""
        # Check existing item to prevent duplicate insertion
        stmt = select(ComparisonItem).where(
            ComparisonItem.session_id == session_id,
            ComparisonItem.product_id == product_id,
        )
        if variant_id is not None:
            stmt = stmt.where(ComparisonItem.variant_id == variant_id)
        else:
            stmt = stmt.where(ComparisonItem.variant_id.is_(None))

        existing = db.execute(stmt).scalar_one_or_none()
        if existing:
            return existing

        item = ComparisonItem(
            session_id=session_id,
            product_id=product_id,
            variant_id=variant_id,
            position=position,
        )
        db.add(item)
        db.flush()
        return item

    @staticmethod
    def get_session_items(
        db: Session,
        session_id: uuid.UUID,
    ) -> list[ComparisonItem]:
        """Fetch all items for a comparison session ordered by position."""
        stmt = (
            select(ComparisonItem)
            .where(ComparisonItem.session_id == session_id)
            .order_by(ComparisonItem.position.asc())
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def remove_item(
        db: Session,
        session_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> bool:
        """Remove an item from a comparison session."""
        item = db.get(ComparisonItem, item_id)
        if not item or item.session_id != session_id:
            return False
        db.delete(item)
        db.flush()
        return True
