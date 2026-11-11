"""Deterministic canonical identity and variant resolver service.

Conforms to ADR-0006 and Phase B8 specifications:
Hierarchy: Category -> Product Family -> Product -> Product Variant -> Marketplace Listing -> Seller Offer.
5-Stage Identity Resolution Pipeline:
1. Exact marketplace ID mapping (ExternalIdentityMapping).
2. Trusted listing mapping (MarketplaceListing with verified match_state).
3. Deterministic product and variant fingerprinting.
4. Attribute-based candidate matching and multi-candidate scoring.
5. Ambiguity and Identity Review Queue management.
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.contracts.extraction.canonical import CanonicalInternalExtraction
from app.models.category import Category
from app.models.identity_mapping import ExternalIdentityMapping, IdentityReviewQueue
from app.models.listing import MarketplaceListing
from app.models.product import Product
from app.models.variant import Variant
from app.schemas.extraction import NormalizedSmartphone
from app.services.fingerprint_service import FingerprintService

logger = logging.getLogger("review_master.identity_resolver")

MatchStateType = Literal["confirmed", "probable", "ambiguous", "unmatched"]


@dataclass
class CandidateMatch:
    """Scored catalog product/variant candidate."""

    product: Product
    variant: Variant | None
    score: float
    reasons: list[str]
    conflicts: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolutionResult:
    """Outcome of canonical identity resolution."""

    match_state: MatchStateType
    product_id: uuid.UUID | None
    variant_id: uuid.UUID | None
    product_name: str | None
    variant_label: str | None
    confidence: float
    reasons: list[str]
    review_queue_id: uuid.UUID | None = None
    candidate_scores: dict[str, float] | None = None
    product_fingerprint: str | None = None
    variant_fingerprint: str | None = None


class IdentityResolver:
    """Authoritative deterministic identity resolver for marketplace listings and catalog entities."""

    def __init__(self, db: Session):
        self.db = db

    def resolve_canonical(
        self,
        marketplace_id: uuid.UUID,
        asin: str | None,
        canonical: CanonicalInternalExtraction,
        auto_queue_review: bool = True,
    ) -> ResolutionResult:
        """Resolve canonical identity from a CanonicalInternalExtraction object."""
        ram_val = canonical.get_attribute_value("ram")
        storage_val = canonical.get_attribute_value("storage")
        display_val = canonical.get_attribute_value("display_size")
        battery_val = canonical.get_attribute_value("battery")
        os_val = canonical.get_attribute_value("operating_system")
        processor_val = canonical.get_attribute_value("processor")
        fiveg_val = canonical.get_attribute_value("supports_5g")

        mock_norm = NormalizedSmartphone(
            category="smartphone",
            brand=canonical.normalized_brand,
            model_name=canonical.normalized_model_name,
            model_number=canonical.normalized_model_number,
            ram_gb=float(ram_val) if ram_val is not None else None,
            storage_gb=float(storage_val) if storage_val is not None else None,
            display_size_inches=float(display_val) if display_val is not None else None,
            battery_capacity_mah=int(battery_val) if battery_val is not None else None,
            operating_system=str(os_val) if os_val is not None else None,
            processor=str(processor_val) if processor_val is not None else None,
            supports_5g=bool(fiveg_val) if fiveg_val is not None else None,
            price_amount=float(canonical.price_amount) if canonical.price_amount is not None else None,
            currency=canonical.currency or "INR",  # type: ignore[arg-type]
            rating=float(canonical.rating) if canonical.rating is not None else None,
            review_count=canonical.review_count,
            availability=canonical.availability,  # type: ignore[arg-type]
        )
        return self.resolve_smartphone(
            marketplace_id=marketplace_id,
            asin=asin,
            normalized=mock_norm,
            raw_title=canonical.raw_title,
            record_id=canonical.ingestion_record_id,
            auto_queue_review=auto_queue_review,
        )

    def resolve_smartphone(
        self,
        marketplace_id: uuid.UUID,
        asin: str | None,
        normalized: NormalizedSmartphone,
        raw_title: str | None = None,
        record_id: str | None = None,
        auto_queue_review: bool = True,
    ) -> ResolutionResult:
        """Execute 5-stage identity resolution for a smartphone extraction."""
        reasons: list[str] = []

        # =========================================================================
        # Stage 1: Exact Marketplace ID Mapping (ExternalIdentityMapping)
        # =========================================================================
        if asin:
            ext_mapping = self.db.execute(
                select(ExternalIdentityMapping).where(
                    ExternalIdentityMapping.marketplace_id == marketplace_id,
                    ExternalIdentityMapping.external_id_type == "asin",
                    ExternalIdentityMapping.external_id_value == asin,
                    ExternalIdentityMapping.mapping_status == "active",
                )
            ).scalar_one_or_none()

            if ext_mapping and ext_mapping.verification_status == "verified":
                prod = self.db.get(Product, ext_mapping.product_id) if ext_mapping.product_id else None
                var = self.db.get(Variant, ext_mapping.variant_id) if ext_mapping.variant_id else None
                if prod and var:
                    reasons.append(
                        f"Stage 1: Verified external identity mapping found for ASIN {asin}."
                    )
                    return ResolutionResult(
                        match_state="confirmed",
                        product_id=prod.id,
                        variant_id=var.id,
                        product_name=prod.name,
                        variant_label=var.sku_label,
                        confidence=1.0,
                        reasons=reasons,
                    )
                elif prod and not ext_mapping.variant_id:
                    reasons.append(
                        f"Stage 1: Product mapped from external mapping {asin}; variant requires verification."
                    )

        # =========================================================================
        # Stage 2: Trusted Listing Mapping (MarketplaceListing)
        # =========================================================================
        if asin:
            existing_listing = self.db.execute(
                select(MarketplaceListing).where(
                    MarketplaceListing.marketplace_id == marketplace_id,
                    MarketplaceListing.external_id == asin,
                )
            ).scalar_one_or_none()

            if (
                existing_listing
                and existing_listing.match_state in ("confirmed", "verified")
                and existing_listing.product_id
                and existing_listing.variant_id
            ):
                prod = self.db.get(Product, existing_listing.product_id)
                var = self.db.get(Variant, existing_listing.variant_id)
                if prod and var:
                    reasons.append("Exact match preserved from verified listing record.")
                    return ResolutionResult(
                        match_state="confirmed",
                        product_id=prod.id,
                        variant_id=var.id,
                        product_name=prod.name,
                        variant_label=var.sku_label,
                        confidence=1.0,
                        reasons=reasons,
                    )

        # =========================================================================
        # Stage 3: Deterministic Fingerprint Matching
        # =========================================================================
        category_name = normalized.category or "smartphone"
        incoming_prod_fp: str | None = None
        incoming_var_fp: str | None = None

        if normalized.brand and normalized.model_name:
            incoming_prod_fp = FingerprintService.generate_product_fingerprint(
                category=category_name,
                manufacturer=normalized.brand,
                model_name=normalized.model_name,
                model_number=normalized.model_number,
            )

            # Check if any catalog product fingerprint matches exactly
            stmt_all_prod = select(Product)
            all_products = self.db.execute(stmt_all_prod).scalars().all()
            for prod in all_products:
                prod_fp = FingerprintService.generate_product_fingerprint(
                    category=category_name,
                    manufacturer=prod.manufacturer,
                    model_name=prod.name,
                    model_number=prod.mpn,
                )
                if prod_fp == incoming_prod_fp:
                    reasons.append(
                        f"Stage 3: Deterministic product fingerprint match for '{prod.name}'."
                    )
                    if normalized.ram_gb is not None or normalized.storage_gb is not None:
                        incoming_cfg: dict[str, Any] = {}
                        if normalized.ram_gb is not None:
                            incoming_cfg["ram_gb"] = normalized.ram_gb
                        if normalized.storage_gb is not None:
                            incoming_cfg["storage_gb"] = normalized.storage_gb

                        incoming_var_fp = FingerprintService.generate_variant_fingerprint(
                            product_fingerprint=prod_fp,
                            configuration=incoming_cfg,
                        )

                        for var in prod.variants:
                            var_fp = FingerprintService.generate_variant_fingerprint(
                                product_fingerprint=prod_fp,
                                configuration=var.configuration,
                            )
                            if var_fp == incoming_var_fp:
                                reasons.append(
                                    f"Stage 3: Deterministic variant fingerprint match for '{var.sku_label}'."
                                )
                                return ResolutionResult(
                                    match_state="confirmed",
                                    product_id=prod.id,
                                    variant_id=var.id,
                                    product_name=prod.name,
                                    variant_label=var.sku_label,
                                    confidence=0.98,
                                    reasons=reasons,
                                    product_fingerprint=incoming_prod_fp,
                                    variant_fingerprint=incoming_var_fp,
                                )

        # =========================================================================
        # Stage 4: Attribute-Based Candidate Matching & Scoring
        # =========================================================================
        candidates = self._score_candidates(
            normalized=normalized,
            raw_title=raw_title,
        )

        if not candidates:
            reasons.append(
                f"No candidates matched criteria for brand '{normalized.brand}' and model '{normalized.model_name}'."
            )
            return ResolutionResult(
                match_state="unmatched",
                product_id=None,
                variant_id=None,
                product_name=None,
                variant_label=None,
                confidence=0.0,
                reasons=reasons,
                product_fingerprint=incoming_prod_fp,
            )

        # Sort candidates descending by score
        candidates.sort(key=lambda c: c.score, reverse=True)
        top = candidates[0]
        candidate_scores_dict = {
            f"{c.product.id}_{c.variant.id if c.variant else 'none'}": round(c.score, 3)
            for c in candidates[:5]
        }

        # Check for ambiguity: multiple candidates with close scores (difference < 0.05) pointing to different products
        is_ambiguous = False
        if len(candidates) > 1 and (top.score - candidates[1].score) < 0.05 and top.score >= 0.45:
            distinct_products = {c.product.id for c in candidates if (top.score - c.score) < 0.05}
            if len(distinct_products) > 1:
                is_ambiguous = True
                reasons.append(
                    f"Ambiguity detected: {len(distinct_products)} candidates scored within 0.05 margin."
                )

        # Evaluate match state based on top score and confidence boundaries
        if is_ambiguous:
            match_state: MatchStateType = "ambiguous"
            confidence = 0.50
        elif top.score >= 0.85:
            if top.variant:
                match_state = "confirmed"
                confidence = min(0.98, top.score)
            else:
                match_state = "probable"
                confidence = min(0.85, top.score)
        elif top.score >= 0.50:
            match_state = "probable"
            confidence = top.score
        elif top.score >= 0.35:
            match_state = "ambiguous"
            confidence = top.score
        else:
            match_state = "unmatched"
            confidence = 0.0

        reasons.extend(top.reasons)

        # =========================================================================
        # Stage 5: Ambiguity & Identity Review Queue
        # =========================================================================
        review_queue_id: uuid.UUID | None = None
        if match_state in ("ambiguous", "probable") and auto_queue_review and asin:
            review_queue_entry = self._queue_identity_review(
                record_id=record_id,
                marketplace_id=marketplace_id,
                asin=asin,
                raw_title=raw_title,
                candidates=candidates[:5],
                candidate_scores=candidate_scores_dict,
                reasons=reasons,
            )
            if review_queue_entry:
                review_queue_id = review_queue_entry.id

        return ResolutionResult(
            match_state=match_state,
            product_id=top.product.id if match_state != "unmatched" else None,
            variant_id=top.variant.id if (top.variant and match_state == "confirmed") else None,
            product_name=top.product.name if match_state != "unmatched" else None,
            variant_label=top.variant.sku_label if (top.variant and match_state == "confirmed") else None,
            confidence=round(confidence, 2),
            reasons=reasons,
            review_queue_id=review_queue_id,
            candidate_scores=candidate_scores_dict,
            product_fingerprint=incoming_prod_fp,
            variant_fingerprint=incoming_var_fp,
        )

    def _score_candidates(
        self,
        normalized: NormalizedSmartphone,
        raw_title: str | None,
    ) -> list[CandidateMatch]:
        """Score all plausible catalog products and variants against extracted smartphone attributes."""
        brand_clean = (normalized.brand or "").strip().lower()
        model_clean = (normalized.model_name or "").strip().lower()
        mpn_clean = (normalized.model_number or "").strip()
        cat_key = (normalized.category or "smartphone").strip().lower()

        # Query products in category matching brand or MPN
        stmt = select(Product).join(Product.category).where(Category.key == cat_key)
        if brand_clean:
            stmt = stmt.where(Product.manufacturer.ilike(f"%{brand_clean}%"))
        products = self.db.execute(stmt).scalars().all()

        if not products and mpn_clean:
            products = (
                self.db.execute(
                    select(Product)
                    .join(Product.category)
                    .where(
                        Category.key == cat_key,
                        or_(
                            Product.mpn.ilike(mpn_clean),
                            Product.mpn.ilike(f"%{mpn_clean}%"),
                        ),
                    )
                )
                .scalars()
                .all()
            )

        candidates: list[CandidateMatch] = []
        for prod in products:
            prod_name_lower = prod.name.lower()
            prod_mfr_lower = prod.manufacturer.lower()
            prod_mpn = (prod.mpn or "").lower()

            # Base score calculations
            score = 0.0
            reasons: list[str] = []
            conflicts: dict[str, Any] = {}

            # Brand evaluation
            if brand_clean and brand_clean == prod_mfr_lower:
                score += 0.25
                reasons.append(f"Brand exact match '{prod.manufacturer}' (+0.25)")
            elif brand_clean and (brand_clean in prod_mfr_lower or prod_mfr_lower in brand_clean):
                score += 0.15
                reasons.append(f"Brand substring match '{prod.manufacturer}' (+0.15)")
            elif brand_clean:
                score -= 0.50
                conflicts["brand"] = {"extracted": normalized.brand, "catalog": prod.manufacturer}
                reasons.append(f"Brand mismatch '{prod.manufacturer}' (-0.50)")

            # MPN evaluation
            if mpn_clean:
                if mpn_clean.lower() == prod_mpn:
                    score += 0.45
                    reasons.append(f"MPN exact match '{prod.mpn}' (+0.45)")
                elif mpn_clean.lower() in prod_mpn or prod_mpn in mpn_clean.lower():
                    score += 0.30
                    reasons.append(f"MPN partial match '{prod.mpn}' (+0.30)")

            # Model Name evaluation
            brand_plus_model = f"{brand_clean} {model_clean}".strip()
            if model_clean:
                if model_clean == prod_name_lower or brand_plus_model == prod_name_lower:
                    score += 0.35
                    reasons.append(f"Model exact match '{prod.name}' (+0.35)")
                elif model_clean in prod_name_lower or prod_name_lower in model_clean:
                    score += 0.25
                    reasons.append(f"Model substring match '{prod.name}' (+0.25)")

            # Raw title support
            if raw_title and prod_name_lower in raw_title.lower():
                score += 0.15
                reasons.append("Catalog product name found in raw title (+0.15)")

            # If brand/model score is negligible, skip
            if score < 0.20:
                continue

            # Evaluate Variants
            ext_ram = normalized.ram_gb
            ext_storage = normalized.storage_gb

            # Case A: Hardware configuration is absent in extraction
            if ext_ram is None and ext_storage is None:
                reasons.append("Hardware configuration absent in extraction; variant cannot be confirmed.")
                candidates.append(
                    CandidateMatch(
                        product=prod,
                        variant=None,
                        score=min(0.80, score),
                        reasons=reasons,
                        conflicts=conflicts,
                    )
                )
                continue

            # Case B: Evaluate specific variants for this product
            variants = prod.variants
            if not variants:
                candidates.append(
                    CandidateMatch(
                        product=prod,
                        variant=None,
                        score=score,
                        reasons=reasons,
                        conflicts=conflicts,
                    )
                )
                continue

            for var in variants:
                var_score = score
                var_reasons = list(reasons)
                var_conflicts = dict(conflicts)

                cfg = var.configuration
                var_ram = cfg.get("ram_gb")
                var_storage = cfg.get("storage_gb")

                # RAM comparison
                if ext_ram is not None and var_ram is not None:
                    if int(ext_ram) == int(var_ram):
                        var_score += 0.15
                        var_reasons.append(f"RAM matches {int(ext_ram)}GB (+0.15)")
                    else:
                        var_score -= 0.60
                        var_conflicts["ram_gb"] = {"extracted": ext_ram, "catalog": var_ram}
                        var_reasons.append(f"RAM conflict: extracted {ext_ram}GB vs variant {var_ram}GB")
                elif ext_ram is not None and var_ram is None:
                    var_reasons.append("RAM missing from variant config (neutral)")

                # Storage comparison
                if ext_storage is not None and var_storage is not None:
                    if int(ext_storage) == int(var_storage):
                        var_score += 0.20
                        var_reasons.append(f"Storage matches {int(ext_storage)}GB (+0.20)")
                    else:
                        var_score -= 0.60
                        var_conflicts["storage_gb"] = {"extracted": ext_storage, "catalog": var_storage}
                        var_reasons.append(f"Storage conflict: extracted {ext_storage}GB vs variant {var_storage}GB")
                elif ext_storage is not None and var_storage is None:
                    var_reasons.append("Storage missing from variant config (neutral)")

                if var_score > 0.1:
                    candidates.append(
                        CandidateMatch(
                            product=prod,
                            variant=var,
                            score=var_score,
                            reasons=var_reasons,
                            conflicts=var_conflicts,
                        )
                    )

        return candidates

    def _queue_identity_review(
        self,
        record_id: str | None,
        marketplace_id: uuid.UUID,
        asin: str,
        raw_title: str | None,
        candidates: list[CandidateMatch],
        candidate_scores: dict[str, float],
        reasons: list[str],
    ) -> IdentityReviewQueue | None:
        """Create or update an IdentityReviewQueue entry for ambiguous or low-confidence resolution."""
        try:
            # Check if pending review already exists for this ASIN
            existing = self.db.execute(
                select(IdentityReviewQueue).where(
                    IdentityReviewQueue.marketplace_id == marketplace_id,
                    IdentityReviewQueue.asin == asin,
                    IdentityReviewQueue.status == "pending",
                )
            ).scalar_one_or_none()

            candidate_prod_ids = [str(c.product.id) for c in candidates]
            candidate_var_ids = [str(c.variant.id) for c in candidates if c.variant]

            conflicts: dict[str, Any] = {}
            for c in candidates:
                if c.conflicts:
                    conflicts[str(c.product.id)] = c.conflicts

            if existing:
                existing.candidate_product_ids = candidate_prod_ids
                existing.candidate_variant_ids = candidate_var_ids
                existing.candidate_scores = candidate_scores
                existing.conflicting_attributes = conflicts
                existing.matching_reasons = reasons
                if raw_title:
                    existing.raw_title = raw_title[:512]
                self.db.flush()
                return existing

            review_entry = IdentityReviewQueue(
                record_id=record_id,
                marketplace_id=marketplace_id,
                asin=asin,
                raw_title=raw_title[:512] if raw_title else None,
                candidate_product_ids=candidate_prod_ids,
                candidate_variant_ids=candidate_var_ids,
                candidate_scores=candidate_scores,
                conflicting_attributes=conflicts,
                matching_reasons=reasons,
                status="pending",
            )
            self.db.add(review_entry)
            self.db.flush()
            return review_entry
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to queue identity review for %s: %s", asin, exc)
            return None
