# Platform adapter boundaries

Checked: 2026-07-18 (+08:00). These are public-documentation adapter contracts. None is proof of a connected store.

## Shopify

- Identity: shop domain + app installation + credential reference + scope set + requested/returned Admin API version.
- Preferred API: versioned GraphQL Admin API.
- AI surfaces observed: Sidekick and Campaign Autopilot. Draft/review/save/approve/activate are separate states.
- Connector truth: `available_unconnected` in T One; no store OAuth or read probe in this cycle.

## WooCommerce

- Identity: HTTPS site base URL + WordPress user + REST key/application connection + WooCommerce/WordPress/plugin/theme versions + permalink mode + HPOS authoritative/backup and synchronization state.
- Preferred API: `/wp-json/wc/v3/`; the official page currently calls v3 recommended for new integrations. Public requirements list WooCommerce 3.5+, WordPress 4.4+ and pretty permalinks; a real adapter must probe the named site instead of assuming them.
- Public storefront surface: `/wp-json/wc/store/v1/` exposes customer-facing product/cart/checkout operations for the current session. It uses no admin API key, cannot read other customers or arbitrary orders, and cannot change store settings; never promote a successful public request to an authenticated connector state.
- Store API product collections expose published products only. Draft, pending and other unpublished products can return 404 and require an authorized admin surface to classify correctly.
- Current-session cart and checkout mutations require a nonce or Cart Token. Do not use the documented development filter that disables nonce checks in production.
- Keep REST, WordPress admin, server, plugin/theme, payment and advertising privileges separate.
- HPOS is not a version-only switch. New installations have defaulted to HPOS since 8.2, while existing stores may use legacy or compatibility modes; the 10.7 advisory disables sync-on-read by default. Use supported CRUD/REST, inspect incompatible plugins and pending synchronization, and never depend on direct `posts/postmeta` reads.
- Native-AI lifecycle: Woo AI product name/description/category/background-removal features were deprecated on 2025-05-15. The WooCommerce.com Support AI Assistant is an account support surface and may use store context only when usage tracking is enabled and the store is connected to Jetpack; it remains guidance with human-support fallback, not a store executor. Third-party AI plugins remain uninstalled extensions until the named store proves installation, provider credential, data flow, output review and version.
- Connector truth: `available_unconnected`; no site identity/key or live UI/API evidence in this cycle.

## BigCommerce

- Identity: `store_hash` + API account type + OAuth scope set + credential reference + channel/storefront.
- Domains: Catalog, Orders, Payments, Webhooks and channels have separate scopes/semantics.
- BigAI Copywriter public constraints: v3 Add/Edit Catalog, currently English, draft suggestion requiring review.
- BigAI Product Recommendations public constraints: closed beta, Enterprise, GCP billing, native analytics and training data.
- Connector truth: `research_only`; the current shared T One registry has no verified adapter or store connection.

## Adobe Commerce / Magento

- First dimension: `paas`, `on_premises` or `saas`. Do not share one auth/base-URL template across them.
- PaaS/on-prem identity: base URL + store-view code + integration/admin/customer identity + credential reference + Commerce version.
- SaaS identity: tenant + environment/project + IMS client/credential reference + `Store` header/store view + supported endpoint set.
- AI services: Live Search and Product Recommendations require entitlement/install/configuration, catalog/event data, storefront path and store-view validation.
- Connector truth: `research_only`; no current T One adapter, Commerce tenant, store view or read probe.

## Salla

- Merchant API identity: partner app + merchant installation/store + scope set + credential reference; base API documented as `https://api.salla.dev/admin/v2`.
- Serialize refresh: the inspected authorization page documents 14-day access tokens and one-month single-use refresh tokens; parallel reuse can revoke the installation.
- Read scopes observed: `products.read` for product list and `orders.read` for order list.
- Product types include physical, service, grouped, codes, digital and booking; choose a vertical delivery extension before mapping fulfillment.
- Partners MCP is a separate Partner Portal surface with app/settings/scopes/publish tools. It is not proof of Merchant API access.
- Connector truth: `research_only` for public API; `blocked_connector` for Partners MCP until owner identity and connector setup exist.

## Zid

- General OAuth identity: server-side authorization-code app + authorization token + store-specific manager identity + credential reference; base API documented as `https://api.zid.sa/v1`.
- Do not hard-code one header template: the general auth page describes `Authorization` and `X-MANAGER-TOKEN`, while the inspected product-list endpoint documents `Access-Token`, `Store-Id`, `Accept-Language` and `Role`.
- Product schema distinguishes product class, parent/child/standalone structure, localization, taxability, shipping need, stock and store ID.
- Webhook conditions were documented only for `order.create` and `order.status.update` at capture time.
- The official Zid AI Connector listing describes an MCP link granting broad store management. Treat the link as a high-privilege credential and keep all writes in T One approval gates.
- Connector truth: `research_only` for public API and `blocked_connector` for Zid AI Connector until store-owner installation and least-privilege probing.

## Adapter admission test

An adapter can move from `research_only` to `available_unconnected` only when T One has an implemented, registry-backed adapter. It can move to `connected_read_only` only after a store-specific credential passes a non-mutating probe and the route, scope set, response, capture time and expiration are recorded. Write scope alone never produces `connected_write_gated`; approval serialization, rollback and post-write verification must also exist.
