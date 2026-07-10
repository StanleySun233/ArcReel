"""Asset library routes."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lib.asset_types import GLOBAL_LIBRARY_ASSET_TYPES, validate_asset_name
from lib.db import async_session_factory
from lib.db.repositories.asset_repo import AssetLibraryItem, AssetRepository, LibraryScope
from lib.db.repositories.file_repo import FileRepository
from lib.i18n import Translator
from server.auth import CurrentUser, CurrentUserInfo
from server.services.tenant_auth import ROLE_MEMBER, ROLE_VIEW, require_tenant_access

router = APIRouter(prefix="/assets", tags=["assets"])


class AssetCreateRequest(BaseModel):
    library: LibraryScope = "tenant"
    type: str
    name: str
    description: str = ""
    voice_style: str = ""
    image_file_id: str | None = None


class AssetUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    voice_style: str | None = None
    image_file_id: str | None = None


class AssetImportRequest(BaseModel):
    source_binding_id: str
    target_library: LibraryScope


class AssetSyncRequest(BaseModel):
    confirm_overwrite: bool = False


def _binding_public_id(binding_id: int) -> str:
    return f"ab_{binding_id}"


def _parse_binding_id(raw: str) -> int:
    value = raw[3:] if raw.startswith("ab_") else raw
    if not value.isdigit():
        raise HTTPException(status_code=404, detail="ASSET_BINDING_NOT_FOUND")
    return int(value)


def _serialize(item: AssetLibraryItem, *, can_write: bool) -> dict:
    asset = item.asset
    binding = item.binding
    return {
        "id": _binding_public_id(binding.id),
        "binding_id": _binding_public_id(binding.id),
        "asset_id": asset.id,
        "type": asset.type,
        "name": asset.name,
        "description": asset.description,
        "voice_style": asset.voice_style,
        "image_file_id": asset.image_file_id,
        "image_path": asset.image_path,
        "source_project": asset.source_project,
        "library": binding.library_scope,
        "tenant_id": binding.tenant_id,
        "user_id": binding.user_id,
        "parent_binding_id": _binding_public_id(binding.parent_id) if binding.parent_id else None,
        "can_write": can_write,
        "can_sync": can_write and binding.parent_id is not None,
        "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
    }


def _target_owner(
    library: LibraryScope, current_user: CurrentUserInfo, tenant_id: str | None
) -> tuple[str | None, str]:
    return (tenant_id if library == "tenant" else None, current_user.id)


def _can_write_personal(item: AssetLibraryItem, current_user: CurrentUserInfo) -> bool:
    return item.binding.library_scope == "personal" and item.binding.user_id == current_user.id


async def _require_library_read(
    repo: AssetRepository, binding_id: str, current_user: CurrentUserInfo
) -> AssetLibraryItem:
    item = await repo.get_item(_parse_binding_id(binding_id))
    if item is None:
        raise HTTPException(status_code=404, detail="ASSET_BINDING_NOT_FOUND")
    if item.binding.library_scope == "personal":
        if item.binding.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="ASSET_SOURCE_ACCESS_DENIED")
        return item
    if item.binding.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="ASSET_SOURCE_ACCESS_DENIED")
    await require_tenant_access(repo.session, current_user, minimum_role=ROLE_VIEW)
    return item


async def _require_library_write(
    repo: AssetRepository,
    binding_id: str,
    current_user: CurrentUserInfo,
    _t: Translator,
) -> AssetLibraryItem:
    item = await _require_library_read(repo, binding_id, current_user)
    if _can_write_personal(item, current_user):
        return item
    if item.binding.library_scope == "tenant":
        await require_tenant_access(repo.session, current_user, minimum_role=ROLE_MEMBER)
        return item
    raise HTTPException(status_code=403, detail="ASSET_LIBRARY_WRITE_DENIED")


async def _require_target_write(
    repo: AssetRepository,
    library: LibraryScope,
    current_user: CurrentUserInfo,
) -> str | None:
    if library == "personal":
        return None
    access = await require_tenant_access(repo.session, current_user, minimum_role=ROLE_MEMBER)
    return access.id


async def _check_file_read(repo: AssetRepository, *, file_id: str | None, current_user: CurrentUserInfo) -> None:
    if file_id is None:
        return
    allowed = await FileRepository(repo.session).can_access_file(
        file_id=file_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="FILE_ACCESS_DENIED")


@router.get("")
async def list_assets(
    current_user: CurrentUser,
    _t: Translator,
    library: LibraryScope = "tenant",
    type: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    if type is not None and type not in GLOBAL_LIBRARY_ASSET_TYPES:
        raise HTTPException(status_code=400, detail=_t("asset_invalid_type"))
    async with async_session_factory() as session:
        repo = AssetRepository(session)
        can_write = library == "personal"
        tenant_id = None
        if library == "tenant":
            access = await require_tenant_access(session, current_user, minimum_role=ROLE_VIEW)
            tenant_id = access.id
            can_write = access.role in {"admin", "member"}
        items = await repo.list_library(
            library_scope=library,
            tenant_id=tenant_id,
            user_id=current_user.id,
            type=type,
            q=q,
            limit=limit,
            offset=offset,
        )
        return {"items": [_serialize(item, can_write=can_write) for item in items]}


@router.get("/{binding_id}")
async def get_asset(binding_id: str, current_user: CurrentUser, _t: Translator):
    async with async_session_factory() as session:
        repo = AssetRepository(session)
        item = await _require_library_read(repo, binding_id, current_user)
        can_write = _can_write_personal(item, current_user)
        if item.binding.library_scope == "tenant":
            access = await require_tenant_access(session, current_user, minimum_role=ROLE_VIEW)
            can_write = access.role in {"admin", "member"}
        return {"asset": _serialize(item, can_write=can_write)}


@router.post("")
async def create_asset(req: AssetCreateRequest, current_user: CurrentUser, _t: Translator):
    if req.type not in GLOBAL_LIBRARY_ASSET_TYPES:
        raise HTTPException(status_code=400, detail=_t("asset_invalid_type"))
    name = _validate_name(req.name, _t)
    async with async_session_factory() as session:
        repo = AssetRepository(session)
        tenant_id = await _require_target_write(repo, req.library, current_user)
        await _check_file_read(repo, file_id=req.image_file_id, current_user=current_user)
        existing = await repo.find_library_name(
            library_scope=req.library,
            tenant_id=tenant_id,
            user_id=current_user.id,
            type=req.type,
            name=name,
        )
        if existing is not None:
            raise HTTPException(status_code=409, detail=_t("asset_already_exists", name=name))
        item = await repo.create_in_library(
            library_scope=req.library,
            tenant_id=tenant_id,
            user_id=current_user.id,
            type=req.type,
            name=name,
            description=req.description,
            voice_style=req.voice_style,
            image_file_id=req.image_file_id,
        )
        await repo.ensure_library_file_link(
            file_id=req.image_file_id,
            library_scope=req.library,
            tenant_id=tenant_id,
            user_id=current_user.id,
        )
        await session.commit()
        await session.refresh(item.asset)
        return {"asset": _serialize(item, can_write=True)}


@router.patch("/{binding_id}")
async def update_asset(binding_id: str, req: AssetUpdateRequest, current_user: CurrentUser, _t: Translator):
    patch = {k: v for k, v in req.model_dump().items() if v is not None}
    if "name" in patch:
        patch["name"] = _validate_name(patch["name"], _t)
    async with async_session_factory() as session:
        repo = AssetRepository(session)
        item = await _require_library_write(repo, binding_id, current_user, _t)
        if "image_file_id" in patch:
            await _check_file_read(repo, file_id=patch["image_file_id"], current_user=current_user)
        updated = await repo.update_binding_asset(item.binding.id, **patch)
        await repo.ensure_library_file_link(
            file_id=patch.get("image_file_id"),
            library_scope=cast(LibraryScope, item.binding.library_scope),
            tenant_id=item.binding.tenant_id,
            user_id=current_user.id,
        )
        await session.commit()
        await session.refresh(updated.asset)
        return {"asset": _serialize(updated, can_write=True)}


@router.delete("/{binding_id}", status_code=204)
async def delete_asset(binding_id: str, current_user: CurrentUser, _t: Translator):
    async with async_session_factory() as session:
        repo = AssetRepository(session)
        item = await _require_library_write(repo, binding_id, current_user, _t)
        await repo.delete_binding(item.binding.id)
        await session.commit()
    return None


@router.post("/import")
async def import_asset(req: AssetImportRequest, current_user: CurrentUser, _t: Translator):
    async with async_session_factory() as session:
        repo = AssetRepository(session)
        source = await _require_library_read(repo, req.source_binding_id, current_user)
        target_tenant_id = await _require_target_write(repo, req.target_library, current_user)
        existing = await repo.find_library_name(
            library_scope=req.target_library,
            tenant_id=target_tenant_id,
            user_id=current_user.id,
            type=source.asset.type,
            name=source.asset.name,
        )
        if existing is not None:
            raise HTTPException(status_code=409, detail=_t("asset_already_exists", name=source.asset.name))
        item = await repo.import_snapshot(
            source=source,
            target_scope=req.target_library,
            target_tenant_id=target_tenant_id,
            target_user_id=current_user.id,
        )
        await repo.ensure_library_file_link(
            file_id=item.asset.image_file_id,
            library_scope=req.target_library,
            tenant_id=target_tenant_id,
            user_id=current_user.id,
        )
        await session.commit()
        await session.refresh(item.asset)
        return {"asset": _serialize(item, can_write=True)}


@router.post("/{binding_id}/sync")
async def sync_asset(binding_id: str, req: AssetSyncRequest, current_user: CurrentUser, _t: Translator):
    if not req.confirm_overwrite:
        raise HTTPException(status_code=409, detail="ASSET_SYNC_REQUIRES_CONFIRMATION")
    async with async_session_factory() as session:
        repo = AssetRepository(session)
        target = await _require_library_write(repo, binding_id, current_user, _t)
        if target.binding.parent_id is None:
            raise HTTPException(status_code=400, detail="ASSET_BINDING_HAS_NO_PARENT")
        await _require_library_read(repo, _binding_public_id(target.binding.parent_id), current_user)
        item = await repo.sync_from_parent(target.binding.id)
        await repo.ensure_library_file_link(
            file_id=item.asset.image_file_id,
            library_scope=cast(LibraryScope, target.binding.library_scope),
            tenant_id=target.binding.tenant_id,
            user_id=current_user.id,
        )
        await session.commit()
        await session.refresh(item.asset)
        return {"asset": _serialize(item, can_write=True)}


def _validate_name(name: str, _t: Translator) -> str:
    try:
        return validate_asset_name(name)
    except ValueError:
        raise HTTPException(status_code=400, detail=_t("asset_invalid_name", name=name))
