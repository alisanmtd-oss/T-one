# Etsy official rules

Verified: 2026-07-19 (Asia/Shanghai). Latest public-browser capture: 2026-07-19T02:39:10+08:00. Scope: Etsy `GLOBAL` marketplace route; seller-country, bank-country, ship-from, buyer destination, item type, and trader status can narrow applicability. Recheck changeable rules before execution.

## Contents

1. Shop and API identity
2. Creativity, POD, AI, images, and IP
3. Listing and search
4. Fees, Etsy Ads, and Offsite Ads
5. Orders, fulfillment, service, and returns
6. Native AI
7. Source register

## 1. Shop and API identity

- Model Etsy as one `GLOBAL` marketplace route per real shop, not one global authorization. Bind every authenticated task to `store_binding_id + shop_id + execution_identity_id + credential_ref`.
- New shops require Etsy Payments availability in the shop's bank country. The eligible-country list is time-sensitive. Etsy currently states that new shops cannot open in China; only already-open China shops can use Etsy Payments.
- Every Open API v3 request needs an approved app API key. Scoped private or write endpoints additionally need shop/user OAuth 2.0. Listing management uses `listings_r`/`listings_w`; deleting additionally uses `listings_d`.
- Etsy personal API access currently supports up to five shops. A general-purpose application serving other sellers requires commercial access. Etsy states commercial applications must not sidestep the API with screen scraping.
- Do not equate API app registration, placeholder environment variables, or a configured key with a verified shop authorization.

## 2. Creativity, POD, AI, images, and IP

- Classify goods from verified seller contribution as Made by, Designed by, Handpicked by, or Sourced by. Digital delivery, POD and buyer personalization do not replace the applicable class. A category name, competitor Listing or historical UI label is not eligibility evidence.
- Made includes genuine handcraft, specialized craft alteration, unique end-product assembly, and seller-owned computerized production from the seller's original design. Manufacturer-instruction assembly and superficial alteration do not qualify; made-by Listings require original media of the real final product when the current policy requires it.
- A sourced craft supply must primarily enable the buyer to create something new by hand. Category examples are non-exhaustive. A qualifying blank has no independent ready-to-use market; plain ready-to-use T-shirts, tumblers, phone cases and canvas bags do not qualify merely because they can be decorated.
- A sourced party supply must be specifically designed for a celebratory gathering. Plain or generic tableware, furniture, lighting, equipment, costumes, seasonal decor, favors and toys do not qualify merely because a buyer could use them at an event.
- A handpicked vintage item must be personally curated and at least 20 years old. Preserve source, age method, designer/collection, materials, marks and photos. Inheritance timing, a competitor Listing or estate/yard-sale provenance is not sufficient by itself, and a commercial remake under 20 years old is not vintage.
- Drop delivery and resale are generally prohibited outside the documented handpicked/sourced exceptions. Adding only a card, tag or note to an unaltered commercial item does not transform it.
- A seller's original design may be produced or printed by a qualifying production partner. A buyer-personalized item may also use a production partner within the current sourced-by-seller rules.
- Disclose production assistance on applicable listings, describe the relationship, and use the actual dispatch location. POD printers can qualify; white-label manufacturers, OEM/ODM businesses, retailers, and wholesalers do not become qualifying production partners merely because they fulfill orders.
- Ready-to-use blank shirts and generic mass-produced goods cannot be resold as handmade. A superficial mass-produced adornment does not automatically make an item made by the seller.
- Seller-prompted AI creations are currently allowed within designed-by-seller, but Etsy requires AI use to be disclosed in the listing description. AI prompt bundles are not allowed under the current Creativity Standards.
- Image rules vary: made-by-seller and uniquely manufactured products generally need real finished-product photos; an original design printed on a base item by a production partner may use a stock mockup; a personalized item's first image must show a finished personalized example, not a blank or placeholder mockup.
- Sellers are responsible for necessary rights. Etsy processes compliant infringement reports but does not give legal advice or make the seller's legal determination. T One IP review is a risk gate, not legal clearance.
- Item eligibility starts with the current What Can I Sell and Prohibited Items rules. Counterfeit goods and prohibited medical/drug claims remain blocked; never rewrite a claim merely to evade review.
- Preserve policy versions by effective date. On the 2026-07-18 capture, the current Prohibited Items Policy remains the live version until 2026-08-11, while a separately published future version becomes effective on 2026-08-11. Do not apply the future fur-related change early.
- Public removal guidance does not prove a bound shop's violation or appeal entitlement. Read the exact `Policy violations` reason and evidence state; appeal rollout may show `Not available` or `View & Appeal`. Appeal, relist and every enforcement-related submission require owner confirmation, and no relisting may circumvent enforcement.

## 3. Listing and search

