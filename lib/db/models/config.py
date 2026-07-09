"""Provider config and system setting ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lib.db.base import Base, UserOwnedMixin, utc_now


class ProviderConfig(UserOwnedMixin, Base):
    __tablename__ = "provider_config"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "key", name="uq_provider_config_user_provider_key"),
        Index("ix_provider_config_provider", "provider"),
        Index("ix_provider_config_user_provider", "user_id", "provider"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class SystemSetting(UserOwnedMixin, Base):
    __tablename__ = "system_setting"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_system_setting_user_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
