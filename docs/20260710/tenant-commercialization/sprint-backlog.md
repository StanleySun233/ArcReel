# Sprint Backlog: Tenant Commercialization

**Date:** 20260710
**Status:** in-progress
**Product brief:** Conversation request: build ArcReel commercial tenant edition with CaMeL login, ArcReel-owned tenants and memberships, PostgreSQL-only storage with RLS, Redis permission cache, MinIO private media storage, file-id project schema, tenant/user asset libraries with snapshot import and manual sync, tenant-scoped configuration/API keys/tasks, and frontend tenant switching. This is a new independent release with no runtime compatibility for SQLite, old local media paths, or old project media schema.
**Main integration branch:** integration/tenant-commercialization

## Sprint Goal

Deliver the tenant-commercialization foundation as a new ArcReel edition: CaMeL-authenticated users enter a personal tenant by default, switch tenants explicitly, operate only inside backend-authorized tenant context, store media in private MinIO through global `files`, and isolate business data through PostgreSQL tenant columns plus RLS.

## Documents

- Architecture design: [architecture-design.md](./architecture-design.md)
- API contract: [api-contract.md](./api-contract.md)
- Preflight CaMeL audit: [preflight-camel-audit.md](./preflight-camel-audit.md)

## Team

| Role | Agent Name | Progress File |
|------|------------|---------------|
| Backend | Tara | [->](./progress/preflight-camel-backend-tara.md) |
| Backend | Atlas | [->](./progress/pg-rls-foundation-backend-atlas.md) |
| Backend | Noah | [->](./progress/tenant-auth-backend-noah.md) |
| Frontend | Mira | [->](./progress/tenant-switcher-frontend-mira.md) |
| Backend | Cyra | [->](./progress/minio-files-backend-cyra.md) |
| Backend | Dax | [->](./progress/projects-tasks-backend-dax.md) |
| Backend | Iris | [->](./progress/assets-config-backend-iris.md) |
| Frontend | Nia | [->](./progress/assets-files-frontend-nia.md) |
| QA | Quinn | [->](./progress/qa-quinn.md) |
| Product Owner | Parker | |

## Implementation Waves

| Wave | Stories | Parallel Policy |
|------|---------|-----------------|
| 0 | Story 0, Story 1 | Parallel: CaMeL contract preflight is ArcReel-only and Story 1 owns infrastructure baseline. CaMeL-api is an external completed dependency and is not modified. |
| 1 | Story 2 | Serialized schema/RLS foundation. All later backend stories depend on this. |
| 2 | Story 2A | Serialized RLS hardening. Story 3+ require the app DB role to be non-superuser and non-BYPASSRLS. |
| 3 | Story 3, Story 4, Story 5, Story 7 | Parallel after Story 2A. Story 4 may build against `api-contract.md` before Story 3 merges, then final QA after Story 3. |
| 4 | Story 6, Story 8, Story 9 | Parallel after Story 5 where file-id behavior is needed. Shared frontend asset files are owned by Story 8/9 with explicit split. |
| 5 | Story 10 | Final cross-story QA and PO acceptance only after all implementation stories merge. |

## Planning Gates

These gates happen before implementation agents start. They are not story worktrees.

| Gate | Owner | Required Output | Pass Condition |
|------|-------|-----------------|----------------|
| Full Chain Design Audit | PM + Quinn | `chain-audit.md` | Every critical chain has an entry path, authority source, data write path, permission check, failure mode, cache invalidation path, and test owner. |
| Comprehensive Scenario Test Matrix | Quinn + PM | `scenario-test-matrix.md` | Every user-facing and security-sensitive scenario has setup, steps, expected result, required automated/manual coverage, and owning story. |

## Stories

### Story 0 - Preflight CaMeL OAuth Contract And API Key Provisioning Hardening

**Slug:** preflight-camel
**User value:** The tenant edition can rely on CaMeL OAuth and initial provider/API key bootstrap without ArcReel-side redirect weakness or unverified external contract assumptions.
**Status:** in-progress
**QA Status:** blocked
**PO Status:** pending

**Acceptance Criteria**
- [x] CaMeL-api is treated as a completed external dependency; this sprint does not modify CaMeL-api files, branches, tests, or worktrees.
- [ ] ArcReel-owned contract verification covers create, conflict, repair, scope/client validation, and retry behavior against the completed CaMeL-api service when endpoint credentials are available.
- [x] ArcReel dynamic OAuth redirect only accepts `http` or `https` forwarded scheme and fails closed on invalid scheme.
- [x] ArcReel bootstrap tests cover invalid forwarded scheme.
- [ ] The sprint audit document findings are either fixed or explicitly carried into later tenant stories.

