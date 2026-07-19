# AliExpress expert course

Use this curriculum only after collecting new visible software or page evidence. A run without new evidence records `no_change`; it does not invent a lesson.

## Evidence gate

For every lesson, capture the software/page, URL or product version, capture time, country/site, commerce mode, ownership, permission scope, actions taken, visible input/output, error, and validity boundary. Use only:

- `verified_live_fact`
- `time_sensitive_evidence`
- `historical_operator_trace`
- `draft`
- `failed_attempt`
- `unknown`
- `blocked_owner_input`

Public documentation is normally `time_sensitive_evidence`. A live fact requires a bound store, object ID, isolated identity, timestamp, and a successful read or post-write readback. Seller experience is only a dated experiment hypothesis.

## Product-scope gate

- Platform-public lessons contain only AliExpress rules, site/mode routing, and common controls.
- Category lessons are replaceable capabilities. Resolve apparel, home, beauty, electronics, food/restricted goods, digital goods, machinery, or another category from current official eligibility and the authorized leaf-category schema.
- Product facts remain inside `tenant_id + project_id + product_id + store_binding_id`; task observations remain inside their evidence record.
- Missing category, variation, price, media, inventory, warehouse, capacity, lead-time, brand, or compliance facts stay `unknown`. Never fill them from a private_tenant project.
- Treat every shared B2B workflow as product-independent. A current project cross-sell is a task trace, not the default sales funnel.
- Mark an unscoped tenant-product default as `scope_leakage`; repair it locally or hand a minimal shared-core patch to the owning task.

Every course module must retain at least one anonymous, non-private_tenant, non-apparel, non-printing-equipment regression example. The sample must not inherit another project's price, variation, media, inventory, warehouse, or customer data.

## AE-C01 — Evidence, identity, and state

- Identify the real browser, app, store identity, site, mode, ownership, and permission before learning.
- Prefer API, then an isolated browser identity, then computer control for uncovered UI gaps.
- Stop at login, CAPTCHA, MFA, identity, bank, payment, or authorization boundaries.
- Before distillation, identify publisher/date/version/site, inspect navigation, expand relevant sections, scroll to footer, follow directly related links, and record pagination/lazy-load coverage plus unavailable regions.
- Treat comments as a separate evidence track: record displayed total separately from visible count, plus the actual pinned/accepted, high-signal, latest, author/official reply, nested follow-up and counterexample range. A login-gated sort or expansion is blocked, not read. Store anonymous topic clusters only and return policy/API/fee claims to a current official source. A video title, description or comment never replaces an unavailable subtitle or body.
- Enforce hard completeness before distillation: a webpage needs recorded body-scroll coverage and a directly relevant second-level page; a video no longer than ten minutes needs at least 95% playback or readable-subtitle coverage plus checked key frames; when comments exist, inspect required sorts/replies/counterexamples and sample at least 10 comments or all if fewer. Any failed applicable gate makes the source `opened_not_reviewed` with no knowledge output.
- Keep at least 70% of each round on the AliExpress seller-operations mainline. Emit a deviation check, opened-not-reviewed list, fully reviewed list, and truthful `no_delta` value; unrelated sources are `irrelevant_skip`.

Pass: the evidence record has exact coverage, satisfies every applicable hard gate, never claims all content/comments without proof, and a tool state is not upgraded by a page or button alone.

## AE-C02 — Seller entity, market, and category service

- Separate seller jurisdiction, buyer market, exact authorized country/site, category service, shop label, and store activation.
- Check U.S., EU/EEA, South Korea, Brazil, or other seller programs against current official terms.
- Require the platform's Start of Services/acceptance response and category authorization.
- Treat a jurisdiction-specific agreement summary as a summary only. For EU/EEA sellers, current evidence supports truthful/current seller information and non-misleading price presentation, but the full agreement and case record control.
- The public qualification rule revised 2026-03-16 is scoped to China-mainland-registered merchants and its named cross-border modes. Resolve the exact leaf category and current authorization before importing any required document; do not transfer it to an overseas local seller or another mode.

Pass: a signed agreement or region name is never treated as an executable store.

## AE-C03 — Cross-border, local, and managed-service concepts

