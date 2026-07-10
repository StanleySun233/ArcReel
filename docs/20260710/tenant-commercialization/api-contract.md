# API Contract: Tenant Commercialization

**Date:** 20260710
**Status:** draft

## Contract Rules

- Business APIs infer tenant from the current tenant access token.
- Business APIs do not trust role or tenant id from request bodies.
- `tenant_role` in JWT responses is UI display data only.
- Backend authorization always checks Redis/PG permission state.
- Frontend may pass a target `tenant_id` only to the tenant-token switch endpoint.
- File APIs expose `file_id`, never MinIO object keys.

## Auth And Tenant Selection

### GET `/api/v1/auth/status`

Returns auth mode and provider list. In commercial tenant edition, `AUTH_MODE=camel` is the supported product mode.

### GET `/api/v1/auth/camel/start`

Query:

```text
from=/app/projects
```

Starts CaMeL OAuth. On success, callback creates/updates ArcReel user, ensures personal tenant exists, and signs a token for the personal tenant.

### GET `/api/v1/auth/camel/callback`

Query:

```text
code=...
state=...
```

Uses signed state cookie, exchanges code with CaMeL, reads userinfo, upserts user, creates personal tenant if missing, and redirects to:

```text
/login/callback#access_token={tenant_access_token}&from={safe_return_path}
```

### GET `/api/v1/auth/me`

Headers:

```text
Authorization: Bearer {tenant_access_token}
```

Response:

```json
{
  "user": {
    "id": "camel:123",
    "username": "alice",
    "provider": "camel"
  },
  "tenant": {
    "id": "ten_...",
    "name": "alice的个人空间",
    "role": "admin",
    "is_owner": true,
    "personal": true
  }
}
```

### GET `/api/v1/auth/tenants`

Returns tenants the current user can enter.

Response:

```json
{
  "tenants": [
    {
      "id": "ten_personal",
      "name": "alice的个人空间",
      "role": "admin",
      "is_owner": true,
      "personal": true
    },
    {
      "id": "ten_team",
      "name": "Studio Team",
      "role": "member",
      "is_owner": false,
      "personal": false
    }
  ]
}
```

### POST `/api/v1/auth/tenant-token`

Request:

```json
{
  "tenant_id": "ten_team"
}
```

Behavior:

- Backend verifies current `user_id` has membership in `tenant_id`.
- Backend signs a new tenant access token.
- Backend includes current role snapshot for UI only.

Response:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "tenant": {
    "id": "ten_team",
    "name": "Studio Team",
    "role": "member",
    "is_owner": false,
    "personal": false
  }
}
```

### POST `/api/v1/auth/refresh-current-tenant`

Refreshes current tenant token after stale-role 403 or explicit frontend refresh.

Response:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "tenant": {
    "id": "ten_...",
    "name": "Studio Team",
    "role": "view",
    "is_owner": false,
    "personal": false
  }
}
```

If the user no longer belongs to the current tenant, backend returns:

```json
{
  "error": "TENANT_ACCESS_REVOKED",
  "fallback_tenant_id": "ten_personal"
}
```

## Tenant Management

### POST `/api/v1/tenants`

Creates a new non-personal tenant. Any active user may create a tenant.

Request:

```json
{
  "name": "Studio Team"
}
```

Response:

```json
{
  "id": "ten_...",
  "name": "Studio Team",
  "owner_user_id": "camel:123",
  "role": "admin",
  "is_owner": true
}
```

### GET `/api/v1/tenant`

Returns current tenant detail.

### PATCH `/api/v1/tenant`

Requires `admin`. First version allows name change only.

Request:

```json
{
  "name": "New Team Name"
}
```

## Tenant Members

All member APIs operate on the current token tenant.

### GET `/api/v1/tenant/members`

Requires `view+`.

Response:

```json
{
  "members": [
    {
      "user_id": "camel:123",
      "username": "alice",
      "role": "admin",
      "is_owner": true
    }
  ]
}
```

### GET `/api/v1/tenant/users/search`

Requires `member+`. Searches activated ArcReel users.

Query:

