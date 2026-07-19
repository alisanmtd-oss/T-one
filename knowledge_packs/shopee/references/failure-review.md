# Shopee failure review

## F-001 Open Platform public fetch

- Status: `failed_attempt`
- Date: 2026-07-18
- Scope: all target sites; developer surface; public read
- Observed: the official documentation root exists, but public fetching returned access errors and no developer login was available.
- Not established: endpoint scopes, App approval, OAuth, shop authorization, write permission, or connector health.
- Retry gate: approved developer account/App plus a read-only scope inventory and store-scoped connector test. Do not bypass access controls.

## F-002 Skill validator dependency

- Status: `failed_attempt`, repaired locally without installing dependencies
- Date: 2026-07-18
- Observed: official `quick_validate.py` could not import PyYAML in the bundled runtime.
- Repair: ran the same validator with an in-process minimal frontmatter parser limited to this Skill's simple `name/description` metadata; result was `Skill is valid!`.
- Boundary: this does not prove PyYAML is installed and must not be generalized to complex YAML.

## F-003 Generated metadata encoding

- Status: `failed_attempt`, corrected
- Date: 2026-07-18
- Observed: initial generated `agents/openai.yaml` contained mojibake.
- Repair: rewrote UTF-8 text and added a regression assertion for the Chinese display name and replacement characters.

## F-004 Live store capability audit

- Status: `blocked_owner_input`
- Date: 2026-07-18
- Evidence checked: `data/real_world/store_profile.jsonl`, `data/workspace_runtime.json`, and `config/workspace_projects.json` contain no Shopee binding.
- Blocked: live product/order/logistics/returns/settlement/native-AI visibility and all writes.
- Owner input: one deliberately authorized site/store binding, shop identity, seller origin, account program, fulfillment, ownership, and separate permission references. MFA, bank, identity, and credentials remain owner-controlled.

Before retrying a failure, record what condition changed. Repeating the same unsuccessful call without a changed condition is not training progress.

## F-005 SG Help search indexing

- Status: `failed_attempt`
- Date/time: 2026-07-18T22:14+08:00
- Actual input: typed `AI` into the SG Help Center search box and pressed Enter.
- Actual output: `No results found`, although the directly opened official AI Terms page was readable at `https://help.shopee.sg/portal/4/article/185261`.
- Lesson: an empty site-search result is not proof that a policy or feature does not exist. Preserve the direct official page and record search-index failure separately.

## F-006 TW native-AI live access boundary

- Status: `blocked_owner_input`
- Date/time: 2026-07-18T22:18+08:00
- Actual path: TW Seller Help search `AI` → 16 results → `AI 商品圖＆AI 試穿圖` → `我的商品`.
- Actual output: Seller Centre redirected to its login form. No credentials were entered and no MFA was triggered.
- Established: public instructions, seller-tier eligibility claim, documented inputs/outputs/edits and manual-download boundary.
- Not established: feature visibility for a real shop, actual generation output, errors, metrics, upload/edit or publication.
- Unblock: owner supplies a deliberately authorized TW store identity and approves a read-only feature inspection; credentials/MFA remain owner-controlled.

## F-007 TW AI Store Customer Service live access boundary

- Status: `blocked_owner_input`
- Date/time: 2026-07-18T22:39+08:00
- Actual path: public article `https://seller.shopee.tw/edu/article/24002` → official `AI 賣場客服` entry → `https://seller.shopee.tw/shop-ai-assistant/home-page`.
- Actual output: the native entry redirected to the TW Seller Centre login page. No phone, username, email, password, social/enterprise login or MFA was used.
- Public search input/output: `AI 賣場客服` returned 407 total results (377 articles, 27 courses, 3 activities), with the feature instructions first.
- Established: article date, limited eligibility, entry, schedule controls, supported question types, handoff triggers, response-rate boundary, record filters, metric definitions, FAQ separation, limitations and recovery guidance.
- Not established: real store eligibility or enabled state, buyer chat, AI reply, human intervention, record, metric, error message or external response.
- Unblock: owner supplies a deliberately authorized TW store identity and approves read-only inspection. Enabling/closing the feature or replying to a buyer requires separate item-level approval.

