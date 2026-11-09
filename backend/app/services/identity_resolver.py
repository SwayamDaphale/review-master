"""Deterministic canonical identity and variant resolver service.

Conforms to ADR-0006:
Hierarchy: Family -> Product -> Variant -> Listing -> Offer.
Deterministic resolution order with states: confirmed, probable, ambiguous, unmatched.
Attributes with source=llm or vague title similarity never produce 'confirmed'.
Different RAM/storage configurations are never merged into a single variant.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.contracts.extraction.canonical import CanonicalInternalExtraction
from app.models.listing import MarketplaceListing
from app.models.product import Product
from app.models.variant import Variant
from app.schemas.extraction import NormalizedSmartphone

logger = logging.getLogger("review_master.identity_resolver")

MatchStateType = Literal["confirmed", "probable", "ambiguous", "unmatched"]


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


class IdentityResolver:
    """Authoritative deterministic identity resolver for marketplace listings."""

    def __init__(self, db: Session):
        self.db = db

    def resolve_canonical(
        self,
        marketplace_id: uuid.UUID,
        asin: str | None,
        canonical: CanonicalInternalExtraction,
    ) -> ResolutionResult:
        """Resolve canonical identity from a CanonicalInternalExtraction object."""
        # Convert canonical data into NormalizedSmartphone representation for resolver engine
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
        )

    def resolve_smartphone(
        self,
        marketplace_id: uuid.UUID,
        asin: str | None,
        normalized: NormalizedSmartphone,
        raw_title: str | None = None,
    ) -> ResolutionResult:
        """Resolve an incoming smartphone extraction to canonical product and variant."""
        reasons: list[str] = []

        # 1. Check existing confirmed listing mapping
        if asin:
            existing_listing = self.db.execute(
                select(MarketplaceListing).where(
                    MarketplaceListing.marketplace_id == marketplace_id,
                    MarketplaceListing.external_id == asin,
                )
            ).scalar_one_or_none()

            if (
                existing_listing
                and existing_listing.match_state == "confirmed"
                and existing_listing.product_id
                and existing_listing.variant_id
            ):
                prod = self.db.get(Product, existing_listing.product_id)
                var = self.db.get(Variant, existing_listing.variant_id)
                if prod and var:
                    reasons.append(
                        "Exact match preserved from verified listing record."
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

        # 2. Check authoritative identifiers (MPN / model number)
        matched_product: Product | None = None
        if normalized.model_number:
            mpn_clean = normalized.model_number.strip()
            prod_by_mpn = (
                self.db.execute(
                    select(Product).where(
                        or_(
                            Product.mpn.ilike(mpn_clean),
                            Product.mpn.ilike(f"%{mpn_clean}%"),
                        )
                    )
                )
                .scalars()
                .all()
            )

            if len(prod_by_mpn) == 1:
                matched_product = prod_by_mpn[0]
                reasons.append(
                    f"Matched canonical product by MPN: {matched_product.mpn}"
                )
            elif len(prod_by_mpn) > 1:
                reasons.append(
                    f"Ambiguous match: multiple products matched MPN {mpn_clean}"
                )
                return ResolutionResult(
                    match_state="ambiguous",
                    product_id=None,
                    variant_id=None,
                    product_name=None,
                    variant_label=None,
                    confidence=0.5,
                    reasons=reasons,
                )

        # 3. Match by Brand + Model Name
        if not matched_product and normalized.brand:
            brand_clean = normalized.brand.strip().lower()
            model_clean = (normalized.model_name or "").strip().lower()

            candidate_products = (
                self.db.execute(
                    select(Product).where(
                        Product.manufacturer.ilike(f"%{brand_clean}%")
                    )
                )
                .scalars()
                .all()
            )

            if not candidate_products:
                reasons.append(
                    f"No canonical products found for brand '{normalized.brand}'"
                )
                return ResolutionResult(
                    match_state="unmatched",
                    product_id=None,
                    variant_id=None,
                    product_name=None,
                    variant_label=None,
                    confidence=0.0,
                    reasons=reasons,
                )

            # Filter candidates by model name or raw title
            matching_products: list[Product] = []
            for cp in candidate_products:
                cp_name_lower = cp.name.lower()
                # Check if canonical name matches extracted model or title
                if (
                    model_clean
                    and (model_clean in cp_name_lower or cp_name_lower in model_clean)
                    or raw_title
                    and cp_name_lower in raw_title.lower()
                ):
                    matching_products.append(cp)

            if len(matching_products) == 1:
                matched_product = matching_products[0]
                reasons.append(
                    f"Matched canonical product by name: {matched_product.name}"
                )
            elif len(matching_products) > 1:
                reasons.append(
                    f"Ambiguous: multiple products match brand '{normalized.brand}' and model: "
                    + ", ".join(p.name for p in matching_products)
                )
                return ResolutionResult(
                    match_state="ambiguous",
                    product_id=None,
                    variant_id=None,
                    product_name=None,
                    variant_label=None,
                    confidence=0.5,
                    reasons=reasons,
                )
            else:
                reasons.append(
                    f"Brand '{normalized.brand}' is known, but model '{normalized.model_name}' did not match any canonical product."
                )
                return ResolutionResult(
                    match_state="unmatched",
                    product_id=None,
                    variant_id=None,
                    product_name=None,
                    variant_label=None,
                    confidence=0.0,
                    reasons=reasons,
                )

        if not matched_product:
            reasons.append(
                "Insufficient brand and model information to identify canonical product."
            )
            return ResolutionResult(
                match_state="unmatched",
                product_id=None,
                variant_id=None,
                product_name=None,
                variant_label=None,
                confidence=0.0,
                reasons=reasons,
            )

        # 4. Configuration-level variant matching
        ext_ram = normalized.ram_gb
        ext_storage = normalized.storage_gb

        # If configuration is missing or unknown, product is known but variant cannot be confirmed
        if ext_ram is None and ext_storage is None:
            reasons.append(
                "Hardware configuration (RAM and storage) is absent; variant cannot be confirmed."
            )
            return ResolutionResult(
                match_state="probable",
                product_id=matched_product.id,
                variant_id=None,
                product_name=matched_product.name,
                variant_label=None,
                confidence=0.7,
                reasons=reasons,
            )

        # Retrieve canonical variants for this product
        variants = (
            self.db.execute(
                select(Variant).where(Variant.product_id == matched_product.id)
            )
            .scalars()
            .all()
        )

        matching_variants: list[Variant] = []
        for var in variants:
            cfg = var.configuration
            var_ram = cfg.get("ram_gb")
            var_storage = cfg.get("storage_gb")

            ram_matches = (
                (ext_ram is None) or (var_ram is None) or (int(ext_ram) == int(var_ram))
            )
            storage_matches = (
                (ext_storage is None)
                or (var_storage is None)
                or (int(ext_storage) == int(var_storage))
            )

            if ram_matches and storage_matches:
                matching_variants.append(var)

        if len(matching_variants) == 1:
            matched_var = matching_variants[0]
            # If both RAM and storage were verified or exactly matched
            is_full_config = ext_storage is not None
            match_state: MatchStateType = "confirmed" if is_full_config else "probable"
            reasons.append(f"Matched configuration variant: {matched_var.sku_label}")
            return ResolutionResult(
                match_state=match_state,
                product_id=matched_product.id,
                variant_id=matched_var.id,
                product_name=matched_product.name,
                variant_label=matched_var.sku_label,
                confidence=0.95 if match_state == "confirmed" else 0.8,
                reasons=reasons,
            )

        elif len(matching_variants) > 1:
            reasons.append(
                f"Multiple variants match configuration ({len(matching_variants)} candidates)."
            )
            return ResolutionResult(
                match_state="probable",
                product_id=matched_product.id,
                variant_id=None,
                product_name=matched_product.name,
                variant_label=None,
                confidence=0.75,
                reasons=reasons,
            )
        else:
            reasons.append(
                f"Product '{matched_product.name}' confirmed, but configuration (RAM: {ext_ram}GB, Storage: {ext_storage}GB) represents an uncataloged variant."
            )
            return ResolutionResult(
                match_state="probable",
                product_id=matched_product.id,
                variant_id=None,
                product_name=matched_product.name,
                variant_label=None,
                confidence=0.75,
                reasons=reasons,
            )
