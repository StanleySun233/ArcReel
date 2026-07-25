from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f4a2c8d9e012"
down_revision: str | Sequence[str] | None = "d1b2c3a4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_USER_ID = "default"
DEFAULT_TENANT_ID = "ten_default"
TENANT_RLS_TABLES = (
    "projects",
    "tasks",
    "task_events",
    "api_calls",
    "api_keys",
    "provider_config",
    "system_setting",
    "provider_credential",
    "custom_provider",
    "custom_provider_model",
    "agent_anthropic_credentials",
)
TENANT_COLUMN_TABLES = (
    ("tasks", "fk_tasks_tenant_id"),
    ("task_events", "fk_task_events_tenant_id"),
    ("api_calls", "fk_api_calls_tenant_id"),
    ("api_keys", "fk_api_keys_tenant_id"),
    ("provider_config", "fk_provider_config_tenant_id"),
    ("system_setting", "fk_system_setting_tenant_id"),
    ("provider_credential", "fk_provider_credential_tenant_id"),
    ("custom_provider", "fk_custom_provider_tenant_id"),
    ("custom_provider_model", "fk_custom_provider_model_tenant_id"),
    ("agent_anthropic_credentials", "fk_agent_credential_tenant_id"),
)


def _tenant_id_column() -> sa.Column:
    return sa.Column("tenant_id", sa.String(length=36), server_default=DEFAULT_TENANT_ID, nullable=False)


def _add_tenant_column(table_name: str, fk_name: str) -> None:
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.add_column(_tenant_id_column())
        batch_op.create_foreign_key(fk_name, "tenants", ["tenant_id"], ["id"], ondelete="CASCADE")
        batch_op.create_index(f"ix_{table_name}_tenant_id", ["tenant_id"], unique=False)
        batch_op.alter_column("tenant_id", server_default=None)


def _enable_tenant_rls(table_name: str) -> None:
    policy_name = f"{table_name}_tenant_context"
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {policy_name} ON {table_name} "
        "FOR ALL "
        "USING (tenant_id = current_setting('app.current_tenant_id', true)) "
        "WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true))"
    )


