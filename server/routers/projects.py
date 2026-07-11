"""
项目管理路由

处理项目的 CRUD 操作，复用 lib/project_manager.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import shutil
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal

if TYPE_CHECKING:
    from server.services.jianying_draft_service import JianyingDraftService

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi import Path as FastAPIPath
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError
from starlette.background import BackgroundTask

logger = logging.getLogger(__name__)

from lib.app_data_dir import app_data_dir
from lib.asset_fingerprints import compute_asset_fingerprints
from lib.config.resolver import ConfigResolver
from lib.db import async_session_factory
from lib.db.repositories.project_repo import ProjectRepository
from lib.db.tenant_context import set_tenant_context
from lib.i18n import Translator
from lib.profile_manifest import ContentMode
from lib.project_change_hints import project_change_source
from lib.project_context import project_json_local_path
from lib.project_manager import EpisodeScriptReboundError, ProjectManager, SourceKind
from lib.status_calculator import StatusCalculator
from lib.style_templates import is_known_template, resolve_template_prompt
from server.auth import CurrentUser, create_download_token, verify_token
from server.routers._reorder import full_permutation_error
from server.routers._validators import validate_backend_value
from server.services.project_archive import (
    ProjectArchiveService,
    ProjectArchiveValidationError,
)
from server.services.project_cover import resolve_project_cover
from server.services.tenant_auth import ROLE_ADMIN, ROLE_MEMBER, ROLE_VIEW, require_tenant_access

router = APIRouter()

# 初始化项目管理器和状态计算器
pm = ProjectManager(app_data_dir())
calc = StatusCalculator(pm)

# episode 字段白名单：只允许持久化合法的 on-disk 字段。
# StatusCalculator 注入的统计字段（scenes_count / status / storyboards / videos 等）
# 是读时计算值，禁止写回 project.json。title 不在白名单：它以剧本顶层 title 为唯一真相源，
# 经 _apply_episode_sync 单向同步进 episodes[].title，专用端点 PATCH /episodes/{episode} 写入。
EPISODE_PERSIST_FIELDS = {"script_file", "generation_mode"}


def get_project_manager() -> ProjectManager:
    return pm


def get_status_calculator() -> StatusCalculator:
    return calc


def get_archive_service() -> ProjectArchiveService:
    return ProjectArchiveService(get_project_manager())


def get_tenant_project_manager(tenant_id: str) -> ProjectManager:
    return ProjectManager(app_data_dir(), tenant_id=tenant_id)


def get_tenant_archive_service(tenant_id: str) -> ProjectArchiveService:
    return ProjectArchiveService(get_tenant_project_manager(tenant_id))


async def _require_project_row(
    project_id: str,
    current_user: CurrentUser,
    _t: Translator,
    *,
    minimum_role: str = ROLE_VIEW,
):
    async with async_session_factory() as session:
        async with session.begin():
            access = await require_tenant_access(session, current_user, minimum_role=minimum_role)
            await set_tenant_context(session, user_id=current_user.id, tenant_id=access.id)
            row = await ProjectRepository(session, tenant_id=access.id).get_by_id(project_id)
            if row is None:
                raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))
    return access, row, get_tenant_project_manager(access.id)


def _project_json_local_path(manager: ProjectManager, project_name: str) -> str:
    return (manager.projects_root / project_name / manager.PROJECT_FILE).relative_to(app_data_dir()).as_posix()


class CreateProjectRequest(BaseModel):
    name: str | None = None
    title: str | None = None
    style: str | None = ""  # 保留但不再是用户入口
    content_mode: ContentMode | None = "narration"
    # 源文件性质（novel / screenplay），缺省 novel；创建即定、之后不可变。
    source_kind: SourceKind | None = None
    aspect_ratio: str | None = "9:16"
    default_duration: int | None = None
    # 仅 content_mode=ad：目标总时长（秒）。UI 给四档（15/30/60/90，默认 60），
    # 数据层不硬枚举，任意正整数合法。
    target_duration: int | None = Field(default=None, gt=0)
    # 仅 content_mode=ad：创作诉求短文本（可空，不走 source_loader）
    brief: str | None = None
    generation_mode: str | None = None
    # ===== 新增 =====
    style_template_id: str | None = None
    video_backend: str | None = None
    image_backend: str | None = None
    image_provider_t2i: str | None = None
    image_provider_i2i: str | None = None
    text_backend_script: str | None = None
    text_backend_overview: str | None = None
    text_backend_style: str | None = None
    model_settings: dict[str, dict[str, str | None]] | None = None


class EpisodePatch(BaseModel):
    """PATCH body entry for a single episode.

    Only whitelisted fields persist; computed fields (scenes_count, status,
    storyboards, etc.) are silently dropped via extra='ignore'.
    """

    model_config = ConfigDict(extra="ignore")
    episode: int
    script_file: str | None = None
    generation_mode: Literal["storyboard", "grid", "reference_video"] | None = None


class UpdateProjectRequest(BaseModel):
    title: str | None = None
    style: str | None = None
    content_mode: ContentMode | None = None
    # 源文件性质创建即定、不可变；出现即拒（与 content_mode 同性质）。
    source_kind: SourceKind | None = None
    aspect_ratio: str | None = None
    default_duration: int | None = None
    # 仅 ad 项目：目标总时长（秒），任意正整数合法，不可清空
    target_duration: int | None = Field(default=None, gt=0)
    # 仅 ad 项目：创作诉求短文本；显式 null 清为空字符串
    brief: str | None = None
    generation_mode: str | None = None
    video_backend: str | None = None
    image_backend: str | None = None
    image_provider_t2i: str | None = None
    image_provider_i2i: str | None = None
    video_generate_audio: bool | None = None
    # 旁白配音（TTS）项目级覆盖：音频后端 / 音色 / 语速；留空 = 跟随全局默认
    audio_backend: str | None = None
    narration_voice: str | None = None
    narration_speed: float | None = None
    text_backend_script: str | None = None
    text_backend_overview: str | None = None
    text_backend_style: str | None = None
    style_template_id: str | None = None
    clear_style_image: bool | None = None
    episodes: list[EpisodePatch] | None = None
    model_settings: dict[str, dict[str, str | None]] | None = None


def _cleanup_temp_file(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        return


def _cleanup_temp_dir(dir_path: str) -> None:
    shutil.rmtree(dir_path, ignore_errors=True)


@router.post("/projects/import")
async def import_project_archive(
    _user: CurrentUser,
    _t: Translator,
    file: UploadFile = File(...),
    conflict_policy: str = Form("prompt"),
):
    """从 ZIP 导入项目。"""
    upload_path: str | None = None
    try:
        async with async_session_factory() as session:
            async with session.begin():
                access = await require_tenant_access(session, _user, minimum_role=ROLE_MEMBER)
                await set_tenant_context(session, user_id=_user.id, tenant_id=access.id)

        fd, upload_path = tempfile.mkstemp(prefix="arcreel-upload-", suffix=".zip")
        os.close(fd)

        # 使用底层 SpooledTemporaryFile 的同步句柄，整循环 offload 到线程，
        # 避免 async 读取 + 同步写入的混合模式阻塞事件循环 (#230)
        raw_file = file.file

        def _write_upload():
            with open(upload_path, "wb") as target:
                while True:
                    chunk = raw_file.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)

        await asyncio.to_thread(_write_upload)

        def _sync():
            return get_tenant_archive_service(access.id).import_project_archive(
                Path(upload_path),
                uploaded_filename=file.filename,
                conflict_policy=conflict_policy,
            )

        result = await asyncio.to_thread(_sync)
        async with async_session_factory() as session:
            async with session.begin():
                await set_tenant_context(session, user_id=_user.id, tenant_id=access.id)
                repo = ProjectRepository(session, tenant_id=access.id)
                if await repo.get_by_name(result.project_name) is None:
                    await repo.create(
                        project_id=f"prj_{uuid.uuid4().hex}",
                        name=result.project_name,
                        created_by_user_id=_user.id,
                        local_path=_project_json_local_path(get_tenant_project_manager(access.id), result.project_name),
                    )
        return {
            "success": True,
            "project_name": result.project_name,
            "project": result.project,
            "warnings": result.warnings,
            "conflict_resolution": result.conflict_resolution,
            "diagnostics": result.diagnostics,
        }
    except ProjectArchiveValidationError as exc:
        diagnostics = exc.extra.get(
            "diagnostics",
            {"blocking": [], "auto_fixable": [], "warnings": []},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "errors": exc.errors,
                "warnings": exc.warnings,
                "diagnostics": diagnostics,
                **exc.extra,
            },
        )
    except Exception:
        logger.exception("请求处理失败")
        return JSONResponse(
            status_code=500,
            content={"detail": _t("internal_server_error"), "errors": [], "warnings": []},
        )
    finally:
        await file.close()
        if upload_path:
            _cleanup_temp_file(upload_path)


@router.post("/projects/{project_id}/export/token")
async def create_export_token(
    project_id: str,
    current_user: CurrentUser,
    _t: Translator,
    scope: str = Query("full"),
):
    """签发短时效下载 token，用于浏览器原生下载认证。"""
    try:
        if scope not in ("full", "current"):
            raise HTTPException(status_code=422, detail=_t("scope_invalid"))
        async with async_session_factory() as session:
            async with session.begin():
                access = await require_tenant_access(session, current_user, minimum_role=ROLE_VIEW)
                await set_tenant_context(session, user_id=current_user.id, tenant_id=access.id)
                if await ProjectRepository(session, tenant_id=access.id).get_by_id(project_id) is None:
                    raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))

        def _sync():
            manager = get_tenant_project_manager(access.id)
            if not manager.project_exists(project_id):
                raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))
            return get_tenant_archive_service(access.id).get_export_diagnostics(project_id, scope=scope)

        diagnostics = await asyncio.to_thread(_sync)
        username = current_user.sub
        download_token = create_download_token(username, f"{access.id}:{project_id}", user_id=current_user.id)
        return {
            "download_token": download_token,
            "expires_in": 300,
            "diagnostics": diagnostics,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("请求处理失败")
        raise HTTPException(status_code=500, detail=_t("internal_server_error"))


@router.get("/projects/{project_id}/export")
async def export_project_archive(
    project_id: str,
    _t: Translator,
    download_token: str = Query(...),
    scope: str = Query("full"),
):
    """将项目导出为 ZIP。需要 download_token 认证（通过 POST /export/token 获取）。"""
    if scope not in ("full", "current"):
        raise HTTPException(status_code=422, detail=_t("scope_invalid"))

    try:
        payload = verify_token(download_token)
        if payload is None or payload.get("purpose") != "download":
            raise ValueError("invalid download token")
        project_claim = str(payload.get("project") or "")
        tenant_id, sep, token_project_id = project_claim.partition(":")
        if not sep or token_project_id != project_id:
            raise ValueError("tenant_id missing")
    except ValueError:
        raise HTTPException(status_code=403, detail=_t("download_token_mismatch"))

    try:
        archive_path, download_name = await asyncio.to_thread(
            lambda: get_tenant_archive_service(str(tenant_id)).export_project(project_id, scope=scope)
        )
        return FileResponse(
            archive_path,
            media_type="application/zip",
            filename=download_name,
            background=BackgroundTask(_cleanup_temp_file, str(archive_path)),
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))
    except HTTPException:
        raise
    except Exception:
        logger.exception("请求处理失败")
        raise HTTPException(status_code=500, detail=_t("internal_server_error"))


# --- 剪映草稿导出 ---


def get_jianying_draft_service(project_manager: ProjectManager | None = None) -> JianyingDraftService:
    from server.services.jianying_draft_service import JianyingDraftService

    return JianyingDraftService(project_manager or get_project_manager())


def _validate_draft_path(draft_path: str, _t: Callable[..., str]) -> str:
    """校验 draft_path 合法性"""
    if not draft_path or not draft_path.strip():
        raise HTTPException(status_code=422, detail=_t("jianying_path_invalid"))
    if len(draft_path) > 1024:
        raise HTTPException(status_code=422, detail=_t("jianying_path_too_long"))
    if any(ord(c) < 32 for c in draft_path):
        raise HTTPException(status_code=422, detail=_t("jianying_path_illegal"))
    return draft_path.strip()


@router.get("/projects/{project_id}/export/jianying-draft")
def export_jianying_draft(
    project_id: str,
    _t: Translator,
    episode: int = Query(..., description="集数编号"),
    draft_path: str = Query(..., description="用户本地剪映草稿目录"),
    download_token: str = Query(..., description="下载 token"),
    jianying_version: str = Query("6", description="剪映版本：6 或 5"),
):
    """导出指定集的剪映草稿 ZIP"""
    import jwt as pyjwt

    try:
        payload = verify_token(download_token)
        if payload is None or payload.get("purpose") != "download":
            raise pyjwt.InvalidTokenError("invalid download token")
        project_claim = str(payload.get("project") or "")
        tenant_id, sep, token_project_id = project_claim.partition(":")
        if not sep or token_project_id != project_id:
            raise ValueError("download token mismatch")
    except ValueError:
        raise HTTPException(status_code=403, detail=_t("download_token_mismatch"))
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail=_t("download_token_invalid"))

    # 2. 校验 draft_path
    draft_path = _validate_draft_path(draft_path, _t)

    # 3. 调用服务
    svc = get_jianying_draft_service(get_tenant_project_manager(str(tenant_id)))
    try:
        zip_path = svc.export_episode_draft(
            project_name=project_id,
            episode=episode,
            draft_path=draft_path,
            use_draft_info_name=(jianying_version != "5"),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        logger.exception("剪映草稿导出失败: project=%s episode=%d", project_id, episode)
        raise HTTPException(status_code=500, detail=_t("jianying_export_failed"))

    download_name = f"{project_id}_episode_{episode}_jianying_draft.zip"

    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=download_name,
        background=BackgroundTask(_cleanup_temp_dir, str(zip_path.parent)),
    )


@router.get("/projects")
async def list_projects(_user: CurrentUser):
    """列出所有项目"""
    async with async_session_factory() as session:
        async with session.begin():
            access = await require_tenant_access(session, _user, minimum_role=ROLE_VIEW)
            await set_tenant_context(session, user_id=_user.id, tenant_id=access.id)
            rows = await ProjectRepository(session, tenant_id=access.id).list_all()

    def _sync():
        manager = get_tenant_project_manager(access.id)
        calculator = StatusCalculator(manager)
        projects = []
        for row in rows:
            project_id = row.id
            name = row.name
            try:
                if manager.project_exists(project_id):
                    project = manager.load_project(project_id)
                    # 一次性预加载每集剧本，喂给 cover + status 两路下游，去除重复 JSON I/O。
                    # key 为 episode['script_file'] 原值（match resolve_project_cover /
                    # StatusCalculator 对 key 的期望）。任何一集加载失败都不影响列表：
                    # 仅跳过入 map，下游消费者自然按"缺失"路径兜底。
                    preloaded_scripts: dict[str, dict] = {}
                    for ep in project.get("episodes") or []:
                        script_file = ep.get("script_file")
                        if not script_file:
                            continue
                        try:
                            preloaded_scripts[script_file] = manager.load_script(project_id, script_file)
                        except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError) as load_err:
                            # 与 resolve_project_cover / StatusCalculator._load_episode_script
                            # 对齐：I/O 缺失 + JSON/schema 解析失败 → 跳过此集，继续预加载其他集；
                            # 非预期异常（RuntimeError/MemoryError 等）让其冒泡到外层 try，走 basic info 兜底行。
                            logger.debug(
                                "list_projects 预加载剧本失败 project=%s script=%s err=%s",
                                project_id,
                                script_file,
                                load_err,
                            )

                    # 封面走 resolve_project_cover fallback 链：
                    # video_thumbnail → storyboard_image → scene_sheet → character_sheet
                    # —— 兼顾 reference / grid / storyboard 三种生成模式。
                    thumbnail = resolve_project_cover(manager, project_id, project, preloaded_scripts=preloaded_scripts)

                    status = calculator.calculate_project_status(
                        project_id, project, preloaded_scripts=preloaded_scripts
                    )

                    raw_title = project.get("title")
                    projects.append(
                        {
                            "id": project_id,
                            "name": name,
                            # title 缺失/为 None/类型异常时统一归一为空串,前端 i18n
                            # 兜底显示「未命名项目」,确保接口契约始终返回 str。
                            "title": raw_title if isinstance(raw_title, str) else "",
                            "style": project.get("style", ""),
                            "style_template_id": project.get("style_template_id"),
                            "style_image": project.get("style_image"),
                            "thumbnail": thumbnail,
                            "status": status,
                        }
                    )
                else:
                    # 没有 project.json 的项目
                    projects.append(
                        {
                            "id": project_id,
                            "name": name,
                            "title": "",
                            "style": "",
                            "thumbnail": None,
                            "status": {},
                        }
                    )
            except Exception as e:
                # 出错时返回基本信息
                logger.warning("加载项目 '%s' 元数据失败: %s", name, e)
                projects.append(
                    {
                        "id": project_id,
                        "name": name,
                        "title": "",
                        "style": "",
                        "thumbnail": None,
                        "status": {},
                        "error": str(e),
                    }
                )

        return {"projects": projects}

    return await asyncio.to_thread(_sync)


@router.post("/projects")
async def create_project(
    req: CreateProjectRequest,
    _user: CurrentUser,
    _t: Translator,
):
    """创建新项目"""
    async with async_session_factory() as session:
        async with session.begin():
            access = await require_tenant_access(session, _user, minimum_role=ROLE_MEMBER)
            await set_tenant_context(session, user_id=_user.id, tenant_id=access.id)
            repo = ProjectRepository(session, tenant_id=access.id)
            try:
                manager = get_tenant_project_manager(access.id)
            except Exception:
                logger.exception("请求处理失败")
                raise HTTPException(status_code=500, detail=_t("internal_server_error"))

            title = (req.title or "").strip()
            manual_name = (req.name or "").strip()
            if not title and not manual_name:
                raise HTTPException(status_code=400, detail=_t("title_required"))
            project_name = manual_name or manager.generate_project_name(title)
            if await repo.get_by_name(project_name) is not None:
                raise HTTPException(status_code=400, detail=_t("project_exists", name=project_name))
            project_id = f"proj-{uuid.uuid4().hex[:16]}"

            try:
                result = await asyncio.to_thread(
                    _create_project_on_disk,
                    manager,
                    project_id,
                    project_name,
                    title,
                    manual_name,
                    req,
                    _t,
                )
                await repo.create(
                    project_id=project_id,
                    name=project_name,
                    created_by_user_id=_user.id,
                    local_path=project_json_local_path(tenant_id=access.id, project_id=project_id),
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except IntegrityError:
                manager.delete_project_directory(project_id)
                raise HTTPException(status_code=400, detail=_t("project_exists", name=project_name))
            return result


def _create_project_on_disk(
    manager: ProjectManager,
    project_id: str,
    project_name: str,
    title: str,
    manual_name: str,
    req: CreateProjectRequest,
    _t: Callable[..., str],
) -> dict[str, Any]:
    style_prompt = req.style or ""
    if req.style_template_id:
        if not is_known_template(req.style_template_id):
            raise HTTPException(
                status_code=400,
                detail=_t("unknown_style_template", template_id=req.style_template_id),
            )
        style_prompt = resolve_template_prompt(req.style_template_id)

    if req.image_backend:
        raise HTTPException(status_code=400, detail=_t("deprecated_image_backend"))

    content_mode = req.content_mode or "narration"
    if content_mode == "ad":
        if req.default_duration is not None:
            raise HTTPException(status_code=400, detail=_t("ad_no_default_duration"))
        if req.generation_mode == "grid":
            raise HTTPException(status_code=400, detail=_t("ad_grid_not_supported"))
    else:
        if req.target_duration is not None:
            raise HTTPException(status_code=400, detail=_t("ad_only_field", field="target_duration"))
        if req.brief is not None:
            raise HTTPException(status_code=400, detail=_t("ad_only_field", field="brief"))

    for field_name in (
        "video_backend",
        "image_provider_t2i",
        "image_provider_i2i",
        "text_backend_script",
        "text_backend_overview",
        "text_backend_style",
    ):
        value = getattr(req, field_name)
        if value:
            validate_backend_value(value, field_name, _t)

    try:
        manager.create_project(project_id, content_mode=req.content_mode or "narration")
    except FileExistsError:
        raise HTTPException(status_code=400, detail=_t("project_exists", name=project_name))
    extras = {
        field: value
        for field in (
            "video_backend",
            "image_provider_t2i",
            "image_provider_i2i",
            "text_backend_script",
            "text_backend_overview",
            "text_backend_style",
        )
        if (value := getattr(req, field))
    }
    if req.model_settings is not None:
        extras["model_settings"] = req.model_settings
    if req.generation_mode is not None:
        extras["generation_mode"] = req.generation_mode
    with project_change_source("webui"):
        project = manager.create_project_metadata(
            project_id,
            title or manual_name,
            style_prompt,
            req.content_mode,
            aspect_ratio=req.aspect_ratio,
            default_duration=req.default_duration,
            style_template_id=req.style_template_id,
            extras=extras or None,
            target_duration=req.target_duration,
            brief=req.brief,
            source_kind=req.source_kind,
        )
    return {"success": True, "id": project_id, "name": project_name, "project": project}


@router.get("/projects/{project_id}/video-capabilities")
async def get_video_capabilities(
    project_id: str,
    _user: CurrentUser,
    _t: Translator,
):
    """解析当前项目视频模型能力 + 用户项目偏好。

    三级模型选择（项目 > 系统设置 > 系统默认）后，读 model 的 `supported_durations`
    并派生 `max_duration`；同时带回 `project.json.default_duration`（用户偏好）。
    所有 generation_mode（storyboard/grid/reference_video）都可复用。
    """
    resolver = ConfigResolver(async_session_factory)
    try:
        await _require_project_row(project_id, _user, _t, minimum_role=ROLE_VIEW)
        return await resolver.video_capabilities(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=_t("video_capabilities_unresolved", name=project_id, reason=str(exc)),
        ) from exc


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    _user: CurrentUser,
    _t: Translator,
):
    """获取项目详情（含实时计算字段）"""
    try:
        async with async_session_factory() as session:
            async with session.begin():
                access = await require_tenant_access(session, _user, minimum_role=ROLE_VIEW)
                await set_tenant_context(session, user_id=_user.id, tenant_id=access.id)
                row = await ProjectRepository(session, tenant_id=access.id).get_by_id(project_id)
                if row is None:
                    raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))
                project_name = row.name

        def _sync():
            manager = get_tenant_project_manager(access.id)
            calculator = StatusCalculator(manager)
            if not manager.project_exists(project_id):
                raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))

            project = manager.load_project(project_id)

            project = calculator.enrich_project(project_id, project)

            # 加载所有剧本并注入计算字段
            scripts = {}
            for ep in project.get("episodes", []):
                script_file = ep.get("script_file", "")
                if script_file:
                    try:
                        script = manager.load_script(project_id, script_file)
                        script = calculator.enrich_script(script)
                        key = (
                            script_file.replace("scripts/", "", 1)
                            if script_file.startswith("scripts/")
                            else script_file
                        )
                        scripts[key] = script
                    except FileNotFoundError:
                        logger.debug("剧本文件不存在，跳过: %s/%s", project_id, script_file)

            project_path = manager.get_project_path(project_id)
            fingerprints = compute_asset_fingerprints(project_path)

            return {
                "id": project_id,
                "name": project_name,
                "project": project,
                "scripts": scripts,
                "asset_fingerprints": fingerprints,
            }

        return await asyncio.to_thread(_sync)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))
    except HTTPException:
        raise
    except Exception:
        logger.exception("请求处理失败")
        raise HTTPException(status_code=500, detail=_t("internal_server_error"))


@router.patch("/projects/{project_id}")
async def update_project(project_id: str, req: UpdateProjectRequest, _user: CurrentUser, _t: Translator):
    """更新项目元数据"""
    try:
        async with async_session_factory() as session:
            async with session.begin():
                access = await require_tenant_access(session, _user, minimum_role=ROLE_ADMIN)
                await set_tenant_context(session, user_id=_user.id, tenant_id=access.id)
                row = await ProjectRepository(session, tenant_id=access.id).get_by_id(project_id)
                if row is None:
                    raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))
                project_name = row.name

        def _sync():
            manager = get_tenant_project_manager(access.id)
            if req.content_mode is not None:
                raise HTTPException(
                    status_code=400,
                    detail=_t("project_id_not_editable"),
                )
            if "source_kind" in req.model_fields_set:
                raise HTTPException(
                    status_code=400,
                    detail=_t("source_kind_not_editable"),
                )

            # legacy image_backend 已退役（拆为 image_provider_t2i/i2i）；写路径直接拒绝，
            # 避免迁移后再写时被解析链忽略、静默落到全局默认的另一供应商。
            if req.image_backend:
                raise HTTPException(status_code=400, detail=_t("deprecated_image_backend"))

            def _mutate(project: dict) -> None:
                # 整段 read-modify-write 在单一 _project_lock 内完成，避免并发 PATCH / 任务回写丢更新
                is_ad = project.get("content_mode") == "ad"
                if req.title is not None:
                    project["title"] = req.title
                if req.style is not None:
                    project["style"] = req.style
                for field in (
                    "video_backend",
                    "image_provider_t2i",
                    "image_provider_i2i",
                    "audio_backend",
                    "text_backend_script",
                    "text_backend_overview",
                    "text_backend_style",
                ):
                    if field in req.model_fields_set:
                        value = getattr(req, field)
                        if value:
                            validate_backend_value(value, field, _t)
                            project[field] = value
                        else:
                            project.pop(field, None)

                if "video_generate_audio" in req.model_fields_set:
                    if req.video_generate_audio is None:
                        project.pop("video_generate_audio", None)
                    else:
                        project["video_generate_audio"] = req.video_generate_audio
                # 旁白音色：照供应商文档填的字符串 id；空串 = 清除回落全局默认
                if "narration_voice" in req.model_fields_set:
                    voice = (req.narration_voice or "").strip()
                    if voice:
                        project["narration_voice"] = voice
                    else:
                        project.pop("narration_voice", None)
                # 旁白语速：仅做正有限数卫生校验（拒绝 0/负数/inf/nan），取值范围由各供应商约束；null = 清除
                if "narration_speed" in req.model_fields_set:
                    if req.narration_speed is None:
                        project.pop("narration_speed", None)
                    else:
                        speed = float(req.narration_speed)
                        if not math.isfinite(speed) or speed <= 0:
                            raise HTTPException(status_code=422, detail=_t("narration_speed_must_be_positive"))
                        project["narration_speed"] = speed
                if "aspect_ratio" in req.model_fields_set and req.aspect_ratio is not None:
                    project["aspect_ratio"] = req.aspect_ratio
                if "generation_mode" in req.model_fields_set:
                    if is_ad and req.generation_mode == "grid":
                        raise HTTPException(status_code=400, detail=_t("ad_grid_not_supported"))
                    if req.generation_mode is None:
                        project.pop("generation_mode", None)
                    else:
                        project["generation_mode"] = req.generation_mode
                if "default_duration" in req.model_fields_set:
                    # ad 项目对字段出现本身即拒绝（含 null）：与创建路径"禁写字段"契约一致，
                    # 避免 null 走删除分支静默返回 200
                    if is_ad:
                        raise HTTPException(status_code=400, detail=_t("ad_no_default_duration"))
                    if req.default_duration is None:
                        project.pop("default_duration", None)
                    else:
                        project["default_duration"] = req.default_duration
                if "target_duration" in req.model_fields_set:
                    if not is_ad:
                        raise HTTPException(status_code=400, detail=_t("ad_only_field", field="target_duration"))
                    if req.target_duration is None:
                        raise HTTPException(status_code=400, detail=_t("ad_target_duration_required"))
                    project["target_duration"] = req.target_duration
                if "brief" in req.model_fields_set:
                    if not is_ad:
                        raise HTTPException(status_code=400, detail=_t("ad_only_field", field="brief"))
                    project["brief"] = req.brief if req.brief is not None else ""

                if "style_template_id" in req.model_fields_set:
                    if req.style_template_id is None:
                        # 取消模版选择：同时清掉展开的 style prompt，避免遗留孤儿文本
                        project.pop("style_template_id", None)
                        project["style"] = ""
                    else:
                        if not is_known_template(req.style_template_id):
                            raise HTTPException(
                                status_code=400,
                                detail=_t("unknown_style_template", template_id=req.style_template_id),
                            )
                        project["style_template_id"] = req.style_template_id
                        project["style"] = resolve_template_prompt(req.style_template_id)
                        # 强互斥:模版与参考图二选一
                        project.pop("style_image", None)
                        project.pop("style_description", None)

                if req.clear_style_image:
                    # 显式清除自定义参考图，用于"取消风格"流程
                    project.pop("style_image", None)
                    project.pop("style_description", None)

                if "model_settings" in req.model_fields_set:
                    if req.model_settings is None:
                        project.pop("model_settings", None)
                    else:
                        project["model_settings"] = req.model_settings

                if "episodes" in req.model_fields_set and req.episodes is not None:
                    # 合并 episodes：保留现有 episode 的完整数据，仅更新请求中显式提供的字段。
                    # 使用 model_fields_set（而非 exclude_none）判断字段是否显式出现，使得
                    # `generation_mode: null` 可用于清空集级覆盖、回退到项目级模式继承。
                    # 白名单同时拦截 StatusCalculator 注入的计算字段（scenes_count / status
                    # / storyboards / videos 等），防止写回 project.json。
                    existing_list = project.get("episodes", [])
                    patch_map: dict[int, EpisodePatch] = {}
                    for ep in req.episodes:
                        if is_ad and ep.generation_mode == "grid":
                            raise HTTPException(status_code=400, detail=_t("ad_grid_not_supported"))
                        patch_map[ep.episode] = ep  # 重复编号：后者覆盖前者

                    new_episodes: list[dict] = []
                    for existing_ep in existing_list:
                        ep_num = existing_ep.get("episode")
                        patch = patch_map.pop(ep_num, None)
                        if patch is None:
                            new_episodes.append(existing_ep)
                            continue
                        updated = dict(existing_ep)
                        for field_name in EPISODE_PERSIST_FIELDS:
                            if field_name not in patch.model_fields_set:
                                continue
                            value = getattr(patch, field_name)
                            if value is None:
                                updated.pop(field_name, None)
                            else:
                                updated[field_name] = value
                        new_episodes.append(updated)

                    for unknown_ep in patch_map:
                        logger.warning("Skipping patch for unknown episode %s", unknown_ep)

                    project["episodes"] = new_episodes

            with project_change_source("webui"):
                return {
                    "success": True,
                    "id": project_id,
                    "name": project_name,
                    "project": manager.update_project(project_id, _mutate),
                }

        return await asyncio.to_thread(_sync)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))
    except HTTPException:
        raise
    except Exception:
        logger.exception("请求处理失败")
        raise HTTPException(status_code=500, detail=_t("internal_server_error"))


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, _user: CurrentUser, _t: Translator):
    """删除项目"""
    try:
        async with async_session_factory() as session:
            async with session.begin():
                access = await require_tenant_access(session, _user, minimum_role=ROLE_ADMIN)
                await set_tenant_context(session, user_id=_user.id, tenant_id=access.id)
                row = await ProjectRepository(session, tenant_id=access.id).get_by_id(project_id)
                if row is None:
                    raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))
                project_name = row.name

        def _sync():
            get_tenant_project_manager(access.id).delete_project_directory(project_id)
            return {"success": True, "message": _t("project_deleted", name=project_name)}

        result = await asyncio.to_thread(_sync)
        async with async_session_factory() as session:
            async with session.begin():
                await set_tenant_context(session, user_id=_user.id, tenant_id=access.id)
                await ProjectRepository(session, tenant_id=access.id).delete_by_id(project_id)
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))
    except HTTPException:
        raise
    except Exception:
        logger.exception("请求处理失败")
        raise HTTPException(status_code=500, detail=_t("internal_server_error"))


@router.get("/projects/{project_id}/scripts/{script_file}")
async def get_script(project_id: str, script_file: str, _user: CurrentUser, _t: Translator):
    """获取剧本内容"""
    try:
        _access, _row, manager = await _require_project_row(project_id, _user, _t, minimum_role=ROLE_VIEW)
        script = await asyncio.to_thread(manager.load_script, project_id, script_file)
        return {"script": script}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("script_not_found", name=script_file))
    except HTTPException:
        raise
    except Exception:
        logger.exception("请求处理失败")
        raise HTTPException(status_code=500, detail=_t("internal_server_error"))


class UpdateSceneRequest(BaseModel):
    script_file: str
    updates: dict


@router.patch("/projects/{project_id}/script-scenes/{scene_id}")
async def update_scene(project_id: str, scene_id: str, req: UpdateSceneRequest, _user: CurrentUser, _t: Translator):
    """更新 drama 模式剧本中的单个场景镜头（按 scene_id 定位）。

    路径与项目场景资产 CRUD（``/projects/{name}/scenes/{entry_name}``）做明确区分，
    避免 FastAPI 按注册顺序优先匹配本端点导致 SceneCard 保存请求被截获、Pydantic
    必填字段校验返回双 "Field required"。
    """
    try:
        _access, _row, manager = await _require_project_row(project_id, _user, _t, minimum_role=ROLE_MEMBER)

        def _sync():
            # 整段 RMW 在单一 _script_lock 内完成；未命中时在锁内 raise，跳过写回
            matched_scene: dict[str, Any] | None = None
            with project_change_source("webui"):
                with manager.locked_script(project_id, req.script_file) as script:
                    for scene in script.get("scenes", []):
                        if scene.get("scene_id") == scene_id:
                            matched_scene = scene
                            # 更新允许的字段
                            for key, value in req.updates.items():
                                if key in [
                                    "duration_seconds",
                                    "image_prompt",
                                    "video_prompt",
                                    "characters_in_scene",
                                    "scenes",
                                    "props",
                                    "segment_break",
                                    "utterances",
                                    "note",
                                ]:
                                    if value is None and key != "note":
                                        continue
                                    scene[key] = value
                            break

                    if matched_scene is None:
                        raise HTTPException(status_code=404, detail=_t("scene_not_found", id=scene_id))
            return {"success": True, "scene": matched_scene}

        return await asyncio.to_thread(_sync)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("script_not_found", name=req.script_file))
    except ValueError as exc:
        # 结构校验失败、集号错配、非法文件名都抛 ValueError（ScriptStructureValidationError
        # 即其子类）：统一转 422 客户端错误，避免落到下面的 500 兜底。
        raise HTTPException(
            status_code=422,
            detail=_t("script_validation_failed", details=str(exc)),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("请求处理失败")
        raise HTTPException(status_code=500, detail=_t("internal_server_error"))


class UpdateShotRequest(BaseModel):
    script_file: str
    updates: dict


# ad 镜头 PATCH 白名单：shot_id（定位键）与 generated_assets（运行时状态）不可改写。
_SHOT_UPDATABLE_FIELDS = (
    "section",
    "voiceover_text",
    "duration_seconds",
    "image_prompt",
    "video_prompt",
    "characters_in_shot",
    "scenes",
    "props",
    "products_in_shot",
    "transition_to_next",
    "note",
)


def _require_ad_script(script: dict, _t: Translator) -> list[dict]:
    """断言剧本是 ad 形状（content_mode=ad 且含 shots 键），返回 shots 列表。

    与 update_segment 的 narration 守卫同模式：其他模式的脚本即使残留 shots 键也拒绝，
    避免被当 ad 改写。
    """
    if script.get("content_mode") != "ad" or "shots" not in script:
        raise HTTPException(status_code=400, detail=_t("ad_mode_required"))
    shots = script.get("shots")
    # 非法形状 fail loud：静默降级为空列表会让 reorder 在客户端传空 shot_ids 时
    # 把损坏的 shots 覆盖成 []，直接丢数据。ValueError 由路由统一转 422。
    if not isinstance(shots, list):
        raise ValueError("ad script field 'shots' must be a list")
    if not all(isinstance(s, dict) for s in shots):
        raise ValueError("ad script field 'shots' contains non-object elements")
    # shot_id 缺失/脏类型同样拦下：否则 PATCH 按 id 定位会误报 404，
    # reorder 的 s["shot_id"] 索引会 KeyError 变 500。
    if not all(isinstance(s.get("shot_id"), str) and s["shot_id"] for s in shots):
        raise ValueError("ad script field 'shots' contains elements missing valid 'shot_id'")
    # shot_id 是单镜头身份键：重复值会让 PATCH 静默更新首个命中项、reorder 失去 1:1 映射
    shot_ids = [s["shot_id"] for s in shots]
    if len(set(shot_ids)) != len(shot_ids):
        raise ValueError("ad script field 'shots' contains duplicate 'shot_id' values")
    return shots


@router.patch("/projects/{project_id}/script-shots/{shot_id}")
async def update_shot(project_id: str, shot_id: str, req: UpdateShotRequest, _user: CurrentUser, _t: Translator):
    """更新 ad 模式剧本中的单个镜头（按 shot_id 定位）。

    路径风格与 ``script-scenes`` 对齐；口播文案 / section / 时长 / 引用列表等
    白名单字段可改，结构合法性由写盘统一入口的「不更坏」校验兜底。
    """
    try:
        _access, _row, manager = await _require_project_row(project_id, _user, _t, minimum_role=ROLE_MEMBER)

        def _sync():
            # 整段 RMW 在单一 _script_lock 内完成；模式不符 / 未命中时在锁内 raise，跳过写回
            matched_shot: dict[str, Any] | None = None
            with project_change_source("webui"):
                with manager.locked_script(project_id, req.script_file) as script:
                    for shot in _require_ad_script(script, _t):
                        if shot.get("shot_id") == shot_id:
                            matched_shot = shot
                            for key, value in req.updates.items():
                                if key in _SHOT_UPDATABLE_FIELDS:
                                    # note 允许显式置 None（清空备注），其余字段 None 视为未提供
                                    if value is None and key != "note":
                                        continue
                                    shot[key] = value
                            break

                    if matched_shot is None:
                        raise HTTPException(status_code=404, detail=_t("shot_not_found", id=shot_id))
            return {"success": True, "shot": matched_shot}

        return await asyncio.to_thread(_sync)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("script_not_found", name=req.script_file))
    except ValueError as exc:
        # 结构校验失败、集号错配、非法文件名都抛 ValueError（ScriptStructureValidationError
        # 即其子类）：统一转 422 客户端错误，避免落到下面的 500 兜底。
        raise HTTPException(
            status_code=422,
            detail=_t("script_validation_failed", details=str(exc)),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("请求处理失败")
        raise HTTPException(status_code=500, detail=_t("internal_server_error"))


class ReorderShotsRequest(BaseModel):
    script_file: str
    shot_ids: list[str]


@router.post("/projects/{project_id}/script-shots/reorder")
async def reorder_shots(project_id: str, req: ReorderShotsRequest, _user: CurrentUser, _t: Translator):
    """按给定全排列重排 ad 剧本的 shots 顺序（与参考视频 units/reorder 同语义）。"""
    try:
        _access, _row, manager = await _require_project_row(project_id, _user, _t, minimum_role=ROLE_MEMBER)

        def _sync():
            with project_change_source("webui"):
                with manager.locked_script(project_id, req.script_file) as script:
                    shots = _require_ad_script(script, _t)
                    existing_ids = [s.get("shot_id") for s in shots]

                    # 校验失败 → 在锁内 raise 400，跳过写回
                    error_kind = full_permutation_error(existing_ids, req.shot_ids)
                    if error_kind is not None:
                        detail_key = {
                            "length": "shot_ids_length_mismatch",
                            "duplicate": "duplicate_shot_ids",
                            "mismatch": "shot_ids_mismatch",
                        }[error_kind]
                        raise HTTPException(status_code=400, detail=_t(detail_key))

                    by_id = {s["shot_id"]: s for s in shots}
                    reordered = [by_id[sid] for sid in req.shot_ids]
                    script["shots"] = reordered
            return {"success": True, "shots": reordered}

        return await asyncio.to_thread(_sync)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("script_not_found", name=req.script_file))
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=_t("script_validation_failed", details=str(exc)),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("请求处理失败")
        raise HTTPException(status_code=500, detail=_t("internal_server_error"))


class UpdateSegmentRequest(BaseModel):
    script_file: str
    duration_seconds: int | None = None
    segment_break: bool | None = None
    image_prompt: dict | str | None = None
    video_prompt: dict | str | None = None
    transition_to_next: str | None = None
    note: str | None = None
    characters_in_segment: list[str] | None = None
    scenes: list[str] | None = None
    props: list[str] | None = None


class UpdateOverviewRequest(BaseModel):
    synopsis: str | None = None
    genre: str | None = None
    theme: str | None = None
    world_setting: str | None = None


class UpdateEpisodeRequest(BaseModel):
    title: str


@router.patch("/projects/{project_id}/segments/{segment_id}")
async def update_segment(
    project_id: str, segment_id: str, req: UpdateSegmentRequest, _user: CurrentUser, _t: Translator
):
    """更新说书模式片段"""
    try:
        _access, _row, manager = await _require_project_row(project_id, _user, _t, minimum_role=ROLE_MEMBER)

        def _sync():
            # 整段 RMW 在单一 _script_lock 内完成；模式不符 / 未命中时在锁内 raise，跳过写回
            matched_segment: dict[str, Any] | None = None
            with project_change_source("webui"):
                with manager.locked_script(project_id, req.script_file) as script:
                    # 检查是否为说书模式：仅 narration 且含 segments 键才放行；
                    # drama 脚本即使残留 segments 键也拒绝，避免被当 narration 改写
                    if script.get("content_mode") != "narration" or "segments" not in script:
                        raise HTTPException(status_code=400, detail=_t("narration_mode_required"))

                    for segment in script.get("segments", []):
                        if segment.get("segment_id") == segment_id:
                            matched_segment = segment
                            if req.duration_seconds is not None:
                                segment["duration_seconds"] = req.duration_seconds
                            if req.segment_break is not None:
                                segment["segment_break"] = req.segment_break
                            if req.image_prompt is not None:
                                segment["image_prompt"] = req.image_prompt
                            if req.video_prompt is not None:
                                segment["video_prompt"] = req.video_prompt
                            if req.transition_to_next is not None:
                                segment["transition_to_next"] = req.transition_to_next
                            if "note" in req.model_fields_set:
                                segment["note"] = req.note
                            for field in ("characters_in_segment", "scenes", "props"):
                                if field in req.model_fields_set:
                                    segment[field] = getattr(req, field) or []
                            break

                    if matched_segment is None:
                        raise HTTPException(status_code=404, detail=_t("segment_not_found", id=segment_id))
            return {"success": True, "segment": matched_segment}

        return await asyncio.to_thread(_sync)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("script_not_found", name=req.script_file))
    except ValueError as exc:
        # 结构校验失败、集号错配、非法文件名都抛 ValueError（ScriptStructureValidationError
        # 即其子类）：统一转 422 客户端错误，避免落到下面的 500 兜底。
        raise HTTPException(
            status_code=422,
            detail=_t("script_validation_failed", details=str(exc)),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("请求处理失败")
        raise HTTPException(status_code=500, detail=_t("internal_server_error"))


@router.patch("/projects/{project_id}/episodes/{episode}")
async def update_episode(project_id: str, episode: int, req: UpdateEpisodeRequest, _user: CurrentUser, _t: Translator):
    """更新分集顶层元数据（当前仅标题）。

    以剧本 scripts/*.json 顶层 title 为唯一真相源：走 locked_episode_script 在
    「脚本锁 → 项目锁」临界区内改剧本 title，并内联 _apply_episode_sync 把镜像同步回
    project.json 的 episodes[].title，原子且无 TOCTOU。镜像由 PATCH /projects 改写的入口
    已移除（title 不在 EPISODE_PERSIST_FIELDS），杜绝第二真相源。
    """
    title = req.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail=_t("episode_title_empty"))

    try:
        _access, _row, manager = await _require_project_row(project_id, _user, _t, minimum_role=ROLE_MEMBER)

        def _sync():
            def _resolve(project: dict) -> str:
                episodes = project.get("episodes") or []
                meta = next((e for e in episodes if e.get("episode") == episode), None)
                if meta is None or not meta.get("script_file"):
                    raise HTTPException(status_code=404, detail=_t("episode_not_found", episode=episode))
                return meta["script_file"]

            with project_change_source("webui"):
                try:
                    with manager.locked_episode_script(project_id, _resolve) as script:
                        script["title"] = title
                except FileNotFoundError as exc:
                    if not manager.project_exists(project_id):
                        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id)) from exc
                    # project.json 指向的脚本文件已删除/移动（stale 绑定）
                    raise HTTPException(status_code=404, detail=_t("ref_script_missing")) from exc
                except EpisodeScriptReboundError as exc:
                    logger.info("episode script rebound during title update: %s", exc)
                    raise HTTPException(status_code=409, detail=_t("ref_script_rebound")) from exc
                except ValueError as exc:
                    raise HTTPException(
                        status_code=422, detail=_t("script_validation_failed", details=str(exc))
                    ) from exc

            # 返回刚写入的值（前端保存后整体 refreshProject，不强依赖此返回）。
            # 不再锁后二次 load_project：省一次读盘，且避免锁外读取被并发写者污染返回值。
            return {"success": True, "episode": {"episode": episode, "title": title}}

        return await asyncio.to_thread(_sync)
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))
    except Exception:
        logger.exception("请求处理失败")
        raise HTTPException(status_code=500, detail=_t("internal_server_error"))


# ==================== 源文件管理 ====================


@router.post("/projects/{project_id}/source")
async def set_project_source(
    project_id: Annotated[str, FastAPIPath(pattern=r"^[a-zA-Z0-9_-]+$")],
    _user: CurrentUser,
    _t: Translator,
    generate_overview: Annotated[bool, Form()] = True,
    content: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
):
    """上传小说源文件或直接提交文本内容，可选触发 AI 概述生成。

    两种输入方式（互斥，均使用 multipart/form-data）：
    - file：上传 .txt/.md 文件，文件名取自上传文件
    - content：直接提交文本内容，自动命名为 novel.txt

    最大 200000 字符（约 10 万汉字）。
    """
    MAX_CHARS = 200_000
    ALLOWED_SUFFIXES = {".txt", ".md"}

    if not content and not file:
        raise HTTPException(status_code=400, detail=_t("content_or_file_required"))
    if content and file:
        raise HTTPException(status_code=400, detail=_t("one_of_content_or_file"))

    try:
        _access, _row, manager = await _require_project_row(project_id, _user, _t, minimum_role=ROLE_MEMBER)

        # 异步读取上传文件
        raw: bytes | None = None
        original_name: str = "novel.txt"
        if file:
            original_name = file.filename or "novel.txt"
            suffix = Path(original_name).suffix.lower()
            if suffix not in ALLOWED_SUFFIXES:
                raise HTTPException(status_code=400, detail=_t("unsupported_file_type", name=suffix))
            if file.size is not None and file.size > MAX_CHARS * 4:
                raise HTTPException(status_code=400, detail=_t("file_too_large", max_chars=MAX_CHARS))
            raw = await file.read()
        text_content: str = content or ""

        # 同步文件 I/O 在线程中执行
        def _sync_write():
            if not manager.project_exists(project_id):
                raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))
            project_dir = manager.get_project_path(project_id)
            source_dir = project_dir / "source"
            source_dir.mkdir(parents=True, exist_ok=True)

            if raw is not None:
                safe_filename = Path(original_name).name
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    raise HTTPException(status_code=400, detail=_t("invalid_encoding"))
                if len(text) > MAX_CHARS:
                    raise HTTPException(status_code=400, detail=_t("file_too_large", max_chars=MAX_CHARS))
                (source_dir / safe_filename).write_text(text, encoding="utf-8")
                return safe_filename, len(text)
            else:
                if len(text_content) > MAX_CHARS:
                    raise HTTPException(status_code=400, detail=_t("file_too_large", max_chars=MAX_CHARS))
                safe_filename = "novel.txt"
                (source_dir / safe_filename).write_text(text_content, encoding="utf-8")
                return safe_filename, len(text_content)

        safe_filename, chars = await asyncio.to_thread(_sync_write)

        result: dict = {"success": True, "filename": safe_filename, "chars": chars}

        if generate_overview:
            try:
                with project_change_source("webui"):
                    overview = await manager.generate_overview(project_id)
                result["overview"] = overview
            except Exception as ov_err:
                result["overview"] = None
                result["overview_error"] = (
                    _t("overview_ai_response_invalid") if isinstance(ov_err, PydanticValidationError) else str(ov_err)
                )

        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("请求处理失败")
        raise HTTPException(status_code=500, detail=_t("internal_server_error"))
    finally:
        if file:
            await file.close()


# ==================== 项目概述管理 ====================


@router.post("/projects/{project_id}/generate-overview")
async def generate_overview(project_id: str, _user: CurrentUser, _t: Translator):
    """使用 AI 生成项目概述"""
    try:
        _access, _row, manager = await _require_project_row(project_id, _user, _t, minimum_role=ROLE_MEMBER)
        with project_change_source("webui"):
            overview = await manager.generate_overview(project_id)
        return {"success": True, "overview": overview}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))
    except PydanticValidationError:
        # 模型输出未通过 schema 校验（后端降级仍失守时的最后防线），
        # 裸 pydantic 错误串含模型原始输出片段，不透传给用户
        logger.exception("概述生成响应解析失败")
        raise HTTPException(status_code=400, detail=_t("overview_ai_response_invalid"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        logger.exception("请求处理失败")
        raise HTTPException(status_code=500, detail=_t("internal_server_error"))


@router.patch("/projects/{project_id}/overview")
async def update_overview(project_id: str, req: UpdateOverviewRequest, _user: CurrentUser, _t: Translator):
    """更新项目概述（手动编辑）"""
    try:
        _access, _row, manager = await _require_project_row(project_id, _user, _t, minimum_role=ROLE_MEMBER)

        def _sync():
            captured: dict[str, Any] = {}

            def _mutate(project: dict) -> None:
                # 整段 RMW 在单一 _project_lock 内完成，避免与并发生成的 overview 回写互相覆盖
                if "overview" not in project:
                    project["overview"] = {}
                if req.synopsis is not None:
                    project["overview"]["synopsis"] = req.synopsis
                if req.genre is not None:
                    project["overview"]["genre"] = req.genre
                if req.theme is not None:
                    project["overview"]["theme"] = req.theme
                if req.world_setting is not None:
                    project["overview"]["world_setting"] = req.world_setting
                captured["overview"] = project["overview"]

            with project_change_source("webui"):
                manager.update_project(project_id, _mutate)
            return {"success": True, "overview": captured["overview"]}

        return await asyncio.to_thread(_sync)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_t("project_not_found", name=project_id))
    except HTTPException:
        raise
    except Exception:
        logger.exception("请求处理失败")
        raise HTTPException(status_code=500, detail=_t("internal_server_error"))
