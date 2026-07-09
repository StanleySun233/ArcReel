# Frontend Sprint Progress: Lena

**Engineer:** Lena
**Story:** Story 3 - AGPL License And Source Compliance
**Story Branch:** story/camel-oauth-user-isolation/license-compliance
**Story Worktree:** ../ArcReel-worktrees/camel-oauth-user-isolation/license-compliance
**File Ownership:** frontend/src/config/legal.ts, frontend/src/components/legal/LegalLinks.tsx, frontend/src/pages/LoginPage.tsx, frontend/src/components/pages/settings/AboutSection.tsx, frontend/src/i18n/*/dashboard.ts

## Acceptance Criteria

- The service explicitly states that this deployment is a modified ArcReel deployment offered free of charge with CaMeL as the API relay; no paid access or commercial API resale is introduced by this story, and free access does not remove AGPL-3.0 obligations.
- The login page shows legal/source links before authentication, including `Powered by ArcReel — https://github.com/ArcReel/ArcReel` and a link to the current deployed source.
- The authenticated About/Legal section shows the same legal/source links and preserves the upstream ArcReel repository link required by NOTICE.
- The legal UI states that ArcReel is provided without warranty, users may receive and convey the covered work under AGPL-3.0, and the full license is available through the visible license link.
- The UI marks the deployment as a modified version and does not imply the deployment is the official ArcReel service unless trademark permission is obtained; if rebranded, attribution remains visible and unmodified.
- Missing deployed source configuration is visible as a compliance warning on the About/Legal surface.

## Subtasks

- [x] Add frontend legal config in `frontend/src/config/legal.ts` backed by `VITE_ARCREEL_LEGAL_*` variables with safe upstream defaults, modified-version notice, modified date, and source configured status.
  - Commit: 606e0dc
- [x] Add reusable legal links component backed by frontend legal config, including upstream attribution, deployed source, license, NOTICE, no-warranty notice, AGPL conveyance notice, modified-version statement, and free CaMeL API relay statement.
  - Commit: 8507fa7
- [ ] Add unauthenticated login-page legal/source links.
  - Commit: blocked pending Story 1 frontend integration
- [x] Update About/Legal section with current deployed source, AGPL license link, NOTICE link, no-warranty/AGPL-rights notice, modified-version statement, free-service/API-relay statement, and upstream attribution.
  - Commit: 9e4ca2f

**Ready for QA:** no

## Blockers

| Date | Subtask | Blocker | Status |
|------|---------|---------|--------|
| 2026-07-09 | Public source link copy | Final deployed source URL is not known until deployment branch or commit is selected. | pending |
| 2026-07-09 | LoginPage legal links | Waiting for Story 1 frontend integration before serially editing `frontend/src/pages/LoginPage.tsx`. | pending |
