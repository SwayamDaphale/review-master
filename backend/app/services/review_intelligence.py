"""Review intelligence service executing analysis pipelines and opinion aggregation."""

import logging
import uuid
from collections import Counter
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.review_intelligence import ReviewAnalysis, ReviewSummary
from app.repositories.review_repository import ReviewRepository
from app.services.llm.orchestrator import InferenceOrchestrator
from app.services.llm.prompts import (
    REVIEW_ANALYSIS_SYSTEM_PROMPT,
    REVIEW_SUMMARY_SYSTEM_PROMPT,
    ProductReviewSummaryOutput,
    ReviewAnalysisOutput,
)

logger = logging.getLogger("review_master.review_intelligence")


class ReviewIntelligenceService:
    """Service orchestrating AI review intelligence, sentiment, aspects, and aggregation."""

    def __init__(self, db: Session, orchestrator: InferenceOrchestrator | None = None):
        self.db = db
        self.orchestrator = orchestrator or InferenceOrchestrator()

    async def analyze_review(
        self,
        *,
        review_text: str,
        product_id: uuid.UUID | None = None,
        variant_id: uuid.UUID | None = None,
        source_evidence_id: uuid.UUID | None = None,
        review_source_id: str | None = None,
    ) -> ReviewAnalysis:
        """Process a single review text through LLM inference, validate output, and persist record."""
        # 1. Execute structured inference
        prompt = f'Analyze the following customer review:\n\n"""\n{review_text}\n"""'

        try:
            result = await self.orchestrator.generate_structured(
                prompt=prompt,
                schema=ReviewAnalysisOutput,
                system_prompt=REVIEW_ANALYSIS_SYSTEM_PROMPT,
            )
            analysis_data: ReviewAnalysisOutput = result.data
            status = "completed"
            error_message = None
        except Exception as e:  # noqa: BLE001 - Catch broad exception to record terminal failure state in database
            logger.error("Failed to analyze review text: %s", e)
            # Create a terminal failure record rather than losing the event
            return ReviewRepository.create_analysis(
                self.db,
                product_id=product_id,
                variant_id=variant_id,
                source_evidence_id=source_evidence_id,
                review_source_id=review_source_id,
                review_text=review_text,
                sentiment="neutral",
                sentiment_confidence=Decimal("0.0"),
                provider="failed",
                model="failed",
                status="failed",
                error_message=str(e),
            )

        # 2. Persist validated analysis and opinion relations
        aspect_dicts = [
            {
                "aspect_key": a.aspect_key,
                "polarity": a.polarity,
                "claim": a.claim,
                "raw_quote": a.raw_quote,
                "confidence": a.confidence,
            }
            for a in analysis_data.aspects
        ]

        pros_cons_payload: list[dict[str, Any]]
        if analysis_data.pros_cons:
            pros_cons_payload = [
                {
                    "item_type": pc.item_type,
                    "text": pc.text,
                    "aspect_key": pc.aspect_key,
                    "confidence": pc.confidence,
                    "source_reference": pc.source_reference,
                }
                for pc in analysis_data.pros_cons
            ]
        else:
            pros_cons_payload = [
                {"item_type": "pro", "text": p, "aspect_key": None}
                for p in analysis_data.pros
            ] + [
                {"item_type": "con", "text": c, "aspect_key": None}
                for c in analysis_data.cons
            ]

        analysis = ReviewRepository.create_analysis(
            self.db,
            product_id=product_id,
            variant_id=variant_id,
            source_evidence_id=source_evidence_id,
            review_source_id=review_source_id,
            review_text=review_text,
            sentiment=analysis_data.sentiment,
            sentiment_confidence=analysis_data.sentiment_confidence,
            provider=result.provider,
            model=result.model,
            status=status,
            error_message=error_message,
            aspects=aspect_dicts,
            pros_cons=pros_cons_payload,
            pros=analysis_data.pros,
            cons=analysis_data.cons,
        )
        return analysis

    async def summarize_product_reviews(
        self,
        *,
        product_id: uuid.UUID,
        variant_id: uuid.UUID | None = None,
    ) -> ReviewSummary | None:
        """Synthesize product-level summary across all analyzed reviews for a product."""
        analyses = ReviewRepository.list_analyses(
            self.db,
            product_id=product_id,
            variant_id=variant_id,
            limit=200,
        )

        completed = [a for a in analyses if a.status == "completed"]
        if not completed:
            logger.info(
                "No completed reviews found to summarize for product %s", product_id
            )
            return None

        # Compute empirical sentiment distribution
        sentiments = Counter(a.sentiment for a in completed)
        sentiment_dist = {
            "positive": sentiments.get("positive", 0),
            "negative": sentiments.get("negative", 0),
            "neutral": sentiments.get("neutral", 0),
            "mixed": sentiments.get("mixed", 0),
        }

        # Collect claims, aspects, and pros/cons
        all_pros: list[str] = []
        all_cons: list[str] = []
        aspect_claims: dict[str, list[str]] = {}

        for a in completed:
            for pro in a.pros_cons:
                if pro.item_type == "pro":
                    all_pros.append(pro.text)
                elif pro.item_type == "con":
                    all_cons.append(pro.text)
            for asp in a.aspect_opinions:
                aspect_claims.setdefault(asp.aspect_key, []).append(
                    f"[{asp.polarity}] {asp.claim}"
                )

        # Build synthesis prompt for LLM aggregation
        prompt_lines = [
            f"Synthesize verified feedback from {len(completed)} customer reviews for this product:",
            f"Sentiment breakdown: {sentiment_dist}",
            "\nExtracted Aspect Claims:",
        ]
        for key, claims in aspect_claims.items():
            prompt_lines.append(f"- {key}: {', '.join(claims[:6])}")

        if all_pros:
            prompt_lines.append(f"\nReported Pros: {', '.join(all_pros[:8])}")
        if all_cons:
            prompt_lines.append(f"Reported Cons: {', '.join(all_cons[:8])}")

        summary_prompt = "\n".join(prompt_lines)

        try:
            result = await self.orchestrator.generate_structured(
                prompt=summary_prompt,
                schema=ProductReviewSummaryOutput,
                system_prompt=REVIEW_SUMMARY_SYSTEM_PROMPT,
            )
            output: ProductReviewSummaryOutput = result.data

            summary = ReviewRepository.save_summary(
                self.db,
                product_id=product_id,
                variant_id=variant_id,
                summary_text=output.summary_text,
                total_reviews_analyzed=len(completed),
                sentiment_distribution=sentiment_dist,
                aspect_summaries=output.aspect_summaries,
                key_pros=output.key_pros or all_pros[:5],
                key_cons=output.key_cons or all_cons[:5],
                confidence=output.confidence,
                provider=result.provider,
                model=result.model,
            )
            return summary
        except Exception as e:  # noqa: BLE001 - Catch broad exception during summary generation to prevent API crash
            logger.error("Failed to generate aggregated review summary: %s", e)
            return None