**Engineering Subtasks**
- [x] Tara: Restrict forwarded scheme in `server/services/camel_auth.py`. (depends: none)
- [x] Tara: Extend `tests/test_camel_auth_provider_bootstrap.py` for invalid forwarded scheme. (depends: none)
- [ ] Tara: Add or document ArcReel-owned CaMeL provisioning contract smoke that does not edit CaMeL-api. (blocked: endpoint credentials and scenario fixtures)
- [ ] Quinn: Run ArcReel targeted pytest and contract smoke against the completed CaMeL-api service when available. (blocked: endpoint credentials and scenario fixtures)

**QA Evidence:** ArcReel redirect hardening targeted test passed with `5 passed in 0.32s`; live CaMeL contract smoke is blocked until endpoint credentials and create/conflict/repair/client/scope/retry fixtures are available.

### Story 1 - Development Middleware And PostgreSQL-Only Runtime Baseline

**Slug:** pg-runtime-baseline
**User value:** Developers and CI run against the same class of infrastructure as the commercial edition: PostgreSQL, Redis, and private MinIO.
**Status:** completed
**QA Status:** passed
**PO Status:** pending

**Acceptance Criteria**
- [x] Local middleware compose provides PostgreSQL, Redis, MinIO API, and MinIO Console with fixed MinIO release tag.
- [x] `.env.example` documents PostgreSQL, Redis, MinIO, and CaMeL tenant-edition settings.
- [x] `lib/db/engine.py` requires `postgresql+asyncpg` and rejects SQLite.
- [x] Test fixtures no longer create SQLite runtime databases for DB integration tests.
- [x] Existing SQLite-only Alembic tests are deleted or converted to PostgreSQL.
- [x] CI/dev commands document how to run tenant-edition tests against PostgreSQL.

**Engineering Subtasks**
- [x] Atlas: Finalize `deploy/dev/docker-compose.middleware.yml` and add env names aligned with runtime config. (depends: none)
- [x] Atlas: Update `.env.example` and `deploy/.env.example` with PG/Redis/MinIO variables. (depends: none)
- [x] Atlas: Change `lib/db/engine.py` to PG-only and remove SQLite helpers/default path. (depends: none)
- [x] Atlas: Convert `tests/conftest.py` DB fixtures to PostgreSQL. (depends: engine)
- [x] Atlas: Convert `tests/agent_session_store/conftest.py` DB fixtures to PostgreSQL or mark file-store-only tests separate. (depends: engine)
- [x] Atlas: Convert Alembic tests that set `sqlite+aiosqlite` to use the dev PostgreSQL URL. (depends: engine)
- [x] Quinn: Verify compose health, `alembic upgrade head`, and targeted DB tests. (depends: implementation)

**QA Evidence:** Middleware health checked via `docker ps`; `alembic upgrade head` passed against local PostgreSQL; targeted Story 1 suite passed with `23 passed in 6.49s`.

### Story 2 - Tenant Schema, RLS, And Request DB Context

**Slug:** tenant-schema-rls
**User value:** Tenant-owned rows are isolated by both application code and PostgreSQL RLS, so accidental cross-tenant SQL does not leak business data.
**Status:** completed
**QA Status:** passed
**PO Status:** pending

**Acceptance Criteria**
- [x] `users` stores CaMeL identity without using display name as a unique authorization key.
- [x] `tenants` and `tenant_memberships` exist with owner rules and role enum/checks.
- [x] Tenant-owned tables have `tenant_id` and indexes/unique constraints scoped by tenant.
- [x] RLS is enabled for tenant-owned business tables.
- [x] DB session context sets `app.current_user_id` and `app.current_tenant_id` per request/worker transaction.
- [x] Missing tenant context denies tenant-owned table access in integration tests.
- [x] `files` remains global and is not protected by a fake single-tenant ownership column.

**Engineering Subtasks**
- [x] Atlas: Add tenant/membership/project/file/asset-binding ORM models in `lib/db/models/tenant.py`, `lib/db/models/project.py`, `lib/db/models/file.py`, and update `lib/db/models/__init__.py`. (depends: Story 1)
- [x] Atlas: Replace `UserOwnedMixin` assumptions with tenant-aware model mixins in `lib/db/base.py`. (depends: Story 1)
- [x] Atlas: Add tenant columns to `Task`, `TaskEvent`, API calls, API keys, config, credentials, custom providers, agent credentials, usage/cost models. (depends: model inventory)
- [x] Atlas: Create PostgreSQL Alembic migration for new tables, tenant columns, scoped unique constraints, indexes, and RLS policies. (depends: models)
- [x] Atlas: Add DB context helper for setting PostgreSQL `app.current_user_id` and `app.current_tenant_id` in `lib/db/tenant_context.py`. (depends: engine)
- [x] Atlas: Add RLS integration tests in `tests/test_tenant_rls.py`. (depends: migration)
- [x] Quinn: Verify cross-tenant deny and same-tenant allow cases under PostgreSQL. (depends: implementation)