- Resolve standard marketplace seller, semi-managed, overseas-managed, and recognition-only full-managed.
- For the U.S. local program, keep `AliExpressLocal Marketplace` and `AliExpressLocal Direct` as separate current public labels. Do not globalize them or infer their T One commerce-mode/ownership mapping without the live agreement and authorization response.
- Disambiguate Choice using the applicable agreement, store authorization, price control, inventory, warehouse, fulfillment, after-sales, and settlement duties.
- Keep `官方店/专卖店/专营店/普店/本土POP` pending until current official or authorization evidence exists.
- Treat `POP/海外托管/全托管/半托管` checkboxes in a manager-contact form as inquiry taxonomy only. A blank public `店铺类型` section leaves the current store matrix unknown.
- Keep public POP/full-managed onboarding steps and values time-sensitive. Identity, UBO, funding, deposit, category, and brand actions remain non-executable and separately authorized.

Pass: no shared execution route exists across modes.

## AE-C04 — Product research and sellability

- Use lawful public or licensed signals for demand, competition, price band, seasonality, and risk hypotheses.
- Select the relevant category capability, then verify leaf-category permission, product safety, certification, IP, image/video rights, ship-from, cost, fees, duty/tax scope, and margin.
- Treat competitor structure and seller experience as experiments, not facts.
- For a B2B route, keep lead, offer, approval, delivery, and evidence scoped to the lawful product and project; do not default to another project's cross-sell.

Pass: a product candidate has known evidence gaps and no invented product facts.

## AE-C05 — Dynamic category and Listing

- Fetch the authorized leaf-category tree for the bound seller.
- Prefer the currently visible seller-permission-filtered category-tree API candidate over a frozen global category list; preserve multilingual category names as labels, not product facts.
- Fetch the current Product Schema for the exact seller/category and validate the draft client-side.
- Treat authorization and Jushita labels on the currently visible Product Schema page as independent connector requirements; the page's sample response is not a fetched schema.
- Resolve variation axes and required fields from that schema. Do not carry apparel sizes/colors, machinery attributes, or physical-logistics fields into another category.
- Use only project-scoped verified titles, descriptions, images, category attributes, SKU attributes, inventory, dimensions, weight, preparation time, shipping/service templates, and product group.
- Re-fetch on rejection or schema/version change.

Pass: schema and product facts are current; publishing remains an approval action.

## AE-C06 — Activities, discounts, and stacking

- Open the live activity page and capture category, product, brand, price, discount, logistics, service, quota, dates, and stacking.
- Model margin and inventory scenarios without changing the store.
- Prepare one approval action per enrollment, discount, coupon, price, or inventory change.

Pass: an accessible activity page is not eligibility proof.

## AE-C07 — Digital Marketing / 直通车 / seller affiliate

- Confirm the current product/UI name and distinguish it from off-platform Meta, TikTok, and Google ads.
- Capture ads identity, eligibility, balance/billing, placement, bid/charge model, attribution, budget, margin, and stop-loss.
- Separate public terms, authenticated reports, simulations, and real campaign results.
- Keep seller Overseas Affiliate Network Marketing separate from Digital Marketing, the publisher-facing Affiliate Program, and seller Open Platform APIs. For seller affiliate, capture current eligibility, promoted-product scope, category/product/default commission rate, attribution, successful-sale definition, withdrawal effective time, refund/dispute treatment, settlement record, and approval state from the bound store.
- Treat the agreement's 15-day attribution example and commission hierarchy as dated `time_sensitive_evidence`; current system values and activity-specific overrides control.

Pass: no enrollment, product promotion, commission/rate change, launch, recharge, bid, or budget change occurs without explicit approval; a publisher portal token is never a seller-store or Open Platform grant.

## AE-C08 — Orders, inventory, and fulfillment

- Bind every order and logistics object to one store/site/mode/identity.
- Separate order reads, receipt-address access, carrier/service lookup, warehouse order creation, tracking declaration, and physical shipment.
- Recheck the current per-order logistics products and SLA; old examples are not current universal limits.

Pass: tracking declaration and physical handover remain independently approval-gated.

## AE-C09 — Customer service, disputes, and refunds

- Read the current issue, deadline, buyer proposal, seller options, evidence rights, return address, order value, and refund effect.
- Keep private buyer data store-scoped and minimal.
- Treat agree, reject, upload evidence, message, return authorization, and refund as distinct writes.

Pass: no dispute resolution or refund is executed without owner approval.

