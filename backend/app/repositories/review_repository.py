"""Review intelligence repository for analysis records, aspects, and summaries."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.review_intelligence import (
    ReviewAnalysis,
    ReviewAspectOpinion,
    ReviewProCon,
    ReviewSummary,
)


class ReviewRepository:
    """Repository handling review analysis and aggregated summary persistence."""

    @staticmethod
    def create_analysis(
        db: Session,
        *,
        product_id: uuid.UUID | None,
        variant_id: uuid.UUID | None = None,
        source_evidence_id: uuid.UUID | None = None,
        review_source_id: str | None = None,
        review_text: str,
        sentiment: str,
        sentiment_confidence: Decimal | float = 1.0,
        provider: str,
        model: str,
        prompt_version: str = "1.0",
        status: str = "completed",
        error_message: str | None = None,
        aspects: list[dict[str, Any]] | None = None,
        pros: list[str] | None = None,
        cons: list[str] | None = None,
        pros_cons: list[dict[str, Any]] | None = None,
    ) -> ReviewAnalysis:
        """Create and persist a complete review analysis record with aspects and pros/cons."""
        analysis = ReviewAnalysis(
            product_id=product_id,
            variant_id=variant_id,
            source_evidence_id=source_evidence_id,
            review_source_id=review_source_id,
            review_text=review_text,
            sentiment=sentiment,
            sentiment_confidence=Decimal(str(sentiment_confidence)),
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            status=status,
            error_message=error_message,
        )
        db.add(analysis)
        db.flush()

        # Add aspect opinions
        if aspects:
            for asp in aspects:
                opinion = ReviewAspectOpinion(
                    analysis_id=analysis.id,
                    aspect_key=asp["aspect_key"],
                    polarity=asp["polarity"],
                    claim=asp["claim"],
                    raw_quote=asp.get("raw_quote"),
                    confidence=Decimal(str(asp.get("confidence", 1.0))),
                    source_evidence_id=source_evidence_id,
                )
                db.add(opinion)

        # Add structured pros/cons with aspect provenance if provided
        if pros_cons:
            for item in pros_cons:
                db.add(
                    ReviewProCon(
                        analysis_id=analysis.id,
                        item_type=item["item_type"],
                        text=item["text"],
                        aspect_key=item.get("aspect_key"),
                        source_evidence_id=source_evidence_id,
                    )
                )
        else:
            # Fallback to string lists for pros and cons
            if pros:
                for pro_text in pros:
                    db.add(
                        ReviewProCon(
                            analysis_id=analysis.id,
                            item_type="pro",
                            text=pro_text,
                            aspect_key=None,
                            source_evidence_id=source_evidence_id,
                        )
                    )

            if cons:
                for con_text in cons:
                    db.add(
                        ReviewProCon(
                            analysis_id=analysis.id,
                            item_type="con",
                            text=con_text,
                            aspect_key=None,
                            source_evidence_id=source_evidence_id,
                        )
                    )

        db.flush()
        return analysis

    @staticmethod
    def get_analysis_by_id(
        db: Session, analysis_id: uuid.UUID
    ) -> ReviewAnalysis | None:
        """Retrieve analysis by ID with aspects and pros/cons loaded."""
        stmt = (
            select(ReviewAnalysis)
            .where(ReviewAnalysis.id == analysis_id)
            .options(
                selectinload(ReviewAnalysis.aspect_opinions),
                selectinload(ReviewAnalysis.pros_cons),
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_analyses(
        db: Session,
        *,
        product_id: uuid.UUID | None = None,
        variant_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReviewAnalysis]:
        """List review analyses with optional product/variant filtering."""
        stmt = select(ReviewAnalysis)
        if variant_id:
            stmt = stmt.where(ReviewAnalysis.variant_id == variant_id)
        elif product_id:
            stmt = stmt.where(ReviewAnalysis.product_id == product_id)
        stmt = (
            stmt.order_by(ReviewAnalysis.created_at.desc()).limit(limit).offset(offset)
        )
        stmt = stmt.options(
            selectinload(ReviewAnalysis.aspect_opinions),
            selectinload(ReviewAnalysis.pros_cons),
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def save_summary(
        db: Session,
        *,
        product_id: uuid.UUID,
        variant_id: uuid.UUID | None = None,
        summary_text: str,
        total_reviews_analyzed: int,
        sentiment_distribution: dict[str, Any],
        aspect_summaries: dict[str, Any],
        key_pros: list[str],
        key_cons: list[str],
        confidence: Decimal | float = 1.0,
        provider: str,
        model: str,
    ) -> ReviewSummary:
        """Persist an aggregated review summary."""
        # Find existing version to increment
        stmt = select(ReviewSummary).where(ReviewSummary.product_id == product_id)
        if variant_id:
            stmt = stmt.where(ReviewSummary.variant_id == variant_id)
        stmt = stmt.order_by(ReviewSummary.version.desc())
        latest = db.execute(stmt).scalars().first()
        next_version = (latest.version + 1) if latest else 1

        summary = ReviewSummary(
            product_id=product_id,
            variant_id=variant_id,
            summary_text=summary_text,
            total_reviews_analyzed=total_reviews_analyzed,
            sentiment_distribution=sentiment_distribution,
            aspect_summaries=aspect_summaries,
            key_pros=key_pros,
            key_cons=key_cons,
            confidence=Decimal(str(confidence)),
            provider=provider,
            model=model,
            version=next_version,
        )
        db.add(summary)
        db.flush()
        return summary

    @staticmethod
    def get_latest_summary(
        db: Session,
        product_id: uuid.UUID,
        variant_id: uuid.UUID | None = None,
    ) -> ReviewSummary | None:
        """Retrieve the latest review summary for a product or variant."""
        stmt = select(ReviewSummary).where(ReviewSummary.product_id == product_id)
        if variant_id:
            stmt = stmt.where(ReviewSummary.variant_id == variant_id)
        stmt = stmt.order_by(ReviewSummary.version.desc())
        return db.execute(stmt).scalars().first()
