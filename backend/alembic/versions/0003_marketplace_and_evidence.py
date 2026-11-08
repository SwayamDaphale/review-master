"""create marketplace, evidence, extraction and evaluation tables

Revision ID: 0003_marketplace_and_evidence
Revises: 0002_catalog_tables
Create Date: 2026-11-08 01:25:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_marketplace_and_evidence"
down_revision: str | None = "0002_catalog_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Marketplaces table
    op.create_table(
        "marketplaces",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("adapter", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column(
            "permitted_sources",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
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
    op.create_index("ix_marketplaces_key", "marketplaces", ["key"], unique=True)

    # 2. Listings table
    op.create_table(
        "listings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "marketplace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("marketplaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "variant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("variants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "match_state", sa.String(32), server_default="unmatched", nullable=False
        ),
        sa.Column("match_confidence", sa.Float(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "raw_metadata",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
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
            "marketplace_id", "external_id", name="uq_listings_mkt_external_id"
        ),
    )
    op.create_index("ix_listings_marketplace_id", "listings", ["marketplace_id"])
    op.create_index("ix_listings_external_id", "listings", ["external_id"])
    op.create_index("ix_listings_product_id", "listings", ["product_id"])
    op.create_index("ix_listings_variant_id", "listings", ["variant_id"])
    op.create_index("ix_listings_match_state", "listings", ["match_state"])
    op.create_index(
        "ix_listings_mkt_ext", "listings", ["marketplace_id", "external_id"]
    )

    # 3. Offers table
    op.create_table(
        "offers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "listing_id",
            UUID(as_uuid=True),
            sa.ForeignKey("listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seller", sa.String(255), nullable=True),
        sa.Column("current_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=True),
        sa.Column("availability", sa.String(32), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "source",
            sa.String(64),
            server_default="browser_extension_user_initiated",
            nullable=False,
        ),
        sa.Column(
            "provenance",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
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
    op.create_index("ix_offers_listing_id", "offers", ["listing_id"])
    op.create_index("ix_offers_observed_at", "offers", ["observed_at"])

    # 4. Price records table
    op.create_table(
        "price_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "offer_id",
            UUID(as_uuid=True),
            sa.ForeignKey("offers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=True),
        sa.Column("availability", sa.String(32), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column(
            "provenance",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
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
    op.create_index("ix_price_records_offer_id", "price_records", ["offer_id"])
    op.create_index("ix_price_records_observed_at", "price_records", ["observed_at"])
    op.create_index(
        "ix_price_records_offer_obs", "price_records", ["offer_id", "observed_at"]
    )

    # 5. Extraction records table
    op.create_table(
        "extraction_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("record_id", sa.String(64), nullable=False),
        sa.Column(
            "marketplace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("marketplaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "listing_id",
            UUID(as_uuid=True),
            sa.ForeignKey("listings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "schema_version", sa.String(16), server_default="1.0", nullable=False
        ),
        sa.Column("asin", sa.String(32), nullable=True),
        sa.Column("product_url", sa.String(1024), nullable=False),
        sa.Column("extraction_method", sa.String(64), nullable=False),
        sa.Column("extension_version", sa.String(32), nullable=False),
        sa.Column(
            "raw_payload",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "normalized_payload",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "validation_payload",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("storage_object_key", sa.String(255), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
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
        "ix_extraction_records_record_id",
        "extraction_records",
        ["record_id"],
        unique=True,
    )
    op.create_index("ix_extraction_records_asin", "extraction_records", ["asin"])
    op.create_index("ix_extraction_records_status", "extraction_records", ["status"])
    op.create_index(
        "ix_extraction_records_extracted_at",
        "extraction_records",
        ["extracted_at"],
    )

    # 6. Ingestion jobs table
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("record_id", sa.String(64), nullable=True),
        sa.Column(
            "listing_id",
            UUID(as_uuid=True),
            sa.ForeignKey("listings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        "ix_ingestion_jobs_idempotency_key",
        "ingestion_jobs",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index("ix_ingestion_jobs_status", "ingestion_jobs", ["status"])

    # 7. Evidence table
    op.create_table(
        "evidence",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "variant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("variants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("parameter_key", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("trust_tier", sa.Integer(), nullable=False),
        sa.Column("current_version_id", UUID(as_uuid=True), nullable=True),
        sa.Column("visibility", sa.String(32), server_default="public", nullable=False),
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
    op.create_index("ix_evidence_product_id", "evidence", ["product_id"])
    op.create_index("ix_evidence_variant_id", "evidence", ["variant_id"])
    op.create_index("ix_evidence_parameter_key", "evidence", ["parameter_key"])
    op.create_index("ix_evidence_trust_tier", "evidence", ["trust_tier"])

    # 8. Evidence versions table
    op.create_table(
        "evidence_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "evidence_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evidence.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "value",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("methodology", sa.String(128), nullable=True),
        sa.Column(
            "verification_state",
            sa.String(32),
            server_default="unverified",
            nullable=False,
        ),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("raw_source_span", sa.String(1024), nullable=True),
        sa.Column(
            "extraction_record_id",
            UUID(as_uuid=True),
            sa.ForeignKey("extraction_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
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
        "ix_evidence_versions_evidence_id",
        "evidence_versions",
        ["evidence_id"],
    )
    op.create_index(
        "ix_evidence_versions_ev_ver",
        "evidence_versions",
        ["evidence_id", "version"],
    )

    # 9. Evaluation models table
    op.create_table(
        "evaluation_models",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "category_id",
            UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
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
        "ix_evaluation_models_category_id",
        "evaluation_models",
        ["category_id"],
    )

    # 10. Evaluation model versions table
    op.create_table(
        "evaluation_model_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "model_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluation_models.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), server_default="draft", nullable=False),
        sa.Column(
            "definition",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column("approved_by", sa.String(128), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("model_id", "version", name="uq_eval_model_version"),
    )
    op.create_index(
        "ix_evaluation_model_versions_model_id",
        "evaluation_model_versions",
        ["model_id"],
    )
    op.create_index(
        "ix_evaluation_model_versions_status",
        "evaluation_model_versions",
        ["status"],
    )

    # 11. Evaluations table
    op.create_table(
        "evaluations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "variant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("variants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "model_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluation_model_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "confidence_state",
            sa.String(32),
            server_default="unavailable",
            nullable=False,
        ),
        sa.Column("confidence_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("coverage", sa.Numeric(4, 3), nullable=True),
        sa.Column(
            "limitations",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("evidence_snapshot_hash", sa.String(64), nullable=True),
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
    op.create_index("ix_evaluations_variant_id", "evaluations", ["variant_id"])
    op.create_index(
        "ix_evaluations_var_created",
        "evaluations",
        ["variant_id", "created_at"],
    )

    # 12. Parameter results table
    op.create_table(
        "parameter_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "evaluation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("parameter_key", sa.String(64), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("status", sa.String(32), server_default="not_scored", nullable=False),
        sa.Column("weight", sa.Numeric(4, 3), nullable=True),
        sa.Column("is_critical", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "evidence_ids",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column(
            "explanation_data",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
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
        "ix_parameter_results_evaluation_id",
        "parameter_results",
        ["evaluation_id"],
    )


def downgrade() -> None:
    op.drop_table("parameter_results")
    op.drop_table("evaluations")
    op.drop_table("evaluation_model_versions")
    op.drop_table("evaluation_models")
    op.drop_table("evidence_versions")
    op.drop_table("evidence")
    op.drop_table("ingestion_jobs")
    op.drop_table("extraction_records")
    op.drop_table("price_records")
    op.drop_table("offers")
    op.drop_table("listings")
    op.drop_table("marketplaces")
