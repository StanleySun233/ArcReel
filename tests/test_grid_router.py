"""基本路由存在性测试：验证 grids router 注册了预期路径。"""

from server.routers.grids import router


def _paths() -> list[str]:
    return [path for route in router.routes if isinstance(path := getattr(route, "path", None), str)]


class TestGridRouterExists:
    def test_router_has_routes(self):
        paths = _paths()
        assert any("generate/grid" in p for p in paths)
        assert any("/grids" in p for p in paths)

    def test_router_has_generate_grid_endpoint(self):
        paths = _paths()
        assert any("generate/grid/{episode}" in p for p in paths)

    def test_router_has_list_grids_endpoint(self):
        paths = _paths()
        assert any(p.endswith("/grids") for p in paths)

    def test_router_has_get_grid_endpoint(self):
        paths = _paths()
        assert any("/grids/{grid_id}" in p for p in paths)

    def test_router_has_regenerate_endpoint(self):
        paths = _paths()
        assert any("regenerate" in p for p in paths)


class TestAdProjectRejected:
    def test_generate_grid_rejects_ad_project(self, monkeypatch):
        """广告/短片项目不开放宫格生视频：动作端点直接 400。"""
        from types import SimpleNamespace

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from server.auth import CurrentUserInfo, get_current_user
        from server.routers import grids
        from server.services.tenant_auth import TenantAccess

        class _AdPM:
            def load_project(self, name):
                return {"content_mode": "ad", "title": "Ad", "episodes": []}

        async def _require_tenant_access(*args, **kwargs):
            return TenantAccess(id="ten_test", name="Tenant", role="admin", is_owner=True, personal=True)

        async def _set_tenant_context(*args, **kwargs):
            return None

        class _Repo:
            def __init__(self, *args, **kwargs):
                pass

            async def get_by_id(self, project_id):
                return SimpleNamespace(id=project_id, name="Demo", tenant_id="ten_test")

        monkeypatch.setattr(grids, "require_tenant_access", _require_tenant_access)
        monkeypatch.setattr(grids, "set_tenant_context", _set_tenant_context)
        monkeypatch.setattr(grids, "ProjectRepository", _Repo)
        monkeypatch.setattr(grids, "get_tenant_project_manager", lambda _tenant_id: _AdPM())

        app = FastAPI()
        app.dependency_overrides[get_current_user] = lambda: CurrentUserInfo(
            id="default",
            sub="testuser",
            role="admin",
            tenant_id="ten_test",
            tenant_role="admin",
        )
        app.include_router(grids.router, prefix="/api/v1")
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/projects/demo/generate/grid/1",
                json={"script_file": "episode_1.json"},
            )
        assert resp.status_code == 400

    def test_regenerate_grid_rejects_ad_project(self, monkeypatch):
        """重生成端点同样封禁 ad:残留的历史 grid 记录不得被重新入队。"""
        from types import SimpleNamespace

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from server.auth import CurrentUserInfo, get_current_user
        from server.routers import grids
        from server.services.tenant_auth import TenantAccess

        class _AdPM:
            def load_project(self, name):
                return {"content_mode": "ad", "title": "Ad", "episodes": []}

        async def _require_tenant_access(*args, **kwargs):
            return TenantAccess(id="ten_test", name="Tenant", role="admin", is_owner=True, personal=True)

        async def _set_tenant_context(*args, **kwargs):
            return None

        class _Repo:
            def __init__(self, *args, **kwargs):
                pass

            async def get_by_id(self, project_id):
                return SimpleNamespace(id=project_id, name="Demo", tenant_id="ten_test")

        monkeypatch.setattr(grids, "require_tenant_access", _require_tenant_access)
        monkeypatch.setattr(grids, "set_tenant_context", _set_tenant_context)
        monkeypatch.setattr(grids, "ProjectRepository", _Repo)
        monkeypatch.setattr(grids, "get_tenant_project_manager", lambda _tenant_id: _AdPM())

        app = FastAPI()
        app.dependency_overrides[get_current_user] = lambda: CurrentUserInfo(
            id="default",
            sub="testuser",
            role="admin",
            tenant_id="ten_test",
            tenant_role="admin",
        )
        app.include_router(grids.router, prefix="/api/v1")
        with TestClient(app) as client:
            resp = client.post("/api/v1/projects/demo/grids/g-1/regenerate")
        assert resp.status_code == 400
