---
name: independent-commerce-operator
description: Operate and audit independent commerce sites across Shopify, WooCommerce, BigCommerce, DTC, POD, dropshipping, digital services, and OTA-style bookings. Use when Codex must classify a site and vertical, inspect catalog/orders/inventory/fulfillment/tax/payment/growth evidence, design store-isolated API or webhook work, separate site operations from Meta/Google/TikTok advertising, create evidence-backed drafts, or gate high-risk store actions.
---

# Independent Commerce Operator

Use one shared commerce workflow, then load the vertical extension that changes fulfillment, returns, tax, payment, or inventory semantics. Never treat a tool name or an adapter declaration as proof of a live connection.

## Load the minimum references

- Read [official-sources.md](references/official-sources.md) before making a platform, API, scope, webhook, tax, or fulfillment claim.
- Read [platform-adapters.md](references/platform-adapters.md) for Shopify, WooCommerce, BigCommerce, Adobe Commerce/Magento, Salla, or Zid authentication and native-AI boundaries.
- Read [vertical-extensions.md](references/vertical-extensions.md) before advising on POD, dropshipping, digital products/services, or OTA bookings.
- Read [training-curriculum.md](references/training-curriculum.md) when training, evaluating, or incrementally updating this expert.
- Read `../../../../config/platform_expert_training/independent_commerce.json` when running T One evaluations, checking connector truth, or producing the machine contract.
- Treat official pages and live authorized-store responses as facts. Treat seller experience, community posts, competitor observations, and tool estimates as dated hypotheses.

## Train only after visible evidence

For every training cycle:

1. Identify the real execution identity, authorized connector, browser, app, or public official surface.
2. Prefer a store-authorized, non-mutating probe. Without owner authorization, manually open official Seller/Admin/Developer/Ads/Help pages, demos, or lawful sandboxes.
3. Record URL or product version, capture time, country/site, store mode, ownership, clicks, scrolls, inputs, outputs, errors, permissions, and recheck trigger.
4. Classify evidence as `verified_live_fact`, `time_sensitive_evidence`, `historical_operator_trace`, `draft`, `failed_attempt`, `unknown`, or `blocked_owner_input`.
   Also assign the training layer: `official_current`, `verified_software_observation`, `multi_source_practice`, `single_case`, `historical_trace`, or `unknown`. Three independent practice sources are the minimum for `multi_source_practice`, and it still remains an experiment unless current official or verified store evidence supports it.
5. Only then distill the smallest affected rule, adapter, course module, failure case, or regression. If no new page/software evidence exists, report `no_new_evidence` and create no lesson.

Never borrow another store identity, bypass login controls, or describe a public documentation session as an authenticated store session.

### Enforce source-review completion

- Classify every candidate as exactly `candidate_screened`, `opened_not_reviewed`, `fully_reviewed`, or `blocked`. Only `fully_reviewed` evidence may add a platform fact or operating rule; a blocked or title-only source can add only a failure/coverage gap.
- For a finite web page, cover at least 90% of its rendered scroll range, reach the footer or record the stop reason, inspect its navigation/table of contents, and open at least one necessary first-party detail page. For infinite scroll, record at least three new-load attempts and the final stop reason.
- When comments exist, inspect pinned/top/latest, author or official replies, disagreement and failure cases, and sample at least 10 comments or every visible comment when fewer than 10 exist. Save anonymous clusters only.
- A video at 0:00 is `opened_not_reviewed`. For a video of 10 minutes or less, require at least 95% playback or reliable subtitle coverage plus visual checks at the opening, core operation and ending; record duration, played seconds, subtitle coverage, checked timestamps and comment coverage.
- Keep at least 70% of each cycle on Shopify/WooCommerce operating outcomes. Tool or AI research must stay at or below 20%, and cross-platform references at or below 10%. If the comparable URL/version/hash is unchanged, record a duplicate skip; if no qualifying evidence changed, return `no_delta`.

### Prefer audited knowledge packages

