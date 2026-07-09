from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse
from starlette.responses import RedirectResponse

from lib.db import get_async_session
from server.auth import CurrentUser
from server.services.camel_auth import build_camel_authorization_redirect
from server.services.camel_bootstrap import get_camel_bootstrap_status

router = APIRouter(prefix="/camel/bootstrap", tags=["CaMeL Bootstrap"])


@router.get("/status")
async def bootstrap_status(
    _user: CurrentUser,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    return await get_camel_bootstrap_status(session, _user.id)


@router.get("/start")
async def bootstrap_start(
    _user: CurrentUser,
    mode: Literal["create", "repair"] = "create",
    from_path: Annotated[str | None, Query(alias="from")] = None,
) -> RedirectResponse:
    intent = "provider_repair" if mode == "repair" else "provider_bootstrap"
    return build_camel_authorization_redirect(
        from_path,
        intent=intent,
        user_id=_user.id,
        idempotency_key=f"arc-bootstrap-{uuid.uuid4().hex}",
    )


@router.post("/start-url")
async def bootstrap_start_url(
    _user: CurrentUser,
    mode: Literal["create", "repair"] = "create",
    from_path: Annotated[str | None, Query(alias="from")] = None,
) -> JSONResponse:
    intent = "provider_repair" if mode == "repair" else "provider_bootstrap"
    redirect = build_camel_authorization_redirect(
        from_path,
        intent=intent,
        user_id=_user.id,
        idempotency_key=f"arc-bootstrap-{uuid.uuid4().hex}",
    )
    response = JSONResponse({"authorization_url": redirect.headers["location"]})
    for key, value in redirect.raw_headers:
        if key.lower() == b"set-cookie":
            response.raw_headers.append((key, value))
    return response
