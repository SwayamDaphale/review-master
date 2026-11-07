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
    assert heads[0] == "0001_initial_baseline"
