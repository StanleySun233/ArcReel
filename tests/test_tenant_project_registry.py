from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from lib.db.models import Tenant, TenantMembership, User
from lib.db.repositories.project_repo import ProjectRepository
from lib.project_manager import ProjectManager


async def _seed_tenants(session) -> None:
    session.add(User(id="usr_1", username="alice", provider="camel", provider_subject="alice"))
    session.add(User(id="usr_2", username="bob", provider="camel", provider_subject="bob"))
    await session.flush()
    session.add(Tenant(id="ten_1", name="Tenant 1", owner_user_id="usr_1", created_by_user_id="usr_1"))
    session.add(Tenant(id="ten_2", name="Tenant 2", owner_user_id="usr_2", created_by_user_id="usr_2"))
    await session.flush()
    session.add(TenantMembership(tenant_id="ten_1", user_id="usr_1", role="admin", created_by_user_id="usr_1"))
    session.add(TenantMembership(tenant_id="ten_2", user_id="usr_2", role="admin", created_by_user_id="usr_2"))
    await session.flush()


def test_project_manager_uses_tenant_project_root(tmp_path) -> None:
    manager = ProjectManager(tmp_path, tenant_id="ten_1")
    assert manager.projects_root == tmp_path / "_tenants" / "ten_1" / "projects"

    project_dir = manager.create_project("demo")

    assert project_dir == tmp_path / "_tenants" / "ten_1" / "projects" / "demo"
    assert (project_dir / "project.json").exists()


@pytest.mark.asyncio
async def test_project_registry_allows_same_name_across_tenants(async_session) -> None:
    await _seed_tenants(async_session)
    repo_1 = ProjectRepository(async_session, tenant_id="ten_1")
    repo_2 = ProjectRepository(async_session, tenant_id="ten_2")

    row_1 = await repo_1.create(
        project_id="prj_ten_1_demo",
        name="demo",
        created_by_user_id="usr_1",
        local_path="_tenants/ten_1/projects/demo/project.json",
    )
    row_2 = await repo_2.create(
        project_id="prj_ten_2_demo",
        name="demo",
        created_by_user_id="usr_2",
        local_path="_tenants/ten_2/projects/demo/project.json",
    )

    assert row_1.name == row_2.name == "demo"
    assert row_1.tenant_id == "ten_1"
    assert row_2.tenant_id == "ten_2"
    assert [row.name for row in await repo_1.list_all()] == ["demo"]
    assert [row.name for row in await repo_2.list_all()] == ["demo"]


@pytest.mark.asyncio
async def test_project_registry_rejects_same_name_in_same_tenant(async_session) -> None:
    await _seed_tenants(async_session)
    repo = ProjectRepository(async_session, tenant_id="ten_1")
    await repo.create(
        project_id="prj_ten_1_demo",
        name="demo",
        created_by_user_id="usr_1",
        local_path="_tenants/ten_1/projects/demo/project.json",
    )

    with pytest.raises(IntegrityError):
        await repo.create(
            project_id="prj_ten_1_demo_2",
            name="demo",
            created_by_user_id="usr_1",
            local_path="_tenants/ten_1/projects/demo-2/project.json",
        )