## F-008 Playwright launcher invocation

- Status: `failed_attempt`, corrected
- Date/time: 2026-07-18T22:38+08:00
- Observed: invoking `npx playwright-cli` without the package selector returned `could not determine executable to run`; it created no Shopee input or output.
- Repair: reused the same isolated session through `npx --yes --package @playwright/cli playwright-cli`; public search and snapshots then succeeded.
- Lesson: record launcher failure as tooling evidence only, never as a platform result.

## F-009 Formal T One portable App current launch

- Status: `failed_attempt`; shared-runtime repair required
- Date/time: 2026-07-18T23:00+08:00
- Actual input: launched `desktop_app/dist/T-One-0.1.0.exe` and inspected process, health endpoints and `logs/desktop-runtime.log`.
- Actual output: the window title was `Error`; the preferred 8768 listener timed out on `/health`, no current `app_ready` was logged, and prior attempts recorded `py ENOENT`/exit 9009. A separate same-workspace 8818 entry returned runtime version 2 and the expected workspace signature.
- Established: the artifact exists, but this launch is not a successful formal-App acceptance. Prior success remains historical evidence only.
- Owner: C1/T2 desktop runtime. This expert does not kill shared processes or modify the launcher.

## F-010 Browser-only T One model save boundary

- Status: `failed_attempt`; expected authorization boundary
- Date/time: 2026-07-18T23:06:44+08:00
- Actual input: selected `zhipu-glm-free-flash` on the live 8818 task page without a desktop owner session.
- Actual output: `/api/v1/task-configuration` returned HTTP 401 and `data/workspace_runtime.json` did not change.
- Established: a model dropdown is not proof of saved configuration, and the browser-only entry cannot impersonate the desktop session.
- Retry gate: formal App becomes healthy, then re-run select→save→reload→real call→clear error. No credential or token is to be extracted for the retry.

## F-011 Shared expert/Skill loading gap

- Status: `failed_attempt`; shared integration required
- Date/time: 2026-07-18T23:05+08:00
- Actual input/output: T One extension search `Shopee` showed the platform pack, generic marketplace plugin and disabled YouYing skill, but not the unique Shopee Skill. The Python expert router returned `None` for VN listing.
- Boundary: installing the visible pack was not attempted because the selected task is Amazon and installation would not create a Shopee authorization.
- Owner: C4/G03 platform expert and extension-catalog owners.

## F-012 Scope leakage in existing task history

- Status: `failed_attempt`; shared context/template repair required
- Actual evidence: the Amazon US task page contains an Amazon ASIN fact-validation prompt whose recorded answer falls into a TikTok generic test-preparation template.
- Lesson: platform/project/store/task facts must be revalidated before selecting a response template. A prior answer cannot be promoted because it appears under the right task.
- Owner: shared chat/context router. Shopee adds cross-platform and cross-product regressions but does not edit the shared server in this task.

## F-013 TH Help search indexing

- Status: `failed_attempt`
- Date/time: 2026-07-18T23:32+08:00
- Actual input: typed `AI` into the TH Help Center search box and pressed Enter.
- Actual output: the page said no matching page was found, although `https://help.shopee.co.th/portal/4/article/171262` was directly reachable and readable.
- Lesson: an empty site-search result is not evidence that the terms or a feature do not exist. Keep the direct official record and treat search indexing as a separate failure.

## F-014 BigSeller public-article overlay

- Status: `failed_attempt`; no retry needed for platform learning
- Date/time: 2026-07-18T23:35+08:00
- Actual input: attempted to click the public article's in-page AI-label section anchor.
- Actual output: a registration overlay intercepted pointer events and the click timed out; the page also reported one console error.
- Boundary: no force click, script bypass, registration, free trial, login, scraping tool or product capability was used. The readable article remains a `single_case` commercial source, not official Shopee evidence.
- Retry gate: only a normal visible close control or an unchanged publicly readable page; never bypass the overlay. The source is not needed to establish a general rule.

