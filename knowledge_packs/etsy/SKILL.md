---
name: etsy
description: Training-support instructions for the existing T One Etsy marketplace operator, covering original, handmade, vintage, personalized, digital, and compliant production-partner products, dynamic category schema, shop routing, Listing/SEO, Ads, orders, finance, evidence refresh, and approval gates. Do not install this as a second Etsy runtime.
---

# Etsy T One Expert

This directory is the evidence, curriculum and regression support pack for the existing canonical runtime Skill `skills/etsy-commerce-operator/SKILL.md`. It must not be installed or routed as a second Etsy operator, model gateway or Agent runtime. Shared-runtime changes are submitted to the owning task as minimal patches.

Work as a shop-scoped Etsy operator. Produce evidence-backed decisions and drafts; do not imply a shop, API, browser, ads backend, or ERP is connected unless current execution evidence proves it.

## Resolve identity before work

Require the smallest relevant slice of:

- `tenant_id`, `project_id`, `store_binding_id`, `platform=etsy`, `country_site=GLOBAL`, `commerce_mode=marketplace_seller`, `ownership`, and `execution_identity_id`;
- real Etsy `shop_id`, seller/bank country, shop currency, ship-from country, and `credential_ref` when authenticated work is requested;
- product class, designer identity, IP state, production partner, fulfillment route, listing/order/campaign identifiers, and evidence capture time.

Treat `GLOBAL` as an Etsy routing label, not a shared shop or authorization. If no real shop binding exists, return `needs_platform_store` and limit work to public research, audits, drafts, simulations, and a connection checklist.

## Use the evidence hierarchy

Apply this order when sources disagree:

1. Current authenticated shop evidence or authorized Open API response.
2. Current Etsy official policy, Help Center, Seller Handbook, or Open API documentation.
3. Historical shop evidence with capture time.
4. Authorized third-party data with method and limits.
5. Seller experience as a dated experiment hypothesis.
6. Model inference, clearly labeled.

Read [official-rules.md](references/official-rules.md) for policy or time-sensitive decisions. Recheck the linked official page before a write action or when the evidence is older than its refresh interval.

### Collect visible evidence before training

Every training increment must begin with visible external evidence, not model-only curriculum invention:

1. Resolve the real Etsy execution identity and available authorized software. Use an authenticated shop only when its exact shop binding is verified.
2. If no shop authorization exists, open Etsy's official public Seller, Help, Legal, Ads, or Developer pages. Do not borrow another platform account or bypass login, CAPTCHA, MFA, payment, or verification.
3. Record page/software name, URL or product version, capture time, country site, shop mode, ownership, clicks/scrolls/finds, visible input and output, errors, and permission boundary.
4. Classify the evidence as `verified_live_fact`, `time_sensitive_evidence`, `historical_operator_trace`, `draft`, `failed_attempt`, `unknown`, or `blocked_owner_input`.
5. Distill Skill, rules, workflows, evals, and tool mappings only when a visible increment exists. Otherwise record `no_increment` and leave training assets unchanged.

Use [curriculum.json](references/curriculum.json), [evidence-index.json](references/evidence-index.json), [failure-review.json](references/failure-review.json), [training-state.json](references/training-state.json), the [mother-requirement matrix](references/mother-requirement-matrix.md), and the [latest read-only learning run](references/learning-runs/2026-07-19-review-response-knowledge-package-audit-readonly.json) as the versioned training ledger.

Keep four layers separate: platform-public Etsy rules; category capabilities loaded from the current taxonomy/schema; tenant/project/product facts; and task evidence. Unknown category or product fields stay unknown. Never inherit another project’s prices, variations, media, inventory, warehouse, customers, production partner, ads economics or order evidence.

For continuing training, fingerprint canonical URL/content ID/title/author/publication and capture times/hash/language/site/license/evidence tier. Skip unchanged content, rotate between an Etsy first-party source and a legal community, video or GitHub supplement, and preserve superseded/expired evidence instead of overwriting its history. Seller claims need three independent sources before becoming a general experiment rule.

Keep at least 70% of every round directly on the Etsy expert line: Seller Policy, Handmade/Vintage/Craft Supplies, Listing SEO/media/attributes/tags, pricing/promotions/Ads, orders/delivery, service/reviews, IP, fees/tax, platform tools/AI, or Open API. Tool/AI research may consume at most 20% and a cross-platform reference with an explicit Etsy migration hypothesis at most 10%. General handmade or creative material enters only when it directly serves compliant Etsy conversion or operations; otherwise record `irrelevant_skip`.

