from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lib.config.service import ConfigService
from lib.custom_provider import make_provider_id
from lib.db.base import Base
from lib.db.models import Tenant, TenantMembership
from lib.db.models.user import User
from lib.db.repositories.agent_credential_repo import AgentCredentialRepository
from lib.db.repositories.custom_provider_repo import CustomProviderRepository

CAMEL_ARCREEL_ENV_KEYS = (
    "CAMEL_ARCREEL_PROVIDER_BASE_URL",
    "CAMEL_ARCREEL_TOKEN_PROVISION_URL",
    "CAMEL_ARCREEL_TOKEN_LINK_TEMPLATE",
    "CAMEL_ARCREEL_IMAGE_ENDPOINT",
    "CAMEL_ARCREEL_TEXT_ENDPOINT",
    "CAMEL_ARCREEL_VIDEO_ENDPOINT",
    "CAMEL_ARCREEL_AUDIO_ENDPOINT",
    "CAMEL_ARCREEL_ANTHROPIC_ENDPOINT",
    "CAMEL_ARCREEL_IMAGE_MODELS",
    "CAMEL_ARCREEL_TEXT_MODELS",
    "CAMEL_ARCREEL_VIDEO_MODELS",
    "CAMEL_ARCREEL_AUDIO_MODELS",
    "CAMEL_ARCREEL_ANTHROPIC_MODELS",
)


def configure_bootstrap_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMEL_ARCREEL_PROVIDER_BASE_URL", "https://api.camel-hub.com")
    monkeypatch.setenv("CAMEL_ARCREEL_TOKEN_PROVISION_URL", "https://api.camel-hub.com/api/arcreel/tokens")
    monkeypatch.setenv("CAMEL_ARCREEL_TOKEN_LINK_TEMPLATE", "https://camel-hub.com/token?keyword={token_name}")
    monkeypatch.setenv("CAMEL_ARCREEL_IMAGE_ENDPOINT", "openai-images")
    monkeypatch.setenv("CAMEL_ARCREEL_TEXT_ENDPOINT", "openai-chat")
    monkeypatch.setenv("CAMEL_ARCREEL_VIDEO_ENDPOINT", "ark-seedance")
    monkeypatch.setenv("CAMEL_ARCREEL_AUDIO_ENDPOINT", "openai-tts")
    monkeypatch.setenv("CAMEL_ARCREEL_IMAGE_MODELS", "gpt-image-2")
    monkeypatch.setenv("CAMEL_ARCREEL_TEXT_MODELS", "gpt-5.5")
    monkeypatch.setenv("CAMEL_ARCREEL_VIDEO_MODELS", "doubao-seedance-2-0-260128")
    monkeypatch.setenv("CAMEL_ARCREEL_AUDIO_MODELS", "gpt-4o-mini-tts")
    monkeypatch.setenv("CAMEL_ARCREEL_ANTHROPIC_MODELS", "claude-opus-4-8")


def clear_bootstrap_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in CAMEL_ARCREEL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def camel_user(*, completed_at: datetime | None = None) -> User:
    return User(
        id="camel:123",
        username="camel-user",
        provider="camel",
        provider_subject="123",
        role="user",
        is_active=True,
        camel_provider_bootstrap_completed_at=completed_at,
    )


async def add_camel_user_with_personal_tenant(
    session: AsyncSession,
    *,
    completed_at: datetime | None = None,
) -> None:
    session.add(camel_user(completed_at=completed_at))
    session.add(
        Tenant(
            id="ten_camel_123",
            name="camel-user的个人空间",
            owner_user_id="camel:123",
            personal_for_user_id="camel:123",
            created_by_user_id="camel:123",
        )
    )
    session.add(
        TenantMembership(
            tenant_id="ten_camel_123",
            user_id="camel:123",
            role="admin",
            created_by_user_id="camel:123",
        )
    )
    session.info["user_id"] = "camel:123"
    session.info["tenant_id"] = "ten_camel_123"
    await session.flush()


