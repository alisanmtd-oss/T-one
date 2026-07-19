# Independent Commerce incremental curriculum

Checked: 2026-07-18 (+08:00)

This curriculum is a set of small evidence-backed modules, not a universal prompt. Every run starts from a new page, software, API, or authorized-store observation recorded in `../state/browser_evidence_2026-07-18.json`. If a run has no new visible evidence, it must not create a new rule or lesson.

## Module 0 — Evidence and execution identity

- Input: route, execution identity, connector truth, official page or authorized software.
- Practice: record URL/version, capture time, country/site, store mode, ownership, clicks/scrolls/inputs/outputs/errors and permission boundary.
- Output: one of `verified_live_fact / time_sensitive_evidence / historical_operator_trace / draft / failed_attempt / unknown / blocked_owner_input`.
- Pass: public documentation is never described as a live store read; store facts require an authorized store response.
- Evidence: `IC-BR-001`, `IC-UN-001`.

## Module 1 — Route, OAuth and store isolation

- Shopify: bind shop domain, app installation, scopes and API version.
- WooCommerce: bind site base URL, WordPress user, REST permission, WooCommerce/WordPress/plugin/theme versions, pretty-permalink readiness, HPOS authoritative/backup datastore, synchronization state and incompatible plugins. Do not depend on direct posts/postmeta reads or sync-on-read.
- BigCommerce: bind `store_hash`, API account type, scope set and channel/storefront.
- Adobe Commerce: first branch by PaaS/on-prem versus SaaS, then bind store view or SaaS tenant/store header.
- Salla: bind partner app, merchant installation and scopes; serialize single-use refresh-token rotation.
- Zid: bind authorization token plus store-specific identity, but use endpoint-family authentication metadata instead of assuming one header template.
- Pass: a credential reference cannot be routed to another store; write scope never removes the action approval gate.
- Evidence: `IC-AD-001`, `IC-SA-001`, `IC-SA-002`, `IC-ZI-001`, `IC-ZI-002`, `IC-ZI-004`, `IC-WC-001`, `IC-WC-002`, `IC-WC-003`.

## Module 2 — Product/PIM and content truth

- Enforce four layers: platform common, category capability, tenant/project/product, and task evidence. Product values never move upward or sideways between tenants, products, stores, or tasks.
- Preserve product identity, type/class, parent-child or variant model, localized fields, SKU/barcode/GTIN, price/cost, taxability, shipping need, rights and channel assignment.
- Read the current platform category schema before choosing fields. Cover apparel, home/living, beauty, electronics, food/restricted goods, digital goods, services/bookings, and machinery with their own variation, compliance, logistics, claims, and advertising constraints.
- Treat physical, digital, service, booking, voucher/code and grouped/bundle types as different delivery contracts.
- Platform AI may draft copy, images or metadata, but product facts and media rights remain source-controlled.
- Pass: missing product facts remain unknown; AI text never invents specifications, compliance, origin, stock or delivery; open-source output contains no private_tenant private fixture.
- Evidence: `IC-SA-003`, `IC-ZI-004`, `IC-BC-003`, `IC-SH-002`.

## Module 3 — CMS, SEO, search and merchandising

- Audit navigation, content ownership, structured metadata, localization, accessibility, search, facets, synonyms and merchandising rules.
- Adobe Live Search is learned as an installed/configured SaaS feature with catalog/event data, not as a default property of every Commerce store.
- BigAI Copywriter is currently an English, v3 catalog draft tool according to the inspected official listing.
- Pass: an official feature page produces `time_sensitive_evidence`; only an entitled store proves actual installation, UI and result quality.
- Evidence: `IC-AD-003`, `IC-BC-003`, `IC-SH-002`.

## Module 4 — Checkout, payment, tax and privacy

- Collect entity, selling market, currency/presentment, registration, payment account, tax service, consent and product/delivery type.
- Model tax, duties, digital-service tax, OTA destination rules and payment capture/refund separately.
- Keep payment gateway/API privileges separate from store admin and advertising permissions.
- Pass: `GLOBAL` never produces a global tax, privacy, payment or consumer-law rule; professional/owner review is requested where required.
- Evidence: official tax/payment sources in `official-sources.md`; no live payment or tax account was authorized this cycle.

## Module 5 — Inventory, orders, webhooks and fulfillment

- Inventory is location/supplier/capacity/entitlement/slot-specific.
- Salla order reads use `orders.read` and documented sequential pagination behavior; product reads use `products.read`.
- Zid webhook conditions are not assumed for all events; current public evidence limits them to two order events.
- Every event consumer needs verification, idempotency, retry/dead-letter handling and reconciliation.
- Pass: no webhook or order record alone proves end-to-end sync, fulfillment, settlement or final state.
- Evidence: `IC-SA-004`, `IC-ZI-003`, Shopify/WooCommerce/BigCommerce webhook sources.

## Module 6 — Customer service, email and lifecycle

