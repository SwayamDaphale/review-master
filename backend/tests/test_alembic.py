"""Tests for Alembic configuration and migration chain validity."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def get_alembic_ini_path() -> Path:
    """Resolve alembic.ini whether executed from repo root, backend/, or container /app."""
    current_dir = Path.cwd()
    if (current_dir / "alembic.ini").exists():
        return current_dir / "alembic.ini"
    if (current_dir / "backend" / "alembic.ini").exists():
        return current_dir / "backend" / "alembic.ini"
    file_dir = Path(__file__).resolve().parent.parent  # backend/
    return file_dir / "alembic.ini"


def test_alembic_config_loads():
    """Verify alembic.ini is present, readable, and points to the alembic directory."""
    alembic_ini_path = get_alembic_ini_path()
    assert alembic_ini_path.exists(), f"alembic.ini must exist at {alembic_ini_path}"

    cfg = Config(str(alembic_ini_path))
    script_location = cfg.get_main_option("script_location")
    assert script_location == "alembic"

    # Verify script directory and revisions
    script_dir = ScriptDirectory.from_config(cfg)
    heads = script_dir.get_heads()
    assert len(heads) == 1
    assert heads[0] == "0011_eval_db_immutability"

    # Verify revision chain integrity
    rev_0011 = script_dir.get_revision("0011_eval_db_immutability")
    assert rev_0011 is not None
    assert rev_0011.down_revision == "0010_eval_engine_b9"

    rev_0010 = script_dir.get_revision("0010_eval_engine_b9")
    assert rev_0010 is not None
    assert rev_0010.down_revision == "0009_identity_and_evidence_quality"

    rev_0009 = script_dir.get_revision("0009_identity_and_evidence_quality")
    assert rev_0009 is not None
    assert rev_0009.down_revision == "0008_durable_jobs"

    rev_0008 = script_dir.get_revision("0008_durable_jobs")
    assert rev_0008 is not None
    assert rev_0008.down_revision == "0007_evidence_and_ingestion"

    rev_0007 = script_dir.get_revision("0007_evidence_and_ingestion")
    assert rev_0007 is not None
    assert rev_0007.down_revision == "0006_catalog_and_review_intel"

    rev_0006 = script_dir.get_revision("0006_catalog_and_review_intel")
    assert rev_0006 is not None
    assert rev_0006.down_revision == "0005_authentication_sessions"

    rev_0005 = script_dir.get_revision("0005_authentication_sessions")
    assert rev_0005 is not None
    assert rev_0005.down_revision == "0004_complete_database_domains"

    rev_0004 = script_dir.get_revision("0004_complete_database_domains")
    assert rev_0004 is not None
    assert rev_0004.down_revision == "0003_marketplace_and_evidence"

    rev_0003 = script_dir.get_revision("0003_marketplace_and_evidence")
    assert rev_0003 is not None
    assert rev_0003.down_revision == "0002_catalog_tables"

    rev_0002 = script_dir.get_revision("0002_catalog_tables")
    assert rev_0002 is not None
    assert rev_0002.down_revision == "0001_initial_baseline"

    rev_0001 = script_dir.get_revision("0001_initial_baseline")
    assert rev_0001 is not None
    assert rev_0001.down_revision is None
