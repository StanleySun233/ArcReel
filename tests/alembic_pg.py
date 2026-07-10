from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class AlembicPostgresDb:
    cfg: Config
    url: str
    schema: str
    rls_role: str

    def execute(self, sql: str, params: dict | None = None) -> None:
        asyncio.run(_execute(self.url, self.schema, sql, params))

    def execute_with_settings(self, settings: dict[str, str], sql: str, params: dict | None = None) -> None:
        asyncio.run(_execute_with_settings(self.url, self.schema, settings, sql, params))

    def execute_as_rls_role_with_settings(
        self, settings: dict[str, str], sql: str, params: dict | None = None
    ) -> None:
        asyncio.run(_execute_with_settings(self.url, self.schema, settings, sql, params, self.rls_role))

    def fetchall(self, sql: str, params: dict | None = None):
        return asyncio.run(_fetchall(self.url, self.schema, sql, params))

    def fetchall_as_rls_role(self, sql: str, params: dict | None = None):
        return asyncio.run(_fetchall(self.url, self.schema, sql, params, self.rls_role))

    def fetchall_with_settings(self, settings: dict[str, str], sql: str, params: dict | None = None):
        return asyncio.run(_fetchall_with_settings(self.url, self.schema, settings, sql, params))

    def fetchall_as_rls_role_with_settings(
        self, settings: dict[str, str], sql: str, params: dict | None = None
    ):
        return asyncio.run(_fetchall_with_settings(self.url, self.schema, settings, sql, params, self.rls_role))

    def grant_rls_role(self) -> None:
        asyncio.run(_grant_rls_role(self.url, self.schema, self.rls_role))

    def scalar(self, sql: str, params: dict | None = None):
        return asyncio.run(_scalar(self.url, self.schema, sql, params))

    def columns(self, table_name: str) -> set[str]:
        rows = self.fetchall(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table_name",
            {"schema": self.schema, "table_name": table_name},
        )
        return {r.column_name for r in rows}


@pytest.fixture
def alembic_pg(monkeypatch: pytest.MonkeyPatch) -> Iterator[AlembicPostgresDb]:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url.startswith("postgresql+asyncpg://"):
        raise RuntimeError("DATABASE_URL must be postgresql+asyncpg:// for Alembic tests")

    suffix = uuid.uuid4().hex[:12]
    schema = f"test_{suffix}"
    rls_role = f"rls_{suffix}"
    asyncio.run(_create_schema(url, schema))
    asyncio.run(_create_role(url, rls_role))
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ARCREEL_TEST_DB_SCHEMA", schema)

    cfg = Config()
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    try:
        yield AlembicPostgresDb(cfg=cfg, url=url, schema=schema, rls_role=rls_role)
    finally:
        asyncio.run(_drop_schema(url, schema))
        asyncio.run(_drop_role(url, rls_role))


def _engine(url: str, schema: str):
    return create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": schema}},
    )


async def _create_schema(url: str, schema: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    finally:
        await engine.dispose()


async def _create_role(url: str, role: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(sa.text(f'CREATE ROLE "{role}"'))
    finally:
        await engine.dispose()


async def _drop_role(url: str, role: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(sa.text(f'DROP ROLE IF EXISTS "{role}"'))
    finally:
        await engine.dispose()


async def _grant_rls_role(url: str, schema: str, role: str) -> None:
    engine = _engine(url, schema)
    try:
        async with engine.begin() as conn:
            await conn.execute(sa.text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
            await conn.execute(
                sa.text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"')
            )
            await conn.execute(sa.text(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA "{schema}" TO "{role}"'))
    finally:
        await engine.dispose()


async def _drop_schema(url: str, schema: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    finally:
        await engine.dispose()


async def _execute(url: str, schema: str, sql: str, params: dict | None = None) -> None:
    engine = _engine(url, schema)
    try:
        async with engine.begin() as conn:
            await conn.execute(sa.text(sql), params or {})
    finally:
        await engine.dispose()


async def _apply_role_and_settings(conn, settings: dict[str, str], role: str | None = None) -> None:
    if role is not None:
        await conn.execute(sa.text(f'SET LOCAL ROLE "{role}"'))
    for name, value in settings.items():
        await conn.execute(sa.text("SELECT set_config(:name, :value, true)"), {"name": name, "value": value})


async def _execute_with_settings(
    url: str, schema: str, settings: dict[str, str], sql: str, params: dict | None = None, role: str | None = None
) -> None:
    engine = _engine(url, schema)
    try:
        async with engine.begin() as conn:
            await _apply_role_and_settings(conn, settings, role)
            await conn.execute(sa.text(sql), params or {})
    finally:
        await engine.dispose()


async def _fetchall(url: str, schema: str, sql: str, params: dict | None = None, role: str | None = None):
    engine = _engine(url, schema)
    try:
        async with engine.begin() as conn:
            if role is not None:
                await conn.execute(sa.text(f'SET LOCAL ROLE "{role}"'))
            result = await conn.execute(sa.text(sql), params or {})
            return result.fetchall()
    finally:
        await engine.dispose()


async def _fetchall_with_settings(
    url: str, schema: str, settings: dict[str, str], sql: str, params: dict | None = None, role: str | None = None
):
    engine = _engine(url, schema)
    try:
        async with engine.begin() as conn:
            await _apply_role_and_settings(conn, settings, role)
            result = await conn.execute(sa.text(sql), params or {})
            return result.fetchall()
    finally:
        await engine.dispose()


async def _scalar(url: str, schema: str, sql: str, params: dict | None = None):
    engine = _engine(url, schema)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(sa.text(sql), params or {})
            return result.scalar_one()
    finally:
        await engine.dispose()