def bypass_pg_tenant_context(monkeypatch: pytest.MonkeyPatch, camel_bootstrap) -> None:
    async def fake_set_tenant_context(session: AsyncSession, *, user_id: str, tenant_id: str) -> None:
        session.info["user_id"] = user_id
        session.info["tenant_id"] = tenant_id

    monkeypatch.setattr(camel_bootstrap, "set_tenant_context", fake_set_tenant_context)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sm() as s:
        yield s
    await engine.dispose()


def test_camel_bootstrap_settings_derive_from_oauth_minimal_env(monkeypatch: pytest.MonkeyPatch):
    from server.services.camel_bootstrap import get_camel_bootstrap_settings

    clear_bootstrap_env(monkeypatch)
    monkeypatch.setenv("CAMEL_OAUTH_BASE_URL", "https://camel.example.com")
    monkeypatch.setenv("CAMEL_OAUTH_INTERNAL_BASE_URL", "http://camel-internal:3000")

    settings = get_camel_bootstrap_settings()

    assert settings.provider_base_url == "http://camel-internal:3000"
    assert settings.token_provision_url == "http://camel-internal:3000/api/oauth/provider/arcreel-tokens"
    assert settings.token_link_template == "https://camel.example.com/token/{token_name}"
    assert [(spec.media, spec.endpoint, spec.models) for spec in settings.media_specs] == [
        ("image", "openai-images", ("gpt-image-2",)),
        ("text", "openai-chat", ("gpt-5.5",)),
        ("video", "ark-seedance", ("doubao-seedance-2-0-260128",)),
        ("audio", "openai-tts", ("gpt-4o-mini-tts",)),
        ("anthropic", "anthropic-messages", ("claude-opus-4-8",)),
    ]


def test_camel_token_provision_payload_includes_arcreel_owned_media_specs(monkeypatch: pytest.MonkeyPatch):
    from server.services.camel_bootstrap import _camel_token_provision_payload, get_camel_bootstrap_settings

    clear_bootstrap_env(monkeypatch)
    monkeypatch.setenv("CAMEL_OAUTH_BASE_URL", "https://camel.example.com")

    settings = get_camel_bootstrap_settings()

    assert _camel_token_provision_payload(settings, mode="create", idempotency_key="idem-1") == {
        "client": "arcreel",
        "mode": "create",
        "idempotency_key": "idem-1",
        "dry_run": False,
        "media_specs": [
            {"media": "image", "models": ["gpt-image-2"]},
            {"media": "text", "models": ["gpt-5.5"]},
            {"media": "video", "models": ["doubao-seedance-2-0-260128"]},
            {"media": "audio", "models": ["gpt-4o-mini-tts"]},
            {"media": "anthropic", "models": ["claude-opus-4-8"]},
        ],
    }


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
                {
                    "media": media,
                    "name": f"camel-arcreel-123-{media}",
                    "key": f"sk-{media}",
                    "model_limits": [f"camel-returned-{media}"],
                }
                for media in ("image", "text", "video", "audio", "anthropic")
            ],
        }

    monkeypatch.setattr(camel_bootstrap, "_request_camel_tokens", fake_request)
    bypass_pg_tenant_context(monkeypatch, camel_bootstrap)

    await add_camel_user_with_personal_tenant(session)

    result = await camel_bootstrap.complete_camel_provider_bootstrap(
        session,
        user_id="camel:123",
        camel_user_id="123",
        access_token="camel-oauth-token",
        mode="create",
        idempotency_key="idem-1",
    )

    assert result["completed"] is True
    from server.services.camel_auth import _provider_intent_redirect

    redirect_location = _provider_intent_redirect("/app/settings?section=account", result).headers["location"]
    assert "camel_bootstrap=completed" in redirect_location
    assert "sk-image" not in redirect_location
    assert "camel-oauth-token" not in redirect_location

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
    assert (
        await service.get_setting("default_image_backend_t2i")
        == f"{make_provider_id(by_name['CaMeL Image'].id)}/camel-returned-image"
    )
    assert (
        await service.get_setting("default_text_backend")
        == f"{make_provider_id(by_name['CaMeL Text'].id)}/camel-returned-text"
    )
    assert (
        await service.get_setting("text_backend_script")
        == f"{make_provider_id(by_name['CaMeL Text'].id)}/camel-returned-text"
    )
    assert (
        await service.get_setting("text_backend_overview")
        == f"{make_provider_id(by_name['CaMeL Text'].id)}/camel-returned-text"
    )
    assert (
        await service.get_setting("text_backend_style")
        == f"{make_provider_id(by_name['CaMeL Text'].id)}/camel-returned-text"
    )
    assert await service.get_setting("default_video_backend") == (
        f"{make_provider_id(by_name['CaMeL Video'].id)}/camel-returned-video"
    )
    assert (
        await service.get_setting("default_audio_backend")
        == f"{make_provider_id(by_name['CaMeL Audio'].id)}/camel-returned-audio"
    )
    agent_credential = await AgentCredentialRepository(session, tenant_id="ten_camel_123").get_active()
    assert agent_credential is not None
    assert agent_credential.display_name == "CaMeL Agent"
    assert agent_credential.base_url == "https://api.camel-hub.com"
    assert agent_credential.api_key == "sk-anthropic"
    assert agent_credential.model == "camel-returned-anthropic"
    assert agent_credential.subagent_model == "camel-returned-anthropic"

    user = (await session.execute(select(User).where(User.id == "camel:123"))).scalar_one()
    assert user.camel_provider_bootstrap_completed_at is not None


