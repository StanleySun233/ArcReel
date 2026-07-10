# Frontend Sprint Progress: Mira

**Engineer:** Mira
**Story:** Story 4 - Frontend Tenant Switcher And Permission UX
**Story Branch:** story/tenant-commercialization/tenant-switcher-ui
**Story Worktree:** ../ArcReel-worktrees/tenant-commercialization/tenant-switcher-ui
**File Ownership:** `frontend/src/api.ts`, `frontend/src/stores/auth-store.ts`, `frontend/src/components/tenant/*`, `frontend/src/utils/auth.ts`, `frontend/src/i18n/*/auth.ts`

## Acceptance Criteria

- Users enter their personal tenant by default after login.
- A listbox allows explicit tenant switching.
- Cached tenant role is used only for UI display.
- API requests carry only the current tenant access token.
- Stale role or revoked access triggers backend-authoritative refresh behavior.

## Subtasks

- [x] Add tenant list and switch UI.
  - Commit: 36c65c0
- [x] Update auth store token and role snapshot handling.
  - Commit: 4a42e1a
- [ ] Add stale-role and revoked-access UI tests.
  - Commit: pending

**Ready for QA:** no

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
| 2026-07-10 | Tenant switcher | Depends on Story 3 tenant API contract or compatible mock contract. | resolved |
