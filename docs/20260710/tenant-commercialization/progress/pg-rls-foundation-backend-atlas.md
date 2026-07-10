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
  - Commit: 30caa98, ce1efa7
- [x] Convert runtime engine to PostgreSQL-only.
  - Commit: edbb97b
- [x] Convert DB fixtures to PostgreSQL-only.
  - Commit: 265f9b2
- [ ] Add tenant, membership, tenant-owned model columns, migrations, indexes, and RLS policies.
  - Commit: pending
- [ ] Add deny-by-default and cross-tenant RLS tests.
  - Commit: pending
- [x] Convert SQLite-only Alembic tests to PostgreSQL.
  - Commit: 93423e0

## Verification Evidence

```text
docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' | rg 'arcreel-dev-(postgres|redis|minio)'

arcreel-dev-postgres-1 Up 32 minutes (healthy)
arcreel-dev-redis-1 Up 32 minutes (healthy)
arcreel-dev-minio-1 Up 32 minutes (healthy)
```

```text
DATABASE_URL=postgresql+asyncpg://arcreel:arcreel_dev_password@127.0.0.1:15432/arcreel \
  /data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m alembic upgrade head

passed
```

```text
DATABASE_URL=postgresql+asyncpg://arcreel:arcreel_dev_password@127.0.0.1:15432/arcreel \
  /data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m pytest \
  tests/test_db_engine.py \
  tests/test_pg_runtime_baseline.py \
  tests/agent_session_store/test_store_concurrency.py \
  tests/test_auth_api_key.py::TestApiKeyOwnerResolution::test_bearer_api_key_resolves_persisted_owner_user_id \
  tests/test_generation_queue_client.py::TestGenerationQueueClient::test_enqueue_task_only_requires_online_worker \
  tests/test_alembic_custom_provider_endpoint.py \
  tests/test_alembic_custom_provider_max_workers.py \
  tests/test_alembic_split_default_image_backend.py \
  tests/test_alembic_supported_durations_backfill.py -q

23 passed in 6.49s
```

**Ready for QA:** Story 1 yes; Story 2 no

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
| 2026-07-10 | PostgreSQL baseline | Existing canonical fixtures and Alembic tests still included SQLite assumptions. | resolved |
| 2026-07-10 | Runtime engine verification | `ruff` is not available in the recorded conda environment; no dependency install was performed. | tracked |
