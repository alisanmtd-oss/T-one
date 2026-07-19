# eBay expert rules

Read this file before changing a rule, evidence record, tool state, or execution recommendation.

## Evidence-first sequence

1. Resolve the available execution identity: real bound eBay seller/API/browser, official sandbox, or anonymous public browser.
2. Capture external evidence before distillation. Record page/software, URL or version, time, site, marketplace, store mode, ownership, permissions, interactions, input, output, error and boundary.
3. Update the Skill, curriculum, workflow, evaluation or tool map only when the run produced new external evidence. With no new evidence, record a no-increment check and do not invent learning.
4. Keep the captured observation separate from the rule inferred from it.
5. Recheck any expired or conflicting item before a recommendation that could affect a seller account.

## Evidence status vocabulary

Use exactly one of these statuses for every evidence item:

- `verified_live_fact`: directly observed in a bound system or on a current first-party page during this run, with scope and capture time.
- `time_sensitive_evidence`: current first-party evidence likely to change by rollout, marketplace, category, release or policy cycle.
- `historical_operator_trace`: dated evidence of an earlier operation; useful for diagnosis but not current state.
- `draft`: proposed content, mapping, experiment or action that has not been externally verified.
- `failed_attempt`: an attempted software/page/tool action that failed, with error and recovery recorded.
- `unknown`: evidence is absent, conflicting, too weak or outside the observed scope.
- `blocked_owner_input`: progress requires seller consent, OAuth, MFA, identity, bank, budget, product facts, or another owner-controlled input.

Do not use seller anecdotes, mother-document assertions, UI labels, tests or model output as `verified_live_fact` unless the external observation itself supports the exact scoped claim.

## Evidence source tiers

Use one independent `evidence_tier` for source strength while retaining the lifecycle/permission `status` above:

- `official_current`: current first-party platform documentation, policy, release or account evidence, with site/time/boundary.
- `verified_software_observation`: actual T One, browser, API, sandbox or bound software input/output/error observed in this run.
- `multi_source_practice`: a non-official practice corroborated by at least three independent sources; it may become only a scoped experiment, never override official rules.
- `single_case`: one seller, anonymous UI sample, post, video or outcome; keep dated and do not generalize.
- `historical_trace`: an older operation, package acceptance, repository state or superseded rule retained for diagnosis/version history.
- `unknown`: source strength or current applicability is not proven.

Do not promote a `single_case` directly to platform public knowledge. Keep `multi_source_practice` empty when three-source corroboration was not actually performed.

## Required evidence fields

Each material record must have:

- `evidence_id`
- `status`
- `source_kind` and `ownership`
- `url_or_software_version`
- `captured_at`
- `published_or_updated_at` when visible
- `country_site` and `marketplace_id`
- `store_mode`
- `store_binding_id` and `execution_identity_id`, or explicit `none_public_read`
- `permissions`
- `actual_interactions`, `actual_input`, `actual_output`, `errors`
- `boundary`
- `valid_until` or review trigger
- a capture artifact or content/claim hash; if unavailable, mark the hash `unknown` rather than inventing it

## Expiry and conflict handling

- API object relationships and OAuth principles: review every 90 days or on release/deprecation.
- API versions, eligibility lists, UI rollout, ad formats, price-history windows, performance/returns rules and site programs: review every 30 days or before action.
- Bound-store privileges, policies, inventory locations, orders, messages, ad eligibility and finance data: refresh in the current session before action.
- When two official pages conflict, keep both as `time_sensitive_evidence`, block execution of the disputed assumption, and recheck the live account or API.

## Route and connection rules

Require `tenant_id + project_id + store_binding_id + platform=ebay + country_site + marketplace_id + commerce_mode + ownership + execution_identity_id`. Store only `credential_ref`.

`GLOBAL` can group research but cannot execute a seller write. A marketplace list, tool name, developer keyset, browser page, OAuth consent, scope, Store subscription or Seller Hub session grants only its observed domain. Inventory, Account, Marketing, Fulfillment, Analytics, Finances, Media, Messages, Notifications and ERP remain separate capability checks.

## Business-policy and inventory-location rules

