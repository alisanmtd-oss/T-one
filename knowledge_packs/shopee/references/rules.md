# Shopee expert rules

## Stable routing invariants

1. Execute only on SG/MY/TH/VN/PH/ID/TW/BR; never on a regional group.
2. Persist `platform + country_site + store_model + seller_origin + account_program + fulfillment_mode + ownership + store_binding_id + execution_identity_id`.
3. SIP and Direct are account programs. FBS is fulfillment. Local/cross-border is seller origin/context.
   `global_store` is also an account-program label, not a country or fulfillment mode; its downstream country scope must come from current official or authorized account evidence.
4. Seller Centre, Open Platform, Ads, affiliate/live, ERP, logistics, and report imports have separate identities and permissions.
5. A tool name, page, button, class, test, draft, or approval is not a live connection or business outcome.
6. `official_full_managed` is recognition-only and blocked from execution.

## PH Standard Product and variation boundaries

PH SSP is a product/catalog link. It does not merge store authorization, inventory, fulfillment, Ads identity or execution identity. A photo/title candidate needs exact attribute and variation review. A notified eligible product can be auto-linked after seven days without a decision, and an SSP profile-renewal proposal can be auto-applied after seven days. Treat both as pending deadlines requiring item-level owner direction, not harmless inaction.

Before `Link and Modify`, review highlighted specification differences; other fields are not documented as automatically changed. Linked variations are uneditable, and at least one prefilled variation must remain. `Standard Product Possible` denotes a potential/similar match. Linking locks or controls documented Category, key attributes and variation type; unlinking uses the current reason flow and may accept optional evidence. Every Link, Don't Link, Link and Modify, Confirm, Change, Unlink, Feedback, Linking Test, Update, No Update Needed, Adopt, evidence upload and Publish remains approval-gated.

SSP-linked products may meet documented Hot Listing eligibility conditions, but eligibility is neither enrollment nor buyer-UI, traffic, review, sales or causation evidence. A review target of 24 hours is not guaranteed unlink approval or business completion.

Keep SSP separate from misuse of product variations. PH first-party guidance prohibits unrelated add-ons, other product types and names that falsely imply every variation has the same type, quantity or quality. Use a separate listing, genuine bundle or accurate shared name as the exact product facts permit. A dated Custom Product L1-L5 table guides discovery but never replaces the current PH category schema.

Three independently reviewed ShopeePH threads support only a repeated `multi_source_practice` pain signal around exact shop/listing/review provenance. Because the qualifying sources share one platform and subreddit, they may prioritize an authorized PH UI audit but cannot define SSP or Hot Listing causation, buyer-interface mechanics, store permissions, review aggregation, shipping or performance. A thread with fewer than 10 visible items and no proven all-item coverage remains `opened_not_reviewed` and is excluded.

## BR fulfillment, order and Ads boundaries

BR `Full` is documented as distribution-center preparation and express delivery alongside seller preparation. Classify it as a fulfillment/delivery mode only. `Rápida` and `Turbo` are BR express-delivery labels. None proves current store enrollment, eligibility, inventory location, service level or another country's FBS support.

For in-stock products, the public buyer page documents post-payment cancellation until ready for collection; ready-to-ship or in-transit recovery uses package refusal. For made-to-order products, the buyer has one hour after payment without seller approval; afterward the seller has 48 hours to accept or reject and silence auto-accepts. Treat every cancel, accept, reject, refuse, return or refund as a current-order, item-level approval action. Silence is consequential.

The BR refund table is buyer-facing. It is conditional on return completion where applicable and payment method/institution state. Keep it separate from seller payout/settlement; never promise a completion date, activate ShopeePay or enter bank data.

One BR new-seller community thread passes the comment-coverage gate but remains `single_case`. Its recommended budgets, fixed ROAS, four/seven-day learning, Ads-visibility, flash-sale, coupon and affiliate claims are hypotheses. Official BR terms do not guarantee views or sales. Reject fake orders/reviews, misleading always-on discount framing, private contact and reuse of other-platform media without verified rights.

## TH DTS and package-preparation boundaries

The current TH Seller Education rule effective 2025-09-01 maps in-stock payment by 12:00 to same-day carrier handover and payment after 12:00 to next-day handover, excluding Sundays and public holidays. Genuine pre-order or made-to-order products may use 7–30 days; Standard Delivery Bulky remains one day. Never misclassify in-stock products as pre-order to evade DTS.

