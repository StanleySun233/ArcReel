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
  - Commit: 2144fe9
- [ ] Convert project media references to file IDs.
  - Commit: pending
- [ ] Add tenant-aware generation enqueue and worker writeback.
  - Commit: pending
- [ ] Add project and task tenant isolation tests.
  - Commit: pending

**Ready for QA:** no

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
| 2026-07-10 | Project file IDs | Depends on Story 5 file service semantics. | planned |
| 2026-07-10 | Story6 registry slice verification | `python -m pytest tests/test_tenant_project_registry.py` cannot import test conftest because `DATABASE_URL` is unset for tenant-edition PostgreSQL. `basedpyright` reports 0 errors but exits non-zero because configured `.venv` path is missing. | blocked on local test environment |
