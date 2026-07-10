# Sprint Backlog: Tenant Project Permission Model

**Date:** 20260711
**Status:** planned
**Product brief:** 基于当前对话：ArcReel 新商业发行版需要重新收敛 user/tenant/project 权限关系。租户承载系统配置和权限，项目只属于一个租户，所有项目业务逻辑按 project_id 查询。API key 功能本轮先下掉，后续再启用。用量统计需要按 tenant/project 分组。无旧版本兼容。
**Main integration branch:** main

## Sprint Goal

形成可并行实现的权限关系设计与实施计划：明确 `user_id + tenant_id + project_id` 的边界、不变量、API 契约、文件/任务/Agent/用量链路，并把后续开发拆成 worktree 可并行的原子 story。

## Documents

- 权限关系设计: [permission-model-design.md](./permission-model-design.md)
- API 契约: [api-contract.md](./api-contract.md)

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
| G1 权限模型确认 | 用户 + PM | `permission-model-design.md` | 用户确认 user/tenant/project 不变量、role 矩阵、API key 暂停策略无歧义 |
| G2 API 契约确认 | 用户 + PM | `api-contract.md` | 用户确认项目路由全部转 project_id，错误码、用量接口、API key 禁用行为可接受 |
| G3 并行实现边界确认 | PM | 本 backlog 的 File Ownership 与 Worktrees | 每个 story 文件归属唯一，共享文件标注串行 owner |

未通过 Gate 前不启动实现 agent。

## Implementation Waves

| Wave | Stories | Parallel Policy |
|------|---------|-----------------|
| 0 | Story 1 | 串行。先冻结 API/数据契约，避免后续 story 互相改口径。 |
| 1 | Story 2, Story 3 | 可并行。Story 2 做后端身份/项目上下文；Story 3 做前端路由和缓存 project_id，但以 Story 1 契约为准。 |
| 2 | Story 4, Story 5, Story 6 | 可并行但依赖 Story 2 的 ProjectContextResolver。任务/Agent/文件链路文件归属拆开。 |
| 3 | Story 7, Story 8 | 可并行。用量统计和 API key disable 不应互改业务链路文件。 |
| 4 | Story 9 | 串行 QA。覆盖所有链路，尤其视频生成、Agent、文件、跨租户同名项目。 |

## Stories

### Story 1 - 权限与 API 契约冻结

**Slug:** contract-freeze
**User value:** 后续实现不再围绕 name/project_id、API key 是否启用、tenant 权限边界反复返工。
**Status:** planned
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] `permission-model-design.md` 明确定义 User/Tenant/Project 关系、不变量、role 矩阵、ProjectContextResolver、API key 暂停策略。
- [ ] `api-contract.md` 明确定义项目 API 全部使用 `project_id`，错误码、租户 API、用量 API、文件 API、任务 API。
- [ ] Sprint backlog 拆出可 worktree 并行实现的 story，并标明共享文件串行策略。

**Engineering Subtasks**
- [ ] Root: 更新 `docs/20260711/tenant-project-permission-model/permission-model-design.md`。 (depends: none)
- [ ] Root: 更新 `docs/20260711/tenant-project-permission-model/api-contract.md`。 (depends: none)
- [ ] Root: 更新 `docs/INDEX.md` 和本 backlog。 (depends: none)

**QA Evidence:** pending

### Story 2 - 后端 Tenant ProjectContext 和项目 ID 化

**Slug:** backend-project-context
**User value:** 所有后端项目读取、写入、文件路径、权限判断都通过 `tenant_id + project_id`，不再按项目名误命中。
**Status:** planned
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] 新增或收敛 `ProjectContextResolver`，所有项目路由和 service 从该入口获取项目上下文。
- [ ] 项目路由从 `{name}` 改为 `{project_id}`，不保留旧路由兼容。
- [ ] 项目文件路径改为 `_tenants/{tenant_id}/projects/{project_id}/project.json`。
- [ ] `projects` 表保持 `unique(tenant_id, name)`，但所有业务查询走 `project_id`。
- [ ] 跨租户同名项目测试通过。

