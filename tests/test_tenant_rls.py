from alembic import command

from tests.alembic_pg import AlembicPostgresDb, alembic_pg  # noqa: F401


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
        "'ten_a/project_a/project.json', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )
    alembic_pg.execute_as_rls_role_with_settings(
        {"app.current_tenant_id": "ten_b", "app.current_user_id": "camel:u2"},
        "INSERT INTO projects (id, tenant_id, name, created_by_user_id, local_path, created_at, updated_at) VALUES "
        "('proj_b', 'ten_b', 'Project B', 'camel:u2', "
        "'ten_b/project_b/project.json', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
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