@pytest.mark.asyncio
async def test_camel_bootstrap_status_returns_needed_provider_plan(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.services import camel_bootstrap

    configure_bootstrap_env(monkeypatch)
    await add_camel_user_with_personal_tenant(session)

    result = await camel_bootstrap.get_camel_bootstrap_status(session, "camel:123")

    assert result["needed"] is True
    assert result["completed"] is False
    assert result["camel_user_id"] == "123"
    assert [p["media"] for p in result["providers"]] == ["image", "text", "video", "audio", "anthropic"]
    video = next(p for p in result["providers"] if p["media"] == "video")
    assert video == {
        "media": "video",
        "provider_name": "CaMeL Video",
        "base_url": "https://api.camel-hub.com",
        "endpoint": "ark-seedance",
        "models": ["doubao-seedance-2-0-260128"],
        "token_name": "camel-arcreel-123-video",
    }


@pytest.mark.asyncio
async def test_camel_bootstrap_status_returns_complete_without_provider_plan(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.services import camel_bootstrap

    configure_bootstrap_env(monkeypatch)
    await add_camel_user_with_personal_tenant(session, completed_at=datetime.now(UTC))

    result = await camel_bootstrap.get_camel_bootstrap_status(session, "camel:123")
    assert result["needed"] is True
    assert result["completed"] is False
    assert [p["media"] for p in result["providers"]] == ["image", "text", "video", "audio", "anthropic"]


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
                    "name": "camel-arcreel-123-video",
                    "key": "sk-conflict-secret",
                    "delete_url": "https://camel-hub.com/token?keyword=camel-arcreel-123-video",
                }
            ],
        }

    monkeypatch.setattr(camel_bootstrap, "_request_camel_tokens", fake_request)
    bypass_pg_tenant_context(monkeypatch, camel_bootstrap)

    await add_camel_user_with_personal_tenant(session)

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
    from server.services.camel_auth import _provider_intent_redirect

    redirect_location = _provider_intent_redirect("/app/settings?section=account", result).headers["location"]
    assert "camel_bootstrap=camel_token_conflict" in redirect_location
    assert "sk-conflict-secret" not in redirect_location
    assert "camel-oauth-token" not in redirect_location

    assert await CustomProviderRepository(session, user_id="camel:123").list_providers() == []


