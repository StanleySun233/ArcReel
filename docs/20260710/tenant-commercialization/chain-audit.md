# Chain Audit: Tenant Commercialization

**Date:** 20260710
**Status:** Story10 live acceptance passed with documented residual risks

This audit checks whether every critical chain has an entry path, authority source, data write path, permission check, failure mode, cache invalidation path, and test owner.

## Audit Summary

| Chain | Coverage | Blocking Gap | Owning Story |
|-------|----------|--------------|--------------|
| CaMeL login to personal tenant token | automated backend + live local CaMeL + browser | localhost/127.0.0.1 OAuth cookie host mismatch documented | Story 3 / Story 10 |
| CaMeL provider/API key bootstrap | automated backend + live local CaMeL create flow | external conflict/repair/wrong-client/missing-scope contract cases remain risk-tracked | Story 0 / Story 7 |
| Tenant switch | automated backend/frontend | none | Story 3 / Story 4 |
| Member CRUD and role matrix | automated backend | none | Story 3 |
| Redis permission cache | automated backend + smoke | none | Story 3 |
| PostgreSQL RLS context | automated backend | none for request path; local dev superuser bypass noted in Story 2 evidence | Story 2 |
| API key auth under tenant | automated backend | none | Story 3 / Story 7 |
| File upload to MinIO | automated backend + live MinIO | signed URL expiry remains not time-waited in live smoke | Story 5 |
| Signed URL access | automated backend + live MinIO | expiry not time-waited; cross-tenant and tamper denial verified | Story 5 |
| Project CRUD and file-id JSON | automated backend + live smoke | media artifacts and project route tenant roots verified; remaining legacy non-media consumers risk-tracked | Story 6 / Story 10 |
| Asset library import/sync | automated backend/frontend | none | Story 8 |
| Tenant provider/config/agent settings | automated backend + live CaMeL bootstrap | legacy provider API unit fixtures are not tenant-aware and are excluded from scenario runner | Story 7 / Story 10 |
| Generation enqueue and worker writeback | automated backend | grid split cell file-id migration remains follow-up | Story 9 / Story 10 |
| Usage/cost attribution | automated backend | aggregate report smoke remains Story10/live | Story 9 |
| Frontend permission UX | automated frontend + browser smoke | view-only deep UI spot checks remain unit/integration evidence, not full browser coverage | Story 4 / Story 8 / Story 10 |

## Scenario Runner Evidence

`scripts/tenant_commercialization_scenarios.py -- -q` passed on the Story10 worktree:

| Group | Result | Scenario IDs |
|-------|--------|--------------|
| `auth_roles` | 30 passed, 1 warning | AUTH-01, AUTH-03, AUTH-04, AUTH-05, AUTH-06, AUTH-07, ROLE-01, ROLE-04, ROLE-05, ROLE-06, ROLE-09, CFG-06, CFG-07 |
| `rls_config` | 10 passed | RLS-01, RLS-02, RLS-03, RLS-04, RLS-06, CFG-01, CFG-02, CFG-03, CFG-04, CFG-05, CAMEL-08, CAMEL-09 |
| `files_projects_assets` | 113 passed, 1 warning | FILE-01, FILE-02, FILE-04, FILE-05, PROJ-01, PROJ-02, PROJ-03, PROJ-04, PROJ-05, PROJ-06, PROJ-07, ASSET-01, ASSET-02, ASSET-03, ASSET-04, ASSET-06, ASSET-07, ASSET-08, ASSET-09 |
| `generation_tasks_usage` | 114 passed, 1 warning | GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, GEN-06, GEN-07, GEN-08 |

Integration branch regression after Story6/8/9 merge also passed:

- Backend tenant/projects/assets/generation targeted suite: 218 passed, 1 warning.
- Frontend `pnpm check`: 107 test files passed, 922 tests passed.
- Python targeted `ruff check`: passed.

Story10 fresh-stack live acceptance after fixes:

