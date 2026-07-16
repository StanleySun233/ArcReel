from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from fastapi import FastAPI
from starlette.responses import RedirectResponse

from server.auth import CurrentUserInfo, get_current_user
from server.routers import auth as auth_router
from server.routers import camel_bootstrap
from server.services import camel_auth
from server.services.camel_auth import CamelOAuthExchange, CamelOAuthState
from server.services.tenant_auth import TenantAccess

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


def build_app(monkeypatch: pytest.MonkeyPatch | None = None) -> FastAPI:
    if monkeypatch is not None:

        async def fake_require_tenant_access(*args, **kwargs):
            return TenantAccess(id="ten_test", name="测试空间", role="admin", is_owner=True, personal=True)

        monkeypatch.setattr(camel_bootstrap, "require_tenant_access", fake_require_tenant_access)

    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: CurrentUserInfo(
        id="camel:123",
        sub="camel-user",
        provider="camel",
        role="admin",
        tenant_id="ten_test",
        tenant_role="admin",
    )
    app.include_router(camel_bootstrap.router, prefix="/api/v1")
    return app


async def post_start_url(
    app: FastAPI,
    params: dict[str, str],
    base_url: str = "https://testserver",
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=base_url) as client:
        return await client.post("/api/v1/camel/bootstrap/start-url", params=params, headers=headers)


async def get_login_start_url(app: FastAPI, base_url: str = "https://arcreel.example.com") -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=base_url) as client:
        return await client.get("/api/v1/auth/camel/start?from=/app/projects", follow_redirects=False)


def decoded_state_cookie(response):
    query = authorization_query(response)
    raw_cookie = response.cookies.get(camel_auth._state_cookie_name(query["state"][0]))
    assert raw_cookie
    return jwt.decode(raw_cookie, AUTH_TOKEN_SECRET, algorithms=["HS256"])


def authorization_query(response):
    authorization_url = response.json()["authorization_url"]
    parts = urlsplit(authorization_url)
    assert parts.scheme == "https"
    assert parts.netloc == "camel.example.com"
    assert parts.path == "/api/oauth/provider/authorize"
    return parse_qs(parts.query)


def login_authorization_query(response):
    parts = urlsplit(response.headers["location"])
    assert parts.scheme == "https"
    assert parts.netloc == "camel.example.com"
    assert parts.path == "/api/oauth/provider/authorize"
    return parse_qs(parts.query)


class _SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_camel_oauth_settings_use_internal_base_for_server_side_urls(monkeypatch):
    configure_oauth_env(monkeypatch)

    settings = camel_auth.get_camel_oauth_settings()

    assert settings.authorize_url == "https://camel.example.com/api/oauth/provider/authorize"
    assert settings.token_url == "http://camel-internal:3000/api/oauth/provider/token"
    assert settings.userinfo_url == "http://camel-internal:3000/api/oauth/provider/userinfo"


@pytest.mark.asyncio
async def test_login_callback_creates_personal_tenant_and_returns_tenant_token(monkeypatch, async_session):
    configure_oauth_env(monkeypatch)
    state = CamelOAuthState(
        nonce="state-123",
        intent="login",
        return_path="/app/projects",
        redirect_uri="https://arcreel.example.com/api/v1/auth/camel/callback",
    )

    async def fake_fetch(settings, code, redirect_uri):
        assert code == "oauth-code"
        assert redirect_uri == "https://arcreel.example.com/api/v1/auth/camel/callback"
        return CamelOAuthExchange(access_token="camel-access", userinfo={"id": "123", "username": "alice"})

    monkeypatch.setattr(camel_auth, "_fetch_camel_exchange", fake_fetch)
    monkeypatch.setattr(camel_auth, "async_session_factory", lambda: _SessionContext(async_session))

    response = await camel_auth.complete_camel_oauth_callback(
        "oauth-code",
        "state-123",
        {camel_auth._state_cookie_name("state-123"): camel_auth._encode_state_cookie(state)},
    )

    location = response.headers["location"]
    fragment = parse_qs(urlsplit(location).fragment)
    token = fragment["access_token"][0]
    payload = jwt.decode(token, AUTH_TOKEN_SECRET, algorithms=["HS256"])
    assert payload["user_id"] == "camel:123"
    assert payload["provider"] == "camel"
    assert payload["tenant_id"].startswith("ten_")
    assert payload["tenant_role"] == "admin"


