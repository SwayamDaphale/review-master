"""Authentication and authorization utilities for Review Master API."""

import logging
import uuid
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import Permission, RoleName, get_permissions_for_roles
from app.core.security import decode_access_token, hash_api_key
from app.db.base import utc_now
from app.db.dependencies import get_db
from app.models.identity import User
from app.repositories.operations_repository import OperationsRepository

logger = logging.getLogger("review_master.auth")


class AuthenticatedUser(BaseModel):
    """Authenticated user context for API requests."""

    id: str
    email: str | None = None
    display_name: str | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: set[str] = Field(default_factory=set)
    is_authenticated: bool = True

    @property
    def role(self) -> str:
        """Primary role for backwards compatibility."""
        return self.roles[0] if self.roles else RoleName.CONSUMER.value

    def has_permission(self, permission: str | Permission) -> bool:
        """Check whether user holds a specific permission."""
        perm_val = permission.value if isinstance(permission, Permission) else permission
        return perm_val in self.permissions

    def has_any_permission(self, *permissions: str | Permission) -> bool:
        """Check whether user holds any of the specified permissions."""
        return any(self.has_permission(p) for p in permissions)

    def has_all_permissions(self, *permissions: str | Permission) -> bool:
        """Check whether user holds all of the specified permissions."""
        return all(self.has_permission(p) for p in permissions)

    def has_role(self, role: str | RoleName) -> bool:
        """Check whether user holds a specific role."""
        role_val = role.value if isinstance(role, RoleName) else role
        return role_val in self.roles


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> AuthenticatedUser:
    """Dependency validating client credentials (JWT Bearer or API Key).

    Anonymous and invalid-credential requests are strictly rejected with HTTP 401
    in all environments (development, test, and production).
    """
    token: str | None = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header format. Expected 'Bearer <token>'.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 1. Validate API Key if provided
    if x_api_key:
        api_roles = [RoleName.API_CONSUMER.value]
        api_perms = get_permissions_for_roles(api_roles)

        # A) Check cryptographic peppered hash against registered import tokens
        if db is not None:
            key_hash = hash_api_key(x_api_key)
            tok = OperationsRepository.get_import_token(db, key_hash)
            if tok and not tok.is_revoked and tok.expires_at > utc_now():
                return AuthenticatedUser(
                    id=str(tok.user_id) if tok.user_id else f"api-consumer-{tok.id}",
                    email=f"api-{tok.id}@reviewmaster.local",
                    display_name="Provisioned API Consumer",
                    roles=api_roles,
                    permissions=api_perms,
                    is_authenticated=True,
                )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Validate Bearer token
    if token:
        # Standard signed JWT decode
        try:
            payload = decode_access_token(token)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: missing subject.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        email = payload.get("email")
        roles = payload.get("roles", [])
        display_name = payload.get("display_name")

        # Verify active user in database if db session is present
        if db is not None:
            try:
                user_uuid = uuid.UUID(user_id_str)
                stmt = (
                    select(User)
                    .where(User.id == user_uuid)
                    .options(selectinload(User.roles))
                )
                user = db.execute(stmt).scalar_one_or_none()
                if user is not None:
                    if not user.is_active:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="User account is deactivated.",
                            headers={"WWW-Authenticate": "Bearer"},
                        )
                    roles = [r.name for r in user.roles]
                    display_name = user.display_name or display_name
                    email = user.email or email
                else:
                    # If subject UUID does not exist in DB, reject as invalid
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User account not found.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            except ValueError:
                pass

        permissions = get_permissions_for_roles(roles)
        return AuthenticatedUser(
            id=user_id_str,
            email=email,
            display_name=display_name,
            roles=roles,
            permissions=permissions,
            is_authenticated=True,
        )

    # 3. Anonymous requests receive 401 unconditionally in both dev and prod
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_authenticated_user(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    """Dependency verifying that request was initiated by an authenticated identity."""
    if not current_user.is_authenticated or current_user.id == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def require_permissions(*required_permissions: str | Permission):
    """FastAPI dependency factory enforcing that current user possesses all specified permissions."""

    def dependency(
        request: Request,
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> AuthenticatedUser:
        missing = [
            (p.value if isinstance(p, Permission) else p)
            for p in required_permissions
            if not current_user.has_permission(p)
        ]
        if missing:
            client_ip = request.client.host if request.client else None
            try:
                OperationsRepository.create_audit_log(
                    db,
                    actor_type="user",
                    actor_id=current_user.id,
                    action="security.access_denied",
                    target_type="route",
                    target_id=request.url.path,
                    status="failure",
                    metadata_payload={
                        "missing_permission": missing[0],
                        "user_roles": current_user.roles,
                        "ip": client_ip,
                    },
                )
                db.commit()
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to record access denial audit log: %s", e)

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden. Missing required permission: {missing[0]}",
            )
        return current_user

    return dependency


def require_roles(*required_roles: str | RoleName):
    """FastAPI dependency factory enforcing that current user possesses at least one of the specified roles."""

    def dependency(
        request: Request,
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> AuthenticatedUser:
        user_roles = set(current_user.roles)
        expected = {(r.value if isinstance(r, RoleName) else r) for r in required_roles}
        if not user_roles.intersection(expected):
            client_ip = request.client.host if request.client else None
            try:
                OperationsRepository.create_audit_log(
                    db,
                    actor_type="user",
                    actor_id=current_user.id,
                    action="security.access_denied",
                    target_type="route",
                    target_id=request.url.path,
                    status="failure",
                    metadata_payload={
                        "expected_roles": list(expected),
                        "user_roles": current_user.roles,
                        "ip": client_ip,
                    },
                )
                db.commit()
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to record access denial audit log: %s", e)

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden. Required role: {next(iter(expected))}",
            )
        return current_user

    return dependency