**Engineering Subtasks**
- [ ] Backend: 修改项目 ORM/repository/service 中 project lookup。 (depends: Story 1)
- [ ] Backend: 修改 `server/routers/projects.py` 和项目相关路由。 (depends: resolver)
- [ ] Backend: 修改 `lib/project_manager.py` 或引入项目上下文文件适配层。 (depends: resolver)
- [ ] Backend: 增加 project_id 路由和跨租户同名项目测试。 (depends: implementation)

**QA Evidence:** pending

### Story 3 - 前端项目 ID 路由、缓存和租户切换

**Slug:** frontend-project-id
**User value:** 前端只把项目名作为展示字段，租户切换和项目访问不会因为同名项目串租户。
**Status:** planned
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] 前端 route、API client、store、localStorage、SSE channel、task polling 全部使用 `project_id`。
- [ ] 项目名仅用于 UI 展示和重命名输入。
- [ ] 登录默认进入个人空间；切租户必须用户手动触发。
- [ ] `tenant_role` 只控制 UI 展示；403 stale role 触发刷新当前 tenant token。

**Engineering Subtasks**
- [ ] Frontend: 修改项目 route 和导航入口。 (depends: Story 1)
- [ ] Frontend: 修改 API client 类型和 project store。 (depends: API contract)
- [ ] Frontend: 修改 SSE/task polling/cache key。 (depends: API client)
- [ ] Frontend: 补充同名项目和 stale role 前端测试。 (depends: implementation)

**QA Evidence:** pending

### Story 4 - 任务、生成和视频链路上下文化

**Slug:** generation-project-context
**User value:** 用户发出生成请求时的权限和项目上下文被准确持久化，视频生成全过程不会用错租户配置或项目文件。
**Status:** planned
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] 所有生成入口按当前 tenant 和 `project_id` 入队。
- [ ] `tasks` 持久化 `tenant_id/project_id/requested_by_user_id`。
- [ ] worker 使用任务持久化上下文读取项目、租户配置、provider credential。
- [ ] 已提交任务不因后续 membership 变化被取消。
- [ ] 图片、文本、视频、音频生成链路测试覆盖。

**Engineering Subtasks**
- [ ] Backend: 修改 `lib/generation_queue.py` 和 task repository 字段使用。 (depends: Story 2)
- [ ] Backend: 修改 `server/services/generation_tasks.py`、`reference_video_tasks.py`、相关 generate routers。 (depends: ProjectContext)
- [ ] Backend: 修改 provider/config resolver 调用上下文。 (depends: task context)
- [ ] QA: 增加完整生成链路测试矩阵。 (depends: implementation)

**QA Evidence:** pending

### Story 5 - Agent 会话和工具链 project_id 化

**Slug:** agent-project-context
**User value:** 右侧 ArcReel 智能体在当前项目目录工作，所有工具调用和会话恢复都不会因为项目名或租户缺失报错。
**Status:** planned
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] `assistant` routes 使用 `project_id`。
- [ ] Agent session 表和 session store 持久化 `tenant_id/project_id/user_id`。
- [ ] Agent cwd 由 ProjectContextResolver 返回。
- [ ] MCP 工具通过注入上下文获取 project_id，不接受项目名推断。
- [ ] “右侧智能体输入文本” E2E 通过。

**Engineering Subtasks**
- [ ] Backend: 修改 `server/routers/assistant.py` 和 `server/agent_runtime/*` 会话上下文。 (depends: Story 2)
- [ ] Backend: 修改 `lib/agent_session_store/*` 和相关模型/repository。 (depends: DB contract)
- [ ] Backend: 修改 `server/agent_runtime/sdk_tools/*` 的项目上下文注入。 (depends: runtime context)
- [ ] QA: 覆盖 session create/send/stream/tool enqueue。 (depends: implementation)

**QA Evidence:** pending

### Story 6 - 文件、MinIO、资产绑定 project_id 化

