from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from lib.app_data_dir import app_data_dir
from lib.db.repositories.project_repo import ProjectRepository, ProjectRow
from lib.user_scope import tenant_projects_root


@dataclass(frozen=True)
class ProjectContext:
    tenant_id: str
    project_id: str
    project_name: str
    project_root: Path
    project_json_path: Path
    row: ProjectRow


async def resolve_project_context(session: AsyncSession, *, tenant_id: str, project_id: str) -> ProjectContext | None:
    row = await ProjectRepository(session, tenant_id=tenant_id).get_by_id(project_id)
    if row is None:
        return None
    project_root = tenant_projects_root(app_data_dir(), tenant_id) / project_id
    return ProjectContext(
        tenant_id=tenant_id,
        project_id=row.id,
        project_name=row.name,
        project_root=project_root,
        project_json_path=project_root / "project.json",
        row=row,
    )


def project_json_local_path(*, tenant_id: str, project_id: str) -> str:
    return (
        (tenant_projects_root(app_data_dir(), tenant_id) / project_id / "project.json")
        .relative_to(app_data_dir())
        .as_posix()
    )
