"""Comparison domain service coordinating session lifecycle, validation, and matrix computation."""

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attribute import AttributeDefinition, VariantAttributeValue
from app.models.comparison import ComparisonSession
from app.models.listing import MarketplaceListing
from app.models.offer import SellerOffer
from app.models.review_intelligence import ReviewSummary
from app.repositories.comparison_repository import (
    ComparisonRepository,
)
from app.schemas.comparison import (
    ComparisonCommunitySummary,
    ComparisonEvaluationParameter,
    ComparisonEvaluationSummary,
    ComparisonItemSchema,
    ComparisonMatrixItem,
    ComparisonMatrixResponse,
    ComparisonOfferSummary,
    ComparisonSpecificationRow,
)
from app.services.evaluation_cache import EvaluationReuseService

logger = logging.getLogger(__name__)


def _dec_to_float(val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (int, float)):
        return float(val)
    return None


class ComparisonService:
    """Service handling comparison sessions and category matrix generation."""

    def __init__(self, db: Session):
        self.db = db
        self.reuse_service = EvaluationReuseService(db)

    def create_session(
        self,
        *,
        user_id: uuid.UUID | None = None,
        anonymous_session_token: str | None = None,
        title: str | None = None,
        category_id: uuid.UUID | None = None,
    ) -> ComparisonSession:
        """Create comparison session enforcing maximum 2 active sessions."""
        return ComparisonRepository.create_session(
            self.db,
            user_id=user_id,
            anonymous_session_token=anonymous_session_token,
            title=title,
            category_id=category_id,
        )

    def get_session(self, session_id: uuid.UUID) -> ComparisonSession | None:
        """Fetch comparison session by ID."""
        return ComparisonRepository.get_session_by_id(self.db, session_id)

    def list_user_sessions(
        self,
        user_id: uuid.UUID,
        status: str | None = "active",
    ) -> list[ComparisonSession]:
        """List sessions for authenticated user."""
        return ComparisonRepository.get_sessions_by_user(self.db, user_id, status=status)

    def list_anonymous_sessions(
        self,
        token: str,
        status: str | None = "active",
    ) -> list[ComparisonSession]:
        """List sessions for anonymous token."""
        return ComparisonRepository.get_sessions_by_token(self.db, token, status=status)

    def archive_session(self, session_id: uuid.UUID) -> ComparisonSession:
        """Archive an active comparison session."""
        session = ComparisonRepository.archive_session(self.db, session_id)
        self.db.commit()
        return session

    def add_variant_to_session(
        self,
        session_id: uuid.UUID,
        variant_id: uuid.UUID,
        position: int | None = None,
    ) -> ComparisonItemSchema:
        """Add variant ensuring category match and max 5 items limit."""
        session = ComparisonRepository.get_session_by_id(self.db, session_id)
        if not session:
            raise ValueError(f"Comparison session '{session_id}' not found.")

        item = ComparisonRepository.add_variant(
            self.db,
            session=session,
            variant_id=variant_id,
            position=position,
        )
        self.db.commit()

        return ComparisonItemSchema(
            id=item.id,
            session_id=item.session_id,
            product_id=item.product_id,
            variant_id=item.variant_id or variant_id,
            position=item.position,
            created_at=item.created_at,
            product_name=item.product.name if item.product else None,
            sku_label=item.variant.sku_label if item.variant else None,
        )

    def remove_variant_from_session(
        self,
        session_id: uuid.UUID,
        variant_id: uuid.UUID,
    ) -> bool:
        """Remove variant from session."""
        session = ComparisonRepository.get_session_by_id(self.db, session_id)
        if not session:
            raise ValueError(f"Comparison session '{session_id}' not found.")

        removed = ComparisonRepository.remove_variant(
            self.db,
            session=session,
            variant_id=variant_id,
        )
        if removed:
            self.db.commit()
        return removed

    def get_comparison_matrix(
        self,
        session_id: uuid.UUID,
        force_recalculate: bool = False,
    ) -> ComparisonMatrixResponse:
        """Generate category-aware comparison matrix with strictly separated dimensions."""
        session = ComparisonRepository.get_session_by_id(self.db, session_id)
        if not session:
            raise ValueError(f"Comparison session '{session_id}' not found.")

        items = session.items
        category = session.category

        # Resolve category attribute definitions
        attr_defs: list[AttributeDefinition] = []
        if category:
            attr_defs = list(
                self.db.execute(
                    select(AttributeDefinition)
                    .where(AttributeDefinition.category_id == category.id)
                    .order_by(AttributeDefinition.name.asc())
                )
                .scalars()
                .all()
            )

        spec_keys_meta = [{"key": ad.key, "label": ad.name} for ad in attr_defs]

        matrix_items: list[ComparisonMatrixItem] = []

        now = datetime.now(UTC)

        for item in items:
            variant = item.variant
            product = item.product
            if not variant or not product:
                continue

            # 1. Gather attribute specifications
            vav_records = (
                self.db.execute(
                    select(VariantAttributeValue).where(
                        VariantAttributeValue.variant_id == variant.id
                    )
                )
                .scalars()
                .all()
            )
            vav_map = {vav.attribute_id: vav for vav in vav_records}

            specs: dict[str, ComparisonSpecificationRow] = {}
            for ad in attr_defs:
                vav = vav_map.get(ad.id)
                # Fallback to variant configuration JSON if not in VAV table
                cfg_val = (
                    variant.configuration.get(ad.key)
                    if variant.configuration
                    else None
                )

                if vav:
                    val = (
                        vav.value_numeric
                        if vav.value_numeric is not None
                        else (
                            vav.value_boolean
                            if vav.value_boolean is not None
                            else (
                                vav.value_text
                                if vav.value_text is not None
                                else vav.value_json
                            )
                        )
                    )
                    specs[ad.key] = ComparisonSpecificationRow(
                        key=ad.key,
                        display_label=ad.name,
                        raw_value=vav.raw_value,
                        canonical_value=_dec_to_float(val) if (isinstance(val, (Decimal, int, float)) and not isinstance(val, bool)) else val,
                        unit=vav.canonical_unit or ad.canonical_unit or ad.unit,
                        is_missing=False,
                    )
                elif cfg_val is not None:
                    specs[ad.key] = ComparisonSpecificationRow(
                        key=ad.key,
                        display_label=ad.name,
                        raw_value=str(cfg_val),
                        canonical_value=_dec_to_float(cfg_val) if (isinstance(cfg_val, (Decimal, int, float)) and not isinstance(cfg_val, bool)) else cfg_val,
                        unit=ad.canonical_unit or ad.unit,
                        is_missing=False,
                    )
                else:
                    # Missing value explicitly preserved
                    specs[ad.key] = ComparisonSpecificationRow(
                        key=ad.key,
                        display_label=ad.name,
                        raw_value=None,
                        canonical_value=None,
                        unit=ad.canonical_unit or ad.unit,
                        is_missing=True,
                    )

            # 2. Gather evaluation dimension via EvaluationReuseService
            evaluation_summary = ComparisonEvaluationSummary()
            try:
                evaluation = self.reuse_service.get_or_evaluate_variant(
                    variant.id, force_recalculate=force_recalculate
                )
                if evaluation:
                    param_list = [
                        ComparisonEvaluationParameter(
                            key=p.parameter_key,
                            name=p.parameter_key.replace("_", " ").title(),
                            score=_dec_to_float(p.score),
                            status=p.status,
                            weight=_dec_to_float(p.weight),
                            is_critical=p.is_critical,
                            trust_tier=(p.explanation_data or {}).get("trust_tier") if p.explanation_data else None,
                            limitations=(p.explanation_data or {}).get("limitations") if p.explanation_data else None,
                        )
                        for p in evaluation.parameter_results
                    ]

                    evaluation_summary = ComparisonEvaluationSummary(
                        evaluation_id=evaluation.id,
                        model_version_id=evaluation.model_version_id,
                        model_version=evaluation.model_version.version if evaluation.model_version else None,
                        overall_score=_dec_to_float(evaluation.overall_score),
                        confidence_state=evaluation.confidence_state,
                        confidence_score=_dec_to_float(evaluation.confidence_score),
                        coverage=_dec_to_float(evaluation.coverage),
                        limitations=evaluation.limitations,
                        parameters=param_list,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.debug("Retaining unavailable evaluation summary for variant %s: %s", variant.id, exc)

            # 3. Gather commercial offer dimension
            offer_summary = ComparisonOfferSummary()
            listings = (
                self.db.execute(
                    select(MarketplaceListing).where(MarketplaceListing.variant_id == variant.id)
                )
                .scalars()
                .all()
            )
            listing_ids = [l.id for l in listings]
            if listing_ids:
                latest_offer = (
                    self.db.execute(
                        select(SellerOffer)
                        .where(SellerOffer.listing_id.in_(listing_ids))
                        .order_by(SellerOffer.observed_at.desc())
                    )
                    .scalars()
                    .first()
                )
                if latest_offer and latest_offer.current_price is not None:
                    age_days = (now - latest_offer.observed_at.replace(tzinfo=UTC)).total_seconds() / 86400.0 if latest_offer.observed_at else 0
                    offer_summary = ComparisonOfferSummary(
                        current_price=_dec_to_float(latest_offer.current_price),
                        currency=latest_offer.currency or "INR",
                        seller=latest_offer.seller,
                        availability=latest_offer.availability,
                        observed_at=latest_offer.observed_at,
                        is_stale=age_days > 7.0,
                        is_available=latest_offer.availability in ("in_stock", "available", None),
                    )

            # 4. Gather community review summary dimension
            community_summary = ComparisonCommunitySummary()
            review_sum = (
                self.db.execute(
                    select(ReviewSummary)
                    .where(
                        (ReviewSummary.variant_id == variant.id)
                        | (ReviewSummary.product_id == product.id)
                    )
                    .order_by(
                        (ReviewSummary.variant_id == variant.id).desc(),
                        ReviewSummary.version.desc(),
                    )
                )
                .scalars()
                .first()
            )
            if review_sum:
                community_summary = ComparisonCommunitySummary(
                    total_reviews_analyzed=review_sum.total_reviews_analyzed,
                    sentiment_distribution=review_sum.sentiment_distribution or {},
                    key_pros=review_sum.key_pros or [],
                    key_cons=review_sum.key_cons or [],
                    summary_text=review_sum.summary_text,
                )

            matrix_items.append(
                ComparisonMatrixItem(
                    variant_id=variant.id,
                    product_id=product.id,
                    product_name=product.name,
                    manufacturer=product.manufacturer,
                    sku_label=variant.sku_label,
                    position=item.position,
                    specifications=specs,
                    evaluation=evaluation_summary,
                    offer=offer_summary,
                    community=community_summary,
                )
            )

        return ComparisonMatrixResponse(
            session_id=session.id,
            title=session.title,
            status=session.status,
            category_id=category.id if category else None,
            category_name=category.name if category else None,
            category_key=category.key if category else None,
            item_count=len(matrix_items),
            specification_keys=spec_keys_meta,
            items=matrix_items,
        )
