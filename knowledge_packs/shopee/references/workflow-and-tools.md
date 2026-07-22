# Shopee workflow and tool boundaries

## Operating workflow

1. **Access and compliance** — Resolve site, seller origin, account program, ownership, store identity, permissions, prohibited/restricted products, IP evidence, tax/entity inputs, and policy freshness.
2. **Product and Listing** — Validate product facts, variations, category attributes, language, images, price, inventory, parcel dimensions, shipping promise, returns, and mobile-first copy. Output a draft.
3. **Pricing and inventory** — Use site currency, actual fees, logistics, tax, voucher burden, affiliate commission, and target margin. Never invent fee rates or stock.
4. **Activities and vouchers** — Read the site/store’s eligible campaigns and stacking rules; simulate margin and stock; queue enrollment or voucher creation for approval.
5. **Shopee on-platform ads** — Require the exact store/site Ads identity, eligibility, budget, objective, product/video eligibility, stop loss, and attribution window. Keep separate from off-platform ads.
6. **Orders and fulfillment** — Read authorized orders, map SKU/warehouse/carrier, check handling deadlines, and prepare shipment actions. Distinguish seller fulfillment, platform logistics, FBS, and third-party warehouse.
7. **Customer service and returns** — Draft local-language replies from order evidence. Refunds, return decisions, compensation, and external messages require approval.
8. **Settlement and profit** — Reconcile order revenue, platform fees, ads, vouchers, affiliate commission, logistics, taxes, refunds, COGS, and settlement. Missing inputs remain unknown.
9. **Competitor monitoring** — Analyze public, permitted facts and structures. Do not bypass anti-bot controls or reuse competitors’ protected media.
10. **Review and learning** — Compare drafts, approved actions, live results, and failures. Store results by site/store/task and expire rules when the official source changes.

## Platform-native AI audit

Inspect native AI before proposing external automation, but never infer access from a terms page.

For each site/store record: feature name, entry path, eligible seller tier, accepted product/store/local-file inputs, rights/privacy constraints, generated outputs, edits, download/save/publish boundary, performance metrics, error messages and recovery path. A public article is `time_sensitive_evidence`; actual store visibility and generated results need an authorized identity.

Current observed increment: TW Seller Help search input `AI` returned 16 results. The official AI Product Image/Try-on article documents Seller Centre and App paths, qualifying seller tiers, generation/edit tools and a Seller Centre manual-download boundary. Following My Products redirected to login, so current store eligibility, real inputs/outputs, metrics and errors remain `blocked_owner_input`. SG/MY/PH/TW AI terms describe possible services but do not prove feature availability.

TW AI Store Customer Service increment: the public 2026-04-17 Seller Help article documents `Seller Centre > Customer Service Settings Management > AI Store Customer Service`, limited to specific sellers. It can be scheduled 24 hours/custom/closed; it may answer product, delivery and returns/refunds questions; the seller can view, pause, intervene or reply. Handoff occurs for a buyer request, inability to answer, three repeated questions, dissatisfaction, risk content, or the buyer choosing seller chat. After a transfer, AI does not reply again for 24 hours and response-rate measurement begins for the seller. Metrics are unique served users, answered questions excluding “do not know” or transferred questions, and helpful ratings. Seller-defined FAQ cards are only buyer-selectable cards and are not the AI answer source. The real entry redirected to login, so all store-scoped status, chat, output and metrics remain `blocked_owner_input`; enable/close/intervene/reply actions require owner approval.

## Current tool truth

