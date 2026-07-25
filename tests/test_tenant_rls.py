from alembic import command
from tests.alembic_pg import AlembicPostgresDb

pytest_plugins = ["tests.alembic_pg"]


def test_projects_rls_denies_missing_context_and_filters_by_tenant(alembic_pg: AlembicPostgresDb):
    command.upgrade(alembic_pg.cfg, "head")
    alembic_pg.grant_rls_role()

    alembic_pg.execute(
        "INSERT INTO users "
        "(id, username, provider, provider_subject, role, is_active, created_at, updated_at) VALUES "
        "('camel:u1', 'user1', 'camel', 'u1', 'user', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), "
        "('camel:u2', 'user2', 'camel', 'u2', 'user', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )
    alembic_pg.execute(
        "INSERT INTO tenants (id, name, owner_user_id, created_by_user_id, created_at, updated_at) VALUES "
        "('ten_a', 'Tenant A', 'camel:u1', 'camel:u1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), "
        "('ten_b', 'Tenant B', 'camel:u2', 'camel:u2', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )
    alembic_pg.execute(
        "INSERT INTO tenant_memberships (tenant_id, user_id, role, created_by_user_id, created_at, updated_at) VALUES "
        "('ten_a', 'camel:u1', 'admin', 'camel:u1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), "
        "('ten_b', 'camel:u2', 'admin', 'camel:u2', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )
    alembic_pg.execute_as_rls_role_with_settings(
        {"app.current_tenant_id": "ten_a", "app.current_user_id": "camel:u1"},
        "INSERT INTO projects (id, tenant_id, name, created_by_user_id, local_path, created_at, updated_at) VALUES "
        "('proj_a', 'ten_a', 'Project A', 'camel:u1', "
        "'ten_a/project_a/project.json', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    )
    alembic_pg.execute_as_rls_role_with_settings(
        {"app.current_tenant_id": "ten_b", "app.current_user_id": "camel:u2"},
        "INSERT INTO projects (id, tenant_id, name, created_by_user_id, local_path, created_at, updated_at) VALUES "
        "('proj_b', 'ten_b', 'Project B', 'camel:u2', "
        "'ten_b/project_b/project.json', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    )

    assert alembic_pg.fetchall_as_rls_role("SELECT name FROM projects ORDER BY name") == []

    rows = alembic_pg.fetchall_as_rls_role_with_settings(
        {"app.current_tenant_id": "ten_a", "app.current_user_id": "camel:u1"},
        "SELECT name FROM projects ORDER BY name",
    )
    assert [row.name for row in rows] == ["Project A"]

    rows = alembic_pg.fetchall_as_rls_role_with_settings(
        {"app.current_tenant_id": "ten_b", "app.current_user_id": "camel:u2"},
        "SELECT name FROM projects ORDER BY name",
    )
    assert [row.name for row in rows] == ["Project B"]


def test_queue_rls_allows_explicit_worker_mode_without_tenant_context(alembic_pg: AlembicPostgresDb):
    command.upgrade(alembic_pg.cfg, "head")
    alembic_pg.grant_rls_role()

    alembic_pg.execute(
        "INSERT INTO users "
        "(id, username, provider, provider_subject, role, is_active, created_at, updated_at) VALUES "
        "('camel:u1', 'user1', 'camel', 'u1', 'user', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), "
        "('camel:u2', 'user2', 'camel', 'u2', 'user', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )
    alembic_pg.execute(
        "INSERT INTO tenants (id, name, owner_user_id, created_by_user_id, created_at, updated_at) VALUES "
        "('ten_a', 'Tenant A', 'camel:u1', 'camel:u1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), "
        "('ten_b', 'Tenant B', 'camel:u2', 'camel:u2', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )
    alembic_pg.execute(
        "INSERT INTO tasks "
        "(task_id, tenant_id, user_id, project_id, task_type, media_type, resource_id, status, source, "
        "queued_at, updated_at) VALUES "
        "('task_a', 'ten_a', 'camel:u1', 'proj_a', 'storyboard', 'image', 'E1S01', 'queued', 'webui', "
        "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), "
        "('task_b', 'ten_b', 'camel:u2', 'proj_b', 'storyboard', 'image', 'E1S01', 'queued', 'webui', "
        "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )

    assert alembic_pg.fetchall_as_rls_role("SELECT task_id FROM tasks ORDER BY task_id") == []

    rows = alembic_pg.fetchall_as_rls_role_with_settings(
        {"app.auth_mode": "worker"},
        "SELECT task_id FROM tasks ORDER BY task_id",
    )
    assert [row.task_id for row in rows] == ["task_a", "task_b"]

    alembic_pg.execute_as_rls_role_with_settings(
        {"app.auth_mode": "worker"},
        "UPDATE tasks SET status = 'running' WHERE task_id = 'task_b'",
    )
    status = alembic_pg.fetchall("SELECT status FROM tasks WHERE task_id = 'task_b'")[0].status
    assert status == "running"

    alembic_pg.execute_as_rls_role_with_settings(
        {"app.auth_mode": "worker"},
        "INSERT INTO task_events (tenant_id, task_id, project_id, event_type, status, created_at) VALUES "
        "('ten_b', 'task_b', 'proj_b', 'running', 'running', CURRENT_TIMESTAMP)",
    )
    assert alembic_pg.fetchall("SELECT event_type FROM task_events WHERE task_id = 'task_b'")[0].event_type == "running"
