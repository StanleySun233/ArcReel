# Backend Sprint Progress: Noah

**Engineer:** Noah
**Story:** Story 3 - Tenant Auth, Membership API, Redis Permission Cache
**Story Branch:** story/tenant-commercialization/tenant-auth
**Story Worktree:** ../ArcReel-worktrees/tenant-commercialization/tenant-auth
**File Ownership:** `server/auth.py`, `server/routers/auth.py`, `server/routers/tenants.py`, `server/services/tenant_auth.py`, `server/services/permission_cache.py`

## Acceptance Criteria

- First login creates a personal tenant and admin membership.
- Current request token contains `user_id`, `tenant_id`, and display-only role snapshot.
- Backend checks real membership from PostgreSQL and never trusts frontend `role` or `tenant_id`.
- Membership CRUD follows owner/admin/member/view rules.
- Redis permission cache is invalidated on membership changes.

## Subtasks

- [ ] Implement tenant token issuance and switch endpoint.
  - Commit: pending
- [ ] Implement membership CRUD and owner invariants.
  - Commit: pending
- [ ] Implement Redis permission cache and invalidation.
  - Commit: pending
- [ ] Add auth and role matrix tests.
  - Commit: pending

**Ready for QA:** no

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
| 2026-07-10 | Tenant auth | Depends on Story 2 tenant schema and DB context. | planned |
