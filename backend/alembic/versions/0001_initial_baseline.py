"""initial baseline

Revision ID: 0001_initial_baseline
Revises:
Create Date: 2026-11-07 12:00:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001_initial_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Phase B1: Baseline revision establishing the migration chain.
    # Core domain entities (catalog, auth, evidence, evaluation) will be added in Phase B3.
    pass


def downgrade() -> None:
    pass
