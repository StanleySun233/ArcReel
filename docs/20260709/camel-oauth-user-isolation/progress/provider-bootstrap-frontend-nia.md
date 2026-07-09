# Frontend Sprint Progress: Nia

**Engineer:** Nia
**Story:** Story 2 - CaMeL Provider Bootstrap And Key Repair
**Story Branch:** story/camel-oauth-user-isolation/provider-bootstrap
**Story Worktree:** ../ArcReel-worktrees/camel-oauth-user-isolation/provider-bootstrap
**File Ownership:** frontend/src/components/auth/CamelProviderBootstrapModal.tsx, frontend/src/components/pages/SystemConfigPage.tsx, frontend/src/components/pages/settings/CamelAccountSection.tsx, frontend/src/api.ts, frontend/src/i18n/*/dashboard.ts, frontend/src/stores/auth-store.ts

## Acceptance Criteria

- On the first incomplete login, the frontend shows a modal explaining that ArcReel will create four CaMeL API keys named `camel-arcreel-{camel_user_id}-{image,text,video,audio}` and configure ArcReel providers for the current user.
- The modal confirmation calls `POST /api/v1/camel/bootstrap/start-url?mode=create` and navigates to the returned CaMeL authorization URL; it does not call a direct key-creation POST.
- If CaMeL reports existing token-name conflicts, the modal shows conflict names plus CaMeL management links and a retry action.
- If ArcReel returns partial bootstrap failure, the modal shows the generated token deletion links and does not claim setup completed.
- On success, the modal closes and refreshes provider/default configuration state.
- Completed users do not see the modal on later logins.
- The personal settings page shows a CaMeL key repair button that calls `POST /api/v1/camel/bootstrap/start-url?mode=repair` and navigates to the returned CaMeL authorization URL.
- Local login and local account mutation controls remain hidden in CaMeL mode.

## Subtasks

- [x] Add first-login bootstrap modal with provider summary and confirmation action.
  - Commit: f758e49
- [x] Add creating, success, conflict, retry, and partial-failure UI states.
  - Commit: f758e49
- [x] Add personal settings CaMeL repair button and result states.
  - Commit: f758e49
- [x] Refresh provider settings after successful bootstrap without exposing raw API keys.
  - Commit: f758e49

**Ready for QA:** yes

## QA Evidence

- Commit: 7f41629
- Command: `pnpm check`
- Result: frontend typecheck passed, lint passed, and 101 Vitest files / 897 tests passed.

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