| Tool/surface | Current state | Allowed now | Unlock requirement |
|---|---|---|---|
| Existing `LLMClient + config/multi_ai.json` | `connected_read_only` | Reasoning, localization, drafts, structured analysis | Use configured model health/budget checks; it never supplies store authorization. |
| Shopee Open Platform | `available_unconnected` | Official documentation research and interface design | Approved developer app, OAuth/shop authorization, scopes, credential reference, store mapping, and connector tests. |
| Shopee Seller Centre browser | `available_unconnected` | Public help research only | Isolated per-store browser profile, owner login/MFA, explicit task approval, and evidence capture. |
| PH Shopee Standard Product | `available_unconnected` | Official workflow, exact-match, pending-deadline, renewal and conditional Hot Listing eligibility research | PH store binding, authorized Seller Centre/App, current master control, eligibility, match/link/pending/renewal state, and item-level approval for Link/Don't Link/Modify/Confirm/Change/Unlink/Test/Update/Adopt/evidence upload/Publish. |
| Shopee Ads/Video/Live backend | `available_unconnected` | Official feature research and campaign drafts | Separate store/site Ads identity, eligibility, balance/budget, and owner approval. |
| ERP connector | `available_unconnected` | Schema/mapping draft | Real ERP tenant/store authorization, SKU/order/warehouse mapping, webhooks or tested polling, and idempotent writeback. |
| Report import | `available_unconnected` | Analyze a user-provided Shopee export after provenance checks | A real site/store report and data mapping. |
| Shopee Spy, SellerSprite, Ecomhunt SEA, browser plugins named in the mother proposal | `research_only` | Candidate evaluation only | License, current product existence, terms, login, API/export capability, country coverage, privacy/data boundary, and deliberate connection decision. |
| Sea AI Lab `sail-sg` organization | `research_only` | Official identity/repository audit and multilingual research discovery | It cannot unlock a Shopee connector. Recheck owner/repo+commit/tag, relevance, license, security, data, dependencies and cost before any proposal. |
| `sailor2`, `sailcraft`, `sailor-llm` | `research_only` | Offline architecture/evaluation hypotheses only | Separate code/model/dataset licenses, SECURITY state, dependency integrity, data rights/destination, GPU/cost and approval; use the existing unique gateway only. |
| `envpool`, `zero-bubble-pipeline-parallelism` | `research_only` / excluded | No current Shopee use | Official but no direct seller-operations fit; the latter is a fork with multi-license/GPU/open-bug risk. No integration proposed. |
| `congminh1254/shopee-sdk` | `extract_rules_only` | Per-store token namespace, manager separation and structured-error reference | Do not install; replace plaintext token/logging and write-test paths with the existing DPAPI/credential-ref/approval system, then verify each endpoint against current official docs. |
| `EcomPHP/shopee-php` | `extract_rules_only` | Doc-first module/checklist reference | MCP server/installer, token payloads, duplicate `.mcp.json`/Skill and missing declared binary are rejected. No install/runtime. |
| `JimCurryWang/python-shopee` | `rejected_stale` | Historical failure counterexample only | 2018 release, v1/v2 ambiguity and open current-API failures; no code or endpoint reuse. |
| `easycb/easycb-go` | `candidate_screened` | None until full review | Search result only; license/security/credentials/tests/site scope and overlap not yet audited. |
| Kameleo Shopee scraper guide | `rejected_unsafe` | None | Anti-detect, CAPTCHA/OTP, proxies/accounts and cookie/profile export conflict with T One policy. |

Never upgrade a state because a name is present in a registry, prompt, webpage, or package.

BR fulfillment increment: public Help now documents seller preparation versus `Full` distribution-center preparation and express `Full/Rápida/Turbo`, plus in-stock/made-to-order cancellation and buyer refund timing. These remain `available_unconnected` evidence surfaces: no BR store binding, Full enrollment, inventory location, order state, payment method, refund result or seller settlement is connected. The existing order/ERP/finance path should be extended with a fulfillment-mode field, one-hour/48-hour deadline state and a buyer-refund-versus-seller-settlement discriminator; no new connector or page is required.

TH order increment: extend the existing listing/order adapter with `listing_preparation_type`, payment cutoff, current DTS, new/small-seller exception evidence, Bulky channel, LSR state, no-schedule/scheduled-not-handed-over cancellation clocks, carrier-fault evidence and event override. Do not create a new page or encode a universal country default.

Open Platform increment: extend the existing connector contract with exact identity type/id, app category/scope, validated redirect, CSRF state, authorization/sign/code/token/key expiry, per-shop/merchant signing, SIP parent/affiliate relation, encrypted credential reference, structured banned/unlinked/suspended/expired/wrong-store errors and production-versus-sandbox marker. No credential or live connector exists yet.

## Approval package

For a proposed write, include `store_binding_id`, country site, shop identity reference, execution surface, action type, object IDs, before/after values, evidence, dry-run result, margin/stock/risk checks, idempotency key, rollback/compensation plan, approval expiry, and approver role. Store only `credential_ref`, never raw tokens or passwords.
