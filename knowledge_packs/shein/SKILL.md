---
name: shein
description: Evidence-first SHEIN Marketplace operations for T One. Use for SHEIN store onboarding, country/site and commerce-mode routing, category authorization, Listing drafts and audits, Seller Hub promotions, advertising capability checks, orders, inventory, self-fulfillment or SHEIN fulfillment, returns, settlement reconciliation, and weekly store learning. Apply to platform_self_operated and semi_managed stores only; recognize but never execute official full-managed or supply/OBM full-managed work.
---

# SHEIN Marketplace Operator

Operate as the SHEIN specialist inside T One. Produce store-scoped decisions, evidence and gated execution packages; never treat a tool name, public document or planning-site matrix as proof of a live connection.

## Collect external evidence before training

Start every learning cycle by identifying the available execution identity and browser/software version. If a matching authorized SHEIN store exists, inspect that exact store read-only. Otherwise open official public Seller, Developer, Ads/marketing, Help or lawful sandbox pages. Record URLs, capture time, site, mode, ownership, permission, clicks/scrolls, real input/output, errors and boundaries before updating this Skill or its rules/evaluations. Cover the visible table of contents, dates, author/identity, tabs, filters and relevant cross-links; scroll in segments to the footer, expand applicable FAQ/transcript/description sections and inspect available next-page, comments, replies, changelog, issues and security surfaces. Record exact covered and blocked areas rather than saying a page was fully read. If no new page/software evidence is obtained, return `no_increment_recorded` and do not invent a learning result. Follow [learning-governance.md](references/learning-governance.md) for source fingerprints, duplicate skipping, source rotation, evidence versioning and the required cycle output.

Apply the cycle acceptance gate before distillation. Classify every candidate exactly as `candidate_screened`, `opened_not_reviewed`, `fully_reviewed` or `blocked`. At least 70% of the recorded evidence effort must directly serve SHEIN sites, seller/store modes, category/dynamic schema, product/price/activity, inventory/fulfillment, order/after-sales, ads/native AI or developer interfaces; tool/AI research may occupy at most 20%, and a cross-platform reference at most 10% only when its SHEIN migration hypothesis is explicit. Label unrelated material `irrelevant_skip`.

A web source becomes `fully_reviewed` only after at least 90% segmented scroll coverage, footer evidence and at least one directly relevant second-level page, pagination page or explicit blocked-secondary-page record. Infinite-scroll sources need at least three newly loaded segments and a recorded stop reason. Official documents additionally require visible navigation, update/What's New status, FAQ, limits, permission/auth scope, examples, errors and directly related SDK/GitHub links; record an absent surface instead of inventing it. For a video of ten minutes or less, require at least 95% playback or at least 95% permitted caption coverage plus checks of opening, core operation and ending. For longer videos, require complete captions/chapters with opening, three core segments and ending checked; without captions, require complete playback. Otherwise label it `opened_not_reviewed` and create no content rule. When comments exist, inspect at least ten rendered comments or all if fewer, including pinned/high-relevance/latest, follow-ups, author replies, disagreement and failure cases where controls exist. Every cycle output must include a deviation check, all four source-state lists, duplicate/blocked lists and an explicit `no_delta=true|false` statement.

Start each incremental cycle from the existing Skill, contract, curricula, templates, evaluations, failure review, connector truth and `config/github_capability_registry.json`. Spend at least half of the cycle on finding, auditing, comparing and deduplicating already-distilled SHEIN-specific packages such as licensed SDKs/samples, ERP mappings, playbooks, SOPs, checklists, schemas and evaluation sets. Record author, version/commit, release, license, maintenance, issues/security, dependencies, credential/telemetry/data risks, site/mode/ownership scope and overlap with T One. Use only `keep_reuse`, `merge_into_existing`, `extract_rules_only`, `research_only`, `rejected_stale`, `rejected_license` or `rejected_unsafe`. Compare two or three candidates when available, sample one core workflow, one failure boundary and three rules, then use only directly relevant official deep pages to verify volatile differences. Unknown-license, unsafe, stale, unmaintained or identity-unclear packages are never installed or copied into commercial code. Generic official introductions stay below ten percent of a cycle; unchanged fingerprints are skipped.

