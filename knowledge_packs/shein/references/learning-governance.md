# SHEIN incremental learning governance

## Provenance layer versus lifecycle status

Every evidence item carries both fields. `provenance_layer` uses `official_current`, `verified_software_observation`, `multi_source_practice`, `single_case`, `historical_trace` or `unknown`. `status` continues to use the versioned machine-contract lifecycle enum. This avoids creating two conflicting knowledge stores: provenance answers where the evidence came from; lifecycle answers whether it is live, time-sensitive, historical, draft, failed, unknown or owner-blocked.

- `official_current` may map to `time_sensitive_evidence` or a store-scoped `verified_live_fact`.
- `verified_software_observation` may record a successful read, a failed attempt or a historical trace; a transient page response is never business completion.
- `multi_source_practice` requires three independent sources and remains `draft`/cross-source hypothesis.
- `single_case` never becomes a universal rule.
- `historical_trace` preserves dated operator evidence without overriding current state.
- `unknown` maps to `unknown` or `blocked_owner_input`.

This is the operating protocol for continuous expert training. It is a T One governance rule, not evidence about SHEIN platform behavior.

## Evidence-before-distillation gate

1. Resolve the matching `tenant_id`, `project_id`, `store_binding_id`, site, mode, ownership and execution identity.
2. If an authorized SHEIN identity exists, inspect that exact environment read-only. Otherwise use official public pages, lawful demos/sandboxes, and public community, video or GitHub material.
3. Record the software/browser version, canonical URL or content ID, capture time, site/mode scope, actions, real input/output, errors and permission boundary.
4. Distill only facts supported by newly captured or changed evidence. A cycle with no new evidence returns `no_increment_recorded`.
5. Stop before every external side effect or owner-only credential, MFA, identity, bank or billing action.

## Knowledge-package-first delta gate

1. Inventory the existing unique SHEIN Skill, contract, curricula, templates, checklists, evaluations, failure review, connector status and GitHub admission registry before searching.
2. Spend at least half of each cycle discovering, auditing, comparing and deduplicating already-distilled SHEIN-specific packages: licensed SDK/sample repositories, ERP mappings, public playbooks/SOPs/checklists, schemas, prompts and evaluation sets. Generic official introductions are limited to ten percent; current official policy/API deep pages used for targeted validation are not generic introductions.
3. For each candidate record name/URL/owner, version or commit and capture time, release/changelog, coverage, cited sources, license, maintenance, issues/PR/security, executable-code and credential/telemetry/data risks, dependencies/deployment cost, T One overlap and `platform + country/site + store_mode + ownership` scope.
4. Candidate dispositions are only `keep_reuse`, `merge_into_existing`, `extract_rules_only`, `research_only`, `rejected_stale`, `rejected_license` and `rejected_unsafe`. Unknown license, unclear identity, unsafe logging/transport, stale APIs or missing maintenance/security paths prohibit installation or commercial code reuse.
5. Compare two or three candidates per topic when available. Sample one core workflow, one failure boundary and three key rules. Verify only the volatile differences against directly relevant current official deep pages, then merge only the net delta into the existing assets.
6. Proprietary public guides may be paraphrased as `extract_rules_only`; do not copy whole documents, assets or code. Package discovery, a passing test or a vendor's connected-product claim never proves a T One connector or live business outcome.

### Hard review acceptance

- Every candidate is exactly `candidate_screened`, `opened_not_reviewed`, `fully_reviewed` or `blocked`; only `fully_reviewed` sources can support distillation.
- At least 70% of each cycle's recorded evidence effort must directly serve SHEIN sites/modes, category/dynamic schema, product/price/activity, inventory/fulfillment, order/after-sales, ads/native AI or developer APIs. Tool/AI research is capped at 20%; cross-platform reference is capped at 10% and requires an explicit SHEIN migration hypothesis. Mark unrelated material `irrelevant_skip`.
- A web source needs at least 90% segmented coverage, footer evidence and a relevant second-level page, pagination page or explicit blocked-secondary-page record. For infinite scroll, trigger at least three new loads and record the stop reason.
- An official document review records navigation, update/What's New state, FAQ, limits, permission/auth scope, examples, errors and directly related SDK/GitHub surfaces; an absent surface is recorded as absent.
- A video of ten minutes or less needs at least 95% playback or 95% permitted-caption coverage plus opening/core/ending checks. A longer video needs complete captions/chapters plus opening, three core segments and ending checks; without captions it requires complete playback. Otherwise it is `opened_not_reviewed` and contributes no rule.
- When comments exist, inspect at least ten rendered comments or all if fewer, including available pinned/high-relevance/latest, follow-up, author reply, disagreement and failure views. Record missing sort/reply controls rather than inventing coverage.
- Every cycle states `no_delta=true|false`; `true` is mandatory when no new external evidence or valid distillation exists.

