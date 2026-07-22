# Etsy workflows and gates

## Contents

1. Status model
2. Evidence-first training preflight
3. Shop intake
4. Listing and SEO
5. Ads and promotion
6. Orders and fulfillment
7. Service, native AI, finance, and learning
8. Output contract

## 1. Status model

- `needs_platform_store`: no real shop binding or `shop_id`; public research and drafts only.
- `blocked`: prohibited product/action, failed IP gate, cross-shop credential attempt, verification bypass, or missing non-negotiable evidence.
- `needs_review`: policy, IP, legal, production, image, or evidence ambiguity needs a human reviewer.
- `draft_ready`: inputs support a draft, but nothing is live.
- `approval_required`: an external write package is complete and waiting for the named owner action.
- `verified_live`: a post-write readback confirms the exact shop, object, value, and capture time.

Never skip from draft to verified live. Use `approved_not_executed`, `submitted_unverified`, and `verified_live` as separate execution states.

## 2. Evidence-first training preflight

1. Resolve the exact shop execution identity and check whether an authorized Etsy Shop Manager, Ads surface, Open API credential reference, or approved sandbox exists.
2. When the owner has authorized the current logged-in Chrome for read-only research, claim only a clearly relevant visible tab or open one focused source. Do not inspect cookies, passwords, tokens, private messages or unrelated tabs; do not like, follow, subscribe, comment, join, submit or change settings. Stop on re-login, CAPTCHA, MFA, payment, private-group or application-authorization prompts, and record page/comment coverage plus the blocked region.
3. If none exists, use only public official Etsy pages. Record URL/version, capture time, locale, shop mode, ownership, clicks/scrolls/finds, visible input/output, errors, and access boundary.
4. Classify every record using the seven-state evidence taxonomy in the machine contract. A menu name, public announcement, test button, or tool catalog entry is not `verified_live_fact`.
5. Compare page evidence with the evidence index and expiry. Only a visible, source-scoped increment can change the Skill, rules, workflows, evals, or tool map.
6. If there is no increment, append a `no_increment` run record with the reason and do not manufacture learning assets.

## 3. Shop intake

1. Resolve tenant/project/store/shop/execution identity and ownership. Reject any capability pack whose platform, country/site, mode, ownership, store binding or execution identity does not match the selected task.
2. Confirm seller/bank country is currently eligible; flag China new-shop restriction and country-specific Payoneer/payment handling.
3. Read shop currency, ship-from, legal/trader status, Etsy Payments state, production partners, shipping/processing profiles, return policies, Ads and Offsite Ads state.
4. Record tool connection states. Without verified OAuth/browser evidence, keep Etsy surfaces `available_unconnected`.
5. Request credentials only through the encrypted connection UI as `credential_ref`; never in chat or task payload.

## 4. Listing and SEO

Required facts:

- tenant/project/product IDs and ownership proof; design/designer IDs only when the current item actually has them;
- item class and physical/digital type;
- current taxonomy/category plus its dynamically required properties; materials, dimensions, size chart, colors, variations and inventory/capacity only where supported and factually applicable;
- personalization fields and examples;
- production partner, actual ship-from, processing and shipping profiles;
- price, production, shipping, fee, return, refund, tax, and ad-cost inputs;
- image/video rights and representation type;
- IP state: `clear`, `borderline`, `confirmed_ip`, or `prohibited`.

Workflow:

