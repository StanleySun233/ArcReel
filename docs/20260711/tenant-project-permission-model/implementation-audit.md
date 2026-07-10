# 租户项目权限实现审计

**日期:** 20260711
**状态:** in-progress

## 已完成

### Issued Tokens 禁用

结论：已按当前发行版禁用 Issued Tokens，并保留原业务实现。

证据：

- `server/routers/api_keys.py` 保留 create/list/delete 业务代码，在入口调用 `_require_issued_tokens_enabled()`，当前统一返回 `403 feature_disabled`。
- `server/auth.py` 不再把 `arc-` token 作为 Bearer API key 认证入口。
- `frontend/src/components/pages/ApiKeysTab.tsx` 保留原 UI/创建/删除逻辑，当前通过 `ISSUED_TOKENS_ENABLED` 禁用加载、创建、删除入口。
- `frontend/src/components/pages/OpenClawModal.tsx` 的获取 API token 按钮 disabled。
- `tests/test_api_keys_router.py` 覆盖 `/api-keys` 统一 403。
- `tests/test_auth_api_key.py` 覆盖 `arc-` token 不走 Issued Token 认证分流。
- 验证命令：
  - `DATABASE_URL=postgresql+asyncpg://arcreel_app:arcreel_app_dev_password@127.0.0.1:15432/arcreel python -m pytest tests/test_api_keys_router.py tests/test_auth_api_key.py -q`
  - `python -m ruff check server/auth.py server/routers/api_keys.py tests/test_api_keys_router.py tests/test_auth_api_key.py`
  - `cd frontend && pnpm check`

## 未完成差距

### Phase 1 - 后端 ProjectContext 和项目 ID 化

当前证据：

- `lib/db/repositories/project_repo.py` 仍以 `get_by_name/touch_local_path/delete_by_name` 为主。
- `server/routers/projects.py` 路由仍大量使用 `/projects/{name}`。
- 项目本地路径仍通过 `_project_json_local_path(manager, project_name)` 生成，指向项目名目录。
- `ProjectManager` 调用仍以 project name 为主要参数。

需要完成：

- 增加 `get_by_id/touch_local_path_by_id/delete_by_id`。
- 项目 API route 参数统一改为 `{project_id}`。
- ProjectContextResolver 以 `tenant_id + project_id` 查询项目并返回 `project_name/project_root/project_json_path`。
- 项目路径统一为 `_tenants/{tenant_id}/projects/{project_id}/project.json`。
- 删除项目权限收敛为 owner/admin。

### Phase 2 - 前端项目 ID 路由和租户上下文

当前证据：

- `frontend/src/api.ts` 仍发送 `project_name` query 参数。
- `frontend/src/types/project.ts`、`workspace.ts`、`assistant.ts`、`task.ts` 仍有 `project_name` 字段。

需要完成：

- route、store、localStorage、SSE、task polling 统一使用 `project_id`。
- 项目名只作为展示字段。

### Phase 3 - 任务、生成、Agent、文件链路上下文化

当前证据：

- `server/routers/generate.py` 路由仍是 `/projects/{project_name}/generate/...`。
- `server/routers/tasks.py` 仍按 `project_name` 过滤、SSE、取消任务。
- `server/routers/assistant.py` 会话所有权仍比较 `session.project_name`。
- `server/routers/files.py`、`reference_videos.py`、`grids.py` 等链路仍有 `project_name` 参数。

需要完成：

- 任务入队持久化和读取统一用 `tenant_id + project_id`。
- Worker 读项目和配置时使用任务上下文，不按项目名查。
- Agent session 持久化 `tenant_id/project_id/user_id`。
- 文件和资产绑定使用 `tenant_id/project_id/entity_type/entity_id`。

### Phase 4 - 用量统计按租户和项目分组

当前证据：

- `server/routers/usage.py` 仍接受 `project_name` query 参数。
- 前端 usage API 仍有 `projectName` filter。

需要完成：

- 用量事实表和查询 API 使用 `project_id`。
- 聚合按 project_id 分组，project name 只作为展示 join 字段。

## 下一步串行顺序

1. 后端 ProjectRepository 和 ProjectContextResolver。
2. `server/routers/projects.py` 项目 CRUD/API 改成 project_id。
3. 前端项目 API/types/store 改成 project_id。
4. generate/tasks/assistant/files/usage 链路逐段迁移。
5. 本机 API 场景测试。
6. agent-browser 人工路径测试。
