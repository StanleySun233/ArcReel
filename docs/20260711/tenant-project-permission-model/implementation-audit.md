# Tenant Project Permission Implementation Audit

**Date:** 20260711
**Status:** in progress

## Verified in this pass

### Issued Tokens disabled, business code retained

The Issued Tokens feature and OpenClaw synchronous Agent chat entry are disabled at invocation boundaries and the existing business implementations remain in place for future development.

Evidence:

- `server/routers/api_keys.py` keeps create/list/update/delete implementation paths behind `ISSUED_TOKENS_ENABLED = False`.
- `server/auth.py` rejects `arc-` Bearer tokens with `403 feature_disabled` while keeping `_verify_api_key`.
- `server/routers/agent_chat.py` keeps the synchronous Agent chat implementation behind `AGENT_CHAT_ENABLED = False`.
- `frontend/src/components/pages/ApiKeysTab.tsx` keeps the UI and disables actions through `ISSUED_TOKENS_ENABLED = false`.
- Tests:
  - `tests/test_api_keys_router.py`
  - `tests/test_auth_api_key.py`
  - `tests/test_agent_chat_router.py`
- `DATABASE_URL=postgresql+asyncpg://... ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://... python -m pytest tests/test_api_keys_router.py tests/test_auth_api_key.py tests/test_tenant_auth_service.py tests/test_tenant_auth_router.py tests/test_projects_router.py::TestProjectsRouter::test_delete_project_requires_admin_role -q`
  - Result: 18 passed, 1 warning

### Project identity is now route-id based on the main workspace path

The project list, create, detail, update, delete, video capability route, cost estimation route, manual shot upload route, script review route, project script routes, episode metadata routes, source import route, overview routes, frontend project cards, create-project navigation, task filters, file routes, assistant routes, project event stream, version routes, grid routes, reference video unit routes, project archive export, Jianying draft export, and usage query routes now use project id as the route key.

Evidence:

- `server/routers/projects.py` resolves project rows by `id` for the main CRUD path.
- `server/routers/projects.py` resolves project rows by `id` for video capabilities, script reads, script scene/shot edits, segment edits, episode title edits, source import, and overview update/generation.
- `server/routers/cost_estimation.py` resolves project rows by `id` and computes by project id.
- `server/routers/shot_uploads.py` resolves project rows by `id`, uses tenant-scoped `ProjectManager`, and records project file links with `resource_id=project_id`.
- `server/routers/script_review.py` resolves project rows by `id`; read requires viewer access, save/confirm require member access.
- `server/routers/versions.py` resolves project rows by `id`; version reads require viewer access and restores require member access.
- `server/routers/grids.py` resolves project rows by `id`; grid list/detail require viewer access and generate/regenerate require member access.
- `server/routers/reference_videos.py` resolves project rows by `id`; unit list requires viewer access and all mutating/generation/upload endpoints require member access.
- `server/routers/projects.py` export token/archive/Jianying draft routes use `project_id`; download tokens bind `tenant_id:project_id` and export services use the token tenant's project repository.
- `server/services/jianying_draft_service.py` supports the current pyJianYingDraft track API through `TrackSpec`.
- `server/routers/usage.py` accepts `project_id` query filters, checks tenant membership, and passes the current tenant to usage reads.
- `lib/db/models/api_call.py` stores usage project scope in `project_id`.
- `lib/db/repositories/usage_repo.py` applies tenant and `project_id` scoping to usage queries.
- `frontend/src/api.ts` sends `project_id` for usage stats/calls filters.
- Project creation stores local project JSON under tenant-scoped project-id paths.
- `frontend/src/types/project.ts` requires `ProjectSummary.id`.
- `frontend/src/components/pages/ProjectsPage.tsx` links and deletes by `project.id`.
- `frontend/src/components/pages/CreateProjectModal.tsx` navigates and uploads style image by `resp.id`.
- `frontend/src/api.ts` uses `project_id` query parameters for task list/stats/SSE.

### File, draft, style image, and project media routes bind files to project id

Project file upload, source import, source read/update/delete, static project file serving, file listing, draft read/write/delete, draft listing, and style image upload use `project_id`. Media uploads return `file_id` and do not expose local server paths.

Evidence:

- `server/routers/files.py` route parameters for project file/source operations are `project_id`.
- `server/routers/files.py` draft and style image endpoints use tenant-scoped `ProjectManager`.
- Project media uploads write `FileLinkSpec(resource_type="project", resource_id=project_id, ...)`.
- `tests/test_files_api_minio.py` asserts project media upload creates a project file link with the route id.
- `tests/test_files_router.py` now validates media upload responses by `filename/file_id` and verifies local metadata separately.

