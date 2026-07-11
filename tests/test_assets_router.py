from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from lib.db.models import Asset, AssetLibraryBinding, File, FileLink, Tenant, TenantMembership, User
from server.auth import CurrentUserInfo, get_current_user
from server.routers import assets
from tests.pg_utils import create_pg_test_engine_with_cleanup


@pytest.fixture
async def assets_env(monkeypatch):
    engine = await create_pg_test_engine_with_cleanup()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(assets, "async_session_factory", factory)

    async with factory() as session:
        session.add_all(
            [
                User(id="usr_1", username="alice", provider="camel", provider_subject="alice"),
                User(id="usr_2", username="bob", provider="camel", provider_subject="bob"),
            ]
        )
        await session.flush()
        session.add(Tenant(id="ten_1", name="Tenant", owner_user_id="usr_1", created_by_user_id="usr_1"))
        await session.flush()
        session.add_all(
            [
                TenantMembership(tenant_id="ten_1", user_id="usr_1", role="member", created_by_user_id="usr_1"),
                TenantMembership(tenant_id="ten_1", user_id="usr_2", role="view", created_by_user_id="usr_1"),
                File(
                    id="fil_1",
                    object_key="one.png",
                    alias="one.png",
                    content_type="image/png",
                    size_bytes=3,
                    checksum="sum",
                    created_by_user_id="usr_1",
                ),
                FileLink(
                    file_id="fil_1",
                    resource_type="tenant_library",
                    resource_id="ten_1",
                    link_type="library",
                    created_by_user_id="usr_1",
                ),
            ]
        )
        await session.commit()

    app = FastAPI()
    user = CurrentUserInfo(id="usr_1", sub="alice", tenant_id="ten_1", tenant_role="member")
    app.dependency_overrides[get_current_user] = lambda: user
    app.include_router(assets.router, prefix="/api/v1")
    try:
        yield app, factory
    finally:
        await engine.dispose()


def _client(app: FastAPI):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_create_tenant_asset_uses_file_id_and_binding(assets_env) -> None:
    app, factory = assets_env
    async with _client(app) as client:
        response = await client.post(
            "/api/v1/assets",
            json={
                "library": "tenant",
                "type": "character",
                "name": "Hero",
                "description": "desc",
                "image_file_id": "fil_1",
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()["asset"]
    assert body["id"].startswith("ab_")
    assert body["image_file_id"] == "fil_1"
    assert body["library"] == "tenant"

    async with factory() as session:
        assert (await session.get(AssetLibraryBinding, int(body["id"][3:]))) is not None


@pytest.mark.asyncio
async def test_import_creates_snapshot_binding_without_copying_file(assets_env) -> None:
    app, factory = assets_env
    async with _client(app) as client:
        source = (
            await client.post(
                "/api/v1/assets",
                json={"library": "tenant", "type": "scene", "name": "Temple", "image_file_id": "fil_1"},
            )
        ).json()["asset"]
        imported = await client.post(
            "/api/v1/assets/import",
            json={"source_binding_id": source["id"], "target_library": "personal"},
        )

    assert imported.status_code == 200, imported.text
    body = imported.json()["asset"]
    assert body["asset_id"] != source["asset_id"]
    assert body["parent_binding_id"] == source["id"]
    assert body["image_file_id"] == "fil_1"
    assert body["library"] == "personal"

    async with factory() as session:
        files = (await session.execute(Asset.__table__.select())).all()
        links = (await session.execute(FileLink.__table__.select())).all()
    assert len(files) == 2
    assert sum(1 for row in links if row.file_id == "fil_1") == 2


@pytest.mark.asyncio
async def test_manual_sync_requires_confirmation_and_source_read_permission(assets_env) -> None:
    app, factory = assets_env
    async with _client(app) as client:
        source = (
            await client.post(
                "/api/v1/assets",
                json={"library": "tenant", "type": "prop", "name": "Coin", "description": "v1"},
            )
        ).json()["asset"]
        target = (
            await client.post(
                "/api/v1/assets/import",
                json={"source_binding_id": source["id"], "target_library": "personal"},
            )
        ).json()["asset"]
        await client.patch(f"/api/v1/assets/{source['id']}", json={"description": "v2"})
        denied = await client.post(f"/api/v1/assets/{target['id']}/sync", json={"confirm_overwrite": False})
        synced = await client.post(f"/api/v1/assets/{target['id']}/sync", json={"confirm_overwrite": True})

    assert denied.status_code == 409
    assert synced.status_code == 200, synced.text
    assert synced.json()["asset"]["description"] == "v2"

    async with factory() as session:
        membership = (
            await session.execute(
                select(TenantMembership).where(
                    TenantMembership.tenant_id == "ten_1",
                    TenantMembership.user_id == "usr_1",
                )
            )
        ).scalar_one()
        await session.delete(membership)
        await session.commit()

    async with _client(app) as client:
        revoked = await client.post(f"/api/v1/assets/{target['id']}/sync", json={"confirm_overwrite": True})
    assert revoked.status_code == 403


@pytest.mark.asyncio
async def test_tenant_write_requires_member_plus(assets_env) -> None:
    app, _factory = assets_env
    app.dependency_overrides[get_current_user] = lambda: CurrentUserInfo(
        id="usr_2", sub="bob", tenant_id="ten_1", tenant_role="view"
    )
    async with _client(app) as client:
        response = await client.post(
            "/api/v1/assets",
            json={"library": "tenant", "type": "scene", "name": "Viewer Scene"},
        )
    assert response.status_code == 403