- Read `SELLING_POLICY_MANAGEMENT` program state before treating Account API policies as usable listing references. A policy name or ID visible in a document, sample or another store never proves opt-in or ownership.
- Resolve policies by the offer's exact `marketplace_id` and category type. For ordinary inventory require the bound seller's payment, fulfillment and return policy IDs; for `MOTORS_VEHICLES`, follow the current exception instead of inventing an eBay return-policy object.
- A policy edit can update compatible active listings, while listings in restricted revise mode or failing validation may be assigned a clone of the old policy with a new ID. After any approved policy change, re-read policy IDs and listing mappings; do not report universal propagation from the update response alone.
- `merchantLocationKey` is seller-defined, case-sensitive where documented, at most 50 characters in the current guide, and cannot be changed after creation. It is store-scoped configuration, never a tenant-independent product default.
- Distinguish `WAREHOUSE`, `STORE`, and `FULFILLMENT_CENTER` location types and their address/operating-field requirements. An omitted type defaults to `WAREHOUSE` at the API level but does not prove warehouse ownership or that warehouse is operationally correct.
- A new location is enabled by default unless created as `DISABLED`; offer readiness requires an enabled, retrieved location whose facts match the project. Deletion is irreversible in the current guide and is always a confirmed external write.
- Community and code snippets that hard-code category `267`, `USD`, quantity `1`, policy IDs or a merchant key are `single_case` counterexamples. Reuse only the product-independent object relationship after official verification; never copy sample values.

Connection states are separate from evidence statuses and must be one of `research_only / available_unconnected / connected_read_only / connected_write_gated / blocked`.

## Product and category scope rules

- Keep platform-public, category-capability, tenant/project/product and task-evidence layers separate.
- For a new user, require their own tenant/project/product/store route. Product-table and owned-image intake may generate candidate facts, but missing SKU, condition, rights, composition, compliance, price, cost, inventory, capacity, lead time and warehouse remain `unknown` until confirmed.
- Resolve `categoryTreeId` for the marketplace, a leaf category, current Taxonomy aspects and Metadata policies. Capture required/recommended/optional aspects, future-required dates, identifiers, conditions/descriptors, variation rules, listing types, shipping/package limits, compatibility, regulatory and product-safety fields.
- Treat apparel, home, beauty, electronics, food/restricted products, digital goods, collectibles, vehicle parts and machinery as different category schemas. A color/size variation example is not a universal listing model.
- Shared POD logic may contribute only generic IP/media-rights, draft and approval gates outside an explicitly POD-scoped project.
- Do not export private_tenant private product, customer, warehouse, price, inventory, contact or task evidence into open-source or multi-tenant assets.
- Mark any cross-layer inheritance as `scope_leakage`; repair it locally or submit a shared-core patch suggestion without copying the leaked facts.

## Listing, media and AI rules

- Resolve category/aspects/condition/listing structure from current marketplace metadata; use category-tree discovery and leaf-category Taxonomy/Metadata instead of a global or apparel schema.
- Preserve both submitted and saved normalized aspect values. Treat Inventory warning `25127` as a signal that eBay may save a standard value instead of custom input.
- For Apparel and Footwear leaf categories, retain the official Size-standardization version chain instead of flattening it. The early blog says June normalization and July full enforcement; Trading release 1455/error catalog retain July rejection wording; the later Q2 2026 newsletter says July warning `21920466` for recognized values normalized and saved, warning `21920467` for unrecognized values, then August hold/not-visible behavior for non-standard or missing Size with automatic conversion stopping. Use the later newsletter for planning, but refresh current Taxonomy and the bound UI/API response before any write because the official pages still conflict.
- Capture the exact marketplace, leaf category, writer surface, metadata retrieval time, submitted Size, warning codes, saved Size, listing visibility/hold state and readback time. A successful Add/Revise response or warning alone is not proof the listing is buyer-visible.
- Public Community threads report missing truthful presets for odd garment sizes, fractional neck sizes and brand-specific infant ranges. They are anonymous `single_case` signals with no visible official reply, not platform rules. Never choose a nearby false size, force an inaccurate category or claim an INAD/return outcome occurred; block the draft until a truthful current schema/value and interface result are available.
- Fashion Size standardization is category-scoped. Non-fashion products must not inherit a Size aspect, apparel mappings or private_tenant colors/sizes/prices/inventory/warehouse facts.
- Do not select condition, material, brand, size, origin, certification or regulatory facts without evidence.
- Treat category suggestions, Inventory Mapping previews, AI descriptions and AI backgrounds as editable drafts.
- Before requesting or accepting a Listing AI description, resolve the bound marketplace and leaf category, verified Item Specifics, truthful condition/defects, exact included components and media rights. AI cannot fill an unknown product fact.
- Store the raw suggestion and a claim-to-fact diff. Any unsupported condition, defect, component, brand/model, compatibility, provenance or compliance claim blocks acceptance; recover by requesting evidence or replacing the suggestion with a manual factual draft.
- Read back the saved draft after edits and keep publication as a separate confirmed write. Neither the public AI button, generated text, save response nor local test proves a buyer-visible Listing or sales outcome.
- Community complaints about generic copy, repeated hyperbole, missing actual-item detail and factual errors are dated counterexamples only. Do not convert one thread, reaction count or buyer opinion into an AI accuracy rate or universal buyer rule.
- Treat uploaded media as processing until the Media API status/moderation and listing persistence are verified.
- A public “starting soon” announcement does not prove feature rollout to the bound account.
- AI Assistant suggestions always stop at human edit/send.

