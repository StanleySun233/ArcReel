# Sprint Backlog: Tenant Project Permission Model

**Date:** 20260711
**Status:** planned
**Product brief:** 基于当前对话：ArcReel 新商业发行版需要重新收敛 user/tenant/project 权限关系。租户承载系统配置和权限，项目只属于一个租户，所有项目业务逻辑按 project_id 查询。Issued Tokens 功能本轮先下掉，后续再启用；这里不包括 CaMeL provider keys、媒体供应商凭证、Agent 凭证。用量统计需要按 tenant/project 分组。无旧版本兼容。
**Main integration branch:** main

## Sprint Goal

形成可串行实现的权限关系设计与实施计划：明确 `user_id + tenant_id + project_id` 的边界、不变量、API 契约、文件/任务/Agent/用量链路，并按单线阶段推进，减少并行合并成本。

## Documents

- 权限关系设计: [permission-model-design.md](./permission-model-design.md)
- API 契约: [api-contract.md](./api-contract.md)
- 文档审计: [document-audit.md](./document-audit.md)
- 实现审计: [implementation-audit.md](./implementation-audit.md)

## Team

| Role | Agent Name | Progress File |
|------|------------|---------------|
| Project Manager | Root | this backlog |
| Backend | 待分配 | 待创建 |
| Frontend | 待分配 | 待创建 |
| QA | 待分配 | 待创建 |
| Product Owner | 用户确认 | |

## Planning Gates

| Gate | Owner | Required Output | Pass Condition |
|------|-------|-----------------|----------------|
| G1 权限模型确认 | 用户 + PM | `permission-model-design.md` | 用户确认 user/tenant/project 不变量、role 矩阵、Issued Tokens 暂停策略无歧义 |
| G2 API 契约确认 | 用户 + PM | `api-contract.md` | 用户确认项目路由全部转 project_id，错误码、用量接口、Issued Tokens 禁用行为可接受 |
| G3 串行执行边界确认 | PM | 本 backlog 的串行实施顺序 | 用户确认不拆 story、不启用 worktree 并行开发 |

Gate 已按用户确认口径更新：Issued Tokens 后台 403、前端按钮 disabled；viewer 可查询成员；项目删除仅 owner/admin；本轮串行实现，不拆 story、不启用 worktree 并行。

## Serial Implementation Plan

### Phase 0 - 契约冻结

**Status:** planned

**Acceptance Criteria**
- [x] `permission-model-design.md` 明确定义 User/Tenant/Project 关系、不变量、role 矩阵、ProjectContextResolver、Issued Tokens 暂停策略。
- [x] `api-contract.md` 明确定义项目 API 全部使用 `project_id`，错误码、租户 API、用量 API、文件 API、任务 API。
- [x] 本 backlog 明确串行执行顺序，不再拆 story 或启用并行 worktree。

### Phase 1 - 后端 ProjectContext 和项目 ID 化

**Status:** planned

**Acceptance Criteria**
- [ ] 新增或收敛 `ProjectContextResolver`，所有项目路由和 service 从该入口获取项目上下文。
- [ ] 项目路由从 `{name}` 改为 `{project_id}`，不保留旧路由兼容。
- [ ] 项目文件路径改为 `_tenants/{tenant_id}/projects/{project_id}/project.json`。
- [ ] `projects` 表保持 `unique(tenant_id, name)`，但所有业务查询走 `project_id`。
- [ ] 跨租户同名项目测试通过。

### Phase 2 - 前端项目 ID 路由和租户上下文

**Status:** planned

**Acceptance Criteria**
- [ ] 前端 route、API client、store、localStorage、SSE channel、task polling 全部使用 `project_id`。
- [ ] 项目名仅用于 UI 展示和重命名输入。
- [ ] 登录默认进入个人空间；切租户必须用户手动触发。
- [ ] `tenant_role` 只控制 UI 展示；403 stale role 触发刷新当前 tenant token。

### Phase 3 - 任务、生成、Agent、文件链路上下文化

**Status:** planned