**Slug:** files-assets-project-id
**User value:** 媒体产物和资产导入用 `file_id/project_id` 绑定，支持租户库、个人库、多对多快照和手动同步，不泄露对象存储路径。
**Status:** planned
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] `files` 表统一承载所有文件，object key 为 UUID 样式，alias 保存真实文件名。
- [ ] `file_links` 使用 `tenant_id/project_id/entity_type/entity_id`，不使用 project name。
- [ ] `project.json` 内媒体引用全部是 `file_id`。
- [ ] 资产 binding 支持 `parent_id` 快照和手动 sync。
- [ ] 后端 service 直接读文件，前端只拿短签名 URL。

**Engineering Subtasks**
- [ ] Backend: 审计并修改 `lib/files/*`、`server/routers/files.py`、上传路由。 (depends: Story 2)
- [ ] Backend: 修改资产库 repository/service/binding schema。 (depends: DB contract)
- [ ] Frontend: 修改媒体展示、上传、资产导入使用 file_id/signed-url。 (depends: file API)
- [ ] QA: 覆盖上传、签名 URL、资产导入、手动 sync。 (depends: implementation)

**QA Evidence:** pending

### Story 7 - 用量统计按租户和项目分组

**Slug:** usage-tenant-project
**User value:** 管理员能按租户、项目、用户、模型查看成本和调用量，普通用户只看到自己有权限的数据。
**Status:** planned
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] `api_calls` 或用量事实表包含 `tenant_id/project_id/user_id/task_id/provider/model/media_type/cost/status`。
- [ ] 后端提供租户总览、项目详情、用户维度查询。
- [ ] 聚合查询不按项目名 group，只 join name 作展示。
- [ ] 前端用量页支持 tenant/project 分组显示。

**Engineering Subtasks**
- [ ] Backend: 修改 usage model/repository/service。 (depends: Story 2)
- [ ] Backend: 修改 `server/routers/usage.py` contract。 (depends: repository)
- [ ] Frontend: 修改用量统计 UI 和类型。 (depends: usage API)
- [ ] QA: 覆盖 admin/member/view 权限下的用量可见性。 (depends: implementation)

**QA Evidence:** pending

### Story 8 - API key 功能禁用

**Slug:** disable-api-keys
**User value:** 当前阶段不会出现一条未设计完整的旁路鉴权入口，避免绕开 tenant/project 权限主线。
**Status:** planned
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] 前端设置页隐藏 API key 入口。
- [ ] 后台 API key 创建、更新、删除默认返回 feature disabled。
- [ ] API key 不参与认证依赖链路。
- [ ] 保留未来 enable 的明确开关或 seam，但不实现真实启用逻辑。

**Engineering Subtasks**
- [ ] Backend: 修改 `server/routers/api_keys.py` 和 auth dependency。 (depends: Story 1)
- [ ] Frontend: 移除或隐藏 API key 设置入口。 (depends: none)
- [ ] QA: 覆盖 UI 不可见、接口不可创建。 (depends: implementation)

**QA Evidence:** pending

### Story 9 - 全链路权限和场景测试

**Slug:** permission-e2e-audit
**User value:** 发布前确认租户、项目、文件、Agent、视频生成、用量、API key disable 全链路没有遗漏。
**Status:** planned
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] 场景矩阵覆盖 owner/admin/member/view。
- [ ] 场景矩阵覆盖跨租户同名项目。
- [ ] 场景矩阵覆盖创建项目、上传文件、生成图片、生成视频、Agent 输入文本、资产导入、用量查看。
- [ ] 场景矩阵覆盖 API key disabled。
- [ ] 自动测试和必须手动验证项都写入 QA evidence。

**Engineering Subtasks**
- [ ] QA: 创建 `scenario-test-matrix.md`。 (depends: Stories 2-8)
- [ ] QA: 执行后端 targeted pytest、前端 check/build、浏览器关键路径。 (depends: implementation)
- [ ] Product Owner: 按设计文档验收所有故事。 (depends: QA pass)

**QA Evidence:** pending

