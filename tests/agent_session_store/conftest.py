"""Fixtures for agent_session_store tests."""

from __future__ import annotations

import os
import uuid as _uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lib.db.base import Base


def _pg_url_from_env() -> str:
    """Return the required PostgreSQL+asyncpg DATABASE_URL."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgresql+asyncpg://"):
        return url
    raise RuntimeError("DATABASE_URL must be postgresql+asyncpg:// for agent session store tests")


_PG_TEST_USER_IDS = ("default", "u1", "conformance", "e2e", "crash-recover", "long-turn")


async def _create_pg_engine():
    schema = f"test_{_uuid.uuid4().hex[:12]}"
    engine = create_async_engine(
        _pg_url_from_env(),
        poolclass=pool.NullPool,
        connect_args={"server_settings": {"search_path": schema}},
    )
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    async with engine.begin() as conn:
        import lib.agent_session_store.models  # noqa: F401
        import lib.db.models  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)
    await _seed_pg_users(engine)
    return engine, schema


async def _drop_pg_engine(engine, schema: str) -> None:
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    finally:
        await engine.dispose()


async def _seed_pg_users(engine) -> None:
    async with engine.begin() as conn:
        for uid in _PG_TEST_USER_IDS:
            await conn.execute(
                text(
                    "INSERT INTO users (id, username, role, is_active, created_at, updated_at) "
                    "VALUES (:id, :username, 'user', true, NOW(), NOW()) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"id": uid, "username": uid},
            )


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Session factory with all tables created in an isolated PostgreSQL schema."""
    engine, schema = await _create_pg_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await _drop_pg_engine(engine, schema)


@pytest.fixture
async def file_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Session factory with independent PostgreSQL connections for concurrency tests."""
    engine, schema = await _create_pg_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await _drop_pg_engine(engine, schema)
