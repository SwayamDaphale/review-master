"""Review Master FastAPI application entrypoint.

Provides core application initialization, CORS middleware, liveness monitoring (/healthz),
and a modular structure ready for versioned API routers (/api/v1).
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
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


@app.get("/healthz", tags=["Health"])
async def healthz() -> dict[str, Any]:
    """Liveness probe endpoint for container orchestration and uptime monitoring."""
    return {
        "status": "ok",
        "app": "review-master-backend",
        "environment": settings.APP_ENV,
    }