- Fresh DB/container: `arcreel_acceptance_20260710214815` with container `arcreel-acceptance-current-20260710214815`.
- Alembic head: `8d7e6f5a4b3c`.
- Live API smoke: `deploy/test/arcreel_api_smoke.py` passed 23 checks, including CaMeL OAuth login, provider bootstrap, default personal tenant, tenant role matrix, project/file isolation, MinIO signed URL denial/tamper cases, and asset `image_file_id` write.
- Live tenant/MinIO smoke: `deploy/test/arcreel_tenant_role_minio_smoke.py` passed role boundary, member/view project access, signed URL cross-tenant denial, and tenant asset file-id checks.
- Browser smoke: `agent-browser` verified login via CaMeL on `http://localhost:11242`, default `{user_name}的个人空间`, visible `Switch space` listbox, backend-created second tenant refresh, and click switch to `UI Team Switch Smoke`.
- Frontend regression: `pnpm lint && pnpm check` passed with 107 test files and 923 tests.
- Targeted backend regression: `tests/test_assets_router.py tests/test_db_engine.py tests/test_files_api_minio.py -q` passed with 14 tests.
- Scenario runner: `auth_roles` 30 passed, `rls_config` 10 passed, `files_projects_assets` 113 passed, `generation_tasks_usage` 114 passed.
- Scoped smoke-script type check: `basedpyright deploy/test/arcreel_api_smoke.py deploy/test/arcreel_tenant_role_minio_smoke.py` reported `0 errors, 0 warnings, 0 notes`; command exit remains 3 because this worktree has no `.venv` subdirectory for basedpyright.

## Chain Details

### 1. CaMeL Login To Personal Tenant Token

| Field | Design |
|-------|--------|
| Entry | `GET /api/v1/auth/camel/start` then `/api/v1/auth/camel/callback` |
| Authority source | CaMeL userinfo for identity; ArcReel PostgreSQL for tenant and membership |
| Writes | `users`, `tenants`, `tenant_memberships` |
| Permission check | Callback owns identity; personal tenant create only for that user |
| Cache invalidation | none on first create; membership cache populated on first business request |
| Failure modes | OAuth failure, userinfo failure, personal tenant create failure, token signing failure |
| Tests | login creates user, personal tenant, admin membership, token tenant claims |

### 2. CaMeL Provider/API Key Bootstrap

| Field | Design |
|-------|--------|
| Entry | `/api/v1/camel/bootstrap/start-url`, OAuth callback with provider intent |
| Authority source | CaMeL OAuth bearer token with `arcreel:token-provision`; ArcReel tenant membership for local writes |
| Writes | CaMeL visible tokens; ArcReel tenant-scoped providers/config/defaults |
| Permission check | CaMeL validates client/scope; ArcReel validates user mismatch and current tenant bootstrap target |
| Cache invalidation | provider/config caches if any; none in current design |
| Failure modes | token conflict, partial local failure, user mismatch, missing env, retry behavior under external contract |
| Tests | Story 0 must run ArcReel-owned contract smoke for create/conflict/repair/client/scope/retry behavior when CaMeL-api endpoint credentials are available |

### 3. Tenant Switch

| Field | Design |
|-------|--------|
| Entry | `POST /api/v1/auth/tenant-token` |
| Authority source | `tenant_memberships` |
| Writes | none except optional session/audit metadata |
| Permission check | target tenant membership for current user |
| Cache invalidation | no invalidation; reads current permission cache |
| Failure modes | target not found, membership missing, user inactive |
| Tests | valid switch, revoked target, stale role refresh |

### 4. Member CRUD And Role Matrix

| Field | Design |
|-------|--------|
| Entry | `/api/v1/tenant/members*` |
| Authority source | `tenants.owner_user_id`, `tenant_memberships.role` |
| Writes | `tenant_memberships` |
| Permission check | owner/admin/member matrix |
| Cache invalidation | delete or bump permission cache for changed user/tenant |
| Failure modes | owner removal, owner downgrade, unauthorized admin promotion, duplicate membership |
| Tests | full role matrix and owner invariants |

### 5. PostgreSQL RLS Context

| Field | Design |
|-------|--------|
| Entry | request DB session and worker DB session |
| Authority source | signed token plus PermissionService membership lookup |
| Writes | PostgreSQL session variables |
| Permission check | application-level service plus RLS policy |
| Cache invalidation | not applicable |
| Failure modes | missing context, wrong tenant context, worker context missing |
| Tests | deny missing context, deny cross tenant, allow same tenant, worker context |

### 6. File Upload And Signed URL

