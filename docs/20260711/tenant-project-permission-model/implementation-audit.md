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

The project list, create, detail, update, delete, frontend project cards, create-project navigation, task filters, file routes, assistant routes, and project event stream now use project id as the route key.

Evidence:

- `server/routers/projects.py` resolves project rows by `id` for the main CRUD path.
- Project creation stores local project JSON under tenant-scoped project-id paths.
- `frontend/src/types/project.ts` requires `ProjectSummary.id`.
- `frontend/src/components/pages/ProjectsPage.tsx` links and deletes by `project.id`.
- `frontend/src/components/pages/CreateProjectModal.tsx` navigates and uploads style image by `resp.id`.
- `frontend/src/api.ts` uses `project_id` query parameters for task list/stats/SSE.

### File and project media routes bind files to project id

Project file upload, source import, source read/update/delete, static project file serving, and file listing use `project_id`. Media uploads return `file_id` and do not expose local server paths.

Evidence:

- `server/routers/files.py` route parameters for project file/source operations are `project_id`.
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
- `tests/test_assistant_routes.py` covers route contract and project-id forwarding.

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

## Verification completed

Backend:

- `python -m pytest tests/test_api_keys_router.py tests/test_auth_api_key.py tests/test_assistant_routes.py tests/test_files_router.py tests/test_files_api_minio.py tests/test_characters_router.py tests/test_scenes_router.py tests/test_props_router.py tests/test_products_router.py tests/test_asset_router_factory.py tests/test_generate_router.py tests/test_generate_router_tts.py tests/test_generation_queue.py tests/test_tasks_router_more.py tests/test_task_cancel_router.py tests/test_projects_router.py::TestProjectsRouter -q`
  - Result: 200 passed
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

The current pass focused on the scenario-critical path: project CRUD, files/source upload, project assets, generation entry points, tasks, assistant, and project event SSE.

The following route families still require a dedicated project-id audit before this can be called complete:

- script review
- versions
- grids
- reference video units
- cost estimation
- usage grouping and display
