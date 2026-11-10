"""0008: Durable background jobs and execution state tracking.

Revision ID: 0008_durable_jobs
Revises: 0007_evidence_and_ingestion
Create Date: 2026-11-10 04:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "0008_durable_jobs"
down_revision = "0007_evidence_and_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create durable 'jobs' table
    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="SET NULL",
                name="fk_jobs_user_id",
            ),
            nullable=True,
        ),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column("worker_id", sa.String(128), nullable=True),
        sa.Column(
            "retry_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "max_retries",
            sa.Integer(),
            server_default="3",
            nullable=False,
        ),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "payload",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column(
            "result",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_jobs_job_type", "jobs", ["job_type"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index(
        "ix_jobs_idempotency_key", "jobs", ["idempotency_key"], unique=True
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    op.create_index("ix_jobs_correlation_id", "jobs", ["correlation_id"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])
    op.create_index("ix_jobs_updated_at", "jobs", ["updated_at"])

    # 2. Add durable tracking columns to ingestion_jobs using batch mode
    with op.batch_alter_table("ingestion_jobs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "retry_count",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "max_retries",
                sa.Integer(),
                server_default="3",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("worker_id", sa.String(128), nullable=True)
        )
        batch_op.add_column(
            sa.Column("correlation_id", sa.String(128), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "user_id",
                UUID(as_uuid=True),
                sa.ForeignKey(
                    "users.id",
                    ondelete="SET NULL",
                    name="fk_ingestion_jobs_user_id",
                ),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index(
            "ix_ingestion_jobs_correlation_id",
            ["correlation_id"],
        )
        batch_op.create_index(
            "ix_ingestion_jobs_user_id",
            ["user_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("ingestion_jobs") as batch_op:
        batch_op.drop_index("ix_ingestion_jobs_user_id")
        batch_op.drop_index("ix_ingestion_jobs_correlation_id")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("user_id")
        batch_op.drop_column("correlation_id")
        batch_op.drop_column("worker_id")
        batch_op.drop_column("heartbeat_at")
        batch_op.drop_column("max_retries")
        batch_op.drop_column("retry_count")

    op.drop_index("ix_jobs_updated_at", table_name="jobs")
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_index("ix_jobs_correlation_id", table_name="jobs")
    op.drop_index("ix_jobs_user_id", table_name="jobs")
    op.drop_index("ix_jobs_idempotency_key", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_job_type", table_name="jobs")
    op.drop_table("jobs")