Keep three clocks separate: current DTS; LSR when handover is after DTS; and the documented auto-cancel boundaries of two days without pickup scheduling or three days when scheduled but not handed to the carrier. A carrier-fault exclusion and any festival/event adjustment require current order/announcement evidence. The new/small seller exception is a live system-calculated state based on account age not over 90 days or average at most one order over the preceding 90 days; community capacity complaints do not establish it.

The older TH order-management page supplies the 30-day package-preparation average and nonworking-day/carrier-pickup exclusions only. Its embedded video was not played and is `opened_not_reviewed`; current deadlines come from the newer policy.

## Open Platform authorization and package boundary

Non-public APIs need an approved profile/app category, current seller authorization and exact identity. Validate the redirect domain and unpredictable `state`. Keep shop, merchant, user and supplier scopes separate; sign with the documented identity-specific HMAC-SHA256 base string. Documentation, generated URLs, sandbox tests, app-category labels and API wrappers do not prove connection or production parity.

Never put Partner Key, authorization code, access token or refresh token in task payloads, logs, plaintext JSON, agent responses or MCP tool results. Use the existing T One credential reference and encrypted secret store. Apply current lifecycle checks and clear errors rather than blind retry: five-minute link signature, one-time ten-minute code, four-hour access token, 30-day refresh token and at most 365-day authorization at the captured version.

A SIP parent authorization can initially cover current affiliates with limited permissions. Each later refresh uses the exact parent/affiliate `shop_id`, and each resulting pair is stored separately. This does not turn SIP into a permanent shared credential or executable region.

Community SDKs are not platform facts. `congminh1254/shopee-sdk` and `EcomPHP/shopee-php` are `extract_rules_only`; plaintext token storage, token-returning MCP tools, duplicate `.mcp.json`/Skill generation, missing declared files and destructive sandbox tests are rejected. `JimCurryWang/python-shopee` is `rejected_stale`. Any English search result, including `easycb/easycb-go`, remains `candidate_screened` until the full license/security/credentials/tests/scope audit is complete.

## Four scope layers

1. Platform public: Shopee/site/program/general operations only. No customer product facts.
2. Category capability: the dynamic category schema, variation, compliance, logistics and advertising constraints are read for the exact site/category. Clothing knowledge cannot stand for beauty, electronics, food/restricted goods, home, digital products or machinery.
3. Tenant/project/product: facts and media remain under the matching tenant, project, product and store binding.
4. Task evidence: one listing, Ads, order, buyer, shipment, settlement, media or failure trace never becomes a default for another task.


## Knowledge status rules

| Status | Use | Promotion rule |
|---|---|---|
| `verified_live_fact` | Current store-scoped result or capability with execution evidence. | Requires site, store, ownership, permission, capture time, and outcome evidence. |
| `time_sensitive_evidence` | Current official policy/help/developer evidence whose applicability may change. | Recheck at expiry or before a write. |
| `historical_operator_trace` | Prior operator action/result. | Never current until independently reverified. |
| `draft` | Proposed copy, mapping, scenario, or action package. | Needs validation and, for writes, owner approval plus execution evidence. |
| `failed_attempt` | A source/tool/test/authorization attempt that did not establish a result. | Retry only after reading the failure review and changing the condition. |
| `unknown` | Evidence is absent or conflicting. | Do not guess; collect the named evidence. |
| `blocked_owner_input` | Owner authorization, identity, money, MFA, bank, tax, or store input is required. | Only the owner can unblock it. |

## Evidence levels

Evidence level and knowledge status are separate axes. Use exactly one level: `official_current`, `verified_software_observation`, `multi_source_practice`, `single_case`, `historical_trace`, or `unknown`.

- `official_current` requires a current first-party URL and capture/fingerprint metadata, but never proves a store is enabled.
- `verified_software_observation` requires actually opening and interacting with the scoped software/page and recording input, output, error and permission boundary; it still does not prove a business outcome.
- `multi_source_practice` requires three independent non-official sources with no official conflict. One seller or creator story remains `single_case`.
- `historical_trace` preserves a prior result without claiming it is current. Use `unknown` when evidence is absent, conflicting, login-blocked or site-unspecific.

## Evidence precedence and conflicts

Current site-specific official policy outranks generic official marketing copy; current authorized store evidence outranks a generic capability claim for store availability; neither converts a time-sensitive rule into a permanent rule. Third-party documentation and seller experience may only form testable hypotheses. When sources conflict, retain both records, mark the decision `unknown` or `needs_review`, and identify the owner/source required to resolve it.