@pytest.mark.asyncio
async def test_request_camel_tokens_accepts_structured_400_business_error(monkeypatch: pytest.MonkeyPatch):
    from server.services import camel_bootstrap

    configure_bootstrap_env(monkeypatch)
    settings = camel_bootstrap.get_camel_bootstrap_settings()

    class FakeClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, headers: dict, json: dict):
            return httpx.Response(
                400,
                request=httpx.Request("POST", url),
                json={
                    "success": False,
                    "error": "token_name_conflict",
                    "conflicts": [
                        {
                            "media": "image",
                            "name": "camel-arcreel-123-image",
                            "key": "sk-should-not-be-exposed",
                            "delete_url": "https://camel.example/token/camel-arcreel-123-image",
                        }
                    ],
                },
            )

    monkeypatch.setattr(camel_bootstrap.httpx, "AsyncClient", FakeClient)

    result = await camel_bootstrap._request_camel_tokens(settings, "oauth-token", "create", "idem-1")

    assert result["success"] is False
    assert result["error"] == "token_name_conflict"


@pytest.mark.asyncio
async def test_camel_bootstrap_repair_updates_existing_provider_and_defaults(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.services import camel_bootstrap

    configure_bootstrap_env(monkeypatch)
    await add_camel_user_with_personal_tenant(session)
    repo = CustomProviderRepository(session, user_id="camel:123")
    existing_video = await repo.create_provider(
        display_name="CaMeL Video",
        discovery_format="openai",
        base_url="https://old.example.com",
        api_key="sk-old-video",
        models=[
            {
                "model_id": "old-video",
                "display_name": "old-video",
                "endpoint": "ark-seedance",
                "is_default": True,
                "is_enabled": True,
            }
        ],
    )
    await session.flush()

    async def fake_request(settings, access_token, mode, idempotency_key):
        assert mode == "repair"
        return {
            "success": True,
            "tokens": [
                {"media": media, "name": f"camel-arcreel-123-{media}", "key": f"sk-repair-{media}"}
                for media in ("image", "text", "video", "audio", "anthropic")
            ],
        }

    monkeypatch.setattr(camel_bootstrap, "_request_camel_tokens", fake_request)
    bypass_pg_tenant_context(monkeypatch, camel_bootstrap)

    result = await camel_bootstrap.complete_camel_provider_bootstrap(
        session,
        user_id="camel:123",
        camel_user_id="123",
        access_token="camel-oauth-token",
        mode="repair",
        idempotency_key="idem-2",
    )

    assert result["completed"] is True
    providers = await repo.list_providers()
    assert len(providers) == 4
    by_name = {p.display_name: p for p in providers}
    assert by_name["CaMeL Video"].id == existing_video.id
    assert by_name["CaMeL Video"].api_key == "sk-repair-video"
    assert by_name["CaMeL Video"].base_url == "https://api.camel-hub.com"
    video_models = await repo.list_models(existing_video.id)
    assert [m.model_id for m in video_models] == ["doubao-seedance-2-0-260128"]
    assert await ConfigService(session, user_id="camel:123").get_setting("default_video_backend") == (
        f"{make_provider_id(existing_video.id)}/doubao-seedance-2-0-260128"
    )


@pytest.mark.asyncio
async def test_camel_bootstrap_rejects_user_mismatch_before_provisioning(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.services import camel_bootstrap

    configure_bootstrap_env(monkeypatch)

    async def fail_request(*args, **kwargs):
        raise AssertionError("provisioning should not be called")

    monkeypatch.setattr(camel_bootstrap, "_request_camel_tokens", fail_request)

    with pytest.raises(HTTPException) as excinfo:
        await camel_bootstrap.complete_camel_provider_bootstrap(
            session,
            user_id="camel:123",
            camel_user_id="999",
            access_token="camel-oauth-token",
            mode="create",
            idempotency_key="idem-1",
        )

    assert excinfo.value.status_code == 400


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
                for media in ("image", "text", "video", "audio", "anthropic")
            ],
        }

    async def fail_upsert(*args, **kwargs):
        raise RuntimeError("db failed")

    monkeypatch.setattr(camel_bootstrap, "_request_camel_tokens", fake_request)
    monkeypatch.setattr(camel_bootstrap, "_upsert_provider", fail_upsert)
    bypass_pg_tenant_context(monkeypatch, camel_bootstrap)

    await add_camel_user_with_personal_tenant(session)

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
        for media in ("image", "text", "video", "audio", "anthropic")
    ]
