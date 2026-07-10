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

    def execute(self, sql: str, params: dict | None = None) -> None:
        asyncio.run(_execute(self.url, self.schema, sql, params))

    def fetchall(self, sql: str, params: dict | None = None):
        return asyncio.run(_fetchall(self.url, self.schema, sql, params))

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

    schema = f"test_{uuid.uuid4().hex[:12]}"
    asyncio.run(_create_schema(url, schema))
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ARCREEL_TEST_DB_SCHEMA", schema)

    cfg = Config()
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    try:
        yield AlembicPostgresDb(cfg=cfg, url=url, schema=schema)
    finally:
        asyncio.run(_drop_schema(url, schema))


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


async def _fetchall(url: str, schema: str, sql: str, params: dict | None = None):
    engine = _engine(url, schema)
    try:
        async with engine.begin() as conn:
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
