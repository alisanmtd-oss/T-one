from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any


CHANNEL_ROUTE_REQUEST_FILENAME = "channel_route_requests.json"
PLATFORM_CAPABILITY_FILENAME = "platform_developer_capabilities.json"
PLATFORM_ACTIVITY_RULE_FILENAME = "platform_activity_rules.json"
ACTIVITY_AD_SIGNALS = {
    "ad",
    "ads",
    "advertising",
    "campaign_budget",
    "budget_change",
    "gmv_max",
    "shop_ads",
    "amazon_ads",
    "catalog_sales",
    "creative_test",
}
EXTERNAL_ACTIVITY_SIGNALS = {
    "publish",
    "submit",
    "activate",
    "launch",
    "create",
    "budget_change",
    "price_change",
    "coupon_publish",
    "campaign_signup",
}
DEFAULT_ACTIVITY_FEE_RATES = {
    "tiktok_shop": 0.08,
    "shein": 0.10,
    "shopee": 0.08,
    "lazada": 0.08,
    "amazon": 0.15,
    "walmart": 0.12,
    "etsy": 0.10,
    "ebay": 0.13,
    "shopify": 0.03,
    "woocommerce": 0.03,
    "meta_ads": 0.00,
}
DEFAULT_MIN_ACTIVITY_MARGIN_RATE = 0.20
DEFAULT_AD_BUDGET_PROFIT_SHARE = 0.35
MIN_CREATIVE_TEST_COUNT = 3
UNSUPPORTED_EXECUTABLE_STORE_MODELS = {"official_full_managed"}


