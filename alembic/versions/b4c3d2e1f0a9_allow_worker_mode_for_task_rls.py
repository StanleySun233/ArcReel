"""allow worker mode for task rls

Revision ID: b4c3d2e1f0a9
Revises: 9a7c6d5e4f32
Create Date: 2026-07-25 14:05:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b4c3d2e1f0a9"
down_revision: str | Sequence[str] | None = "9a7c6d5e4f32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

QUEUE_RLS_TABLES = ("tasks", "task_events")
TENANT_POLICY = "tenant_id = current_setting('app.current_tenant_id', true)"
WORKER_POLICY = f"(current_setting('app.auth_mode', true) = 'worker' OR {TENANT_POLICY})"


def _replace_policy(table_name: str, expression: str) -> None:
    policy_name = f"{table_name}_tenant_context"
    op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table_name}")
    op.execute(f"CREATE POLICY {policy_name} ON {table_name} FOR ALL USING ({expression}) WITH CHECK ({expression})")


def upgrade() -> None:
    for table_name in QUEUE_RLS_TABLES:
        _replace_policy(table_name, WORKER_POLICY)


def downgrade() -> None:
    for table_name in QUEUE_RLS_TABLES:
        _replace_policy(table_name, TENANT_POLICY)
