"""create catalog tables

Revision ID: 0002_catalog_tables
Revises: 0001_initial_baseline
Create Date: 2026-11-07 17:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_catalog_tables"
down_revision: str | None = "0001_initial_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Categories table
    op.create_table(
        "categories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "schema_version", sa.String(32), server_default="1.0.0", nullable=False
        ),
        sa.Column(
            "spec_schema", JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True
        ),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
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
    op.create_index("ix_categories_key", "categories", ["key"], unique=True)

    # 2. Product Families table
    op.create_table(
        "product_families",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "category_id",
            UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("manufacturer", sa.String(255), nullable=False),
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
        "ix_product_families_category_id", "product_families", ["category_id"]
    )
    op.create_index(
        "ix_product_families_manufacturer", "product_families", ["manufacturer"]
    )
    op.create_index(
        "ix_product_families_mfr_name", "product_families", ["manufacturer", "name"]
    )

    # 3. Products table
    op.create_table(
        "products",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "family_id",
            UUID(as_uuid=True),
            sa.ForeignKey("product_families.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "category_id",
            UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("manufacturer", sa.String(255), nullable=False),
        sa.Column("mpn", sa.String(128), nullable=True),
        sa.Column("gtin", sa.String(64), nullable=True),
        sa.Column("generation", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
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
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_family_id", "products", ["family_id"])
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_manufacturer", "products", ["manufacturer"])
    op.create_index("ix_products_gtin", "products", ["gtin"])
    op.create_index("ix_products_mfr_mpn", "products", ["manufacturer", "mpn"])

    # 4. Variants table
    op.create_table(
        "variants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "configuration",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("sku_label", sa.String(255), nullable=False),
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
            "product_id", "config_hash", name="uq_variants_product_config_hash"
        ),
    )
    op.create_index("ix_variants_product_id", "variants", ["product_id"])
    op.create_index("ix_variants_config_hash", "variants", ["config_hash"])


def downgrade() -> None:
    op.drop_table("variants")
    op.drop_table("products")
    op.drop_table("product_families")
    op.drop_table("categories")