PLATFORM_DEVELOPER_DOMAIN_DETAILS: dict[str, dict[str, dict[str, Any]]] = {
    "tiktok_shop": {
        "listing": {
            "api_objects": ["Product API", "Inventory API", "Global Product API"],
            "required_authorizations": ["shop_authorization", "authorized_shop_token"],
            "execution_surfaces": ["Shop Open API", "Seller Center product backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_publish_or_update",
            "official_source_url": "https://partner.tiktokshop.com/docv2/",
        },
        "promotion": {
            "api_objects": ["Product Discount API", "Flash Deal API", "Promotion API"],
            "required_authorizations": ["shop_authorization", "seller_center_access", "promotion_permission"],
            "execution_surfaces": ["Promotion API", "Seller Center promotion backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_campaign_signup_or_price_change",
            "official_source_url": "https://partner.tiktokshop.com/docv2/",
        },
        "coupon": {
            "api_objects": ["Coupon API", "Voucher API", "Seller Center Coupon"],
            "required_authorizations": ["shop_authorization", "seller_center_access", "coupon_permission"],
            "execution_surfaces": ["Coupon/Voucher API", "Seller Center coupon backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_coupon_publish",
            "official_source_url": "https://partner.tiktokshop.com/docv2/",
        },
        "ads": {
            "api_objects": ["TikTok Business API", "Ads Manager", "Ad Account Reports"],
            "required_authorizations": ["business_center", "ads_account", "advertiser_permission"],
            "execution_surfaces": ["Business Center", "Ads Manager", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_ad_launch_or_budget_change",
            "official_source_url": "https://business-api.tiktok.com/portal/docs",
        },
        "reporting": {
            "api_objects": ["Authorized Shops", "Order API", "Reports / Seller Center export"],
            "required_authorizations": ["shop_authorization", "authorized_shop_token"],
            "execution_surfaces": ["Shop Open API", "Seller Center reports", "report_import"],
            "final_submission_gate": "read_only_no_external_submit",
            "official_source_url": "https://partner.tiktokshop.com/docv2/",
        },
    },
    "shein": {
        "listing": {
            "api_objects": ["Product API", "Inventory API", "Open Platform integration"],
            "required_authorizations": ["open_platform_account", "application_review", "seller_site_authorization"],
            "execution_surfaces": ["SHEIN Open Platform", "Seller Hub", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_listing_submit",
            "official_source_url": "https://open.sheincorp.com/",
        },
        "promotion": {
            "api_objects": ["Campaign backend", "Campaign price", "Inventory campaign"],
            "required_authorizations": ["seller_hub_access", "site_store_model_verified"],
            "execution_surfaces": ["Seller Hub campaign backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_campaign_price_or_inventory_commit",
            "official_source_url": "https://open.sheincorp.com/",
        },
        "coupon": {
            "api_objects": ["Seller discount backend", "Platform rule draft"],
            "required_authorizations": ["seller_hub_access", "site_store_model_verified"],
            "execution_surfaces": ["Seller Hub discount backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_discount_publish",
            "official_source_url": "https://open.sheincorp.com/",
        },
        "reporting": {
            "api_objects": ["Order API", "After-sales API", "Report import"],
            "required_authorizations": ["open_platform_account", "seller_site_authorization"],
            "execution_surfaces": ["SHEIN Open Platform", "Seller Hub reports", "report_import"],
            "final_submission_gate": "read_only_no_external_submit",
            "official_source_url": "https://open.sheincorp.com/",
        },
    },
    "amazon": {
        "listing": {
            "api_objects": ["Listings Items API", "Catalog Items API", "Feeds API"],
            "required_authorizations": ["sp_api_authorization", "marketplace_verified"],
            "execution_surfaces": ["Selling Partner API", "Seller Central", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_listing_or_feed_submit",
            "official_source_url": "https://developer-docs.amazon.com/sp-api/",
        },
        "promotion": {
            "api_objects": ["Seller Central Promotions", "Deals", "Price Discount"],
            "required_authorizations": ["seller_central_access", "marketplace_verified"],
            "execution_surfaces": ["Seller Central promotion backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_deal_or_price_change",
            "official_source_url": "https://developer-docs.amazon.com/sp-api/",
        },
        "coupon": {
            "api_objects": ["Seller Central Coupons", "Deal draft"],
            "required_authorizations": ["seller_central_access", "marketplace_verified"],
            "execution_surfaces": ["Seller Central coupon backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_coupon_submit",
            "official_source_url": "https://developer-docs.amazon.com/sp-api/",
        },
        "ads": {
            "api_objects": ["Amazon Ads API", "Sponsored Products", "Sponsored Brands"],
            "required_authorizations": ["amazon_ads_authorization", "advertiser_profile"],
            "execution_surfaces": ["Amazon Ads API", "Advertising Console", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_ad_launch_or_budget_change",
            "official_source_url": "https://advertising.amazon.com/API/docs/en-us",
        },
        "reporting": {
            "api_objects": ["Reports API", "Orders API", "Finances API"],
            "required_authorizations": ["sp_api_authorization", "marketplace_verified"],
            "execution_surfaces": ["Selling Partner API", "Seller Central reports", "report_import"],
            "final_submission_gate": "read_only_no_external_submit",
            "official_source_url": "https://developer-docs.amazon.com/sp-api/",
        },
    },
    "shopify": {
        "listing": {
            "api_objects": ["Admin GraphQL Product APIs", "Inventory APIs"],
            "required_authorizations": ["store_app_installed", "write_products", "write_inventory"],
            "execution_surfaces": ["Shopify Admin API", "Shopify Admin UI", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_product_or_inventory_write",
            "official_source_url": "https://shopify.dev/docs/api/admin-graphql",
        },
        "promotion": {
            "api_objects": ["Discount Code APIs", "Automatic Discount APIs", "Shopify Functions"],
            "required_authorizations": ["store_app_installed", "write_discounts", "discount_function_if_custom"],
            "execution_surfaces": ["Admin API discounts", "Shopify Admin UI", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_discount_activate",
            "official_source_url": "https://shopify.dev/docs/apps/build/discounts",
        },
        "coupon": {
            "api_objects": ["Discount Code Basic", "Free Shipping Discount", "Automatic Discounts"],
            "required_authorizations": ["store_app_installed", "write_discounts"],
            "execution_surfaces": ["Admin API discounts", "Shopify Admin UI", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_coupon_or_discount_publish",
            "official_source_url": "https://shopify.dev/docs/api/admin-graphql",
        },
        "ads": {
            "api_objects": ["Meta Ads", "Google Ads", "TikTok Ads"],
            "required_authorizations": ["external_ads_account", "business_or_ad_account_permission"],
            "execution_surfaces": ["external_ads_backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_ad_launch_or_budget_change",
            "official_source_url": "https://shopify.dev/docs/api/usage/access-scopes",
        },
        "reporting": {
            "api_objects": ["Orders API", "Analytics / report export", "Webhooks"],
            "required_authorizations": ["store_app_installed", "read_orders", "read_products"],
            "execution_surfaces": ["Shopify Admin API", "Webhooks", "report_import"],
            "final_submission_gate": "read_only_no_external_submit",
            "official_source_url": "https://shopify.dev/docs/api/usage/access-scopes",
        },
    },
    "shopee": {
        "listing": {
            "api_objects": ["Product API", "Item API", "Inventory / stock update"],
            "required_authorizations": ["shop_access_token", "merchant_or_shop_permission"],
            "execution_surfaces": ["Shopee Open Platform", "Seller Center", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_item_or_stock_write",
            "official_source_url": "https://open.shopee.com/documents",
        },
        "promotion": {
            "api_objects": ["Discount API", "Add-on Deal", "Bundle Deal"],
            "required_authorizations": ["shop_access_token", "voucher_or_discount_permission", "country_site_verified"],
            "execution_surfaces": ["Shopee Open Platform", "Seller Center campaign backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_campaign_or_discount_submit",
            "official_source_url": "https://open.shopee.com/documents",
        },
        "coupon": {
            "api_objects": ["Voucher API", "Shop Voucher", "Free Shipping Voucher"],
            "required_authorizations": ["shop_access_token", "voucher_permission", "country_site_verified"],
            "execution_surfaces": ["Voucher API", "Seller Center voucher backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_voucher_publish",
            "official_source_url": "https://open.shopee.com/documents",
        },
        "ads": {
            "api_objects": ["Shopee Ads", "Keyword Ads", "Discovery Ads"],
            "required_authorizations": ["ads_account_if_ads", "shop_or_merchant_permission"],
            "execution_surfaces": ["Shopee Ads backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_ad_launch_or_budget_change",
            "official_source_url": "https://open.shopee.com/documents",
        },
        "reporting": {
            "api_objects": ["Order API", "Returns API", "Seller reports"],
            "required_authorizations": ["shop_access_token", "orders_or_report_permission"],
            "execution_surfaces": ["Shopee Open Platform", "Seller Center reports", "report_import"],
            "final_submission_gate": "read_only_no_external_submit",
            "official_source_url": "https://open.shopee.com/documents",
        },
    },
    "lazada": {
        "listing": {
            "api_objects": ["Product API", "Feed API", "Inventory update"],
            "required_authorizations": ["seller_authorization_code", "seller_access_token"],
            "execution_surfaces": ["Lazada Open Platform", "Seller Center", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_product_or_stock_write",
            "official_source_url": "https://open.lazada.com/doc/doc.htm",
        },
        "promotion": {
            "api_objects": ["Flexi Combo", "Seller Voucher", "Campaign backend"],
            "required_authorizations": ["seller_access_token", "promotion_permission", "country_site_verified"],
            "execution_surfaces": ["Lazada Open Platform", "Seller Center campaign backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_campaign_submit",
            "official_source_url": "https://open.lazada.com/doc/doc.htm",
        },
        "coupon": {
            "api_objects": ["Voucher API", "Seller Voucher", "Free Shipping promotion"],
            "required_authorizations": ["seller_access_token", "voucher_permission", "country_site_verified"],
            "execution_surfaces": ["Seller Voucher API", "Seller Center voucher backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_voucher_activate",
            "official_source_url": "https://open.lazada.com/doc/doc.htm",
        },
        "ads": {
            "api_objects": ["Lazada Sponsored Solutions", "Sponsored Search", "Discovery ads"],
            "required_authorizations": ["ads_account_if_ads", "seller_ads_permission"],
            "execution_surfaces": ["Lazada Ads backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_ad_launch_or_budget_change",
            "official_source_url": "https://open.lazada.com/doc/doc.htm",
        },
        "reporting": {
            "api_objects": ["Order API", "Finance / reports", "Seller Center export"],
            "required_authorizations": ["seller_access_token", "orders_or_report_permission"],
            "execution_surfaces": ["Lazada Open Platform", "Seller Center reports", "report_import"],
            "final_submission_gate": "read_only_no_external_submit",
            "official_source_url": "https://open.lazada.com/doc/doc.htm",
        },
    },
    "walmart": {
        "listing": {
            "api_objects": ["Items API", "Inventory API", "Price API"],
            "required_authorizations": ["marketplace_seller_authorization"],
            "execution_surfaces": ["Walmart Marketplace API", "Seller Center", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_item_price_or_stock_write",
            "official_source_url": "https://developer.walmart.com/us-marketplace/docs",
        },
        "promotion": {
            "api_objects": ["Promotions API", "Price Promotions", "Seller Center deals"],
            "required_authorizations": ["marketplace_seller_authorization", "seller_center_access"],
            "execution_surfaces": ["Marketplace promotions", "Seller Center", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_promotion_or_price_change",
            "official_source_url": "https://developer.walmart.com/us-marketplace/docs",
        },
        "coupon": {
            "api_objects": ["Marketplace Promotions", "Price Discount", "Seller Center offer"],
            "required_authorizations": ["marketplace_seller_authorization", "seller_center_access"],
            "execution_surfaces": ["Marketplace API", "Seller Center", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_offer_discount_submit",
            "official_source_url": "https://developer.walmart.com/us-marketplace/docs",
        },
        "ads": {
            "api_objects": ["Walmart Connect", "Sponsored Products", "Search Brand Amplifier"],
            "required_authorizations": ["walmart_connect_authorization", "ads_account_permission"],
            "execution_surfaces": ["Walmart Connect", "Ads API", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_walmart_connect_launch_or_budget_change",
            "official_source_url": "https://developer.walmart.com/us-marketplace/docs",
        },
        "reporting": {
            "api_objects": ["Orders API", "Returns API", "Reports API"],
            "required_authorizations": ["marketplace_seller_authorization"],
            "execution_surfaces": ["Walmart Marketplace API", "Seller Center reports", "report_import"],
            "final_submission_gate": "read_only_no_external_submit",
            "official_source_url": "https://developer.walmart.com/us-marketplace/docs",
        },
    },
    "etsy": {
        "listing": {
            "api_objects": ["Listings API", "Inventory API", "Shop sections"],
            "required_authorizations": ["etsy_app_oauth", "listings_w_scope"],
            "execution_surfaces": ["Etsy Open API v3", "Shop Manager", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_listing_or_inventory_write",
            "official_source_url": "https://developers.etsy.com/documentation/",
        },
        "promotion": {
            "api_objects": ["Sales and Coupons", "Shop sale", "Thank-you coupon"],
            "required_authorizations": ["etsy_app_oauth", "shop_manager_access"],
            "execution_surfaces": ["Shop Manager sales/coupons", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_sale_or_coupon_publish",
            "official_source_url": "https://developers.etsy.com/documentation/",
        },
        "coupon": {
            "api_objects": ["Coupon", "Abandoned cart offer", "Thank-you coupon"],
            "required_authorizations": ["etsy_app_oauth", "shop_manager_access"],
            "execution_surfaces": ["Shop Manager coupon backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_coupon_publish",
            "official_source_url": "https://developers.etsy.com/documentation/",
        },
        "ads": {
            "api_objects": ["Etsy Ads", "Offsite Ads review", "Ad budget backend"],
            "required_authorizations": ["etsy_ads_access_if_ads", "shop_manager_access"],
            "execution_surfaces": ["Etsy Ads backend", "Shop Manager", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_etsy_ads_budget_change",
            "official_source_url": "https://developers.etsy.com/documentation/",
        },
        "reporting": {
            "api_objects": ["Receipts API", "Payments API", "Shop data"],
            "required_authorizations": ["etsy_app_oauth", "transactions_or_payments_scope"],
            "execution_surfaces": ["Etsy Open API v3", "Shop Manager reports", "report_import"],
            "final_submission_gate": "read_only_no_external_submit",
            "official_source_url": "https://developers.etsy.com/documentation/",
        },
    },
    "ebay": {
        "listing": {
            "api_objects": ["Sell Inventory API", "Offer API", "Account policies"],
            "required_authorizations": ["sell_inventory_scope", "seller_account_authorization"],
            "execution_surfaces": ["eBay Sell APIs", "Seller Hub", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_offer_or_inventory_write",
            "official_source_url": "https://developer.ebay.com/api-docs/sell/static/sell-landing.html",
        },
        "promotion": {
            "api_objects": ["Sell Marketing Promotions", "Markdown Sale", "Order Discount"],
            "required_authorizations": ["sell_marketing_scope", "seller_hub_access"],
            "execution_surfaces": ["Sell Marketing API", "Seller Hub promotions", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_promotion_publish",
            "official_source_url": "https://developer.ebay.com/api-docs/sell/marketing/static/overview.html",
        },
        "coupon": {
            "api_objects": ["Coupon", "Markdown sale event", "Promotions Manager"],
            "required_authorizations": ["sell_marketing_scope", "seller_hub_access"],
            "execution_surfaces": ["Sell Marketing API", "Seller Hub", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_coupon_or_markdown_publish",
            "official_source_url": "https://developer.ebay.com/api-docs/sell/marketing/static/overview.html",
        },
        "ads": {
            "api_objects": ["Promoted Listings", "Campaign", "Ad rate / budget"],
            "required_authorizations": ["sell_marketing_scope", "ads_campaign_permission_if_ads"],
            "execution_surfaces": ["Sell Marketing API", "Promoted Listings", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_promoted_listing_launch_or_budget_change",
            "official_source_url": "https://developer.ebay.com/api-docs/sell/marketing/static/overview.html",
        },
        "reporting": {
            "api_objects": ["Sell Fulfillment API", "Finances API", "Analytics / reports"],
            "required_authorizations": ["sell_fulfillment_scope", "sell_finances_scope"],
            "execution_surfaces": ["eBay Sell APIs", "Seller Hub reports", "report_import"],
            "final_submission_gate": "read_only_no_external_submit",
            "official_source_url": "https://developer.ebay.com/api-docs/sell/static/sell-landing.html",
        },
    },
    "woocommerce": {
        "listing": {
            "api_objects": ["Products API", "Variations API", "Stock status"],
            "required_authorizations": ["rest_api_key_or_plugin_access", "write_products"],
            "execution_surfaces": ["WooCommerce REST API", "WordPress admin", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_product_or_stock_write",
            "official_source_url": "https://developer.woocommerce.com/docs/apis/rest-api/",
        },
        "promotion": {
            "api_objects": ["Coupons API", "Sale price", "Free shipping method"],
            "required_authorizations": ["rest_api_key_or_plugin_access", "coupon_or_product_write_scope"],
            "execution_surfaces": ["WooCommerce REST API", "WordPress admin", "plugin_backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_coupon_or_sale_price_publish",
            "official_source_url": "https://developer.woocommerce.com/docs/apis/rest-api/",
        },
        "coupon": {
            "api_objects": ["Coupons API", "Free shipping coupon", "Usage restrictions"],
            "required_authorizations": ["rest_api_key_or_plugin_access", "coupon_write_scope"],
            "execution_surfaces": ["WooCommerce REST API", "WordPress admin", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_coupon_publish",
            "official_source_url": "https://developer.woocommerce.com/docs/apis/rest-api/",
        },
        "ads": {
            "api_objects": ["Meta Ads", "Google Ads", "TikTok Ads"],
            "required_authorizations": ["external_ads_account", "business_or_ad_account_permission"],
            "execution_surfaces": ["external_ads_backend", "isolated_cloud_plugin"],
            "final_submission_gate": "owner_confirmation_before_ad_launch_or_budget_change",
            "official_source_url": "https://developer.woocommerce.com/docs/apis/rest-api/",
        },
        "reporting": {
            "api_objects": ["Orders API", "Refunds API", "Reports API"],
            "required_authorizations": ["rest_api_key_or_plugin_access", "read_orders"],
            "execution_surfaces": ["WooCommerce REST API", "WordPress admin reports", "report_import"],
            "final_submission_gate": "read_only_no_external_submit",
            "official_source_url": "https://developer.woocommerce.com/docs/apis/rest-api/",
        },
    },
}


PLATFORM_ACTIVITY_MECHANISM_DETAILS: dict[str, list[dict[str, Any]]] = {
    "tiktok_shop": [
        {
            "activity_type": "product_discount",
            "display": "Product Discount",
            "stacking": ["platform_campaign", "shop_coupon", "creator_commission", "ad_budget"],
            "guardrails": ["margin_floor", "stock_sla", "seller_center_rule"],
            "api_objects": ["Product Discount API"],
        },
        {
            "activity_type": "flash_deal",
            "display": "Flash Deal",
            "stacking": ["platform_campaign", "limited_time_price", "inventory_reserve"],
            "guardrails": ["campaign_window", "stock_lock", "price_floor"],
            "api_objects": ["Flash Deal API", "Seller Center campaign backend"],
        },
        {
            "activity_type": "shop_coupon",
            "display": "Coupon / Voucher",
            "stacking": ["product_discount", "platform_subsidy", "creator_coupon"],
            "guardrails": ["coupon_budget", "margin_after_coupon", "eligibility"],
            "api_objects": ["Coupon API", "Voucher API"],
        },
        {
            "activity_type": "ads_test_plan",
            "display": "Ads budget / GMV Max",
            "stacking": ["promotion_price", "creative_count", "break_even_roas"],
            "guardrails": ["daily_budget_cap", "stop_loss_line", "ad_account_owner"],
            "api_objects": ["TikTok Business API", "Ads Manager"],
        },
    ],
    "shein": [
        {
            "activity_type": "campaign_price",
            "display": "Campaign Price",
            "stacking": ["platform_campaign", "stock_reserve", "site_store_model"],
            "guardrails": ["price_floor", "reserved_stock", "fulfillment_sla"],
            "api_objects": ["Seller Hub campaign backend"],
        },
        {
            "activity_type": "inventory_campaign",
            "display": "Inventory Campaign",
            "stacking": ["site_campaign_window", "semi_managed_route", "local_or_crossborder_rule"],
            "guardrails": ["inventory_commit", "return_risk", "site_rule"],
            "api_objects": ["SHEIN Open Platform", "Seller Hub"],
        },
    ],
    "amazon": [
        {
            "activity_type": "coupon",
            "display": "Coupon",
            "stacking": ["buy_box_price", "deal_price", "ads_acos"],
            "guardrails": ["seller_central_rule", "fee_margin", "marketplace"],
            "api_objects": ["Seller Central Coupons"],
        },
        {
            "activity_type": "amazon_ads",
            "display": "Amazon Ads",
            "stacking": ["coupon_or_deal", "acos_limit", "inventory_sla"],
            "guardrails": ["daily_budget_cap", "acos_stop_loss", "ads_profile"],
            "api_objects": ["Amazon Ads API"],
        },
    ],
    "shopify": [
        {
            "activity_type": "discount_code",
            "display": "Discount Code",
            "stacking": ["automatic_discount", "free_shipping", "app_discount"],
            "guardrails": ["write_discounts_scope", "combination_rule", "margin_floor"],
            "api_objects": ["Discount Code APIs"],
        },
        {
            "activity_type": "automatic_discount",
            "display": "Automatic Discount",
            "stacking": ["discount_combination", "bundle", "free_shipping"],
            "guardrails": ["write_discounts_scope", "discount_function", "tax_shipping"],
            "api_objects": ["Automatic Discount APIs", "Shopify Functions"],
        },
    ],
    "shopee": [
        {
            "activity_type": "shop_voucher",
            "display": "Shop Voucher",
            "stacking": ["platform_voucher", "product_discount", "free_shipping_voucher"],
            "guardrails": ["voucher_budget", "country_site_rule", "margin_after_voucher"],
            "api_objects": ["Voucher API", "Seller Center voucher"],
        },
        {
            "activity_type": "product_discount",
            "display": "Discount Promotion",
            "stacking": ["shop_voucher", "bundle_deal", "ads_budget"],
            "guardrails": ["price_floor", "stock_sla", "commission_shipping_fee"],
            "api_objects": ["Discount API", "Seller Center discount"],
        },
        {
            "activity_type": "bundle_deal",
            "display": "Bundle / Add-on Deal",
            "stacking": ["voucher", "free_shipping", "campaign_window"],
            "guardrails": ["bundle_margin", "sku_stock", "country_site_rule"],
            "api_objects": ["Bundle Deal", "Add-on Deal"],
        },
        {
            "activity_type": "shopee_ads",
            "display": "Shopee Ads",
            "stacking": ["voucher_discount", "keyword_bid", "break_even_roas"],
            "guardrails": ["daily_budget_cap", "stop_loss_line", "ads_account_permission"],
            "api_objects": ["Shopee Ads", "Keyword Ads"],
        },
    ],
    "lazada": [
        {
            "activity_type": "seller_voucher",
            "display": "Seller Voucher",
            "stacking": ["platform_campaign", "product_discount", "free_shipping"],
            "guardrails": ["voucher_permission", "country_site_rule", "margin_after_voucher"],
            "api_objects": ["Voucher API", "Seller Voucher"],
        },
        {
            "activity_type": "flexi_combo",
            "display": "Flexi Combo / Bundle",
            "stacking": ["seller_voucher", "campaign_price", "ads_budget"],
            "guardrails": ["combo_margin", "stock_sla", "delivery_sla"],
            "api_objects": ["Flexi Combo", "Seller Center campaign"],
        },
        {
            "activity_type": "lazada_ads",
            "display": "Sponsored Solutions",
            "stacking": ["voucher_discount", "sponsored_search", "break_even_roas"],
            "guardrails": ["daily_budget_cap", "stop_loss_line", "seller_ads_permission"],
            "api_objects": ["Sponsored Search", "Lazada Ads backend"],
        },
    ],
    "walmart": [
        {
            "activity_type": "price_discount",
            "display": "Price Discount / Promotion",
            "stacking": ["marketplace_price_rule", "buy_box_price", "walmart_connect_ads"],
            "guardrails": ["price_floor", "fee_margin", "seller_authorization"],
            "api_objects": ["Promotions API", "Price API"],
        },
        {
            "activity_type": "deal",
            "display": "Marketplace Deal",
            "stacking": ["discount_price", "stock_sla", "fulfillment_sla"],
            "guardrails": ["deal_eligibility", "inventory_sla", "buy_box_check"],
            "api_objects": ["Seller Center deals", "Marketplace promotion"],
        },
        {
            "activity_type": "walmart_connect_ads",
            "display": "Walmart Connect Ads",
            "stacking": ["marketplace_promotion", "sponsored_products", "budget_cap"],
            "guardrails": ["walmart_connect_authorization", "daily_budget_cap", "stop_loss_line"],
            "api_objects": ["Walmart Connect", "Sponsored Products"],
        },
    ],
    "etsy": [
        {
            "activity_type": "shop_sale",
            "display": "Shop Sale",
            "stacking": ["coupon", "free_shipping", "offsite_ads_fee"],
            "guardrails": ["item_margin", "shipping_profile", "shop_manager_access"],
            "api_objects": ["Sales and Coupons", "Shop Manager sale"],
        },
        {
            "activity_type": "coupon",
            "display": "Coupon / Thank-you Coupon",
            "stacking": ["shop_sale", "abandoned_cart_offer", "free_shipping"],
            "guardrails": ["coupon_scope", "usage_limit", "margin_after_coupon"],
            "api_objects": ["Coupon", "Thank-you coupon"],
        },
        {
            "activity_type": "etsy_ads",
            "display": "Etsy Ads / Offsite Ads review",
            "stacking": ["shop_sale", "coupon", "ad_budget"],
            "guardrails": ["etsy_ads_budget", "offsite_ads_fee", "listing_margin"],
            "api_objects": ["Etsy Ads", "Offsite Ads review"],
        },
    ],
    "ebay": [
        {
            "activity_type": "markdown_sale",
            "display": "Markdown Sale",
            "stacking": ["order_discount", "coupon", "promoted_listings"],
            "guardrails": ["marketing_scope", "price_floor", "seller_hub_access"],
            "api_objects": ["Sell Marketing Promotions", "Markdown Sale"],
        },
        {
            "activity_type": "coupon",
            "display": "Coupon / Order Discount",
            "stacking": ["markdown_sale", "best_offer", "promoted_listings"],
            "guardrails": ["promotion_stack", "fee_margin", "seller_account_scope"],
            "api_objects": ["Coupon", "Order Discount"],
        },
        {
            "activity_type": "promoted_listings",
            "display": "Promoted Listings",
            "stacking": ["markdown_sale", "coupon", "ad_rate"],
            "guardrails": ["ad_rate_budget", "campaign_permission", "stop_loss_line"],
            "api_objects": ["Promoted Listings", "Campaign"],
        },
    ],
    "woocommerce": [
        {
            "activity_type": "coupon",
            "display": "Coupon",
            "stacking": ["sale_price", "free_shipping", "usage_restrictions"],
            "guardrails": ["coupon_write_scope", "margin_after_coupon", "rollback_plan"],
            "api_objects": ["Coupons API", "Usage restrictions"],
        },
        {
            "activity_type": "sale_price",
            "display": "Sale Price",
            "stacking": ["coupon", "bundle_plugin", "shipping_zone"],
            "guardrails": ["product_write_scope", "price_floor", "stock_status"],
            "api_objects": ["Products API", "Variations API"],
        },
        {
            "activity_type": "free_shipping",
            "display": "Free Shipping",
            "stacking": ["coupon", "shipping_zone", "minimum_order"],
            "guardrails": ["shipping_zone", "carrier_cost", "margin_after_shipping"],
            "api_objects": ["Coupons API", "Shipping methods"],
        },
    ],
}


DEFAULT_PLATFORM_CAPABILITIES: list[dict[str, Any]] = [
    {
        "channel_id": "tiktok_shop",
        "label": "TikTok Shop",
        "sites": ["US", "GB", "DE", "FR", "IT", "ES", "IE", "MX", "BR", "SG", "MY", "TH", "VN", "PH", "ID"],
        "listing": "api_or_cloud_plugin_after_confirmation",
        "order": "api_read_after_store_authorization",
        "shipment": "api_or_erp_callback_after_mapping",
        "settlement": "api_or_report_import",
        "discount": "api_or_seller_center_draft",
        "promotion": "seller_center_or_campaign_backend_draft",
        "ads": "separate_business_api_and_ad_account",
        "official_source_url": "https://partner.tiktokshop.com/docv2/",
        "notes": "站点、店铺模式、广告账号和广告归属主体必须分开；活动/广告真实提交仍进确认队列。",
    },
    {
        "channel_id": "shein",
        "label": "SHEIN Marketplace",
        "sites": ["US", "GB", "DE", "FR", "IT", "ES", "BR", "MX"],
        "listing": "api_or_cloud_plugin_after_confirmation",
        "order": "api_read_after_store_authorization",
        "shipment": "api_or_erp_callback_after_mapping",
        "settlement": "api_or_report_import",
        "discount": "platform_rule_draft_then_confirmation",
        "promotion": "platform_campaign_backend_draft",
        "ads": "separate_ads_or_platform_backend",
        "official_source_url": "https://open.sheincorp.com/",
        "notes": "本土、跨境半托、TeeLab 联名运营和平台官方全托管识别标签不能混用。",
    },
    {
        "channel_id": "shopee",
        "label": "Shopee",
        "sites": ["SG", "MY", "TH", "VN", "PH", "ID", "TW", "BR"],
        "listing": "api_or_seller_center_draft",
        "order": "api_read_after_store_authorization",
        "shipment": "api_or_erp_callback_after_mapping",
        "settlement": "api_or_report_import",
        "discount": "seller_center_draft_then_confirmation",
        "promotion": "seller_center_campaign_draft",
        "ads": "separate_ads_account_or_backend",
        "official_source_url": "https://open.shopee.com/documents",
        "notes": "东南亚不能合并成一个站点；每个国家站点和店铺身份单独判断。",
    },
    {
        "channel_id": "lazada",
        "label": "Lazada",
        "sites": ["SG", "MY", "TH", "VN", "PH", "ID"],
        "listing": "api_or_seller_center_draft",
        "order": "api_read_after_store_authorization",
        "shipment": "api_or_erp_callback_after_mapping",
        "settlement": "api_or_report_import",
        "discount": "seller_center_draft_then_confirmation",
        "promotion": "seller_center_campaign_draft",
        "ads": "separate_ads_account_or_backend",
        "official_source_url": "https://open.lazada.com/doc/doc.htm",
        "notes": "按国家站点和店铺身份拆分；活动后台能力不足时只生成草稿。",
    },
    {
        "channel_id": "amazon",
        "label": "Amazon",
        "sites": ["US", "CA", "MX", "GB", "DE", "FR", "IT", "ES", "NL", "SE", "PL", "JP", "IN", "AU", "AE", "SA"],
        "listing": "sp_api_after_seller_authorization",
        "order": "sp_api_after_seller_authorization",
        "shipment": "sp_api_or_fba_mapping",
        "settlement": "sp_api_reports_or_finance_report",
        "discount": "seller_central_or_api_draft",
        "promotion": "seller_central_draft_then_confirmation",
        "ads": "separate_amazon_ads_api",
        "official_source_url": "https://developer-docs.amazon.com/sp-api/",
        "notes": "SP-API 与 Amazon Ads API 分开授权；站点和卖家授权不能混用。",
    },
    {
        "channel_id": "walmart",
        "label": "Walmart Marketplace",
        "sites": ["US", "CA", "MX"],
        "listing": "marketplace_api_after_seller_authorization",
        "order": "marketplace_api_after_seller_authorization",
        "shipment": "marketplace_api_or_erp_callback",
        "settlement": "marketplace_reports_or_report_import",
        "discount": "seller_center_or_marketplace_api_draft",
        "promotion": "seller_center_or_marketplace_api_draft",
        "ads": "separate_walmart_connect_or_ads_api",
        "official_source_url": "https://developer.walmart.com/us-marketplace/docs",
        "notes": "Marketplace seller APIs and Walmart Connect advertising require separate authorization.",
    },
    {
        "channel_id": "walmart",
        "label": "Walmart marketplace promotions and ads",
        "countries": ["US", "CA", "MX"],
        "store_models": ["marketplace_seller", "local_store"],
        "activity_types": ["promotion", "price_discount", "deal", "walmart_connect_ads", "campaign"],
        "stacking_rules": ["marketplace_price_rule_check", "buy_box_price_check", "walmart_connect_budget_check", "stock_and_fulfillment_sla_check"],
        "api_boundary": "marketplace_api_or_seller_center_draft",
        "ads_boundary": "separate_walmart_connect_or_ads_api",
        "execution_mode": "draft_then_confirmation_or_isolated_cloud_plugin",
        "margin_guardrail": "price_fee_shipping_and_ad_cost_check",
        "inventory_guardrail": "inventory_and_fulfillment_sla_required",
        "confirmation_required": True,
        "official_source_url": "https://developer.walmart.com/us-marketplace/docs",
        "last_checked_at": "2026-06-27",
        "notes": "Marketplace seller APIs and Walmart Connect advertising are separate authorization surfaces.",
    },
    {
        "channel_id": "etsy",
        "label": "Etsy",
        "sites": ["GLOBAL"],
        "listing": "open_api_v3_after_shop_authorization",
        "order": "open_api_receipts_after_shop_authorization",
        "shipment": "open_api_or_shop_manager_callback",
        "settlement": "payments_api_or_report_import",
        "discount": "shop_manager_sale_coupon_draft",
        "promotion": "shop_manager_sale_coupon_draft_then_confirmation",
        "ads": "separate_etsy_ads_or_offsite_ads_backend",
        "official_source_url": "https://developers.etsy.com/documentation/",
        "notes": "Etsy Open API scopes, Shop Manager promotions, Etsy Ads and Offsite Ads are separate surfaces. Listing publish, sales/coupons and ads budget changes require confirmation.",
    },
    {
        "channel_id": "ebay",
        "label": "eBay",
        "sites": ["GLOBAL"],
        "listing": "sell_inventory_api_after_seller_authorization",
        "order": "sell_fulfillment_api_after_seller_authorization",
        "shipment": "sell_fulfillment_or_erp_callback",
        "settlement": "sell_finances_or_report_import",
        "discount": "marketing_api_or_seller_hub_draft",
        "promotion": "marketing_api_promotions_draft_then_confirmation",
        "ads": "separate_promoted_listings_marketing_api",
        "official_source_url": "https://developer.ebay.com/api-docs/sell/static/sell-landing.html",
        "notes": "eBay Inventory, Fulfillment, Finances and Marketing APIs are separate scopes. Promotions, Promoted Listings and budget changes require confirmation.",
    },
    {
        "channel_id": "shopify",
        "label": "Shopify",
        "sites": ["GLOBAL"],
        "listing": "admin_api_after_store_authorization",
        "order": "admin_api_or_webhook",
        "shipment": "admin_api_or_fulfillment_callback",
        "settlement": "report_import_or_payment_mapping",
        "discount": "admin_api_or_discount_function",
        "promotion": "app_or_theme_draft_then_confirmation",
        "ads": "separate_meta_google_tiktok_ads",
        "official_source_url": "https://shopify.dev/docs/apps/build/discounts",
        "notes": "每个独立站是一家店铺授权；广告账户不等同 Admin API。",
    },
    {
        "channel_id": "woocommerce",
        "label": "WooCommerce",
        "sites": ["GLOBAL"],
        "listing": "rest_api_after_store_authorization",
        "order": "rest_api_or_webhook",
        "shipment": "rest_api_or_fulfillment_callback",
        "settlement": "report_import_or_payment_mapping",
        "discount": "rest_api_coupons_or_store_backend_draft",
        "promotion": "plugin_or_store_backend_draft_then_confirmation",
        "ads": "separate_meta_google_tiktok_ads",
        "official_source_url": "https://developer.woocommerce.com/docs/apis/rest-api/",
        "notes": "Each WooCommerce store has separate REST API keys/webhooks. Ads and marketplace campaigns stay outside store API authorization.",
    },
    {
        "channel_id": "meta_ads",
        "label": "Meta Ads / Facebook Marketing",
        "sites": ["GLOBAL"],
        "listing": "not_a_listing_store",
        "order": "not_an_order_store",
        "shipment": "not_a_shipment_store",
        "settlement": "ad_spend_report_import",
        "discount": "not_a_store_discount_api",
        "promotion": "campaign_draft_after_business_authorization",
        "ads": "marketing_api_after_business_and_ad_account_authorization",
        "official_source_url": "https://developers.facebook.com/docs/marketing-apis/",
        "notes": "Ad accounts, pixels, catalogs and Business permissions are separate from store ERP authorization. Budget and campaign changes require confirmation.",
    },
]


DEFAULT_PLATFORM_ACTIVITY_RULES: list[dict[str, Any]] = [
    {
        "channel_id": "tiktok_shop",
        "label": "TikTok Shop promotions",
        "countries": ["US", "GB", "DE", "FR", "IT", "ES", "IE", "MX", "BR", "SG", "MY", "TH", "VN", "PH", "ID"],
        "store_models": ["local_store", "cross_border", "tiktok_accu_local", "platform_co_ops", "teelab_owned"],
        "activity_types": ["platform_campaign", "product_discount", "shop_coupon", "live_coupon", "creator_coupon", "free_shipping"],
        "stacking_rules": ["platform_rule_first", "merchant_subsidy_margin_check", "creator_commission_check", "ad_roas_check"],
        "api_boundary": "promotion_api_or_seller_center_draft",
        "ads_boundary": "separate_tiktok_business_api_and_ad_account",
        "execution_mode": "draft_then_confirmation_or_isolated_cloud_plugin",
        "margin_guardrail": "min_margin_and_break_even_roas_required",
        "inventory_guardrail": "campaign_stock_and_sla_required",
        "confirmation_required": True,
        "official_source_url": "https://partner.tiktokshop.com/docv2/",
        "last_checked_at": "2026-06-26",
        "notes": "TikTok Shop promotions, Seller Center activity drafts, ads, and ad ownership must stay separated by site and store identity.",
    },
    {
        "channel_id": "shein",
        "label": "SHEIN marketplace campaigns",
        "countries": ["US", "GB", "DE", "FR", "IT", "ES", "BR", "MX"],
        "store_models": ["marketplace_seller", "local_store", "cross_border", "platform_co_ops", "teelab_owned"],
        "activity_types": ["platform_campaign", "product_discount", "campaign_price", "inventory_campaign"],
        "stacking_rules": ["platform_eligibility_check", "campaign_price_floor", "stock_and_fulfillment_check"],
        "api_boundary": "open_platform_or_backend_draft",
        "ads_boundary": "separate_ads_or_platform_backend",
        "execution_mode": "draft_then_confirmation",
        "margin_guardrail": "campaign_price_floor_and_fee_check",
        "inventory_guardrail": "reserved_stock_and_sla_required",
        "confirmation_required": True,
        "official_source_url": "https://open.sheincorp.com/",
        "last_checked_at": "2026-06-26",
        "notes": "SHEIN semi-managed, local, cross-border, TeeLab co-ops, and official full managed labels must not be mixed.",
    },
    {
        "channel_id": "shopee",
        "label": "Shopee campaigns",
        "countries": ["SG", "MY", "TH", "VN", "PH", "ID", "TW", "BR"],
        "store_models": ["local_store", "cross_border", "marketplace_seller", "platform_co_ops"],
        "activity_types": ["campaign", "shop_voucher", "product_discount", "bundle_deal", "free_shipping"],
        "stacking_rules": ["voucher_stack_check", "platform_subsidy_check", "commission_and_shipping_check"],
        "api_boundary": "open_platform_or_seller_center_draft",
        "ads_boundary": "separate_ads_backend_or_account",
        "execution_mode": "draft_then_confirmation_or_isolated_cloud_plugin",
        "margin_guardrail": "voucher_after_margin_required",
        "inventory_guardrail": "campaign_stock_and_delivery_sla_required",
        "confirmation_required": True,
        "official_source_url": "https://open.shopee.com/documents",
        "last_checked_at": "2026-06-26",
        "notes": "Shopee SG / MY / TH / VN / PH / ID sites must be split by country; campaign execution should not be treated as one regional store.",
    },
    {
        "channel_id": "lazada",
        "label": "Lazada campaigns",
        "countries": ["SG", "MY", "TH", "VN", "PH", "ID"],
        "store_models": ["local_store", "cross_border", "marketplace_seller", "platform_co_ops"],
        "activity_types": ["campaign", "seller_voucher", "product_discount", "bundle", "free_shipping"],
        "stacking_rules": ["country_site_rule_check", "voucher_stack_check", "ad_cost_and_fee_check"],
        "api_boundary": "open_platform_or_seller_center_draft",
        "ads_boundary": "separate_ads_backend_or_account",
        "execution_mode": "draft_then_confirmation_or_isolated_cloud_plugin",
        "margin_guardrail": "discount_fee_and_ad_cost_check",
        "inventory_guardrail": "stock_and_fulfillment_sla_required",
        "confirmation_required": True,
        "official_source_url": "https://open.lazada.com/doc/doc.htm",
        "last_checked_at": "2026-06-26",
        "notes": "Lazada campaign and promotion coverage can vary by country site, so unresolved paths stay as drafts.",
    },
    {
        "channel_id": "amazon",
        "label": "Amazon promotions and ads",
        "countries": ["US", "CA", "MX", "GB", "DE", "FR", "IT", "ES", "NL", "SE", "PL", "JP", "IN", "AU", "AE", "SA"],
        "store_models": ["marketplace_seller", "local_store", "cross_border"],
        "activity_types": ["coupon", "promotion", "deal", "price_discount", "amazon_ads"],
        "stacking_rules": ["seller_central_rule_check", "buy_box_price_check", "amazon_ads_budget_check"],
        "api_boundary": "sp_api_reports_or_seller_central_draft",
        "ads_boundary": "separate_amazon_ads_api",
        "execution_mode": "draft_then_confirmation",
        "margin_guardrail": "buy_box_price_fee_and_acos_check",
        "inventory_guardrail": "fba_or_mfn_stock_sla_required",
        "confirmation_required": True,
        "official_source_url": "https://developer-docs.amazon.com/sp-api/",
        "last_checked_at": "2026-06-26",
        "notes": "Amazon SP-API and Amazon Ads API are separate authorization surfaces.",
    },
    {
        "channel_id": "etsy",
        "label": "Etsy shop promotions and ads",
        "countries": ["GLOBAL"],
        "store_models": ["marketplace_seller", "self_store", "platform_co_ops"],
        "activity_types": ["shop_sale", "coupon", "thank_you_coupon", "abandoned_cart_offer", "etsy_ads", "offsite_ads_review"],
        "stacking_rules": ["sale_coupon_stack_check", "free_shipping_margin_check", "etsy_ads_budget_check", "offsite_ads_fee_check"],
        "api_boundary": "open_api_or_shop_manager_draft",
        "ads_boundary": "separate_etsy_ads_or_offsite_ads_backend",
        "execution_mode": "draft_then_confirmation_or_isolated_cloud_plugin",
        "margin_guardrail": "item_fee_shipping_offsite_ads_and_ad_budget_check",
        "inventory_guardrail": "listing_quantity_processing_time_and_shipping_profile_required",
        "confirmation_required": True,
        "official_source_url": "https://developers.etsy.com/documentation/",
        "last_checked_at": "2026-06-27",
        "notes": "Etsy listing, inventory and order APIs do not equal permission to create sales, coupons or change Etsy Ads budgets. Shop Manager changes require confirmation.",
    },
    {
        "channel_id": "ebay",
        "label": "eBay promotions and promoted listings",
        "countries": ["GLOBAL"],
        "store_models": ["marketplace_seller", "cross_border", "platform_co_ops"],
        "activity_types": ["order_discount", "markdown_sale", "coupon", "promoted_listings", "seller_hub_campaign"],
        "stacking_rules": ["marketing_promotion_stack_check", "best_offer_price_check", "promoted_listing_budget_check", "cross_border_fee_check"],
        "api_boundary": "marketing_api_or_seller_hub_draft",
        "ads_boundary": "separate_promoted_listings_marketing_api",
        "execution_mode": "draft_then_confirmation_or_isolated_cloud_plugin",
        "margin_guardrail": "price_fee_shipping_cross_border_and_ad_rate_check",
        "inventory_guardrail": "offer_quantity_fulfillment_policy_required",
        "confirmation_required": True,
        "official_source_url": "https://developer.ebay.com/api-docs/sell/marketing/static/overview.html",
        "last_checked_at": "2026-06-27",
        "notes": "eBay Sell Marketing API, Seller Hub promotions and Promoted Listings are separate from inventory/order sync. Campaign launch and budget changes require confirmation.",
    },
    {
        "channel_id": "shopify",
        "label": "Shopify discounts and campaigns",
        "countries": ["GLOBAL"],
        "store_models": ["independent_site", "platform_co_ops", "teelab_owned"],
        "activity_types": ["discount_code", "automatic_discount", "bundle", "free_shipping", "email_or_ads_campaign"],
        "stacking_rules": ["discount_combination_check", "app_scope_check", "payment_and_tax_check"],
        "api_boundary": "admin_api_or_discount_function_draft",
        "ads_boundary": "separate_meta_google_tiktok_ads",
        "execution_mode": "draft_then_confirmation",
        "margin_guardrail": "discount_combination_and_margin_check",
        "inventory_guardrail": "inventory_policy_and_fulfillment_check",
        "confirmation_required": True,
        "official_source_url": "https://shopify.dev/docs/apps/build/discounts",
        "last_checked_at": "2026-06-26",
        "notes": "Each independent store has its own app scopes; ads are not part of store Admin API authorization.",
    },
    {
        "channel_id": "woocommerce",
        "label": "WooCommerce coupons and store campaigns",
        "countries": ["GLOBAL"],
        "store_models": ["independent_site", "platform_co_ops", "teelab_owned"],
        "activity_types": ["coupon", "sale_price", "bundle", "free_shipping", "email_or_ads_campaign"],
        "stacking_rules": ["coupon_stack_check", "plugin_scope_check", "payment_tax_shipping_check"],
        "api_boundary": "rest_api_coupon_or_store_backend_draft",
        "ads_boundary": "separate_meta_google_tiktok_ads",
        "execution_mode": "draft_then_confirmation_or_isolated_cloud_plugin",
        "margin_guardrail": "coupon_sale_price_and_margin_check",
        "inventory_guardrail": "stock_status_and_fulfillment_check",
        "confirmation_required": True,
        "official_source_url": "https://developer.woocommerce.com/docs/apis/rest-api/",
        "last_checked_at": "2026-06-26",
        "notes": "WooCommerce coupons and sale prices depend on per-store REST keys/plugins; external ads stay separate.",
    },
    {
        "channel_id": "meta_ads",
        "label": "Meta Ads campaigns",
        "countries": ["GLOBAL"],
        "store_models": ["content_catalog", "platform_co_ops", "teelab_owned"],
        "activity_types": ["campaign", "ad_set", "ad", "catalog_sales", "budget_change", "creative_test"],
        "stacking_rules": ["business_permission_check", "ad_account_budget_check", "catalog_pixel_check", "store_margin_roas_check"],
        "api_boundary": "not_store_api",
        "ads_boundary": "marketing_api_after_business_and_ad_account_authorization",
        "execution_mode": "draft_then_confirmation_or_isolated_cloud_plugin",
        "margin_guardrail": "break_even_roas_and_daily_budget_required",
        "inventory_guardrail": "catalog_stock_and_fulfillment_check",
        "confirmation_required": True,
        "official_source_url": "https://developers.facebook.com/docs/marketing-apis/",
        "last_checked_at": "2026-06-26",
        "notes": "Meta Ads uses Business/ad-account permissions. It is not unlocked by store ERP binding and must be isolated per ad account.",
    },
]


def config_path(root: Path, filename: str) -> Path:
    return root / "config" / filename


def load_channel_route_requests(root: Path) -> list[dict[str, Any]]:
    payload = load_json(config_path(root, CHANNEL_ROUTE_REQUEST_FILENAME))
    if isinstance(payload, dict):
        items = payload.get("requests") or payload.get("routes") or []
    else:
        items = payload
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def load_platform_capabilities(root: Path) -> list[dict[str, Any]]:
    payload = load_json(config_path(root, PLATFORM_CAPABILITY_FILENAME))
    if isinstance(payload, dict):
        items = payload.get("capabilities") or payload.get("platforms") or []
    else:
        items = payload
    if isinstance(items, list) and items:
        return enrich_platform_capabilities([item for item in items if isinstance(item, dict)])
    return enrich_platform_capabilities(DEFAULT_PLATFORM_CAPABILITIES)


def load_platform_execution_capability_matrix(root: Path) -> list[dict[str, Any]]:
    payload = load_json(config_path(root, PLATFORM_CAPABILITY_FILENAME))
    if isinstance(payload, dict):
        items = payload.get("execution_capability_matrix") or payload.get("capability_matrix") or []
    else:
        items = []
    if isinstance(items, list) and items:
        return enrich_platform_execution_capability_matrix([item for item in items if isinstance(item, dict)])
    return enrich_platform_execution_capability_matrix(
        [execution_capability_entry_from_capability(item) for item in load_platform_capabilities(root)]
    )


def load_platform_developer_capability_config(root: Path) -> dict[str, Any]:
    payload = load_json(config_path(root, PLATFORM_CAPABILITY_FILENAME))
    if isinstance(payload, dict):
        return payload
    return {
        "last_checked_at": date.today().isoformat(),
        "source_review": {
            "checked_at": date.today().isoformat(),
            "default_boundary": "Platform APIs, seller backends, ads accounts, and backend task identities stay separated by route.",
            "official_sources": [],
            "implementation_policy": [
                "Map every action to channelId:countryCode:storeModel before planning.",
                "Keep external submissions, ad launches, price changes, and authorization changes behind confirmation.",
            ],
        },
        "execution_capability_matrix": [
            execution_capability_entry_from_capability(item) for item in DEFAULT_PLATFORM_CAPABILITIES
        ],
        "capabilities": DEFAULT_PLATFORM_CAPABILITIES,
    }


def save_platform_execution_capability_matrix(
    root: Path,
    matrix: Any,
    *,
    updated_by: str = "admin",
) -> dict[str, Any]:
    sanitized = sanitize_platform_execution_capability_matrix(matrix)
    payload = load_platform_developer_capability_config(root)
    payload["execution_capability_matrix"] = sanitized
    payload["matrix_last_updated_at"] = date.today().isoformat()
    payload["matrix_updated_by"] = str(updated_by or "admin")[:80]
    path = config_path(root, PLATFORM_CAPABILITY_FILENAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "path": str(path),
        "execution_capability_matrix": sanitized,
        "count": len(sanitized),
    }


def sanitize_platform_execution_capability_matrix(matrix: Any) -> list[dict[str, Any]]:
    if not isinstance(matrix, list):
        raise ValueError("能力矩阵必须是数组。")
    sanitized: list[dict[str, Any]] = []
    for index, item in enumerate(matrix, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 行不是有效对象。")
        channel = channel_id(item.get("channel_id"))
        if channel in {"", "channel"}:
            raise ValueError(f"第 {index} 行缺少 channel_id。")
        domains = item.get("domains")
        if not isinstance(domains, dict) or not domains:
            raise ValueError(f"{channel} 缺少 domains。")
        sanitized_domains: dict[str, dict[str, Any]] = {}
        for domain, spec in domains.items():
            domain_key = str(domain or "").strip()
            if not domain_key:
                continue
            if not isinstance(spec, dict):
                raise ValueError(f"{channel}.{domain_key} 不是有效能力配置。")
            mode = str(spec.get("mode") or "").strip()
            surface = str(spec.get("surface") or "").strip()
            if not mode or not surface:
                raise ValueError(f"{channel}.{domain_key} 必须填写 mode 和 surface。")
            sanitized_domains[domain_key] = {
                **spec,
                "mode": mode,
                "surface": surface,
                "required_authorizations": rule_list(spec.get("required_authorizations") or spec.get("required_scopes")),
            }
        if not sanitized_domains:
            raise ValueError(f"{channel} 没有有效能力域。")
        store_models = [normalize_store_model_for_route(value) for value in rule_list(item.get("store_models"))]
        reject_unsupported_executable_store_models(store_models, f"{channel} 能力矩阵")
        sanitized.append(
            {
                **item,
                "channel_id": channel,
                "label": str(item.get("label") or channel).strip(),
                "sites": [str(value).strip().upper() for value in rule_list(item.get("sites") or item.get("countries"))] or ["GLOBAL"],
                "store_models": store_models,
                "store_binding_policy": str(item.get("store_binding_policy") or "one_store_one_route_no_cross_store_write_permission").strip(),
                "cloud_package_policy": str(item.get("cloud_package_policy") or "isolated_cloud_profile_after_confirmation_stop_before_external_submit").strip(),
                "single_store_isolation_required": bool(item.get("single_store_isolation_required", True)),
                "official_sources": rule_list(item.get("official_sources") or item.get("official_source_url")),
                "blocked_external_actions": rule_list(item.get("blocked_external_actions")),
                "domains": sanitized_domains,
            }
        )
    return sanitized


def load_platform_activity_rules(root: Path) -> list[dict[str, Any]]:
    payload = load_json(config_path(root, PLATFORM_ACTIVITY_RULE_FILENAME))
    if isinstance(payload, dict):
        items = payload.get("rules") or payload.get("activities") or payload.get("platforms") or []
    else:
        items = payload
    if isinstance(items, list) and items:
        return enrich_platform_activity_rules([item for item in items if isinstance(item, dict)])
    return enrich_platform_activity_rules(DEFAULT_PLATFORM_ACTIVITY_RULES)


def load_platform_activity_rule_config(root: Path) -> dict[str, Any]:
    payload = load_json(config_path(root, PLATFORM_ACTIVITY_RULE_FILENAME))
    if isinstance(payload, dict):
        return payload
    return {
        "last_checked_at": date.today().isoformat(),
        "source_review": {
            "checked_at": date.today().isoformat(),
            "default_boundary": "Campaign rules are maintained per channel, country/site, store model, and ad account. Real campaign signup, discount publish, ad launch, budget changes, price changes, and external submission require confirmation.",
            "required_checks": [
                "eligibility",
                "stacking",
                "margin",
                "inventory",
                "ads_budget",
                "platform_policy",
            ],
            "official_sources": [],
        },
        "site_overrides": [],
        "rules": DEFAULT_PLATFORM_ACTIVITY_RULES,
    }


def load_platform_activity_site_overrides(root: Path) -> list[dict[str, Any]]:
    payload = load_json(config_path(root, PLATFORM_ACTIVITY_RULE_FILENAME))
    if isinstance(payload, dict):
        items = payload.get("site_overrides") or payload.get("siteOverrides") or []
    else:
        items = []
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def enrich_platform_capabilities(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in items:
        channel = channel_id(item.get("channel_id"))
        details = PLATFORM_DEVELOPER_DOMAIN_DETAILS.get(channel, {})
        if not details:
            enriched.append(item)
            continue
        next_item = dict(item)
        next_item.setdefault("domain_details", details)
        next_item.setdefault("developer_rule_summary", developer_domain_detail_summary(details))
        enriched.append(next_item)
    return enriched


def enrich_platform_execution_capability_matrix(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in items:
        channel = channel_id(item.get("channel_id"))
        details = PLATFORM_DEVELOPER_DOMAIN_DETAILS.get(channel, {})
        if not details:
            enriched.append(item)
            continue
        next_item = dict(item)
        domains = next_item.get("domains") if isinstance(next_item.get("domains"), dict) else {}
        next_domains: dict[str, dict[str, Any]] = {}
        for domain, spec in domains.items():
            if not isinstance(spec, dict):
                continue
            domain_key = str(domain or "").strip()
            domain_detail = details.get(domain_key, {})
            merged = {**domain_detail, **spec}
            for list_key in ("api_objects", "required_authorizations", "execution_surfaces"):
                merged[list_key] = list(dict.fromkeys([*rule_list(domain_detail.get(list_key)), *rule_list(spec.get(list_key))]))
            if not merged.get("official_source_url"):
                merged["official_source_url"] = domain_detail.get("official_source_url") or ""
            if not merged.get("final_submission_gate"):
                merged["final_submission_gate"] = domain_detail.get("final_submission_gate") or ""
            next_domains[domain_key] = merged
        for domain_key, domain_detail in details.items():
            if domain_key not in next_domains:
                next_domains[domain_key] = dict(domain_detail)
        next_item["domains"] = next_domains
        next_item.setdefault("domain_details", details)
        next_item.setdefault("developer_rule_summary", developer_domain_detail_summary(details))
        enriched.append(next_item)
    return enriched


def enrich_platform_activity_rules(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in items:
        channel = channel_id(item.get("channel_id"))
        mechanisms = PLATFORM_ACTIVITY_MECHANISM_DETAILS.get(channel, [])
        if not mechanisms:
            enriched.append(item)
            continue
        next_item = dict(item)
        existing = item.get("activity_mechanisms") if isinstance(item.get("activity_mechanisms"), list) else []
        next_item["activity_mechanisms"] = merge_activity_mechanisms(existing, mechanisms)
        next_item.setdefault("developer_rule_summary", activity_mechanism_summary(next_item["activity_mechanisms"]))
        next_item.setdefault("platform_rule_scope", "country_site_store_model_activity_type_and_authorization")
        next_item.setdefault("customer_execution_boundary", "backend_ai_prepares_rule_checked_drafts_real_submit_requires_owner_confirmation")
        next_item.setdefault("cloud_plugin_reason", "api_or_seller_backend_actions_need_isolated_store_or_ad_identity")
        enriched.append(next_item)
    return enriched


def merge_activity_mechanisms(existing: list[Any], defaults: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in [*defaults, *existing]:
        if not isinstance(item, dict):
            continue
        key = str(item.get("activity_type") or item.get("display") or "").strip()
        if not key:
            continue
        previous = merged.get(key, {})
        next_item = {**previous, **item}
        for list_key in ("stacking", "guardrails", "api_objects"):
            next_item[list_key] = list(dict.fromkeys([*rule_list(previous.get(list_key)), *rule_list(item.get(list_key))]))
        merged[key] = next_item
    return list(merged.values())


def developer_domain_detail_summary(details: dict[str, dict[str, Any]]) -> str:
    bits: list[str] = []
    for domain in ("listing", "promotion", "coupon", "ads", "reporting"):
        detail = details.get(domain)
        if not isinstance(detail, dict):
            continue
        objects = rule_list(detail.get("api_objects"))[:3]
        if objects:
            bits.append(f"{domain}: {', '.join(objects)}")
    return " | ".join(bits)


def activity_mechanism_summary(mechanisms: list[dict[str, Any]]) -> str:
    bits: list[str] = []
    for item in mechanisms[:5]:
        label = str(item.get("display") or item.get("activity_type") or "").strip()
        stack = ", ".join(rule_list(item.get("stacking"))[:2])
        if label:
            bits.append(f"{label}: {stack}" if stack else label)
    return " | ".join(bits)


def save_platform_activity_rule_config(
    root: Path,
    rules: Any,
    *,
    site_overrides: Any | None = None,
    updated_by: str = "admin",
) -> dict[str, Any]:
    sanitized_rules = sanitize_platform_activity_rules(rules)
    sanitized_overrides = sanitize_platform_activity_site_overrides(site_overrides or [])
    payload = load_platform_activity_rule_config(root)
    payload["rules"] = sanitized_rules
    payload["site_overrides"] = sanitized_overrides
    payload["rules_last_updated_at"] = date.today().isoformat()
    payload["rules_updated_by"] = str(updated_by or "admin")[:80]
    path = config_path(root, PLATFORM_ACTIVITY_RULE_FILENAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "path": str(path),
        "rules": sanitized_rules,
        "site_overrides": sanitized_overrides,
        "count": len(sanitized_rules),
        "site_override_count": len(sanitized_overrides),
    }


def sanitize_platform_activity_rules(rules: Any) -> list[dict[str, Any]]:
    if not isinstance(rules, list):
        raise ValueError("活动规则必须是数组。")
    sanitized: list[dict[str, Any]] = []
    for index, item in enumerate(rules, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 行不是有效对象。")
        channel = channel_id(item.get("channel_id"))
        if channel in {"", "channel"}:
            raise ValueError(f"第 {index} 行缺少 channel_id。")
        activity_types = rule_list(item.get("activity_types"))
        if not activity_types:
            raise ValueError(f"{channel} 缺少 activity_types。")
        stacking_rules = rule_list(item.get("stacking_rules"))
        api_boundary = str(item.get("api_boundary") or "").strip()
        ads_boundary = str(item.get("ads_boundary") or "").strip()
        execution_mode = str(item.get("execution_mode") or "").strip()
        if not api_boundary or not ads_boundary or not execution_mode:
            raise ValueError(f"{channel} 必须填写 api_boundary、ads_boundary 和 execution_mode。")
        store_models = [normalize_store_model_for_route(value) for value in rule_list(item.get("store_models"))]
        reject_unsupported_executable_store_models(store_models, f"{channel} 活动规则")
        sanitized.append(
            {
                **item,
                "channel_id": channel,
                "label": str(item.get("label") or channel).strip(),
                "countries": [str(value).strip().upper() for value in rule_list(item.get("countries") or item.get("sites"))] or ["GLOBAL"],
                "store_models": store_models,
                "activity_types": activity_types,
                "stacking_rules": stacking_rules or ["stackability_check_required"],
                "api_boundary": api_boundary,
                "ads_boundary": ads_boundary,
                "execution_mode": execution_mode,
                "margin_guardrail": str(item.get("margin_guardrail") or "margin_guardrail_required").strip(),
                "inventory_guardrail": str(item.get("inventory_guardrail") or "inventory_guardrail_required").strip(),
                "confirmation_required": bool(item.get("confirmation_required", True)),
                "authorization_requirements": rule_list(item.get("authorization_requirements")),
                "execution_surfaces": rule_list(item.get("execution_surfaces")),
                "real_submission_requires": rule_list(item.get("real_submission_requires")),
                "official_source_url": str(item.get("official_source_url") or "").strip(),
                "last_checked_at": str(item.get("last_checked_at") or date.today().isoformat()).strip(),
                "notes": str(item.get("notes") or "").strip(),
            }
        )
    return sanitized


def sanitize_platform_activity_site_overrides(overrides: Any) -> list[dict[str, Any]]:
    if overrides in (None, ""):
        return []
    if not isinstance(overrides, list):
        raise ValueError("站点覆盖规则必须是数组。")
    sanitized: list[dict[str, Any]] = []
    for index, item in enumerate(overrides, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"站点覆盖第 {index} 行不是有效对象。")
        channel = channel_id(item.get("channel_id"))
        if channel in {"", "channel"}:
            raise ValueError(f"站点覆盖第 {index} 行缺少 channel_id。")
        countries = [str(value).strip().upper() for value in rule_list(item.get("countries") or item.get("sites"))]
        if not countries:
            raise ValueError(f"{channel} 站点覆盖缺少 countries。")
        store_models = [normalize_store_model_for_route(value) for value in rule_list(item.get("store_models"))]
        reject_unsupported_executable_store_models(store_models, f"{channel} 站点覆盖")
        sanitized.append(
            {
                **item,
                "site_override_id": str(item.get("site_override_id") or f"{channel}_{'_'.join(countries).lower()}_activity").strip(),
                "channel_id": channel,
                "countries": countries,
                "store_models": store_models,
                "site_activity_focus": rule_list(item.get("site_activity_focus")),
                "site_campaign_window": str(item.get("site_campaign_window") or "").strip(),
                "site_ads_notes": rule_list(item.get("site_ads_notes")),
                "site_rule_notes": rule_list(item.get("site_rule_notes")),
                "activity_types_add": rule_list(item.get("activity_types_add")),
                "stacking_rules_add": rule_list(item.get("stacking_rules_add")),
                "authorization_requirements_add": rule_list(item.get("authorization_requirements_add")),
                "real_submission_requires_add": rule_list(item.get("real_submission_requires_add")),
            }
        )
    return sanitized


def platform_developer_capability_guardrail_issues(payload: dict[str, Any]) -> list[str]:
    if not isinstance(payload, dict):
        return ["platform_developer_capability_payload_not_object"]
    issues: list[str] = []
    matrix = payload.get("execution_capability_matrix") or payload.get("capability_matrix") or []
    capabilities = payload.get("capabilities") or payload.get("platforms") or []
    if isinstance(matrix, list):
        for index, item in enumerate(matrix, start=1):
            if isinstance(item, dict):
                issues.extend(developer_matrix_guardrail_issues(index, item))
            else:
                issues.append(f"execution_capability_matrix:{index}:not_object")
    else:
        issues.append("execution_capability_matrix:not_list")
    if isinstance(capabilities, list):
        for index, item in enumerate(capabilities, start=1):
            if isinstance(item, dict):
                issues.extend(developer_capability_summary_guardrail_issues(index, item))
            else:
                issues.append(f"capabilities:{index}:not_object")
    else:
        issues.append("capabilities:not_list")
    return issues


def developer_matrix_guardrail_issues(index: int, item: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    item_id = str(item.get("channel_id") or item.get("label") or index)
    channel = channel_id(item.get("channel_id"))
    sites = [str(value).strip().upper() for value in rule_list(item.get("sites") or item.get("countries"))]
    models = [normalize_store_model_for_route(value) for value in rule_list(item.get("store_models"))]
    haystack = json.dumps(item, ensure_ascii=False).lower()
    if any(site in {"SEA", "LATAM"} for site in sites):
        issues.append(f"execution_capability_matrix:{item_id}:region_used_as_executable_site")
    if any(model in UNSUPPORTED_EXECUTABLE_STORE_MODELS for model in models):
        issues.append(f"execution_capability_matrix:{item_id}:official_full_managed_not_executable")
    if channel in {"tiktok_shop", "shopee", "lazada"}:
        sea_sites = {"SG", "MY", "TH", "VN", "PH", "ID"}
        grouped_sea = len(sea_sites.intersection(sites)) > 1
        if grouped_sea and not (
            any(token in haystack for token in ["country", "sites", "site"])
            and any(token in haystack for token in ["separate", "split", "one_store_one_route", "shop_authorization"])
        ):
            issues.append(f"execution_capability_matrix:{item_id}:southeast_asia_sites_need_country_split_boundary")
    if "latam" in haystack and "latin america" not in haystack:
        issues.append(f"execution_capability_matrix:{item_id}:visible_latam_label")
    if "联名代运营" in haystack:
        issues.append(f"execution_capability_matrix:{item_id}:old_co_ops_label")
    if "official_full_managed" in haystack and "no_official_full_managed" not in haystack and "not_executable" not in haystack:
        issues.append(f"execution_capability_matrix:{item_id}:official_full_managed_missing_rejection_boundary")
    cloud_policy = str(item.get("cloud_package_policy") or "").lower()
    if "cloud" in cloud_policy and not all(token in cloud_policy for token in ["confirmation", "stop_before_external_submit"]):
        issues.append(f"execution_capability_matrix:{item_id}:cloud_policy_missing_confirmation_stop_gate")
    if bool(item.get("single_store_isolation_required", True)) is False and channel not in {"meta_ads"}:
        issues.append(f"execution_capability_matrix:{item_id}:single_store_isolation_must_stay_on")
    domains = item.get("domains") if isinstance(item.get("domains"), dict) else {}
    for domain_name, spec in domains.items():
        if isinstance(spec, dict):
            issues.extend(domain_guardrail_issues(item_id, str(domain_name), spec))
    return issues


def domain_guardrail_issues(item_id: str, domain_name: str, spec: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    mode = str(spec.get("mode") or "").lower()
    surface = str(spec.get("surface") or "").lower()
    auths = [str(value).lower() for value in rule_list(spec.get("required_authorizations") or spec.get("required_scopes"))]
    if domain_name in {"promotion", "coupon", "ads", "listing"}:
        boundary = " ".join([mode, surface])
        auth_text = " ".join(auths)
        if not any(
            token in " ".join([boundary, auth_text])
            for token in ["draft", "confirmation", "separate", "review", "authorization", "permission", "scope", "installed", "access"]
        ):
            issues.append(f"execution_capability_matrix:{item_id}:{domain_name}:missing_draft_or_authorization_boundary")
    if domain_name == "ads":
        joined = " ".join([mode, surface, " ".join(auths)])
        if "ads" not in joined and "ad_account" not in joined and "business" not in joined:
            issues.append(f"execution_capability_matrix:{item_id}:ads:missing_ads_account_boundary")
    if any("submit" in token or "launch" in token or "publish" in token for token in [mode, surface]):
        if not any(token in mode for token in ["draft", "confirmation", "review", "authorization", "permission"]):
            issues.append(f"execution_capability_matrix:{item_id}:{domain_name}:write_surface_without_confirmation_mode")
    return issues


def developer_capability_summary_guardrail_issues(index: int, item: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    item_id = str(item.get("channel_id") or item.get("label") or index)
    haystack = json.dumps(item, ensure_ascii=False).lower()
    if "latam" in haystack and "latin america" not in haystack:
        issues.append(f"capabilities:{item_id}:visible_latam_label")
    if "联名代运营" in haystack:
        issues.append(f"capabilities:{item_id}:old_co_ops_label")
    if "official_full_managed" in haystack and "do not mix" not in haystack and "no_official_full_managed" not in haystack:
        issues.append(f"capabilities:{item_id}:official_full_managed_missing_rejection_boundary")
    cloud_policy = str(item.get("cloud_plugin_policy") or item.get("cloud_package_policy") or "").lower()
    if cloud_policy and not all(token in cloud_policy for token in ["confirmation", "stop_before_external_submit"]):
        issues.append(f"capabilities:{item_id}:cloud_policy_missing_confirmation_stop_gate")
    if bool(item.get("single_store_isolation_required", True)) is False and channel_id(item.get("channel_id")) not in {"meta_ads"}:
        issues.append(f"capabilities:{item_id}:single_store_isolation_must_stay_on")
    ads = " ".join(str(item.get(key) or "").lower() for key in ["ads", "notes", "authorization_surface"])
    if "ads" in ads and not any(token in ads for token in ["separate", "ad account", "ads_account", "business"]):
        issues.append(f"capabilities:{item_id}:ads_not_separated_from_store_api")
    return issues


def platform_activity_rule_guardrail_issues(payload: dict[str, Any]) -> list[str]:
    if not isinstance(payload, dict):
        return ["platform_activity_rules_payload_not_object"]
    issues: list[str] = []
    rules = payload.get("rules") or payload.get("activities") or payload.get("platforms") or []
    site_overrides = payload.get("site_overrides") or payload.get("siteOverrides") or []
    for section, items in [("rules", rules), ("site_overrides", site_overrides)]:
        if not isinstance(items, list):
            issues.append(f"{section}:not_list")
            continue
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                issues.append(f"{section}:{index}:not_object")
                continue
            issues.extend(activity_guardrail_issues_for_item(section, index, item))
    return issues


def activity_guardrail_issues_for_item(section: str, index: int, item: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    item_id = str(item.get("site_override_id") or item.get("rule_id") or item.get("label") or item.get("channel_id") or index)
    channel = channel_id(item.get("channel_id"))
    countries = [str(value).strip().upper() for value in rule_list(item.get("countries") or item.get("sites"))]
    models = [normalize_store_model_for_route(value) for value in rule_list(item.get("store_models"))]
    haystack = json.dumps(item, ensure_ascii=False).lower()
    if any(country in {"SEA", "LATAM"} for country in countries):
        issues.append(f"{section}:{item_id}:region_used_as_executable_country")
    if any(model in UNSUPPORTED_EXECUTABLE_STORE_MODELS for model in models):
        issues.append(f"{section}:{item_id}:official_full_managed_not_executable")
    if channel in {"tiktok_shop", "shopee", "lazada"}:
        sea_countries = {"SG", "MY", "TH", "VN", "PH", "ID"}
        grouped_sea = len(sea_countries.intersection(countries)) > 1
        compat_allowed = (
            grouped_sea
            and "compat" in item_id.lower()
            and "sea_site_separate_by_country" in haystack
            and not {"SEA"}.intersection(countries)
        )
        country_site_guarded = (
            grouped_sea
            and "country_site" in haystack
            and any(token in haystack for token in ["separate", "split", "country_site_rule_check", "separate_by_country"])
            and not {"SEA"}.intersection(countries)
        )
        if grouped_sea and not compat_allowed and not country_site_guarded:
            issues.append(f"{section}:{item_id}:southeast_asia_must_be_country_split_or_compat_guarded")
    if "latam" in haystack and "latin america" not in haystack:
        issues.append(f"{section}:{item_id}:visible_latam_label")
    if "联名代运营" in haystack:
        issues.append(f"{section}:{item_id}:old_co_ops_label")
    if "official_full_managed" in haystack and "do_not_mix" not in haystack and "not_executable" not in haystack:
        issues.append(f"{section}:{item_id}:official_full_managed_missing_rejection_boundary")
    if section == "rules":
        boundary = " ".join(
            str(item.get(key) or "")
            for key in ["api_boundary", "ads_boundary", "execution_mode", "customer_execution_boundary"]
        ).lower()
        if not any(token in boundary for token in ["draft", "confirmation", "confirm", "后台", "草稿", "确认"]):
            issues.append(f"{section}:{item_id}:missing_draft_confirmation_boundary")
    return issues


def reject_unsupported_executable_store_models(store_models: list[str], context: str) -> None:
    if any(model in UNSUPPORTED_EXECUTABLE_STORE_MODELS for model in store_models):
        raise ValueError(
            f"{context} 不能把平台官方全托管保存为可执行店铺模式；"
            "官方全托管只做识别标签，请改用 TeeLab 代运营、TeeLab 自营、设计师自运营、本土店、跨境店或半托管路线。"
        )


def build_platform_activity_readiness(root: Path, profile_stores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules = load_platform_activity_rules(root)
    site_overrides = load_platform_activity_site_overrides(root)
    route_rows = build_channel_route_readiness(root, profile_stores)
    if not route_rows:
        return [
            {
                "route_key": f"{channel_id(rule.get('channel_id'))}:GLOBAL:store_model_pending",
                "channel_id": channel_id(rule.get("channel_id")),
                "country_code": "GLOBAL",
                "store_model": "store_model_pending",
                "status": "route_needed",
                "activity_types": rule_list(rule.get("activity_types")),
                "stacking_rules": rule_list(rule.get("stacking_rules")),
                "api_boundary": rule.get("api_boundary") or "rules_need_review",
                "ads_boundary": rule.get("ads_boundary") or "rules_need_review",
                "execution_mode": "draft_only_until_route_exists",
                "margin_guardrail": rule.get("margin_guardrail") or "needs_margin_review",
                "inventory_guardrail": rule.get("inventory_guardrail") or "needs_inventory_review",
                "confirmation_required": True,
                "official_source_url": rule.get("official_source_url") or "",
                "execution_readiness": "needs_platform_store",
                "execution_readiness_label": "缺店铺",
                "next_step": "还没有平台路由；后台 AI 只能学习规则和生成活动草稿，不能准备真实店铺动作。",
            }
            for rule in rules[:6]
        ]
    rows: list[dict[str, Any]] = []
    for route in route_rows:
        status = str(route.get("status") or "")
        rule = find_activity_rule_for_route(route, rules, site_overrides)
        if status in {"needs_platform_store", "platform_store_pending_authorization", "platform_store_pending_identity"}:
            rows.append(
                activity_row_from_route(
                    route,
                    rule,
                    status="needs_platform_store",
                    execution_mode="candidate_only_no_store_action",
                    next_step="设计师申请了这个站点，但后台还没有真实平台店铺；只能做候选规划、平台招商或开店准备。",
                )
            )
            continue
        if not rule:
            rows.append(
                activity_row_from_route(
                    route,
                    {},
                    status="rules_need_review",
                    execution_mode="draft_only_then_confirmation",
                    next_step="这条路径还没有维护活动规则；先保守出草稿，确认前再核对官方规则。",
                )
            )
            continue
        rows.append(
            activity_row_from_route(
                route,
                rule,
                status="rule_available",
                execution_mode=str(rule.get("execution_mode") or "draft_then_confirmation"),
                next_step="后台 AI 可以为这条路径生成活动方案、叠加校验、毛利止损线和负责人确认包。",
            )
        )
    return dedupe_activity_rows(rows)


def build_platform_activity_execution_plan(
    root: Path,
    request: dict[str, Any],
    profile_stores: list[dict[str, Any]],
) -> dict[str, Any]:
    requested_route = normalize_activity_request_route(request)
    activity_type = requested_activity_type(request)
    includes_ads = activity_request_includes_ads(request, activity_type)
    route_rows = build_channel_route_readiness(root, profile_stores)
    activity_rows = build_platform_activity_readiness(root, profile_stores)
    route = find_route_row_for_activity_request(requested_route, route_rows) or synthetic_route_row_for_activity_request(
        requested_route,
        profile_stores,
    )
    row = find_activity_row_for_activity_request(requested_route, activity_rows)
    if row is None:
        rule = find_activity_rule_for_route(route, load_platform_activity_rules(root), load_platform_activity_site_overrides(root))
        row = activity_row_from_route(
            route,
            rule or {},
            status="rules_need_review" if rule is None else ("needs_platform_store" if route.get("status") == "needs_platform_store" else "rule_available"),
            execution_mode=str((rule or {}).get("execution_mode") or "draft_only_then_confirmation"),
            next_step="先生成活动草稿和负责人确认包；外部提交前由后台 AI 复核平台规则。",
        )

    unsupported = requested_route["store_model"] == "official_full_managed"
    missing = activity_plan_missing_prerequisites(row, includes_ads=includes_ads, unsupported=unsupported)
    required_checks = activity_plan_required_checks(row, includes_ads=includes_ads)
    can_prepare_draft = not unsupported
    can_queue_cloud_task = can_prepare_draft and not missing and "isolated_cloud_plugin" in str(row.get("execution_mode") or "")
    external_submit_allowed = False
    owner_confirmation_required = bool(row.get("confirmation_required", True))
    plan_status = activity_plan_status(row, missing, unsupported=unsupported, can_queue_cloud_task=can_queue_cloud_task)
    stack_guardrail = build_activity_stack_guardrail(request, row, includes_ads=includes_ads)
    rule_playbook = build_activity_rule_playbook(row, request, includes_ads=includes_ads)
    ad_budget_plan = build_ad_budget_plan(
        request,
        row,
        stack_guardrail,
        includes_ads=includes_ads,
        missing_prerequisites=missing,
    )
    developer_capability_plan = build_developer_capability_plan(
        root,
        row,
        activity_type=activity_type,
        includes_ads=includes_ads,
    )
    source_review = activity_source_review(root)
    rule_evidence_pack = build_activity_rule_evidence_pack(
        row,
        source_review=source_review,
        developer_capability_plan=developer_capability_plan,
        rule_playbook=rule_playbook,
    )
    rule_to_task_closure = build_activity_rule_to_task_closure(
        row,
        plan_status=plan_status,
        rule_playbook=rule_playbook,
        stack_guardrail=stack_guardrail,
        developer_capability_plan=developer_capability_plan,
        can_queue_cloud_task=can_queue_cloud_task,
        includes_ads=includes_ads,
    )
    operator_preflight_pack = build_operator_activity_preflight_pack(
        row,
        plan_status=plan_status,
        missing_prerequisites=missing,
        required_checks=required_checks,
        rule_evidence_pack=rule_evidence_pack,
        rule_playbook=rule_playbook,
        stack_guardrail=stack_guardrail,
        ad_budget_plan=ad_budget_plan,
        developer_capability_plan=developer_capability_plan,
        can_queue_cloud_task=can_queue_cloud_task,
        includes_ads=includes_ads,
    )
    store_ownership = infer_store_ownership_for_route(
        {
            **request,
            **row,
            "store_model": row.get("store_model") or requested_route["store_model"],
        }
    )
    return {
        "ok": True,
        "route_key": row.get("route_key") or requested_route["route_key"],
        "channel_id": row.get("channel_id") or requested_route["channel_id"],
        "country_code": row.get("country_code") or requested_route["country_code"],
        "store_model": row.get("store_model") or requested_route["store_model"],
        "store_ownership": store_ownership,
        "store_ownership_label": store_ownership_label(store_ownership),
        "store_name": route.get("matched_store") or request.get("store_name") or request.get("store") or "",
        "activity_type": activity_type,
        "includes_ads": includes_ads,
        "plan_status": plan_status,
        "can_prepare_draft": can_prepare_draft,
        "can_queue_cloud_task": can_queue_cloud_task,
        "external_submit_allowed": external_submit_allowed,
        "owner_confirmation_required": owner_confirmation_required,
        "missing_prerequisites": missing,
        "required_checks": required_checks,
        "activity_stack_guardrail": stack_guardrail,
        "activity_rule_playbook": rule_playbook,
        "activity_rule_evidence_pack": rule_evidence_pack,
        "ad_budget_plan": ad_budget_plan,
        "developer_capability_plan": developer_capability_plan,
        "rule_to_task_closure": rule_to_task_closure,
        "operator_preflight_pack": operator_preflight_pack,
        "alternative_supported_routes": supported_alternative_routes_for_activity(requested_route) if unsupported else [],
        "not_supported_reason": (
            "official_full_managed_is_platform_official_mode_not_teelab_operation"
            if unsupported
            else ""
        ),
        "activity_types": rule_list(row.get("activity_types")),
        "stacking_rules": rule_list(row.get("stacking_rules")),
        "site_activity_focus": rule_list(row.get("site_activity_focus")),
        "site_campaign_window": row.get("site_campaign_window") or "",
        "site_ads_notes": rule_list(row.get("site_ads_notes")),
        "site_rule_notes": rule_list(row.get("site_rule_notes")),
        "authorization_requirements": rule_list(row.get("authorization_requirements")),
        "execution_surfaces": rule_list(row.get("execution_surfaces")),
        "real_submission_requires": rule_list(row.get("real_submission_requires")),
        "api_boundary": row.get("api_boundary") or "rules_need_review",
        "ads_boundary": row.get("ads_boundary") or "rules_need_review",
        "execution_mode": row.get("execution_mode") or "draft_then_confirmation",
        "execution_readiness": row.get("execution_readiness") or "draft_only",
        "execution_readiness_label": row.get("execution_readiness_label") or "",
        "margin_guardrail": row.get("margin_guardrail") or "needs_margin_review",
        "inventory_guardrail": row.get("inventory_guardrail") or "needs_inventory_review",
        "customer_execution_boundary": row.get("customer_execution_boundary") or default_customer_execution_boundary(str(row.get("execution_readiness") or "")),
        "cloud_plugin_reason": row.get("cloud_plugin_reason") or default_cloud_plugin_reason(row),
        "recommended_executor": activity_plan_executor(row, includes_ads=includes_ads, can_queue_cloud_task=can_queue_cloud_task),
        "task_package_hint": activity_plan_task_package_hint(activity_type, includes_ads=includes_ads),
        "official_source_url": row.get("official_source_url") or "",
        "next_step": activity_plan_next_step(plan_status, row, includes_ads=includes_ads),
        "source_status": row.get("source_status") or route.get("status") or "",
        "source_review": source_review,
    }


def build_activity_rule_evidence_pack(
    row: dict[str, Any],
    *,
    source_review: dict[str, Any],
    developer_capability_plan: dict[str, Any],
    rule_playbook: dict[str, Any],
) -> dict[str, Any]:
    checked_at = str(
        row.get("last_checked_at")
        or source_review.get("checked_at")
        or source_review.get("last_checked_at")
        or ""
    ).strip()
    official_sources = list(
        dict.fromkeys(
            [
                *url_list(row.get("official_source_url")),
                *rule_list(developer_capability_plan.get("official_sources")),
                *source_review_official_source_urls(source_review),
            ]
        )
    )
    authorization_surfaces = list(
        dict.fromkeys(
            [
                *rule_list(row.get("execution_surfaces")),
                *rule_list(developer_capability_plan.get("execution_surfaces")),
            ]
        )
    )
    stop_before_actions = list(
        dict.fromkeys(
            [
                *rule_list(developer_capability_plan.get("blocked_external_actions")),
                "campaign_signup_without_owner_confirmation",
                "coupon_or_discount_publish_without_owner_confirmation",
                "ad_launch_or_budget_change_without_owner_confirmation",
                "price_inventory_refund_shipment_without_owner_confirmation",
            ]
        )
    )
    return {
        "checked_at": checked_at,
        "official_sources": official_sources[:8],
        "route_key": row.get("route_key") or "",
        "rule_scope": row.get("platform_rule_scope") or "channel_country_store_model",
        "store_binding_policy": developer_capability_plan.get("store_binding_policy")
        or "one_store_one_route_no_cross_store_write_permission",
        "cloud_package_policy": developer_capability_plan.get("cloud_package_policy")
        or "isolated_cloud_profile_after_confirmation_stop_before_external_submit",
        "authorization_surfaces": authorization_surfaces[:12],
        "requested_domains": rule_list(developer_capability_plan.get("requested_domains"))[:8],
        "stackability_checks": rule_list(rule_playbook.get("stackability_checks"))[:8],
        "submission_gates": rule_list(rule_playbook.get("real_submission_gates"))[:8],
        "blocked_external_actions": stop_before_actions[:10],
        "customer_boundary": row.get("customer_execution_boundary")
        or "AI may prepare drafts and evidence; real external changes require owner confirmation.",
        "external_submit_allowed": False,
        "summary": (
            "Official rule evidence, route scope, authorization surfaces, stack checks, and final-submit "
            "boundaries are attached before backend execution."
        ),
    }


def source_review_official_source_urls(source_review: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    raw_sources = source_review.get("official_sources") if isinstance(source_review, dict) else []
    if isinstance(raw_sources, list):
        for item in raw_sources:
            if isinstance(item, dict):
                url = str(item.get("url") or item.get("official_source_url") or "").strip()
            else:
                url = str(item or "").strip()
            if url:
                urls.append(url)
    elif isinstance(raw_sources, str):
        urls.extend(rule_list(raw_sources))
    return urls


def url_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def build_activity_rule_to_task_closure(
    row: dict[str, Any],
    *,
    plan_status: str,
    rule_playbook: dict[str, Any],
    stack_guardrail: dict[str, Any],
    developer_capability_plan: dict[str, Any],
    can_queue_cloud_task: bool,
    includes_ads: bool,
) -> dict[str, Any]:
    gates = list(
        dict.fromkeys(
            [
                *(rule_list(rule_playbook.get("real_submission_gates")) or rule_list(row.get("real_submission_requires"))),
                "owner_confirmation_required",
            ]
        )
    )
    stack_checks = rule_list(rule_playbook.get("stackability_checks")) or rule_list(row.get("stacking_rules"))
    capability_domains = rule_list(developer_capability_plan.get("requested_domains"))
    source_url = str(row.get("official_source_url") or "").strip()
    rule_status = str(row.get("source_status") or row.get("status") or "rule_available").strip()
    return {
        "closure_status": "ready_for_confirmation_package" if can_queue_cloud_task else plan_status or "draft_only",
        "rule_source_status": rule_status,
        "official_source_url": source_url,
        "stack_checks": stack_checks[:8],
        "margin_guardrail_status": str(stack_guardrail.get("calculation_status") or "not_evaluated"),
        "real_submission_gates": gates[:8],
        "capability_domains": capability_domains[:8],
        "task_package_readiness": "backend_task_package_after_confirmation" if can_queue_cloud_task else "draft_only_until_prerequisites_ready",
        "includes_ads": includes_ads,
        "external_submit_allowed": False,
        "summary": "Rule source, stack checks, margin guardrail, confirmation gates, and backend task package are linked before any external submission.",
    }


def build_operator_activity_preflight_pack(
    row: dict[str, Any],
    *,
    plan_status: str,
    missing_prerequisites: list[str],
    required_checks: list[str],
    rule_evidence_pack: dict[str, Any],
    rule_playbook: dict[str, Any],
    stack_guardrail: dict[str, Any],
    ad_budget_plan: dict[str, Any],
    developer_capability_plan: dict[str, Any],
    can_queue_cloud_task: bool,
    includes_ads: bool,
) -> dict[str, Any]:
    sources = rule_list(rule_evidence_pack.get("official_sources"))
    source_status = "ready" if sources else "needs_review"
    route_status = "blocked" if "platform_store" in missing_prerequisites else "ready"
    ads_status = (
        "not_needed"
        if not includes_ads
        else ("blocked" if any(item in missing_prerequisites for item in ["ads_account", "business_center"]) else "ready")
    )
    economics_status = str(stack_guardrail.get("calculation_status") or "needs_price_cost_inputs")
    economics_ready = economics_status in {"pass", "margin_pass", "ready", "calculated"}
    budget_status = str(ad_budget_plan.get("planning_status") or ("not_needed" if not includes_ads else "needs_budget_review"))
    execution_status = "ready_after_confirmation" if can_queue_cloud_task else "draft_only"
    checkpoints = [
        {
            "key": "official_rules",
            "label": "官方规则与公开资料",
            "status": source_status,
            "next_action": "后台 AI 已记录官方资料，执行前继续按站点复核。"
            if source_status == "ready"
            else "后台 AI 先复核官方资料，再生成负责人确认包。",
        },
        {
            "key": "route_store_identity",
            "label": "真实店铺和站点身份",
            "status": route_status,
            "next_action": "真实平台店铺已匹配到这条路径。"
            if route_status == "ready"
            else "先补这条路径的真实平台店铺，只保留候选和开店准备。",
        },
        {
            "key": "ads_identity",
            "label": "广告账号和归属主体",
            "status": ads_status,
            "next_action": "广告账号与归属主体已可进入预算草稿。"
            if ads_status == "ready"
            else ("本次不涉及广告投放。" if ads_status == "not_needed" else "先补广告账号和归属主体，只保留投放草稿。"),
        },
        {
            "key": "stack_margin_inventory",
            "label": "优惠叠加、毛利和库存",
            "status": "ready" if economics_ready else "needs_inputs",
            "next_action": "优惠叠加、毛利和库存已可进入确认包。"
            if economics_ready
            else "先补售价、成本、库存和履约数据，后台 AI 只做测算草稿。",
        },
        {
            "key": "owner_confirmation",
            "label": "负责人确认和外部提交边界",
            "status": "required",
            "next_action": "真实报名、改价、发券、投广告、退款或发货都必须负责人确认。",
        },
        {
            "key": "writeback",
            "label": "执行后证据和 ERP 回写",
            "status": execution_status,
            "next_action": "确认后只生成后台待执行包，执行后必须回写截图、编号、日志、ERP 状态和回滚结果。"
            if can_queue_cloud_task
            else "前置条件未齐前只保留草稿，不进入真实外部后台。",
        },
    ]
    if includes_ads:
        checkpoints.insert(
            4,
            {
                "key": "ads_budget",
                "label": "广告预算和止损",
                "status": "ready" if budget_status in {"draft_ready", "ready"} else budget_status,
                "next_action": "后台 AI 先计算保本 ROAS、日预算上限和止损线，确认前不消耗预算。",
            },
        )
    return {
        "summary": "后台 AI 先替客户完成官方规则、店铺身份、活动叠加、毛利库存、广告预算、负责人确认和回写预检。",
        "plan_status": plan_status,
        "checkpoints": checkpoints,
        "required_checks": required_checks[:12],
        "missing_prerequisites": missing_prerequisites[:12],
        "source_count": len(sources),
        "stackability_checks": rule_list(rule_playbook.get("stackability_checks"))[:8],
        "external_submit_allowed": False,
        "customer_boundary": "客户只看结果和确认项；后台 AI 自己查规则、生成草稿、准备证据，真实外部动作必须确认。",
    }


def normalize_activity_request_route(request: dict[str, Any]) -> dict[str, str]:
    route_key = str(request.get("route_key") or "").strip()
    if route_key and route_key.count(":") >= 2:
        channel, country, store_model = route_key.split(":", 2)
        return {
            "route_key": route_key,
            "channel_id": channel_id(channel),
            "country_code": str(country or "GLOBAL").strip().upper() or "GLOBAL",
            "store_model": normalize_store_model_for_route(store_model),
        }
    channel = channel_id(request.get("channel_id") or request.get("platform"))
    country = str(request.get("country_code") or request.get("country") or "GLOBAL").strip().upper() or "GLOBAL"
    store_model = normalize_store_model_for_route(request.get("store_model") or request.get("shop_type") or request.get("operation_model"))
    return {
        "route_key": make_route_key(channel, country, store_model),
        "channel_id": channel,
        "country_code": country,
        "store_model": store_model,
    }


def requested_activity_type(request: dict[str, Any]) -> str:
    return str(
        request.get("activity_type")
        or request.get("campaign_type")
        or request.get("action_type")
        or request.get("operation")
        or "activity_plan"
    ).strip() or "activity_plan"


def activity_request_includes_ads(request: dict[str, Any], activity_type: str) -> bool:
    if isinstance(request.get("includes_ads"), bool):
        return bool(request.get("includes_ads"))
    text = " ".join(
        str(value or "")
        for value in [
            activity_type,
            request.get("title"),
            request.get("goal"),
            request.get("intent"),
            request.get("ads_boundary"),
        ]
    ).lower()
    return any(signal in text for signal in ACTIVITY_AD_SIGNALS)


def find_route_row_for_activity_request(route: dict[str, str], route_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in route_rows:
        if str(row.get("route_key") or "") == route["route_key"]:
            return row
    return None


def find_activity_row_for_activity_request(route: dict[str, str], activity_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in activity_rows:
        if str(row.get("route_key") or "") == route["route_key"]:
            return row
    return None


def synthetic_route_row_for_activity_request(route: dict[str, str], profile_stores: list[dict[str, Any]]) -> dict[str, Any]:
    for store in profile_stores:
        if platform_route_id_for_store(store) == route["route_key"]:
            if not store_route_is_ready_for_mapping(store):
                return {
                    **route,
                    "status": "needs_platform_store",
                    "matched_store": store.get("store_name") or "",
                    "ads_account_status": "registered" if str(store.get("ads_account_id") or "").strip() else "missing",
                    "business_center_status": "registered" if str(store.get("business_center_id") or "").strip() else "missing",
                    "next_step": store_route_pending_next_step(store),
                }
            return {
                **route,
                "status": "platform_store_configured",
                "matched_store": store.get("store_name") or "",
                "store_visibility_note": store_route_visibility_note(store),
                "ads_account_status": "registered" if str(store.get("ads_account_id") or "").strip() else "missing",
                "business_center_status": "registered" if str(store.get("business_center_id") or "").strip() else "missing",
            }
    return {
        **route,
        "status": "needs_platform_store",
        "matched_store": "",
        "ads_account_status": "missing",
        "business_center_status": "missing",
    }


def activity_plan_missing_prerequisites(row: dict[str, Any], *, includes_ads: bool, unsupported: bool) -> list[str]:
    missing: list[str] = []
    if unsupported:
        missing.append("official_full_managed_not_supported")
    if str(row.get("status") or "") in {"needs_platform_store", "platform_store_pending_authorization", "platform_store_pending_identity", "route_needed"} or str(row.get("execution_readiness") or "") == "needs_platform_store":
        missing.append("platform_store")
    if str(row.get("status") or "") == "rules_need_review":
        missing.append("platform_activity_rule")
    if includes_ads:
        if str(row.get("ads_account_status") or "") != "registered":
            missing.append("ads_account")
        if str(row.get("business_center_status") or "") != "registered":
            missing.append("business_center")
    return list(dict.fromkeys(missing))


def activity_plan_required_checks(row: dict[str, Any], *, includes_ads: bool) -> list[str]:
    checks = ["eligibility", "stacking", "margin", "inventory", "fulfillment_sla", "platform_policy"]
    if includes_ads:
        checks.extend(["ads_account", "ads_budget", "break_even_roas"])
    if row.get("confirmation_required", True):
        checks.append("owner_confirmation")
    checks.extend(rule_list(row.get("real_submission_requires")))
    return list(dict.fromkeys(checks))


def activity_plan_status(
    row: dict[str, Any],
    missing: list[str],
    *,
    unsupported: bool,
    can_queue_cloud_task: bool,
) -> str:
    if unsupported:
        return "not_supported_official_full_managed"
    if "platform_store" in missing:
        return "needs_platform_store"
    if "ads_account" in missing or "business_center" in missing:
        return "needs_ads_account"
    if "platform_activity_rule" in missing:
        return "rules_need_review"
    if can_queue_cloud_task:
        return "ready_for_cloud_plugin_after_confirmation"
    return "draft_ready_confirmation_required"


def activity_plan_executor(row: dict[str, Any], *, includes_ads: bool, can_queue_cloud_task: bool) -> str:
    if includes_ads:
        return "cloud_ads_executor" if can_queue_cloud_task else "ads_draft_planner"
    if can_queue_cloud_task:
        return "cloud_store_executor"
    if "api" in str(row.get("api_boundary") or ""):
        return "api_mapping_planner"
    return "activity_draft_planner"


def activity_plan_task_package_hint(activity_type: str, *, includes_ads: bool) -> str:
    lowered = activity_type.lower()
    if includes_ads:
        return "ads_backend"
    if any(signal in lowered for signal in ["coupon", "discount", "promotion", "campaign", "voucher", "bundle", "free_shipping"]):
        return "store_backend"
    return "read_only_collection"


def build_developer_capability_plan(
    root: Path,
    row: dict[str, Any],
    *,
    activity_type: str,
    includes_ads: bool,
) -> dict[str, Any]:
    capability_row = find_execution_capability_for_route(root, row)
    requested_domains = activity_capability_domains(activity_type, includes_ads=includes_ads)
    all_domains = capability_row.get("domains") if isinstance(capability_row.get("domains"), dict) else {}
    domain_specs: dict[str, Any] = {}
    for domain in requested_domains:
        spec = all_domains.get(domain)
        if isinstance(spec, dict):
            domain_specs[domain] = spec
    domain_action_details = {
        domain: {
            "api_objects": rule_list(spec.get("api_objects")),
            "execution_surfaces": rule_list(spec.get("execution_surfaces") or spec.get("surface")),
            "required_authorizations": rule_list(spec.get("required_authorizations") or spec.get("required_scopes")),
            "final_submission_gate": str(spec.get("final_submission_gate") or "").strip(),
            "official_source_url": str(spec.get("official_source_url") or "").strip(),
        }
        for domain, spec in domain_specs.items()
        if isinstance(spec, dict)
    }
    execution_surfaces = list(
        dict.fromkeys(
            [
                *rule_list(row.get("execution_surfaces")),
                *[
                    str(spec.get("surface") or "").strip()
                    for spec in domain_specs.values()
                    if str(spec.get("surface") or "").strip()
                ],
                *[
                    item
                    for spec in domain_specs.values()
                    for item in rule_list(spec.get("execution_surfaces"))
                ],
            ]
        )
    )
    required_authorizations = list(
        dict.fromkeys(
            [
                *rule_list(row.get("authorization_requirements")),
                *[
                    item
                    for spec in domain_specs.values()
                    for item in rule_list(spec.get("required_authorizations") or spec.get("required_scopes"))
                ],
            ]
        )
    )
    cloud_package_type = (
        "ads_backend"
        if "ads" in requested_domains
        else ("content_catalog" if "catalog" in requested_domains else "store_backend")
    )
    return {
        "capability_status": "capability_available" if domain_specs else "capability_needs_review",
        "route_key": row.get("route_key") or "",
        "channel_id": row.get("channel_id") or capability_row.get("channel_id") or "",
        "country_code": row.get("country_code") or "",
        "store_model": row.get("store_model") or "",
        "activity_type": activity_type,
        "requested_domains": requested_domains,
        "domains": domain_specs,
        "domain_action_details": domain_action_details,
        "execution_surfaces": execution_surfaces,
        "required_authorizations": required_authorizations,
        "cloud_package_type": cloud_package_type,
        "cloud_package_policy": capability_row.get("cloud_package_policy")
        or capability_row.get("cloud_plugin_policy")
        or "isolated_cloud_profile_after_confirmation_stop_before_external_submit",
        "store_binding_policy": capability_row.get("store_binding_policy") or "one_store_one_route_no_cross_store_write_permission",
        "single_store_isolation_required": bool(capability_row.get("single_store_isolation_required", True)),
        "owner_confirmation_required": True,
        "external_submit_allowed": False,
        "blocked_external_actions": list(
            dict.fromkeys(
                [
                    *rule_list(capability_row.get("blocked_external_actions")),
                    "external_submit_without_owner_confirmation",
                    "budget_or_campaign_change_without_confirmation",
                ]
            )
        ),
        "official_sources": rule_list(capability_row.get("official_sources"))
        or [str(capability_row.get("official_source_url") or row.get("official_source_url") or "").strip()],
        "summary": developer_capability_plan_summary(requested_domains, cloud_package_type),
    }


def activity_capability_domains(activity_type: str, *, includes_ads: bool) -> list[str]:
    lowered = str(activity_type or "").lower()
    domains: list[str] = []
    if any(signal in lowered for signal in ["listing", "publish_listing", "product_listing", "item_sync"]):
        domains.append("listing")
    if any(signal in lowered for signal in ["coupon", "voucher", "discount", "promotion", "campaign", "deal", "bundle", "free_shipping", "shop_coupon", "seller_voucher", "price"]):
        domains.append("promotion")
    if any(signal in lowered for signal in ["coupon", "voucher", "discount", "free_shipping", "bundle", "shop_coupon", "seller_voucher"]):
        domains.append("coupon")
    if includes_ads or any(signal in lowered for signal in ACTIVITY_AD_SIGNALS):
        domains.append("ads")
    if any(signal in lowered for signal in ["affiliate", "creator", "live_coupon", "达人", "creator_coupon"]):
        domains.append("affiliate")
    if any(signal in lowered for signal in ["catalog", "feed", "asset", "content_catalog", "merchant_center", "product_feed"]):
        domains.append("catalog")
    domains.append("reporting")
    if len(domains) == 1:
        domains.insert(0, "promotion")
    return list(dict.fromkeys(domains))


def find_execution_capability_for_route(root: Path, row: dict[str, Any]) -> dict[str, Any]:
    route_channel = channel_id(row.get("channel_id"))
    route_country = str(row.get("country_code") or "GLOBAL").strip().upper() or "GLOBAL"
    route_model = normalize_store_model_for_route(row.get("store_model"))
    fallback: dict[str, Any] | None = None
    for item in load_platform_execution_capability_matrix(root):
        if channel_id(item.get("channel_id")) != route_channel:
            continue
        sites = [str(value).strip().upper() for value in rule_list(item.get("sites") or item.get("countries"))]
        models = [normalize_store_model_for_route(value) for value in rule_list(item.get("store_models"))]
        country_match = not sites or route_country in sites or "GLOBAL" in sites
        model_match = store_model_matches_rule(route_model, models)
        if country_match and model_match:
            return item
        if country_match and fallback is None:
            fallback = item
    if fallback:
        return fallback
    capability = next(
        (item for item in load_platform_capabilities(root) if channel_id(item.get("channel_id")) == route_channel),
        {},
    )
    return execution_capability_entry_from_capability(capability or row)


def execution_capability_entry_from_capability(capability: dict[str, Any]) -> dict[str, Any]:
    channel = channel_id(capability.get("channel_id"))
    sources = [str(capability.get("official_source_url") or "").strip()]
    return {
        "channel_id": channel,
        "label": capability.get("label") or channel,
        "sites": rule_list(capability.get("sites")) or ["GLOBAL"],
        "store_models": rule_list(capability.get("store_models")),
        "store_binding_policy": capability.get("store_binding_policy") or "one_store_one_route_no_cross_store_write_permission",
        "cloud_package_policy": capability.get("cloud_plugin_policy") or "isolated_cloud_profile_after_confirmation_stop_before_external_submit",
        "single_store_isolation_required": bool(capability.get("single_store_isolation_required", True)),
        "official_sources": [source for source in sources if source],
        "blocked_external_actions": ["external_submit_without_owner_confirmation", "budget_or_campaign_change_without_confirmation"],
        "domains": {
            "listing": {"mode": capability.get("listing") or "draft_then_confirmation", "surface": "listing_api_or_backend"},
            "promotion": {"mode": capability.get("promotion") or "draft_then_confirmation", "surface": "promotion_api_or_backend"},
            "coupon": {"mode": capability.get("discount") or "draft_then_confirmation", "surface": "coupon_or_discount_api"},
            "ads": {"mode": capability.get("ads") or "separate_ads_backend", "surface": "ads_backend_or_business_center", "required_authorizations": ["ads_account", "business_center"]},
            "affiliate": {"mode": "creator_or_affiliate_backend_draft", "surface": "affiliate_or_creator_backend"},
            "catalog": {"mode": "catalog_or_feed_draft", "surface": "content_catalog_or_feed_api"},
            "reporting": {"mode": "read_after_authorization", "surface": "api_report_or_report_import"},
        },
    }


def developer_capability_plan_summary(requested_domains: list[str], cloud_package_type: str) -> str:
    domain_text = ", ".join(requested_domains)
    return (
        f"按能力域 [{domain_text}] 准备 {cloud_package_type} 草稿和证据；"
        "确认前只停在后台草稿，不做真实外部提交。"
    )


def activity_plan_next_step(plan_status: str, row: dict[str, Any], *, includes_ads: bool) -> str:
    if plan_status == "not_supported_official_full_managed":
        return "不提供平台官方全托管执行；改走 TeeLab 代运营、TeeLab 自营或设计师自运营店铺路线。"
    if plan_status == "needs_platform_store":
        return "先由后台匹配或创建这条路径的真实平台店铺，再准备上架、拉单、活动、发券或广告动作。"
    if plan_status == "needs_ads_account":
        return "先补齐这条路径对应的广告账号和广告归属主体；未补齐前只保留投放草稿。"
    if plan_status == "rules_need_review":
        return "先保留为后台草稿；后台 AI 复核平台活动规则后，再交给负责人确认。"
    if plan_status == "ready_for_cloud_plugin_after_confirmation":
        return "先生成负责人确认包；确认后准备后台待执行包，并停在最终提交前。"
    if includes_ads:
        return "后台 AI 准备广告和活动草稿，计算保本 ROAS 与止损线，然后等待负责人确认。"
    return "后台 AI 准备活动草稿、叠加规则校验、毛利止损线和负责人确认包。"


def supported_alternative_routes_for_activity(route: dict[str, str]) -> list[dict[str, str]]:
    channel = channel_id(route.get("channel_id"))
    country = str(route.get("country_code") or "GLOBAL").strip().upper() or "GLOBAL"
    alternatives_by_channel = {
        "tiktok_shop": [
            ("platform_co_ops", "TeeLab 代运营 / 联名运营"),
            ("local_store", "本土店"),
            ("cross_border", "跨境店"),
            ("semi_managed_crossborder", "半托管跨境"),
            ("semi_managed_local", "半托管本土"),
            ("tiktok_accu_local", "ACCU / TikTok 本土店"),
        ],
        "shein": [
            ("platform_co_ops", "TeeLab 代运营 / 联名运营"),
            ("marketplace_seller", "平台卖家店"),
            ("local_store", "本土店"),
            ("cross_border", "跨境店"),
            ("semi_managed_crossborder", "半托管跨境"),
            ("semi_managed_local", "半托管本土"),
        ],
    }
    defaults = [
        ("platform_co_ops", "TeeLab 代运营 / 联名运营"),
        ("marketplace_seller", "平台卖家店"),
        ("self_store", "设计师自运营店"),
    ]
    result = []
    for store_model, label in alternatives_by_channel.get(channel, defaults):
        result.append(
            {
                "route_key": make_route_key(channel, country, store_model),
                "channel_id": channel,
                "country_code": country,
                "store_model": store_model,
                "label": label,
                "next_step": "按这个可接入模式重新生成活动/广告草稿和 ERP 映射准备。",
            }
        )
    return result


def build_activity_rule_playbook(
    row: dict[str, Any],
    request: dict[str, Any],
    *,
    includes_ads: bool,
) -> dict[str, Any]:
    campaign_window = str(row.get("site_campaign_window") or default_activity_campaign_window(row)).strip()
    focus = rule_list(row.get("site_activity_focus")) or default_activity_focus(row) or rule_list(row.get("activity_types"))[:5]
    stackability_checks = build_activity_stackability_checks(row, includes_ads=includes_ads)
    ads_notes = rule_list(row.get("site_ads_notes"))
    rule_notes = rule_list(row.get("site_rule_notes"))
    authorization_checks = rule_list(row.get("authorization_requirements"))
    submission_gates = list(dict.fromkeys([*rule_list(row.get("real_submission_requires")), *default_activity_submission_gates(row)]))
    calendar_slots = activity_calendar_slots(campaign_window, row)
    requested_activity = requested_activity_type(request)
    return {
        "campaign_window": campaign_window,
        "calendar_slots": calendar_slots,
        "site_activity_focus": focus,
        "requested_activity_type": requested_activity,
        "recommended_activity_type": recommend_activity_type_for_window(requested_activity, focus),
        "stackability_checks": stackability_checks,
        "ads_notes": ads_notes,
        "site_rule_notes": rule_notes,
        "authorization_checks": authorization_checks,
        "real_submission_gates": submission_gates,
        "requires_owner_confirmation": True,
        "external_submit_allowed": False,
        "api_boundary": row.get("api_boundary") or "rules_need_review",
        "ads_boundary": row.get("ads_boundary") or "rules_need_review",
        "summary": activity_rule_playbook_summary(campaign_window, focus, stackability_checks, submission_gates),
    }


def default_activity_campaign_window(row: dict[str, Any]) -> str:
    channel = channel_id(row.get("channel_id"))
    country = str(row.get("country_code") or "GLOBAL").strip().upper() or "GLOBAL"
    if country == "US":
        return "us_holiday_and_weekend_calendar" if channel in {"tiktok_shop", "shein", "amazon", "walmart"} else "us_marketplace_seasonal_calendar"
    if country == "MY":
        return "my_local_payday_and_double_day_calendar"
    if country == "TH":
        return "th_local_double_day_and_live_calendar"
    if country in {"MY", "SG", "TH", "VN", "PH", "ID"}:
        return f"{country.lower()}_local_double_day_and_payday_calendar"
    if country in {"MX", "BR"}:
        return f"{country.lower()}_marketplace_local_calendar"
    if country == "GLOBAL":
        return "evergreen_coupon_and_content_calendar"
    return f"{country.lower()}_local_seasonal_calendar"


def default_activity_focus(row: dict[str, Any]) -> list[str]:
    country = str(row.get("country_code") or "GLOBAL").strip().upper() or "GLOBAL"
    channel = channel_id(row.get("channel_id"))
    if channel == "tiktok_shop" and country == "US":
        return ["shop_ads_gmv_max", "creator_affiliate_push", "holiday_calendar", "shop_coupon", "free_shipping"]
    if channel == "tiktok_shop" and country == "MY":
        return ["localized_voucher", "free_shipping", "creator_affiliate_push", "payday_campaign", "live_coupon"]
    if channel == "tiktok_shop" and country == "TH":
        return ["localized_voucher", "free_shipping", "creator_affiliate_push", "live_coupon", "double_day_campaign"]
    if country in {"MY", "TH", "SG", "VN", "PH", "ID"}:
        return ["localized_voucher", "product_discount", "free_shipping", "double_day_campaign"]
    if country == "US":
        return ["seasonal_campaign", "shop_coupon", "product_discount", "creator_affiliate_push"]
    return []


def build_activity_stackability_checks(row: dict[str, Any], *, includes_ads: bool) -> list[str]:
    checks = [
        "platform_eligibility_check",
        *rule_list(row.get("stacking_rules")),
        *default_activity_site_checks(row),
        "margin_guardrail_passed",
        "inventory_sla_checked",
    ]
    if includes_ads:
        checks.extend(["ads_account_budget_check", "break_even_roas_passed"])
    if row.get("confirmation_required", True):
        checks.append("owner_confirmation_required")
    return list(dict.fromkeys(item for item in checks if item))


def default_activity_site_checks(row: dict[str, Any]) -> list[str]:
    country = str(row.get("country_code") or "GLOBAL").strip().upper() or "GLOBAL"
    if country == "US":
        return ["site_holiday_margin_check"]
    if country in {"MY", "TH", "SG", "VN", "PH", "ID"}:
        return ["country_site_rule_check", "local_fulfillment_sla_check"]
    if country in {"MX", "BR"}:
        return ["local_currency_margin_check", "local_delivery_sla_check"]
    return []


def default_activity_submission_gates(row: dict[str, Any]) -> list[str]:
    country = str(row.get("country_code") or "GLOBAL").strip().upper() or "GLOBAL"
    if country == "US":
        return ["site_calendar_checked"]
    if country in {"MY", "TH", "SG", "VN", "PH", "ID"}:
        return ["local_site_store_verified", "fulfillment_sla_passed"]
    if country in {"MX", "BR"}:
        return ["local_site_store_verified", "local_currency_margin_passed"]
    return ["owner_confirmation_required"]


def activity_calendar_slots(campaign_window: str, row: dict[str, Any]) -> list[str]:
    window = str(campaign_window or "").strip()
    mapping = {
        "us_holiday_and_weekend_calendar": ["weekend_flash_test", "summer_back_to_school", "q4_holiday_push"],
        "us_marketplace_seasonal_calendar": ["seasonal_campaign_review", "payday_coupon_test", "q4_holiday_push"],
        "my_local_payday_and_double_day_calendar": ["payday_25_31", "double_day_campaign", "weekend_live_coupon"],
        "th_local_double_day_and_live_calendar": ["double_day_campaign", "live_coupon_weekend", "local_language_campaign"],
        "my_shopee_double_day_and_payday_calendar": ["double_day_campaign", "payday_voucher", "free_shipping_push"],
        "th_shopee_double_day_and_local_calendar": ["double_day_campaign", "local_language_campaign", "shop_voucher_test"],
        "my_lazada_double_day_and_payday_calendar": ["double_day_campaign", "payday_seller_voucher", "free_shipping_push"],
        "th_lazada_double_day_and_local_calendar": ["double_day_campaign", "local_language_campaign", "seller_voucher_test"],
        "mx_marketplace_local_calendar": ["local_payday_campaign", "localized_price_check", "seasonal_campaign_review"],
        "evergreen_coupon_and_content_calendar": ["evergreen_coupon_test", "content_seed_test", "monthly_margin_review"],
    }
    if window in mapping:
        return mapping[window]
    focus = rule_list(row.get("site_activity_focus")) or rule_list(row.get("activity_types"))
    if focus:
        return focus[:3]
    return ["evergreen_coupon_test", "monthly_campaign_review", "margin_guardrail_review"]


def recommend_activity_type_for_window(requested_activity: str, focus: list[str]) -> str:
    if requested_activity and requested_activity != "activity_plan":
        return requested_activity
    if focus:
        return focus[0]
    return "activity_plan"


def activity_rule_playbook_summary(
    campaign_window: str,
    focus: list[str],
    stackability_checks: list[str],
    submission_gates: list[str],
) -> str:
    focus_text = ", ".join(focus[:3]) if focus else "activity draft"
    stack_text = ", ".join(stackability_checks[:3]) if stackability_checks else "stacking check"
    gate_text = ", ".join(submission_gates[:3]) if submission_gates else "owner confirmation"
    return (
        f"Use {campaign_window or 'route calendar'}; focus on {focus_text}; "
        f"check {stack_text}; require {gate_text}; no external submission before approval."
    )


def build_ad_budget_plan(
    request: dict[str, Any],
    row: dict[str, Any],
    stack_guardrail: dict[str, Any],
    *,
    includes_ads: bool,
    missing_prerequisites: list[str],
) -> dict[str, Any]:
    if not includes_ads:
        return {"applies": False, "external_submit_allowed": False}
    ads_missing = [item for item in missing_prerequisites if item in {"ads_account", "business_center"}]
    if ads_missing:
        return {
            "applies": True,
            "planning_status": "needs_ads_identity",
            "missing_prerequisites": ads_missing,
            "external_submit_allowed": False,
            "budget_change_allowed": False,
            "summary": "Ads account and ad ownership must be confirmed before AI can prepare ad budget drafts.",
        }
    if not stack_guardrail.get("can_evaluate_margin"):
        return {
            "applies": True,
            "planning_status": "needs_unit_economics",
            "missing_prerequisites": stack_guardrail.get("missing_inputs") or ["list_price", "product_cost"],
            "external_submit_allowed": False,
            "budget_change_allowed": False,
            "summary": "Price and cost are required before setting a paid ads budget ladder.",
        }
    if str(stack_guardrail.get("calculation_status") or "") == "margin_stop":
        return {
            "applies": True,
            "planning_status": "stop_before_ads",
            "external_submit_allowed": False,
            "budget_change_allowed": False,
            "summary": "Margin is below guardrail; do not launch or raise ads budget.",
            "pause_rules": ["margin_below_guardrail", "negative_profit_before_ads"],
        }

    customer_price = positive_float(stack_guardrail.get("customer_price")) or 0.0
    profit_before_ads = positive_float(stack_guardrail.get("profit_before_ads")) or 0.0
    break_even_roas = positive_float(stack_guardrail.get("break_even_roas"))
    target_roas = positive_float(stack_guardrail.get("target_roas"))
    requested_daily_budget = positive_float(stack_guardrail.get("daily_ad_budget")) or positive_float(request.get("daily_ad_budget") or request.get("ad_budget") or request.get("budget"))
    safe_daily_budget = positive_float(stack_guardrail.get("safe_daily_ad_budget"))
    requested_creative_count = creative_count_from_request(request)
    creative_count = int(requested_creative_count or 3)
    creative_count = max(1, min(creative_count, 12))
    creative_scorecard = build_ad_creative_scorecard(request, row, creative_count=creative_count)
    test_days = int(positive_float(request.get("test_days") or request.get("min_test_days")) or 3)
    test_days = max(2, min(test_days, 7))
    target_roas_for_rule = target_roas or (break_even_roas * 1.15 if break_even_roas else None)
    cold_start_budget = choose_cold_start_daily_budget(
        requested_daily_budget=requested_daily_budget,
        safe_daily_budget=safe_daily_budget,
        customer_price=customer_price,
        profit_before_ads=profit_before_ads,
    )
    budget_cap = safe_daily_budget if safe_daily_budget is not None else cold_start_budget
    warnings: list[str] = []
    if safe_daily_budget is not None and requested_daily_budget and requested_daily_budget > safe_daily_budget:
        warnings.append("requested_budget_above_safe_cap")
    if break_even_roas is None:
        warnings.append("break_even_roas_unavailable")
    if target_roas and break_even_roas and target_roas < break_even_roas:
        warnings.append("target_roas_below_break_even")
    if creative_scorecard.get("creative_status") != "creative_ready":
        warnings.append("creative_assets_need_review")
    planning_status = "ads_budget_warning" if warnings else "ready_for_confirmed_ads_draft"
    no_order_spend_cap = max(customer_price, profit_before_ads * 2, cold_start_budget * 1.2)
    scale_threshold = round_metric((break_even_roas or 1) * 1.25) or None
    hold_threshold = round_metric((break_even_roas or 1) * 1.05) or None
    next_budget = min(cold_start_budget * 1.3, budget_cap) if budget_cap else cold_start_budget * 1.2
    return {
        "applies": True,
        "planning_status": planning_status,
        "external_submit_allowed": False,
        "budget_change_allowed": False,
        "requires_owner_confirmation": True,
        "ads_boundary": row.get("ads_boundary") or "ads_need_separate_review",
        "creative_count": creative_count,
        "creative_scorecard": creative_scorecard,
        "test_days": test_days,
        "cold_start_daily_budget": round_money(cold_start_budget),
        "budget_cap_per_day": round_money(budget_cap),
        "safe_daily_ad_budget": round_money(safe_daily_budget),
        "requested_daily_budget": round_money(requested_daily_budget),
        "budget_per_creative": round_money(cold_start_budget / creative_count),
        "break_even_roas": round_metric(break_even_roas),
        "target_roas": round_metric(target_roas_for_rule),
        "no_order_spend_cap": round_money(no_order_spend_cap),
        "budget_ladder": [
            {
                "stage": "cold_start",
                "days": f"1-{test_days}",
                "daily_budget": round_money(cold_start_budget),
                "creative_count": creative_count,
                "rule": "collect_clicks_orders_and_creative_signal_no_auto_scale",
            },
            {
                "stage": "validate",
                "daily_budget": round_money(next_budget),
                "rule": "raise_only_after_break_even_roas_and_owner_confirmation",
            },
            {
                "stage": "scale",
                "daily_budget": round_money(budget_cap),
                "rule": "scale_max_30_percent_after_two_good_days_and_confirmation",
            },
        ],
        "pause_rules": [
            "pause_if_spend_reaches_no_order_cap_without_order",
            "pause_if_roas_below_break_even_after_test_window",
            "pause_if_refund_or_stock_sla_risk_appears",
        ],
        "scale_rules": [
            f"scale_if_roas_at_or_above_{scale_threshold}_for_two_days" if scale_threshold else "scale_only_after_positive_roas_signal",
            "scale_only_if_margin_inventory_and_owner_confirmation_pass",
            "do_not_raise_budget_more_than_30_percent_per_day",
        ],
        "hold_rules": [
            f"hold_if_roas_between_break_even_and_{hold_threshold}" if hold_threshold else "hold_until_roas_is_clear",
            "refresh_creative_before_budget_increase",
        ],
        "creative_test_plan": creative_scorecard.get("test_plan") or [],
        "warnings": warnings,
        "summary": "AI may prepare an ads draft and budget ladder, but launch, pause, and budget changes require owner confirmation.",
    }


def build_ad_creative_scorecard(
    request: dict[str, Any],
    row: dict[str, Any],
    *,
    creative_count: int,
) -> dict[str, Any]:
    assets = creative_assets_from_request(request)
    text = creative_request_text(request, assets)
    explicit_count = creative_count_from_request(request)
    evaluated_count = max(len(assets), int(explicit_count or 0))
    if evaluated_count <= 0 and creative_count and request_flag(
        request,
        ["creative_ready", "has_creative_assets", "materials_ready"],
        text,
        ["creative ready", "materials ready", "素材齐", "素材已备", "素材准备"],
    ):
        evaluated_count = creative_count

    signals = {
        "product_proof": request_flag(
            request,
            ["has_product_proof", "product_proof_ready", "proof_ready", "has_product_video", "has_product_demo"],
            text,
            ["product proof", "demo", "unboxing", "review", "detail shot", "buyer proof", "实拍", "细节", "测评", "买家秀"],
        ),
        "hook": request_flag(
            request,
            ["has_hook", "has_viral_hook", "hook_ready", "opening_hook_ready"],
            text,
            ["hook", "0-2", "opening", "first second", "pain point", "钩子", "开头", "前三秒", "痛点"],
        ),
        "offer": request_flag(
            request,
            ["has_offer", "has_coupon", "offer_ready", "coupon_ready", "discount_ready"],
            text,
            ["offer", "coupon", "voucher", "discount", "deal", "优惠", "折扣", "店铺券", "券"],
        ),
        "creator_or_ugc": request_flag(
            request,
            ["has_ugc", "has_creator", "creator_ready", "has_influencer", "ugc_ready"],
            text,
            ["ugc", "creator", "influencer", "testimonial", "达人", "种草", "买家", "评论", "达人视频"],
        ),
        "cta_product_card": request_flag(
            request,
            ["has_cta", "has_product_card", "product_card_ready", "link_ready"],
            text,
            ["cta", "call to action", "product card", "shop now", "link", "上链接", "商品卡", "购物车", "引导购买"],
        ),
        "compliance_review": request_flag(
            request,
            ["has_compliance_review", "compliance_reviewed", "music_rights_reviewed", "ip_reviewed", "claim_reviewed"],
            text,
            ["compliance review", "music rights", "ip review", "claim review", "合规", "授权", "音乐版权", "侵权", "审核"],
        ),
    }
    weights = {
        "product_proof": 20,
        "hook": 20,
        "offer": 15,
        "creator_or_ugc": 15,
        "cta_product_card": 10,
        "compliance_review": 10,
    }
    score = sum(weight for key, weight in weights.items() if signals.get(key))
    if evaluated_count >= MIN_CREATIVE_TEST_COUNT:
        score += 10
    elif evaluated_count >= 2:
        score += 4

    missing_assets: list[str] = []
    if not signals["product_proof"]:
        missing_assets.append("product_proof")
    if not signals["hook"]:
        missing_assets.append("hook")
    if not signals["offer"]:
        missing_assets.append("offer")
    if not signals["creator_or_ugc"]:
        missing_assets.append("creator_or_ugc")
    if not signals["cta_product_card"]:
        missing_assets.append("cta_product_card")
    if evaluated_count < MIN_CREATIVE_TEST_COUNT:
        missing_assets.append("creative_variety")
    required_reviews: list[str] = []
    if not signals["compliance_review"]:
        missing_assets.append("compliance_review")
        required_reviews = ["ip_review", "music_rights_review", "claim_review"]

    if not missing_assets:
        creative_status = "creative_ready"
    elif any(item in missing_assets for item in ["product_proof", "hook", "creative_variety"]):
        creative_status = "creative_needs_assets"
    else:
        creative_status = "creative_review_required"

    test_plan = build_ad_creative_test_plan(signals, evaluated_count)
    return {
        "creative_status": creative_status,
        "score": min(score, 100),
        "creative_count": evaluated_count,
        "minimum_creative_count": MIN_CREATIVE_TEST_COUNT,
        "missing_assets": missing_assets,
        "strengths": [key for key, present in signals.items() if present],
        "required_reviews": required_reviews,
        "test_plan": test_plan,
        "replacement_rules": [
            "pause_material_with_no_click_signal_after_test_window",
            "replace_loser_creatives_before_budget_scale",
            "no_budget_increase_until_creative_and_roas_pass",
        ],
        "external_submit_allowed": False,
        "source": row.get("route_key") or row.get("channel_id") or "activity_route",
    }


def build_ad_creative_test_plan(signals: dict[str, bool], evaluated_count: int) -> list[str]:
    plan: list[str] = []
    plan.append("product_proof_creative" if signals.get("product_proof") else "collect_product_proof_creative")
    plan.append("hook_first_three_seconds_creative" if signals.get("hook") else "draft_hook_creative")
    plan.append("creator_hook_creative" if signals.get("creator_or_ugc") else "seed_creator_or_ugc_creative")
    if signals.get("offer"):
        plan.append("offer_angle_creative")
    else:
        plan.append("draft_offer_angle_creative")
    if evaluated_count >= MIN_CREATIVE_TEST_COUNT:
        plan.append("rotate_minimum_three_creatives")
    else:
        plan.append("create_minimum_three_creatives")
    plan.append("replace_loser_creatives_before_budget_scale")
    return plan


def creative_count_from_request(request: dict[str, Any]) -> int | None:
    for key in ["creative_count", "material_count", "asset_count", "video_count", "素材数量"]:
        value = positive_float(request.get(key))
        if value is not None:
            return max(0, min(int(value), 50))
    assets = creative_assets_from_request(request)
    if assets:
        return min(len(assets), 50)
    text = creative_request_text(request, [])
    patterns = [
        r"([0-9]+)\s*(?:creatives?|materials?|assets?|videos?|素材|条素材|个素材)",
        r"(?:creative|material|asset|video|素材|视频)[^0-9]{0,8}([0-9]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = positive_float(match.group(1))
            if value is not None:
                return max(0, min(int(value), 50))
    return None


def creative_assets_from_request(request: dict[str, Any]) -> list[Any]:
    for key in ["creative_assets", "creatives", "materials", "assets", "videos"]:
        value = request.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = value.get("items") or value.get("assets") or value.get("creatives")
            if isinstance(nested, list):
                return nested
            return [value]
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                nested = parsed.get("items") or parsed.get("assets") or parsed.get("creatives")
                if isinstance(nested, list):
                    return nested
                return [parsed]
    return []


def creative_request_text(request: dict[str, Any], assets: list[Any]) -> str:
    fields = ["goal", "message", "title", "description", "notes", "pricing_text", "creative_notes", "page_context"]
    parts = [str(request.get(key) or "") for key in fields]
    if assets:
        parts.append(json.dumps(assets, ensure_ascii=False, default=str))
    return " ".join(parts)


def request_flag(
    request: dict[str, Any],
    keys: list[str],
    text: str,
    terms: list[str],
) -> bool:
    for key in keys:
        if key not in request:
            continue
        value = request.get(key)
        if isinstance(value, bool):
            return value
        clean = str(value or "").strip().lower()
        if clean in {"1", "true", "yes", "y", "ready", "ok", "pass", "passed"}:
            return True
        if clean in {"0", "false", "no", "n", "missing", "none", "not_ready"}:
            return False
    return text_has_any(text, terms)


def text_has_any(text: str, terms: list[str]) -> bool:
    lowered = str(text or "").lower()
    return any(term.lower() in lowered for term in terms if term)


def choose_cold_start_daily_budget(
    *,
    requested_daily_budget: float | None,
    safe_daily_budget: float | None,
    customer_price: float,
    profit_before_ads: float,
) -> float:
    if requested_daily_budget is not None:
        return min(requested_daily_budget, safe_daily_budget) if safe_daily_budget is not None else requested_daily_budget
    floor = max(10.0, min(30.0, customer_price or 10.0))
    if safe_daily_budget is None:
        return floor
    if safe_daily_budget <= 0:
        return 0.0
    suggested = max(floor, min(safe_daily_budget * 0.5, profit_before_ads * 3 if profit_before_ads > 0 else floor))
    return min(suggested, safe_daily_budget)


def build_activity_stack_guardrail(
    request: dict[str, Any],
    row: dict[str, Any],
    *,
    includes_ads: bool,
) -> dict[str, Any]:
    inputs = activity_stack_inputs(request, row)
    missing = [
        field
        for field in ["list_price", "product_cost"]
        if inputs.get(field) is None
    ]
    source_notes = inputs.pop("source_notes", [])
    if missing:
        return {
            "calculation_status": "needs_price_cost_inputs",
            "can_evaluate_margin": False,
            "missing_inputs": missing,
            "source_notes": source_notes,
            "summary": "Price and product cost are required before AI can judge discount stacking, margin, or ad break-even.",
            "external_submit_allowed": False,
        }

    list_price = max(float(inputs["list_price"] or 0), 0.0)
    product_cost = max(float(inputs["product_cost"] or 0), 0.0)
    shipping_cost = max(float(inputs.get("shipping_cost") or 0), 0.0)
    handling_cost = max(float(inputs.get("handling_cost") or 0), 0.0)
    discount_amount = max(float(inputs.get("discount_amount") or 0), 0.0)
    coupon_amount = max(float(inputs.get("coupon_amount") or 0), 0.0)
    discount_rate = clamp_rate(inputs.get("discount_rate"))
    coupon_rate = clamp_rate(inputs.get("coupon_rate"))
    platform_subsidy_amount = max(float(inputs.get("platform_subsidy_amount") or 0), 0.0)
    platform_subsidy_rate = clamp_rate(inputs.get("platform_subsidy_rate"))
    platform_fee_rate = clamp_rate(inputs.get("platform_fee_rate"))
    creator_commission_rate = clamp_rate(inputs.get("creator_commission_rate"))
    min_margin_rate = clamp_rate(inputs.get("min_margin_rate"), default=DEFAULT_MIN_ACTIVITY_MARGIN_RATE)
    expected_orders = max(float(inputs.get("expected_orders") or 0), 0.0)
    target_roas = positive_float(inputs.get("target_roas"))
    daily_ad_budget = positive_float(inputs.get("daily_ad_budget"))
    ad_spend_per_order = positive_float(inputs.get("ad_spend_per_order"))
    if ad_spend_per_order is None and target_roas and list_price > 0:
        ad_spend_per_order = list_price / target_roas

    seller_discount_amount = min(
        list_price,
        discount_amount + coupon_amount + list_price * discount_rate + list_price * coupon_rate,
    )
    platform_subsidy_total = platform_subsidy_amount + list_price * platform_subsidy_rate
    customer_price = max(list_price - seller_discount_amount, 0.0)
    fee_amount = customer_price * platform_fee_rate
    creator_commission_amount = customer_price * creator_commission_rate
    fixed_cost = product_cost + shipping_cost + handling_cost
    seller_revenue_after_fees = customer_price + platform_subsidy_total - fee_amount - creator_commission_amount
    profit_before_ads = seller_revenue_after_fees - fixed_cost
    profit_after_ads = profit_before_ads - (ad_spend_per_order or 0.0)
    revenue_base = max(customer_price + platform_subsidy_total, 0.01)
    contribution_margin_rate = profit_before_ads / revenue_base
    final_margin_rate = profit_after_ads / revenue_base
    break_even_roas = customer_price / profit_before_ads if profit_before_ads > 0 and customer_price > 0 else None
    budget_safety_ratio = clamp_rate(inputs.get("budget_safety_ratio"), default=DEFAULT_AD_BUDGET_PROFIT_SHARE)
    safe_daily_ad_budget = profit_before_ads * expected_orders * budget_safety_ratio if expected_orders and profit_before_ads > 0 else None
    max_discount_rate = max_seller_discount_rate_at_margin(
        list_price=list_price,
        fixed_cost=fixed_cost,
        platform_fee_rate=platform_fee_rate,
        creator_commission_rate=creator_commission_rate,
        min_margin_rate=min_margin_rate,
        platform_subsidy_total=platform_subsidy_total,
    )

    warnings: list[str] = []
    if customer_price <= 0:
        warnings.append("discount_wipes_out_price")
    if profit_before_ads <= 0:
        warnings.append("negative_profit_before_ads")
    if contribution_margin_rate < min_margin_rate:
        warnings.append("margin_below_guardrail")
    if includes_ads and break_even_roas is None:
        warnings.append("ads_break_even_not_available")
    if includes_ads and target_roas and break_even_roas and target_roas < break_even_roas:
        warnings.append("target_roas_below_break_even")
    if includes_ads and daily_ad_budget and safe_daily_ad_budget is not None and daily_ad_budget > safe_daily_ad_budget:
        warnings.append("daily_budget_above_safe_cap")
    if includes_ads and daily_ad_budget is None and ad_spend_per_order is None:
        warnings.append("ads_budget_needed")

    if "negative_profit_before_ads" in warnings or "margin_below_guardrail" in warnings:
        status = "margin_stop"
    elif "target_roas_below_break_even" in warnings or "daily_budget_above_safe_cap" in warnings:
        status = "ads_guardrail_warning"
    elif warnings:
        status = "needs_review"
    else:
        status = "margin_pass"

    return {
        "calculation_status": status,
        "can_evaluate_margin": True,
        "external_submit_allowed": False,
        "inputs": rounded_activity_numbers(inputs),
        "list_price": round_money(list_price),
        "seller_discount_amount": round_money(seller_discount_amount),
        "seller_discount_rate": round_rate(seller_discount_amount / list_price if list_price else 0),
        "customer_price": round_money(customer_price),
        "platform_subsidy_total": round_money(platform_subsidy_total),
        "platform_fee_amount": round_money(fee_amount),
        "creator_commission_amount": round_money(creator_commission_amount),
        "fixed_cost": round_money(fixed_cost),
        "profit_before_ads": round_money(profit_before_ads),
        "profit_after_ads_per_order": round_money(profit_after_ads),
        "contribution_margin_rate": round_rate(contribution_margin_rate),
        "final_margin_rate": round_rate(final_margin_rate),
        "min_margin_rate": round_rate(min_margin_rate),
        "break_even_roas": round_metric(break_even_roas),
        "target_roas": round_metric(target_roas),
        "safe_daily_ad_budget": round_money(safe_daily_ad_budget),
        "daily_ad_budget": round_money(daily_ad_budget),
        "max_seller_discount_rate_at_min_margin": round_rate(max_discount_rate),
        "warnings": warnings,
        "source_notes": source_notes,
        "summary": activity_stack_guardrail_summary(status, includes_ads=includes_ads),
    }


def activity_stack_inputs(request: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(
        str(request.get(key) or "")
        for key in ["goal", "message", "title", "description", "notes", "pricing_text"]
    )
    channel = channel_id(row.get("channel_id") or request.get("channel_id") or request.get("platform"))
    inputs = {
        "list_price": activity_number_from_request(request, ["list_price", "price", "sale_price", "selling_price"], text, ["price", "售价", "客单价"]),
        "product_cost": activity_number_from_request(request, ["product_cost", "cost", "cogs", "production_cost"], text, ["cost", "成本", "生产成本"]),
        "shipping_cost": activity_number_from_request(request, ["shipping_cost", "logistics_cost", "fulfillment_cost"], text, ["shipping", "物流", "运费"]),
        "handling_cost": activity_number_from_request(request, ["handling_cost", "packaging_cost"], text, ["handling", "包装"]),
        "discount_amount": activity_number_from_request(request, ["discount_amount", "product_discount_amount"], text, ["discount amount", "折扣金额"]),
        "coupon_amount": activity_number_from_request(request, ["coupon_amount", "voucher_amount"], text, ["coupon", "voucher", "优惠券", "店铺券"]),
        "platform_subsidy_amount": activity_number_from_request(request, ["platform_subsidy_amount", "subsidy_amount"], text, ["platform subsidy", "平台补贴"]),
        "daily_ad_budget": activity_number_from_request(request, ["daily_ad_budget", "ad_budget", "budget"], text, ["daily budget", "ad budget", "预算", "日预算"]),
        "ad_spend_per_order": activity_number_from_request(request, ["ad_spend_per_order", "target_cpa", "expected_cpa", "cpa"], text, ["cpa", "单单广告费"]),
        "expected_orders": activity_number_from_request(request, ["expected_orders", "orders"], text, ["orders", "预计订单", "订单"]),
        "target_roas": activity_number_from_request(request, ["target_roas", "expected_roas", "roas"], text, ["roas", "目标roas"]),
        "discount_rate": activity_rate_from_request(request, ["discount_rate", "product_discount_rate"], text, ["discount", "折扣"]),
        "coupon_rate": activity_rate_from_request(request, ["coupon_rate", "voucher_rate"], text, ["coupon rate", "voucher rate", "券率"]),
        "platform_subsidy_rate": activity_rate_from_request(request, ["platform_subsidy_rate", "subsidy_rate"], text, ["platform subsidy", "平台补贴"]),
        "platform_fee_rate": activity_rate_from_request(request, ["platform_fee_rate", "commission_rate", "referral_fee_rate"], text, ["platform fee", "平台费", "佣金"]),
        "creator_commission_rate": activity_rate_from_request(request, ["creator_commission_rate", "affiliate_commission_rate"], text, ["creator commission", "affiliate", "达人佣金"]),
        "min_margin_rate": activity_rate_from_request(request, ["min_margin_rate", "target_margin_rate"], text, ["min margin", "最低毛利", "目标毛利"]),
        "budget_safety_ratio": activity_rate_from_request(request, ["budget_safety_ratio", "ad_budget_profit_share"], text, ["budget safety", "预算安全"]),
        "source_notes": [],
    }
    if inputs["platform_fee_rate"] is None:
        inputs["platform_fee_rate"] = DEFAULT_ACTIVITY_FEE_RATES.get(channel, 0.10)
        inputs["source_notes"].append("platform_fee_rate_defaulted_by_channel")
    if inputs["min_margin_rate"] is None:
        inputs["min_margin_rate"] = DEFAULT_MIN_ACTIVITY_MARGIN_RATE
        inputs["source_notes"].append("min_margin_rate_defaulted")
    if inputs["budget_safety_ratio"] is None:
        inputs["budget_safety_ratio"] = DEFAULT_AD_BUDGET_PROFIT_SHARE
        inputs["source_notes"].append("budget_safety_ratio_defaulted")
    return inputs


def activity_number_from_request(
    request: dict[str, Any],
    keys: list[str],
    text: str,
    labels: list[str],
) -> float | None:
    for key in keys:
        value = positive_float(request.get(key))
        if value is not None:
            return value
    return parse_activity_number(text, labels)


def activity_rate_from_request(
    request: dict[str, Any],
    keys: list[str],
    text: str,
    labels: list[str],
) -> float | None:
    for key in keys:
        value = request.get(key)
        if value is None or value == "":
            continue
        parsed = parse_rate_value(value)
        if parsed is not None:
            return parsed
    return parse_activity_rate(text, labels)


def parse_activity_number(text: str, labels: list[str]) -> float | None:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*(?:=|:|：|is|为)?\s*[$￥€£]?\s*([0-9]+(?:\.[0-9]+)?)(?!\s*%)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return positive_float(match.group(1))
    return None


def parse_activity_rate(text: str, labels: list[str]) -> float | None:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*(?:=|:|：|is|为)?\s*([0-9]+(?:\.[0-9]+)?)\s*%"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return parse_rate_value(match.group(1) + "%")
    return None


def parse_rate_value(value: Any) -> float | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text.replace("%", "").strip())
    except ValueError:
        return None
    if "%" in text or number > 1:
        number = number / 100
    return clamp_rate(number)


def positive_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(str(value).replace("$", "").replace("￥", "").replace(",", "").strip())
    except ValueError:
        return None
    return number if number >= 0 else None


def clamp_rate(value: Any, *, default: float = 0.0) -> float:
    parsed = parse_rate_value(value) if not isinstance(value, (int, float)) else float(value)
    if parsed is None:
        parsed = default
    return min(max(parsed, 0.0), 0.95)


def max_seller_discount_rate_at_margin(
    *,
    list_price: float,
    fixed_cost: float,
    platform_fee_rate: float,
    creator_commission_rate: float,
    min_margin_rate: float,
    platform_subsidy_total: float,
) -> float | None:
    if list_price <= 0:
        return None
    variable_keep_rate = 1 - platform_fee_rate - creator_commission_rate - min_margin_rate
    if variable_keep_rate <= 0:
        return 0.0
    minimum_customer_price = max((fixed_cost - platform_subsidy_total) / variable_keep_rate, 0.0)
    return min(max((list_price - minimum_customer_price) / list_price, 0.0), 0.95)


def rounded_activity_numbers(inputs: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in inputs.items():
        if isinstance(value, (int, float)):
            result[key] = round_metric(float(value))
        elif value is not None:
            result[key] = value
    return result


def round_money(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def round_rate(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def round_metric(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 3)


def activity_stack_guardrail_summary(status: str, *, includes_ads: bool) -> str:
    if status == "margin_pass":
        return "Margin guardrail passed. Keep the draft in confirmation before any external submission."
    if status == "margin_stop":
        return "Margin is below the guardrail. Do not submit this campaign or discount until price, cost, coupon, or commission is adjusted."
    if status == "ads_guardrail_warning":
        return "Ads budget or ROAS is risky. Keep as a draft and reduce budget or raise expected ROAS before approval."
    if includes_ads:
        return "Ads guardrail needs review before any launch or budget change."
    return "Activity stack needs review before confirmation."


def activity_source_review(root: Path) -> dict[str, Any]:
    payload = load_json(config_path(root, PLATFORM_ACTIVITY_RULE_FILENAME))
    if isinstance(payload, dict) and isinstance(payload.get("source_review"), dict):
        return payload["source_review"]
    return {
        "default_boundary": "Activity, promotion, coupon, price, ad, budget, refund, shipment, and authorization changes require confirmation.",
        "required_checks": ["eligibility", "stacking", "margin", "inventory", "fulfillment_sla", "platform_policy"],
    }


def find_activity_rule_for_route(
    route: dict[str, Any],
    rules: list[dict[str, Any]],
    site_overrides: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    route_channel = channel_id(route.get("channel_id"))
    route_country = str(route.get("country_code") or "GLOBAL").strip().upper() or "GLOBAL"
    route_model = normalize_store_model_for_route(route.get("store_model"))
    best: dict[str, Any] | None = None
    best_rank = -1
    fallback: dict[str, Any] | None = None
    for rule in rules:
        if channel_id(rule.get("channel_id")) != route_channel:
            continue
        countries = [str(item).strip().upper() for item in rule_list(rule.get("countries") or rule.get("sites"))]
        models = [normalize_store_model_for_route(item) for item in rule_list(rule.get("store_models"))]
        country_match = not countries or route_country in countries or "GLOBAL" in countries
        model_rank = store_model_match_rank(route_model, models)
        if country_match and model_rank > best_rank:
            best = rule
            best_rank = model_rank
            if model_rank >= 2:
                continue
        if country_match and fallback is None:
            fallback = rule
    if best and best_rank > 0:
        return merge_site_activity_override(route, best, site_overrides or [])
    if fallback:
        return merge_site_activity_override(route, fallback, site_overrides or [])
    return None


def merge_site_activity_override(
    route: dict[str, Any],
    base_rule: dict[str, Any],
    site_overrides: list[dict[str, Any]],
) -> dict[str, Any]:
    override = find_site_activity_override(route, site_overrides)
    if not override:
        return base_rule
    merged = dict(base_rule)
    for field in [
        "site_override_id",
        "site_activity_focus",
        "site_campaign_window",
        "site_ads_notes",
        "site_rule_notes",
    ]:
        if override.get(field):
            merged[field] = override.get(field)
    append_rule_values(merged, "activity_types", override.get("activity_types_add"))
    append_rule_values(merged, "stacking_rules", override.get("stacking_rules_add"))
    append_rule_values(merged, "authorization_requirements", override.get("authorization_requirements_add"))
    append_rule_values(merged, "execution_surfaces", override.get("execution_surfaces_add"))
    append_rule_values(merged, "real_submission_requires", override.get("real_submission_requires_add"))
    return merged


def find_site_activity_override(route: dict[str, Any], site_overrides: list[dict[str, Any]]) -> dict[str, Any] | None:
    route_channel = channel_id(route.get("channel_id"))
    route_country = str(route.get("country_code") or "GLOBAL").strip().upper() or "GLOBAL"
    route_model = normalize_store_model_for_route(route.get("store_model"))
    best: dict[str, Any] | None = None
    best_rank = -1
    fallback: dict[str, Any] | None = None
    for override in site_overrides:
        if channel_id(override.get("channel_id")) != route_channel:
            continue
        countries = [str(item).strip().upper() for item in rule_list(override.get("countries") or override.get("sites"))]
        models = [normalize_store_model_for_route(item) for item in rule_list(override.get("store_models"))]
        country_match = not countries or route_country in countries or "GLOBAL" in countries
        model_rank = store_model_match_rank(route_model, models)
        if country_match and model_rank > best_rank:
            best = override
            best_rank = model_rank
            if model_rank >= 2:
                continue
        if country_match and fallback is None:
            fallback = override
    if best and best_rank > 0:
        return best
    return fallback


def append_rule_values(target: dict[str, Any], field: str, values: Any) -> None:
    additions = rule_list(values)
    if not additions:
        return
    existing = rule_list(target.get(field))
    seen = set(existing)
    for item in additions:
        if item in seen:
            continue
        existing.append(item)
        seen.add(item)
    target[field] = existing


def activity_row_from_route(
    route: dict[str, Any],
    rule: dict[str, Any] | None,
    *,
    status: str,
    execution_mode: str,
    next_step: str,
) -> dict[str, Any]:
    rule = rule or {}
    row = {
        "route_key": route.get("route_key") or make_route_key(route.get("channel_id"), route.get("country_code"), route.get("store_model")),
        "channel_id": route.get("channel_id") or channel_id(rule.get("channel_id")),
        "country_code": str(route.get("country_code") or "GLOBAL").strip().upper() or "GLOBAL",
        "store_model": route.get("store_model") or "store_model_pending",
        "source_status": route.get("status") or "",
        "status": status,
        "activity_types": rule_list(rule.get("activity_types")),
        "activity_mechanisms": rule.get("activity_mechanisms") if isinstance(rule.get("activity_mechanisms"), list) else [],
        "developer_rule_summary": rule.get("developer_rule_summary") or "",
        "stacking_rules": rule_list(rule.get("stacking_rules")),
        "api_boundary": rule.get("api_boundary") or "rules_need_review",
        "ads_boundary": rule.get("ads_boundary") or "rules_need_review",
        "execution_mode": execution_mode,
        "margin_guardrail": rule.get("margin_guardrail") or "needs_margin_review",
        "inventory_guardrail": rule.get("inventory_guardrail") or "needs_inventory_review",
        "confirmation_required": True if rule.get("confirmation_required", True) else False,
        "official_source_url": rule.get("official_source_url") or "",
        "authorization_requirements": rule_list(rule.get("authorization_requirements")),
        "execution_surfaces": rule_list(rule.get("execution_surfaces")),
        "platform_rule_scope": rule.get("platform_rule_scope") or "route_key",
        "customer_execution_boundary": rule.get("customer_execution_boundary") or "",
        "cloud_plugin_reason": rule.get("cloud_plugin_reason") or "",
        "real_submission_requires": rule_list(rule.get("real_submission_requires")),
        "automation_level": rule.get("automation_level") or "L2_draft_or_L3_after_confirmation",
        "site_override_id": rule.get("site_override_id") or "",
        "site_activity_focus": rule_list(rule.get("site_activity_focus")),
        "site_campaign_window": rule.get("site_campaign_window") or "",
        "site_ads_notes": rule_list(rule.get("site_ads_notes")),
        "site_rule_notes": rule_list(rule.get("site_rule_notes")),
        "ads_account_status": route.get("ads_account_status") or "missing",
        "business_center_status": route.get("business_center_status") or "missing",
        "next_step": next_step,
    }
    readiness, label = activity_execution_readiness(row)
    row["execution_readiness"] = readiness
    row["execution_readiness_label"] = label
    if not usable_config_text(row["customer_execution_boundary"]):
        row["customer_execution_boundary"] = default_customer_execution_boundary(readiness)
    if not usable_config_text(row["cloud_plugin_reason"]):
        row["cloud_plugin_reason"] = default_cloud_plugin_reason(row)
    return row


def activity_execution_readiness(row: dict[str, Any]) -> tuple[str, str]:
    status = str(row.get("status") or "")
    execution_mode = str(row.get("execution_mode") or "")
    ads_boundary = str(row.get("ads_boundary") or "")
    ads_status = str(row.get("ads_account_status") or "")
    business_status = str(row.get("business_center_status") or "")
    if status in {"needs_platform_store", "route_needed"}:
        return "needs_platform_store", "缺店铺"
    if (
        status == "rule_available"
        and ads_boundary
        and ads_boundary not in {"not_store_api", "ads_need_separate_review"}
        and (ads_status != "registered" or business_status != "registered")
    ):
        return "needs_ads_account", "缺广告账号"
    if "isolated_cloud_plugin" in execution_mode:
        return "ready_after_confirmation", "确认后可执行"
    return "draft_only", "只能草稿"


def default_customer_execution_boundary(readiness: str) -> str:
    if readiness == "needs_platform_store":
        return "后台还没有真实平台店铺；只能做候选规划、规则学习和开店准备。"
    if readiness == "needs_ads_account":
        return "后台还没有广告账号和广告归属主体；只能保留广告草稿、预算上限和止损线。"
    if readiness == "ready_after_confirmation":
        return "后台 AI 可以生成确认包；真实提交、改价、发券、投放仍需负责人最后确认。"
    return "后台 AI 只输出活动草稿、叠加校验和毛利测算，不进入真实外部执行。"


def default_cloud_plugin_reason(row: dict[str, Any]) -> str:
    execution_mode = str(row.get("execution_mode") or "")
    ads_boundary = str(row.get("ads_boundary") or "")
    if "isolated_cloud_plugin" in execution_mode:
        return "平台连接、卖家后台、广告后台或登录身份不能安全混用时，必须按店铺路径使用后台执行身份。"
    if ads_boundary and ads_boundary not in {"not_store_api", "rules_need_review"}:
        return "广告账号与店铺授权分离，投放动作必须单独核对广告身份。"
    return "当前只允许生成草稿和确认项，避免误操作真实店铺。"


def usable_config_text(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    has_cjk = any("\u4e00" <= char <= "\u9fff" for char in text)
    return has_cjk and text.count("?") < max(3, len(text) // 6)


def rule_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,/|;]+", value) if part.strip()]
    return []


def compatible_store_models(store_model: Any) -> list[str]:
    model = normalize_store_model_for_route(store_model)
    compatibility = {
        "semi_managed_crossborder": ["semi_managed_crossborder", "cross_border", "cross_border_seller", "marketplace_seller"],
        "semi_managed_local": ["semi_managed_local", "local_store", "local_seller", "marketplace_seller"],
        "cross_border_seller": ["cross_border_seller", "cross_border", "marketplace_seller"],
        "local_seller": ["local_seller", "local_store", "marketplace_seller"],
        "tiktok_accu_local": ["tiktok_accu_local", "local_store", "local_seller", "marketplace_seller"],
        "self_store": ["self_store", "marketplace_seller"],
    }
    return compatibility.get(model, [model])


def store_model_matches_rule(route_model: Any, rule_models: list[str]) -> bool:
    return store_model_match_rank(route_model, rule_models) > 0


def store_model_match_rank(route_model: Any, rule_models: list[str]) -> int:
    if not rule_models:
        return 1
    normalized_rule_models = [normalize_store_model_for_route(model) for model in rule_models]
    if "marketplace_seller" in normalized_rule_models:
        return 1
    normalized_route_model = normalize_store_model_for_route(route_model)
    if normalized_route_model in normalized_rule_models:
        return 2
    if any(model in normalized_rule_models for model in compatible_store_models(normalized_route_model)):
        return 1
    return 0


def dedupe_activity_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("route_key") or ""), str(row.get("status") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def store_route_missing_prerequisites(store: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    scopes = rule_list(store.get("authorization_scopes"))
    if not scopes:
        missing.append("authorization_scope")
    has_store_identity = any(
        str(store.get(key) or "").strip()
        for key in ["store_external_id", "platform_store_id", "shop_id", "seller_id"]
    ) or bool(store.get("key_present"))
    method = str(store.get("connection_method") or "").strip()
    model = normalize_store_model_for_route(store.get("shop_type"))
    identity_required = method == "official_authorization" and model not in {
        "independent_site",
        "content_catalog",
    }
    if not has_store_identity and (not scopes or identity_required):
        missing.append("platform_store_identity")
    return missing


def store_route_is_ready_for_mapping(store: dict[str, Any]) -> bool:
    return not store_route_missing_prerequisites(store)


def store_route_readiness_status(store: dict[str, Any]) -> str:
    missing = store_route_missing_prerequisites(store)
    if not missing:
        return "platform_store_configured"
    if "authorization_scope" in missing:
        return "platform_store_pending_authorization"
    if "platform_store_identity" in missing:
        return "platform_store_pending_identity"
    return "platform_store_pending_authorization"


def store_route_pending_next_step(store: dict[str, Any]) -> str:
    missing = store_route_missing_prerequisites(store)
    reasons: list[str] = []
    if "authorization_scope" in missing:
        reasons.append("权限范围")
    if "platform_store_identity" in missing:
        reasons.append("平台店铺编号 / 卖家ID / 真实平台店铺身份")
    reason_text = "、".join(reasons) or "可执行授权"
    if missing == ["platform_store_identity"]:
        return "权限范围已登记，但还缺平台店铺编号、卖家ID或真实平台店铺身份；内部子店铺 / 业务线只作备注，不能进入系统连接或外部执行。"
    return f"店铺已登记，但还缺{reason_text}；只能保留候选、报表导入或开店准备，不能自动上架或拉单。"


def store_route_visibility_note(store: dict[str, Any]) -> str:
    name = str(store.get("store_name") or "").strip()
    missing = store_route_missing_prerequisites(store)
    method = str(store.get("connection_method") or "").strip()
    has_real_identity = any(
        str(store.get(key) or "").strip()
        for key in ("store_external_id", "platform_store_id", "shop_id", "seller_id")
    ) or bool(store.get("key_present"))
    if re.search(r"\b(demo|sample|test|bundle)\b", name, flags=re.IGNORECASE) and not has_real_identity:
        return "后台已识别为历史/测试痕迹；不作为真实店铺拉单、投放或外部执行"
    if "platform_store_identity" in missing and method == "official_authorization":
        return "待补真实平台店铺身份；只建立读取边界，不进入外部执行"
    return "真实动作仍进入确认队列；后台 AI 只按当前店铺范围读取"


def build_channel_route_readiness(root: Path, profile_stores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    platform_store_routes = {
        platform_route_id_for_store(store): store
        for store in profile_stores
        if store_route_is_ready_for_mapping(store)
    }
    rows: list[dict[str, Any]] = []
    for store in profile_stores:
        route_key = platform_route_id_for_store(store)
        ready_for_mapping = store_route_is_ready_for_mapping(store)
        status = store_route_readiness_status(store)
        rows.append(
            {
                "route_key": route_key,
                "source_type": "platform_store",
                "source_label": store.get("store_name") or route_key,
                "channel_id": channel_id(store.get("platform_id") or store.get("platform_label")),
                "country_code": str(store.get("country_code") or "GLOBAL").strip().upper() or "GLOBAL",
                "store_model": normalize_store_model_for_route(store.get("shop_type")),
                "status": status,
                "next_step": (
                    "已有后台平台店铺；进入系统连接、订单同步、物流回传和账单映射准备。"
                    if ready_for_mapping
                    else store_route_pending_next_step(store)
                ),
                "matched_store": store.get("store_name") or "",
                "store_visibility_note": store_route_visibility_note(store),
                "ads_account_status": "registered" if str(store.get("ads_account_id") or "").strip() else "missing",
                "business_center_status": "registered" if str(store.get("business_center_id") or "").strip() else "missing",
            }
        )
    for request in load_channel_route_requests(root):
        route_key = route_key_from_request(request)
        matched_store = platform_store_routes.get(route_key, {})
        status = "ready_for_api_mapping" if matched_store else "needs_platform_store"
        rows.append(
            {
                "route_key": route_key,
                "source_type": str(request.get("source_type") or "designer_application"),
                "source_label": str(request.get("designer_name") or request.get("design_title") or request.get("product_name") or request.get("request_id") or "设计师站点申请"),
                "channel_id": channel_id(request.get("channel_id") or request.get("platform")),
                "country_code": str(request.get("country_code") or request.get("country") or "GLOBAL").strip().upper() or "GLOBAL",
                "store_model": normalize_store_model_for_route(request.get("store_model") or request.get("shop_type") or request.get("operation_model")),
                "status": status,
                "next_step": (
                    "已有后台平台店铺；可以进入上架、订单、物流、结算映射准备。"
                    if status == "ready_for_api_mapping"
                    else "设计师只申请了这个站点；后台还没有对应平台店铺，只能进入候选/招商/开店准备，不能自动上架或拉单。"
                ),
                "matched_store": matched_store.get("store_name") if matched_store else "",
                "store_visibility_note": store_route_visibility_note(matched_store) if matched_store else "",
                "ads_account_status": "registered" if str(matched_store.get("ads_account_id") or "").strip() else "missing",
                "business_center_status": "registered" if str(matched_store.get("business_center_id") or "").strip() else "missing",
            }
        )
    return dedupe_route_rows(rows)


def route_key_from_request(request: dict[str, Any]) -> str:
    return make_route_key(
        request.get("channel_id") or request.get("platform"),
        request.get("country_code") or request.get("country"),
        request.get("store_model") or request.get("shop_type") or request.get("operation_model"),
    )


def platform_route_id_for_store(store: dict[str, Any]) -> str:
    return make_route_key(
        store.get("platform_id") or store.get("platform_label") or store.get("marketplace"),
        store.get("country_code"),
        store.get("shop_type"),
    )


def make_route_key(channel: Any, country: Any, store_model: Any) -> str:
    return f"{channel_id(channel)}:{str(country or 'GLOBAL').strip().upper() or 'GLOBAL'}:{normalize_store_model_for_route(store_model)}"


def normalize_store_model_for_route(shop_type: Any) -> str:
    text = str(shop_type or "").strip().lower()
    if not text:
        return "store_model_pending"
    normalized = text.replace("-", "_").replace(" ", "_")
    if "semi_managed_crossborder" in normalized or "semi_managed_cross_border" in normalized:
        return "semi_managed_crossborder"
    if "semi_managed_local" in normalized:
        return "semi_managed_local"
    if ("半托" in text or "半托管" in text or "semi managed" in text or "semi-managed" in text) and (
        "本土" in text or "本地" in text or "local" in text
    ):
        return "semi_managed_local"
    if "半托" in text or "半托管" in text or "semi managed" in text or "semi-managed" in text:
        return "semi_managed_crossborder"
    if "cross_border_seller" in normalized:
        return "cross_border_seller"
    if "local_seller" in normalized:
        return "local_seller"
    if "self_store" in normalized:
        return "self_store"
    if "independent_site" in normalized:
        return "independent_site"
    if "official_full_managed" in normalized or any(signal in text for signal in ["官方全托管", "平台全托管", "全托管", "full managed", "full service"]):
        return "official_full_managed"
    if "accu" in text:
        return "tiktok_accu_local"
    if "teelab_owned" in normalized or ("teelab" in text and "自营" in text and "联名" not in text and "代运营" not in text):
        return "teelab_owned"
    if "platform_co_ops" in normalized or "代运营" in text or "联名" in text:
        return "platform_co_ops"
    if "cross_border" in normalized or "半托" in text or "跨境" in text or "cross border" in text or "crossborder" in text:
        return "cross_border"
    if "local_store" in normalized or "本土" in text or "本地" in text or "local" in text:
        return "local_store"
    if "独立站" in text or "shopify" in text or "woocommerce" in text:
        return "independent_site"
    if "catalog" in text or "目录" in text:
        return "content_catalog"
    if "marketplace_seller" in normalized or (
        ("marketplace" in text or "seller" in text or "卖家" in text)
        and "unknown" not in text
        and "partner" not in text
    ):
        return "marketplace_seller"
    return "store_model_pending"


def infer_store_ownership_for_route(source: dict[str, Any] | Any) -> str:
    if not isinstance(source, dict):
        source = {"store_model": source}
    explicit = str(
        source.get("store_ownership")
        or source.get("ownership")
        or source.get("ownership_type")
        or source.get("store_owner_type")
        or source.get("store_owner")
        or ""
    ).strip().lower()
    normalized = explicit.replace("-", "_").replace(" ", "_")
    if normalized in {
        "teelab_co_ops",
        "teelab_platform_co_ops",
        "platform_co_ops",
        "platform_ops",
    } or "联名" in explicit or "代运营" in explicit:
        return "teelab_co_ops"
    if normalized in {"teelab_owned", "owned_platform", "teelab_self_owned"} or ("teelab" in normalized and "owned" in normalized):
        return "teelab_owned"
    if normalized in {"designer_self_store", "self_store", "seller_self_store", "merchant_owned"} or "自运营" in explicit:
        return "designer_self_store"
    if normalized in {"official_full_managed", "platform_official_full_managed"} or "全托管" in explicit:
        return "official_full_managed_unsupported"
    if normalized in {"content_catalog", "catalog"} or "目录" in explicit:
        return "content_catalog"
    if normalized in {"platform_operator_store", "operator_store", "backend_platform_store"}:
        return "platform_operator_store"

    model = normalize_store_model_for_route(
        source.get("store_model")
        or source.get("shop_type")
        or source.get("operation_model")
        or source.get("store_mode")
    )
    platform = channel_id(source.get("platform_id") or source.get("platform") or source.get("channel_id"))
    if model == "platform_co_ops":
        return "teelab_co_ops"
    if model == "teelab_owned" or platform == "teelab_platform":
        return "teelab_owned"
    if model == "self_store":
        return "designer_self_store"
    if model == "official_full_managed":
        return "official_full_managed_unsupported"
    if model == "content_catalog":
        return "content_catalog"
    if model == "store_model_pending":
        return "store_ownership_pending"
    return "platform_operator_store"


def store_ownership_label(ownership: Any) -> str:
    code = str(ownership or "").strip()
    labels = {
        "teelab_co_ops": "TeeLab 代运营 / 联名运营",
        "teelab_owned": "TeeLab 自营",
        "designer_self_store": "设计师自运营店铺",
        "platform_operator_store": "后台平台店铺 / 运营店铺",
        "content_catalog": "内容/商品目录",
        "official_full_managed_unsupported": "平台官方全托管（不接）",
        "store_ownership_pending": "店铺归属待确认",
    }
    return labels.get(code, labels.get(infer_store_ownership_for_route({"store_ownership": code}), "店铺归属待确认"))


def store_ownership_label_for_route(source: dict[str, Any] | Any) -> str:
    return store_ownership_label(infer_store_ownership_for_route(source))


def channel_id(platform: Any) -> str:
    raw = str(platform or "channel").strip().lower()
    mapping = {
        "tiktok": "tiktok_shop",
        "tiktok shop": "tiktok_shop",
        "tiktok_shop": "tiktok_shop",
        "shein marketplace": "shein",
        "amazon sp-api": "amazon",
        "shopify / woocommerce": "shopify",
        "woocommerce": "woocommerce",
        "teelab platform": "teelab_platform",
    }
    if raw in mapping:
        return mapping[raw]
    return re.sub(r"[^a-z0-9]+", "_", raw).strip("_") or "channel"


def dedupe_route_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        visibility_note = str(row.get("store_visibility_note") or "")
        matched_store = str(row.get("matched_store") or "")
        source_label = str(row.get("source_label") or "")
        if "历史/测试" in visibility_note or re.search(r"\b(demo|sample|test|bundle)\b", source_label, flags=re.IGNORECASE):
            source_label = "历史/测试店铺"
            matched_store = "历史/测试店铺"
        key = (
            str(row.get("route_key") or ""),
            str(row.get("source_type") or ""),
            str(row.get("status") or ""),
            source_label,
            matched_store,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