**QA Evidence:** Story 2 PostgreSQL/RLS regression slice passed with `51 passed in 8.17s`; Python compile check passed. RLS tests use a temporary non-superuser role because the local dev `arcreel` role has `SUPERUSER` and `BYPASSRLS`.

### Story 2A - PostgreSQL App Role RLS Hardening

**Slug:** pg-app-role-rls
**User value:** ArcReel connects to PostgreSQL through a non-superuser app role, so PostgreSQL RLS is an active production safety boundary instead of a bypassed policy.
**Status:** completed
**QA Status:** passed
**PO Status:** pending

**Acceptance Criteria**
- [x] Local middleware creates or updates an `arcreel_app` login role with `NOSUPERUSER` and `NOBYPASSRLS`.
- [x] Default tenant-edition `DATABASE_URL` examples use the app role, not the PostgreSQL admin role.
- [x] PostgreSQL integration tests can still create isolated schemas through an explicit admin URL while running application DB work as the app role.
- [x] A regression test fails when `DATABASE_URL` points at a role with `SUPERUSER` or `BYPASSRLS`.
- [x] RLS tests pass when `DATABASE_URL` uses the app role.
- [x] Existing development docs explain that existing PostgreSQL volumes need role initialization before switching to the app URL.

**Engineering Subtasks**
- [x] Atlas: Add dev PostgreSQL app-role init script and compose service. (depends: Story 2)
- [x] Atlas: Update `.env.example`, `deploy/.env.example`, and `deploy/dev/README.md` for app/admin DB URLs. (depends: init script)
- [x] Atlas: Update PostgreSQL test helpers to use `ARCREEL_TEST_DATABASE_ADMIN_URL` for schema/role setup. (depends: env docs)
- [x] Atlas: Add app-role guard test and run Story 2 regression with app `DATABASE_URL`. (depends: test helpers)
- [x] Quinn: Verify RLS deny/allow tests use the app role and do not rely on superuser bypass. (depends: implementation)

**QA Evidence:** App-role PostgreSQL regression slice passed with `52 passed in 8.26s`; `tests/test_pg_app_role.py` fails as expected when `DATABASE_URL` points at the local superuser `arcreel`; `sh -n deploy/dev/postgres-init-app-role.sh`, `docker compose config`, and `compileall` passed.

### Story 3 - Tenant Auth, Membership API, Redis Permission Cache

**Slug:** tenant-auth
**User value:** A CaMeL-authenticated user gets a personal tenant by default, can switch into memberships manually, and every backend request uses current real tenant permission.
**Status:** implementation complete
**QA Status:** passed
**PO Status:** pending

**Acceptance Criteria**
- [x] CaMeL login creates personal tenant if missing and signs token for personal tenant.
- [x] `CurrentUserInfo` or replacement principal includes `user_id`, `tenant_id`, `tenant_role` snapshot, and provider.
- [x] PermissionService checks Redis first, PostgreSQL on miss, and invalidates cache on membership changes.
- [x] Tenant list endpoint returns only memberships for current user.
- [x] Tenant token switch endpoint validates membership before signing.
- [x] Member CRUD enforces owner/admin/member/view rules.
- [x] API key auth resolves tenant-scoped key and checks current membership.
- [x] 403 stale role path allows frontend token refresh.

**Engineering Subtasks**
- [x] Noah: Extend token creation/verification in `server/auth.py` for tenant-scoped JWT. (depends: Story 2)
- [x] Noah: Add `server/services/tenant_auth.py` for personal tenant creation, token signing, and tenant selection. (depends: Story 2)
- [x] Noah: Add `server/services/permission_cache.py` for Redis-backed permission cache. (depends: Story 2)
- [x] Noah: Add `server/routers/tenants.py` for tenant detail, create, member list/search/create/update/delete. (depends: services)
- [x] Noah: Extend `server/routers/auth.py` with `/auth/me`, `/auth/tenants`, `/auth/tenant-token`, `/auth/refresh-current-tenant`. (depends: token/service)
- [x] Noah: Convert `server/routers/api_keys.py` and `lib/db/repositories/api_key_repository.py` to tenant-scoped API keys. (depends: Story 2)
- [x] Noah: Add backend tests for login personal tenant, switch, role matrix, stale token refresh, and API key tenant auth. (depends: routes)
- [x] Quinn: Run auth/router/API key targeted tests under PostgreSQL. (depends: implementation)

**QA Evidence:** PostgreSQL app-role regression passed with `76 passed, 1 warning`; API key and tenant auth slice passed with `36 passed, 1 warning`; `ruff check`, `ruff format --check`, `basedpyright`, `compileall`, Redis permission cache set/get/delete smoke, and `alembic heads` passed.

