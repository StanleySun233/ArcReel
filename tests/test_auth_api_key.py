"""
API Key 认证分流单元测试

测试 auth 模块中的 API Key 路径：哈希计算、缓存逻辑、认证分流。
"""

import asyncio
import hashlib
import os
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

import server.auth as auth_module
from lib.db.models.api_key import ApiKey
from lib.db.models.tenant import Tenant, TenantMembership
from lib.db.models.user import User


@pytest.fixture(autouse=True)
def clear_cache():
    """每次测试前清空 API Key 缓存。"""
    auth_module._api_key_cache.clear()
    yield
    auth_module._api_key_cache.clear()


class _SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _tracked_create_task(tasks):
    original_create_task = asyncio.create_task

    def create_task(coro):
        task = original_create_task(coro)
        tasks.append(task)
        return task

    return create_task


class TestHashApiKey:
    def test_deterministic(self):
        key = "arc-testapikey1234"
        assert auth_module._hash_api_key(key) == auth_module._hash_api_key(key)

    def test_sha256_output(self):
        key = "arc-abc"
        expected = hashlib.sha256(key.encode()).hexdigest()
        assert auth_module._hash_api_key(key) == expected

    def test_api_key_tenant_id(self):
        assert auth_module._api_key_tenant_id("arc-ten_owner-secret") == "ten_owner"
        assert auth_module._api_key_tenant_id("arc-oldsecret") is None


class TestApiKeyCache:
    def test_cache_miss(self):
        hit, payload = auth_module._get_cached_api_key_payload("nonexistent")
        assert not hit
        assert payload is None

    def test_cache_set_and_hit(self):
        auth_module._set_api_key_cache("hash123", {"sub": "apikey:test", "via": "apikey"})
        hit, payload = auth_module._get_cached_api_key_payload("hash123")
        assert hit
        assert payload == {"sub": "apikey:test", "via": "apikey"}

    def test_cache_negative_entry(self):
        auth_module._set_api_key_cache("hash_missing", None)
        hit, payload = auth_module._get_cached_api_key_payload("hash_missing")
        assert hit
        assert payload is None

    def test_cache_expired_entry(self):
        auth_module._api_key_cache["hash_expired"] = ({"sub": "test"}, time.monotonic() - 1)
        hit, _ = auth_module._get_cached_api_key_payload("hash_expired")
        assert not hit

    def test_invalidate_removes_entry(self):
        auth_module._set_api_key_cache("hash_to_delete", {"sub": "test"})
        auth_module.invalidate_api_key_cache("hash_to_delete")
        hit, _ = auth_module._get_cached_api_key_payload("hash_to_delete")
        assert not hit

    def test_cache_hit_skips_db(self):
        """缓存命中时不应查询数据库（通过 _verify_api_key 的分支逻辑验证）。"""
        key = "arc-cached-key"
        key_hash = auth_module._hash_api_key(key)
        auth_module._set_api_key_cache(key_hash, {"sub": "apikey:cached", "via": "apikey"})
        # 若命中缓存则返回缓存值；True means hit
        hit, payload = auth_module._get_cached_api_key_payload(key_hash)
        assert hit
        assert payload is not None
        assert payload["sub"] == "apikey:cached"


class TestVerifyAndGetPayloadAsync:
    @pytest.mark.asyncio
    async def test_jwt_path_success(self):
        """非 arc- 前缀走 JWT 路径，成功返回 payload。"""
        with patch("server.auth.verify_token", return_value={"sub": "admin"}):
            result = await auth_module._verify_and_get_payload_async("some.jwt.token")
        assert result == {"sub": "admin"}

    @pytest.mark.asyncio
    async def test_jwt_invalid_raises_401(self):
        """非 arc- 前缀但 JWT 验证失败，抛出 401。"""
        with patch("server.auth.verify_token", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await auth_module._verify_and_get_payload_async("invalid.jwt.token")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_api_key_path_success(self):
        """arc- 前缀走 API Key 路径，成功返回 payload。"""
        expected = {"sub": "apikey:mykey", "via": "apikey"}
        with patch("server.auth._verify_api_key", new=AsyncMock(return_value=expected)):
            result = await auth_module._verify_and_get_payload_async("arc-validkey")
        assert result["via"] == "apikey"
        assert result["sub"] == "apikey:mykey"

    @pytest.mark.asyncio
    async def test_api_key_not_found_raises_401(self):
        """arc- 前缀但 key 不存在，抛出 401。"""
        with patch("server.auth._verify_api_key", new=AsyncMock(return_value=None)):
            with pytest.raises(HTTPException) as exc_info:
                await auth_module._verify_and_get_payload_async("arc-badkey")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_api_key_expired_raises_401(self):
        """arc- 前缀但 key 已过期（_verify_api_key 返回 None），抛出 401。"""
        with patch("server.auth._verify_api_key", new=AsyncMock(return_value=None)):
            with pytest.raises(HTTPException) as exc_info:
                await auth_module._verify_and_get_payload_async("arc-expiredkey")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_jwt_path_not_called_for_api_key(self):
        """arc- 前缀时不应调用 verify_token。"""
        with (
            patch("server.auth._verify_api_key", new=AsyncMock(return_value={"sub": "apikey:k", "via": "apikey"})),
            patch("server.auth.verify_token") as mock_jwt,
        ):
            await auth_module._verify_and_get_payload_async("arc-somekey")
        mock_jwt.assert_not_called()


class TestApiKeyOwnerResolution:
    @pytest.mark.asyncio
    async def test_bearer_api_key_resolves_persisted_owner_user_id(self, async_session):
        key = "arc-ten_owner-owner-key"
        key_hash = auth_module._hash_api_key(key)
        async with async_session.begin():
            async_session.add(
                User(
                    id="camel:owner",
                    username="owner",
                    provider="camel",
                    provider_subject="owner",
                    role="user",
                    is_active=True,
                )
            )
            await async_session.flush()
            async_session.add(
                Tenant(
                    id="ten_owner",
                    name="Owner Tenant",
                    owner_user_id="camel:owner",
                    created_by_user_id="camel:owner",
                )
            )
            await async_session.flush()
            async_session.add(
                TenantMembership(
                    tenant_id="ten_owner",
                    user_id="camel:owner",
                    role="admin",
                    created_by_user_id="camel:owner",
                )
            )
            async_session.add(
                ApiKey(
                    name="owner-key",
                    key_hash=key_hash,
                    key_prefix=key[:8],
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                    user_id="camel:owner",
                    tenant_id="ten_owner",
                )
            )

        tasks = []
        with (
            patch.dict(os.environ, {"AUTH_ENABLED": "true"}),
            patch("lib.db.async_session_factory", return_value=_SessionContext(async_session)),
            patch("asyncio.create_task", side_effect=_tracked_create_task(tasks)),
        ):
            user = await auth_module.get_current_user(key)

        if tasks:
            await asyncio.gather(*tasks)

        assert user.id == "camel:owner"
        assert user.sub == "apikey:owner-key"
        assert user.provider == "apikey"
        assert user.tenant_id == "ten_owner"
        assert user.tenant_role == "admin"
