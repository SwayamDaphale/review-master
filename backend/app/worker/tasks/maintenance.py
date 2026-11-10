"""Background tasks for operational maintenance, stale job recovery, and cleanup."""

import logging
from typing import Any

from celery import Celery, Task  # type: ignore[import-untyped]
from sqlalchemy import delete

import app.worker.celery_app as ca
from app.db.base import utc_now
from app.models.operation import ImportToken
from app.worker.services.job_service import DurableJobService

logger = logging.getLogger("review_master.tasks.maintenance")


def register_maintenance_tasks(celery_app: Celery) -> None:
    """Register periodic maintenance and cleanup tasks."""

    @celery_app.task(
        bind=True,
        name="maintenance.cleanup",
        max_retries=2,
        default_retry_delay=10,
    )
    def cleanup_maintenance(self: Task) -> dict[str, Any]:
        """Sweep expired worker heartbeats and clean up expired import tokens."""
        db = ca.SessionLocal()
        try:
            job_service = DurableJobService(db)

            # 1. Recover stale jobs whose worker heartbeats expired (> 15 minutes)
            recovered = job_service.recover_stale_jobs(stale_threshold_seconds=900)

            # 2. Clean up expired import tokens
            now = utc_now()
            del_stmt = delete(ImportToken).where(
                ImportToken.expires_at.is_not(None),
                ImportToken.expires_at < now,
            )
            res = db.execute(del_stmt)
            expired_tokens_count = int(getattr(res, "rowcount", 0) or 0)

            db.commit()

            logger.info(
                "Maintenance cleanup complete: %d stale jobs recovered, %d expired tokens removed.",
                len(recovered),
                expired_tokens_count,
            )

            return {
                "recovered_jobs_count": len(recovered),
                "recovered_jobs": recovered,
                "expired_tokens_removed": expired_tokens_count,
                "status": "completed",
            }

        except Exception as exc:
            logger.error("Error running maintenance cleanup: %s", exc)
            db.rollback()
            raise
        finally:
            db.close()
