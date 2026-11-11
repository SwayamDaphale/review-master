"""0009: Identity resolution mappings, review queue, evidence conflicts, and verification history.

Revision ID: 0009_identity_and_evidence_quality
Revises: 0008_durable_jobs
Create Date: 2026-11-11 11:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "0009_identity_and_evidence_quality"
down_revision = "0008_durable_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0. Widen alembic_version.version_num if needed to allow revision names > 32 chars
    op.alter_column(
        "alembic_version",
        "version_num",
        type_=sa.String(64),
        existing_type=sa.String(32),
    )

    # 1. Create 'external_identity_mappings' table
    op.create_table(
        "external_identity_mappings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "marketplace_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "marketplaces.id",
                ondelete="CASCADE",
                name="fk_ext_ident_mkt_id",
            ),
            nullable=False,
        ),
        sa.Column("external_id_type", sa.String(32), server_default="asin", nullable=False),
        sa.Column("external_id_value", sa.String(64), nullable=False),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "products.id",
                ondelete="SET NULL",
                name="fk_ext_ident_prod_id",
            ),
            nullable=True,
        ),
        sa.Column(
            "variant_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "variants.id",
                ondelete="SET NULL",
                name="fk_ext_ident_var_id",
            ),
            nullable=True,
        ),
        sa.Column("mapping_status", sa.String(32), server_default="active", nullable=False),
        sa.Column("verification_status", sa.String(32), server_default="unverified", nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("provenance", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "marketplace_id",
            "external_id_type",
            "external_id_value",
            name="uq_ext_identity_mkt_type_val",
        ),
    )
    op.create_index(
        "ix_ext_identity_mkt_type_val",
        "external_identity_mappings",
        ["marketplace_id", "external_id_type", "external_id_value"],
    )
    op.create_index(
        "ix_ext_identity_product_id",
        "external_identity_mappings",
        ["product_id"],
    )
    op.create_index(
        "ix_ext_identity_variant_id",
        "external_identity_mappings",
        ["variant_id"],
    )

    # 2. Create 'identity_review_queue' table
    op.create_table(
        "identity_review_queue",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("record_id", sa.String(64), nullable=True),
        sa.Column(
            "marketplace_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "marketplaces.id",
                ondelete="SET NULL",
                name="fk_id_rev_mkt_id",
            ),
            nullable=True,
        ),
        sa.Column("asin", sa.String(64), nullable=True),
        sa.Column("raw_title", sa.String(512), nullable=True),
        sa.Column("candidate_product_ids", JSONB, nullable=True),
        sa.Column("candidate_variant_ids", JSONB, nullable=True),
        sa.Column("candidate_scores", JSONB, nullable=True),
        sa.Column("conflicting_attributes", JSONB, nullable=True),
        sa.Column("matching_reasons", JSONB, nullable=True),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column(
            "assigned_reviewer_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="SET NULL",
                name="fk_id_rev_reviewer_id",
            ),
            nullable=True,
        ),
        sa.Column("reviewer_decision", sa.String(32), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_identity_review_queue_status", "identity_review_queue", ["status"])
    op.create_index("ix_identity_review_queue_asin", "identity_review_queue", ["asin"])
    op.create_index("ix_identity_review_queue_record_id", "identity_review_queue", ["record_id"])

    # 3. Create 'evidence_conflicts' table
    op.create_table(
        "evidence_conflicts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("parameter_key", sa.String(64), nullable=False),
        sa.Column("existing_value", JSONB, nullable=False),
        sa.Column("conflicting_value", JSONB, nullable=False),
        sa.Column("existing_unit", sa.String(32), nullable=True),
        sa.Column("conflicting_unit", sa.String(32), nullable=True),
        sa.Column(
            "existing_evidence_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "evidence.id",
                ondelete="SET NULL",
                name="fk_ev_conf_exist_ev_id",
            ),
            nullable=True,
        ),
        sa.Column(
            "incoming_evidence_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "evidence.id",
                ondelete="SET NULL",
                name="fk_ev_conf_incom_ev_id",
            ),
            nullable=True,
        ),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "products.id",
                ondelete="CASCADE",
                name="fk_ev_conf_prod_id",
            ),
            nullable=True,
        ),
        sa.Column(
            "variant_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "variants.id",
                ondelete="CASCADE",
                name="fk_ev_conf_var_id",
            ),
            nullable=True,
        ),
        sa.Column("status", sa.String(32), server_default="open", nullable=False),
        sa.Column(
            "resolved_by",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="SET NULL",
                name="fk_ev_conf_user_id",
            ),
            nullable=True,
        ),
        sa.Column("resolution_decision", sa.String(64), nullable=True),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_evidence_conflicts_param_status",
        "evidence_conflicts",
        ["parameter_key", "status"],
    )
    op.create_index(
        "ix_evidence_conflicts_prod_var",
        "evidence_conflicts",
        ["product_id", "variant_id"],
    )

    # 4. Create 'evidence_verification_history' table
    op.create_table(
        "evidence_verification_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "evidence_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "evidence.id",
                ondelete="CASCADE",
                name="fk_ev_ver_hist_ev_id",
            ),
            nullable=False,
        ),
        sa.Column("previous_status", sa.String(32), nullable=False),
        sa.Column("new_status", sa.String(32), nullable=False),
        sa.Column(
            "actor_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="SET NULL",
                name="fk_ev_ver_hist_actor_id",
            ),
            nullable=True,
        ),
        sa.Column("actor_role", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "supporting_evidence_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "evidence.id",
                ondelete="SET NULL",
                name="fk_ev_ver_hist_supp_id",
            ),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_ev_ver_hist_ev_created",
        "evidence_verification_history",
        ["evidence_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("evidence_verification_history")
    op.drop_table("evidence_conflicts")
    op.drop_table("identity_review_queue")
    op.drop_table("external_identity_mappings")