- Etsy's current Listing form includes photo/video, category, item details, item options, pricing/shipping, how it is made, and settings. The Help article updated 2026-07-17 documents up to two Listing videos, each at most 100 MB and 3–15 seconds; treat limits as refresh-required.
- Current Help lists MP4, MOV, FLV, AAC, AVI, 3GP and MPEG, a 500 px minimum with 1080 px or higher preferred, and aspect ratios from 2:1 through 1:2. Etsy removes audio after upload, so product-critical information must not depend on sound alone.
- The 2020 smartphone guide's singular-video and 5-second-minimum wording is historical and does not override current Help. Its background, lighting, stabilization, focus and framing guidance remains usable when it matches the current product and rights evidence.
- Use video to show verified scale, materials, variations, use, making process or relevant wear/flaws only when accurate for the category. Do not reuse another tenant's media, competitor footage, creator content or music without documented rights.
- A Listing video may be a testable search or buyer-information hypothesis, but the public can-help-search wording and older buyer research do not guarantee ranking, conversion or sales. Actual upload/delete, desktop/app parity, buyer-device visibility and outcome require the bound shop, approval and readback.
- Current Open API personalization uses dedicated get/update/delete endpoints and a `personalization_questions` structure. Legacy personalization fields are deprecated and should not be sent on Listing create/update requests.
- Etsy's official announcement set 2026-05-11 as GA for multiple typed questions. The current guide supports up to five questions across text, dropdown and file-upload types. Personalization POST fully replaces existing data; read first, preserve question identity, stop on conflicts, and require post-write readback.
- Send `supports_multiple_personalization_questions=true` only after the integration can consume and preserve every current question type. The official schema warns that adding the flag to an unmigrated application can delete seller-entered data.
- Transaction personalization remains in the transaction `variations` array. Do not assume the display name is always “Personalization” or that only one `property_id: 54` entry exists.
- The current third-variation tutorial is renderable and documents preview read/write compatibility, product limits and deletion risk. It still does not prove general availability, an eligible shop, a T One connector or a successful response. Do not release preview behavior to production without Etsy's GA notice and authenticated evidence.
- From 2026-07-29, Etsy says the `Shipping` and `Inventory` includes on Listing reads will return 400; migrate to `getListingsShippingByListingIds` and `getListingsInventoryByListingIds` and keep date-pinned adapter tests.
- Seller API Access is for an eligible individual seller's own shop. It is not a commercial cross-shop authorization; app tier, shop binding, owner OAuth and execution identity remain per store.
- Etsy's hosted OpenAPI Dev MCP supplies documentation/schema/guide lookup and explicitly does not call Etsy APIs. Keep it research-only until T One registration and security/data review; it is not OAuth, a shop connector or execution evidence.
- Third-party Etsy clients are not connection or policy evidence. Two current audited candidates have unresolved repository licenses and are rejected; the Apache-2.0 Kotlin client contributes only a generation-preflight idea. No candidate was cloned, installed, executed or copied into T One.
- Pin and hash the exact official OpenAPI specification before generation. The 2026-07-19 pinned `3.0.0` document hash is `f1ef521ae668f147e9e9ab298047922708d6b20a62b5794ceaa0f555938da4ae`; it currently has scalar `null` defaults on the `includes` arrays for `GET /v3/application/shops/{shop_id}/listings`, `GET /v3/application/listings/{listing_id}`, and `GET /v3/application/listings/batch`. Record any transform exactly and fixture-test request encoding, auth and errors; do not skip spec validation or generated tests.
- Every v3 request requires `x-api-key: keystring:shared_secret`; shop-scoped operations additionally require the bound OAuth bearer. Package defaults such as 5 QPS/5000 QPD do not prove an app's quota; use the authenticated Developer Portal and current response headers, honor `429 retry-after`, and keep the connector blocked without approved app/shop credentials.
- Use up to 13 accurate tags. Each tag currently allows up to 20 characters. Prefer distinct buyer-intent phrases over repeated keyword fragments. The current tag Help also limits characters and documents desktop and Seller app edit paths; those public steps do not prove a bound-shop edit or outcome.
- Choose the most specific truthful category. Categories and attributes can act like tags for query matching, so do not spend a standalone tag repeating an exact category or attribute phrase. Fill relevant truthful attributes before using tags for accurate buyer terms the controlled attribute set cannot express.
- Category selection determines the available attributes. If an exact value is absent, choose the closest truthful available option and preserve the specific term in title, description or an accurate tag when useful. Never invent an Etsy attribute, copy an unrelated category's property, or carry a product value across tenants or shops.
- Keep primary titles and tags in the shop language; use seller-provided translation fields for other languages. Do not deliberately misspell or waste tags on simple plural variants. Regional phrases remain market-scoped hypotheses and require verified buyer-market evidence.
- Sustainability attributes are claim-bearing product facts. Use only a current category-exposed control backed by project evidence such as receipts or certifications, avoid unsupported broad environmental claims, and retain the evidence packet. Publishing an attribute change remains owner-confirmed.
- The current Create-a-Listing Help page updated 2026-07-18 says two videos of 5-15 seconds, while the dedicated Listing-video Help updated 2026-07-17 says up to two videos of 3-15 seconds. Preserve the official conflict, use the dedicated technical Help for draft preflight, and require an authorized editor readback before claiming live acceptance or error behavior.
- Etsy's April 27, 2026 title guidance says to identify the item clearly, lead with important objective traits, keep titles scannable, consider fewer than 15 words, avoid repetition, and move nonessential gifting/aspirational phrases to tags or descriptions.
- Search is holistic: title, tags, attributes, descriptions, first photo, reviews, conversion/customer-service signals, and other factors can contribute. Do not claim a deterministic ranking formula.
- Etsy's title-suggestion tool is optional and conditional on eligible English shops/Listings. Public paths include Search Visibility, existing Listing edit, possible new Listing and Etsy Seller app; `Update titles` leads to review, edit and approval.
- The title-specific guide names current title, first photo and description as inputs, while the later AI overview additionally names tags, attributes and reviews. Preserve this dated source difference; actual current inputs remain unknown without an eligible authenticated observation.
- The official OpenAPI 3.0.0 document defines `getListing?allow_suggested_title=true` and a nullable `suggested_title` response. It is restricted to the Listing owner through owner-scoped OAuth; the shop language must be English and not every Listing receives a suggestion. This documents a read schema only. No T One call, response or write path is connected.
- The seller may accept, customize, edit, refine, dismiss or start from scratch and can work on one or many Listings. Before updating, download a Listing CSV and retain an exact snapshot/revert path. Suggestions do not prove the current title underperforms.
- Attribute suggestions are described as using entered category, description and featured image. Verify every suggestion against product facts; public documentation does not show the current accept/edit/reject controls for a real shop.
- Search Visibility insights typically clear within 24 hours after improvements and changes can take up to a day to reflect. Evaluate experiments against authorized Stats, not immediate or personalized self-search.
- Marketplace Insights is a conditional Shop Manager research tool on desktop and mobile web. Current Help documents a 30-day search/Listing-count window, 15 free keyword searches per week with seven-day result retention, and unlimited searches for Etsy Plus; actual availability, quota, locale and result remain shop-scoped evidence.
- Marketplace Insights does not update Listings. Treat its search and Listing counts as dated hypothesis inputs, not sales, conversion, profit, ranking or causality. A surfaced term is not Seller Policy or IP permission.
- Seller Trend Reports are dated directional evidence, not a universal product or keyword brief. Preserve publication date, data-as-of cutoff, comparison window, geography/population, normalization or metric definition, category, seasonal frame and refresh/expiry state with every extracted trend.
- The Spring and Summer 2026 report was published 2026-03-17 with data as of 2026-02-10. Unless otherwise noted, it compares the prior three months with the same period one year earlier using normalized signed-in U.S. search activity; age-generation insights use a U.S. active-buyer age-signal subset, and the seasonal frame is Northern Hemisphere.
- Do not turn trend percentages into absolute volume, global demand, shop demand, sales, profit or ranking claims. Validate authentic product fit, rights, taxonomy, capacity and margin, then check the bound Marketplace Insights or authorized Stats. Listing, inventory, promotion and Ads actions remain separately approved.