**Acceptance Criteria**
- [ ] 所有生成入口按当前 tenant 和 `project_id` 入队。
- [ ] `tasks` 持久化 `tenant_id/project_id/requested_by_user_id`。
- [ ] worker 使用任务持久化上下文读取项目、租户配置、provider credential。
- [ ] `assistant` routes 使用 `project_id`。
- [ ] Agent session 表和 session store 持久化 `tenant_id/project_id/user_id`。
- [ ] Agent cwd 由 ProjectContextResolver 返回。
- [ ] MCP 工具通过注入上下文获取 project_id，不接受项目名推断。
- [ ] `file_links` 使用 `tenant_id/project_id/entity_type/entity_id`，不使用 project name。
- [ ] `project.json` 内媒体引用全部是 `file_id`。
- [ ] 后端 service 直接读文件，前端只拿短签名 URL。

### Phase 4 - 用量统计和 Issued Tokens 禁用

**Status:** planned

**Acceptance Criteria**
- [ ] `api_calls` 或用量事实表包含 `tenant_id/project_id/user_id/task_id/provider/model/media_type/cost/status`。
- [ ] 后端提供租户总览、项目详情、用户维度查询。
- [ ] 聚合查询不按项目名 group，只 join name 作展示。
- [ ] 前端用量页支持 tenant/project 分组显示。
- [x] 前端设置页 Issued Tokens 按钮 disabled。
- [x] 后台 `/api-keys` 列表、创建、更新、删除统一返回 `403 feature_disabled`。
- [x] Issued Tokens 不参与认证依赖链路。
- [x] CaMeL provider keys、媒体供应商凭证、Agent 凭证不受影响。

### Phase 5 - 全链路审计和测试

**Status:** planned

**Acceptance Criteria**
- [ ] 场景矩阵覆盖 owner/admin/member/view。
- [ ] 场景矩阵覆盖 viewer 查询成员列表。
- [ ] 场景矩阵覆盖只允许 owner/admin 删除项目。
- [ ] 场景矩阵覆盖跨租户同名项目。
- [ ] 场景矩阵覆盖创建项目、上传文件、生成图片、生成视频、Agent 输入文本、资产导入、用量查看。
- [x] 场景矩阵覆盖 Issued Tokens disabled。
- [ ] 自动测试和必须手动验证项都写入 QA evidence。

## Serial File Touch Order

| Order | Area | Representative Paths |
|-------|------|----------------------|
| 1 | 契约与 schema | `docs/20260711/tenant-project-permission-model/*`, `lib/db/models/*`, Alembic migration |
| 2 | 后端项目上下文 | `lib/db/repositories/project*`, `lib/project_manager.py`, `server/routers/projects.py` |
| 3 | 前端项目上下文 | `frontend/src/api.ts`, `frontend/src/stores/*project*`, `frontend/src/routes/*` |
| 4 | 生成任务 | `lib/generation_queue.py`, `server/services/generation_tasks.py`, `server/routers/generate.py` |
| 5 | Agent runtime | `server/routers/assistant.py`, `server/agent_runtime/*`, `lib/agent_session_store/*` |
| 6 | 文件和资产 | `lib/files/*`, `server/routers/files.py`, `lib/db/repositories/asset*` |
| 7 | 用量统计 | `server/routers/usage.py`, `lib/usage_tracker.py` |
| 8 | Issued Tokens 禁用 | `server/routers/api_keys.py`, `frontend/src/pages/settings*` |
| 9 | 测试和审计 | `tests/*`, `frontend/src/**/*.test.*`, `scenario-test-matrix.md` |

## Execution Workspace

本轮不使用 worktree 并行开发。所有实现串行落在当前集成分支，按阶段提交，每个阶段完成后再进入下一阶段。

## Blockers

| Date | Story/Subtask | Owner | Blocker | Resolution |
|------|---------------|-------|---------|------------|
| 2026-07-11 | G1/G2/G3 | 用户 + PM | Issued Tokens 禁用行为、role 权限矩阵、project_id 路由迁移口径和串行执行方式 | 已确认：后台 `/api-keys` 403，前端按钮 disabled；viewer 可查成员；项目删除仅 owner/admin；串行实现 |
