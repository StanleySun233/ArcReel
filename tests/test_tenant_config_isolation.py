from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lib.config.service import ConfigService
from lib.db.models import Tenant, TenantMembership, User
from lib.db.repositories.agent_credential_repo import AgentCredentialRepository
from lib.db.repositories.api_key_repository import ApiKeyRepository
from lib.db.repositories.credential_repository import CredentialRepository
from lib.db.repositories.custom_provider_repo import CustomProviderRepository
from server.services.camel_bootstrap import complete_camel_provider_bootstrap, get_camel_bootstrap_status


async def _add_user(async_session, user_id: str = "camel:owner") -> None:
    async_session.add(
        User(
            id=user_id,
            username="owner",
            provider="camel",
            provider_subject=user_id.removeprefix("camel:"),
            role="user",
            is_active=True,
        )
    )
    await async_session.flush()


async def _add_tenant(
    async_session,
    tenant_id: str,
    user_id: str = "camel:owner",
    *,
    personal: bool = False,
) -> None:
    async_session.add(
        Tenant(
            id=tenant_id,
            name=tenant_id,
            owner_user_id=user_id,
            personal_for_user_id=user_id if personal else None,
            created_by_user_id=user_id,
        )
    )
    await async_session.flush()
    async_session.add(
        TenantMembership(
            tenant_id=tenant_id,
            user_id=user_id,
            role="admin",
            created_by_user_id=user_id,
        )
    )
    await async_session.flush()


async def _add_user_with_two_tenants(async_session) -> None:
    await _add_user(async_session)
    await _add_tenant(async_session, "ten_alpha")
    await _add_tenant(async_session, "ten_beta")


@pytest.mark.asyncio
async def test_provider_config_and_system_settings_are_tenant_scoped(async_session):
    await _add_user_with_two_tenants(async_session)

    alpha = ConfigService(async_session, user_id="camel:owner", tenant_id="ten_alpha")
    beta = ConfigService(async_session, user_id="camel:owner", tenant_id="ten_beta")
    await alpha.set_provider_config("openai", "api_key", "alpha-secret")
    await alpha.set_setting("default_text_backend", "openai/alpha-model")

    assert await alpha.get_provider_config("openai") == {"api_key": "alpha-secret"}
    assert await beta.get_provider_config("openai") == {}
    assert await beta.get_setting("default_text_backend", "") == ""


@pytest.mark.asyncio
async def test_provider_credentials_are_tenant_scoped(async_session):
    await _add_user_with_two_tenants(async_session)

    alpha = CredentialRepository(async_session, user_id="camel:owner", tenant_id="ten_alpha")
    beta = CredentialRepository(async_session, user_id="camel:owner", tenant_id="ten_beta")
    created = await alpha.create("openai", "shared-name", api_key="alpha-key")

    assert created.tenant_id == "ten_alpha"
    assert await alpha.has_active_credential("openai") is True
    assert await beta.has_active_credential("openai") is False


@pytest.mark.asyncio
async def test_custom_providers_and_models_are_tenant_scoped(async_session):
    await _add_user_with_two_tenants(async_session)

    alpha = CustomProviderRepository(async_session, user_id="camel:owner", tenant_id="ten_alpha")
    beta = CustomProviderRepository(async_session, user_id="camel:owner", tenant_id="ten_beta")
    provider = await alpha.create_provider(
        display_name="Tenant Provider",
        discovery_format="openai",
        base_url="https://alpha.example.com",
        api_key="alpha-key",
        models=[
            {
                "model_id": "alpha-model",
                "display_name": "Alpha Model",
                "endpoint": "openai-chat",
                "is_default": True,
                "is_enabled": True,
            }
        ],
    )
    models = await alpha.list_models(provider.id)

    assert provider.tenant_id == "ten_alpha"
    assert models[0].tenant_id == "ten_alpha"
    assert await beta.list_providers() == []
    assert await beta.list_models(provider.id) == []


@pytest.mark.asyncio
async def test_agent_anthropic_credentials_are_tenant_scoped(async_session):
    await _add_user_with_two_tenants(async_session)

    alpha = AgentCredentialRepository(async_session, tenant_id="ten_alpha")
    beta = AgentCredentialRepository(async_session, tenant_id="ten_beta")
    created = await alpha.create(
        preset_id="deepseek",
        display_name="Alpha Agent",
        base_url="https://alpha.example.com",
        api_key="alpha-key",
        user_id="camel:owner",
    )
    await alpha.set_active(created.id, user_id="camel:owner")

    assert created.tenant_id == "ten_alpha"
    assert await alpha.get_active(user_id="camel:owner") is not None
    assert await beta.get_active(user_id="camel:owner") is None