## F-015 Formal T One transient recovery and quit

- Status: `failed_attempt`; partial recovery observed, stable acceptance not proven
- Date/time: 2026-07-18T23:41–23:46+08:00
- Actual input: inspected the already-running formal T One window, opened Extensions, and read health/log state without saving or installing anything.
- Actual output: 8768 returned healthy, `app_ready` was logged, the task and Extensions pages rendered, and the capability center showed 30 packs, 24 plugins, 46 Skills and 35 agents. Before Shopee search completed, the window disappeared; the log recorded normal `app_quit`, 8768 became unreachable, and 8818 remained healthy.
- Established: the formal package can currently reach a visible workspace and Extensions page. Not established: stable lifetime, Shopee search result, unique Skill loading, route result, model save/reload/call chain or connector state in this run.
- Boundary: no T One close control was intentionally used and the log does not identify the quit initiator. Do not attribute the cause or overwrite the prior Shopee catalog evidence.
- Retry gate: a fresh owner-controlled formal-App run that remains open through Shopee search and the read-only save/reload/error sequence; no store authorization is needed for the catalog portion.

## F-016 Shopee Indonesia historical webinar replay boundary

- Status: `failed_attempt`; historical source retained, no bypass or registration retry
- Date/time: 2026-07-18T23:58+08:00
- Actual path: publicly opened `https://app.livestorm.co/shopee-id/tingkatkan-penjualanmu-dengan-shopee-video` and read the event state, date, duration, agenda and host.
- Actual output: the 7 December 2022 webinar was ended. The page offered resend-access-link/sign-in paths for registered participants and linked instructions for replay access, but exposed no public replay or transcript.
- Established: a dated official Seller Education event and agenda existed. Not established: replay content, current Shopee Video UI or policy, attendance, completion, store eligibility, metrics or business outcome.
- Boundary: no registration, resend-link request, sign-in, download, recording, DRM bypass or media reuse was attempted. Retry only if Shopee exposes a normal public no-login replay or transcript; otherwise rotate source.

## F-017 Formal T One window-identity mismatch

- Status: `failed_attempt`; input stopped
- Date/time: 2026-07-19T00:51+08:00
- Actual evidence: five T One-related processes were present; both 8768 and 8818 returned runtime version 2, workspace signature `a9d5c12a8af8716c`, workspace-ready true and two projects. The log recorded `app_ready` at 2026-07-18T16:22:16.222Z.
- Target validation: Windows app metadata and accessibility text reported `实时大盘 · T One` and exposed an Extensions link. The first navigation request was rejected before input pending a fresh window state. The subsequent screenshot showed the Codex task window rather than the reported T One dashboard.
- Established: runtime/process health. Not established: the current T One UI identity, Extensions navigation, Shopee search, unique Skill, expert route, model save/call chain or connector state.
- Boundary: no effective click or text input occurred. Input stopped immediately because automating Codex is prohibited. Retry only with a fresh target handle whose metadata, accessibility and screenshot all agree before any input.

## F-018 Public GitHub API rate limit

- Status: `failed_attempt`; legal fallback succeeded
- Date/time: 2026-07-19T01:00–01:27+08:00
- Actual output: an unauthenticated direct GitHub API request reached a rate limit during the SAIL audit.
- Recovery: continued with normal public GitHub pages in the isolated browser and the read-only GitHub connector. No token, login, retry flood, proxy change, scraping workaround or rate-limit bypass was used.
- Lesson: a rate-limited metadata path is a tooling failure, not evidence about a repository. Record it and rotate to an allowed source surface.

## F-019 Official research organization confused with seller connector