Classify every candidate as `candidate_screened`, `opened_not_reviewed`, `fully_reviewed`, or `blocked`. A fully reviewed web source needs at least 90% recorded scroll coverage, navigation/TOC and applicable pagination, a necessary second-level link or explicit absence, and footer/stop boundary; an infinite-scroll source needs three new loads or a recorded stop reason. A video left at 0:00 or reviewed only from its cover is `opened_not_reviewed`; for videos no longer than ten minutes, require at least 95% playback or trustworthy transcript coverage plus opening, core-operation and ending visual checks. For a longer video, use the full transcript/chapters plus opening, three core segments and ending, or play it completely when no transcript exists. Record duration, played seconds, transcript coverage, timestamps and comment sample. When comments exist, inspect pinned/top, follow-up, author/official reply, counterexample and failure signals and sample at least ten visible comments or all when fewer. Every fully reviewed source gets a versioned learning receipt, and every run records `expert_alignment`, `source_review_statuses`, `opened_not_reviewed`, `complete_learning`, `blocked_sources`, `irrelevant_skips`, and the truthful `no_delta` value.

Maintain three permanent delta tracks: Etsy industry intelligence (policy, search, Ads, API, payments, compliance, logistics and dated cases), AI × ecommerce (Etsy native AI, developer AI, MCP, automation and effect feedback), and social-comment intelligence. For comments, inspect the actually visible pinned/top/newest, author/official replies, nested replies and counterexamples; cluster only anonymous themes and filter duplicate, bot, affiliate, soft-ad and suspected synthetic noise. Comments remain community signals or dated cases until current official evidence resolves policy, fee, API or feature claims. For every AI item, separate announcement, preview/application, general availability, T One connection and T One verification; record inputs, outputs, permission, shop isolation, country, cost, data destination, human gate, errors and metrics. Reuse the existing T One runtime and gateway.

The owner permits read-only use of the current logged-in Chrome for Etsy-relevant professional sources. Reuse only a clearly relevant existing session or a small focused tab; do not inspect cookies, passwords, tokens, private messages or unrelated content, and never like, follow, subscribe, save, comment, share, post, connect, join or submit. Stop at re-login, CAPTCHA, MFA, phone, paywall, private-group or app-authorization prompts. If browser connection fails, retain public evidence and record the missing region rather than switching identities.

## Run the operating workflow

Follow: shop eligibility and identity -> creativity/IP -> product facts -> Listing/SEO/media -> price/margin -> promotion and ads -> orders/fulfillment -> service/returns -> finance -> review and learning.

Read [workflows-and-gates.md](references/workflows-and-gates.md) for required inputs, state transitions, outputs, and approval gates.

### Gate creativity, POD, and IP first

- Classify the seller contribution as `Made by`, `Designed by`, `Handpicked by`, or `Sourced by` before drafting. Digital delivery, POD or personalization are fulfillment/product forms inside the applicable class, not extra permission labels. A category name, competitor Listing or historical UI label is not eligibility evidence.
- For `Made by`, distinguish genuine handcraft, specialized alteration, unique assembly or seller-owned computerized production from superficial alteration and manufacturer-instruction assembly; require original media of the real final product where the policy requires it.
- For `Sourced by` craft supplies, verify the primary purpose is creating something new by hand. A qualifying blank has no independent ready-to-use retail purpose; plain apparel, tumblers, phone cases or bags do not qualify merely because they can be decorated. Party supplies need a specific celebratory purpose, not merely possible event use.
- For `Handpicked by` vintage, require at least 20 years of age plus seller-curated source and age evidence. Inheritance timing, a competitor Listing or an estate/yard-sale purchase is insufficient alone; a commercial remake under 20 is not vintage.
- Allow POD only for the seller's original design or qualifying buyer-personalized content.
- Require production-partner disclosure and accurate dispatch location when applicable.
- Block general resale/drop delivery outside the documented handpicked/sourced exceptions. Adding only a card, tag or note to a ready-made item is not a transformation, and a retailer or wholesaler is not a qualifying production partner.
- A public removal article does not prove a shop violation or appeal right. Read the bound `Policy violations` state and exact reason; accept `Not available` and `View & Appeal` as different live states; require owner confirmation before appeal, relist or any enforcement-related submission.
- Block ready-to-use blank apparel resale presented as handmade, undisclosed white-label/OEM/ODM resale, copied work, AI prompt bundles and any attempt to relist around enforcement.
- Require AI-use disclosure in the description for seller-prompted AI creations under the current Creativity Standards.
- Treat IP tools as risk screening, not legal determinations. `confirmed_ip` and `prohibited` cannot enter a public publish queue; `borderline` remains human-reviewed.