### Assistant routes enforce tenant permissions and project-id session ownership

Assistant send/list/get/delete/entries/interrupt/answer/skills routes validate the current tenant membership before using the assistant service. Session ownership compares the stored session project key against the route `project_id`.

Permission split:

- viewer: list sessions, get session, read entries, stream entries, list skills
- member/admin: send, delete session, interrupt, answer pending questions

Evidence:

- `server/routers/assistant.py` calls `_require_tenant_role`.
- `server/agent_runtime/service.py` already resolves project cwd through tenant-aware `ProjectManager`.
- `server/agent_runtime/session_manager.py` provides scoped project roots to SDK options.
- `tests/test_assistant_routes.py` covers route contract, project-id forwarding, and preservation of tenant permission errors.

### Generation queue and workers now carry tenant/user execution scope

Generation task enqueue, provider derivation, worker provider extraction, resume executor finalization, and SDK MCP tool enqueue calls now carry the request-time `tenant_id` and `user_id`. Worker-side project lookup and provider credential resolution run under the task's stored tenant/user context instead of the process-global default.

Evidence:

- `lib/generation_queue.py` derives provider id under `task_tenant_scope`.
- `lib/db/models/task.py` stores task and task event project scope in `project_id`.
- `lib/db/repositories/task_repo.py` writes and filters task/task event rows through `project_id`.
- `lib/generation_queue_client.py` uses the current identity context when SDK tools do not pass explicit ids.
- `lib/generation_worker.py` resolves project config/provider capacity under the task tenant.
- `server/services/generation_tasks.py` and `lib/config/resolver.py` return tenant-scoped `ProjectManager` instances.
- `server/services/resume_executor.py` passes task tenant/user into media generator and video finalization.
- `server/agent_runtime/sdk_tools/*` pass `tenant_id/user_id/requested_by_user_id` when enqueueing tasks.
- `tests/test_generation_queue.py::test_enqueue_provider_derivation_receives_tenant_and_user`.
- `tests/test_generation_queue.py::test_queue_client_uses_current_identity_scope_by_default`.
- `tests/test_generation_worker_module.py::test_project_lookup_is_scoped_by_task_tenant`.
- `DATABASE_URL=postgresql+asyncpg://... ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://... python -m pytest tests/test_task_repo.py tests/test_task_repo_state_machine.py tests/test_generation_queue.py tests/test_generation_worker_module.py tests/test_tasks_router_more.py -q`
  - Result: 145 passed, 1 warning

### Agent session metadata, event log, and transcript store are tenant-scoped

Agent session metadata, UI event log, and Claude SDK transcript mirror now include tenant scoping. A single process-level `DbSessionStore` no longer freezes the startup tenant; if no explicit tenant is passed, each store operation resolves the current request tenant.

Evidence:

- `lib/db/models/session.py` stores `tenant_id/project_id/user_id` on `agent_sessions`.
- `lib/db/repositories/session_repo.py` creates and filters sessions by tenant, user, and `project_id`.
- `server/agent_runtime/event_log.py` writes and reads event log rows by tenant.
- `lib/agent_session_store/models.py` adds tenant ownership to transcript entries and summaries.
- `lib/agent_session_store/store.py` filters append/load/list/delete/list_subkeys by tenant.
- `server/agent_runtime/options_assembler.py` injects current tenant/user into SDK MCP server construction.
- `server/agent_runtime/session_store.py` constructs tenant-aware repositories from request context.
- `alembic/versions/9a7c6d5e4f32_scope_agent_sessions_by_tenant.py` adds tenant columns and tenant-aware indexes.
- `alembic/versions/156fe0aa0414_initial_schema.py` and the tenant-scoping migration define the session project column as `project_id`.
- `tests/test_agent_session_user_scope.py` covers user isolation, tenant isolation, and dynamic tenant resolution for a reused `DbSessionStore`.
- `tests/agent_session_store` verifies the SDK transcript store contract against PostgreSQL.

### Project event stream is tenant-checked

Project event SSE now validates current tenant membership through backend membership lookup instead of trusting the JWT tenant snapshot alone.

Evidence:

- `server/routers/project_events.py` calls `require_tenant_access(..., minimum_role=ROLE_VIEW)` and sets tenant context before resolving the stream.

### Project asset CRUD is tenant/project-id aware

Character, scene, prop, and product project asset CRUD routes use `project_id` and require member permissions for writes.

Evidence:

- `server/routers/_asset_router_factory.py`
- `server/routers/characters.py`
- `server/routers/scenes.py`
- `server/routers/props.py`
- `server/routers/products.py`

### Project display name is not accepted as a route key on the repaired path

