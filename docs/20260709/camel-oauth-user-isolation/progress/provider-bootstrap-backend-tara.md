# Backend Sprint Progress: Tara

**Engineer:** Tara
**Story:** Story 2 - CaMeL Provider Bootstrap And Key Repair
**Story Branch:** story/camel-oauth-user-isolation/provider-bootstrap
**Story Worktree:** ../ArcReel-worktrees/camel-oauth-user-isolation/provider-bootstrap
**File Ownership:** server/routers/camel_bootstrap.py, server/services/camel_bootstrap.py, lib/db/models/user.py, lib/config/repository.py, lib/config/resolver.py, lib/config/service.py, lib/db/models/config.py, lib/db/models/credential.py, lib/db/models/custom_provider.py, lib/db/repositories/credential_repository.py, lib/db/repositories/custom_provider_repo.py, server/routers/system_config.py, server/routers/providers.py, server/routers/custom_providers.py, ../CaMeL-api/controller/oauth_provider.go, ../CaMeL-api/router/api-router.go, ../CaMeL-api/model/token.go, ../CaMeL-api/common/*

## Acceptance Criteria

- Provider credentials, built-in provider configuration, custom providers, custom provider models, and provider defaults are stored, listed, selected, resolved, and deleted per CaMeL-derived ArcReel user.
- Generation queue provider resolution uses the task owner's user id when resolving provider credentials and custom providers.
- After CaMeL login, ArcReel detects whether the current user has completed CaMeL provider bootstrap.
- The bootstrap action redirects the browser through a CaMeL OAuth authorization flow with the dedicated `arcreel:token-provision` scope.
- ArcReel consumes the CaMeL access token only inside the OAuth callback request and does not persist it.
- Raw CaMeL API keys returned by provisioning are consumed server-side only and never returned to the browser.
- The personal settings page includes a CaMeL key repair button that starts the same authorization flow in `mode=repair`.
- Repair mode requires CaMeL re-authentication or a recent CaMeL authentication check, and ArcReel never asks for the user's CaMeL password.
- If CaMeL reports existing token-name conflicts, ArcReel does not create or overwrite local providers; the response returns conflict names plus CaMeL management links.
- On success, ArcReel creates four user-owned custom providers: one each for image, text, video, and audio, so the user can inspect or delete them independently.
- Each custom provider uses the configured CaMeL base URL and only registers the configured allowlisted models for its media type.
- The Seedance video provider uses the `ark-seedance` endpoint and the canonical CaMeL base URL without requiring users to manually append `/api/v3`.
- Successful bootstrap marks the user's onboarding state as complete and sets the new providers/models as the user's defaults where ArcReel already has per-user default selection fields.
- If local provider creation fails after CaMeL token creation, bootstrap remains incomplete and the response returns deletion links for the generated CaMeL token names.

## Subtasks

- [x] Add CaMeL provisioning settings and endpoint behavior for visible per-media tokens, conflicts, repair mode, ArcReel-managed marking, idempotency, model allowlist enforcement, and one-time key return.
  - Commit: d847d2bb (CaMeL-api)
- [x] Add ArcReel bootstrap status, authorization start, callback handling, and repair start flow under authenticated API routes.
  - Commit: 3181512, f758e49
- [x] Add ArcReel user-scoped persistence for provider credentials, built-in provider configuration, custom providers, custom provider models, provider defaults, and bootstrap completion state.
  - Commit: 8e05499, f758e49
- [x] Implement the ArcReel service that calls CaMeL provisioning in create or repair mode, creates or updates user-owned custom providers, creates model rows, and updates user provider defaults.
  - Commit: 3181512, f758e49
- [x] Add conflict retry behavior and partial-failure handling for CaMeL tokens created before local provider persistence fails.
  - Commit: d847d2bb (CaMeL-api), 3181512, f758e49

**Ready for QA:** yes

## QA Evidence

- Commit: 7f41629
- Command: `python -m pytest tests/test_camel_bootstrap_service.py tests/test_camel_auth_provider_bootstrap.py tests/test_config_repository.py tests/test_credential_repository.py tests/test_custom_provider_repo.py tests/test_credential_api.py tests/test_providers_api.py tests/test_custom_providers_api.py tests/test_system_config_router.py tests/test_custom_provider_models.py tests/test_db_models.py tests/test_generation_tasks_service.py -q`
- Result: 326 passed, 1 existing FastAPI/TestClient warning.
- Command: `git diff --check`
- Result: passed.

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
