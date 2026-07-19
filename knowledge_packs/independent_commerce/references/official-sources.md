# Official sources and evidence scope

Checked: 2026-07-19 (+08:00)

Use this file as the dated evidence index, not as a substitute for rechecking a live source before a risky action. Keep the source URL, checked date, route, applicable object, and recheck trigger in every distilled rule.

## Shopify

| ID | Official URL | Applies to | Verified fact | Recheck trigger |
|---|---|---|---|---|
| `shopify_api_versioning` | https://shopify.dev/docs/api/usage/versioning | Shopify apps; all markets; `independent_site` | Shopify releases dated API versions quarterly, recommends specifying a version, and supports stable versions for at least 12 months. On 2026-07-18, `2026-07` is stable and listed accessible until 2027-07-16. | Quarterly release, deprecation notice, returned version differs |
| `shopify_access_scopes` | https://shopify.dev/docs/api/usage/access-scopes | Per Shopify store/app installation | Apps request resource-specific scopes. Order access defaults to the recent 60-day window unless `read_all_orders` is separately approved; protected customer data requires additional approval. | Scope or protected-data policy change |
| `shopify_webhooks` | https://shopify.dev/docs/apps/build/webhooks | Per Shopify app/store subscription | Verify HMAC, deduplicate by webhook ID, tolerate non-guaranteed ordering, and run reconciliation because delivery is not guaranteed. | Webhook/Event platform change |
| `shopify_fulfillment_orders` | https://shopify.dev/docs/api/admin-graphql/latest/objects/FulfillmentOrder | Physical fulfillment per store/location | Shopify creates fulfillment orders after order routing; apps need the relevant fulfillment-order scopes and cannot manually create a `FulfillmentOrder`. | API schema/version change |
| `shopify_orders` | https://shopify.dev/docs/api/admin-graphql/latest/objects/Order | Orders, returns, refunds, fulfillment | The Order object connects purchase, payment and fulfillment data; order and customer access remains scope-gated. | API schema/version change |
| `shopify_taxes` | https://help.shopify.com/en/manual/taxes/ | Country/region-specific; seller entity-specific | Tax services vary by region, and the merchant remains responsible for correct registration, collection, filing, and remittance unless a specific automated filing service applies. | Selling market, entity, registration, tax-service or law change |
| `shopify_digital_services` | https://help.shopify.com/en/manual/products/digital-service-product/selling-services-or-digital-products | Digital products and service bookings | Disable physical shipping for digital/service items; delivery or booking generally needs an app. The official page flags EU VAT treatment for digital goods as market-specific. | Product type, app, selling market, tax rule change |
| `shopify_duties_markets` | https://help.shopify.com/en/manual/markets/customizations/duties-and-taxes | Cross-border physical goods | Market settings can control tax display and estimated duty collection; correct HS code, origin, destination, and market configuration remain necessary. | Origin, destination, product code, carrier, law change |
| `shopify_theme_performance_best_practices` | https://shopify.dev/docs/storefronts/themes/best-practices/performance/index | Shopify Liquid themes; global public developer surface | The current page ties storefront performance to conversion, repeat business and search; recommends progressive enhancement, non-blocking/minimal JavaScript, responsive Shopify-hosted assets, no lazy loading for above-the-fold media, Theme Check, RUM for field evidence and repeatable Lighthouse testing when field data is absent. The performance GraphQL queries shown are `unstable`, not a production connector contract. | Theme guidance, metric/API version, Theme Check or report surface changes |
| `shopify_performance_getting_started` | https://performance.shopify.com/pages/getting-started-with-performance | Shopify storefront performance learning index | The first-party index separates field/RUM evidence from lab testing and points to an ongoing measure-test-optimize-implement cycle; its linked articles are not proof that a named store was measured or improved. | Index, linked article or ownership change |
| `shopify_performance_optimization_index` | https://performance.shopify.com/pages/techniques-for-optimizing-web-performance | Shopify storefront LCP/CLS/INP diagnosis | The first-party index separates metrics/testing, LCP, CLS, INP and long-term performance management and links Shopify-specific diagnostic material. Use it to route a bounded diagnosis, not to apply every technique or install a speed app. | Index, metric or linked implementation guidance change |
| `shopify_build_web_pixels_current` | https://shopify.dev/docs/apps/build/marketing/build-web-pixels | Shopify app pixels; per app/store; global developer surface | The current workflow requires app-development permission, a development store, authenticated GraphQL and `write_pixels` plus `read_customer_events`. `shopify app dev` connects development but does not create or subscribe a pixel; `webPixelCreate` with reviewed settings activates it, while deploy/release is a separate stateful step. Privacy purposes are configured per pixel and store. | CLI/app version, scope, mutation, privacy-purpose or deploy workflow change |
| `shopify_web_pixels_customerprivacy` | https://shopify.dev/docs/api/web-pixels-api/standard-api/customerprivacy | Shopify app and custom pixels; per storefront visitor consent state | App and custom pixel examples read current booleans from `init.customerPrivacy` and update them on `visitorConsentCollected`. Consent state belongs in the event handoff; the page does not prove any named store pixel, consent banner, destination or ad account is connected. | Customer Privacy API, consent field, event or regional privacy behavior change |