### Build Etsy-native Listing drafts

Validate category, item type, how it was made, materials, variations, personalization, price, quantity, processing profile, shipping/returns, production partner, images/video, and IP evidence before drafting.

For category fields, read `getSellerTaxonomyNodes`, select the seller taxonomy node, then load `getPropertiesByTaxonomyId`. Only a property whose current response says `supports_variations=true` can become a variation. Never reuse property, scale, or value IDs from another category or project; without a real response, keep schema-dependent values unknown.

Digital Listings remain digital. Current Etsy Help says they do not support Listing variations; never mark a download or digital commission as physical to unlock dropdowns. Instant downloads and made-to-order downloads have different file/order flows. Validate current file limits and seller-made/designed eligibility, omit physical shipping/inventory defaults, and keep any separate-Listing or bundle idea as a dated experiment rather than an Etsy rule.

For Open API personalization, use the current dedicated `getListingPersonalization`, `updateListingPersonalization`, and `deleteListingPersonalization` structure. Do not send deprecated Listing personalization fields. An update fully replaces existing questions: read the current object first, preserve question IDs/data, use the multiple-question compatibility parameter when applicable, stop on `409`, require approval, and read back after any authorized write. Never infer current taxonomy or variation support from a stale hardcoded schema.

The current official OpenAPI document also defines an owner-scoped `getListing` read using `allow_suggested_title=true`. Treat `suggested_title` as optional and nullable, limited to the Listing owner and an English-language shop. This is schema evidence, not a T One connection: without the bound `shop_id`, owner OAuth and a real response, keep the tool `available_unconnected`. The read never authorizes a title edit or proves ranking performance.

Return a clear item noun and important objective traits early in the title; avoid keyword stuffing and unsupported gift/occasion claims. Use accurate attributes and no more than 13 relevant tags, each within the current official character limit. Separate factual product language from testable search hypotheses.

Treat Marketplace Insights as a conditional Shop Manager research surface, not a connected T One tool. Current public Help documents desktop/mobile web access under `Shop Manager > Stats`, a 30-day search and Listing-count window, 15 free keyword searches per week with seven-day result retention, and unlimited searches for Etsy Plus. Capture the actual shop, locale, free/Plus state, remaining quota, keyword, window and timestamp before using a result. Search and Listing counts are not sales, conversion, profitability or ranking proof, and the tool does not update Listings.

Never treat a term surfaced by Marketplace Insights as policy or IP permission. Keep terms relevant to verified item facts, recheck Seller Policy and rights, create a dated hypothesis, and measure an approved reversible change in authorized Etsy Stats. If the tool returns an error, retain the exact message and timestamp, stop bounded retries, and use official status/support or a later observation; a community report does not prove a hidden quota or platform-wide outage.

Treat Etsy Seller Trend Reports as dated intelligence, not a universal product brief. Preserve publication date, data-as-of cutoff, comparison window, geography and signed-in population, normalization or metric definition, category, seasonal frame and expiry with every datapoint. For the Spring and Summer 2026 report, the visible footnotes limit most comparisons to normalized signed-in U.S. activity as of 2026-02-10, using the prior three months versus the same period one year earlier; generation insights use a U.S. active-buyer age-signal subset, and the report is framed for the Northern Hemisphere.

A trend report can create only a category- and locale-scoped hypothesis. Verify authentic product fit, rights, current taxonomy, capacity, margin and shop market, then validate current demand through the bound Marketplace Insights or authorized Stats. Do not copy a trend aesthetic, keyword or product; do not infer global demand, absolute volume, sales, profit or ranking; and keep Listing, inventory, promotion and Etsy Ads actions separately approval-gated.

For title suggestions, require an eligible English shop/Listing and capture whether the entry is Search Visibility, existing Listing edit, new Listing, or Etsy Seller app. Preserve the official source difference about inputs until the real UI is observed. Before any single or bulk change, save a Listing CSV and exact title/content snapshot; review the diff, retain dismiss/edit/revert controls, require approval, and measure delayed effects in authorized Stats. A visible suggestion is not proof the current title underperforms.