## 4. Fees, Etsy Ads, and Offsite Ads

- Current base fees include USD 0.20 per Listing, a four-month Listing period, and a 6.5% transaction fee on the order total including charged shipping and gift wrapping. Payment processing varies by country. Currency conversion and regulatory fees can apply. Always load the actual shop Payment account before a live margin decision.
- Payment account finance is a state machine: sale/receipt, ledger entry, payment record, current balance, Available for deposit, scheduled deposit, sent deposit and bank receipt are not interchangeable. A positive current balance does not prove funds are available, sent or settled.
- Ads click charges, Payment account line items, current balance, month-end negative balance, Amount due, conditional autobilling/card charge and bank receipt are also distinct. Paid clicks can create fees without sales; sales funds can offset fees, and a negative month-end balance can become Amount due.
- Before labeling an Ads charge incorrect or fraudulent, align the same shop, date range, clicks, display/Payment-account currencies, taxes and fee type, Offsite-versus-onsite surface, Payment account entries, current balance and Amount due. Do not promote a community currency explanation or promise a credit without live evidence.
- Available for deposit reflects available sales funds after fees, refunds, taxes and reserve effects. Deposit schedules govern when available funds are sent; country/currency minimums, fees, security holds, Payoneer routing and bank processing can affect later stages.
- Payment account reserve percentage and default holding period are shop-specific. For physical orders, early release requires Etsy to confirm valid tracking is in transit; merely adding a tracking number does not prove release.
- Monthly statement CSV supports Payment account reconciliation, but deposit amount is not Net profit and neither a CSV nor an Open API ledger proves bank receipt.
- Deposit-schedule changes, `Request it now` and conditional instant transfers are payment actions. Recheck live eligibility, amount, fee, destination and limits and obtain owner confirmation before any action.
- Etsy Ads are onsite CPC ads run through Shop Manager with a daily budget and auction-based placement. Listing quality/relevance and Etsy-managed bids affect delivery. Ads use designated ad spaces and a different process from organic search.
- Etsy Ads reporting keeps views, clicks, click rate, attributed orders, attributed revenue, spend, average CPC, ROAS and search terms separate. A paid ad click is not the same as a Shop Stats visit, and low-traffic search terms may be withheld for privacy rather than equal zero.
- Orders and revenue may be attributed when a shopper interacts with an Etsy Ad and buys any item in the shop within 30 days; the clicked and ordered Listings or dates can differ. This is platform attribution, not proof of incremental causality.
- Average CPC uses same-scope spend divided by ad interactions. ROAS uses ad-attributed revenue divided by Ads spend and is not net profit; load product costs, shipping, discounts, fees, refunds, taxes and other attributable costs before a profitability claim.
- The daily budget is a maximum, not guaranteed spend, delivery or orders. Actual click costs are normally posted to Payment account the next day. Keep report date range plus budget, strategy and advertised-Listing changes, and use at least the current recommended 30-day context before trend-based adjustments.
- Offsite Ads are Etsy-managed external ads. Current rules attribute qualifying orders within 30 days of a click. Shops always below USD 10,000 in any consecutive 365-day period are currently charged 15% and may opt out; shops that reach at least USD 10,000 are currently charged 12% and participation becomes mandatory. The current fee cap is USD 100 per order.
- Offsite Ads do not offer seller listing selection or a daily budget. A single click may attribute multiple orders within the window. If the buyer's final click is through an Etsy Ad, current guidance says only the Etsy Ads fee applies. Use the actual Offsite Ads dashboard, order and Payment account to resolve revenue, fees, clicks, traffic, search terms and Listing performance.
- Keep sales/coupons, targeted offers, Etsy Ads, and Offsite Ads separate in authorization, margin, and approval records.
- Sales can be scoped and scheduled in Shop Manager, but overlapping promotions and discount eligibility must be read from the actual shop before activation. Draft separate promotion objects, calculate margin under each applicable combination, and require owner approval.

