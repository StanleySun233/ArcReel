from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lib.agent_provider_catalog import CUSTOM_SENTINEL_ID
from lib.config.service import ConfigService
from lib.custom_provider import make_provider_id
from lib.custom_provider.endpoints import ENDPOINT_REGISTRY
from lib.db.models import Tenant
from lib.db.models.user import User
from lib.db.repositories.agent_credential_repo import AgentCredentialRepository
from lib.db.repositories.custom_provider_repo import CustomProviderRepository
from lib.db.tenant_context import set_tenant_context

CamelBootstrapMode = Literal["create", "repair"]
MEDIA_ORDER = ("image", "text", "video", "audio")
_TOKEN_PROVISION_PATH = "/api/oauth/provider/arcreel-tokens"
_TOKEN_LINK_TEMPLATE_PATH = "/token/{token_name}"
_SECRET_VALUE_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|Bearer\s+[A-Za-z0-9._~+/=-]+|"
    r"(?i:(api[_-]?key|secret|token|password))\s*[:=]\s*[^,\s}]+)"
)
_DEFAULT_MEDIA_SPECS = {
    "image": ("CaMeL Image", "openai-images", ("camel-image",)),
    "text": ("CaMeL Text", "openai-chat", ("camel-text",)),
    "video": ("CaMeL Video", "ark-seedance", ("doubao-seedance-2-0-260128",)),
    "audio": ("CaMeL Audio", "openai-tts", ("camel-audio",)),
    "anthropic": ("CaMeL Agent", "anthropic-messages", ("claude-opus-4-8",)),
}


@dataclass(frozen=True)
class CamelMediaSpec:
    media: str
    display_name: str
    endpoint: str
    models: tuple[str, ...]
    default_keys: tuple[str, ...]


@dataclass(frozen=True)
class CamelBootstrapSettings:
    provider_base_url: str
    token_provision_url: str
    token_link_template: str
    media_specs: tuple[CamelMediaSpec, ...]


class CamelLocalBootstrapError(Exception):
    def __init__(self, result: dict):
        super().__init__("Local CaMeL provider bootstrap failed")
        self.result = result


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise HTTPException(status_code=503, detail=f"{name} is not configured")
    return value


def _env_or_default(name: str, default: str) -> str:
    return os.environ.get(name, "").strip() or default