- Separate customer-data permission, support identity, email/SMS/WhatsApp provider, consent, template, suppression and send state.
- Draft campaigns, discount logic and service replies without sending.
- Shopify Campaign Autopilot settings may permit platform automation, but T One retains explicit confirmation for activation, budget, send and stop actions.
- Pass: draft/pending/approved/active/completed/stopped are distinct states and require post-action evidence.
- Evidence: `IC-SH-003`.

## Module 7 — External acquisition and attribution

- Produce a versioned landing-page/feed/event/consent brief for Meta, Google and TikTok Ads.
- Bind business/account/advertiser identities, OAuth, billing and measurement separately from the commerce store.
- Record attribution window, profit model, stop-loss, experiment design and cross-channel deduplication.
- Pass: pixel, tag, app, feed, catalog or channel button is not writable ad-account authorization.
- Evidence: official external-channel sources; current connectors remain unconnected.

## Module 8 — Vertical fulfillment and tax extensions

- DTC physical: stock location, ship-from, carrier, duties and returns.
- POD: design rights, blank/variant map, production site/SLA, reprint/refund and tracking.
- Dropshipping: supplier stock/price freshness, actual origin, customs, delivery and return destination.
- Digital: entitlement, license, access, delivery proof, refund and digital tax.
- Service: provider capacity, timezone, completion, reschedule/no-show and capture/payout.
- OTA: supplier contract, live slot, voucher, amendments, local fees/license, force majeure and settlement.
- Pass: shared catalog fields may be reused, but delivery, tax, capacity and refund semantics are never collapsed.
- Evidence: `vertical-extensions.md`, Salla/Zid product-type evidence.

## Module 9 — Platform-native AI and MCP safety

| Surface | Verified public behavior | Current T One state | Required gate |
|---|---|---|---|
| Shopify Sidekick / Campaign Autopilot | Drafts and reviews content/actions; some merchant permissions can broaden automation | `research_only` | Authorized store, role/plan check, draft-only test, confirm every external mutation |
| Adobe Live Search / Product Recommendations | AI/ML search, reranking and recommendations after service setup/data sync | `research_only` | Entitlement, extension/config, store view, data/event health and metric validation |
| Adobe Developer AI Assistant | Documentation beta; first tested answer failed | `research_only` | Treat output as draft and open every cited official source |
| BigAI Copywriter | English v3 product-editor draft generator with review disclaimer | `research_only` | Store compatibility, app install, product-fact input, human QA, separate save/publish confirmation |
| BigAI Product Recommendations | Closed beta, Enterprise, GCP billing/data/analytics requirements | `research_only` | Waitlist/plan, billing approval, data consent, model and storefront test |
| Salla Partners MCP | Operates Partner Portal apps/settings/scopes; not merchant store runtime | `blocked_connector` | Partner ownership, OAuth, least privilege and per-action approval |
| Zid AI Connector MCP | Official listing claims full store-management tool surface | `blocked_connector` | Store-owner install, scope inventory, secure link storage, read-only probe and per-write approval |
| Salla public AI prompts | Browser returned HTTP 403 | `failed_attempt` | Recheck without bypass or use an owner-authorized environment |

- Pass: platform documentation or an app listing never becomes `connected`; an AI draft never becomes saved/published; an MCP link with broad access is treated as a credential.
- Evidence: `IC-SH-001..003`, `IC-AD-002..004`, `IC-BC-001..003`, `IC-SA-005..007`, `IC-ZI-005`.

## Module 10 — Failure recovery

- Preserve the attempted action, exact error, impact, recovery and promotion rule.
- Recover only within normal access: refresh a snapshot, use a bounded read of the loaded page, follow an official link, or stop.
- Never recover by bypassing CAPTCHA, MFA, robots, rate limits, paywalls or account controls.
- Pass: every failed evidence path remains visible in `../state/failure_log.json` and cannot silently become a success claim.

## Module 11 — Incremental evaluation and automation

- Run fingerprint preflight from `../state/source_fingerprints.json`; unchanged canonical URL/version/hash goes to `duplicate_skips` and is not reopened for training.
- Rotate sources: include at least one first-party source and one community, permitted video/subtitle, or GitHub source. A blocked source is recorded and replaced with another lawful source.
- Store post/video/repository content ID, title, author, publish time, capture time, language, country/site, license and evidence level. Never download protected media or install an unadmitted repository.
- Keep single operator/blogger evidence as a dated anecdote. Three independent sources are the minimum for proposing a general experimental rule, and official evidence plus counterexamples still control its scope.
- Select only evidence newer than the stored watermark or a previously failed/unknown item that changed state.
- Update the smallest affected adapter/rule/evaluation; do not rewrite the entire expert.
- Generate regression cases only from observed rules or failures and include a falsifiable oracle.
- Run `python -m unittest -v tests.test_independent_commerce_expert_training`.
- Advance the watermark only after JSON validation and passing tests.
- Pass: a no-evidence run reports `no_new_evidence`; it does not fabricate a lesson.

Weekly maintenance merges synonyms, detects conflicts and adds counterexamples. Monthly maintenance rechecks expired rules, failed tools/connectors and evaluation coverage while retaining superseded evidence in a version chain.

> Private runtime paths, evidence, execution identities, and product records are intentionally excluded from this public pack.
