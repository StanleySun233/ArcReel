"""Tests for cost estimation router."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.auth import CurrentUserInfo, get_current_user
from server.routers import cost_estimation
from server.services.tenant_auth import TenantAccess


def _mock_pm(**overrides):
    mock = MagicMock()
    for key, value in overrides.items():
        setattr(mock, key, MagicMock(return_value=value))
    return mock


def _make_client(monkeypatch, mock_pm, *, rows: dict[str, str] | None = None):
    project_rows = rows or {"demo": "Demo"}

    class _Begin:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

    class _Session:
        def begin(self):
            return _Begin()

    class _SessionContext:
        async def __aenter__(self):
            return _Session()

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

    class _Repo:
        def __init__(self, _session, *, tenant_id):
            self.tenant_id = tenant_id

        async def get_by_id(self, project_id):
            name = project_rows.get(project_id)
            if name is None:
                return None
            return SimpleNamespace(id=project_id, name=name)

    async def _access(_session, _user, *, minimum_role="view", permission_cache=None):
        return TenantAccess(id="ten_test", name="Tenant", role="admin", is_owner=True, personal=True)

    async def _set_context(_session, *, user_id, tenant_id):
        return None

    monkeypatch.setattr(cost_estimation, "async_session_factory", lambda: _SessionContext())
    monkeypatch.setattr(cost_estimation, "ProjectRepository", _Repo)
    monkeypatch.setattr(cost_estimation, "require_tenant_access", _access)
    monkeypatch.setattr(cost_estimation, "set_tenant_context", _set_context)
    monkeypatch.setattr(cost_estimation, "ProjectManager", lambda _root, tenant_id=None: mock_pm)

    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: CurrentUserInfo(
        id="default",
        sub="testuser",
        role="admin",
        tenant_id="ten_test",
        tenant_role="admin",
    )
    app.include_router(cost_estimation.router, prefix="/api/v1")
    return TestClient(app)


class TestCostEstimationRouter:
    def test_project_not_found_returns_404(self, monkeypatch):
        client = _make_client(monkeypatch, _mock_pm(project_exists=False), rows={})
        with client:
            resp = client.get("/api/v1/projects/nonexistent/cost-estimate")
        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]

    def test_success_returns_correct_structure(self, monkeypatch):
        fake_result = {
            "project_name": "proj-demo",
            "models": {
                "image": {"provider": "gemini", "model": "m"},
                "video": {"provider": "gemini", "model": "m"},
            },
            "episodes": [],
            "project_totals": {"estimate": {}, "actual": {}},
        }
        mock_pm = _mock_pm(project_exists=True, load_project={"episodes": []})

        service = MagicMock()
        service.compute = AsyncMock(return_value=fake_result)
        monkeypatch.setattr(cost_estimation, "CostEstimationService", lambda _resolver, _tracker: service)

        client = _make_client(monkeypatch, mock_pm, rows={"proj-demo": "Display Name"})
        with client:
            resp = client.get("/api/v1/projects/proj-demo/cost-estimate")

        assert resp.status_code == 200
        body = resp.json()
        assert body["project_name"] == "proj-demo"
        assert "models" in body
        assert "episodes" in body
        assert "project_totals" in body
        service.compute.assert_awaited_once()
        assert service.compute.await_args.kwargs["project_name"] == "proj-demo"
        mock_pm.load_project.assert_called_once_with("proj-demo")

    def test_display_name_is_not_accepted_as_project_id(self, monkeypatch):
        service = MagicMock()
        service.compute = AsyncMock(
            return_value={
                "project_name": "proj-alpha",
                "models": {},
                "episodes": [],
                "project_totals": {"estimate": {}, "actual": {}},
            }
        )
        monkeypatch.setattr(cost_estimation, "CostEstimationService", lambda _resolver, _tracker: service)
        mock_pm = _mock_pm(project_exists=True, load_project={"episodes": []})
        client = _make_client(monkeypatch, mock_pm, rows={"proj-alpha": "duplicated-display-name"})

        with client:
            by_id = client.get("/api/v1/projects/proj-alpha/cost-estimate")
            by_name = client.get("/api/v1/projects/duplicated-display-name/cost-estimate")

        assert by_id.status_code == 200
        assert by_name.status_code == 404

    def test_no_auth_returns_401(self):
        app = FastAPI()
        app.include_router(cost_estimation.router, prefix="/api/v1")
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/api/v1/projects/demo/cost-estimate")
        assert resp.status_code == 401
