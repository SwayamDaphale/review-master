"""Recommendation domain service orchestrating parsing, eligibility, deterministic ranking, and persistence."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.attribute import VariantAttributeValue
from app.models.category import Category
from app.models.listing import MarketplaceListing
from app.models.operation import AuditLog
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.review_intelligence import ReviewSummary
from app.models.variant import Variant
from app.schemas.recommendation import (
    CandidateEvaluationOutcome,
    ConstraintOutcome,
    ExcludedProductItem,
    ParsedRequirements,
    RecommendationRequest,
    RecommendationResponse,
    RecommendedProductItem,
)
from app.services.constraint_engine import ConstraintEngine
from app.services.evaluation_cache import EvaluationReuseService
from app.services.ranking_service import RecommendationRankingService
from app.services.requirement_parser import RequirementParserService


def _dec_to_float(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, Decimal):
        return float(val)
    return None


class RecommendationService:
    """Service providing end-to-end requirement extraction, eligibility filtering, and deterministic recommendations."""

    def __init__(self, db: Session):
        self.db = db
        self.parser = RequirementParserService()
        self.reuse_service = EvaluationReuseService(db)

    def generate_recommendations(
        self,
        request: RecommendationRequest,
        user_id: uuid.UUID | None = None,
        anonymous_session_token: str | None = None,
    ) -> RecommendationResponse:
        """Execute requirement-based recommendation pipeline."""
        # 1. Resolve structured requirements
        requirements: ParsedRequirements
        if request.requirements:
            requirements = request.requirements
        elif request.query:
            parse_resp = self.parser.parse_query(
                request.query, category_hint=request.category_key
            )
            requirements = parse_resp.requirements
        else:
            raise ValueError("Either 'query' or 'requirements' must be provided.")

        # 2. Resolve target Category
        category: Category | None = None
        if request.category_id:
            category = self.db.get(Category, request.category_id)
        elif request.category_key:
            category = self.db.execute(
                select(Category).where(Category.key == request.category_key)
            ).scalar_one_or_none()
        elif requirements.category_key:
            category = self.db.execute(
                select(Category).where(Category.key == requirements.category_key)
            ).scalar_one_or_none()

        if not category:
            # Fallback lookup
            category = self.db.execute(
                select(Category).where(Category.key == "smartphone")
            ).scalar_one_or_none()
            if not category:
                raise ValueError("No matching category found for recommendation.")

        # 3. Retrieve all candidate variants in the category
        candidates_stmt = (
            select(Variant)
            .join(Product, Variant.product_id == Product.id)
            .where(Product.category_id == category.id)
            .options(
                selectinload(Variant.product),
                selectinload(Variant.attribute_values).joinedload(VariantAttributeValue.attribute_definition),
                selectinload(Variant.listings).selectinload(MarketplaceListing.offers),
            )
        )
        candidates = list(self.db.execute(candidates_stmt).scalars().all())

        # 4. Filter candidates via ConstraintEngine
        eligible_outcomes: list[CandidateEvaluationOutcome] = []
        excluded_candidates: list[ExcludedProductItem] = []
        variants_map: dict[uuid.UUID, Variant] = {}
        offers_map: dict[uuid.UUID, dict[str, Any]] = {}
        community_map: dict[uuid.UUID, str | None] = {}

        for variant in candidates:
            variants_map[variant.id] = variant

            # Gather attributes
            attr_values: dict[str, Any] = {}
            if variant.configuration:
                for k, v in variant.configuration.items():
                    if v is not None:
                        attr_values[k.lower()] = v

            for vav in variant.attribute_values:
                if vav.attribute_definition:
                    k = vav.attribute_definition.key.lower()
                    val = (
                        vav.value_numeric
                        if vav.value_numeric is not None
                        else (
                            vav.value_boolean
                            if vav.value_boolean is not None
                            else (vav.value_text if vav.value_text is not None else vav.raw_value)
                        )
                    )
                    if val is not None:
                        attr_values[k] = val

            # Gather latest commercial offer
            latest_offer = None
            for listing in variant.listings:
                for off in listing.offers:
                    if off.current_price is not None and (latest_offer is None or off.observed_at > latest_offer.observed_at):
                        latest_offer = off

            offer_info: dict[str, Any] = {}
            if latest_offer and latest_offer.current_price is not None:
                offer_info = {
                    "price": _dec_to_float(latest_offer.current_price),
                    "currency": latest_offer.currency or "INR",
                    "seller": latest_offer.seller,
                    "availability": latest_offer.availability,
                    "is_available": latest_offer.availability in ("in_stock", "available", None),
                }
            offers_map[variant.id] = offer_info

            # Gather community summary text
            comm_sum = self.db.execute(
                select(ReviewSummary).where(
                    (ReviewSummary.variant_id == variant.id)
                    | (ReviewSummary.product_id == variant.product_id)
                )
            ).scalars().first()
            community_map[variant.id] = comm_sum.summary_text if comm_sum else None

            # Evaluate three-valued constraints
            candidate_outcome = ConstraintEngine.evaluate_candidate(
                requirements=requirements,
                variant_id=variant.id,
                product_id=variant.product_id,
                product_name=variant.product.name,
                manufacturer=variant.product.manufacturer,
                sku_label=variant.sku_label,
                attribute_values=attr_values,
                current_price=offer_info.get("price"),
                price_available=bool(offer_info.get("price") is not None),
            )

            if candidate_outcome.is_eligible:
                eligible_outcomes.append(candidate_outcome)
            else:
                failed = [c.attribute_key for c in candidate_outcome.constraints if c.outcome == ConstraintOutcome.FAIL]
                unknown = [c.attribute_key for c in candidate_outcome.constraints if c.outcome == ConstraintOutcome.UNKNOWN]
                excluded_candidates.append(
                    ExcludedProductItem(
                        variant_id=variant.id,
                        product_id=variant.product_id,
                        product_name=variant.product.name,
                        sku_label=variant.sku_label,
                        failed_constraints=failed,
                        unknown_constraints=unknown,
                        reasons=candidate_outcome.exclusion_reasons,
                    )
                )

        # 5. Fetch/reuse B9 Evaluations for eligible candidates
        evaluations_map = {}
        for outcome in eligible_outcomes:
            var_id = outcome.variant_id
            eval_record = self.reuse_service.get_or_evaluate_variant(
                var_id, force_recalculate=request.force_recalculate_evaluations
            )
            evaluations_map[var_id] = eval_record

        # 6. Rank eligible candidates deterministically
        ranked_items = RecommendationRankingService.rank_and_explain(
            requirements=requirements,
            eligible_outcomes=eligible_outcomes,
            evaluations_map=evaluations_map,
            variants_map=variants_map,
            offers_map=offers_map,
            community_map=community_map,
            limit=request.limit,
        )

        # 7. Compute deterministic fingerprints
        input_fp, output_fp = RecommendationRankingService.compute_fingerprints(
            requirements=requirements,
            ranked_items=ranked_items,
            excluded_count=len(excluded_candidates),
        )

        # 8. Resolve active model version identity for response
        first_eval = evaluations_map.get(ranked_items[0].variant_id) if ranked_items else None
        active_model_ver_id = first_eval.model_version_id if first_eval else None
        active_model_ver_str = first_eval.model_version.version if first_eval and first_eval.model_version else None

        # 9. Persist Recommendation record (Module 9)
        rec_id = uuid.uuid4()
        now_dt = datetime.now(UTC)

        recommendation_record = Recommendation(
            id=rec_id,
            user_id=user_id,
            anonymous_session_token=anonymous_session_token,
            category_id=category.id,
            raw_query=request.query,
            parsed_requirements=requirements.model_dump(),
            parser_version=requirements.parser_version,
            ranking_policy_version=RecommendationRankingService.RANKING_POLICY_VERSION,
            model_version_id=active_model_ver_id,
            eligible_count=len(eligible_outcomes),
            ineligible_count=len(excluded_candidates),
            hard_constraint_results={
                "eligible": [o.model_dump(mode="json") for o in eligible_outcomes],
                "excluded": [e.model_dump(mode="json") for e in excluded_candidates],
            },
            ranked_results=[r.model_dump(mode="json") for r in ranked_items],
            rejected_results=[e.model_dump(mode="json") for e in excluded_candidates],
            input_fingerprint=input_fp,
            output_fingerprint=output_fp,
            created_at=now_dt,
        )
        self.db.add(recommendation_record)

        # Audit log entry
        audit_log = AuditLog(
            actor_type="user" if user_id else "anonymous",
            actor_id=str(user_id) if user_id else anonymous_session_token,
            action="recommendation:generate",
            target_type="recommendation",
            target_id=str(rec_id),
            status="success",
            metadata_payload={
                "category": category.key,
                "eligible_count": len(eligible_outcomes),
                "ineligible_count": len(excluded_candidates),
                "ranked_count": len(ranked_items),
                "input_fingerprint": input_fp,
                "output_fingerprint": output_fp,
            },
            created_at=now_dt,
        )
        self.db.add(audit_log)
        self.db.commit()

        return RecommendationResponse(
            recommendation_id=rec_id,
            category_id=category.id,
            category_key=category.key,
            query=request.query,
            parsed_requirements=requirements,
            eligible_count=len(eligible_outcomes),
            ineligible_count=len(excluded_candidates),
            ranked_recommendations=ranked_items,
            excluded_candidates=excluded_candidates,
            ranking_policy_version=RecommendationRankingService.RANKING_POLICY_VERSION,
            model_version_id=active_model_ver_id,
            model_version=active_model_ver_str,
            input_fingerprint=input_fp,
            output_fingerprint=output_fp,
            created_at=now_dt,
        )

    def get_recommendation(self, recommendation_id: uuid.UUID) -> RecommendationResponse | None:
        """Fetch historical recommendation result by ID."""
        rec = self.db.get(Recommendation, recommendation_id)
        if not rec:
            return None

        parsed_req = ParsedRequirements.model_validate(rec.parsed_requirements)
        ranked_items = [RecommendedProductItem.model_validate(r) for r in rec.ranked_results]
        excluded_items = [ExcludedProductItem.model_validate(e) for e in rec.rejected_results]

        return RecommendationResponse(
            recommendation_id=rec.id,
            category_id=rec.category_id,
            category_key=rec.category.key if rec.category else "unknown",
            query=rec.raw_query,
            parsed_requirements=parsed_req,
            eligible_count=rec.eligible_count,
            ineligible_count=rec.ineligible_count,
            ranked_recommendations=ranked_items,
            excluded_candidates=excluded_items,
            ranking_policy_version=rec.ranking_policy_version,
            model_version_id=rec.model_version_id,
            model_version=rec.model_version.version if rec.model_version else None,
            input_fingerprint=rec.input_fingerprint or "",
            output_fingerprint=rec.output_fingerprint or "",
            created_at=rec.created_at,
        )
