# Scenario Test Matrix: Tenant Commercialization

**Date:** 20260710
**Status:** draft

Coverage labels:

- Automated backend: pytest or Go test.
- Automated frontend: Vitest/Playwright.
- Manual: browser or deployed-stack verification with recorded evidence.

## Auth And Tenant Selection

| ID | Scenario | Setup | Expected Result | Coverage | Owner |
|----|----------|-------|-----------------|----------|-------|
| AUTH-01 | First CaMeL login creates personal tenant | New CaMeL user with no ArcReel tenant | User row, personal tenant, admin membership, personal tenant JWT | Automated backend | Story 3 |
| AUTH-02 | Existing user login defaults to personal tenant | User belongs to personal tenant and team tenant | JWT tenant is personal tenant, not last team | Automated backend | Story 3 |
| AUTH-03 | Tenant list returns all memberships | User belongs to three tenants | Response includes only user's tenants and role snapshots | Automated backend | Story 3 |
| AUTH-04 | Tenant switch succeeds | User has membership in target tenant | New JWT has target tenant and UI role snapshot | Automated backend/frontend | Story 3 / Story 4 |
| AUTH-05 | Tenant switch denied | User lacks target membership | 403/404 without token issuance | Automated backend | Story 3 |
| AUTH-06 | Stale role refresh | User token says admin, DB role is view | Write request denied; refresh returns view role | Automated backend/frontend | Story 3 / Story 4 |
| AUTH-07 | Revoked tenant fallback | User removed from current tenant | Refresh returns access revoked and personal fallback | Automated backend/frontend | Story 3 / Story 4 |
| AUTH-08 | Invalid OAuth forwarded scheme | Allowed host with invalid `x-forwarded-proto` | OAuth start returns 400 | Automated backend | Story 0 |

## CaMeL Provider/API Key Bootstrap

| ID | Scenario | Setup | Expected Result | Coverage | Owner |
|----|----------|-------|-----------------|----------|-------|
| CAMEL-01 | Provision create success | Valid ArcReel OAuth bearer with scope | Four visible CaMeL tokens, model limits, ArcReel-managed marker | Automated Go | Story 0 |
| CAMEL-02 | Provision create conflict | Same-name non-managed token exists | Conflict response, no new tokens | Automated Go | Story 0 |
| CAMEL-03 | Provision repair managed tokens | Existing ArcReel-managed tokens | Tokens rotated, model limits updated, cache invalidated | Automated Go | Story 0 |
| CAMEL-04 | Provision repair non-managed conflict | Same-name non-managed token exists | Conflict response, token not rotated | Automated Go | Story 0 |
| CAMEL-05 | Provision rejects wrong client | OAuth bearer from other client | Forbidden invalid client | Automated Go | Story 0 |
| CAMEL-06 | Provision rejects missing scope | Bearer lacks `arcreel:token-provision` | Forbidden insufficient scope | Automated Go | Story 0 |
| CAMEL-07 | Provision idempotency retry | Same user/client/idempotency key retried | Deterministic success or explicit already-completed contract | Automated Go | Story 0 |
| CAMEL-08 | ArcReel local partial failure | CaMeL tokens created, local provider write fails | Bootstrap incomplete and deletion links returned | Automated backend | Story 0 / Story 7 |
| CAMEL-09 | Tenant-scoped bootstrap completeness | Tenant providers deleted after previous success | Status detects missing config and offers repair | Automated backend | Story 7 |

## Membership And Roles

| ID | Scenario | Setup | Expected Result | Coverage | Owner |
|----|----------|-------|-----------------|----------|-------|
| ROLE-01 | Owner adds admin | Current user is owner | Admin membership created | Automated backend | Story 3 |
| ROLE-02 | Admin cannot add admin | Current user admin but not owner | 403 | Automated backend | Story 3 |
| ROLE-03 | Admin adds member/view | Current user admin | Membership created | Automated backend | Story 3 |
| ROLE-04 | Member adds view | Current user member | View membership created | Automated backend | Story 3 |
| ROLE-05 | Member cannot add member | Current user member | 403 | Automated backend | Story 3 |
| ROLE-06 | View cannot add anyone | Current user view | 403 | Automated backend | Story 3 |
| ROLE-07 | Owner cannot be removed | Delete owner membership | 409/403 owner invariant | Automated backend | Story 3 |
| ROLE-08 | Owner cannot be downgraded | Patch owner to member/view | 409/403 owner invariant | Automated backend | Story 3 |
| ROLE-09 | Member change invalidates Redis | Role changed from admin to view | Cache invalidated; next request denied | Automated backend | Story 3 |

