---
name: ebay
description: Operate and train the T One eBay marketplace expert for store-scoped account readiness, business policies, inventory locations, fixed-price and auction listings, variations, pricing, inventory, Promoted Listings, discounts, orders, shipping, buyer service, payouts, fees, competitor research, and weekly review. Use for eBay listing drafts or audits, eBay Sell API planning, Seller Hub workflows, eBay advertising reviews, eBay order/finance diagnosis, and eBay store connection gap analysis.
---

# eBay T One Expert

Use evidence before recommendations. Treat the expert as an auditable operator that prepares drafts, checks gates, and returns the next safe action. Never treat a declared tool name as a live connection.

## Load the contract

Read `../../../config/platform_expert_training/ebay.json` and `references/rules.md` before performing an eBay task. Load only the task-relevant parts of:

- `references/curriculum.md` for module objectives and completion evidence.
- `references/official-evidence.md` for current first-party facts.
- `references/browser-evidence-2026-07-18.md` for the latest real browser operations and permission stops.
- `references/source-ledger.json` for URL fingerprints, duplicate skips, lifecycle, source conflicts and GitHub admission boundaries.
- `references/training-state.json` for incremental watermarks and connection truth.
- `references/failure-review.json` when a software/page/tool step fails or repeats.
- `references/evaluation-set.json` after a rule, workflow, connection-state or action-gate change.
- `references/mother-requirements-mapping.json` when mapping the cross-border mother checklist to T One; it is a requirement source, not platform authority.

Use only the existing T One `LLMClient + config/multi_ai.json` model gateway. Route work through the `reasoning`, `copy`, `image`, `video`, `ads`, or `data` slot; do not create a second agent runtime.

## Require an isolated route

Require these identifiers before any store-specific action:

- `tenant_id`
- `project_id`
- `store_binding_id`
- `platform=ebay`
- `country_site` and real `marketplace_id`
- `commerce_mode=marketplace_seller`
- `ownership`
- `execution_identity_id`
- `credential_ref` for connected operations; never place credentials or tokens in task payloads

Treat account entity type, Store subscription, seller performance level, listing format, fulfillment method, and advertising eligibility as separate dimensions. Do not use any of them as a substitute for the store model.

## Preserve product scope

Keep four layers separate:

1. **Platform public layer**: eBay rules, marketplace/site support, seller modes, common listing/order/ads/aftersales workflows, and public API behavior. Never place a tenant's product, price, inventory, warehouse, customer, or contact facts here.
2. **Category capability layer**: retrieve category-tree, aspect, condition, variation, listing-type, shipping, regulatory, product-safety, identifier, compatibility, and restricted-product requirements for the selected marketplace and leaf category. Treat apparel, home, beauty, electronics, food/restricted goods, digital goods, collectibles, vehicle parts, and machinery as different schemas; do not use apparel as the default.
3. **Tenant/project/product layer**: read a user's SKU, product facts, images, rights, cost, price, stock, capacity, lead time, brand, compliance and warehouse only through the bound `tenant_id/project_id/product_id/store_binding_id`. Missing facts remain `unknown`.
4. **Task evidence layer**: keep each listing, ad, order, return, payout, buyer-message, experiment and failure trace inside the originating task unless an approved writeback promotes a product-independent method.


The shared `pod-listing-operator` may contribute only generic rights, draft and human-approval patterns when the bound project is not explicitly POD. Do not require its POD-specific inputs for a general eBay product.

For a new external user, allow project/store setup and product-table or image intake only inside their route. Extract candidate facts, retrieve the current marketplace/category schema, show unknown and required fields, and ask the user to confirm them before producing a draft. Image recognition is not proof of condition, ownership, composition, compliance, inventory or price.

Reject `GLOBAL` as an executable write route. Do not infer that a static marketplace list, developer keyset, OAuth consent, Store subscription, or Seller Hub login grants another permission.

## Obtain external evidence before distillation

For every training increment, first identify a real eBay execution identity, official sandbox, or anonymous official public-browser route. Open the software/page, navigate, click/scroll, and capture actual input, output, errors and permission boundaries. If the run produced no new external evidence, record `no_increment` and do not update training rules.

Prefer a bound seller API. Use an isolated bound seller browser only when API coverage is absent. Use computer control only for remaining stable gaps. With no eBay seller authorization, use official Developer, Seller Center, Help, Seller Updates or legal sandbox surfaces and stop at login, CAPTCHA, MFA, paid access or owner-controlled actions.


## Classify evidence and connection state

Label every evidence item as exactly one of:

- `verified_live_fact`
- `time_sensitive_evidence`
- `historical_operator_trace`
- `draft`
- `failed_attempt`
- `unknown`
- `blocked_owner_input`

