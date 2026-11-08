"""Identity repository for user and role persistence operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.identity import Role, User, user_roles


class UserRepository:
    """Repository handling User database operations."""

    @staticmethod
    def create(
        db: Session,
        *,
        email: str,
        display_name: str | None = None,
        is_active: bool = True,
        password_hash: str | None = None,
    ) -> User:
        """Create and persist a new user."""
        user = User(
            email=email,
            display_name=display_name,
            is_active=is_active,
            password_hash=password_hash,
        )
        db.add(user)
        db.flush()
        return user

    @staticmethod
    def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
        """Retrieve user by ID with roles loaded."""
        stmt = select(User).where(User.id == user_id).options(selectinload(User.roles))
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_email(db: Session, email: str) -> User | None:
        """Retrieve user by unique email with roles loaded."""
        stmt = select(User).where(User.email == email).options(selectinload(User.roles))
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_users(db: Session, limit: int = 50, offset: int = 0) -> list[User]:
        """List active users with pagination."""
        stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        return list(db.execute(stmt).scalars().all())


class RoleRepository:
    """Repository handling Role database operations."""

    @staticmethod
    def create(
        db: Session,
        *,
        name: str,
        description: str | None = None,
    ) -> Role:
        """Create and persist a system role."""
        role = Role(name=name, description=description)
        db.add(role)
        db.flush()
        return role

    @staticmethod
    def get_by_id(db: Session, role_id: uuid.UUID) -> Role | None:
        """Retrieve role by primary key."""
        return db.get(Role, role_id)

    @staticmethod
    def get_by_name(db: Session, name: str) -> Role | None:
        """Retrieve role by unique name."""
        stmt = select(Role).where(Role.name == name)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_roles(db: Session) -> list[Role]:
        """List all system roles."""
        stmt = select(Role).order_by(Role.name.asc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def assign_role_to_user(db: Session, user_id: uuid.UUID, role_id: uuid.UUID) -> bool:
        """Assign role to user via user_roles association."""
        user = db.get(User, user_id)
        role = db.get(Role, role_id)
        if not user or not role:
            return False

        # Check existing assignment
        check_stmt = select(user_roles).where(
            user_roles.c.user_id == user_id,
            user_roles.c.role_id == role_id,
        )
        if db.execute(check_stmt).first():
            return True

        insert_stmt = user_roles.insert().values(user_id=user_id, role_id=role_id)
        db.execute(insert_stmt)
        db.flush()
        return True

    @staticmethod
    def get_user_roles(db: Session, user_id: uuid.UUID) -> list[Role]:
        """Fetch all roles assigned to a user."""
        stmt = (
            select(Role)
            .join(user_roles, Role.id == user_roles.c.role_id)
            .where(user_roles.c.user_id == user_id)
        )
        return list(db.execute(stmt).scalars().all())

