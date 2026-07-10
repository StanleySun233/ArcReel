from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Literal, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
import jwt
from fastapi import HTTPException
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import RedirectResponse

from lib.db import async_session_factory
from lib.db.models.user import User
from server.auth import create_token, get_token_secret
from server.services.tenant_auth import ensure_personal_tenant, read_tenant_access

CAMEL_STATE_COOKIE_NAME = "arcreel_camel_oauth_state"
CAMEL_STATE_COOKIE_PREFIX = f"{CAMEL_STATE_COOKIE_NAME}_"
CAMEL_STATE_TTL_SECONDS = 600
CAMEL_OAUTH_CALLBACK_PATH = "/api/v1/auth/camel/callback"
CamelOAuthIntent = Literal["login", "provider_bootstrap", "provider_repair"]


@dataclass(frozen=True)
class CamelOAuthSettings:
    base_url: str
    internal_base_url: str
    client_id: str
    client_secret: str
    redirect_uri: str
    redirect_hosts: tuple[str, ...]
    scopes: str
    bootstrap_scopes: str
    repair_max_age_seconds: str

    @property
    def configured(self) -> bool:
        return bool(
            self.base_url and self.client_id and self.client_secret and (self.redirect_uri or self.redirect_hosts)
        )

    @property
    def authorize_url(self) -> str:
        return f"{self.base_url}/api/oauth/provider/authorize"

    @property
    def token_url(self) -> str:
        return f"{self.internal_base_url}/api/oauth/provider/token"

    @property
    def userinfo_url(self) -> str:
        return f"{self.internal_base_url}/api/oauth/provider/userinfo"


@dataclass(frozen=True)
class CamelOAuthState:
    nonce: str
    intent: CamelOAuthIntent
    return_path: str
    redirect_uri: str
    user_id: str | None = None
    tenant_id: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class CamelLocalUser:
    id: str
    username: str
    camel_user_id: str


@dataclass(frozen=True)
class CamelOAuthExchange:
    access_token: str
    userinfo: dict


def get_camel_oauth_settings() -> CamelOAuthSettings:
    base_url = os.environ.get("CAMEL_OAUTH_BASE_URL", "").strip().rstrip("/")
    return CamelOAuthSettings(
        base_url=base_url,
        internal_base_url=(os.environ.get("CAMEL_OAUTH_INTERNAL_BASE_URL", "").strip().rstrip("/") or base_url),
        client_id=os.environ.get("CAMEL_OAUTH_CLIENT_ID", "").strip(),
        client_secret=os.environ.get("CAMEL_OAUTH_CLIENT_SECRET", "").strip(),
        redirect_uri=os.environ.get("CAMEL_OAUTH_REDIRECT_URI", "").strip(),
        redirect_hosts=_split_env_values(os.environ.get("CAMEL_OAUTH_REDIRECT_HOSTS", "")),
        scopes=os.environ.get("CAMEL_OAUTH_SCOPES", "profile email").strip(),
        bootstrap_scopes=os.environ.get(
            "CAMEL_OAUTH_BOOTSTRAP_SCOPES", "profile email arcreel:token-provision"
        ).strip(),
        repair_max_age_seconds=os.environ.get("CAMEL_OAUTH_REPAIR_MAX_AGE_SECONDS", "").strip(),
    )


def camel_oauth_provider_available() -> bool:
    return get_camel_oauth_settings().configured


def _require_settings() -> CamelOAuthSettings:
    settings = get_camel_oauth_settings()
    if not settings.configured:
        raise HTTPException(status_code=503, detail="CaMeL OAuth is not configured")
    return settings


def _split_env_values(raw: str) -> tuple[str, ...]:
    values: list[str] = []
    for item in raw.replace("\n", ",").replace(" ", ",").split(","):
        value = item.strip()
        if value:
            values.append(value)
    return tuple(values)


def _camel_redirect_uri(settings: CamelOAuthSettings, request: Request) -> str:
    host = request.url.netloc.strip().lower()
    allowed_hosts = {candidate.lower() for candidate in settings.redirect_hosts}
    if host and host in allowed_hosts:
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
        scheme = forwarded_proto or request.url.scheme or "http"
        if scheme not in {"http", "https"}:
            raise HTTPException(status_code=400, detail="Invalid OAuth redirect scheme")
        return f"{scheme}://{host}{CAMEL_OAUTH_CALLBACK_PATH}"
    if settings.redirect_uri:
        return settings.redirect_uri
    raise HTTPException(status_code=400, detail="Current host is not allowed for CaMeL OAuth")


