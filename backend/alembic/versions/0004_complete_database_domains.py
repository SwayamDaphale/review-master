"""complete database domains: identity, attributes, comparison, ops, jobs, append-only triggers

Revision ID: 0004_complete_database_domains
Revises: 0003_marketplace_and_evidence
Create Date: 2026-11-08 02:45:00.000000

"""

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_complete_database_domains"
down_revision: str | None = "0003_marketplace_and_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # ==========================================
    # 1. Identity Domain: users, roles, user_roles
    # ==========================================
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
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
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
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
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "role_id",
            UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # ==========================================
    # 2. Normalized Catalog Attributes
    # ==========================================
    op.create_table(
        "attribute_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "category_id",
            UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("data_type", sa.String(32), server_default="string", nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("is_filterable", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_searchable", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
        sa.UniqueConstraint("category_id", "key", name="uq_attribute_definitions_category_key"),
    )
    op.create_index("ix_attribute_definitions_key", "attribute_definitions", ["key"])
    op.create_index("ix_attribute_definitions_category_id", "attribute_definitions", ["category_id"])

    op.create_table(
        "variant_attribute_values",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "variant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("variants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "attribute_id",
            UUID(as_uuid=True),
            sa.ForeignKey("attribute_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("value_text", sa.String(512), nullable=True),
        sa.Column("value_numeric", sa.Numeric(12, 4), nullable=True),
        sa.Column("value_boolean", sa.Boolean(), nullable=True),
        sa.Column(
            "value_json",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("raw_value", sa.Text(), nullable=True),
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
            "variant_id",
            "attribute_id",
            name="uq_variant_attribute_values_variant_attribute",
        ),
    )
    op.create_index("ix_variant_attribute_values_variant_id", "variant_attribute_values", ["variant_id"])
    op.create_index("ix_variant_attribute_values_attribute_id", "variant_attribute_values", ["attribute_id"])

    # ==========================================
    # 3. Comparison Domain: sessions, items
    # ==========================================
    op.create_table(
        "comparison_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("anonymous_session_token", sa.String(128), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column(
            "category_id",
            UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
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
    op.create_index("ix_comparison_sessions_user_id", "comparison_sessions", ["user_id"])
    op.create_index(
        "ix_comparison_sessions_token",
        "comparison_sessions",
        ["anonymous_session_token"],
    )
    op.create_index("ix_comparison_sessions_category_id", "comparison_sessions", ["category_id"])

    op.create_table(
        "comparison_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("comparison_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "session_id",
            "product_id",
            "variant_id",
            name="uq_comparison_items_session_product_variant",
        ),
    )
    op.create_index("ix_comparison_items_session_id", "comparison_items", ["session_id"])
    op.create_index("ix_comparison_items_product_id", "comparison_items", ["product_id"])
    op.create_index("ix_comparison_items_variant_id", "comparison_items", ["variant_id"])

    # ==========================================
    # 4. Operations Domain: audit_logs, import_tokens
    # ==========================================
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("actor_type", sa.String(32), server_default="user", nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), server_default="success", nullable=False),
        sa.Column("request_id", sa.String(128), nullable=True),
        sa.Column(
            "metadata_payload",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_target_type", "audit_logs", ["target_type"])
    op.create_index("ix_audit_logs_target_id", "audit_logs", ["target_id"])
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.create_table(
        "import_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("context", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_import_tokens_token_hash", "import_tokens", ["token_hash"], unique=True)
    op.create_index("ix_import_tokens_user_id", "import_tokens", ["user_id"])
    op.create_index("ix_import_tokens_expires_at", "import_tokens", ["expires_at"])

    # ==========================================
    # 5. Jobs Reconciliation: extend ingestion_jobs
    # ==========================================
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "job_type",
            sa.String(64),
            server_default="ingestion",
            nullable=False,
        ),
    )
    op.create_index("ix_ingestion_jobs_job_type", "ingestion_jobs", ["job_type"])
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "payload",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
    )

    # ==========================================
    # 6. Append-Only Database Triggers (PostgreSQL)
    # ==========================================
    if is_postgres:
        op.execute(
            """
            CREATE OR REPLACE FUNCTION prevent_append_only_modification()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'Table % is append-only: updates and deletes are prohibited', TG_TABLE_NAME;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        for tbl in ["price_records", "evidence_versions", "evaluations", "audit_logs"]:
            op.execute(
                f"""
                CREATE TRIGGER trg_{tbl}_append_only
                BEFORE UPDATE OR DELETE ON {tbl}
                FOR EACH ROW
                EXECUTE FUNCTION prevent_append_only_modification();
                """
            )

    # ==========================================
    # 7. Safe Data Migration: Populate attribute definitions & variant values
    # ==========================================
    # Define common attribute definitions
    attr_defs = [
        {"key": "ram_gb", "name": "RAM", "data_type": "numeric", "unit": "GB"},
        {"key": "storage_gb", "name": "Internal Storage", "data_type": "numeric", "unit": "GB"},
        {"key": "color", "name": "Color", "data_type": "string", "unit": None},
        {"key": "processor", "name": "Processor", "data_type": "string", "unit": None},
        {"key": "capacity_tb", "name": "Storage Capacity", "data_type": "numeric", "unit": "TB"},
        {"key": "interface", "name": "Interface", "data_type": "string", "unit": None},
    ]

    now_ts = datetime.now(UTC)
    attr_id_map: dict[str, uuid.UUID] = {}
    for d in attr_defs:
        attr_uuid = uuid.uuid4()
        attr_id_map[d["key"]] = attr_uuid
        op.execute(
            sa.text(
                "INSERT INTO attribute_definitions (id, key, name, data_type, unit, is_filterable, is_searchable, created_at, updated_at) "
                "VALUES (:id, :key, :name, :data_type, :unit, true, false, :created_at, :updated_at) "
                "ON CONFLICT DO NOTHING"
            ).bindparams(
                id=attr_uuid,
                key=d["key"],
                name=d["name"],
                data_type=d["data_type"],
                unit=d["unit"],
                created_at=now_ts,
                updated_at=now_ts,
            )
        )

    # Fetch existing definitions to guarantee we have the actual IDs even if pre-existing
    defs_result = bind.execute(sa.text("SELECT id, key FROM attribute_definitions")).fetchall()
    actual_attr_map = {row[1]: row[0] for row in defs_result}

    # Inspect variants and migrate known keys without touching variants.configuration
    variants_rows = bind.execute(sa.text("SELECT id, configuration FROM variants")).fetchall()
    for v_id, raw_config in variants_rows:
        if not raw_config:
            continue
        config = raw_config if isinstance(raw_config, dict) else json.loads(raw_config)
        for key, val in config.items():
            if key in actual_attr_map and val is not None:
                attr_id = actual_attr_map[key]
                val_text = str(val) if not isinstance(val, (int, float, bool)) else None
                val_numeric = float(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else None
                val_boolean = bool(val) if isinstance(val, bool) else None
                op.execute(
                    sa.text(
                        "INSERT INTO variant_attribute_values (id, variant_id, attribute_id, value_text, value_numeric, value_boolean, raw_value, created_at, updated_at) "
                        "VALUES (:id, :variant_id, :attribute_id, :val_text, :val_numeric, :val_boolean, :raw_val, :created_at, :updated_at) "
                        "ON CONFLICT (variant_id, attribute_id) DO NOTHING"
                    ).bindparams(
                        id=uuid.uuid4(),
                        variant_id=v_id,
                        attribute_id=attr_id,
                        val_text=val_text,
                        val_numeric=val_numeric,
                        val_boolean=val_boolean,
                        raw_val=str(val),
                        created_at=now_ts,
                        updated_at=now_ts,
                    )
                )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # Drop triggers and append-only trigger function if postgres
    if is_postgres:
        for tbl in ["price_records", "evidence_versions", "evaluations", "audit_logs"]:
            op.execute(f"DROP TRIGGER IF EXISTS trg_{tbl}_append_only ON {tbl}")
        op.execute("DROP FUNCTION IF EXISTS prevent_append_only_modification()")

    # Remove added columns from ingestion_jobs
    op.drop_index("ix_ingestion_jobs_job_type", table_name="ingestion_jobs")
    op.drop_column("ingestion_jobs", "payload")
    op.drop_column("ingestion_jobs", "job_type")

    # Drop tables in reverse topological order
    op.drop_index("ix_import_tokens_expires_at", table_name="import_tokens")
    op.drop_index("ix_import_tokens_user_id", table_name="import_tokens")
    op.drop_index("ix_import_tokens_token_hash", table_name="import_tokens")
    op.drop_table("import_tokens")

    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_request_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_target_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_target_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_comparison_items_variant_id", table_name="comparison_items")
    op.drop_index("ix_comparison_items_product_id", table_name="comparison_items")
    op.drop_index("ix_comparison_items_session_id", table_name="comparison_items")
    op.drop_table("comparison_items")

    op.drop_index("ix_comparison_sessions_category_id", table_name="comparison_sessions")
    op.drop_index("ix_comparison_sessions_token", table_name="comparison_sessions")
    op.drop_index("ix_comparison_sessions_user_id", table_name="comparison_sessions")
    op.drop_table("comparison_sessions")

    op.drop_index("ix_variant_attribute_values_attribute_id", table_name="variant_attribute_values")
    op.drop_index("ix_variant_attribute_values_variant_id", table_name="variant_attribute_values")
    op.drop_table("variant_attribute_values")

    op.drop_index("ix_attribute_definitions_category_id", table_name="attribute_definitions")
    op.drop_index("ix_attribute_definitions_key", table_name="attribute_definitions")
    op.drop_table("attribute_definitions")

    op.drop_table("user_roles")

    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_table("roles")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
