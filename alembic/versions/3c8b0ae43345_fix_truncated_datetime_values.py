"""deprecated timestamp repair revision

Revision ID: 3c8b0ae43345
Revises: b942e8c5d545
Create Date: 2026-03-18 16:22:16.940767

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "3c8b0ae43345"
down_revision: str | Sequence[str] | None = "b942e8c5d545"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