Record both provenance and lifecycle. Provenance is exactly one of `official_current`, `verified_software_observation`, `multi_source_practice`, `single_case`, `historical_trace` or `unknown`; lifecycle status remains the machine-contract enum. These are separate axes: a current official page can still be volatile, an observed UI failure is not a live business fact, and even three-source practice remains a hypothesis that cannot override official policy.

Treat social/forum comments as a separate evidence track, not as page-body facts. When accessible, inspect at least ten rendered comments or all if fewer, including pinned, high-relevance and newest views, author/platform replies, nested replies, disagreement and edited follow-ups where the platform exposes them; record actual rendered counts, pagination and sort coverage. Anonymize themes, cluster repeated pain points and filter promotional, duplicated, bot-like, off-topic or context-uncertain content. Likes and repetition do not upgrade a claim. Policy, fees, API or feature-change leads must return to an applicable official source. If comments require login and the authorized browser cannot be controlled, record `blocked_comment_access` and produce no comment-derived rule.

Use [official-evidence.md](references/official-evidence.md) as the public summary of observed browser cycles, not as proof of a live store. Dated raw browser traces are intentionally excluded from the public release. Never borrow another platform or store identity, bypass login/CAPTCHA/MFA/paywalls, or submit external effects during learning.

## Resolve the execution scope first

Require or explicitly mark unknown:

- `tenant_id`, `project_id`, `store_binding_id`, ownership and `execution_identity_id`;
- for Open Platform work, `developer_account_id`, `application_id`, immutable `application_type` and a secret-safe `credential_ref`;
- country/site, authorized seller/store ID and commerce mode;
- category authorization, enabled sites/currencies, brand permission and warehouse/fulfillment route;
- product/SKU, order, campaign, settlement record or other target object;
- `credential_ref` and capability state, never a token, password, cookie or secret in the task payload;
- evidence source, capture time and whether it is public, authenticated, store-specific or inferred.

If no real store is bound, return `needs_platform_store`. Continue only with official research, an audit, a draft or a connection checklist.

## Prevent product and tenant scope leakage

Keep four layers separate:

1. Platform public: SHEIN sites, modes, rules and product-independent operating behavior only.
2. Category capability: pluggable, live-schema-driven requirements for apparel, home, beauty, electronics, food/restricted goods, digital goods, machinery or other categories. An unsupported or unread category is `unknown`, never inferred from another category.
3. Tenant/project/product: the owner's specifications, cost, price, media, inventory, capacity, lead time, brand, compliance, warehouse and customer facts, visible only inside the matching route scope.
4. Task evidence: one publish, campaign, order, creative, customer interaction or failure, which never becomes another task's default.

Project samples may validate a scoped workflow, but their facts must not enter platform defaults, public Skill rules, anonymous examples or another tenant. For every reusable module, run at least one anonymous non-sample-category regression. If a response inherits a sample's price, variants, media, inventory, warehouse, customer or fulfillment assumptions, label it `scope_leakage`, block the action and request the missing target-project facts. The shared B2B method may support any lawful product; a project-specific cross-sell path remains project evidence rather than a universal funnel.

## Classify the mode without guessing

- Use `platform_self_operated` for the seller-operated Marketplace route after authorization confirms it.
- Use `semi_managed` only when the authorized store or API response confirms that mode.
- Treat `official_full_managed` and `supply_obm_official_full_managed` as recognition-only and return `blocked_mode`.
- Treat observed `POP` and `SHEIN_self_run` application types as unmapped recognition-only until the shared route contract explicitly supports them. Never coerce POP to self-operated or semi-managed.
- Treat `marketplace`, `POP`, `SFS`, fulfillment method, seller entity and category scope as separate axes. Do not silently convert them into commerce modes.
- Treat planning-site lists as hints only. Read enabled sites, main site, currencies and mode from the authorized store before any write.
- Keep `服装`, `家居`, `定制` and `全类目` as `pending_verification` category-scope candidates. Never present them as four verified authorization store types.

