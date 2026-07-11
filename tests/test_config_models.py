import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lib.db.models.config import ProviderConfig, SystemSetting
from tests.pg_utils import create_pg_test_engine, drop_pg_test_engine


@pytest.fixture
async def session():
    engine, schema = await create_pg_test_engine()
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as s:
        yield s
    await drop_pg_test_engine(engine, schema)


async def test_provider_config_crud(session: AsyncSession):
    row = ProviderConfig(
        provider="gemini-aistudio",
        key="api_key",
        value="AIza-test",
        is_secret=True,
    )
    session.add(row)
    await session.flush()

    result = await session.execute(select(ProviderConfig).where(ProviderConfig.provider == "gemini-aistudio"))
    found = result.scalar_one()
    assert found.key == "api_key"
    assert found.value == "AIza-test"
    assert found.is_secret is True
    assert found.updated_at is not None


async def test_provider_config_unique_constraint(session: AsyncSession):
    row1 = ProviderConfig(provider="gemini-aistudio", key="api_key", value="v1", is_secret=True)
    row2 = ProviderConfig(provider="gemini-aistudio", key="api_key", value="v2", is_secret=True)
    session.add(row1)
    await session.flush()
    session.add(row2)
    with pytest.raises(Exception):  # IntegrityError
        await session.flush()


async def test_system_setting_crud(session: AsyncSession):
    row = SystemSetting(key="default_video_backend", value="gemini-vertex/veo-3.1-fast-generate-001")
    session.add(row)
    await session.flush()

    result = await session.execute(select(SystemSetting).where(SystemSetting.key == "default_video_backend"))
    found = result.scalar_one()
    assert found.value == "gemini-vertex/veo-3.1-fast-generate-001"