When a project id differs from the display name, repaired routes resolve by `project_id` and reject display-name lookups.

Evidence:

- `tests/test_projects_router.py::TestProjectsRouter::test_project_detail_uses_id_not_display_name` covers detail, script read, and source import route behavior.

### Tenant role refresh and project deletion permissions are enforced

The backend now returns `STALE_TENANT_ROLE` when a request is denied because the token role snapshot differs from the database role. The frontend API layer refreshes the current tenant token and retries once. Project deletion requires admin-level tenant access, matching the owner/admin-only product rule.

Evidence:

- `server/services/tenant_auth.py` compares the JWT role snapshot against the database role when permission is denied.
- `frontend/src/api.ts` handles `STALE_TENANT_ROLE` through `/auth/refresh-current-tenant` and retries the original request.
- `server/routers/projects.py` requires `ROLE_ADMIN` for `DELETE /projects/{project_id}`.
- `tests/test_tenant_auth_service.py` covers stale-role and non-stale denial behavior.
- `frontend/src/api.test.ts` covers refresh-and-retry behavior.
- `tests/test_projects_router.py::TestProjectsRouter::test_delete_project_requires_admin_role` covers delete permission.

### PostgreSQL is the only supported runtime database

All runtime and test code paths have been moved off local embedded database support. The project now requires `postgresql+asyncpg://` for `DATABASE_URL`; the old local database dependency, migration script, file-path sensitive-list entries, dialect branches, dialect-specific model arguments, and in-memory database test fixtures have been removed.

Evidence:

- `pyproject.toml` and `uv.lock` no longer include the embedded database driver dependency.
- `lib/db/engine.py` requires PostgreSQL URLs and no longer exposes a compatibility backend helper.
- `lib/agent_session_store/store.py` uses PostgreSQL `INSERT ... ON CONFLICT` only.
- ORM models and Alembic migrations only keep `postgresql_where` partial-index definitions.
- The old local database migration script and `deploy/production/MIGRATE-TO-POSTGRES.md` were removed.
- Agent sandbox sensitive-path policy no longer assumes a local database file.
- Tests use `tests/pg_utils.py` to create isolated PostgreSQL schemas.
- Runtime source, migrations, tests, lockfiles, CI, deployment docs, and agent profiles were scanned for old local database markers.
  - Result: no matches.

### Issued Tokens business code is retained behind invocation-level 403

The OpenClaw/Issued Tokens feature remains in the codebase for later enablement. The current edition disables it only at call boundaries.

Evidence:

- `server/routers/api_keys.py` retains create/list/update/delete implementation paths behind `ISSUED_TOKENS_ENABLED = False`.
- `server/auth.py` rejects `arc-` token authentication with `403 feature_disabled` while retaining the verification path.
- `frontend/src/components/pages/ApiKeysTab.tsx` keeps the UI structure and disables actions.
- `tests/test_api_keys_router.py` includes a business-path-retained test with the flag enabled.

### Tenant role matrix is covered by route tests

The tenant membership API covers the product role constraints:

- owner can add admin.
- admin can add member and viewer but cannot add admin.
- member can add viewer but cannot add member.
- viewer can list members but cannot add members.

Evidence:

- `tests/test_tenant_auth_router.py`
- `DATABASE_URL=postgresql+asyncpg://... ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://... python -m pytest tests/test_tenant_auth_service.py tests/test_tenant_auth_router.py -q`
  - Result: 12 passed

### Usage facts are stored and queried by project id

API usage facts now use `project_id` as the storage column. Usage read APIs still accept the public `project_id` query parameter and validate that the project belongs to the current tenant before querying.

Evidence:

- `lib/db/models/api_call.py`
- `lib/db/repositories/usage_repo.py`
- `server/routers/usage.py`
- `DATABASE_URL=postgresql+asyncpg://... ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://... python -m pytest tests/test_usage_repo.py tests/test_usage_tracker.py tests/test_usage_router.py tests/test_session_manager_sdk_session_id.py -q`
  - Result: 54 passed, 1 warning

### Multi-project Agent session isolation is verified at tenant/project boundaries

Agent session metadata and transcript storage are scoped by tenant/user and project key. Route-level ownership checks compare the stored session project key with the requested `project_id`, while transcript mirror rows include `tenant_id + project_key + session_id` in their primary key.

Evidence:

- `lib/db/repositories/session_repo.py` scopes `get/list/update/delete` by `tenant_id` and `user_id`.
- `server/routers/assistant.py` rejects session operations when the stored session project key differs from the route `project_id`.
- `lib/agent_session_store/models.py` keys transcript entries by `tenant_id + project_key + session_id + subpath + seq`.
- `DATABASE_URL=postgresql+asyncpg://... ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://... python -m pytest tests/test_session_repo.py tests/test_session_meta_store.py tests/test_session_manager_project_scope.py tests/agent_session_store/test_conformance.py tests/agent_runtime/test_event_log.py tests/test_assistant_routes.py tests/test_assistant_router_full.py tests/test_assistant_service_more.py tests/test_agent_chat_router.py tests/test_session_manager_sdk_session_id.py tests/agent_runtime/test_entry_stream.py tests/agent_runtime/test_agent_startup_error.py -q`
  - Result: 179 passed, 1 warning

## Verification completed

Backend:

- `DATABASE_URL=postgresql+asyncpg://... ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://... python -m pytest tests/test_session_repo.py tests/test_session_meta_store.py tests/test_session_manager_project_scope.py tests/agent_session_store/test_conformance.py tests/agent_runtime/test_event_log.py tests/test_assistant_routes.py tests/test_assistant_router_full.py tests/test_assistant_service_more.py tests/test_agent_chat_router.py tests/test_session_manager_sdk_session_id.py tests/agent_runtime/test_entry_stream.py tests/agent_runtime/test_agent_startup_error.py tests/test_task_repo.py tests/test_task_repo_state_machine.py tests/test_generation_queue.py tests/test_generation_worker_module.py tests/test_tasks_router_more.py tests/test_usage_repo.py tests/test_usage_tracker.py tests/test_usage_router.py -q`
  - Result: 370 passed, 1 warning
- `python -m pytest tests/test_api_keys_router.py tests/test_auth_api_key.py tests/test_agent_chat_router.py tests/test_assistant_routes.py tests/test_files_router.py tests/test_files_api_minio.py tests/test_characters_router.py tests/test_scenes_router.py tests/test_props_router.py tests/test_products_router.py tests/test_asset_router_factory.py tests/test_generate_router.py tests/test_generate_router_tts.py tests/test_generation_queue.py tests/test_tasks_router_more.py tests/test_task_cancel_router.py tests/test_projects_router.py::TestProjectsRouter tests/test_projects_router.py::TestUnexpectedErrorsDoNotLeak tests/test_cost_estimation_router.py tests/test_shot_uploads_router.py tests/test_shot_uploads_minio.py tests/test_script_review.py tests/test_versions_router.py tests/test_grids_router.py tests/test_grid_router.py tests/server/test_reference_videos_router.py tests/server/test_reference_videos_router_ad.py tests/server/test_reference_video_e2e_backend.py tests/integration/test_reference_video_e2e.py tests/test_projects_archive_routes.py tests/test_jianying_draft_routes.py tests/test_usage_router.py tests/test_usage_repo.py tests/test_usage_tracker.py -q`
  - Result: 426 passed
- `python -m pytest tests/test_session_repo.py tests/test_session_meta_store.py tests/test_agent_session_user_scope.py tests/agent_runtime/test_event_log.py tests/agent_session_store tests/test_generation_queue.py tests/test_generation_worker_module.py tests/test_resume_executor.py -q`
  - Result: 212 passed
- `python -m pytest tests/test_tenant_auth_service.py tests/test_tenant_auth_router.py tests/test_projects_router.py::TestProjectsRouter::test_delete_project_requires_admin_role -q`
  - Result: 10 passed
- `DATABASE_URL=postgresql+asyncpg://... ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://... python -m pytest tests/test_db_engine.py tests/test_api_keys_router.py tests/test_auth_api_key.py tests/test_agent_chat_router.py tests/test_tenant_auth_service.py tests/test_tenant_auth_router.py tests/test_tenant_project_routes.py tests/test_projects_router.py::TestProjectsRouter::test_delete_project_requires_admin_role tests/test_projects_router.py::TestProjectsRouter::test_list_and_create_and_delete tests/test_generation_queue.py tests/test_task_repo.py tests/test_config_repository.py tests/test_asset_repo.py tests/agent_runtime/test_event_log.py tests/agent_session_store/test_conformance.py -q`
  - Result: 177 passed, 1 warning
- `python -m ruff check server lib alembic tests scripts`
  - Result: passed
- `python -m ruff check <changed backend files and tests>`
  - Result: passed
- `basedpyright <changed backend task/session files>`
  - Result: 0 errors; command exits non-zero because project config references a missing `.venv` path.

Frontend:

- `pnpm check`
  - Result: typecheck passed, lint passed, 925 tests passed.
- `pnpm vitest run src/api.test.ts`
  - Result: 51 passed
- `pnpm vitest run src/api.test.ts src/stores/auth-store.test.ts src/components/tenant/TenantSwitcher.test.tsx src/components/auth/CamelProviderBootstrapModal.test.tsx`
  - Result: 4 files passed, 63 tests passed

