from __future__ import annotations

import os
from unittest.mock import patch

import httpx
import jwt
import pytest
from fastapi import FastAPI

from lib.db import get_async_session
from lib.db.models import Tenant, TenantMembership, User
from server.auth import CurrentUserInfo, get_current_user
from server.routers import auth as auth_router
from server.routers import tenants as tenants_router
from server.services.tenant_auth import ROLE_ADMIN, ROLE_MEMBER, ROLE_VIEW

AUTH_TOKEN_SECRET = "tenant-router-secret-key-at-least-32-bytes"


async def _request(app: FastAPI, method: str, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        return await client.request(method, path, **kwargs)


async def _seed_user(async_session, user_id: str, username: str, *, active: bool = True) -> None:
    async_session.add(
        User(
            id=user_id,
            username=username,
            provider="camel",
            provider_subject=user_id.removeprefix("camel:"),
            role="user",
            is_active=active,
        )
    )
    await async_session.flush()


async def _seed_team(async_session) -> None:
    await _seed_user(async_session, "camel:owner", "owner")
    await _seed_user(async_session, "camel:member", "member")
    await _seed_user(async_session, "camel:viewer", "viewer")
    async_session.add(
        Tenant(
            id="ten_team",
            name="Team",
            owner_user_id="camel:owner",
            created_by_user_id="camel:owner",
        )
    )
    async_session.add_all(
        [
            TenantMembership(
                tenant_id="ten_team",
                user_id="camel:owner",
                role=ROLE_ADMIN,
                created_by_user_id="camel:owner",
            ),
            TenantMembership(
                tenant_id="ten_team",
                user_id="camel:member",
                role=ROLE_MEMBER,
                created_by_user_id="camel:owner",
            ),
        ]
    )
    await async_session.flush()


def _app(async_session, user: CurrentUserInfo) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: user

    async def override_session():
        yield async_session

    app.dependency_overrides[get_async_session] = override_session
    app.include_router(auth_router.router, prefix="/api/v1")
    app.include_router(tenants_router.router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
async def test_tenant_token_switch_returns_signed_current_tenant_snapshot(async_session):
    await _seed_team(async_session)
    user = CurrentUserInfo(id="camel:member", sub="member", provider="camel", role="admin")
    app = _app(async_session, user)

    with patch.dict(os.environ, {"AUTH_TOKEN_SECRET": AUTH_TOKEN_SECRET, "AUTH_ENABLED": "true"}):
        response = await _request(app, "POST", "/api/v1/auth/tenant-token", json={"tenant_id": "ten_team"})

    assert response.status_code == 200
    body = response.json()
    payload = jwt.decode(body["access_token"], AUTH_TOKEN_SECRET, algorithms=["HS256"])
    assert body["tenant"] == {
        "id": "ten_team",
        "name": "Team",
        "role": ROLE_MEMBER,
        "is_owner": False,
        "personal": False,
    }
    assert payload["user_id"] == "camel:member"
    assert payload["tenant_id"] == "ten_team"
    assert payload["tenant_role"] == ROLE_MEMBER


@pytest.mark.asyncio
async def test_member_can_add_viewer_but_cannot_add_member(async_session):
    await _seed_team(async_session)
    user = CurrentUserInfo(
        id="camel:member",
        sub="member",
        provider="camel",
        role="admin",
        tenant_id="ten_team",
        tenant_role=ROLE_ADMIN,
    )
    app = _app(async_session, user)

    allowed = await _request(
        app,
        "POST",
        "/api/v1/tenant/members",
        json={"user_id": "camel:viewer", "role": ROLE_VIEW},
    )
    denied = await _request(
        app,
        "POST",
        "/api/v1/tenant/members",
        json={"user_id": "camel:owner", "role": ROLE_MEMBER},
    )

    assert allowed.status_code == 200
    assert allowed.json()["role"] == ROLE_VIEW
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_change_existing_member_role(async_session):
    await _seed_team(async_session)
    async_session.add(
        TenantMembership(
            tenant_id="ten_team",
            user_id="camel:viewer",
            role=ROLE_MEMBER,
            created_by_user_id="camel:owner",
        )
    )
    await async_session.flush()
    user = CurrentUserInfo(
        id="camel:member",
        sub="member",
        provider="camel",
        role="admin",
        tenant_id="ten_team",
        tenant_role=ROLE_ADMIN,
    )
    app = _app(async_session, user)

    response = await _request(
        app,
        "PATCH",
        "/api/v1/tenant/members/camel:viewer",
        json={"role": ROLE_VIEW},
    )

    assert response.status_code == 403
