"""Durable background job management service with PostgreSQL persistence and Redis acceleration."""

import datetime
import json
import logging
import random
import time
import uuid
from typing import Any

import redis
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.rate_limit import get_redis_client
from app.db.base import utc_now
from app.models.extraction import IngestionJob
from app.models.job import Job

logger = logging.getLogger("review_master.job_service")


class DurableJobService:
    """Orchestrates durable background job state transitions, heartbeats, retries, and reconciliation."""

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
        if "Bearer " in cleaned or "sk-" in cleaned or "key=" in cleaned.lower():
            return "Task execution failed due to an upstream provider error."
        return cleaned[:200]

    @staticmethod
    def calculate_backoff(
        attempt: int,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        jitter: bool = True,
    ) -> float:
        """Calculate bounded exponential backoff with optional jitter."""
        delay = min(max_delay, base_delay * (2 ** max(0, attempt - 1)))
        if jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        return round(delay, 2)

    def create_or_get_job(
        self,
        *,
        idempotency_key: str,
        job_type: str = "generic",
        payload: dict[str, Any] | None = None,
        user_id: uuid.UUID | str | None = None,
        correlation_id: str | None = None,
        max_retries: int = 3,
    ) -> tuple[Job, bool]:
        """Atomically create a new job or return existing job if duplicate.

        Returns:
            tuple[Job, bool]: (job, was_created)
        """
        stmt = select(Job).where(Job.idempotency_key == idempotency_key)
        existing = self.db.execute(stmt).scalar_one_or_none()
        if existing:
            return existing, False

        parsed_user_id = (
            uuid.UUID(str(user_id)) if user_id and str(user_id).strip() else None
        )

        job = Job(
            idempotency_key=idempotency_key,
            job_type=job_type,
            status="pending",
            user_id=parsed_user_id,
            correlation_id=correlation_id,
            max_retries=max_retries,
            payload=payload or {},
        )
        self.db.add(job)
        self.db.flush()

        if self.redis:
            try:
                job_state = {
                    "job_id": str(job.id),
                    "job_type": job_type,
                    "user_id": str(parsed_user_id) if parsed_user_id else None,
                    "status": "pending",
                    "retry_count": 0,
                    "max_retries": max_retries,
                    "correlation_id": correlation_id,
                    "created_at": time.time(),
                    "payload": payload or {},
                }
                self.redis.set(f"job:{job.id}", json.dumps(job_state), ex=86400)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to cache job state in Redis: %s", e)

        return job, True

    def start_job(
        self,
        job_id: uuid.UUID,
        worker_id: str | None = None,
    ) -> Job | None:
        """Mark job as running with initial heartbeat and worker assignment."""
        job = self.db.get(Job, job_id)
        now = utc_now()
        if job:
            job.status = "running"
            job.started_at = now
            job.heartbeat_at = now
            if worker_id:
                job.worker_id = worker_id
            self.db.flush()

        # Also sync ingestion_jobs if present
        ing_job = self.db.get(IngestionJob, job_id)
        if ing_job:
            ing_job.status = "running"
            ing_job.started_at = now
            ing_job.heartbeat_at = now
            if worker_id:
                ing_job.worker_id = worker_id
            self.db.flush()

        if self.redis:
            try:
                cache_key = f"job:{job_id}"
                cached = self.redis.get(cache_key)
                state = json.loads(cached) if cached else {}
                state.update(
                    {
                        "status": "running",
                        "started_at": time.time(),
                        "heartbeat_at": time.time(),
                        "worker_id": worker_id,
                    }
                )
                self.redis.set(cache_key, json.dumps(state), ex=86400)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to update running state in Redis: %s", e)

        return job

    def record_heartbeat(
        self,
        job_id: uuid.UUID,
        worker_id: str | None = None,
    ) -> bool:
        """Record worker heartbeat timestamp to prevent stale job recovery."""
        now = utc_now()
        job = self.db.get(Job, job_id)
        if job:
            job.heartbeat_at = now
            if worker_id:
                job.worker_id = worker_id

        ing_job = self.db.get(IngestionJob, job_id)
        if ing_job:
            ing_job.heartbeat_at = now
            if worker_id:
                ing_job.worker_id = worker_id

        if job or ing_job:
            self.db.flush()

        if self.redis:
            try:
                cache_key = f"job:{job_id}"
                cached = self.redis.get(cache_key)
                if cached:
                    state = json.loads(cached)
                    state["heartbeat_at"] = time.time()
                    if worker_id:
                        state["worker_id"] = worker_id
                    self.redis.set(cache_key, json.dumps(state), ex=86400)
            except Exception as e:  # noqa: BLE001
                logger.debug("Failed to record heartbeat in Redis: %s", e)
        return bool(job or ing_job)

    def complete_job(
        self,
        job_id: uuid.UUID,
        result_payload: dict[str, Any] | None = None,
    ) -> Job | None:
        """Mark job as successfully completed."""
        now = utc_now()
        job = self.db.get(Job, job_id)
        if job:
            job.status = "completed"
            job.completed_at = now
            job.result = result_payload
            self.db.flush()

        ing_job = self.db.get(IngestionJob, job_id)
        if ing_job:
            ing_job.status = "completed"
            ing_job.completed_at = now
            if result_payload:
                current_p = dict(ing_job.payload or {})
                current_p["result"] = result_payload
                ing_job.payload = current_p
            self.db.flush()

        if self.redis:
            try:
                cache_key = f"job:{job_id}"
                cached = self.redis.get(cache_key)
                state = json.loads(cached) if cached else {}
                state.update(
                    {
                        "status": "completed",
                        "completed_at": time.time(),
                        "result": result_payload,
                    }
                )
                self.redis.set(cache_key, json.dumps(state), ex=86400)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to record completion in Redis: %s", e)

        return job

    def fail_job(
        self,
        job_id: uuid.UUID,
        error_message: str | None,
        can_retry: bool = False,
    ) -> Job | None:
        """Record job failure or schedule bounded retry."""
        sanitized_err = self.sanitize_error(error_message)
        now = utc_now()
        job = self.db.get(Job, job_id)
        target_status = "failed"

        if job:
            job.retry_count += 1
            if can_retry and job.retry_count <= job.max_retries:
                job.status = "retrying"
                target_status = "retrying"
            else:
                job.status = "failed"
                job.completed_at = now
                target_status = "failed"
            job.error_message = sanitized_err
            self.db.flush()

        ing_job = self.db.get(IngestionJob, job_id)
        if ing_job:
            ing_job.retry_count += 1
            if can_retry and ing_job.retry_count <= ing_job.max_retries:
                ing_job.status = "retrying"
                target_status = "retrying"
            else:
                ing_job.status = "failed"
                ing_job.completed_at = now
                target_status = "failed"
            ing_job.error_message = sanitized_err
            self.db.flush()

        if self.redis:
            try:
                cache_key = f"job:{job_id}"
                cached = self.redis.get(cache_key)
                state = json.loads(cached) if cached else {}
                state.update(
                    {
                        "status": target_status,
                        "retry_count": state.get("retry_count", 0) + 1,
                        "error": sanitized_err,
                        "updated_at": time.time(),
                    }
                )
                if target_status == "failed":
                    state["completed_at"] = time.time()
                self.redis.set(cache_key, json.dumps(state), ex=86400)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to update failure state in Redis: %s", e)

        return job

    def get_job_status(self, job_id: uuid.UUID) -> dict[str, Any] | None:
        """Fetch sanitized job status checking Redis first, then PostgreSQL."""
        if self.redis:
            try:
                cached = self.redis.get(f"job:{job_id}")
                if cached:
                    state = json.loads(cached)
                    res = state.get("result") or {}
                    created_val = state.get("created_at")
                    created_iso = (
                        datetime.datetime.fromtimestamp(
                            created_val, tz=datetime.UTC
                        ).isoformat()
                        if isinstance(created_val, (int, float))
                        else str(created_val)
                        if created_val
                        else None
                    )
                    completed_val = state.get("completed_at")
                    completed_iso = (
                        datetime.datetime.fromtimestamp(
                            completed_val, tz=datetime.UTC
                        ).isoformat()
                        if isinstance(completed_val, (int, float))
                        else str(completed_val)
                        if completed_val
                        else None
                    )
                    return {
                        "job_id": str(job_id),
                        "job_type": state.get("job_type", "generic"),
                        "status": state.get("status", "pending"),
                        "user_id": state.get("user_id"),
                        "correlation_id": state.get("correlation_id"),
                        "retry_count": state.get("retry_count", 0),
                        "created_at": created_iso,
                        "completed_at": completed_iso
                        if state.get("status") in ("completed", "failed")
                        else None,
                        "error_summary": self.sanitize_error(state.get("error")),
                        "result_summary": res if res else None,
                    }
            except Exception as e:  # noqa: BLE001
                logger.debug("Redis read error for job %s: %s", job_id, e)

        # Fallback 1: Check Job table
        job = self.db.get(Job, job_id)
        if job:
            return {
                "job_id": str(job.id),
                "job_type": job.job_type,
                "status": job.status,
                "user_id": str(job.user_id) if job.user_id else None,
                "correlation_id": job.correlation_id,
                "retry_count": job.retry_count,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "completed_at": job.completed_at.isoformat()
                if job.completed_at
                else None,
                "error_summary": self.sanitize_error(job.error_message),
                "result_summary": job.result,
            }

        # Fallback 2: Check IngestionJob table
        ing_job = self.db.get(IngestionJob, job_id)
        if ing_job:
            payload = ing_job.payload or {}
            res = payload.get("result") or {}
            result_summary = (
                {"analysis_id": res.get("analysis_id"), "status": res.get("status")}
                if "analysis_id" in res
                else (res if res else None)
            )
            return {
                "job_id": str(ing_job.id),
                "job_type": ing_job.job_type,
                "status": ing_job.status,
                "user_id": str(ing_job.user_id)
                if ing_job.user_id
                else payload.get("user_id"),
                "correlation_id": ing_job.correlation_id,
                "retry_count": ing_job.retry_count,
                "created_at": ing_job.created_at.isoformat()
                if ing_job.created_at
                else None,
                "completed_at": ing_job.completed_at.isoformat()
                if ing_job.completed_at
                else (
                    ing_job.updated_at.isoformat()
                    if ing_job.status in ("completed", "failed") and ing_job.updated_at
                    else None
                ),
                "error_summary": self.sanitize_error(ing_job.error_message),
                "result_summary": result_summary,
            }

        return None

    def redispatch_job(
        self,
        job_id: uuid.UUID,
        job_type: str,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        """Safely redispatch a recovered task to Celery broker without duplicating work."""
        from app.worker.celery_app import celery_app

        payload = payload or {}
        job_id_str = str(job_id)

        try:
            if job_type in (
                "ingestion",
                "ingestion.process",
                "review_master.process_listing_ingestion",
            ):
                celery_app.send_task("ingestion.process", args=[job_id_str])
                return True
            if job_type in (
                "review_analysis",
                "review_master.process_review_analysis",
            ):
                review_text = payload.get("review_text", "")
                celery_app.send_task(
                    "review_master.process_review_analysis",
                    args=[job_id_str, review_text],
                    kwargs={
                        "product_id_str": payload.get("product_id"),
                        "variant_id_str": payload.get("variant_id"),
                        "source_evidence_id_str": payload.get("source_evidence_id"),
                        "review_source_id": payload.get("review_source_id"),
                    },
                )
                return True
            if job_type == "attributes.normalize":
                variant_id = payload.get("variant_id") or payload.get("variant_id_str")
                if variant_id:
                    celery_app.send_task(
                        "attributes.normalize",
                        args=[str(variant_id)],
                        kwargs={"job_id_str": job_id_str},
                    )
                    return True
            if job_type == "attributes.enrich":
                raw_text = payload.get("raw_text", "")
                celery_app.send_task(
                    "attributes.enrich",
                    args=[raw_text],
                    kwargs={
                        "variant_id_str": payload.get("variant_id"),
                        "source_evidence_id_str": payload.get("source_evidence_id"),
                        "job_id_str": job_id_str,
                    },
                )
                return True
            if job_type == "identity.resolve":
                celery_app.send_task(
                    "identity.resolve",
                    kwargs={
                        "marketplace_code": payload.get("marketplace_code", "amazon.in"),
                        "asin": payload.get("asin", ""),
                        "title": payload.get("title"),
                        "brand": payload.get("brand"),
                        "model_name": payload.get("model_name"),
                        "job_id_str": job_id_str,
                    },
                )
                return True
            if job_type == "evaluation.calculate":
                variant_id = payload.get("variant_id") or payload.get("variant_id_str")
                if variant_id:
                    celery_app.send_task(
                        "evaluation.calculate",
                        args=[str(variant_id)],
                        kwargs={"job_id_str": job_id_str},
                    )
                    return True
            if job_type == "price.refresh":
                celery_app.send_task(
                    "price.refresh",
                    kwargs={
                        "listing_id_str": payload.get("listing_id_str"),
                        "new_price": payload.get("new_price"),
                        "currency": payload.get("currency", "INR"),
                        "seller": payload.get("seller"),
                        "job_id_str": job_id_str,
                    },
                )
                return True
            if job_type == "comparison.prepare":
                session_id = payload.get("session_id") or payload.get("session_id_str")
                if session_id:
                    celery_app.send_task(
                        "comparison.prepare",
                        args=[str(session_id)],
                        kwargs={"job_id_str": job_id_str},
                    )
                    return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to redispatch recovered job %s (%s): %s", job_id, job_type, exc)
            return False
        return False

    def retry_job(self, job_id: uuid.UUID) -> bool:
        """Manually or programmatically reset and redispatch a failed job."""
        job = self.db.get(Job, job_id)
        ing_job = self.db.get(IngestionJob, job_id)
        target = job or ing_job
        if not target:
            return False
        target.status = "retrying"
        target.error_message = None
        target.completed_at = None
        self.db.flush()

        if self.redis:
            try:
                cache_key = f"job:{job_id}"
                cached = self.redis.get(cache_key)
                if cached:
                    state = json.loads(cached)
                    state["status"] = "retrying"
                    state["error"] = None
                    self.redis.set(cache_key, json.dumps(state), ex=86400)
            except Exception as e:  # noqa: BLE001
                logger.debug("Failed to sync retry state to Redis: %s", e)

        return self.redispatch_job(
            target.id, target.job_type, getattr(target, "payload", None)
        )

    def recover_stale_jobs(
        self,
        stale_threshold_seconds: int = 900,
        redispatch: bool = True,
    ) -> list[dict[str, Any]]:
        """Identify, lock, and recover or fail jobs stuck in 'running' state with expired heartbeats."""
        threshold_dt = utc_now() - datetime.timedelta(seconds=stale_threshold_seconds)
        recovered: list[dict[str, Any]] = []

        is_sqlite = bool(self.db.bind and self.db.bind.dialect.name == "sqlite")

        # 1. Recover stale Job records with concurrency protection
        stmt_job = select(Job).where(
            Job.status == "running",
            or_(
                Job.heartbeat_at < threshold_dt,
                (Job.heartbeat_at.is_(None)) & (Job.started_at < threshold_dt),
                (Job.heartbeat_at.is_(None))
                & (Job.started_at.is_(None))
                & (Job.created_at < threshold_dt),
            ),
        )
        if not is_sqlite:
            stmt_job = stmt_job.with_for_update(skip_locked=True)

        stale_jobs = self.db.execute(stmt_job).scalars().all()
        for j in stale_jobs:
            j.retry_count += 1
            redispatched = False
            if j.retry_count <= j.max_retries:
                j.status = "retrying"
                j.error_message = (
                    "Execution stalled (worker heartbeat missing); scheduled for retry."
                )
                action = "marked_retrying"
                if redispatch:
                    redispatched = self.redispatch_job(j.id, j.job_type, j.payload)
            else:
                j.status = "failed"
                j.completed_at = utc_now()
                j.error_message = (
                    "Execution timed out: worker heartbeat missing for > 15m."
                )
                action = "marked_failed"

            if self.redis:
                try:
                    c_key = f"job:{j.id}"
                    cached = self.redis.get(c_key)
                    if cached:
                        state = json.loads(cached)
                        state["status"] = j.status
                        state["retry_count"] = j.retry_count
                        state["error"] = j.error_message
                        if j.status == "failed":
                            state["completed_at"] = time.time()
                        self.redis.set(c_key, json.dumps(state), ex=86400)
                except Exception as e:  # noqa: BLE001
                    logger.debug("Failed to sync recovered job to Redis: %s", e)

            recovered.append(
                {
                    "job_id": str(j.id),
                    "job_type": j.job_type,
                    "action": action,
                    "retry_count": j.retry_count,
                    "redispatched": redispatched,
                }
            )

        # 2. Recover stale IngestionJob records with concurrency protection
        stmt_ing = select(IngestionJob).where(
            IngestionJob.status == "running",
            or_(
                IngestionJob.heartbeat_at < threshold_dt,
                (IngestionJob.heartbeat_at.is_(None))
                & (IngestionJob.started_at < threshold_dt),
                (IngestionJob.heartbeat_at.is_(None))
                & (IngestionJob.started_at.is_(None))
                & (IngestionJob.created_at < threshold_dt),
            ),
        )
        if not is_sqlite:
            stmt_ing = stmt_ing.with_for_update(skip_locked=True)

        stale_ings = self.db.execute(stmt_ing).scalars().all()
        for ij in stale_ings:
            ij.retry_count += 1
            redispatched = False
            if ij.retry_count <= ij.max_retries:
                ij.status = "retrying"
                ij.error_message = (
                    "Execution stalled (worker heartbeat missing); scheduled for retry."
                )
                action = "marked_retrying"
                if redispatch:
                    redispatched = self.redispatch_job(ij.id, ij.job_type, ij.payload)
            else:
                ij.status = "failed"
                ij.completed_at = utc_now()
                ij.error_message = (
                    "Execution timed out: worker heartbeat missing for > 15m."
                )
                action = "marked_failed"

            if self.redis:
                try:
                    c_key = f"job:{ij.id}"
                    cached = self.redis.get(c_key)
                    if cached:
                        state = json.loads(cached)
                        state["status"] = ij.status
                        state["retry_count"] = ij.retry_count
                        state["error"] = ij.error_message
                        if ij.status == "failed":
                            state["completed_at"] = time.time()
                        self.redis.set(c_key, json.dumps(state), ex=86400)
                except Exception as e:  # noqa: BLE001
                    logger.debug("Failed to sync recovered job to Redis: %s", e)

            recovered.append(
                {
                    "job_id": str(ij.id),
                    "job_type": ij.job_type,
                    "action": action,
                    "retry_count": ij.retry_count,
                    "redispatched": redispatched,
                }
            )

        if recovered:
            self.db.flush()
            logger.info("Recovered %d stale background jobs.", len(recovered))

        return recovered
