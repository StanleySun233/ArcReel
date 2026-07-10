from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lib.db.models import Project


@dataclass(frozen=True)
class ProjectRow:
    id: str
    tenant_id: str
    name: str
    created_by_user_id: str
    local_path: str
    created_at: datetime
    updated_at: datetime


class ProjectRepository:
    def __init__(self, session: AsyncSession, *, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    async def create(
        self,
        *,
        project_id: str,
        name: str,
        created_by_user_id: str,
        local_path: str,
    ) -> ProjectRow:
        row = Project(
            id=project_id,
            tenant_id=self.tenant_id,
            name=name,
            created_by_user_id=created_by_user_id,
            local_path=local_path,
        )
        self.session.add(row)
        await self.session.flush()
        return _project_row(row)

    async def get_by_name(self, name: str) -> ProjectRow | None:
        row = (
            await self.session.execute(select(Project).where(Project.tenant_id == self.tenant_id, Project.name == name))
        ).scalar_one_or_none()
        return _project_row(row) if row is not None else None

    async def list_all(self) -> list[ProjectRow]:
        rows = (
            await self.session.execute(
                select(Project).where(Project.tenant_id == self.tenant_id).order_by(Project.updated_at.desc())
            )
        ).scalars()
        return [_project_row(row) for row in rows]

    async def touch_local_path(self, name: str, local_path: str) -> ProjectRow | None:
        row = (
            await self.session.execute(select(Project).where(Project.tenant_id == self.tenant_id, Project.name == name))
        ).scalar_one_or_none()
        if row is None:
            return None
        row.local_path = local_path
        await self.session.flush()
        return _project_row(row)

    async def delete_by_name(self, name: str) -> bool:
        row = (
            await self.session.execute(select(Project).where(Project.tenant_id == self.tenant_id, Project.name == name))
        ).scalar_one_or_none()
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.flush()
        return True


def _project_row(row: Project) -> ProjectRow:
    return ProjectRow(
        id=row.id,
        tenant_id=row.tenant_id,
        name=row.name,
        created_by_user_id=row.created_by_user_id,
        local_path=row.local_path,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