| Field | Design |
|-------|--------|
| Entry | `POST /api/v1/files`, `GET /api/v1/files/{file_id}/signed-url` |
| Authority source | current tenant/user permission and business file links |
| Writes | MinIO object, `files`, `file_links` |
| Permission check | upload requires `member+`; signed URL requires accessible referencing resource |
| Cache invalidation | none |
| Failure modes | object write success with DB failure, DB success with object failure, orphaned link, revoked access |
| Tests | private bucket, signed URL, cross-tenant deny, rollback/orphan cleanup |

### 7. Project CRUD And File-Id JSON

| Field | Design |
|-------|--------|
| Entry | `/api/v1/projects*` |
| Authority source | current tenant context and `projects` registry |
| Writes | `projects`, tenant-local `project.json`, file links |
| Permission check | `view+` read, `member+` write |
| Cache invalidation | project events only |
| Failure modes | duplicate name in same tenant, legacy path media reference, filesystem write failure |
| Tests | same-name cross tenant, legacy path rejection, tenant directory path |

### 8. Asset Import And Manual Sync

| Field | Design |
|-------|--------|
| Entry | `/api/v1/assets`, `/api/v1/assets/import`, `/api/v1/assets/{binding_id}/sync` |
| Authority source | user library ownership; tenant membership for tenant libraries |
| Writes | `assets`, `asset_library_bindings`, file links |
| Permission check | source read, target `member+`, sync confirmation |
| Cache invalidation | none |
| Failure modes | source no longer readable, parent deleted, overwrite without confirmation |
| Tests | personal-to-tenant import, tenant-to-tenant import, source revoke, sync overwrite |

### 9. Tenant Provider/Config/Agent Settings

| Field | Design |
|-------|--------|
| Entry | existing config/provider/custom-provider/agent routes |
| Authority source | current tenant membership |
| Writes | tenant-scoped config, credentials, custom providers, agent credentials |
| Permission check | `admin` for tenant management settings where required; `member+` for generation provider use if needed |
| Cache invalidation | provider/config resolver caches if introduced |
| Failure modes | reading personal config from team tenant, stale bootstrap timestamp, API key duplicate name |
| Tests | tenant A/B config isolation, API key tenant uniqueness, bootstrap completeness |

### 10. Generation Queue And Worker

| Field | Design |
|-------|--------|
| Entry | `/api/v1/generate*`, reference video routes, agent SDK enqueue tools |
| Authority source | current tenant membership at enqueue time |
| Writes | `tasks`, `task_events`, `files`, `project.json`, usage/cost |
| Permission check | `member+` at enqueue; worker trusts persisted task tenant context |
| Cache invalidation | task events/project events |
| Failure modes | role revoked after enqueue, worker missing tenant context, cross-tenant dedupe collision |
| Tests | enqueue permission, revoked-after-enqueue continues, tenant dedupe, worker writeback |

### 11. Frontend Permission UX

| Field | Design |
|-------|--------|
| Entry | login callback, auth store init, tenant listbox, API error interceptor |
| Authority source | backend token/tenant list; cached role only for display |
| Writes | browser token store and UI state |
| Permission check | backend final authority |
| Cache invalidation | token refresh on stale role or access revoked |
| Failure modes | stale role shows wrong button, revoked tenant token loops, signed URL expires |
| Tests | listbox switch, stale role refresh, revoked fallback, view-only UI |

## Residual Risks Before Product Release

- CaMeL OAuth login and bootstrap create flow are live-verified against the local completed CaMeL stack, but conflict/repair/wrong-client/missing-scope external contract cases are still not fully smoke-tested.
- Live MinIO signed URL success, tamper denial, and cross-tenant denial are verified. Direct bucket URL denial and TTL expiry are covered by lower-level tests or risk-tracked, not time-waited in the final live smoke.
- Commercial project media paths now use file IDs in the tested flows. Non-media legacy path consumers and grid split outputs remain tracked release risks.
- Grid split cell outputs still write legacy storyboard paths and need a follow-up migration with GridManager, version restore, and frontend consumers.
- Older provider/custom-provider/credential API unit tests still use single-tenant fixtures without tenant principal/session context. Story7 tenant-aware tests pass and are used by the scenario runner, but these legacy unit fixtures should be migrated before broad full-suite CI is treated as authoritative.
- Browser click-through now verifies login callback and tenant switching. View-only deep UI, asset sync confirmation, and signed media preview are still covered by unit/API tests rather than full browser click-through.
