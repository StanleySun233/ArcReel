# Preflight Audit: CaMeL OAuth And Provider Bootstrap

**Date:** 20260710
**Scope:** Audit the prerequisite ArcReel-side capabilities for the tenant commercial edition: CaMeL OAuth login, ArcReel user upsert, ArcReel API key owner resolution, and CaMeL provider/API key bootstrap integration.

## Verdict

ArcReel-side CaMeL OAuth login, provider bootstrap, repair, and API key owner resolution are usable as prerequisites for the tenant design.

CaMeL-api is now treated as a completed external dependency. This sprint must not modify CaMeL-api. ArcReel work is limited to contract verification, ArcReel-side hardening, and tenant-edition integration behavior. If a running CaMeL-api instance violates the expected ArcReel contract, the result is an external dependency defect, not an ArcReel-side code change in this sprint.

## Verified Evidence

ArcReel-side baseline tests:

```text
/data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m pytest \
  tests/test_camel_auth_provider_bootstrap.py \
  tests/test_camel_bootstrap_service.py \
  tests/test_auth_api_key.py \
  tests/test_api_keys_router.py -q

32 passed, 1 warning in 0.56s
```

ArcReel-side redirect hardening test after local audit:

```text
/data/data1/HOME_DIR/sijin/miniconda3/bin/conda run -n arcreel python -m pytest \
  tests/test_camel_auth_provider_bootstrap.py -q

5 passed in 0.32s
```

Read-only CaMeL-api local snapshot smoke run, kept only as historical context:

```text
go test ./model ./controller -run 'ArcReel|OAuthProviderArcReel|ProvisionArcReel'

ok github.com/QuantumNous/new-api/model [no tests to run]
ok github.com/QuantumNous/new-api/controller [no tests to run]
```

No CaMeL-api changes are planned from this audit.

## Findings

### Finding 1: CaMeL-api provisioning behavior is an external contract gate

**Severity:** release gate
**Boundary:** external dependency

ArcReel depends on CaMeL-api for ArcReel-managed visible token provisioning. The expected external contract is:

- create succeeds for a valid ArcReel OAuth bearer with `arcreel:token-provision`;
- create detects same-name non-managed token conflicts;
- repair rotates ArcReel-managed tokens without taking over non-managed tokens;
- wrong OAuth client and missing scope are rejected;
- retry behavior for the same logical provisioning request is deterministic under the completed CaMeL-api contract.

Requirement:

- Story 0 runs ArcReel-owned contract verification against the completed CaMeL-api service when credentials and endpoint are available.
- ArcReel does not modify CaMeL-api files or create a CaMeL-api worktree.
- Any contract mismatch is recorded as an external dependency defect and handled outside this ArcReel sprint.

### Finding 2: ArcReel needs CaMeL contract smoke evidence

**Severity:** major
**Files:**

- ArcReel test or QA contract-smoke files owned by Story 0

The tenant edition relies on a completed external CaMeL-api implementation. ArcReel still needs reproducible evidence that its configured client, scopes, callback, and local bootstrap behavior match that external API.

Required ArcReel-owned coverage:

- OAuth start/callback redirect behavior.
- local provider/API key bootstrap success.
- local partial failure response shape.
- user mismatch rejection.
- external contract smoke for create, conflict, repair, client, scope, and retry behavior when the CaMeL-api service is available.

### Finding 3: ArcReel OAuth dynamic redirect trusts `X-Forwarded-Proto` without scheme allowlist

**Severity:** medium
**File:** `server/services/camel_auth.py:115`

`_camel_redirect_uri()` previously used `x-forwarded-proto` to construct `redirect_uri` after the host matched `CAMEL_OAUTH_REDIRECT_HOSTS`. The scheme was not limited to `http` or `https`.

Impact:

- A loose proxy could allow the client to influence the OAuth `redirect_uri` scheme.
- CaMeL should reject unregistered redirect URIs, but ArcReel should fail closed at its own boundary.

Status:

- Fixed in ArcReel commit `0a80f9c`.
- Targeted test added for invalid forwarded scheme.
- Production deployments should still register only the intended HTTPS redirect URIs.

### Finding 4: Current API key name is globally unique, not user-scoped

**Severity:** medium
**File:** `lib/db/models/api_key.py:17`

`ApiKey.name` is globally unique today. Although list/delete/create are scoped by `user_id`, two users cannot create the same API key name.

Impact:

- Under current CaMeL user isolation, users can still collide on API key names.
- The tenant edition must use `unique(tenant_id, name)` or `unique(tenant_id, created_by_user_id, name)` depending on final product semantics.

Requirement:

- Story 2 or Story 7 removes the global name unique constraint.
- The new constraint is tenant-scoped.

### Finding 5: Bootstrap status only checks timestamp, not actual provider completeness

**Severity:** minor
**File:** `server/services/camel_bootstrap.py:203`

`get_camel_bootstrap_status()` only checks `users.camel_provider_bootstrap_completed_at`. If the user later deletes CaMeL providers or defaults, status still returns completed.

Impact:

- First-login UI will not automatically repair missing providers.
- The current repair entry point provides a workaround.
- The tenant edition must move bootstrap completeness to tenant config/provider state.

Requirement:

- Do not reuse user-level timestamp as the only completion source.
- Use tenant-level bootstrap state and validate required provider/default completeness.

### Finding 6: CaMeL display username uniqueness may become tenant onboarding blocker

**Severity:** minor
**Files:**

- `server/services/camel_auth.py:250`
- `lib/db/models/user.py:16`

`upsert_camel_user()` writes CaMeL `username` or `display_name` to `users.username`, while `users.username` is unique. This is safe only if CaMeL username is globally unique and the display-name fallback never collides.

Requirement:

- The tenant schema binds unique user identity to provider subject.
- `username` and `display_name` are display fields only.

## Conclusion For Tenant Commercialization

The tenant system can continue to build on the existing CaMeL OAuth and ArcReel bootstrap integration, with Story 0 scoped to ArcReel-owned verification and hardening:

1. Treat CaMeL-api as a completed external dependency.
2. Do not modify CaMeL-api files or branches.
3. Keep the ArcReel dynamic redirect scheme hardening from commit `0a80f9c`.
4. Add or run ArcReel-owned contract verification for CaMeL provisioning behavior.
5. Remove API key global name uniqueness and user-level bootstrap timestamp dependency in later tenant stories.