@pytest.mark.asyncio
async def test_login_callback_accepts_server_state_when_browser_cookie_missing(monkeypatch):
    configure_oauth_env(monkeypatch)
    app = FastAPI()
    app.include_router(auth_router.router, prefix="/api/v1")
    start_response = await get_login_start_url(app)
    query = login_authorization_query(start_response)
    state = query["state"][0]

    async def fake_fetch(settings, code, redirect_uri):
        assert code == "oauth-code"
        assert redirect_uri == "https://arcreel.example.com/api/v1/auth/camel/callback"
        return CamelOAuthExchange(access_token="camel-access", userinfo={"id": "123", "username": "alice"})

    async def fake_handle_login(userinfo, oauth_state):
        assert userinfo["id"] == "123"
        assert oauth_state.nonce == state
        assert oauth_state.return_path == "/app/projects"
        return RedirectResponse("/ok")

    monkeypatch.setattr(camel_auth, "_fetch_camel_exchange", fake_fetch)
    monkeypatch.setattr(camel_auth, "_handle_login_intent", fake_handle_login)

    response = await camel_auth.complete_camel_oauth_callback("oauth-code", state, {})

    assert response.headers["location"] == "/ok"


@pytest.mark.asyncio
async def test_start_url_create_returns_authorization_url_and_provider_bootstrap_state_cookie(monkeypatch):
    configure_oauth_env(monkeypatch)

    response = await post_start_url(build_app(monkeypatch), {"mode": "create", "from": "/app/projects?camel=1"})

    assert response.status_code == 200
    assert "authorization_url" in response.json()
    assert camel_auth.CAMEL_STATE_COOKIE_NAME in response.headers["set-cookie"]
    assert camel_auth.CAMEL_STATE_COOKIE_PREFIX in response.headers["set-cookie"]
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


def test_state_cookie_lookup_prefers_state_specific_cookie(monkeypatch):
    configure_oauth_env(monkeypatch)
    first_state = CamelOAuthState(
        nonce="state-first",
        intent="login",
        return_path="/app/projects",
        redirect_uri="https://arcreel.example.com/api/v1/auth/camel/callback",
    )
    second_state = CamelOAuthState(
        nonce="state-second",
        intent="login",
        return_path="/app/projects",
        redirect_uri="https://arcreel.example.com/api/v1/auth/camel/callback",
    )

    cookie = camel_auth._state_cookie_from_request(
        "state-first",
        {
            camel_auth._state_cookie_name("state-first"): camel_auth._encode_state_cookie(first_state),
            camel_auth.CAMEL_STATE_COOKIE_NAME: camel_auth._encode_state_cookie(second_state),
        },
    )
    decoded = camel_auth._decode_state_cookie("state-first", cookie)

    assert decoded.nonce == "state-first"


@pytest.mark.asyncio
async def test_start_url_uses_current_allowed_host_for_redirect_uri(monkeypatch):
    configure_oauth_env(monkeypatch)
    monkeypatch.delenv("CAMEL_OAUTH_REDIRECT_URI")
    monkeypatch.setenv("CAMEL_OAUTH_REDIRECT_HOSTS", "dream.camel-hub.com,dream.camel-hub.cn")

    response = await post_start_url(
        build_app(monkeypatch),
        {"mode": "create", "from": "/app/projects"},
        base_url="http://dream.camel-hub.cn",
        headers={"x-forwarded-proto": "https"},
    )

    assert response.status_code == 200
    query = authorization_query(response)
    state_payload = decoded_state_cookie(response)
    assert query["redirect_uri"] == ["https://dream.camel-hub.cn/api/v1/auth/camel/callback"]
    assert state_payload["redirect_uri"] == "https://dream.camel-hub.cn/api/v1/auth/camel/callback"


@pytest.mark.asyncio
async def test_start_url_rejects_invalid_forwarded_proto(monkeypatch):
    configure_oauth_env(monkeypatch)
    monkeypatch.delenv("CAMEL_OAUTH_REDIRECT_URI")
    monkeypatch.setenv("CAMEL_OAUTH_REDIRECT_HOSTS", "dream.camel-hub.cn")

    response = await post_start_url(
        build_app(monkeypatch),
        {"mode": "create", "from": "/app/projects"},
        base_url="http://dream.camel-hub.cn",
        headers={"x-forwarded-proto": "javascript"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid OAuth redirect scheme"


@pytest.mark.asyncio
async def test_start_url_repair_returns_authorization_url_and_provider_repair_state_cookie(monkeypatch):
    configure_oauth_env(monkeypatch)

    response = await post_start_url(build_app(monkeypatch), {"mode": "repair", "from": "/app/settings?section=account"})

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