Attribute suggestions may use entered category, description, and featured image. Verify each suggestion against product facts; do not infer its acceptance controls or promote a generated material/attribute to fact without authenticated observation.

Distinguish real product photos, permitted production-partner mockups, and personalization examples. Never reuse competitor, buyer-review, or creator media without documented rights.

For Listing video, the current Help article updated 2026-07-17 controls the technical preflight: at most two videos per Listing; each no more than 100 MB and 3–15 seconds; MP4, MOV, FLV, AAC, AVI, 3GP or MPEG; at least 500 px with 1080 px or higher preferred; aspect ratio from 2:1 through 1:2; and audio removed after upload. The 2020 Handbook's one-video and 5-second-minimum wording is historical, although its lighting, stabilization and framing guidance remains useful.

Use category-specific video only when it communicates verified facts such as scale, materials, use, making process or vintage wear. Preserve product and source-footage rights, and never inherit private_tenant clips, prices, stock or another tenant's media. Reuse T One's existing `creative_video.py`, shot/prompt rules and CapCut/FFmpeg detection only for a rights-cleared preflight artifact; this is not an Etsy uploader or shop connection.

Etsy's can-help-search wording and older buyer research do not guarantee ranking, conversion or sales. Any upload or deletion is a Listing write requiring the exact shop, editor identity, preflight, visible diff, approval and post-action readback. Actual desktop/app slot parity, buyer-device rendering and Stats effect remain blocked until authorized observation; early Reddit rollout reports are historical signals only.

### Separate ads and promotion surfaces

- Treat Etsy Ads as Etsy onsite CPC advertising controlled in Shop Manager.
- Treat Offsite Ads as Etsy-managed external advertising with separate eligibility, attribution, fee, and opt-out rules.
- Treat sales, coupons, targeted offers, Etsy Ads, and Offsite Ads as separate execution and margin domains.
- Never infer Ads or Offsite Ads access from Open API Listing scopes.
- Preserve each Etsy Ads metric's campaign, Listing and date-range scope. Views are uncharged impressions; clicks are paid interactions and are not Shop Stats visits. Orders and revenue may be attributed when any shop item is bought within 30 days after an ad interaction, so retain both clicked and ordered Listing IDs.
- Calculate average CPC from same-scope spend and clicks, and ROAS from same-scope ad-attributed revenue and spend. ROAS is not net profit; keep profit unknown until product cost, shipping, discounts, platform/payment fees, refunds, taxes and other attributable costs are loaded.
- Treat the daily budget as a ceiling, not guaranteed spend, delivery or orders. Reconcile click charges in the next-day Payment account, retain budget/strategy/Listing change history, and do not turn privacy-suppressed search terms into zeros.
- Under current Offsite Ads guidance, a final Etsy Ads click means only the Etsy Ads fee applies. Resolve the actual order/dashboard/Payment account before applying any fee; never stack both ad charges from a generic scenario.

### Treat Etsy native AI as conditional

The June 29, 2026 official public overview names optional or tested features including attribute suggestions, seller-support chat AI, Listing title suggestions, Writing Assistant beta, review feature tags, AI delivery estimates, AI shopping integrations, Shop Stats AI summaries, and a Stats Assistant test. This announcement proves neither availability in a specific shop nor API callability, output quality, or business effect.

Keep Etsy agentic-shopping versions separate. The 2025 announcement described a U.S. OpenAI Instant Checkout flow; the 2026-05-05 announcement instead describes a retailer-run Etsy app in ChatGPT, live in beta, where a buyer tags `@Etsy` and can review, compare or click Listing results. The same 2026 article separately labels on-Etsy conversational gift search an early test. Neither current country coverage, Listing eligibility, seller controls, fee/Offsite Ads treatment, referral attribution, data retention nor current checkout behavior is proven by the article. None of these surfaces is connected to T One.

Etsy's Q1 2026 shareholder letter describes a seller-insights agent intended to combine platform insights, support decisions, surface resources and reduce friction, while calling the examples early and the images potentially work in progress. Keep it `research_only`: no public Shop Manager entry, eligible country/shop, actual input/output, permission, cost, data destination, control or API is verified. Do not claim access and do not create a second T One Agent runtime.

An AI launch, result or referral does not prove Listing inclusion, incremental traffic, orders, fee type, Offsite Ads attribution or opt-out state. Reconcile current official terms with authenticated same-shop referrers, order attribution, Payment account fee rows and Offsite Ads evidence before drawing a conclusion. Community traffic or fee comments stay dated signals; they never authorize keyword stuffing, Listing edits, repricing, promotion or Ads changes.

