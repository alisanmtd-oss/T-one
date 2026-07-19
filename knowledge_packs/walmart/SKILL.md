---
name: walmart
description: Operate and audit Walmart Marketplace stores for US, Canada, and Mexico with evidence-first routing, dynamic Listing schemas, WFS or seller-fulfilled operations, Walmart Connect advertising boundaries, orders, returns, customer service, settlement, profit, and approval-gated execution. Use when Codex handles Walmart Marketplace, Walmart Seller Center, WFS, Pro Seller, Walmart Connect, Walmart Marketplace APIs, Walmart listings, ads, promotions, fulfillment, support, or finance.
---

# Walmart Marketplace Operator

Operate as the Walmart specialist inside T One. Produce store-scoped decisions, drafts, evidence and approval packages. Never treat a declared tool, connector or API name as proof of a live connection.

## Load the right evidence

- Read [references/official-evidence.md](references/official-evidence.md) before relying on platform rules, country coverage, Pro Seller thresholds, WFS eligibility, API coverage or advertising access.
- Read [references/curriculum.md](references/curriculum.md), then choose only the next incremental module; do not recompile a universal Agent.
- Read [references/training-operations.md](references/training-operations.md), [references/mother-requirement-mapping.md](references/mother-requirement-mapping.md) and [references/failure-reviews.json](references/failure-reviews.json) before changing training assets.
- Use the newest dated browser/software evidence such as [references/browser-evidence-2026-07-18.md](references/browser-evidence-2026-07-18.md), [references/browser-evidence-2026-07-18-wfs.md](references/browser-evidence-2026-07-18-wfs.md), [references/browser-evidence-2026-07-18-dynamic-schema.md](references/browser-evidence-2026-07-18-dynamic-schema.md), [references/browser-evidence-2026-07-18-native-ai.md](references/browser-evidence-2026-07-18-native-ai.md), [references/browser-evidence-2026-07-18-payments.md](references/browser-evidence-2026-07-18-payments.md), [references/browser-evidence-2026-07-19-global-reports.md](references/browser-evidence-2026-07-19-global-reports.md), [references/browser-evidence-2026-07-19-success-hub.md](references/browser-evidence-2026-07-19-success-hub.md), [references/browser-evidence-2026-07-19-content-recovery.md](references/browser-evidence-2026-07-19-content-recovery.md), [references/browser-evidence-2026-07-19-release-notes-gtin-mcs.md](references/browser-evidence-2026-07-19-release-notes-gtin-mcs.md), [references/browser-evidence-2026-07-19-ca-performance.md](references/browser-evidence-2026-07-19-ca-performance.md), [references/browser-evidence-2026-07-19-seller-app.md](references/browser-evidence-2026-07-19-seller-app.md) and [references/github-official-audit-2026-07-19.md](references/github-official-audit-2026-07-19.md); a research conclusion without a newly opened page, authorized software output or legal sandbox result is not a training increment.
- Read `config/platform_expert_training/walmart.json` when machine-readable routing, tool state, evaluations or gap status is needed.
- Recheck official sources when a rule is marked `time_sensitive`, when its verification date is stale, or before any external write.
- Treat seller reports, forums and courses as experiments, never as platform rules. Record sample, date, site and a falsifiable hypothesis.
- Before broad browsing, inspect the existing Skill, contract, curriculum, evaluations, failures, connector state and GitHub registry. Search for 2–3 mature SDK/SOP/schema/evaluation knowledge packages that target the exact gap; record license, maintenance, security, credentials, dependencies, overlap and country/store scope, then retain only the delta. Skip unchanged official introduction pages and use current deep official evidence only to verify package differences.
- Use English package-discovery combinations first: Walmart Marketplace/WFS/Connect plus `agent skills`, `playbook`, `SOP`, `checklist`, `template`, `evaluation`, `SDK`, `MCP`, `ERP`, `OMS`, `PIM` or `WMS`. Record the exact query, skip unchanged owner/repo fingerprints, and mark non-Walmart commerce packages `irrelevant_skip` rather than borrowing their platform contract.

## Collect visible evidence before distillation

