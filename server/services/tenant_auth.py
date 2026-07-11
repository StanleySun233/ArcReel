from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal, cast

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lib.db.models import Tenant, TenantMembership, User
from server.auth import CurrentUserInfo
from server.services.permission_cache import CachedPermission, PermissionCache, get_permission_cache

ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLE_VIEW = "view"
TenantRole = Literal["admin", "member", "view"]
ROLE_RANK = {ROLE_VIEW: 1, ROLE_MEMBER: 2, ROLE_ADMIN: 3}


@dataclass(frozen=True)
class TenantAccess:
    id: str
    name: str
    role: str
    is_owner: bool
    personal: bool


@dataclass(frozen=True)
class TenantMember:
    user_id: str
    username: str
    role: str
    is_owner: bool


@dataclass(frozen=True)
class TenantUser:
    id: str
    username: str


def tenant_to_dict(access: TenantAccess) -> dict:
    return {
        "id": access.id,
        "name": access.name,
        "role": access.role,
        "is_owner": access.is_owner,
        "personal": access.personal,
    }


def member_to_dict(member: TenantMember) -> dict:
    return {
        "user_id": member.user_id,
        "username": member.username,
        "role": member.role,
        "is_owner": member.is_owner,
    }


def _validate_role(role: str) -> TenantRole:
    if role not in ROLE_RANK:
        raise HTTPException(status_code=400, detail="Invalid tenant role")
    return cast(TenantRole, role)


def _tenant_id() -> str:
    return f"ten_{uuid.uuid4().hex}"


