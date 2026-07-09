from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from fastapi import FastAPI

from server.auth import CurrentUserInfo, get_current_user
from server.routers import camel_bootstrap
from server.services import camel_auth

AUTH_TOKEN_SECRET = "oauth-test-secret-32-bytes-long-value"


def configure_oauth_env(monkeypatch):
    monkeypatch.setenv("AUTH_TOKEN_SECRET", AUTH_TOKEN_SECRET)
    monkeypatch.setenv("CAMEL_OAUTH_BASE_URL", "https://camel.example.com")
    monkeypatch.setenv("CAMEL_OAUTH_INTERNAL_BASE_URL", "http://camel-internal:3000")
    monkeypatch.setenv("CAMEL_OAUTH_CLIENT_ID", "arc-client")
    monkeypatch.setenv("CAMEL_OAUTH_CLIENT_SECRET", "arc-secret")
    monkeypatch.setenv("CAMEL_OAUTH_REDIRECT_URI", "https://arcreel.example.com/api/v1/auth/camel/callback")
    monkeypatch.setenv("CAMEL_OAUTH_BOOTSTRAP_SCOPES", "profile email arcreel:token-provision")
    monkeypatch.setenv("CAMEL_OAUTH_REPAIR_MAX_AGE_SECONDS", "120")


def build_app() -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: CurrentUserInfo(
        id="camel:123",
        sub="camel-user",
        provider="camel",
        role="admin",
    )
    app.include_router(camel_bootstrap.router, prefix="/api/v1")
    return app


async def post_start_url(app: FastAPI, params: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        return await client.post("/api/v1/camel/bootstrap/start-url", params=params)


def decoded_state_cookie(response):
    raw_cookie = response.cookies.get(camel_auth.CAMEL_STATE_COOKIE_NAME)
    assert raw_cookie
    return jwt.decode(raw_cookie, AUTH_TOKEN_SECRET, algorithms=["HS256"])


def authorization_query(response):
    authorization_url = response.json()["authorization_url"]
    parts = urlsplit(authorization_url)
    assert parts.scheme == "https"
    assert parts.netloc == "camel.example.com"
    assert parts.path == "/api/oauth/provider/authorize"
    return parse_qs(parts.query)


def test_camel_oauth_settings_use_internal_base_for_server_side_urls(monkeypatch):
    configure_oauth_env(monkeypatch)

    settings = camel_auth.get_camel_oauth_settings()

    assert settings.authorize_url == "https://camel.example.com/api/oauth/provider/authorize"
    assert settings.token_url == "http://camel-internal:3000/api/oauth/provider/token"
    assert settings.userinfo_url == "http://camel-internal:3000/api/oauth/provider/userinfo"


@pytest.mark.asyncio
async def test_start_url_create_returns_authorization_url_and_provider_bootstrap_state_cookie(monkeypatch):
    configure_oauth_env(monkeypatch)

    response = await post_start_url(build_app(), {"mode": "create", "from": "/app/projects?camel=1"})

    assert response.status_code == 200
    assert "authorization_url" in response.json()
    assert camel_auth.CAMEL_STATE_COOKIE_NAME in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    query = authorization_query(response)
    state_payload = decoded_state_cookie(response)
    assert query["client_id"] == ["arc-client"]
    assert query["redirect_uri"] == ["https://arcreel.example.com/api/v1/auth/camel/callback"]
    assert query["scope"] == ["profile email arcreel:token-provision"]
    assert "max_age" not in query
    assert state_payload["intent"] == "provider_bootstrap"
    assert state_payload["user_id"] == "camel:123"
    assert state_payload["from"] == "/app/projects?camel=1"
    assert state_payload["state"] == query["state"][0]
    assert state_payload["idempotency_key"].startswith("arc-bootstrap-")


@pytest.mark.asyncio
async def test_start_url_repair_returns_authorization_url_and_provider_repair_state_cookie(monkeypatch):
    configure_oauth_env(monkeypatch)

    response = await post_start_url(build_app(), {"mode": "repair", "from": "/app/settings?section=account"})

    assert response.status_code == 200
    assert "authorization_url" in response.json()
    query = authorization_query(response)
    state_payload = decoded_state_cookie(response)
    assert query["scope"] == ["profile email arcreel:token-provision"]
    assert query["max_age"] == ["120"]
    assert state_payload["intent"] == "provider_repair"
    assert state_payload["user_id"] == "camel:123"
    assert state_payload["from"] == "/app/settings?section=account"
    assert state_payload["state"] == query["state"][0]