### Story 4 - Frontend Tenant Switcher And Permission UX

**Slug:** tenant-switcher-ui
**User value:** Users see the current tenant, switch tenants deliberately, and the UI updates role-gated actions without trusting cached role for backend authorization.
**Status:** planned
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] Auth store persists token, current tenant, tenant list, cached role, and owner flag.
- [ ] Login callback defaults to personal tenant token.
- [ ] Tenant listbox switches tenant by calling `/auth/tenant-token`.
- [ ] 403 stale role/access revoked responses trigger refresh or personal-space fallback.
- [ ] Role-gated UI hides write actions for `view`, tenant admin actions for non-admin, and admin promotion for non-owner.
- [ ] Frontend tests cover listbox, switch token replacement, stale role refresh, and access revoked fallback.

**Engineering Subtasks**
- [ ] Mira: Extend auth API types and client helpers in `frontend/src/api.ts`. (depends: api-contract)
- [ ] Mira: Extend `frontend/src/stores/auth-store.ts` for current tenant, tenant list, token switch, and refresh. (depends: API helpers)
- [ ] Mira: Add tenant listbox component under `frontend/src/components/tenant/`. (depends: store)
- [ ] Mira: Wire tenant listbox into the app shell/navigation. (depends: component)
- [ ] Mira: Add frontend permission helpers in `frontend/src/utils/auth.ts`. (depends: store)
- [ ] Mira: Update auth i18n in `frontend/src/i18n/{zh,en,vi}/auth.ts`. (depends: UI)
- [ ] Mira: Add frontend tests for auth store, listbox, stale role, and revoked tenant. (depends: implementation)
- [ ] Quinn: Run `pnpm check` targeted frontend suite. (depends: implementation)

**QA Evidence:** pending

### Story 5 - FileService, MinIO, Private Files, Signed URLs

**Slug:** minio-files
**User value:** Media artifacts are stored privately in MinIO, referenced by `file_id`, and exposed to browsers only through authorized short-lived signed URLs.
**Status:** planned
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] `files` table stores object metadata and alias; object key is `{uuid}.{ext}`.
- [ ] MinIO StorageService can put/get/stat/delete objects.
- [ ] FileService creates `files` rows and object writes in a safe order with rollback behavior documented.
- [ ] File links support project, asset, task, and personal library references.
- [ ] `/files/{file_id}/signed-url` checks current access before signing.
- [ ] Private bucket is not directly public.
- [ ] Existing upload/file routes return `file_id` instead of local paths for media.

**Engineering Subtasks**
- [ ] Cyra: Add MinIO settings and storage abstraction in `lib/storage/minio.py` and `lib/storage/__init__.py`. (depends: Story 1)
- [ ] Cyra: Add FileService in `lib/files/service.py`. (depends: Story 2)
- [ ] Cyra: Add file repository in `lib/db/repositories/file_repo.py`. (depends: Story 2)
- [ ] Cyra: Update `server/routers/files.py` to upload and sign by file_id. (depends: service)
- [ ] Cyra: Update `server/routers/shot_uploads.py` and upload helpers to return file_id. (depends: service)
- [ ] Cyra: Add tests for object key format, private signed URL, access deny, and file links. (depends: routes)
- [ ] Quinn: Verify MinIO integration through local middleware and targeted file tests. (depends: implementation)

**QA Evidence:** pending

### Story 6 - Tenant Project System And File-Id Project JSON

**Slug:** tenant-projects
**User value:** Projects are created and read inside a tenant-scoped project registry and local tenant directory, while all media references use `file_id`.
**Status:** planned
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] Project registry table enforces `unique(tenant_id, name)`.
- [ ] Project files live under `$ARCREEL_DATA_DIR/_tenants/{tenant_id}/projects/{project_name}/project.json`.
- [ ] ProjectManager cannot be constructed without tenant context.
- [ ] `project.json` validators reject legacy local path media references.
- [ ] Project create/list/read/update/archive routes are tenant-scoped.
- [ ] Same project name in two tenants is allowed and isolated.

**Engineering Subtasks**
- [ ] Dax: Refactor `lib/user_scope.py` into tenant project path helpers or remove user project scope. (depends: Story 2)
- [ ] Dax: Refactor `lib/project_manager.py` to require tenant context and tenant project root. (depends: Story 2)
- [ ] Dax: Add project repository in `lib/db/repositories/project_repo.py`. (depends: Story 2)
- [ ] Dax: Update `server/routers/projects.py` and project services for registry-backed tenant list/create/read. (depends: ProjectManager)
- [ ] Dax: Update `lib/data_validator.py` and project schema helpers to require file_id for media. (depends: Story 5)
- [ ] Dax: Update archive/cover/events services for tenant paths and file_id media. (depends: routes)
- [ ] Dax: Replace legacy project tests with tenant/file-id tests. (depends: implementation)
- [ ] Quinn: Verify cross-tenant same-name projects and legacy path rejection. (depends: implementation)

