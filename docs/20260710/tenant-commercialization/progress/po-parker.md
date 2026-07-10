# Product Owner Sprint Review: Parker

**Date:** 2026-07-10
**Main integration branch:** `integration/tenant-commercialization`
**Reviewed head:** `986cd22`
**Status:** accepted for integration-branch automated acceptance; final live container rebuild remains a release-evidence step

## Accepted Stories

- Story 0 - Preflight CaMeL OAuth Contract And API Key Provisioning Hardening: accepted for local tenant-edition acceptance. Evidence: redirect hardening test passed and `deploy/test/camel_provisioning_contract_smoke.py` passed live missing bearer, missing token-provision scope, wrong client, repeated create conflict, new-key conflict, and repair checks against the completed local CaMeL stack without modifying CaMeL-api.
- Story 1 - Development Middleware And PostgreSQL-Only Runtime Baseline: accepted. Evidence: local PostgreSQL/Redis/MinIO stack and PG-only runtime evidence are recorded; acceptance container uses PostgreSQL app role and migrations.
- Story 2 / 2A - Tenant Schema, RLS, And App Role Hardening: accepted. Evidence: RLS scenario runner and app-role regression evidence passed; runtime app role is non-superuser/non-BYPASSRLS.
- Story 3 - Tenant Auth, Membership API, Redis Permission Cache: accepted. Evidence: scenario runner `auth_roles` passed 30 tests, live API smoke covered default personal tenant, tenant switching, role matrix, stale/denied paths, and API key tenant auth.
- Story 4 - Frontend Tenant Switcher And Permission UX: accepted for tested tenant switch and role UI scope. Evidence: agent-browser verified login, default personal space, listbox tenant switch, view-only project controls hidden; `pnpm check` passed 925 tests.
- Story 5 - FileService, MinIO, Private Files, Signed URLs: accepted for private bucket and backend-signed access. Evidence: live API smoke, focused tenant/MinIO smoke, `arcreel_minio_security_smoke.py`, and restart persistence smoke passed.
- Story 6 - Tenant Project System And File-Id Project JSON: accepted for tenant-scoped project registry, tenant paths, route isolation, and validator rejection of legacy media paths in covered flows.
- Story 7 - Tenant-Scoped Provider Config, Credentials, Agent Config, API Keys: accepted for tenant-aware config behavior. Evidence: tenant config scenario runner passed and live CaMeL bootstrap wrote tenant-scoped provider setup.
- Story 8 - Asset Libraries, Snapshot Import, Manual Sync: accepted for personal/tenant asset libraries, snapshot import, manual sync, and view-only UI. Evidence: scenario runner asset group passed and agent-browser verified signed media preview plus sync confirmation/result.
- Story 9 - Generation Tasks, Worker Tenant Context, File Outputs: accepted for enqueue-time permission, tenant task visibility, worker tenant context, usage attribution, and FileService output records in covered flows.
- Story 10 - Cross-Story QA, Security Review, Product Acceptance: accepted for local CaMeL + MinIO + tenant/browser acceptance evidence.
- Story 11 - Strict File-Id-Only Project Media Closure: accepted for integration-branch automated acceptance. Evidence: integration branch `986cd22` passed Story11 targeted backend regression with 4 tests, scenario runner with 30 + 10 + 113 + 115 tests, frontend `pnpm check` with 107 test files and 925 tests, and scoped ruff check/format.

## Remaining Release Evidence

- The current live acceptance container predates Story11. Final live release evidence must rebuild the acceptance container from `986cd22` or later and rerun the live smoke scripts before claiming live-runtime acceptance for Story11.

## Closed Follow-Up Story

### Story 11 - Strict File-Id-Only Project Media Closure

**User value:** Commercial project media state has one file reference model, so generated image/video/text/audio and grid split outputs cannot drift between legacy paths and `file_id`.

**Acceptance Criteria**

- Generation writeback no longer relies on companion legacy path fields for any commercial media read path.
- Grid split cell outputs store and expose `file_id` references or are explicitly disabled from the first commercial release.
- Validators reject legacy media path fields for all commercial project media surfaces covered by user-facing routes.
- Frontend and backend media consumers read through `file_id` plus signed URL/FileService.
- Regression tests fail if grid split or generation writeback produces a media-only legacy local path without a corresponding authoritative `file_id`.

## Verdict

Tenant + CaMeL authorization login + MinIO private access are locally accepted from Story10 evidence. Strict file-id-only project media semantics are accepted on integration-branch automated evidence at `986cd22`; live-runtime evidence still requires rebuilding the acceptance container from that head.