## 5. Orders, fulfillment, service, and returns

- Physical Listings require accurate processing and delivery inputs. Processing profiles can be set at Listing or variation level; ship-by dates are commitments.
- Sellers remain responsible for delivery when a third party fulfills. Match production-partner capacity, dispatch location, processing profile, transit, carrier, and tracking to the offer.
- Do not act on an order marked payment processing or not paid. Etsy says review can take up to 72 hours or longer; wait for payment confirmation.
- Refund and cancellation are distinct: a refund does not automatically cancel the order, while seller cancellation is a full-refund transition. Cancellation can take up to 48 hours to process and buyer receipt can take 3 to 5 days, so neither submission nor an order-page change proves the buyer has funds.
- Etsy Payments refunds are available only after payment processing and before 180 days. An unavailable refund control, elapsed window or chargeback must not be bypassed; any outside refund is a separate payment action and Etsy says it does not recover seller fees.
- Refund funding comes from the Payment account and a shortfall can charge the card on file. The seller cannot choose the buyer's refund destination. Show the exact live effect and require approval before submission.
- Coordinate a return's destination, timeframe and shipping-cost responsibility, then wait for the item or applicable proof before refunding. Return labels and buyer messages are separate external actions; Etsy refunds cannot exceed the original order amount.
- Completing an order and adding tracking are customer-impacting writes. Current Etsy Help says tracking is required to complete an order for US sellers, with limited no-tracking reasons in some flows.
- Current customer-service standards include responding to at least 80% of first messages within 48 hours and shipping at least 80% of eligible orders on time. Review and case standards use separate denominators and exclusions; stats refresh daily and the monthly overview resets on the first. Treat every threshold and authenticated shop value as refresh-required, not permanent or inferable from one review.
- Returns depend on Listing policy and law. For professional traders shipping to the EU/EEA, Etsy's current legal guidance describes a minimum 14-day withdrawal right with exclusions; beginning early July 2026, buyers can submit withdrawal requests through help requests. Escalate legal applicability and do not give legal advice.
- Buyers can leave reviews during the current 100-day eligibility window, beginning at estimated delivery or digital download and continuing to run during an open case. Keep the rolling 12-month shop-rating average separate from the monthly customer-service review standard.
- Bind the exact order, review text/media, estimated-delivery date and last-edit time before triage. A compliant negative opinion, delivered tracking state, or review that mixes a carrier issue with item/service feedback is not automatically removable. Reporting is confidential, available only in the current report window, does not guarantee removal, should not be repeated and is not the IP-infringement route.
- Use a private order-bound resolution draft first when appropriate. A public response is a separate owner-approved external write: it is available once within 100 days of the buyer's last edit, cannot be edited or reposted after deletion, locks buyer editing even after deletion, and must exclude tracking numbers, external links and private information.
- Block review extortion and shilling: no threat, sock-puppet activity, scripted biased review, or refund/replacement/discount/compensation/extra item conditioned on a positive, changed or deleted review. A dated policy page does not authorize a modern incentive scheme; any neutral promotion needs current Etsy-policy, jurisdiction and owner review.
- Review themes may become anonymous same-shop improvement hypotheses, but never authorize buyer-media reuse, personal-data retention, cross-tenant leakage, automatic Listing edits, public responses or causal ranking/sales claims.
- Seller Purchase Protection is conditional and case-specific, not a guarantee. Preserve payment, processing, dispatch, tracking, message, and order evidence and verify the current program criteria before relying on it.
- A labeled Help request starts the normal 48-hour seller-resolution window before a buyer can open a case. Etsy policy controls over a conflicting shop policy, and order-issue communication belongs in Etsy Messages.
- Keep case type, eligibility timing, case log, Etsy information-request deadline, closure, refund funding, Payment account recoupment and review as separate states. Current Cases Policy requires seller responses to Etsy within two calendar days and prohibits conditioning resolution on the buyer closing the case.
- A buyer can use only one dispute method for an order: an Etsy case and a bank/card/PayPal chargeback cannot run in parallel. A chargeback can close or prevent an Etsy case.
- Chargebacks use an Etsy-requested evidence deadline and can appear as a Payment account debit rather than an order refund. Do not issue a parallel refund or contact the buyer's financial institution.
- The current Seller Purchase Protection policy effective 2026-07-09 requires order-level DDP evidence for shipments to the United States. Do not infer DDP from a carrier brand; the rare no-DDP exception requires actual unavailability and explicit Etsy-Message buyer acknowledgement of estimated charges.

