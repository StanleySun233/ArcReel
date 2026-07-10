# Backend Sprint Progress: Noah

**Engineer:** Noah
**Story:** Story 3 - Tenant Auth, Membership API, Redis Permission Cache
**Story Branch:** story/tenant-commercialization/tenant-auth
**Story Worktree:** ../ArcReel-worktrees/tenant-commercialization/tenant-auth
**File Ownership:** `server/auth.py`, `server/routers/auth.py`, `server/routers/tenants.py`, `server/routers/api_keys.py`, `server/services/tenant_auth.py`, `server/services/permission_cache.py`, `server/services/camel_auth.py`, `lib/db/repositories/api_key_repository.py`

## Acceptance Criteria

- First login creates a personal tenant and admin membership.
- Current request token contains `user_id`, `tenant_id`, and display-only role snapshot.
- Backend checks real membership from PostgreSQL and never trusts frontend `role` or `tenant_id`.
- Membership CRUD follows owner/admin/member/view rules.
- Redis permission cache is invalidated on membership changes.

## Subtasks

- [x] Implement tenant token issuance and switch endpoint.
  - Commit: 941c447
- [x] Implement membership CRUD and owner invariants.
  - Commit: 941c447
- [x] Implement Redis permission cache and invalidation.
  - Commit: 941c447
- [x] Add auth and role matrix tests.
  - Commit: 941c447
- [x] Tenant-scope API key creation, listing, deletion, and bearer auth.
  - Commit: 941c447

**Ready for QA:** yes

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
| 2026-07-10 | Tenant auth | Depends on Story 2 tenant schema and DB context. | resolved |

## Verification

| Date | Command | Result |
|------|---------|--------|
| 2026-07-10 | `python -m pytest tests/test_api_keys_router.py tests/test_auth_api_key.py tests/test_tenant_auth_service.py tests/test_tenant_auth_router.py tests/test_camel_auth_provider_bootstrap.py -q` | `36 passed, 1 warning` |
| 2026-07-10 | `python -m pytest tests/test_tenant_auth_service.py tests/test_tenant_auth_router.py tests/test_camel_auth_provider_bootstrap.py tests/test_auth.py tests/test_auth_router.py tests/test_auth_api_key.py tests/test_tenant_rls.py tests/test_tenant_context.py tests/test_api_keys_router.py -q` | `76 passed, 1 warning` |
| 2026-07-10 | `python -m ruff check ...` and `python -m ruff format --check ...` | passed |
| 2026-07-10 | `basedpyright ...` with worktree `.venv` symlink to the configured conda env | `0 errors, 0 warnings, 0 notes` |
| 2026-07-10 | Redis permission cache set/get/delete smoke against `redis://127.0.0.1:16379/0` | `redis-permission-cache-ok` |
| 2026-07-10 | `python -m compileall ...` | passed |
| 2026-07-10 | `alembic heads` | `f4a2c8d9e012 (head)` |
