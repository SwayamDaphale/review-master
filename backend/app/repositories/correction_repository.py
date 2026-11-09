"""Administrative catalog correction repository."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.correction import CatalogCorrection


class CorrectionRepository:
    """Repository handling administrative catalog correction ledger entries."""

    @staticmethod
    def create_correction(
        db: Session,
        *,
        target_type: str,
        target_id: uuid.UUID,
        field_name: str,
        before_value: dict[str, Any] | None,
        after_value: dict[str, Any],
        reason: str,
        actor_id: str,
        evidence_reference: str | None = None,
    ) -> CatalogCorrection:
        """Create and persist an auditable catalog correction record."""
        correction = CatalogCorrection(
            target_type=target_type,
            target_id=target_id,
            field_name=field_name,
            before_value=before_value,
            after_value=after_value,
            reason=reason,
            actor_id=actor_id,
            evidence_reference=evidence_reference,
        )
        db.add(correction)
        db.flush()
        return correction

    @staticmethod
    def list_corrections(
        db: Session,
        *,
        target_type: str | None = None,
        target_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CatalogCorrection]:
        """List catalog correction entries with optional filtering."""
        stmt = select(CatalogCorrection)
        if target_type:
            stmt = stmt.where(CatalogCorrection.target_type == target_type)
        if target_id:
            stmt = stmt.where(CatalogCorrection.target_id == target_id)
        stmt = (
            stmt.order_by(CatalogCorrection.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(db.execute(stmt).scalars().all())
