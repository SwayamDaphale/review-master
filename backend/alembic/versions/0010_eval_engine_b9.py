"""0010: Evaluation engine extensions for deterministic versioned scoring.

Revision ID: 0010_eval_engine_b9
Revises: 0009_identity_and_evidence_quality
Create Date: 2026-11-11 12:45:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "0010_eval_engine_b9"
down_revision = "0009_identity_and_evidence_quality"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Extend 'evaluation_models'
    op.add_column("evaluation_models", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "evaluation_models",
        sa.Column("status", sa.String(32), server_default="draft", nullable=False),
    )
    op.add_column(
        "evaluation_models",
        sa.Column(
            "active_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluation_model_versions.id", ondelete="SET NULL", name="fk_eval_models_active_ver"),
            nullable=True,
        ),
    )
    op.add_column(
        "evaluation_models",
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_eval_models_user"),
            nullable=True,
        ),
    )

    # 2. Extend 'evaluation_model_versions'
    op.add_column(
        "evaluation_model_versions",
        sa.Column("configuration_hash", sa.String(64), nullable=True),
    )

    # 3. Extend 'evaluations'
    op.add_column(
        "evaluations",
        sa.Column("configuration_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "evaluations",
        sa.Column("input_fingerprint", sa.String(64), nullable=True),
    )
    op.add_column(
        "evaluations",
        sa.Column("output_fingerprint", sa.String(64), nullable=True),
    )
    op.add_column(
        "evaluations",
        sa.Column("calculation_policy_version", sa.String(32), server_default="v1", nullable=True),
    )

    # 4. Extend 'parameter_results'
    op.add_column(
        "parameter_results",
        sa.Column("effective_weight", sa.Numeric(6, 5), nullable=True),
    )
    op.add_column(
        "parameter_results",
        sa.Column(
            "evidence_version_ids",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )
    op.add_column(
        "parameter_results",
        sa.Column(
            "raw_input_value",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
    )
    op.add_column(
        "parameter_results",
        sa.Column(
            "normalized_value",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
    )
    op.add_column(
        "parameter_results",
        sa.Column("scoring_rule", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    # 4. Parameter results
    op.drop_column("parameter_results", "scoring_rule")
    op.drop_column("parameter_results", "normalized_value")
    op.drop_column("parameter_results", "raw_input_value")
    op.drop_column("parameter_results", "evidence_version_ids")
    op.drop_column("parameter_results", "effective_weight")

    # 3. Evaluations
    op.drop_column("evaluations", "calculation_policy_version")
    op.drop_column("evaluations", "output_fingerprint")
    op.drop_column("evaluations", "input_fingerprint")
    op.drop_column("evaluations", "configuration_hash")

    # 2. Evaluation model versions
    op.drop_column("evaluation_model_versions", "configuration_hash")

    # 1. Evaluation models
    op.drop_constraint("fk_eval_models_user", "evaluation_models", type_="foreignkey")
    op.drop_constraint("fk_eval_models_active_ver", "evaluation_models", type_="foreignkey")
    op.drop_column("evaluation_models", "created_by")
    op.drop_column("evaluation_models", "active_version_id")
    op.drop_column("evaluation_models", "status")
    op.drop_column("evaluation_models", "description")

