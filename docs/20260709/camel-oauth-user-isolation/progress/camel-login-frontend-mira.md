# Frontend Sprint Progress: Mira

**Engineer:** Mira
**Story:** Story 1 - CaMeL OAuth Login And User Identity
**Story Branch:** story/camel-oauth-user-isolation/camel-auth
**Story Worktree:** ../ArcReel-worktrees/camel-oauth-user-isolation/camel-auth
**File Ownership:** frontend/src/pages/LoginPage.tsx, frontend/src/stores/auth-store.ts, frontend/src/router.tsx, frontend/src/i18n/*/auth.ts

## Acceptance Criteria

- `/login` shows only the CaMeL login button in CaMeL auth mode.
- `/login/callback` consumes the ArcReel JWT from the URL fragment and redirects to the safe return path.
- Local username/password inputs and account mutation entry points are hidden in CaMeL auth mode.
- Existing Bearer-token API behavior remains unchanged after login.

## Subtasks

- [ ] Add auth status mode handling to the auth store.
  - Commit: pending
- [ ] Replace the local login form with CaMeL login in CaMeL mode.
  - Commit: pending
- [ ] Add frontend callback token consumption.
  - Commit: pending
- [ ] Update auth translations.
  - Commit: pending
**Ready for QA:** no

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