Local clean E2E smoke:

- Local cleanup was explicitly authorized and executed only against ArcReel local development state.
- PostgreSQL `arcreel.public` schema was dropped/recreated, Redis DB 0 was flushed, and `alembic upgrade head` completed.
- Local service `http://127.0.0.1:1241` returned `200` for `/api/v1/auth/status` with `mode=camel`.
- A CaMeL-shaped local token for `camel:passbygrocer` was used only to bypass the local OAuth redirect registration blocker and verify ArcReel internals.
- `/api/v1/auth/me` created the default personal tenant `passbygrocer的个人空间` with role `admin`.
- `/api/v1/camel/bootstrap/status` returned the expected five token/provider plan:
  - image: `gpt-image-2`
  - text: `gpt-5.5`
  - video: `doubao-seedance-2-0-260128`
  - audio: `gpt-4o-mini-tts`
  - anthropic: `claude-opus-4-8`
- `/api/v1/camel/bootstrap/start-url` generated a CaMeL authorization URL with scope `profile email arcreel:token-provision`.
- `POST /api/v1/projects` created `proj-b9b796ff259d461b` under the current tenant.
- `POST /api/v1/projects/proj-b9b796ff259d461b/source` imported `月亮与六便士第一章一.txt`.
- `GET /api/v1/projects/proj-b9b796ff259d461b/files` listed the imported source file.
- `POST /api/v1/projects/proj-b9b796ff259d461b/assistant/sessions/send` returned `accepted` and created a session scoped to `tenant_id + project_id`.
- Reading that assistant session returned `project_id=proj-b9b796ff259d461b`; the async agent then failed with `Not logged in · Please run /login`, which is expected for this local run because provider bootstrap could not complete.

Browser smoke:

- `agent-browser` opened `/app/projects` with the local token injected into `localStorage`.
- Project list displayed the created project and default personal space.
- Tenant switcher opened as a listbox and showed `passbygrocer的个人空间`, role `Admin`, and `Personal space`.
- The CaMeL setup modal displayed five planned keys and default models, including `camel-arcreel-passbygrocer-anthropic`.
- Opening the project card navigated to the project workspace by project id.
- The license/footer surface was previously observed as the requested single line: `Powered by ArcReel — https://github.com/ArcReel/ArcReel`.

Documentation audit:

- Added [final-tenant-user-project-model.md](./final-tenant-user-project-model.md) as the single final delivery summary for the `user_id + tenant_id + project_id` relationship, role matrix, storage, files, CaMeL bootstrap, Issued Tokens, assets, usage, Agent, task, and frontend boundaries.
- `CONTEXT.md` download-token glossary now says export tokens bind `tenant_id + project_id`, not project display name.
- `AGENTS.md` project event stream route now uses `{project_id}`, not `{name}`.
- `rg -n "绑定项目名|项目名的一次性|projects/\{name\}|projects/\{project_name\}|\{project_name\} 项目路径|按项目名寻址|项目名路由|项目名作为" docs/20260711 CONTEXT.md AGENTS.md README.md -S`
  - Result: only "not supported / not retained" authority statements remain.
- `rg -n "sqlite|aiosqlite|\.arcreel\.db|migrate_sqlite" docs server lib alembic tests pyproject.toml uv.lock -S`
  - Result: only audit/final "removed / unsupported" statements remain.
- `python -m ruff check AGENTS.md CONTEXT.md docs/20260711/tenant-project-permission-model`
  - Result: passed; no Python files under those paths.

Additional focused regression:

- Added MCP / usage session identity regression.
  - `UsageTracker.start_call()` now resolves default calls from current `user_id + tenant_id` identity scope instead of falling back to `default / ten_default`.
  - MCP enqueue tool tests now accept and verify `user_id`, `tenant_id`, and `requested_by_user_id` propagation into the queue boundary.
  - Evidence: `tests/test_usage_tracker.py::TestUsageTracker::test_start_call_uses_current_identity_scope_by_default`.
  - Evidence: `tests/test_usage_tracker.py::TestUsageTracker::test_start_call_explicit_identity_wins_over_current_scope`.
  - Evidence: `tests/server/agent_runtime/test_sdk_tools.py::test_generate_assets_happy`.