- Status: `failed_attempt` prevented by identity and relevance checks
- Evidence: the Sea Careers → Sea AI Lab → `sail-sg` chain verifies the research organization. Organization searches found Sailor research repositories but no match for the named Shopee/OpenAPI/SDK/OAuth/webhook/MCP/agent terms in the covered pages/search surface.
- Not established: a Shopee Open Platform organization, seller SDK, OAuth, Ads, ERP, MCP, store authorization or T One integration. The bounded non-result also cannot prove global absence.
- Lesson: preserve both directions of the boundary—official identity does not imply ecommerce relevance, and a limited search non-result does not imply nonexistence.

## F-020 README license claim without repository license file

- Status: `failed_attempt`; installation blocked
- Evidence: `sailor2` says Apache 2.0 in README, but a top-level LICENSE fetch returned 404; `sailcraft` also exposed no top-level license. Neither repository exposed a SECURITY.md in the checked surface.
- Lesson: review actual code license, model/upstream terms, data rights and security separately. A README sentence cannot authorize clone/install/commercial use or seller-data routing.

## F-021 Data cleaning and model evaluation failure cases

- Status: `dated_operator_case`; no repository execution
- Evidence: SailCraft issue replies describe legal risk around processed pretraining data and aggressive defaults that heavily reduced a small Chinese corpus. `sailor-llm` closed issues include GPU worker assertions and incomplete HuggingFace downloads followed by missing evaluation fields.
- Lesson: preserve source data, test deletion/language/category bias on a scoped copy, validate artifact integrity and schema before evaluation, and fail closed rather than invent missing fields. These issue cases are not Shopee platform rules.

## F-022 Social-comment coverage absent in the GitHub-focused round

- Status: `unknown`; protocol added, no learning claim
- Evidence: official Sea identity pages had no comment surface. GitHub issue/reply samples were covered, but no Shopee-specific YouTube/social/forum comment source was opened in this round.
- Lesson: do not label the new logged-Chrome comment protocol as completed evidence. Rotate the next safe round to a Shopee professional comment source and record sorts, loaded range, anonymous clusters, official rechecks, counterexamples and filtered noise.
- Follow-up: the next round covered one public Shopee ID video under Top and Newest. YouTube displayed the same two items in both sorts; this resolves the missing-sample task only, not C15 mastery or logged-session coverage.

## F-023 Supported logged-Chrome runtime bootstrap

- Status: `failed_attempt`; legal public fallback succeeded
- Date/time: 2026-07-19T01:42–01:49+08:00
- Actual output: the required browser-client module was present, but supported runtime setup failed twice with `Cannot redefine property: process` before any tab enumeration. The troubleshooting helper was unavailable because the runtime never initialized.
- Boundary: no Chrome tab, cookie, token, password, profile, account data, private content or owner page was read; no system-level browser takeover or alternate identity was attempted.
- Recovery: stopped the logged-session path and opened the already-known public video in a new isolated Playwright session. The fallback was explicitly recorded as anonymous and did not claim logged coverage.
- Lesson: authorization to reuse a session does not make a failed control path successful. Fail closed on identity/runtime ambiguity, preserve the exact error, and separate `failed_attempt` from the public fallback observation.

## F-024 Comment demand signal confused with outcome evidence

- Status: `failed_attempt` prevented by official recheck
- Evidence: a two-item public comment surface contained one question about whether the AI-video practice could make money and one creator clarification request without an answer. Top and Newest returned the same items. Both known ID official pages had unchanged hashes; the AI Terms still provide no sales/page-view guarantee, while the Video guide covers disclosure/safety rather than earnings or commission.
- Lesson: a monetization question is a demand-intent `community_signal`, not sales, commission, eligibility, conversion or profitability evidence. Deduplicate the same comments across sorts and require authorized store/site reports for performance claims.

## F-025 Reddit public browser JavaScript challenge

