# Backend Sprint Progress: Atlas

**Engineer:** Atlas
**Primary Stories:** Story 1 - Development Middleware And PostgreSQL-Only Runtime Baseline; Story 2 - Tenant Schema, RLS, And Request DB Context
**Story Branches:** story/tenant-commercialization/pg-runtime-baseline; story/tenant-commercialization/tenant-schema-rls
**Story Worktrees:** ../ArcReel-worktrees/tenant-commercialization/pg-runtime-baseline; ../ArcReel-worktrees/tenant-commercialization/tenant-schema-rls
**File Ownership:** `deploy/dev/docker-compose.middleware.yml`, `.env.example`, `deploy/.env.example`, `lib/db/*`, `alembic/versions/*`, PostgreSQL/RLS tests

## Acceptance Criteria

- Local middleware provides PostgreSQL, Redis, MinIO API, and MinIO Console with a fixed MinIO release tag.
- Runtime and tests are PostgreSQL-only for the tenant edition.
- Tenant and membership schema exists with tenant-scoped constraints.
- Tenant-owned tables enforce PostgreSQL RLS with request/worker DB context.
- Missing tenant context denies tenant-owned table access in integration tests.

## Subtasks

- [x] Finalize middleware and environment documentation.
  - Commit: pending
- [x] Convert runtime engine to PostgreSQL-only.
  - Commit: pending
- [x] Convert DB fixtures to PostgreSQL-only.
  - Commit: pending
- [ ] Add tenant, membership, tenant-owned model columns, migrations, indexes, and RLS policies.
  - Commit: pending
- [ ] Add deny-by-default and cross-tenant RLS tests.
  - Commit: pending
- [x] Convert SQLite-only Alembic tests to PostgreSQL.
  - Commit: pending

**Ready for QA:** no

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
| 2026-07-10 | PostgreSQL baseline | Existing tests still include SQLite assumptions. | planned |
| 2026-07-10 | Runtime engine verification | `ruff` is not available in the recorded conda environment; no dependency install was performed. | active |