- Audited project runtime skills.
  - ArcReel runtime skills live under `agent_runtime_profile/.claude/skills`; no host-level `~/.codex/skills` or `~/.claude` skill files were modified.
  - `manage-project`, `generate-assets`, `generate-storyboard`, `generate-grid`, `generate-video`, `generate-narration-audio`, and `generate-script` route project writes through `mcp__arcreel__*`.
  - `compose-video` is the only runtime skill with a Python script that writes files; it requires the assistant session cwd to be the current project root and writes final media under current-project `output/`.
  - `server/agent_runtime/agent_access_policy.py` rejects Write/Edit outside the session project cwd and rejects direct writes to `project.json` and `scripts/`.
  - `server/agent_runtime/options_assembler.py` sets Claude SDK `cwd` to the session project root and builds a per-session in-process MCP server with current `user_id + tenant_id`.
- Added assistant running-idle watchdog.
  - `server/agent_runtime/session_manager.py` now refreshes session activity on every SDK message and interrupts sessions that remain `running` without any SDK output past the idle threshold.
  - This prevents a model/subagent stall from leaving the session permanently `running` and blocking the project assistant lane.
  - Evidence: `tests/test_session_lifecycle.py::TestCleanup::test_running_watchdog_interrupts_idle_session`.
  - Evidence: `tests/test_session_lifecycle.py::TestCleanup::test_running_watchdog_cancelled_on_finalize`.
- `DATABASE_URL=postgresql+asyncpg://... ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://... python -m pytest tests/test_usage_tracker.py tests/test_text_generator.py tests/server/agent_runtime/test_sdk_tools.py -q`
  - Result: 106 passed
- `DATABASE_URL=postgresql+asyncpg://... python -m pytest tests/test_session_lifecycle.py tests/test_session_manager_sdk_session_id.py tests/test_session_actor.py -q`
  - Result: 53 passed
- `DATABASE_URL=postgresql+asyncpg://... ruff check server/agent_runtime/session_manager.py tests/test_session_lifecycle.py`
  - Result: passed
- `ruff check lib/usage_tracker.py tests/test_usage_tracker.py tests/server/agent_runtime/test_sdk_tools.py`
  - Result: passed
- `DATABASE_URL=postgresql+asyncpg://... ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://... python -m pytest tests/test_tenant_auth_service.py tests/test_tenant_auth_router.py tests/test_projects_router.py::TestProjectsRouter::test_delete_project_requires_admin_role tests/test_api_keys_router.py tests/test_auth_api_key.py tests/test_assistant_routes.py tests/test_files_router.py tests/test_task_repo.py tests/test_usage_repo.py tests/test_session_repo.py -q`
  - Result: 139 passed, 1 warning
- Added `tests/test_task_repo.py::TestTaskRepository::test_cancel_all_queued_is_scoped_by_project_id`.
  - Evidence: cancelling queued tasks for `proj-alpha` leaves same-tenant `proj-beta` queued and project-filtered events do not mix.
- Added `tests/test_session_repo.py::TestSessionRepository::test_list_filters_by_tenant_user_and_project_id`.
  - Evidence: same-tenant multi-project sessions list by `project_id`; same-tenant other-user and other-tenant sessions are invisible.
- `DATABASE_URL=postgresql+asyncpg://... ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://... python -m pytest tests/test_session_repo.py tests/test_task_repo.py -q`
  - Result: 36 passed
- `DATABASE_URL=postgresql+asyncpg://... ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://... python -m pytest tests/test_session_repo.py tests/test_session_meta_store.py tests/test_session_manager_project_scope.py tests/test_assistant_routes.py tests/test_assistant_router_full.py tests/test_task_repo.py tests/test_generation_queue.py tests/test_generation_worker_module.py -q`
  - Result: 162 passed, 1 warning
- `python -m ruff check tests/test_session_repo.py tests/test_task_repo.py`
  - Result: passed
- Added `frontend/src/hooks/useAssistantSession.test.tsx` coverage for `arcreel:lastSessionByProject`.
  - Evidence: explicit user-selected assistant sessions are persisted under `proj-alpha` and `proj-beta` keys, proving duplicate project display names cannot cross-load the right-panel assistant session.
- `pnpm vitest run src/hooks/useAssistantSession.test.tsx`
  - Result: 1 file passed, 15 tests passed
- `pnpm vitest run src/hooks/useAssistantSession.test.tsx src/api.test.ts src/components/copilot/AgentCopilot.test.tsx`
  - Result: 3 files passed, 70 tests passed
- `pnpm exec eslint src/hooks/useAssistantSession.test.tsx --quiet`
  - Result: passed
- Added OpenAI-compatible text response regression.
  - Root cause: the remote CaMeL text path called `lib.text_backends.openai` with `gpt-5.5`; the compatible endpoint could return a raw JSON string while the adapter assumed an SDK object and accessed `response.usage`.
  - Fix: `OpenAITextBackend._generate_native()` now treats string responses as valid text payloads with unknown token usage.
  - Evidence: `tests/test_openai_text_backend.py::TestOpenAITextBackend::test_generate_tolerates_string_response_from_compatible_endpoint`.
  - Evidence: `tests/test_openai_text_backend.py::TestOpenAITextBackend::test_generate_structured_output_tolerates_json_string_response`.
