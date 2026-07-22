# Walmart official GitHub audit — 2026-07-19

## Scope and guardrails

- Capture window: 2026-07-19 01:04–01:18 Asia/Shanghai.
- Browser: headed public Playwright session `walmart-github-audit-20260719`; no GitHub sign-in, clone, install, execution, authorization, credential entry or form submission.
- Country/store scope: global Walmart engineering open source; this is not a US/CA/MX Marketplace seller account, Marketplace OAuth grant, Walmart Connect account or WFS enrollment.
- Shared registry check: `config/github_capability_registry.json` contained no `walmartlabs/*` owner/repo record. Existing `whitebox-co/walmart-marketplace-api` and `api-evangelist/walmart` records are third-party and remain `research_only` / `rejected_unsafe`; this file does not modify the shared registry.

## Official identity verification chain

1. Opened the Walmart Global Tech Blog article [Beyond Open Source @WalmartLabs](https://medium.com/walmartglobaltech/beyond-open-source-walmartlabs-e690c934fe35), identified publication, author and date (2016-10-21 in the rendered page), opened the table-of-contents control, read all three body sections, scrolled through three viewports to the page end, opened the single public response, and followed the body `github.com` link.
2. That visible link opened [github.com/walmartlabs](https://github.com/walmartlabs), whose organization page rendered the name `Walmart Global Tech`, 135 repositories and `opensource@email.wal-mart.com`.
3. Therefore `walmartlabs` is `verified_official_organization`. No inference is made that `github.com/walmart`, any similarly named account, or a search-ranked repository is official.

Coverage limitation: the Medium response thread contained one short supportive response and no author reply. The page later showed a sign-up dialog; it was closed without account action. The old article verifies the organization link, not the current support status of every repository.

## Organization list coverage

- Opened organization Overview, scrolled to the footer, then opened `View all repositories`.
- Repository list was visibly sorted by `Last pushed` descending and showed `135 repositories`.
- Read page 1 and `Next` page 2, including archived/source/fork labels, licenses where GitHub exposed them, issue/PR counts and update dates.
- Independently enumerated all 135 public repository metadata rows through the unauthenticated GitHub REST organization endpoint before the rate limit was exhausted; searched names/descriptions/topics for Marketplace, commerce, retail, catalog, inventory, order, OAuth, webhook, GraphQL, X12, supply, mobile, design and analytics terms.
- The REST endpoint later returned HTTP 403 rate-limit responses; no token was requested or used. Repository deep reads continued through public rendered pages.

Result corrected by the later knowledge-package pass: the organization contains an official seller SDK, `walmartlabs/partnerapi_sdk_dotnet`, but Walmart archived it on 2020-08-14 and the README marks it unsupported. No maintained current official Walmart Marketplace Seller API SDK, Walmart Connect SDK, Marketplace OAuth 2.0 sample or seller webhook sample was established. The earlier absolute `not_found` statement is superseded; “found, archived and unsupported” is the current status.

## Deep repository audit

### `walmartlabs/walmart-api`

- URL: https://github.com/walmartlabs/walmart-api
- Purpose observed: JavaScript wrapper for the former consumer-facing Walmart Labs Open API (product/search/store/feed reads), not Marketplace seller item/order/inventory/ads APIs.
- Status: owner archived it on 2026-05-20; README says deprecated and unsupported and points to `walmart.io`; latest visible commit `b86cff5` is dated 2019-07-11.
- License/dependencies/deployment: MIT; old npm usage `npm install walmart --save`; API-key model. No clone or install was performed.
- Release/changelog coverage: Releases page says no releases; two tags are visible. Commit history was read to the oldest visible group.
- Issues/PR/comments: latest-updated issue list had 7 open / 1 closed; issue #14 was read to the end and contained a single operator question about finding API discussion communities, with no answer. PR list showed three old open PRs. This is a `single_case` community signal, not a current rule.
- Security/discussions: no security policy and no published advisory were rendered; `/discussions` returned GitHub 404.
- Disposition: `rejected_unsafe` for T One connector integration and `historical_trace` only. It must never be routed as Marketplace or OAuth 2.0.
- Key artifacts: `page-2026-07-18T17-07-32-142Z.yml` SHA-256 `903A6D46EC4161873DC8ABEBFDCA1FF073E1CE8FF459F26A9F151C8625CFF8BB`; issue #14 `page-2026-07-18T17-10-51-258Z.yml` SHA-256 `4C7E9A1F16F86FEDB7459EE12AE144EA53168E6167403ED04A300EB04A8275EA`.

### `walmartlabs/gozer`

- URL: https://github.com/walmartlabs/gozer
- Purpose observed: Java X12 parser for retail/supply-chain messages. README support table showed generic 5010, DEX 894 and ASN 856 support, while PO 850 was WIP and several acknowledgements/invoice/shipment sets were under consideration.
- License/dependencies/deployment: Apache-2.0; Maven/Java project. The README warns that successful parsing does not validate element values and adopters must enforce their own compliance guides.
- Maintenance: latest visible commit `698df7e` dated 2026-02-11 upgraded to JUnit 5; release page latest was `0.3.4` dated 2022-04-26. Thus recent maintenance does not equal a new release or Marketplace readiness.
- Releases/changelog coverage: read release list to its end, commit history across 2026/2024/2023/2022 groups, and `UPGRADE_SUMMARY.md` including dependency/security notes.
- Issues/PR/comments: latest-updated issue and PR lists were read to the end. Issue #144 stated a Walmart supplier guide change for a DTM segment in the ASN 856 Pack loop; the thread linked PR #145 and closed as completed. This is evidence of the repo's X12 maintenance path, not Marketplace Seller API behavior.
- Security/discussions: no security policy and no published advisory were rendered; `/discussions` returned 404.
- Reuse boundary: `research_only` for a future, separately authorized EDI/supply-chain adapter. It is not a Walmart Marketplace item/order/inventory SDK and must not be installed until dependency/security review and a real EDI requirement exist.
- Key artifacts: README `page-2026-07-18T17-11-42-106Z.yml` SHA-256 `8666D23BC46EA49AE99F5A7EA9FFEA8DC9118C90450379BF7E162D213B28420A`; issue #144 `page-2026-07-18T17-15-00-711Z.yml` SHA-256 `0C0745602D014A50152BDAE134EC4557F6743900359E1EB71CC3A2EBA4B992BB`.

### `walmartlabs/lacinia`

- URL: https://github.com/walmartlabs/lacinia
- Purpose observed: a backend-agnostic GraphQL execution engine in Clojure, not a Walmart Marketplace GraphQL client or schema.
- License/dependencies/deployment: Apache-2.0; Clojure/Java with ANTLR-generated parsers. README documents `clojure -X:deps prep`, build, test and code-generation steps; none were run.
- Maintenance/release: latest visible commit `bd6a630` dated 2026-06-04. `CHANGES.md` shows version 1.3.0 dated 2026-06-02; tags and changelog were opened and read to their page ends.
- Issues/PR/comments: latest-updated issue and PR lists were read. Issue #460 was read from body through the end of its public discussion: an operator reported subscription ordering problems; an organization member asked for timing/reproduction details, later stated the cause was still unclear, and the reporter said the issue had blocked that use. This remains a dated project-specific counterexample, not seller-platform evidence.
- Security/discussions: no security policy and no published advisory were rendered; `/discussions` returned 404.
- Disposition: `official_but_no_direct_seller_relevance`; exclude from the Walmart expert connector. Star count and current maintenance do not make it a Marketplace dependency.
- Key artifacts: README `page-2026-07-18T17-15-44-214Z.yml` SHA-256 `E2DD5A69792A32D3E44B95F0CF977761AF8A4622F64D1094EF6A77C9F8582D9C`; issue #460 `page-2026-07-18T17-18-45-034Z.yml` SHA-256 `84A23086572B1B91C9209AE708FEABDFC7F9FC3065779255FA74FF51ECF3407D`.

## Knowledge-package priority comparison

Captured: 2026-07-19 03:10–03:49 Asia/Shanghai. The existing T One Walmart Skill, contract, curriculum, evaluations, failure log, connector truth and shared GitHub registry were checked first. The concrete gap was not another API wrapper; it was a current, store-scoped OAuth/domain client with country isolation, raw-response preservation, throttling, effect verification and approval gates. Five packages were compared without cloning, installing or running them. Current official facts were reused from the already fingerprinted OAuth, market-availability, item-spec and payment evidence; unchanged official introduction pages were not reopened.

English discovery queries used in the incremental pass:

- `site:github.com Walmart marketplace agent skills seller playbook API SDK`
- `site:github.com WFS operations SOP Walmart marketplace seller`
- `site:github.com Walmart Connect ads automation SDK`
- `site:github.com ecommerce agent skills commerce MCP order inventory fulfillment automation`

The first three queries directly screened Walmart-specific packages. The general commerce query surfaced Shopline, Shopify, Kibo and generic agent-commerce projects; they were marked `irrelevant_skip` because they did not implement a Walmart seller contract. `whitebox-co/walmart-marketplace-api` was skipped after search as the same already-reviewed owner/repo/version fingerprint. No GitHub search result, star count or collection size was treated as evidence of quality.

### `walmartlabs/partnerapi_sdk_dotnet`

- URL/identity: https://github.com/walmartlabs/partnerapi_sdk_dotnet; official through the verified `walmartlabs` chain.
- Version/maintenance: v1.0.1 released 2018-06-08; last commit `322b4b5` on 2020-08-14 archives the repository. README says archived and not supported.
- Coverage/license: feeds, items, prices/promotions, orders and inventory with sample/tests; Apache-2.0.
- Deep coverage: README, API coverage table, Docs, Sample, changelog, two releases, license, issue/PR/security state and latest commit were checked. The sample requires a mounted `credentials.json` containing Consumer ID and Private Key. No security policy or published advisory was visible.
- Core/failure/rules sample: core order and feed methods were present; the archive/legacy credential model is the boundary failure; three extracted historical rules were seller credentials required, order effects remain distinct, and mock/sample results are not production effects.
- T One fit: high functional duplication plus .NET 4.6/.NET Standard 1.3/.NET Core 2.0 deployment cost. Current T One official OAuth 2.0 and per-endpoint country evidence supersede its legacy contract.
- Disposition: `rejected_stale`. Do not copy the private-key sample or treat official ownership as current support.

### `whitebox-co/walmart-marketplace-api`

- URL/identity: https://github.com/whitebox-co/walmart-marketplace-api; third-party Whitebox package, not Walmart official.
- Version/maintenance: MIT v3.0.1 released 2022-12-14; latest main commit is also dated 2022-12-14, with a later unmerged generation PR and open 2023–2024 failures.
- Deep coverage: README, package manifest, changelog, latest release, license, issues, PRs and Security were checked. The repo shows five open issues, seven open PRs, no SECURITY.md and no published advisory. Visible failures include Recon representation, duplicate requests, missing throttle control and unresolved Canada support.
- Core/failure/rules sample: configured Orders API plus token cache and recursive pagination were sampled; missing throttling and modified/generated schemas are the failure boundary; three reusable rules are central store-scoped token handling, raw pagination preservation and current-official schema/header validation.
- Credential/dependency boundary: client ID/secret and consumer-channel type enter an in-process token cache. No telemetry was declared on the reviewed surfaces, but debug/log redaction was not proven. Node 16.19–<18, NPM 8, Axios, Java/OpenAPI Generator and Quicktype would duplicate and mismatch T One’s current runtime.
- Disposition: `extract_rules_only`. Do not install or import the 2022 generated clients.

### `highsidelabs/walmart-api-php`

- URL/identity: https://github.com/highsidelabs/walmart-api-php; third-party Highside Labs package, not Walmart official.
- Version/maintenance: BSD-3-Clause v0.7.0 released 2023-08-18; the README coverage claim is explicitly “as of 8/17/2023.”
- Deep coverage: README, Composer manifest, generated country/API layout, release, license, issues, PRs and Security were checked. The visible state had 15 open issues, four open PRs, no SECURITY.md and no published advisory. Current cases cover Catalog `itemId`, Returns `DateTime`, order shape, Canada responses, schema idempotency and carrier quote failures.
- Core/failure/rules sample: US/CA/MX category/API namespace selection was sampled; stale generated models and unresolved serialization/response failures are the boundary; three reusable rules are country/API namespaces, auth-mode isolation and raw-response/model validation.
- Credential/dependency boundary: client ID/secret plus optional Consumer ID/private key; debug output can go to stdout or a file. No telemetry was declared in reviewed README/Composer surfaces. PHP 8, cURL/JSON/mbstring, Guzzle, UUID, Symfony UID and phpseclib duplicate the existing runtime.
- Disposition: `extract_rules_only`. Its 2023 country matrix must not override current official endpoint evidence.

### `nexscope-ai/eCommerce-Skills/walmart-seller-guide`

- URL/identity: https://github.com/nexscope-ai/eCommerce-Skills/tree/main/walmart-seller-guide; third-party Nexscope skill, not Walmart official.
- Version/maintenance: repository-level MIT license, no published releases, and the collection labels the Walmart skill `Beta`. The path-history route and anonymous GitHub API returned 429/403, so its latest path commit remains `unknown`; no access-control bypass or credential was used.
- Deep coverage: repository README and collection status, raw `walmart-seller-guide/SKILL.md`, license, Issues and Security pages were checked. The relevant file is 1,117 characters, SHA-256 `8F99811F65F6A16EDDD2214B2A5640439DF42D95DCF60FBFB256A5AA700DBBDD`; it contains one capability list and three example prompts, but no Walmart citations, country/site scope, permissions, error recovery, effect verification or evaluation set. Two open issues and two open PRs were visible; one issue asks for updates to beta skills. No SECURITY.md or published advisory was present.
- Core/failure/rules sample: the sampled workflows were application setup, listing optimization and WFS-versus-self-fulfillment advice. The boundary failure is that all are labels rather than reproducible operations. Its WFS, Connect and Pro Seller concepts were checked against T One's existing official evidence and added no rule delta.
- Credential/dependency boundary: the relevant file declares no credential or telemetry; the advertised global `npx skills add` command was not run. Installing the collection would create a duplicate Walmart Skill with less evidence than the existing one.
- Scope: generic Walmart.com seller summary; CA/MX, store mode, ownership and execution identity are absent.
- Disposition: `research_only`. Do not install or merge the thin beta Skill.

### `stores-com/walmart-marketplace`

- URL/identity: https://github.com/stores-com/walmart-marketplace; third-party Stores.com wrapper, not Walmart official.
- Version/maintenance: MIT v2.0.0 released 2026-02-12 at `24ae67a`; latest visible main commit `d7926ed` on 2026-06-24. The page showed 102 commits, two releases, zero open issues and one open PR. No SECURITY.md or published advisory was present.
- Deep coverage: README, release, commit history, package manifest, raw `index.js`, raw test file, license, test directory, PR and Security pages were checked. Raw hashes are `2405244333FCFFD7470B94DE8A5A649B06D724D10230616104E36754482A128C` for `index.js` and `36A5F0314D0EB49CACFD19E43BA1C33306060B986AD117805DFCBD3290C56E97` for the test file. No code was executed.
- Core/failure/rules sample: token acquisition, correlation IDs, catalog/order/report pagination and inventory/price/order effects were sampled. The access-token cache expires at half the server lifetime and pagination follows `nextCursor`; those are test ideas only. The constructor's full `_options`, including `clientSecret`, is JSON-serialized as the memory-cache key. No timeout, retry, country-market isolation, owner approval or effect verification layer was found in the reviewed source.
- Credential/dependency boundary: client ID/secret and bearer token handling are in process; secret redaction is not proven. Runtime dependencies include `@stores.com/http-error`, `csv-parse`, `jszip` and `memory-cache`. It duplicates the existing T One OAuth/domain client and directly exposes destructive item, inventory, price, order and shipment methods.
- Scope: reviewed routes and README are US Walmart.com Marketplace oriented; CA/MX headers, endpoints and contracts were not established.
- Disposition: `rejected_unsafe`. Current maintenance and tests do not offset the secret-bearing cache key or missing execution gates; do not install or import it.

### Comparison result and avoided rework

- No candidate qualifies for `merge_into_existing` code integration. Installing any of them would duplicate the existing Skill or adapter/OAuth/domain boundary while importing a thin shell, stale generated contracts, unsafe credential handling or a second language runtime.
- The only retained delta is design evidence already missing from the connector gap list: store-scoped token cache, country/API namespaces, raw pagination and response preservation, explicit throttle/schema preflight, credential/debug redaction and failure-shaped contract tests.
- Avoided rework: no second SDK wrapper, no second Agent/Skill, no new model gateway, no copied item schema and no package install. Current first-party OAuth, dynamic schema, market availability and payment references remain the authority.
- Still requires official/authorized validation: current endpoint-by-country matrix, OAuth scopes, throttles, sandbox response shapes and one owner-authorized read payload per implemented domain. No candidate supplied a current Marketplace Connect/WFS/Ads credential or business effect.

## Triage-only exclusions

- `walmartlabs/oauth2`: archived owner fork of `golang/oauth2`, BSD-3-Clause, no releases; it is not a Walmart Marketplace OAuth sample. Exclude from connector design.
- `walmartlabs/apidocs`: static HTML pages for selected WalmartLabs open-source project docs, no repository description, no release and no visible license; it is not Marketplace API documentation. Exclude.
- `walmartlabs/concord`: actively maintained workflow/CD server (2.43.0 dated 2026-06-22) with Java/Docker/Node build stack; official but unrelated to seller operations. Do not create a second workflow runtime.
- `cookie-cutter`, `concord-plugins`, `lacinia-pedestal`, `vespa-helm` and other high-update infrastructure: official organization assets without direct Marketplace seller relevance. Exclude from this expert regardless of stars or recency.

These triage-only exclusions used organization metadata and public repository landing pages. They were not promoted to reusable code and require a fresh deep audit if a later T One gap specifically matches them.

## Distilled rules and regression targets

1. Verify an official GitHub organization through a first-party/verified official outbound link plus organization identity; a matching name is insufficient.
2. `official repository` is an ownership fact, not a connector, Marketplace relevance, maintenance, license or safety conclusion.
3. An archived/deprecated consumer API wrapper must not be mapped to seller Marketplace APIs.
4. A general GraphQL/OAuth/workflow library must not be inferred to implement Walmart Marketplace authorization or schemas.
5. GitHub issue/author replies are project-maintenance evidence; platform rules, fees, country behavior and Seller Center features still require current Walmart first-party sources.
6. No clone/install/run occurs before license, dependency, maintenance, security, data-boundary and exact T One reuse review.
7. Add regression cases for false-official organization claims, deprecated API confusion, star-count integration, missing security policy, and an anonymous non-private_tenant product route.

## Uncovered / blocked areas

- GitHub REST rate limit blocked later per-repo metadata calls; public pages were used instead without credentials.
- Discussions routes for the three deep-audited repositories returned 404, so no discussion threads existed at those routes in this capture.
- No authenticated Marketplace seller account, API credential, Walmart Connect account, WFS enrollment or sandbox payload was used.
- A separate attempt to attach to the owner's already logged-in Chrome failed during the browser-client initialization (`Cannot redefine property: process`). No cookies, passwords, tokens, private tabs or account settings were inspected. Login-state social/video supplementation remains blocked by the local Chrome control runtime, not by a platform login attempt.
