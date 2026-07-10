"""场景管理路由（CRUD 由 _asset_router_factory 统一生成）。"""

from lib.app_data_dir import app_data_dir
from lib.project_manager import ProjectManager
from server.routers._asset_router_factory import build_asset_router

pm = ProjectManager(app_data_dir())


def get_project_manager(tenant_id: str | None = None) -> ProjectManager:
    return ProjectManager(app_data_dir(), tenant_id=tenant_id) if tenant_id else pm


# late-binding 必需：测试通过 monkeypatch.setattr(scenes, "get_project_manager", ...) 替换模块属性
router = build_asset_router(
    asset_type="scene",
    pm_getter=lambda tenant_id=None: get_project_manager(tenant_id) if tenant_id else get_project_manager(),
)