async def ensure_personal_tenant(session: AsyncSession, *, user_id: str, username: str) -> TenantAccess:
    result = await session.execute(select(Tenant).where(Tenant.personal_for_user_id == user_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(
            id=_tenant_id(),
            name=f"{username}的个人空间",
            owner_user_id=user_id,
            personal_for_user_id=user_id,
            created_by_user_id=user_id,
        )
        session.add(tenant)
        await session.flush()
        session.add(
            TenantMembership(
                tenant_id=tenant.id,
                user_id=user_id,
                role=ROLE_ADMIN,
                created_by_user_id=user_id,
            )
        )
        await session.flush()
    return TenantAccess(
        id=tenant.id,
        name=tenant.name,
        role=ROLE_ADMIN,
        is_owner=True,
        personal=True,
    )


async def list_user_tenants(session: AsyncSession, user_id: str) -> list[TenantAccess]:
    rows = (
        await session.execute(
            select(Tenant, TenantMembership)
            .join(TenantMembership, TenantMembership.tenant_id == Tenant.id)
            .join(User, User.id == TenantMembership.user_id)
            .where(TenantMembership.user_id == user_id, User.is_active.is_(True))
            .order_by(Tenant.personal_for_user_id.is_(None), Tenant.created_at.asc())
        )
    ).all()
    return [_row_to_access(tenant, membership, user_id) for tenant, membership in rows]


async def create_tenant(session: AsyncSession, *, user_id: str, name: str) -> TenantAccess:
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Tenant name is required")
    tenant = Tenant(id=_tenant_id(), name=clean_name, owner_user_id=user_id, created_by_user_id=user_id)
    session.add(tenant)
    await session.flush()
    session.add(TenantMembership(tenant_id=tenant.id, user_id=user_id, role=ROLE_ADMIN, created_by_user_id=user_id))
    await session.flush()
    return TenantAccess(id=tenant.id, name=tenant.name, role=ROLE_ADMIN, is_owner=True, personal=False)


async def read_tenant_access(
    session: AsyncSession,
    *,
    user_id: str,
    tenant_id: str,
    permission_cache: PermissionCache | None = None,
) -> TenantAccess | None:
    cache = permission_cache if permission_cache is not None else get_permission_cache()
    cached = await cache.get(user_id, tenant_id) if cache is not None else None
    if cached is not None:
        tenant = await _tenant(session, tenant_id)
        return TenantAccess(
            id=tenant.id,
            name=tenant.name,
            role=cached.role,
            is_owner=cached.is_owner,
            personal=tenant.personal_for_user_id == user_id,
        )
    result = await session.execute(
        select(Tenant, TenantMembership)
        .join(TenantMembership, TenantMembership.tenant_id == Tenant.id)
        .join(User, User.id == TenantMembership.user_id)
        .where(Tenant.id == tenant_id, TenantMembership.user_id == user_id, User.is_active.is_(True))
    )
    row = result.one_or_none()
    if row is None:
        return None
    tenant, membership = row
    access = _row_to_access(tenant, membership, user_id)
    if cache is not None:
        await cache.set(
            CachedPermission(
                user_id=user_id,
                tenant_id=tenant_id,
                role=access.role,
                is_owner=access.is_owner,
            )
        )
    return access


async def require_tenant_access(
    session: AsyncSession,
    current_user: CurrentUserInfo,
    *,
    minimum_role: str = ROLE_VIEW,
    permission_cache: PermissionCache | None = None,
) -> TenantAccess:
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=403, detail="TENANT_ACCESS_REQUIRED")
    access = await read_tenant_access(
        session,
        user_id=current_user.id,
        tenant_id=tenant_id,
        permission_cache=permission_cache,
    )
    if access is None:
        raise HTTPException(status_code=403, detail="TENANT_ACCESS_REVOKED")
    try:
        _require_role(access.role, minimum_role)
    except HTTPException:
        if current_user.tenant_role is not None and current_user.tenant_role != access.role:
            raise HTTPException(status_code=403, detail="STALE_TENANT_ROLE")
        raise
    return access


async def add_tenant_member(
    session: AsyncSession,
    *,
    actor_user_id: str,
    tenant_id: str,
    target_user_id: str,
    role: str,
    permission_cache: PermissionCache | None = None,
) -> TenantMember:
    target_role = _validate_role(role)
    actor = await _membership_access(session, actor_user_id, tenant_id, permission_cache)
    _require_can_assign(actor, target_role)
    target = await _active_user(session, target_user_id)
    existing = await _membership(session, target_user_id, tenant_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Tenant member already exists")
    membership = TenantMembership(
        tenant_id=tenant_id,
        user_id=target_user_id,
        role=target_role,
        created_by_user_id=actor_user_id,
    )
    session.add(membership)
    await session.flush()
    await _invalidate(permission_cache, target_user_id, tenant_id)
    return TenantMember(
        user_id=target_user_id,
        username=target.username,
        role=target_role,
        is_owner=False,
    )


async def update_tenant_member(
    session: AsyncSession,
    *,
    actor_user_id: str,
    tenant_id: str,
    target_user_id: str,
    role: str,
    permission_cache: PermissionCache | None = None,
) -> TenantMember:
    target_role = _validate_role(role)
    tenant = await _tenant(session, tenant_id)
    actor = await _membership_access(session, actor_user_id, tenant_id, permission_cache)
    _require_can_change_role(actor, target_role)
    if tenant.owner_user_id == target_user_id:
        raise HTTPException(status_code=403, detail="Tenant owner role cannot be changed")
    membership = await _membership(session, target_user_id, tenant_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Tenant member not found")
    user = await _active_user(session, target_user_id)
    membership.role = target_role
    await session.flush()
    await _invalidate(permission_cache, target_user_id, tenant_id)
    return TenantMember(user_id=target_user_id, username=user.username, role=target_role, is_owner=False)


async def delete_tenant_member(
    session: AsyncSession,
    *,
    actor_user_id: str,
    tenant_id: str,
    target_user_id: str,
    permission_cache: PermissionCache | None = None,
) -> None:
    tenant = await _tenant(session, tenant_id)
    if tenant.owner_user_id == target_user_id:
        raise HTTPException(status_code=403, detail="Tenant owner cannot be removed")
    actor = await _membership_access(session, actor_user_id, tenant_id, permission_cache)
    _require_role(actor.role, ROLE_ADMIN)
    membership = await _membership(session, target_user_id, tenant_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Tenant member not found")
    await session.delete(membership)
    await session.flush()
    await _invalidate(permission_cache, target_user_id, tenant_id)


async def list_tenant_members(session: AsyncSession, *, current_user: CurrentUserInfo) -> list[TenantMember]:
    access = await require_tenant_access(session, current_user)
    rows = (
        await session.execute(
            select(Tenant, TenantMembership, User)
            .join(TenantMembership, TenantMembership.tenant_id == Tenant.id)
            .join(User, User.id == TenantMembership.user_id)
            .where(Tenant.id == access.id, User.is_active.is_(True))
            .order_by(TenantMembership.created_at.asc())
        )
    ).all()
    return [
        TenantMember(
            user_id=user.id,
            username=user.username,
            role=membership.role,
            is_owner=tenant.owner_user_id == user.id,
        )
        for tenant, membership, user in rows
    ]


async def search_active_users(session: AsyncSession, *, current_user: CurrentUserInfo, query: str) -> list[TenantUser]:
    await require_tenant_access(session, current_user, minimum_role=ROLE_MEMBER)
    clean_query = query.strip()
    if not clean_query:
        return []
    rows = (
        await session.execute(
            select(User)
            .where(
                User.is_active.is_(True),
                or_(User.username.ilike(f"%{clean_query}%"), User.id.ilike(f"%{clean_query}%")),
            )
            .order_by(User.username.asc())
            .limit(20)
        )
    ).scalars()
    return [TenantUser(id=user.id, username=user.username) for user in rows]


async def _membership_access(
    session: AsyncSession,
    user_id: str,
    tenant_id: str,
    permission_cache: PermissionCache | None = None,
) -> TenantAccess:
    access = await read_tenant_access(
        session,
        user_id=user_id,
        tenant_id=tenant_id,
        permission_cache=permission_cache,
    )
    if access is None:
        raise HTTPException(status_code=403, detail="TENANT_ACCESS_REVOKED")
    return access


async def _tenant(session: AsyncSession, tenant_id: str) -> Tenant:
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


async def _membership(session: AsyncSession, user_id: str, tenant_id: str) -> TenantMembership | None:
    return (
        await session.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == user_id,
                TenantMembership.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()


async def _active_user(session: AsyncSession, user_id: str) -> User:
    result = await session.execute(select(User).where(and_(User.id == user_id, User.is_active.is_(True))))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Active user not found")
    return user


def _row_to_access(tenant: Tenant, membership: TenantMembership, user_id: str) -> TenantAccess:
    return TenantAccess(
        id=tenant.id,
        name=tenant.name,
        role=membership.role,
        is_owner=tenant.owner_user_id == user_id,
        personal=tenant.personal_for_user_id == user_id,
    )


def _require_role(actual_role: str, minimum_role: str) -> None:
    _validate_role(actual_role)
    _validate_role(minimum_role)
    if ROLE_RANK[actual_role] < ROLE_RANK[minimum_role]:
        raise HTTPException(status_code=403, detail="TENANT_PERMISSION_DENIED")


def _require_can_assign(actor: TenantAccess, target_role: str) -> None:
    if target_role == ROLE_ADMIN:
        if not actor.is_owner:
            raise HTTPException(status_code=403, detail="Only tenant owner can assign admin")
        return
    if target_role == ROLE_MEMBER:
        _require_role(actor.role, ROLE_ADMIN)
        return
    _require_role(actor.role, ROLE_MEMBER)


def _require_can_change_role(actor: TenantAccess, target_role: str) -> None:
    if target_role == ROLE_ADMIN:
        if not actor.is_owner:
            raise HTTPException(status_code=403, detail="Only tenant owner can assign admin")
        return
    _require_role(actor.role, ROLE_ADMIN)


async def _invalidate(permission_cache: PermissionCache | None, user_id: str, tenant_id: str) -> None:
    cache = permission_cache if permission_cache is not None else get_permission_cache()
    if cache is not None:
        await cache.delete(user_id, tenant_id)