## PostgreSQL RLS

| ID | Scenario | Setup | Expected Result | Coverage | Owner |
|----|----------|-------|-----------------|----------|-------|
| RLS-01 | Missing tenant context | Query tenant table with no context | Denied or zero rows | Automated backend | Story 2 |
| RLS-02 | Same-tenant read | Context tenant A, row tenant A | Row visible | Automated backend | Story 2 |
| RLS-03 | Cross-tenant read | Context tenant A, row tenant B | Row invisible | Automated backend | Story 2 |
| RLS-04 | Cross-tenant write | Context tenant A, insert tenant B | Write rejected | Automated backend | Story 2 |
| RLS-05 | Worker context | Worker processes tenant B task | Reads/writes only tenant B rows | Automated backend | Story 9 |
| RLS-06 | Membership list exception | User has memberships across tenants | Own memberships visible for tenant list | Automated backend | Story 2 / Story 3 |

## Files And MinIO

| ID | Scenario | Setup | Expected Result | Coverage | Owner |
|----|----------|-------|-----------------|----------|-------|
| FILE-01 | Upload media | Member uploads image | `files` row, MinIO object, file link | Automated backend | Story 5 |
| FILE-02 | Object key format | Upload alias `foo.png` | Object key is uuid-style `.png`, alias preserved | Automated backend | Story 5 |
| FILE-03 | Private bucket | Try unauthenticated MinIO URL | Access denied | Automated/manual | Story 5 |
| FILE-04 | Signed URL allowed | User can access linked project/asset | Short signed URL returned | Automated backend | Story 5 |
| FILE-05 | Signed URL denied | User lacks resource access | 403 | Automated backend | Story 5 |
| FILE-06 | Signed URL expires | Use URL after TTL | Object access denied | Manual or integration | Story 5 |
| FILE-07 | DB failure after object write | Simulated DB exception | Orphan handled or recorded for cleanup | Automated backend | Story 5 |
| FILE-08 | GC candidate | Remove last file link | File becomes GC candidate, object not deleted inline | Automated backend | Story 5 |

## Projects

| ID | Scenario | Setup | Expected Result | Coverage | Owner |
|----|----------|-------|-----------------|----------|-------|
| PROJ-01 | Create project in tenant | Member in tenant A | Registry row and tenant path created | Automated backend | Story 6 |
| PROJ-02 | Same name across tenants | Tenant A and B create `demo` | Both succeed and isolate project JSON | Automated backend | Story 6 |
| PROJ-03 | Duplicate name same tenant | Tenant A creates `demo` twice | Second request rejected | Automated backend | Story 6 |
| PROJ-04 | View reads project | View member reads project | Read succeeds | Automated backend | Story 6 |
| PROJ-05 | View cannot edit project | View member PATCH | 403 | Automated backend/frontend | Story 6 / Story 4 |
| PROJ-06 | Legacy media path rejected | `project.json` contains local path media | Validation rejects | Automated backend | Story 6 |
| PROJ-07 | File-id media accepted | `project.json` contains file_id references | Validation succeeds | Automated backend | Story 6 |
| PROJ-08 | Project archive | Tenant project with file_id media | Archive resolves files through FileService | Automated backend | Story 6 |

## Asset Libraries

| ID | Scenario | Setup | Expected Result | Coverage | Owner |
|----|----------|-------|-----------------|----------|-------|
| ASSET-01 | Create personal asset | Active user | User library binding created | Automated backend/frontend | Story 8 |
| ASSET-02 | Create tenant asset | Tenant member | Tenant binding created | Automated backend/frontend | Story 8 |
| ASSET-03 | View cannot create tenant asset | Tenant view user | 403 and hidden UI action | Automated backend/frontend | Story 8 |
| ASSET-04 | Import personal to tenant | User has personal asset, member in tenant | New asset snapshot and parent binding | Automated backend | Story 8 |
| ASSET-05 | Import tenant to tenant | User can read source and write target | Snapshot created in target | Automated backend | Story 8 |
| ASSET-06 | Import without source read | Source membership removed | 403 | Automated backend | Story 8 |
| ASSET-07 | Manual sync confirmed | Target has parent and confirm true | Target asset overwritten from source | Automated backend/frontend | Story 8 |
| ASSET-08 | Manual sync without confirm | Target edited locally | 400/409 confirmation required | Automated backend/frontend | Story 8 |
| ASSET-09 | Sync source unavailable | Parent binding deleted or inaccessible | Clear error, target unchanged | Automated backend | Story 8 |