1. Identify the exact store-bound execution identity, browser and software. Never mix it with another store or platform identity.
2. If no Walmart authorization exists, use only official public Seller, Developer, Ads or Help pages, official demos or a legal sandbox.
3. Actually open and navigate the surface. Record URL/product version, capture time, site, store mode, ownership, identity, clicks/scrolls, inputs, outputs, errors and permissions.
4. Classify each observation as `verified_live_fact`, `time_sensitive_evidence`, `historical_operator_trace`, `draft`, `failed_attempt`, `unknown` or `blocked_owner_input`.
5. Inspect Walmart-native AI first: entry, permissions, accepted inputs, outputs, edit/submit boundary, metrics and failure recovery.
6. Only then update rules, workflows, evaluations or tool mappings. With no new visible evidence, report no learning increment and make no knowledge change.

## Resolve the store route first

Require:

- `tenant_id`, `project_id`, `store_binding_id` and `execution_identity_id`;
- `platform=walmart`, `country_site=US|CA|MX`, `commerce_mode=marketplace_seller` and ownership;
- seller or partner ID, marketplace authorization state, currency, locale and settlement identity;
- fulfillment mode: `seller_fulfilled`, `wfs` or verified third-party warehouse;
- separate Walmart Connect advertiser ID and access type when advertising is involved.

Return `needs_platform_store` if no real Walmart store is bound. Return `needs_authorization` if the store exists but the required domain is not authorized. Do not create a cross-country `GLOBAL` write route or reuse credentials, browser identities, advertiser IDs, warehouses or settlement accounts across stores.

## Keep product data in the correct layer

- Platform public layer contains only Walmart rules, country sites, commerce/fulfillment modes and generic listing, ads, order, return and finance workflows. Never place a tenant product, price, image, inventory, warehouse or customer fact here.
- Category capability layer is replaceable. Load the current site/product-type schema and compliance requirements for apparel, home, beauty, electronics, food/restricted goods, digital goods, mechanical equipment or the actual category. If the category or schema is unavailable, return `unknown`; do not invent fields or use apparel as the universal template.
- Tenant/project/product layer contains the user's product, variants, cost, price, images, rights, inventory, capacity, lead time, brand and compliance evidence. Resolve `tenant_id + project_id + product_id + store_binding_id` before reading it.
- Task evidence layer contains one listing, campaign, order, return, media, customer or failure run. Never promote its private facts to another product or user; only reviewed, anonymized methods may become reusable rules.
- Current private_tenant product and sales projects are regression samples, not T One defaults. Never inherit their identifiers, prices, size/color matrices, images, inventory, warehouse, customers or cross-sell process into a Walmart task.
- For a new external user, accept their project/store binding and imported product table or images, identify candidate fields, then request only missing hard facts and current Walmart category fields. Without user evidence, keep facts `unknown`.

## Keep concepts separate

- Treat Walmart Marketplace as the commerce platform and `marketplace_seller` as the commerce mode.
- Treat WFS as a fulfillment program, never a store type. Verify enrollment, item eligibility, inbound inventory and country-specific rules before using it.
- Treat Pro Seller as a performance status. US and CA criteria differ; do not infer Mexico criteria without current official evidence.
- Keep general Seller Performance separate from Pro Seller eligibility. The Apr 15 Canada page lists five general metrics, but its metric-description table uses strict comparators while its `Meets Standard` bands use inclusive comparators at the same values, and its VTR attention band contains malformed source text. Preserve that conflict and return `needs_review` for an exact-boundary decision until current Walmart clarification or an authenticated CA dashboard status resolves it; never copy either table to US or MX.
- Treat Marketplace APIs and Seller Center as seller-operation surfaces. Treat Walmart Connect Ad Center and advertising APIs as separate authorization surfaces.
- Treat domestic/international as seller origin and onboarding evidence, not as another commerce mode; keep the target country-site route.
- Treat Walmart Marketplace SEM as a US-only, Marketplace-OAuth Google Shopping acquisition surface using Walmart-managed bidding. Keep it separate from Walmart Connect and the seller's own Google Ads identity.
- Treat Walmart Connect `Reporting Only` access as read-only. Require `Full-Service` partner access plus advertiser authorization and owner confirmation for campaign writes.
- Treat the Walmart Seller App as a US mobile interface over existing Seller Center domains, not as a commerce mode, API authorization or second connector. The May 11 guide says it cannot manage CA, MX or CL; keep that market-management boundary separate from iOS and Android download restrictions.
- Treat the Walmart product catalog, offer, SKU, item ID, variant group, ship node and fulfillment program as separate objects.

## Run the operating workflow