- Inventory the existing Skill, rules, curriculum, templates, regressions, failure log, connectors, source fingerprints, and shared GitHub decisions before searching. Search the smallest operating gap with English combinations of platform terms plus `skill`, `playbook`, `SOP`, `checklist`, `template`, `evaluation`, `SDK`, `MCP`, `ERP`, `OMS`, `PIM`, or `WMS`; do not restart from an introduction page.
- Compare two or three mature packages for one topic. For each candidate record exact owner/repository, verification chain, version or commit, update/release state, license, issues/security, credential or telemetry behavior, executable code and tests, dependencies/deployment cost, T One overlap, and `platform + country_site + store_mode + ownership` scope.
- Sample one core workflow, one failure boundary, and three important rules. Verify only those time-sensitive differences against current first-party deep pages. Classify each candidate exactly `keep_reuse`, `merge_into_existing`, `extract_rules_only`, `research_only`, `rejected_stale`, `rejected_license`, or `rejected_unsafe`.
- Never clone, install, run, copy, or commercially merge a package with unknown admission, license, security, maintenance, credential, telemetry, or data-flow risk. Merge only the evidence-backed delta into this unique Skill and existing T One contracts; a repository, CLI, SDK, sample, or passing package test is not a live store connector.

## Establish the execution route

Require these fields before any store-specific conclusion:

`tenant_id + project_id + store_binding_id + platform + country_site + commerce_mode + ownership + execution_identity_id`

Also collect:

- site domain and platform-native store identity (`shop`/store URL, WooCommerce base URL, or BigCommerce `store_hash`);
- selling markets, business entity, store currency, presentment currencies, tax registrations, payment account, fulfillment locations, and return address;
- vertical: `dtc_physical`, `pod`, `dropshipping`, `digital_product`, `service_booking`, or `ota_booking`;
- connector state and granted scopes for catalog, orders, customers, inventory, discounts, fulfillment, returns, analytics, payments, and webhooks;
- separate ad account identities for Meta, Google, and TikTok when external acquisition is in scope.

Use `GLOBAL` only as the independent-site route label. Never infer that tax, privacy, shipping, product eligibility, payment, or advertising rules are globally uniform.

## Isolate platform, category, product, and task scope

Keep four layers separate:

1. **Platform common**: platform rules, country/site, store mode, authorization and generic catalog/order/after-sales behavior. Never place a tenant product, price, inventory, warehouse, customer, media, or task result here.
2. **Category capability**: load the current platform's official category schema and category-specific variation, compliance, logistics, advertising, and claims rules. Apparel, home/living, beauty, electronics, food/restricted goods, digital goods, services/bookings, and machinery each have different checks.
3. **Tenant/project/product**: bind product facts only to `tenant_id + project_id + product_id + store_binding_id`. A photo or import without price, variants, inventory, origin, rights, or compliance evidence leaves those fields `unknown`.
4. **Task evidence**: keep a listing attempt, campaign draft, order, asset, customer event, or failure inside its task/evidence ID. Distill only the product-independent method; never copy the product value into another route.


For an unknown category, read the authorized platform schema before designing fields. Never substitute an apparel schema for furniture, beauty, electronics, food, digital goods, services, or machinery. Open-source and multi-tenant distributions must use synthetic anonymous fixtures and exclude private_tenant private facts.

## Verify connector truth

Classify each capability as exactly one of:

- `connected_read_only`: a current store-specific credential has passed a real read probe and its scopes are recorded;
- `connected_write_gated`: read is verified, required write scopes are present, and every mutation still enters the approval queue;
- `available_unconnected`: an official API or supported connector exists but no current store-specific authorization is verified;
- `research_only`: public documentation or lawful public-page research is available, with no authenticated store action;
- `blocked`: policy, license, missing identity, missing scope, missing evidence, or project safety rules prohibit use.

Store only `credential_ref`; never place tokens, keys, secrets, passwords, cookies, or MFA material in task payloads, reports, prompts, logs, or tests.

## Enforce the local reliability contract

