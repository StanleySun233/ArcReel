# Sprint Backlog: Current Project Audit And Stabilization

**Date:** 20260725
**Status:** planned
**Scope:** 审计当前 ArcReel 工作区的问题与缺陷，并补充下一步开发计划。本计划只基于当前工作区代码、文档、CI 配置和轻量验证结果；不把子代理自评当作完成证据。

## Current Evidence

- 当前工作区已有未提交修改，集中在 Alembic migration、`server/services/generation_tasks.py`、`server/services/resolution_resolver.py` 和多组测试文件。本计划不覆盖这些改动。
- `git diff --check` 通过。
- `pnpm lint` 在 `frontend/` 通过。
- `python -m pytest tests/test_i18n_consistency.py -q` 未进入测试体：加载 `tests/conftest.py` 时因缺少 `DATABASE_URL` 直接失败。这说明纯 i18n 检查当前也依赖数据库初始化。
- `docs/INDEX.md` 的 Active 区为空，但 `docs/20260711/tenant-project-permission-model/sprint-backlog.md` 内仍有多项未完成验收项。

## Defects And Risks

### P0 - Production Isolation And Security

1. **Credentialed backend cache can cross tenant scope**
   - Evidence: `server/services/generation_tasks.py` 的 `_backend_cache` key 只有 `(channel, provider_name, model)`，但 backend assembly 会读取 tenant-scoped config/credentials。
   - Impact: 不同 tenant 使用同 provider/model 时，可能复用另一个 tenant 的 API key、base_url 或 client。
   - Next action: 移除 credentialed backend cache，或把 cache key 扩展为 `tenant_id/user_id/provider/model/config_version`，并补 tenant isolation regression tests。

2. **Worker queue paths need an explicit RLS strategy**
   - Evidence: `tasks` RLS 依赖 `app.current_tenant_id`，但 worker 的 claim/orphan/requeue 路径是全局 worker 视角。
   - Impact: PostgreSQL forced RLS 下，worker 可能看不到 tenant 任务，orphan 任务卡住，或 requeue/cancel 在错误 scope 下失败。
   - Next action: 明确采用 privileged global worker 还是 per-tenant worker；把 claim、orphan list、requeue、cancel fallback 放进同一个 deep queue worker store module，并以 PostgreSQL/RLS 集成测试锁定。

3. **Provider route can drift between enqueue, submit, and resume**
   - Evidence: 入队派生 `provider_id`，执行层再次 resolve backend；`provider_job_id` 落库时没有冻结真实 submit provider/model；orphan resume 信任旧 `provider_id`。
   - Impact: 用户在 enqueue 和 submit 之间改 provider config 时，resume 可能轮询错误 provider。
   - Next action: 在 submit 成功时冻结真实 provider/model，或强制执行层使用入队时冻结的 route；补 provider drift tests。

4. **Reference video resume loses tenant file records**
   - Evidence: normal finalize 传 `created_by_user_id/tenant_id/task_id`，`resume_executor` 调 `_finalize_reference_video_unit` 时未传；tenant 缺失时 `_record_output_file` 直接返回 `None`。
   - Impact: reference video resume 成功后可能只写本地路径，不写 `file_id` 与 file_links，破坏多 tenant 媒体访问链路。
   - Next action: 修复 resume finalizer 参数，并补 `reference_video` resume 回归测试。

5. **SSE bearer token is exposed in query strings**
   - Evidence: frontend `withAuthQuery()` 把 bearer token 拼进 EventSource URL；任务、项目事件、assistant stream 都使用该路径。
   - Impact: token 可能进入浏览器历史、代理日志或服务端 access log。
   - Next action: 改为短期 stream token 或 cookie-backed session；至少把 stream auth 变成独立 module 并补安全测试。

### P1 - User-Visible Runtime Correctness

1. **Tenant switch does not invalidate provider/config status**
   - Evidence: `ConfigStatusLoader` 只随 `isAuthenticated` 触发；`config-status-store` 初始化后 `fetch()` 直接返回；`auth-store.switchTenant()` 不清理或刷新 config status。
   - Impact: tenant A 的 provider 可用性可能显示到 tenant B。
   - Next action: 让 config status 按 `tenantId` scoped；switch/logout 时 reset 或强制 refresh；补 tenant switch regression tests。

2. **Project media fingerprints are not scoped by project**
   - Evidence: fingerprint cache 按 path 存储；项目 unmount 时只清 current project，不清 fingerprint。
   - Impact: 跨项目同路径媒体可能错误 cache-bust 或显示 stale image。
   - Next action: cache key 改为 `(project_id, path)`，或项目切换/加载失败时清 fingerprint；补同路径跨项目测试。

3. **Media URL builders do not encode every path segment**
   - Evidence: frontend file/global asset URL 只 encode project id 或直接拼 filename。
   - Impact: 文件名含空格、`#`、`?`、`%`、非 ASCII 时可能图裂或请求错路由。
   - Next action: 建一个 media URL builder module，按 segment 编码；补特殊文件名 tests。

4. **Frontend API errors and UI copy still leak hardcoded Chinese**
   - Evidence: API fallback error、toast close aria-label、部分 login copy 仍是硬编码中文。
   - Impact: 英文/越南文 UI 可能混中文，错误处理无法按 namespace 管理。
   - Next action: 统一 error code → UI i18n mapping；补 zh/en/vi nested key 和 placeholder 一致性测试。

### P2 - Quality Gates And Documentation Drift

