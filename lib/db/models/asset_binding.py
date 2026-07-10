from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from lib.db.base import Base, TimestampMixin


class AssetLibraryBinding(TimestampMixin, Base):
    __tablename__ = "asset_library_bindings"
    __table_args__ = (
        CheckConstraint("library_scope IN ('tenant', 'personal')", name="ck_asset_library_bindings_scope"),
        CheckConstraint(
            "(library_scope = 'tenant' AND tenant_id IS NOT NULL AND user_id IS NULL) "
            "OR (library_scope = 'personal' AND user_id IS NOT NULL AND tenant_id IS NULL)",
            name="ck_asset_library_bindings_owner",
        ),
        Index(
            "uq_asset_library_binding_tenant",
            "tenant_id",
            "asset_id",
            unique=True,
            postgresql_where=text("library_scope = 'tenant' AND tenant_id IS NOT NULL"),
        ),
        Index(
            "uq_asset_library_binding_personal",
            "user_id",
            "asset_id",
            unique=True,
            postgresql_where=text("library_scope = 'personal' AND user_id IS NOT NULL"),
        ),
        Index("ix_asset_library_bindings_tenant", "tenant_id"),
        Index("ix_asset_library_bindings_user", "user_id"),
        Index("ix_asset_library_bindings_parent", "parent_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    library_scope: Mapped[str] = mapped_column(String(16), nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("asset_library_bindings.id", ondelete="SET NULL"), nullable=True
    )
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")
