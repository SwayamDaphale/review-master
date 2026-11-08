"""Evaluation repository for models, versions, evaluations, and parameter scores."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.evaluation import (
    Evaluation,
    EvaluationModel,
    ParameterResult,
)


class EvaluationRepository:
    """Repository managing evaluation models, evaluations, and parameter scores."""

    @staticmethod
    def get_model_by_name(
        db: Session,
        category_id: uuid.UUID,
        name: str,
    ) -> EvaluationModel | None:
        """Lookup evaluation model by category and name."""
        stmt = (
            select(EvaluationModel)
            .where(
                EvaluationModel.category_id == category_id,
                EvaluationModel.name == name,
            )
            .options(selectinload(EvaluationModel.versions))
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_latest_evaluation(
        db: Session,
        variant_id: uuid.UUID,
    ) -> Evaluation | None:
        """Retrieve most recent evaluation for a product variant."""
        stmt = (
            select(Evaluation)
            .where(Evaluation.variant_id == variant_id)
            .order_by(Evaluation.created_at.desc())
            .options(
                selectinload(Evaluation.parameter_results),
                selectinload(Evaluation.model_version),
            )
        )
        return db.execute(stmt).scalars().first()

    @staticmethod
    def create_evaluation(
        db: Session,
        *,
        variant_id: uuid.UUID,
        model_version_id: uuid.UUID,
        confidence_state: str,
        confidence_score: float,
        overall_score: Decimal | float | None = None,
        limitations: list[str] | None = None,
    ) -> Evaluation:
        """Create an append-only evaluation record."""
        dec_score = Decimal(str(overall_score)) if overall_score is not None else None
        evaluation = Evaluation(
            variant_id=variant_id,
            model_version_id=model_version_id,
            overall_score=dec_score,
            confidence_state=confidence_state,
            confidence_score=confidence_score,
            limitations=limitations or [],
        )
        db.add(evaluation)
        db.flush()
        return evaluation

    @staticmethod
    def add_parameter_result(
        db: Session,
        *,
        evaluation_id: uuid.UUID,
        parameter_key: str,
        score: Decimal | float | None,
        weight: Decimal | float | None = None,
        status: str = "scored",
        is_critical: bool = False,
        explanation_data: dict[str, Any] | None = None,
        evidence_ids: list[str] | None = None,
    ) -> ParameterResult:
        """Add a parameter score to an evaluation."""
        result = ParameterResult(
            evaluation_id=evaluation_id,
            parameter_key=parameter_key,
            score=Decimal(str(score)) if score is not None else None,
            weight=Decimal(str(weight)) if weight is not None else None,
            status=status,
            is_critical=is_critical,
            explanation_data=explanation_data,
            evidence_ids=evidence_ids or [],
        )
        db.add(result)
        db.flush()
        return result