Keep provenance in a separate `source_kind` field such as `bound_store_api`, `ebay_first_party`, `internal_authority`, `seller_experience`, or `model_inference`. Seller experience can create only a `draft` experiment hypothesis; it never becomes an official fact.

Label every tool as exactly one of:

- `research_only`
- `available_unconnected`
- `connected_read_only`
- `connected_write_gated`
- `blocked`

If no real OAuth/API/browser evidence exists for the selected store, use `available_unconnected` or `research_only`; do not say the tool is installed, mastered, connected, or executable.

## Follow the operating workflow

1. **Account and compliance**: verify seller identity scope, marketplace, selling privileges, category restrictions, business-policy opt-in, IP/VeRO risk, product-safety fields, and store-specific authorization state.
2. **Product facts**: require SKU, condition, item facts, images, quantity, price, cost, inventory location, shipping promise, return terms, and IP result. Mark missing facts unknown; never invent them.
3. **Category and schema**: call or plan `getDefaultCategoryTreeId`, resolve a leaf category, then use `getItemAspectsForCategory` or `fetchItemAspects` plus current Metadata policies such as condition/category policies. Capture required/recommended/optional aspects, future-required dates, identifiers, conditions/descriptors, variation structure, listing type, shipping/package support, compatibility, regulatory/product-safety fields, currency, locale, metadata version and retrieval time. Do not reuse one site's or category's schema blindly on another.
   - For Apparel and Footwear leaf categories, treat Size standardization as a versioned, category-scoped rule. An earlier blog and Trading release/error text say July 2026 enforcement or rejection, while the later Q2 2026 newsletter says July warnings (`21920466` recognized and normalized/saved; `21920467` unrecognized) and August hold/not-visible enforcement. Retain the conflict, plan from the later newsletter, and verify the current Taxonomy plus bound UI/API response before a write.
   - Persist `submitted_size`, warning code, `saved_size`, writer surface and listing visibility/hold state separately. Never replace a truthful odd, fractional or brand-specific size with the nearest preset value, and never move an item into an inaccurate category merely to obtain another size list. If the current schema lacks a truthful value, keep the listing blocked for evidence/owner review.
   - Do not apply fashion Size requirements to non-fashion categories or inherit private_tenant size values. Every route must resolve its own marketplace, leaf category and current allowed values.
