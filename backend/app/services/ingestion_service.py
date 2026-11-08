"""Ingestion service coordinating extraction validation, listing persistence, identity resolution, and evidence."""

import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.extraction import ExtractionRecord, IngestionJob
from app.models.listing import MarketplaceListing
from app.models.marketplace import Marketplace
from app.models.offer import PriceRecord, SellerOffer
from app.schemas.contract_validator import assert_valid_contract_payload
from app.schemas.extraction import SmartphoneExtractionPayload
from app.services.evidence_service import EvidenceService
from app.services.identity_resolver import IdentityResolver, ResolutionResult

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
