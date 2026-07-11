from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lib.db.base import Base, TimestampMixin


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (
        UniqueConstraint("personal_for_user_id", name="uq_tenants_personal_for_user"),
        Index("ix_tenants_owner_user_id", "owner_user_id"),
        Index("ix_tenants_created_by_user_id", "created_by_user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    personal_for_user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class TenantMembership(TimestampMixin, Base):
    __tablename__ = "tenant_memberships"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'member', 'view')", name="ck_tenant_memberships_role"),
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_memberships_tenant_user"),
        Index("ix_tenant_memberships_user_id", "user_id"),
        Index("ix_tenant_memberships_tenant_role", "tenant_id", "role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
