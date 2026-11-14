"""Structured logging and error-tracking initialization for Review Master.

Provides JSON structured logging in deployed environments, human-readable
logging in development, request correlation ID propagation (X-Request-ID),
sensitive credential scrubbing, and optional Sentry integration.
"""

import contextvars
import json
import logging
import re
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

# Context variable storing the current request/correlation ID
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)

# Regex patterns for scrubbing sensitive values from logs
SENSITIVE_PATTERNS = [
    re.compile(r'(password["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])', re.IGNORECASE),
    re.compile(r'(access_token["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])', re.IGNORECASE),
    re.compile(r'(refresh_token["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])', re.IGNORECASE),
    re.compile(r'(import_code["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])', re.IGNORECASE),
    re.compile(r'(authorization["\']?\s*[:=]\s*["\']Bearer\s+)([^"\']+)(["\'])', re.IGNORECASE),
    re.compile(r'(api_key["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])', re.IGNORECASE),
]


def scrub_sensitive_text(text: str) -> str:
    """Mask credentials and tokens in log strings."""
    if not text:
        return text
    scrubbed = text
    for pattern in SENSITIVE_PATTERNS:
        scrubbed = pattern.sub(r"\1***REDACTED***\3", scrubbed)
    return scrubbed


class JSONLogFormatter(logging.Formatter):
    """JSON structured log formatter for deployed environments."""

    def format(self, record: logging.LogRecord) -> str:
        req_id = request_id_ctx.get("") or getattr(record, "request_id", "")
        message = record.getMessage()
        safe_message = scrub_sensitive_text(message)

        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": safe_message,
            "environment": settings.APP_ENV,
            "service": "review-master-backend",
        }

        if req_id:
            log_entry["request_id"] = req_id

        if record.exc_info:
            log_entry["exception"] = scrub_sensitive_text(
                self.formatException(record.exc_info)
            )

        # Include custom extra fields if present
        for key, val in record.__dict__.items():
            if key not in {
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "levelname", "levelno", "lineno", "module", "msecs",
                "msg", "name", "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName", "request_id",
            }:
                try:
                    json.dumps(val)  # Test serialization
                    log_entry[key] = val
                except (TypeError, ValueError):
                    log_entry[key] = str(val)

        return json.dumps(log_entry)


class DevelopmentLogFormatter(logging.Formatter):
    """Clean, human-readable log formatter for local development."""

    def format(self, record: logging.LogRecord) -> str:
        req_id = request_id_ctx.get("") or getattr(record, "request_id", "")
        prefix = f"[{req_id[:8]}] " if req_id else ""
        record.msg = scrub_sensitive_text(str(record.msg))
        base = super().format(record)
        if prefix:
            return f"{prefix}{base}"
        return base


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Extract or generate request correlation ID, set context, and append to response headers."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming_id = request.headers.get("x-request-id")
        if incoming_id and len(incoming_id) <= 64:
            req_id = incoming_id.strip()
        else:
            req_id = uuid.uuid4().hex

        # Store in contextvar and request state
        token = request_id_ctx.set(req_id)
        request.state.request_id = req_id

        try:
            response = await call_next(request)
            response.headers["x-request-id"] = req_id
            return response
        finally:
            request_id_ctx.reset(token)


def init_logging() -> None:
    """Configure root logger with environment-appropriate formatter."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to prevent duplicate lines
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if settings.APP_ENV in {"production", "staging"}:
        handler.setFormatter(JSONLogFormatter())
    else:
        handler.setFormatter(
            DevelopmentLogFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )

    root_logger.addHandler(handler)


def init_sentry() -> None:
    """Initialize optional Sentry error tracking if SENTRY_DSN is configured."""
    if not settings.SENTRY_DSN:
        logging.getLogger("review_master").debug(
            "SENTRY_DSN not configured; external error reporting disabled."
        )
        return

    try:
        import sentry_sdk  # type: ignore[import-not-found]
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore[import-not-found]
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration  # type: ignore[import-not-found]

        def before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
            # Scrub sensitive headers and body data
            if "request" in event:
                headers = event["request"].get("headers", {})
                for sensitive_header in ("authorization", "cookie", "x-csrf-token", "x-api-key"):
                    if sensitive_header in headers:
                        headers[sensitive_header] = "***REDACTED***"
            return event

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT or settings.APP_ENV,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            before_send=before_send,
            send_default_pii=False,
        )
        logging.getLogger("review_master").info(
            "Sentry error tracking initialized for environment '%s'",
            settings.SENTRY_ENVIRONMENT or settings.APP_ENV,
        )
    except ImportError:
        logging.getLogger("review_master").warning(
            "SENTRY_DSN configured but sentry-sdk package is not installed."
        )
    except (AttributeError, ValueError, RuntimeError) as exc:
        logging.getLogger("review_master").error("Failed to initialize Sentry: %s", exc)
