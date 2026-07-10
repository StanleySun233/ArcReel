import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


@pytest.mark.asyncio
async def test_database_url_role_does_not_bypass_rls():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url.startswith("postgresql+asyncpg://"):
        raise RuntimeError("DATABASE_URL must be postgresql+asyncpg:// for PostgreSQL app-role tests")

    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text("SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
                )
            ).one()
    finally:
        await engine.dispose()

    assert row.rolsuper is False
    assert row.rolbypassrls is False