1. Validate account, site, business identity, policy status and authorization scopes.
2. Validate product facts, IP/compliance, identifiers, condition, category and current site-specific item schema.
3. Search the catalog, choose match versus full item setup, build the Listing draft and validate feed status.
4. Reconcile offer price, promotional price, inventory, ship nodes, delivery promise, returns and margin.
5. Check listing quality, Buy Box/offer competitiveness and only then prepare activity or advertising experiments.
6. Separate Marketplace promotion writes from Walmart Connect advertising writes and build an approval package.
7. Retrieve, acknowledge and process orders; gate shipment, cancellation and refund writes.
8. Handle customer service through permitted Walmart surfaces; do not send unsolicited marketing messages.
9. Reconcile payments, commissions, refunds, shipping, WFS and advertising costs before reporting profit.
10. Write back store-scoped outcomes, failures, stale-rule flags and the next verified action.

## Build truthful Listing drafts

Require real product and route facts: SKU, GTIN/UPC or verified exemption path, product type, title, brand authorization, condition, key features, description, images, variants, price, inventory, ship node, fulfillment mode, returns and compliance attributes.

For a US GTIN/UPC exemption, first verify a legitimate no-identifier use case, admin-level Seller Center access, exact brand and current Product Type. Keep `Approved`, `Processing`, `Needs info`, `Denied` and `Closed` distinct. Approval is scoped to the approved brand plus Product Type and still requires a four-hour wait before item setup; it is not a universal product-ID waiver or publication proof. Request, appeal and item setup are separate external writes.

The current US WFS FAQ contains one narrow catalog exception: an existing WFS item that already has a product ID cannot replace it with an exemption and must be set up as a separate listing to apply an approved exemption. Use this only after exact current-page, item, brand, Product Type and exemption checks. Never generalize it into duplicate-item permission or use it to evade content ownership, AI, catalog-match or policy controls.

Fetch the current official item taxonomy/specification for the target site and product type. Do not rely on a permanent cross-platform field list or copy US-only Spec endpoints into CA/MX workflows.

For the US API path, pin `feedType + spec version + Product Type`, retrieve the current taxonomy and Get Spec response, preserve the raw JSON Schema, and validate required fields, enums, formats, limits and conditional requirements. Treat HTTP 207 as a partial response with both schema and errors. Recheck the official version/diff table before migration. CA and MX must use their own current guides, schemas and feed types; never copy the US contract across sites.

Return:

1. `listing_status`: `draft_ready`, `needs_review`, `blocked`, `needs_platform_store`, `needs_authorization` or `approval_required`.
2. Verified facts, assumptions and unknowns as separate lists.
3. Catalog-match/full-item-setup decision and required dynamic fields.
4. Title, key features, description, attribute and media drafts grounded in facts.
5. Price, inventory, fulfillment, returns and margin checks.
6. Feed/API or Seller Center execution plan with current connection state.
7. A pending approval action; never claim publication from a draft or accepted feed receipt.

## Use Walmart-native AI as a reviewed suggestion layer

- For the evidenced US-facing flow, enter `Growth > Success Hub > Edit Listings with Gen AI`, search existing catalog items by SKU, Item ID or item name, inspect Item ID and Content Quality Score context, and select one item at a time. The public guide/GIF demonstrates this workflow; it is not a live store connection or tenant item list.
- Treat generated product name, description and key features as an editable draft. `Use this Suggestion` selects or keeps a draft; `Submit changes` is a separate external write that requires a final diff, verified facts/schema/compliance/rights and explicit owner approval. Submission does not prove Walmart.com displays the content.
- Keep AI output optional and fallible. Reject unsupported brand, material, origin, compatibility, performance, nutrition, health or other claims. Never import product IDs, scores, images, prices or facts from the public demo.
- Route each Success Hub suggestion by effect. Content, price/Repricer, WFS, inventory, review incentives, SEM and Flash Deals have different permissions, costs and approvals; never expose one generic accept-all action. Refresh dated suggestions before action and never guarantee performance.
- Treat Pro Seller AI-powered performance insights as a separate, US Seller Center read/recommendation surface under `Growth > Pro Seller`. The Jul 16 release establishes the public capability but not a matching store session, entitlement, private metric input, exact output, API or result. Keep it `available_unconnected`; verify the daily metrics and tier refresh state before drafting any resulting action.
- Keep CA/MX Gen AI availability `unknown`; localized exact routes showed `No Data found`, not an unavailability policy. Smart Assistant navigation/inputs/outputs also remain unknown without an authorized store trace. Community reports are failure hypotheses only, and duplicate-item workarounds are prohibited.
- If generated content conflicts with verified tenant facts or will not save, preserve the original facts and exact diff, separate schema validation from unified-catalog content privilege and content-quality rejection, then follow Feed ID, Activity Feed, Pending Review and approved support evidence. Never copy the AI text back merely to satisfy a gate, disable controls, create a duplicate item or claim the problem is universal from one community thread.

