from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from lib.db import get_async_session
from lib.db.models import Project, Tenant, TenantMembership, User
from lib.files import FileLinkSpec, FileService
from server.auth import CurrentUserInfo, get_current_user
from server.routers import files


class FakeStorage:
    def __init__(self) -> None:
        self.puts: list[str] = []

    async def put_object(self, object_key: str, content: bytes, *, content_type: str | None = None) -> None:
        self.puts.append(object_key)

    async def delete_object(self, object_key: str) -> None:
        pass

    def signed_get_url(self, object_key: str, *, expires_in: int = 300) -> str:
        return f"https://files.example.test/{object_key}?exp={expires_in}"


def _app(async_session, user: CurrentUserInfo, storage: FakeStorage) -> FastAPI:
    app = FastAPI()

    async def override_session():
        yield async_session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_async_session] = override_session
    app.include_router(files.router, prefix="/api/v1")
    files.get_storage_service = lambda: storage
    return app


async def _seed_member(async_session) -> None:
    async_session.add(User(id="usr_1", username="alice", provider="camel", provider_subject="alice"))
    await async_session.flush()
    async_session.add(Tenant(id="ten_1", name="Tenant", owner_user_id="usr_1", created_by_user_id="usr_1"))
    await async_session.flush()
    async_session.add(TenantMembership(tenant_id="ten_1", user_id="usr_1", role="member", created_by_user_id="usr_1"))
    await async_session.flush()


@pytest.mark.asyncio
async def test_files_upload_route_returns_file_id_without_object_key(async_session) -> None:
    await _seed_member(async_session)
    storage = FakeStorage()
    user = CurrentUserInfo(id="usr_1", sub="alice", tenant_id="ten_1", tenant_role="member")
    app = _app(async_session, user, storage)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/files",
            data={"alias": "cover.png", "purpose": "cover"},
            files={"file": ("cover.png", b"image", "image/png")},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["file_id"].startswith("fil_")
    assert body["alias"] == "cover.png"
    assert body["mime_type"] == "image/png"
    assert body["size_bytes"] == 5
    assert "object_key" not in body
    assert storage.puts


@pytest.mark.asyncio
async def test_signed_url_route_checks_current_project_access_before_signing(async_session) -> None:
    await _seed_member(async_session)
    async_session.add(
        Project(
            id="prj_1",
            tenant_id="ten_1",
            name="Demo",
            created_by_user_id="usr_1",
            local_path="ten_1/Demo/project.json",
        )
    )
    await async_session.flush()
    storage = FakeStorage()
    record = await FileService(async_session, storage).create_file(
        content=b"image",
        alias="cover.png",
        content_type="image/png",
        created_by_user_id="usr_1",
        links=[FileLinkSpec(resource_type="project", resource_id="prj_1", link_type="cover")],
    )
    user = CurrentUserInfo(id="usr_1", sub="alice", tenant_id="ten_1", tenant_role="member")
    app = _app(async_session, user, storage)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        allowed = await client.get(f"/api/v1/files/{record.file_id}/signed-url")

    assert allowed.status_code == 200, allowed.text
    assert allowed.json() == {
        "file_id": record.file_id,
        "url": f"https://files.example.test/{record.object_key}?exp=300",
        "expires_in": 300,
    }


@pytest.mark.asyncio
async def test_signed_url_route_denies_file_without_current_access(async_session) -> None:
    await _seed_member(async_session)
    storage = FakeStorage()
    record = await FileService(async_session, storage).create_file(
        content=b"image",
        alias="cover.png",
        content_type="image/png",
        created_by_user_id="usr_1",
    )
    user = CurrentUserInfo(id="usr_2", sub="bob", tenant_id="ten_2", tenant_role="member")
    app = _app(async_session, user, storage)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        denied = await client.get(f"/api/v1/files/{record.file_id}/signed-url")

    assert denied.status_code == 403
