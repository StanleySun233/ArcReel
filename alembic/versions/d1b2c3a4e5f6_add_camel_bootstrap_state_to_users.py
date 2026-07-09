"""add camel bootstrap state to users

Revision ID: d1b2c3a4e5f6
Revises: c0a9d4e5f6b7
Create Date: 2026-07-09 00:00:00.000001

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1b2c3a4e5f6"
down_revision: str | Sequence[str] | None = "c0a9d4e5f6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("camel_provider_bootstrap_completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("camel_provider_bootstrap_completed_at")