**QA Evidence:** pending

### Story 7 - Tenant-Scoped Provider Config, Credentials, Agent Config, API Keys

**Slug:** tenant-config
**User value:** Each tenant has its own provider credentials, custom providers, defaults, Agent credentials, and API keys; personal configuration lives in the personal tenant.
**Status:** planned
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] Provider config and system settings are tenant-scoped.
- [ ] Provider credentials are tenant-scoped.
- [ ] Custom providers and models are tenant-scoped.
- [ ] Agent Anthropic credentials are tenant-scoped.
- [ ] API key names are unique per tenant, not globally.
- [ ] Existing routes infer tenant from token and never accept frontend tenant id.
- [ ] CaMeL provider bootstrap writes into current personal tenant or selected tenant according to auth flow rules.

**Engineering Subtasks**
- [ ] Iris: Convert `lib/config/repository.py`, `lib/config/service.py`, `lib/config/resolver.py` to tenant context. (depends: Story 2)
- [ ] Iris: Convert `lib/db/models/config.py` and related tests to tenant constraints. (depends: Story 2)
- [ ] Iris: Convert `lib/db/models/credential.py` and `lib/db/repositories/credential_repository.py`. (depends: Story 2)
- [ ] Iris: Convert `lib/db/models/custom_provider.py` and `lib/db/repositories/custom_provider_repo.py`. (depends: Story 2)
- [ ] Iris: Convert `lib/db/models/agent_credential.py` and `lib/db/repositories/agent_credential_repo.py`. (depends: Story 2)
- [ ] Iris: Update `server/routers/system_config.py`, `server/routers/providers.py`, `server/routers/custom_providers.py`, `server/routers/agent_config.py`. (depends: repositories)
- [ ] Iris: Convert `server/services/camel_bootstrap.py` from user-level completion to tenant-level completeness. (depends: Story 3)
- [ ] Quinn: Run provider/config/API key/agent credential tests under PostgreSQL. (depends: implementation)

**QA Evidence:** pending

### Story 8 - Asset Libraries, Snapshot Import, Manual Sync

**Slug:** asset-libraries
**User value:** Users can manage personal and tenant asset libraries, import across readable libraries as snapshots, and manually sync from the source when desired.
**Status:** planned
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] Asset entity stores file_id media references.
- [ ] Asset binding supports user library and tenant library with `parent_binding_id`.
- [ ] Tenant library write requires `member+`.
- [ ] Personal library access requires owning user.
- [ ] Import creates a new asset snapshot and binding; it does not copy MinIO object.
- [ ] Manual sync overwrites target asset only after explicit confirmation.
- [ ] Source read permission is checked during import and sync.
- [ ] Frontend exposes personal/tenant library views and sync confirmation.

**Engineering Subtasks**
- [ ] Iris: Replace global asset uniqueness in `lib/db/models/asset.py` with asset entity plus library binding model. (depends: Story 2)
- [ ] Iris: Refactor `lib/db/repositories/asset_repo.py` for personal/tenant libraries, import, and sync. (depends: model)
- [ ] Iris: Update `server/routers/assets.py` and `_asset_router_factory.py` for binding ids and file_id media. (depends: repository)
- [ ] Iris: Update `lib/asset_types.py` consumers for file_id fields. (depends: routes)
- [ ] Nia: Update frontend asset types in `frontend/src/types/asset.ts`. (depends: API contract)
- [ ] Nia: Update asset store and components under `frontend/src/stores/assets-store.ts` and `frontend/src/components/assets/`. (depends: backend contract)
- [ ] Nia: Add sync confirmation UI and permission states. (depends: components)
- [ ] Quinn: Verify import snapshot, manual sync, source permission revoke, and frontend flows. (depends: implementation)

**QA Evidence:** pending

### Story 9 - Generation Tasks, Worker Tenant Context, File Outputs

**Slug:** tenant-generation
**User value:** Generation requests enforce permission at submission time, run later under the captured tenant context, and write all outputs as file IDs.
**Status:** planned
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] Task rows include `tenant_id` and `requested_by_user_id`.
- [ ] Enqueue checks current permission and stores tenant/user snapshot.
- [ ] Worker sets DB tenant context from task row.
- [ ] User role changes after enqueue do not cancel submitted tasks.
- [ ] Task queries/SSE are tenant-scoped.
- [ ] Generated image/video/text/audio outputs are written through FileService and referenced as file_id.
- [ ] Dedupe indexes include tenant_id.

