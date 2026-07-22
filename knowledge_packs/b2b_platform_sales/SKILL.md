---
name: b2b-platform-sales-operator
description: Operate T One's B2B platform sales specialist for Alibaba.com, Made-in-China, Global Sources, TradeKey, and other explicitly evidenced B2B marketplaces: seller/store readiness, catalog and keyword drafts, RFQ and inquiry qualification, platform messages, paid-platform diagnostics, quotations, orders, and handoff to the shared export workflow. Use when work starts from a B2B marketplace or platform account rather than independent outbound prospecting.
---

# B2B Platform Sales Operator

## Load the shared foundation

1. Read the authority files required by `AGENTS.md`.
2. Read `skills/b2b-foreign-trade-sales/SKILL.md`. It remains the canonical account timeline, qualification, quotation, negotiation, delivery, collection, and approval workflow.
3. Read [source-and-boundaries.md](references/source-and-boundaries.md) before using the user training document or any fixed threshold from it.
4. Reuse `ai_ecommerce_director/b2b_sales_runtime.py`; do not create a second CRM, customer, quote, order, payment, or shipment runtime.

## Resolve one exact platform route

Require `tenant_id`, `project_id`, `task_id`, `platform_id`, `country_site`, `store_model`, `ownership`, `store_binding_id`, `execution_identity_id`, `product_id`, and `account_id` before a state write. A platform family such as “B2B 平台” is not an executable account.

Treat these as separate routes: `alibaba_com`, `made_in_china`, `global_sources`, `tradekey`, and any future platform supported by current exact-platform evidence. Never transfer seller level, RFQ quota, message permissions, fees, traffic, keyword data, paid placement, buyer rank, Trade Assurance, order, payment, or dispute behavior between platforms or country sites.

Without an authorized seller account, keep store status, entitlement, quota, performance, buyer identity, inquiries, messages, orders, payments, and platform-native AI input/output `unknown` or `blocked_owner_input`.

## Run the platform workflow

1. Inventory the existing Skill, platform expert, training contract, connector, catalog, account timeline, evidence, and GitHub admission registry. Repair or extend; do not rebuild.
2. Establish the exact seller/store identity and current platform surface. Separate public documentation from authorized account state.
3. Prepare product/category/attribute, storefront, keyword, content, and paid-placement diagnostics only from the matching tenant product facts and current platform schema. Unknown price, MOQ, inventory, capacity, lead time, certification, warehouse, or media stays `unknown`.
4. Treat matched RFQs, inquiries, buyer ranks, activity, platform AI, suggested replies, and traffic estimates as candidates or intermediate states. They are not qualified buyers, sent quotations, orders, revenue, or receipts.
5. Deduplicate the company into the shared canonical account timeline. Preserve platform inquiry/RFQ ID, buyer account ID, source URL, timestamp, target product, destination, quantity, requested terms, and evidence strength.
6. Qualify request fit, decision role, quantity, destination, timing, commercial fields, sanctions/export-control escalation, and fraud signals. Do not reject or accuse a buyer from a single heuristic.
7. Draft a platform reply or quotation through the shared workflow. Stop before Send, Submit Quotation, paid RFQ access, ad spend, catalog publish, order acceptance, contract, payment, refund, or shipment.
8. Advance a stage only from the correctly scoped external receipt. A visible button, generated text, approval, API 2xx, or screenshot is not a receipt.

## Prefer mature knowledge packages

Before repeatedly opening official introductions, search the existing assets and approved GitHub registry for maintained B2B marketplace playbooks, schemas, SDK samples, ERP/CRM/OMS connectors, evaluation sets, and failure traces. Audit owner, license, version, commits/releases, core files, tests, issues/security, credentials, telemetry, writes, dependencies, deployment cost, overlap, and exact platform/site/mode scope.

Use only `keep_reuse`, `merge_into_existing`, `extract_rules_only`, `research_only`, `rejected_stale`, `rejected_license`, or `rejected_unsafe`. Unknown license blocks copy, install, and commercial integration. Use current deep official documentation only to verify time-sensitive differences. A public homepage, search snippet, tool name, README, passing unit test, or install button does not prove a live connector.

## Share cross-cutting capabilities

Reuse the shared legal/IP, product-truth, communications, CRM, pricing/profit, trade compliance, fraud, video, documents, logistics, payment, security, and approval capabilities. Do not create platform-local copies. Keep one customer owner across platform and outbound channels; route evidence to the same account timeline and prevent duplicate or contradictory contact.

## Hard stops

- Do not log in, connect a store, change seller settings, publish products, bid, buy traffic/RFQ access, send a message or quotation, accept an order, commit a contract, request/confirm money, ship, refund, or open a dispute without the matching authorization and item-level owner confirmation.
- Do not scrape private buyer data, bypass login/CAPTCHA/rate limits, reuse another platform/store identity, or automate account-evasion behavior.
- Do not promote fixed budgets, response times, buyer-score cutoffs, platform ROI, fees, quotas, or country habits from the user course into machine truth without current exact-platform evidence.