def _disable_tenant_rls(table_name: str) -> None:
    policy_name = f"{table_name}_tenant_context"
    op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table_name}")
    op.execute(f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("provider", sa.String(length=32), server_default="local", nullable=False))
        batch_op.add_column(sa.Column("provider_subject", sa.String(length=200), nullable=True))

    op.execute(
        "UPDATE users SET "
        "provider = CASE WHEN id LIKE 'camel:%' THEN 'camel' ELSE 'local' END, "
        "provider_subject = CASE WHEN id LIKE 'camel:%' THEN substring(id from 7) ELSE id END"
    )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("provider_subject", nullable=False)
        batch_op.alter_column("provider", server_default="camel")

    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_key")
    op.create_unique_constraint("uq_users_provider_subject", "users", ["provider", "provider_subject"])

    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("owner_user_id", sa.String(), nullable=False),
        sa.Column("personal_for_user_id", sa.String(), nullable=True),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["personal_for_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("personal_for_user_id", name="uq_tenants_personal_for_user"),
    )
    op.create_index("ix_tenants_owner_user_id", "tenants", ["owner_user_id"], unique=False)
    op.create_index("ix_tenants_created_by_user_id", "tenants", ["created_by_user_id"], unique=False)

    op.create_table(
        "tenant_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'member', 'view')", name="ck_tenant_memberships_role"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_tenant_memberships_tenant_user"),
    )
    op.create_index("ix_tenant_memberships_user_id", "tenant_memberships", ["user_id"], unique=False)
    op.create_index("ix_tenant_memberships_tenant_role", "tenant_memberships", ["tenant_id", "role"], unique=False)

    op.execute(
        "INSERT INTO tenants "
        "(id, name, owner_user_id, personal_for_user_id, created_by_user_id, created_at, updated_at) "
        f"VALUES ('{DEFAULT_TENANT_ID}', 'Default Personal Space', '{DEFAULT_USER_ID}', '{DEFAULT_USER_ID}', "
        f"'{DEFAULT_USER_ID}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
        "ON CONFLICT (id) DO NOTHING"
    )
    op.execute(
        "INSERT INTO tenant_memberships (tenant_id, user_id, role, created_by_user_id, created_at, updated_at) "
        f"VALUES ('{DEFAULT_TENANT_ID}', '{DEFAULT_USER_ID}', 'admin', '{DEFAULT_USER_ID}', "
        "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
        "ON CONFLICT (tenant_id, user_id) DO NOTHING"
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("local_path", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_projects_tenant_name"),
    )
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"], unique=False)
    op.create_index("ix_projects_tenant_updated", "projects", ["tenant_id", "updated_at"], unique=False)
    op.create_index("ix_projects_created_by_user_id", "projects", ["created_by_user_id"], unique=False)

    op.create_table(
        "files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("alias", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=200), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key", name="uq_files_object_key"),
    )
    op.create_index("ix_files_created_by_user_id", "files", ["created_by_user_id"], unique=False)

    op.create_table(
        "file_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.String(length=36), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("link_type", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_id", "resource_type", "resource_id", "link_type", name="uq_file_links_resource"),
    )
    op.create_index("ix_file_links_file_id", "file_links", ["file_id"], unique=False)
    op.create_index("ix_file_links_resource", "file_links", ["resource_type", "resource_id"], unique=False)

    op.create_table(
        "asset_library_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("library_scope", sa.String(length=16), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("asset_id", sa.String(length=36), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("snapshot_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("library_scope IN ('tenant', 'personal')", name="ck_asset_library_bindings_scope"),
        sa.CheckConstraint(
            "(library_scope = 'tenant' AND tenant_id IS NOT NULL AND user_id IS NULL) "
            "OR (library_scope = 'personal' AND user_id IS NOT NULL AND tenant_id IS NULL)",
            name="ck_asset_library_bindings_owner",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["asset_library_bindings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asset_library_bindings_parent", "asset_library_bindings", ["parent_id"], unique=False)
    op.create_index("ix_asset_library_bindings_tenant", "asset_library_bindings", ["tenant_id"], unique=False)
    op.create_index("ix_asset_library_bindings_user", "asset_library_bindings", ["user_id"], unique=False)
    op.create_index(
        "uq_asset_library_binding_tenant",
        "asset_library_bindings",
        ["tenant_id", "asset_id"],
        unique=True,
        postgresql_where=sa.text("library_scope = 'tenant' AND tenant_id IS NOT NULL"),
    )
    op.create_index(
        "uq_asset_library_binding_personal",
        "asset_library_bindings",
        ["user_id", "asset_id"],
        unique=True,
        postgresql_where=sa.text("library_scope = 'personal' AND user_id IS NOT NULL"),
    )

    for table_name, fk_name in TENANT_COLUMN_TABLES:
        _add_tenant_column(table_name, fk_name)

    op.drop_index("idx_tasks_dedupe_active", table_name="tasks")
    op.create_index("idx_tasks_tenant_status_queued_at", "tasks", ["tenant_id", "status", "queued_at"], unique=False)
    op.create_index(
        "idx_tasks_tenant_project_updated_at", "tasks", ["tenant_id", "project_id", "updated_at"], unique=False
    )
    op.create_index(
        "idx_tasks_dedupe_active",
        "tasks",
        ["tenant_id", "project_id", "task_type", "resource_id", sa.text("COALESCE(script_file, '')")],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running', 'cancelling')"),
    )
    op.create_index("idx_task_events_tenant_project_id", "task_events", ["tenant_id", "project_id", "id"], unique=False)
    op.create_index("idx_api_calls_tenant_project_id", "api_calls", ["tenant_id", "project_id"], unique=False)
    op.create_index("idx_api_calls_tenant_started_at", "api_calls", ["tenant_id", "started_at"], unique=False)

    op.execute("ALTER TABLE api_keys DROP CONSTRAINT IF EXISTS api_keys_name_key")
    op.create_unique_constraint("uq_api_keys_tenant_name", "api_keys", ["tenant_id", "name"])

    op.drop_constraint("uq_provider_config_user_provider_key", "provider_config", type_="unique")
    op.create_unique_constraint(
        "uq_provider_config_tenant_provider_key", "provider_config", ["tenant_id", "provider", "key"]
    )
    op.create_index("ix_provider_config_tenant_provider", "provider_config", ["tenant_id", "provider"], unique=False)

    op.drop_constraint("uq_system_setting_user_key", "system_setting", type_="unique")
    op.create_unique_constraint("uq_system_setting_tenant_key", "system_setting", ["tenant_id", "key"])

    op.drop_index("uq_provider_credential_one_active", table_name="provider_credential")
    op.create_index(
        "ix_provider_credential_tenant_provider",
        "provider_credential",
        ["tenant_id", "provider"],
        unique=False,
    )
    op.create_index(
        "uq_provider_credential_one_active",
        "provider_credential",
        ["tenant_id", "provider"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.drop_constraint("uq_custom_provider_model", "custom_provider_model", type_="unique")
    op.create_index("ix_custom_provider_model_tenant", "custom_provider_model", ["tenant_id"], unique=False)
    op.create_unique_constraint(
        "uq_custom_provider_model_tenant", "custom_provider_model", ["tenant_id", "provider_id", "model_id"]
    )

    op.drop_index("uq_agent_credential_one_active_per_user", table_name="agent_anthropic_credentials")
    op.create_index("ix_agent_credential_tenant", "agent_anthropic_credentials", ["tenant_id"], unique=False)
    op.create_index(
        "uq_agent_credential_one_active_per_tenant",
        "agent_anthropic_credentials",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.execute("ALTER TABLE assets DROP CONSTRAINT IF EXISTS uq_asset_type_name")
    op.create_index("ix_asset_type_name", "assets", ["type", "name"], unique=False)

    for table_name in TENANT_RLS_TABLES:
        _enable_tenant_rls(table_name)

    op.execute("ALTER TABLE asset_library_bindings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE asset_library_bindings FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY asset_library_bindings_context ON asset_library_bindings FOR ALL "
        "USING ("
        "(library_scope = 'tenant' AND tenant_id = current_setting('app.current_tenant_id', true)) OR "
        "(library_scope = 'personal' AND user_id = current_setting('app.current_user_id', true))"
        ") WITH CHECK ("
        "(library_scope = 'tenant' AND tenant_id = current_setting('app.current_tenant_id', true)) OR "
        "(library_scope = 'personal' AND user_id = current_setting('app.current_user_id', true))"
        ")"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS asset_library_bindings_context ON asset_library_bindings")
    op.execute("ALTER TABLE asset_library_bindings NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE asset_library_bindings DISABLE ROW LEVEL SECURITY")
    for table_name in reversed(TENANT_RLS_TABLES):
        _disable_tenant_rls(table_name)

    op.drop_index("ix_asset_type_name", table_name="assets")
    op.create_unique_constraint("uq_asset_type_name", "assets", ["type", "name"])

    op.drop_index("uq_agent_credential_one_active_per_tenant", table_name="agent_anthropic_credentials")
    op.drop_index("ix_agent_credential_tenant", table_name="agent_anthropic_credentials")
    op.create_index(
        "uq_agent_credential_one_active_per_user",
        "agent_anthropic_credentials",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.drop_constraint("uq_custom_provider_model_tenant", "custom_provider_model", type_="unique")
    op.drop_index("ix_custom_provider_model_tenant", table_name="custom_provider_model")
    op.create_unique_constraint("uq_custom_provider_model", "custom_provider_model", ["provider_id", "model_id"])

    op.drop_index("uq_provider_credential_one_active", table_name="provider_credential")
    op.drop_index("ix_provider_credential_tenant_provider", table_name="provider_credential")
    op.create_index(
        "uq_provider_credential_one_active",
        "provider_credential",
        ["user_id", "provider"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.drop_constraint("uq_system_setting_tenant_key", "system_setting", type_="unique")
    op.create_unique_constraint("uq_system_setting_user_key", "system_setting", ["user_id", "key"])

    op.drop_index("ix_provider_config_tenant_provider", table_name="provider_config")
    op.drop_constraint("uq_provider_config_tenant_provider_key", "provider_config", type_="unique")
    op.create_unique_constraint(
        "uq_provider_config_user_provider_key", "provider_config", ["user_id", "provider", "key"]
    )

    op.drop_constraint("uq_api_keys_tenant_name", "api_keys", type_="unique")
    op.create_unique_constraint("api_keys_name_key", "api_keys", ["name"])

    op.drop_index("idx_api_calls_tenant_started_at", table_name="api_calls")
    op.drop_index("idx_api_calls_tenant_project_id", table_name="api_calls")
    op.drop_index("idx_task_events_tenant_project_id", table_name="task_events")
    op.drop_index("idx_tasks_dedupe_active", table_name="tasks")
    op.drop_index("idx_tasks_tenant_project_updated_at", table_name="tasks")
    op.drop_index("idx_tasks_tenant_status_queued_at", table_name="tasks")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'tasks' AND column_name = 'project_id'
            ) THEN
                CREATE UNIQUE INDEX idx_tasks_dedupe_active
                ON tasks (project_id, task_type, resource_id, COALESCE(script_file, ''))
                WHERE status IN ('queued', 'running', 'cancelling');
            ELSIF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'tasks' AND column_name = 'project_name'
            ) THEN
                CREATE UNIQUE INDEX idx_tasks_dedupe_active
                ON tasks (project_name, task_type, resource_id, COALESCE(script_file, ''))
                WHERE status IN ('queued', 'running', 'cancelling');
            END IF;
        END $$;
        """
    )

    for table_name, fk_name in reversed(TENANT_COLUMN_TABLES):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_index(f"ix_{table_name}_tenant_id")
            batch_op.drop_constraint(fk_name, type_="foreignkey")
            batch_op.drop_column("tenant_id")

    op.drop_table("asset_library_bindings")
    op.drop_table("file_links")
    op.drop_table("files")
    op.drop_table("projects")
    op.drop_table("tenant_memberships")
    op.drop_table("tenants")

    op.drop_constraint("uq_users_provider_subject", "users", type_="unique")
    op.create_unique_constraint("users_username_key", "users", ["username"])
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("provider_subject")
        batch_op.drop_column("provider")
