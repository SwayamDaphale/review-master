"""Review Master FastAPI application entrypoint.

Provides core application initialization, CORS middleware, liveness monitoring (/healthz),
and a modular structure ready for versioned API routers (/api/v1).
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.logging import RequestIDMiddleware, init_logging, init_sentry
from app.db.session import engine

# Configure environment-appropriate logging and error tracking
init_logging()
init_sentry()
logger = logging.getLogger("review_master")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown procedures."""
    # Log non-sensitive startup configuration summary
    safe_config = settings.safe_summary()
    logger.info(
        "Starting Review Master API backend in '%s' mode", safe_config["app_env"]
    )
    logger.info("Active database endpoint: %s", safe_config["database_url"])
    logger.info("Configured CORS origins: %s", safe_config["cors_origins"])
    yield
    logger.info("Shutting down Review Master API backend")


app = FastAPI(
    title="Review Master API",
    version="0.1.0",
    description="Evidence-driven product evaluation and recommendation platform",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Correlation ID propagation middleware
app.add_middleware(RequestIDMiddleware)

# CORS configuration for web application and browser extension
cors_origins = (
    settings.CORS_ORIGINS
    if isinstance(settings.CORS_ORIGINS, list)
    else [settings.CORS_ORIGINS]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> Response:
    """Safe exception handler preventing stack trace disclosure in production."""
    req_id = getattr(request.state, "request_id", "unknown")
    logger.error("Unhandled server exception [req_id=%s]: %s", req_id, exc)
    if settings.DEBUG:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Internal Server Error: {exc!s}", "request_id": req_id},
            headers={"x-request-id": req_id},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred.", "request_id": req_id},
        headers={"x-request-id": req_id},
    )


@app.get("/healthz", tags=["Health"])
async def healthz() -> dict[str, Any]:
    """Liveness probe endpoint for container orchestration and uptime monitoring."""
    return {
        "status": "ok",
        "app": "review-master-backend",
        "environment": settings.APP_ENV,
    }


@app.get("/readyz", tags=["Health"])
def readyz(response: Response) -> dict[str, Any]:
    """Readiness probe validating core infrastructure connectivity (PostgreSQL)."""
    checks: dict[str, str] = {}
    is_ready = True

    # 1. Check database connectivity
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except (SQLAlchemyError, OSError) as exc:
        is_ready = False
        checks["database"] = f"error: {exc.__class__.__name__}"

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "checks": checks}

    return {"status": "ok", "checks": checks}


# Register versioned API routers
app.include_router(api_v1_router)