@pytest.mark.asyncio
async def test_api_key_names_are_unique_per_tenant(async_session):
    await _add_user_with_two_tenants(async_session)

    alpha = ApiKeyRepository(async_session, user_id="camel:owner", tenant_id="ten_alpha")
    beta = ApiKeyRepository(async_session, user_id="camel:owner", tenant_id="ten_beta")
    expires_at = datetime.now(UTC) + timedelta(days=1)
    await alpha.create(
        name="same-name",
        key_hash="alpha-hash",
        key_prefix="arc-ten_alpha",
        expires_at=expires_at,
        user_id="camel:owner",
        tenant_id="ten_alpha",
    )
    await beta.create(
        name="same-name",
        key_hash="beta-hash",
        key_prefix="arc-ten_beta",
        expires_at=expires_at,
        user_id="camel:owner",
        tenant_id="ten_beta",
    )

    assert [row["name"] for row in await alpha.list_all()] == ["same-name"]
    assert [row["name"] for row in await beta.list_all()] == ["same-name"]


@pytest.mark.asyncio
async def test_camel_bootstrap_status_uses_current_tenant_state(async_session, monkeypatch):
    await _add_user_with_two_tenants(async_session)
    user = await async_session.get(User, "camel:owner")
    user.camel_provider_bootstrap_completed_at = datetime.now(UTC)
    await async_session.flush()
    monkeypatch.setenv("CAMEL_ARCREEL_PROVIDER_BASE_URL", "https://camel.example.com")
    monkeypatch.setenv("CAMEL_ARCREEL_TOKEN_PROVISION_URL", "https://camel.example.com/provision")
    monkeypatch.setenv("CAMEL_ARCREEL_TOKEN_LINK_TEMPLATE", "https://camel.example.com/tokens/{token_name}")
    monkeypatch.setenv("CAMEL_ARCREEL_IMAGE_ENDPOINT", "openai-images")
    monkeypatch.setenv("CAMEL_ARCREEL_IMAGE_MODELS", "image-model")
    monkeypatch.setenv("CAMEL_ARCREEL_TEXT_ENDPOINT", "openai-chat")
    monkeypatch.setenv("CAMEL_ARCREEL_TEXT_MODELS", "text-model")
    monkeypatch.setenv("CAMEL_ARCREEL_VIDEO_ENDPOINT", "openai-video")
    monkeypatch.setenv("CAMEL_ARCREEL_VIDEO_MODELS", "video-model")
    monkeypatch.setenv("CAMEL_ARCREEL_AUDIO_ENDPOINT", "openai-tts")
    monkeypatch.setenv("CAMEL_ARCREEL_AUDIO_MODELS", "audio-model")

    status = await get_camel_bootstrap_status(async_session, "camel:owner", tenant_id="ten_beta")

    assert status["needed"] is True
    assert status["completed"] is False


@pytest.mark.asyncio
async def test_camel_bootstrap_without_selected_tenant_writes_personal_tenant(async_session, monkeypatch):
    await _add_user(async_session)
    await _add_tenant(async_session, "ten_personal", personal=True)
    await _add_tenant(async_session, "ten_team")
    monkeypatch.setenv("CAMEL_ARCREEL_PROVIDER_BASE_URL", "https://camel.example.com")
    monkeypatch.setenv("CAMEL_ARCREEL_TOKEN_PROVISION_URL", "https://camel.example.com/provision")
    monkeypatch.setenv("CAMEL_ARCREEL_TOKEN_LINK_TEMPLATE", "https://camel.example.com/tokens/{token_name}")
    monkeypatch.setenv("CAMEL_ARCREEL_IMAGE_ENDPOINT", "openai-images")
    monkeypatch.setenv("CAMEL_ARCREEL_IMAGE_MODELS", "image-model")
    monkeypatch.setenv("CAMEL_ARCREEL_TEXT_ENDPOINT", "openai-chat")
    monkeypatch.setenv("CAMEL_ARCREEL_TEXT_MODELS", "text-model")
    monkeypatch.setenv("CAMEL_ARCREEL_VIDEO_ENDPOINT", "openai-video")
    monkeypatch.setenv("CAMEL_ARCREEL_VIDEO_MODELS", "video-model")
    monkeypatch.setenv("CAMEL_ARCREEL_AUDIO_ENDPOINT", "openai-tts")
    monkeypatch.setenv("CAMEL_ARCREEL_AUDIO_MODELS", "audio-model")

    async def fake_request(settings, access_token, mode, idempotency_key):
        return {
            "success": True,
            "tokens": [
                {"media": media, "name": f"camel-arcreel-owner-{media}", "key": f"sk-{media}"}
                for media in ("image", "text", "video", "audio")
            ],
        }

    monkeypatch.setattr("server.services.camel_bootstrap._request_camel_tokens", fake_request)

    result = await complete_camel_provider_bootstrap(
        async_session,
        user_id="camel:owner",
        camel_user_id="owner",
        access_token="camel-oauth-token",
        mode="create",
        idempotency_key="idem-1",
    )

    personal_repo = CustomProviderRepository(async_session, user_id="camel:owner", tenant_id="ten_personal")
    team_repo = CustomProviderRepository(async_session, user_id="camel:owner", tenant_id="ten_team")
    personal_config = ConfigService(async_session, user_id="camel:owner", tenant_id="ten_personal")
    team_config = ConfigService(async_session, user_id="camel:owner", tenant_id="ten_team")

    assert result["completed"] is True
    assert [provider.display_name for provider in await personal_repo.list_providers()] == [
        "CaMeL Image",
        "CaMeL Text",
        "CaMeL Video",
        "CaMeL Audio",
    ]
    assert await team_repo.list_providers() == []
    assert await personal_config.get_setting("default_text_backend", "") != ""
    assert await team_config.get_setting("default_text_backend", "") == ""


