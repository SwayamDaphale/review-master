"""Comparison repository for sessions and item management."""

import uuid

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.models.comparison import ComparisonItem, ComparisonSession
from app.models.variant import Variant


class ActiveComparisonSessionLimitError(ValueError):
    """Raised when active comparison sessions limit is exceeded."""

    pass


class ComparisonValidationError(ValueError):
    """Raised for comparison validation failures like cross-category or capacity."""

    pass


class ComparisonRepository:
    """Repository handling persistent comparison sessions and items."""

    MAX_ACTIVE_SESSIONS = 2
    MAX_ITEMS_PER_SESSION = 5

    @classmethod
    def _acquire_owner_lock(
        cls,
        db: Session,
        user_id: uuid.UUID | None,
        anonymous_session_token: str | None,
    ) -> None:
        """Acquire transaction-scoped advisory lock for concurrency-safe session counting."""
        owner_key: str | None = None
        if user_id is not None:
            owner_key = f"comp_session_user:{user_id}"
        elif anonymous_session_token:
            owner_key = f"comp_session_anon:{anonymous_session_token}"

        if owner_key:
            bind = db.get_bind()
            if bind.dialect.name == "postgresql":
                db.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                    {"key": owner_key},
                )

    @classmethod
    def count_active_sessions(
        cls,
        db: Session,
        *,
        user_id: uuid.UUID | None = None,
        anonymous_session_token: str | None = None,
        exclude_session_id: uuid.UUID | None = None,
    ) -> int:
        """Count active sessions for given owner."""
        stmt = select(func.count(ComparisonSession.id)).where(
            ComparisonSession.status == "active"
        )
        if user_id is not None:
            stmt = stmt.where(ComparisonSession.user_id == user_id)
        elif anonymous_session_token:
            stmt = stmt.where(
                ComparisonSession.anonymous_session_token == anonymous_session_token
            )
        else:
            return 0

        if exclude_session_id is not None:
            stmt = stmt.where(ComparisonSession.id != exclude_session_id)

        return db.execute(stmt).scalar() or 0

    @classmethod
    def create_session(
        cls,
        db: Session,
        *,
        user_id: uuid.UUID | None = None,
        anonymous_session_token: str | None = None,
        title: str | None = None,
        category_id: uuid.UUID | None = None,
    ) -> ComparisonSession:
        """Create a new comparison session enforcing max 2 active sessions per owner."""
        cls._acquire_owner_lock(db, user_id, anonymous_session_token)

        active_count = cls.count_active_sessions(
            db, user_id=user_id, anonymous_session_token=anonymous_session_token
        )
        if active_count >= cls.MAX_ACTIVE_SESSIONS:
            raise ActiveComparisonSessionLimitError(
                f"Maximum {cls.MAX_ACTIVE_SESSIONS} active comparison sessions allowed per owner. Please archive an existing session."
            )

        session = ComparisonSession(
            user_id=user_id,
            anonymous_session_token=anonymous_session_token,
            title=title,
            status="active",
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
                selectinload(ComparisonSession.category),
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_sessions_by_user(
        db: Session,
        user_id: uuid.UUID,
        status: str | None = "active",
    ) -> list[ComparisonSession]:
        """List comparison sessions belonging to an authenticated user."""
        stmt = (
            select(ComparisonSession)
            .where(ComparisonSession.user_id == user_id)
            .options(
                selectinload(ComparisonSession.items).joinedload(ComparisonItem.product),
                selectinload(ComparisonSession.items).joinedload(ComparisonItem.variant),
                selectinload(ComparisonSession.category),
            )
            .order_by(ComparisonSession.updated_at.desc())
        )
        if status:
            stmt = stmt.where(ComparisonSession.status == status)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_sessions_by_token(
        db: Session,
        token: str,
        status: str | None = "active",
    ) -> list[ComparisonSession]:
        """Lookup comparison sessions by anonymous session token."""
        stmt = (
            select(ComparisonSession)
            .where(ComparisonSession.anonymous_session_token == token)
            .options(
                selectinload(ComparisonSession.items).joinedload(ComparisonItem.product),
                selectinload(ComparisonSession.items).joinedload(ComparisonItem.variant),
                selectinload(ComparisonSession.category),
            )
            .order_by(ComparisonSession.updated_at.desc())
        )
        if status:
            stmt = stmt.where(ComparisonSession.status == status)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def archive_session(
        db: Session,
        session_id: uuid.UUID,
    ) -> ComparisonSession:
        """Archive a comparison session explicitly, releasing an active session slot."""
        session = db.get(ComparisonSession, session_id)
        if not session:
            raise ValueError(f"Comparison session '{session_id}' not found.")
        session.status = "archived"
        db.flush()
        return session

    @classmethod
    def add_variant(
        cls,
        db: Session,
        *,
        session: ComparisonSession,
        variant_id: uuid.UUID,
        position: int | None = None,
    ) -> ComparisonItem:
        """Add a variant to a comparison session validating category, capacity, and uniqueness."""
        if session.status != "active":
            raise ComparisonValidationError(
                f"Cannot modify comparison session in '{session.status}' status. Only active sessions can be modified."
            )

        # 1. Fetch variant and verify existence
        variant = db.get(Variant, variant_id)
        if not variant:
            raise ComparisonValidationError(f"Product variant '{variant_id}' not found.")

        product = variant.product
        if not product:
            raise ComparisonValidationError(f"Product for variant '{variant_id}' not found.")

        # 2. Category validation: establish category or reject cross-category
        if session.category_id is None:
            session.category_id = product.category_id
            db.flush()
        elif session.category_id != product.category_id:
            raise ComparisonValidationError(
                f"Cross-category comparison is not allowed. Session is locked to category '{session.category_id}', but variant belongs to '{product.category_id}'."
            )

        # 3. Prevent duplicate variants in the same session
        existing_stmt = select(ComparisonItem).where(
            ComparisonItem.session_id == session.id,
            ComparisonItem.variant_id == variant.id,
        )
        existing = db.execute(existing_stmt).scalar_one_or_none()
        if existing:
            raise ComparisonValidationError(
                f"Variant '{variant_id}' is already included in this comparison session."
            )

        # 4. Enforce max items capacity (5 items)
        current_count = db.execute(
            select(func.count(ComparisonItem.id)).where(ComparisonItem.session_id == session.id)
        ).scalar() or 0

        if current_count >= cls.MAX_ITEMS_PER_SESSION:
            raise ComparisonValidationError(
                f"Maximum {cls.MAX_ITEMS_PER_SESSION} items allowed per comparison session."
            )

        if position is None:
            position = current_count

        item = ComparisonItem(
            session_id=session.id,
            product_id=product.id,
            variant_id=variant.id,
            position=position,
        )
        db.add(item)
        db.flush()
        return item

    @classmethod
    def remove_variant(
        cls,
        db: Session,
        *,
        session: ComparisonSession,
        variant_id: uuid.UUID,
    ) -> bool:
        """Remove a variant from comparison session."""
        if session.status != "active":
            raise ComparisonValidationError(
                f"Cannot modify comparison session in '{session.status}' status."
            )

        stmt = select(ComparisonItem).where(
            ComparisonItem.session_id == session.id,
            ComparisonItem.variant_id == variant_id,
        )
        item = db.execute(stmt).scalar_one_or_none()
        if not item:
            return False

        db.delete(item)
        db.flush()
        return True

    @staticmethod
    def get_session_items(
        db: Session,
        session_id: uuid.UUID,
    ) -> list[ComparisonItem]:
        """Fetch all items for a comparison session ordered by position."""
        stmt = (
            select(ComparisonItem)
            .where(ComparisonItem.session_id == session_id)
            .options(
                selectinload(ComparisonItem.product),
                selectinload(ComparisonItem.variant),
            )
            .order_by(ComparisonItem.position.asc())
        )
        return list(db.execute(stmt).scalars().all())
