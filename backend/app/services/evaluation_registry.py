"""Evaluation model registry service managing lifecycle: draft -> validated -> published -> deprecated."""

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.models.category import Category
from app.models.evaluation import EvaluationModel, EvaluationModelVersion
from app.schemas.evaluation_config import (
    EvaluationModelConfig,
    compute_configuration_hash,
)

logger = logging.getLogger("review_master.evaluation_registry")


class EvaluationRegistryService:
    """Service governing evaluation model versioning, validation, immutability, and publication."""

    def __init__(self, db: Session):
        self.db = db

    def create_model(
        self,
        category_id: uuid.UUID,
        name: str,
        description: str | None = None,
        created_by: uuid.UUID | None = None,
    ) -> EvaluationModel:
        """Create a new category evaluation model in draft status."""
        cat = self.db.get(Category, category_id)
        if not cat:
            raise ValueError(f"Category '{category_id}' not found.")

        model = EvaluationModel(
            category_id=category_id,
            name=name.strip(),
            description=description.strip() if description else None,
            status="draft",
            created_by=created_by,
        )
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model

    def add_version(
        self,
        model_id: uuid.UUID,
        version: str,
        definition: dict[str, Any],
        user_id: uuid.UUID | None = None,
    ) -> EvaluationModelVersion:
        """Add a new version configuration to an evaluation model."""
        model = self.db.get(EvaluationModel, model_id)
        if not model:
            raise ValueError(f"Evaluation model '{model_id}' not found.")

        # Check for duplicate version on this model
        existing = self.db.execute(
            select(EvaluationModelVersion).where(
                EvaluationModelVersion.model_id == model_id,
                EvaluationModelVersion.version == version.strip(),
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError(f"Version '{version}' already exists for model '{model_id}'.")

        cfg_hash = compute_configuration_hash(definition)
        mv = EvaluationModelVersion(
            model_id=model_id,
            version=version.strip(),
            status="draft",
            definition=definition,
            configuration_hash=cfg_hash,
            approved_by=None,
            published_at=None,
        )
        self.db.add(mv)
        self.db.commit()
        self.db.refresh(mv)
        return mv

    def validate_version(self, version_id: uuid.UUID) -> EvaluationModelConfig:
        """Validate model version definition against strict Pydantic contract."""
        mv = self.db.get(EvaluationModelVersion, version_id)
        if not mv:
            raise ValueError(f"Evaluation model version '{version_id}' not found.")

        # Parse definition strictly
        validated_config = EvaluationModelConfig.model_validate(mv.definition)

        # Update status to validated if draft
        if mv.status == "draft":
            mv.status = "validated"
            mv.configuration_hash = compute_configuration_hash(validated_config)
            self.db.commit()
            self.db.refresh(mv)

        return validated_config

    def publish_version(
        self,
        version_id: uuid.UUID,
        published_by: uuid.UUID | None = None,
    ) -> EvaluationModelVersion:
        """Publish a validated model version, freezing it as immutable and activating it for the category."""
        mv = self.db.get(EvaluationModelVersion, version_id)
        if not mv:
            raise ValueError(f"Evaluation model version '{version_id}' not found.")

        if mv.status == "published":
            raise ValueError(f"Evaluation model version '{version_id}' is already in published status and is immutable.")

        if mv.status == "deprecated":
            raise ValueError("Deprecated model version cannot be republished. Create a new version.")

        # Validate definition before publishing
        validated_config = EvaluationModelConfig.model_validate(mv.definition)

        mv.status = "published"
        mv.published_at = utc_now()
        mv.approved_by = str(published_by) if published_by else "system_admin"
        mv.configuration_hash = compute_configuration_hash(validated_config)

        # Update parent model status and pointer
        model = mv.model
        model.status = "published"
        model.active_version_id = mv.id

        self.db.commit()
        self.db.refresh(mv)
        logger.info("Published evaluation model version %s for category %s", mv.version, model.category_id)
        return mv

    def deprecate_version(
        self,
        version_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> EvaluationModelVersion:
        """Deprecate a published model version without deleting historical evaluation records."""
        mv = self.db.get(EvaluationModelVersion, version_id)
        if not mv:
            raise ValueError(f"Evaluation model version '{version_id}' not found.")

        mv.status = "deprecated"
        model = mv.model
        if model.active_version_id == mv.id:
            model.active_version_id = None
            # Check if any other published version exists
            other_published = self.db.execute(
                select(EvaluationModelVersion).where(
                    EvaluationModelVersion.model_id == model.id,
                    EvaluationModelVersion.status == "published",
                    EvaluationModelVersion.id != mv.id,
                ).order_by(EvaluationModelVersion.published_at.desc())
            ).scalars().first()
            if other_published:
                model.active_version_id = other_published.id
            else:
                model.status = "deprecated"

        self.db.commit()
        self.db.refresh(mv)
        logger.info("Deprecated evaluation model version %s", mv.version)
        return mv

    def get_active_model_version(self, category_id: uuid.UUID) -> tuple[EvaluationModel, EvaluationModelVersion] | None:
        """Retrieve currently active published model version for category."""
        model = self.db.execute(
            select(EvaluationModel)
            .where(
                EvaluationModel.category_id == category_id,
                EvaluationModel.status == "published",
            )
            .order_by(EvaluationModel.created_at.desc())
        ).scalars().first()
        if not model or not model.active_version_id:
            return None

        active_ver = self.db.get(EvaluationModelVersion, model.active_version_id)
        if not active_ver or active_ver.status != "published":
            return None

        return model, active_ver
