"""Run the SDK's official 14-contract SessionStore conformance suite."""

from __future__ import annotations

import pytest
from claude_agent_sdk.testing import run_session_store_conformance
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from lib.agent_session_store.store import DbSessionStore
from tests.pg_utils import create_pg_test_engine, drop_pg_test_engine


@pytest.mark.asyncio
async def test_db_session_store_passes_sdk_conformance():
    """DbSessionStore must satisfy all required + optional SessionStore contracts.

    The SDK's conformance suite invokes ``make_store`` once per contract for
    isolation, and reuses the same ``_KEY`` ({project_key="proj",
    session_id="sess"}) across multiple contracts. We therefore build a brand
    new PostgreSQL schema per invocation so contracts don't bleed state.
    """

    engines: list[tuple[object, str]] = []

    async def make_store():
        engine, schema = await create_pg_test_engine()
        engines.append((engine, schema))
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO users "
                    "(id, username, provider, provider_subject, role, is_active, created_at, updated_at) "
                    "VALUES ('conformance', 'conformance', 'camel', 'conformance', 'user', true, NOW(), NOW()) "
                    "ON CONFLICT (id) DO NOTHING"
                )
            )
            await conn.execute(
                text(
                    "INSERT INTO tenants "
                    "(id, name, owner_user_id, personal_for_user_id, created_by_user_id, created_at, updated_at) "
                    "VALUES ('ten_default', 'Default', 'conformance', 'conformance', 'conformance', NOW(), NOW()) "
                    "ON CONFLICT (id) DO NOTHING"
                )
            )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        return DbSessionStore(factory, user_id="conformance")

    try:
        await run_session_store_conformance(make_store)
    finally:
        for engine, schema in engines:
            await drop_pg_test_engine(engine, schema)