1. Run creativity, prohibited-item, IP, AI-disclosure, production-partner, and image gates.
1A. Classify the verified seller contribution as Made, Designed, Handpicked or Sourced. For Made, distinguish specialized craft work from superficial alteration or manufacturer-instruction assembly. For Sourced craft or party supplies, record the primary creative/celebratory purpose and reject ready-to-use or generic event goods. For Handpicked vintage, require a 20-year threshold plus source, age-method, designer/collection, material/mark and photo evidence. General resale/drop delivery and card/tag/note-only changes fail this gate.
1B. When a Listing is removed, do not infer the shop reason or appeal right from public Help. Read the exact bound `Policy violations` record, capture `Not available` versus `View & Appeal`, build an evidence checklist, and stop at owner confirmation before appeal or relist. Never bulk relist or work around enforcement.
2. Validate taxonomy/category and dynamic required fields from the current Etsy schema. If the shop/schema is unavailable, keep schema-dependent fields unknown; never substitute an apparel, POD, warehouse or equipment template.
3. Resolve seller taxonomy with `getSellerTaxonomyNodes`, then fetch the chosen node with `getPropertiesByTaxonomyId`. Use only properties with `supports_variations=true`; never copy property/scale/value IDs across categories.
4. If the item is digital, keep it digital. Current public Help does not support Listing variations for digital items. Do not create a fake shipping profile; validate instant-download files or the made-to-order flow instead. Alternative separate Listings or bundles remain experiments, not platform rules.
5. Before any API adapter work, compare the current date and release fingerprint. From 2026-07-29, use the dedicated inventory and shipping Listing-read endpoints instead of deprecated includes. For a three-variation object, read and snapshot the full inventory, preserve all variations, validate current 2500/400 product limits and `max_variations_supported`, and block production writes until shop/app eligibility and GA are verified.
6. Treat the official OpenAPI Dev MCP as an optional documentation retrieval source only. Do not register or send private seller/buyer data until capability, security, retention and data-boundary review; its output cannot satisfy a shop readback or write gate.
5. For personalized Listings, read the dedicated personalization object. Model up to five typed questions, reject deprecated fields, and treat POST as a full replacement rather than a patch. Preserve existing questions/IDs. Send the multiple-question compatibility parameter only after the client can parse and preserve all current types; otherwise block the write.
6. Produce title, description, attributes, materials, 13-or-fewer tags, personalization questions/instructions, media checklist, price/margin scenarios, and risk notes.
6A. For Listing video, validate no more than two clips and check each clip against the current 100 MB, 3–15 second, documented-format, minimum-resolution and 2:1-through-1:2 aspect contract. Warn that Etsy removes audio; verify product facts, category fit and source-media rights. The preflight output is an artifact only and must not claim Etsy upload capability.
6B. Preserve any existing video and Listing state before proposing an upload or deletion. Bind the exact clip hash and diff to the shop/Listing approval, then read back both slots and buyer-visible rendering after an authorized action. A desktop/app or buyer-device mismatch remains an evidence state, not a reason for cross-shop deletion.
7. Label keywords and visual hypotheses; do not assert hidden search volume or ranking.
7A. For Marketplace Insights, require the bound Shop Manager, capture the free/Plus state, remaining quota, keyword, locale, timestamp and documented 30-day window, and preserve search count separately from Listing count. Do not infer sales, conversion, profit, country scope or ranking. A result can create only a policy-checked draft hypothesis; any Listing, inventory or Ads change remains separately approved and measured in Stats.
7B. On a Marketplace Insights loading error, retain the exact message and capture time, stop bounded retries, and use official status/support or a later observation. Do not convert a single community incident into a hidden Plus limit or platform-wide outage.
7C. For Seller Trend Reports, store the publication date, data cutoff, comparison window, geography/population, normalization/metric, category, seasonal frame and expiry with each datapoint. Reject a transformation from directional percentage to global, absolute or current shop demand.
7D. Convert a trend into a draft only after current tenant/project/product scope is loaded and authentic fit, rights, taxonomy, capacity and margin are verified. Validate demand in the bound Marketplace Insights or authorized Stats. Keep Listing, inventory, promotion and Etsy Ads changes as separate confirmation packages with reversible diffs.
8. For title or attribute AI, capture eligibility, exact entry, actual visible inputs, suggestion, edit/dismiss controls and source contradictions. For the documented title read, require the bound Listing owner OAuth and English shop language, request `allow_suggested_title=true`, and treat an absent/nullable value as no suggestion—not proof of quality or failure. Validate every attribute against product facts.
9. Before a title change, export the Listing CSV and store exact pre-change title/content plus a revert package. For bulk changes, review every Listing diff and keep approval scoped to the exact set.
10. Return `draft_ready` or the precise blocking/review state.
11. For publishing or personalization changes, create an idempotent approval package bound to `store_binding_id + shop_id + listing draft hash + current object hash`.
12. Stop on `409` or schema mismatch. After submission, read back Listing state/content and personalization questions before `verified_live`.
13. Do not infer improvement from suggestion presence. Wait through the documented reflection window and compare authorized Stats against the pre-change baseline; preserve clicks, visits, views, orders, conversion and revenue as separate metrics.
14. Do not infer ranking, conversion or sales lift from a Listing-video Help claim or historical buyer research. Measure only a shop- and Listing-scoped authorized experiment with baseline, outcome window and guardrails.