## Time-sensitive rules

Fees, taxes, eligibility, campaign windows, stacking order, ad products, budgets, logistics SLAs, return windows, category restrictions, dynamic attributes, and API scopes must be refreshed for the exact site/store before a write. Never copy one site's rule to another.

## Action boundary

Research, audits, imports, drafts, and simulations are allowed. Publishing, price/inventory changes, promotions, ad spend, affiliate invitations, shipments, refunds, messages, payments, settlement changes, or authorizations require explicit item-level confirmation. Block CAPTCHA/MFA/anti-bot bypass, linkage evasion, cross-store authorization, private-data harvesting, unauthorized media reuse, and invented facts.

For TW AI Store Customer Service, keep the FAQ-card surface separate from the AI answer source: seller-defined FAQ cards do not ground AI replies. Treat feature enable/close, pause/intervention and buyer replies as external store actions. A public feature page or login redirect cannot establish store eligibility, enabled state, generated replies, chat records or performance metrics.

For VN AI Product Content Suggestions, image-driven title/category/description/attribute/variation output is a suggestion. The seller must check and edit it; gradual rollout is not store eligibility evidence, and `Save & Display` is a separate approval-gated listing publication.

For TH AI, the current official terms establish governance, not a specific enabled tool. Shopee may auto-enable a feature for relevant users and permits opt-out through Seller Center, but the current store state, menu and effect remain unknown without authorized observation. Do not enter sensitive personal, login, password, PIN or financial information; independently verify output; require rights and an AI-generated label for third-party AIGC submitted to Shopee. Do not promise sales or traffic gains. Changing the feature state or publishing content remains approval-gated.

For ID Shopee Video, the current public guide documents an `AI-generated content` control on the Posting screen and a creator-applied label after publication. This is an instruction-page observation, not proof that a current account or app version exposes the control. Before any draft can advance, verify ownership/licensing and consent, disclose fully AI-generated or significantly AI-edited media, and preserve the underlying Community Guidelines. A label does not make misleading content, rights/privacy infringement, unconsented impersonation/deepfakes, depictions of minors, or illegal/harmful material permissible. `Posting` is an external write. A creator video's app-update recovery suggestion remains `single_case` until current official support or an authorized account observation verifies it.

A Help search returning no results does not invalidate a directly reachable official page. A commercial industry article is `single_case`; its commission, penalty, detection or cross-site claims cannot become a rule until the exact country has current official evidence.

## Official GitHub admission boundary

Verify an official organization from a first-party website/developer link; a same-name account is `unknown`. Record the reverse link, capture time and coverage. Search results are bounded by the organization, query terms, pages and capture time, so “no match” never proves global absence.

Audit repository identity at `owner/repo + commit/tag`. README claims, code LICENSE, model-weight/upstream terms, dataset rights, dependencies, security policy/advisories, data destination, GPU/cost and maintenance are separate gates. A repository is not installed, connected or useful to seller operations because it is official, active or popular.

The verified `sail-sg` organization belongs to Sea AI Lab. `sailor2`, `sailcraft` and `sailor-llm` remain multilingual-model/data research candidates only; they must not create another gateway or receive seller data without a separate review. `envpool` and `zero-bubble-pipeline-parallelism` are official research repositories but have no direct Shopee seller-operation or connector fit. None proves a Shopee Open Platform, OAuth, Ads, ERP, MCP or store connection.

## Comment evidence boundary

Record pinned/high-vote, latest, author/official replies, nested replies, disputes, actual loaded range and available sorts. Cluster anonymous themes and separate `official_reply`, `dated_operator_case`, `community_signal`, conflict, sentiment and filtered spam/affiliate/bot/synthetic repetition. Likes and frequency affect research priority, not truth. Any policy, fee, API or feature claim returns to current site-specific official evidence before promotion.

A public question such as whether AI video can make money is a monetization-intent signal, not earnings, commission, eligibility or conversion evidence. A creator's request for clarification is still not an answer. Deduplicate the same items across Top/Newest sorts, preserve the capture-time displayed range, and require authorized site/store performance reports before any outcome conclusion.

Do not retain usernames, avatars, contacts or private content. Logged Chrome learning is read-only and cannot copy cookies/tokens, change identity/network, like, follow, subscribe, save, comment, join or submit. A GitHub issue or maintainer reply can explain a dated project failure; it cannot become a Shopee platform rule.

> Private runtime paths, evidence, execution identities, and product records are intentionally excluded from this public pack.