## 6. Native AI

- Etsy's public Seller Handbook overview dated 2026-06-29 describes optional or tested seller/buyer AI features: attribute suggestions, AI seller-support chat, Listing title suggestions, Writing Assistant beta, review feature tags, AI delivery estimates, AI shopping integrations, Shop Stats AI summaries, and a Stats Assistant test.
- Version agentic-shopping surfaces separately. The 2025-09-29 announcement described U.S. ChatGPT discovery, browsing and Instant Checkout for some purchases; the 2026-05-05 announcement describes a retailer-run Etsy app in ChatGPT, live in beta, where a buyer tags `@Etsy` and can review, compare or click Listing results. The latter separately describes on-Etsy conversational gift search as an early test. The historical checkout flow must not be assumed current.
- The current app announcement does not establish country coverage, Listing eligibility, seller controls or opt-out, fees, Offsite Ads treatment, referral attribution, data retention, current checkout behavior or a seller API. Keep it `available_unconnected`; an announcement or buyer result does not prove a shop's inclusion, traffic or order outcome.
- Etsy's Q1 2026 shareholder letter describes an early seller-insights agent and says images may depict work in progress. Keep this `research_only`: there is no verified public Shop Manager entry, eligible country/shop, actual input/output, permission, cost, data boundary, control or API, and it is not a reason to create a second T One Agent runtime.
- Before attributing an AI-shopping result or changing operations, reconcile current official terms with authenticated same-shop referrer, order attribution, Payment account fee type and Offsite Ads evidence. Reddit traffic, fee, opt-out or checkout claims remain dated community signals and cannot authorize keyword stuffing, Listing edits, repricing, promotion or Ads changes.
- Current Help documents the Customer Support AI Agent as a Shop Manager chat surface for eligible active shops in good standing, with official Contact Support form fallback. It uses relevant Help Center materials, categorizes issues, may escalate to a human and may request verification; none of those states proves an account, refund, billing or case outcome.
- Etsy names Zendesk AI and Sierra AI for the support agent and documents recording, monitoring, storage, identifier masking, regional training/privacy rights and possible transcript retention for six years after account closure. Minimize inputs and never add full bank/card credentials, cross-shop evidence or unrelated buyer data.
- Etsy has no public inbound support phone number. Use only the signed-in official support path; callback, password, MFA, support submission, payment and account-recovery actions remain owner controlled.
- The Writing Assistant beta is described for selected English-speaking US sellers. Public documentation alone does not prove eligibility in a particular shop.
- The operational guide shows the reply-field sparkle entry in desktop or Etsy Seller app Messages. It may use Listing descriptions, the current conversation and relevant past customer messages; insufficient context prompts the seller for more detail. The draft remains editable and must be reviewed before sending.
- Etsy Stats has distinct metrics and refresh behavior. Visits refresh a few times daily and may change after bot filtering; Etsy Ads clicks and Shop Stats visits are not equivalent because counting and app coverage differ. Self-search is not performance proof.
- Keep all named features `available_unconnected` until an authorized shop session or owner-scoped API read proves the exact shop response. The title-suggestion read schema is documented in the official OpenAPI file, but T One has no Etsy shop/OAuth connector and no captured response; no other named seller AI surface has a verified API path here.
- Any future observation must capture entry path, permissions, accepted inputs, generated output, edit/reject controls, submission boundary, visible metrics, failures, and recovery. AI output remains an editable draft until seller review and the relevant write approval.

