# Incremental training evidence and failure review

## Checked software/pages and actual operations — 2026-07-18

No AliExpress `store_binding_id`, OAuth, ads account, ERP authorization, Seller Center identity, or native-AI entitlement was available. No login, credential entry, write, payment, shipment, refund, message, MFA, bank, or identity action occurred.

| Evidence | Status | Actual operation | Visible result | Boundary |
|---|---|---|---|---|
| Google Chrome 150.0.7871.125, Profile 1 | `failed_attempt` | Checked running browser, selected profile, enabled Codex extension and native-host manifest; retried read-only control initialization | Chrome and extension were present; later exact diagnostics showed the installed native manifest was invalid and tab inventory failed before any page read | No cookies/session/profile data inspected; AliExpress identity remains unknown |
| [Seller authorization](https://open.alitrip.com/docs/doc.htm?articleId=120687&docType=1&treeId=727) | `time_sensitive_evidence` | Opened and read OAuth flow/token fields | Seller OAuth2 code-for-token is documented | 2022 document; no app approval, scope, OAuth or token was obtained |
| [Category Mappings](https://open.alitrip.com/docs/doc.htm?articleId=120679&docType=1&treeId=727) | `time_sensitive_evidence` | Clicked from the official Open Platform menu and scrolled authorized-tree fields | Authorized tree is seller-specific; leaf categories are posting targets | Current endpoint and permission must be rechecked |
| [Product Schema Post/Edit](https://open.alitrip.com/docs/doc.htm?articleId=120682&docType=1&treeId=727) | `time_sensitive_evidence` | Clicked menu, scrolled required fields and change warning | JSON schema contains seller/category-dependent posting rules and can change over time | No schema API was called; the 17-field example is not universal/current |
| [Order fulfillment by sellers](https://open.alitrip.com/docs/doc.htm?articleId=120683&docType=1&treeId=727) | `time_sensitive_evidence` | Clicked and scrolled order status/tracking fields | Order query, address, carrier and tracking declaration are separate steps | No order or shipment was read/declared |
| [Order fulfillment by AliExpress](https://open.alitrip.com/docs/doc.htm?articleId=120684&docType=1&treeId=727) | `time_sensitive_evidence` | Clicked and scrolled order/logistics fields | Logistics services are account/order scoped | Old example size, weight, route and SLA are not current universal rules |
| [Issue API](https://open.alitrip.com/docs/api.htm?apiId=36092) | `time_sensitive_evidence` | Opened and scrolled permission/request fields | Agreeing to a dispute solution is an authorized write; documentation shows a Jushita constraint | No issue, buyer data, proposal, evidence or refund action was accessed |
| [EU/EEA Seller Agreement](https://cdn.contract.alibaba.com/terms/EU_EE_UK_platform_service_agreement/20250320103243738/20250320103243738.html?lng=en) | `time_sensitive_evidence` | Opened, scrolled Start of Services, searched category services and dispute | Updated 2026-04-23, effective 2026-05-08; agreement acceptance is not activation; buyer disputes start in Seller Center/Customer Service | Seller jurisdiction agreement is not an executable store or site grant |
| [U.S. local AI-image announcement](https://www.prnewswire.com/news-releases/aliexpress-unveils-powerful-new-tools-for-us-sellers-to-boost-growth-and-efficiency-302611764.html) | `time_sensitive_evidence` | Opened and scrolled AI image/local fulfillment sections | AliExpress announced an AI-enabled listing-image tool for eligible U.S. local sellers | Press release is not a visible Seller Center workflow or global entitlement |
| Current open.aliexpress.com developer guide links | `failed_attempt` | Clicked current guide/API links from the official mirrored page | Research surface returned a non-retryable open error | Used old official mirror only as stale architecture evidence |
| AliExpress Seller Center native AI | `unknown` | Searched official public evidence; no authenticated store was available | No entry, input, output, editing, submission, metric or recovery was observed | Must be learned in an eligible isolated seller environment |

## Product-scope increment — 2026-07-18

This increment inspected existing T One software and reused the same AliExpress expert. It did not create another runtime, gateway, expert, page, or connector.

| Existing asset | Ledger status | Actual observation | Increment or handoff |
|---|---|---|---|
| T One platform/store/task route and single LLM gateway | `keep_reuse` | Existing route and model configuration surfaces remain the only shared base | Reused without modification |
| AliExpress Skill, contract, validator and evaluations | `repair_extend` | Dynamic schema rules existed, but the four product-scope layers and anonymous category isolation were not machine-enforced | Added the scope contract, validator checks, and fourteen anonymous non-apparel/non-printing-equipment cases |
| Shared product-intake UI | `repair_extend` | Generic placeholders and downloadable template expose one private_tenant product pattern | Recorded `scope_leakage`; shared-core owner should replace it with neutral category-diverse input |
| Shared company sales snapshot | `repair_extend` | Missing product context falls back to a private_tenant product rather than `unknown` | Recorded `scope_leakage`; shared-core owner should require project product context |
| Shared B2B runtime | `repair_extend` | Missing/unrecognized product scope falls back to apparel and a project-specific pipeline | Recorded `scope_leakage`; C3 owner should add a generic lawful-product scope |
| AliExpress store, OAuth/API, ads, ERP and native AI | `blocked_connector` | No isolated store identity or successful read exists | The unique missing input remains one authorized read-only AliExpress store route |
| Verification bypass, cross-store credentials and unlicensed reuse | `rejected_unsafe` | No such action was attempted | Permanent execution block retained |

Knowledge uses `official_current`, `verified_software_observation`, `multi_source_practice`, `single_case`, `historical_trace`, or `unknown`. These layers complement the seven execution-evidence statuses; they do not turn a page, test, or code observation into business completion.

### Fingerprints and repeat skips

- Stored normalized-excerpt SHA-256 fingerprints for the deprecated ISV test-account page, seller OAuth page, Alibaba Group Choice explainer, AliExpress U.S.-local AI announcement, and the MIT `nexscope-ai/eCommerce-Skills` repository.
- Kept the old ISV and OAuth pages as `historical_trace`; they do not prove a current sandbox, endpoint, scope, app approval, or connection.
- Kept the Choice explainer and U.S.-local AI announcement as scoped `official_current` public claims, not executable store evidence.
- Kept the GitHub repository as a `single_case` taxonomy reference; no repository was installed or copied.
- Skipped repeat distillation of the OAuth, Choice, and AI announcement captures because the same canonical URL and excerpt fingerprint were already ingested on 2026-07-18.

## Rules distilled from this evidence

1. Fetch the authorized leaf-category tree per seller; the full tree is not the seller's permission set.
2. Fetch Product Schema at task time and validate the draft; do not hard-code the old example.
3. Treat order read, address access, carrier/service selection, tracking declaration, and physical shipment as separate capabilities/actions.
4. Treat issue read, proposal decision, evidence upload, buyer message, return authorization, and refund as separate permission and approval domains.
5. An EU/EEA or U.S. seller agreement proves a seller-program legal route, not category activation, store creation, buyer-market scope, or connection.
6. A public AliExpress AI announcement proves a scoped product claim only. Without visible seller access and real input/output, platform-native AI remains `unknown`.
7. Platform rules cannot contain tenant product facts. Category capability is replaceable; product facts require tenant/project/product/store scope; task traces never become defaults.
8. Missing category or product facts remain `unknown`; do not inherit another project's variation, price, media, inventory, warehouse, customer, B2B, or creative data.

## Failure review

### AE-FAIL-001 — Browser control initialization (updated 2026-07-19)

- Result: `failed_attempt`.
- Evidence: Chrome runs, Profile 1 is selected and the Codex extension is enabled; initialization failed before tab inventory, and the later native-manifest diagnostic returned `installed=true, valid=false`.
- Containment: did not inspect cookies, profiles, credentials, or alternate store identities; did not repair/install the browser integration.
- Next test: after the owner repairs or reinstalls the existing plugin/native manifest, retry through the supported read-only client rather than self-repairing or exporting the session.

### AE-FAIL-002 — Current developer site

- Result: `failed_attempt`.
- Evidence: current guide/API links could not be opened by the research surface.
- Containment: kept 2022 mirrored docs as `time_sensitive_evidence`; did not claim current endpoint/scope/limit validity.
- Next test: open the current developer console in an authorized browser or official sandbox.

### AE-FAIL-003 — Platform-native AI

- Result: `unknown`.
- Evidence: U.S.-local public announcement exists, but no seller feature flow was visible.
- Containment: no imagined UI, permission, output, performance or recovery rule entered the Skill.
- Next test: capture one eligible store's visible AI feature from entry through editable draft, stopping before submission.

### AE-FAIL-004 — Live store/API/ads/ERP

- Result: `blocked_owner_input`.
- Missing: isolated AliExpress `store_binding_id`, execution identity, OAuth/app scopes, ads identity/billing, ERP authorization, and successful read.
- Next test: owner authorizes one read-only store diagnostic. Writes remain separately approval-gated.

### AE-FAIL-005 — T One formal-package launch

- Result: `failed_attempt`.
- Evidence: launching the existing T-One 0.1.0 package produced an Error-titled temporary process that exited before the exact body was captured.
- Containment: did not install, delete, overwrite, or change shared desktop files.
- Next test: shared-core owner captures launch logs and repairs the existing package chain; do not create another desktop shell.

### AE-FAIL-006 — T One extension-page acceptance

- Result: `failed_attempt`.
- Evidence: two Chrome windows titled Extensions · T One were present, but read-only control stopped because the current URL could not be determined confidently.
- Containment: no page clicks, saves, model calls, cookies, or session data were inspected after the stop.
- Next test: use a policy-compliant visible URL or repaired formal-app entry, then verify Skill reading, connector truth, errors, and task route.

## U.S.-local and developer-source rotation — 2026-07-18 23:41 +08:00

| Evidence | Actual operation | Visible result | Distillation boundary |
|---|---|---|---|
| [AliExpress U.S.-local offerings announcement](https://www.prnewswire.com/news-releases/aliexpress-announces-new-offerings-for-u-s-sellers-affording-greater-flexibility-and-seamless-platform-integration-302402958.html) | Opened the AliExpress-issued page and scrolled the program-label, Open API/ISV and onboarding sections | The page describes `AliExpressLocal Marketplace` and `AliExpressLocal Direct` for U.S. local sellers, plus developer-qualification-dependent Open API/ISV application types | Public program description only; not a global mode, store activation, approved app, OAuth scope or successful call |
| [U.S. Seller Agreement](https://cdn.contract.alibaba.com/terms/b_platform_service_agreement/20240701183317609/20240701183317609.html) | Compared the announcement's onboarding shorthand with the existing official seller/category review and Start of Services clauses | The legal activation conditions are stricter than the marketing sequence | Current legal agreement and live authorization control when sources differ |
| [moh3a/ae_sdk](https://github.com/moh3a/ae_sdk) | First read T One's GitHub admission registry, then opened and scrolled repository metadata, README prerequisites, license and release | MIT repository self-identifies as unofficial, requires developer/app/token setup, and was absent from T One's admission registry | `single_case`, `research_only_no_install`; no dependency, credential or API action occurred |
| Public YouTube result `dQ5Ce8-nzVM` | Searched and attempted to open the public video without downloading it | The page fetch failed before metadata or subtitles were visible | `failed_attempt`; no claim was ingested and no bypass was attempted |

Repeat handling: same-day OAuth, Choice and U.S.-local AI fingerprints were not reopened merely to restate existing rules. The new announcement and GitHub repository received new normalized-excerpt SHA-256 fingerprints; the failed video received a failure record, not a content fingerprint.

Distilled increment:

1. `AliExpressLocal Marketplace` and `AliExpressLocal Direct` are scoped U.S.-local public labels. Do not globalize them or map `Direct` to Choice, semi-managed, official full-managed, or `platform_co_ops` by name.
2. Registration, authentication and payment setup do not override seller/category review, the current agreement, the Start of Services notice or live authorization results.
3. An official statement that Open API/ISV application types exist does not prove app approval, scope, token or a successful store-scoped call.
4. An unofficial SDK remains research-only until shared-registry admission, official endpoint matching, maintenance, dependency/security, credential boundary, pinned-version and isolated-test gates pass.

### AE-FAIL-007 — Public video evidence

- Result: `failed_attempt`.
- Evidence: the public video page failed before author, date, video or subtitles could be read.
- Containment: no download, DRM/login bypass, alternate scraping or snippet-based inference.
- Next test: rotate to a publicly accessible transcript or another licensed video source.

## Continuous training mechanism

- Automation ID: `aliexpress`; name: `AliExpress专家持续增量训练`; state: active; cadence: once daily.
- Process only evidence after the last successful cursor. Deduplicate by URL, page date/version, content hash, site, mode, ownership, and permission scope.
- On no new evidence, record `no_change`; do not rewrite rules or manufacture learning.
- Update only AliExpress Skill, training contract, AliExpress tests, and expert-training outputs.
- Run `scripts/validate_incremental_evidence.py` and the directed unittest after an evidence-backed update.

## Seller affiliate and API-permission rotation — 2026-07-19 00:06 +08:00

No AliExpress store, seller affiliate account, Open Platform app, OAuth, ads identity, ERP authorization, or native-AI entitlement was available. No login, credential, application, permission request, enrollment, rate, campaign, payment, shipment, refund, message, MFA, bank, identity, or other write occurred.

| Evidence | Actual operation | Visible result | Boundary |
|---|---|---|---|
| [Overseas Affiliate Network Marketing Service Agreement](https://terms.alicdn.com/legal-agreement/terms/suit_bu1_aliexpress/suit_bu1_aliexpress202202191746_57536.html) | Opened and scrolled definitions, service, eligibility, commission, withdrawal and fees | Seller-side CPS/commission marketing is distinct; eligibility and effect are not guaranteed, and category/product/system values can differ | Effective 2022-02-18; all rates, attribution and current UI remain time-sensitive and unconnected |
| [Request API Permission](https://developer.alibaba.com/docs/doc.htm?articleId=120676&docType=1&treeId=727) | Opened and read permission-group states and application steps | Application permission groups can be `Active` or `Inactive`; gateway denies calls without permission | Updated 2022-03-02; no current app, permission state or call was observed |
| [Configure Seller Authorization](https://open.alitrip.com/docs/doc.htm?articleId=120677&docType=1&treeId=727) | Opened and scrolled authorization policy, token-duration, user-limit and seller-whitelist fields | Authorization strategy is application-category scoped and can restrict which sellers authorize | Updated 2022-03-02; values and current console remain unverified |
| [API Endpoint URLs](https://developer.alibaba.com/docs/doc.htm?articleId=120689&docType=1&treeId=727) | Opened and read the production-environment warning | The documented environment uses real online data and write calls may affect a shop | Updated 2022-01-29; it is not a sandbox or current endpoint contract |
| [Reddit affiliate/developer access report](https://www.reddit.com/r/Affiliatemarketing/comments/1rwhph4/aliexpress_affiliate_help_have_partial_access_to/) | Opened the public post and read the dated report and replies | One user reported affiliate/developer portal confusion and a later Tools/API/apply redirect | `single_case`; no credential-flow or support rule was promoted |
| [Seller Workbench PDF](https://ae-pic-a1.aliexpress-media.com/kf/S270b37a6df9f4c038d3156879ff19aeao.pdf) | Opened all four pages and inspected title, menu summary, date/copyright and provenance fields | Official-looking host and dashboard examples were visible, but no reliable publisher/applicability/ownership metadata was found | `unknown`; store-specific examples were excluded and the file was not treated as an official manual |

Repeat skips: the search returned the already fingerprinted 2022 seller-OAuth page and yesterday's U.S.-local/SDK sources; the existing hashes were reused instead of re-ingesting them. Six new normalized-excerpt hashes cover only the new sources above.

Distilled increment:

1. Separate seller Overseas Affiliate Network Marketing, publisher Affiliate Program, Digital Marketing, and seller Open Platform API identities, permissions, billing and reports.
2. Treat affiliate eligibility, rates, attribution, successful-sale definition, withdrawal and refund/dispute handling as live seller-system facts. The 2022 values are dated hypotheses only.
3. Advance an API connector only through developer/application approval, permission-group state, authorization strategy/seller scope, seller OAuth, token reference and a successful store-scoped read. No earlier stage proves a later one.
4. Never test a write against a documented production endpoint as if it were a sandbox.
5. Require publisher, version/date, applicability, ownership/license and official-index consistency before treating an official-looking document as authoritative; exclude embedded store data when provenance is unknown.

### AE-FAIL-008 — Unattributed Seller Workbench PDF

- Result: `unknown`.
- Evidence: the public PDF was readable, but host name and visual style were the only apparent official signals; publisher, scope and authorization were absent, while store-specific examples were embedded.
- Containment: did not copy metrics or treat menu labels as a current global Seller Center taxonomy.
- Next test: locate the document from a current official Seller Center/Help index or discard it as an unverified attachment.

## Platform-native AI scope rotation — 2026-07-19 00:35 +08:00

No AliExpress store, seller login, native-AI entitlement, Open Platform app, ads identity or ERP authorization was available. No registration, login, credential, CAPTCHA, MFA, identity, bank, publish, price, inventory, activity, campaign, payment, shipment, refund or message action occurred.

| Evidence | Actual operation | Visible result | Boundary |
|---|---|---|---|
| [Alibaba Group: AI Powers Large-scale Applications](https://www.alibabagroup.com/en-US/document-1915930722120499200) | Opened and scrolled the publication header, named platforms, merchant tools and reported metrics | The article explicitly concerns Taobao/Tmall 11.11 and names AI bidding, AIGC media, AI Business Advisor and Dianxiaomi | First-party but wrong platform for AliExpress; no name, metric, entitlement or workflow is transferable |
| [Digital Commerce 360 U.S.-local report](https://www.digitalcommerce360.com/2025/11/11/aliexpress-expands-us-local-seller-program-with-ai-tools/amp/) | Opened and scrolled author/date and the AI imaging, labeling, Brand+ and Quipt summary | Independent reporting corroborates the public U.S.-local announcement wording | `single_case` secondary corroboration only; no Seller Center entry, input/output or seller entitlement was observed |
| [AliExpress-issued U.S.-local announcement](https://www.prnewswire.com/news-releases/aliexpress-unveils-powerful-new-tools-for-us-sellers-to-boost-growth-and-efficiency-302611764.html) | Reused the existing fingerprint, scrolled to the official seller-registration link and followed it | The target resolved to an AliExpress seller-registration URL but returned a non-retryable open error | Duplicate content was not re-ingested; link existence is not registration, store activation or AI entitlement |
| USTR public-submission PDF candidate | Followed the public regulations.gov PDF result | The document request returned HTTP 403 before content was visible | No snippet or inaccessible PDF content was ingested; no access-control bypass |
| Official-video/subtitle search | Queried for AliExpress official U.S.-local seller AI imaging, Brand+ and labeling demos | No relevant official AliExpress video or readable subtitle result was returned | Unrelated video results were discarded; no download, DRM bypass or inferred workflow |

### Duplicate skips

- `AE-FP-004` was returned again. Its canonical URL and normalized excerpt were already captured; only the previously unseen seller-registration link was followed, and the announcement body was not distilled again.
- Existing seller terms, Choice, seller-affiliate and old Open Platform pages were not reopened in this source-rotation pass.

### Distilled increment

1. Exact-platform scope is mandatory for native AI. Alibaba Group ownership does not make a Taobao/Tmall feature an AliExpress feature.
2. Secondary media may corroborate an announcement but cannot fill operational evidence fields that it did not observe.
3. A registration link or account-creation page does not prove completed registration, store activation, authenticated Seller Center access or feature entitlement.
4. Native-AI completion still requires AliExpress-specific site/mode eligibility, visible authenticated entry, accepted inputs, real output, edit/submit boundary, metrics and failure recovery.

### AE-FAIL-009 — Seller registration/native-AI entry

- Result: `failed_attempt`.
- Evidence: the official AliExpress announcement exposed a seller-registration link, but the registration target and direct public seller-entry candidates returned non-retryable open errors.
- Containment: did not retry through alternate identities, enter credentials, bypass access controls, or infer any Seller Center menu or entitlement.
- Next test: use one owner-authorized, isolated AliExpress seller route for a read-only observation, stopping before registration/auth changes or submission.

### AE-FAIL-010 — Public regulatory PDF and official video

- Result: `failed_attempt`.
- Evidence: the public USTR PDF returned 403, and targeted official-video searches produced no relevant AliExpress seller-AI video or readable subtitles.
- Containment: did not use snippets as source content, download media, bypass DRM/login, or substitute unrelated videos.
- Next test: rotate to an accessible first-party AliExpress Help/Seller page, official demo transcript, or lawful sandbox; retain `unknown` when none is available.

## Current API catalog and GitHub rotation — 2026-07-19 00:57 +08:00

No AliExpress application, seller OAuth, Jushita environment, store binding or API credential was available. No API request, test-tool call, SDK download/install, dependency execution, login, credential entry, publication, price, inventory, shipment, refund or message action occurred.

| Evidence | Actual operation | Visible result | Boundary |
|---|---|---|---|
| [Seller category tree API](https://developer.alibaba.com/docs/api.htm?apiId=46042) | Opened from the current `AE-Oversea-Solution` catalog; scrolled authorization, request and response fields | Requires authorization; can filter to categories the seller may publish and returns leaf/level/multilingual names | Public catalog candidate only; no seller category response was obtained |
| [Product Schema API](https://developer.alibaba.com/docs/api.htm?apiId=43456) | Clicked from the same catalog; scrolled authorization/Jushita labels, category input, schema/error output and examples | Requires authorization and Jushita; accepts category ID and returns schema text | Example success/error and rotating timestamp are documentation, not a fetched schema |
| [Seller order list API](https://developer.alibaba.com/docs/api.htm?apiId=42270) | Clicked the seller-order entry; scrolled authorization/Jushita labels, query/status fields and sample response | Requires authorization and Jushita; exposes seller-order list/status fields | No app permission, OAuth, store identity, buyer data or successful read |
| [`aliexpress.trade.order.open.query`](https://developer.alibaba.com/docs/api.htm?apiId=50338) | Opened the separate `全球速卖通` API page and compared namespace/parameters | Uses `trade.order.open` plus buyer/open-app/business-code fields | Do not substitute it for the seller-order connector by name similarity |
| [alonseg/AliexpressApi](https://github.com/alonseg/AliexpressApi) | Opened repository, README and package manifest; inspected scope, declared license, releases, security surface and dependencies | ISC declared in package.json; affiliate/product wrapper; 16 commits, 4 stars, no releases; `request ^2.88.2` dependency | Unknown repository absent from T One registry; no install or credential use |
| [npm request 2.88.2](https://www.npmjs.com/package/request?activeTab=code) | Opened package record and read maintainer deprecation notice | Package is deprecated; 2.88.2 was published about six years before capture | Dependency-risk evidence only; no package was downloaded |

### Duplicate skips

- Existing 2022 OAuth, permission-group, authorization-strategy and endpoint pages were not reopened. Their architecture evidence remains versioned historical context.
- Existing `moh3a/ae_sdk` fingerprint was skipped; this pass audited a different repository.

### Distilled increment

1. Choose an API by current namespace, application category, authorization label and environment constraint; an `aliexpress.*` prefix is insufficient.
2. The seller category tree must be read with the bound seller's permissions. Its multilingual names are category labels, not inferred product translations.
3. A Schema page or sample schema is not a store-scoped fetch. Authorization, Jushita, seller category, OAuth and a successful response are separate gates.
4. Documentation-generated timestamps, session-like samples, success JSON, API-test buttons and SDK links never advance a connection state.
5. Unknown GitHub SDKs remain outside the runtime; a declared permissive license does not override missing registry admission or a deprecated dependency.

### AE-FAIL-011 — Unregistered Node wrapper

- Result: `failed_attempt` for integration, `single_case` for research.
- Evidence: the repository is public and declares ISC in `package.json`, but it is absent from T One's admission registry, has no published GitHub release, exposes no current official endpoint match or isolated security result, and depends on deprecated `request@2.88.2`.
- Containment: no clone, install, dependency execution, credential entry or API request occurred.
- Next test: the shared GitHub owner may audit a pinned commit, license file, maintenance, dependency/security findings, endpoint match and secret boundary; until then retain `research_only_no_install`.

## Deep official/API/GitHub and comment rotation — 2026-07-19 01:30 +08:00

No AliExpress store, application, OAuth, Jushita, ads, ERP or native-AI authorization was available. Logged Chrome was owner-authorized for read-only use, but the supported client stopped before tab inventory because the native manifest was installed but invalid. No tabs, cookies, tokens, identities or private pages were read, and no browser configuration was changed.

| Source | Actual coverage | New evidence | Boundary |
|---|---|---|---|
| [Alibaba Open Source catalog](https://opensource.alibaba.com/project) | Inspected identity/footer, filters, initial batch, one load-more batch, all 39 visible records, exact GitHub links and searches for `AliExpress`/`速卖通`; reached footer | Exact official reverse-link chain; zero AliExpress/速卖通 match in the visible catalog | Same-name GitHub identities remain unknown |
| [Product Schema](https://developer.alibaba.com/docs/api.htm?apiId=43456), [seller category tree](https://developer.alibaba.com/docs/api.htm?apiId=46042), [seller order list](https://developer.alibaba.com/docs/api.htm?apiId=42270) | Read catalog/namespace, authorization/environment labels, request/response, expanded nested rows/examples and footer | Current visible pages separate seller permission, Jushita, category schema and order-query gates | Examples, buttons and SDK links are not calls |
| [SDK Management](https://developer.alibaba.com/docs/doc.htm?articleId=117992&docType=1&treeId=505) and [OAuth](https://developer.alibaba.com/docs/doc.htm?articleId=107726&docType=1&treeId=445) | Read identity/date/TOC, flows, tables, examples and footer | SDK is application/permission specific; OAuth2 needs app + seller authorization | Deprecated/dated evidence; no SDK download, OAuth or token |
| [Higress](https://github.com/higress-group/higress) | Followed the official link and redirect; read README, license, security, v2.2.3 changelog, recent commits, two issue pages, PRs and discussions | Active official-linked generic gateway, not AliExpress seller connector | `research_only_no_install`; do not duplicate T One gateway |
| [alonseg/AliexpressApi](https://github.com/alonseg/AliexpressApi) | Read README/package, all 16 visible commits, releases, license surface, security, issues, PRs and discussion absence | Unofficial wrapper has no releases/security policy and a deprecated dependency | `research_only_no_install`; no clone/install/credentials |

### Comment-track coverage

- Higress issue 4034: read the description and 32 comments, including maintainer rechecks, counterclaims and a failed agent status. One answered discussion was also read through the accepted answer and author follow-up; the follow-up remained unresolved. This is repository-maintenance risk only.
- `alonseg/AliexpressApi` issue 1: read the question and the single public reply. It pointed to a logged affiliate portal, but there was no maintainer/official answer and the issue remained open. Usernames, avatars, screenshot media and tokenized media URLs were filtered. The claim remains a dated community signal.
- Official API, SDK and OAuth pages exposed empty FAQ/comment surfaces. No social-media page was introduced this round, so no social comment cluster was invented.

Distilled increment:

1. Reverse-verify exact GitHub identities from a first-party property and record redirects/transfers; never infer official status from a name or stars.
2. Official ownership and maintenance do not establish seller relevance. Generic gateway infrastructure is excluded when it duplicates T One and lacks AliExpress seller endpoints.
3. An accepted answer can solve only one question; follow-up and readback decide workflow closure.
4. Comment coverage must report actual count/range and preserve anonymous summaries. Policy/API/fee claims return to official verification.
5. Logged Chrome remains `blocked_connector`; copying cookies or creating a new identity is rejected.

### Updated AE-FAIL-001 — Logged Chrome connector

- Result: `failed_attempt`; the browser client stopped before tab inventory and the native manifest diagnostic returned `installed=true, valid=false`.
- Containment: no tabs, cookies, tokens, sessions, credentials or account data were read; no repair or bypass occurred.
- Next test: after the owner repairs or reinstalls the existing plugin, rerun supported read-only initialization.

## Public Seller/onboarding and independent comment rotation — 2026-07-19 02:16 +08:00

No AliExpress store, Seller Center identity, OAuth, Jushita, ads, ERP, native-AI entitlement, funding account, or deposit authorization was available. No registration, form submission, login, identity, bank, payment, publication, price, promotion, message, shipment, refund, media download, or engagement action occurred.

### Pages/software actually checked

| Source/software | Actual operation and coverage | Visible result | Unavailable boundary |
|---|---|---|---|
| [EU/EEA seller agreement summary](https://cdn.contract.alibaba.com/terms/b_platform_service_agreement/20250516111505112/20250516111505112.html?lng=en) | Read identity/date and sections 1–9 to footer; expanded history; opened the 2025-12-29 version; followed the directly related seller-rules link | Current summary is scoped to EU/EEA sellers and expressly does not replace the full agreement; seller integrity and possible restriction categories were visible | Exact historical diff was not computed; back-to-latest control was disabled after opening history |
| [AliExpress Seller public landing](https://sell.aliexpress.com/zh/) | Read navigation, Choice, AI, five steps, cases, auto-open contact interests and footer; closed the form without input; followed onboarding | Public AI Agent claim names four scenario groups; interest form lists POP/海外托管/全托管/半托管 | Store-type content blank; no authenticated entry, mode entitlement, AI input/output or metric |
| [速卖通品牌商家开店流程](https://alidocs.dingtalk.com/i/nodes/gvNG4YZ7Jnxop15OCEDEjYG7W2LD0oRE) | Read creation/edit metadata; scrolled the 2,707-word lazy document at ten recorded positions to final height 8,110; read POP steps 1–7 and full-managed steps 1–5; inspected related help links | Public guide separates POP and full-managed flows and exposes identity, funding/UBO, deposit, category and brand steps | Comment entry yielded no readable list; current console fields, eligibility and fee values unavailable |
| Current logged Chrome bridge | Re-ran supported read-only bootstrap only | Failed before tab inventory with the existing process-property conflict | Zero tabs/session data inspected; no cookie/token/profile read |
| [Reddit topic](https://www.reddit.com/r/Aliexpress/comments/1uy6wa3/these_type_of_sellers_should_be_banned/) | Opened the top-sort URL and stopped at network-security block | HTTP 403 only | No body or comments read; no workaround used |
| [Bilibili operator video](https://www.bilibili.com/video/BV1g8y6YDEke/) | Played 395.433/395.433 seconds (100%); checked frames at 30/120/240/360 seconds; read metadata; inspected subtitle control; scrolled comments; attempted latest sort and a four-reply expansion | Video gate passed, but the page displayed 24 comments and anonymously exposed only two top-level comments plus one author reply | Comment sample was below 10 and not all; latest, nested replies and remaining comments triggered login. Whole source is `opened_not_reviewed`; no distillation |

### Duplicate skips

- Existing AI press release, API catalog, OAuth/SDK pages, Choice/full-managed agreements and GitHub candidates were not reopened; their existing fingerprints remain valid until a version/content change.
- The Seller landing was reached from a direct current official cross-link rather than repeating an old announcement.

### New and invalidated knowledge

1. `official_public_surface_claim_verified_execution_pending` now distinguishes a current first-party AliExpress AI scenario claim from both announcement-only evidence and authenticated operation. It does not advance the tool beyond `research_only`.
2. Public manager-contact checkboxes are inquiry taxonomy, not a store-type matrix. The blank `店铺类型` section keeps the exact current matrix `unknown`.
3. The current EU/EEA summary adds a jurisdiction-scoped integrity rule, but explicitly cannot replace the full agreement or a case-specific Seller Center record.
4. Public onboarding documents can narrow candidate steps, yet identity, UBO, funding, deposit and brand fields remain high-risk, time-sensitive, and non-executable without owner action and current authorization.
5. A source can pass video playback yet still fail the independent comment gate. The Bilibili source therefore remains `opened_not_reviewed`; its metadata, frames and visible comments contribute no new operator rule.

### Comment coverage and filters — no knowledge distillation

- `opened_not_reviewed`: the video reached 100% playback and four key frames were checked, but only two top-level comments and one author reply were readable out of 24 displayed.
- `blocked`: latest ordering, four nested replies and the remaining comments required login. The current Chrome bridge failed before tab inventory, so the authorized logged session could not legally complete the sample.
- `filtered_noise`: identity, engagement counts, promotional framing, profanity and emotion were not retained or promoted.
- `distilled_comment_delta`: none. The incomplete comment themes are not an operator case, policy lead or course input; AE-EVAL-076–078 only test rejection of overclaiming.

### Hard-truth outputs

- `deviation_check`: all reviewed content sources were AliExpress seller-operations sources; browser diagnostics only supported the authorized evidence path. Direct-mainline share exceeded the 70% minimum.
- `opened_not_reviewed`: Reddit topic (HTTP 403, no body/comments); Bilibili video (playback complete, comment gate incomplete); logged Chrome bridge (failed before tab inventory).
- `fully_reviewed`: EU/EEA seller agreement summary; AliExpress Seller public landing; official-linked brand-merchant onboarding guide.
- `no_delta`: `false` for official knowledge because three fully reviewed first-party/official-linked pages added scoped facts and corrected overclaims; `true` for community knowledge because no community source passed the hard gate.

### Distilled assets and next source

- Added fingerprints AE-FP-026 through 029, live evidence AE-LIVE-20260719-039 through 044, failures AE-FAIL-012/013, and evaluations AE-EVAL-069 through 078. AE-FP-029/AE-LIVE-044 are dedupe/failure records only and are excluded from successful evidence and knowledge distillation.
- Updated the unique Skill and training contract; no shared registry, adapter, queue, runtime, model gateway, page, or second automation was created.
- Next safe source rotation: the official-linked `入驻材料与费用` document and current AliExpress Help rule pages, then a lawful public community/video source with readable subtitle and comments. Revisit logged sources only after the existing Chrome bridge is repaired.

## Entry fees, category qualifications, transaction fees, and Rules AI surface — 2026-07-19 02:54 +08:00

No AliExpress store, authenticated Seller Center role, category authorization, deposit/payment authority, native-AI entitlement, OAuth, ads, ERP or buyer/order data was available. All work was public and read-only; no form, AI prompt, category application, identity document, payment, publication, price, activity, ad, shipment, refund, message or authorization action occurred.

### Pages/software actually checked

| Source | Actual coverage and operation | Visible result | Boundary |
|---|---|---|---|
| [速卖通入驻材料与费用](https://alidocs.dingtalk.com/i/nodes/N7dx2rn0JbxOaqnACQjbk79AWMGjLRb3) | Read creation/edit metadata; rendered body fit 899/899 px; read both fee/material sections; opened the deposit, transaction-fee and qualification links; opened `所有评论 (0)` and read all one item under `已解决 (1)` | Overview indexes deposit, commission and transaction-service surfaces; one anonymous question mentions a manager-described one-time fee | Overview values are not universal; no official reply, contract, invoice or payment evidence for the comment |
| [各类目保证金一览表](https://rule.aliexpress.com/rule-channels/36963666/122523112) | Read revision 2025-12-12; scrolled the exact content container from 0 to 708/708 px; read category rows, applicability note and footer; followed qualification link | Deposit depends on category; multiple permitted categories use the highest applicable amount | No bound category, eligibility result, authenticated fee screen or payment |
| [部分类目准入资质要求](https://rule.aliexpress.com/rule-channels/36963666/122523100) | Read revision 2026-03-16; inspected positions 0/1500/3000/4500/6000/7500/9000/9681 in a 10,538 px container and reached footer | Express scope: China-mainland-registered merchants and named cross-border modes; requirements vary by exact category | Templates/attachments not downloaded; no identity, licence or application action; overseas-local applicability not established |
| [卖家基础规则（交易）](https://rule.aliexpress.com/rule-channels/36963666/122523016) | Read revision 2026-06-29; inspected 13 positions from 0 to 24,054 in a 24,911 px container and reached footer; covered registration, category/brand, orders, logistics, disputes, settlement, fees, chargebacks, deposit and compliance | Applicable category rate is taken at order release and charged on final transaction amount; cancellation/seller refund returns the corresponding fee proportionally | No store/category/order/statement binding and no operational action |
| [规则速递列表](https://rule.aliexpress.com/rule-channels/41564732/?tocUuid=sEN874os1ChjlXQM) | Inspected page 1 and page 2 of a visible 70-item/7-page list | Latest page-1 item was dated 2026-07-13 | No item body opened; `opened_not_reviewed`; no policy claim distilled |
| Rules-page `AI助手` | Observed the same public panel on deposit, qualification, transaction-rule and digest surfaces; recorded visible labels; entered no prompt | `AI助手`, `限时免费`, `有新结果(0)`, and prompt invitation were visible | No account role, eligibility, input, output, quota/cost, data destination, edit/submit, metric, recovery or T One connection evidence |

### Duplicate and irrelevant skips

- Existing Seller landing, onboarding process, Choice/full-managed agreements, seller-affiliate agreement, API catalog, OAuth/SDK and GitHub fingerprints were unchanged and were not reopened.
- No unrelated generic cross-border, other-platform AI, GitHub or tool source was used. `irrelevant_skip`: none opened.

### New, invalidated, and conflicting knowledge

1. Invalidated: an onboarding overview percentage or amount cannot become a universal cross-category fee default. Use the current exact leaf-category rule and authenticated context.
2. New scoped fact: the 2026-03-16 qualification page states a China-mainland entity and named cross-border-mode boundary; it cannot be generalized to overseas local sellers.
3. New scoped fact: the 2026-06-29 self-operated transaction rule ties the rate to order-release time and the charge to final transaction amount, with proportional return after cancellation/seller refund.
4. Conflict retained: one anonymous fee question has no official reply or documentary support. It is a `single_case` signal requiring the exact signed program, current rule/system and owner-approved invoice/payee verification.
5. Invalidated: a visible public `AI助手` and `限时免费` label do not prove seller entitlement, ongoing free cost, real input/output or T One connection.

### Hard-truth outputs and distillation

- `deviation_check`: 100% of reviewed content directly served AliExpress seller fees, category entry, transaction settlement or AliExpress-native AI. Tools/AI was a bounded observation within the mainline; cross-platform reference was 0%.
- `fully_reviewed`: AE-LIVE-20260719-045 through 048. AE-LIVE-20260719-050 is a verified negative-boundary observation attached to those fully reviewed Rules pages.
- `opened_not_reviewed`: AE-LIVE-20260719-049, Rules digest pages 1–2 of 7; no item body and no policy delta.
- `blocked`: authenticated category/fee/store context, financial approval, and native-AI operation.
- `no_delta`: `false` for official mainline facts; `true` for generalized community practice because the single anonymous comment cannot be promoted.
- Added AE-FP-030 through 034, AE-CONFLICT-002, AE-LIVE-20260719-045 through 050, AE-FAIL-014 and AE-EVAL-079 through 084. Updated the existing unique Skill/course/workflow/evidence files only; no shared core, new runtime, new connector, second Skill, task or automation was created.

Next weakest mainline topic: a current official AliExpress activity/Digital Marketing or order-logistics rule with a fully reviewable second-level page. Native-AI execution waits for a legally authorized isolated seller identity; the public panel will not be prompted merely to manufacture output.

## Knowledge-package-first ads/API delta — 2026-07-19 03:37 +08:00

No package was cloned, installed, imported, built, executed, or given credentials. No Seller Center, ad account, ERP, OAuth, buyer/order data, campaign, budget, payment, activity enrollment, publication, shipment, refund, or message action occurred.

### English discovery and duplicate screening

Executed the English candidate queries `"AliExpress seller agent skills" GitHub OR GitLab`, `"AliExpress operations playbook" OR "AliExpress seller SOP"`, `"AliExpress ads automation" GitHub SDK`, and `"AliExpress ERP integration" GitHub OMS PIM WMS`. Results dominated by commercial integration claims, generic ERP/PIM services, affiliate tooling, and stale unrelated material. Search snippets were `candidate_screened` only and produced no evidence or package adoption. Existing owner/repo, commit/release, and file hashes prevented reopening unchanged candidates.

Time allocation was 72% package discovery/audit/reuse/deduplication, 23% targeted first-party deep verification, 0% introductory official pages, and 5% community candidate screening. This satisfies the 50% package minimum and 10% introductory-page ceiling.

### Fully reviewed package candidates

| Package | Audit coverage | Decision and exact fusion |
|---|---|---|
| [nexscope-ai/eCommerce-Skills](https://github.com/nexscope-ai/eCommerce-Skills) | Full repository catalog plus complete PPC and cross-border Skill files; MIT; 114 visible commits; latest 2026-06-10; no releases/security policy; two open issues and two open PRs; outbound tracking/marketing links and unsourced benchmarks recorded | `extract_rules_only`: merge only input-completeness, explicit-estimate, and non-executable-plan guards into the unique Skill and AE-EVAL-085–087. Do not install the overlapping package. |
| [moh3a/ae_sdk](https://github.com/moh3a/ae_sdk) | README, manifest, MIT surface, v0.6.0 release/changelog, issue 9, PR 11 and security surface; latest 2025-03-30; unresolved invalid-token failure; unmerged order-details change | `research_only`: dropshipping/affiliate SDK is not seller Digital Marketing or store authorization. Add surface-separation and credential-failure tests only. |
| [bayborodin/aliexpress-sdk](https://github.com/bayborodin/aliexpress-sdk) | README, MIT license, pyproject, core source, generated API tree, sole test, all 17 commit dates, releases/issues/PR/security | `rejected_unsafe`: last code 2022, Python 3.6–3.8 alpha, port-80 default, process-global credential state and mismatched version test. Add rejection tests; no code reuse. |
| [kk71/aliexpress-sdk-py3k](https://github.com/kk71/aliexpress-sdk-py3k) | README, MIT license, full single source file, all five commits, releases/issues/PR/security | `rejected_unsafe`: last code 2014, plaintext authorization/API URLs and credential-bearing URL logging. Add transport/logging rejection tests; no code reuse. |

Each audit sampled one core workflow, one failure boundary and three rules. `higress-group/higress` and `alonseg/AliexpressApi` were unchanged and skipped by their existing fingerprints.

### Targeted official deep verification

| Source | Coverage | Bounded result |
|---|---|---|
| [AliExpress activity seller rules](https://terms.alicdn.com/legal-agreement/terms/product/20221027172120871/20221027172120871.html) | Read all 15 clauses and exact footer; HTTP Last-Modified 2022-11-01; no visible effective date/version | Historical checklist for category/product/brand/price/discount/logistics/service/display/quota, truthful rights/discounts, order/after-sales duties, and no participation/effect guarantee. Current activity and store conditions remain live-system dependent. |
| [Digital Marketing product service agreement](https://terms.alicdn.com/legal-agreement/terms/product/20220707153343377/20220707153343377.html) | Read effective date, China-mainland scope and sections 1–11 to footer; followed the directly related seller-rule page | Historical product/brand marketing, CPC/impression/display-duration, prepayment/report and no-result-guarantee architecture. No current product name, UI, rate, attribution, balance or permission was observed. |
| [Digital Marketing account service agreement](https://terms.alicdn.com/legal-agreement/terms/product/20220707144537599/20220707144537599.html) | Read effective date and sections 1–11 to footer | Historical account, recharge, plan, payment, report and security architecture. Current minimum, refund and authenticated account state remain unknown. |
| Current Product Schema and Seller Order API pages | Reused existing unchanged deep-page fingerprints rather than reopening the catalog | HTTPS, authorization and Jushita constraints reject legacy SDK assumptions; examples remain documentation, not calls. |

### Hard-truth output

- `deviation_check`: package and official verification work directly served AliExpress ads, activities, seller API and connector safety; generic package rules were retained only where mapped to those surfaces.
- `fully_reviewed`: AE-LIVE-20260719-051 through 057.
- `opened_not_reviewed`: none in the adopted evidence set.
- `irrelevant_skip`: AE-LIVE-20260719-058, an 08:18 generic/Taobao/Tmall video stopped at 0:00 before playback/comments; it contributed no knowledge.
- `duplicate_skip`: unchanged `moh3a/ae_sdk` release identity, existing API deep pages, `higress-group/higress`, and `alonseg/AliexpressApi` fingerprints were reused rather than relearned.
- `no_delta`: `false` for Skill guards, package decisions, failure containment, and ten regression cases; `true` for the English search snippets themselves.
- `blocked`: AliExpress seller/ads identity, current Digital Marketing product/UI/billing/report state, store-scoped OAuth/Jushita/API read, live activity eligibility, and platform-native AI operation.

Added AE-FP-035 through 040, AE-LIVE-20260719-051 through 058, AE-FAIL-015/016, and AE-EVAL-085 through 094. Updated the existing unique Skill, contract, validator, references and tests only; no second Skill, Agent, course, gateway, connector, task, goal, or automation was created.

## Knowledge-package-first order/inventory/fulfillment delta — 2026-07-19 03:48 +08:00

The round started by reading T One's generic adapter, store-type evidence, GitHub registry, existing AliExpress Skill/contract/tests and dedupe fingerprints. The shared runtime has generic listing/order/inventory/shipment domains, but no AliExpress-specific adapter, OAuth/API call, store binding or ERP diagnostic. The Miaoshou help record is a public authorization lead only. A registry delta corrected `nexscope-ai/eCommerce-Skills` from local `unknown_repository_blocked` to shared `reference_only`; ERPNext is also shared `reference_only` for entity/ledger vocabulary.

### English package discovery and decisions

Executed four order/inventory/ERP query variants: GitHub AliExpress order/inventory connector ERP; AliExpress Open Platform orders/logistics maintained SDK; GitHub/GitLab AliExpress ERP connector source; and awesome ecommerce OMS/inventory/fulfillment agent/MCP. No adoptable open AliExpress OMS/ERP package was found.

| Candidate | Complete audit boundary | Decision |
|---|---|---|
| FlexigoTech Odoo 19 AliExpress connector | Full 414-line public listing, OPL-1 terms, price, versions, dependencies, workflow and footer; comments login-gated; no public source/tests/security/demo | `research_only`; retain only one-store identity, separate read/write scopes, and idempotent retry/readback hypotheses |
| `saleor/saleor-mcp` | Reused unchanged independent-commerce full fingerprint at commit `7270f057`; AGPL-3.0, v0.1.8, permissions, domain allowlist, release/issues/PR/security | `extract_rules_only`; read-only is not low privilege, require exact domain allowlist and per-store credential reference; not AliExpress |
| `frappe/erpnext` | README to footer, GPL-3.0, SECURITY, releases, one issue, and PR 57216 boundary; no install/database/admin | `keep_reuse` under shared `reference_only`; reuse order/stock/warehouse/shipment/ledger vocabulary only |

ERPNext PR 57216 is `opened_not_reviewed`: its demo video failed and inline comments were incomplete, so neither the PR nor its visible bot warning was distilled. The commercial package comments remained login-gated. No clone, purchase, install, dependency execution, credential, demo login or comment action occurred.

### Targeted official differences and distillation

The batch-inventory, order-delivery, shipment-modify and shipment-query deep pages were read through the footer, with the query endpoint as the directly related second-level page. Net rules: treat ERP/API as eight independent store-scoped capabilities; persist per-item batch results; classify shipment errors and read back before completion; prevent cross-store tracking; keep time/count/route restrictions time-sensitive; and gate delivery address/tax/passport fields as separately authorized high-sensitivity data.

- `fully_reviewed`: AE-LIVE-20260719-059 through 065.
- `opened_not_reviewed`: AE-LIVE-20260719-066, ERPNext PR 57216.
- `duplicate_skip`: the Saleor MCP full audit and unchanged shared registry evidence were reused by fingerprint.
- `irrelevant_skip`: none.
- `no_delta`: `true` for search summaries and inaccessible PR/comments; `false` for registry reconciliation, capability matrix, three official API rules, two failure reviews and ten cross-category evaluations.
- `deviation_check`: all reviewed sources served AliExpress order, inventory, shipment, ERP/API permissions or the directly mapped connector boundary; generic packages contributed only mapped patterns.

Added AE-FP-041 through 046, AE-LIVE-20260719-059 through 066, AE-FAIL-017/018, and AE-EVAL-095 through 104. No second Skill, Agent, course, gateway, connector, task, goal, cron or external action was created.
