from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from lib.app_data_dir import _reset_for_tests
from lib.db.models import Tenant, TenantMembership, User
from lib.i18n import get_translator
from server.auth import CurrentUserInfo, get_current_user
from server.routers import projects


class _SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


async def _seed(async_session) -> None:
    async_session.add(User(id="usr_1", username="alice", provider="camel", provider_subject="alice"))
    async_session.add(User(id="usr_2", username="bob", provider="camel", provider_subject="bob"))
    await async_session.flush()
    async_session.add(Tenant(id="ten_1", name="Tenant 1", owner_user_id="usr_1", created_by_user_id="usr_1"))
    async_session.add(Tenant(id="ten_2", name="Tenant 2", owner_user_id="usr_2", created_by_user_id="usr_2"))
    await async_session.flush()
    async_session.add(TenantMembership(tenant_id="ten_1", user_id="usr_1", role="member", created_by_user_id="usr_1"))
    async_session.add(TenantMembership(tenant_id="ten_2", user_id="usr_2", role="member", created_by_user_id="usr_2"))
    await async_session.commit()


def _app(async_session, current: dict[str, CurrentUserInfo], monkeypatch) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    app.dependency_overrides[get_translator] = lambda: lambda key, **kwargs: key.format(**kwargs)
    app.include_router(projects.router, prefix="/api/v1")
    monkeypatch.setattr(projects, "async_session_factory", lambda: _SessionContext(async_session))
    return app


@pytest.mark.asyncio
async def test_project_routes_scope_same_name_by_current_tenant(async_session, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARCREEL_DATA_DIR", str(tmp_path / "data"))
    _reset_for_tests()
    await _seed(async_session)
    current = {"user": CurrentUserInfo(id="usr_1", sub="alice", tenant_id="ten_1", tenant_role="member")}
    app = _app(async_session, current, monkeypatch)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/v1/projects", json={"name": "demo", "title": "Tenant One"})
        assert first.status_code == 200, first.text

        current["user"] = CurrentUserInfo(id="usr_2", sub="bob", tenant_id="ten_2", tenant_role="member")
        second = await client.post("/api/v1/projects", json={"name": "demo", "title": "Tenant Two"})
        assert second.status_code == 200, second.text

        tenant_two_project = await client.get("/api/v1/projects/demo")
        assert tenant_two_project.status_code == 200, tenant_two_project.text
        assert tenant_two_project.json()["project"]["title"] == "Tenant Two"

        current["user"] = CurrentUserInfo(id="usr_1", sub="alice", tenant_id="ten_1", tenant_role="member")
        tenant_one_list = await client.get("/api/v1/projects")
        assert tenant_one_list.status_code == 200, tenant_one_list.text
        assert [item["name"] for item in tenant_one_list.json()["projects"]] == ["demo"]

        patch = await client.patch("/api/v1/projects/demo", json={"title": "Tenant One Updated"})
        assert patch.status_code == 200, patch.text

        current["user"] = CurrentUserInfo(id="usr_2", sub="bob", tenant_id="ten_2", tenant_role="member")
        tenant_two_after_patch = await client.get("/api/v1/projects/demo")
        assert tenant_two_after_patch.json()["project"]["title"] == "Tenant Two"

    assert (tmp_path / "data" / "_tenants" / "ten_1" / "projects" / "demo" / "project.json").exists()
    assert (tmp_path / "data" / "_tenants" / "ten_2" / "projects" / "demo" / "project.json").exists()
