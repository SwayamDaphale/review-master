"""Rate limiting utilities using Redis with safe local in-memory fallback.

Provides server-side atomic rate limiting, trusted-proxy client IP resolution,
fail-safe policies (fail open vs fail closed), and pre-configured policies
across authentication, ingestion, token handoff, search, and comparisons.
"""

import ipaddress
import logging
import threading
import time
from collections import defaultdict
from typing import Literal

import redis
from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger("review_master.rate_limit")

_redis_client: redis.Redis | None = None
_local_lock = threading.Lock()
_local_buckets: dict[str, list[float]] = defaultdict(list)


def get_redis_client() -> redis.Redis | None:
    """Lazy initialize and return Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
        except (redis.RedisError, ConnectionError, OSError) as e:
            logger.warning("Failed to initialize Redis client for rate limiting: %s", e)
            return None
    return _redis_client


def _is_trusted_proxy(ip_str: str) -> bool:
    """Check whether a client IP matches configured trusted proxy CIDRs/IPs."""
    if not ip_str or ip_str == "unknown":
        return False
    try:
        ip = ipaddress.ip_address(ip_str)
        trusted = settings.TRUSTED_PROXIES
        trusted_list = trusted if isinstance(trusted, list) else [trusted]
        for proxy in trusted_list:
            if not proxy:
                continue
            if "/" in proxy:
                if ip in ipaddress.ip_network(proxy, strict=False):
                    return True
            elif ip == ipaddress.ip_address(proxy):
                return True
    except (ValueError, TypeError):
        return False
    return False


def get_client_ip(request: Request) -> str:
    """Resolve client IP safely, only trusting X-Forwarded-For if peer is a trusted proxy."""
    peer_ip = request.client.host if request.client else "unknown"
    if _is_trusted_proxy(peer_ip):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # First element is original client
            client_ip = forwarded.split(",")[0].strip()
            if client_ip:
                return client_ip
    return peer_ip


def _check_local_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    """Thread-safe local sliding-window rate limit fallback when Redis is unreachable.

    Prunes expired entries to prevent unbounded memory growth.
    """
    now = time.monotonic()
    cutoff = now - window_seconds
    with _local_lock:
        if len(_local_buckets) > 1000:
            stale_keys = [k for k, ts in _local_buckets.items() if not ts or ts[-1] <= cutoff]
            for k in stale_keys:
                del _local_buckets[k]

        timestamps = _local_buckets[key]
        valid = [t for t in timestamps if t > cutoff]
        if len(valid) >= max_requests:
            retry_after = int(valid[0] + window_seconds - now) + 1
            _local_buckets[key] = valid
            headers = {"Retry-After": str(max(retry_after, 1))}
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers=headers,
            )
        valid.append(now)
        _local_buckets[key] = valid


class RateLimiter:
    """FastAPI dependency for IP and action-based rate limiting using Redis sliding counters

    with safe local in-memory fallback and fail-safe policies.
    """

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60,
        action: str = "default",
        identity_dimension: Literal["ip", "user_or_ip", "api_key_or_ip"] = "user_or_ip",
        fail_closed: bool = False,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.action = action
        self.identity_dimension = identity_dimension
        self.fail_closed = fail_closed

    def _resolve_identity(self, request: Request) -> str:
        """Resolve the tracking identifier based on configured identity dimension."""
        client_ip = get_client_ip(request)

        if self.identity_dimension == "user_or_ip":
            # Check if user state was already attached by auth dependency
            user = getattr(request.state, "user", None)
            if user and hasattr(user, "id"):
                return f"user:{user.id}"
            # Check Bearer token prefix to distinguish callers if not yet decoded
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                import hashlib
                token_hash = hashlib.sha256(auth_header.encode()).hexdigest()[:16]
                return f"token:{token_hash}"

        elif self.identity_dimension == "api_key_or_ip":
            api_key = request.headers.get("x-api-key")
            if api_key:
                import hashlib
                key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
                return f"key:{key_hash}"

        return f"ip:{client_ip}"

    def __call__(self, request: Request) -> None:
        """Check rate limit for caller identity.

        Raises:
            HTTPException: 429 when rate limit exceeded.
        """
        if not settings.RATE_LIMIT_ENABLED:
            return

        # In non-production environments (test/dev), allow test suites with explicit header to run unimpeded
        if (
            settings.APP_ENV not in {"production", "staging"}
            and request.headers.get("x-bypass-rate-limit") == "true"
        ):
            return

        identifier = self._resolve_identity(request)
        key = f"rate_limit:{self.action}:{identifier}"

        client = get_redis_client()
        if client is None:
            logger.warning("Redis client unavailable; applying local rate limiter for %s", key)
            try:
                _check_local_rate_limit(key, self.max_requests, self.window_seconds)
            except HTTPException:
                raise
            except Exception as e:
                logger.error("Local rate limiter error (%s) for %s", e, key)
                if self.fail_closed:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Service rate-limiting check unavailable. Please retry shortly.",
                        headers={"Retry-After": "5"},
                    ) from e
            return

        try:
            pipe = client.pipeline()
            pipe.incr(key)
            pipe.ttl(key)
            results = pipe.execute()
            current_count = results[0]
            ttl = results[1]

            if current_count == 1 or ttl == -1:
                client.expire(key, self.window_seconds)
                ttl = self.window_seconds

            if current_count > self.max_requests:
                headers = {"Retry-After": str(max(ttl, 1))}
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers=headers,
                )
        except HTTPException:
            raise
        except (redis.RedisError, ConnectionError, OSError) as e:
            logger.warning("Redis operation failed (%s); applying local rate limiter for %s", e, key)
            try:
                _check_local_rate_limit(key, self.max_requests, self.window_seconds)
            except HTTPException:
                raise
            except Exception as local_err:
                logger.error("Local rate limiter fallback error (%s) for %s", local_err, key)
                if self.fail_closed:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Rate-limiting check temporarily unavailable. Please retry shortly.",
                        headers={"Retry-After": "5"},
                    ) from local_err


# Pre-configured rate limiters for application routers
auth_login_limiter = RateLimiter(
    max_requests=10, window_seconds=60, action="auth_login", fail_closed=True
)
auth_register_limiter = RateLimiter(
    max_requests=5, window_seconds=60, action="auth_register", fail_closed=True
)
auth_refresh_limiter = RateLimiter(
    max_requests=20, window_seconds=60, action="auth_refresh", fail_closed=True
)
import_token_limiter = RateLimiter(
    max_requests=20, window_seconds=60, action="import_token", fail_closed=True
)
comparison_limiter = RateLimiter(
    max_requests=40, window_seconds=60, action="comparison", fail_closed=False
)
recommendation_limiter = RateLimiter(
    max_requests=25, window_seconds=60, action="recommendation", fail_closed=False
)
search_limiter = RateLimiter(
    max_requests=60, window_seconds=60, action="search", fail_closed=False
)
ingest_limiter = RateLimiter(
    max_requests=30, window_seconds=60, action="ingest", fail_closed=True
)
admin_limiter = RateLimiter(
    max_requests=30, window_seconds=60, action="admin", fail_closed=True
)
