# Shopee site and program matrix

## Executable country sites

| Site | Route rule | Minimum store identity | Country-rule source | Strict boundary |
|---|---|---|---|---|
| SG | Independent route | `store_binding_id + shop_id + execution_identity_id` | https://help.shopee.sg/ | Do not reuse MY/TH/VN/PH/ID/TW/BR authorization or Ads identity. |
| MY | Independent route | `store_binding_id + shop_id + execution_identity_id` | https://help.shopee.com.my/ | SIP may originate from a Malaysia Shop, but SIP child listings are not proof of independent child-shop authorization. |
| TH | Independent route | `store_binding_id + shop_id + execution_identity_id` | https://help.shopee.co.th/ | Require Thai-site category, content, logistics, fee, and campaign evidence. |
| VN | Independent route | `store_binding_id + shop_id + execution_identity_id` | https://help.shopee.vn/ | Require Vietnam-site category, content, logistics, fee, and campaign evidence. |
| PH | Independent route | `store_binding_id + shop_id + execution_identity_id` | https://help.shopee.ph/ | Direct eligibility and overseas-shop scope must come from the actual account/program. |
| ID | Independent route | `store_binding_id + shop_id + execution_identity_id` | https://help.shopee.co.id/ | Export, local programs, ads, video, and campaigns are separate policy surfaces. |
| TW | Independent route | `store_binding_id + shop_id + execution_identity_id` | https://help.shopee.tw/ | Do not treat a TW global/SIP parent account as proof that every downstream site is independently writable. |
| BR | Independent route | `store_binding_id + shop_id + execution_identity_id` | https://help.shopee.com.br/ | Do not reuse Southeast Asia policies, logistics assumptions, language, fees, or Ads identity. |

`SEA` and `Southeast Asia` are reporting groups only. They are never values for a write route.

## Required classification axes

| Axis | Values | Meaning |
|---|---|---|
| `platform` | `shopee` | Marketplace identity. |
| `country_site` | `SG/MY/TH/VN/PH/ID/TW/BR` | Concrete executable site. |
| `store_model` | `marketplace_seller` | Current adapter’s common Shopee store model. |
| `seller_origin` | `local/cross_border/unknown` | Whether the seller operates from the site’s local market or cross-border context. Do not infer it from a marketing label. |
| `account_program` | `ordinary_store/global_store/sip/direct/light_overseas/pending_verification` | Account, export, or multi-site program. SIP, Direct and global-store labels live here. |
| `fulfillment_mode` | `seller_fulfilled/platform_logistics_if_available/fulfilled_by_shopee/third_party_warehouse/unknown` | Order fulfillment. FBS lives here. |
| `ownership` | `self_owned/private_tenant_owned/platform_co_ops/partner_owned` | Who owns or operates the store. private_tenant co-operation is not Shopee official full managed. |
| `execution_surface` | `open_platform/seller_center/ads_backend/affiliate_live_backend/erp/report_import/logistics_backend` | Authorization and tool boundary. |

## Program decisions

- SIP: preserve the local parent shop, overseas listing scope, program eligibility, linked-shop permission limits, and which actions Shopee manages. A parent authorization may initially cover current affiliates, but each later refresh uses the exact parent/affiliate `shop_id` and stores the resulting pair separately. Do not invent credentials or use one permanent shared regional token.
- Direct: preserve local and overseas shop identities, both markets’ policies, logistics handoff, and settlement/fee evidence. Do not label it SIP or FBS.
- Global store: treat the label as an account program only. Read its concrete downstream country scope and child-shop identities from current official or authorized account evidence; never route a write to `global`, `SEA`, or a region.
- FBS: require site/shop enrollment, warehouse, SKU mapping, inbound status, storage/handling fees, and service SLA before operational claims.
- Local versus cross-border: read from the authorized account or verified onboarding documents. If unknown, remain `unknown` and block writes.
- `official_full_managed`: recognize and block; T One/private_tenant does not connect it as an executable mode.

TH DTS is a country-rule field on the listing/order/logistics route, not a store model or account program. Resolve current in-stock versus genuine pre-order/made-to-order truth, Bulky channel, exception evidence, DTS, LSR and auto-cancel clocks under the exact TH `store_binding_id`; never reuse it for another country.