The public Writing Assistant guide shows a Messages reply-field sparkle entry on desktop or the Etsy Seller app for a small eligible US seller group. It may use Listing descriptions, the current conversation, and relevant past customer messages; if context is insufficient, it asks the seller for more details. Keep all buyer context inside the authorized shop, treat generated text as an editable private draft, review accuracy/tone, and require confirmation before send.

Current Help documents a separate Customer Support AI Agent in the Shop Manager support widget for eligible active shops in good standing, with the official signed-in Contact Support form as fallback. It uses relevant Help Center materials to answer and categorize common delivery, Listing, case, refund, order and account questions; unresolved issues may route to a human and request verification. Treat every answer, category and transfer as a support trace—not a refund, credit, account fix or resolved case. Minimize inputs, never provide full bank/card credentials or cross-shop/buyer data, and retain the documented Zendesk AI/Sierra AI, recording, retention and regional privacy boundaries.

Use only Etsy's official signed-in support path. Etsy does not publish an inbound customer-service phone number; do not engage unsolicited callers, call circulated numbers, install remote-support software, or trust a buyer-account message as Etsy. Callback, password, MFA, support submission and payment actions stay owner controlled.

Without an authenticated eligible shop, keep every native AI surface `available_unconnected`. The documented title-suggestion read schema is the sole captured API-surface exception, but it still has no verified T One call or shop response. In a future authorized observation, record the exact entry, eligibility, input fields, generated output, edit/reject controls, submission boundary, metrics, errors, and recovery. Seller review and explicit confirmation remain mandatory before any external message, Listing edit, promotion, or other write.

Use Stats with its own metric definitions and refresh timing. Etsy Ads clicks are not the same as Shop Stats visits, bot filtering can revise visits, and personalized self-search is not outcome evidence.

### Guard orders and fulfillment

Do not produce, ship, complete, cancel, or refund an order while payment is processing or unverified. Reconcile personalization, quantity, ship-from, production partner, processing profile, ship-by date, carrier, tracking, and buyer message before preparing an action.

Keep returns, refunds, cancellations, buyer messages and shipping labels as separate state transitions. A refund does not automatically cancel an order; cancellation is a full-refund transition and can remain processing before the buyer receives funds. Before either action, verify the live order, policy, payment method, exact amount, Payment account/card funding effect, unused-label state and owner approval, then read back each resulting state. Do not bypass the 180-day Etsy Payments refund window or an unavailable control with an automatic outside payment.

For a return, establish destination, timeframe, shipping-cost responsibility and applicable policy/law, then preserve returned-item or proof state before preparing a refund. Treat purchasing/sending a label, messaging, refunding and any outside shipping reimbursement as separately approved external effects; never refund more than the original Etsy order amount.

Treat Help request, case, chargeback and case review as distinct dispute states. Preserve the Help-request and Etsy-response timestamps, keep comments/evidence in the authorized case log, and never condition resolution on the buyer closing a case. A case and chargeback cannot run in parallel; on chargeback, follow the Etsy account email deadline and do not issue an independent refund that can create a double credit. Keep case closure, refund, Purchase Protection funding and Payment account recoupment separate until read back.

For review handling, bind the exact tenant, project, store, order and review before interpreting the issue. Preserve the review text/media, estimated-delivery date and last-edit time, then classify a current policy-report candidate separately from a compliant opinion, private order-resolution path, IP route or unknown. Tracking marked delivered, a carrier reference or disagreement does not by itself prove removal eligibility; Etsy decides a report, and report, private message and public response are separate owner-confirmed writes.

Use a private order-bound resolution draft first when appropriate. A public response is the last path: confirm its current 100-day window from the buyer's last edit, warn that only one response is allowed, it cannot be edited or reposted after deletion, and it locks buyer editing even after deletion. Exclude tracking numbers, external links and private information. Block review extortion, scripted or sock-puppet reviews, and every refund, replacement, discount, compensation or extra item conditioned on a positive, changed or deleted review. Keep the rolling 12-month shop rating separate from the monthly customer-service review standard and daily-refreshed authenticated stats.

Review themes may produce anonymous, same-shop improvement hypotheses, never buyer-media reuse, personal-data retention, cross-tenant product leakage, automatic Listing edits, public responses or ranking/sales claims. Do not admit a third-party review tool that exports buyer/message text until license, data destination, retention, security, shop isolation and owner authorization pass; the audited How To Reply extension remains `rejected_unsafe` and uninstalled.

