# Backend Sprint Progress: Cyra

**Engineer:** Cyra
**Story:** Story 5 - FileService, MinIO, Private Files, Signed URLs
**Story Branch:** story/tenant-commercialization/minio-files
**Story Worktree:** ../ArcReel-worktrees/tenant-commercialization/minio-files
**File Ownership:** `lib/storage/*`, `lib/files/*`, `lib/db/repositories/file_repo.py`, `server/routers/files.py`, `server/routers/shot_uploads.py`

## Acceptance Criteria

- Every file is represented by a global `files` row.
- Object keys are UUID-style names with original name stored as alias.
- MinIO bucket is private and frontend access uses short signed URLs.
- Backend services access files by service code, not frontend signed URL.
- Media outputs migrate to MinIO while first-version local project saving remains allowed.

## Subtasks

- [x] Add FileService and MinIO storage adapter.
  - Commit: 30ff915, 2a06c27
- [x] Add `files` repository and signed URL endpoints.
  - Commit: 2a06c27, 672ceac
- [x] Convert upload/media output routes to file IDs.
  - Commit: 2b3309e
- [x] Add private bucket, signed URL, and rollback tests.
  - Commit: 2b3309e

**Verification**

- `python -m pytest tests/test_minio_storage.py tests/test_file_service.py tests/test_files_api_minio.py tests/test_shot_uploads_minio.py -q` — 9 passed
- `python -m ruff check lib/storage/__init__.py lib/storage/minio.py lib/files/__init__.py lib/files/service.py lib/db/repositories/file_repo.py server/routers/files.py server/routers/shot_uploads.py tests/test_minio_storage.py tests/test_file_service.py tests/test_files_api_minio.py tests/test_shot_uploads_minio.py` — passed
- `python -m ruff format lib/storage/__init__.py lib/storage/minio.py lib/files/__init__.py lib/files/service.py lib/db/repositories/file_repo.py server/routers/files.py server/routers/shot_uploads.py tests/test_minio_storage.py tests/test_file_service.py tests/test_files_api_minio.py tests/test_shot_uploads_minio.py` — unchanged
- `basedpyright lib/storage/minio.py lib/files/service.py lib/db/repositories/file_repo.py server/routers/files.py server/routers/shot_uploads.py tests/test_minio_storage.py tests/test_file_service.py tests/test_files_api_minio.py tests/test_shot_uploads_minio.py` — blocked by missing configured `.venv`; output reported 0 errors before exiting with environment error

**Ready for QA:** yes

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
| 2026-07-10 | MinIO release | Product/legal release gate for MinIO commercial use remains outside code implementation. | tracked |
