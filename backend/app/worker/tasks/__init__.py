"""Celery tasks registration package."""

from celery import Celery  # type: ignore[import-untyped]

from app.worker.tasks.attributes import register_attribute_tasks
from app.worker.tasks.comparison import register_comparison_tasks
from app.worker.tasks.evaluation import register_evaluation_tasks
from app.worker.tasks.evidence import register_evidence_tasks
from app.worker.tasks.identity import register_identity_tasks
from app.worker.tasks.ingestion import register_ingestion_tasks
from app.worker.tasks.maintenance import register_maintenance_tasks
from app.worker.tasks.pricing import register_pricing_tasks
from app.worker.tasks.review_intelligence import register_review_tasks


def register_all_tasks(celery_app: Celery) -> None:
    """Register all task modules onto the Celery application instance."""
    register_ingestion_tasks(celery_app)
    register_attribute_tasks(celery_app)
    register_identity_tasks(celery_app)
    register_evidence_tasks(celery_app)
    register_evaluation_tasks(celery_app)
    register_pricing_tasks(celery_app)
    register_comparison_tasks(celery_app)
    register_maintenance_tasks(celery_app)
    register_review_tasks(celery_app)

