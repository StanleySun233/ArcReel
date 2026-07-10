# Defect 004: Story10 Live Acceptance Regressions Found And Fixed

**Reported by:** Quinn
**Date:** 2026-07-10
**Related story:** Story 10 - Cross-Story QA, Security Review, Product Acceptance
**Story branch:** story/tenant-commercialization/tenant-commercialization-qa
**Story worktree:** ../ArcReel-worktrees/tenant-commercialization/tenant-commercialization-qa
**Severity:** major
**Status:** fixed and reverified

## Findings

| Finding | Runtime symptom | Fix | Verification |
|---------|-----------------|-----|--------------|
| Fresh PostgreSQL used the runtime app role for Alembic | Startup failed on a clean DB because `arcreel_app` could not create migration metadata/schema objects | Added `get_migration_database_url()` and changed Alembic to use the admin migration URL while runtime keeps the app role | Fresh DB `arcreel_acceptance_20260710214815` migrated to `8d7e6f5a4b3c`; container `arcreel-acceptance-current-20260710214815` started successfully |
| Runtime app role lacked future table/sequence grants | Runtime app role could fail after fresh migrations | Added Alembic grant migration for schema, existing objects, sequences, and default privileges | Live API smoke passed under `DATABASE_URL=postgresql+asyncpg://arcreel_app:...` |
| `assets.image_file_id` existed in models/API but not in fresh migrations | Fresh DB asset create with file-id media failed | Added `8d7e6f5a4b3c_add_asset_image_file_id.py` | Live asset create with `image_file_id` passed in both smoke scripts |
| Asset binding writes missed PostgreSQL RLS tenant context | Insert into `asset_library_bindings` failed under RLS | Asset router now prepares session `user_id`/`tenant_id` and sets tenant context before repository writes | `deploy/test/arcreel_tenant_role_minio_smoke.py` passed |
| CaMeL bootstrap local writes missed tenant context | Provider/config bootstrap could fail under tenant-scoped writes | Bootstrap service sets tenant context after resolving target tenant | `deploy/test/arcreel_api_smoke.py` passed provider bootstrap for multiple CaMeL users |
| Project file upload/read routes used the global ProjectManager | Tenant project source/media routes could read or write outside tenant project roots | File router now builds a tenant-scoped ProjectManager from backend-validated tenant access | Scenario runner `files_projects_assets` passed with 113 tests |
| Tenant switcher component existed but was not rendered in the projects lobby | Real browser session had tenant state but no visible tenant switch listbox | Projects top bar now renders `TenantSwitcher` | agent-browser verified visible `Switch space` listbox and switching |
| Frontend auth initialization trusted cached tenant list after refresh | Creating a new tenant then reloading still showed only the cached personal tenant | `auth-store.initialize()` now refreshes `/auth/me` and `/auth/tenants` when a token exists | agent-browser verified fresh backend tenant list after reload and UI switch to the new tenant |
| Acceptance Docker runtime failed bwrap sandbox startup without extra container privileges | Fresh rebuilt acceptance container exited with `SANDBOX_BWRAP_BROKEN on Linux` | Run the local acceptance container with `--privileged` for this Docker validation environment | Container `arcreel-acceptance-current-20260710220207` started healthy and reported `Sandbox runtime: enabled=True docker=True` |
| Tenant viewer could still see project and asset write affordances | Browser showed project create/import/new-project/actions and tenant asset create controls for `view` role | Projects and asset library pages now derive write affordances from current tenant role and hide tenant write actions for `view` | `agent-browser` verified view tenant project lobby and tenant asset library; `pnpm check` passed with 925 tests |

## Local Hostname Corner Case

Opening ArcReel on `127.0.0.1:11242` while `CAMEL_OAUTH_REDIRECT_URI` is configured as `http://localhost:11242/...` causes the OAuth state cookie to be scoped to a different host and the callback returns `Missing OAuth state cookie`. The final browser acceptance used `http://localhost:11242`, matching the configured redirect URI.

The production rule is: OAuth callback host must match the user-facing ArcReel origin used to start login, or the deployment must enforce a canonical host before starting OAuth.

## File Size Note

The final viewer-permission fix touched existing large frontend page files (`ProjectsPage.tsx` and `AssetLibraryPage.tsx`). They already exceed the current 400-line coding preference. The acceptance fix was kept minimal because splitting these pages during final QA would expand the change surface beyond the defect. A follow-up refactor should split the page shell, toolbar, and card/list sections before further feature work in those files.
