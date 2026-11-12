"""Phase B10: Comparison sessions concurrency trigger and recommendations persistence.

Revision ID: 0012_b10_comparison_recommendations
Revises: 0011_eval_db_immutability
Create Date: 2026-11-12 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0012_b10_comparison_recommendations"
down_revision: str | None = "0011_eval_db_immutability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        # 1. Trigger function enforcing maximum 2 active comparison sessions per owner under concurrency
        op.execute(
            """
            CREATE OR REPLACE FUNCTION public.enforce_max_active_comparison_sessions()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                active_count integer;
                owner_key text;
            BEGIN
                IF NEW.status = 'active' THEN
                    IF NEW.user_id IS NOT NULL THEN
                        owner_key := 'comp_session_user:' || NEW.user_id::text;
                    ELSIF NEW.anonymous_session_token IS NOT NULL THEN
                        owner_key := 'comp_session_anon:' || NEW.anonymous_session_token;
                    ELSE
                        owner_key := NULL;
                    END IF;

                    IF owner_key IS NOT NULL THEN
                        -- Transaction-scoped advisory lock serialized per owner
                        PERFORM pg_advisory_xact_lock(hashtext(owner_key));

                        -- Count active sessions for this owner excluding current row
                        IF NEW.user_id IS NOT NULL THEN
                            SELECT COUNT(*) INTO active_count
                            FROM public.comparison_sessions
                            WHERE user_id = NEW.user_id
                              AND status = 'active'
                              AND id <> COALESCE(NEW.id, '00000000-0000-0000-0000-000000000000'::uuid);
                        ELSE
                            SELECT COUNT(*) INTO active_count
                            FROM public.comparison_sessions
                            WHERE anonymous_session_token = NEW.anonymous_session_token
                              AND status = 'active'
                              AND id <> COALESCE(NEW.id, '00000000-0000-0000-0000-000000000000'::uuid);
                        END IF;

                        IF active_count >= 2 THEN
                            RAISE EXCEPTION 'Maximum active comparison sessions limit reached (2 allowed per user/session)'
                                USING ERRCODE = 'check_violation';
                        END IF;
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$;
            """
        )

        op.execute(
            """
            CREATE TRIGGER trg_comparison_sessions_max_active
            BEFORE INSERT OR UPDATE OF status, user_id, anonymous_session_token
            ON public.comparison_sessions
            FOR EACH ROW
            EXECUTE FUNCTION public.enforce_max_active_comparison_sessions();
            """
        )

    # 2. Recommendations persistence table
    op.create_table(
        "recommendations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("anonymous_session_token", sa.String(128), nullable=True, index=True),
        sa.Column(
            "category_id",
            UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("raw_query", sa.Text(), nullable=True),
        sa.Column("parsed_requirements", JSONB if is_postgres else sa.JSON(), nullable=False),
        sa.Column("parser_version", sa.String(32), server_default="v1", nullable=False),
        sa.Column("ranking_policy_version", sa.String(32), server_default="v1", nullable=False),
        sa.Column(
            "model_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluation_model_versions.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("eligible_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ineligible_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("hard_constraint_results", JSONB if is_postgres else sa.JSON(), nullable=False),
        sa.Column("ranked_results", JSONB if is_postgres else sa.JSON(), nullable=False),
        sa.Column("rejected_results", JSONB if is_postgres else sa.JSON(), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=True, index=True),
        sa.Column("output_fingerprint", sa.String(64), nullable=True, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            index=True,
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.drop_table("recommendations")

    if is_postgres:
        op.execute("DROP TRIGGER IF EXISTS trg_comparison_sessions_max_active ON public.comparison_sessions;")
        op.execute("DROP FUNCTION IF EXISTS public.enforce_max_active_comparison_sessions();")

