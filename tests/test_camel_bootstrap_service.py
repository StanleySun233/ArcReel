from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lib.config.service import ConfigService
from lib.custom_provider import make_provider_id
from lib.db.base import Base
from lib.db.models.user import User
from lib.db.repositories.custom_provider_repo import CustomProviderRepository


def configure_bootstrap_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMEL_ARCREEL_PROVIDER_BASE_URL", "https://api.camel-hub.com")
    monkeypatch.setenv("CAMEL_ARCREEL_TOKEN_PROVISION_URL", "https://api.camel-hub.com/api/arcreel/tokens")
    monkeypatch.setenv("CAMEL_ARCREEL_TOKEN_LINK_TEMPLATE", "https://camel-hub.com/token?keyword={token_name}")
    monkeypatch.setenv("CAMEL_ARCREEL_IMAGE_ENDPOINT", "openai-images")
    monkeypatch.setenv("CAMEL_ARCREEL_TEXT_ENDPOINT", "openai-chat")
    monkeypatch.setenv("CAMEL_ARCREEL_VIDEO_ENDPOINT", "ark-seedance")
    monkeypatch.setenv("CAMEL_ARCREEL_AUDIO_ENDPOINT", "openai-tts")
    monkeypatch.setenv("CAMEL_ARCREEL_IMAGE_MODELS", "camel-image")
    monkeypatch.setenv("CAMEL_ARCREEL_TEXT_MODELS", "camel-text")
    monkeypatch.setenv("CAMEL_ARCREEL_VIDEO_MODELS", "doubao-seedance-2-0-260128")
    monkeypatch.setenv("CAMEL_ARCREEL_AUDIO_MODELS", "camel-audio")


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sm() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_camel_bootstrap_creates_user_owned_providers_and_defaults(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.services import camel_bootstrap

    configure_bootstrap_env(monkeypatch)

    async def fake_request(settings, access_token, mode, idempotency_key):
        assert access_token == "camel-oauth-token"
        assert mode == "create"
        assert idempotency_key == "idem-1"
        return {
            "success": True,
            "tokens": [
                {"media": media, "name": f"camel-arcreel-123-{media}", "key": f"sk-{media}"}
                for media in ("image", "text", "video", "audio")
            ],
        }

    monkeypatch.setattr(camel_bootstrap, "_request_camel_tokens", fake_request)

    session.add(User(id="camel:123", username="camel-user", role="user", is_active=True))
    await session.flush()

    result = await camel_bootstrap.complete_camel_provider_bootstrap(
        session,
        user_id="camel:123",
        camel_user_id="123",
        access_token="camel-oauth-token",
        mode="create",
        idempotency_key="idem-1",
    )

    assert result["completed"] is True
    repo = CustomProviderRepository(session, user_id="camel:123")
    providers = await repo.list_providers()
    assert [p.display_name for p in providers] == ["CaMeL Image", "CaMeL Text", "CaMeL Video", "CaMeL Audio"]
    assert {p.display_name: p.api_key for p in providers} == {
        "CaMeL Image": "sk-image",
        "CaMeL Text": "sk-text",
        "CaMeL Video": "sk-video",
        "CaMeL Audio": "sk-audio",
    }

    service = ConfigService(session, user_id="camel:123")
    by_name = {p.display_name: p for p in providers}
    assert await service.get_setting("default_image_backend_t2i") == f"{make_provider_id(by_name['CaMeL Image'].id)}/camel-image"
    assert await service.get_setting("default_text_backend") == f"{make_provider_id(by_name['CaMeL Text'].id)}/camel-text"
    assert await service.get_setting("default_video_backend") == (
        f"{make_provider_id(by_name['CaMeL Video'].id)}/doubao-seedance-2-0-260128"
    )
    assert await service.get_setting("default_audio_backend") == f"{make_provider_id(by_name['CaMeL Audio'].id)}/camel-audio"

    user = (await session.execute(select(User).where(User.id == "camel:123"))).scalar_one()
    assert user.camel_provider_bootstrap_completed_at is not None


@pytest.mark.asyncio
async def test_camel_bootstrap_conflict_does_not_create_local_providers(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.services import camel_bootstrap

    configure_bootstrap_env(monkeypatch)

    async def fake_request(settings, access_token, mode, idempotency_key):
        return {
            "success": False,
            "error": "token_name_conflict",
            "conflicts": [
                {
                    "media": "video",
                    "token_name": "camel-arcreel-123-video",
                    "delete_url": "https://camel-hub.com/token?keyword=camel-arcreel-123-video",
                }
            ],
        }

    monkeypatch.setattr(camel_bootstrap, "_request_camel_tokens", fake_request)

    session.add(User(id="camel:123", username="camel-user", role="user", is_active=True))
    await session.flush()

    result = await camel_bootstrap.complete_camel_provider_bootstrap(
        session,
        user_id="camel:123",
        camel_user_id="123",
        access_token="camel-oauth-token",
        mode="create",
        idempotency_key="idem-1",
    )

    assert result == {
        "completed": False,
        "error": "camel_token_conflict",
        "conflicts": [
            {
                "media": "video",
                "token_name": "camel-arcreel-123-video",
                "delete_url": "https://camel-hub.com/token?keyword=camel-arcreel-123-video",
            }
        ],
    }
    assert await CustomProviderRepository(session, user_id="camel:123").list_providers() == []


@pytest.mark.asyncio
async def test_camel_bootstrap_partial_failure_returns_created_token_links(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.services import camel_bootstrap

    configure_bootstrap_env(monkeypatch)

    async def fake_request(settings, access_token, mode, idempotency_key):
        return {
            "success": True,
            "tokens": [
                {"media": media, "name": f"camel-arcreel-123-{media}", "key": f"sk-{media}"}
                for media in ("image", "text", "video", "audio")
            ],
        }

    async def fail_upsert(*args, **kwargs):
        raise RuntimeError("db failed")

    monkeypatch.setattr(camel_bootstrap, "_request_camel_tokens", fake_request)
    monkeypatch.setattr(camel_bootstrap, "_upsert_provider", fail_upsert)

    session.add(User(id="camel:123", username="camel-user", role="user", is_active=True))
    await session.flush()

    with pytest.raises(camel_bootstrap.CamelLocalBootstrapError) as excinfo:
        await camel_bootstrap.complete_camel_provider_bootstrap(
            session,
            user_id="camel:123",
            camel_user_id="123",
            access_token="camel-oauth-token",
            mode="create",
            idempotency_key="idem-1",
        )

    assert excinfo.value.result["completed"] is False
    assert excinfo.value.result["error"] == "partial_bootstrap_failed"
    assert excinfo.value.result["created_tokens"] == [
        {
            "media": media,
            "token_name": f"camel-arcreel-123-{media}",
            "delete_url": f"https://camel-hub.com/token?keyword=camel-arcreel-123-{media}",
        }
        for media in ("image", "text", "video", "audio")
    ]
