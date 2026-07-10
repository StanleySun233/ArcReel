# Backend Sprint Progress: Dax

**Engineer:** Dax
**Primary Stories:** Story 6 - Tenant Project System And File-Id Project JSON; Story 9 - Generation Tasks, Worker Tenant Context, File Outputs
**Story Branches:** story/tenant-commercialization/tenant-projects; story/tenant-commercialization/tenant-generation
**Story Worktrees:** ../ArcReel-worktrees/tenant-commercialization/tenant-projects; ../ArcReel-worktrees/tenant-commercialization/tenant-generation
**File Ownership:** `lib/project_manager.py`, project repositories/routes/services, generation queue/worker/repositories, generation routers/services

## Acceptance Criteria

- Projects are tenant-scoped and same-name projects can exist in different tenants.
- `project.json` stores media as file IDs, not legacy local paths.
- Project read requires `view+`; project write and generation enqueue require `member+`.
- Submitted generation tasks are evaluated by permission at enqueue time.
- Workers use persisted tenant context for task writeback and usage attribution.

## Subtasks

- [x] Add tenant project registry and project path scoping.
  - Commit: 2144fe9, 877306d
- [x] Convert project media references to file IDs.
  - Commit: 65fbbc8
- [x] Add tenant-aware generation enqueue and worker writeback.
  - Commit: b8393b9 (queue/task tenant snapshot + tenant-scoped repository queries)
  - Commit: adaa992 (generation enqueue/list/detail/SSE/cancel tenant permission scope + worker task tenant context)
  - Commit: 9842503 (tenant FileService output records and usage attribution for generation media)
- [ ] Finish file-id-only project media migration.
  - Current status: generation outputs now write FileService records and companion `*_file_id` fields while preserving legacy path fields.
  - Remaining: migrate downstream consumers and project schema to read file IDs as the primary media reference; grid split cell outputs still write legacy storyboard paths only.
- [x] Add project and task tenant isolation tests.
  - Commit: 877306d, 65fbbc8 for project isolation/file-id coverage
  - Commit: b8393b9, adaa992 for task tenant scope coverage
  - Commit: 9842503 for generation output file records and usage attribution coverage

**Ready for QA:** yes

## Verification

- `DATABASE_URL=postgresql+asyncpg://arcreel_app:arcreel_app_dev_password@127.0.0.1:15432/arcreel /data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m pytest tests/test_tenant_project_registry.py tests/test_project_file_id_validation.py tests/test_tenant_project_routes.py tests/test_projects_router.py -q`
  - Result: 74 passed, 1 warning
- `/data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m ruff format ...`
  - Result: 2 files reformatted, 10 files left unchanged
- `/data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m ruff check ...`
  - Result: All checks passed
- `DATABASE_URL=postgresql+asyncpg://arcreel_app:arcreel_app_dev_password@127.0.0.1:15432/arcreel /data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel basedpyright ...`
  - Result: 0 errors, 14 warnings; command returned non-zero because configured `.venv` path is missing
- `DATABASE_URL=postgresql+asyncpg://arcreel_app:arcreel_app_dev_password@127.0.0.1:15432/arcreel ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://arcreel:arcreel_dev_password@127.0.0.1:15432/arcreel /data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m pytest tests/test_generation_tasks_service.py tests/test_generation_tasks_dispatch.py tests/test_generation_queue.py tests/test_task_repo.py tests/test_tasks_router_more.py tests/test_task_cancel_router.py -q`
  - Result: 114 passed, 1 warning
- `/data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel ruff check ... && /data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel ruff format --check ...`
  - Result: All checks passed; 17 files already formatted
- `DATABASE_URL=postgresql+asyncpg://arcreel_app:arcreel_app_dev_password@127.0.0.1:15432/arcreel ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://arcreel:arcreel_dev_password@127.0.0.1:15432/arcreel /data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel basedpyright ...`
  - Result: 0 errors, 37 warnings

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
| 2026-07-10 | Project file IDs | Depends on Story 5 file service semantics. | resolved for project JSON validation |
| 2026-07-10 | Story6 registry slice verification | `python -m pytest tests/test_tenant_project_registry.py` cannot import test conftest because `DATABASE_URL` is unset for tenant-edition PostgreSQL. `basedpyright` reports 0 errors but exits non-zero because configured `.venv` path is missing. | pytest resolved with documented PostgreSQL URL; basedpyright still returns non-zero on missing `.venv` despite 0 errors |
| 2026-07-10 | Generation FileService outputs | Compatibility slice done; full file-id-only project JSON requires coordinated consumer migration. | open for Story10 audit/follow-up defect |