def safe_return_path(raw: str | None) -> str:
    if not raw:
        return "/app/projects"
    parts = urlsplit(raw)
    if parts.scheme or parts.netloc or not parts.path.startswith("/app/") or raw.startswith("//"):
        raise HTTPException(status_code=400, detail="Invalid return path")
    return urlunsplit(("", "", parts.path, parts.query, parts.fragment))


def _encode_state_cookie(state: CamelOAuthState) -> str:
    now = int(time.time())
    payload = {
        "state": state.nonce,
        "intent": state.intent,
        "from": state.return_path,
        "redirect_uri": state.redirect_uri,
        "iat": now,
        "exp": now + CAMEL_STATE_TTL_SECONDS,
    }
    if state.user_id is not None:
        payload["user_id"] = state.user_id
    if state.tenant_id is not None:
        payload["tenant_id"] = state.tenant_id
    if state.idempotency_key is not None:
        payload["idempotency_key"] = state.idempotency_key
    return jwt.encode(payload, get_token_secret(), algorithm="HS256")


def _state_cookie_name(state: str) -> str:
    return f"{CAMEL_STATE_COOKIE_PREFIX}{state}"


def _state_cookie_from_request(state: str, cookies: dict[str, str]) -> str | None:
    return cookies.get(_state_cookie_name(state)) or cookies.get(CAMEL_STATE_COOKIE_NAME)


