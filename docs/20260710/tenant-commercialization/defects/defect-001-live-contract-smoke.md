# Defect 001: Live CaMeL And MinIO Smoke Evidence Missing

**Reported by:** Quinn
**Date:** 2026-07-10
**Related story:** Story 10 - Cross-Story QA, Security Review, Product Acceptance
**Related subtask:** Live backend and release smoke
**Story branch:** story/tenant-commercialization/tenant-commercialization-qa
**Story worktree:** ../ArcReel-worktrees/tenant-commercialization/tenant-commercialization-qa
**Severity:** major
**Status:** fixed and reverified

## Description

Backend scenario runner covers ArcReel-owned ASGI/API behavior, but final commercial acceptance originally lacked live evidence against the completed CaMeL-api service and live MinIO private bucket behavior.

Story10 later added live local-stack evidence for CaMeL OAuth login, provider bootstrap create flow, CaMeL provisioning contract denial/conflict/repair behavior, MinIO upload, signed URL success, direct private bucket denial, signed URL tamper/expiry denial, cross-tenant signed URL denial, and restart persistence.

## Reproduction

- Run `scripts/tenant_commercialization_scenarios.py -- -q`; it passes local API/service scenarios.
- Recorded run proves ArcReel CaMeL OAuth login and bootstrap create flow against local completed CaMeL stack.
- Recorded run proves MinIO file upload, signed URL success, tamper denial, cross-tenant signed URL denial, direct private bucket denial, expired signed token denial, and persistence after ArcReel app restart.
- Recorded run proves CaMeL missing bearer, missing token-provision scope, wrong client, repeated create conflict, new-key conflict, and repair behavior against the completed local CaMeL stack.

## Affected Files

- `docs/20260710/tenant-commercialization/chain-audit.md`: records this as an open acceptance gap.
- `docs/20260710/tenant-commercialization/scenario-test-matrix.md`: updated with live/manual acceptance evidence for SMOKE-01..SMOKE-04.

## Resolution

- [x] Start local PostgreSQL, Redis, MinIO, ArcReel, and the completed CaMeL-api tool.
- [x] Run live CaMeL OAuth login and provider bootstrap create smoke.
- [x] Run live MinIO upload, signed URL success, tamper denial, and cross-tenant denial smoke.
- [x] Run CaMeL conflict/repair/wrong-client/missing-scope/retry contract smoke.
  - Evidence: `deploy/test/camel_provisioning_contract_smoke.py` passed 6 checks against local completed CaMeL.
- [x] Run MinIO direct private bucket URL denial and signed URL expiry smoke.
  - Evidence: `deploy/test/arcreel_minio_security_smoke.py` passed direct private bucket, 300s signed URL, tampered token, and expired token checks.
- [x] Run restart persistence smoke.
  - Evidence: `deploy/test/arcreel_minio_persistence_smoke.py --phase seed`, `docker restart arcreel-acceptance-current-20260710220207`, then `--phase verify` passed.
