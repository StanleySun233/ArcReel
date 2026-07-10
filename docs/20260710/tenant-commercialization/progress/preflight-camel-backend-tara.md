# Backend Sprint Progress: Tara

**Engineer:** Tara
**Story:** Story 0 - Preflight CaMeL OAuth Contract And API Key Provisioning Hardening
**Story Branch:** story/tenant-commercialization/preflight-camel
**Story Worktree:** ../ArcReel-worktrees/tenant-commercialization/preflight-camel
**File Ownership:** `server/services/camel_auth.py`, `tests/test_camel_auth_provider_bootstrap.py`, ArcReel-owned contract smoke files if added

## Acceptance Criteria

- CaMeL-api is treated as a completed external dependency; this sprint does not modify CaMeL-api files, branches, tests, or worktrees.
- ArcReel-owned contract verification covers create, conflict, repair, scope/client validation, and retry behavior against the completed CaMeL-api service when endpoint credentials are available.
- ArcReel dynamic OAuth redirect only accepts `http` or `https` forwarded scheme and fails closed on invalid scheme.
- ArcReel bootstrap tests cover invalid forwarded scheme.
- The sprint audit document findings are either fixed or explicitly carried into later tenant stories.

## Subtasks

- [x] Restrict forwarded scheme in `server/services/camel_auth.py`.
  - Commit: 0a80f9c
- [x] Extend `tests/test_camel_auth_provider_bootstrap.py` for invalid forwarded scheme.
  - Commit: 0a80f9c
- [ ] Add or document ArcReel-owned CaMeL provisioning contract smoke that does not edit CaMeL-api.
  - Commit: pending

**Ready for QA:** no

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
| 2026-07-10 | Contract smoke | Completed CaMeL-api endpoint credentials are required for live contract verification. | pending |