## Use the Seller App without inventing mobile completion

- Require the matching US Seller Center account, authorized device/app installation and store binding before any private read. Public guides, transcripts and demo screens prove only the dated interface contract; they do not prove a T One connection, tenant data, entitlement, store status or successful write.
- Route notifications, catalog, price/inventory, orders/returns/refunds/tracking, WFS monitoring, payment statements and performance back to their existing domain modules. Do not create a duplicate mobile Agent or assume an app login supplies Marketplace API OAuth.
- Keep mobile `Good`, `Monitor` and `Urgent` as aggregate performance labels. An authorized private read is required for actual metrics and Insights drivers, and those labels do not establish Pro Seller eligibility.
- Treat WFS inventory in the current app material as monitoring. Never infer WFS enrollment, eligibility, stock or arbitrary inventory-edit authority from a public screen.
- Keep public demo products, SKUs, prices, inventory and WFS counts outside tenant/project/product/store/task facts. For any approved price, inventory, cancellation, refund, tracking or shipped-status change, record a scoped diff and verify the effect.
- Present force-close, notification settings, logout/login and Support as dated troubleshooting steps. Do not install, downgrade, clear data, log out, change roles or 2-step verification, or contact Support automatically; stop on any CAPTCHA or account-security prompt.

## Verify content ownership and post-submit effects

- Before suggesting an item-content update, distinguish a dynamic-schema problem from a content-ownership restriction. In Walmart's unified catalog, multiple sellers may submit the same item's content; brand owners and authorized resellers receive priority, and a seller without privileges may see even blank fields locked.
- Do not invent a value, create a duplicate item, reuse another seller's role or claim a platform defect when a field is locked. Explain the official Brand Portal, Brand Manager or Support route and keep the action `blocked_owner_input` until the matching seller supplies owner-controlled trademark or letter-of-authorization evidence through a secure approved workflow.
- Treat Brand Manager application, legal-document upload, Support contact and email submission as external actions. Prepare a checklist and request explicit approval; never ask the user to paste trademark, identity or authorization documents into chat.
- After an approved `Submit` or `Submit changes`, record the Feed ID and a pending effect. Inspect Activity Feed for feed type, processing status, submitted/pending/error counts and an error report; inspect Pending Review for policy holds when applicable; then verify the published item or authorized API state. A success receipt or `Processed` status alone is not publication, display, content ownership or business success.
- Recover by fixing the source and resubmitting the original feed, or by creating a new feed containing only failed items. Do not resubmit unchanged data repeatedly. Keep documented waiting periods, file limits and throttle values country- and date-scoped.
- For the dated Canada page, `Received`, `Processing`, `Processed` and `Error` are feed states while SKU errors remain separate. Its 4–6 hour timeout wait and 6–8 hour item-to-inventory wait are CA evidence only. The equivalent Mexico path returned `No Data found`; keep MX behavior `unknown` instead of copying US or CA.

## Reconcile payments without inventing payout or profit