**Engineering Subtasks**
- [ ] Dax: Update `lib/db/models/task.py`, `lib/db/repositories/task_repo.py`, and task migration pieces owned by Story 2. (depends: Story 2)
- [ ] Dax: Update `lib/generation_queue.py` and `lib/generation_queue_client.py` to persist tenant/user. (depends: auth context)
- [ ] Dax: Update `lib/generation_worker.py` to set tenant DB context from task. (depends: DB context)
- [ ] Dax: Update `server/services/generation_tasks.py` and `server/services/reference_video_tasks.py` to use FileService outputs. (depends: Story 5)
- [ ] Dax: Update `server/routers/generate.py`, `server/routers/tasks.py`, and task SSE behavior. (depends: queue)
- [ ] Dax: Update usage/cost tracking to include tenant_id. (depends: Story 2)
- [ ] Quinn: Verify enqueue permission, post-enqueue role change, worker writeback, and tenant-scoped task queries. (depends: implementation)

**QA Evidence:** pending

### Story 10 - Cross-Story QA, Security Review, Product Acceptance

**Slug:** tenant-commercialization-qa
**User value:** The tenant edition has evidence that the critical cross-tenant, file-access, and auth flows work together before implementation is accepted.
**Status:** planned
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] Fresh PostgreSQL + Redis + MinIO environment can start from empty state.
- [ ] First CaMeL login creates personal tenant and tenant token.
- [ ] User creates second tenant, adds member/viewer, switches tenant, and sees correct UI permissions.
- [ ] Cross-tenant project/file/task/asset access attempts are denied.
- [ ] File signed URL requires current access and bucket stays private.
- [ ] Asset import and manual sync work across personal and tenant libraries.
- [ ] Provider bootstrap initializes tenant-scoped providers without leaking raw keys to frontend.
- [ ] `chain-audit.md` has no unresolved critical chain gap.
- [ ] `scenario-test-matrix.md` covers login, tenant switching, member CRUD, role downgrade, revoked access, project CRUD, file upload/signing, asset import/sync, provider bootstrap/repair, API key auth, generation queue, worker writeback, usage/cost, SSE, and frontend permission UI.
- [ ] Every scenario in `scenario-test-matrix.md` is either automated or marked manual with reason and evidence.
- [ ] All story QA evidence is recorded before PO review.

**Engineering Subtasks**
- [ ] Quinn: Complete `chain-audit.md` from the final design and merged implementation. (depends: all stories)
- [ ] Quinn: Complete `scenario-test-matrix.md` with automated/manual coverage mapping. (depends: all stories)
- [ ] Quinn: Build backend integration test matrix for tenant isolation and RLS. (depends: all backend stories)
- [ ] Quinn: Build frontend integration test matrix for tenant switching and permission UI. (depends: frontend stories)
- [ ] Quinn: Run targeted test suites and record command output. (depends: all stories)
- [ ] Quinn: File defects under `docs/20260710/tenant-commercialization/defects/`. (depends: failures)
- [ ] Parker: Product Owner review of all acceptance criteria from the main integration branch. (depends: QA passed)

**QA Evidence:** pending

## File Ownership

