import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lib.config.repository import ProviderConfigRepository, SystemSettingRepository
from tests.pg_utils import create_pg_test_engine, drop_pg_test_engine


@pytest.fixture
async def session():
    engine, schema = await create_pg_test_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        s.info["tenant_id"] = "ten_default"
        s.info["user_id"] = "default"
        yield s
    await drop_pg_test_engine(engine, schema)


# --- ProviderConfigRepository ---


async def test_set_and_get(session: AsyncSession):
    repo = ProviderConfigRepository(session)
    await repo.set("gemini-aistudio", "api_key", "AIza-test", is_secret=True)
    config = await repo.get_all("gemini-aistudio")
    assert config == {"api_key": "AIza-test"}


async def test_set_overwrites(session: AsyncSession):
    repo = ProviderConfigRepository(session)
    await repo.set("gemini-aistudio", "api_key", "old", is_secret=True)
    await repo.set("gemini-aistudio", "api_key", "new", is_secret=True)
    config = await repo.get_all("gemini-aistudio")
    assert config == {"api_key": "new"}


async def test_delete(session: AsyncSession):
    repo = ProviderConfigRepository(session)
    await repo.set("grok", "api_key", "xai-test", is_secret=True)
    await repo.delete("grok", "api_key")
    config = await repo.get_all("grok")
    assert config == {}


async def test_get_secrets_masked(session: AsyncSession):
    repo = ProviderConfigRepository(session)
    await repo.set("gemini-aistudio", "api_key", "AIzaSyD-longkey123", is_secret=True)
    await repo.set("gemini-aistudio", "base_url", "https://example.com", is_secret=False)
    masked = await repo.get_all_masked("gemini-aistudio")
    assert masked["api_key"]["is_set"] is True
    assert "AIzaSyD" not in masked["api_key"]["masked"]  # value is masked
    assert masked["base_url"]["is_set"] is True
    assert masked["base_url"]["value"] == "https://example.com"


async def test_get_configured_keys(session: AsyncSession):
    repo = ProviderConfigRepository(session)
    await repo.set("ark", "api_key", "ark-test", is_secret=True)
    keys = await repo.get_configured_keys("ark")
    assert keys == ["api_key"]


async def test_provider_config_is_scoped_by_tenant(session: AsyncSession):
    repo_a = ProviderConfigRepository(session, tenant_id="ten_alpha")
    repo_b = ProviderConfigRepository(session, tenant_id="ten_beta")

    await repo_a.set("gemini-aistudio", "api_key", "AIza-user-a-secret", is_secret=True)
    await repo_a.set("gemini-aistudio", "base_url", "https://a.example.com", is_secret=False)
    await repo_b.set("gemini-aistudio", "api_key", "AIza-user-b-secret", is_secret=True)
    await repo_b.set("gemini-aistudio", "base_url", "https://b.example.com", is_secret=False)
    await repo_b.set("ark", "api_key", "ark-user-b-secret", is_secret=True)

    assert await repo_a.get_all("gemini-aistudio") == {
        "api_key": "AIza-user-a-secret",
        "base_url": "https://a.example.com",
    }
    assert await repo_b.get_all("gemini-aistudio") == {
        "api_key": "AIza-user-b-secret",
        "base_url": "https://b.example.com",
    }

    masked_a = await repo_a.get_all_masked("gemini-aistudio")
    masked_b = await repo_b.get_all_masked("gemini-aistudio")
    assert masked_a["api_key"]["is_set"] is True
    assert masked_a["api_key"]["masked"] != "AIza-user-a-secret"
    assert masked_a["base_url"]["value"] == "https://a.example.com"
    assert masked_b["api_key"]["is_set"] is True
    assert masked_b["api_key"]["masked"] != "AIza-user-b-secret"
    assert masked_b["base_url"]["value"] == "https://b.example.com"

    assert set(await repo_a.get_configured_keys("gemini-aistudio")) == {"api_key", "base_url"}
    assert set(await repo_b.get_configured_keys("gemini-aistudio")) == {"api_key", "base_url"}
    assert await repo_a.get_all_configs_bulk() == {
        "gemini-aistudio": {
            "api_key": "AIza-user-a-secret",
            "base_url": "https://a.example.com",
        }
    }
    assert await repo_b.get_all_configs_bulk() == {
        "gemini-aistudio": {
            "api_key": "AIza-user-b-secret",
            "base_url": "https://b.example.com",
        },
        "ark": {"api_key": "ark-user-b-secret"},
    }
    bulk_keys_a = await repo_a.get_all_configured_keys_bulk()
    bulk_keys_b = await repo_b.get_all_configured_keys_bulk()
    assert set(bulk_keys_a["gemini-aistudio"]) == {"api_key", "base_url"}
    assert set(bulk_keys_b["gemini-aistudio"]) == {"api_key", "base_url"}
    assert set(bulk_keys_b["ark"]) == {"api_key"}

    await repo_a.delete("gemini-aistudio", "api_key")
    assert await repo_a.get_all("gemini-aistudio") == {"base_url": "https://a.example.com"}
    assert await repo_b.get_all("gemini-aistudio") == {
        "api_key": "AIza-user-b-secret",
        "base_url": "https://b.example.com",
    }

    await repo_b.delete("gemini-aistudio", "base_url")
    assert await repo_a.get_all("gemini-aistudio") == {"base_url": "https://a.example.com"}
    assert await repo_b.get_all("gemini-aistudio") == {"api_key": "AIza-user-b-secret"}


# --- SystemSettingRepository ---


async def test_setting_set_and_get(session: AsyncSession):
    repo = SystemSettingRepository(session)
    await repo.set("default_video_backend", "gemini-vertex/veo-3.1-fast-generate-001")
    val = await repo.get("default_video_backend")
    assert val == "gemini-vertex/veo-3.1-fast-generate-001"


async def test_setting_get_default(session: AsyncSession):
    repo = SystemSettingRepository(session)
    val = await repo.get("nonexistent", default="fallback")
    assert val == "fallback"


async def test_setting_get_all(session: AsyncSession):
    repo = SystemSettingRepository(session)
    await repo.set("key1", "val1")
    await repo.set("key2", "val2")
    all_settings = await repo.get_all()
    assert all_settings == {"key1": "val1", "key2": "val2"}


async def test_setting_is_scoped_by_tenant(session: AsyncSession):
    repo_a = SystemSettingRepository(session, tenant_id="ten_alpha")
    repo_b = SystemSettingRepository(session, tenant_id="ten_beta")
    await repo_a.set("default_video_backend", "custom-1/model-a")
    await repo_b.set("default_video_backend", "custom-2/model-b")

    assert await repo_a.get("default_video_backend") == "custom-1/model-a"
    assert await repo_b.get("default_video_backend") == "custom-2/model-b"
    assert await repo_a.get_all() == {"default_video_backend": "custom-1/model-a"}
    assert await repo_b.get_all() == {"default_video_backend": "custom-2/model-b"}