- Status: `failed_attempt`; normal public reader fallback succeeded partially
- Date/time: 2026-07-19T02:03–02:08+08:00
- Actual output: normal anonymous Playwright navigation to one public r/ShopeePH thread returned HTTP 403 with a JavaScript challenge. No challenge-solving, token reuse, login, proxy change, retry flood or anti-bot bypass was attempted.
- Recovery: stopped the browser path and used the normal public web reader, which exposed the main post, Best/New visible comment ranges and five selected reply branches. It did not expose raw source bytes or a machine comment total, so the record uses `source content hash = unknown` and `at least 50 visible blocks`, never “all comments.”
- Lesson: a legal fallback can add bounded community evidence without converting a blocked browser path into success. Preserve inaccessible regions and never manufacture a raw hash or exact total.

## F-026 SSP, variation misuse and community grouping conflated

- Status: `failed_attempt` prevented by first-party cross-links
- Evidence: PH Seller Education separately documents (1) misuse of product variations, (2) customized-product category guidance, and (3) Shopee Standard Product photo/title matching, exact product review, locked fields and unlink flow. One community thread proposed several incompatible explanations for buyer-facing cross-shop grouping, including AI, Hotlisting, warehouse and dropshipping theories.
- Lesson: SSP is a catalog link, variation misuse is a listing-policy violation, and community grouping complaints are hypotheses. Do not turn any of them into store authorization, fulfillment, review aggregation, AI-ad behavior or a performance result. Verify buyer and seller surfaces independently with the same PH scope.

## F-027 SSP silence treated as no action

- Status: `failed_attempt` prevented by current first-party evidence
- Evidence: the PH Seller Education article documents automatic linking of a notified eligible product after seven days without a decision and automatic application of an SSP profile-renewal proposal after seven days.
- Lesson: represent both as pending deadlines. Obtain item-level owner direction before expiry; inactivity is not authorization.

## F-028 Hot Listing eligibility conflated with causation

- Status: `failed_attempt` corrected
- Evidence: the current PH SSP article documents conditional Hot Listing eligibility for certain linked products. It does not document guaranteed enrollment, buyer-UI grouping, review aggregation, traffic or sales causation.
- Lesson: replace the prior blanket “no official relation” statement with the narrower eligibility fact while preserving all unsupported community mechanisms as `unknown`.

## F-029 Product Category Guide treated as a public live schema

- Status: `blocked_owner_input`
- Evidence: the vehicle-parts article linked to the current Product Category Guide, but the second-level page redirected to Seller Centre login. No credentials, QR login, social login, Main/Sub switch or help action was used.
- Lesson: the public migration rule can be distilled; live category and mandatory-attribute values remain unknown until an authorized PH store session loads them.

## F-030 Under-threshold comments promoted into learning

- Status: `failed_attempt` prevented by the hard gate
- Evidence: one ShopeePH thread exposed fewer than 10 visible comment/reply blocks in each checked sort, and the reader did not prove every accessible item had been reviewed.
- Lesson: classify it `opened_not_reviewed`, exclude it from clusters, and require at least 10 items or proven all-item coverage. Three other independently reviewed threads support only a repeated provenance pain signal, not an official rule or platform mechanism.

## F-031 BR Full treated as a store or account program

- Status: `failed_attempt` prevented by first-party delivery evidence
- Evidence: BR Help describes preparation by the seller or by a Shopee distribution center when delivery is `Full`, then names `Full`, `Rápida` and `Turbo` as express-delivery modes.
- Lesson: route Full on the fulfillment axis for BR only. Public buyer language does not prove seller enrollment, inventory location, eligibility or another country's FBS capability.

## F-032 Made-to-order seller silence treated as harmless

- Status: `failed_attempt` prevented by deadline evidence
- Evidence: after the one-hour buyer cancellation window, the BR seller has 48 hours to accept or reject; no response leads to automatic acceptance and refund processing.
- Lesson: surface the deadline and current order state, then stop for item-level owner direction. Never convert silence into authorization.

## F-033 Buyer refund timing conflated with seller settlement

- Status: `failed_attempt` prevented by the full payment-method table
- Evidence: the BR page is explicitly buyer-facing, conditional on return completion where applicable, and varies by payment method and financial institution.
- Lesson: keep buyer refund and seller payout ledgers separate. Do not promise dates, activate ShopeePay or enter bank information.