def _env_models(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    models = tuple(m.strip() for m in raw.split(",") if m.strip())
    if not models:
        raise HTTPException(status_code=503, detail=f"{name} is not configured")
    return models


def _oauth_public_base_url() -> str:
    return _env("CAMEL_OAUTH_BASE_URL").rstrip("/")


def _oauth_internal_base_url() -> str:
    return os.environ.get("CAMEL_OAUTH_INTERNAL_BASE_URL", "").strip().rstrip("/") or _oauth_public_base_url()


def _provider_base_url() -> str:
    override = os.environ.get("CAMEL_ARCREEL_PROVIDER_BASE_URL", "").strip()
    if override:
        return override.rstrip("/")
    return _oauth_internal_base_url()


def _token_provision_url(provider_base_url: str) -> str:
    override = os.environ.get("CAMEL_ARCREEL_TOKEN_PROVISION_URL", "").strip()
    if override:
        return override
    return _join_url(provider_base_url, _TOKEN_PROVISION_PATH)


def _token_link_template() -> str:
    override = os.environ.get("CAMEL_ARCREEL_TOKEN_LINK_TEMPLATE", "").strip()
    if override:
        return override
    return _join_url(_oauth_public_base_url(), _TOKEN_LINK_TEMPLATE_PATH)


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _media_spec(media: str, endpoint_env: str, models_env: str) -> CamelMediaSpec:
    display_name, default_endpoint, default_models = _DEFAULT_MEDIA_SPECS[media]
    endpoint = _env_or_default(endpoint_env, default_endpoint)
    if media != "anthropic" and endpoint not in ENDPOINT_REGISTRY:
        raise HTTPException(status_code=503, detail=f"{endpoint_env} is invalid")
    default_keys = {
        "image": ("default_image_backend_t2i", "default_image_backend_i2i"),
        "text": ("default_text_backend", "text_backend_script", "text_backend_overview", "text_backend_style"),
        "video": ("default_video_backend",),
        "audio": ("default_audio_backend",),
        "anthropic": (),
    }[media]
    return CamelMediaSpec(media, display_name, endpoint, _env_models(models_env, default_models), default_keys)


def get_camel_bootstrap_settings() -> CamelBootstrapSettings:
    provider_base_url = _provider_base_url()
    return CamelBootstrapSettings(
        provider_base_url=provider_base_url,
        token_provision_url=_token_provision_url(provider_base_url),
        token_link_template=_token_link_template(),
        media_specs=(
            _media_spec("image", "CAMEL_ARCREEL_IMAGE_ENDPOINT", "CAMEL_ARCREEL_IMAGE_MODELS"),
            _media_spec("text", "CAMEL_ARCREEL_TEXT_ENDPOINT", "CAMEL_ARCREEL_TEXT_MODELS"),
            _media_spec("video", "CAMEL_ARCREEL_VIDEO_ENDPOINT", "CAMEL_ARCREEL_VIDEO_MODELS"),
            _media_spec("audio", "CAMEL_ARCREEL_AUDIO_ENDPOINT", "CAMEL_ARCREEL_AUDIO_MODELS"),
            _media_spec("anthropic", "CAMEL_ARCREEL_ANTHROPIC_ENDPOINT", "CAMEL_ARCREEL_ANTHROPIC_MODELS"),
        ),
    )


def camel_user_id_from_arc_user(user_id: str) -> str:
    if not user_id.startswith("camel:") or len(user_id) <= len("camel:"):
        raise HTTPException(status_code=400, detail="Current user is not a CaMeL user")
    return user_id.removeprefix("camel:")


async def _request_camel_tokens(
    settings: CamelBootstrapSettings,
    access_token: str,
    mode: CamelBootstrapMode,
    idempotency_key: str | None,
) -> dict:
    payload = _camel_token_provision_payload(settings, mode=mode, idempotency_key=idempotency_key)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                settings.token_provision_url,
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
            )
            body = _decode_camel_token_response(response)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="CaMeL token provisioning request failed") from exc
    if response.status_code >= 400 and body.get("success") is not False:
        raise HTTPException(status_code=502, detail="CaMeL token provisioning request failed")
    return body


def _decode_camel_token_response(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="CaMeL token provisioning response was invalid") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=502, detail="CaMeL token provisioning response was invalid")
    return body


def _camel_token_provision_payload(
    settings: CamelBootstrapSettings,
    *,
    mode: CamelBootstrapMode,
    idempotency_key: str | None,
) -> dict:
    return {
        "client": "arcreel",
        "mode": mode,
        "idempotency_key": idempotency_key,
        "dry_run": False,
        "media_specs": [
            {
                "media": spec.media,
                "models": list(spec.models),
            }
            for spec in settings.media_specs
        ],
    }


def _token_link(settings: CamelBootstrapSettings, token_name: str, media: str) -> str:
    try:
        return settings.token_link_template.format(token_name=token_name, name=token_name, media=media)
    except KeyError:
        return settings.token_link_template.replace("{token_name}", token_name)


def _token_deletion_links(settings: CamelBootstrapSettings, tokens: list[dict]) -> list[dict]:
    links = []
    for token in tokens:
        media = str(token.get("media") or "")
        name = str(token.get("name") or "")
        if not media or not name:
            continue
        links.append(
            {
                "media": media,
                "token_name": name,
                "delete_url": str(token.get("delete_url") or _token_link(settings, name, media)),
            }
        )
    return links


def _camel_conflict_links(conflicts: object) -> list[dict]:
    if not isinstance(conflicts, list):
        return []
    links = []
    for conflict in conflicts:
        if not isinstance(conflict, dict):
            continue
        token_name = str(conflict.get("token_name") or conflict.get("name") or "")
        media = str(conflict.get("media") or "")
        delete_url = str(conflict.get("delete_url") or conflict.get("management_url") or "")
        if token_name and delete_url:
            links.append({"media": media, "token_name": token_name, "delete_url": delete_url})
    return links


