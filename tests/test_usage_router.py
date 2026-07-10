from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.auth import CurrentUserInfo, get_current_user
from server.routers import usage
from server.services.tenant_auth import TenantAccess


class _FakeTracker:
    def __init__(self):
        self.calls = []

    async def get_stats(self, **kwargs):
        self.calls.append(("stats", kwargs))
        return {"total_cost": 1.2, "image_count": 1, "video_count": 2, "failed_count": 0, "total_count": 3}

    async def get_calls(self, **kwargs):
        self.calls.append(("calls", kwargs))
        return {"items": [{"id": 1}], "total": 1, "page": kwargs["page"], "page_size": kwargs["page_size"]}

    async def get_projects_list(self, **kwargs):
        self.calls.append(("projects", kwargs))
        return ["demo", "demo2"]


def _client(monkeypatch):
    tracker = _FakeTracker()
    monkeypatch.setattr(usage, "_tracker", tracker)

    async def _fake_access(*args, **kwargs):
        return TenantAccess(id="ten_test", name="Tenant", role="admin", is_owner=True, personal=True)

    async def _fake_set_context(*args, **kwargs):
        return None

    class _ProjectRepo:
        def __init__(self, *args, **kwargs):
            pass

        async def get_by_id(self, project_id):
            if project_id != "proj_1":
                return None
            return SimpleNamespace(id=project_id, name="Demo", tenant_id="ten_test")

    monkeypatch.setattr(usage, "require_tenant_access", _fake_access)
    monkeypatch.setattr(usage, "set_tenant_context", _fake_set_context)
    monkeypatch.setattr(usage, "ProjectRepository", _ProjectRepo)

    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: CurrentUserInfo(
        id="default",
        sub="testuser",
        role="admin",
        tenant_id="ten_test",
        tenant_role="admin",
    )
    app.include_router(usage.router, prefix="/api/v1")
    return TestClient(app), tracker


class TestUsageRouter:
    def test_usage_endpoints(self, monkeypatch):
        client, tracker = _client(monkeypatch)
        with client:
            stats = client.get("/api/v1/usage/stats?project_id=proj_1&start_date=2026-02-01&end_date=2026-02-10")
            assert stats.status_code == 200
            assert stats.json()["total_count"] == 3
            assert tracker.calls[-1][1]["project_name"] == "proj_1"
            assert tracker.calls[-1][1]["tenant_id"] == "ten_test"

            calls = client.get("/api/v1/usage/calls?page=2&page_size=10")
            assert calls.status_code == 200
            assert calls.json()["page"] == 2
            assert calls.json()["page_size"] == 10
            assert tracker.calls[-1][1]["tenant_id"] == "ten_test"

            projects = client.get("/api/v1/usage/projects")
            assert projects.status_code == 200
            assert projects.json()["projects"] == ["demo", "demo2"]
            assert tracker.calls[-1][1]["tenant_id"] == "ten_test"

    def test_usage_rejects_display_name_route_key(self, monkeypatch):
        client, _tracker = _client(monkeypatch)
        with client:
            resp = client.get("/api/v1/usage/stats?project_id=Demo")
        assert resp.status_code == 404
