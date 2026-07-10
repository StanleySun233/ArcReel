"""宫格图路由的「未预期异常 → 通用 500 且不泄露内部细节」回归测试。

每个端点的 try 块内最早调用 get_project_manager()，把它 monkeypatch 成抛 RuntimeError
（带唯一哨兵串），即可绕过前面的 FileNotFoundError/HTTPException/ScriptEditError 分支，
落到末端的 except Exception。断言响应 500 且哨兵串不出现在响应体里——验证内部异常细节
仅落服务端日志、不泄露给客户端。
"""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.auth import CurrentUserInfo, get_current_user
from server.routers import grids
from server.services.tenant_auth import TenantAccess


def _client(monkeypatch, **patches):
    _install_route_stubs(monkeypatch)
    for name, fn in patches.items():
        monkeypatch.setattr(grids, name, fn)
    app = FastAPI()
    app.dependency_overrides[get_current_user] = _current_user
    app.include_router(grids.router, prefix="/api/v1")
    return TestClient(app)


def _install_route_stubs(monkeypatch, project_ids: set[str] | None = None):
    allowed_project_ids = project_ids or {"demo"}

    async def _require_tenant_access(*args, **kwargs):
        return TenantAccess(id="ten_test", name="Tenant", role="admin", is_owner=True, personal=True)

    async def _set_tenant_context(*args, **kwargs):
        return None

    class _Repo:
        def __init__(self, *args, **kwargs):
            pass

        async def get_by_id(self, project_id):
            if project_id not in allowed_project_ids:
                return None
            return SimpleNamespace(id=project_id, name="Demo", tenant_id="ten_test")

    monkeypatch.setattr(grids, "require_tenant_access", _require_tenant_access)
    monkeypatch.setattr(grids, "set_tenant_context", _set_tenant_context)
    monkeypatch.setattr(grids, "ProjectRepository", _Repo)


def _current_user() -> CurrentUserInfo:
    return CurrentUserInfo(
        id="default",
        sub="testuser",
        role="admin",
        tenant_id="ten_test",
        tenant_role="admin",
    )


def test_generate_grid_unexpected_error_no_leak(monkeypatch):
    # generate_grid 末端 catch-all：load_project 抛非预期异常时不泄露内部细节
    client = _client(
        monkeypatch,
        get_tenant_project_manager=lambda _tenant_id: (_ for _ in ()).throw(RuntimeError("LEAK_generate")),
    )
    with client:
        resp = client.post(
            "/api/v1/projects/demo/generate/grid/1",
            json={"script_file": "episode_1.json"},
        )
        assert resp.status_code == 500
        assert "LEAK_generate" not in resp.text


def test_list_grids_unexpected_error_no_leak(monkeypatch):
    # list_grids 末端 catch-all：get_project_path 抛非预期异常时不泄露内部细节
    client = _client(
        monkeypatch,
        get_tenant_project_manager=lambda _tenant_id: (_ for _ in ()).throw(RuntimeError("LEAK_list")),
    )
    with client:
        resp = client.get("/api/v1/projects/demo/grids")
        assert resp.status_code == 500
        assert "LEAK_list" not in resp.text


def test_get_grid_unexpected_error_no_leak(monkeypatch):
    # get_grid 末端 catch-all：get_project_path 抛非预期异常时不泄露内部细节
    client = _client(
        monkeypatch,
        get_tenant_project_manager=lambda _tenant_id: (_ for _ in ()).throw(RuntimeError("LEAK_get")),
    )
    with client:
        resp = client.get("/api/v1/projects/demo/grids/grid-123")
        assert resp.status_code == 500
        assert "LEAK_get" not in resp.text


def test_regenerate_grid_unexpected_error_no_leak(monkeypatch):
    # regenerate_grid 末端 catch-all：load_project 抛非预期异常时不泄露内部细节
    client = _client(
        monkeypatch,
        get_tenant_project_manager=lambda _tenant_id: (_ for _ in ()).throw(RuntimeError("LEAK_regen")),
    )
    with client:
        resp = client.post("/api/v1/projects/demo/grids/grid-123/regenerate")
        assert resp.status_code == 500
        assert "LEAK_regen" not in resp.text


def test_list_grids_rejects_display_name_route_key(monkeypatch):
    _install_route_stubs(monkeypatch, project_ids={"proj_1"})

    def _manager_should_not_be_used(_tenant_id):
        raise AssertionError("project display name must not resolve to a project path")

    monkeypatch.setattr(grids, "get_tenant_project_manager", _manager_should_not_be_used)

    app = FastAPI()
    app.dependency_overrides[get_current_user] = _current_user
    app.include_router(grids.router, prefix="/api/v1")
    with TestClient(app) as client:
        resp = client.get("/api/v1/projects/Demo/grids")

    assert resp.status_code == 404
