# Defect 005: Tenant Switch Did Not Refresh Project List

**Reported by:** Quinn
**Date:** 2026-07-10
**Related story:** Story 4 / Story 10 / Story 12
**Related subtask:** Frontend tenant switcher browser acceptance
**Story branch:** story/tenant-commercialization/tenant-switch-project-refresh
**Story worktree:** ../ArcReel-worktrees/tenant-commercialization/tenant-switch-project-refresh
**Severity:** major
**Status:** closed on integration branch `4ee8d99`

## Description

During latest-head browser acceptance, the user could switch from the personal tenant to a team tenant, but `ProjectsPage` kept showing the personal tenant empty state. Browser network evidence showed `POST /api/v1/auth/tenant-token` succeeded, but no follow-up `GET /api/v1/projects` was sent after the tenant changed.

## Reproduction

- Start ArcReel from integration head with a fresh PostgreSQL acceptance database.
- Log in through CaMeL as `po-j1`.
- Dismiss the CaMeL provider setup modal.
- Open the `Switch space` listbox and select `Persist j1`.
- Observe that the header changes to `Persist j1` but the project list remains empty.
- Confirm by browser network log that only `POST /api/v1/auth/tenant-token` fired after the switch.

## Affected Files

- `frontend/src/components/pages/ProjectsPage.tsx`: project list effect did not depend on the current tenant id.
- `frontend/src/components/pages/ProjectsPage.test.tsx`: no regression covered tenant change refetch behavior.

## Resolution

- [x] Make `ProjectsPage` clear stale projects and refetch when `currentTenant.id` changes.
  - Fixed by: `facc22d`.
- [x] Add a regression test proving project list reloads after current tenant change.
  - Evidence: targeted `ProjectsPage.test.tsx` passed 11 tests.
- [x] Run frontend QA in story and integration worktrees.
  - Evidence: story worktree `pnpm check` passed 107 test files and 926 tests; integration branch `pnpm check` passed 107 test files and 926 tests.
- [x] Rebuild latest acceptance container and rerun browser acceptance.
  - Evidence: integration branch `4ee8d99` rebuilt into `arcreel-acceptance-current:integration`; fresh DB `arcreel_acceptance_20260710231108` passed live API, CaMeL, MinIO, persistence, and browser tenant switch/project refresh checks.