## Source rotation and duplicate control

- Before reopening an official page, compare its canonical URL, title, publication/update date, `Last-Modified` when exposed, and content hash with the source ledger. Skip unchanged content and record it in `duplicate_skips`.
- Each evidence-bearing cycle must include at least one first-party source and one lawful supplemental source class from public community, permitted video/transcript, or GitHub. If a source is login-, region-, payment- or permission-blocked, record the block and rotate to another lawful class. Do not bypass access controls.
- Do not run consecutive evidence-bearing cycles against only the same official host unless another allowed source class is unavailable and the reason is recorded.
- Seller or creator experience begins as a dated anecdote. Three genuinely independent sources may justify a cross-source hypothesis, but never override official rules or replace store-scoped validation.

## Source record

For every source store:

```json
{
  "canonical_url": "https://example.invalid/item",
  "platform_content_id": "unknown_if_absent",
  "title": "source title",
  "author_or_owner": "publisher",
  "published_at": "unknown_if_absent",
  "captured_at": "ISO-8601 with timezone",
  "content_sha256": "sha256_of_captured_normalized_content",
  "language": "language tag",
  "country_site": "site scope or global_public",
  "commerce_mode": "mode scope or unknown",
  "ownership": "ownership scope or unknown",
  "license_or_access_basis": "official_public|public_quote_summary_only|permitted_transcript|repository_license|owner_authorized",
  "evidence_level": "first_party|independent_secondary|dated_anecdote|research_candidate",
  "review_at": "date or trigger",
  "supersedes": "prior evidence id or null"
}
```

Do not retain protected images, video, music, private messages, customer material, secrets or bulk personal data as training evidence.

## Knowledge lifecycle

- Preserve multiple sources as an evidence graph; do not concatenate source texts into a new authority.
- Distill `stable_rule`, `time_sensitive_evidence`, `counterexample`, `applicability_conditions` and `expiry_conditions` separately.
- A newer official rule marks the older record `superseded` or `expired`; it does not erase the evidence chain.
- Weekly: merge synonyms, detect conflicts, attach counterexamples and review failed attempts.
- Monthly: recheck stale rules, failed/removed tools, connector truth and regression coverage.

## Source-specific boundaries

- Video: prefer platform-permitted captions or transcripts. Download only owner-authorized material when platform terms allow it; never bypass DRM, login, CAPTCHA or anti-bot controls.
- Public social/community: summarize claims and retain attribution; do not copy protected media, buyer assets, private groups or personal datasets.
- GitHub: consult `config/github_capability_registry.json` first. Verify repository ownership, license, maintenance, dependencies, security and data boundaries. Unknown candidates remain `research_only` and are not installed automatically.
- “Anti-association” requests are limited to compliant per-store identity stability and authorization isolation; evasion of platform controls is `rejected_unsafe`.

## Required cycle output

Every cycle reports, in order:

1. `deviation_check`
2. `checked_software_and_pages`
3. `candidate_screened`
4. `opened_not_reviewed`
5. `fully_reviewed`
6. `blocked`
7. `no_delta_truth`
8. `duplicate_skips`
9. `new_facts`
10. `superseded_or_expired_knowledge`
11. `multi_source_conflicts`
12. `distilled_skill_rules_evaluations`
13. `t_one_reuse_or_extension`
14. `authorization_blocks`
15. `next_source_class`

Classify each capability change as `reuse_existing`, `extend_existing`, `research_only`, `blocked_connector` or `rejected_unsafe`. A page, button, report, test pass or drafted payload is never a completed business action.