- Use `ai_ecommerce_director.independent_commerce_reliability` only for durable local evidence and verification. It does not call a platform, payment provider, PIM, or store.
- Fail closed when the webhook secret is missing, the HMAC does not match the exact timestamp and raw UTF-8 bytes, the event is outside the admitted time window, or one `platform + event_id` is reused with changed facts or payload. Exact replays are idempotent.
- Treat `payment.succeeded` as `provider_reported_success_pending_local_finality`. Local finality requires an exact store binding, order, transaction, currency and amount match plus an explicit local `paid` readback and evidence reference.
- Persist refund and dispute events independently of delivery order, then recompute their state from signed events ordered by `occurred_at`. A refund or dispute without payment evidence remains unresolved; duplicate delivery never creates a second transition.
- Require every PIM operation to say `set` or `clear`. `clear` carries no value field; an empty string or null used as a clear instruction is ambiguous. Inspect every item response and exact readback. One failed or mismatched item makes the batch partial or failed, never successful.
- Keep publishing, pricing, inventory, payment, refund, dispute response, product mutation, and external messaging behind their existing owner and connector gates. Passing the local reliability contract is evidence, not authorization.

## Run the shared workflow

1. **Account and compliance**: verify store ownership, selling markets, entity, platform plan/version, payment and tax responsibility, privacy boundary, and prohibited-product constraints.
2. **Catalog and offer**: preserve product facts, variants, media rights, cost, price, stock or capacity, delivery promise, policies, and localization. Mark missing facts unknown.
3. **Inventory and fulfillment**: select the vertical extension; map location, supplier or production partner, service capacity, delivery artifact, SLA, returns, cancellations, duties, and exception ownership.
4. **Store experience**: audit navigation, search, collection/product page, checkout path, trust evidence, accessibility, mobile behavior, localization, tracking consent, and conversion friction.
5. **Promotion and retention**: calculate margin after discounts, shipping, tax, payment fees, returns, supplier/POD costs, and channel spend. Draft discounts, email, loyalty, and lifecycle tests; do not activate them.
6. **External acquisition handoff**: pass a versioned landing-page/feed/measurement brief to the Meta, Google, or TikTok Ads channel connector. Keep store API and ad-account authorization separate.
7. **Orders, service, and finance**: reconcile orders, refunds, chargebacks, fulfillment/service delivery, payout fees, taxes, and profit using store-specific evidence.
8. **Review and learn**: write facts, failures, outcomes, and dated hypotheses to the correct tenant/project/store/task scope. Expire time-sensitive rules instead of treating them as permanent.

## Apply platform adapters

### Shopify

