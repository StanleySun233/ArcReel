from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9a7c6d5e4f32"
down_revision: str | Sequence[str] | None = "91b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_TENANT_ID = "ten_default"


def _tenant_id_column() -> sa.Column:
    return sa.Column("tenant_id", sa.String(length=36), server_default=DEFAULT_TENANT_ID, nullable=False)


def _add_tenant(table_name: str, fk_name: str) -> None:
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.add_column(_tenant_id_column())
        batch_op.create_foreign_key(fk_name, "tenants", ["tenant_id"], ["id"], ondelete="CASCADE")
        batch_op.create_index(f"ix_{table_name}_tenant_id", ["tenant_id"], unique=False)
        batch_op.alter_column("tenant_id", server_default=None)


def upgrade() -> None:
    _add_tenant("agent_sessions", "fk_agent_sessions_tenant_id")
    _add_tenant("agent_session_event_log", "fk_agent_event_log_tenant_id")
    _add_tenant("agent_session_entries", "fk_agent_session_entries_tenant_id")
    _add_tenant("agent_session_summaries", "fk_agent_session_summaries_tenant_id")

    op.create_index(
        "idx_agent_sessions_tenant_project",
        "agent_sessions",
        ["tenant_id", "project_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_event_log_tenant_session",
        "agent_session_event_log",
        ["tenant_id", "session_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_entries_tenant_listing",
        "agent_session_entries",
        ["tenant_id", "project_key", "session_id", "mtime_ms"],
        unique=False,
    )
    op.drop_index("idx_agent_entries_listing", table_name="agent_session_entries")
    op.create_index(
        "idx_agent_entries_listing",
        "agent_session_entries",
        ["tenant_id", "project_key", "session_id", "mtime_ms"],
        unique=False,
    )
    op.drop_index("uq_agent_entries_uuid", table_name="agent_session_entries")
    op.create_index(
        "uq_agent_entries_uuid",
        "agent_session_entries",
        ["tenant_id", "project_key", "session_id", "subpath", "uuid"],
        unique=True,
        postgresql_where=sa.text("uuid IS NOT NULL"),
    )

    op.drop_index("uq_agent_event_log_client_key", table_name="agent_session_event_log")
    op.create_index(
        "uq_agent_event_log_client_key",
        "agent_session_event_log",
        ["tenant_id", "session_id", "client_key"],
        unique=True,
        postgresql_where=sa.text("client_key IS NOT NULL"),
    )
    op.drop_index("ix_agent_event_log_client_key", table_name="agent_session_event_log")
    op.create_index(
        "ix_agent_event_log_client_key",
        "agent_session_event_log",
        ["tenant_id", "client_key"],
        unique=False,
        postgresql_where=sa.text("client_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_agent_event_log_client_key", table_name="agent_session_event_log")
    op.create_index(
        "ix_agent_event_log_client_key",
        "agent_session_event_log",
        ["client_key"],
        unique=False,
        postgresql_where=sa.text("client_key IS NOT NULL"),
    )
    op.drop_index("uq_agent_event_log_client_key", table_name="agent_session_event_log")
    op.create_index(
        "uq_agent_event_log_client_key",
        "agent_session_event_log",
        ["session_id", "client_key"],
        unique=True,
        postgresql_where=sa.text("client_key IS NOT NULL"),
    )
    op.drop_index("uq_agent_entries_uuid", table_name="agent_session_entries")
    op.create_index(
        "uq_agent_entries_uuid",
        "agent_session_entries",
        ["project_key", "session_id", "subpath", "uuid"],
        unique=True,
        postgresql_where=sa.text("uuid IS NOT NULL"),
    )
    op.drop_index("idx_agent_entries_listing", table_name="agent_session_entries")
    op.create_index(
        "idx_agent_entries_listing",
        "agent_session_entries",
        ["project_key", "session_id", "mtime_ms"],
        unique=False,
    )
    op.drop_index("ix_agent_entries_tenant_listing", table_name="agent_session_entries")
    op.drop_index("ix_agent_event_log_tenant_session", table_name="agent_session_event_log")
    op.drop_index("idx_agent_sessions_tenant_project", table_name="agent_sessions")
    for table_name, fk_name in (
        ("agent_session_summaries", "fk_agent_session_summaries_tenant_id"),
        ("agent_session_entries", "fk_agent_session_entries_tenant_id"),
        ("agent_session_event_log", "fk_agent_event_log_tenant_id"),
        ("agent_sessions", "fk_agent_sessions_tenant_id"),
    ):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_index(f"ix_{table_name}_tenant_id")
            batch_op.drop_constraint(fk_name, type_="foreignkey")
            batch_op.drop_column("tenant_id")
