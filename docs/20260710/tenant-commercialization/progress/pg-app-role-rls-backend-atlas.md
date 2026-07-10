# Backend Sprint Progress: Atlas

**Engineer:** Atlas
**Story:** Story 2A - PostgreSQL App Role RLS Hardening
**Story Branch:** story/tenant-commercialization/pg-app-role-rls
**Story Worktree:** ../ArcReel-worktrees/tenant-commercialization/pg-app-role-rls
**File Ownership:** `deploy/dev/docker-compose.middleware.yml`, `deploy/dev/postgres-init-app-role.sh`, `.env.example`, `deploy/.env.example`, `deploy/dev/README.md`, PostgreSQL test helpers and app-role tests

## Acceptance Criteria

- Local middleware creates or updates an `arcreel_app` login role with `NOSUPERUSER` and `NOBYPASSRLS`.
- Default tenant-edition `DATABASE_URL` examples use the app role, not the PostgreSQL admin role.
- PostgreSQL integration tests can use an explicit admin URL for setup while app DB work uses the app role.
- A regression test fails when `DATABASE_URL` points at a role with `SUPERUSER` or `BYPASSRLS`.
- RLS tests pass when `DATABASE_URL` uses the app role.
- Existing development docs explain that existing PostgreSQL volumes need role initialization before switching URLs.

## Subtasks

- [x] Add dev PostgreSQL app-role init script and compose service.
  - Commit: pending
- [x] Update environment examples and development documentation for app/admin DB URLs.
  - Commit: pending
- [x] Update PostgreSQL test helpers to use `ARCREEL_TEST_DATABASE_ADMIN_URL` for setup.
  - Commit: pending
- [x] Add app-role guard test and run Story 2 regression with app `DATABASE_URL`.
  - Commit: pending

## Verification Evidence

```text
docker exec -i -e PGUSER=arcreel -e PGPASSWORD=arcreel_dev_password \
  -e PGDATABASE=arcreel -e ARCREEL_DEV_POSTGRES_APP_USER=arcreel_app \
  -e ARCREEL_DEV_POSTGRES_APP_PASSWORD=arcreel_app_dev_password \
  arcreel-dev-postgres-1 sh -s < deploy/dev/postgres-init-app-role.sh

DO
```

```text
DATABASE_URL=postgresql+asyncpg://arcreel_app:arcreel_app_dev_password@127.0.0.1:15432/arcreel \
ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://arcreel:arcreel_dev_password@127.0.0.1:15432/arcreel \
  /data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m pytest \
  tests/test_db_engine.py \
  tests/test_pg_runtime_baseline.py \
  tests/test_pg_app_role.py \
  tests/test_db_models.py \
  tests/test_auth_api_key.py \
  tests/test_alembic_custom_provider_endpoint.py \
  tests/test_alembic_custom_provider_max_workers.py \
  tests/test_alembic_split_default_image_backend.py \
  tests/test_alembic_supported_durations_backfill.py \
  tests/test_tenant_rls.py \
  tests/test_tenant_context.py -q

52 passed in 8.26s
```

```text
DATABASE_URL=postgresql+asyncpg://arcreel:arcreel_dev_password@127.0.0.1:15432/arcreel \
  /data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m pytest \
  tests/test_pg_app_role.py -q

failed as expected because current_user arcreel has rolsuper=true and rolbypassrls=true
```

```text
sh -n deploy/dev/postgres-init-app-role.sh
docker compose -f deploy/dev/docker-compose.middleware.yml config
/data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m compileall -q \
  deploy/dev/postgres-init-app-role.sh tests/conftest.py tests/alembic_pg.py \
  tests/test_pg_app_role.py tests/test_alembic_split_default_image_backend.py

passed
```

**Ready for QA:** yes

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
| 2026-07-10 | Lint/type verification | `ruff` and `basedpyright` are not available in the recorded conda environment; no dependency install was performed. | tracked |