```text
q=alice
```

Response:

```json
{
  "users": [
    {
      "id": "camel:456",
      "username": "alice2"
    }
  ]
}
```

### POST `/api/v1/tenant/members`

Requires:

- owner to add `admin`
- `admin` to add `member` or `view`
- `member` to add `view`

Request:

```json
{
  "user_id": "camel:456",
  "role": "member"
}
```

### PATCH `/api/v1/tenant/members/{user_id}`

Changes role. Owner cannot be changed. Only owner may promote to `admin`.

Request:

```json
{
  "role": "view"
}
```

### DELETE `/api/v1/tenant/members/{user_id}`

Removes a member. Owner cannot be removed.

## Files

### POST `/api/v1/files`

Uploads a media artifact through backend. Requires `member+` unless called by an internal service.

Multipart fields:

```text
file
alias
purpose
```

Response:

```json
{
  "file_id": "fil_...",
  "alias": "cover.png",
  "mime_type": "image/png",
  "size_bytes": 12345
}
```

### GET `/api/v1/files/{file_id}/signed-url`

Returns a short-lived URL after verifying current user can access a resource referencing the file.

Response:

```json
{
  "file_id": "fil_...",
  "url": "https://...",
  "expires_in": 300
}
```

### DELETE `/api/v1/files/{file_id}/links/{link_id}`

Internal or admin-only cleanup endpoint if needed. Deleting a link does not delete the MinIO object immediately.

## Projects

### GET `/api/v1/projects`

Lists projects in current tenant.

### POST `/api/v1/projects`

Requires `member+`. Creates a project registry row and local tenant project directory.

Request:

```json
{
  "name": "demo",
  "content_mode": "narration",
  "generation_mode": "image_to_video"
}
```

### GET `/api/v1/projects/{project_name}`

Returns `project.json` content. Media references remain as `file_id`.

### PATCH `/api/v1/projects/{project_name}`

Requires `member+`. Updates project JSON through existing validation, with file-id-only schema.

## Asset Libraries

### GET `/api/v1/assets`

Query:

```text
library=tenant|personal
type=character|scene|prop
```

### POST `/api/v1/assets`

Creates asset in current tenant library or personal library.

Request:

```json
{
  "library": "tenant",
  "type": "character",
  "name": "Hero",
  "description": "...",
  "image_file_id": "fil_..."
}
```

### POST `/api/v1/assets/import`

Creates a snapshot asset and binding in target library.

Request:

```json
{
  "source_binding_id": "ab_...",
  "target_library": "tenant"
}
```

### POST `/api/v1/assets/{binding_id}/sync`

Manual sync from `parent_binding_id`. Requires target write permission and source read permission.

Request:

```json
{
  "confirm_overwrite": true
}
```

## Provider Configuration

Existing provider/config/custom-provider/agent credential endpoints keep their paths but become current-tenant scoped. They do not accept `tenant_id` in request bodies.

Affected endpoints:

- `/api/v1/system-config`
- `/api/v1/providers`
- `/api/v1/custom-providers`
- `/api/v1/api-keys`
- `/api/v1/agent/*`

## Tasks

Task APIs remain current-tenant scoped:

- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`
- `POST /api/v1/tasks/{task_id}/cancel`
- task SSE endpoints

Generation endpoints persist `tenant_id` and `requested_by_user_id` at enqueue time.

## Error Codes

Common error response:

```json
{
  "detail": {
    "code": "PERMISSION_DENIED",
    "message": "..."
  }
}
```

Codes:

- `PERMISSION_DENIED`
- `TENANT_ROLE_STALE`
- `TENANT_ACCESS_REVOKED`
- `TENANT_NOT_FOUND`
- `MEMBER_NOT_FOUND`
- `OWNER_CANNOT_BE_REMOVED`
- `OWNER_CANNOT_BE_DOWNGRADED`
- `FILE_ACCESS_DENIED`
- `FILE_NOT_FOUND`
- `ASSET_SYNC_SOURCE_UNAVAILABLE`
- `PROJECT_SCHEMA_REQUIRES_FILE_ID`