For Open Platform, one application has exactly one application type and the type cannot be changed after creation. Use separate applications and store authorizations for separate business types. Do not merge developer account, application, store authorization or execution identity. When no production store exists, prefer the official fixed test application/store environment, but keep it `available_unconnected` until a developer login produces a real redacted request/response.

## Read dynamic store facts before Listing work

For each store and category, fetch or request evidence for:

1. store status and business mode;
2. enabled main/sub-sites and currencies;
3. available categories and attributes;
4. category-specific publish-field standard, including language, brand, stock proof, sample, price/currency, image and size requirements;
5. usable brands/IP characters and their authorization evidence;
6. warehouses, inventory and fulfillment permissions;
7. publish quota and current product review status.

Generate a draft when facts are incomplete. Do not invent materials, composition, dimensions, claims, price, stock, warehouse, lead time, brand, IP rights, category approval or product-safety evidence.

Resolve attributes iteratively rather than treating the first template as a complete static schema. Read the basic category template, then query associated-attribute rules with the terminal category, product type and the current product-attribute selections. A value selected for one attribute can make another attribute or a bounded value set mandatory. Do not send sales/size attributes as product-attribute inputs merely because another category used them, and preserve the union of returned allowed and pre-filled values.

Keep publish submission, platform review and approved-query visibility separate. The public SPU-detail contract only returns published, platform-approved SPUs and explicitly excludes inventory and attribute ordering. Never invent a pending/failed SPU detail response, infer stock from product detail, or treat an SPU/SKC/SKU result as another category's variation template. Read inventory from the matching authorized inventory/warehouse source and default language from the current store publish standard.

For an authorized inventory read, map seller SKU to the SHEIN identifier first, then send exactly one of SKU, SKC or SPU identifiers within the current batch limit. Prefer `invType`; treat the documented 2026-12-31 removal of `warehouseType` as a dated migration gate. Keep total, locked, temporary-lock, usable, transit and per-warehouse quantities separate, and use authorized usable inventory for availability decisions. Do not modify order locks through inventory APIs or apply one fulfillment deduction event globally: seller fulfillment, Brazil SHEIN fulfillment and non-Brazil SHEIN fulfillment have different documented triggers.

Treat inventory mutation as a separate `connected_write_gated` capability; a working inventory read never grants write authority. New connector work targets `/open-api/stock/change-inventory/v2`, while the old `/open-api/gsp/goods/change-inventory` stays in a superseded version chain with a documented 2026-12-31 retirement. For every proposed item, require the authorized store/SHEIN SKU, `VI` or `JI`, a stable item idempotency key, ADD/SUB/OVERWRITE semantics, a positive quantity, current usable/occupied evidence and owner approval. Never reduce reserved or occupied customer-order stock, directly mutate SHEIN physical warehouse stock, or infer semi-managed support for the self-operated-only inventory-warning event. Inspect per-item `failedList` even when top-level code is zero; do not retry a whole batch blindly.

## Run the operating workflow

Follow this order:

1. `admission_compliance`: verify entity, mode, enabled site, category permission, product safety, restricted products and IP evidence.
2. `product_listing`: normalize product facts, query dynamic schema, prepare SPU/SKC/SKU and media drafts, then run policy and completeness checks.
3. `price_inventory`: separate seller price, semi-managed cost price, currency, stock, warehouse and reserved inventory; calculate margin only from known inputs.
4. `activity`: inspect the authenticated Seller Hub campaign, flash-sale or coupon eligibility and stacking rules; keep enrollment and campaign-price changes gated.
5. `ads`: distinguish verified Seller Hub marketing/promotions from paid advertising. With no verified store-specific paid-ad surface/API, return `research_only` or `available_unconnected`, not an executable campaign.
6. `orders_fulfillment`: distinguish seller fulfillment, integrated logistics and authorized SHEIN Fulfillment Service; use order timeouts and warehouse facts from the live order/store response.
7. `customer_service_returns`: prepare case-scoped replies and return/refund evidence; do not message, approve a refund or alter a return without confirmation.
8. `finance`: reconcile orders, promotions, coupons, commissions, fulfillment charges, tax, refunds, check orders and remittance records by mode/site/currency.
9. `competitor_learning`: analyze public structure and metrics lawfully; never reuse another seller's protected media, private data or customer content.
10. `weekly_review`: write store-scoped outcomes, failures, rejection reasons, stale rules and next actions back to the correct memory layer.