| File Path | Owner | Story | Parallel Policy |
|-----------|-------|-------|-----------------|
| `docs/20260710/tenant-commercialization/*` | PM | Sprint planning | exclusive |
| `server/services/camel_auth.py` | Tara | Story 0 | exclusive until merged, then Noah may integrate tenant token changes |
| `tests/test_camel_auth_provider_bootstrap.py` | Tara | Story 0 | exclusive |
| `deploy/dev/docker-compose.middleware.yml` | Atlas | Story 1 | exclusive |
| `deploy/dev/postgres-init-app-role.sh` | Atlas | Story 2A | exclusive |
| `.env.example` | Atlas | Story 1 | exclusive |
| `deploy/.env.example` | Atlas | Story 1 | exclusive |
| `deploy/dev/README.md` | Atlas | Story 2A | exclusive |
| `lib/db/engine.py` | Atlas | Story 1 | exclusive |
| `tests/conftest.py` | Atlas | Story 1 | exclusive |
| `tests/agent_session_store/conftest.py` | Atlas | Story 1 | exclusive |
| `alembic/versions/*tenant*.py` | Atlas | Story 2 | exclusive schema owner |
| `lib/db/base.py` | Atlas | Story 2 | exclusive |
| `lib/db/models/*.py` | Atlas | Story 2 | schema owner for columns; later story owners may edit behavior only after Story 2 merge |
| `lib/db/tenant_context.py` | Atlas | Story 2 | exclusive |
| `tests/test_tenant_rls.py` | Atlas | Story 2 | exclusive |
| `tests/test_pg_app_role.py` | Atlas | Story 2A | exclusive |
| `server/auth.py` | Noah | Story 3 | exclusive after Story 0 merge |
| `server/routers/auth.py` | Noah | Story 3 | exclusive |
| `server/routers/tenants.py` | Noah | Story 3 | exclusive |
| `server/services/tenant_auth.py` | Noah | Story 3 | exclusive |
| `server/services/permission_cache.py` | Noah | Story 3 | exclusive |
| `server/routers/api_keys.py` | Noah/Iris | Story 3 / Story 7 | serialized: Noah auth behavior first, Iris tenant config constraints second |
| `lib/db/repositories/api_key_repository.py` | Noah/Iris | Story 3 / Story 7 | serialized |
| `frontend/src/api.ts` | Mira/Nia | Story 4 / Story 8 | serialized: Mira tenant auth helpers first, Nia asset helpers second |
| `frontend/src/stores/auth-store.ts` | Mira | Story 4 | exclusive |
| `frontend/src/components/tenant/*` | Mira | Story 4 | exclusive |
| `frontend/src/utils/auth.ts` | Mira | Story 4 | exclusive |
| `frontend/src/i18n/*/auth.ts` | Mira | Story 4 | exclusive |
| `lib/storage/*` | Cyra | Story 5 | exclusive |
| `lib/files/*` | Cyra | Story 5 | exclusive |
| `lib/db/repositories/file_repo.py` | Cyra | Story 5 | exclusive |
| `server/routers/files.py` | Cyra | Story 5 | exclusive |
| `server/routers/shot_uploads.py` | Cyra | Story 5 | exclusive |
| `lib/user_scope.py` | Dax | Story 6 | exclusive, likely removed/replaced |
| `lib/project_manager.py` | Dax | Story 6 | exclusive |
| `lib/db/repositories/project_repo.py` | Dax | Story 6 | exclusive |
| `server/routers/projects.py` | Dax | Story 6 | exclusive |
| `server/services/project_archive.py` | Dax | Story 6 | exclusive |
| `server/services/project_cover.py` | Dax | Story 6 | exclusive |
| `server/services/project_events.py` | Dax | Story 6 | exclusive |
| `lib/config/*` | Iris | Story 7 | exclusive after Story 2 |
| `lib/db/repositories/credential_repository.py` | Iris | Story 7 | exclusive |
| `lib/db/repositories/custom_provider_repo.py` | Iris | Story 7 | exclusive |
| `lib/db/repositories/agent_credential_repo.py` | Iris | Story 7 | exclusive |
| `server/routers/system_config.py` | Iris | Story 7 | exclusive |
| `server/routers/providers.py` | Iris | Story 7 | exclusive |
| `server/routers/custom_providers.py` | Iris | Story 7 | exclusive |
| `server/routers/agent_config.py` | Iris | Story 7 | exclusive |
| `server/services/camel_bootstrap.py` | Iris | Story 7 | exclusive after Story 0 |
| `lib/db/models/asset.py` | Atlas/Iris | Story 2 / Story 8 | Atlas schema first, Iris behavior-specific changes after merge |
| `lib/db/repositories/asset_repo.py` | Iris | Story 8 | exclusive |
| `server/routers/assets.py` | Iris | Story 8 | exclusive |
| `server/routers/_asset_router_factory.py` | Iris | Story 8 | exclusive |
| `lib/asset_types.py` | Iris | Story 8 | exclusive |
| `frontend/src/types/asset.ts` | Nia | Story 8 | exclusive |
| `frontend/src/stores/assets-store.ts` | Nia | Story 8 | exclusive |
| `frontend/src/components/assets/*` | Nia | Story 8 | exclusive |
| `lib/db/models/task.py` | Atlas/Dax | Story 2 / Story 9 | Atlas schema first, Dax behavior after merge |
| `lib/db/repositories/task_repo.py` | Dax | Story 9 | exclusive |
| `lib/generation_queue.py` | Dax | Story 9 | exclusive |
| `lib/generation_queue_client.py` | Dax | Story 9 | exclusive |
| `lib/generation_worker.py` | Dax | Story 9 | exclusive |
| `server/services/generation_tasks.py` | Dax | Story 9 | exclusive |
| `server/services/reference_video_tasks.py` | Dax | Story 9 | exclusive |
| `server/routers/generate.py` | Dax | Story 9 | exclusive |
| `server/routers/tasks.py` | Dax | Story 9 | exclusive |
| `tests/**` | Quinn | Story 10 | QA may add/adjust tests after story implementation slices; story owners own their local tests before QA |

## Worktrees

