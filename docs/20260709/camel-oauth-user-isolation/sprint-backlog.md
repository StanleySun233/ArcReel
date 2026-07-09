# Sprint Backlog: CaMeL OAuth User Isolation

**Date:** 20260709
**Status:** in_progress
**Product brief:** Conversation request on 2026-07-09: replace ArcReel local login with CaMeL login, support real multi-user state without organization-level tenancy, isolate provider configuration plus custom providers per CaMeL user, bootstrap first-time CaMeL users with working CaMeL-backed image, text, video, and audio providers, add a personal-settings repair action for ArcReel-managed CaMeL keys, and make the free CaMeL API relay deployment comply with ArcReel AGPL-3.0 plus NOTICE obligations.
**Main integration branch:** fix/seedance-mounted-base-url

## Sprint Goal

ArcReel signs users in through CaMeL OAuth and maps each CaMeL identity to a local ArcReel user. Provider credentials, built-in provider configuration, custom providers, and provider defaults are isolated per user. A first-time CaMeL user can authorize one-time CaMeL key provisioning and receive four ArcReel custom providers for image, text, video, and audio; an existing user can repair ArcReel-managed CaMeL keys from personal settings after CaMeL re-authentication. The modified free deployment preserves ArcReel attribution and gives every network user a clear path to the exact corresponding source code for the running version.

This sprint does not introduce organizations, tenant administration, cross-user sharing, team membership, quotas, billing, admin impersonation, paid access, or commercial API resale.

## Team

| Role | Agent Name | Progress File |
|------|------------|---------------|
| Backend | Noah | [->](./progress/camel-auth-backend-noah.md) |
| Frontend | Mira | [->](./progress/camel-login-frontend-mira.md) |
| Backend | Tara | [->](./progress/provider-bootstrap-backend-tara.md) |
| Frontend | Nia | [->](./progress/provider-bootstrap-frontend-nia.md) |
| Frontend | Lena | [->](./progress/license-compliance-frontend-lena.md) |
| QA | Quinn | |
| Product Owner | Parker | |

## Implementation Agent Allocation

| Product Story | Backend Agent | Frontend Agent | Notes |
|---------------|---------------|----------------|-------|
| Story 1 - CaMeL OAuth Login And User Identity | Noah | Mira | ArcReel backend and frontend login state. |
| Story 2 - CaMeL Provider Bootstrap And Key Repair | Tara | Nia | ArcReel provider isolation, bootstrap, repair, and CaMeL provisioning integration. |
| Story 3 - AGPL License And Source Compliance | none | Lena | Frontend-only compliance display; no backend endpoint for this story. |

The implementation team has five development agents total: Noah, Mira, Tara, Nia, and Lena. Quinn owns ArcReel-side test coverage after the implementation slices land.

`api-contract.md` is the shared implementation contract for all three stories. It is not a separate product story in this sprint.

## Stories

### Story: Story 1 - CaMeL OAuth Login And User Identity

**Slug:** camel-auth
**User value:** A user clicks "Login by CaMeL", signs in through CaMeL if needed, and ArcReel recognizes the correct local user without ArcReel passwords.
**Status:** implemented
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [ ] ArcReel exposes a CaMeL OAuth start endpoint and callback endpoint under `/api/v1/auth`.
- [ ] The callback exchanges the authorization code with CaMeL, reads `/api/oauth/provider/userinfo`, upserts the local ArcReel user, and issues an ArcReel JWT containing the real `user_id`.
- [ ] The callback never persists the CaMeL OAuth credential and never exposes it in the ArcReel JWT, URL fragment, or browser storage.
- [ ] The callback supports OAuth state intent dispatch for regular login, provider bootstrap, and provider repair.
- [ ] `CurrentUserInfo.id` reflects the local CaMeL-derived user id instead of `default`.
- [ ] Local username/password login, password generation, create-password, and local-account mutation controls are disabled in CaMeL auth mode.
- [ ] API key Bearer auth resolves the owning user id from the API key row.
- [ ] `/login` shows only the CaMeL login path in CaMeL auth mode.
- [ ] `/login/callback` consumes the ArcReel JWT from the URL fragment and redirects to the safe return path.