## 7. Source register

- API home/access levels: https://developers.etsy.com/
- Authentication/scopes: https://developers.etsy.com/documentation/essentials/authentication/
- Listing API tutorial: https://developers.etsy.com/documentation/tutorials/listings/
- Shop management: https://developers.etsy.com/documentation/tutorials/shopmanagement/
- Creativity Standards: https://www.etsy.com/legal/creativity/
- Craft and party supply eligibility: https://help.etsy.com/hc/en-us/articles/32404729668887-What-Craft-and-Party-Supplies-am-I-Allowed-to-Sell
- Drop delivery and reselling: https://help.etsy.com/hc/en-gb/articles/23948763872151-Does-Etsy-Allow-Drop-Delivery-or-Reselling
- Creativity Standards removal reasons and appeal states: https://help.etsy.com/hc/en-in/articles/34707360607511-Reasons-a-Listing-May-Be-Removed-Under-Etsy-s-Creativity-Standards
- Historical vintage evidence-detail policy, last updated 2018-11-16: https://www.etsy.com/legal/policy/vintage-items-on-etsy/242665563649
- Production partners: https://help.etsy.com/hc/en-us/articles/360000336547-Working-with-Production-Partners-on-Etsy
- Listing image requirements: https://www.etsy.com/legal/policy/listing-image-requirements/253962679005
- Current Listing-video contract: https://help.etsy.com/hc/en-us/articles/360053206073-How-to-Add-Listing-Videos
- Historical smartphone filming guide, published 2020-05-15: https://www.etsy.com/seller-handbook/article/821069114343
- Category-scoped Listing-video use guide, published 2024-11-05: https://www.etsy.com/seller-handbook/article/821069530001
- Intellectual Property Policy: https://www.etsy.com/legal/ip/
- Tags: https://help.etsy.com/hc/en-us/articles/360000336307-How-to-Use-Tags-to-Get-Found-in-Search
- Attributes: https://help.etsy.com/hc/en-us/articles/115014502508-How-to-Use-Attributes-When-Listing-an-Item
- Keywords 101, published 2025-08-26 and marked as of August 2025: https://www.etsy.com/seller-handbook/article/382774281517
- Current public Listing form: https://help.etsy.com/hc/en-us/articles/115015628707-How-to-Create-a-Listing
- 2026 title guidance: https://www.etsy.com/seller-handbook/article/1399426136697
- Fees: https://help.etsy.com/hc/en-gb/articles/115014483627-What-are-the-Fees-and-Taxes-for-Selling-on-Etsy
- Etsy Payments countries: https://help.etsy.com/hc/en-us/articles/115015710408-Countries-Eligible-for-Etsy-Payments
- Advertising policy: https://www.etsy.com/legal/advertising/
- Offsite Ads: https://help.etsy.com/hc/en-us/articles/360000338367-How-Etsy-s-Offsite-Ads-Work
- Etsy Ads campaign and charges: https://help.etsy.com/hc/en-us/articles/360033701174-How-to-Set-Up-and-Manage-an-Etsy-Ads-Campaign
- Etsy Ads performance metrics: https://help.etsy.com/hc/en-us/articles/360034223613-How-to-Review-the-Performance-of-Your-Etsy-Ads
- Contact Etsy Support: https://help.etsy.com/hc/en-us/articles/115013375488-How-to-Contact-Etsy-Support
- Customer Support AI Agent: https://help.etsy.com/hc/en-us/articles/27283630080151-How-Etsy-s-Customer-Support-AI-Agent-Works
- Pay shop balance / Amount due: https://help.etsy.com/hc/en-us/articles/360024112294-How-Do-I-Pay-My-Etsy-Shop-Balance
- Suspected account fraud: https://help.etsy.com/hc/en-us/articles/115015654008-What-to-Do-if-You-Suspect-Fraud-in-Your-Etsy-Account
- Processing profiles: https://help.etsy.com/hc/en-us/articles/115015588087-How-to-Set-Processing-Times-Processing-Profiles-and-Ship-By-Dates
- Complete order/tracking: https://help.etsy.com/hc/en-us/articles/115015774228-How-to-Add-Tracking-and-Complete-an-Order
- Customer service standards: https://help.etsy.com/hc/en-us/articles/360036207794-What-are-Etsy-s-Customer-Service-Standards
- EU returns: https://help.etsy.com/hc/en-us/articles/5703129136407-How-Do-I-Follow-EU-Law-Regarding-Returns-and-Refunds
- Cancel a sale: https://help.etsy.com/hc/en-us/articles/115015587347-How-to-Cancel-a-Sale
- Issue a refund: https://help.etsy.com/hc/en-us/articles/360002089188-How-to-Issue-a-Full-or-Partial-Refund-For-an-Order
- Help a buyer with a return: https://help.etsy.com/hc/en-us/articles/360022953514-How-to-Help-a-Buyer-With-a-Return
- Processing order/payment: https://help.etsy.com/hc/en-us/articles/115015440727-Why-Is-an-Order-or-Payment-in-My-Shop-Still-Processing
- What can be sold: https://help.etsy.com/hc/en-us/articles/360024112614-What-Can-I-Sell-on-Etsy
- Current prohibited-items policy: https://www.etsy.com/legal/prohibited/
- Future prohibited-items policy, effective 2026-08-11: https://www.etsy.com/legal/policy/prohibited-items-policy-effective/1475031537022
- Sales and discounts: https://help.etsy.com/hc/en-gb/articles/115014260108-How-to-Set-Up-Sales-and-Discounts-for-Your-Shop
- Review system: https://help.etsy.com/hc/en-us/articles/360000572708-How-the-Review-System-Works-for-Sellers
- Buyer review eligibility and edit lock: https://help.etsy.com/hc/en-us/articles/115013197687-How-to-Leave-a-Review-on-Etsy
- Negative-review handling: https://help.etsy.com/hc/en-us/articles/115015808588-What-to-Do-if-You-Receive-a-Negative-Review
- Review reporting: https://help.etsy.com/hc/en-us/articles/360000442208-How-to-Report-a-Review
- Review extortion: https://www.etsy.com/legal/policy/extortion/239966959186
- Review shilling: https://www.etsy.com/legal/policy/shilling/243317364583
- Seller Purchase Protection: https://help.etsy.com/hc/en-us/articles/5850122619287-What-is-Etsy-s-Purchase-Protection-for-Sellers
- Answer a Help request: https://help.etsy.com/hc/en-us/articles/13241489600919-How-to-Answer-a-Help-Request-from-a-Buyer
- Resolve a buyer case: https://help.etsy.com/hc/en-us/articles/360016126873-How-to-Resolve-a-Case-from-a-Buyer
- Seller chargebacks: https://help.etsy.com/hc/en-us/articles/115015729027-What-to-Do-If-There-s-a-Chargeback-in-Your-Shop
- Cases Policy, effective 2026-07-09: https://www.etsy.com/legal/policy/cases-policy/243306189901
- Seller Purchase Protection Policy, effective 2026-07-09: https://www.etsy.com/legal/policy/purchase-protection-program-for-sellers/34509585385
- Etsy Ads campaign management: https://help.etsy.com/hc/en-us/articles/360033701174-How-to-Set-Up-and-Manage-an-Etsy-Ads-Campaign
- Etsy Ads placement: https://help.etsy.com/hc/en-us/articles/115015745808-How-Ads-Are-Placed-in-Etsy-Search
- Etsy seller AI overview: https://www.etsy.com/seller-handbook/article/1402347260856
- Etsy app in ChatGPT and on-Etsy conversational-search test, published 2026-05-05: https://www.etsy.com/news/from-keywords-to-conversation-etsyas-next-steps-into-conversational-search-with-app-in-chatgpt
- Historical OpenAI Instant Checkout announcement, published 2025-09-29: https://www.etsy.com/news/meeting-buyers-where-they-are-etsy-partners-with-openai-to-enable-ai-powered-shopping
- Etsy Q1 2026 shareholder letter describing early buyer/seller agents, published 2026-04-29: https://investors.etsy.com/sec-filings/all-sec-filings/content/0001370637-26-000042/q126shareholderletter.htm
- Listing personalization migration: https://developers.etsy.com/documentation/tutorials/personalization-migration/
- Personalization migration-period history: https://developers.etsy.com/documentation/tutorials/personalization/endpoint-migration/
- Multiple/new personalization question support: https://developers.etsy.com/documentation/tutorials/personalization/multiple-and-new-question-type-support/
- Current Open API reference: https://developers.etsy.com/documentation/reference/
- Official OpenAPI 3.0.0 JSON: https://www.etsy.com/openapi/generated/oas/3.0.0.json
- Open API 3.0.0 release, 2026-03-24: https://github.com/etsy/open-api/releases/tag/3.0.0-general-release-2026-03-24
- Personalization GA announcement, 2026-05-11: https://github.com/etsy/open-api/discussions/1581
- Writing Assistant operational guide: https://www.etsy.com/seller-handbook/article/1391026289050
- Search Visibility: https://help.etsy.com/hc/en-us/articles/25869947521175-How-to-Use-the-Etsy-Search-Visibility-Page
- Etsy Stats: https://help.etsy.com/hc/en-us/articles/115015774268-How-to-Use-Etsy-Stats-for-Your-Shop
- Marketplace Insights Help: https://help.etsy.com/hc/en-us/articles/35122361353239-How-Do-I-Use-Etsy-s-Marketplace-Insights-Tool
- Marketplace Insights Seller Handbook guide, published 2025-11-04: https://www.etsy.com/seller-handbook/article/1404564905677
- Seller Trend Report: Spring and Summer 2026, published 2026-03-17: https://www.etsy.com/seller-handbook/article/1473931456647
- Open API Request Standards: https://developers.etsy.com/documentation/essentials/requests/
- Open API rate limits: https://developers.etsy.com/documentation/essentials/rate-limits/
- Open API webhooks: https://developers.etsy.com/documentation/essentials/webhooks/
- API Testing Policy: https://www.etsy.com/legal/policy/api-testing-policy/169130941112
- Payments tutorial: https://developers.etsy.com/documentation/tutorials/payments/
- Payment account: https://help.etsy.com/hc/en-us/articles/115015747228-How-to-Manage-Your-Payment-Account
- Receiving deposits: https://help.etsy.com/hc/en-us/articles/360046998234-How-to-Receive-Your-Etsy-Payments-Deposit
- Payment account reserves: https://help.etsy.com/hc/en-us/articles/360058722214-What-is-a-Payment-Account-Reserve
- Deposit reconciliation: https://help.etsy.com/hc/en-us/articles/360016389113-How-to-Calculate-Your-Etsy-Payments-Deposit-Amount
- Third Variation tutorial: https://developer.etsy.com/documentation/tutorials/third-variation/
- Official Etsy Open API GitHub repository, research evidence only until license/admission review: https://github.com/etsy/open-api
- Official shared-secret enforcement announcement: https://github.com/etsy/open-api/discussions/1531
- Verified Etsy GitHub organization: https://github.com/etsy
- OpenAPI Dev MCP documentation: https://developer.etsy.com/documentation/mcp_server/devmcpserver/
- Seller API Access announcement, 2026-07-13: https://github.com/etsy/open-api/discussions/1647
- Inventory/shipping endpoint migration, effective 2026-07-29: https://github.com/etsy/open-api/discussions/1653
- Third-variation readiness announcement, 2026-07-14: https://github.com/etsy/open-api/discussions/1648
- Open API repository Security policy: https://github.com/etsy/open-api/security/policy
- Variations Help: https://help.etsy.com/hc/en-us/articles/115015664047-How-to-Add-Variations-for-Your-Listings
- Digital Listings Help: https://help.etsy.com/hc/en-us/articles/115015628347-How-to-Manage-Your-Digital-Listings

