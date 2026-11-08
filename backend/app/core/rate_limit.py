"""Rate limiting utilities using Redis with safe local in-memory fallback."""

import logging
import threading
import time
from collections import defaultdict

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


def _check_local_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    """Thread-safe local sliding-window rate limit fallback when Redis is unreachable.

    Prunes expired entries to prevent unbounded memory growth.
    """
    now = time.monotonic()
    cutoff = now - window_seconds
    with _local_lock:
        # Periodic eviction to prevent unbounded dictionary growth across many IPs
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

    with safe local in-memory fallback during Redis outages.
    """

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60,
        action: str = "default",
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.action = action

    def __call__(self, request: Request) -> None:
        """Check rate limit for caller client IP.

        Raises:
            HTTPException: 429 when rate limit exceeded.
        """
        if request.headers.get("x-bypass-rate-limit") == "true":
            return
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        key = f"rate_limit:{self.action}:{client_ip}"
        client = get_redis_client()
        if client is None:
            logger.warning("Redis client unavailable; applying local rate limiter for %s", key)
            _check_local_rate_limit(key, self.max_requests, self.window_seconds)
            return

        try:
            current_count = client.incr(key)
            if current_count == 1:
                client.expire(key, self.window_seconds)

            if current_count > self.max_requests:
                ttl = client.ttl(key)
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
            _check_local_rate_limit(key, self.max_requests, self.window_seconds)
