"""Evidence and provenance service conforming to ADR-0007 and DATA_MODEL.md.

Derives trust tiers at insertion:
- Tier 1: Independent/expert-tested.
- Tier 2: Manufacturer / marketplace / authorized specification.
- Tier 3: Community feedback.
Preserves historical evidence via append-only EvidenceVersion records.
"""

import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.extraction.canonical import CanonicalInternalExtraction
from app.models.evidence import Evidence, EvidenceVersion
from app.repositories.attribute_repository import AttributeRepository
from app.schemas.extraction import NormalizedSmartphone, RawSmartphoneExtraction

logger = logging.getLogger("review_master.evidence_service")


class EvidenceService:
    """Service managing evidence extraction, provenance, and historical versioning."""

    def __init__(self, db: Session):
        self.db = db

    def persist_smartphone_evidence(
        self,
        product_id: uuid.UUID | None,
        variant_id: uuid.UUID | None,
        normalized: NormalizedSmartphone,
        raw_extraction: RawSmartphoneExtraction,
        extraction_record_id: uuid.UUID,
        observed_at: datetime,
        source_url: str,
    ) -> list[Evidence]:
        """Convert extracted technical and commercial parameters into versioned evidence."""
        evidence_items: list[Evidence] = []

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

            # Query existing evidence record
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
                    trust_tier=2,  # Fixed at insertion: Tier 2 for marketplace specification claims
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
                # Evidence exists: check if latest value is identical
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
                    # Same value observed: preserve existing version, update observation timestamp if needed
                    pass
                else:
                    next_ver_num = (latest_version.version + 1) if latest_version else 1
                    new_version = EvidenceVersion(
                        evidence_id=ev.id,
                        version=next_ver_num,
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
    ) -> list[Evidence]:
        """Convert canonical internal extraction attributes into versioned evidence and typed attributes."""
        evidence_items: list[Evidence] = []
        params_to_record: list[dict[str, Any]] = []

        # 1. Map canonical extracted attributes
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

        # 2. Add commercial rating / review count if present
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

        # 3. Upsert evidence records and versions
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
                    trust_tier=2,
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
                    next_ver = (latest_version.version + 1) if latest_version else 1
                    new_version = EvidenceVersion(
                        evidence_id=ev.id,
                        version=next_ver,
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

            evidence_items.append(ev)

            # 4. Link to VariantAttributeValue if definition exists
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
