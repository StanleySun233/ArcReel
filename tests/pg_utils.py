from __future__ import annotations

import os
import uuid

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from lib.db.base import Base


def _pg_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url.startswith("postgresql+asyncpg://"):
        raise RuntimeError("DATABASE_URL must be postgresql+asyncpg:// for database tests")
    return url


def _pg_database_admin_url() -> str:
    return os.environ.get("ARCREEL_TEST_DATABASE_ADMIN_URL", "").strip() or _pg_database_url()


def _database_role(url: str) -> str:
    role = make_url(url).username
    if not role:
        raise RuntimeError("DATABASE_URL must include a PostgreSQL user")
    return role


def _quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


async def create_pg_test_engine() -> tuple[AsyncEngine, str]:
    url = _pg_database_url()
    admin_url = _pg_database_admin_url()
    app_role = _database_role(url)
    schema = f"test_{uuid.uuid4().hex[:12]}"
    engine = create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": schema}},
    )
    admin_engine = create_async_engine(admin_url, poolclass=NullPool)
    try:
        async with admin_engine.begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {_quote_ident(schema)}"))
            await conn.execute(
                text(f"GRANT USAGE, CREATE ON SCHEMA {_quote_ident(schema)} TO {_quote_ident(app_role)}")
            )
    finally:
        await admin_engine.dispose()
    async with engine.begin() as conn:
        import lib.agent_session_store.models  # noqa: F401
        import lib.db.models  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "INSERT INTO users "
                "(id, username, provider, provider_subject, role, is_active, created_at, updated_at) "
                "VALUES ('default', 'default', 'local', 'default', 'user', true, NOW(), NOW()) "
                "ON CONFLICT (id) DO NOTHING"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO tenants "
                "(id, name, owner_user_id, personal_for_user_id, created_by_user_id, created_at, updated_at) "
                "VALUES ('ten_default', 'Default', 'default', 'default', 'default', NOW(), NOW()) "
                "ON CONFLICT (id) DO NOTHING"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO tenant_memberships "
                "(tenant_id, user_id, role, created_by_user_id, created_at, updated_at) "
                "VALUES ('ten_default', 'default', 'admin', 'default', NOW(), NOW()) "
                "ON CONFLICT (tenant_id, user_id) DO NOTHING"
            )
        )
        for user_id in ("user-a", "user-b", "camel:alice", "camel:bob"):
            await conn.execute(
                text(
                    "INSERT INTO users "
                    "(id, username, provider, provider_subject, role, is_active, created_at, updated_at) "
                    "VALUES (:id, :id, 'test', :id, 'user', true, NOW(), NOW()) "
                    "ON CONFLICT (id) DO NOTHING"
                ).bindparams(id=user_id)
            )
        for tenant_id in ("ten_alpha", "ten_beta", "ten_team", "ten_other"):
            await conn.execute(
                text(
                    "INSERT INTO tenants "
                    "(id, name, owner_user_id, personal_for_user_id, created_by_user_id, created_at, updated_at) "
                    "VALUES (:id, :id, 'default', NULL, 'default', NOW(), NOW()) "
                    "ON CONFLICT (id) DO NOTHING"
                ).bindparams(id=tenant_id)
            )
    return engine, schema


async def drop_pg_test_engine(engine: AsyncEngine, schema: str) -> None:
    try:
        admin_engine = create_async_engine(_pg_database_admin_url(), poolclass=NullPool)
        try:
            async with admin_engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {_quote_ident(schema)} CASCADE"))
        finally:
            await admin_engine.dispose()
    finally:
        await engine.dispose()


async def create_pg_test_engine_with_cleanup() -> AsyncEngine:
    engine, schema = await create_pg_test_engine()
    _ = schema
    return engine
