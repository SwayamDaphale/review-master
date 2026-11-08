"""Evidence repository for evidence items and append-only evidence versions."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.base import utc_now
from app.models.evidence import Evidence, EvidenceVersion


class EvidenceRepository:
    """Repository managing evidence records and append-only evidence versions."""

    @staticmethod
    def get_evidence_by_variant(
        db: Session,
        variant_id: uuid.UUID,
    ) -> list[Evidence]:
        """Fetch all evidence records and versions for a variant."""
        stmt = (
            select(Evidence)
            .where(Evidence.variant_id == variant_id)
            .options(selectinload(Evidence.versions))
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create_evidence(
        db: Session,
        *,
        variant_id: uuid.UUID,
        parameter_key: str,
        source_type: str,
        trust_tier: int = 2,
    ) -> Evidence:
        """Create an evidence grouping record."""
        evidence = Evidence(
            variant_id=variant_id,
            parameter_key=parameter_key,
            source_type=source_type,
            trust_tier=trust_tier,
        )
        db.add(evidence)
        db.flush()
        return evidence

    @staticmethod
    def add_version(
        db: Session,
        *,
        evidence_id: uuid.UUID,
        value: dict[str, Any],
        raw_source_span: str | None = None,
        observed_at: datetime | None = None,
        methodology: str | None = None,
        verification_state: str = "unverified",
        source_url: str | None = None,
    ) -> EvidenceVersion:
        """Append a new version to an existing evidence record."""
        # Determine next version number
        count_stmt = select(EvidenceVersion).where(EvidenceVersion.evidence_id == evidence_id)
        existing_versions = db.execute(count_stmt).scalars().all()
        next_ver = len(existing_versions) + 1

        version = EvidenceVersion(
            evidence_id=evidence_id,
            version=next_ver,
            value=value,
            raw_source_span=raw_source_span,
            observed_at=observed_at or utc_now(),
            methodology=methodology,
            verification_state=verification_state,
            source_url=source_url,
        )
        db.add(version)
        db.flush()
        return version
