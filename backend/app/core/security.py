"""Cryptographic security utilities: password hashing, JWT generation and verification, and opaque token hashing."""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

# Argon2id password hasher with secure recommended defaults
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
)


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    if not password:
        raise ValueError("Password cannot be empty")
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    if not hashed_password or not plain_password:
        return False
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def hash_needs_rehash(hashed_password: str) -> bool:
    """Determine whether a stored password hash needs updating due to parameter upgrades."""
    try:
        return _hasher.check_needs_rehash(hashed_password)
    except (InvalidHashError, ValueError):
        return True


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a signed short-lived JWT access token."""
    to_encode = data.copy()
    now = datetime.now(UTC)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
    })

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token signature and expiration."""
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )


def hash_refresh_token(token: str) -> str:
    """Compute SHA-256 hash of an opaque token for secure persistence."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> tuple[str, str]:
    """Generate high-entropy opaque refresh token and its SHA-256 digest.

    Returns:
        tuple[str, str]: (raw_token, token_hash)
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_refresh_token(raw_token)
    return raw_token, token_hash


def hash_api_key(key: str) -> str:
    """Compute HMAC-SHA256 digest of an API key using cryptographic pepper."""
    return hmac.new(
        settings.API_KEY_PEPPER.encode("utf-8"),
        key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