- `DATABASE_URL=postgresql+asyncpg://... python -m pytest tests/test_openai_text_backend.py tests/test_text_backends/test_instructor_support.py -q`
  - Result: 53 passed
- `DATABASE_URL=postgresql+asyncpg://... ruff check lib/text_backends/openai.py tests/test_openai_text_backend.py`
  - Result: passed
- Audited paid video generation paths without calling real video providers.
  - Normal storyboard video path: `execute_video_task` receives task `tenant_id`, constructs `MediaGenerator(... tenant_id=tenant_id)`, records `UsageTracker.start_call(... tenant_id=self._tenant_id)`, persists `api_call_id` to task payload, and finalizes video/thumbnail through `_record_output_file(... tenant_id=tenant_id, task_id=task_id)`.
  - Reference video path: `execute_reference_video_task` receives task `tenant_id`, constructs `MediaGenerator(... tenant_id=tenant_id)`, calls `generate_video_async`, and finalizes video/thumbnail through `_finalize_reference_video_unit(... tenant_id=tenant_id, task_id=task_id)`.
  - Resume path: `execute_resume_video_task` reads persisted task `tenant_id`, re-enters `task_tenant_scope`, constructs `MediaGenerator(... tenant_id=tenant_id)`, and finalizes normal/reference videos with persisted identity.
  - Worker lane routing treats `reference_video` as video lane for provider derivation and capacity, not image lane.
  - Queue/task storage persists `tenant_id`, `requested_by_user_id`, and `project_id`; cancel/list/event operations are project/tenant scoped.
- Fixed a reference-video grouping identity gap.
  - Root cause: `resolve_max_unit_duration(project, user_id=...)` constructed `ConfigResolver` without tenant, so ad + reference_video grouping could lose model-specific max-duration constraints under tenant-scoped config.
  - Fix: `resolve_max_unit_duration()` now accepts `tenant_id`; HTTP derive route passes `_user.tenant_id`; SDK video tool passes `ctx.tenant_id`.
  - Evidence: `tests/server/agent_runtime/test_sdk_tools.py::test_generate_video_episode_ad_reference_passes_tenant_to_duration_resolver`.
- Fixed a low-cost video test harness gap.
  - `MediaGenerator.__init__` already initializes `_tenant_id` in production; `tests/server/test_reference_video_tasks.py::test_execute_reference_video_task_uses_real_media_generator` uses `object.__new__(MediaGenerator)` to avoid DB/provider setup and now mirrors `_tenant_id`.
- `DATABASE_URL=postgresql+asyncpg://... ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://... python -m pytest tests/server/test_reference_video_tasks.py tests/server/test_ad_reference_video_tasks.py tests/server/agent_runtime/test_sdk_tools.py::test_generate_video_episode_ad_reference_derives_and_enqueues tests/server/agent_runtime/test_sdk_tools.py::test_generate_video_episode_ad_reference_passes_tenant_to_duration_resolver tests/server/agent_runtime/test_sdk_tools.py::test_generate_video_episode_ad_reference_regenerates_reset_unit tests/server/agent_runtime/test_sdk_tools.py::test_generate_video_episode_ad_reference_skips_unchanged_unit_with_output tests/server/agent_runtime/test_sdk_tools.py::test_generate_video_all_ad_reference_falls_through_to_episode -q`
  - Result: 36 passed
- `DATABASE_URL=postgresql+asyncpg://... ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://... python -m pytest tests/test_generation_worker_module.py::TestExtractProvider::test_reference_video_routes_to_video_lane tests/test_generation_worker_module.py::TestExtractProvider::test_project_lookup_is_scoped_by_task_tenant tests/test_generation_worker_module.py::TestExtractProviderAlignsWithExecution::test_video_alignment tests/test_generation_worker_module.py::TestGenerationWorker::test_process_resume_task_locks_persisted_provider_to_payload tests/test_task_repo.py::TestTaskRepository::test_task_storage_uses_project_id_column tests/test_task_repo.py::TestTaskRepository::test_claim_next_running_event_uses_claimed_task_tenant tests/test_task_repo.py::TestTaskRepository::test_cancel_all_queued_is_scoped_by_project_id tests/test_task_repo.py::TestTaskRepository::test_tenant_snapshot_and_scoped_queries -q`
  - Result: 8 passed
- `DATABASE_URL=postgresql+asyncpg://... ruff check server/services/reference_video_tasks.py server/agent_runtime/sdk_tools/enqueue_videos.py server/routers/reference_videos.py tests/server/agent_runtime/test_sdk_tools.py tests/server/test_reference_video_tasks.py`
  - Result: passed

