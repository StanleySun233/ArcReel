# API Contract: CaMeL OAuth User Isolation

## Scope

ArcReel uses CaMeL as the identity provider. ArcReel still owns its own authorization token and application state, but the local user identity is derived from CaMeL `/api/oauth/provider/userinfo`.

This contract covers individual CaMeL users only. It does not define organizations, tenant admins, team sharing, role management, billing, quotas, or cross-user project sharing.

## Auth Configuration

Required backend settings:

| Setting | Purpose |
|---------|---------|
| `AUTH_MODE=camel` | Enables CaMeL-only login and disables local username/password login. |
| `CAMEL_OAUTH_BASE_URL` | CaMeL API public base URL, for example `https://api.camel-hub.com`. |
| `CAMEL_OAUTH_CLIENT_ID` | Registered OAuth provider app client id from CaMeL. |
| `CAMEL_OAUTH_CLIENT_SECRET` | Registered OAuth provider app client secret from CaMeL. |
| `CAMEL_OAUTH_REDIRECT_URI` | Exact ArcReel callback URL registered in CaMeL. |
| `CAMEL_OAUTH_SCOPES` | Default `profile email`. |
| `CAMEL_OAUTH_BOOTSTRAP_SCOPES` | Default `profile email arcreel:token-provision`; used only when a user authorizes provider bootstrap or repair. |
| `CAMEL_OAUTH_REPAIR_MAX_AGE_SECONDS` | Maximum CaMeL authentication age accepted for key repair. Use `0` or a short window when CaMeL supports it. |

Required bootstrap settings:

| Setting | Purpose |
|---------|---------|
| `CAMEL_ARCREEL_PROVIDER_BASE_URL` | Base URL written into ArcReel custom providers, for example `https://api.camel-hub.com`. The Seedance endpoint appends its required `/api/v3` path internally. |
| `CAMEL_ARCREEL_TOKEN_PROVISION_URL` | CaMeL OAuth-provider API endpoint used by ArcReel to create the four restricted API keys. |
| `CAMEL_ARCREEL_TOKEN_LINK_TEMPLATE` | Template used for token conflict links, for example `https://camel-hub.com/console/token?keyword={token_name}`. |
| `CAMEL_ARCREEL_TOKEN_GROUP` | CaMeL token group used for the generated ArcReel API keys. |
| `CAMEL_ARCREEL_IMAGE_MODELS` | Comma-separated image model allowlist registered in the image custom provider and enforced by CaMeL. |
| `CAMEL_ARCREEL_TEXT_MODELS` | Comma-separated text model allowlist registered in the text custom provider and enforced by CaMeL. |
| `CAMEL_ARCREEL_VIDEO_MODELS` | Comma-separated video model allowlist. The confirmed Seedance model is `doubao-seedance-2-0-260128`. |
| `CAMEL_ARCREEL_AUDIO_MODELS` | Comma-separated audio model allowlist registered in the audio custom provider and enforced by CaMeL. |
| `CAMEL_ARCREEL_IMAGE_ENDPOINT` | ArcReel custom provider endpoint key for image models. |
| `CAMEL_ARCREEL_TEXT_ENDPOINT` | ArcReel custom provider endpoint key for text models. |
| `CAMEL_ARCREEL_VIDEO_ENDPOINT` | ArcReel custom provider endpoint key for video models. Default `ark-seedance` for Seedance. |
| `CAMEL_ARCREEL_AUDIO_ENDPOINT` | ArcReel custom provider endpoint key for audio models. |

The deployed `camelbot` configuration is the production source of truth for the final CaMeL base URL, token group, and media model allowlists. ArcReel reads those values from environment configuration instead of hardcoding model ids in code.

`AUTH_ENABLED=false` remains a local development bypass. In `AUTH_MODE=camel`, `ensure_auth_password()` does not generate or persist `AUTH_PASSWORD`. ArcReel does not preserve legacy local-login, local-password, or local-account mutation behavior in CaMeL mode; CaMeL OAuth is the only supported product path for this deployment.

## Legal Compliance Configuration

This deployment is offered free of charge and uses CaMeL as an API relay. Story 3 does not introduce paid access or commercial API resale. Free access does not remove AGPL-3.0 obligations for the modified ArcReel deployment.

Story 3 is frontend-only. Legal data is read from frontend build-time environment variables and rendered before and after authentication.

Required legal settings for public deployment:

| Setting | Purpose |
|---------|---------|
| `VITE_ARCREEL_LEGAL_SOURCE_URL` | Public URL for the exact corresponding source of the running modified ArcReel version, such as a fork branch, commit, release tag, or source archive page. |
| `VITE_ARCREEL_LEGAL_SOURCE_REF` | Human-readable source ref, such as git commit SHA, branch name, or release tag. |
| `VITE_ARCREEL_LEGAL_SOURCE_ARCHIVE_URL` | Optional direct source archive URL for the running version. |
| `VITE_ARCREEL_LEGAL_MODIFIED_DATE` | Relevant modification date displayed with the modified-version notice. |
| `VITE_ARCREEL_LEGAL_MODIFIED_NOTICE` | Default `This deployment runs a modified version of ArcReel.` |
| `VITE_ARCREEL_LEGAL_UPSTREAM_URL` | Default `https://github.com/ArcReel/ArcReel`. |
| `VITE_ARCREEL_LEGAL_LICENSE_URL` | Default `https://github.com/ArcReel/ArcReel/blob/main/LICENSE`. |
| `VITE_ARCREEL_LEGAL_NOTICE_URL` | Default `https://github.com/ArcReel/ArcReel/blob/main/NOTICE`. |
| `VITE_ARCREEL_LEGAL_SERVICE_MODEL` | Default `free`. Displayed as service context, not as a license exception. |
| `VITE_ARCREEL_LEGAL_API_RELAY_NAME` | Default `CaMeL`. Displayed as the API relay used by this deployment. |
| `VITE_ARCREEL_LEGAL_DEPLOYMENT_NAME` | Deployment-specific service name. It must not imply this is the official ArcReel service unless trademark permission is obtained. |

`VITE_ARCREEL_LEGAL_SOURCE_URL` is required before public deployment. Missing source configuration should produce a frontend legal-compliance warning on the About/Legal surface.

The corresponding source published through `VITE_ARCREEL_LEGAL_SOURCE_URL` must exclude secrets, `.env` files, production credentials, private CaMeL API keys, and deployment-private infrastructure values.

The legal UI must preserve `Powered by ArcReel — https://github.com/ArcReel/ArcReel`, link to the upstream repository, state that ArcReel is provided without warranty, state that users may receive and convey the covered work under AGPL-3.0, link to the full license text, and mark the running service as a modified version with the relevant modification date.

## Auth Endpoints

### `GET /api/v1/auth/status`

Response:

```json
{
  "enabled": true,
  "mode": "camel",
  "providers": [
    {
      "id": "camel",
      "label": "CaMeL",
      "login_url": "/api/v1/auth/camel/start"
    }
  ]
}
```

`mode="local"` may exist only when `AUTH_MODE` is not `camel`. The frontend uses this response to decide whether to show the CaMeL button or the local password form.

### Frontend Legal Config Shape

`frontend/src/config/legal.ts` exports this shape:

```ts
{
  deploymentName: "CaMeL ArcReel",
  serviceModel: "free",
  apiRelayName: "CaMeL",
  license: "AGPL-3.0",
  upstreamName: "ArcReel",
  upstreamUrl: "https://github.com/ArcReel/ArcReel",
  noticeText: "Powered by ArcReel — https://github.com/ArcReel/ArcReel",
  licenseUrl: "https://github.com/ArcReel/ArcReel/blob/main/LICENSE",
  noticeUrl: "https://github.com/ArcReel/ArcReel/blob/main/NOTICE",
  sourceUrl: "https://github.com/StanleySun233/ArcReel/tree/deploy-commit",
  sourceRef: "deploy-commit",
  sourceArchiveUrl: "https://github.com/StanleySun233/ArcReel/archive/deploy-commit.zip",
  modifiedNotice: "This deployment runs a modified version of ArcReel.",
  modifiedDate: "2026-07-09",
  warrantyNotice: "ArcReel is provided without warranty under AGPL-3.0.",
  conveyanceNotice: "You may receive and convey the covered work under AGPL-3.0.",
  sourceConfigured: true
}
```

Legal config must not include deployment secrets, provider credentials, OAuth client secrets, API keys, or private repository tokens.

When `sourceConfigured=false`, the frontend still displays upstream attribution and license links, but also shows a legal-compliance warning that the deployed source URL is not configured.

### `GET /api/v1/auth/camel/start?from=/app/projects`

Behavior:

- validates that `from` is a safe ArcReel-relative path;
- creates an OAuth `state` containing the safe return path;
- stores state verification material in a short-lived signed cookie;
- redirects to:

```text
{CAMEL_OAUTH_BASE_URL}/api/oauth/provider/authorize
  ?response_type=code
  &client_id={CAMEL_OAUTH_CLIENT_ID}
  &redirect_uri={CAMEL_OAUTH_REDIRECT_URI}
  &scope={CAMEL_OAUTH_SCOPES}
  &state={state}
```

If the browser does not already have a CaMeL session, CaMeL redirects the user to its own login page and then resumes the authorization flow.

### `GET /api/v1/auth/camel/callback?code=...&state=...`

Behavior:

- validates the state cookie and extracts the safe return path;
- posts the authorization code to CaMeL `/api/oauth/provider/token`;
- calls CaMeL `/api/oauth/provider/userinfo` with the OAuth access token;
- upserts an ArcReel `users` row using the CaMeL user id;
- signs an ArcReel JWT with `sub`, `user_id`, `provider`, and expiration;
- redirects to the frontend callback route with the ArcReel JWT in the URL fragment:

```text
/login/callback#access_token={arc_jwt}&from={safe_return_path}
```

The fragment is consumed by the frontend and stored through the existing auth token storage.

The CaMeL OAuth access token is not persisted, not embedded in the ArcReel JWT, not returned in the URL fragment, and not written to browser storage.

The callback also supports OAuth state intent dispatch:

| Intent | Behavior |
|--------|----------|
| `login` | Upsert the local user, issue the ArcReel JWT, and redirect to the frontend. |
| `provider_bootstrap` | Verify the CaMeL user matches the current ArcReel user, call CaMeL provisioning in `mode=create` in the same callback request, consume returned keys server-side, and redirect with a non-sensitive result status. |
| `provider_repair` | Verify the CaMeL user matches the current ArcReel user, call CaMeL provisioning in `mode=repair` in the same callback request, consume returned keys server-side, and redirect with a non-sensitive result status. |

### `POST /api/v1/auth/token`

In `AUTH_MODE=camel`, this endpoint returns `404` or `403` and never accepts local credentials.

### `GET /api/v1/auth/verify`

Response:

```json
{
  "valid": true,
  "username": "camel-user",
  "user_id": "camel:123",
  "provider": "camel"
}
```

## JWT Payload

ArcReel JWT payload:

```json
{
  "sub": "camel-user",
  "user_id": "camel:123",
  "provider": "camel",
  "iat": 1783560000,
  "exp": 1784164800
}
```

`CurrentUserInfo.id` is always populated from `user_id`. API key Bearer auth uses the `api_keys.user_id` owner from the database.

## Local User Mapping

CaMeL userinfo response fields used by ArcReel:

| CaMeL field | ArcReel field |
|-------------|---------------|
| `id` or `sub` | `users.id` as `camel:{id}` |
| `username` | `users.username` |
| `email` | Stored only if an ArcReel user email column exists in the implementation. |
| `display_name` | Stored only if an ArcReel display name column exists in the implementation. |

The user upsert is idempotent. Existing users are updated with the latest CaMeL username when it changes.

## First Login Provider Bootstrap

After a successful CaMeL login, ArcReel checks whether the local user has completed CaMeL provider bootstrap. Bootstrap is user-scoped and runs only after the user confirms the prompt. Confirmation starts a new CaMeL OAuth authorization request with `CAMEL_OAUTH_BOOTSTRAP_SCOPES`; it does not use a previously stored CaMeL access token.

Bootstrap creates four local ArcReel custom providers:

| Media | Provider Name | Endpoint Key | Model Source | CaMeL Token Name |
|-------|---------------|--------------|--------------|------------------|
| Image | `CaMeL Image` | `CAMEL_ARCREEL_IMAGE_ENDPOINT` | `CAMEL_ARCREEL_IMAGE_MODELS` | `camel-arcreel-{camel_user_id}-image` |
| Text | `CaMeL Text` | `CAMEL_ARCREEL_TEXT_ENDPOINT` | `CAMEL_ARCREEL_TEXT_MODELS` | `camel-arcreel-{camel_user_id}-text` |
| Video | `CaMeL Video` | `CAMEL_ARCREEL_VIDEO_ENDPOINT` | `CAMEL_ARCREEL_VIDEO_MODELS` | `camel-arcreel-{camel_user_id}-video` |
| Audio | `CaMeL Audio` | `CAMEL_ARCREEL_AUDIO_ENDPOINT` | `CAMEL_ARCREEL_AUDIO_MODELS` | `camel-arcreel-{camel_user_id}-audio` |