**Engineering Subtasks**
- [ ] Noah: Add CaMeL OAuth settings, client helpers, state validation, callback handling, and user upsert support in `server/auth.py`, `server/routers/auth.py`, and a focused auth service module. (depends: api-contract)
- [ ] Noah: Add OAuth state intent dispatch for login, provider bootstrap, and provider repair without persisting CaMeL access tokens. (depends: api-contract)
- [ ] Noah: Disable local password login and automatic password generation in CaMeL auth mode. (depends: api-contract)
- [ ] Noah: Update API key verification to include the persisted owner `user_id` in the auth payload. (depends: api-contract)
- [ ] Mira: Replace the login form with CaMeL login in CaMeL auth mode and add callback token handling in `frontend/src/pages/LoginPage.tsx`, `frontend/src/stores/auth-store.ts`, `frontend/src/router.tsx`, and auth i18n files. (depends: api-contract)
- [ ] Quinn: Add ArcReel-side backend and frontend coverage for CaMeL auth status, local login disablement, callback token handling, real `user_id`, and API key owner auth. (depends: camel-auth)

**QA Evidence:** pending

### Story: Story 2 - CaMeL Provider Bootstrap And Key Repair

**Slug:** provider-bootstrap
**User value:** A first-time CaMeL user can accept one prompt and get working ArcReel image, text, video, and audio providers backed by CaMeL without manually copying base URLs, model ids, or API keys; an existing user can repair those keys from personal settings.
**Status:** implemented
**QA Status:** passed
**PO Status:** pending

**Acceptance Criteria**
- [x] Provider credentials, built-in provider configuration, custom providers, custom provider models, and provider defaults are stored, listed, selected, resolved, and deleted per CaMeL-derived ArcReel user.
- [x] Generation queue provider resolution uses the task owner's user id when resolving provider credentials and custom providers.
- [x] After CaMeL login, ArcReel detects whether the current user has completed CaMeL provider bootstrap.
- [x] On the first incomplete login, the frontend shows a modal explaining that ArcReel will create four CaMeL API keys named `camel-arcreel-{camel_user_id}-{image,text,video,audio}` and configure ArcReel providers for the current user.
- [x] The bootstrap action redirects the browser through a CaMeL OAuth authorization flow with the dedicated `arcreel:token-provision` scope.
- [x] CaMeL token provisioning identifies the current CaMeL user from the OAuth bearer token, checks for same-name token conflicts before creating anything, enforces the ArcReel model allowlist server-side, and returns each plaintext key once.
- [x] ArcReel consumes the CaMeL access token and raw CaMeL API keys server-side only; neither value is persisted, returned to the browser, or written into browser storage.
- [x] The personal settings page includes a CaMeL key repair button that starts the same authorization flow in `mode=repair`.
- [x] Repair mode requires CaMeL re-authentication or a recent CaMeL authentication check, and ArcReel never asks for the user's CaMeL password.
- [x] If CaMeL reports existing token-name conflicts, ArcReel does not create or overwrite local providers; the modal shows conflict names plus CaMeL management links and a retry action.
- [x] On success, ArcReel creates four user-owned custom providers: one each for image, text, video, and audio, so the user can inspect or delete them independently.
- [x] Each custom provider uses the configured CaMeL base URL and only registers the configured allowlisted models for its media type.
- [x] The Seedance video provider uses the `ark-seedance` endpoint and the canonical CaMeL base URL without requiring users to manually append `/api/v3`.
- [x] Successful bootstrap marks the user's onboarding state as complete and sets the new providers/models as the user's defaults where ArcReel already has per-user default selection fields.
- [x] If local provider creation fails after CaMeL token creation, bootstrap remains incomplete and the user receives deletion links for the created CaMeL token names.

