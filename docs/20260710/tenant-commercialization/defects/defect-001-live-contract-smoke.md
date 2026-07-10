# Defect 001: Live CaMeL And MinIO Smoke Evidence Missing

**Reported by:** Quinn
**Date:** 2026-07-10
**Related story:** Story 10 - Cross-Story QA, Security Review, Product Acceptance
**Related subtask:** Live backend and release smoke
**Story branch:** story/tenant-commercialization/tenant-commercialization-qa
**Story worktree:** ../ArcReel-worktrees/tenant-commercialization/tenant-commercialization-qa
**Severity:** major

## Description

Backend scenario runner covers ArcReel-owned ASGI/API behavior, but final commercial acceptance still lacks live evidence against the completed CaMeL-api service and live MinIO private bucket behavior.

## Reproduction

- Run `scripts/tenant_commercialization_scenarios.py -- -q`; it passes local API/service scenarios.
- No recorded run currently proves CaMeL create/conflict/repair/client/scope/retry against the live CaMeL-api tool.
- No recorded run currently proves private bucket direct-deny and signed URL expiry against live MinIO.

## Affected Files

- `docs/20260710/tenant-commercialization/chain-audit.md`: records this as an open acceptance gap.
- `docs/20260710/tenant-commercialization/scenario-test-matrix.md`: SMOKE-01..SMOKE-04 remain live/manual pending.

## Resolution

- [ ] Start local PostgreSQL, Redis, MinIO, ArcReel, and the completed CaMeL-api tool.
- [ ] Run live CaMeL provider bootstrap contract smoke.
- [ ] Run live MinIO private bucket and signed URL expiry smoke.
