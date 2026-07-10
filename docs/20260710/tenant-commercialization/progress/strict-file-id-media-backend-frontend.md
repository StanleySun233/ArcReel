# Story 11 Progress: Strict File-Id-Only Project Media Closure

**Story:** Story 11 - Strict File-Id-Only Project Media Closure
**Story Branch:** story/tenant-commercialization/strict-file-id-media
**Story Worktree:** ../ArcReel-worktrees/tenant-commercialization/strict-file-id-media
**File Ownership:** `server/services/generation_tasks.py`, `server/services/reference_video_tasks.py`, `lib/grid/models.py`, grid/media frontend consumers, Story11 tests

## Acceptance Criteria

- Generation writeback treats file IDs as authoritative for storyboard, video, thumbnail, narration audio, reference video, grid composite, and grid split cell media when FileService records exist.
- Grid records persist `grid_image_file_id` and split cells persist `image_file_id`.
- Frontend grid, shot media, and reference-video previews prefer file IDs and fetch backend signed URLs.
- Legacy path reads remain fallback only.
- Regression tests fail if grid split output lacks authoritative file IDs.

## Subtasks

- [x] Add grid file-id fields to backend and frontend grid models.
  - Commit: c10d646
- [x] Write file IDs into storyboard/video/tts/reference-video generated asset fields when available.
  - Commit: c10d646
- [x] Record grid composite and split cell outputs through FileService and write file IDs into grid/script metadata.
  - Commit: c10d646
- [x] Make frontend media consumers prefer file IDs and backend signed URLs.
  - Commit: c10d646
- [x] Add grid split file-id regression.
  - Commit: c10d646

## Verification

- `python -m ruff check server/services/generation_tasks.py server/services/reference_video_tasks.py lib/grid/models.py tests/test_generation_tasks_service.py tests/test_project_file_id_validation.py`: passed.
- `python -m ruff format --check server/services/generation_tasks.py server/services/reference_video_tasks.py lib/grid/models.py tests/test_generation_tasks_service.py tests/test_project_file_id_validation.py`: passed.
- `python -m pytest tests/test_generation_tasks_service.py::TestGenerationTasks::test_execute_grid_task_records_grid_and_cell_file_ids tests/test_project_file_id_validation.py -q`: 4 passed.
- `pnpm check`: 107 test files passed, 925 tests passed.

**Ready for QA:** yes