- Prefer the versioned GraphQL Admin API. Record the requested and returned API version.
- Request least-privilege scopes per store. `read_orders` does not imply all historical orders; protected customer data and some scopes require additional approval.
- Verify webhook HMAC, deduplicate deliveries, tolerate out-of-order events, and run reconciliation because delivery is not guaranteed.
- Model fulfillment through locations and fulfillment orders. Do not invent a fulfillment location or manually create a Shopify `FulfillmentOrder`.
- Treat Sidekick as a store-context admin assistant, not a T One connector or an independent execution identity. Map every proposed object to the current staff permission and a visible Shopify review control; keep T One confirmation for Apply, Save, Install, Update order, transfers, discounts, customer changes, app activation, theme changes, VAT/tax configuration, marketing, payment, fulfillment, refund, and publishing.
- Separate Sidekick surfaces: chat, Pulse, generated content, generated Admin apps, saved prompts, memory, third-party app calls, and Campaign Autopilot have different plan, device, permission, data, save, and availability boundaries. A Help Center page or prompt result does not prove a named store has any surface enabled.
- Generated Sidekick apps require an eligible plan, desktop web, `App development > Develop`, store-level sharing, permission review, testing, and an explicit Install. They work inside Shopify admin through supported Admin API data and do not establish theme, checkout, customer-account, external-system, or T One access.
- Never use Sidekick memory or a shareable saved prompt as authoritative business state. Bind every run to the named tenant/project/store/task, re-read current objects, and keep credentials, customer data, private store facts, and tenant-specific instructions out of shareable Sidekick skills.
- Treat Sidekick app recommendations as a bounded candidate list, not an exhaustive or verified shortlist. Recheck claimed features, Built for Shopify status, pricing, permissions, personal-data access, recent activity, compatibility, billing, and support on the current listing/about page before any install proposal; a recommendation never authorizes install or charges.
- Shopify-made app activity is not currently exposed in the third-party app activity table. Capture pre/post object evidence and the human review event separately instead of treating a missing activity row as proof that Sidekick made no change.
- Treat storefront performance as an operating experiment, not a synthetic-score contest. Start from the named store's field data when authorized, segment LCP, INP and CLS by device and page type, correlate regressions with theme/app/tag/content changes, and pair every performance change with conversion, checkout, error and accessibility guardrails. Without store Reports/RUM access, keep the store result `unknown` and use public guidance only for a draft test plan.
- For theme changes, prefer HTML/CSS and progressive enhancement, avoid parser-blocking or unnecessary third-party JavaScript, use responsive Shopify-hosted assets, never lazy-load above-the-fold/LCP media, and use Theme Check or repeatable lab tests before a review. Change one bounded cause at a time, retain rollback, and read field data again before claiming improvement; neither Lighthouse 90+ nor one community case proves conversion lift.
- Treat Customer Events as the store-side measurement handoff, not Meta, Google, or TikTok Ads authorization. Bind every app/custom pixel to the current store, pixel type, settings, consent purposes, event contract, destination and owner; never reuse one store's pixel, customer data or ad identity in another route.
- For an app pixel, require app-development permission, a development store, authenticated GraphQL and the current `write_pixels` plus `read_customer_events` scopes. `shopify app dev` only creates the development connection and can still show the pixel as Disconnected; activation requires the reviewed `webPixelCreate` settings mutation and a current Connected/readback state. Deploying or releasing an app version remains an owner-gated side effect.
- Declare analytics, marketing, preferences and sale-of-data purposes from the real processing. Do not label nonessential tracking as strictly necessary. Read `init.customerPrivacy`, listen for `visitorConsentCollected`, and pass current consent state through the event handoff so downstream tags can fail closed when permission is absent or changes.
- Minimize the event payload: prohibit raw email, address, customer objects, secrets or full checkout/event dumps in `dataLayer`, console logs, evidence or tests. Define event name/version, store and session pseudonymous keys, Shopify event ID when available, transaction ID, currency/value/items and consent state; specify retention and destination ownership before any implementation.
- Test in a development store across denied/granted/changed consent, navigation, product/cart/checkout/purchase, reload/retry and duplicate delivery. Reconcile missing and duplicate events with event ID plus transaction-level idempotency, inspect browser and destination errors, and read back counts before claiming attribution completeness. Pixel installation never authorizes ad-account upload, campaign launch, budget change or audience processing.

### WooCommerce

- Bind one WordPress/WooCommerce site to one REST key or approved application connection. Respect the WordPress user's roles and key permission level.
- Prefer HTTPS and `wc/v3`. Keep plugin, theme, server, payment, and REST credentials as separate privilege domains.
- Before a read probe, record the site URL, WooCommerce/WordPress versions, permalink mode, REST-user capability, HPOS authoritative datastore, compatibility/synchronization state, and incompatible extensions. Prefer supported CRUD/REST behavior; never infer order state from direct `posts/postmeta` reads or from the WooCommerce version alone.
- Verify webhook signatures and delivery status. Test HPOS and plugin compatibility before relying on any storage or synchronization assumption.
- Keep the authenticated WooCommerce REST API (`wc/v3`) separate from the public Store API (`wc/store/v1`). Store API access is a customer-facing, current-session surface and is never proof that T One has an admin/store connector.
- Store API product reads cover published products. A missing draft or pending product is not deletion evidence; use an authorized admin surface before changing product state.
- Require a documented nonce or Cart Token flow for current-customer cart and checkout mutations. Never disable Store API nonce checks in production; the official bypass example is explicitly development-only.
- Treat variation galleries, visual swatches, and Product Gallery media as version-and-feature-flag capabilities. For variation galleries, probe `system_status.settings.enabled_features` or the store's advanced feature setting and record the migration marker before reading or writing `gallery_image_ids`; a Woo version or rollout announcement alone is insufficient.
- WooCommerce 10.9 introduced opt-in variation galleries and experimental Color / Image (`wc-visual`) attributes for block themes. Verify the named store's theme, feature flag, migration, plugin/theme compatibility, and staging result. Treat later canary/full-rollout dates and Product Gallery video support discussed by maintainers as dated roadmap evidence until the release and store flag are independently observed.
- Treat the legacy Woo AI product-content plugin as deprecated from 2025-05-15. The WooCommerce.com Support AI Assistant is guidance with optional Jetpack/store context, not a Woo Admin executor; it cannot prove a price, refund, order, or publishing action.
- Treat every marketplace/community AI plugin as extension-specific. Require verified installation, version, license, provider credential, sent fields, retention/privacy terms, editable output, and a human review step before assigning any capability.

