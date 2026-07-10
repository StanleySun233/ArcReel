# Defect 002: Project JSON File-Id-Only Migration Is Not Fully Proven

**Reported by:** Quinn
**Date:** 2026-07-10
**Related story:** Story 6 / Story 9 / Story 10
**Related subtask:** File-id project JSON and generation output writeback
**Story branch:** story/tenant-commercialization/tenant-commercialization-qa
**Story worktree:** ../ArcReel-worktrees/tenant-commercialization/tenant-commercialization-qa
**Severity:** major

## Description

Story6 rejects legacy media paths in validators and Story9 writes FileService records with companion `*_file_id` fields. Story9 intentionally preserved legacy path fields during generation output writeback, and grid split cell outputs still write legacy storyboard paths.

## Reproduction

- Inspect Story9 progress evidence: generation outputs create FileService records and companion file-id fields while preserving old path fields.
- Grid split cell output migration requires coordinated changes to GridManager, version restore, and frontend consumers.

## Affected Files

- `server/services/generation_tasks.py`
- `server/services/reference_video_tasks.py`
- `lib/grid/*`
- project JSON consumers in frontend and service code

## Resolution

- [ ] Decide whether first commercial release permits companion legacy path fields.
- [ ] If not permitted, migrate remaining project JSON consumers to file-id primary reads.
- [ ] Add a failing regression for grid split cell output if legacy storyboard paths remain.
