# Workflow and tool states

## Decision sequence

1. Identify the real browser/software and execution identity, then collect visible read-only evidence. If none is available, record `no_change` rather than inventing training.
2. Resolve seller entity and exact authorized market.
3. Resolve store/service mode and Choice context.
4. Resolve platform, category, tenant/project/product, and task-evidence scopes. Mark any unscoped tenant default as `scope_leakage`.
5. Check category, dynamic Product Schema, product/IP, price, inventory, warehouse, returns, and settlement facts. Missing facts remain `unknown`.
6. Check the required execution surface and its store-scoped connection evidence.
7. Produce an audit, draft, simulation, or approval package.
8. Execute only after authorization, eligibility, owner approval, and an isolated store lock.
9. Record the real result, failure, timestamp, and evidence status inside the same task scope.

## Tool-state contract

| Surface | Default training state | Evidence needed to advance |
|---|---|---|
| Public official terms/rules | `research_only` | URL, checked date, applicable entity/site/mode |
| T One LLM gateway | `connected_read_only` | Existing configured model health and task-safe data boundary |
| AliExpress Seller Center / CSP | `available_unconnected` | Bound store, isolated browser/OAuth identity, successful authenticated read |
| AliExpress platform API | `research_only` | Current namespace/application category, page authorization/environment constraints, approved app, OAuth scope, store binding, successful call |
| AliExpress Digital Marketing console/API | `available_unconnected` | Separate ads eligibility/account, billing state, authenticated read, approval gate |
| AliExpress seller Overseas Affiliate Network Marketing | `available_unconnected` | Bound seller eligibility, current promoted-product/rate/attribution/settlement state, authenticated read, approval gate |
| ERP/Miaoshou route | `available_unconnected` | Per-store authorization, site/mode mapping, supported read/write scopes, successful diagnostic |
| Third-party research tools | `research_only` | Terms/license, paid/login state, allowed data boundary, current access evidence |
| Chrome read-only control | `blocked` | Repaired supported runtime, visible tab inventory, isolated AliExpress identity, read-only capture |
| AliExpress platform-native AI | `research_only`; Seller claim and Rules-page `AI助手` surface observed, execution pending | Exact account role/site/mode, eligible authenticated seller entry, accepted inputs, observed output, edit/submit boundary, quota/cost, data destination, metrics, failure recovery |

Never upgrade a state because a config entry, UI button, marketing claim, or documentation page exists.

Do not transfer AI evidence across Alibaba platforms. A first-party Taobao/Tmall merchant-AI page proves only those named platforms. The current AliExpress Seller landing verifies only that the public surface names AI Agent scenarios for product publishing, new-product incubation, offsite marketing and customer-service consultation. Neither that page nor a media announcement supplies Seller Center entry, eligibility, real input/output, edit/submit boundary, metrics, recovery, or connection. A visible registration URL likewise does not prove registration, store activation, or feature entitlement.

Public Seller surfaces have three additional guards: broad global-reach copy is planning context rather than an executable country matrix; POP/海外托管/全托管/半托管 manager-contact checkboxes are inquiry interests rather than store authorization; and a public onboarding document is time-sensitive guidance, not permission to handle identity, UBO, funding, deposit, category, or brand actions.

For entry fees and category qualifications, the public overview is only an index. Resolve seller jurisdiction, exact mode, authorized leaf category, current rule revision and authenticated fee screen before using a value. The 2026-03-16 qualification table is expressly scoped to China-mainland-registered merchants in its named cross-border modes. The 2026-06-29 self-operated transaction rule makes the applicable category rate depend on order-release time and final transaction amount, with proportional return after cancellation or seller refund. None of these pages authorizes identity submission, category application or payment.

The Rules pages displayed `AI助手`, `限时免费`, `有新结果(0)` and a prompt invitation. No prompt, output or account entitlement was tested. Preserve this as `official_public_ai_assistant_surface_observed_execution_pending`; do not infer ongoing free cost, quota, data handling, edit/submit capability or T One connection.