## Provider Configuration And API Keys

| ID | Scenario | Setup | Expected Result | Coverage | Owner |
|----|----------|-------|-----------------|----------|-------|
| CFG-01 | Tenant A provider config | Set default in tenant A | Tenant B sees independent default | Automated backend | Story 7 |
| CFG-02 | Provider credential active per tenant | Active key in tenant A and B | Active uniqueness isolated | Automated backend | Story 7 |
| CFG-03 | Custom provider per tenant | Same display name in two tenants | Both allowed | Automated backend | Story 7 |
| CFG-04 | Agent credential per tenant | Set agent credential in tenant A | Tenant B cannot read it | Automated backend | Story 7 |
| CFG-05 | API key name per tenant | Same key name in two tenants | Both allowed | Automated backend | Story 7 |
| CFG-06 | API key owner removed | API key owner removed from tenant | API key auth fails | Automated backend | Story 3 / Story 7 |
| CFG-07 | API key cannot manage keys | API-key-auth request to key CRUD | 403 | Automated backend | Story 3 |

## Generation, Tasks, Usage

| ID | Scenario | Setup | Expected Result | Coverage | Owner |
|----|----------|-------|-----------------|----------|-------|
| GEN-01 | Member enqueues generation | Member in tenant | Task created with tenant_id/user_id | Automated backend | Story 9 |
| GEN-02 | View cannot enqueue | View in tenant | 403 | Automated backend/frontend | Story 9 / Story 4 |
| GEN-03 | Role revoked after enqueue | Task queued, user removed | Worker continues and completes | Automated backend | Story 9 |
| GEN-04 | Worker file output | Generation produces image/video/text | FileService stores output and project JSON gets file_id | Automated backend | Story 9 |
| GEN-05 | Cross-tenant task list | Tenant A and B tasks | Each tenant sees only own tasks | Automated backend | Story 9 |
| GEN-06 | SSE tenant isolation | User subscribes task/project events | Only current tenant events delivered | Automated backend | Story 9 |
| GEN-07 | Dedupe by tenant | Same project/resource in two tenants | No cross-tenant dedupe collision | Automated backend | Story 9 |
| GEN-08 | Usage/cost by tenant | Task completes in tenant A | Usage/cost row has tenant A only | Automated backend | Story 9 |

## Frontend End-To-End

| ID | Scenario | Setup | Expected Result | Coverage | Owner |
|----|----------|-------|-----------------|----------|-------|
| UI-01 | Login callback stores tenant token | OAuth callback hash contains token | Store has token and personal tenant | Automated frontend | Story 4 |
| UI-02 | Tenant listbox switch | User has two tenants | Token replaced, stores refreshed, project list reloads | Automated frontend | Story 4 |
| UI-03 | View-only UI | Current role view | Write/generate/member controls hidden | Automated frontend | Story 4 |
| UI-04 | Member UI | Current role member | Project/generate/asset write visible, admin hidden | Automated frontend | Story 4 |
| UI-05 | Owner UI | Current user owner | Add admin visible | Automated frontend | Story 4 |
| UI-06 | Stale role interceptor | API returns `TENANT_ROLE_STALE` | Refresh current token and retry/settle | Automated frontend | Story 4 |
| UI-07 | Access revoked interceptor | API returns `TENANT_ACCESS_REVOKED` | Switch to personal space or tenant selector | Automated frontend | Story 4 |
| UI-08 | File preview signed URL | Component receives file_id | Requests signed URL and renders media | Automated frontend | Story 5 / Story 8 |

## Release Smoke

| ID | Scenario | Setup | Expected Result | Coverage | Owner |
|----|----------|-------|-----------------|----------|-------|
| SMOKE-01 | Empty stack bootstrap | Fresh PG/Redis/MinIO | Alembic upgrade, app starts, health ok | Manual + automated scripts | Story 10 |
| SMOKE-02 | Full happy path | New user logs in, creates tenant, uploads asset, creates project, generates media | All outputs file_id, tenant isolation preserved | Manual browser evidence | Story 10 |
| SMOKE-03 | Cross-tenant attack path | User tries known IDs from other tenant | All project/file/asset/task endpoints deny | Automated backend + manual spot check | Story 10 |
| SMOKE-04 | Restart persistence | Restart app with existing PG/Redis/MinIO volumes | Tenant, project registry, files, assets, tasks remain usable | Manual | Story 10 |
