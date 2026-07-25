# SHEIN expert curriculum

This curriculum is store-scoped and evidence-first. A module is not passed because a page, button, API name or test exists; it is passed only when the required decision record and regression evidence exist. Public rules are rechecked before use, and authenticated store facts never cross `store_binding_id`.

## Module map

| Module | Competency | Required evidence | Pass gate |
|---|---|---|---|
| `M00_evidence_identity` | Separate fact, evidence, operator trace, draft, failure, unknown and owner-blocked input | Source URL or store trace, capture time, site, mode, ownership, permission and validity | Every claim uses an allowed evidence status and has a review trigger |
| `M01_site_mode_route` | Route country/site, seller identity and commerce mode | Authorized store info for execution; official planning evidence for research | Supports only `platform_self_operated` or `semi_managed`; full-managed labels are recognition-only |
| `M02_admission_category` | Separate application screening, selection, approval/KYC, category/brand authorization and store activation; verify entity and compliance | Current official application plus live category/attribute/brand responses and applicable policy | Intake/marketing category taxonomies and revenue buckets never become authorization or hard-coded thresholds |
| `M03_listing` | Build SPU/SKC/SKU and media drafts from true product facts; resolve basic and linked attribute requirements iteratively | Dynamic publish standard, base attribute template, associated-attribute rules, enabled sites/currencies, quota and product facts | No invented material, size, price, stock, claims, rights or category permission; pending/failed-review SPUs never become approved detail results |
| `M04_price_inventory` | Keep seller price, semi-managed cost price, currency, total/locked/temporary-lock/usable/transit stock and warehouse separate; propose v2 inventory changes idempotently | Mode-specific store/order/schema and dedicated inventory responses; SHEIN/SKC/SPU identifier mapping, current `invType`, v2 permission, item idempotency key and partial-failure result | SPU detail is not inventory; usable inventory is not total inventory; deprecated v1/`warehouseType`, occupied stock, unsupported physical-warehouse mutation and public sample quantities never become a write |
| `M05_activity_ads` | Separate campaigns, seller promotions, flash sales, coupons, storefront/social/affiliate benefits and paid ads | Authenticated eligibility/stacking/account/billing evidence or official public research | A public `$0 Advertising` label does not prove free spend or an Ads API; no activation or spend without owner approval |
| `M06_orders_fulfillment` | Route seller fulfillment, integrated logistics, SFS, allowed third-party warehouse paths and order-event triggers | Live order/detail read, site, warehouse, fulfillment type, timeout, inventory-lock state and policy | Event payload is not full order truth; SFS is never a commerce mode; deduction triggers do not cross scopes; shipment confirmation stays gated |
| `M07_returns_service` | Reconcile return events/lists, read current case detail and prepare evidence-scoped customer-service decisions | Matching application/store/site/mode; event or overlapped list high-water mark; current return/per-goods status, waybills, receive/sign times, `goodsId`, media, reasons, charges and policy version | Event/list/carrier delivery are not warehouse receipt or refund authority; sign, refund and external message remain gated writes |
| `M08_finance` | Reconcile order, check-order and remittance fields by mode/site/currency | Store-scoped statements and mode-specific fields | No cross-mode formula reuse and no bank/tax/payment mutation |
| `M09_native_intelligence` | Distinguish seller-facing automation, internal platform AI, analytics, first-party-hosted guest claims and third-party tools | Current official source plus authenticated surface when available; transcript speaker attribution and rights boundary | Feature/card/report or a hosted transcript mentioning AI never becomes native AI, a ranking rule, an API or live connection claim |
| `M10_connector_runtime` | Map official capability to real T One connector state, enforce Webhook signature/durable acknowledgement and reject unsafe transports | Store binding, execution identity, credential reference, admitted dependency, callback/subscription proof and redacted read/write/event trace | Capability state advances only from observed store-scoped proof; event name/card is not a receiver; default-disabled TLS verification blocks integration |
| `M11_review_iteration` | Convert outcomes and failures into expiring rules and regression cases | Versioned rule, source fingerprint, duplicate-skip ledger, result/failure, supersession and next check | Only incremental knowledge is added; weekly conflict/synonym review and monthly stale-rule/tool/coverage review are recorded |
| `M12_scope_isolation` | Separate platform, category, tenant/product and task-evidence layers | Route-scoped product facts plus dynamic category schema and an anonymous non-project sample | No project price, variants, media, stock, warehouse, customer or workflow becomes a platform/category default |

## Practice sequence