@pytest.mark.asyncio
async def test_camel_bootstrap_with_selected_tenant_writes_selected_tenant(async_session, monkeypatch):
    await _add_user(async_session)
    await _add_tenant(async_session, "ten_personal", personal=True)
    await _add_tenant(async_session, "ten_team")
    monkeypatch.setenv("CAMEL_ARCREEL_PROVIDER_BASE_URL", "https://camel.example.com")
    monkeypatch.setenv("CAMEL_ARCREEL_TOKEN_PROVISION_URL", "https://camel.example.com/provision")
    monkeypatch.setenv("CAMEL_ARCREEL_TOKEN_LINK_TEMPLATE", "https://camel.example.com/tokens/{token_name}")
    monkeypatch.setenv("CAMEL_ARCREEL_IMAGE_ENDPOINT", "openai-images")
    monkeypatch.setenv("CAMEL_ARCREEL_IMAGE_MODELS", "image-model")
    monkeypatch.setenv("CAMEL_ARCREEL_TEXT_ENDPOINT", "openai-chat")
    monkeypatch.setenv("CAMEL_ARCREEL_TEXT_MODELS", "text-model")
    monkeypatch.setenv("CAMEL_ARCREEL_VIDEO_ENDPOINT", "openai-video")
    monkeypatch.setenv("CAMEL_ARCREEL_VIDEO_MODELS", "video-model")
    monkeypatch.setenv("CAMEL_ARCREEL_AUDIO_ENDPOINT", "openai-tts")
    monkeypatch.setenv("CAMEL_ARCREEL_AUDIO_MODELS", "audio-model")

    async def fake_request(settings, access_token, mode, idempotency_key):
        return {
            "success": True,
            "tokens": [
                {"media": media, "name": f"camel-arcreel-owner-{media}", "key": f"sk-{media}"}
                for media in ("image", "text", "video", "audio")
            ],
        }

    monkeypatch.setattr("server.services.camel_bootstrap._request_camel_tokens", fake_request)

    result = await complete_camel_provider_bootstrap(
        async_session,
        user_id="camel:owner",
        tenant_id="ten_team",
        camel_user_id="owner",
        access_token="camel-oauth-token",
        mode="create",
        idempotency_key="idem-1",
    )

    personal_repo = CustomProviderRepository(async_session, user_id="camel:owner", tenant_id="ten_personal")
    team_repo = CustomProviderRepository(async_session, user_id="camel:owner", tenant_id="ten_team")
    personal_config = ConfigService(async_session, user_id="camel:owner", tenant_id="ten_personal")
    team_config = ConfigService(async_session, user_id="camel:owner", tenant_id="ten_team")

    assert result["completed"] is True
    assert await personal_repo.list_providers() == []
    assert [provider.display_name for provider in await team_repo.list_providers()] == [
        "CaMeL Image",
        "CaMeL Text",
        "CaMeL Video",
        "CaMeL Audio",
    ]
    assert await personal_config.get_setting("default_text_backend", "") == ""
    assert await team_config.get_setting("default_text_backend", "") != ""