## AE-C10 — Settlement, fees, and profit

- Read/import one store statement with time range, settlement currency, commission, logistics, activity, ads, refund, exchange, duty/tax, and chargeback fields.
- Use public fee/onboarding pages only to locate the current category rule. Resolve the exact leaf category, seller jurisdiction/mode, rule revision and authenticated fee screen; do not generalize an overview percentage or deposit band.
- For the self-operated transaction rule revised 2026-06-29, use the category rate applicable when the order is released and the final transaction amount. Model proportional fee return after cancellation or seller refund, then reconcile the actual statement.
- Reconcile to orders and payouts without mixing stores or modes.
- Escalate legal, tax, bank, and identity questions to current official evidence and owner input.

Pass: profit is labeled observed, reconciled, estimated, or unknown.

## AE-C11 — Platform-native AI

- Learn only in an eligible seller environment or official legal demo.
- Require the evidence to name AliExpress itself, the exact country/site, seller program and mode. Group ownership is not feature portability: Taobao/Tmall, Alibaba.com or generic Alibaba merchant-AI evidence cannot establish AliExpress access, names, metrics or performance.
- Record evidence maturity. The current public AliExpress Seller landing verifies a public claim for product publishing, new-product incubation, offsite marketing, and customer-service consultation, but remains `official_public_surface_claim_verified_execution_pending` until an authenticated workflow is observed.
- The Rules pages also visibly expose an `AI助手` panel. Because this round entered no prompt and observed no answer, this is public-surface evidence only; `限时免费` does not establish permanent cost, quota, eligibility or a T One connection.
- Capture the visible entry, eligibility, accepted inputs, actual output, edit controls, submit boundary, metrics, failure message, retry/recovery, and provenance.
- Preserve product and rights facts; AI output is a draft until reviewed.

Pass: the 2025 U.S.-local imaging announcement, secondary reporting, and current public Seller landing are not global access proof. An official seller-registration link is not completed registration or AI entitlement. Without a visible authenticated AliExpress seller workflow, keep the tool `research_only` and the connector `blocked_owner_input`.

## AE-C12 — Developer API, ERP, and multistore isolation

- Verify developer type, approved app, OAuth scope, seller identity, token reference, endpoint version, and a successful read.
- Resolve the current API namespace and application category before choosing an endpoint. `AE-Oversea-Solution`, `全球速卖通`, mini-app, affiliate and seller operations are not interchangeable merely because their methods begin with `aliexpress`.
- Capture page-level constraints such as `需要授权` and `聚石塔内调用` separately. A documentation-generated timestamp, sample session, example success payload, API-test button or SDK link proves none of them is satisfied.
- For the U.S. local program, distinguish the officially announced Open API and ISV application types from an approved application, credential scope, SDK, or successful call.
- Treat an unofficial community SDK as `single_case` research. Require GitHub-registry admission, license, maintenance, dependency/security review, secret-handling review, a pinned version, and isolated tests before any pilot; unknown repositories remain blocked from installation.
- Reverse-verify an official GitHub identity from an exact repository/organization link on a first-party property and record redirects or transfers. Official ownership, stars, releases or an accepted answer do not prove AliExpress seller relevance or workflow completion.
- Keep official-but-unrelated gateway infrastructure out of the AliExpress connector. The 2026-07-19 official Alibaba catalog exposed no AliExpress/速卖通 project; `higress-group/higress` is generic infrastructure and T One already has one gateway/runtime.
- Validate the API connection chain one stage at a time: developer identity, application approval/category, permission group `Active`, authorization strategy/seller scope, seller OAuth, token reference, and successful store-scoped read. A later stage cannot be inferred from an earlier one.
- Treat the old production-environment page as a safety warning, not a current endpoint contract or sandbox. Never test write-class APIs against a real store without explicit action approval, idempotency, readback, and rollback/stop conditions.
- Verify ERP authorization, exact site/mode mapping, supported objects, read/write scope, and diagnostic output per store.
- Serialize writes by store and use approval, idempotency, readback, evidence, and failure recovery.

Pass: documentation, configuration, a portal credential, permission application, or a UI authorization button never becomes connection evidence; only the exact staged evidence and successful store read advance the connector.

> Private runtime paths, evidence, execution identities, and product records are intentionally excluded from this public pack.