## Product Research and Sourcing Insights rules

- Resolve the bound seller or delegated Team Access identity before entering Seller Hub. Never share the owner's password; delegated access remains a separate execution identity and permission set.
- Current US public evidence says Product Research is available to sellers with Seller Hub access, while Sourcing Insights requires a Basic-or-above Store subscription. Recheck the actual registration site, account, subscription and mobile/desktop surface instead of treating the US page as global entitlement.
- Capture the original query and platform-echoed query, marketplace, category, condition, product identifiers, buyer/seller locations, listing format, date window and retrieval time. A documented `AND NOT`, minus or `OR` expression is not accepted until the bound UI echoes and applies it.
- Keep the result window and metric definitions visible: the current Help page allows one day to three years, while sell-through is limited to searches of items sold 90 days ago or less. Actual accepted Best Offer prices and calculated metrics remain query-scoped evidence, not a universal price.
- Inspect the newest visible sale date, daily result continuity, sample size and missing-date anomalies before using the output. A June 2026 Community thread reported transient missing days and minus-sign stripping; it is a dated single case without official incident confirmation, so it creates a freshness/query-roundtrip check rather than a platform outage rule.
- Comparing photos, price and item specifics does not grant rights to copy competitor media or text. Product Research may inform a draft or an owner-approved, site-scoped experiment only; it never authorizes a listing, price, inventory or sourcing purchase.

## Seller Standards rules

- Resolve `tenant/project/store_binding`, registration/listing site, buyer delivery destination, seller-standards program and evaluation cycle before interpreting performance. `GLOBAL` can describe a program returned by Analytics, but it is not an executable country site and must not replace the real site/account route.
- On the current eBay.com policy page, evaluation occurs on the 20th of each month. More than 400 transactions in the previous 3 months uses that 3-month period; fewer than 400 uses the last 12 months. Preserve this as US-page evidence and recheck other sites instead of applying it globally.
- For the current US program, cases closed without seller resolution allow 2 cases or 0.3% of transactions, whichever allowance is higher. Transaction defects allow up to 2%, and a Below Standard result from transaction defects requires involvement of more than 4 different buyers. A high late-shipment rate alone does not create Below Standard, although it affects Top Rated eligibility.
- Treat Below Standard as a cross-module eligibility constraint. The public policy says it can lower Best Match placement, reduce selling limits, block Promoted Listings creation/editing, hold funds, prevent certain refund deductions and add higher final value fees from the following month. Before an ad or pricing recommendation, read the bound seller level and projected cycle; a visible campaign button is insufficient.
- Retrieve seller profiles only with the exact seller User token and `https://api.ebay.com/oauth/api_scope/sell.analytics.readonly`. Keep `CURRENT` and `PROJECTED`, program, evaluation date/month, metric numerator/denominator, thresholds and lookback dates separate. The public method supports Sandbox, but T One currently has no authorized eBay seller or sandbox token.
- The public `findSellerStandardsProfiles` sample contains 2016 data. It verifies schema shape, four program/cycle combinations and metric fields only; never use its dates, counts, percentages or levels as current policy or seller state.
- Community Mentor comments are `single_case`, not official support or account evidence. In the reviewed January 2025 thread, the fixed 12-month statement omits the 400-transaction/3-month branch, and an intentional loss-making-sales suggestion has no official support and creates margin/abuse risk. Diagnose the actual dashboard metric and age-off window; do not recommend gaming volume.
- Seller Dashboard access, defect appeal/removal, policy edits, campaign changes, refunds and buyer contact require the bound seller and the existing human gates. A public page, schema, dashboard link or test does not prove recovery or business completion.

## Payment dispute and digital-signature rules