def _safe_camel_error_message(body: dict) -> str:
    for key in ("message", "detail", "error_description"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return _SECRET_VALUE_RE.sub("[redacted]", value.strip())[:300]
    error = body.get("error")
    if isinstance(error, str) and error.strip() and error != "token_name_conflict":
        return error.strip()[:120]
    return ""


def _token_models(token: dict, spec: CamelMediaSpec) -> tuple[str, ...]:
    raw = token.get("model_limits")
    if not isinstance(raw, list):
        return spec.models
    models = tuple(str(model).strip() for model in raw if str(model).strip())
    return models or spec.models


def _models_for_spec(spec: CamelMediaSpec, models: tuple[str, ...]) -> list[dict]:
    return [
        {
            "model_id": model,
            "display_name": model,
            "endpoint": spec.endpoint,
            "is_default": index == 0,
            "is_enabled": True,
        }
        for index, model in enumerate(models)
    ]


async def _upsert_provider(
    session: AsyncSession,
    user_id: str,
    tenant_id: str,
    settings: CamelBootstrapSettings,
    spec: CamelMediaSpec,
    models: tuple[str, ...],
    api_key: str,
):
    repo = CustomProviderRepository(session, user_id=user_id, tenant_id=tenant_id)
    existing = next((p for p in await repo.list_providers() if p.display_name == spec.display_name), None)
    if existing is None:
        provider = await repo.create_provider(
            display_name=spec.display_name,
            discovery_format="openai",
            base_url=settings.provider_base_url,
            api_key=api_key,
            models=_models_for_spec(spec, models),
        )
    else:
        provider = await repo.update_provider(
            existing.id,
            display_name=spec.display_name,
            base_url=settings.provider_base_url,
            api_key=api_key,
        )
        await repo.replace_models(existing.id, _models_for_spec(spec, models))
    return provider


async def _upsert_agent_credential(
    session: AsyncSession,
    user_id: str,
    tenant_id: str,
    settings: CamelBootstrapSettings,
    spec: CamelMediaSpec,
    models: tuple[str, ...],
    api_key: str,
):
    repo = AgentCredentialRepository(session, tenant_id=tenant_id)
    existing = next((cred for cred in await repo.list_for_tenant() if cred.display_name == spec.display_name), None)
    if existing is None:
        credential = await repo.create(
            preset_id=CUSTOM_SENTINEL_ID,
            display_name=spec.display_name,
            base_url=settings.provider_base_url,
            api_key=api_key,
            model=models[0],
            subagent_model=models[0],
            user_id=user_id,
        )
    else:
        credential = await repo.update(
            existing.id,
            base_url=settings.provider_base_url,
            api_key=api_key,
            model=models[0],
            subagent_model=models[0],
        )
    if credential is None:
        raise HTTPException(status_code=502, detail="CaMeL agent credential bootstrap failed")
    await repo.set_active(credential.id)
    return credential


async def _resolve_tenant_id(session: AsyncSession, user_id: str, tenant_id: str | None) -> str:
    resolved = tenant_id or session.info.get("tenant_id")
    if resolved:
        session.info["tenant_id"] = str(resolved)
        return str(resolved)
    result = await session.execute(select(Tenant.id).where(Tenant.personal_for_user_id == user_id))
    personal_tenant_id = result.scalar_one_or_none()
    if personal_tenant_id is None:
        raise HTTPException(status_code=403, detail="TENANT_ACCESS_REQUIRED")
    session.info["tenant_id"] = personal_tenant_id
    return personal_tenant_id


async def _tenant_bootstrap_completed(
    session: AsyncSession,
    *,
    user_id: str,
    tenant_id: str,
    settings: CamelBootstrapSettings,
) -> bool:
    repo = CustomProviderRepository(session, user_id=user_id, tenant_id=tenant_id)
    providers = await repo.list_providers()
    provider_names = {provider.display_name for provider in providers}
    provider_specs = [spec for spec in settings.media_specs if spec.media != "anthropic"]
    if any(spec.display_name not in provider_names for spec in provider_specs):
        return False
    if await AgentCredentialRepository(session, tenant_id=tenant_id).get_active() is None:
        return False
    config = ConfigService(session, user_id=user_id, tenant_id=tenant_id)
    for spec in provider_specs:
        for key in spec.default_keys:
            if not await config.get_setting(key, ""):
                return False
    return True


async def get_camel_bootstrap_status(session: AsyncSession, user_id: str, tenant_id: str | None = None) -> dict:
    camel_user_id = camel_user_id_from_arc_user(user_id)
    resolved_tenant_id = await _resolve_tenant_id(session, user_id, tenant_id)
    settings = get_camel_bootstrap_settings()
    if await _tenant_bootstrap_completed(session, user_id=user_id, tenant_id=resolved_tenant_id, settings=settings):
        return {"needed": False, "completed": True}
    return {
        "needed": True,
        "completed": False,
        "camel_user_id": camel_user_id,
        "providers": [
            {
                "media": spec.media,
                "provider_name": spec.display_name,
                "base_url": settings.provider_base_url,
                "endpoint": spec.endpoint,
                "models": list(spec.models),
                "token_name": f"camel-arcreel-{camel_user_id}-{spec.media}",
            }
            for spec in settings.media_specs
        ],
    }


async def complete_camel_provider_bootstrap(
    session: AsyncSession,
    *,
    user_id: str,
    tenant_id: str | None = None,
    camel_user_id: str,
    access_token: str,
    mode: CamelBootstrapMode,
    idempotency_key: str | None,
) -> dict:
    if camel_user_id_from_arc_user(user_id) != camel_user_id:
        raise HTTPException(status_code=400, detail="CaMeL user mismatch")

    settings = get_camel_bootstrap_settings()
    resolved_tenant_id = await _resolve_tenant_id(session, user_id, tenant_id)
    await set_tenant_context(session, user_id=user_id, tenant_id=resolved_tenant_id)
    session.info["user_id"] = user_id
    session.info["tenant_id"] = resolved_tenant_id
    provisioned = await _request_camel_tokens(settings, access_token, mode, idempotency_key)
    if provisioned.get("success") is not True:
        message = _safe_camel_error_message(provisioned)
        result = {
            "completed": False,
            "error": "camel_token_conflict"
            if provisioned.get("error") == "token_name_conflict"
            else "camel_token_error",
            "conflicts": _camel_conflict_links(provisioned.get("conflicts")),
        }
        if message:
            result["message"] = message
        return result

    tokens = provisioned.get("tokens")
    if not isinstance(tokens, list):
        raise HTTPException(status_code=502, detail="CaMeL token provisioning response was invalid")
    token_rows = [t for t in tokens if isinstance(t, dict)]
    token_by_media = {str(t.get("media")): t for t in token_rows}
    created_token_links = _token_deletion_links(settings, token_rows)

    repo_results = []
    config = ConfigService(session, user_id=user_id, tenant_id=resolved_tenant_id)
    try:
        for spec in settings.media_specs:
            token = token_by_media.get(spec.media)
            api_key = token.get("key") if isinstance(token, dict) else None
            if not isinstance(api_key, str) or not api_key:
                raise HTTPException(status_code=502, detail="CaMeL token provisioning response was incomplete")
            models = _token_models(token, spec)
            if spec.media == "anthropic":
                await _upsert_agent_credential(session, user_id, resolved_tenant_id, settings, spec, models, api_key)
                continue
            provider = await _upsert_provider(session, user_id, resolved_tenant_id, settings, spec, models, api_key)
            if provider is None:
                raise HTTPException(status_code=502, detail="CaMeL provider bootstrap failed")
            provider_ref = f"{make_provider_id(provider.id)}/{models[0]}"
            for key in spec.default_keys:
                await config.set_setting(key, provider_ref)
            repo_results.append(
                {
                    "media": spec.media,
                    "provider_id": provider.id,
                    "provider_name": spec.display_name,
                    "models": list(models),
                }
            )

        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is not None:
            user.camel_provider_bootstrap_completed_at = datetime.now(UTC)
        await session.flush()
    except Exception as exc:
        raise CamelLocalBootstrapError(
            {
                "completed": False,
                "error": "partial_bootstrap_failed",
                "created_tokens": created_token_links,
            }
        ) from exc
    return {"completed": True, "providers": repo_results}