1. **Docs-only changes have no gate**
   - Evidence: CI 的 code gate 排除 `*.md` 和 `docs/**`，docs-only PR 可直接 skip code jobs。
   - Impact: ADR status、`CONTEXT.md`、roadmap、链接漂移不会被自动发现。
   - Next action: 增加 docs gate，至少检查 Markdown 链接、ADR frontmatter/status、`CONTEXT.md` 引用路径和 `docs/INDEX.md` Active/Completed 一致性。

2. **Local frontend command docs drift from CI**
   - Evidence: project instructions 说 CI 等价 `pnpm lint && pnpm check`，实际 CI 跑 `pnpm lint`、`pnpm build`、`pnpm test:coverage`。
   - Impact: 本地验收会低估 CI 真实门槛。
   - Next action: 更新开发命令说明，或明确 `pnpm check` 只是快速门禁。

3. **Coverage policy is not a single number**
   - Evidence: backend CI `--cov-fail-under=80`；frontend vitest coverage 只覆盖选定入口且 lines 阈值为 60。
   - Impact: 文档中的“CI 覆盖率 ≥80%”会误导 frontend 风险判断。
   - Next action: 要么提升并扩大 frontend coverage，要么文档明确 backend/frontend 分别门槛。

4. **Type-checking policy differs from documented warning level**
   - Evidence: docs 说 tests 内 unknown 系列降为 warning；`pyproject.toml` 实际设置为 `none`。
   - Impact: 测试代码中的 unknown 类型风险不会被门禁暴露。
   - Next action: 配置改 warning，或文档承认 tests 中 unknown 类型关闭。

5. **Domain docs and ADR status are stale**
   - Evidence: reference-video roadmap 仍标 PR3-PR7 plan “待写”，但文件已存在；ADR 0039 仍是 proposed；`CONTEXT.md` 对 audio lane 的描述落后于 worker 代码。
   - Impact: 后续 agent 会按旧路线规划，重复做已完成工作或忽略真实剩余风险。
   - Next action: 刷新 `CONTEXT.md`、ADR 0039、reference-video roadmap 和 `docs/INDEX.md` 状态。

### P3 - Architecture Deepening Candidates

1. **Deepen task execution routing**
   - Current module shape: `GenerationQueue`、`TaskRepository`、`GenerationWorker`、`generation_tasks`、`resume_executor` 之间重复 provider/tenant/task dict 约定。
   - Target depth: 一个 task route module 返回 `media_type/capability/provider_id/model_id/tenant_id/user_id`，enqueue、capacity、execution、resume 共享同一 route。
   - Test surface: route resolver interface + PostgreSQL worker store interface。

2. **Deepen frontend HTTP and stream adapters**
   - Current module shape: `frontend/src/api.ts` 是 2300+ 行 shallow god interface，`auth-store` 还重复实现 fetch adapter。
   - Target depth: 一个 HTTP adapter module 管 auth、language、403 recovery、error normalization；一个 stream adapter module 管 SSE auth。
   - Test surface: adapter tests 覆盖 401/403/retry/language/stream token。

3. **Deepen tenant runtime state**
   - Current module shape: auth、config status、project cache、assistant reset 分散在 store caller 中。
   - Target depth: 一个 tenant session lifecycle module 处理 switch/logout 后哪些 store 失效、哪些重拉。
   - Test surface: `switchTenant` observable outcomes。

## Execution Plan

### Phase 1 - Stop Isolation Leaks

**Acceptance Criteria**
- Backend cache 不会跨 tenant/user 复用 credentialed backend。
- Worker claim/orphan/requeue/cancel 在 PostgreSQL forced RLS 下有明确策略并有集成测试。
- Provider submit route 被冻结，resume 使用真实 submit provider/model。
- Reference video resume 写回 `file_id` 和 file_links。
- SSE 不再把长期 bearer token 放进 URL。

### Phase 2 - Fix Tenant-Aware Frontend State

**Acceptance Criteria**
- 切换 tenant 后 provider/config status 必须刷新或清空，不显示旧 tenant 状态。
- 项目媒体 fingerprint cache 不跨 project 泄漏。
- 文件 URL 对每个 path segment 编码。
- Toast、login、API fallback 错误走 i18n；toast 有 live region。

### Phase 3 - Add Quality Gates

**Acceptance Criteria**
- docs-only PR 至少跑 docs gate。
- 本地开发命令说明与 CI 命令一致。
- coverage policy、basedpyright tests policy 与实际配置一致。
- `DATABASE_URL` 对测试入口的要求写清楚；纯 i18n 检查不应意外初始化 DB，除非明确记录为 PostgreSQL-backed test。

### Phase 4 - Deepen Modules After Leaks Are Closed

**Acceptance Criteria**
- `TaskRoutingResolver` 或等价 module 成为 provider routing 单一入口。
- Queue worker store interface 收敛 claim/terminal/orphan/requeue/cancel 语义。
- Frontend HTTP adapter 和 stream adapter 从 `api.ts` 中分离。
- Store raw setters 在关键路径被 intent methods 替代。

## Deferred Until After Phase 1

- 大规模拆分 `frontend/src/api.ts`。
- 大规模拆分 `server/services/generation_tasks.py`。
- 调整 frontend coverage 阈值到 80%。
- 重写 reference-video roadmap 的历史 PR 拆分。

这些工作有价值，但它们不是当前最高风险。先修生产隔离、安全和可观察的状态错误。