- Read payment-dispute summaries before proposing an action. Preserve the bound seller, order, `paymentDisputeId`, `paymentDisputeStatus`, reason, buyer, retrieval time and `respondByDate`; `ACTION_NEEDED` means seller action is required, not that T One is authorized to act.
- Accepting a payment dispute refunds the buyer and closes the dispute. Contesting must follow `uploadEvidenceFile -> addEvidence -> contestPaymentDispute`; after the dispute is officially contested, `addEvidence` and `updateEvidence` are no longer available. Read `getActivities` for the timestamped audit trail.
- `uploadEvidenceFile` requires the seller User OAuth scope `sell.payment.dispute`, `multipart/form-data`, a form key named `file`, and one encrypted binary `.JPEG`, `.JPG` or `.PNG` per request. Enforce the current 1.5 MB limit, a non-empty filename of at most 255 characters, permitted dispute state and file-count limit. The returned `fileId` is only an uploaded object until it is attached through `addEvidence` or `updateEvidence`. Proof-of-delivery tracking belongs in `createShippingFulfillment`, not this upload.
- Before `addEvidence`, read the current dispute `evidenceRequests`; all files in one evidence set must use the same `evidenceType`. Preserve the returned `evidenceId` for later `updateEvidence` or `fetchEvidenceContent`. Before `contestPaymentDispute`, attach all evidence, use the current required `revision`, and include `returnAddress` when the seller expects the buyer to return the item.
- For sellers domiciled in the EU or UK, the current official signature guide requires digital signatures for all Finances API methods, Fulfillment `issueRefund`, Trading `GetAccount`, and the listed Post-Order refund/return/cancellation methods. Require `x-ebay-signature-key`, `Signature` and `Signature-Input`. `Content-Digest` is not required for a no-payload GET; it is required for a payload and uses SHA-256 over its UTF-8 bytes. Correct documented 215000-series header/digest/timestamp/JWE/application-key/signature failures; do not bypass a signature-required 403.
- eBay Key Management creates the private key, public key and public key as JWE, but eBay does not retain the private key. Store only a protected credential reference, never the private key in a task/evidence record. If lost, generate a new keypair. Sandbox verification must use a sandbox seller domiciled in an applicable EU/UK country such as DE or GB.
- Keep `eBay/digital-signature-java-sdk` as `research_only` until the shared GitHub capability registry admits it and dependency/license/security/data-boundary review passes. Public ownership, Apache-2.0 and recent maintenance do not equal runtime admission or security proof.
- The eBay organization identity is accepted only because a first-party Developer guide linked into it. Deduplicate official repositories by `owner/repo + commit/tag`. The current `eBay/npm-public-api-mcp` candidate remains uninstalled and `research_only`: its README says Production GET-only and Sandbox unsupported, while source constants expose Sandbox methods, so the Sandbox claim remains conflicting/unknown. The source defaults an absent or invalid `EBAY_API_ENV` to production and caches access tokens in memory. T One must require an explicit environment/store binding, use its existing DPAPI credential-reference layer, reject credential hardcoding even when a README troubleshooting section suggests it, and preserve application/User-token scope isolation. Any future admitted reuse must merge into the existing connector layer, not create a second Agent, model gateway or credential store.

## Knowledge-package reuse rules

- Before adding platform knowledge, inventory the existing unique Skill, rules, contract, templates, evaluations, failures, connector truth and GitHub admissions. Search the identified gap with English platform terms plus `skill`, `playbook`, `SOP`, `checklist`, `schema`, `evaluation`, `SDK`, `MCP`, `ERP`, `OMS`, `PIM` and `WMS`; do not recreate an already covered module.
- Audit each package at `owner/repo + commit/tag`. Record provenance, license, maintenance, releases, issues, PRs, security/advisories, credentials/telemetry, dependencies, deployment cost, tests, T One overlap and `platform + country/site + store_mode + ownership`. Sample one core flow, one failure/authorization boundary and three claims. Use only `keep_reuse`, `merge_into_existing`, `extract_rules_only`, `research_only`, `rejected_stale`, `rejected_license` or `rejected_unsafe`.
- Keep `nexscope-ai/eCommerce-Skills` only as the shared registry's community taxonomy reference. The audited eBay guide, advertising and tools files are small Beta outlines without citations, site/store scope, failure recovery or evaluations. Do not install them or create a second eBay Skill.
- `YosefHayim/ebay-mcp` is unofficial and unadmitted. Its read-only classifier, tool-family allowlist and error-surfacing tests are useful rule patterns, but T One must default-deny writes, bind every allowed family to tenant/project/store/marketplace/execution identity, keep DPAPI credential references authoritative and redact errors. Never adopt its default `all` tool exposure, unset-read-only behavior, `.env` token ownership, client-config writes, OAuth setup or separate MCP runtime.
- Reject `adbertram/cli-tools` eBay execution. Its no-`--publish` pseudo-draft is an actual publish-at-$99,999 followed by listing termination, not a draft. Official Inventory API state remains `inventory item -> unpublished offer -> separately authorized publishOffer -> active listing`; a created offer is not buyer-visible.
- Package discovery, README text, source inspection, tests or a public repository do not authorize clone/install/run, OAuth, token entry, client-config mutation or seller calls. Merge only reviewed rule deltas into the existing T One Skill/connector contract.

## External action gates

Explicit owner confirmation and the bound execution identity are required for publish/withdraw, price/quantity, policy/location, discounts, campaign/ad changes, offers to buyers, email campaigns, Messages, feedback, shipment, returns, refunds, payment disputes, payment, or external contact.

Always reject CAPTCHA/MFA/verification/rate-limit bypass, anti-association evasion, cross-store credential reuse, private-data scraping, unauthorized image/video/review/buyer-photo reuse, invented facts, and a second general-purpose model/agent runtime.

> Private runtime paths, evidence, execution identities, and product records are intentionally excluded from this public pack.
