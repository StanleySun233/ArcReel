from __future__ import annotations

import re

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from lib.db.models import File, FileLink, User
from lib.files import FileLinkSpec, FileService


class FakeStorage:
    def __init__(self) -> None:
        self.puts: list[tuple[str, bytes, str | None]] = []
        self.deletes: list[str] = []

    async def put_object(self, object_key: str, content: bytes, *, content_type: str | None = None) -> None:
        self.puts.append((object_key, content, content_type))

    async def delete_object(self, object_key: str) -> None:
        self.deletes.append(object_key)

    def signed_get_url(self, object_key: str, *, expires_in: int = 300) -> str:
        return f"https://files.example.test/{object_key}?exp={expires_in}"


@pytest.mark.asyncio
async def test_file_service_writes_object_then_file_row_and_links(async_session) -> None:
    async_session.add(User(id="usr_1", username="alice", provider="camel", provider_subject="alice"))
    await async_session.flush()
    storage = FakeStorage()
    service = FileService(async_session, storage)

    record = await service.create_file(
        content=b"hello",
        alias="cover.png",
        content_type="image/png",
        created_by_user_id="usr_1",
        links=[
            FileLinkSpec(resource_type="project", resource_id="prj_1", link_type="cover"),
            FileLinkSpec(resource_type="task", resource_id="tsk_1", link_type="result"),
            FileLinkSpec(resource_type="asset", resource_id="ast_1", link_type="image"),
            FileLinkSpec(resource_type="personal_library", resource_id="usr_1", link_type="library"),
        ],
    )

    assert record.file_id.startswith("fil_")
    assert re.fullmatch(r"[0-9a-f-]{36}\.png", storage.puts[0][0])
    assert storage.puts == [(record.object_key, b"hello", "image/png")]
    row = await async_session.get(File, record.file_id)
    assert row is not None
    assert row.object_key == record.object_key
    assert row.alias == "cover.png"
    assert row.content_type == "image/png"
    assert row.size_bytes == 5
    links = (await async_session.execute(select(FileLink).where(FileLink.file_id == record.file_id))).scalars().all()
    assert {(link.resource_type, link.resource_id, link.link_type) for link in links} == {
        ("project", "prj_1", "cover"),
        ("task", "tsk_1", "result"),
        ("asset", "ast_1", "image"),
        ("personal_library", "usr_1", "library"),
    }


@pytest.mark.asyncio
async def test_file_service_deletes_object_when_file_row_cannot_be_created(async_session) -> None:
    storage = FakeStorage()
    service = FileService(async_session, storage)

    with pytest.raises(IntegrityError):
        await service.create_file(
            content=b"orphan",
            alias="orphan.jpg",
            content_type="image/jpeg",
            created_by_user_id="missing_user",
        )

    assert storage.deletes == [storage.puts[0][0]]
