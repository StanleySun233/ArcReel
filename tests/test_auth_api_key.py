from unittest.mock import patch

import pytest
from fastapi import HTTPException

import server.auth as auth_module


@pytest.mark.asyncio
async def test_jwt_path_success():
    with patch("server.auth.verify_token", return_value={"sub": "admin"}):
        result = await auth_module._verify_and_get_payload_async("some.jwt.token")

    assert result == {"sub": "admin"}


@pytest.mark.asyncio
async def test_invalid_token_raises_401():
    with patch("server.auth.verify_token", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            await auth_module._verify_and_get_payload_async("invalid.jwt.token")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_arc_prefixed_token_returns_403_when_issued_tokens_disabled():
    with (
        patch("server.auth._verify_api_key") as verify_api_key,
        patch("server.auth.verify_token") as verify_jwt,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await auth_module._verify_and_get_payload_async("arc-ten_1-secret")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "feature_disabled"
    verify_api_key.assert_not_called()
    verify_jwt.assert_not_called()