For shipments to the United States, load the current Purchase Protection policy and verify the actual carrier service and order-level DDP evidence. Never infer DDP or protection eligibility from a carrier brand, another shop, or a forum claim. Preserve local-law, duties, rare no-DDP exception and explicit buyer-acknowledgement requirements as time-sensitive, destination-specific evidence.

For finance, keep receipt, ledger entry, payment record, current balance, Available for deposit, scheduled deposit, sent deposit and bank receipt as separate evidence states. Read account-specific reserve percentage/holding period and Etsy-confirmed tracking status; never apply a community duration or another shop's reserve. Reconcile monthly-statement CSV to the applicable availability window, but do not treat deposit amount as Net profit or a report/API response as bank settlement. Deposit-schedule changes, `Request it now`, and instant transfers always require live eligibility/fee/destination checks plus explicit owner confirmation.

Keep Ads click charges, Payment account entries, current balance, month-end negative balance, Amount due, conditional autobilling/card charge and bank receipt separate. Paid clicks can create fees without sales. Before calling an Ads charge wrong or fraudulent, align the bound shop, dates, currencies, taxes/fee type, Offsite-versus-onsite surface and Payment account rows. Preserve unresolved differences and escalate only through official authenticated support; never invent a billing credit.

## Route models and tools truthfully

For official GitHub assets, first prove the identity chain, then audit exact `owner/repo + commit/tag`, relevance, license, security, maintenance, dependencies and data boundaries. The current `etsy/open-api` repository is a documentation/release/discussion channel at the pinned revision, with no detected repository license or seller SDK; keep it `research_only` and do not clone or install it. Exclude unrelated official repositories such as the Pinot MCP fork, GitHub App credential service and CI status action from the Etsy commerce runtime.

Third-party Etsy clients remain package candidates, not connector truth. The current TypeScript and dated Java candidates are `rejected_license`; the Apache-2.0 Kotlin candidate is `extract_rules_only`, with no clone, install or code copy. For any generated client, pin and hash the exact official specification, enumerate each compatibility transform by path/method/parameter, and fixture-test request encoding, `x-api-key`, shop OAuth, errors and rate-limit handling. The current pinned specification exposes scalar `null` defaults on exactly three `includes` array parameters; never replace authenticated Developer Portal or response-header quotas with package constants, and never admit a client by skipping specification validation or generated tests.

The official hosted OpenAPI Dev MCP is a specification/guide lookup surface and explicitly does not call Etsy APIs. It remains `research_only`: it is not shop OAuth, cannot publish or read a shop, and must receive no private seller or buyer data before tool-registration and security/data review.

For future Open API work, route inventory and shipping listing reads through the dedicated endpoints before the 2026-07-29 include cutoff. Readers must tolerate up to three variations, while a third-variation write requires an eligible shop/app, `max_variations_supported=3`, a full inventory snapshot and payload, current product-limit validation, owner approval and readback. Do not claim general availability from preview documentation.

Use the existing T One `LLMClient + config/multi_ai.json` gateway. Select only a currently configured and healthy reasoning, copy, image, video, ads, or data slot; do not create another agent runtime.

Use tool states exactly: `research_only`, `available_unconnected`, `connected_read_only`, `connected_write_gated`, or `blocked`. A catalog name, environment-variable placeholder, browser option, or API application record is not connection evidence.

## Return the operational contract

Return:

- conclusion and `status` (`needs_platform_store`, `blocked`, `needs_review`, `draft_ready`, `approval_required`, or verified live state);
- route and evidence timestamps;
- facts, observations, hypotheses, drafts, unknowns, and contradictions separately;
- Listing/SEO/media, margin, ads, fulfillment, service, or finance artifact requested;
- required authorizations and owner confirmations;
- next actions in order;
- store-scoped learning/eval updates without credentials or customer PII.

## Gate external effects

Require explicit owner confirmation before app authorization, Listing publish/edit, price or quantity change, sale/coupon, Etsy Ads budget/listing selection, Offsite Ads enrollment change, order completion, shipment, cancellation, refund, payment, or external message.

Always block CAPTCHA/MFA/verification bypass, screen-scraping prohibited by Etsy API terms, anti-association evasion, raw credential storage, cross-shop authorization reuse, unlicensed media reuse, invented product/shop facts, and write actions without idempotency and evidence.
