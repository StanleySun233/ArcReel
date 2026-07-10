# QA Sprint Progress: Quinn

**Engineer:** Quinn
**Story:** Story 10 - Cross-Story QA, Security Review, Product Acceptance
**Story Branch:** story/tenant-commercialization/tenant-commercialization-qa
**Story Worktree:** ../ArcReel-worktrees/tenant-commercialization/tenant-commercialization-qa
**File Ownership:** `tests/**` after story-owner slices are merged, `docs/20260710/tenant-commercialization/defects/*`

## Acceptance Criteria

- Every scenario in `scenario-test-matrix.md` has automated or recorded manual evidence.
- Every new feature has at least three scenario tests plus corner cases where applicable.
- Backend API scenario tests cover permission, filesystem, system config, MinIO, Redis, and tenant isolation chains.
- Frontend browser tests cover login, tenant switch, permission UI, file/media display, and asset workflows.
- Product Owner review happens from the main integration branch only after QA passes.

## Subtasks

- [x] Build scenario test harness and map tests to matrix IDs.
  - Evidence: `scripts/tenant_commercialization_scenarios.py -- -q` maps auth, RLS/config, files/projects/assets, and generation/tasks/usage groups to matrix IDs.
- [x] Run backend API scenario tests on a fresh initialized stack.
  - Evidence: fresh DB `arcreel_acceptance_20260710214815`, live `deploy/test/arcreel_api_smoke.py`, live `deploy/test/arcreel_tenant_role_minio_smoke.py`, and scenario runner passed.
- [x] Run frontend browser click tests with agent-browser.
  - Evidence: `agent-browser` verified CaMeL login, default personal space, `Switch space` listbox, backend tenant refresh, team tenant switch, view-only project lobby, view-only tenant asset library, signed media preview through backend file endpoints, and personal asset sync confirmation on `http://localhost:11242`.
- [x] Record defects and verify fixes after full reinitialization.
  - Evidence: `defects/defect-004-story10-live-acceptance-fixes.md` records fresh PG, migration, RLS context, ProjectManager tenant context, and frontend switcher/cache fixes; final fresh stack passed after fixes.

**Ready for QA:** yes

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
| 2026-07-10 | Full-chain QA | Depends on implementation stories merging into `integration/tenant-commercialization`. | cleared for Story10 local branch |
| 2026-07-10 | Full basedpyright | Full-tree basedpyright exits nonzero because of existing unrelated errors and missing `.venv`; Story10 modified smoke scripts are 0 error / 0 warning under scoped basedpyright. | residual risk |

## Final Story10 Evidence

| Area | Evidence |
|------|----------|
| Fresh stack | Container `arcreel-acceptance-current-20260710214815`, DB `arcreel_acceptance_20260710214815`, Alembic head `8d7e6f5a4b3c` |
| Live API smoke | `deploy/test/arcreel_api_smoke.py` passed 23 checks |
| Focused tenant/MinIO smoke | `deploy/test/arcreel_tenant_role_minio_smoke.py` passed 4 checks |
| Scenario runner | 30 + 10 + 113 + 114 tests passed |
| Frontend | `pnpm lint && pnpm check` passed; 107 test files, 923 tests |
| Targeted backend | `tests/test_assets_router.py tests/test_db_engine.py tests/test_files_api_minio.py -q`: 14 passed |
| Static | ruff check/format passed for Story10 changed Python files; scoped basedpyright for smoke scripts: 0 errors, 0 warnings |

## Integration Merge Evidence

| Area | Evidence |
|------|----------|
| Merge | `integration/tenant-commercialization` at merge commit `056e8b7` |
| Fresh stack | Container `arcreel-acceptance-current-20260710220207`, DB `arcreel_acceptance_20260710220207`, Alembic head `8d7e6f5a4b3c` |
| Live API smoke | `deploy/test/arcreel_api_smoke.py` passed 23 checks |
| Focused tenant/MinIO smoke | `deploy/test/arcreel_tenant_role_minio_smoke.py` passed 4 checks |
| Scenario runner | 30 + 10 + 113 + 114 tests passed |
| Frontend | `pnpm lint && pnpm check` passed; 107 test files, 923 tests |
| Targeted backend | `tests/test_assets_router.py tests/test_db_engine.py tests/test_files_api_minio.py -q`: 14 passed |

## Residual Acceptance Extension

| Area | Evidence |
|------|----------|
| Rebuilt runtime | Image `arcreel-acceptance-current:integration`, container `arcreel-acceptance-current-20260710220207` running with `--privileged` for bwrap sandbox support |
| CaMeL contract | `deploy/test/camel_provisioning_contract_smoke.py` passed 6 checks: missing bearer, missing token-provision scope, wrong client, repeated create conflict, new-key conflict, repair |
| MinIO security | `deploy/test/arcreel_minio_security_smoke.py` passed private bucket direct-deny, backend signed read, 300 second TTL, tampered URL denial, expired token denial |
| MinIO persistence | `deploy/test/arcreel_minio_persistence_smoke.py --phase seed`, ArcReel app restart, then `--phase verify` passed |
| Browser deep checks | View tenant cannot see project/asset write actions; signed media loads via backend file endpoints; owner personal asset sync confirmation and result verified |
| Frontend final | `pnpm lint` passed; `pnpm check` passed with 107 test files and 925 tests |
| Smoke script static | `ruff check` and `ruff format --check` passed for the four live acceptance helper scripts |
