"""Evaluation reuse and caching service conforming to Phase B9/B10 contracts.

Ensures:
- Valid existing B9 evaluations are reused based on exact match:
  (variant_id, model_version_id, configuration_hash, evidence_snapshot_hash).
- PostgreSQL remains authoritative.
- Redis acts as a fast transparent cache; Redis outage falls back seamlessly to PostgreSQL.
- Stale or mismatched cache entries are bypassed/invalidated.
- Explicit recalculation delegates to EvaluationFoundationService which appends new records.
"""

import logging
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.rate_limit import get_redis_client
from app.models.evaluation import Evaluation, EvaluationModelVersion
from app.models.evidence import Evidence
from app.models.variant import Variant
from app.services.evaluation_service import EvaluationFoundationService

logger = logging.getLogger("review_master.evaluation_cache")


def _decimal_to_float(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_float(i) for i in obj]
    return obj


class EvaluationReuseService:
    """Service managing evaluation lookup, reuse verification, and Redis caching."""

    CACHE_TTL_SECONDS = 86400  # 24 hours

    def __init__(self, db: Session):
        self.db = db
        self.eval_service = EvaluationFoundationService(db)
        self.redis = get_redis_client()

    @staticmethod
    def build_cache_key(
        variant_id: uuid.UUID,
        model_version_id: uuid.UUID,
        config_hash: str | None,
        evidence_hash: str | None,
    ) -> str:
        """Construct deterministic Redis cache key incorporating all four reuse dimensions."""
        cfg = config_hash or "none"
        ev = evidence_hash or "none"
        return f"eval_cache:{variant_id}:{model_version_id}:{cfg}:{ev}"

    def get_or_evaluate_variant(
        self,
        variant_id: uuid.UUID,
        force_recalculate: bool = False,
        model_version_id: uuid.UUID | None = None,
    ) -> Evaluation:
        """Retrieve valid existing evaluation or compute a new one if stale, missing, or forced."""
        variant = self.db.get(Variant, variant_id)
        if not variant:
            raise ValueError(f"Variant '{variant_id}' not found.")

        # 1. Resolve active or requested model version
        resolved_model_version: EvaluationModelVersion | None = None
        if model_version_id:
            resolved_model_version = self.db.get(EvaluationModelVersion, model_version_id)
        else:
            active_pair = self.eval_service.registry.get_active_model_version(
                variant.product.category_id
            )
            if active_pair:
                _, resolved_model_version = active_pair

        if not resolved_model_version:
            # Fallback to evaluating/recording uncalibrated evaluation
            return self.eval_service.evaluate_variant(variant_id, force_model_version_id=model_version_id)

        # 2. Compute current evidence snapshot hash
        evidence_records = (
            self.db.execute(
                select(Evidence).where(
                    (Evidence.variant_id == variant.id) | (Evidence.product_id == variant.product_id)
                )
            )
            .scalars()
            .all()
        )
        evidence_map = {e.parameter_key: e for e in evidence_records}
        current_evidence_hash = self.eval_service._compute_evidence_snapshot_hash(evidence_map)
        current_config_hash = resolved_model_version.configuration_hash

        # 3. Check for valid reuse if recalculation is NOT forced
        if not force_recalculate:
            # First check Redis cache
            cached_eval_id = self._get_from_redis(
                variant_id, resolved_model_version.id, current_config_hash, current_evidence_hash
            )
            if cached_eval_id:
                eval_from_db = self._get_full_evaluation(cached_eval_id)
                if eval_from_db and self._is_evaluation_valid(
                    eval_from_db, resolved_model_version.id, current_config_hash, current_evidence_hash
                ):
                    return eval_from_db

            # Authoritative lookup in PostgreSQL
            existing_eval = self._find_matching_evaluation(
                variant_id=variant.id,
                model_version_id=resolved_model_version.id,
                config_hash=current_config_hash,
                evidence_hash=current_evidence_hash,
            )
            if existing_eval:
                # Populate Redis cache for future queries
                self._save_to_redis(
                    variant_id,
                    resolved_model_version.id,
                    current_config_hash,
                    current_evidence_hash,
                    existing_eval.id,
                )
                return existing_eval

        # 4. If no valid evaluation exists or recalculation forced, perform evaluation
        new_evaluation = self.eval_service.evaluate_variant(
            variant_id, force_model_version_id=resolved_model_version.id
        )

        # Cache new evaluation ID
        self._save_to_redis(
            variant_id,
            resolved_model_version.id,
            current_config_hash,
            current_evidence_hash,
            new_evaluation.id,
        )
        return new_evaluation

    def _find_matching_evaluation(
        self,
        *,
        variant_id: uuid.UUID,
        model_version_id: uuid.UUID,
        config_hash: str | None,
        evidence_hash: str | None,
    ) -> Evaluation | None:
        """Find authoritative matching evaluation in PostgreSQL."""
        stmt = (
            select(Evaluation)
            .where(
                Evaluation.variant_id == variant_id,
                Evaluation.model_version_id == model_version_id,
            )
            .options(
                selectinload(Evaluation.parameter_results),
                selectinload(Evaluation.model_version),
            )
            .order_by(Evaluation.created_at.desc())
        )
        if config_hash:
            stmt = stmt.where(Evaluation.configuration_hash == config_hash)
        if evidence_hash:
            stmt = stmt.where(Evaluation.evidence_snapshot_hash == evidence_hash)

        return self.db.execute(stmt).scalars().first()

    def _get_full_evaluation(self, evaluation_id: uuid.UUID) -> Evaluation | None:
        """Fetch full evaluation with parameter results."""
        stmt = (
            select(Evaluation)
            .where(Evaluation.id == evaluation_id)
            .options(
                selectinload(Evaluation.parameter_results),
                selectinload(Evaluation.model_version),
            )
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def _is_evaluation_valid(
        self,
        evaluation: Evaluation,
        model_version_id: uuid.UUID,
        config_hash: str | None,
        evidence_hash: str | None,
    ) -> bool:
        """Verify that evaluation matches current required version and hashes."""
        if evaluation.model_version_id != model_version_id:
            return False
        if config_hash and evaluation.configuration_hash != config_hash:
            return False
        return not (evidence_hash and evaluation.evidence_snapshot_hash != evidence_hash)

    def _get_from_redis(
        self,
        variant_id: uuid.UUID,
        model_version_id: uuid.UUID,
        config_hash: str | None,
        evidence_hash: str | None,
    ) -> uuid.UUID | None:
        """Safe Redis read falling back to None on error."""
        if not self.redis:
            return None
        try:
            key = self.build_cache_key(
                variant_id, model_version_id, config_hash, evidence_hash
            )
            val = self.redis.get(key)
            if val:
                return uuid.UUID(val.decode("utf-8") if isinstance(val, bytes) else str(val))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis cache read failure (falling back to DB): %s", exc)
        return None

    def _save_to_redis(
        self,
        variant_id: uuid.UUID,
        model_version_id: uuid.UUID,
        config_hash: str | None,
        evidence_hash: str | None,
        evaluation_id: uuid.UUID,
    ) -> None:
        """Safe Redis write ignoring errors."""
        if not self.redis:
            return
        try:
            key = self.build_cache_key(
                variant_id, model_version_id, config_hash, evidence_hash
            )
            self.redis.set(key, str(evaluation_id), ex=self.CACHE_TTL_SECONDS)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis cache write failure (non-critical): %s", exc)
