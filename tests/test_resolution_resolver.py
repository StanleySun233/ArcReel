"""测试 resolve_resolution 按 project → legacy → custom default → None 顺序解析。"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from lib.user_scope import current_identity_scope
from server.services.resolution_resolver import _from_project, get_custom_resolution_default, resolve_resolution

# --- 纯项目字典路径（同步即可） ---


def test_from_project_returns_none_when_nothing_configured():
    assert _from_project({}, "gemini-aistudio", "veo-3.1-lite-generate-preview") is None


def test_from_project_legacy_only():
    project = {"video_model_settings": {"veo-3.1": {"resolution": "1080p"}}}
    assert _from_project(project, "gemini-aistudio", "veo-3.1") == "1080p"


def test_from_project_model_settings_overrides_legacy():
    project = {
        "model_settings": {"gemini-aistudio/veo-3.1": {"resolution": "720p"}},
        "video_model_settings": {"veo-3.1": {"resolution": "1080p"}},
    }
    assert _from_project(project, "gemini-aistudio", "veo-3.1") == "720p"


def test_from_project_empty_string_override_treated_as_unset():
    project = {"model_settings": {"p/m": {"resolution": ""}}}
    assert _from_project(project, "p", "m") is None


def test_from_project_composite_key_format_uses_slash():
    project = {"model_settings": {"a/b": {"resolution": "4K"}}}
    assert _from_project(project, "a", "b") == "4K"
    assert _from_project(project, "a-b", "") is None


def test_from_project_tolerates_null_entries():
    # project.json 可能被手编为 null 值；既不应崩也不应当作已配置。
    project = {
        "model_settings": {"a/b": None},
        "video_model_settings": {"m": None},
    }
    assert _from_project(project, "a", "b") is None
    assert _from_project(project, "x", "m") is None


# --- 包含 custom default 的 async 集成路径 ---


@pytest.mark.asyncio
async def test_resolve_returns_none_when_nothing_configured():
    assert await resolve_resolution({}, "gemini-aistudio", "veo-3.1") is None


@pytest.mark.asyncio
async def test_resolve_returns_custom_default_when_only_custom():
    with patch(
        "server.services.resolution_resolver.get_custom_resolution_default",
        return_value="720p",
    ):
        assert await resolve_resolution({}, "custom-1", "my-model") == "720p"


@pytest.mark.asyncio
async def test_resolve_project_override_wins_over_custom_default():
    project = {"model_settings": {"custom-1/m": {"resolution": "2K"}}}
    with patch(
        "server.services.resolution_resolver.get_custom_resolution_default",
        return_value="1K",
    ) as mock_custom:
        assert await resolve_resolution(project, "custom-1", "m") == "2K"
        mock_custom.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_legacy_wins_over_custom_default():
    project = {"video_model_settings": {"m": {"resolution": "1080p"}}}
    with patch(
        "server.services.resolution_resolver.get_custom_resolution_default",
        return_value="720p",
    ) as mock_custom:
        assert await resolve_resolution(project, "custom-1", "m") == "1080p"
        mock_custom.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_falls_through_to_custom_when_project_empty_string():
    project = {"model_settings": {"custom-1/m": {"resolution": ""}}}
    with patch(
        "server.services.resolution_resolver.get_custom_resolution_default",
        return_value="1K",
    ):
        assert await resolve_resolution(project, "custom-1", "m") == "1K"


@pytest.mark.asyncio
async def test_custom_default_passes_current_tenant_to_repository(monkeypatch):
    captured = {}

    @asynccontextmanager
    async def fake_session_factory():
        yield object()

    class FakeRepo:
        def __init__(self, session, *, user_id=None, tenant_id=None):
            captured["user_id"] = user_id
            captured["tenant_id"] = tenant_id

        async def get_model_by_ids(self, provider_id, model_id):
            captured["provider_id"] = provider_id
            captured["model_id"] = model_id
            return SimpleNamespace(resolution="720p")

    monkeypatch.setattr("lib.db.async_session_factory", fake_session_factory)
    monkeypatch.setattr("lib.db.repositories.custom_provider_repo.CustomProviderRepository", FakeRepo)

    with current_identity_scope(user_id="camel:16", tenant_id="ten_9979"):
        assert await get_custom_resolution_default("custom-1", "model-a") == "720p"

    assert captured == {
        "user_id": "camel:16",
        "tenant_id": "ten_9979",
        "provider_id": 1,
        "model_id": "model-a",
    }


@pytest.mark.asyncio
async def test_custom_default_uses_endpoint_family_fallback_when_resolution_unset(monkeypatch):
    @asynccontextmanager
    async def fake_session_factory():
        yield object()

    class FakeRepo:
        def __init__(self, session, *, user_id=None, tenant_id=None):
            pass

        async def get_model_by_ids(self, provider_id, model_id):
            return SimpleNamespace(resolution=None, endpoint="ark-seedance")

    monkeypatch.setattr("lib.db.async_session_factory", fake_session_factory)
    monkeypatch.setattr("lib.db.repositories.custom_provider_repo.CustomProviderRepository", FakeRepo)

    with current_identity_scope(user_id="camel:16", tenant_id="ten_9979"):
        assert await get_custom_resolution_default("custom-1", "doubao-seedance-2-0-260128") == "720p"
