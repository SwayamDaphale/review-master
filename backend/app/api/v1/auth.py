"""Authentication and Authorization REST endpoints."""

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.auth import (
    AuthenticatedUser,
    require_authenticated_user,
)
from app.core.config import settings
from app.core.permissions import RoleName
from app.core.rate_limit import RateLimiter, get_client_ip
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_needs_rehash,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.base import utc_now
from app.db.dependencies import get_db
from app.models.identity import User
from app.repositories.auth_repository import AuthRepository
from app.repositories.identity_repository import RoleRepository, UserRepository
from app.repositories.operations_repository import OperationsRepository
from app.schemas.auth import (
    AuthTokenResponse,
    LogoutResponse,
    RefreshTokenRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

logger = logging.getLogger("review_master.api.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is offset-aware UTC for cross-database compatibility."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _extract_client_info(request: Request) -> tuple[str | None, str | None]:
    """Extract client IP and User-Agent header safely."""
    user_agent = request.headers.get("user-agent")
    if user_agent and len(user_agent) > 512:
        user_agent = user_agent[:512]

    client_ip = get_client_ip(request)
    return client_ip, user_agent


def _generate_csrf_token() -> str:
    """Generate high-entropy cryptographically secure anti-CSRF token."""
    return secrets.token_urlsafe(32)


def _set_auth_cookies(response: Response, refresh_token: str, csrf_token: str) -> None:
    """Attach secure HTTP-only refresh cookie and anti-CSRF cookie to outgoing response."""
    is_prod = settings.APP_ENV == "production"
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )
    response.set_cookie(
        key="rm_csrf_token",
        value=csrf_token,
        httponly=False,  # Accessible to client-side scripts to echo back in X-CSRF-Token header
        secure=is_prod,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear both refresh and anti-CSRF cookies using identical path, domain, and SameSite attributes."""
    is_prod = settings.APP_ENV == "production"
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth",
        samesite="lax",
        secure=is_prod,
    )
    response.delete_cookie(
        key="rm_csrf_token",
        path="/api/v1/auth",
        samesite="lax",
        secure=is_prod,
    )


def _verify_csrf(request: Request, is_cookie_auth: bool) -> None:
    """Validate anti-CSRF token when request relies on ambient cookie authentication."""
    if is_cookie_auth:
        csrf_cookie = request.cookies.get("rm_csrf_token")
        csrf_header = request.headers.get("x-csrf-token")
        if (
            not csrf_cookie
            or not csrf_header
            or not secrets.compare_digest(csrf_cookie, csrf_header)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed: missing or invalid X-CSRF-Token header.",
            )


def _build_user_response(user: User) -> UserResponse:
    """Format safe public user response from User entity."""
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=[r.name for r in user.roles],
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post(
    "/register",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="User self-registration",
    description="Registers a new consumer account with Argon2id password hashing and issues session tokens.",
    dependencies=[Depends(RateLimiter(max_requests=10, window_seconds=60, action="auth:register"))],
)
def register(
    payload: UserRegisterRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> AuthTokenResponse:
    """Register a new user account."""
    client_ip, user_agent = _extract_client_info(request)

    # 1. Check for email conflict
    existing_user = UserRepository.get_by_email(db, payload.email)
    if existing_user is not None:
        OperationsRepository.create_audit_log(
            db,
            actor_type="anonymous",
            action="auth.register_failed",
            target_type="user",
            status="failure",
            metadata_payload={"email": payload.email, "reason": "email_taken", "ip": client_ip},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    # 2. Hash password and persist user
    hashed_pw = hash_password(payload.password)
    user = UserRepository.create(
        db,
        email=payload.email,
        display_name=payload.display_name,
        password_hash=hashed_pw,
        is_active=True,
    )

    # 3. Assign default 'consumer' role
    consumer_role = RoleRepository.get_by_name(db, RoleName.CONSUMER.value)
    if consumer_role is not None:
        RoleRepository.assign_role_to_user(db, user.id, consumer_role.id)

    # Refresh user to load roles
    user = UserRepository.get_by_id(db, user.id) or user
    role_names = [r.name for r in user.roles] or [RoleName.CONSUMER.value]

    # 4. Issue token bundle
    access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "roles": role_names,
    })

    raw_refresh, refresh_hash = generate_refresh_token()
    session_expires = utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    AuthRepository.create_session(
        db,
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        expires_at=session_expires,
        user_agent=user_agent,
        ip_address=client_ip,
    )

    # 5. Audit log
    OperationsRepository.create_audit_log(
        db,
        actor_type="user",
        actor_id=str(user.id),
        action="auth.register",
        target_type="user",
        target_id=str(user.id),
        status="success",
        metadata_payload={"email": user.email, "ip": client_ip},
    )

    db.commit()
    csrf_token = _generate_csrf_token()
    _set_auth_cookies(response, raw_refresh, csrf_token)

    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        csrf_token=csrf_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_build_user_response(user),
    )


@router.post(
    "/login",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User authentication login",
    description="Authenticates email and password, verifies Argon2id hash, and issues token session.",
    dependencies=[Depends(RateLimiter(max_requests=10, window_seconds=60, action="auth:login"))],
)
def login(
    payload: UserLoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> AuthTokenResponse:
    """Authenticate user with email and password."""
    client_ip, user_agent = _extract_client_info(request)

    # 1. Lookup user
    user = UserRepository.get_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        OperationsRepository.create_audit_log(
            db,
            actor_type="anonymous",
            action="auth.login_failed",
            target_type="user",
            status="failure",
            metadata_payload={"email": payload.email, "reason": "invalid_credentials", "ip": client_ip},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Check if user is active
    if not user.is_active:
        OperationsRepository.create_audit_log(
            db,
            actor_type="user",
            actor_id=str(user.id),
            action="auth.login_failed",
            target_type="user",
            target_id=str(user.id),
            status="failure",
            metadata_payload={"email": payload.email, "reason": "account_deactivated", "ip": client_ip},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    # 3. Transparently rehash if Argon2id parameters upgraded
    if user.password_hash and hash_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    role_names = [r.name for r in user.roles]

    # 4. Issue access and refresh tokens
    access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "roles": role_names,
    })

    raw_refresh, refresh_hash = generate_refresh_token()
    session_expires = utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    AuthRepository.create_session(
        db,
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        expires_at=session_expires,
        user_agent=user_agent,
        ip_address=client_ip,
    )

    # 5. Audit log
    OperationsRepository.create_audit_log(
        db,
        actor_type="user",
        actor_id=str(user.id),
        action="auth.login",
        target_type="user",
        target_id=str(user.id),
        status="success",
        metadata_payload={"email": user.email, "ip": client_ip},
    )

    db.commit()
    csrf_token = _generate_csrf_token()
    _set_auth_cookies(response, raw_refresh, csrf_token)

    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        csrf_token=csrf_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_build_user_response(user),
    )


@router.post(
    "/refresh",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and issue new access token",
    description="Validates opaque refresh token with token-family reuse detection. Atomically rotates token.",
    dependencies=[Depends(RateLimiter(max_requests=30, window_seconds=60, action="auth:refresh"))],
)
def refresh(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    payload: RefreshTokenRequest | None = None,
    cookie_token: Annotated[str | None, Cookie(alias="refresh_token")] = None,
) -> AuthTokenResponse:
    """Exchange rotating refresh token for a new access token and rotated refresh token."""
    client_ip, user_agent = _extract_client_info(request)

    # 1. Resolve raw refresh token from explicit body payload or cookie
    is_cookie_auth = not (payload and payload.refresh_token) and (cookie_token is not None)
    _verify_csrf(request, is_cookie_auth)

    raw_token = (payload.refresh_token if payload and payload.refresh_token else None) or cookie_token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_hash = hash_refresh_token(raw_token)

    # 2. Pessimistic lock on session to prevent concurrent race conditions
    session = AuthRepository.get_session_by_hash_for_update(db, token_hash)
    if session is None:
        OperationsRepository.create_audit_log(
            db,
            actor_type="anonymous",
            action="auth.refresh_failed",
            target_type="auth_session",
            status="failure",
            metadata_payload={"reason": "session_not_found", "ip": client_ip},
        )
        db.commit()
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Token reuse detection: if already revoked/rotated, revoke entire family!
    if session.is_revoked:
        revoked_count = AuthRepository.revoke_family(db, session.token_family)
        OperationsRepository.create_audit_log(
            db,
            actor_type="user",
            actor_id=str(session.user_id),
            action="auth.refresh_reuse_detected",
            target_type="auth_session",
            target_id=str(session.id),
            status="warning",
            metadata_payload={
                "token_family": str(session.token_family),
                "revoked_count": revoked_count,
                "ip": client_ip,
            },
        )
        db.commit()
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token. Token reuse detected.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Check expiration
    if _ensure_utc(session.expires_at) < utc_now():
        AuthRepository.revoke_session(db, session)
        db.commit()
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 5. Check user status
    user = UserRepository.get_by_id(db, session.user_id) or session.user
    if not user or not user.is_active:
        AuthRepository.revoke_family(db, session.token_family)
        db.commit()
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    # 6. Rotate session atomically
    new_raw_refresh, new_refresh_hash = generate_refresh_token()
    new_expires = utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    new_session = AuthRepository.rotate_session(
        db,
        old_session=session,
        new_refresh_token_hash=new_refresh_hash,
        expires_at=new_expires,
        user_agent=user_agent,
        ip_address=client_ip,
    )

    role_names = [r.name for r in user.roles]

    # 7. Issue new access token
    access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "roles": role_names,
    })

    # 8. Audit log
    OperationsRepository.create_audit_log(
        db,
        actor_type="user",
        actor_id=str(user.id),
        action="auth.refresh",
        target_type="auth_session",
        target_id=str(new_session.id),
        status="success",
        metadata_payload={"ip": client_ip},
    )

    db.commit()
    new_csrf_token = _generate_csrf_token()
    _set_auth_cookies(response, new_raw_refresh, new_csrf_token)

    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=new_raw_refresh,
        csrf_token=new_csrf_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_build_user_response(user),
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke authentication session",
    description="Revokes the current refresh token session and clears authentication cookies.",
)
def logout(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    payload: RefreshTokenRequest | None = None,
    cookie_token: Annotated[str | None, Cookie(alias="refresh_token")] = None,
) -> LogoutResponse:
    """Revoke session and logout caller."""
    client_ip, _ = _extract_client_info(request)

    is_cookie_auth = not (payload and payload.refresh_token) and (cookie_token is not None)
    _verify_csrf(request, is_cookie_auth)

    raw_token = (payload.refresh_token if payload and payload.refresh_token else None) or cookie_token

    if raw_token:
        token_hash = hash_refresh_token(raw_token)
        session = AuthRepository.get_session_by_hash(db, token_hash)
        if session is not None and not session.is_revoked:
            AuthRepository.revoke_session(db, session)
            OperationsRepository.create_audit_log(
                db,
                actor_type="user",
                actor_id=str(session.user_id),
                action="auth.logout",
                target_type="auth_session",
                target_id=str(session.id),
                status="success",
                metadata_payload={"ip": client_ip},
            )
            db.commit()

    _clear_auth_cookies(response)
    return LogoutResponse()


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
    description="Retrieves the profile and roles of the currently authenticated identity.",
)
def get_me(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
) -> UserResponse:
    """Return profile for currently authenticated identity."""
    try:
        user_uuid = uuid.UUID(current_user.id)
        user = UserRepository.get_by_id(db, user_uuid)
        if user is not None:
            return _build_user_response(user)
    except ValueError:
        pass

    # Fallback for dev identities
    return UserResponse(
        id=uuid.uuid4(),
        email=current_user.email or "unknown@local",
        display_name=current_user.display_name or "Authenticated User",
        roles=current_user.roles,
        is_active=True,
        created_at=utc_now(),
    )
