"""add asset image file id

Revision ID: 8d7e6f5a4b3c
Revises: 7c1d2e3f4a5b
Create Date: 2026-07-10 21:25:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8d7e6f5a4b3c"
down_revision: str | Sequence[str] | None = "7c1d2e3f4a5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("assets") as batch_op:
        batch_op.add_column(sa.Column("image_file_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_assets_image_file_id_files",
            "files",
            ["image_file_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("assets") as batch_op:
        batch_op.drop_constraint("fk_assets_image_file_id_files", type_="foreignkey")
        batch_op.drop_column("image_file_id")
