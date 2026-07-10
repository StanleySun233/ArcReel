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
- [ ] Add `files` repository and signed URL endpoints.
  - Commit: pending
- [ ] Convert upload/media output routes to file IDs.
  - Commit: pending
- [ ] Add private bucket, signed URL, and rollback tests.
  - Commit: pending

**Ready for QA:** no

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
| 2026-07-10 | MinIO release | Product/legal release gate for MinIO commercial use remains outside code implementation. | tracked |
