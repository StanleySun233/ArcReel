# Defect 002: Project JSON File-Id-Only Migration Is Not Fully Proven

**Reported by:** Quinn
**Date:** 2026-07-10
**Related story:** Story 6 / Story 9 / Story 10
**Related subtask:** File-id project JSON and generation output writeback
**Story branch:** story/tenant-commercialization/tenant-commercialization-qa
**Story worktree:** ../ArcReel-worktrees/tenant-commercialization/tenant-commercialization-qa
**Severity:** major
**Status:** fixed in Story 11; pending integration merge and final acceptance rerun

## Description

Story6 rejects legacy media paths in validators and Story9 writes FileService records with companion `*_file_id` fields. Story9 initially preserved legacy path fields during generation output writeback, and grid split cell outputs still wrote legacy storyboard paths.

Story11 changes the commercial write/read path so generated media main fields prefer `file_id` when FileService produces one. Grid composite records now persist `grid_image_file_id`; grid split cells persist `FrameCell.image_file_id` and write `storyboard_image` plus `storyboard_image_file_id` as file IDs. Frontend media consumers prefer file IDs and fetch backend signed URLs.

## Reproduction

- Inspect Story9 progress evidence: generation outputs create FileService records and companion file-id fields while preserving old path fields.
- Run Story11 regression: `tests/test_generation_tasks_service.py::TestGenerationTasks::test_execute_grid_task_records_grid_and_cell_file_ids`.
- Run frontend `pnpm check` to verify grid, storyboard, video, and reference-video consumers accept file-id media references.

## Affected Files

- `server/services/generation_tasks.py`
- `server/services/reference_video_tasks.py`
- `lib/grid/*`
- project JSON consumers in frontend and service code

## Resolution

- [x] Decide whether first commercial release permits companion legacy path fields.
  - Decision: commercial runtime treats file IDs as authoritative; legacy paths may remain only as fallback for non-tenant or not-yet-migrated data.
- [x] If not permitted, migrate remaining project JSON consumers to file-id primary reads.
  - Evidence: `MediaCard`, `GridPreviewPanel`, `ShotDetail`, and reference video preview prefer file IDs and fetch backend signed URLs.
- [x] Add a failing regression for grid split cell output if legacy storyboard paths remain.
  - Evidence: `test_execute_grid_task_records_grid_and_cell_file_ids` asserts grid composite and split cells persist file IDs and write file IDs into scene generated assets.
- [x] Run targeted checks.
  - Evidence: Python ruff check/format passed; Story11 targeted pytest passed; frontend `pnpm check` passed with 107 test files and 925 tests.
