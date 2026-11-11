"""Evidence and provenance service conforming to ADR-0007, DATA_MODEL.md, and Phase B8 specs.

Derives backend-controlled trust tiers at insertion:
- Tier 1: Independent/expert-tested / primary official manufacturer specifications.
- Tier 2: Authenticated marketplace specification claims.
- Tier 3: Verified secondary / community feedback.
- Tier 4: Unverified / weakly sourced evidence.
Client-provided trust tiers are strictly ignored/rejected.
Preserves historical evidence via append-only EvidenceVersion records.
Detects attribute conflicts without overwriting, logging EvidenceConflict and EvidenceVerificationHistory.
"""

import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.extraction.canonical import CanonicalInternalExtraction
from app.db.base import utc_now
from app.models.evidence import Evidence, EvidenceVersion
from app.models.evidence_quality import EvidenceConflict, EvidenceVerificationHistory
from app.repositories.attribute_repository import AttributeRepository
from app.schemas.extraction import NormalizedSmartphone, RawSmartphoneExtraction

logger = logging.getLogger("review_master.evidence_service")

VALID_VERIFICATION_STATES = {
    "unverified",
    "verified",
    "rejected",
    "conflicting",
    "superseded",
}


class EvidenceService:
    """Service managing evidence extraction, provenance, historical versioning, and quality controls."""

    def __init__(self, db: Session):
        self.db = db

    @classmethod
    def determine_trust_tier(
        cls,
        source_type: str,
        client_claimed_tier: Any = None,
    ) -> int:
        """Determine backend-controlled source trust tier.

        Client-submitted trust metadata is strictly ignored to prevent privilege escalation.
        - Tier 1: Official / lab / manufacturer primary specification.
        - Tier 2: Authenticated marketplace listing extraction.
        - Tier 3: Verified secondary / community reviews.
        - Tier 4: Unverified / weak source.
        """
        source_normalized = (source_type or "").lower().strip()
        if source_normalized in ("official", "lab", "manufacturer_spec", "primary_official"):
            return 1
        elif source_normalized in ("marketplace", "authorized_retailer", "dom_extraction"):
            return 2
        elif source_normalized in ("community", "user_review", "crowdsourced", "secondary"):
            return 3
        else:
            return 4

    def update_verification_state(
        self,
        evidence_id: uuid.UUID,
        new_status: str,
        actor_id: uuid.UUID | None,
        actor_role: str,
        reason: str,
        supporting_evidence_id: uuid.UUID | None = None,
    ) -> EvidenceVersion:
        """Transition verification state of the active evidence version and record audit history."""
        if new_status not in VALID_VERIFICATION_STATES:
            raise ValueError(
                f"Invalid verification state '{new_status}'. Allowed: {VALID_VERIFICATION_STATES}"
            )

        ev = self.db.get(Evidence, evidence_id)
        if not ev:
            raise ValueError(f"Evidence {evidence_id} not found.")

        latest_version = (
            self.db.execute(
                select(EvidenceVersion)
                .where(EvidenceVersion.evidence_id == ev.id)
                .order_by(EvidenceVersion.version.desc())
            )
            .scalars()
            .first()
        )
        if not latest_version:
            raise ValueError(f"Evidence {evidence_id} has no version records.")

        prev_status = latest_version.verification_state
        latest_version.verification_state = new_status

        history_record = EvidenceVerificationHistory(
            evidence_id=ev.id,
            previous_status=prev_status,
            new_status=new_status,
            actor_id=actor_id,
            actor_role=actor_role,
            reason=reason,
            supporting_evidence_id=supporting_evidence_id,
        )
        self.db.add(history_record)
        self.db.flush()
        return latest_version

    def resolve_conflict(
        self,
        conflict_id: uuid.UUID,
        resolution_decision: str,
        resolution_reason: str,
        resolved_by: uuid.UUID | None,
    ) -> EvidenceConflict:
        """Resolve an open evidence conflict and update affected evidence records."""
        valid_decisions = {"accept_incoming", "keep_existing", "supersede_both"}
        if resolution_decision not in valid_decisions:
            raise ValueError(
                f"Invalid resolution decision '{resolution_decision}'. Allowed: {valid_decisions}"
            )

        conflict = self.db.get(EvidenceConflict, conflict_id)
        if not conflict:
            raise ValueError(f"Evidence conflict {conflict_id} not found.")

        conflict.status = "resolved"
        conflict.resolution_decision = resolution_decision
        conflict.resolution_reason = resolution_reason
        conflict.resolved_by = resolved_by
        conflict.resolved_at = utc_now()

        # Update evidence records based on decision
        if resolution_decision == "accept_incoming":
            if conflict.incoming_evidence_id:
                self.update_verification_state(
                    evidence_id=conflict.incoming_evidence_id,
                    new_status="verified",
                    actor_id=resolved_by,
                    actor_role="reviewer",
                    reason=f"Conflict resolved: accepted incoming evidence. Reason: {resolution_reason}",
                )
            if conflict.existing_evidence_id:
                self.update_verification_state(
                    evidence_id=conflict.existing_evidence_id,
                    new_status="superseded",
                    actor_id=resolved_by,
                    actor_role="reviewer",
                    reason=f"Conflict resolved: superseded by incoming evidence. Reason: {resolution_reason}",
                )
        elif resolution_decision == "keep_existing":
            if conflict.existing_evidence_id:
                self.update_verification_state(
                    evidence_id=conflict.existing_evidence_id,
                    new_status="verified",
                    actor_id=resolved_by,
                    actor_role="reviewer",
                    reason=f"Conflict resolved: kept existing evidence. Reason: {resolution_reason}",
                )
            if conflict.incoming_evidence_id:
                self.update_verification_state(
                    evidence_id=conflict.incoming_evidence_id,
                    new_status="rejected",
                    actor_id=resolved_by,
                    actor_role="reviewer",
                    reason=f"Conflict resolved: incoming evidence rejected. Reason: {resolution_reason}",
                )
        elif resolution_decision == "supersede_both":
            if conflict.existing_evidence_id:
                self.update_verification_state(
                    evidence_id=conflict.existing_evidence_id,
                    new_status="superseded",
                    actor_id=resolved_by,
                    actor_role="reviewer",
                    reason=f"Conflict resolved: both records superseded. Reason: {resolution_reason}",
                )
            if conflict.incoming_evidence_id:
                self.update_verification_state(
                    evidence_id=conflict.incoming_evidence_id,
                    new_status="superseded",
                    actor_id=resolved_by,
                    actor_role="reviewer",
                    reason=f"Conflict resolved: both records superseded. Reason: {resolution_reason}",
                )

        self.db.flush()
        return conflict

    def _detect_and_record_conflict(
        self,
        ev: Evidence,
        existing_version: EvidenceVersion,
        new_val_payload: dict[str, Any],
        new_unit: str | None,
        product_id: uuid.UUID | None,
        variant_id: uuid.UUID | None,
    ) -> EvidenceConflict | None:
        """Compare existing evidence value with new incoming value; record conflict if values disagree."""
        exist_val = existing_version.value.get("value")
        incom_val = new_val_payload.get("value")

        if exist_val is None or incom_val is None:
            return None

        # Compare values
        is_conflicting = False
        if isinstance(exist_val, (int, float)) and isinstance(incom_val, (int, float)):
            is_conflicting = abs(float(exist_val) - float(incom_val)) > 0.001
        elif isinstance(exist_val, str) and isinstance(incom_val, str):
            is_conflicting = exist_val.strip().lower() != incom_val.strip().lower()
        else:
            is_conflicting = exist_val != incom_val

        if is_conflicting:
            conflict = EvidenceConflict(
                parameter_key=ev.parameter_key,
                existing_value=existing_version.value,
                conflicting_value=new_val_payload,
                existing_unit=existing_version.unit,
                conflicting_unit=new_unit,
                existing_evidence_id=ev.id,
                incoming_evidence_id=ev.id,
                product_id=product_id,
                variant_id=variant_id,
                status="open",
            )
            self.db.add(conflict)
            self.db.flush()
            logger.info(
                "Evidence conflict detected on %s: %s vs %s (conflict_id=%s)",
                ev.parameter_key,
                exist_val,
                incom_val,
                conflict.id,
            )
            return conflict
        return None

    def persist_smartphone_evidence(
        self,
        product_id: uuid.UUID | None,
        variant_id: uuid.UUID | None,
        normalized: NormalizedSmartphone,
        raw_extraction: RawSmartphoneExtraction,
        extraction_record_id: uuid.UUID,
        observed_at: datetime,
        source_url: str,
        client_trust_tier: Any = None,
    ) -> list[Evidence]:
        """Convert extracted technical and commercial parameters into versioned evidence."""
        evidence_items: list[Evidence] = []
        assigned_trust_tier = self.determine_trust_tier("marketplace", client_trust_tier)

        # Map normalized attributes to parameter keys, units, and raw values
        params_to_record: list[dict[str, Any]] = []

        if normalized.ram_gb is not None:
            params_to_record.append(
                {
                    "key": "ram_gb",
                    "value": normalized.ram_gb,
                    "unit": "GB",
                    "raw_span": self._find_spec_raw_span(
                        raw_extraction, ["ram", "memory"]
                    ),
                }
            )

        if normalized.storage_gb is not None:
            params_to_record.append(
                {
                    "key": "storage_gb",
                    "value": normalized.storage_gb,
                    "unit": "GB",
                    "raw_span": self._find_spec_raw_span(
                        raw_extraction, ["storage", "capacity"]
                    ),
                }
            )

        if normalized.battery_capacity_mah is not None:
            params_to_record.append(
                {
                    "key": "battery_capacity_mah",
                    "value": normalized.battery_capacity_mah,
                    "unit": "mAh",
                    "raw_span": self._find_spec_raw_span(raw_extraction, ["battery"]),
                }
            )

        if normalized.display_size_inches is not None:
            params_to_record.append(
                {
                    "key": "display_size_inches",
                    "value": normalized.display_size_inches,
                    "unit": "inches",
                    "raw_span": self._find_spec_raw_span(
                        raw_extraction, ["screen", "display"]
                    ),
                }
            )

        if normalized.operating_system:
            params_to_record.append(
                {
                    "key": "operating_system",
                    "value": normalized.operating_system,
                    "unit": None,
                    "raw_span": self._find_spec_raw_span(
                        raw_extraction, ["os", "operating"]
                    ),
                }
            )

        if normalized.processor:
            params_to_record.append(
                {
                    "key": "processor",
                    "value": normalized.processor,
                    "unit": None,
                    "raw_span": self._find_spec_raw_span(
                        raw_extraction, ["processor", "chipset", "cpu"]
                    ),
                }
            )

        if normalized.supports_5g is not None:
            params_to_record.append(
                {
                    "key": "supports_5g",
                    "value": normalized.supports_5g,
                    "unit": None,
                    "raw_span": self._find_spec_raw_span(
                        raw_extraction, ["cellular", "network", "5g"]
                    ),
                }
            )

        if normalized.price_amount is not None:
            params_to_record.append(
                {
                    "key": "price_amount",
                    "value": normalized.price_amount,
                    "unit": normalized.currency or "INR",
                    "raw_span": raw_extraction.price_text,
                }
            )

        if normalized.rating is not None:
            params_to_record.append(
                {
                    "key": "rating",
                    "value": normalized.rating,
                    "unit": "stars",
                    "raw_span": raw_extraction.rating_text,
                }
            )

        if normalized.review_count is not None:
            params_to_record.append(
                {
                    "key": "review_count",
                    "value": normalized.review_count,
                    "unit": "reviews",
                    "raw_span": raw_extraction.review_count_text,
                }
            )

        for p in params_to_record:
            param_key = p["key"]
            val_payload = {"value": p["value"]}
            unit = p["unit"]
            raw_span = p["raw_span"]

            stmt = select(Evidence).where(
                Evidence.parameter_key == param_key,
                Evidence.source_type == "marketplace",
            )
            if variant_id:
                stmt = stmt.where(Evidence.variant_id == variant_id)
            elif product_id:
                stmt = stmt.where(
                    Evidence.product_id == product_id,
                    Evidence.variant_id.is_(None),
                )
            else:
                continue

            ev = self.db.execute(stmt).scalar_one_or_none()

            if not ev:
                ev = Evidence(
                    product_id=product_id,
                    variant_id=variant_id,
                    parameter_key=param_key,
                    source_type="marketplace",
                    trust_tier=assigned_trust_tier,
                    visibility="public",
                )
                self.db.add(ev)
                self.db.flush()

                new_version = EvidenceVersion(
                    evidence_id=ev.id,
                    version=1,
                    value=val_payload,
                    unit=unit,
                    observed_at=observed_at,
                    methodology="browser_extension_dom_extraction",
                    verification_state="unverified",
                    source_url=source_url,
                    raw_source_span=raw_span,
                    extraction_record_id=extraction_record_id,
                )
                self.db.add(new_version)
                self.db.flush()
                ev.current_version_id = new_version.id
            else:
                latest_version = (
                    self.db.execute(
                        select(EvidenceVersion)
                        .where(EvidenceVersion.evidence_id == ev.id)
                        .order_by(EvidenceVersion.version.desc())
                    )
                    .scalars()
                    .first()
                )

                if latest_version and latest_version.value == val_payload:
                    pass
                else:
                    conflict = None
                    if latest_version:
                        conflict = self._detect_and_record_conflict(
                            ev=ev,
                            existing_version=latest_version,
                            new_val_payload=val_payload,
                            new_unit=unit,
                            product_id=product_id,
                            variant_id=variant_id,
                        )

                    next_ver_num = (latest_version.version + 1) if latest_version else 1
                    ver_state = "conflicting" if conflict else "unverified"
                    new_version = EvidenceVersion(
                        evidence_id=ev.id,
                        version=next_ver_num,
                        value=val_payload,
                        unit=unit,
                        observed_at=observed_at,
                        methodology="browser_extension_dom_extraction",
                        verification_state=ver_state,
                        source_url=source_url,
                        raw_source_span=raw_span,
                        extraction_record_id=extraction_record_id,
                    )
                    self.db.add(new_version)
                    self.db.flush()
                    ev.current_version_id = new_version.id

            evidence_items.append(ev)

        return evidence_items

    def persist_canonical_evidence(
        self,
        canonical: CanonicalInternalExtraction,
        product_id: uuid.UUID | None,
        variant_id: uuid.UUID | None,
        extraction_record_id: uuid.UUID,
        observed_at: datetime,
        source_url: str,
        client_trust_tier: Any = None,
    ) -> list[Evidence]:
        """Convert canonical internal extraction attributes into versioned evidence and typed attributes."""
        evidence_items: list[Evidence] = []
        params_to_record: list[dict[str, Any]] = []
        assigned_trust_tier = self.determine_trust_tier("marketplace", client_trust_tier)

        for attr in canonical.extracted_attributes:
            val = attr.normalized_value if attr.normalized_value is not None else attr.value
            if val is not None:
                params_to_record.append({
                    "key": attr.attribute_key,
                    "value": val,
                    "unit": attr.normalized_unit or attr.original_unit,
                    "raw_span": attr.source_reference,
                    "attr_type": attr.value_type,
                })

        if canonical.rating is not None:
            params_to_record.append({
                "key": "rating",
                "value": float(canonical.rating),
                "unit": "stars",
                "raw_span": canonical.raw_rating_text,
                "attr_type": "numeric",
            })

        if canonical.review_count is not None:
            params_to_record.append({
                "key": "review_count",
                "value": canonical.review_count,
                "unit": "reviews",
                "raw_span": canonical.raw_review_count_text,
                "attr_type": "numeric",
            })

        for p in params_to_record:
            param_key = p["key"]
            val_payload = {"value": p["value"]}
            unit = p["unit"]
            raw_span = p["raw_span"]

            stmt = select(Evidence).where(
                Evidence.parameter_key == param_key,
                Evidence.source_type == "marketplace",
            )
            if variant_id:
                stmt = stmt.where(Evidence.variant_id == variant_id)
            elif product_id:
                stmt = stmt.where(
                    Evidence.product_id == product_id,
                    Evidence.variant_id.is_(None),
                )
            else:
                continue

            ev = self.db.execute(stmt).scalar_one_or_none()
            if not ev:
                ev = Evidence(
                    product_id=product_id,
                    variant_id=variant_id,
                    parameter_key=param_key,
                    source_type="marketplace",
                    trust_tier=assigned_trust_tier,
                    visibility="public",
                )
                self.db.add(ev)
                self.db.flush()

                new_version = EvidenceVersion(
                    evidence_id=ev.id,
                    version=1,
                    value=val_payload,
                    unit=unit,
                    observed_at=observed_at,
                    methodology="browser_extension_dom_extraction",
                    verification_state="unverified",
                    source_url=source_url,
                    raw_source_span=raw_span,
                    extraction_record_id=extraction_record_id,
                )
                self.db.add(new_version)
                self.db.flush()
                ev.current_version_id = new_version.id
            else:
                latest_version = (
                    self.db.execute(
                        select(EvidenceVersion)
                        .where(EvidenceVersion.evidence_id == ev.id)
                        .order_by(EvidenceVersion.version.desc())
                    )
                    .scalars()
                    .first()
                )
                if not latest_version or latest_version.value != val_payload:
                    conflict = None
                    if latest_version:
                        conflict = self._detect_and_record_conflict(
                            ev=ev,
                            existing_version=latest_version,
                            new_val_payload=val_payload,
                            new_unit=unit,
                            product_id=product_id,
                            variant_id=variant_id,
                        )

                    next_ver = (latest_version.version + 1) if latest_version else 1
                    ver_state = "conflicting" if conflict else "unverified"
                    new_version = EvidenceVersion(
                        evidence_id=ev.id,
                        version=next_ver,
                        value=val_payload,
                        unit=unit,
                        observed_at=observed_at,
                        methodology="browser_extension_dom_extraction",
                        verification_state=ver_state,
                        source_url=source_url,
                        raw_source_span=raw_span,
                        extraction_record_id=extraction_record_id,
                    )
                    self.db.add(new_version)
                    self.db.flush()
                    ev.current_version_id = new_version.id

            evidence_items.append(ev)

            # Link to VariantAttributeValue if definition exists
            if variant_id:
                attr_def = AttributeRepository.get_definition_by_key(self.db, param_key)
                if attr_def:
                    val_num = Decimal(str(p["value"])) if p.get("attr_type") == "numeric" else None
                    val_txt = str(p["value"]) if p.get("attr_type") != "numeric" else None
                    AttributeRepository.set_variant_value(
                        self.db,
                        variant_id=variant_id,
                        attribute_id=attr_def.id,
                        value_numeric=val_num,
                        value_text=val_txt,
                        original_unit=unit,
                        canonical_unit=attr_def.canonical_unit or unit,
                        evidence_id=ev.id,
                    )

        return evidence_items

    def _find_spec_raw_span(
        self, raw: RawSmartphoneExtraction, keywords: list[str]
    ) -> str | None:
        """Find matching raw specification text snippet from raw extraction items."""
        for spec in raw.specifications_text:
            label_lower = spec.label.lower()
            if any(k in label_lower for k in keywords):
                return f"{spec.label}: {spec.value}"
        return None
