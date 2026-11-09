"""Asynchronous job orchestration for review analysis and batch pipelines."""

import datetime
import json
import logging
import time
import uuid
from typing import Any

import redis
from sqlalchemy.orm import Session

from app.core.rate_limit import get_redis_client
from app.models.extraction import IngestionJob

logger = logging.getLogger("review_master.async_jobs")


class AsyncJobManager:
    """Manages asynchronous processing jobs with Redis-backed status and PostgreSQL persistence."""

    def __init__(self, db: Session, redis_client: redis.Redis | None = None):
        self.db = db
        self.redis = redis_client or get_redis_client()

    @staticmethod
    def sanitize_error(err: str | None) -> str | None:
        """Strip tracebacks, credentials, and internal details from error messages."""
        if not err:
            return None
        cleaned = err.strip()
        if "Traceback" in cleaned:
            lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
            last_line = lines[-1] if lines else "Internal processing error."
            cleaned = f"Task execution failed: {last_line}"
        # Redact potential sensitive tokens or authorization keys
        if "Bearer " in cleaned or "sk-" in cleaned or "key=" in cleaned.lower():
            return "Task execution failed due to an upstream provider error."
        return cleaned[:200]

    def create_or_get_job(
        self,
        *,
        idempotency_key: str,
        job_type: str = "review_analysis",
        payload: dict[str, Any] | None = None,
        user_id: uuid.UUID | str | None = None,
    ) -> tuple[IngestionJob, bool]:
        """Atomically create a new job or return existing job if duplicate.

        Returns:
            tuple[IngestionJob, bool]: (job, was_created)
        """
        # Check database for existing job with idempotency key
        existing = (
            self.db.query(IngestionJob)
            .filter(IngestionJob.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing, False

        full_payload = dict(payload or {})
        if user_id:
            full_payload["user_id"] = str(user_id)

        job = IngestionJob(
            idempotency_key=idempotency_key,
            job_type=job_type,
            status="pending",
            payload=full_payload,
        )
        self.db.add(job)
        self.db.flush()

        if self.redis:
            try:
                job_state = {
                    "job_id": str(job.id),
                    "job_type": job_type,
                    "user_id": str(user_id) if user_id else None,
                    "status": "pending",
                    "retries": 0,
                    "created_at": time.time(),
                    "payload": full_payload,
                }
                self.redis.set(
                    f"job:{job.id}",
                    json.dumps(job_state),
                    ex=86400,  # 24h TTL
                )
            except (
                redis.RedisError,
                ConnectionError,
                OSError,
                json.JSONDecodeError,
            ) as e:
                logger.warning("Failed to cache job state in Redis: %s", e)

        return job, True

    def update_job_status(
        self,
        job_id: uuid.UUID,
        status: str,
        result_payload: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> IngestionJob | None:
        """Update job status in PostgreSQL and Redis."""
        job = self.db.get(IngestionJob, job_id)
        if not job:
            return None

        job.status = status
        if error_message:
            job.error_message = self.sanitize_error(error_message)
        if result_payload:
            current_payload = dict(job.payload or {})
            current_payload["result"] = result_payload
            job.payload = current_payload

        self.db.flush()

        if self.redis:
            try:
                cache_key = f"job:{job_id}"
                cached_data = self.redis.get(cache_key)
                state = json.loads(cached_data) if cached_data else {}
                state.update(
                    {
                        "status": status,
                        "updated_at": time.time(),
                        "result": result_payload,
                        "error": error_message,
                    }
                )
                self.redis.set(cache_key, json.dumps(state), ex=86400)
            except (
                redis.RedisError,
                ConnectionError,
                OSError,
                json.JSONDecodeError,
            ) as e:
                logger.warning("Failed to update job state in Redis: %s", e)

        return job

    def get_job_status(self, job_id: uuid.UUID) -> dict[str, Any] | None:
        """Fetch sanitized job status, checking Redis first then PostgreSQL."""
        # 1. Try Redis cache
        if self.redis:
            try:
                cached = self.redis.get(f"job:{job_id}")
                if cached:
                    state = json.loads(cached)
                    payload = state.get("payload") or {}
                    res = state.get("result") or {}
                    result_summary = (
                        {
                            "analysis_id": res.get("analysis_id"),
                            "status": res.get("status"),
                        }
                        if res
                        else None
                    )

                    created_at_val = state.get("created_at")
                    created_at_iso: str | None
                    if isinstance(created_at_val, (int, float)):
                        created_at_iso = datetime.datetime.fromtimestamp(
                            created_at_val, tz=datetime.UTC
                        ).isoformat()
                    else:
                        created_at_iso = str(created_at_val) if created_at_val else None

                    updated_at_val = state.get("updated_at")
                    completed_at_iso: str | None
                    if isinstance(updated_at_val, (int, float)):
                        completed_at_iso = datetime.datetime.fromtimestamp(
                            updated_at_val, tz=datetime.UTC
                        ).isoformat()
                    else:
                        completed_at_iso = (
                            str(updated_at_val) if updated_at_val else None
                        )

                    return {
                        "job_id": str(job_id),
                        "job_type": state.get("job_type", "review_analysis"),
                        "status": state.get("status", "pending"),
                        "user_id": state.get("user_id") or payload.get("user_id"),
                        "created_at": created_at_iso,
                        "completed_at": completed_at_iso
                        if state.get("status") in ("completed", "failed")
                        else None,
                        "error_summary": self.sanitize_error(state.get("error")),
                        "result_summary": result_summary,
                    }
            except (
                redis.RedisError,
                ConnectionError,
                OSError,
                json.JSONDecodeError,
            ) as e:
                logger.debug("Redis cache miss or read error for job %s: %s", job_id, e)

        # 2. Database fallback
        job = self.db.get(IngestionJob, job_id)
        if not job:
            return None

        payload = job.payload or {}
        res = payload.get("result") or {}
        result_summary = (
            {"analysis_id": res.get("analysis_id"), "status": res.get("status")}
            if res
            else None
        )

        return {
            "job_id": str(job.id),
            "job_type": job.job_type,
            "status": job.status,
            "user_id": payload.get("user_id"),
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.updated_at.isoformat()
            if (job.status in ("completed", "failed") and job.updated_at)
            else None,
            "error_summary": self.sanitize_error(job.error_message),
            "result_summary": result_summary,
        }
