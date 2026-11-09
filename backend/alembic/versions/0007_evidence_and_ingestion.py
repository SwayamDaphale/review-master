"""0007: Evidence and ingestion extensions.

Revision ID: 0007_evidence_and_ingestion
Revises: 0006_catalog_and_review_intel
Create Date: 2026-11-10 02:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "0007_evidence_and_ingestion"
down_revision = "0006_catalog_and_review_intel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add sha256_digest and user_id to extraction_records using batch mode for cross-DB compatibility
    with op.batch_alter_table("extraction_records") as batch_op:
        batch_op.add_column(
            sa.Column("sha256_digest", sa.String(64), nullable=True),
        )
        batch_op.add_column(
            sa.Column(
                "user_id",
                UUID(as_uuid=True),
                sa.ForeignKey(
                    "users.id",
                    ondelete="SET NULL",
                    name="fk_extraction_records_user_id",
                ),
                nullable=True,
            ),
        )
        batch_op.create_index(
            "ix_extraction_records_sha256_digest",
            ["sha256_digest"],
        )
        batch_op.create_index(
            "ix_extraction_records_user_id",
            ["user_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("extraction_records") as batch_op:
        batch_op.drop_index("ix_extraction_records_user_id")
        batch_op.drop_index("ix_extraction_records_sha256_digest")
        batch_op.drop_column("user_id")
        batch_op.drop_column("sha256_digest")
