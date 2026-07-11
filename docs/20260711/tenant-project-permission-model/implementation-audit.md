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
- `lib/db/repositories/usage_repo.py` applies tenant scoping to usage queries.
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
- `lib/generation_queue_client.py` uses the current identity context when SDK tools do not pass explicit ids.
- `lib/generation_worker.py` resolves project config/provider capacity under the task tenant.
- `server/services/generation_tasks.py` and `lib/config/resolver.py` return tenant-scoped `ProjectManager` instances.
- `server/services/resume_executor.py` passes task tenant/user into media generator and video finalization.
- `server/agent_runtime/sdk_tools/*` pass `tenant_id/user_id/requested_by_user_id` when enqueueing tasks.
- `tests/test_generation_queue.py::test_enqueue_provider_derivation_receives_tenant_and_user`.
- `tests/test_generation_queue.py::test_queue_client_uses_current_identity_scope_by_default`.
- `tests/test_generation_worker_module.py::test_project_lookup_is_scoped_by_task_tenant`.

### Agent session metadata, event log, and transcript store are tenant-scoped

Agent session metadata, UI event log, and Claude SDK transcript mirror now include tenant scoping. A single process-level `DbSessionStore` no longer freezes the startup tenant; if no explicit tenant is passed, each store operation resolves the current request tenant.

Evidence:

- `lib/db/models/session.py` adds tenant ownership to `agent_sessions`.
- `lib/db/repositories/session_repo.py` filters create/get/list/update/delete/interrupt by tenant and user.
- `server/agent_runtime/event_log.py` writes and reads event log rows by tenant.
- `lib/agent_session_store/models.py` adds tenant ownership to transcript entries and summaries.
- `lib/agent_session_store/store.py` filters append/load/list/delete/list_subkeys by tenant.
- `server/agent_runtime/options_assembler.py` injects current tenant/user into SDK MCP server construction.
- `server/agent_runtime/session_store.py` constructs tenant-aware repositories from request context.
- `alembic/versions/9a7c6d5e4f32_scope_agent_sessions_by_tenant.py` adds tenant columns and tenant-aware indexes.
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

## Verification completed

Backend:

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

## Remaining gaps

### Full API scenario test is not complete

The local service at `127.0.0.1:1241` was not running during this pass. No server process was started because project rules prohibit starting services without explicit user authorization.

Required scenario still pending:

- Login as the provided CaMeL user.
- Create a narration project with AI manga/comic style.
- Import `~/月亮与六便士第一章一.txt`.
- Use the right-side assistant to create 3 characters, 3 scenes, 3 props.
- Generate images for characters/scenes/props.
- Create 1 episode.

### Browser scenario test is not complete

`agent-browser` testing requires a running local ArcReel web service. This remains pending until the service is available or explicit authorization is given to start it.

### Remaining old `project_name` storage names

Some persistence models and task/session payload fields still use `project_name` as a historical column or response field name while carrying project id values. These need a separate schema-level cleanup if the final storage vocabulary must also be renamed to `project_id`.

### Remaining project-id audit gap

No active project route family is currently known to use display name as the lookup key. Some internal persistence/API response field names still use `project_name` while carrying project id values and are tracked as schema vocabulary cleanup rather than route authorization gaps.