### BigCommerce

- Bind each store to its `store_hash`, API account type, access token reference, and least-privilege OAuth scopes.
- Separate Catalog, Orders, Payments, channels/storefronts, and webhooks. Do not assume a product scope grants order or payment access.
- Record product type (`physical` or `digital`) and channel assignment. Treat service and OTA behavior as an extension, not a generic physical-product order.

### Adobe Commerce / Magento

- Branch first by PaaS, on-premises, or SaaS. Bind PaaS/on-prem requests to base URL and store-view code; bind SaaS requests to tenant/IMS identity and the documented store header.
- Treat Live Search and Product Recommendations as unconnected until entitlement, install/configuration, catalog/event sync, store view, storefront path, result, and metric are verified.

### Salla

- Bind the partner app, merchant installation, scopes, store identity, and credential reference. Serialize refresh-token rotation; never refresh the documented single-use token concurrently.
- Keep Merchant API and Partners MCP distinct. Partner Portal tools that create, update, delete, publish, change scopes, or change shipping still require owner authorization and T One confirmation.

### Zid

- Bind the server-side OAuth app and store-specific identity. Model authentication per endpoint family because the official general OAuth page and the product-list endpoint document different header sets.
- Treat the Zid AI Connector MCP link as a high-privilege store credential. Do not activate, copy, store, or call it without store-owner authorization; every mutation remains confirmation-gated.

### Medusa

- Reuse the shared registry decision for `medusajs/medusa`: it is admitted only as an `adopt_reference` for commerce-module boundaries, workflow compensation, and event contracts. It is not a runtime replacement or store connector; bind every future use to a named project, sales channel, region, currency, payment provider, fulfillment provider, admin/API identity, and store route.
- Keep Medusa development commands such as database migration, schema generation, and user creation inside an owner-approved development sandbox. Never run them as merchant operations or against an unidentified production project.
- Do not install `medusajs/medusa-agent-skills` while its repository license remains unasserted in the shared GitHub registry. Audit each bundled MCP, duplicate server declaration, data destination, secret, and stateful command before any future admission.
- Treat the official Agentic Commerce tutorial and `medusajs/examples/agentic-commerce` as reference code, not a completed commerce channel. At the reviewed commit, feed upload and order-webhook delivery are TODO/log-only, the example package is pinned to Medusa 2.14.0 while current docs/release are 2.17.2, and its only checked HTTP integration test is `/health`; no checkout, payment, cancellation, webhook, or recovery path is proven by that test.
- Never carry sample fallback secrets into T One. Require a secret reference, fail closed when it is absent, verify request signatures, bind idempotency/request IDs, and redact checkout, order, address, payment, and signature data from logs.
- Do not universalize the example's automatic cheapest-shipping choice. Re-read eligible methods after address/cart changes and apply the merchant's documented SLA, cost, duties, tracking, product, destination, and customer-choice policy; keep selection blocked when that policy or authorization is absent.
- Re-price and revalidate checkout after item, address, shipping, tax, discount, or currency changes. Model payment sessions as asynchronous: `pending_authorization` and `requires_more` are not failure or completion, provider webhooks may finish work after the browser stops, and payment success still requires idempotent cart/order reconciliation and a scoped order readback.
- Preserve documentation/code conflicts as blocked evidence. The reviewed cancellation prose and example validation disagree around authorized payment sessions, so do not cancel, refund, or claim recovery semantics until the named version/provider path is resolved and tested.
- The hosted Medusa Docs MCP is documentation access for authenticated Medusa Cloud users, not a merchant-store connector. Keep it `blocked_connector` until a named Cloud organization, entitlement, owner-authorized `credential_ref`, client, data boundary, and read-only probe exist; never paste or generate access keys in a task.

