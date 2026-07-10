"""
认证 API 路由

提供 OAuth2 登录和 token 验证接口。
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from starlette.responses import RedirectResponse

from lib.i18n import Translator
from server.auth import (
    CurrentUser,
    check_credentials,
    create_token,
    get_auth_mode,
    is_camel_auth_mode,
    is_auth_enabled,
)
from server.services.camel_auth import (
    CAMEL_STATE_COOKIE_NAME,
    build_camel_authorization_redirect,
    camel_oauth_provider_available,
    complete_camel_oauth_callback,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 响应模型 ====================


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class VerifyResponse(BaseModel):
    valid: bool
    username: str
    user_id: str
    provider: str


class AuthProviderResponse(BaseModel):
    id: str
    label: str
    login_url: str


class AuthStatusResponse(BaseModel):
    enabled: bool
    mode: str
    providers: list[AuthProviderResponse]


# ==================== 路由 ====================


@router.get("/auth/status", response_model=AuthStatusResponse)
async def auth_status():
    """暴露 ``AUTH_ENABLED`` 状态供前端 bootstrap 判断是否需要登录拦截。

    前端 ``auth-store.initialize()`` 在 localStorage 无 token 时调用本接口：
    ``enabled=false`` 时跳过登录页直接进主界面；``enabled=true`` 时保留原
    登录链路。本接口本身**不要求认证**——一个 boolean 比 401 探针更直观，
    且实际"是否需要登录"通过 401/200 也能从外部观察到，因此不增量泄露。
    """
    mode = get_auth_mode()
    providers = []
    if mode == "camel" and camel_oauth_provider_available():
        providers.append(AuthProviderResponse(id="camel", label="CaMeL", login_url="/api/v1/auth/camel/start"))
    return AuthStatusResponse(enabled=is_auth_enabled(), mode=mode, providers=providers)


@router.post("/auth/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    _t: Translator,
):
    """用户登录

    使用 OAuth2 标准表单格式验证凭据，成功返回 access_token。
    ``AUTH_ENABLED=false`` 时跳过凭据校验，直接签发 token，让前端
    LoginPage 即便被打开也能正常跳转主界面。
    """
    if is_camel_auth_mode():
        raise HTTPException(status_code=403, detail="Local password login is disabled")
    if is_auth_enabled() and not check_credentials(form_data.username, form_data.password):
        logger.warning("登录失败: 用户名或密码错误 (用户: %s)", form_data.username)
        raise HTTPException(
            status_code=401,
            detail=_t("unauthorized"),
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_token(form_data.username)
    logger.info("用户登录成功: %s", form_data.username)
    return TokenResponse(access_token=token, token_type="bearer")


@router.get("/auth/verify", response_model=VerifyResponse)
async def verify(
    current_user: CurrentUser,
):
    """验证 token 有效性

    使用 OAuth2 Bearer token 依赖自动提取和验证 token。
    """
    return VerifyResponse(
        valid=True,
        username=current_user.sub,
        user_id=current_user.id,
        provider=current_user.provider,
    )


@router.get("/auth/camel/start")
async def camel_start(
    request: Request,
    from_path: Annotated[str | None, Query(alias="from")] = None,
) -> RedirectResponse:
    return build_camel_authorization_redirect(request, from_path, intent="login")


@router.get("/auth/camel/callback")
async def camel_callback(
    code: str,
    state: str,
    state_cookie: Annotated[str | None, Cookie(alias=CAMEL_STATE_COOKIE_NAME)] = None,
) -> RedirectResponse:
    return await complete_camel_oauth_callback(code, state, state_cookie)
