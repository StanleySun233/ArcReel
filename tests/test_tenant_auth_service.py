from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from lib.db.models import Tenant, TenantMembership, User
from server.auth import CurrentUserInfo
from server.services.permission_cache import CachedPermission
from server.services.tenant_auth import (
    ROLE_ADMIN,
    ROLE_MEMBER,
    ROLE_VIEW,
    add_tenant_member,
    ensure_personal_tenant,
    read_tenant_access,
    require_tenant_access,
)


class RecordingPermissionCache:
    def __init__(self) -> None:
        self.deleted: list[tuple[str, str]] = []
        self.values: dict[tuple[str, str], CachedPermission] = {}

    async def get(self, user_id: str, tenant_id: str) -> CachedPermission | None:
        return self.values.get((user_id, tenant_id))

    async def set(self, permission: CachedPermission) -> None:
        self.values[(permission.user_id, permission.tenant_id)] = permission

    async def delete(self, user_id: str, tenant_id: str) -> None:
        self.deleted.append((user_id, tenant_id))
        self.values.pop((user_id, tenant_id), None)


async def _add_user(async_session, user_id: str, username: str, *, active: bool = True) -> None:
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


@pytest.mark.asyncio
async def test_ensure_personal_tenant_creates_owner_admin_membership(async_session):
    await _add_user(async_session, "camel:123", "alice")

    access = await ensure_personal_tenant(async_session, user_id="camel:123", username="alice")
    await async_session.flush()

    assert access.name == "alice的个人空间"
    assert access.role == ROLE_ADMIN
    assert access.is_owner is True
    assert access.personal is True

    membership = (
        await async_session.execute(
            select(TenantMembership).where(
                TenantMembership.tenant_id == access.id,
                TenantMembership.user_id == "camel:123",
            )
        )
    ).scalar_one()
    tenant = (await async_session.execute(select(Tenant).where(Tenant.id == access.id))).scalar_one()
    assert tenant.owner_user_id == "camel:123"
    assert tenant.personal_for_user_id == "camel:123"
    assert membership.role == ROLE_ADMIN


@pytest.mark.asyncio
async def test_ensure_personal_tenant_is_idempotent(async_session):
    await _add_user(async_session, "camel:123", "alice")

    first = await ensure_personal_tenant(async_session, user_id="camel:123", username="alice")
    second = await ensure_personal_tenant(async_session, user_id="camel:123", username="alice-renamed")
    await async_session.flush()

    count = (
        await async_session.execute(
            select(func.count()).select_from(Tenant).where(Tenant.personal_for_user_id == "camel:123")
        )
    ).scalar_one()
    assert second.id == first.id
    assert count == 1


@pytest.mark.asyncio
async def test_require_tenant_access_uses_database_role_not_jwt_snapshot(async_session):
    await _add_user(async_session, "camel:owner", "owner")
    async_session.add(
        Tenant(
            id="ten_team",
            name="Team",
            owner_user_id="camel:owner",
            created_by_user_id="camel:owner",
        )
    )
    async_session.add(
        TenantMembership(
            tenant_id="ten_team",
            user_id="camel:owner",
            role=ROLE_VIEW,
            created_by_user_id="camel:owner",
        )
    )
    await async_session.flush()
    stale_user = CurrentUserInfo(
        id="camel:owner",
        sub="owner",
        provider="camel",
        role="admin",
        tenant_id="ten_team",
        tenant_role=ROLE_ADMIN,
    )

    with pytest.raises(HTTPException) as exc:
        await require_tenant_access(async_session, stale_user, minimum_role=ROLE_MEMBER)

    assert exc.value.status_code == 403
    assert exc.value.detail == "STALE_TENANT_ROLE"


@pytest.mark.asyncio
async def test_require_tenant_access_denies_without_stale_role_when_snapshot_matches(async_session):
    await _add_user(async_session, "camel:owner", "owner")
    async_session.add(
        Tenant(
            id="ten_team",
            name="Team",
            owner_user_id="camel:owner",
            created_by_user_id="camel:owner",
        )
    )
    async_session.add(
        TenantMembership(
            tenant_id="ten_team",
            user_id="camel:owner",
            role=ROLE_VIEW,
            created_by_user_id="camel:owner",
        )
    )
    await async_session.flush()
    user = CurrentUserInfo(
        id="camel:owner",
        sub="owner",
        provider="camel",
        role="admin",
        tenant_id="ten_team",
        tenant_role=ROLE_VIEW,
    )

    with pytest.raises(HTTPException) as exc:
        await require_tenant_access(async_session, user, minimum_role=ROLE_MEMBER)

    assert exc.value.status_code == 403
    assert exc.value.detail == "TENANT_PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_read_tenant_access_populates_and_reuses_permission_cache(async_session):
    await _add_user(async_session, "camel:owner", "owner")
    async_session.add(
        Tenant(
            id="ten_team",
            name="Team",
            owner_user_id="camel:owner",
            created_by_user_id="camel:owner",
        )
    )
    async_session.add(
        TenantMembership(
            tenant_id="ten_team",
            user_id="camel:owner",
            role=ROLE_MEMBER,
            created_by_user_id="camel:owner",
        )
    )
    await async_session.flush()
    cache = RecordingPermissionCache()

    first = await read_tenant_access(
        async_session,
        user_id="camel:owner",
        tenant_id="ten_team",
        permission_cache=cache,
    )
    membership = (
        await async_session.execute(
            select(TenantMembership).where(
                TenantMembership.tenant_id == "ten_team",
                TenantMembership.user_id == "camel:owner",
            )
        )
    ).scalar_one()
    membership.role = ROLE_VIEW
    await async_session.flush()
    second = await read_tenant_access(
        async_session,
        user_id="camel:owner",
        tenant_id="ten_team",
        permission_cache=cache,
    )

    assert first is not None
    assert first.role == ROLE_MEMBER
    assert second is not None
    assert second.role == ROLE_MEMBER


@pytest.mark.asyncio
async def test_add_tenant_member_applies_role_rules_and_invalidates_cache(async_session):
    await _add_user(async_session, "camel:owner", "owner")
    await _add_user(async_session, "camel:admin", "admin")
    await _add_user(async_session, "camel:member", "member")
    await _add_user(async_session, "camel:viewer", "viewer")
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
    cache = RecordingPermissionCache()

    admin_member = await add_tenant_member(
        async_session,
        actor_user_id="camel:owner",
        tenant_id="ten_team",
        target_user_id="camel:admin",
        role=ROLE_ADMIN,
        permission_cache=cache,
    )
    viewer_member = await add_tenant_member(
        async_session,
        actor_user_id="camel:member",
        tenant_id="ten_team",
        target_user_id="camel:viewer",
        role=ROLE_VIEW,
        permission_cache=cache,
    )

    assert admin_member.role == ROLE_ADMIN
    assert viewer_member.role == ROLE_VIEW
    assert cache.deleted == [("camel:admin", "ten_team"), ("camel:viewer", "ten_team")]
