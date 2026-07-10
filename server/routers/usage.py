"""
API 调用统计路由

提供调用记录查询和统计摘要接口。
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from lib.db import async_session_factory
from lib.db.repositories.project_repo import ProjectRepository
from lib.db.tenant_context import set_tenant_context
from lib.providers import CallType
from lib.usage_tracker import UsageTracker
from server.auth import CurrentUser
from server.services.tenant_auth import ROLE_VIEW, require_tenant_access

router = APIRouter()

_tracker = UsageTracker()


async def _require_usage_scope(user, project_id: str | None = None):
    async with async_session_factory() as session:
        async with session.begin():
            access = await require_tenant_access(session, user, minimum_role=ROLE_VIEW)
            await set_tenant_context(session, user_id=user.id, tenant_id=access.id)
            if project_id is not None and await ProjectRepository(session, tenant_id=access.id).get_by_id(project_id) is None:
                raise HTTPException(status_code=404, detail="project_not_found")
            return access


@router.get("/usage/stats")
async def get_stats(
    _user: CurrentUser,
    project_id: str | None = Query(None, description="项目 ID（可选）"),
    provider: str | None = Query(None, description="按供应商筛选"),
    start_date: str | None = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="结束日期 (YYYY-MM-DD)"),
    group_by: str | None = Query(None, description="分组方式: provider"),
):
    access = await _require_usage_scope(_user, project_id)
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    if group_by == "provider":
        stats = await _tracker.get_stats_grouped_by_provider(
            project_name=project_id,
            provider=provider,
            start_date=start,
            end_date=end,
            tenant_id=access.id,
        )
    else:
        stats = await _tracker.get_stats(
            project_name=project_id,
            provider=provider,
            start_date=start,
            end_date=end,
            tenant_id=access.id,
        )
    return stats


@router.get("/usage/calls")
async def get_calls(
    _user: CurrentUser,
    project_id: str | None = Query(None, description="项目 ID"),
    call_type: CallType | None = Query(None, description="调用类型 (image/video/text)"),
    status: str | None = Query(None, description="状态 (success/failed)"),
    start_date: str | None = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="结束日期 (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页记录数"),
):
    access = await _require_usage_scope(_user, project_id)
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    result = await _tracker.get_calls(
        project_name=project_id,
        call_type=call_type,
        status=status,
        start_date=start,
        end_date=end,
        page=page,
        page_size=page_size,
        tenant_id=access.id,
    )
    return result


@router.get("/usage/projects")
async def get_projects_list(_user: CurrentUser):
    access = await _require_usage_scope(_user)
    projects = await _tracker.get_projects_list(tenant_id=access.id)
    return {"projects": projects}
