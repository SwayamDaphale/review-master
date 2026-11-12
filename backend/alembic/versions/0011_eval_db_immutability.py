"""Database-level immutability for parameter_results and evaluation_model_versions.

Revision ID: 0011_eval_db_immutability
Revises: 0010_eval_engine_b9
Create Date: 2026-11-11 16:30:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011_eval_db_immutability"
down_revision: str | None = "0010_eval_engine_b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        # 1. Protect parameter_results as append-only (rejects all direct UPDATE and DELETE)
        op.execute(
            """
            CREATE TRIGGER trg_parameter_results_append_only
            BEFORE UPDATE OR DELETE ON public.parameter_results
            FOR EACH ROW
            EXECUTE FUNCTION prevent_append_only_modification();
            """
        )

        # 2. Function enforcing lifecycle immutability rules on evaluation_model_versions
        op.execute(
            """
            CREATE OR REPLACE FUNCTION public.enforce_eval_model_version_immutability()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.status = 'published' THEN
                        RAISE EXCEPTION 'Published evaluation model version % cannot be deleted', OLD.id;
                    ELSIF OLD.status = 'deprecated' THEN
                        RAISE EXCEPTION 'Deprecated evaluation model version % cannot be deleted', OLD.id;
                    END IF;
                    RETURN OLD;
                ELSIF TG_OP = 'UPDATE' THEN
                    IF OLD.status = 'published' THEN
                        -- Allow transition from published to deprecated ONLY if all other core columns remain identical
                        IF NEW.status = 'deprecated' THEN
                            IF (OLD.id IS DISTINCT FROM NEW.id) OR
                               (OLD.model_id IS DISTINCT FROM NEW.model_id) OR
                               (OLD.version IS DISTINCT FROM NEW.version) OR
                               (OLD.definition IS DISTINCT FROM NEW.definition) OR
                               (OLD.approved_by IS DISTINCT FROM NEW.approved_by) OR
                               (OLD.published_at IS DISTINCT FROM NEW.published_at) OR
                               (OLD.created_at IS DISTINCT FROM NEW.created_at) OR
                               (OLD.configuration_hash IS DISTINCT FROM NEW.configuration_hash) THEN
                                RAISE EXCEPTION 'Published evaluation model version % is immutable: only status may be changed to deprecated', OLD.id;
                            END IF;
                            RETURN NEW;
                        ELSE
                            RAISE EXCEPTION 'Published evaluation model version % is immutable and cannot be updated', OLD.id;
                        END IF;
                    ELSIF OLD.status = 'deprecated' THEN
                        RAISE EXCEPTION 'Deprecated evaluation model version % is immutable and cannot be updated', OLD.id;
                    END IF;
                    RETURN NEW;
                END IF;
                RETURN NEW;
            END;
            $$;
            """
        )

        # 3. Attach trigger to evaluation_model_versions
        op.execute(
            """
            CREATE TRIGGER trg_eval_model_version_immutability
            BEFORE UPDATE OR DELETE ON public.evaluation_model_versions
            FOR EACH ROW
            EXECUTE FUNCTION enforce_eval_model_version_immutability();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP TRIGGER IF EXISTS trg_eval_model_version_immutability ON public.evaluation_model_versions;")
        op.execute("DROP FUNCTION IF EXISTS public.enforce_eval_model_version_immutability();")
        op.execute("DROP TRIGGER IF EXISTS trg_parameter_results_append_only ON public.parameter_results;")