- Keep five evidence states separate: available report date, successfully downloaded and checksummed report, parsed statement/reconciliation rows, matched orders/refunds/fees/deposits, and owner-authorized payout or bank confirmation. Never skip a state.
- Use the US Payment Statement for current-cycle account summary and transaction details; use Recon JSON for transaction-level order, commission, refund, WFS-charge and adjustment matching. Preserve raw payload, report date/identity, store/site route, pagination such as `nextOffset`, unmatched rows and checksum before normalization.
- Treat `openingBalance`, `closingBalance`, `paidToYou`, scheduled settlement, transaction net and bank deposit as distinct values. An available report date is not payment, a public response example is not store data, and a Walmart report alone is not profit.
- Calculate profit only from verified tenant-scoped product, fulfillment/WFS, shipping, return/refund, advertising, tax and other costs. Return unknowns rather than importing private_tenant or another product's costs.
- Scope the observed report contracts to US. CA/MX guide-path substitutions returned 404, and a Global FAQ conflicts with the dedicated Payment Statement schema; keep CA/MX contracts `unknown` and block connector normalization until current API Reference, legal sandbox or an authorized payload resolves the route and schema.
- For migration, inspect the latest dated Global partner API mapping workbook by market. Interpret `Global availability=No` only as “no active Global partner API equivalent identified”; do not convert it into “the legacy US endpoint is unavailable.” The 2026-07-06 mapping lists no Global equivalent for the inspected US Payment Reports and no CA/MX payment-report row, so keep US on its verified market-specific path and CA/MX `unknown`.
- Prefer the relevant US API Reference over the conflicting Global FAQ for response-shape design. Preserve the FAQ as a dated conflict, preserve raw responses at runtime, and keep the connector unconnected until a legal sandbox or authorized store payload passes acceptance.
- Treat static sandbox data as read-only mock data and dynamic sandbox as US-only. A 401 `/dataset` attempt means credentials are required; never fabricate headers or reuse another store key. Sandbox output proves parser/integration behavior only, never a production payout, reconciliation or profit.

## Gate advertising and activities

- Classify Sponsored Products as Walmart Connect on-platform advertising. Do not mix it with Google, Meta or TikTok off-platform acquisition.
- Classify Marketplace SEM separately. Its algorithmic bids, budget recommendations and projected impact remain suggestions; create, update, stop, delete or auto-apply requires the US SEM authorization and owner approval.
- Treat the public Marty/advertising-assistant evidence as a dated Walmart Connect layer, not a second Agent runtime. The 2026-01-06 source described Sponsored Search chat as beta, with bidding, keyword, billing and alert guidance plus four research reports; broader rollout and FY27 insights were future statements. Require a current matching Ad Center entitlement before saying the assistant or any report is available.
- Treat Automated Creative Generation's 80% time reduction as an early-beta, limited-period median from creation to submission, not a quality, ROAS, availability or tenant-performance guarantee. Generated creative remains a draft with product-fact, rights, brand, policy and owner review.
- Before any Connect API read or integration test, check the current Deprecation Log. For the 2026-07-15 changes, reject `advertiserAttributes`, `keywordRecommendations`, removed legacy attributed-sales metrics, request fields `bid`/`reportDate` and response field `suggestedBid`; use the documented replacements only after schema and account-access verification. Never send a deprecated payload just because a placeholder connector accepts it locally.
- Keep Campaign Recommendations read/report semantics separate from budget writes. `outOfBudget` and `itemAlerts` may inform a draft; suggestions, missed-opportunity estimates and health dimensions do not authorize budget, bid, item, shipping, price, review or campaign changes. Treat public `Smart Performance (alpha)` survey text as research-only and never submit feedback without approval.
- Verify advertiser ID, account access, partner type, catalog eligibility, stock, offer competitiveness, listing quality, budget, attribution window and stop-loss rule.
- Keep `research_only`, `available_unconnected`, `connected_read_only`, `connected_write_gated` and `blocked` states explicit.
- Require owner confirmation before promotional price, deal submission, campaign creation, bid/budget change, creative submission or launch.

## Handle WFS and customer obligations by country

- Verify WFS separately for US, CA and MX. Do not transfer one country's enrollment, inventory or fulfillment-center identity to another.
- Treat WFS inbound-quantity, restock, seller-fulfilled-to-WFS and unpublished-item recommendations as read-only decision inputs. Estimates and suggested units do not authorize conversion, replenishment, publication or inventory commitment.
- Require `recommendation → item/eligibility check → inventory/cost/margin check → inbound or conversion draft → owner approval → write → status verification`.
- Keep US recommendation API evidence scoped to US until current CA/MX endpoint or authorized Seller Center evidence proves availability.
- Treat Walmart Multichannel Solutions (MCS) as an optional WFS-based fulfillment extension for orders from other sales channels, not as a store type, Marketplace country route or proof of enrollment. Current US public evidence requires existing WFS use, a default billing method and eligible items; multi-box and big/bulky items are not eligible. Preserve the sales-channel ID, inventory pool, delivery option, order/fulfillment-request identity, fees and provider/API route. Seller Center order submission, provider connection and every fulfillment request remain authorized external actions.
- Keep the Jul 9 MCS Marty support improvement as dated public evidence only. Without an authenticated Seller Center route, its entry, exact prompt/input, response, edit/escalation boundary and effect remain `unknown`.
- For WFS items, confirm which fulfillment, returns and customer-support duties Walmart performs in that country; keep seller policy and financial responsibilities visible.
- For US seller-fulfilled items, validate ship nodes, delivery settings, tracking, return center, response obligations and performance metrics from current official policy. Late Shipment Rate measures handoff by Expected Ship Date and targets 5% or less; late `Shipped` marking, late first scan and missing/invalid scan are separate drivers. Preserve the Jul 9 release note's end-of-July accountability date instead of claiming enforcement early, and do not copy the US metric/effective date to CA/MX.
- For Canada Marketplace, treat the public `Performance > Order & Fulfillment` route as a documented navigation target, not as proof of a bound store or private account state. A performance suspension appeal or Business Plan of Action is owner-controlled external work: require the actual notice and tenant-scoped evidence, draft for review, and never guarantee reinstatement or submit a Partner Support case without confirmation.
- Before a US Shipping API request, run the dated carrier-name preflight. As captured Jul 19, use `Jitsu`, not `AxleHire`, and `Estes Forwarding Worldwide`, not `Estes`; stale values can fail validation and block order-status updates. Recheck Release Notes/API reference before release rather than freezing these names permanently.
- Never describe WFS or Pro Seller as evidence that an item is currently eligible, enrolled, in stock, winning the Buy Box or profitable.

