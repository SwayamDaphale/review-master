"""Migration lifecycle test verifying upgrade, downgrade, and re-upgrade on an isolated database."""

import os
import tempfile
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command


@pytest.fixture
def isolated_alembic_env():
    """Create a temporary isolated SQLite database file and configured Alembic Config."""
    fd, tmp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Resolve alembic.ini path
    current_dir = Path.cwd()
    if (current_dir / "alembic.ini").exists():
        ini_path = current_dir / "alembic.ini"
    elif (current_dir / "backend" / "alembic.ini").exists():
        ini_path = current_dir / "backend" / "alembic.ini"
    else:
        ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"

    cfg = Config(str(ini_path))
    temp_url = f"sqlite:///{tmp_db_path}"
    cfg.set_main_option("sqlalchemy.url", temp_url)

    yield cfg, temp_url, tmp_db_path

    # Teardown
    if os.path.exists(tmp_db_path):
        os.remove(tmp_db_path)


def test_migration_upgrade_downgrade_cycle(isolated_alembic_env):
    """Test clean upgrade to head, verify tables, downgrade to 0003, and re-upgrade."""
    cfg, db_url, _ = isolated_alembic_env

    # 1. Upgrade from clean database through head
    command.upgrade(cfg, "head")

    engine = sa.create_engine(db_url)
    inspector = sa.inspect(engine)
    tables = inspector.get_table_names()

    # Verify all expected B3 completion tables exist
    expected_tables = {
        "users",
        "roles",
        "user_roles",
        "attribute_definitions",
        "variant_attribute_values",
        "comparison_sessions",
        "comparison_items",
        "audit_logs",
        "import_tokens",
        "categories",
        "product_families",
        "products",
        "variants",
        "marketplaces",
        "listings",
        "offers",
        "price_records",
        "extraction_records",
        "ingestion_jobs",
        "evidence",
        "evidence_versions",
        "evaluation_models",
        "evaluation_model_versions",
        "evaluations",
        "parameter_results",
    }
    for expected in expected_tables:
        assert expected in tables, f"Expected table '{expected}' not found after upgrade to head"

    # Verify columns added to ingestion_jobs
    job_cols = {col["name"] for col in inspector.get_columns("ingestion_jobs")}
    assert "job_type" in job_cols
    assert "payload" in job_cols

    # 2. Downgrade to 0003_marketplace_and_evidence
    command.downgrade(cfg, "0003_marketplace_and_evidence")

    inspector_down = sa.inspect(engine)
    down_tables = inspector_down.get_table_names()

    # B3 completion tables must be dropped in downgrade
    for dropped in [
        "users",
        "roles",
        "user_roles",
        "attribute_definitions",
        "variant_attribute_values",
        "comparison_sessions",
        "comparison_items",
        "audit_logs",
        "import_tokens",
    ]:
        assert dropped not in down_tables, f"Table '{dropped}' should have been dropped on downgrade"

    # Existing 0003 tables must remain
    for preserved in ["marketplaces", "listings", "offers", "products", "variants"]:
        assert preserved in down_tables, f"Existing table '{preserved}' should be preserved"

    # 3. Re-upgrade to head
    command.upgrade(cfg, "head")

    inspector_reup = sa.inspect(engine)
    reup_tables = inspector_reup.get_table_names()
    for expected in expected_tables:
        assert expected in reup_tables, f"Expected table '{expected}' not found after re-upgrade"

    engine.dispose()
