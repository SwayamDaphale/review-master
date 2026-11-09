"""Ingestion service coordinating extraction validation, listing persistence, identity resolution, and evidence."""

import hashlib
import json
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.extraction.canonical import CanonicalInternalExtraction
from app.contracts.extraction.registry import contract_registry
from app.models.extraction import ExtractionRecord, IngestionJob
from app.models.listing import MarketplaceListing
from app.models.marketplace import Marketplace
from app.models.offer import PriceRecord, SellerOffer
from app.schemas.contract_validator import assert_valid_contract_payload
from app.schemas.extraction import SmartphoneExtractionPayload
from app.services.evidence_service import EvidenceService
from app.services.evidence_storage import EvidenceStorageService
from app.services.identity_resolver import IdentityResolver, ResolutionResult
from app.services.marketplace_registry import MarketplaceRegistry

logger = logging.getLogger("review_master.ingestion_service")


class IngestionService:
    """Core domain service for user-initiated marketplace extraction ingestion."""

    def __init__(self, db: Session):
        self.db = db
        self.resolver = IdentityResolver(db)
        self.evidence_service = EvidenceService(db)

    def ingest_smartphone_extraction(
        self,
        payload: SmartphoneExtractionPayload,
        idempotency_key: str | None = None,
    ) -> tuple[ExtractionRecord, MarketplaceListing, ResolutionResult, int, bool]:
        """Execute atomic transactional ingestion pipeline for smartphone extraction snapshot.

        Returns:
            tuple: (extraction_record, listing, resolution_result, evidence_count, is_newly_created)
        """
        # 1. Validate payload against frozen JSON Schema Draft 2020-12
        raw_dict = payload.model_dump(mode="json")
        assert_valid_contract_payload(raw_dict)

        # 2. Get or ensure Amazon India marketplace exists
        marketplace = self.db.execute(
            select(Marketplace).where(Marketplace.key == payload.source.marketplace)
        ).scalar_one_or_none()

        if not marketplace:
            marketplace = Marketplace(
                key=payload.source.marketplace,
                name="Amazon India",
                adapter="amazon_in_scraper_v1",
                status="active",
                permitted_sources={"category_scopes": ["smartphone"]},
            )
            self.db.add(marketplace)
            self.db.flush()

        # 3. Determine record ID
        rec_id = payload.record_id or str(uuid.uuid4())

        # 4. Check for duplicate/idempotent submission
        existing_record = self.db.execute(
            select(ExtractionRecord).where(ExtractionRecord.record_id == rec_id)
        ).scalar_one_or_none()

        if existing_record and existing_record.listing_id:
            listing = self.db.get(MarketplaceListing, existing_record.listing_id)
            if listing:
                # Re-resolve for return response
                res = self.resolver.resolve_smartphone(
                    marketplace.id,
                    payload.source.asin,
                    payload.normalized,
                    payload.raw_extraction.title,
                )
                logger.info(
                    "Extraction record %s already ingested; returning idempotent response.",
                    rec_id,
                )
                return (existing_record, listing, res, 0, False)

        # 5. Persist ExtractionRecord (audit trail)
        storage_key = (
            f"extractions/{payload.source.extracted_at.year}/"
            f"{payload.source.extracted_at.month:02d}/{rec_id}.json"
        )

        extraction_record = ExtractionRecord(
            record_id=rec_id,
            marketplace_id=marketplace.id,
            schema_version=payload.schema_version,
            asin=payload.source.asin,
            product_url=payload.source.product_url,
            extraction_method=payload.source.extraction_method,
            extension_version=payload.source.extension_version,
            raw_payload=payload.raw_extraction.model_dump(mode="json"),
            normalized_payload=payload.normalized.model_dump(mode="json"),
            validation_payload=payload.validation.model_dump(mode="json"),
            status=payload.validation.status,
            storage_object_key=storage_key,
            extracted_at=payload.source.extracted_at,
        )
        self.db.add(extraction_record)
        self.db.flush()

        # 6. Canonical Identity & Variant Resolution
        resolution = self.resolver.resolve_smartphone(
            marketplace.id,
            payload.source.asin,
            payload.normalized,
            payload.raw_extraction.title,
        )

        # 7. Marketplace Listing Upsert
        external_id = payload.source.asin or rec_id
        listing = self.db.execute(
            select(MarketplaceListing).where(
                MarketplaceListing.marketplace_id == marketplace.id,
                MarketplaceListing.external_id == external_id,
            )
        ).scalar_one_or_none()

        if not listing:
            listing = MarketplaceListing(
                marketplace_id=marketplace.id,
                external_id=external_id,
                url=payload.source.product_url,
                product_id=resolution.product_id,
                variant_id=resolution.variant_id,
                match_state=resolution.match_state,
                match_confidence=resolution.confidence,
                first_seen_at=payload.source.extracted_at,
                last_seen_at=payload.source.extracted_at,
                raw_metadata={"page_title": payload.source.page_title},
            )
            self.db.add(listing)
            self.db.flush()
        else:
            listing.last_seen_at = payload.source.extracted_at
            listing.url = payload.source.product_url
            if resolution.match_state == "confirmed" or (
                listing.match_state != "confirmed"
                and resolution.match_state in ("confirmed", "probable")
            ):
                listing.product_id = resolution.product_id
                listing.variant_id = resolution.variant_id
                listing.match_state = resolution.match_state
                listing.match_confidence = resolution.confidence
            self.db.flush()

        extraction_record.listing_id = listing.id

        # 8. Seller Offer & Price History Tracking
        has_commercial_data = (
            payload.normalized.price_amount is not None
            or payload.normalized.availability is not None
        )
        if has_commercial_data:
            offer = (
                self.db.execute(
                    select(SellerOffer).where(SellerOffer.listing_id == listing.id)
                )
                .scalars()
                .first()
            )

            current_price_dec = (
                Decimal(str(payload.normalized.price_amount))
                if payload.normalized.price_amount is not None
                else None
            )

            if not offer:
                offer = SellerOffer(
                    listing_id=listing.id,
                    seller="Amazon India Seller",
                    current_price=current_price_dec,
                    currency=payload.normalized.currency or "INR",
                    availability=payload.normalized.availability,
                    observed_at=payload.source.extracted_at,
                    source=payload.source.extraction_method,
                    provenance={
                        "asin": external_id,
                        "extraction_record_id": str(extraction_record.id),
                    },
                )
                self.db.add(offer)
                self.db.flush()
            else:
                offer.current_price = current_price_dec
                offer.availability = payload.normalized.availability
                offer.observed_at = payload.source.extracted_at
                self.db.flush()

            # Append to price history
            price_record = PriceRecord(
                offer_id=offer.id,
                price=current_price_dec,
                currency=payload.normalized.currency or "INR",
                availability=payload.normalized.availability,
                observed_at=payload.source.extracted_at,
                source=payload.source.extraction_method,
                provenance={
                    "asin": external_id,
                    "extraction_record_id": str(extraction_record.id),
                },
            )
            self.db.add(price_record)
            self.db.flush()

        # 9. Evidence Persistence
        evidence_items = self.evidence_service.persist_smartphone_evidence(
            product_id=resolution.product_id,
            variant_id=resolution.variant_id,
            normalized=payload.normalized,
            raw_extraction=payload.raw_extraction,
            extraction_record_id=extraction_record.id,
            observed_at=payload.source.extracted_at,
            source_url=payload.source.product_url,
        )

        # 10. Record Ingestion Job if key was provided
        if idempotency_key:
            job = self.db.execute(
                select(IngestionJob).where(
                    IngestionJob.idempotency_key == idempotency_key
                )
            ).scalar_one_or_none()
            if not job:
                job = IngestionJob(
                    idempotency_key=idempotency_key,
                    status="completed",
                    record_id=rec_id,
                    listing_id=listing.id,
                )
                self.db.add(job)

        self.db.commit()
        logger.info(
            "Successfully ingested extraction %s -> listing %s (match_state=%s, evidence=%d)",
            rec_id,
            listing.id,
            resolution.match_state,
            len(evidence_items),
        )

        return (extraction_record, listing, resolution, len(evidence_items), True)

    def create_durable_ingestion(
        self,
        raw_bytes: bytes,
        payload_dict: dict[str, Any],
        user_id: uuid.UUID | str,
        idempotency_key_header: str | None = None,
    ) -> tuple[IngestionJob, ExtractionRecord | None, str, str, bool]:
        """Atomically validate, store raw evidence, and persist durable IngestionJob record.

        Returns:
            tuple: (job, extraction_record_or_none, contract_name, schema_version, is_duplicate)
        """
        # 1. Compute exact SHA-256 digest of submitted request bytes
        sha256_digest = hashlib.sha256(raw_bytes).hexdigest()

        # 2. Identify contract and execute versioned schema validation
        _adapter, contract_name, schema_version = contract_registry.resolve_and_validate(payload_dict)

        # 3. Extract core routing fields based on contract type
        if contract_name == "smartphone_extraction":
            src = payload_dict.get("source") or {}
            mkt = src.get("marketplace")
            url = src.get("product_url")
            rec_id = payload_dict.get("record_id")
            page_type = "product_detail"
            asin = src.get("asin")
            ext_method = src.get("extraction_method")
            ext_ver = src.get("extension_version")
            extracted_at_raw = src.get("extracted_at")
            val_status = (payload_dict.get("validation") or {}).get("status", "valid")
            raw_payload = payload_dict.get("raw_extraction") or {}
            norm_payload = payload_dict.get("normalized") or {}
            val_payload = payload_dict.get("validation") or {}
        else:
            contract_meta = payload_dict.get("contract") or {}
            src = payload_dict.get("source") or {}
            ctx = payload_dict.get("product_context") or {}
            mkt = src.get("marketplace")
            url = src.get("product_url")
            rec_id = contract_meta.get("record_id")
            page_type = src.get("page_type", "product_detail")
            asin = ctx.get("external_id")
            ext_method = src.get("extraction_method")
            ext_ver = src.get("extension_version")
            extracted_at_raw = contract_meta.get("captured_at")
            val_status = (payload_dict.get("validation") or {}).get("status", "valid")
            raw_payload = payload_dict.get("raw_evidence") or {}
            norm_payload = payload_dict.get("extracted_data") or {}
            val_payload = payload_dict.get("validation") or {}

        # 4. Enforce Marketplace, Page Type, and URL security policies
        MarketplaceRegistry.validate_ingestion_scope(mkt, page_type, url)

        # 5. Deterministic Idempotency Key Derivation
        if idempotency_key_header:
            effective_key = idempotency_key_header.strip()
        elif rec_id and len(rec_id.strip()) <= 128:
            effective_key = rec_id.strip()
        else:
            # Deterministic owner-scoped digest key
            effective_key = hashlib.sha256(
                f"{user_id}:{mkt}:{sha256_digest}".encode()
            ).hexdigest()

        # 6. Database Idempotency Check
        existing_job = self.db.execute(
            select(IngestionJob).where(IngestionJob.idempotency_key == effective_key)
        ).scalar_one_or_none()

        if existing_job:
            job_payload = existing_job.payload or {}
            existing_digest = job_payload.get("payload_sha256")
            if existing_digest and existing_digest != sha256_digest:
                logger.warning(
                    "Idempotency conflict for key '%s': existing digest '%s' != new digest '%s'",
                    effective_key,
                    existing_digest,
                    sha256_digest,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency key collision: identical key provided with conflicting payload.",
                )

            logger.info("Idempotent replay for key '%s' (job_id=%s)", effective_key, existing_job.id)
            existing_rec = None
            if existing_job.record_id:
                existing_rec = self.db.execute(
                    select(ExtractionRecord).where(ExtractionRecord.record_id == existing_job.record_id)
                ).scalar_one_or_none()
            return (existing_job, existing_rec, contract_name, schema_version, True)

        # 7. Immutable Evidence Persistence in SeaweedFS
        storage = EvidenceStorageService()
        object_key, _stored_digest, byte_size = storage.store_evidence(
            content_bytes=raw_bytes,
            content_type="application/json",
        )

        # 8. Get or create Marketplace
        marketplace = self.db.execute(
            select(Marketplace).where(Marketplace.key == mkt)
        ).scalar_one_or_none()
        if not marketplace:
            marketplace = Marketplace(
                key=mkt,
                name="Amazon India" if mkt == "amazon.in" else str(mkt),
                adapter="amazon_in_scraper_v1",
                status="active",
                permitted_sources={"category_scopes": ["smartphone", "general"]},
            )
            self.db.add(marketplace)
            self.db.flush()

        # 9. Create ExtractionRecord audit entity
        record_uuid_str = rec_id or str(uuid.uuid4())
        user_uuid = uuid.UUID(str(user_id)) if user_id else None

        extracted_at_dt: datetime
        if isinstance(extracted_at_raw, datetime):
            extracted_at_dt = extracted_at_raw
        elif extracted_at_raw:
            try:
                extracted_at_dt = datetime.fromisoformat(str(extracted_at_raw))
            except ValueError:
                extracted_at_dt = datetime.now()
        else:
            extracted_at_dt = datetime.now()

        extraction_record = ExtractionRecord(
            record_id=record_uuid_str,
            marketplace_id=marketplace.id,
            schema_version=schema_version,
            asin=asin,
            product_url=url,
            extraction_method=ext_method or "browser_extension_user_initiated",
            extension_version=ext_ver or "1.0.0",
            raw_payload=raw_payload,
            normalized_payload=norm_payload,
            validation_payload=val_payload,
            status=val_status,
            storage_object_key=object_key,
            sha256_digest=sha256_digest,
            user_id=user_uuid,
            extracted_at=extracted_at_dt,
        )
        self.db.add(extraction_record)
        self.db.flush()

        # 10. Create durable IngestionJob record
        job_metadata = {
            "user_id": str(user_id) if user_id else None,
            "payload_sha256": sha256_digest,
            "byte_size": byte_size,
            "storage_object_key": object_key,
            "contract_type": contract_name,
            "schema_version": schema_version,
            "product_url": url,
            "marketplace": mkt,
            "record_id": record_uuid_str,
        }

        job = IngestionJob(
            idempotency_key=effective_key,
            job_type="listing_ingestion",
            status="pending",
            record_id=record_uuid_str,
            payload=job_metadata,
        )
        self.db.add(job)
        self.db.commit()

        # 11. Cache job state in Redis for fast polling if client is active
        try:
            from app.services.async_jobs import AsyncJobManager
            manager = AsyncJobManager(self.db)
            if manager.redis:
                manager.update_job_status(job.id, status="pending")
        except Exception as e:  # noqa: BLE001
            logger.debug("Non-blocking Redis job cache write notice: %s", e)

        logger.info(
            "Created durable ingestion job %s (key=%s, record_id=%s, sha256=%s)",
            job.id,
            effective_key,
            record_uuid_str,
            sha256_digest,
        )
        return (job, extraction_record, contract_name, schema_version, False)

    def process_canonical_ingestion(self, job_id: uuid.UUID) -> dict[str, Any]:
        """Execute background listing ingestion, catalog matching, and evidence persistence."""
        job = self.db.get(IngestionJob, job_id)
        if not job:
            raise ValueError(f"Ingestion job '{job_id}' not found.")

        payload_meta = job.payload or {}
        storage_key = payload_meta.get("storage_object_key")
        expected_digest = payload_meta.get("payload_sha256")

        if not storage_key:
            raise ValueError(f"Ingestion job '{job_id}' is missing storage_object_key in payload.")

        # 1. Retrieve raw evidence bytes from SeaweedFS & verify digest
        storage = EvidenceStorageService()
        raw_bytes, _, _ = storage.retrieve_evidence(
            object_key=storage_key,
            expected_sha256=expected_digest,
        )

        # 2. Parse JSON & resolve canonical model
        payload_dict = json.loads(raw_bytes.decode("utf-8"))
        canonical: CanonicalInternalExtraction = contract_registry.to_canonical(
            payload_dict,
            record_id=job.record_id,
            storage_object_key=storage_key,
            sha256_digest=expected_digest,
        )

        # 3. Ensure Marketplace exists
        marketplace = self.db.execute(
            select(Marketplace).where(Marketplace.key == canonical.marketplace)
        ).scalar_one_or_none()
        if not marketplace:
            marketplace = Marketplace(
                key=canonical.marketplace,
                name="Amazon India" if canonical.marketplace == "amazon.in" else canonical.marketplace,
                adapter="amazon_in_scraper_v1",
                status="active",
                permitted_sources={"category_scopes": ["smartphone", "general"]},
            )
            self.db.add(marketplace)
            self.db.flush()

        # 4. Canonical Identity & Variant Resolution
        resolution = self.resolver.resolve_canonical(
            marketplace_id=marketplace.id,
            asin=canonical.asin,
            canonical=canonical,
        )

        # 5. Marketplace Listing Upsert
        external_id = canonical.asin or canonical.ingestion_record_id
        listing = self.db.execute(
            select(MarketplaceListing).where(
                MarketplaceListing.marketplace_id == marketplace.id,
                MarketplaceListing.external_id == external_id,
            )
        ).scalar_one_or_none()

        if not listing:
            listing = MarketplaceListing(
                marketplace_id=marketplace.id,
                external_id=external_id,
                url=canonical.product_url,
                product_id=resolution.product_id,
                variant_id=resolution.variant_id,
                match_state=resolution.match_state,
                match_confidence=resolution.confidence,
                first_seen_at=canonical.extracted_at,
                last_seen_at=canonical.extracted_at,
                raw_metadata={"page_title": canonical.page_title},
            )
            self.db.add(listing)
            self.db.flush()
        else:
            listing.last_seen_at = canonical.extracted_at
            listing.url = canonical.product_url
            if resolution.match_state == "confirmed" or (
                listing.match_state != "confirmed"
                and resolution.match_state in ("confirmed", "probable")
            ):
                listing.product_id = resolution.product_id
                listing.variant_id = resolution.variant_id
                listing.match_state = resolution.match_state
                listing.match_confidence = resolution.confidence
            self.db.flush()

        # 6. Commercial Offers & Price Records
        if canonical.price_amount is not None or canonical.availability is not None:
            offer = (
                self.db.execute(
                    select(SellerOffer).where(SellerOffer.listing_id == listing.id)
                )
                .scalars()
                .first()
            )
            price_dec = Decimal(str(canonical.price_amount)) if canonical.price_amount is not None else None

            if not offer:
                offer = SellerOffer(
                    listing_id=listing.id,
                    seller=f"{marketplace.name} Seller",
                    current_price=price_dec,
                    currency=canonical.currency or "INR",
                    availability=canonical.availability,
                    observed_at=canonical.extracted_at,
                    source=canonical.extraction_method,
                    provenance={
                        "asin": external_id,
                        "job_id": str(job.id),
                        "record_id": canonical.ingestion_record_id,
                    },
                )
                self.db.add(offer)
                self.db.flush()
            else:
                offer.current_price = price_dec
                offer.availability = canonical.availability
                offer.observed_at = canonical.extracted_at
                self.db.flush()

            # Record historical price
            price_record = PriceRecord(
                offer_id=offer.id,
                price=price_dec,
                currency=canonical.currency or "INR",
                availability=canonical.availability,
                observed_at=canonical.extracted_at,
                source=canonical.extraction_method,
                provenance={
                    "asin": external_id,
                    "job_id": str(job.id),
                    "record_id": canonical.ingestion_record_id,
                },
            )
            self.db.add(price_record)
            self.db.flush()

        # 7. Update ExtractionRecord
        rec = None
        if job.record_id:
            rec = self.db.execute(
                select(ExtractionRecord).where(ExtractionRecord.record_id == job.record_id)
            ).scalar_one_or_none()

        if rec:
            rec.listing_id = listing.id
            rec.status = canonical.validation_status
            self.db.flush()

        # 8. Persist Canonical Evidence & Typed Attributes
        evidence_items = self.evidence_service.persist_canonical_evidence(
            canonical=canonical,
            product_id=resolution.product_id,
            variant_id=resolution.variant_id,
            extraction_record_id=rec.id if rec else job.id,
            observed_at=canonical.extracted_at,
            source_url=canonical.product_url,
        )

        # 9. Update IngestionJob state
        job.listing_id = listing.id
        job.status = "completed"
        current_pl = dict(job.payload or {})
        current_pl["result"] = {
            "listing_id": str(listing.id),
            "product_id": str(resolution.product_id) if resolution.product_id else None,
            "variant_id": str(resolution.variant_id) if resolution.variant_id else None,
            "match_state": resolution.match_state,
            "evidence_count": len(evidence_items),
            "status": "completed",
        }
        job.payload = current_pl
        self.db.commit()

        # Update Redis cache
        try:
            from app.services.async_jobs import AsyncJobManager
            manager = AsyncJobManager(self.db)
            manager.update_job_status(
                job.id,
                status="completed",
                result_payload=current_pl["result"],
            )
        except Exception as e:  # noqa: BLE001
            logger.debug("Redis status cache sync notice: %s", e)

        logger.info(
            "Completed ingestion job %s (listing=%s, match_state=%s, evidence=%d)",
            job.id,
            listing.id,
            resolution.match_state,
            len(evidence_items),
        )
        return {
            "job_id": str(job.id),
            "status": "completed",
            "listing_id": str(listing.id),
            "match_state": resolution.match_state,
            "evidence_count": len(evidence_items),
        }