def _decode_state_cookie(state: str, state_cookie: str | None) -> CamelOAuthState:
    if not state_cookie:
        raise HTTPException(status_code=400, detail="Missing OAuth state cookie")
    try:
        payload = jwt.decode(state_cookie, get_token_secret(), algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    if payload.get("state") != state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    intent = payload.get("intent")
    if intent not in {"login", "provider_bootstrap", "provider_repair"}:
        raise HTTPException(status_code=400, detail="Invalid OAuth intent")
    return CamelOAuthState(
        nonce=state,
        intent=cast(CamelOAuthIntent, intent),
        return_path=safe_return_path(payload.get("from")),
        redirect_uri=str(payload.get("redirect_uri") or ""),
        user_id=payload.get("user_id"),
        tenant_id=payload.get("tenant_id"),
        idempotency_key=payload.get("idempotency_key"),
    )


def build_camel_authorization_redirect(
    request: Request,
    from_path: str | None,
    intent: CamelOAuthIntent = "login",
    user_id: str | None = None,
    tenant_id: str | None = None,
    idempotency_key: str | None = None,
) -> RedirectResponse:
    settings = _require_settings()
    redirect_uri = _camel_redirect_uri(settings, request)
    oauth_state = CamelOAuthState(
        nonce=secrets.token_urlsafe(32),
        intent=intent,
        return_path=safe_return_path(from_path),
        redirect_uri=redirect_uri,
        user_id=user_id,
        tenant_id=tenant_id,
        idempotency_key=idempotency_key,
    )
    params = {
        "response_type": "code",
        "client_id": settings.client_id,
        "redirect_uri": redirect_uri,
        "scope": settings.scopes if intent == "login" else settings.bootstrap_scopes,
        "state": oauth_state.nonce,
    }
    if intent == "provider_repair" and settings.repair_max_age_seconds:
        params["max_age"] = settings.repair_max_age_seconds
    response = RedirectResponse(f"{settings.authorize_url}?{urlencode(params)}")
    cookie_value = _encode_state_cookie(oauth_state)
    for cookie_name in (_state_cookie_name(oauth_state.nonce), CAMEL_STATE_COOKIE_NAME):
        response.set_cookie(
            cookie_name,
            cookie_value,
            max_age=CAMEL_STATE_TTL_SECONDS,
            httponly=True,
            samesite="lax",
            secure=redirect_uri.startswith("https://"),
        )
    return response


async def _fetch_camel_exchange(settings: CamelOAuthSettings, code: str, redirect_uri: str) -> CamelOAuthExchange:
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_response = await client.post(
            settings.token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": settings.client_id,
                "client_secret": settings.client_secret,
            },
        )
        token_response.raise_for_status()
        token_body = token_response.json()
        if not isinstance(token_body, dict):
            raise HTTPException(status_code=502, detail="CaMeL token response was invalid")
        access_token = token_body.get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail="CaMeL token response did not include an access token")
        userinfo_response = await client.get(
            settings.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        userinfo_response.raise_for_status()
        userinfo = userinfo_response.json()
        if not isinstance(userinfo, dict):
            raise HTTPException(status_code=502, detail="CaMeL userinfo response was invalid")
        return CamelOAuthExchange(access_token=str(access_token), userinfo=userinfo)


def _camel_user_id(userinfo: dict) -> str:
    raw = userinfo.get("id") or userinfo.get("sub")
    if raw is None or str(raw).strip() == "":
        raise HTTPException(status_code=502, detail="CaMeL userinfo did not include a user id")
    return str(raw)


async def upsert_camel_user(userinfo: dict) -> CamelLocalUser:
    camel_user_id = _camel_user_id(userinfo)
    user_id = f"camel:{camel_user_id}"
    username = str(userinfo.get("username") or userinfo.get("display_name") or user_id)
    async with async_session_factory() as session:
        async with session.begin():
            result = await session.execute(select(User).where(User.id == user_id))
            row = result.scalar_one_or_none()
            if row is None:
                session.add(
                    User(
                        id=user_id,
                        username=username,
                        provider="camel",
                        provider_subject=camel_user_id,
                        role="user",
                        is_active=True,
                    )
                )
            else:
                row.username = username
                row.is_active = True
                row.provider = "camel"
                row.provider_subject = camel_user_id
    return CamelLocalUser(id=user_id, username=username, camel_user_id=camel_user_id)


def _delete_state_cookies(response: RedirectResponse, state: str) -> None:
    response.delete_cookie(_state_cookie_name(state))
    response.delete_cookie(CAMEL_STATE_COOKIE_NAME)


def _frontend_callback_redirect(token: str, state: str, return_path: str) -> RedirectResponse:
    response = RedirectResponse(f"/login/callback#{urlencode({'access_token': token, 'from': return_path})}")
    _delete_state_cookies(response, state)
    return response


async def _handle_login_intent(userinfo: dict, state: CamelOAuthState) -> RedirectResponse:
    user = await upsert_camel_user(userinfo)
    async with async_session_factory() as session:
        async with session.begin():
            tenant = await ensure_personal_tenant(session, user_id=user.id, username=user.username)
    token = create_token(user.username, user_id=user.id, provider="camel", tenant_id=tenant.id, tenant_role=tenant.role)
    return _frontend_callback_redirect(token, state.nonce, state.return_path)


def _provider_intent_redirect(return_path: str, result: dict, state: str | None = None) -> RedirectResponse:
    parts = urlsplit(return_path)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if result.get("completed") is True:
        query["camel_bootstrap"] = "completed"
    else:
        query["camel_bootstrap"] = str(result.get("error") or "failed")
    query["camel_bootstrap_result"] = json.dumps(result, separators=(",", ":"))
    response = RedirectResponse(urlunsplit(("", "", parts.path, urlencode(query), parts.fragment)))
    if state is not None:
        _delete_state_cookies(response, state)
    else:
        response.delete_cookie(CAMEL_STATE_COOKIE_NAME)
    return response


async def _handle_provider_intent_with_token(
    userinfo: dict,
    state: CamelOAuthState,
    access_token: str,
) -> RedirectResponse:
    from server.services.camel_bootstrap import CamelLocalBootstrapError, complete_camel_provider_bootstrap

    user = await upsert_camel_user(userinfo)
    if state.user_id is not None and state.user_id != user.id:
        raise HTTPException(status_code=400, detail="CaMeL user mismatch")
    mode = "repair" if state.intent == "provider_repair" else "create"
    try:
        async with async_session_factory() as session:
            async with session.begin():
                if state.tenant_id is not None:
                    access = await read_tenant_access(session, user_id=user.id, tenant_id=state.tenant_id)
                    if access is None:
                        raise HTTPException(status_code=403, detail="TENANT_ACCESS_REVOKED")
                result = await complete_camel_provider_bootstrap(
                    session,
                    user_id=user.id,
                    tenant_id=state.tenant_id,
                    camel_user_id=user.camel_user_id,
                    access_token=access_token,
                    mode=mode,
                    idempotency_key=state.idempotency_key,
                )
    except CamelLocalBootstrapError as exc:
        result = exc.result
    return _provider_intent_redirect(state.return_path, result, state.nonce)


async def complete_camel_oauth_callback(code: str, state: str, cookies: dict[str, str]) -> RedirectResponse:
    settings = _require_settings()
    oauth_state = _decode_state_cookie(state, _state_cookie_from_request(state, cookies))
    redirect_uri = oauth_state.redirect_uri or settings.redirect_uri
    if not redirect_uri:
        raise HTTPException(status_code=400, detail="Missing OAuth redirect URI")
    try:
        exchange = await _fetch_camel_exchange(settings, code, redirect_uri)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="CaMeL OAuth request failed")
    if oauth_state.intent == "login":
        return await _handle_login_intent(exchange.userinfo, oauth_state)
    return await _handle_provider_intent_with_token(exchange.userinfo, oauth_state, exchange.access_token)