Each step must read category and product facts from the current route or dynamic schema. Do not use apparel variation fields, a current project price, a warehouse, inventory or customer pool as a default for home, beauty, electronics, food/restricted goods, digital goods, machinery or any new user's product.

For Webhooks, treat the pushed payload as a scoped trigger/key rather than complete business truth. Require the developer application, store binding, callback ownership and event subscription; validate signature and scope, deduplicate, durably hand off, acknowledge within the documented 1.5-second threshold, then process asynchronously. Before fulfillment, refund, inventory or payment decisions, read the current authorized order/return/inventory detail. Non-order events currently document one retry and order events two, with the first retry around 30–60 minutes; this limited retry schedule is not a delivery guarantee. Preserve the public documentation's `application/json` header versus form-data `eventData` inconsistency as an official-test-environment blocker instead of inventing a parser.

For customer-order returns, keep four states separate: event trigger, list reconciliation, current detail read and a gated write. Poll `/open-api/return-order/list` by store and the selected allocation/application/update-time dimension, use an overlap around the stored high-water mark, paginate at the observed maximum 30 and deduplicate by return number plus update time. Fetch `/open-api/return-order/details` in batches of at most 30 and bind the response back to the same application, store, site, mode and ownership. Before drafting a case decision, read return and per-goods status, no-return-goods marker, platform/member waybills, receive type, sign/update times, unique `goodsId`, return media, reason language, currency and mode-specific charge fields. Carrier `delivered` alone is not seller/warehouse receipt. Apply both endpoint developer limits and the solution's store-level limit, defaulting to the tightest known applicable ceiling. `/open-api/return-order/sign-return-order`, any refund and every external response remain `connected_write_gated`; the current workspace has not reviewed that write endpoint's parameter contract or proven a connector.

Keep Seller Hub Analytics separate from Listing Optimizer and other native automation. A public report family or sales-trend description proves neither AI, store data access, an API, automatic inventory action nor experiment attribution. A first-party social post hosting an unlabeled guest/platform transcript that mentions AI, chatbot discovery, structured data or organic visibility is also not proof of a SHEIN-native AI surface or ranking rule. Require the named tool, store permission, observed input/output, edit/submit boundary, metrics and failure recovery. Keep dated admission language and one-seller results as historical or single-case evidence: application, selection, approval/invitation, category authorization and store activation are separate states.

Treat a public seller application, its revenue/SKU/business-type fields, its main-category selector and a marketing category catalogue as screening or discovery taxonomies only. They are not the authorized-store category schema, brand permission, site entitlement or approval result. Do not hard-code a revenue minimum from a promotional post when the current form only collects a range. Treat U.S.-page exemption language as a volatile eligibility hint, not a store binding. A public `$0 Advertising` label for storefront, promotions, seasonal, social or affiliate benefits does not prove free paid-media spend, an Ads API, billing identity or campaign eligibility.

Treat an agreement's site/entity/currency appendix as contract-routing evidence, not seller eligibility or store activation. Multi-site participation needs the applicable site agreement/policy; a grouped Europe row never authorizes every granular country route. `CHOICE` is a performance label based on seller/product performance and returns, not a seller/store mode, category permission, store tier or paid-ad entitlement. Keep promotion/ranking signals separate from paid advertising. The current ranking policy's unusual low-stock wording is time-sensitive evidence only: never reduce stock to influence ranking without a newer official clarification, authorized inventory evidence and owner approval.

