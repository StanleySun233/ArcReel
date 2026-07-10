# Defect 001: Live CaMeL And MinIO Smoke Evidence Missing

**Reported by:** Quinn
**Date:** 2026-07-10
**Related story:** Story 10 - Cross-Story QA, Security Review, Product Acceptance
**Related subtask:** Live backend and release smoke
**Story branch:** story/tenant-commercialization/tenant-commercialization-qa
**Story worktree:** ../ArcReel-worktrees/tenant-commercialization/tenant-commercialization-qa
**Severity:** major
**Status:** partially fixed; residual external-contract cases remain tracked

## Description

Backend scenario runner covers ArcReel-owned ASGI/API behavior, but final commercial acceptance still lacks live evidence against the completed CaMeL-api service and live MinIO private bucket behavior.

Story10 later added live local-stack evidence for CaMeL OAuth login, provider bootstrap create flow, MinIO upload, signed URL success, signed URL tamper denial, and cross-tenant signed URL denial. The remaining uncovered cases are the deeper CaMeL external provisioning contract cases and time-based/direct-bucket MinIO checks.

## Reproduction

- Run `scripts/tenant_commercialization_scenarios.py -- -q`; it passes local API/service scenarios.
- Recorded run proves ArcReel CaMeL OAuth login and bootstrap create flow against local completed CaMeL stack.
- Recorded run proves MinIO file upload, signed URL success, tamper denial, and cross-tenant signed URL denial.
- No recorded run currently proves CaMeL conflict/repair/client/scope/retry against the live CaMeL-api tool.
- No recorded run currently proves private bucket direct-deny and signed URL expiry against live MinIO.

## Affected Files

- `docs/20260710/tenant-commercialization/chain-audit.md`: records this as an open acceptance gap.
- `docs/20260710/tenant-commercialization/scenario-test-matrix.md`: SMOKE-01..SMOKE-04 remain live/manual pending.

## Resolution

- [x] Start local PostgreSQL, Redis, MinIO, ArcReel, and the completed CaMeL-api tool.
- [x] Run live CaMeL OAuth login and provider bootstrap create smoke.
- [x] Run live MinIO upload, signed URL success, tamper denial, and cross-tenant denial smoke.
- [ ] Run CaMeL conflict/repair/wrong-client/missing-scope/retry contract smoke.
- [ ] Run MinIO direct private bucket URL denial and signed URL expiry smoke.
