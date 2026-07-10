from __future__ import annotations

from io import BytesIO

import httpx
import pytest
from fastapi import FastAPI
from PIL import Image

from lib.db import get_async_session
from lib.db.models import Tenant, TenantMembership, User
from lib.project_manager import ProjectManager
from server.auth import CurrentUserInfo, get_current_user
from server.routers import shot_uploads
from server.services import generation_tasks, upload_finalize


class FakeStorage:
    def __init__(self) -> None:
        self.puts: dict[str, bytes] = {}

    async def put_object(self, object_key: str, content: bytes, *, content_type: str | None = None) -> None:
        self.puts[object_key] = content

    async def get_object(self, object_key: str) -> bytes:
        return self.puts[object_key]

    async def delete_object(self, object_key: str) -> None:
        self.puts.pop(object_key, None)

    def signed_get_url(self, object_key: str, *, expires_in: int = 300) -> str:
        return f"https://files.example.test/{object_key}?exp={expires_in}"


def _img_bytes() -> bytes:
    image = Image.new("RGB", (8, 8), (255, 0, 0))
    buf = BytesIO()
    image.save(buf, format="JPEG")
    return buf.getvalue()


async def _seed_member(async_session) -> None:
    async_session.add(User(id="usr_1", username="alice", provider="camel", provider_subject="alice"))
    await async_session.flush()
    async_session.add(Tenant(id="ten_1", name="Tenant", owner_user_id="usr_1", created_by_user_id="usr_1"))
    await async_session.flush()
    async_session.add(TenantMembership(tenant_id="ten_1", user_id="usr_1", role="member", created_by_user_id="usr_1"))
    await async_session.flush()


def _seed_project(tmp_path) -> ProjectManager:
    pm = ProjectManager(tmp_path / "projects")
    pm.create_project("demo")
    pm.create_project_metadata("demo", "Demo", "Anime", "narration")
    pm.save_script(
        "demo",
        {
            "episode": 1,
            "title": "E1",
            "content_mode": "narration",
            "segments": [
                {
                    "segment_id": "E1S01",
                    "novel_text": "t",
                    "duration_seconds": 5,
                    "generated_assets": {"status": "pending"},
                }
            ],
        },
        "episode_1.json",
        validate=False,
    )
    return pm


@pytest.mark.asyncio
async def test_shot_storyboard_upload_returns_file_id_without_local_path(async_session, tmp_path) -> None:
    await _seed_member(async_session)
    pm = _seed_project(tmp_path)
    shot_uploads.get_project_manager = lambda: pm
    upload_finalize.get_project_manager = lambda: pm
    generation_tasks.get_project_manager = lambda: pm
    storage = FakeStorage()
    shot_uploads.get_storage_service = lambda: storage
    app = FastAPI()

    async def override_session():
        yield async_session

    app.dependency_overrides[get_current_user] = lambda: CurrentUserInfo(
        id="usr_1",
        sub="alice",
        tenant_id="ten_1",
        tenant_role="member",
    )
    app.dependency_overrides[get_async_session] = override_session
    app.include_router(shot_uploads.router, prefix="/api/v1")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/projects/demo/shots/E1S01/upload/storyboard?script_file=episode_1.json",
            files={"file": ("board.jpg", _img_bytes(), "image/jpeg")},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["file_id"].startswith("fil_")
    assert body["version"] == 1
    assert "path" not in body
    assert storage.puts