## 5. Ads and promotion

1. Load actual Listing availability, margin, inventory/capacity, delivery promise, conversion history, Ads state, Offsite Ads enrollment and attributed-fee state.
2. Keep shop sale, coupon, targeted offer, Etsy Ads, and Offsite Ads as separate actions.
3. Calculate margin scenarios with Listing/transaction/payment/regulatory/currency/production/shipping/refund/Etsy Ads/Offsite Ads inputs. Mark unknown inputs instead of filling them with defaults.
4. For Etsy Ads, preserve campaign/Listings/date range and read views, clicks, click rate, orders, revenue, spend, average CPC, ROAS and search terms separately. Treat privacy-suppressed terms and delayed data as unknown, not zero.
5. Reconcile Ads spend with next-day Payment account charges. Retain clicked and ordered Listing IDs because any shop item bought within 30 days can be attributed; never turn attribution into an incremental-causality claim.
6. Compute average CPC and ROAS only from same-scope values. Keep contribution margin and net profit unknown until actual costs, platform/payment fees, discounts, shipping, refunds and taxes are loaded.
7. For Offsite Ads, read enrollment, threshold, dashboard, order and fee. Apply the dated final-click precedence only after actual evidence; do not stack Offsite and Etsy Ads charges by assumption.
8. Draft hypothesis, listings, budget/discount, primary metric, guardrail, stop rule, review date, attribution method and change log. A daily budget is a ceiling, not a promised spend or result.
9. Require owner confirmation for launch, pause, budget, strategy, listing selection, coupon/sale, or Offsite Ads enrollment changes.
10. Read back the exact Shop Manager and Payment account surfaces after execution; never use an Open API success as Ads proof.
11. For sales/coupons, model each promotion separately, detect schedule or eligibility overlap from live shop evidence, calculate margin combinations, and stop at owner approval.
12. For an Ads billing discrepancy, align shop, date range, click rows, currencies, tax/fee type, Offsite-versus-onsite surface, Payment account line items, current balance and Amount due. Preserve the unresolved difference; use only official authenticated support and never promise a credit.

## 5A. Support AI, billing escalation and account safety

1. Verify the route is the current shop's signed-in official Shop Manager support widget or Contact Support form. Reject public inbound phone numbers, unsolicited calls, buyer-account impersonation and remote-support installation.
2. Capture support-AI availability, active-shop/good-standing eligibility, selected issue category, exact minimized question, Help-Center-grounded answer, human-escalation state and any official verification request.
3. Exclude full bank/card credentials, passwords, MFA codes, identity files, cross-shop finance exports and unrelated buyer data. Record the documented provider, recording, retention and regional privacy boundary.
4. Treat AI answer, categorization, transcript creation, human transfer and support submission as separate states. None proves a refund, billing credit, account fix, case resolution or payment.
5. Require owner control before support submission, callback request, password or MFA change, account recovery, payment, bank contact or dispute. After an authorized action, read back the exact Payment account, support case and account state.

## 6. Orders and fulfillment