`camel_user_id` is the CaMeL user id from `/api/oauth/provider/userinfo` before ArcReel adds the local `camel:` prefix. The token names must fit CaMeL's token name length constraint.

The local provider base URL is `CAMEL_ARCREEL_PROVIDER_BASE_URL`. For Seedance, ArcReel stores the canonical CaMeL base URL, such as `https://api.camel-hub.com`, and relies on the `ark-seedance` endpoint implementation to add `/api/v3/contents/generations/tasks`. Users do not need to configure `https://api.camel-hub.com/api/v3`.

### `GET /api/v1/camel/bootstrap/status`

Requires an ArcReel authenticated session.

Response when bootstrap is needed:

```json
{
  "needed": true,
  "completed": false,
  "camel_user_id": "123",
  "providers": [
    {
      "media": "video",
      "provider_name": "CaMeL Video",
      "base_url": "https://api.camel-hub.com",
      "endpoint": "ark-seedance",
      "models": ["doubao-seedance-2-0-260128"],
      "token_name": "camel-arcreel-123-video"
    }
  ]
}
```

Response after bootstrap is complete:

```json
{
  "needed": false,
  "completed": true
}
```

### `POST /api/v1/camel/bootstrap/start-url?mode=create&from=/app/settings`

Requires an ArcReel authenticated session.

Behavior:

- validates that `from` is a safe ArcReel-relative path;
- validates that `mode` is `create` or `repair`;
- creates an OAuth `state` containing the mode, safe return path, current ArcReel user id, and idempotency key;
- sets the short-lived OAuth state cookie and returns the CaMeL `/api/oauth/provider/authorize` URL with `CAMEL_OAUTH_BOOTSTRAP_SCOPES`;
- for `mode=repair`, requests a fresh CaMeL authentication check through `max_age` or `prompt=login` when supported by CaMeL.

Response:

```json
{
  "authorization_url": "https://api.camel-hub.com/api/oauth/provider/authorize?response_type=code&..."
}
```

The frontend calls this endpoint with its normal ArcReel `Authorization: Bearer` header, then navigates the browser to `authorization_url`. It does not navigate directly to an authenticated ArcReel redirect endpoint because browser top-level navigation does not include the stored ArcReel bearer token.

Redirect example:

```text
{CAMEL_OAUTH_BASE_URL}/api/oauth/provider/authorize
  ?response_type=code
  &client_id={CAMEL_OAUTH_CLIENT_ID}
  &redirect_uri={CAMEL_OAUTH_REDIRECT_URI}
  &scope={CAMEL_OAUTH_BOOTSTRAP_SCOPES}
  &state={state_with_provider_bootstrap_or_repair_intent}
  &max_age={CAMEL_OAUTH_REPAIR_MAX_AGE_SECONDS}
```

### OAuth Callback For Bootstrap Or Repair

The OAuth callback exchanges the authorization code, calls CaMeL `/api/oauth/provider/userinfo`, verifies that the CaMeL user maps to the current ArcReel user, and immediately calls CaMeL token provisioning in the requested mode. The CaMeL access token exists only in this callback request.

Browser-visible result data is non-sensitive and never includes raw API keys. Successful result shape:

```json
{
  "completed": true,
  "providers": [
    {
      "media": "video",
      "provider_id": 14,
      "provider_name": "CaMeL Video",
      "models": ["doubao-seedance-2-0-260128"]
    }
  ]
}
```

Conflict result shape:

```json
{
  "completed": false,
  "error": "camel_token_conflict",
  "conflicts": [
    {
      "media": "video",
      "token_name": "camel-arcreel-123-video",
      "delete_url": "https://camel-hub.com/console/token?keyword=camel-arcreel-123-video"
    }
  ]
}
```

ArcReel must not create or overwrite local custom providers when CaMeL returns any conflict. The retry button starts a new CaMeL authorization request and re-runs provisioning after the user deletes the conflicting token in CaMeL.

Raw CaMeL API keys returned by provisioning are consumed by the ArcReel backend only. The bootstrap response to the browser never includes API keys.

ArcReel marks bootstrap complete only after all four local custom providers, their model rows, and provider defaults are committed. If CaMeL token creation succeeds but local provider creation fails, ArcReel returns `partial_bootstrap_failed` with deletion links for the created CaMeL token names and leaves bootstrap incomplete. The next retry must start from a clean CaMeL token-name state.

## Personal Settings Key Repair

The personal settings page shows a CaMeL key repair action when `AUTH_MODE=camel`. The button calls:

```text
POST /api/v1/camel/bootstrap/start-url?mode=repair&from=%2Fapp%2Fsettings%3Fsection%3Daccount
```

Repair mode reauthorizes through CaMeL before changing keys. ArcReel never asks for the user's CaMeL password. CaMeL validates the user's current authentication and the dedicated `arcreel:token-provision` scope.

Repair behavior:

| Case | Behavior |
|------|----------|
| ArcReel-managed token exists | CaMeL rotates that token and returns the new plaintext key once. |
| ArcReel-managed token is missing | CaMeL creates it and returns the plaintext key once. |
| Same-name token exists but was not created by ArcReel provisioning | CaMeL returns a conflict with a management link and does not rotate it. |
| Local provider exists | ArcReel updates the API key and configured model allowlist. |
| Local provider is missing | ArcReel recreates the missing media provider. |

## CaMeL Token Provisioning Contract

ArcReel uses a dedicated CaMeL endpoint instead of the existing CaMeL Chat `auto-token` endpoint or the general CaMeL token-management endpoints. The existing `auto-token` endpoint creates hidden `lobechat-auto:<group>` tokens, while ArcReel needs visible per-media tokens that the user can manage and delete. The general token-management create path is not a good contract for this flow because ArcReel needs conflict-first creation, server-side ArcReel model allowlist enforcement, and one-time plaintext key return in the same OAuth-authorized operation.

### `POST {CAMEL_ARCREEL_TOKEN_PROVISION_URL}`

Authentication:

```text
Authorization: Bearer {camel_oauth_access_token}
```

Request:

```json
{
  "client": "arcreel",
  "mode": "create",
  "idempotency_key": "arc-bootstrap-uuid",
  "dry_run": false
}
```

CaMeL derives the user id from the bearer token. The request does not accept user id, model ids, token names, or token group from ArcReel as trusted values. CaMeL must verify that the bearer token was issued to the ArcReel OAuth client and includes `arcreel:token-provision`.

Successful response:

```json
{
  "success": true,
  "tokens": [
    {
      "media": "video",
      "name": "camel-arcreel-123-video",
      "key": "sk-...",
      "group": "default",
      "model_limits": ["doubao-seedance-2-0-260128"]
    }
  ]
}
```

Conflict response:

```json
{
  "success": false,
  "error": "token_name_conflict",
  "conflicts": [
    {
      "media": "video",
      "name": "camel-arcreel-123-video",
      "delete_url": "https://camel-hub.com/console/token?keyword=camel-arcreel-123-video"
    }
  ]
}
```

Provisioned CaMeL token requirements:

| Field | Requirement |
|-------|-------------|
| `name` | `camel-arcreel-{camel_user_id}-{media}` |
| `hidden` | `false` |
| `source_client` | `arcreel` or equivalent persistent marker. |
| `source_media` | `image`, `text`, `video`, or `audio`. |
| `model_limits_enabled` | `true` |
| `model_limits` | Server-side ArcReel allowlist for the media type only. |
| `group` | Server-side `CAMEL_ARCREEL_TOKEN_GROUP`. |
| `expired_time` | Deployment default for ArcReel bootstrap tokens. |
| `unlimited_quota` | Deployment policy; recommended `true` when quota is controlled by CaMeL group policy. |

In `mode=create`, the CaMeL endpoint checks conflicts before creating any token. If one of the four names already exists, it creates none of them and returns conflict links.

In `mode=repair`, the CaMeL endpoint creates missing ArcReel-managed tokens and rotates existing ArcReel-managed tokens. It must not rotate a same-name token unless that token carries the ArcReel source marker.

## User-Owned State

The following state is scoped by `CurrentUserInfo.id`:

| Area | Scope Requirement |
|------|-------------------|
| Projects and project files | Every project operation uses the current user's project namespace. Same visible project name is allowed under different users. |
| Tasks and task events | Task rows carry `user_id`; event queries join tasks or use user-aware repository methods. |
| API keys | API keys are created, listed, verified, and deleted by owner. |
| Usage | API call records carry `user_id`; usage summaries filter by owner. |
| Agent sessions | Session summaries, entries, and event logs filter by owner. |
| Global asset library | Asset rows and uploaded global asset files are owned by user. |
| Built-in provider config | Provider config and credentials resolve by user. |
| Custom providers | Provider rows, model rows, discovery, default model selection, and deletion resolve by user. |

## Deployment-Global State

These remain global:

| Area | Reason |
|------|--------|
| Database connection, migrations, queue worker lease, CORS, logging, sandbox availability | Deployment infrastructure, not user preference. |
| Provider registry definitions and endpoint catalogs | Static capability catalog shared by all users. |
| Worker capacity defaults | Deployment-level throughput controls. |

## Frontend Contract

In `mode="camel"`:

- `/login` shows only the CaMeL login button.
- `/login` displays legal/source links before authentication, including the `Powered by ArcReel — https://github.com/ArcReel/ArcReel` NOTICE attribution and the configured source URL for this modified deployment.
- `/login/callback` consumes `#access_token` and redirects to the `from` path.
- Local username/password inputs are hidden.
- Local password creation, password reset, email mutation, and local account mutation entry points are hidden or absent.
- Existing `Authorization: Bearer` request behavior remains unchanged after the token is stored.
- The first-login bootstrap modal calls `POST /api/v1/camel/bootstrap/start-url?mode=create`, then navigates to the returned `authorization_url`.
- The personal settings page includes a CaMeL key repair button that calls `POST /api/v1/camel/bootstrap/start-url?mode=repair`, then navigates to the returned `authorization_url`.
- The About/Legal section displays the same frontend legal config data as the login page.
- The UI must preserve ArcReel attribution without presenting this deployment as the official ArcReel service unless trademark permission is obtained.

## CaMeL Provider App Registration

ArcReel needs a registered CaMeL OAuth provider app with a redirect URI matching `CAMEL_OAUTH_REDIRECT_URI` exactly.

Recommended CaMeL master environment for ArcReel:

```bash
CAMEL_OAUTH_ARCREEL_NAME="ArcReel"
CAMEL_OAUTH_ARCREEL_REDIRECT_URI="https://arcreel.example.com/api/v1/auth/camel/callback"
CAMEL_OAUTH_ARCREEL_SCOPES="profile email"
CAMEL_OAUTH_ARCREEL_BOOTSTRAP_SCOPES="profile email arcreel:token-provision"
```

CaMeL Chat keeps the legacy `CAMEL_OAUTH_SEED_*` variables. ArcReel uses the dedicated `CAMEL_OAUTH_ARCREEL_*` namespace so both clients can be registered without deleting or rotating the existing Chat app.

## Error Handling

| Case | Behavior |
|------|----------|
| Missing OAuth config | `auth/status` reports no usable provider; login page shows a configuration error. |
| Invalid state | Callback returns `400` and does not issue a token. |
| CaMeL token exchange failure | Callback returns `502` or redirects to login with an auth error. |
| Userinfo failure | Callback returns `502` or redirects to login with an auth error. |
| Disabled local login endpoint | `POST /api/v1/auth/token` returns `403` or `404` in CaMeL mode. |
| Missing `arcreel:token-provision` scope | Bootstrap or repair callback fails before any local provider mutation. |
| CaMeL user mismatch in bootstrap or repair callback | Callback fails before provisioning and no local providers are created. |
| CaMeL token conflict | Bootstrap or repair result returns conflict names and CaMeL token-management links; no local providers are created or updated. |
| Local provider creation failure after CaMeL token creation | Bootstrap remains incomplete and the response returns deletion links for the generated CaMeL token names. |

## Verification Matrix

| Scenario | Expected Result |
|----------|-----------------|
| User A and User B create project `demo` | Each user sees only their own `demo`. |
| User A creates a custom Seedance provider | User B cannot list, select, or use it. |
| User A configures `https://api.camel-hub.com/api/v3` for Seedance | User B provider config remains unchanged. |
| New CaMeL user accepts bootstrap | ArcReel creates exactly four user-owned custom providers and CaMeL creates four visible restricted tokens. |
| Bootstrap sees `camel-arcreel-123-video` already in CaMeL | ArcReel shows the CaMeL token link and does not create local providers. |
| User clicks repair keys in personal settings | ArcReel sends the user through CaMeL re-auth and updates only ArcReel-managed keys/providers. |
| Bootstrapped user uses Seedance video | ArcReel calls the Seedance endpoint through the configured base URL without requiring manual `/api/v3` in the provider base URL. |
| User A enqueues video generation | The task row and SSE events are visible only to User A. |
| User A creates an ArcReel API key | The key authenticates as User A and cannot manage User B resources. |
| Anonymous user opens login page | Legal links show AGPL-3.0, NOTICE, upstream ArcReel attribution, and current deployed source URL. |
| Authenticated user opens About/Legal | Legal links match the login page and include the current modified-source location. |
| Source URL missing in public deployment config | About/Legal shows a compliance warning and backend emits a startup warning. |