| Story | Branch | Worktree Path | Merge Target | Merge Status | Cleanup Status |
|-------|--------|---------------|--------------|--------------|----------------|
| Story 0 - Preflight CaMeL OAuth Contract And API Key Provisioning Hardening | `story/tenant-commercialization/preflight-camel` | `../ArcReel-worktrees/tenant-commercialization/preflight-camel` | `integration/tenant-commercialization` | pending | pending |
| Story 1 - Development Middleware And PostgreSQL-Only Runtime Baseline | `story/tenant-commercialization/pg-runtime-baseline` | `../ArcReel-worktrees/tenant-commercialization/pg-runtime-baseline` | `integration/tenant-commercialization` | merged | removed |
| Story 2 - Tenant Schema, RLS, And Request DB Context | `story/tenant-commercialization/tenant-schema-rls` | `../ArcReel-worktrees/tenant-commercialization/tenant-schema-rls` | `integration/tenant-commercialization` | merged | removed |
| Story 2A - PostgreSQL App Role RLS Hardening | `story/tenant-commercialization/pg-app-role-rls` | `../ArcReel-worktrees/tenant-commercialization/pg-app-role-rls` | `integration/tenant-commercialization` | merged | removed |
| Story 3 - Tenant Auth, Membership API, Redis Permission Cache | `story/tenant-commercialization/tenant-auth` | `../ArcReel-worktrees/tenant-commercialization/tenant-auth` | `integration/tenant-commercialization` | merged | pending |
| Story 4 - Frontend Tenant Switcher And Permission UX | `story/tenant-commercialization/tenant-switcher-ui` | `../ArcReel-worktrees/tenant-commercialization/tenant-switcher-ui` | `integration/tenant-commercialization` | pending | pending |
| Story 5 - FileService, MinIO, Private Files, Signed URLs | `story/tenant-commercialization/minio-files` | `../ArcReel-worktrees/tenant-commercialization/minio-files` | `integration/tenant-commercialization` | pending | pending |
| Story 6 - Tenant Project System And File-Id Project JSON | `story/tenant-commercialization/tenant-projects` | `../ArcReel-worktrees/tenant-commercialization/tenant-projects` | `integration/tenant-commercialization` | pending | pending |
| Story 7 - Tenant-Scoped Provider Config, Credentials, Agent Config, API Keys | `story/tenant-commercialization/tenant-config` | `../ArcReel-worktrees/tenant-commercialization/tenant-config` | `integration/tenant-commercialization` | pending | pending |
| Story 8 - Asset Libraries, Snapshot Import, Manual Sync | `story/tenant-commercialization/asset-libraries` | `../ArcReel-worktrees/tenant-commercialization/asset-libraries` | `integration/tenant-commercialization` | pending | pending |
| Story 9 - Generation Tasks, Worker Tenant Context, File Outputs | `story/tenant-commercialization/tenant-generation` | `../ArcReel-worktrees/tenant-commercialization/tenant-generation` | `integration/tenant-commercialization` | pending | pending |
| Story 10 - Cross-Story QA, Security Review, Product Acceptance | `story/tenant-commercialization/tenant-commercialization-qa` | `../ArcReel-worktrees/tenant-commercialization/tenant-commercialization-qa` | `integration/tenant-commercialization` | pending | pending |

## Blockers

| Date | Story/Subtask | Owner | Blocker | Resolution |
|------|---------------|-------|---------|------------|
| 2026-07-10 | Story 0 | Tara/Quinn | CaMeL-api is a completed external dependency and not owned by this sprint. | Verify the contract from ArcReel; record any mismatch as an external defect without editing CaMeL-api. |
| 2026-07-10 | Story 1 | Atlas | Existing ArcReel tests and Alembic tests still assume SQLite. | Resolved in Story 1 merge `7c58035`. |
| 2026-07-10 | Story 2 | Atlas | RLS context leak or wrong tenant setting is a high-severity isolation failure. | Centralize DB context and require deny-by-default RLS tests. |
| 2026-07-10 | Story 5 | Cyra | MinIO community/commercial licensing risk is not a code blocker but must be resolved before commercial release. | Track as product/legal release gate. |
| 2026-07-10 | Story 6 | Dax | `project.json` remains local, so horizontal deployment requires shared filesystem or later project metadata migration. | Accept for first tenant edition; document deployment topology. |
| 2026-07-10 | Story 8 | Iris/Nia | Manual asset sync overwrites snapshot data. | Require explicit frontend confirmation and backend `confirm_overwrite=true`. |

## Definition Of Done For This Sprint

- Every story has a story branch and worktree.
- Every story records implementation commits in its progress file.
- Every story passes story-level QA in its worktree.
- All story branches merge into the integration branch.
- All merged story worktrees are removed with `git worktree remove`.
- Product Owner accepts every story or rejects it into a follow-up story.
- `docs/INDEX.md` moves this sprint from `in-progress` to `completed` only after PO acceptance.
