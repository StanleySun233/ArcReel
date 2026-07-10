# Tenant Project Permission Implementation Audit

**Date:** 20260711
**Status:** in progress

## Verified in this pass

### Issued Tokens disabled, business code retained

The Issued Tokens feature is disabled at invocation boundaries and the existing business implementation remains in place for future development.

Evidence:

- `server/routers/api_keys.py` keeps create/list/update/delete implementation paths behind `ISSUED_TOKENS_ENABLED = False`.
- `server/auth.py` rejects `arc-` Bearer tokens with `403 feature_disabled` while keeping `_verify_api_key`.
- `frontend/src/components/pages/ApiKeysTab.tsx` keeps the UI and disables actions through `ISSUED_TOKENS_ENABLED = false`.
- Tests:
  - `tests/test_api_keys_router.py`
  - `tests/test_auth_api_key.py`

### Project identity is now route-id based on the main workspace path

The project list, create, detail, update, delete, video capability route, cost estimation route, manual shot upload route, script review route, project script routes, episode metadata routes, source import route, overview routes, frontend project cards, create-project navigation, task filters, file routes, assistant routes, project event stream, version routes, grid routes, and reference video unit routes now use project id as the route key.

Evidence:

- `server/routers/projects.py` resolves project rows by `id` for the main CRUD path.
- `server/routers/projects.py` resolves project rows by `id` for video capabilities, script reads, script scene/shot edits, segment edits, episode title edits, source import, and overview update/generation.
- `server/routers/cost_estimation.py` resolves project rows by `id` and computes by project id.
- `server/routers/shot_uploads.py` resolves project rows by `id`, uses tenant-scoped `ProjectManager`, and records project file links with `resource_id=project_id`.
- `server/routers/script_review.py` resolves project rows by `id`; read requires viewer access, save/confirm require member access.
- `server/routers/versions.py` resolves project rows by `id`; version reads require viewer access and restores require member access.
- `server/routers/grids.py` resolves project rows by `id`; grid list/detail require viewer access and generate/regenerate require member access.
- `server/routers/reference_videos.py` resolves project rows by `id`; unit list requires viewer access and all mutating/generation/upload endpoints require member access.
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

## Verification completed

Backend:

- `python -m pytest tests/test_api_keys_router.py tests/test_auth_api_key.py tests/test_assistant_routes.py tests/test_files_router.py tests/test_files_api_minio.py tests/test_characters_router.py tests/test_scenes_router.py tests/test_props_router.py tests/test_products_router.py tests/test_asset_router_factory.py tests/test_generate_router.py tests/test_generate_router_tts.py tests/test_generation_queue.py tests/test_tasks_router_more.py tests/test_task_cancel_router.py tests/test_projects_router.py::TestProjectsRouter tests/test_projects_router.py::TestUnexpectedErrorsDoNotLeak tests/test_cost_estimation_router.py tests/test_shot_uploads_router.py tests/test_shot_uploads_minio.py tests/test_script_review.py tests/test_versions_router.py tests/test_grids_router.py tests/test_grid_router.py tests/server/test_reference_videos_router.py tests/server/test_reference_videos_router_ad.py tests/server/test_reference_video_e2e_backend.py tests/integration/test_reference_video_e2e.py -q`
  - Result: 335 passed
- `python -m ruff check <changed backend files and tests>`
  - Result: passed
- `basedpyright <changed backend route files>`
  - Result: 0 errors, 0 warnings; command exits non-zero because project config references a missing `.venv` path.

Frontend:

- `pnpm check`
  - Result: typecheck passed, lint passed, 925 tests passed.

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

### Non-core project subroutes still need full audit

The current pass focused on the scenario-critical path: project CRUD, scripts, segments, source import, drafts, style image upload, files/source upload, project assets, generation entry points, manual shot uploads, script review, cost estimation, tasks, assistant, and project event SSE.

The following route families still require a dedicated project-id audit before this can be called complete:

- usage grouping and display
- project export and Jianying draft export
