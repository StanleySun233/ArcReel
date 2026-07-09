# Backend Sprint Progress: Noah

**Engineer:** Noah
**Story:** Story 1 - CaMeL OAuth Login And User Identity
**Story Branch:** story/camel-oauth-user-isolation/camel-auth
**Story Worktree:** ../ArcReel-worktrees/camel-oauth-user-isolation/camel-auth
**File Ownership:** server/auth.py, server/routers/auth.py, server/services/*auth*, lib/db/models/user.py, server/routers/api_keys.py, lib/db/repositories/api_key_repository.py

## Acceptance Criteria

- ArcReel exposes a CaMeL OAuth start endpoint and callback endpoint under `/api/v1/auth`.
- The callback exchanges the authorization code with CaMeL, reads `/api/oauth/provider/userinfo`, upserts the local ArcReel user, and issues an ArcReel JWT containing the real `user_id`.
- The callback never persists the CaMeL OAuth credential and never exposes it in the ArcReel JWT, URL fragment, or browser storage.
- The callback supports OAuth state intent dispatch for regular login, provider bootstrap, and provider repair.
- `CurrentUserInfo.id` reflects the local CaMeL-derived user id instead of `default`.
- Local username/password login, password generation, create-password, and local-account mutation controls are disabled in CaMeL auth mode.
- API key Bearer auth resolves the owning user id from the API key row.

## Subtasks

- [ ] Add CaMeL OAuth backend settings and helpers.
  - Commit: pending
- [ ] Add auth start/callback routes and state validation.
  - Commit: pending
- [ ] Upsert CaMeL users and sign JWTs with real `user_id`.
  - Commit: pending
- [ ] Add OAuth state intent dispatch without persisting CaMeL access tokens.
  - Commit: pending
- [ ] Disable local password login in CaMeL mode.
  - Commit: pending
- [ ] Resolve API key Bearer auth to the persisted owner.
  - Commit: pending
**Ready for QA:** no

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