### Shopify Customer Events package audit

- `Shopify/cli@5adc504` / release `4.5.2` is official and MIT. The existing shared registry decision remains the authority; this cycle classifies it `keep_reuse` for the official starter/activation lifecycle only. It was not installed, authenticated or deployed.
- `karolk95/shopify-customer-events-plain@8a72bbd` is GPL-3.0 and was classified `rejected_unsafe`: its reviewed purchase mapping sends raw checkout email/address, its README directs a privacy classification that cannot be universalized, debug logging can expose full events, and no consent-event or event-ID dedup contract was found. Structural event names were inspected but no code was copied.
- `analyzify/shopify-pixels@a02141d` was classified `rejected_license`: no license or release was exposed, the latest commit was 2022-12-15, consent/event-ID handling was absent, and an open issue reports duplicate sessions. No code was installed or copied.

## WooCommerce

| ID | Official URL | Applies to | Verified fact | Recheck trigger |
|---|---|---|---|---|
| `woocommerce_rest_api` | https://developer.woocommerce.com/docs/apis/rest-api/ | Each WooCommerce/WordPress site | The public requirements currently list WooCommerce 3.5+, WordPress 4.4+ and pretty permalinks; default permalinks do not work. This does not prove a named site satisfies them. | WooCommerce/WordPress version, permalink or REST API change |
| `woocommerce_rest_api_v3` | https://developer.woocommerce.com/docs/apis/rest-api/v3/ | New WooCommerce REST integrations | The page calls `/wp-json/wc/v3/` current and recommended for new integrations. A site/user-scoped key and real read probe are still required. | REST version or endpoint guidance changes |
| `woocommerce_authentication` | https://developer.woocommerce.com/docs/apis/rest-api/authentication | Per-site REST authorization | REST key permissions follow the selected WordPress user's capabilities. HTTPS supports Basic Auth with consumer key/secret; the application authorization endpoint can grant read/write levels. | Authentication method or site role change |
| `woocommerce_webhooks` | https://developer.woocommerce.com/docs/apis/rest-api/v3/webhooks/ | Per WooCommerce site | Webhooks can be managed through REST, have status/topic/delivery URL/secret, and use an HMAC signature for verification. | Webhook implementation or plugin change |
| `woocommerce_hpos` | https://developer.woocommerce.com/docs/features/orders/high-performance-order-storage/ | WooCommerce order storage and plugins | HPOS is stable and enabled by default for new installations since WooCommerce 8.2; existing stores may retain legacy or compatibility modes. Check the authoritative datastore, pending sync and incompatible extensions instead of assuming legacy `posts/postmeta` storage. | WooCommerce upgrade, storage-mode, synchronization or plugin change |
| `woocommerce_hpos_sync_on_read_10_7` | https://developer.woocommerce.com/2026/02/16/hpos-sync-on-read-to-be-disabled-by-default-in-woocommerce-10-7/ | WooCommerce 10.7+ stores using HPOS compatibility mode | The dated advisory says HPOS sync-on-read is disabled by default from 10.7 and may affect custom code or plugins that are not fully HPOS-compatible. | Core version, compatibility mode or advisory changes |

### WooCommerce GitHub supplement