**Engineering Subtasks**
- [x] Tara: Add CaMeL provisioning settings for ArcReel allowed models, token group, dedicated scope, ArcReel client validation, and token-management link template in CaMeL-api. (depends: api-contract)
- [x] Tara: Add CaMeL provisioning endpoint behavior for visible per-media token creation, conflict-first checks, repair mode, ArcReel-managed token marking, idempotency, model allowlist enforcement, and one-time key return. (depends: api-contract)
- [x] Tara: Add ArcReel bootstrap status, authorization start, callback handling, and repair start flow under authenticated API routes. (depends: camel-auth)
- [x] Tara: Add ArcReel user-scoped persistence for provider credentials, built-in provider configuration, custom providers, custom provider models, provider defaults, and bootstrap completion state. (depends: camel-auth)
- [x] Tara: Implement the ArcReel service that calls CaMeL provisioning in create or repair mode, creates or updates user-owned custom providers, creates model rows, updates user provider defaults, and returns non-sensitive result states. (depends: camel-auth)
- [x] Nia: Add first-login bootstrap modal, success state, conflict state with links, retry action, and partial-failure state. (depends: camel-auth)
- [x] Nia: Add personal settings CaMeL repair button and repair result states. (depends: camel-auth)
- [x] Nia: Refresh provider/default configuration state after successful bootstrap without exposing raw API keys. (depends: provider-bootstrap)
- [x] Quinn: Add ArcReel-side backend and frontend coverage for first login, provider isolation, custom provider isolation, success, conflict, retry-after-delete, repair, partial failure, and non-first-login no-op paths. (depends: provider-bootstrap)

**QA Evidence:** 2026-07-10: `python -m pytest tests/test_camel_bootstrap_service.py tests/test_camel_auth_provider_bootstrap.py tests/test_config_repository.py tests/test_credential_repository.py tests/test_custom_provider_repo.py tests/test_credential_api.py tests/test_providers_api.py tests/test_custom_providers_api.py tests/test_system_config_router.py tests/test_custom_provider_models.py tests/test_db_models.py tests/test_generation_tasks_service.py -q` passed with 326 tests. `pnpm check` passed with frontend typecheck, lint, and 101 Vitest files / 897 tests. `git diff --check` passed. Full `python -m pytest -q` is blocked by local dependency drift unrelated to this story: the conda environment has `volcengine-python-sdk 5.0.39` instead of locked `5.0.21` and `pyjianyingdraft 0.3.0` instead of locked `0.2.7`, causing Ark SDK import syntax failure and Jianying `ScriptFile.add_track` API failures.

### Story: Story 3 - AGPL License And Source Compliance

**Slug:** license-compliance
**User value:** Users of the free CaMeL API relay deployment can see the ArcReel attribution, license, NOTICE terms, and the exact source code for the modified version they are using.
**Status:** implemented
**QA Status:** pending
**PO Status:** pending

**Acceptance Criteria**
- [x] The service explicitly states that this deployment is a modified ArcReel deployment offered free of charge with CaMeL as the API relay; no paid access or commercial API resale is introduced by this story, and free access does not remove AGPL-3.0 obligations.
- [x] A frontend legal config module exposes original ArcReel attribution, upstream repository URL, AGPL-3.0 license link, NOTICE link, deployed source URL, deployed source ref, optional source archive URL, modified-version notice, and modified date from `VITE_ARCREEL_LEGAL_*` variables with safe defaults.
- [x] The login page shows legal/source links before authentication, including `Powered by ArcReel — https://github.com/ArcReel/ArcReel` and a link to the current deployed source.
- [x] The authenticated About/Legal section shows the same legal/source links and preserves the upstream ArcReel repository link required by NOTICE.
- [x] The legal UI states that ArcReel is provided without warranty, users may receive and convey the covered work under AGPL-3.0, and the full license is available through the visible license link.
- [x] The deployed source link points to the fork/branch/commit or source archive that corresponds to the running modified ArcReel version, excluding secrets and deployment-private configuration.
- [x] The UI marks the deployment as a modified version and does not imply the deployment is the official ArcReel service unless trademark permission is obtained; if rebranded, attribution remains visible and unmodified.
- [x] CaMeL-api is documented as a separate API relay service unless AGPL ArcReel code is copied into it or the services are combined into one derivative work.

**Engineering Subtasks**
- [x] Lena: Add frontend legal config in `frontend/src/config/legal.ts` reading `VITE_ARCREEL_LEGAL_*` variables with safe upstream defaults, modified-version notice, modified date, and source configured status. (depends: api-contract)
- [x] Lena: Add a reusable legal links component for login and About/Legal surfaces. (depends: api-contract)
- [x] Lena: Add unauthenticated login-page legal/source links without requiring a user session. (depends: camel-auth)
- [x] Lena: Update About/Legal section to include current deployed source URL, AGPL license link, NOTICE link, no-warranty/AGPL-rights notice, modified-version statement, free-service/API-relay statement, and upstream attribution. (depends: license-compliance)
- [ ] Quinn: Add frontend coverage for unauthenticated login-page legal links, authenticated About/Legal links, and missing deployed-source warning. (depends: license-compliance)