## F-034 Community Ads settings promoted to defaults

- Status: `failed_attempt` prevented by official recheck
- Evidence: one BR thread contains conflicting budgets, ROAS values, four/seven-day learning claims and outcomes; current BR terms say paid advertising does not guarantee increased views or sales.
- Lesson: retain budget and conversion pain as `single_case`. Require current authorized Ads UI, campaign inputs and metrics before any setting or conclusion.

## F-035 Unsafe first-sale and creative tactics retained

- Status: `rejected_unsafe`
- Evidence: the community surface included fake-order/review, misleading always-on discount and other-platform AI-image reuse suggestions plus private-contact invitations.
- Lesson: filter these from general practice. Require truthful pricing, authentic transactions/reviews, tenant media rights and platform-specific terms; never contact the commenters.

## F-036 Community SDK coverage claim treated as platform truth

- Status: `failed_attempt` prevented by package and issue audit
- Evidence: one active TypeScript SDK claims complete endpoint/live-sandbox coverage, but its public issue history includes wrong content type, wrong shipping-document fields, wrong HTTP method and download failures. It also defaults to a plaintext JSON token file and shows token-printing examples.
- Lesson: use `extract_rules_only`; reimplement only store namespace, manager separation and structured errors in the existing connector/DPAPI layer. Never install, log tokens, run write tests or promote author claims without targeted official verification.

## F-037 Third-party MCP installer duplicated T One

- Status: `rejected_unsafe`
- Evidence: the PHP package can write `.mcp.json` and a second Shopee Skill, passes partner key/shop/access token through an MCP server, returns token payloads, and declares a binary missing from the pinned commit.
- Lesson: do not install or execute it. Extract only a doc-first API checklist. Preserve the single T One runtime, model gateway, Skill and credential boundary.

## F-038 Legacy wrapper treated as current Open Platform SDK

- Status: `rejected_stale`
- Evidence: the Python package's README says 1.4.0, badge says 1.3.7, last release is 1.3.1 from 2018, and old/v2 client paths coexist while current image/chat/webhook/attribute issues remain open.
- Lesson: keep it as a historical counterexample; current official docs and identity-scoped tests are mandatory before implementing any endpoint.

## F-039 TH pre-order used as a DTS escape hatch

- Status: `rejected_unsafe`
- Evidence: the community thread repeatedly suggested moving ordinary in-stock products to pre-order. The official TH article limits the 7–30-day preparation window to genuine pre-order/made-to-order products and defines separate in-stock DTS.
- Lesson: listing mode follows product truth. Surface current DTS, exception, LSR and cancellation state; any listing change is approval-gated.

## F-040 DTS, LSR and auto-cancel collapsed into one deadline

- Status: `failed_attempt` prevented by the full FAQ/related-page chain
- Evidence: the official TH page distinguishes handover by DTS, late-shipment-rate impact after DTS, two-day no-schedule auto-cancel and three-day scheduled-but-not-handed-over auto-cancel.
- Lesson: store the clocks separately and require current order/carrier evidence. Shipping before auto-cancel can still be late.

## F-041 SIP authorization simplified to one shared permanent token

- Status: `failed_attempt` prevented by guide plus token FAQ
- Evidence: a parent authorization can initially cover current affiliates with limited permissions, but later refresh calls use each parent/affiliate `shop_id` and each resulting token pair is stored separately.
- Lesson: preserve SIP as an account program and route/secret namespace each concrete shop. Never reuse tokens across unrelated stores/sites or silently reauthorize.

## F-042 Unsafe anti-detect scraper candidate

- Status: `rejected_unsafe`; stopped at candidate screen
- Evidence: visible candidate content promoted fingerprint evasion, proxy/account rotation, CAPTCHA and OTP automation, virtual numbers and cookie/profile export.
- Lesson: no deep execution or integration. Never bypass access controls, export owner sessions or use multiple identities to evade platform limits. Continue with official APIs, public compliant pages or authorized fixed identities only.
