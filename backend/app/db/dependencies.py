"""FastAPI dependency injection providers for database sessions."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import get_db_session


def get_db() -> Generator[Session, None, None]:
    """Dependency provider yielding a request-scoped database session."""
    yield from get_db_session()
