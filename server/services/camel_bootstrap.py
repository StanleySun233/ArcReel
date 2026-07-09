from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lib.config.service import ConfigService
from lib.custom_provider import make_provider_id
from lib.custom_provider.endpoints import ENDPOINT_REGISTRY
from lib.db.models.user import User
from lib.db.repositories.custom_provider_repo import CustomProviderRepository

CamelBootstrapMode = Literal["create", "repair"]
MEDIA_ORDER = ("image", "text", "video", "audio")


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


def _env_models(name: str) -> tuple[str, ...]:
    models = tuple(m.strip() for m in _env(name).split(",") if m.strip())
    if not models:
        raise HTTPException(status_code=503, detail=f"{name} is not configured")
    return models


def _media_spec(media: str, display_name: str, endpoint_env: str, models_env: str) -> CamelMediaSpec:
    endpoint = _env(endpoint_env)
    if endpoint not in ENDPOINT_REGISTRY:
        raise HTTPException(status_code=503, detail=f"{endpoint_env} is invalid")
    default_keys = {
        "image": ("default_image_backend_t2i", "default_image_backend_i2i"),
        "text": ("default_text_backend",),
        "video": ("default_video_backend",),
        "audio": ("default_audio_backend",),
    }[media]
    return CamelMediaSpec(media, display_name, endpoint, _env_models(models_env), default_keys)


def get_camel_bootstrap_settings() -> CamelBootstrapSettings:
    return CamelBootstrapSettings(
        provider_base_url=_env("CAMEL_ARCREEL_PROVIDER_BASE_URL").rstrip("/"),
        token_provision_url=_env("CAMEL_ARCREEL_TOKEN_PROVISION_URL"),
        token_link_template=_env("CAMEL_ARCREEL_TOKEN_LINK_TEMPLATE"),
        media_specs=(
            _media_spec("image", "CaMeL Image", "CAMEL_ARCREEL_IMAGE_ENDPOINT", "CAMEL_ARCREEL_IMAGE_MODELS"),
            _media_spec("text", "CaMeL Text", "CAMEL_ARCREEL_TEXT_ENDPOINT", "CAMEL_ARCREEL_TEXT_MODELS"),
            _media_spec("video", "CaMeL Video", "CAMEL_ARCREEL_VIDEO_ENDPOINT", "CAMEL_ARCREEL_VIDEO_MODELS"),
            _media_spec("audio", "CaMeL Audio", "CAMEL_ARCREEL_AUDIO_ENDPOINT", "CAMEL_ARCREEL_AUDIO_MODELS"),
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
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                settings.token_provision_url,
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "client": "arcreel",
                    "mode": mode,
                    "idempotency_key": idempotency_key,
                    "dry_run": False,
                },
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="CaMeL token provisioning request failed") from exc
    try:
        body = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="CaMeL token provisioning response was invalid") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=502, detail="CaMeL token provisioning response was invalid")
    return body


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


def _models_for_spec(spec: CamelMediaSpec) -> list[dict]:
    return [
        {
            "model_id": model,
            "display_name": model,
            "endpoint": spec.endpoint,
            "is_default": index == 0,
            "is_enabled": True,
        }
        for index, model in enumerate(spec.models)
    ]


async def _upsert_provider(
    session: AsyncSession,
    user_id: str,
    settings: CamelBootstrapSettings,
    spec: CamelMediaSpec,
    api_key: str,
):
    repo = CustomProviderRepository(session, user_id=user_id)
    existing = next((p for p in await repo.list_providers() if p.display_name == spec.display_name), None)
    if existing is None:
        provider = await repo.create_provider(
            display_name=spec.display_name,
            discovery_format="openai",
            base_url=settings.provider_base_url,
            api_key=api_key,
            models=_models_for_spec(spec),
        )
    else:
        provider = await repo.update_provider(
            existing.id,
            display_name=spec.display_name,
            base_url=settings.provider_base_url,
            api_key=api_key,
        )
        await repo.replace_models(existing.id, _models_for_spec(spec))
    return provider


async def get_camel_bootstrap_status(session: AsyncSession, user_id: str) -> dict:
    camel_user_id = camel_user_id_from_arc_user(user_id)
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    completed = bool(user and user.camel_provider_bootstrap_completed_at)
    if completed:
        return {"needed": False, "completed": True}
    settings = get_camel_bootstrap_settings()
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
    camel_user_id: str,
    access_token: str,
    mode: CamelBootstrapMode,
    idempotency_key: str | None,
) -> dict:
    if camel_user_id_from_arc_user(user_id) != camel_user_id:
        raise HTTPException(status_code=400, detail="CaMeL user mismatch")

    settings = get_camel_bootstrap_settings()
    provisioned = await _request_camel_tokens(settings, access_token, mode, idempotency_key)
    if provisioned.get("success") is not True:
        return {
            "completed": False,
            "error": "camel_token_conflict" if provisioned.get("error") == "token_name_conflict" else "camel_token_error",
            "conflicts": _camel_conflict_links(provisioned.get("conflicts")),
        }

    tokens = provisioned.get("tokens")
    if not isinstance(tokens, list):
        raise HTTPException(status_code=502, detail="CaMeL token provisioning response was invalid")
    token_rows = [t for t in tokens if isinstance(t, dict)]
    token_by_media = {str(t.get("media")): t for t in token_rows}
    created_token_links = _token_deletion_links(settings, token_rows)

    repo_results = []
    config = ConfigService(session, user_id=user_id)
    try:
        for spec in settings.media_specs:
            token = token_by_media.get(spec.media)
            api_key = token.get("key") if isinstance(token, dict) else None
            if not isinstance(api_key, str) or not api_key:
                raise HTTPException(status_code=502, detail="CaMeL token provisioning response was incomplete")
            provider = await _upsert_provider(session, user_id, settings, spec, api_key)
            provider_ref = f"{make_provider_id(provider.id)}/{spec.models[0]}"
            for key in spec.default_keys:
                await config.set_setting(key, provider_ref)
            repo_results.append(
                {
                    "media": spec.media,
                    "provider_id": provider.id,
                    "provider_name": spec.display_name,
                    "models": list(spec.models),
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