**QA Evidence:** Implementation merged in `659701e`; frontend coverage remains pending under Quinn.

## File Ownership

| File Path | Owner | Story | Parallel Policy |
|-----------|-------|-------|-----------------|
| `docs/20260709/camel-oauth-user-isolation/api-contract.md` | PM | Shared Contract | exclusive |
| `server/auth.py` | Noah | Story 1 - CaMeL OAuth Login And User Identity | exclusive |
| `server/routers/auth.py` | Noah | Story 1 - CaMeL OAuth Login And User Identity | exclusive |
| `server/services/*auth*` | Noah | Story 1 - CaMeL OAuth Login And User Identity | exclusive |
| `lib/db/models/user.py` | Noah/Tara | Story 1 / Story 2 | serialized: Noah owns identity fields first, Tara owns bootstrap fields second |
| `server/routers/api_keys.py` | Noah | Story 1 - CaMeL OAuth Login And User Identity | exclusive for API key owner auth |
| `lib/db/repositories/api_key_repository.py` | Noah | Story 1 - CaMeL OAuth Login And User Identity | exclusive for API key owner auth |
| `frontend/src/pages/LoginPage.tsx` | Mira/Lena | Story 1 / Story 3 | serialized: Mira owns CaMeL login first, Lena owns legal links second |
| `frontend/src/stores/auth-store.ts` | Mira/Nia | Story 1 / Story 2 | serialized: Mira owns auth status first, Nia owns bootstrap status second |
| `frontend/src/router.tsx` | Mira | Story 1 - CaMeL OAuth Login And User Identity | exclusive |
| `frontend/src/i18n/*/auth.ts` | Mira | Story 1 - CaMeL OAuth Login And User Identity | exclusive |
| `../CaMeL-api/controller/oauth_provider.go` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive in CaMeL-api repo |
| `../CaMeL-api/router/api-router.go` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive in CaMeL-api repo |
| `../CaMeL-api/model/token.go` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive in CaMeL-api repo |
| `../CaMeL-api/common/*` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | review required for shared config changes |
| `server/routers/camel_bootstrap.py` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive |
| `server/services/camel_bootstrap.py` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive |
| `lib/config/repository.py` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive |
| `lib/config/resolver.py` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive |
| `lib/config/service.py` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive |
| `lib/db/models/config.py` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive |
| `lib/db/models/credential.py` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive |
| `lib/db/models/custom_provider.py` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive |
| `lib/db/repositories/credential_repository.py` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive |
| `lib/db/repositories/custom_provider_repo.py` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive |
| `server/routers/system_config.py` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive |
| `server/routers/providers.py` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive |
| `server/routers/custom_providers.py` | Tara | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive |
| `frontend/src/components/auth/CamelProviderBootstrapModal.tsx` | Nia | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive |
| `frontend/src/components/pages/SystemConfigPage.tsx` | Nia | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive for personal settings repair entry |
| `frontend/src/components/pages/settings/CamelAccountSection.tsx` | Nia | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive |
| `frontend/src/api.ts` | Nia | Story 2 - CaMeL Provider Bootstrap And Key Repair | exclusive for bootstrap/repair API helpers |
| `frontend/src/i18n/*/dashboard.ts` | Nia/Lena | Story 2 / Story 3 | serialized by frontend integration owner |
| `frontend/src/config/legal.ts` | Lena | Story 3 - AGPL License And Source Compliance | exclusive |
| `frontend/src/components/legal/LegalLinks.tsx` | Lena | Story 3 - AGPL License And Source Compliance | exclusive |
| `frontend/src/components/pages/settings/AboutSection.tsx` | Lena | Story 3 - AGPL License And Source Compliance | exclusive |
| `tests/**` | Quinn | All Stories | QA owns ArcReel-side test additions after implementation slices land |
| `frontend/src/**/*.test.tsx` | Quinn | All Stories | QA owns ArcReel-side frontend test additions after implementation slices land |
| `frontend/src/**/*.test.ts` | Quinn | All Stories | QA owns ArcReel-side frontend test additions after implementation slices land |

