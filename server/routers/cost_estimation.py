"""费用估算 API 路由。"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from lib.app_data_dir import app_data_dir
from lib.config.resolver import ConfigResolver
from lib.db import async_session_factory
from lib.db.repositories.project_repo import ProjectRepository
from lib.db.tenant_context import set_tenant_context
from lib.i18n import Translator
from lib.project_manager import ProjectManager
from lib.usage_tracker import UsageTracker
from server.auth import CurrentUser
from server.services.cost_estimation import CostEstimationService
from server.services.tenant_auth import ROLE_VIEW, require_tenant_access

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/projects/{project_id}/cost-estimate")
async def get_cost_estimate(project_id: str, _user: CurrentUser, _t: Translator):
    """获取项目费用估算（预估 + 实际）。"""
    async with async_session_factory() as session:
        async with session.begin():
            access = await require_tenant_access(session, _user, minimum_role=ROLE_VIEW)
            await set_tenant_context(session, user_id=_user.id, tenant_id=access.id)
            if await ProjectRepository(session, tenant_id=access.id).get_by_id(project_id) is None:
                raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))
    manager = ProjectManager(app_data_dir(), tenant_id=access.id)

    def _sync():
        if not manager.project_exists(project_id):
            raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))

        try:
            project_data = manager.load_project(project_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))

        # 加载所有剧本
        scripts: dict[str, dict] = {}
        for ep in project_data.get("episodes", []):
            script_file = ep.get("script_file", "")
            if script_file:
                try:
                    scripts[script_file] = manager.load_script(project_id, script_file)
                except FileNotFoundError:
                    logger.debug("剧本文件不存在，跳过: %s/%s", project_id, script_file)

        return project_data, scripts

    project_data, scripts = await asyncio.to_thread(_sync)

    resolver = ConfigResolver(async_session_factory)
    tracker = UsageTracker(session_factory=async_session_factory)
    service = CostEstimationService(resolver, tracker)

    try:
        return await service.compute(project_data, scripts, project_name=project_id)
    except Exception:
        logger.exception("费用估算失败")
        raise HTTPException(status_code=500, detail=_t("cost_estimation_failed"))
