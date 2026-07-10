from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from lib.db import get_async_session
from lib.db.models import Tenant
from server.auth import CurrentUser
from server.services.tenant_auth import (
    ROLE_ADMIN,
    add_tenant_member,
    create_tenant,
    delete_tenant_member,
    list_tenant_members,
    member_to_dict,
    read_tenant_access,
    require_tenant_access,
    search_active_users,
    tenant_to_dict,
    update_tenant_member,
)

router = APIRouter()


class TenantCreateRequest(BaseModel):
    name: str


class TenantUpdateRequest(BaseModel):
    name: str


class TenantResponse(BaseModel):
    id: str
    name: str
    role: str
    is_owner: bool
    personal: bool


class MemberRequest(BaseModel):
    user_id: str
    role: str


class MemberUpdateRequest(BaseModel):
    role: str


class MemberResponse(BaseModel):
    user_id: str
    username: str
    role: str
    is_owner: bool


class MembersResponse(BaseModel):
    members: list[MemberResponse]


class UserSearchResponse(BaseModel):
    users: list[dict]


@router.post("/tenants", response_model=TenantResponse)
async def create_tenant_route(
    request: TenantCreateRequest,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    tenant = await create_tenant(session, user_id=current_user.id, name=request.name)
    await session.commit()
    return TenantResponse(**tenant_to_dict(tenant))


@router.get("/tenant", response_model=TenantResponse)
async def current_tenant(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    tenant = await require_tenant_access(session, current_user)
    return TenantResponse(**tenant_to_dict(tenant))


@router.patch("/tenant", response_model=TenantResponse)
async def update_current_tenant(
    request: TenantUpdateRequest,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    tenant = await require_tenant_access(session, current_user, minimum_role=ROLE_ADMIN)
    row = await read_tenant_access(session, user_id=current_user.id, tenant_id=tenant.id)
    if row is None:
        raise HTTPException(status_code=403, detail="TENANT_ACCESS_REVOKED")
    result = await session.get(Tenant, tenant.id)
    if result is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tenant name is required")
    result.name = name
    await session.commit()
    updated = await read_tenant_access(session, user_id=current_user.id, tenant_id=tenant.id)
    if updated is None:
        raise HTTPException(status_code=403, detail="TENANT_ACCESS_REVOKED")
    return TenantResponse(**tenant_to_dict(updated))


@router.get("/tenant/members", response_model=MembersResponse)
async def members(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    items = await list_tenant_members(session, current_user=current_user)
    return MembersResponse(members=[MemberResponse(**member_to_dict(item)) for item in items])


@router.get("/tenant/users/search", response_model=UserSearchResponse)
async def search_users(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    q: Annotated[str, Query(min_length=1)],
):
    users = await search_active_users(session, current_user=current_user, query=q)
    return UserSearchResponse(users=[{"id": user.id, "username": user.username} for user in users])


@router.post("/tenant/members", response_model=MemberResponse)
async def add_member(
    request: MemberRequest,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    if current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="TENANT_ACCESS_REQUIRED")
    member = await add_tenant_member(
        session,
        actor_user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        target_user_id=request.user_id,
        role=request.role,
    )
    await session.commit()
    return MemberResponse(**member_to_dict(member))


@router.patch("/tenant/members/{user_id}", response_model=MemberResponse)
async def update_member(
    user_id: str,
    request: MemberUpdateRequest,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    if current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="TENANT_ACCESS_REQUIRED")
    member = await update_tenant_member(
        session,
        actor_user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        target_user_id=user_id,
        role=request.role,
    )
    await session.commit()
    return MemberResponse(**member_to_dict(member))


@router.delete("/tenant/members/{user_id}", status_code=204)
async def delete_member(
    user_id: str,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    if current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="TENANT_ACCESS_REQUIRED")
    await delete_tenant_member(
        session,
        actor_user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        target_user_id=user_id,
    )
    await session.commit()
    return None
