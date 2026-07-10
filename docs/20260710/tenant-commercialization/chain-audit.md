# Chain Audit: Tenant Commercialization

**Date:** 20260710
**Status:** draft

This audit checks whether every critical chain has an entry path, authority source, data write path, permission check, failure mode, cache invalidation path, and test owner.

## Audit Summary

| Chain | Coverage | Blocking Gap | Owning Story |
|-------|----------|--------------|--------------|
| CaMeL login to personal tenant token | covered by design | none | Story 3 |
| CaMeL provider/API key bootstrap | covered by design | external contract smoke required | Story 0 |
| Tenant switch | covered by design | none | Story 3 / Story 4 |
| Member CRUD and role matrix | covered by design | none | Story 3 |
| Redis permission cache | covered by implementation | none | Story 3 |
| PostgreSQL RLS context | covered by design | deny-by-default tests required | Story 2 |
| API key auth under tenant | covered by implementation | provider/config tenant bootstrap remains Story 7 | Story 3 / Story 7 |
| File upload to MinIO | covered by design | object/write rollback behavior must be implemented | Story 5 |
| Signed URL access | covered by design | file link consistency tests required | Story 5 |
| Project CRUD and file-id JSON | covered by design | legacy path rejection tests required | Story 6 |
| Asset library import/sync | covered by design | overwrite confirmation tests required | Story 8 |
| Tenant provider/config/agent settings | covered by design | tenant bootstrap completeness must replace user timestamp | Story 7 |
| Generation enqueue and worker writeback | covered by design | worker DB context tests required | Story 9 |
| Usage/cost attribution | covered by design | tenant aggregation tests required | Story 9 |
| Frontend permission UX | covered by design | stale-role and revoked-access tests required | Story 4 |

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

## Required Follow-Up Before Implementation

- Story 0 must verify the completed CaMeL-api contract from ArcReel without modifying CaMeL-api.
- `scenario-test-matrix.md` must map every chain above to automated or manual coverage.
- No implementation story starts before this audit is reviewed with the sprint backlog.