### Saleor

- Bind Saleor work to a named environment, channel, currency, warehouse, app/user identity, GraphQL endpoint, permissions, and tenant/store binding. Public GraphQL patterns or agent skills do not establish a live project or writable authorization.
- Treat `saleor/agent-skills` as a developer-reference candidate only. Its repository license separates BSD-3-Clause code from CC-BY-4.0 artwork while individual Skill metadata may state MIT; block installation and code/content reuse until the shared registry owner resolves the exact file-level license and security review.
- Preserve user-scope versus app-scope permissions and verify JWT or webhook signatures server-side. A Dashboard visibility check alone does not authorize a backend route or mutation.
- Treat the current `saleor/saleor-mcp` main line and release `0.1.8` as a read-only developer reference, not a T One connector. Its hosted endpoint is documented for Saleor Cloud, it requires `MANAGE_PRODUCTS` and `MANAGE_ORDERS`, and its tools can return channel, product, stock, warehouse, order and customer-related data. Read-only does not mean low privilege: bind one exact environment, use only a `credential_ref`, minimize outputs/logs, require an explicit domain allowlist, and never paste the app token into prompts, tasks or reports.
- Do not treat open mutation PRs in `saleor/saleor-mcp` as current capability. Until a mutation is merged, released, admitted by the shared GitHub registry, connected to a named store and owner-gated, the current MCP remains research-only and read-only. AGPL-3.0 network-service/source obligations also require registry-owner and license-owner review before reuse, installation or deployment.
- Treat Saleor Instant Checkout as its current ACP-feed beta: Saleor 3.21+, one feed per channel, on-demand scans, manual upload and no automatic refresh. Missing required variant mappings can omit variants or produce an empty feed. The current app does not upload the feed to OpenAI and does not complete checkout or payment in ChatGPT; those are still marked coming soon.
- For AI catalog enrichment, use the current Saleor product type, assigned attributes, input types and allowed choice slugs as a closed schema. Ask the model to extract only evidence-backed values from existing product content, preserve an evidence quote, skip unsupported types, and keep review/apply as a separate protected route. Revalidate before `productUpdate`, inspect mutation errors even when HTTP is 200, and reload/read back before claiming the Dashboard changed. The public demonstration repository remains `research_only` until its identity, license, dependencies, secrets and data flow are separately audited.

For platforms without a registered adapter, remain `research_only` or `blocked` until official authentication, object schema, webhook behavior, and store isolation are implemented and tested.

## Gate platform-native AI

- Separate documentation assistants, admin assistants, recommendation/search services, copy generators, and MCP execution connectors.
- Capture the actual entry point, plan/role/app prerequisites, accepted inputs, returned output, editable fields, save/publish boundary, metrics, errors, and recovery.
- Treat all generated text, media, segments, reports, discounts, campaigns, workflows, recommendations, and tool calls as drafts until their facts, rights, state transition, and save/activation evidence are checked.
- A platform setting that permits automatic execution does not override T One's owner confirmation for publishing, pricing, discounts, advertising, payment, fulfillment, refunds, outreach, identity, or high-privilege connector activation.

## Admit official open-source assets safely

- Verify an organization or repository by following a link from the platform's official site or developer documentation. A matching name, search rank, star count, or GitHub topic is not an official-identity chain.
- Before revisiting a repository, compare `owner/repo + commit/tag + license + security state` with `config/github_capability_registry.json` and the expert source fingerprints. Recheck only a changed version/security/license state or an explicitly incomplete prior coverage record.
- Inspect the relevant README/docs, releases or changelog, license, recent commits, issues and replies, discussions when present, pull requests/reviews, security policy/advisories, dependencies, deployment path, data destinations, secrets, and stateful commands. Record sections reached and areas blocked by sign-in, lazy loading, rate limits, or missing files.
- `official`, `active`, `MIT/BSD/GPL`, `has releases`, `has an MCP`, and `has agent skills` are evidence attributes, not integration status. Only the shared GitHub registry owner can admit code; until then use `research_only` or `blocked`, and never clone, install, execute, or add dependencies.
- Treat repository privacy statements as vendor claims. Verify workflows and scripts for telemetry or external data flows separately. Installation-count telemetry is not automatically customer-data collection, but it must be disclosed and scoped before admission.
- If repository-level and file-level license metadata conflict, or a license/security policy is absent, stop reuse and submit the exact conflict to the registry owner. Do not choose the most permissive label.

