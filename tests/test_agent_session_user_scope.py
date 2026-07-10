import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from lib.db.base import Base, DEFAULT_USER_ID
from lib.user_scope import set_current_user_id
from server.agent_runtime.event_log import EventLogStore
from server.agent_runtime.session_store import SessionMetaStore


@pytest.fixture()
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()
    set_current_user_id(DEFAULT_USER_ID)


@pytest.mark.asyncio
async def test_agent_session_metadata_and_event_log_are_scoped_by_current_user(session_factory):
    meta_store = SessionMetaStore(session_factory=session_factory)
    event_store = EventLogStore(session_factory=session_factory)

    set_current_user_id("camel:alice")
    await meta_store.create("project-a", "session-a")
    await event_store.append_user_entry(
        "session-a",
        {"type": "user", "uuid": "alice-message", "content": [{"type": "text", "text": "alice"}]},
    )

    set_current_user_id("camel:bob")
    await meta_store.create("project-b", "session-b")
    await event_store.append_user_entry(
        "session-b",
        {"type": "user", "uuid": "bob-message", "content": [{"type": "text", "text": "bob"}]},
    )

    assert [session.id for session in await meta_store.list()] == ["session-b"]
    assert await meta_store.get("session-a") is None
    assert await event_store.list_after("session-a") == []
    assert (await event_store.list_after("session-b"))[0]["uuid"] == "bob-message"

    set_current_user_id("camel:alice")
    assert [session.id for session in await meta_store.list()] == ["session-a"]
    assert await meta_store.get("session-b") is None
    assert await event_store.list_after("session-b") == []
    assert (await event_store.list_after("session-a"))[0]["uuid"] == "alice-message"
