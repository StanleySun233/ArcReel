# Backend Sprint Progress: Iris

**Engineer:** Iris
**Primary Stories:** Story 7 - Tenant-Scoped Provider Config, Credentials, Agent Config, API Keys; Story 8 - Asset Libraries, Snapshot Import, Manual Sync
**Story Branches:** story/tenant-commercialization/tenant-config; story/tenant-commercialization/asset-libraries
**Story Worktrees:** ../ArcReel-worktrees/tenant-commercialization/tenant-config; ../ArcReel-worktrees/tenant-commercialization/asset-libraries
**File Ownership:** `lib/config/*`, credential/custom-provider repositories, config/provider routers, asset repositories/routes/specs

## Acceptance Criteria

- [x] Provider config, credentials, custom providers, agent config, and API keys are tenant-scoped.
- [x] Tenant bootstrap completeness is based on tenant config/provider state, not user timestamp alone.
- [x] Asset libraries support tenant and personal scopes.
- [x] Asset bindings support snapshot import with `parent_id` and manual sync.
- [x] Cross-library import requires readable source and `member+` target permission.
- [x] Project-level asset routes consume `*_sheet_file_id` media fields.
- [x] Frontend exposes tenant/personal library views, sync confirmation, and permission state.

## Subtasks

- [x] Tenant-scope provider/config/credential/API key storage.
  - Commit: 571724b
- [x] Replace user-level bootstrap timestamp dependency.
  - Commit: 571724b
- [x] Implement asset library bindings, snapshots, and manual sync.
  - Commit: a69e5b4
- [x] Add config isolation tests.
  - Commit: 571724b
- [x] Add asset import/sync tests.
  - Commit: a69e5b4

**Story 7 Ready for QA:** yes
**Story 8 Ready for QA:** yes

## Story 8 Verification

- `pytest tests/test_assets_router.py tests/test_asset_repo.py tests/test_asset_model.py -q`: 12 passed.
- `pytest tests/test_asset_router_factory.py tests/test_asset_types_product.py -q`: 18 passed.
- `pytest tests/test_assets_router.py tests/test_asset_repo.py tests/test_asset_model.py tests/test_asset_router_factory.py tests/test_asset_types_product.py -q`: 30 passed.
- `ruff check` on modified Story 8 backend files: passed.
- `ruff format --check` on modified Story 8 backend files: passed.
- `basedpyright` on modified Story 8 backend files: reported 0 errors, 0 warnings, 0 notes; command exited 3 because the story worktree has no `.venv` directory referenced by pyright config.
- `pnpm check`: 107 test files passed, 922 tests passed, using a temporary symlink to the main worktree's existing `frontend/node_modules` because this story worktree has no installed `node_modules`.

## Story 8 Commits

- Backend bindings/import/sync: a69e5b4
- Project-level file-id fields and frontend library UI: b808bb1

## Story 7 Verification

- `pytest tests/test_tenant_config_isolation.py -q`: 8 passed.
- `ruff check` on modified Story 7 files: passed.
- `ruff format --check` on modified Story 7 files: passed.
- `basedpyright` on modified Story 7 files: 0 errors, 0 warnings, 0 notes.

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
| 2026-07-10 | Asset bindings | Depends on Story 2 tenant schema and Story 5 file links. | cleared |
