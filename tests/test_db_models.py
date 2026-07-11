"""Tests for ORM model definitions — verify tables can be created."""

import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import lib.db.models  # noqa: F401 — ensure all models registered for Base.metadata
from lib.db.base import Base, TenantOwnedMixin, TimestampMixin, UserOwnedMixin
from lib.db.models import AgentSession, Task, Tenant, TenantMembership, User


@pytest.fixture
async def engine():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url.startswith("postgresql+asyncpg://"):
        raise RuntimeError("DATABASE_URL must be postgresql+asyncpg:// for database model tests")
    schema = f"test_{uuid.uuid4().hex[:12]}"
    eng = create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": schema}},
    )
    async with eng.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    try:
        async with eng.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    finally:
        await eng.dispose()


@pytest.fixture
async def session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(id="default", username="admin", provider="local", provider_subject="default"))
        await session.flush()
        session.add(
            Tenant(
                id="ten_test",
                name="Test Tenant",
                owner_user_id="default",
                personal_for_user_id="default",
                created_by_user_id="default",
            )
        )
        await session.flush()
        session.add(
            TenantMembership(tenant_id="ten_test", user_id="default", role="admin", created_by_user_id="default")
        )
        await session.commit()
        yield session


class TestModelsCreateTables:
    async def test_all_tables_exist(self, engine):
        async with engine.connect() as conn:
            table_names = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
        assert "tasks" in table_names
        assert "task_events" in table_names
        assert "worker_lease" in table_names
        assert "api_calls" in table_names
        assert "agent_sessions" in table_names

    async def test_task_round_trip(self, session):
        now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        task = Task(
            task_id="abc123",
            project_name="demo",
            task_type="storyboard",
            media_type="image",
            resource_id="E1S01",
            status="queued",
            queued_at=now,
            updated_at=now,
            tenant_id="ten_test",
        )
        session.add(task)
        await session.commit()

        from sqlalchemy import select

        result = await session.execute(select(Task).where(Task.task_id == "abc123"))
        loaded = result.scalar_one()
        assert loaded.project_name == "demo"
        assert loaded.status == "queued"

    async def test_agent_session_round_trip(self, session):
        now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        s = AgentSession(
            id="sess123",
            sdk_session_id="sdk-sess123",
            project_name="demo",
            status="idle",
            created_at=now,
            updated_at=now,
        )
        session.add(s)
        await session.commit()

        from sqlalchemy import select

        result = await session.execute(select(AgentSession).where(AgentSession.id == "sess123"))
        loaded = result.scalar_one()
        assert loaded.project_name == "demo"


class TestUserModel:
    async def test_user_model_columns(self, engine):
        """Verify User table has correct columns."""
        async with engine.connect() as conn:
            columns = await conn.run_sync(
                lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("users")}
            )
        assert columns == {
            "id",
            "username",
            "provider",
            "provider_subject",
            "role",
            "is_active",
            "camel_provider_bootstrap_completed_at",
            "created_at",
            "updated_at",
        }

    async def test_user_round_trip(self, session):
        user = User(id="u1", username="alice", provider="camel", provider_subject="u1")
        session.add(user)
        await session.commit()

        result = await session.execute(select(User).where(User.id == "u1"))
        loaded = result.scalar_one()
        assert loaded.username == "alice"
        assert loaded.role == "user"  # server_default
        assert loaded.created_at is not None
        assert loaded.updated_at is not None


class TestTimestampMixin:
    def test_timestamp_mixin_defaults(self):
        """Verify TimestampMixin provides default and onupdate."""
        assert hasattr(TimestampMixin, "created_at")
        assert hasattr(TimestampMixin, "updated_at")
        # Access the underlying Column via MappedColumn.column
        col_created = TimestampMixin.__dict__["created_at"].column
        col_updated = TimestampMixin.__dict__["updated_at"].column
        assert col_created.default is not None
        assert col_updated.default is not None
        assert col_updated.onupdate is not None


class TestUserOwnedMixin:
    def test_user_owned_mixin_server_default(self):
        """Verify UserOwnedMixin has server_default='default'."""
        col = UserOwnedMixin.__dict__["user_id"].column
        assert col.server_default is not None
        assert col.server_default.arg == "default"


class TestTenantOwnedMixin:
    def test_tenant_owned_mixin_has_tenant_id(self):
        col = TenantOwnedMixin.__dict__["tenant_id"].column
        assert col.foreign_keys


class TestMixinApplicationToModels:
    """Verify Mixin columns are present on ORM models after refactoring."""

    async def test_task_has_user_id(self, engine):
        async with engine.connect() as conn:
            columns = await conn.run_sync(
                lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("tasks")}
            )
        assert "user_id" in columns
        assert "tenant_id" in columns

    async def test_api_call_has_timestamp_and_user_id(self, engine):
        """ApiCall should have created_at (NOT NULL), updated_at, and user_id from Mixins."""
        async with engine.connect() as conn:
            col_info = await conn.run_sync(
                lambda sync_conn: {c["name"]: c for c in inspect(sync_conn).get_columns("api_calls")}
            )
        assert "created_at" in col_info
        assert col_info["created_at"]["nullable"] is False
        assert "updated_at" in col_info
        assert "user_id" in col_info
        assert "tenant_id" in col_info

    async def test_api_key_has_timestamp_and_user_id(self, engine):
        """ApiKey should have updated_at and user_id from Mixins."""
        async with engine.connect() as conn:
            columns = await conn.run_sync(
                lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("api_keys")}
            )
        assert "updated_at" in columns
        assert "user_id" in columns
        assert "tenant_id" in columns

    async def test_agent_session_has_timestamp_and_user_id(self, engine):
        """AgentSession should have created_at, updated_at, and user_id from Mixins."""
        async with engine.connect() as conn:
            columns = await conn.run_sync(
                lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("agent_sessions")}
            )
        assert "created_at" in columns
        assert "updated_at" in columns
        assert "user_id" in columns

    async def test_task_event_no_user_id(self, engine):
        async with engine.connect() as conn:
            columns = await conn.run_sync(
                lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("task_events")}
            )
        assert "user_id" not in columns
        assert "tenant_id" in columns

    async def test_worker_lease_no_user_id(self, engine):
        """WorkerLease should NOT have user_id — it was not given UserOwnedMixin."""
        async with engine.connect() as conn:
            columns = await conn.run_sync(
                lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("worker_lease")}
            )
        assert "user_id" not in columns