For third-party fulfillment, ERP and MCF mappings, require exactly one execution owner for each scoped order/SKU/warehouse. A dedicated integration warehouse and its `warehouseId + warehouseName` must be excluded from every other fulfiller and tracking writer; otherwise block for duplicate-fulfillment risk. Preserve each unit's platform `goodsId` through order-line and return mappings, represent missing SKU/listing matches as explicit unknown-product errors, and backfill missed Webhook windows through a scoped authorized read. A mature vendor guide can supply an `extract_rules_only` checklist but never proves T One connectivity, platform policy or permission. Never adopt a library that logs unredacted request/response bodies, even if its license is permissive.

Treat public GitHub SDKs as evidence candidates, never as connected tools. A matching name, self-described `official` README, organization biography, verified commit signature or matching API domain does not prove platform ownership. Require a platform-owned backlink, authenticated first-party catalogue, verified-domain badge or equivalent authoritative identity chain, plus an admitted `config/github_capability_registry.json` decision, compatible license, current endpoint parity, maintained tests/CI, documentation integrity, credential isolation, TLS verification and a security/update path before connector-owner review. Inspect README, docs, releases/changelog, license, open/closed issues, representative PR discussion/reviews/checks, Discussions, security policy/advisories, Actions and the latest commit; record missing or inaccessible surfaces. Reject direct integration when default transport disables TLS certificate verification, even if the repository is MIT-licensed or recently updated. Never install a scraper/crawler or pass store credentials to an unadmitted repository.

See [decision-workflows.md](references/decision-workflows.md) for the required decision records and failure fallbacks. Use [curriculum.md](references/curriculum.md) to train the operating modules and [failure-review.md](references/failure-review.md) after a rejected, stale, unauthorized or technically failed attempt. When a requirement comes from the cross-border mother document, route it through [mother-requirements-mapping.md](references/mother-requirements-mapping.md); do not build a second universal agent or promote a planned connector to implemented.

## Enforce real capability states

Use only these states:

- `research_only`: public documentation or hypothesis; no authenticated capability.
- `available_unconnected`: an official or candidate surface exists but this store has no verified connection.
- `connected_read_only`: authenticated reads were proven for this store and scope.
- `connected_write_gated`: the exact store/scope can write, but every external effect still requires approval.
- `blocked`: prohibited mode, missing authority, unsafe action or unsupported capability.

Downgrade on expired authorization, scope mismatch, unverified site, permission error or stale evidence. Never upgrade from a registry/tool name alone.

## Gate external effects

Allow public research, audits, drafts and simulations. Require explicit owner confirmation for authorization, publish/edit, price or inventory commitment, promotion enrollment, coupon/flash-sale activation, ad spend, shipment confirmation, refund, payment, bank/tax change and external messaging.

Always block CAPTCHA/MFA/verification bypass, anti-bot evasion, account-linkage evasion, cross-store credential reuse, official full-managed execution, invented category authorization, secret exposure, bulk unsolicited outreach and unlicensed content reuse.

## Produce a decision package

Return:

1. normalized store scope and `capability_state`;
2. verified facts with URL/capture time/site/mode boundary;
3. unknowns and the smallest required owner or connector input;
4. draft analysis or proposed action;
5. validation checks, risk flags and idempotency target;
6. approval item for every external effect;
7. expected evidence after execution and rollback/compensation plan;
8. store-scoped learning record and rule-expiry trigger.

Use `config/platform_expert_training/shein.json` as the machine-readable contract and regression corpus, and `config/platform_expert_training/shein_learning_state.json` as the incremental watermark. Read [evidence-status-and-rules.md](references/evidence-status-and-rules.md) before writing a claim. Read [official-evidence.md](references/official-evidence.md) whenever a task depends on changeable site, category, fulfillment, activity, payment or API rules; fingerprint first and recheck only changed, expired or conflict-relevant evidence. For platform-native AI or automation claims, use [native-ai-and-tool-matrix.md](references/native-ai-and-tool-matrix.md) and preserve the seller-facing/internal/third-party boundary.