1. Run `M00` and `M01` before every authenticated scenario.
2. Train `M02` through `M08` independently for `platform_self_operated` and `semi_managed`; never transfer a field or formula merely because the label looks similar.
3. Run `M09` as a capability audit, not a tool-promotion exercise.
4. Run `M10` against the real workspace state. Without a store binding, the correct result is `needs_platform_store`.
5. Run `M11` after every evidence change, rejection, API error, expired rule or store outcome.
6. Run `M12` for every reusable module with an anonymous non-apparel/non-machinery example; label any inherited project fact `scope_leakage` and block it.
7. For Listing practice, query the base template before linked rules, then keep review-state and inventory-source evidence separate from SPU detail.
8. For inventory practice, map seller/SHEIN identifiers, select exactly one identifier family, use `invType`, preserve lock/usable/per-warehouse fields and read the site-specific deduction trigger without performing a write.
9. For platform GitHub practice, establish an official identity chain from a SHEIN-owned page or verified domain before treating any organization or repository as official; then inspect README, docs, release/changelog, license, issues, discussions, pull requests, security and CI surfaces before proposing shared-registry admission.
10. For social-comment practice, cover available pinned/high-relevance/newest/author-reply/nested/counterexample surfaces and save only anonymous themes. When comment bodies or sort controls are login-gated, record `blocked_comment_access`; reactions never substitute for comments and no sentiment or frequency may be inferred.
11. For inventory-write practice, migrate new work to v2, bind a stable per-item idempotency key, preserve occupied stock, inspect `failedList` under top-level success and stop before the owner approval gate.
12. For Webhook practice, validate app/store scope and signature, deduplicate, durably enqueue, acknowledge within the documented threshold, then query current detail asynchronously; never turn an order/return trigger into shipment or refund approval.
13. For return reconciliation, query the list by a selected time dimension with a store-scoped overlap and 30-row pagination, deduplicate by return number/update time, read details in batches of at most 30, then compare carrier, platform and seller/warehouse receipt evidence. Apply the tightest known developer/store limit and stop before sign, refund or outbound response.

## Evidence exercises

Each exercise must produce:

- one normalized preflight record from `decision-workflows.md`;
- a claim table using the statuses in `evidence-status-and-rules.md`;
- the smallest safe next action and all owner approval items;
- expected post-action evidence and an idempotency/compensation note for any proposed write;
- at least one regression case when the increment exposes a new failure mode.

## Completion rubric

- `seeded`: official evidence and a draft decision exist.
- `evaluated`: a deterministic regression case passes.
- `store_verified`: an authorized store response proves the fact for one exact site/mode/ownership scope.
- `operationally_validated`: an owner-approved action produced expected evidence and a store-scoped outcome.

No current module may be labeled `store_verified` or `operationally_validated` until a real SHEIN store, execution identity and matching authorization are present.

## Current evidence binding

These bindings prevent the curriculum from becoming a reasoning-only syllabus. `browser_observed` means a public page was actually opened and interacted with; it is not store verification.

| Module | External evidence anchor | Current level |
|---|---|---|
| `M00_evidence_identity` | Open Platform login redirect observed after clicking `智能客服`; isolated browser version recorded | `browser_observed` |
| `M01_site_mode_route` | Public self-operated/semi-managed/full-managed/POP/SHEIN self-run application table plus mode guides; POP remains unmapped | `browser_observed` |
| `M02_admission_category` | Current U.S. application fields, 25-choice intake taxonomy, 17-family pricing catalogue, historical/community selection language and live-schema boundary | `browser_observed` |
| `M03_listing` | Product Listings, mode-specific publish solutions, associated-attribute rules, and approved-only SPU detail with a 2026-07-10 update record | `browser_observed` |
| `M04_price_inventory` | Current inventory-query schema plus v2 mutation page expose identifiers, `invType`, usable/occupied boundaries, per-item idempotency, partial failures and the 2026-12-31 v1 retirement; no signed store response or write | `browser_observed` |
| `M05_activity_ads` | Marketing Promotions plus current `$0 Advertising` public benefit group; no paid-media account/API/billing/eligibility | `browser_observed` |
| `M06_orders_fulfillment` | Semi-managed guide, inventory FAQ and current `/order_push_notice` page distinguish fulfillment deductions and event-trigger/detail-read boundaries | `browser_observed` |
| `M07_returns_service` | Current `/return_order_push_notice`, `/return-order/list`, `/return-order/details` and the linked customer-order return/refund solution. List/detail pages are self-operated and semi-managed; the 2024 UK community case is only a dated receipt-gap counterexample | `browser_observed`; no signed read, live case, sign-API schema review, refund or message |
| `M08_finance` | Semi-managed check-order API entries; no store statement | `browser_observed` |
| `M09_native_intelligence` | Listing Optimizer public card, login-gated Developer `智能客服`, US Analytics click and current first-party-hosted `Scaling Smarter` transcript; unlabeled AI/structured-data claims remain single-case and T One search returned no Listing Optimizer capability | `browser_observed` |
| `M10_connector_runtime` | Fixed test tools plus Webhook setup/signature/encryption/1.5-second acknowledgement and limited retry docs; T One exact event searches returned zero; no callback, subscription or redacted event trace | `browser_observed` |
| `M11_review_iteration` | Eight browser evidence cycles, source/version fingerprints, v1 supersession, GitHub duplicate skips, comment zero/block boundaries, stale-ref/locator recovery, software registry observations, failure records and regression corpus | `evaluated` |
| `M12_scope_isolation` | Product-scope contract plus anonymous home, beauty, appliance, toy, pet, electronics, food/restricted-goods, digital and general B2B regression cases | `evaluated` |

The public evidence series is summarized in [official-evidence.md](official-evidence.md). Dated raw browser traces are intentionally excluded from the public release. No module is currently `store_verified` or `operationally_validated`.