## File Ownership

| File Path | Owner | Story | Parallel Policy |
|-----------|-------|-------|-----------------|
| `docs/20260711/tenant-project-permission-model/*` | Root | Story 1 | exclusive |
| `docs/INDEX.md` | Root | Story 1 | exclusive |
| `lib/db/models/*` | Backend | Story 2 | serialize before Stories 4-7 |
| `lib/db/repositories/project*` | Backend | Story 2 | exclusive |
| `lib/project_manager.py` | Backend | Story 2 | exclusive |
| `server/routers/projects.py` | Backend | Story 2 | exclusive |
| `frontend/src/api.ts` | Frontend | Story 3 | serialize API type edits |
| `frontend/src/stores/*project*` | Frontend | Story 3 | exclusive |
| `frontend/src/routes/*` | Frontend | Story 3 | exclusive |
| `lib/generation_queue.py` | Backend | Story 4 | exclusive |
| `server/services/generation_tasks.py` | Backend | Story 4 | exclusive |
| `server/routers/generate.py` | Backend | Story 4 | exclusive |
| `server/routers/assistant.py` | Backend | Story 5 | exclusive |
| `server/agent_runtime/*` | Backend | Story 5 | exclusive |
| `lib/agent_session_store/*` | Backend | Story 5 | exclusive |
| `lib/files/*` | Backend | Story 6 | exclusive |
| `server/routers/files.py` | Backend | Story 6 | exclusive |
| `lib/db/repositories/asset*` | Backend | Story 6 | exclusive |
| `server/routers/usage.py` | Backend | Story 7 | exclusive |
| `lib/usage_tracker.py` | Backend | Story 7 | exclusive |
| `server/routers/api_keys.py` | Backend | Story 8 | exclusive |
| `frontend/src/pages/settings*` | Frontend | Story 8 | exclusive |
| `tests/*` | QA + story owner | Story scoped | test files owned by related story; cross-story E2E owned by Story 9 |

## Worktrees

| Story | Branch | Worktree Path | Merge Target | Merge Status | Cleanup Status |
|-------|--------|---------------|--------------|--------------|----------------|
| Story 1 | story/tenant-project-permission-model/contract-freeze | ../ArcReel-worktrees/tenant-project-permission-model/contract-freeze | main | pending | pending |
| Story 2 | story/tenant-project-permission-model/backend-project-context | ../ArcReel-worktrees/tenant-project-permission-model/backend-project-context | main | pending | pending |
| Story 3 | story/tenant-project-permission-model/frontend-project-id | ../ArcReel-worktrees/tenant-project-permission-model/frontend-project-id | main | pending | pending |
| Story 4 | story/tenant-project-permission-model/generation-project-context | ../ArcReel-worktrees/tenant-project-permission-model/generation-project-context | main | pending | pending |
| Story 5 | story/tenant-project-permission-model/agent-project-context | ../ArcReel-worktrees/tenant-project-permission-model/agent-project-context | main | pending | pending |
| Story 6 | story/tenant-project-permission-model/files-assets-project-id | ../ArcReel-worktrees/tenant-project-permission-model/files-assets-project-id | main | pending | pending |
| Story 7 | story/tenant-project-permission-model/usage-tenant-project | ../ArcReel-worktrees/tenant-project-permission-model/usage-tenant-project | main | pending | pending |
| Story 8 | story/tenant-project-permission-model/disable-api-keys | ../ArcReel-worktrees/tenant-project-permission-model/disable-api-keys | main | pending | pending |
| Story 9 | story/tenant-project-permission-model/permission-e2e-audit | ../ArcReel-worktrees/tenant-project-permission-model/permission-e2e-audit | main | pending | pending |

## Blockers

| Date | Story/Subtask | Owner | Blocker | Resolution |
|------|---------------|-------|---------|------------|
| 2026-07-11 | G1/G2 | 用户 + PM | 需要用户确认本文档中 API key 禁用行为、role 权限矩阵、project_id 路由迁移口径 | 等待确认后启动实现 worktree |