## Protect execution and learning

### Audit official open source without inventing a connector

- Verify a GitHub organization through a Walmart first-party or verified official outbound link and a matching organization identity. A matching name, search position, stars or repository topic is insufficient.
- Separate `official ownership`, `seller-operation relevance`, `license`, `maintenance`, `security posture`, `country/store applicability`, `integration state` and `runtime validation`. None implies another.
- The captured `walmartlabs/walmart-api` is an archived, deprecated consumer Open API wrapper using an old API-key model; never route it as Marketplace Seller API, OAuth 2.0, item/order/inventory, Walmart Connect or WFS capability.
- The official `walmartlabs/partnerapi_sdk_dotnet` exists but was archived in 2020 and marked unsupported. Its Consumer ID/private-key sample is historical, not the current OAuth 2.0 connector contract; keep it `rejected_stale` and never mount or copy its credentials file.
- Treat the Whitebox TypeScript and Highside Labs PHP Marketplace clients as `extract_rules_only`: their token-cache, country namespace, pagination and generated-client patterns may inform tests, but 2022/2023 releases, open response/schema failures, absent security policies and second-language deployment costs block installation or code import.
- Keep `nexscope-ai/eCommerce-Skills/walmart-seller-guide` `research_only`: the reviewed beta file is a thin capability list without official citations, country/permission boundaries, errors, effects or evaluations, so it adds no delta to the existing unique Walmart Skill.
- Reject direct use of `stores-com/walmart-marketplace`: despite 2026 maintenance and tests, the reviewed client serializes secret-bearing constructor options as a token-cache key and exposes write methods without T One approval/effect gates. Do not install it; retain only non-executable correlation-ID, pagination and token-expiry test ideas.
- `walmartlabs/gozer` is an X12 parsing library and remains `research_only` for a future separately authorized EDI/supply-chain requirement. `walmartlabs/lacinia` is a general GraphQL engine and has no direct seller connector role.
- Before any future clone/install/run, recheck owner/repo plus commit/tag, license, dependencies, security policy/advisories, release/changelog, issues/PRs, data boundary and the exact existing T One module it would extend. Unknown or unmatched repositories stay `research_only`; archived/deprecated or incompatible assets stay blocked.
- Treat issue bodies, maintainer replies and community comments as dated project evidence. They cannot create Walmart Marketplace rules, fees, country support or live-connector claims without current Walmart first-party evidence.

Allow public official research, audits, drafts, simulations and sandbox work. Require owner confirmation for authorization, publish, price, promotion, ad spend, inventory commitment, shipment, cancellation, refund, external message, payment or settlement changes.

Always block CAPTCHA/MFA/verification bypass, anti-bot evasion, account-linkage evasion, credential sharing, cross-store authorization reuse, unlicensed media reuse, invented product facts, fabricated online status and unsolicited customer marketing.

Use the existing `LLMClient + config/multi_ai.json` gateway. Route by `reasoning`, `copy`, `image`, `video`, `ads` and `data`; do not create a second general Agent runtime. Keep public rules, tenant, project, store and task memory separate, and save only `credential_ref`, never secrets or buyer PII.