An official announcement that Open API or ISV application types exist does not prove T One has an approved app or connection. An unofficial SDK README is weaker still: keep it outside the runtime until the shared GitHub registry admits a pinned version after license, maintenance, dependency, security, data-boundary, and isolated-test review.

Old official developer pages are `time_sensitive_evidence`: they can define an architecture or test hypothesis, but current endpoint, scope, field, limit, SLA, and eligibility must be rechecked. A Product Schema must be fetched for the exact seller/category and validated at task time.

The public API catalog observed 2026-07-19 exposes `aliexpress.solution.seller.category.tree.query`, `aliexpress.solution.product.schema.get`, `aliexpress.solution.product.list.get`, and `aliexpress.solution.order.get`. The category tree says it can filter to categories the seller may publish; the Schema and order pages show authorization and Jushita constraints. Keep these as current catalog candidates only. Do not save or replay documentation sample credentials, and do not interpret rotating sample timestamps or example success JSON as a store-scoped response.

`alonseg/AliexpressApi` is absent from the shared GitHub registry. Its package declares ISC, focuses on affiliate/product data, has no published GitHub releases, and depends on deprecated `request@2.88.2`; keep it `research_only_no_install` until the shared owner performs admission, maintenance, dependency/security, endpoint, credential-boundary and isolated-test review.

Keep seller affiliate marketing, the publisher Affiliate Program, Digital Marketing, and seller Open Platform API identities separate. A portal app id, key, token, report, or anecdotal redirect on one surface does not prove access to another. For seller API connection, record application approval, permission-group state, authorization strategy/seller scope, completed OAuth, token reference, and a successful store-scoped read as separate stages.

An official-looking host or UI is not sufficient source provenance. Require a named publisher, document identity/version/date, applicability, ownership/license, and a current official index or agreement before promotion to `official_current`. Do not copy store metrics, customer data, or media from an unverified public PDF or screenshot.

private_tenant product traces are project regression evidence only. The platform layer cannot contain their SKU, variation, price, media, inventory, warehouse, customer, capacity, or lead-time values. Category capabilities are replaceable, and an unknown category must use the current official schema rather than a clothing, machinery, or other project template. Shared B2B workflows accept any lawful project product and must not default to one cross-sell case.

## Browser and open-source states — 2026-07-19

- Existing logged Chrome: `blocked`. The supported read-only bootstrap again failed before tab inventory with the same process-property conflict. No tabs, cookies, tokens or account pages were read. Do not copy the session or create another identity; resume only after the existing plugin bridge is repaired.
- Alibaba Open Source catalog: `research_only`. The official site reverse-verifies only its exact repository links. Its visible 39-project catalog returned no AliExpress/速卖通 match.
- `higress-group/higress`: `research_only_no_install`. Official-linked, Apache-2.0 and active, but generic gateway infrastructure rather than an AliExpress seller connector; T One already has one gateway/runtime.
- `alonseg/AliexpressApi`: `research_only_no_install`. Unofficial, not admitted to the shared registry, no releases/security policy, no separate license file observed, and depends on deprecated `request@2.88.2`.

For GitHub, inspect README/docs, release/changelog, license, security, issues, pull requests, discussions and recent commits before deciding. Record exact owner/repo plus commit/tag and any redirect. An accepted answer, active issue discussion, star count or sample authentication code is never connector or business-completion evidence.

## Knowledge-package decisions and ad/API guards — 2026-07-19

