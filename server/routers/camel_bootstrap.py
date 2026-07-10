from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse, RedirectResponse

from lib.db import get_async_session
from lib.db.tenant_context import set_tenant_context
from server.auth import CurrentUser
from server.services.camel_auth import build_camel_authorization_redirect
from server.services.camel_bootstrap import get_camel_bootstrap_status
from server.services.tenant_auth import ROLE_VIEW, require_tenant_access

router = APIRouter(prefix="/camel/bootstrap", tags=["CaMeL Bootstrap"])


@router.get("/status")
async def bootstrap_status(
    _user: CurrentUser,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    access = await require_tenant_access(session, _user, minimum_role=ROLE_VIEW)
    await set_tenant_context(session, user_id=_user.id, tenant_id=access.id)
    session.info["user_id"] = _user.id
    session.info["tenant_id"] = access.id
    return await get_camel_bootstrap_status(session, _user.id, tenant_id=access.id)


@router.get("/start")
async def bootstrap_start(
    request: Request,
    _user: CurrentUser,
    session: AsyncSession = Depends(get_async_session),
    mode: Literal["create", "repair"] = "create",
    from_path: Annotated[str | None, Query(alias="from")] = None,
) -> RedirectResponse:
    intent = "provider_repair" if mode == "repair" else "provider_bootstrap"
    access = await require_tenant_access(session, _user, minimum_role=ROLE_VIEW)
    return build_camel_authorization_redirect(
        request,
        from_path,
        intent=intent,
        user_id=_user.id,
        tenant_id=access.id,
        idempotency_key=f"arc-bootstrap-{uuid.uuid4().hex}",
    )


@router.post("/start-url")
async def bootstrap_start_url(
    request: Request,
    _user: CurrentUser,
    session: AsyncSession = Depends(get_async_session),
    mode: Literal["create", "repair"] = "create",
    from_path: Annotated[str | None, Query(alias="from")] = None,
) -> JSONResponse:
    intent = "provider_repair" if mode == "repair" else "provider_bootstrap"
    access = await require_tenant_access(session, _user, minimum_role=ROLE_VIEW)
    redirect = build_camel_authorization_redirect(
        request,
        from_path,
        intent=intent,
        user_id=_user.id,
        tenant_id=access.id,
        idempotency_key=f"arc-bootstrap-{uuid.uuid4().hex}",
    )
    response = JSONResponse({"authorization_url": redirect.headers["location"]})
    for key, value in redirect.raw_headers:
        if key.lower() == b"set-cookie":
            response.raw_headers.append((key, value))
    return response