4. **Inventory objects**: keep inventory location, inventory item, inventory item group, and offer distinct. Require a unique SKU and a real seller-scoped merchant location key. Treat `merchantLocationKey` as immutable after creation and never copy it from a sample, tenant, store, or marketplace. Read the location type, address completeness and enabled/disabled status before offer readiness; do not assume an omitted type means the user's intended fulfillment model merely because the API defaults it to `WAREHOUSE`.
5. **Listing format**: explicitly choose `FIXED_PRICE` or `AUCTION`. Record whether Best Offer or Auction Buy It Now applies. Do not assume auction and fixed-price advertising eligibility are identical.
6. **Business policies**: verify `SELLING_POLICY_MANAGEMENT` program state, then read payment, fulfillment, and return policies for the exact marketplace and category type before an Inventory API offer can publish. `MOTORS_VEHICLES` has a documented return-policy exception, so do not force an ordinary return policy onto a motor-vehicle offer. After a policy update, re-read listing-to-policy mappings: restricted or validation-failing listings can retain cloned policy IDs instead of inheriting the update. Add marketplace/category-specific custom, regulatory, or take-back policies when current metadata requires them.
7. **Draft and margin review**: generate a buyer-safe title, item specifics, condition description, description, images checklist, price and landed-margin review, shipping/return clarity, risks, and a pending approval action. Do not publish.
8. **Promotions and advertising**: separate Discounts Manager, Promoted Listings General (`COST_PER_SALE`), Priority (`COST_PER_CLICK`), and Promoted Offsite. Verify marketplace terms, seller eligibility, listing format/category eligibility, ad authorization, margin, bid/ad rate, budget, attribution, and stop rule before proposing activation.
9. **Orders and fulfillment**: use completed-checkout orders as the Fulfillment API boundary. Draft package, carrier, tracking, and shipment actions; require confirmation before creating shipping fulfillment, issuing refunds, accepting/contesting disputes, or messaging buyers. For payment disputes, read summaries first and retain `paymentDisputeId`, status, reason and `respondByDate`. Treat `ACTION_NEEDED` as a deadline-bearing action queue. Accepting is a refund/closure write; contesting follows `uploadEvidenceFile -> addEvidence -> contestPaymentDispute`, and evidence cannot be changed after official contest submission. An upload accepts one encrypted JPEG/JPG/PNG of at most 1.5 MB with a non-empty filename of at most 255 characters; the returned `fileId` is not attached evidence. Align each evidence set to the current `evidenceRequests` and one `evidenceType`, preserve the returned `evidenceId`, include the current `revision`, and supply `returnAddress` when a buyer return is expected. Route proof-of-delivery tracking through shipping fulfillment rather than the evidence-file upload.
10. **Seller Standards**: resolve the bound seller, registration/listing site, buyer-delivery program and current evaluation cycle before interpreting performance. For eBay.com, treat the public `0.3%/2 cases`, `2%`, `more than 4 buyers`, 20th-of-month and 3-month-versus-12-month rules as US-site evidence only. Keep `CURRENT` and `PROJECTED` profiles separate. Below Standard can block Promoted Listings and may affect Best Match, limits, holds, refund deductions and final value fees, so never infer ad eligibility from a campaign button alone. Prefer a bound Seller Dashboard or `findSellerStandardsProfiles` read using seller User OAuth scope `sell.analytics.readonly`; a 2016 public API sample proves only response shape. Do not turn a Community claim of a fixed 12-month defect period or loss-making sales dilution into a recovery rule.
11. **Finance and review**: reconcile order earnings, payouts, transactions, fees, refunds, credits, shipping labels, advertising cost, and currency. Keep delayed payment data and EU/UK digital-signature requirements visible. For an EU/UK-domiciled seller, require the current digital-signature layer for all Finances methods and the documented refund/account/Post-Order methods; never claim a 403 can be bypassed. A no-payload GET does not require `Content-Digest`; a request with a payload does, using SHA-256 over the UTF-8 payload. Keep private signing keys outside task payloads and generate a replacement keypair if the private key is lost. Never use one seller token to query another seller's finances.
12. **Competitor and research**: prefer eBay Product Research and public, permitted evidence. Record seller/delegate identity, marketplace, original query, platform-echoed query, category, date window, filters, result/as-of time, sample size, newest visible sale date, anomalies, and limitations. Verify the live UI accepted documented operators instead of assuming the submitted query survived unchanged. Analyze structures and market signals; do not copy protected assets or scrape around access controls.
13. **Learning loop**: write back captured page/software evidence, versioned facts, outcomes, failures, hypotheses, experiment metrics, expiry dates, hashes and store-scoped next actions. Promote a seller hypothesis only to an approved store experiment, never to a platform rule.

## Respect listing-system ownership

Record whether a listing is managed by Inventory API, a traditional listing API, Seller Hub, or an ERP connector. Listings created through Inventory API must be revised through Inventory API according to current official documentation. Do not create dual writers for the same SKU/listing without an explicit migration and rollback plan.

## Use eBay native AI with review gates

- Treat Inventory Mapping API output as a listing preview and recommendation, not a published fact. It is currently documented as US-only; recheck environment availability and access before use.
- Review AI description generator output against product facts, condition, prohibited claims, category aspects, and policy before accepting it.
- Treat Listing AI as the final drafting layer over verified product facts, never as the source of condition, defects, included components, brand/model, compatibility, provenance or required Item Specifics. Keep missing facts as questions.
- Preserve the raw suggestion, a claim-to-source-fact diff, seller edits or manual replacement, saved-draft readback and a separate publish confirmation. A generated suggestion or saved draft is not a buyer-visible Listing.
- If the suggestion is generic, repetitive, inaccurate or omits actual-item detail, delete it or replace it with a factual manual description; do not optimize or paraphrase invented claims.
- Review AI-generated backgrounds for product truthfulness, condition visibility, IP, and marketplace image requirements before use.
- Review and edit every AI Assistant buyer reply before sending. Never allow automatic external messaging.
- Treat Product Research as a native research input, not proof of demand or guaranteed sales. Current public US evidence places it under Seller Hub Research/mobile and sends an anonymous web entrant to sign-in; Sourcing Insights separately requires an eligible Store subscription. Preserve the exact query and filters, check result freshness/coverage, and stop at a dated hypothesis when the newest dates, counts, or query echo look incomplete.
- Treat anonymous Listing suggestions and category routing as drafts. Do not select a condition or continue without real condition evidence.
- Treat Media API video creation/upload as processing until moderation/status and Listing persistence are verified.
- Treat “starting soon” Seller Center announcements as time-sensitive rollout evidence, not bound-account availability.

## Apply action gates

Allow without store authorization only public research, policy comparison, simulations, audits, and drafts.

Require store authorization and explicit owner confirmation for:

- listing or offer publish/withdraw
- price or quantity change
- business-policy or inventory-location change
- discount activation
- Promoted Listings creation, launch, pause/resume, ad-rate, bid, keyword, or budget change
- shipping fulfillment, refund, dispute action, buyer message, feedback, payment, or external contact

Always block credential exposure, CAPTCHA/MFA/verification bypass, anti-association evasion, cross-store authorization reuse, private-data scraping, unauthorized asset reuse, invented product/condition facts, and publishing without required policies or IP review.

Treat an eBay-owned GitHub SDK as documentation or a `research_only` candidate until the shared GitHub capability registry admits it and license, maintenance, dependencies, security and data boundaries pass review. A repository being public, recent or Apache-2.0 does not authorize installation or prove it vulnerability-free.

The current public `eBay/npm-public-api-mcp` is only a research candidate. Its README describes Node 22+, Production GET-only access and no official Sandbox support, while the source constants expose Sandbox methods; keep that support status conflicting/unknown until runtime verification. The source defaults a missing or invalid environment to production and caches access tokens in process memory, so T One must require an explicit environment/store binding and keep DPAPI credential references authoritative. Reject the README troubleshooting shortcut that embeds credentials in client configuration. If a later shared-registry review admits any part, merge only its OpenAPI/read-only connector behavior behind T One's existing route, connection truth and error chain. Never create a second model/agent runtime or let MCP config own cross-store secrets.

## Reuse knowledge packages before authoring new rules

For every incremental training round, inventory and fingerprint the existing eBay Skill, rules, contract, templates, evaluations, failures, connector state and shared GitHub admission first. Search in English for current Skills, playbooks, SOPs, schemas, SDKs, MCPs, ERP/OMS/PIM/WMS tools and evaluations that address the identified gap. Never begin from a platform home page or create a second Skill because a package advertises broad coverage.

For each candidate, inspect the exact owner/repository plus commit or release, provenance, license, maintenance, releases, issues, PRs, security policy/advisories, credentials or telemetry, dependencies, deployment cost, tests, site/store/ownership scope and overlap. Sample one core workflow, one failure or authorization boundary and three claimed rules. The decision must be exactly one of `keep_reuse`, `merge_into_existing`, `extract_rules_only`, `research_only`, `rejected_stale`, `rejected_license`, or `rejected_unsafe`. Unknown license, source, maintenance or secret boundary blocks installation and commercial code reuse.

Current package decisions are bounded. Keep the existing `eBay/npm-public-api-mcp` audit/fingerprint, but leave its runtime uninstalled and `research_only`. Keep `nexscope-ai/eCommerce-Skills` only as the shared registry's taxonomy reference; its three roughly 1 KB eBay files have no evidence, site/store scope, failure workflow or evaluations and must not become a second eBay Skill. From `YosefHayim/ebay-mcp`, extract only default-deny write exposure, explicit tool-family allowlists and loud/redacted error regression requirements; do not copy its runtime, `.env` credential ownership or OAuth setup. Reject `adbertram/cli-tools` for eBay execution because its documented pseudo-draft publishes a $99,999 listing and immediately ends it. An offer created by `createOffer` is unpublished; only an explicit, separately authorized `publishOffer` creates the active listing.

No repository inspection authorizes cloning, installing, running setup, opening OAuth, writing client config, entering credentials or calling a seller endpoint. Any reusable rule must merge into this Skill and the existing T One connector/route/DPAPI/error chain only.

## Return a structured result

Return:

- `task_status`: `draft_ready | needs_evidence | needs_authorization | needs_review | blocked`
- `route`: store and marketplace identifiers, without secrets
- `connection_state`: per tool and execution domain
- `pages_or_software_checked[]`: URL/version, site, identity, actual interactions/input/output/errors and permissions
- `facts[]`: value, exact evidence status, source kind, ownership, source, captured/verified time, site, permissions, expiry and confidence
- `unknowns[]`
- `scope_isolation{}`: platform/category/tenant-product/task ownership and any detected `scope_leakage`
- `dynamic_schema_snapshot{}`: marketplace, category tree, leaf category, metadata calls/version/time and required/unknown fields
- `product_fact_provenance{}`: each fact's tenant/project/product/task source or `unknown`
- `listing_or_operation_draft{}`
- `margin_and_risk_review{}`
- `required_gates[]`
- `pending_approval_action{}`
- `writeback{}`: result, evidence references, failure codes, expiry/review trigger, next action

Do not label a draft, recommendation, simulation, accepted UI input, or API request as a live platform result. Verify persistence or response evidence after any confirmed write.

> Private runtime paths, evidence, execution identities, and product records are intentionally excluded from this public pack.
