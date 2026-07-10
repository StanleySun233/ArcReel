from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from lib.db.repositories.file_repo import FileRepository


class StorageService(Protocol):
    async def put_object(self, object_key: str, content: bytes, *, content_type: str | None = None) -> None: ...

    async def delete_object(self, object_key: str) -> None: ...

    def signed_get_url(self, object_key: str, *, expires_in: int = 300) -> str: ...


@dataclass(frozen=True)
class FileLinkSpec:
    resource_type: str
    resource_id: str
    link_type: str


@dataclass(frozen=True)
class FileRecord:
    file_id: str
    object_key: str
    alias: str
    content_type: str | None
    size_bytes: int
    checksum: str


class FileService:
    def __init__(
        self,
        session: AsyncSession,
        storage: StorageService,
        *,
        repository: FileRepository | None = None,
    ):
        self.session = session
        self.storage = storage
        self.repository = repository or FileRepository(session)

    async def create_file(
        self,
        *,
        content: bytes,
        alias: str,
        content_type: str | None,
        created_by_user_id: str,
        links: list[FileLinkSpec] | None = None,
    ) -> FileRecord:
        object_key = _object_key(alias)
        checksum = hashlib.sha256(content).hexdigest()
        await self.storage.put_object(object_key, content, content_type=content_type)
        try:
            row = await self.repository.create_file(
                file_id=f"fil_{uuid.uuid4().hex}",
                object_key=object_key,
                alias=alias,
                content_type=content_type,
                size_bytes=len(content),
                checksum=checksum,
                created_by_user_id=created_by_user_id,
            )
            for link in links or []:
                await self.repository.add_link(
                    file_id=row.id,
                    resource_type=link.resource_type,
                    resource_id=link.resource_id,
                    link_type=link.link_type,
                    created_by_user_id=created_by_user_id,
                )
        except Exception:
            await self.storage.delete_object(object_key)
            raise
        return FileRecord(
            file_id=row.id,
            object_key=row.object_key,
            alias=row.alias,
            content_type=row.content_type,
            size_bytes=row.size_bytes or len(content),
            checksum=row.checksum or checksum,
        )

    async def signed_url_for_user(
        self,
        *,
        file_id: str,
        user_id: str,
        tenant_id: str | None,
        expires_in: int = 300,
    ) -> str | None:
        if not await self.repository.can_access_file(file_id=file_id, user_id=user_id, tenant_id=tenant_id):
            return None
        row = await self.repository.get_file(file_id)
        if row is None:
            return None
        return self.storage.signed_get_url(row.object_key, expires_in=expires_in)


def _object_key(alias: str) -> str:
    suffix = Path(alias).suffix.lower().lstrip(".") or "bin"
    return f"{uuid.uuid4()}.{suffix}"
