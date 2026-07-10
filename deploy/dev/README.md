# ArcReel Tenant Edition Development Middleware

This directory contains the local PostgreSQL, Redis, and MinIO middleware stack for the tenant edition.

## Middleware

```bash
docker compose -f deploy/dev/docker-compose.middleware.yml up -d
```

Expected local endpoints:

- PostgreSQL: `127.0.0.1:15432`
- Redis: `127.0.0.1:16379`
- MinIO API: `127.0.0.1:19000`
- MinIO Console: `127.0.0.1:19001`

## Tenant-edition environment

Use PostgreSQL. SQLite is not a supported runtime database for this edition.

```bash
export DATABASE_URL=postgresql+asyncpg://arcreel_app:arcreel_app_dev_password@127.0.0.1:15432/arcreel
export ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://arcreel:arcreel_dev_password@127.0.0.1:15432/arcreel
export REDIS_URL=redis://127.0.0.1:16379/0
export ARCREEL_FILE_STORAGE_BACKEND=minio
export ARCREEL_MINIO_ENDPOINT=http://127.0.0.1:19000
export ARCREEL_MINIO_PUBLIC_ENDPOINT=http://127.0.0.1:19000
export ARCREEL_MINIO_ACCESS_KEY=arcreelminio
export ARCREEL_MINIO_SECRET_KEY=arcreel_minio_dev_password
export ARCREEL_MINIO_BUCKET=arcreel-files
```

`arcreel` is the local PostgreSQL admin role.
It is used by `ARCREEL_TEST_DATABASE_ADMIN_URL` for test schema setup.
It is also used by `postgres-app-role-init` to create the app role.

Do not use the admin role as the ArcReel runtime `DATABASE_URL`, because PostgreSQL superuser roles bypass RLS.

If an existing `postgres_data` volume was created before `postgres-app-role-init` existed,
run the init service once or recreate the dev volume before switching `DATABASE_URL` to `arcreel_app`.

## Database migration

```bash
uv run alembic upgrade head
```

## PostgreSQL test slice

```bash
DATABASE_URL=postgresql+asyncpg://arcreel_app:arcreel_app_dev_password@127.0.0.1:15432/arcreel \
ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://arcreel:arcreel_dev_password@127.0.0.1:15432/arcreel \
  uv run python -m pytest \
  tests/test_db_engine.py \
  tests/test_pg_runtime_baseline.py \
  tests/agent_session_store/test_store_concurrency.py \
  tests/test_alembic_custom_provider_endpoint.py \
  tests/test_alembic_custom_provider_max_workers.py \
  tests/test_alembic_split_default_image_backend.py \
  tests/test_alembic_supported_durations_backfill.py
```
