"""catalog intelligence, unit registry, corrections, and review intelligence

Revision ID: 0006_catalog_intelligence_and_review_intelligence
Revises: 0005_authentication_sessions
Create Date: 2026-11-08 12:00:00.000000

"""

from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_catalog_and_review_intel"
down_revision: str | None = "0005_authentication_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    now_default = sa.text("now()") if is_postgres else sa.text("CURRENT_TIMESTAMP")
    false_default = sa.text("false") if is_postgres else sa.text("0")
    true_default = sa.text("true") if is_postgres else sa.text("1")

    # 1. Domain Units Registry Table
    units_table = op.create_table(
        "units",
        sa.Column("key", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("dimension", sa.String(32), nullable=False),
        sa.Column("canonical_unit", sa.String(32), nullable=False),
        sa.Column("conversion_factor", sa.Numeric(24, 12), nullable=False),
        sa.Column(
            "is_binary", sa.Boolean(), server_default=false_default, nullable=False
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=true_default, nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=now_default,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=now_default,
            nullable=False,
        ),
    )
    op.create_index("ix_units_key", "units", ["key"])
    op.create_index("ix_units_dimension", "units", ["dimension"])

    # Seed core domain units into units table
    initial_units = [
        # Decimal storage
        {
            "key": "b",
            "name": "Byte",
            "symbol": "B",
            "dimension": "storage",
            "canonical_unit": "GB",
            "conversion_factor": Decimal("0.000000001"),
            "is_binary": False,
        },
        {
            "key": "kb",
            "name": "Kilobyte",
            "symbol": "KB",
            "dimension": "storage",
            "canonical_unit": "GB",
            "conversion_factor": Decimal("0.000001"),
            "is_binary": False,
        },
        {
            "key": "mb",
            "name": "Megabyte",
            "symbol": "MB",
            "dimension": "storage",
            "canonical_unit": "GB",
            "conversion_factor": Decimal("0.001"),
            "is_binary": False,
        },
        {
            "key": "gb",
            "name": "Gigabyte",
            "symbol": "GB",
            "dimension": "storage",
            "canonical_unit": "GB",
            "conversion_factor": Decimal("1.0"),
            "is_binary": False,
        },
        {
            "key": "tb",
            "name": "Terabyte",
            "symbol": "TB",
            "dimension": "storage",
            "canonical_unit": "GB",
            "conversion_factor": Decimal("1000.0"),
            "is_binary": False,
        },
        # Binary storage
        {
            "key": "kib",
            "name": "Kibibyte",
            "symbol": "KiB",
            "dimension": "storage_binary",
            "canonical_unit": "GiB",
            "conversion_factor": Decimal("0.0009765625"),
            "is_binary": True,
        },
        {
            "key": "mib",
            "name": "Mebibyte",
            "symbol": "MiB",
            "dimension": "storage_binary",
            "canonical_unit": "GiB",
            "conversion_factor": Decimal("0.0009765625"),
            "is_binary": True,
        },
        {
            "key": "gib",
            "name": "Gibibyte",
            "symbol": "GiB",
            "dimension": "storage_binary",
            "canonical_unit": "GiB",
            "conversion_factor": Decimal("1.0"),
            "is_binary": True,
        },
        {
            "key": "tib",
            "name": "Tebibyte",
            "symbol": "TiB",
            "dimension": "storage_binary",
            "canonical_unit": "GiB",
            "conversion_factor": Decimal("1024.0"),
            "is_binary": True,
        },
        # Length / Display
        {
            "key": "inch",
            "name": "Inch",
            "symbol": "in",
            "dimension": "length",
            "canonical_unit": "inch",
            "conversion_factor": Decimal("1.0"),
            "is_binary": False,
        },
        {
            "key": "cm",
            "name": "Centimeter",
            "symbol": "cm",
            "dimension": "length",
            "canonical_unit": "inch",
            "conversion_factor": Decimal("0.393700787402"),
            "is_binary": False,
        },
        {
            "key": "mm",
            "name": "Millimeter",
            "symbol": "mm",
            "dimension": "length",
            "canonical_unit": "inch",
            "conversion_factor": Decimal("0.039370078740"),
            "is_binary": False,
        },
        # Charge
        {
            "key": "mah",
            "name": "Milliampere-hour",
            "symbol": "mAh",
            "dimension": "charge",
            "canonical_unit": "mAh",
            "conversion_factor": Decimal("1.0"),
            "is_binary": False,
        },
        {
            "key": "ah",
            "name": "Ampere-hour",
            "symbol": "Ah",
            "dimension": "charge",
            "canonical_unit": "mAh",
            "conversion_factor": Decimal("1000.0"),
            "is_binary": False,
        },
        # Mass
        {
            "key": "g",
            "name": "Gram",
            "symbol": "g",
            "dimension": "mass",
            "canonical_unit": "g",
            "conversion_factor": Decimal("1.0"),
            "is_binary": False,
        },
        {
            "key": "kg",
            "name": "Kilogram",
            "symbol": "kg",
            "dimension": "mass",
            "canonical_unit": "g",
            "conversion_factor": Decimal("1000.0"),
            "is_binary": False,
        },
        # Frequency
        {
            "key": "ghz",
            "name": "Gigahertz",
            "symbol": "GHz",
            "dimension": "frequency",
            "canonical_unit": "GHz",
            "conversion_factor": Decimal("1.0"),
            "is_binary": False,
        },
        {
            "key": "mhz",
            "name": "Megahertz",
            "symbol": "MHz",
            "dimension": "frequency",
            "canonical_unit": "GHz",
            "conversion_factor": Decimal("0.001"),
            "is_binary": False,
        },
        # Power
        {
            "key": "w",
            "name": "Watt",
            "symbol": "W",
            "dimension": "power",
            "canonical_unit": "W",
            "conversion_factor": Decimal("1.0"),
            "is_binary": False,
        },
    ]
    op.bulk_insert(units_table, initial_units)

    # 2. Extend Attribute Definitions
    op.add_column(
        "attribute_definitions",
        sa.Column("canonical_unit", sa.String(32), nullable=True),
    )
    op.add_column(
        "attribute_definitions",
        sa.Column("validation_rules", sa.JSON(), server_default="{}", nullable=False),
    )
    op.add_column(
        "attribute_definitions",
        sa.Column(
            "is_required", sa.Boolean(), server_default=false_default, nullable=False
        ),
    )
    op.add_column(
        "attribute_definitions",
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
    )

    # 3. Extend Variant Attribute Values
    op.add_column(
        "variant_attribute_values",
        sa.Column("original_unit", sa.String(32), nullable=True),
    )
    op.add_column(
        "variant_attribute_values",
        sa.Column("canonical_unit", sa.String(32), nullable=True),
    )
    op.add_column(
        "variant_attribute_values",
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
    )
    op.add_column(
        "variant_attribute_values",
        sa.Column(
            "validation_status", sa.String(32), server_default="valid", nullable=False
        ),
    )
    op.add_column(
        "variant_attribute_values",
        sa.Column("evidence_id", UUID(as_uuid=True), nullable=True),
    )
    if is_postgres:
        op.create_foreign_key(
            "fk_vav_evidence_id",
            "variant_attribute_values",
            "evidence",
            ["evidence_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_vav_evidence_id", "variant_attribute_values", ["evidence_id"])

    # 4. Catalog Correction Ledger Table
    op.create_table(
        "catalog_corrections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(64), nullable=False),
        sa.Column("before_value", sa.JSON(), nullable=True),
        sa.Column("after_value", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("evidence_reference", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=now_default,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=now_default,
            nullable=False,
        ),
    )
    op.create_index(
        "ix_catalog_corrections_target",
        "catalog_corrections",
        ["target_type", "target_id"],
    )
    op.create_index("ix_catalog_corrections_actor", "catalog_corrections", ["actor_id"])

    # 5. Review Analyses Table
    op.create_table(
        "review_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "variant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("variants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_evidence_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evidence.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("review_source_id", sa.String(128), nullable=True),
        sa.Column("review_text", sa.Text(), nullable=False),
        sa.Column("sentiment", sa.String(32), nullable=False),
        sa.Column(
            "sentiment_confidence",
            sa.Numeric(5, 4),
            server_default="1.0",
            nullable=False,
        ),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column(
            "prompt_version", sa.String(32), server_default="1.0", nullable=False
        ),
        sa.Column("status", sa.String(32), server_default="completed", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=now_default,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=now_default,
            nullable=False,
        ),
    )
    op.create_index("ix_review_analyses_product_id", "review_analyses", ["product_id"])
    op.create_index("ix_review_analyses_variant_id", "review_analyses", ["variant_id"])
    op.create_index("ix_review_analyses_sentiment", "review_analyses", ["sentiment"])
    op.create_index("ix_review_analyses_status", "review_analyses", ["status"])

    # 6. Review Aspect Opinions Table
    op.create_table(
        "review_aspect_opinions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            UUID(as_uuid=True),
            sa.ForeignKey("review_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("aspect_key", sa.String(64), nullable=False),
        sa.Column("polarity", sa.String(32), nullable=False),
        sa.Column("claim", sa.String(512), nullable=False),
        sa.Column("raw_quote", sa.String(1024), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), server_default="1.0", nullable=False),
        sa.Column(
            "source_evidence_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evidence.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=now_default,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=now_default,
            nullable=False,
        ),
    )
    op.create_index(
        "ix_review_aspects_analysis_id", "review_aspect_opinions", ["analysis_id"]
    )
    op.create_index(
        "ix_review_aspects_aspect_key", "review_aspect_opinions", ["aspect_key"]
    )
    op.create_index(
        "ix_review_aspects_polarity", "review_aspect_opinions", ["polarity"]
    )

    # 7. Review Pros and Cons Table
    op.create_table(
        "review_pros_cons",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            UUID(as_uuid=True),
            sa.ForeignKey("review_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_type", sa.String(16), nullable=False),
        sa.Column("text", sa.String(512), nullable=False),
        sa.Column("aspect_key", sa.String(64), nullable=True),
        sa.Column(
            "source_evidence_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evidence.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=now_default,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=now_default,
            nullable=False,
        ),
    )
    op.create_index(
        "ix_review_pros_cons_analysis_id", "review_pros_cons", ["analysis_id"]
    )
    op.create_index("ix_review_pros_cons_type", "review_pros_cons", ["item_type"])

    # 8. Review Summaries Table
    op.create_table(
        "review_summaries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "variant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("variants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column(
            "total_reviews_analyzed", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "sentiment_distribution", sa.JSON(), server_default="{}", nullable=False
        ),
        sa.Column("aspect_summaries", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("key_pros", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("key_cons", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), server_default="1.0", nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=now_default,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=now_default,
            nullable=False,
        ),
    )
    op.create_index(
        "ix_review_summaries_product_id", "review_summaries", ["product_id"]
    )
    op.create_index(
        "ix_review_summaries_variant_id", "review_summaries", ["variant_id"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.drop_table("review_summaries")
    op.drop_table("review_pros_cons")
    op.drop_table("review_aspect_opinions")
    op.drop_table("review_analyses")
    op.drop_table("catalog_corrections")

    if is_postgres:
        op.drop_constraint(
            "fk_vav_evidence_id", "variant_attribute_values", type_="foreignkey"
        )
    op.drop_index("ix_vav_evidence_id", table_name="variant_attribute_values")
    op.drop_column("variant_attribute_values", "evidence_id")
    op.drop_column("variant_attribute_values", "validation_status")
    op.drop_column("variant_attribute_values", "confidence")
    op.drop_column("variant_attribute_values", "canonical_unit")
    op.drop_column("variant_attribute_values", "original_unit")

    op.drop_column("attribute_definitions", "status")
    op.drop_column("attribute_definitions", "is_required")
    op.drop_column("attribute_definitions", "validation_rules")
    op.drop_column("attribute_definitions", "canonical_unit")

    op.drop_table("units")
