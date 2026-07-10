# Backend Sprint Progress: Iris

**Engineer:** Iris
**Primary Stories:** Story 7 - Tenant-Scoped Provider Config, Credentials, Agent Config, API Keys; Story 8 - Asset Libraries, Snapshot Import, Manual Sync
**Story Branches:** story/tenant-commercialization/tenant-config; story/tenant-commercialization/asset-libraries
**Story Worktrees:** ../ArcReel-worktrees/tenant-commercialization/tenant-config; ../ArcReel-worktrees/tenant-commercialization/asset-libraries
**File Ownership:** `lib/config/*`, credential/custom-provider repositories, config/provider routers, asset repositories/routes/specs

## Acceptance Criteria

- [x] Provider config, credentials, custom providers, agent config, and API keys are tenant-scoped.
- [x] Tenant bootstrap completeness is based on tenant config/provider state, not user timestamp alone.
- Asset libraries support tenant and personal scopes.
- Asset bindings support snapshot import with `parent_id` and manual sync.
- Cross-library import requires readable source and `member+` target permission.

## Subtasks

- [x] Tenant-scope provider/config/credential/API key storage.
  - Commit: 571724b
- [x] Replace user-level bootstrap timestamp dependency.
  - Commit: 571724b
- [ ] Implement asset library bindings, snapshots, and manual sync.
  - Commit: pending
- [x] Add config isolation tests.
  - Commit: 571724b
- [ ] Add asset import/sync tests.
  - Commit: pending

**Story 7 Ready for QA:** yes
**Story 8 Ready for QA:** no

## Story 7 Verification

- `pytest tests/test_tenant_config_isolation.py -q`: 8 passed.
- `ruff check` on modified Story 7 files: passed.
- `ruff format --check` on modified Story 7 files: passed.
- `basedpyright` on modified Story 7 files: 0 errors, 0 warnings, 0 notes.

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
| 2026-07-10 | Asset bindings | Depends on Story 2 tenant schema and Story 5 file links. | planned |