## Worktrees

| Story | Branch | Worktree Path | Merge Target | Merge Status | Cleanup Status |
|-------|--------|---------------|--------------|--------------|----------------|
| Story 1 - CaMeL OAuth Login And User Identity | `story/camel-oauth-user-isolation/camel-auth` | `../ArcReel-worktrees/camel-oauth-user-isolation/camel-auth` | `fix/seedance-mounted-base-url` | merged | removed |
| Story 2 - CaMeL Provider Bootstrap And Key Repair | `story/camel-oauth-user-isolation/provider-bootstrap` | `../ArcReel-worktrees/camel-oauth-user-isolation/provider-bootstrap` | `fix/seedance-mounted-base-url` | merged in `74181fb` | removed |
| Story 3 - AGPL License And Source Compliance | `story/camel-oauth-user-isolation/license-compliance` | `../ArcReel-worktrees/camel-oauth-user-isolation/license-compliance` | `fix/seedance-mounted-base-url` | merged | removed |

## Blockers

| Date | Story/Subtask | Owner | Blocker | Resolution |
|------|---------------|-------|---------|------------|
| 2026-07-09 | Story 1 - CaMeL OAuth Login And User Identity | Noah | ArcReel public callback URL must be registered in CaMeL OAuth provider app configuration. | Use the final ArcReel public base URL before production deployment. |
| 2026-07-09 | Story 1 - CaMeL OAuth Login And User Identity | Noah | CaMeL client id and client secret are produced once when the OAuth provider app is created. | Capture the startup log or rotate by deleting/reseeding the app row. |
| 2026-07-09 | Story 2 - CaMeL Provider Bootstrap And Key Repair | Tara | Existing CaMeL `/api/oauth/provider/auto-token` creates hidden `lobechat-auto:<group>` tokens and is not suitable for visible ArcReel per-media token management. | Add an ArcReel-specific provisioning endpoint with visible token creation, conflict links, and model allowlist enforcement. |
| 2026-07-09 | Story 2 - CaMeL Provider Bootstrap And Key Repair | Tara | Repair mode must not rotate manually created same-name tokens. | Mark tokens created by the ArcReel provisioning endpoint and rotate only ArcReel-managed tokens. |
| 2026-07-09 | Story 2 - CaMeL Provider Bootstrap And Key Repair | Tara | Token provisioning must not be authorized by a generic profile bearer token. | Require ArcReel OAuth client validation and dedicated `arcreel:token-provision` scope. |
| 2026-07-09 | Story 2 - CaMeL Provider Bootstrap And Key Repair | Tara | Exact image, text, and audio model ids must come from the deployed CaMeL ArcReel allowlist; only the Seedance model `doubao-seedance-2-0-260128` is currently confirmed from production usage. | Store the four media model ids in deployment configuration and make bootstrap fail closed if any media allowlist is missing. |
| 2026-07-09 | Story 2 - CaMeL Provider Bootstrap And Key Repair | Tara | The `camelbot` deployment is the production source of truth for the prepared CaMeL base URL, token group, and media model allowlists. | Mirror those values into the `CAMEL_ARCREEL_*` environment settings before production bootstrap is enabled. |
| 2026-07-09 | Story 3 - AGPL License And Source Compliance | Lena | Free service operation does not remove AGPL-3.0 network-source obligations for the modified ArcReel deployment. | Provide visible license/NOTICE/upstream attribution, no-warranty notice, AGPL rights notice, modified-version notice, and current deployed source links to all network users. |
| 2026-07-09 | Story 3 - AGPL License And Source Compliance | Lena | Final deployed source URL is not known until deployment branch/commit is selected. | Require `VITE_ARCREEL_LEGAL_SOURCE_URL` before public deployment and surface a frontend warning if missing. |
| 2026-07-09 | Story 3 - AGPL License And Source Compliance | Lena | ArcReel name and logo are not licensed as trademarks by AGPL. | Preserve required attribution, but use deployment-specific branding unless separate trademark permission is obtained. |
