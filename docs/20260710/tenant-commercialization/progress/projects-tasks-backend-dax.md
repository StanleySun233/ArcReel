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

- [ ] Add tenant project registry and project path scoping.
  - Commit: pending
- [ ] Convert project media references to file IDs.
  - Commit: pending
- [x] Add tenant-aware generation enqueue and worker writeback.
  - Commit: b8393b9 (queue/task tenant snapshot + tenant-scoped repository queries)
  - Commit: adaa992 (generation enqueue/list/detail/SSE/cancel tenant permission scope + worker task tenant context)
  - Commit: 9842503 (tenant FileService output records and usage attribution for generation media)
- [ ] Finish file-id-only project media migration.
  - Current status: generation outputs now write FileService records and companion `*_file_id` fields while preserving legacy path fields.
  - Remaining: migrate downstream consumers and project schema to read file IDs as the primary media reference; grid split cell outputs still write legacy storyboard paths only.
- [ ] Add project and task tenant isolation tests.
  - Commit: pending

**Ready for QA:** no

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
| 2026-07-10 | Project file IDs | Depends on Story 5 file service semantics. | planned |
| 2026-07-10 | Generation FileService outputs | Compatibility slice done; full file-id-only project JSON requires coordinated consumer migration. | open |
