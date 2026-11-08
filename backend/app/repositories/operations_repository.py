"""Operations repository for audit logging, import tokens, and jobs reconciliation."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.extraction import IngestionJob
from app.models.operation import AuditLog, ImportToken


class OperationsRepository:
    """Repository handling audit logging, import token verification, and job tracking."""

    @staticmethod
    def create_audit_log(
        db: Session,
        *,
        actor_type: str,
        action: str,
        target_type: str,
        actor_id: str | None = None,
        target_id: str | None = None,
        status: str = "success",
        request_id: str | None = None,
        metadata_payload: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Create an append-only audit log entry."""
        log = AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            status=status,
            request_id=request_id,
            metadata_payload=metadata_payload,
        )
        db.add(log)
        db.flush()
        return log

    @staticmethod
    def list_audit_logs(
        db: Session,
        *,
        target_type: str | None = None,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLog]:
        """Query audit log entries with optional filters."""
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        if target_type:
            stmt = stmt.where(AuditLog.target_type == target_type)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        stmt = stmt.limit(limit).offset(offset)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create_import_token(
        db: Session,
        *,
        token_hash: str,
        expires_at: datetime,
        user_id: uuid.UUID | None = None,
        context: str | None = None,
    ) -> ImportToken:
        """Create an import token entry with hashed credential representation."""
        token = ImportToken(
            token_hash=token_hash,
            user_id=user_id,
            context=context,
            expires_at=expires_at,
        )
        db.add(token)
        db.flush()
        return token

    @staticmethod
    def get_import_token(
        db: Session,
        token_hash: str,
    ) -> ImportToken | None:
        """Retrieve import token by hash."""
        stmt = select(ImportToken).where(ImportToken.token_hash == token_hash)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def revoke_import_token(
        db: Session,
        token_hash: str,
    ) -> bool:
        """Mark an import token as revoked."""
        token = OperationsRepository.get_import_token(db, token_hash)
        if not token:
            return False
        token.is_revoked = True
        db.flush()
        return True

    @staticmethod
    def record_job(
        db: Session,
        *,
        idempotency_key: str,
        job_type: str = "ingestion",
        status: str = "pending",
        record_id: str | None = None,
        listing_id: uuid.UUID | None = None,
        payload: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> IngestionJob:
        """Create or update a job record (reconciling generic and ingestion jobs)."""
        stmt = select(IngestionJob).where(IngestionJob.idempotency_key == idempotency_key)
        job = db.execute(stmt).scalar_one_or_none()
        if job:
            job.status = status
            job.job_type = job_type
            if record_id:
                job.record_id = record_id
            if listing_id:
                job.listing_id = listing_id
            if payload:
                job.payload = payload
            if error_message:
                job.error_message = error_message
        else:
            job = IngestionJob(
                idempotency_key=idempotency_key,
                job_type=job_type,
                status=status,
                record_id=record_id,
                listing_id=listing_id,
                payload=payload,
                error_message=error_message,
            )
            db.add(job)
        db.flush()
        return job
