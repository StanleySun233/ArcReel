# Defect 003: Legacy Provider API Unit Fixtures Are Not Tenant-Aware

**Reported by:** Quinn
**Date:** 2026-07-10
**Related story:** Story 7 / Story 10
**Related subtask:** Provider configuration/API test coverage
**Story branch:** story/tenant-commercialization/tenant-commercialization-qa
**Story worktree:** ../ArcReel-worktrees/tenant-commercialization/tenant-commercialization-qa
**Severity:** minor

## Description

Story7 tenant-aware configuration isolation tests pass and are used by the backend scenario runner. Older single-tenant provider/custom-provider/credential API unit tests still create `CurrentUserInfo` without tenant membership/session context, so they return `TENANT_ACCESS_REQUIRED` under tenant-edition authorization.

## Reproduction

Run:

```bash
DATABASE_URL=postgresql+asyncpg://arcreel_app:arcreel_app_dev_password@127.0.0.1:15432/arcreel ARCREEL_TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://arcreel:arcreel_dev_password@127.0.0.1:15432/arcreel /data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m pytest tests/test_providers_api.py tests/test_custom_providers_api.py tests/test_credential_api.py -q
```

Observed result: legacy fixtures receive `403 TENANT_ACCESS_REQUIRED`.

## Affected Files

- `tests/test_providers_api.py`
- `tests/test_custom_providers_api.py`
- `tests/test_credential_api.py`

## Resolution

- [ ] Update legacy provider API unit fixtures to seed tenant membership or patch `require_tenant_access` without bypassing production behavior.
- [ ] Keep `tests/test_tenant_config_isolation.py` as the tenant-edition source of truth for cross-tenant config isolation.
