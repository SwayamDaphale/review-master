"""Celery background worker package for Review Master."""

from app.worker.celery_app import celery_app

__all__ = ["celery_app"]