- `nexscope-ai/eCommerce-Skills`: `extract_rules_only`, `research_only_no_install`. Reuse only three product-independent controls: request current unit economics before planning, label estimates and required replacement data, and keep generic budget recommendations non-executable. Its Google/Meta/TikTok PPC examples, unsourced benchmarks, marketing links and outbound tracking parameters do not become AliExpress rules or tools.
- `moh3a/ae_sdk`: `research_only`, `research_only_no_install`. Its dropshipping/affiliate client boundaries, unresolved invalid-token issue and unmerged order-details change do not provide seller Digital Marketing access, current endpoint proof or a safe connector.
- `bayborodin/aliexpress-sdk`: `rejected_unsafe`. Legacy port-80 default, process-global credential state, old runtime range and weak/mismatched tests fail T One transport and store-isolation requirements.
- `kk71/aliexpress-sdk-py3k`: `rejected_unsafe`. Plaintext authorization/API URLs and credential-bearing URL logging fail the security gate. Do not run unchanged code.

Generic PPC formulas are planning aids only. A contribution-margin or break-even calculation requires current product cost, platform/payment/transaction fees, shipping, returns/refunds, tax and attributable ad cost. Missing inputs stay explicit; historical Digital Marketing agreements do not establish a current product name, UI, permission, minimum recharge, rate, attribution, account balance or report. Campaign creation, budget change and spend require a bound store/ads identity, current authenticated read and a separate owner approval.

Package discovery uses English query combinations and then deduplicates `owner/repo + pinned commit or release + file hash`. Search snippets screen candidates only. Reopen a rejected or research-only candidate only after a commit/release, license, maintenance, security, shared-registry or AliExpress-relevance change.

## Order, inventory, shipment, and ERP capability matrix — 2026-07-19

Do not display one `AliExpress ERP connected` boolean. Resolve the exact store route and track these capabilities independently: `orders_read`, `order_delivery_sensitive_read`, `inventory_batch_write`, `shipment_declare_write`, `shipment_modify_write`, `shipment_query_read`, `returns_disputes_write`, and `settlement_read`. A documented endpoint, vendor feature list, authorization button, HTTP success, or one working read never advances another capability.

- Inventory batches require a per-store product/SKU mapping, an independently approved write, idempotency, the platform's successful and failed item lists, and inventory readback. Do not retry the full batch because one item failed.
- Shipment declaration, modification, and query/readback are separate. Bind order, tracking, carrier/service, ship-from country/warehouse, destination, and execution identity to the same store. Current same-store, destination, tracking-format, prior-declaration, time, and count restrictions are prechecks, not permanent global constants.
- Classify shipment errors before retry. A mismatch, unsupported route, missing entitlement, absent prior record, invalid format, or expired/count-limited modification needs correction or human review, not repetition.
- Delivery-address reads contain high-sensitivity field classes. Store only a credential reference, use the narrowest role, redact logs and test fixtures, minimize retention, and exclude documentation sample identity values.
- Marketplace inventory is not the entire ERP ledger. Reconcile available, reserved, returned, in-transit, warehouse and financial evidence before calling stock or profit complete.

Package reuse stays bounded: the commercial FlexigoTech/Odoo package is a `research_only` workflow hypothesis; Saleor MCP contributes least-privilege and exact-domain patterns only; ERPNext contributes entity/ledger vocabulary under the shared registry's `reference_only` decision. No package was installed or treated as AliExpress connectivity.

## Required approval actions

Create a separate `pending_approval_action` for each publication, price, inventory, activity, discount, ad spend, shipment, refund, message, payment, or authorization change. Include the exact store route, proposed payload summary, evidence, idempotency key, expected effect, risk, rollback/stop condition, and expiry. Never include raw credentials.

## Failure handling

- Missing store: `needs_platform_store`.
- Missing or stale authorization: `needs_authorization`.
- Missing product or route facts: remain `draft_ready` or `needs_review`; do not fill gaps with model knowledge.
- Tenant product facts appearing outside their route: `scope_leakage`; stop propagation and repair the owned file or hand off a minimal shared-core patch.
- Full-managed execution, bypass, cross-store credential reuse, unauthorized scraping, or media theft: `blocked`.
- Platform rejection or unclear rule: save the error and source, stop writes, and request the smallest missing owner input or official evidence.