The official [WooCommerce monorepo](https://github.com/woocommerce/woocommerce) was opened on 2026-07-18. Public repository metadata showed the active `trunk` branch and release `10.9.4` published 2026-07-07; the WooCommerce plugin subtree contains a GPL-3.0-or-later license file. Because `config/github_capability_registry.json` has no WooCommerce admission, the repository remains `research_only`: no clone, install, dependency change, code reuse, or runtime integration was performed.

## BigCommerce

| ID | Official URL | Applies to | Verified fact | Recheck trigger |
|---|---|---|---|---|
| `bigcommerce_api_accounts` | https://docs.bigcommerce.com/developer/docs/overview/api-fundamentals/api-accounts | Each BigCommerce store/app/account | BigCommerce has store-, app-, and account-level OAuth API accounts. Use `X-Auth-Token` and least-privilege scopes; account type and scope determine accessible resources. | OAuth/account model change |
| `bigcommerce_oauth_flow` | https://docs.bigcommerce.com/developer/docs/integrations/apps/guide/auth | App installation per store | OAuth returns a store context such as `stores/{STORE_HASH}` and scope set; validate returned scopes and bind the token reference to that store. | OAuth flow or scope change |
| `bigcommerce_catalog` | https://docs.bigcommerce.com/developer/docs/admin/catalog-and-inventory/products-overview | Catalog per store/channel | Catalog supports physical and digital products. Product modify/read-only scopes are distinct, and channel assignments matter for multi-storefront stores. | Catalog schema or channel assignment change |
| `bigcommerce_orders` | https://docs.bigcommerce.com/developer/docs/admin/checkout-and-cart/orders/overview | Orders, shipments, transactions, refunds | Orders V2 covers core order and shipment operations; V3 exposes transactions/refunds. Required scopes must be checked per operation. | Orders/Payments API change |
| `bigcommerce_webhooks` | https://docs.bigcommerce.com/developer/docs/integrations/webhooks/overview | Per-store event subscription | Webhooks are registered for a store and event scope; payloads can contain only an entity ID, so consumers may need an authorized follow-up read. | Webhook event/schema change |
| `bigcommerce_bigai` | https://www.bigcommerce.com/solutions/ai-for-commerce/ | Public BigAI product surface | Public page distinguishes available Copywriter from recommendation/analytics/quote features carrying coming-soon or plan limits. It does not prove store entitlement. | Availability, plan, region or product-page change |
| `bigcommerce_recommendations_beta` | https://docs.bigcommerce.com/developer/docs/beta/product-recommendations/overview | Enterprise closed beta | Requires beta access, Enterprise, billed GCP, sufficient training data, enabled native analytics and Storefront GraphQL integration. | Beta, plan, billing, data or API change |
| `bigcommerce_copywriter` | https://www.bigcommerce.com/apps/bigai-copywriter/ | BigCommerce v3 Add/Edit Catalog | Public listing says current output is English, supports style/tone/keyword/length inputs, and is a draft requiring user review and revision. | App version, compatibility, language, price or terms change |

## Adobe Commerce / Magento

| ID | Official URL | Applies to | Verified fact | Recheck trigger |
|---|---|---|---|---|
| `adobe_commerce_rest` | https://developer.adobe.com/commerce/webapi/rest/ | Adobe Commerce PaaS/on-prem/SaaS integrations | Deployment modes use different REST surfaces and authentication/store scoping. PaaS/on-prem commonly use store-view-coded paths and token/OAuth patterns; SaaS uses IMS and tenant/store context. | Deployment, auth, endpoint or store-scope change |
| `adobe_live_search` | https://experienceleague.adobe.com/en/docs/commerce/live-search/overview | Installed/configured Commerce Live Search | Provides AI-powered faceting/reranking after installation/configuration and catalog/event data sharing; Admin, storefront and retention constraints apply. | Extension, service, limits, data or retention change |
| `adobe_product_recommendations` | https://experienceleague.adobe.com/en/docs/commerce/product-recommendations/overview | Entitled Commerce Product Recommendations | Uses Adobe AI/ML with catalog and aggregated behavior, has storefront-specific implementations and is not HIPAA-ready for PHI workloads. | Eligibility, data handling, HIPAA status, implementation or retention change |

## Salla

| ID | Official URL | Applies to | Verified fact | Recheck trigger |
|---|---|---|---|---|
| `salla_get_started` | https://docs.salla.dev/421117m0 | Salla Merchant API | Base API is documented as `https://api.salla.dev/admin/v2`; access is OAuth2/scoped through a partner app and merchant installation. | Base URL, API version, partner or OAuth change |
| `salla_authorization` | https://docs.salla.dev/421118m0 | Salla Merchant OAuth | Inspected page documents 14-day access tokens and one-month single-use refresh tokens; refresh must be serialized to avoid revocation. | Token lifetime, rotation or app-mode change |
| `salla_products` | https://docs.salla.dev/5394168e0 | Product list per merchant store | GET products requires `products.read`; product types include physical, service, grouped, codes, digital and booking semantics. | Endpoint, scope, type or schema change |
| `salla_orders` | https://docs.salla.dev/5394146e0 | Order list per merchant store | GET orders requires `orders.read`; the page documents sequential pagination, `per_page=30`, a 15-minute cache window and dated deprecations. | Pagination, deprecation, scope or customer-data change |
| `salla_partners_mcp_auth` | https://docs.salla.dev/2228618m0 | Salla Partners Portal MCP | Uses OAuth 2.1 with PKCE against the Partners Portal; this is not proof of Merchant API/store authorization. | MCP server, session, auth or client change |
| `salla_partners_mcp_tools` | https://docs.salla.dev/2228622m0 | Partner apps/settings/scopes | Tools include create/update/delete/publish and scope/shipping operations; runtime token storage, webhook retry and app code stay outside MCP. | Tool, service gate or portal behavior change |

## Zid

| ID | Official URL | Applies to | Verified fact | Recheck trigger |
|---|---|---|---|---|
| `zid_start_here` | https://docs.zid.sa/start-here | Zid partner and Merchant APIs | Real access starts with partner/app/store prerequisites; public domains include products, orders, inventory, shipping, marketing, customers and webhooks. | Partner, plan/API Access or domain change |
| `zid_authorization` | https://docs.zid.sa/authorization | Zid Merchant OAuth | Uses server-side authorization-code flow. General docs separate API authorization from store-specific manager access and list `https://api.zid.sa/v1` and `https://oauth.zid.sa`. | Grant, token, header, API version or scope change |
| `zid_products` | https://docs.zid.sa/retrieve-a-list-of-products | Zid product-list endpoint | The inspected endpoint requires `products.read` and documents `Access-Token`, `Store-Id`, `Accept-Language`, and `Role`; adapter auth must be endpoint-family-specific. | Header, scope, locale, class or schema change |
| `zid_webhooks` | https://docs.zid.sa/webhooks | Zid merchant events | Conditions were documented only for `order.create` and `order.status.update`; do not generalize them to all events. | Event, condition, health or schema change |
| `zid_ai_connector` | https://apps.zid.sa/en/application/4820 | Official Zid App Market MCP listing | Listing developed by Zid describes broad store-management tools and says the MCP link grants full store access. Treat it as a high-privilege credential, not a T One connection. | App version, scope, setup, price or security change |

## Platform-native AI browser evidence

| ID | Official URL | Actual operation on 2026-07-18 | Boundary |
|---|---|---|---|
| `shopify_sidekick` | https://help.shopify.com/en/manual/ai-powered-tools/sidekick | Opened page and followed create-content navigation | No admin login, plan, role, store data or live output |
| `shopify_sidekick_content` | https://help.shopify.com/en/manual/ai-powered-tools/sidekick/generate-content | Read image/content/discount/report/Flow save and review states | Draft/save/publish are separate; rights and product facts still require review |
| `shopify_campaign_autopilot` | https://help.shopify.com/en/manual/promoting-marketing/autopilot/managing-autopilot-strategies | Clicked from Sidekick help and scrolled permissions/metrics sections | Early access; platform permission never overrides T One action confirmation |
| `adobe_developer_ai_assistant` | https://developer.adobe.com/commerce/webapi/rest/ | Opened beta assistant and submitted an auth/store-scope question | First answer failed; docs AI is not Commerce Admin AI and every claim needs source verification |
| `salla_ai_prompts_blocked` | https://salla.com/en/tools/ai-prompts | Opened once; browser received HTTP 403 | No bypass; UI/input/output remain unknown |

The detailed interaction record, capture times, errors and permission boundaries are in `../state/browser_evidence_2026-07-18.json`.

## External acquisition channel boundary

| ID | Official URL | Applies to | Verified fact or retained boundary | Recheck trigger |
|---|---|---|---|---|
| `google_ads_oauth` | https://developers.google.com/google-ads/api/docs/oauth/overview | Google Ads accounts, not store APIs | Google Ads API uses OAuth 2.0 and also requires a developer token. The user/service identity must have access to the target Ads account. Last updated by Google: 2026-06-24 UTC. | API version, access model, account hierarchy change |
| `tiktok_business_api` | https://business-api.tiktok.com/portal/docs | TikTok advertising/business accounts, not TikTok Shop or store APIs | TikTok API for Business is a separate developer surface. Treat its authorization and advertiser identity independently from the store. | API version, advertiser authorization change |
| `meta_marketing_api` | https://developers.facebook.com/docs/marketing-apis/ | Meta business/ad accounts, not store APIs | Retain only the separation boundary until the exact account/token/permission documentation is successfully fetched and dated. The official page was not reliably retrievable in this verification run. | Before any Meta-specific rule or action |

## Evidence rules

- Use a live authorized response for store facts; documentation only establishes possible objects and scopes.
- Record `checked_at`, source URL, platform, country/market, commerce mode, ownership, object/scope, and recheck trigger.
- Mark community or seller experience `experiment_hypothesis`, even when multiple sellers agree.
- Mark inaccessible, conflicting, or platform-specific details `unknown_pending_official_verification`.
- Keep a documented platform or tool `research_only` until T One has a verified store-specific authorization and read probe.
- Never promote a time-sensitive price, tax rate, API version, feature availability, payment method, carrier, or advertising rule into the stable Skill body.
