# Google Ads official-evidence routing

Use the canonical records in `config/platform_expert_training/advertising_media_buyer/evidence_index.json`.

## Current public evidence observed on 2026-07-18

- `GOOGLE-001`: official PMax API guide, updated 2026-07-13 UTC, requires conversion tracking and documents CampaignBudget, Campaign, AssetGroups, and AssetGroupAssets.
- `GOOGLE-002`: the public developer Page Summary control returned five document-summary bullets after a click. This is not account automation.
- `GOOGLE-003`: the navigation advertised generative asset creation as closed beta, while the linked page returned HTTP 404. Inputs, outputs, eligibility, and edit/submit boundaries remain unknown.
- `GOOGLE-004`: API identity requires OAuth, developer token, customer context, and manager context where applicable.
- `GOOGLE-005`: experiments require a hypothesis; overlapping experiments can interfere.
- `GOOGLE-006`: current OAuth security guidance requires owner-controlled 2SV for new refresh-token authorization.
- `GOOGLE-007`: the current Enhanced Conversions settings page says Google Ads began accepting website-tag, Data Manager, and API user-provided data simultaneously in April 2026, combined web and leads into one switch in June 2026, and moved offline/enhanced-leads uploads to the Data Manager API on 2026-06-15. Treat old Google Ads API leads samples as superseded unless a dated legacy allowlist is verified.
- `GOOGLE-008`: the current online-click conversion API guide keeps web enhancement as a distinct `WEBPAGE` workflow: the original tag records the conversion, the API adds hashed first-party data within 24 hours using `order_id`, each `UserIdentifier` sets one oneof member, and uploads use partial failure. A successful response is not proof of attribution.
- `GOOGLE-009`: Consent Mode v2 is a separate data-use gate. `ad_user_data=denied` disables enhanced-conversion hashed first-party data; defaults must precede measurement commands, updates must follow user choices and revocation, and hashing does not replace consent or data-processing terms.
- `GOOGLE-010`: current Google Ads API prose and the 2026-07-14 Data Manager formatting guide agree that only Gmail/Googlemail local parts lose periods and the full plus suffix; other domains retain periods and plus suffixes. The current Python SDK sample conflicts with this rule by stripping `.` and `+` for every domain without removing the suffix, so do not copy its helper without domain-specific regression tests.
- `GOOGLE-011`: offline-data diagnostics must be part of effect writeback. Track status, alerts, successful/failed/pending counts, conversion-action scope, and `job_id`; request acceptance, HTTP 200, or a generated report alone is not business completion.

## Review requirements

- Verify conversion tracking and conversion customer ownership before PMax.
- Bind OAuth, developer token, customer ID, optional login-customer-id, feed/merchant owner, country, and store/project route.
- Do not treat recommendations, Page Summary, or beta labels as owner-approved account changes.
- Review location explicitly; an unspecified PMax location can broaden coverage.
- Keep the unified Enhanced Conversions UI switch separate from implementation routes: `web_enhancement` uses a website tag plus `WEBPAGE`/`order_id`, while current lead/offline event ingestion uses the Data Manager API and `UPLOAD_CLICKS` destinations.
- Bind conversion customer, login customer, developer-token owner, OAuth owner, website/GTM owner, and consent source to the tenant/project/store route before any user-data upload.
- Block enhanced-conversion user data when `ad_user_data` is denied or unknown; SHA-256 hashing is not an authorization signal.
- Do not copy the current Python email-normalization sample. Test Gmail/Googlemail plus-suffix removal and preservation of dots/plus suffixes for other domains.
- Treat partial-failure and diagnostics review as required writeback, not optional troubleshooting.
