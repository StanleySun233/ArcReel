# Chain Audit: Tenant Commercialization

**Date:** 20260710
**Status:** implementation-audited

This audit checks whether every critical chain has an entry path, authority source, data write path, permission check, failure mode, cache invalidation path, and test owner.

## Audit Summary

| Chain | Coverage | Blocking Gap | Owning Story |
|-------|----------|--------------|--------------|
| CaMeL login to personal tenant token | automated backend | live CaMeL-api smoke still external | Story 3 |
| CaMeL provider/API key bootstrap | automated local + external planned | live CaMeL-api create/conflict/repair smoke still required | Story 0 / Story 7 |
| Tenant switch | automated backend/frontend | none | Story 3 / Story 4 |
| Member CRUD and role matrix | automated backend | none | Story 3 |
| Redis permission cache | automated backend + smoke | none | Story 3 |
| PostgreSQL RLS context | automated backend | none for request path; local dev superuser bypass noted in Story 2 evidence | Story 2 |
| API key auth under tenant | automated backend | none | Story 3 / Story 7 |
| File upload to MinIO | automated backend | live MinIO private bucket smoke still required | Story 5 |
| Signed URL access | automated backend | signed URL TTL expiry remains manual/live-smoke only | Story 5 |
| Project CRUD and file-id JSON | automated backend | full removal of every legacy path consumer remains follow-up | Story 6 / Story 10 |
| Asset library import/sync | automated backend/frontend | none | Story 8 |
| Tenant provider/config/agent settings | automated backend | legacy provider API unit fixtures are not tenant-aware and are excluded from scenario runner | Story 7 / Story 10 |
| Generation enqueue and worker writeback | automated backend | grid split cell file-id migration remains follow-up | Story 9 / Story 10 |
| Usage/cost attribution | automated backend | aggregate report smoke remains Story10/live | Story 9 |
| Frontend permission UX | automated frontend | browser click-through still required | Story 4 / Story 8 / Story 10 |

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

## Open Gaps Before Final Product Acceptance

- Live CaMeL-api contract smoke is still required against the completed external service: create, conflict, repair, wrong client, missing scope, retry behavior.
- Live MinIO smoke is still required for private bucket access and signed URL expiry semantics.
- `project.json` is not yet strictly file-id-only for every downstream consumer. Story6 rejects legacy paths in validators and Story9 writes companion `*_file_id` fields, but Story9 intentionally preserved legacy path fields for compatibility during this sprint.
- Grid split cell outputs still write legacy storyboard paths and need a follow-up migration with GridManager, version restore, and frontend consumers.
- Older provider/custom-provider/credential API unit tests still use single-tenant fixtures without tenant principal/session context. Story7 tenant-aware tests pass and are used by the scenario runner, but these legacy unit fixtures should be migrated before broad full-suite CI is treated as authoritative.
- Browser click-through evidence with `agent-browser` is still required for login callback, tenant switcher, view-only UI, asset sync confirmation, and signed media preview.