## 8. Dynamic taxonomy and digital-item boundary

- The renderable Listings Tutorial directs seller applications to read `getSellerTaxonomyNodes`, choose the category, then call `getPropertiesByTaxonomyId`. Only properties marked `supports_variations=true` are eligible for `property_values`.
- Seller taxonomy and buyer taxonomy are not interchangeable; seller hierarchy may be deeper. Never carry a property, scale or value ID from an unrelated category into a new product.
- Current public Shop Manager Help describes up to two variation attributes and category-dependent choices. The API third-variation preview is a separate dated compatibility track; it does not prove that every current shop UI exposes a third attribute.
- Current Digital Listings Help distinguishes instant downloads and made-to-order downloads and says digital items do not support Listing variations. Do not mark digital goods as physical to unlock variation controls.
- Three independent public seller discussions corroborate the missing digital-variation control, but suggested separate Listings, bundles or shop sections remain dated practice hypotheses. The two official Help pages control the rule.
- The verified Etsy GitHub identity is only an ownership gate. `etsy/open-api` is currently a documentation/release/discussion channel at commit `2ecce66e07627358a074d46188586f0283c9a6cf`; no repository license or seller SDK was detected. Do not clone/install it, and exclude unrelated official repositories such as `etsy/mcp-pinot`, `etsy/github-app-sts` and `etsy/combined-status-check-action` from the Etsy commerce runtime.