## Remote real model scenario

Remote environment:

- URL: `https://dream.camel-hub.com/`
- ArcReel deploy path: `/home/sijin/ArcReel/deploy/arcreel`
- Image source: `registry.kr777.top/arcreel/arcreel:latest`
- Commit: `b10249b fix(text): handle compatible string responses`
- CI: GitHub Action `Private Docker Deploy` run `29145494000`, result passed
- Remote deploy: `docker compose pull app && docker compose up -d app`, app health became `healthy`

Authentication and tenant:

- `/api/v1/auth/me` returned CaMeL user `camel:16`, username `passbygrocer`.
- Current tenant: `ten_9979b6290cd14993a42f3cb909409827`.
- Current role: `admin`.

Project scenario:

- Project id: `proj-c56f473025444b8d`.
- Project title: `月亮与六便士第一章 2资产测试`.
- Content mode: narration.
- Existing generated assets verified from project detail and project files:
  - 2 characters with completed image files.
  - 2 scenes with completed image files.
  - 2 props with completed image files.
- Step1 review was written through `PUT /api/v1/projects/{project_id}/episodes/1/script-review/content`.
- Step1 review was confirmed through `POST /api/v1/projects/{project_id}/episodes/1/script-review/confirm`.

Assistant scenario:

- Session id: `15883284-93f5-461c-a5bd-e6fb1d2b79e4`.
- Request: right-side assistant was instructed to call `mcp__arcreel__generate_episode_script({"episode":1})` only.
- Tool result: `✅ 剧本生成完成: /app/projects/_tenants/ten_9979b6290cd14993a42f3cb909409827/projects/proj-c56f473025444b8d/scripts/episode_1.json`.
- Assistant completed after reading the generated file.
- Generated script:
  - title: `思特里克兰德的名字与画作`
  - segments: 3
- API verification:
  - episode `script_file=scripts/episode_1.json`
  - episode `script_status=generated`
  - episode `status=scripted`
  - `.scripts["episode_1.json"].segments | length == 3`
- Remote file verification through container Python returned the same title and segment count.

Browser verification:

- agent-browser used isolated session `arcreel-ui-1573151018d0`.
- Opened `/app/projects/proj-c56f473025444b8d`.
- Project page displayed:
  - `Characters 2`
  - `Scenes 2`
  - `Props 2`
  - `E1 思特里克兰德的名字与画作 Draft 3 · 0:24`
  - right-side assistant tool record `GENERATE SCRIPT {"episode":1} ✓`
- Clicking the episode opened the detail page:
  - title `思特里克兰德的名字与画作`
  - 3 pending shots
  - prompt fields rendered
  - right-side assistant session remained project-scoped

## Remaining gaps

### Full pytest suite is not green yet

The PostgreSQL-only conversion is validated by focused PG suites, but the full legacy test suite still contains tests that assume global config, missing tenant context, old route authorization defaults, or pre-tenant fixture ordering.

Latest evidence:

- `DATABASE_URL=postgresql+asyncpg://... ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://... python -m pytest -q`
  - Result: 5367 passed, 446 failed, 34 errors

Dominant failure classes:

- `tenant_id is required` in config/model resolver tests that still instantiate services without tenant context.
- `403` responses in route tests that do not provide current tenant membership.
- PostgreSQL foreign-key failures in fixtures that insert tenant rows before user rows.
- Remaining tests may still use `project_name` as a function argument name while carrying project ids.

### Local real CaMeL OAuth scenario is blocked by redirect registration

The local browser login path reaches CaMeL OAuth, but CaMeL rejects the local redirect URI:

- redirect URI used locally: `http://127.0.0.1:1241/api/v1/auth/camel/callback`
- observed CaMeL error: `redirect_uri is not registered for this client`

This blocks real local provider bootstrap because ArcReel correctly requires a CaMeL OAuth access token with `arcreel:token-provision` scope before creating local media providers and the Anthropic Bridge credential. No fallback or password-grant path was assumed. Remote `dream.camel-hub.com` uses a registered redirect URI and has completed the real model-backed validation above.

### Remaining old function-argument `project_name` names

Some internal function arguments and temporary response aliases still use `project_name` while carrying project ids. The storage schema for sessions, tasks, task events, and usage facts has been moved to `project_id`; remaining work is naming cleanup at call boundaries.

### Remaining project-id audit gap

No active project route family is currently known to use display name as the lookup key. Some internal persistence/API response field names still use `project_name` while carrying project id values and are tracked as schema vocabulary cleanup rather than route authorization gaps.
