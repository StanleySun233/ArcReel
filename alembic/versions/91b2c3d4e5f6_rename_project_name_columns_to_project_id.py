from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "91b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "8d7e6f5a4b3c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROJECT_SCOPED_TABLES = ("agent_sessions", "api_calls", "task_events", "tasks")


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _rename_column_if_needed(table_name: str, old_name: str, new_name: str) -> None:
    if _has_column(table_name, old_name) and not _has_column(table_name, new_name):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.alter_column(old_name, new_column_name=new_name)


def upgrade() -> None:
    for table_name in PROJECT_SCOPED_TABLES:
        _rename_column_if_needed(table_name, "project_name", "project_id")


def downgrade() -> None:
    for table_name in PROJECT_SCOPED_TABLES:
        _rename_column_if_needed(table_name, "project_id", "project_name")