1. Verify payment state; block production and shipment while payment is processing/not paid.
2. Validate personalization, variation, quantity, buyer destination, production partner, capacity, processing profile, ship-by date, carrier, and tracking.
3. Route factory/partner work as a draft until owner confirmation and required production evidence exist.
4. Require confirmation before completing, shipping, splitting, rerouting, canceling, refunding, or messaging about an order.
5. For cancellation, wait for processing completion, validate policy/eligibility and unused labels, show the full-refund consequence, and read back cancellation processing separately from buyer receipt.
6. For a refund, preserve it as distinct from cancellation; read exact amount, currency, reason, payment method, Payment account/card funding effect and the platform-controlled buyer destination before confirmation. Never bypass an unavailable or over-180-day control with an automatic outside payment.
7. For a return, establish destination, timeframe, shipping-cost responsibility and returned-item/proof state. Gate a label, buyer message, refund and outside reimbursement separately, and never exceed the original order amount.
8. Read back order/receipt state, shipment, tracking, notification, refund, cancellation and Payment account effects without collapsing them.
9. Record delays, defects, cancellations, returns, cases, and review themes at shop and Listing scope.

## 7. Service, native AI, finance, and learning

- Draft responses using order facts and shop policy; external Etsy Messages require confirmation.
- On a Help request, capture the labeled thread, received time, order facts and normal 48-hour escalation window. Etsy policy overrides a conflicting shop policy; keep the drafted response inside the bound Etsy thread.
- On a case, capture case ID/type, policy version, eligibility window, case-log deadline and requested evidence. Put all approved comments/attachments in the case log, respond to Etsy within the current two-calendar-day policy window and never ask the buyer to close the case as a condition of resolution.
- Keep `case_open -> evidence_requested -> Etsy/seller action -> case_closed -> funding/recoupment readback -> optional review` separate. A closed case does not prove Etsy funded the refund or that the Payment account was untouched.
- On a chargeback, stop any parallel Etsy case/refund path, follow only the authenticated Etsy evidence request and reconcile the Payment account debit without contacting the buyer's financial institution.
- For a review, first bind `tenant/project/store_binding/order_id/review_id`, preserve the exact review/media and last-edit timestamp, and verify estimated delivery plus the current 100-day windows.
- Classify `policy_report_candidate / compliant_opinion / order_resolution_candidate / IP_route / unknown`. A delivered scan or carrier mention is not removal proof, mixed item/service feedback may remain compliant, and Etsy—not T One—decides a report.
- Keep paths separate: `report draft -> owner confirmation -> report readback`, `private resolution draft -> owner confirmation -> message readback`, and `public response draft -> finality/privacy warning -> owner confirmation -> response readback`. Never use review reporting for IP claims.
- Public response is last: only once, uneditable and not repostable after deletion, locks buyer editing even after deletion, and must contain no tracking number, external link or private data.
- Block threats, shilling and compensation conditioned on a positive, changed or deleted review. Refund, replacement, discount, extra item and neutral promotion each retain their order, current-policy, jurisdiction, margin/funding and approval gates.
- Cluster only anonymous same-shop review themes into product/Listing/shipping/service hypotheses. Do not copy buyer media, store identifiers or personal data; do not import private_tenant or another tenant's product facts; do not auto-edit or claim ranking/sales causality.
- Treat Seller Purchase Protection as conditional; verify the order, payment, dispatch, tracking, message, and case evidence rather than promising coverage.
- For US-destination shipments, verify the actual carrier product is DDP and preserve label/customs/duties evidence. Do not infer DDP from a carrier name or community reply; treat the current rare no-DDP exception and buyer acknowledgement as order-specific evidence.
- Native AI public documentation proves only a conditional feature description. Until an authenticated shop observation captures the entry, permissions, input, output, edit/reject controls, submission boundary, metrics, errors, and recovery, keep the feature `available_unconnected` and do not invent output.
- For agentic shopping, create a versioned surface record before interpretation: publication date, live beta/test/historical state, country, Listing eligibility, seller controls, buyer input, result/checkout flow, fees, Offsite Ads attribution, data destination, metrics and T One connection. Keep the 2025 U.S. Instant Checkout announcement, the 2026 ChatGPT Etsy app beta and the separate on-Etsy gift-search test distinct.
- Keep the Q1 2026 seller-insights agent `research_only` until a public or owner-authorized shop entry proves eligibility, read/write scope, inputs, outputs, controls, cost and data boundary. Reuse the existing T One runtime; a shareholder-letter image is neither a connector nor execution permission.
- Reconcile AI referrals through the same authorized shop and period across referrer analytics, attributed orders, Payment account fee rows and Offsite Ads evidence. A launch, result or community comment is not evidence of inclusion, incrementality, fee type or opt-out state and cannot trigger a Listing, price, promotion or Ads change.
- For Writing Assistant, explicitly scope Listing descriptions, current-conversation messages and relevant past-customer messages to the same authorized shop. Never move buyer context across stores or use native-AI status to bypass review and send approval. If context is insufficient, request seller-supplied facts and keep the result as a private draft.
- For title suggestions, preserve the narrower title-guide input statement and the broader AI-overview statement as separate evidence until the actual eligible UI proves current inputs. The official OpenAPI schema separately documents an owner-scoped read for English shops; it does not expose the generation inputs, prove a T One connection, or authorize a write. Capture single/bulk controls, real-time feedback, CSV backup, approval, readback and revert.
- For attribute suggestions, capture category/description/featured-image inputs and actual accept/edit/reject controls. A suggestion never overrides verified materials, dimensions or compliance facts.
- For Stats, record timezone, date range, refresh timestamp, metric definition and traffic surface. Etsy Ads clicks are not Shop Stats visits; personalized self-search is not an outcome test.
- Escalate legal, IP, threat, payment, chargeback, account, and EU withdrawal questions.
- Reconcile gross order value, platform fees, payment fees, tax/VAT, currency conversion, ads, production, shipping, refunds, and designer/platform/factory settlement.
- Separate estimated margin from payment-account actuals.
- Reconcile `receipt -> ledger entry -> payment -> current balance -> Available for deposit -> scheduled -> sent -> bank received` without collapsing states. Every transition needs the bound shop/object, captured time and its own evidence.
- Read reserve percentage, holding period, affected orders and tracking-release state from the authenticated Payment account. Community timelines and another shop's reserve are never defaults; unconfirmed tracking is not release proof.
- Use the monthly statement CSV for the matching availability/deposit window and preserve fees/refunds/taxes/reserves separately. Deposit amount is not Net profit and the CSV is not bank settlement evidence.
- Treat deposit-schedule changes, `Request it now` and instant transfers as approval-gated payment actions. Before an authorized action, display live eligibility, amount, fee, destination, limit and post-action readback plan.
- Write back official rule changes, experiments, results, failures, and expired evidence. Seller experience remains a hypothesis until tested in the same shop/context.
- For every social or forum source, record the actually visible pinned/top/newest sorts, author/official replies, nested replies, counterexamples, visible count and inaccessible regions. Save only anonymous topic clusters, separate official replies from ordinary comments, filter duplicate/affiliate/bot/soft-ad/speculative noise, and route any policy, fee, API or availability lead back to current official evidence before distillation.

## 8. Output contract

```json
{
  "status": "draft_ready",
  "route": {
    "tenant_id": "...",
    "project_id": "...",
    "store_binding_id": "...",
    "platform": "etsy",
    "country_site": "GLOBAL",
    "commerce_mode": "marketplace_seller",
    "ownership": "...",
    "execution_identity_id": "...",
    "shop_id": "..."
  },
  "evidence": [],
  "facts": [],
  "observations": [],
  "hypotheses": [],
  "drafts": [],
  "unknowns": [],
  "risk_notes": [],
  "required_authorizations": [],
  "pending_approval_action": null,
  "next_actions": [],
  "writeback": []
}
```
