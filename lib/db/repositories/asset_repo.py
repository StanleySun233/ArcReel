"""AssetRepository: async asset library operations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import exists, select

from lib.db.models import Asset, AssetLibraryBinding, FileLink
from lib.db.repositories.base import BaseRepository

LibraryScope = Literal["tenant", "personal"]


@dataclass(frozen=True)
class AssetLibraryItem:
    binding: AssetLibraryBinding
    asset: Asset


class AssetRepository(BaseRepository):
    async def create(
        self,
        *,
        type: str,
        name: str,
        description: str = "",
        voice_style: str = "",
        image_file_id: str | None = None,
        image_path: str | None = None,
        source_project: str | None = None,
    ) -> Asset:
        asset = Asset(
            id=str(uuid.uuid4()),
            type=type,
            name=name,
            description=description,
            voice_style=voice_style,
            image_file_id=image_file_id,
            image_path=image_path,
            source_project=source_project,
        )
        self.session.add(asset)
        await self.session.flush()
        return asset

    async def bind(
        self,
        *,
        asset_id: str,
        library_scope: LibraryScope,
        tenant_id: str | None,
        user_id: str | None,
        parent_binding_id: int | None = None,
    ) -> AssetLibraryBinding:
        binding = AssetLibraryBinding(
            library_scope=library_scope,
            tenant_id=tenant_id if library_scope == "tenant" else None,
            user_id=user_id if library_scope == "personal" else None,
            asset_id=asset_id,
            parent_id=parent_binding_id,
            snapshot_json="{}",
        )
        self.session.add(binding)
        await self.session.flush()
        return binding

    async def create_in_library(
        self,
        *,
        library_scope: LibraryScope,
        tenant_id: str | None,
        user_id: str,
        type: str,
        name: str,
        description: str = "",
        voice_style: str = "",
        image_file_id: str | None = None,
    ) -> AssetLibraryItem:
        asset = await self.create(
            type=type,
            name=name,
            description=description,
            voice_style=voice_style,
            image_file_id=image_file_id,
        )
        binding = await self.bind(
            asset_id=asset.id,
            library_scope=library_scope,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        return AssetLibraryItem(binding=binding, asset=asset)

    async def get_by_id(self, asset_id: str) -> Asset | None:
        return (await self.session.execute(select(Asset).where(Asset.id == asset_id))).scalar_one_or_none()

    async def get_by_type_name(self, type: str, name: str) -> Asset | None:
        return (
            await self.session.execute(select(Asset).where(Asset.type == type, Asset.name == name))
        ).scalar_one_or_none()

    async def get_by_ids(self, asset_ids: list[str]) -> list[Asset]:
        if not asset_ids:
            return []
        return list((await self.session.execute(select(Asset).where(Asset.id.in_(asset_ids)))).scalars())

    async def list(
        self,
        *,
        type: str | None,
        q: str | None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Asset]:
        stmt = select(Asset)
        if type:
            stmt = stmt.where(Asset.type == type)
        if q:
            stmt = stmt.where(Asset.name.contains(q))
        return list(
            (await self.session.execute(stmt.order_by(Asset.updated_at.desc()).limit(limit).offset(offset))).scalars()
        )

    async def get_item(self, binding_id: int) -> AssetLibraryItem | None:
        row = (
            await self.session.execute(
                select(AssetLibraryBinding, Asset)
                .join(Asset, Asset.id == AssetLibraryBinding.asset_id)
                .where(AssetLibraryBinding.id == binding_id)
            )
        ).one_or_none()
        if row is None:
            return None
        binding, asset = row
        return AssetLibraryItem(binding=binding, asset=asset)

    async def list_library(
        self,
        *,
        library_scope: LibraryScope,
        tenant_id: str | None,
        user_id: str,
        type: str | None,
        q: str | None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AssetLibraryItem]:
        stmt = select(AssetLibraryBinding, Asset).join(Asset, Asset.id == AssetLibraryBinding.asset_id)
        if library_scope == "tenant":
            stmt = stmt.where(AssetLibraryBinding.library_scope == "tenant", AssetLibraryBinding.tenant_id == tenant_id)
        else:
            stmt = stmt.where(AssetLibraryBinding.library_scope == "personal", AssetLibraryBinding.user_id == user_id)
        if type:
            stmt = stmt.where(Asset.type == type)
        if q:
            stmt = stmt.where(Asset.name.contains(q))
        rows = (await self.session.execute(stmt.order_by(Asset.updated_at.desc()).limit(limit).offset(offset))).all()
        return [AssetLibraryItem(binding=binding, asset=asset) for binding, asset in rows]

    async def find_library_name(
        self,
        *,
        library_scope: LibraryScope,
        tenant_id: str | None,
        user_id: str,
        type: str,
        name: str,
    ) -> AssetLibraryItem | None:
        items = await self.list_library(
            library_scope=library_scope,
            tenant_id=tenant_id,
            user_id=user_id,
            type=type,
            q=name,
            limit=100,
            offset=0,
        )
        return next((item for item in items if item.asset.name == name), None)

    async def import_snapshot(
        self,
        *,
        source: AssetLibraryItem,
        target_scope: LibraryScope,
        target_tenant_id: str | None,
        target_user_id: str,
    ) -> AssetLibraryItem:
        asset = source.asset
        snapshot = await self.create(
            type=asset.type,
            name=asset.name,
            description=asset.description,
            voice_style=asset.voice_style,
            image_file_id=asset.image_file_id,
            image_path=asset.image_path,
            source_project=asset.source_project,
        )
        binding = await self.bind(
            asset_id=snapshot.id,
            library_scope=target_scope,
            tenant_id=target_tenant_id,
            user_id=target_user_id,
            parent_binding_id=source.binding.id,
        )
        return AssetLibraryItem(binding=binding, asset=snapshot)

    async def update(self, asset_id: str, **fields: Any) -> Asset:
        asset = await self.get_by_id(asset_id)
        if asset is None:
            raise ValueError(f"Asset not found: {asset_id}")
        for k, v in fields.items():
            setattr(asset, k, v)
        await self.session.flush()
        return asset

    async def update_binding_asset(self, binding_id: int, **fields: Any) -> AssetLibraryItem:
        item = await self.get_item(binding_id)
        if item is None:
            raise ValueError(f"Asset binding not found: {binding_id}")
        await self.update(item.asset.id, **fields)
        return item

    async def sync_from_parent(self, binding_id: int) -> AssetLibraryItem:
        target = await self.get_item(binding_id)
        if target is None or target.binding.parent_id is None:
            raise ValueError(f"Asset binding has no parent: {binding_id}")
        source = await self.get_item(target.binding.parent_id)
        if source is None:
            raise ValueError(f"Parent asset binding not found: {target.binding.parent_id}")
        await self.update(
            target.asset.id,
            type=source.asset.type,
            name=source.asset.name,
            description=source.asset.description,
            voice_style=source.asset.voice_style,
            image_file_id=source.asset.image_file_id,
            image_path=source.asset.image_path,
            source_project=source.asset.source_project,
        )
        return target

    async def delete(self, asset_id: str) -> None:
        asset = await self.get_by_id(asset_id)
        if asset:
            await self.session.delete(asset)
            await self.session.flush()

    async def delete_binding(self, binding_id: int) -> None:
        item = await self.get_item(binding_id)
        if item is None:
            return
        await self.session.delete(item.binding)
        await self.session.delete(item.asset)
        await self.session.flush()

    async def exists(self, type: str, name: str) -> bool:
        return await self.get_by_type_name(type, name) is not None

    async def ensure_library_file_link(
        self,
        *,
        file_id: str | None,
        library_scope: LibraryScope,
        tenant_id: str | None,
        user_id: str,
    ) -> None:
        if file_id is None:
            return
        resource_type = "tenant_library" if library_scope == "tenant" else "personal_library"
        resource_id = tenant_id if library_scope == "tenant" else user_id
        link_exists = (
            await self.session.execute(
                select(
                    exists().where(
                        FileLink.file_id == file_id,
                        FileLink.resource_type == resource_type,
                        FileLink.resource_id == resource_id,
                        FileLink.link_type == "library",
                    )
                )
            )
        ).scalar()
        if link_exists:
            return
        self.session.add(
            FileLink(
                file_id=file_id,
                resource_type=resource_type,
                resource_id=resource_id or "",
                link_type="library",
                created_by_user_id=user_id,
            )
        )
        await self.session.flush()
