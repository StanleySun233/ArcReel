from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lib.db.models import File, FileLink, Project, Task


@dataclass(frozen=True)
class FileRow:
    id: str
    object_key: str
    alias: str
    content_type: str | None
    size_bytes: int | None
    checksum: str | None
    created_by_user_id: str


@dataclass(frozen=True)
class FileLinkRow:
    id: int
    file_id: str
    resource_type: str
    resource_id: str
    link_type: str


class FileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_file(
        self,
        *,
        file_id: str,
        object_key: str,
        alias: str,
        content_type: str | None,
        size_bytes: int,
        checksum: str,
        created_by_user_id: str,
    ) -> FileRow:
        row = File(
            id=file_id,
            object_key=object_key,
            alias=alias,
            content_type=content_type,
            size_bytes=size_bytes,
            checksum=checksum,
            created_by_user_id=created_by_user_id,
        )
        self.session.add(row)
        await self.session.flush()
        return _file_row(row)

    async def add_link(
        self,
        *,
        file_id: str,
        resource_type: str,
        resource_id: str,
        link_type: str,
        created_by_user_id: str,
    ) -> FileLinkRow:
        row = FileLink(
            file_id=file_id,
            resource_type=resource_type,
            resource_id=resource_id,
            link_type=link_type,
            created_by_user_id=created_by_user_id,
        )
        self.session.add(row)
        await self.session.flush()
        return FileLinkRow(
            id=row.id,
            file_id=row.file_id,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            link_type=row.link_type,
        )

    async def get_file(self, file_id: str) -> FileRow | None:
        row = await self.session.get(File, file_id)
        return _file_row(row) if row is not None else None

    async def can_access_file(self, *, file_id: str, user_id: str, tenant_id: str | None) -> bool:
        file_row = await self.session.get(File, file_id)
        if file_row is None:
            return False
        personal = exists().where(
            FileLink.file_id == file_id,
            FileLink.resource_type == "personal_library",
            FileLink.resource_id == user_id,
        )
        if tenant_id is None:
            result = await self.session.execute(select(personal))
            return bool(result.scalar())
        project = exists().where(
            FileLink.file_id == file_id,
            FileLink.resource_type == "project",
            or_(Project.id == FileLink.resource_id, Project.name == FileLink.resource_id),
            Project.tenant_id == tenant_id,
        )
        task = exists().where(
            FileLink.file_id == file_id,
            FileLink.resource_type == "task",
            Task.task_id == FileLink.resource_id,
            Task.tenant_id == tenant_id,
        )
        tenant_library = exists().where(
            FileLink.file_id == file_id,
            FileLink.resource_type == "tenant_library",
            FileLink.resource_id == tenant_id,
        )
        result = await self.session.execute(select(personal | project | task | tenant_library))
        return bool(result.scalar())


def _file_row(row: File) -> FileRow:
    return FileRow(
        id=row.id,
        object_key=row.object_key,
        alias=row.alias,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        checksum=row.checksum,
        created_by_user_id=row.created_by_user_id,
    )