## Capture complete-enough page evidence

- Before distillation, record page identity, title/author or official ownership, date/version, country/site, store mode, and route ownership. Read the relevant table of contents or tabs, then cover the body through its footer or a recorded stop condition.
- Expand directly relevant accordions, FAQs, descriptions, subtitles, changelogs, attachments, and linked official detail pages. For lists, record the first page, next/latest view attempted, sorting, and the inspected item range. For community or issue threads, separate the body, official/author replies, accepted answer, counterexamples, and comment noise.
- Store a coverage record with sections read, links opened, comment/reply range, pagination range, final section reached, inaccessible areas and reason, and confidence. Never write `read all` or infer hidden content.
- Stop after two link layers add no new fact, the topic drifts, the content repeats, or login, CAPTCHA, paywall, rate limit, or other access control appears. Record the gap and continue with another lawful source; never bypass it.

## Learn from comments without promoting noise

- For a selected public professional thread, inspect the post body plus pinned, top, newest, author/official replies, nested replies, disagreement, later corrections, and at least two sort orders when the platform exposes them. Record the actual comment/reply counts or inspected range and every inaccessible lazy-loaded area; never claim every comment was read.
- Cluster only anonymous themes such as checkout friction, payment trust, delivery uncertainty, returns, feature requests, migration failures, performance, accessibility, or extension conflicts. Store counts only within the inspected thread and keep language/context uncertainty explicit. Do not save usernames, avatars, contact details, private messages, or large excerpts.
- Separate `official_reply`, `dated_operator_case`, `community_signal`, `conflicting_evidence`, and filtered noise. Votes and repetition do not create truth; suspected promotion, affiliate claims, copied text, bots, generic reactions, and off-topic content never become rules.
- Backcheck every comment claim about versions, fees, policy, API fields, feature availability, or rollout against a current official page. A maintainer roadmap reply remains time-sensitive until a release/changelog and a named-store probe confirm it. Convert unresolved signals into regression questions or research targets, not live capability claims.

## Keep advertising separate

- Shopify, WooCommerce, or BigCommerce authorization does not authorize Meta Ads, Google Ads, or TikTok Ads.
- A pixel, tag, catalog app, marketing event, or Merchant Center feed is not proof that an ad account is writable.
- Require the external channel's business/account identity, OAuth or token scope, billing access, tracking/consent state, budget, objective, attribution window, and stop-loss rule.
- Draft campaigns and measurement plans without authorization. Require owner confirmation for campaign creation, activation, budget/bid changes, audience upload, tracking changes, and paid asset purchase.

## Produce auditable outputs

Return:

1. route and vertical classification;
2. evidence table with source URL, checked date, country/market, store mode, applicability, and expiration/recheck trigger;
3. connector truth table;
4. facts, inferences, hypotheses, and unknowns as separate sections;
5. ordered actions with owner, prerequisites, risk, approval gate, rollback, and verification evidence;
6. platform/vertical-specific fulfillment, tax, payment, privacy, and returns gaps;
7. external-ad handoff, if requested, without claiming the ad connector is live;
8. result metrics and a next review date.

## Enforce boundaries

Always block:

- bypassing robots, anti-bot controls, CAPTCHAs, MFA, rate limits, account linkage controls, or platform restrictions;
- cross-store or cross-ad-account credential reuse;
- copying competitor/customer images, reviews, video, music, trademarks, or personal data without permission;
- inventing product, stock, capacity, tax, payment, delivery, conversion, or connector facts;
- treating a draft, approval, queued action, webhook receipt, or API capability as a completed live mutation;
- unconfirmed publishing, repricing, discount activation, ad spend, tracking changes, payment changes, external messages, refunds, fulfillment, or supplier commitments.

> Private runtime paths, evidence, execution identities, and product records are intentionally excluded from this public pack.
