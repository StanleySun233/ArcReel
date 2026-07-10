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
async def test_arc_prefixed_token_does_not_use_issued_token_auth():
    with (
        patch("server.auth._verify_api_key") as verify_api_key,
        patch("server.auth.verify_token", return_value=None) as verify_jwt,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await auth_module._verify_and_get_payload_async("arc-ten_1-secret")

    assert exc_info.value.status_code == 401
    verify_api_key.assert_not_called()
    verify_jwt.assert_called_once_with("arc-ten_1-secret")
