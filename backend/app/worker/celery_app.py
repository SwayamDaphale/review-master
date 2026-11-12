"""Celery worker application and background task registry for Review Master."""

import logging
from typing import Any

from celery import Celery  # type: ignore[import-untyped]

from app.core.config import settings
from app.db.session import SessionLocal  # noqa: F401
from app.worker.schedules import CELERY_BEAT_SCHEDULE
from app.worker.tasks import register_all_tasks

logger = logging.getLogger("review_master.worker")

celery_app = Celery(
    "review_master",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=300,
    task_soft_time_limit=270,
    result_expires=86400,
    beat_schedule=CELERY_BEAT_SCHEDULE,
)

# Register all modular domain background tasks
register_all_tasks(celery_app)

# Direct task handles for imports in existing tests and domain services
process_review_analysis_task: Any = celery_app.tasks["review_master.process_review_analysis"]
process_listing_ingestion_task: Any = celery_app.tasks["review_master.process_listing_ingestion"]
process_ingestion_task: Any = celery_app.tasks["ingestion.process"]
normalize_attributes_task: Any = celery_app.tasks["attributes.normalize"]
enrich_attributes_task: Any = celery_app.tasks["attributes.enrich"]
resolve_identity_task: Any = celery_app.tasks["identity.resolve"]
calculate_evaluation_task: Any = celery_app.tasks["evaluation.calculate"]
recalculate_evaluation_task: Any = celery_app.tasks["evaluation.recalculate"]
refresh_price_task: Any = celery_app.tasks["price.refresh"]
prepare_comparison_task: Any = celery_app.tasks["comparison.prepare"]
cleanup_maintenance_task: Any = celery_app.tasks["maintenance.cleanup"]
