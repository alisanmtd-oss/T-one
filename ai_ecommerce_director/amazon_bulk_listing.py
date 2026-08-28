from __future__ import annotations

import csv
import html
import json
import os
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlparse
from typing import Any, Mapping
from xml.etree import ElementTree

from .project_facts import (
    private_amazon_browser_profile,
    private_amazon_product,
    private_project_section,
)


_PRIVATE_AMAZON_BULK = private_project_section("amazon_bulk_listing")
_PRIVATE_AMAZON_PRIMARY = private_amazon_product(0)
_PRIVATE_AMAZON_BUNDLE = private_amazon_product(1)
_PRIVATE_AMAZON_BROWSER_PROFILE = private_amazon_browser_profile()


AMAZON_US_MARKETPLACE_ID = "ATVPDKIKX0DER"
AMAZON_10001_DEFAULT_ASSET_DIR = Path(
    os.environ.get("TEELAB_AMAZON_10001_ASSET_DIR") or "outputs/amazon_10001_ready"
)

AMAZON_10001_BULK_ROUTE = {
    "platform": "amazon",
    "country": "US",
    "store_model": "marketplace_seller",
    "ownership": "self_store",
    "route_key": "amazon:US:marketplace_seller",
    "operation_scope_key": "amazon:US:marketplace_seller:self_store:FBM",
}


AMAZON_FASTTRACK_TOOLS: tuple[dict[str, str], ...] = (
    {
        "name": "Amazon official SP-API SDK",
        "url": "https://github.com/amzn/selling-partner-api-sdk",
        "role": "Use the official SDK for authenticated SP-API calls once Amazon developer credentials are ready.",
        "fit": "best_long_term_sdk",
        "risk": "Requires Seller Central developer app, LWA, AWS credentials, and seller authorization.",
    },
    {
        "name": "Amazon official listings feed JSON schemas",
        "url": "https://github.com/amzn/selling-partner-api-models/tree/main/schemas/feeds",
        "role": "Use the official listings-feed-schema-v2 and processing-report schema to generate batch listing payloads.",
        "fit": "best_immediate_schema",
        "risk": "Schema alone does not bypass Product Identity, GTIN, brand, category, or authorization checks.",
    },
    {
        "name": "python-amazon-sp-api",
        "url": "https://pypi.org/project/python-amazon-sp-api/",
        "role": "Optional Python wrapper for Feeds, Listings Items, Product Type Definitions, Reports, Orders, and Finances flows.",
        "fit": "fastest_python_wrapper",
        "risk": "Community package; pin version and keep the official schema/report layer in our code.",
    },
)


AMAZON_VIDEO_LEARNING_SOURCES: tuple[dict[str, str], ...] = (
    {
        "name": "Amazon Seller University - bulk listings and variations",
        "url": "https://www.youtube.com/watch?v=W7GYNksNWeo",
        "source_type": "official_video_index",
        "lesson": "Use Add Products via Upload for matching or creating product listings and variations in bulk.",
    },
    {
        "name": "Amazon Seller Central - add products using inventory files",
        "url": "https://sellercentral.amazon.com/gp/help/external/201576410",
        "source_type": "official_help",
        "lesson": "Inventory files are the operational path for bulk listing work; templates and upload reports should become first-class artifacts.",
    },
    {
        "name": "Amazon Seller Forums - quick tip for upload files",
        "url": "https://sellercentral.amazon.com/seller-forums/discussions/t/aff6e014-3f9e-4286-a348-8ff70d92f88a",
        "source_type": "official_forum_tip",
        "lesson": "Bulk upload is a time saver for many items, but it depends on the correct seller plan and file access.",
    },
    {
        "name": "Miaoshou ERP - Amazon listing video",
        "url": "https://erp.91miaoshou.com/help_center/video_4156.html",
        "source_type": "erp_video",
        "lesson": "ERP listing videos focus on the whole flow: images, publish failures, slow review, brand fields, and efficient upload.",
    },
    {
        "name": "Miaoshou ERP - Amazon listing article",
        "url": "https://erp.91miaoshou.com/help_center/article_3050.html",
        "source_type": "erp_article",
        "lesson": "Follow collection box -> public collection box -> platform collection box -> publish -> publication record.",
    },
)


VIDEO_DERIVED_FAST_ACTIONS: tuple[str, ...] = (
    "Do not make the browser form the main listing path; use upload files, feed, or SP-API first.",
    "Create a product master before channel submission so title, images, variants, price, quantity, and compliance are handled once.",
    "Generate Amazon upload/feed artifacts from product master and keep template version, route, and seller scope.",
    "Read processing or publication reports as the source of truth after submission.",
    "Turn upload failures into field-level repair tasks instead of repeating page clicks.",
    "Keep images, brand/Product Identity, variants, inventory, price, ads, and promotions as separate queues.",
)


AMAZON_10001_SUBMISSION_GATES: tuple[dict[str, str], ...] = (
    {
        "gate": "sp_api_authorization",
        "owner": "Store Integration Operator",
        "needed_for": "Product Type Definitions, Listings Items validation preview, and Feeds API submission.",
    },
    {
        "gate": "seller_scoped_secret",
        "owner": "Credential Custodian",
        "needed_for": "LWA refresh token and AWS signing credentials must be isolated to the Amazon US self-operated store.",
    },
    {
        "gate": "product_type_schema",
        "owner": "Listing Operator",
        "needed_for": "Amazon US product type and attributes must be validated before feed submission.",
    },
    {
        "gate": "product_identity",
        "owner": "Compliance Operator",
        "needed_for": "Legal GS1 UPC/GTIN or approved Amazon GTIN exemption is required before publish.",
    },
    {
        "gate": "owner_confirmation",
        "owner": "Responsible Owner",
        "needed_for": "Real external submit, price changes, inventory sync, ads, or promotions require final confirmation.",
    },
)


AMAZON_SP_API_SECRET_GROUPS: tuple[dict[str, tuple[str, ...] | str], ...] = (
    {
        "key": "seller_id",
        "label": "Amazon seller id",
        "env_names": ("AMAZON_SP_API_SELLER_ID", "SP_API_SELLER_ID"),
    },
    {
        "key": "lwa_refresh_token",
        "label": "LWA refresh token",
        "env_names": ("AMAZON_SP_API_REFRESH_TOKEN", "SP_API_REFRESH_TOKEN"),
    },
    {
        "key": "lwa_client_id",
        "label": "LWA app client id",
        "env_names": ("AMAZON_SP_API_LWA_APP_ID", "LWA_APP_ID"),
    },
    {
        "key": "lwa_client_secret",
        "label": "LWA client secret",
        "env_names": ("AMAZON_SP_API_LWA_CLIENT_SECRET", "LWA_CLIENT_SECRET"),
    },
    {
        "key": "aws_access_key",
        "label": "AWS access key",
        "env_names": ("AMAZON_SP_API_AWS_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID"),
    },
    {
        "key": "aws_secret_key",
        "label": "AWS secret key",
        "env_names": ("AMAZON_SP_API_AWS_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY"),
    },
    {
        "key": "aws_region",
        "label": "AWS region",
        "env_names": ("AMAZON_SP_API_AWS_REGION", "AWS_REGION"),
    },
)


AMAZON_10001_GTIN_EXEMPTION_REQUIREMENTS: tuple[dict[str, str], ...] = (
    {
        "id": "route_scope",
        "label": "Route scope",
        "why": "GTIN exemption is not global; it must match Amazon US, store ownership, product category, and brand/generic path.",
    },
    {
        "id": "product_identity_statement",
        "label": "Product identity statement",
        "why": "Amazon needs a clear reason the 10001 T-shirt has no manufacturer barcode or legal GS1 code yet.",
    },
    {
        "id": "front_image",
        "label": "Front product image",
        "why": "A real product/front mockup is needed to support the exemption and listing draft.",
    },
    {
        "id": "back_image",
        "label": "Back product image",
        "why": "A back image helps prove the product and packaging do not show an existing barcode.",
    },
    {
        "id": "brand_or_generic_decision",
        "label": "Brand or Generic decision",
        "why": "Using TeeLab may require brand authorization; using Generic changes listing strategy and must be intentional.",
    },
    {
        "id": "packaging_barcode_evidence",
        "label": "Packaging/barcode evidence",
        "why": "If there is no barcode on product or packaging, evidence should be retained before applying.",
    },
)


AMAZON_10001_PRODUCT_IDENTITY_OPTIONS: tuple[dict[str, str], ...] = (
    {
        "id": "gs1_gtin",
        "label": "Legal GS1 GTIN",
        "when_to_use": "Use when the owner has legitimate GS1 UPC/EAN/GTIN codes assigned to the 10001 SKU family.",
        "requirements": "GS1 certificate or invoice, per-SKU code assignment, and owner confirmation before external submit.",
        "amazon_product_id_type": "UPC/EAN/GTIN",
    },
    {
        "id": "amazon_gtin_exemption_generic",
        "label": "Amazon GTIN exemption - Generic/private label",
        "when_to_use": "Use when there is no legal GS1 code and the first live listing should avoid unapproved brand claims.",
        "requirements": "Amazon US Clothing exemption approval, product images, packaging/no-barcode evidence, and owner confirmation.",
        "amazon_product_id_type": "GTIN exemption",
    },
    {
        "id": "amazon_gtin_exemption_brand",
        "label": "Amazon GTIN exemption - brand authorized",
        "when_to_use": "Use when TeeLab or another brand is authorized for this seller account and exemption is approved for that brand/category.",
        "requirements": "Brand authorization or registry evidence plus Amazon US Clothing exemption approval and owner confirmation.",
        "amazon_product_id_type": "GTIN exemption",
    },
)


AMAZON_PRODUCT_IDENTITY_OFFICIAL_SOURCES: tuple[dict[str, str], ...] = (
    {
        "name": "Amazon Seller Central - List products that do not have a product ID",
        "url": "https://sellercentral.amazon.com/gp/help/external/G200426310",
        "use": "GTIN exemption must be requested separately for each store and category before listing without product IDs.",
    },
    {
        "name": "Amazon Seller Central - Build your inventory file",
        "url": "https://sellercentral.amazon.com/help/hub/reference/external/G581",
        "use": "Category-level Product ID requirements and exemptions must be checked before building the final upload file.",
    },
    {
        "name": "Amazon Seller University - Apply for a Product ID or GTIN Exemption",
        "url": "https://www.youtube.com/watch?v=YQnU5Kxzc2o",
        "use": "Seller University explains what Product ID means, how to apply, and how to check exemption status.",
    },
    {
        "name": "Printful POD GTIN exemption guide",
        "url": "https://help.printful.com/hc/en-us/articles/360014067899-How-do-I-request-GTIN-exemption-from-Amazon",
        "use": "POD-specific operational reference: prepare product name/category, brand or Generic path, 2-9 real product photos, no visible barcode evidence, and matching brand/category.",
    },
)


AMAZON_PRODUCT_TYPE_OFFICIAL_SOURCES: tuple[dict[str, str], ...] = (
    {
        "name": "Amazon Product Type Definitions API",
        "url": "https://developer-docs.amazon.com/sp-api/docs/product-type-definitions-api",
        "use": "Retrieve latest marketplace-specific JSON schemas and attribute requirements.",
    },
    {
        "name": "getDefinitionsProductType reference",
        "url": "https://developer-docs.amazon.com/sp-api/reference/getdefinitionsproducttype",
        "use": "Fetch LISTING requirements with ENFORCED or NOT_ENFORCED validation rules.",
    },
    {
        "name": "Listings Items API",
        "url": "https://developer-docs.amazon.com/sp-api/docs/listings-items-api",
        "use": "Single-SKU listing create/update path; JSON_LISTINGS_FEED is the bulk equivalent.",
    },
    {
        "name": "Listings feed type values",
        "url": "https://developer-docs.amazon.com/sp-api/docs/listings-feed-type-values",
        "use": "Confirm JSON_LISTINGS_FEED should be validated with Product Type Definitions requirements.",
    },
)


AMAZON_SP_API_AUTHORIZATION_SOURCES: tuple[dict[str, str], ...] = (
    {
        "name": "Amazon SP-API - Authorize applications",
        "url": "https://developer-docs.amazon.com/sp-api/docs/authorizing-selling-partner-api-applications",
        "use": "Decide whether the Amazon US store should use private self-authorization or public OAuth authorization.",
    },
    {
        "name": "Amazon SP-API - Authorize private applications",
        "url": "https://developer-docs.amazon.com/sp-api/docs/self-authorization",
        "use": "Self-authorize a private application in Seller Central for the current seller account.",
    },
    {
        "name": "Amazon SP-API - Connect to the API",
        "url": "https://developer-docs.amazon.com/sp-api/docs/connecting-to-the-selling-partner-api",
        "use": "Exchange LWA refresh token for access tokens and sign requests with the seller-scoped AWS credentials.",
    },
    {
        "name": "Amazon SP-API - Roles",
        "url": "https://developer-docs.amazon.com/sp-api/docs/roles-in-the-selling-partner-api",
        "use": "Limit app roles to what the store route needs, such as Product Listing and inventory/order access.",
    },
    {
        "name": "Amazon SP-API - Policies and agreements",
        "url": "https://developer-docs.amazon.com/sp-api/docs/policies-and-agreements",
        "use": "Keep data protection, acceptable use, and solution provider obligations attached to this execution identity.",
    },
)


AMAZON_SELLER_CENTRAL_ALIGNMENT_SOURCES: tuple[dict[str, str], ...] = (
    {
        "name": "Amazon Seller Central - Add products using inventory files",
        "url": "https://sellercentral.amazon.com/gp/help/external/201576410",
        "use": "Inventory templates are tab-delimited files used to add multiple listings; the internal seed CSV must be mapped to the downloaded template before upload.",
    },
    {
        "name": "Amazon Seller Central - Create your inventory file template",
        "url": "https://sellercentral.amazon.com/help/hub/reference/external/G202094740?locale=en-US",
        "use": "Seller Central route is Add Products > Spreadsheet > Download a blank template for the selected product type.",
    },
    {
        "name": "Amazon SP-API - Manage Product Listings",
        "url": "https://developer-docs.amazon.com/sp-api/docs/manage-product-listings-guide",
        "use": "JSON_LISTINGS_FEED can bulk create/update listings, but the payload must follow Product Type Definitions.",
    },
    {
        "name": "Amazon SP-API - Mapping product attributes",
        "url": "https://developer-docs.amazon.com/sp-api/docs/mapping-product-attributes",
        "use": "Legacy flat-file fields and JSON_LISTINGS_FEED attributes do not always share names; keep a mapping layer.",
    },
)


AMAZON_10001_TEMPLATE_COLUMN_CANDIDATES: tuple[dict[str, Any], ...] = (
    {
        "internal_field": "sku",
        "required": True,
        "aliases": ("item_sku", "sku", "seller-sku", "seller_sku"),
        "source": "bulk_upload_seed.sku",
    },
    {
        "internal_field": "parent_sku",
        "required": True,
        "aliases": ("parent_sku", "parentage_sku", "parent-sku"),
        "source": "bulk_upload_seed.parent_sku",
    },
    {
        "internal_field": "parent_child",
        "required": True,
        "aliases": ("parent_child", "parentage", "parent-child"),
        "source": "bulk_upload_seed.relationship_type",
    },
    {
        "internal_field": "relationship_type",
        "required": True,
        "aliases": ("relationship_type", "relationship-type", "relationship"),
        "source": "bulk_upload_seed.relationship_type",
    },
    {
        "internal_field": "variation_theme",
        "required": True,
        "aliases": ("variation_theme", "variation-theme", "variation theme"),
        "source": "bulk_upload_seed.variation_theme",
    },
    {
        "internal_field": "item_name",
        "required": True,
        "aliases": ("item_name", "item-name", "title", "product_title"),
        "source": "bulk_upload_seed.item_name",
    },
    {
        "internal_field": "brand",
        "required": True,
        "aliases": ("brand_name", "brand-name", "brand"),
        "source": "bulk_upload_seed.brand",
    },
    {
        "internal_field": "color",
        "required": True,
        "aliases": ("color_name", "color-name", "color"),
        "source": "bulk_upload_seed.color",
    },
    {
        "internal_field": "size",
        "required": True,
        "aliases": ("size_name", "size-name", "size"),
        "source": "bulk_upload_seed.size",
    },
    {
        "internal_field": "price_usd",
        "required": True,
        "aliases": ("standard_price", "standard-price", "price", "your_price"),
        "source": "bulk_upload_seed.price_usd",
    },
    {
        "internal_field": "quantity",
        "required": True,
        "aliases": ("quantity", "item_quantity", "fulfillment_quantity"),
        "source": "bulk_upload_seed.quantity",
    },
    {
        "internal_field": "fulfillment_channel",
        "required": True,
        "aliases": ("fulfillment_channel", "fulfillment-channel", "fulfillment-center-id"),
        "source": "bulk_upload_seed.fulfillment_channel",
    },
    {
        "internal_field": "main_image_locator",
        "required": True,
        "aliases": ("main_image_url", "main-image-url", "main_product_image_locator", "main-image"),
        "source": "image_url_mapping.main_image_locator",
    },
    {
        "internal_field": "other_image_locator_1",
        "required": False,
        "aliases": ("other_image_url1", "other-image-url1", "other_product_image_locator", "other-image-url-1"),
        "source": "image_url_mapping.other_image_locator_1",
    },
    {
        "internal_field": "product_id",
        "required": True,
        "aliases": ("product_id", "external_product_id", "external-product-id"),
        "source": "gtin_or_exemption",
    },
    {
        "internal_field": "product_id_type",
        "required": True,
        "aliases": ("product_id_type", "external_product_id_type", "external-product-id-type"),
        "source": "gtin_or_exemption",
    },
)


AMAZON_10001_ASSET_PROVIDER_ENV_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "provider": "cloudflare_r2_s3_compatible",
        "required_env": (
            "R2_ACCOUNT_ID",
            "R2_BUCKET",
            "R2_ACCESS_KEY_ID",
            "R2_SECRET_ACCESS_KEY",
            "ASSET_PUBLIC_BASE_URL",
        ),
        "endpoint_template": "https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        "cli": "aws s3 cp --endpoint-url",
    },
    {
        "provider": "aws_s3_cloudfront",
        "required_env": (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_REGION",
            "ASSET_S3_BUCKET",
            "ASSET_PUBLIC_BASE_URL",
        ),
        "endpoint_template": "aws_default",
        "cli": "aws s3 cp",
    },
    {
        "provider": "generic_s3_compatible",
        "required_env": (
            "S3_ENDPOINT_URL",
            "S3_BUCKET",
            "S3_ACCESS_KEY_ID",
            "S3_SECRET_ACCESS_KEY",
            "ASSET_PUBLIC_BASE_URL",
        ),
        "endpoint_template": "{S3_ENDPOINT_URL}",
        "cli": "aws s3 cp --endpoint-url",
    },
)


AMAZON_10001_PRODUCT_TYPE_PRECHECKS: tuple[dict[str, str], ...] = (
    {
        "id": "product_type_recommendation",
        "label": "Product type recommendation",
        "required_action": "Use PTD recommendations for item name and Amazon US marketplace before locking SHIRT.",
    },
    {
        "id": "get_definitions_child",
        "label": "Child schema",
        "required_action": "Retrieve getDefinitionsProductType for productType=SHIRT, requirements=LISTING, parentageLevel=CHILD.",
    },
    {
        "id": "get_definitions_parent",
        "label": "Parent schema",
        "required_action": "Retrieve getDefinitionsProductType for productType=SHIRT, requirements=LISTING, parentageLevel=PARENT.",
    },
    {
        "id": "variation_theme",
        "label": "Variation theme",
        "required_action": "Confirm Amazon US SHIRT supports color/size variation theme for 10001.",
    },
    {
        "id": "browse_node_or_item_type",
        "label": "Browse node / item type",
        "required_action": "Confirm item type keyword or recommended browse node for men's fashion T-shirts.",
    },
    {
        "id": "required_attributes",
        "label": "Required attributes",
        "required_action": "Compare local feed attributes against live PTD required attributes and enums.",
    },
    {
        "id": "image_requirements",
        "label": "Image requirements",
        "required_action": "Confirm main image, color images, and variant image rules for Amazon US apparel.",
    },
)


AMAZON_10001_LOCAL_ATTRIBUTE_COVERAGE: tuple[dict[str, str], ...] = (
    {"attribute": "item_name", "status": "ready", "source": "feed_draft"},
    {"attribute": "brand", "status": "needs_identity_decision", "source": "gtin_exemption_packet"},
    {"attribute": "condition_type", "status": "ready", "source": "feed_draft"},
    {"attribute": "color", "status": "ready_single_sku", "source": "feed_draft"},
    {"attribute": "size", "status": "ready_single_sku", "source": "feed_draft"},
    {"attribute": "material", "status": "ready", "source": "feed_draft"},
    {"attribute": "fabric_type", "status": "ready", "source": "feed_draft"},
    {"attribute": "fit_type", "status": "ready", "source": "feed_draft"},
    {"attribute": "bullet_point", "status": "ready", "source": "feed_draft"},
    {"attribute": "product_description", "status": "ready", "source": "feed_draft"},
    {"attribute": "purchasable_offer", "status": "ready", "source": "feed_draft"},
    {"attribute": "fulfillment_availability", "status": "ready", "source": "feed_draft"},
    {"attribute": "externally_assigned_product_identifier", "status": "blocked", "source": "gtin_or_exemption"},
    {"attribute": "variation_theme", "status": "needs_live_ptd_schema", "source": "product_type_definitions"},
    {"attribute": "recommended_browse_node_id", "status": "needs_live_ptd_schema", "source": "product_type_definitions"},
    {"attribute": "main_product_image_locator", "status": "ready_local_file_needs_public_url", "source": "local_assets"},
)


AMAZON_10001_SIZE_CODES: tuple[str, ...] = ("S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL")


AMAZON_10001_SINGLE_VARIATION_COLORS: tuple[dict[str, str], ...] = (
    {
        "code": "BLK",
        "amazon_color": "Black",
        "source_color": "黑色",
        "asset_slug": "black",
        "launch_wave": "first_batch",
        "asset_status": "front_back_ready_local",
    },
    {
        "code": "GRY",
        "amazon_color": "Washed Gray",
        "source_color": "灰色",
        "asset_slug": "washed_gray",
        "launch_wave": "first_batch",
        "asset_status": "front_back_ready_local",
    },
    {
        "code": "COF",
        "amazon_color": "Coffee Brown",
        "source_color": "咖啡色",
        "asset_slug": "coffee_brown",
        "launch_wave": "first_batch",
        "asset_status": "front_back_ready_local",
    },
    {
        "code": "ROS",
        "amazon_color": "Rose Red",
        "source_color": "玫红色",
        "asset_slug": "rose_red",
        "launch_wave": "first_batch",
        "asset_status": "front_back_ready_local",
    },
    {
        "code": "PUR",
        "amazon_color": "Purple",
        "source_color": "紫色",
        "asset_slug": "purple",
        "launch_wave": "first_batch",
        "asset_status": "front_back_ready_local",
    },
    {
        "code": "BLU",
        "amazon_color": "Washed Blue",
        "source_color": "巴黎世家蓝",
        "asset_slug": "washed_blue",
        "launch_wave": "first_batch",
        "asset_status": "front_back_ready_local",
    },
    {
        "code": "APR",
        "amazon_color": "Apricot",
        "source_color": "杏色",
        "asset_slug": "apricot",
        "launch_wave": "live_catalog",
        "asset_status": "missing_verified_flat_images",
    },
    {
        "code": "ORG",
        "amazon_color": "Papaya Orange",
        "source_color": "木瓜橙",
        "asset_slug": "papaya_orange",
        "launch_wave": "live_catalog",
        "asset_status": "missing_verified_flat_images",
    },
    {
        "code": "GRN",
        "amazon_color": "Grass Green",
        "source_color": "草绿",
        "asset_slug": "grass_green",
        "launch_wave": "live_catalog",
        "asset_status": "missing_verified_flat_images",
    },
    {
        "code": "OLV",
        "amazon_color": "Olive Green",
        "source_color": "橄榄绿",
        "asset_slug": "olive_green",
        "launch_wave": "live_catalog",
        "asset_status": "missing_verified_flat_images",
    },
    {
        "code": "ARM",
        "amazon_color": "Army Green",
        "source_color": "军绿",
        "asset_slug": "army_green",
        "launch_wave": "live_catalog",
        "asset_status": "missing_verified_flat_images",
    },
)


AMAZON_10001_COLOR_BACKLOG: tuple[dict[str, str], ...] = (
    {"code": "APR", "amazon_color": "Apricot", "source_color": "杏色"},
    {"code": "ORG", "amazon_color": "Papaya Orange", "source_color": "木瓜橙"},
    {"code": "GRN", "amazon_color": "Grass Green", "source_color": "草绿"},
    {"code": "OLV", "amazon_color": "Olive Green", "source_color": "橄榄绿"},
    {"code": "ARM", "amazon_color": "Army Green", "source_color": "军绿"},
)


AMAZON_10001_LOCAL_ASSET_FILES: tuple[dict[str, str], ...] = (
    {"asset_slug": "coffee_brown", "front": "\u5496\u8272\u6b63.jpg", "back": "\u5496\u8272\u53cd.jpg"},
    {"asset_slug": "washed_gray", "front": "\u7070\u8272\u6b63.jpg", "back": "\u7070\u53cd.jpg"},
    {"asset_slug": "rose_red", "front": "\u73ab\u7ea2\u6b63.jpg", "back": "\u73ab\u7ea2\u53cd.jpg"},
    {"asset_slug": "purple", "front": "\u7d2b\u8272\u6b63\u9762.jpg", "back": "\u7d2b\u8272\u80cc.jpg"},
    {"asset_slug": "washed_blue", "front": "\u84dd\u6b63.jpg", "back": "\u84dd\u53cd.jpg"},
    {"asset_slug": "black", "front": "\u9ed1\u6b63.jpg", "back": "\u9ed1\u53cd.jpg"},
)


@dataclass(frozen=True, slots=True)
class AmazonListingField:
    field: str
    value: str
    status: str
    notes: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "value": self.value,
            "status": self.status,
            "notes": self.notes,
        }


AMAZON_10001_SINGLE_FIELDS: tuple[AmazonListingField, ...] = (
    AmazonListingField("sku", "TL10001-BLK-S", "ready", "Single black size S test SKU."),
    AmazonListingField("product_code", "10001", "ready", "230g vintage washed cotton T-shirt."),
    AmazonListingField("title", "TeeLab Men's Short Sleeve T-Shirt, Black, S, Oversized Fit, Casual, Crewneck, 100% Cotton", "ready"),
    AmazonListingField("category_path", "Clothing, Shoes & Jewelry > Men > Clothing > Shirts > T-Shirts", "ready"),
    AmazonListingField("item_type_keyword", "fashion-t-shirts", "ready"),
    AmazonListingField("brand", "TeeLab", "ready", "Brand still needs Product Identity compliance."),
    AmazonListingField("color", "Black", "ready"),
    AmazonListingField("size", "S", "ready"),
    AmazonListingField("material", "Cotton", "ready"),
    AmazonListingField("fabric_type", "100% Cotton", "ready"),
    AmazonListingField("fit_type", "Oversized Fit", "ready"),
    AmazonListingField("fulfillment", "FBM self warehouse", "ready", "User asked to ship from own warehouse, not FBA."),
    AmazonListingField("condition", "New", "ready"),
    AmazonListingField("quantity", "10", "ready"),
    AmazonListingField("price_usd", "20.00", "ready"),
    AmazonListingField("list_price_usd", "20.00", "ready", "Do not create fake discount by inflating list price."),
    AmazonListingField(
        "import_designation",
        "Imported",
        "ready",
        "Amazon Import Designation enum confirmed in the live US SHIRT editor; this is separate from country_of_origin.",
    ),
    AmazonListingField("package_dimensions", "12 x 8 x 1 inches", "ready"),
    AmazonListingField("package_weight", "0.5 pounds", "ready"),
    AmazonListingField("main_image", str(AMAZON_10001_DEFAULT_ASSET_DIR / "TL10001_black_front_main.jpg"), "ready"),
    AmazonListingField("back_image", str(AMAZON_10001_DEFAULT_ASSET_DIR / "TL10001_black_back.jpg"), "ready"),
    AmazonListingField("product_id_type", "", "blocked", "Need UPC/EAN/GTIN or approved GTIN exemption."),
    AmazonListingField("product_id", "", "blocked", "Do not fabricate UPC, EAN, or GTIN."),
    AmazonListingField("gtin_exemption", "", "todo", "Apply per Amazon store and category if there is no legal GS1 code."),
)


ERP_BULK_LISTING_STAGES: tuple[dict[str, str], ...] = (
    {
        "stage": "product_master",
        "owner": "AI Listing Operator",
        "purpose": "Keep one clean internal product record for product, images, size, price, inventory, and compliance.",
    },
    {
        "stage": "channel_template_mapping",
        "owner": "AI Listing Operator",
        "purpose": "Map product master fields to Amazon US marketplace seller feed fields and required attributes.",
    },
    {
        "stage": "compliance_gate",
        "owner": "AI Compliance Officer",
        "purpose": "Block publish when Product ID, GTIN exemption, brand authorization, image, or category requirements are missing.",
    },
    {
        "stage": "feed_or_sp_api_submit",
        "owner": "Feed Runner",
        "purpose": "Use inventory file, JSON feed, or SP-API as the primary listing path instead of slow page-by-page clicking.",
    },
    {
        "stage": "processing_report_repair",
        "owner": "Error Repair Queue",
        "purpose": "Read Amazon processing reports, map errors back to fields, and create repair tasks.",
    },
    {
        "stage": "browser_plugin_fallback",
        "owner": "Browser Plugin Operator",
        "purpose": "Only verify pages or operate settings that cannot be covered by feed/API.",
    },
)


def build_amazon_10001_bulk_listing_plan() -> dict[str, Any]:
    fields = [field.to_dict() for field in AMAZON_10001_SINGLE_FIELDS]
    blockers = [field for field in fields if field["status"] == "blocked"]
    todos = [field for field in fields if field["status"] == "todo"]
    ready = [field for field in fields if field["status"] == "ready"]
    return {
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "sku": "TL10001-BLK-S",
        "product": {
            "product_code": "10001",
            "single_price_usd": 20.00,
            "four_pack_price_usd": 50.00,
            "fulfillment": "FBM self warehouse",
            "fba_policy": "do_not_use_fba_for_first_test",
        },
        "primary_execution_surface": "feed_or_sp_api",
        "browser_execution_surface": "fallback_verification_only",
        "selected_existing_tools": list(AMAZON_FASTTRACK_TOOLS),
        "video_learning_sources": list(AMAZON_VIDEO_LEARNING_SOURCES),
        "video_derived_fast_actions": list(VIDEO_DERIVED_FAST_ACTIONS),
        "submission_gates": list(AMAZON_10001_SUBMISSION_GATES),
        "current_amazon_status": {
            "description": "ready",
            "product_details": "ready",
            "offer": "ready",
            "safety_and_compliance": "ready",
            "product_identity": "blocked_3_of_5",
        },
        "external_submit_allowed": False,
        "publish_status": "blocked_by_product_identity",
        "ready_fields": ready,
        "blocked_fields": blockers,
        "todo_fields": todos,
        "bulk_listing_stages": list(ERP_BULK_LISTING_STAGES),
        "required_before_publish": [
            "legal_gs1_gtin_or_amazon_gtin_exemption",
            "brand_or_generic_listing_path_confirmed",
            "amazon_processing_report_has_no_product_identity_error",
        ],
    }


def build_amazon_sp_api_secret_readiness(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    source = os.environ if environ is None else environ
    groups: list[dict[str, Any]] = []
    missing: list[str] = []
    present: list[str] = []
    for item in AMAZON_SP_API_SECRET_GROUPS:
        env_names = tuple(str(name) for name in item["env_names"])
        found_name = next((name for name in env_names if str(source.get(name) or "").strip()), "")
        row = {
            "key": str(item["key"]),
            "label": str(item["label"]),
            "status": "present" if found_name else "missing",
            "accepted_env_names": list(env_names),
            "present_env_name": found_name,
            "value_visible": False,
        }
        groups.append(row)
        if found_name:
            present.append(str(item["key"]))
        else:
            missing.append(str(item["key"]))
    return {
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "status": "ready" if not missing else "missing_secrets",
        "ready_for_sp_api_calls": not missing,
        "present": present,
        "missing": missing,
        "groups": groups,
        "privacy_rule": "Only key presence is reported; secret values are never exposed in page, report, or queue output.",
    }


def build_amazon_10001_store_authorization_runbook(
    *,
    root: Path | None = None,
    environ: Mapping[str, str] | None = None,
    seller_id: str = "SELLER_ID_TODO",
    seller_central_logged_in: bool = False,
    bitbrowser_profile_ready: bool = False,
    plugin_connected: bool = False,
    owner_confirmed_authorization: bool = False,
    sp_api_app_ready: bool = False,
    sp_api_roles_ready: bool = False,
) -> dict[str, Any]:
    base_root = root or Path.cwd()
    extension_manifest = (
        base_root
        / "browser_extension"
        / "ai_ecommerce_director_capture"
        / "manifest.json"
    )
    plugin_installed_locally = extension_manifest.exists()
    secret_readiness = build_amazon_sp_api_secret_readiness(environ)
    seller_scoped_secret_ready = bool(secret_readiness["ready_for_sp_api_calls"])
    blockers: list[dict[str, str]] = []
    if not owner_confirmed_authorization:
        blockers.append(
            {
                "gate": "owner_authorization_confirmation",
                "severity": "confirmation_required",
                "reason": "Owner confirmation is required before connecting a real Amazon seller authorization or execution identity.",
                "next_step": "Confirm this exact route: amazon + US + marketplace_seller + self_store + FBM.",
            }
        )
    if not seller_central_logged_in:
        blockers.append(
            {
                "gate": "seller_central_session",
                "severity": "blocker",
                "reason": "The fixed Amazon US Seller Central session is not confirmed inside BitBrowser profile 22.",
                "next_step": "Open BitBrowser profile 22 and stop at any OTP, captcha, account security, or policy prompt.",
            }
        )
    if not bitbrowser_profile_ready:
        blockers.append(
            {
                "gate": "bitbrowser_profile_22",
                "severity": "blocker",
                "reason": "The stable browser profile/IP identity is not confirmed as the execution surface for this store.",
                "next_step": "Keep one store in one stable profile/IP; do not rotate, share, or mix store identities.",
            }
        )
    if not plugin_installed_locally:
        blockers.append(
            {
                "gate": "browser_extension_manifest",
                "severity": "blocker",
                "reason": "The local AI Ecommerce Director Capture extension manifest is not present.",
                "next_step": "Install the local extension from browser_extension/ai_ecommerce_director_capture.",
            }
        )
    if not plugin_connected:
        blockers.append(
            {
                "gate": "browser_extension_connection",
                "severity": "blocker",
                "reason": "The browser extension has not confirmed a local capture/task-package connection for Amazon profile 22.",
                "next_step": "Use the extension local test capture and pull a listing_preflight task package from 127.0.0.1:8765.",
            }
        )
    if not sp_api_app_ready:
        blockers.append(
            {
                "gate": "sp_api_application",
                "severity": "blocker",
                "reason": "No Amazon US seller-scoped SP-API application authorization is marked ready.",
                "next_step": "Prepare a private/self-authorized SP-API app or approved public app for this seller account.",
            }
        )
    if not sp_api_roles_ready:
        blockers.append(
            {
                "gate": "sp_api_roles",
                "severity": "blocker",
                "reason": "SP-API roles for listings, feeds, Product Type Definitions, inventory, orders, and reports are not confirmed.",
                "next_step": "Grant only the minimum roles needed for product listing, feed validation, inventory, orders, and reports.",
            }
        )
    if not seller_scoped_secret_ready:
        blockers.append(
            {
                "gate": "seller_scoped_secret",
                "severity": "blocker",
                "reason": "Seller-scoped SP-API credentials are missing or incomplete.",
                "next_step": "Save LWA refresh token, LWA client, AWS keys, region, and seller id under this Amazon US store route only.",
            }
        )

    browser_ready = seller_central_logged_in and bitbrowser_profile_ready and plugin_installed_locally and plugin_connected
    sp_api_ready = sp_api_app_ready and sp_api_roles_ready and seller_scoped_secret_ready
    if browser_ready and sp_api_ready and owner_confirmed_authorization:
        status = "store_execution_identity_ready"
    elif browser_ready:
        status = "browser_plugin_ready_sp_api_pending"
    elif sp_api_ready:
        status = "sp_api_ready_browser_plugin_pending"
    else:
        status = "needs_store_authorization_setup"

    return {
        "packet_type": "amazon_10001_store_authorization_runbook",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "seller_id": seller_id,
        "store_id": "amazon-us-new-store",
        "browser_profile": "BitBrowser-22",
        "official_sources": list(AMAZON_SP_API_AUTHORIZATION_SOURCES),
        "status": status,
        "secret_readiness": secret_readiness,
        "execution_surfaces": [
            {
                "surface": "browser_extension",
                "role": "Capture visible Seller Central context, pull listing_preflight task packages, and record evidence.",
                "ready": browser_ready,
                "allowed_actions": [
                    "read_visible_page_context",
                    "capture_screenshot_or_page_snapshot",
                    "pull_local_task_package",
                    "record_preflight_evidence",
                ],
                "forbidden_actions": [
                    "bypass_otp_captcha_or_account_security",
                    "click_submit_publish_save_launch_without_confirmation",
                    "change_price_inventory_ads_payment_or_shipping_without_confirmation",
                ],
            },
            {
                "surface": "sp_api",
                "role": "Fetch PTD schema, validate feeds, upload final feed only after every product/listing gate is ready.",
                "ready": sp_api_ready,
                "allowed_actions": [
                    "searchDefinitionsProductTypes",
                    "getDefinitionsProductType",
                    "createFeedDocument_after_final_gates",
                    "getFeed_processing_report",
                ],
                "forbidden_actions": [
                    "reuse_credentials_across_stores",
                    "submit_unvalidated_feed",
                    "request_restricted_data_without_need",
                ],
            },
            {
                "surface": "isolated_cloud_executor",
                "role": "Run confirmed backend tasks for this route only after owner approval.",
                "ready": browser_ready or sp_api_ready,
                "allowed_actions": [
                    "execute_confirmed_listing_preflight",
                    "store_route_scoped_task_logs",
                    "stop_on_external_submit_boundary",
                ],
                "forbidden_actions": [
                    "execute_other_store_route",
                    "mix_amazon_with_shein_tiktok_or_other_store_identity",
                    "perform_payment_refund_ship_or_ad_launch_without_confirmation",
                ],
            },
        ],
        "steps": [
            {
                "id": "AMZ-10001-AUTH-01",
                "action": "Confirm the execution route is Amazon US marketplace seller / self-operated store.",
                "ready": owner_confirmed_authorization,
            },
            {
                "id": "AMZ-10001-AUTH-02",
                "action": "Keep Seller Central in BitBrowser profile 22 with a stable IP/browser identity.",
                "ready": seller_central_logged_in and bitbrowser_profile_ready,
            },
            {
                "id": "AMZ-10001-AUTH-03",
                "action": "Install and test the local browser extension connection to 127.0.0.1:8765.",
                "ready": plugin_installed_locally and plugin_connected,
            },
            {
                "id": "AMZ-10001-AUTH-04",
                "action": "Authorize the seller-scoped SP-API app and store credentials without exposing values.",
                "ready": sp_api_app_ready and seller_scoped_secret_ready,
            },
            {
                "id": "AMZ-10001-AUTH-05",
                "action": "Confirm minimal SP-API roles before PTD, feeds, orders, inventory, reports, ads, or fulfillment tasks.",
                "ready": sp_api_roles_ready,
            },
        ],
        "blockers": blockers,
        "automation_boundary": [
            "One store uses one route, one browser profile, and one seller-scoped credential set.",
            "Browser plugin is for capture and task-package assistance; SP-API is for schema/feed work.",
            "The agent must stop at OTP, captcha, account-security, payment, policy acknowledgement, publish, ads launch, refund, shipment, or irreversible submit prompts unless separately confirmed.",
        ],
        "next_automation_step": "fetch_ptd_schema_or_pull_listing_task_package"
        if status == "store_execution_identity_ready"
        else "repair_store_authorization_blockers",
    }


def _amazon_10001_default_asset_path(file_name: str) -> Path:
    return AMAZON_10001_DEFAULT_ASSET_DIR / file_name


def build_amazon_10001_gtin_exemption_packet(
    *,
    front_image_path: Path | None = None,
    back_image_path: Path | None = None,
    brand_path: str = "TeeLab brand path pending authorization",
    has_packaging_barcode_evidence: bool = False,
    product_identity_statement_ready: bool = True,
) -> dict[str, Any]:
    front = front_image_path or _amazon_10001_default_asset_path("TL10001_black_front_main.jpg")
    back = back_image_path or _amazon_10001_default_asset_path("TL10001_black_back.jpg")
    evidence: list[dict[str, Any]] = [
        {
            "id": "route_scope",
            "status": "ready",
            "value": AMAZON_10001_BULK_ROUTE["route_key"],
            "note": "Amazon US marketplace seller / self-operated store.",
        },
        {
            "id": "product_identity_statement",
            "status": "ready" if product_identity_statement_ready else "missing",
            "value": "10001 is a private/POD 230g vintage washed cotton T-shirt prepared for FBM self-warehouse fulfillment.",
            "note": "Do not claim a manufacturer barcode unless a legal GS1 code is available.",
        },
        {
            "id": "front_image",
            "status": "ready" if front.exists() else "missing",
            "value": str(front),
            "note": "Existing file is used as exemption/listing evidence when present.",
        },
        {
            "id": "back_image",
            "status": "ready" if back.exists() else "missing",
            "value": str(back),
            "note": "Existing file is used as exemption/listing evidence when present.",
        },
        {
            "id": "brand_or_generic_decision",
            "status": "needs_decision",
            "value": brand_path,
            "note": "TeeLab brand listing may require authorization; Generic path changes the listing strategy.",
        },
        {
            "id": "packaging_barcode_evidence",
            "status": "ready" if has_packaging_barcode_evidence else "missing",
            "value": "product_or_packaging_barcode_photo",
            "note": "Keep evidence that product/packaging has no existing barcode before applying.",
        },
    ]
    blockers = [
        {
            "id": item["id"],
            "status": item["status"],
            "next_step": _amazon_10001_gtin_next_step(str(item["id"])),
        }
        for item in evidence
        if item["status"] != "ready"
    ]
    return {
        "packet_type": "amazon_10001_gtin_exemption_packet",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "sku": "TL10001-BLK-S",
        "marketplace_id": AMAZON_US_MARKETPLACE_ID,
        "requirements": list(AMAZON_10001_GTIN_EXEMPTION_REQUIREMENTS),
        "evidence": evidence,
        "status": "ready_to_apply_gtin_exemption" if not blockers else "needs_more_evidence",
        "blockers": blockers,
        "submission_boundary": "Prepare packet only; actual Amazon GTIN exemption application remains an external Seller Central action.",
        "hard_rule": "Never fabricate UPC/EAN/GTIN.",
    }


def _amazon_10001_gtin_next_step(requirement_id: str) -> str:
    steps = {
        "brand_or_generic_decision": "Confirm whether the first Amazon draft uses TeeLab brand authorization or a Generic/private-label path.",
        "packaging_barcode_evidence": "Add product or packaging photo/evidence showing no existing manufacturer barcode.",
        "front_image": "Regenerate or locate the front product image before applying.",
        "back_image": "Regenerate or locate the back product image before applying.",
        "product_identity_statement": "Write the no-GTIN product identity statement before applying.",
    }
    return steps.get(requirement_id, "Complete the missing GTIN exemption evidence.")


def build_amazon_10001_product_identity_decision(
    *,
    has_legal_gs1_gtin: bool = False,
    gtin_exemption_approved: bool = False,
    brand_decision: str = "",
    packaging_evidence_ready: bool = False,
    owner_confirmed_external_submit: bool = False,
) -> dict[str, Any]:
    normalized_brand = (brand_decision or "").strip().lower()
    valid_brand_paths = {
        "generic",
        "private_label",
        "teelab_authorized_brand",
        "brand_authorized",
    }
    blockers: list[dict[str, str]] = []
    selected_path = "needs_product_identity_decision"
    recommended_path = "amazon_gtin_exemption_generic"

    if has_legal_gs1_gtin:
        selected_path = "gs1_gtin"
    elif gtin_exemption_approved and normalized_brand in valid_brand_paths:
        selected_path = (
            "amazon_gtin_exemption_brand"
            if normalized_brand in {"teelab_authorized_brand", "brand_authorized"}
            else "amazon_gtin_exemption_generic"
        )

    if not has_legal_gs1_gtin and not gtin_exemption_approved:
        blockers.append(
            {
                "gate": "product_id_source",
                "severity": "blocker",
                "reason": "No legal GS1 GTIN or Amazon GTIN exemption approval is available for Amazon US.",
                "next_step": "Apply for Amazon US Clothing GTIN exemption or assign legitimate GS1 codes before submit.",
            }
        )
    if not normalized_brand or normalized_brand not in valid_brand_paths:
        blockers.append(
            {
                "gate": "brand_or_generic_decision",
                "severity": "blocker",
                "reason": "Brand/Generic path is not confirmed for Seller Central Product Identity.",
                "next_step": "Choose Generic/private-label first, or provide TeeLab/brand authorization evidence.",
            }
        )
    if not has_legal_gs1_gtin and not packaging_evidence_ready:
        blockers.append(
            {
                "gate": "packaging_no_barcode_evidence",
                "severity": "blocker",
                "reason": "GTIN exemption route needs product or packaging evidence showing no existing manufacturer barcode.",
                "next_step": "Capture front/back product and packaging/no-barcode evidence before exemption submission.",
            }
        )
    if not owner_confirmed_external_submit:
        blockers.append(
            {
                "gate": "owner_confirmation",
                "severity": "blocker",
                "reason": "External Seller Central submission has not been confirmed by the responsible owner.",
                "next_step": "Keep the feed as a local draft until the owner confirms real Amazon submission.",
            }
        )

    if not blockers:
        status = "ready_with_gs1_gtin" if selected_path == "gs1_gtin" else "ready_with_gtin_exemption"
    else:
        status = "needs_product_identity_decision"

    return {
        "packet_type": "amazon_10001_product_identity_decision",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "marketplace_id": AMAZON_US_MARKETPLACE_ID,
        "product_type": "SHIRT",
        "selected_path": selected_path,
        "recommended_path": recommended_path,
        "status": status,
        "options": list(AMAZON_10001_PRODUCT_IDENTITY_OPTIONS),
        "inputs": {
            "has_legal_gs1_gtin": has_legal_gs1_gtin,
            "gtin_exemption_approved": gtin_exemption_approved,
            "brand_decision": brand_decision,
            "packaging_evidence_ready": packaging_evidence_ready,
            "owner_confirmed_external_submit": owner_confirmed_external_submit,
        },
        "blockers": blockers,
        "hard_rules": [
            "Never fabricate UPC/EAN/GTIN.",
            "Do not use another product's barcode.",
            "Do not submit under TeeLab brand unless brand authorization is ready for this seller account.",
        ],
        "next_automation_step": "feed_submit_preflight" if not blockers else "complete_product_identity_evidence",
    }


def build_amazon_10001_product_identity_evidence_tasks(
    decision: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    packet = decision or build_amazon_10001_product_identity_decision()
    blocker_gates = {str(item.get("gate") or "") for item in packet.get("blockers") or [] if isinstance(item, dict)}
    task_defs = (
        {
            "id": "AMZ-10001-ID-01",
            "gate": "product_id_source",
            "task": "Choose legal GS1 GTIN or Amazon GTIN exemption path",
            "output": "GS1 certificate/code assignment or Seller Central GTIN exemption approval record",
            "owner": "AI Listing Operator + store owner",
        },
        {
            "id": "AMZ-10001-ID-02",
            "gate": "brand_or_generic_decision",
            "task": "Confirm Generic/private-label or brand-authorized listing path",
            "output": "brand_decision value: generic, private_label, teelab_authorized_brand, or brand_authorized",
            "owner": "AI Compliance Officer",
        },
        {
            "id": "AMZ-10001-ID-03",
            "gate": "packaging_no_barcode_evidence",
            "task": "Collect product and packaging evidence showing no manufacturer barcode",
            "output": "front/back product image plus packaging/no-barcode image stored with the 10001 evidence pack",
            "owner": "AI Listing Operator",
        },
        {
            "id": "AMZ-10001-ID-04",
            "gate": "owner_confirmation",
            "task": "Confirm real Seller Central submission after identity path is ready",
            "output": "owner approval record tied to the Amazon US marketplace seller store",
            "owner": "Store owner",
        },
    )
    tasks: list[dict[str, str]] = []
    for item in task_defs:
        gate = item["gate"]
        tasks.append(
            {
                **item,
                "status": "blocked" if gate in blocker_gates else "ready",
                "route_key": AMAZON_10001_BULK_ROUTE["route_key"],
            }
        )
    return tasks


def build_amazon_10001_gtin_exemption_store_runbook(
    *,
    brand_decision: str = "generic",
    product_photos_ready_count: int | None = None,
    packaging_evidence_ready: bool | None = None,
    seller_central_logged_in: bool = False,
    root: Path | None = None,
) -> dict[str, Any]:
    normalized_brand = (brand_decision or "").strip().lower()
    evidence_pack = build_amazon_10001_gtin_exemption_evidence_pack(root)
    actual_photo_count = (
        int(product_photos_ready_count)
        if product_photos_ready_count is not None
        else int(evidence_pack["selected_product_photos_count"])
    )
    actual_packaging_ready = (
        bool(packaging_evidence_ready)
        if packaging_evidence_ready is not None
        else bool(evidence_pack["packaging_evidence_count"])
    )
    image_ready = 2 <= actual_photo_count <= 9
    store_ready = seller_central_logged_in and normalized_brand in {"generic", "private_label", "teelab_authorized_brand", "brand_authorized"}
    blockers: list[dict[str, str]] = []
    if normalized_brand not in {"generic", "private_label", "teelab_authorized_brand", "brand_authorized"}:
        blockers.append(
            {
                "gate": "brand_or_generic_decision",
                "severity": "blocker",
                "reason": "GTIN exemption request needs a concrete brand or Generic path.",
                "next_step": "Use Generic/private-label for the first safe draft, or attach brand authorization before using TeeLab/brand.",
            }
        )
    if not image_ready:
        blockers.append(
            {
                "gate": "product_photo_count",
                "severity": "blocker",
                "reason": "GTIN exemption request should have 2-9 real product photos ready for the selected product/category.",
                "next_step": "Prepare front, back, detail, tag/packaging, and no-barcode photos before opening the exemption form.",
            }
        )
    if not actual_packaging_ready:
        blockers.append(
            {
                "gate": "no_barcode_evidence",
                "severity": "blocker",
                "reason": "The agent has not recorded product or packaging evidence showing there is no manufacturer barcode.",
                "next_step": "Capture packaging/tag/no-barcode evidence and attach it to the 10001 evidence pack.",
            }
        )
    if not seller_central_logged_in:
        blockers.append(
            {
                "gate": "seller_central_session",
                "severity": "needs_store_session",
                "reason": "A live Seller Central session is required to apply or check the exemption.",
                "next_step": "Open the fixed Amazon US BitBrowser/Seller Central session; do not bypass 2FA or account-security prompts.",
            }
        )

    steps = [
        {
            "id": "AMZ-10001-GTIN-RUN-01",
            "surface": "seller_central",
            "action": "Open Add Products / Product ID exemption flow for Amazon US.",
            "agent_mode": "browser_assist",
            "safe_to_automate": seller_central_logged_in,
        },
        {
            "id": "AMZ-10001-GTIN-RUN-02",
            "surface": "seller_central",
            "action": "Select Clothing / Shirts category and confirm marketplace United States.",
            "agent_mode": "browser_assist",
            "safe_to_automate": seller_central_logged_in,
        },
        {
            "id": "AMZ-10001-GTIN-RUN-03",
            "surface": "seller_central",
            "action": "Enter brand value: Generic for first draft, or authorized brand only with proof.",
            "agent_mode": "guided_fill",
            "safe_to_automate": store_ready,
        },
        {
            "id": "AMZ-10001-GTIN-RUN-04",
            "surface": "seller_central",
            "action": "Upload 2-9 product photos, including front/back and no-barcode evidence.",
            "agent_mode": "guided_upload",
            "safe_to_automate": store_ready and image_ready and packaging_evidence_ready,
        },
        {
            "id": "AMZ-10001-GTIN-RUN-05",
            "surface": "seller_central",
            "action": "Save the application result, approval status, screenshots, and category/brand scope.",
            "agent_mode": "record_result",
            "safe_to_automate": store_ready,
        },
    ]
    return {
        "packet_type": "amazon_10001_gtin_exemption_store_runbook",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "status": "ready_to_apply_in_store" if not blockers else "blocked_before_store_apply",
        "recommended_brand_decision": "generic",
        "current_brand_decision": brand_decision,
        "product_photos_ready_count": actual_photo_count,
        "evidence_pack_status": evidence_pack["status"],
        "evidence_pack": evidence_pack,
        "official_sources": list(AMAZON_PRODUCT_IDENTITY_OFFICIAL_SOURCES),
        "steps": steps,
        "blockers": blockers,
        "automation_boundary": [
            "The agent may prepare evidence and guide/fill the live form only inside the fixed Amazon US seller session.",
            "The agent must stop at 2FA, captcha, account-security, payment, irreversible publish, or policy acknowledgement prompts.",
            "The agent must not invent UPC/EAN/GTIN or use another product's barcode.",
        ],
        "next_automation_step": "apply_gtin_exemption_in_store" if not blockers else "repair_gtin_exemption_runbook_blockers",
    }


def latest_amazon_10001_product_identity_capture(root: Path) -> dict[str, Any] | None:
    from .storage import read_records

    candidates: list[dict[str, Any]] = []
    for record in read_records(root, "store_operation_event"):
        fields = record.fields
        route_key = str(fields.get("route_key") or fields.get("erp_route_key") or "").strip()
        source = str(fields.get("source_platform") or "").lower()
        country = str(fields.get("country_code") or fields.get("country_site") or "").upper()
        page_url = str(fields.get("page_url") or fields.get("url") or "")
        page_title = str(fields.get("page_title") or fields.get("product_name") or "")
        page_text = str(fields.get("page_text") or "")
        screenshot_path = str(fields.get("screenshot_path") or fields.get("image_path") or "")
        combined = f"{route_key} {source} {page_url} {page_title} {page_text}".lower()
        if "amazon" not in combined:
            continue
        if route_key and route_key != AMAZON_10001_BULK_ROUTE["route_key"]:
            continue
        if country and country != "US":
            continue
        if not (
            "product_identity" in combined
            or "product identity" in combined
            or "product id exemption" in combined
            or "gtin" in combined
            or "upc" in combined
            or "add a product" in combined
        ):
            continue
        controls = fields.get("page_controls") if isinstance(fields.get("page_controls"), list) else []
        inputs = fields.get("page_inputs") if isinstance(fields.get("page_inputs"), list) else []
        blocked_controls = [
            str(item.get("text") or item.get("label") or item.get("name") or item)
            for item in controls
            if any(
                token in str(item).lower()
                for token in ("submit", "publish", "save", "launch", "approval", "gtin exemption", "product id exemption")
            )
        ][:20]
        input_labels = [
            str(item.get("label") or item.get("name") or item.get("placeholder") or item.get("value") or item)
            for item in inputs
        ][:30]
        signals = {
            "product_identity_page": "product_identity" in combined or "product identity" in combined,
            "add_product_page": "add a product" in combined,
            "brand_signal": "brand" in combined,
            "gtin_or_upc_signal": "gtin" in combined or "upc" in combined,
            "product_id_exemption_signal": "product id exemption" in combined,
            "item_type_signal": "item type" in combined or "fashion-t-shirts" in combined or "t-shirt" in combined,
            "category_route_undefined": "itemtype=undefined" in combined
            or "recommendedbrowsenodeid=undefined" in combined
            or "displaypath=undefined" in combined,
        }
        candidates.append(
            {
                "record_id": record.record_id,
                "created_at": record.created_at,
                "source": record.source,
                "route_key": route_key or AMAZON_10001_BULK_ROUTE["route_key"],
                "store_id": str(fields.get("store_id") or "amazon-us-new-store"),
                "browser_profile": str(fields.get("browser_profile") or "BitBrowser-22"),
                "page_title": page_title,
                "page_url": page_url,
                "screenshot_path": screenshot_path,
                "signals": signals,
                "blocked_control_labels": blocked_controls,
                "input_labels": input_labels,
                "text_excerpt": page_text[:800],
                "status": "captured_review_needed",
            }
        )
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: str(item.get("created_at") or ""))[-1]


def build_amazon_10001_gtin_exemption_evidence_refs(
    capture: dict[str, Any] | None,
    *,
    evidence_pack: dict[str, Any],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if capture:
        refs.append(
            {
                "id": "seller_central_product_identity_page",
                "kind": "seller_central_capture",
                "status": "ready",
                "record_id": str(capture.get("record_id") or ""),
                "ref": str(capture.get("page_url") or ""),
                "screenshot_path": str(capture.get("screenshot_path") or ""),
                "note": "Latest Product Identity/Add Product/Product ID exemption page capture.",
            }
        )
        text = f"{capture.get('page_title') or ''} {capture.get('text_excerpt') or ''}".lower()
        if "approved" in text or "approval granted" in text or "exemption approved" in text:
            refs.append(
                {
                    "id": "gtin_exemption_approval_result",
                    "kind": "seller_central_approval_capture",
                    "status": "ready",
                    "record_id": str(capture.get("record_id") or ""),
                    "ref": str(capture.get("page_url") or ""),
                    "screenshot_path": str(capture.get("screenshot_path") or ""),
                    "note": "Captured Seller Central text indicates GTIN exemption approval. Pending text is not accepted.",
                }
            )
    for index, photo in enumerate(evidence_pack.get("selected_product_photos") or [], start=1):
        if not isinstance(photo, dict):
            continue
        refs.append(
            {
                "id": f"product_photo_{index}",
                "kind": str(photo.get("kind") or "product_photo"),
                "status": str(photo.get("status") or "ready"),
                "ref": str(photo.get("path") or ""),
                "asset_slug": str(photo.get("asset_slug") or ""),
                "note": "Product photo candidate for the GTIN exemption evidence pack.",
            }
        )
    for index, item in enumerate(evidence_pack.get("packaging_evidence") or [], start=1):
        if not isinstance(item, dict):
            continue
        refs.append(
            {
                "id": f"packaging_no_barcode_{index}",
                "kind": str(item.get("kind") or "packaging_no_barcode"),
                "status": str(item.get("status") or "ready"),
                "ref": str(item.get("path") or ""),
                "note": "Packaging/tag/product evidence showing no manufacturer barcode.",
            }
        )
    return refs


def build_amazon_10001_product_identity_live_checks(capture: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not capture:
        return [
            {
                "id": "live_product_identity_capture",
                "label": "Seller Central Product Identity page capture",
                "status": "missing",
                "ready": False,
                "next_step": "Capture the live Product Identity/Add a Product page with the BitBrowser plugin.",
            }
        ]
    signals = capture.get("signals") if isinstance(capture.get("signals"), dict) else {}
    input_text = " ".join(str(item) for item in capture.get("input_labels") or []).lower()
    blocked_labels = [str(item) for item in capture.get("blocked_control_labels") or []]
    checks = [
        {
            "id": "live_product_identity_page",
            "label": "Product Identity/Add Product surface",
            "ready": bool(signals.get("product_identity_page") or signals.get("add_product_page")),
            "next_step": "Open Product Identity or Add a Product, then capture again.",
        },
        {
            "id": "live_brand_or_generic_field",
            "label": "Brand/Generic field signal",
            "ready": bool(signals.get("brand_signal") or "brand" in input_text or "generic" in input_text),
            "next_step": "Capture the Brand Name field or Generic/private-label selection before GTIN exemption work.",
        },
        {
            "id": "live_gtin_or_exemption_field",
            "label": "GTIN/UPC/Product ID exemption signal",
            "ready": bool(signals.get("gtin_or_upc_signal") or signals.get("product_id_exemption_signal") or "external product id" in input_text),
            "next_step": "Capture the External Product ID, UPC/GTIN, or Product ID exemption field/notice.",
        },
        {
            "id": "live_item_type_category_path",
            "label": "Item Type/category path is concrete",
            "ready": bool(signals.get("item_type_signal")) and not bool(signals.get("category_route_undefined")),
            "next_step": "Repair itemType/recommendedBrowseNodeId/displayPath so the visible category path is concrete.",
        },
        {
            "id": "live_external_submit_controls_blocked",
            "label": "Submit/Save/Publish controls are visible but blocked for automation",
            "ready": not bool(blocked_labels),
            "next_step": "Do not click visible Save/Submit/Publish/Exemption controls; capture them as blocked controls only.",
        },
    ]
    for item in checks:
        item["status"] = "ready" if item["ready"] else "blocked"
    return checks


def build_amazon_10001_gtin_exemption_application_checks(
    capture: dict[str, Any] | None,
    *,
    evidence_pack: dict[str, Any],
    runbook: dict[str, Any],
    evidence_refs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    text = ""
    input_text = ""
    blocked_labels: list[str] = []
    signals: dict[str, Any] = {}
    if capture:
        text = f"{capture.get('page_title') or ''} {capture.get('page_url') or ''} {capture.get('text_excerpt') or ''}".lower()
        input_text = " ".join(str(item) for item in capture.get("input_labels") or []).lower()
        blocked_labels = [str(item) for item in capture.get("blocked_control_labels") or []]
        signals = capture.get("signals") if isinstance(capture.get("signals"), dict) else {}
    selected_photos = int(evidence_pack.get("selected_product_photos_count") or 0)
    packaging_count = int(evidence_pack.get("packaging_evidence_count") or 0)
    refs = evidence_refs or []
    refs_by_kind = {
        "seller_central_capture": [item for item in refs if item.get("kind") == "seller_central_capture"],
        "seller_central_approval_capture": [item for item in refs if item.get("kind") == "seller_central_approval_capture"],
        "product_photo": [item for item in refs if str(item.get("kind") or "").startswith(("product_", "single_", "bundle_", "contact_sheet"))],
        "packaging_no_barcode": [item for item in refs if item.get("kind") == "packaging_no_barcode"],
    }
    brand_ready = bool(signals.get("brand_signal") or "brand" in input_text or "generic" in input_text or "generic" in text)
    category_ready = bool(
        ("clothing" in text or "shirt" in text or "t-shirt" in text or "tshirt" in text or "item type" in text)
        and not bool(signals.get("category_route_undefined"))
    )
    checks = [
        {
            "id": "gtin_exemption_application_surface",
            "label": "Product ID exemption application surface",
            "ready": bool(capture and (signals.get("product_id_exemption_signal") or "exemption" in text or "external product id" in input_text)),
            "next_step": "Open the Product ID exemption application/notice in Amazon US and capture the page.",
            "evidence_ref": str((refs_by_kind["seller_central_capture"][:1] or [{}])[0].get("record_id") or ""),
        },
        {
            "id": "gtin_exemption_marketplace_us",
            "label": "Marketplace is Amazon US",
            "ready": bool(capture and str(capture.get("route_key") or "") == AMAZON_10001_BULK_ROUTE["route_key"]),
            "next_step": "Use the fixed Amazon US marketplace seller store; do not mix marketplaces.",
        },
        {
            "id": "gtin_exemption_category_clothing_tshirt",
            "label": "Category is Clothing/Shirt/T-shirt",
            "ready": category_ready,
            "next_step": "Capture the concrete Clothing/Shirt/T-shirt category path before applying.",
        },
        {
            "id": "gtin_exemption_brand_or_generic",
            "label": "Brand or Generic path is present",
            "ready": brand_ready,
            "next_step": "Capture Brand Name or Generic/private-label path before the exemption application.",
        },
        {
            "id": "gtin_exemption_product_photos",
            "label": "2-9 product photos are prepared",
            "ready": 2 <= selected_photos <= 9,
            "next_step": "Prepare 2-9 real product photos for the selected product/category.",
            "evidence_ref": str((refs_by_kind["product_photo"][:1] or [{}])[0].get("ref") or ""),
        },
        {
            "id": "gtin_exemption_no_barcode_evidence",
            "label": "No-barcode packaging/product evidence is prepared",
            "ready": packaging_count > 0,
            "next_step": "Capture packaging/tag/product evidence showing there is no manufacturer barcode.",
            "evidence_ref": str((refs_by_kind["packaging_no_barcode"][:1] or [{}])[0].get("ref") or ""),
        },
        {
            "id": "gtin_exemption_approval_result_capture",
            "label": "Approval result or application status is captured",
            "ready": bool(refs_by_kind["seller_central_approval_capture"]),
            "next_step": "After owner-approved manual application, capture the approved exemption result; pending/status text is not enough.",
            "evidence_ref": str((refs_by_kind["seller_central_approval_capture"][:1] or [{}])[0].get("record_id") or ""),
        },
        {
            "id": "gtin_exemption_submit_apply_controls_blocked",
            "label": "Submit/Apply controls remain blocked for automation",
            "ready": not any("submit" in item.lower() or "apply" in item.lower() or "exemption" in item.lower() for item in blocked_labels),
            "next_step": "Do not click Submit/Apply/Product ID exemption controls; capture them as blocked controls only.",
        },
    ]
    runbook_blockers = {str(item.get("gate") or "") for item in runbook.get("blockers") or [] if isinstance(item, dict)}
    if "seller_central_session" in runbook_blockers:
        checks.append(
            {
                "id": "gtin_exemption_store_session",
                "label": "Live Seller Central session is available",
                "ready": False,
                "next_step": "Open the fixed BitBrowser profile Amazon US Seller Central session before application work.",
            }
        )
    for item in checks:
        item["status"] = "ready" if item["ready"] else "blocked"
    return checks


def build_amazon_10001_product_identity_check(root: Path | None = None) -> dict[str, Any]:
    base_root = root or Path.cwd()
    live_capture = latest_amazon_10001_product_identity_capture(base_root)
    live_checks = build_amazon_10001_product_identity_live_checks(live_capture)
    decision = build_amazon_10001_product_identity_decision()
    evidence_tasks = build_amazon_10001_product_identity_evidence_tasks(decision)
    gtin_packet = build_amazon_10001_gtin_exemption_packet()
    evidence_pack = build_amazon_10001_gtin_exemption_evidence_pack(base_root)
    runbook = build_amazon_10001_gtin_exemption_store_runbook(root=base_root)
    evidence_refs = build_amazon_10001_gtin_exemption_evidence_refs(
        live_capture,
        evidence_pack=evidence_pack,
    )
    exemption_application_checks = build_amazon_10001_gtin_exemption_application_checks(
        live_capture,
        evidence_pack=evidence_pack,
        runbook=runbook,
        evidence_refs=evidence_refs,
    )
    blockers: list[dict[str, Any]] = []
    if not live_capture:
        blockers.append(
            {
                "source": "seller_central_live_capture",
                "gate": "product_identity_page_capture",
                "severity": "blocker",
                "reason": "No latest BitBrowser Seller Central Product Identity/Add Product capture is attached to this checker.",
                "next_step": "Open Amazon Seller Central Product Identity/Add a Product in BitBrowser profile, capture page text/inputs/controls, and rerun this checker.",
            }
        )
    elif live_capture.get("signals", {}).get("category_route_undefined"):
        blockers.append(
            {
                "source": "seller_central_live_capture",
                "gate": "category_route_undefined",
                "severity": "blocker",
                "reason": "The latest captured Product Identity URL or page text still shows undefined category route values.",
                "next_step": "Repair itemType, recommendedBrowseNodeId, and visible category path before saving or submitting.",
            }
        )
    for check in live_checks:
        if not check.get("ready"):
            blockers.append(
                {
                    "source": "seller_central_live_check",
                    "gate": str(check.get("id") or ""),
                    "severity": "blocker",
                    "reason": str(check.get("label") or "Seller Central live check is not ready."),
                    "next_step": str(check.get("next_step") or "Capture and repair the live Product Identity page."),
                }
            )
    for check in exemption_application_checks:
        if not check.get("ready"):
            blockers.append(
                {
                    "source": "gtin_exemption_application_check",
                    "gate": str(check.get("id") or ""),
                    "severity": "blocker",
                    "reason": str(check.get("label") or "GTIN exemption application check is not ready."),
                    "next_step": str(check.get("next_step") or "Repair the GTIN exemption application evidence."),
                }
            )
    blockers.extend(
        {
            "source": "product_identity_decision",
            "gate": str(item.get("gate") or ""),
            "severity": str(item.get("severity") or "blocker"),
            "reason": str(item.get("reason") or ""),
            "next_step": str(item.get("next_step") or ""),
        }
        for item in decision.get("blockers") or []
        if isinstance(item, dict)
    )
    blockers.extend(
        {
            "source": "gtin_exemption_packet",
            "gate": str(item.get("id") or item.get("gate") or ""),
            "severity": "blocker",
            "reason": str(item.get("status") or "missing"),
            "next_step": str(item.get("next_step") or ""),
        }
        for item in gtin_packet.get("blockers") or []
        if isinstance(item, dict)
    )
    blockers.extend(
        {
            "source": "gtin_exemption_store_runbook",
            "gate": str(item.get("gate") or ""),
            "severity": str(item.get("severity") or "blocker"),
            "reason": str(item.get("reason") or ""),
            "next_step": str(item.get("next_step") or ""),
        }
        for item in runbook.get("blockers") or []
        if isinstance(item, dict)
    )
    next_step = (
        "Product Identity path is ready for owner review; keep external submit blocked until explicit owner approval."
        if not blockers
        else str(blockers[0].get("next_step") or "Finish Product Identity and GTIN exemption evidence before upload.")
    )
    return {
        "packet_type": "amazon_10001_product_identity_check",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "marketplace_id": AMAZON_US_MARKETPLACE_ID,
        "status": "product_identity_ready_for_owner_review" if not blockers else "blocked_before_product_identity_submit",
        "external_submit_allowed": False,
        "store_usable_for_external_upload": False,
        "checker_id": "product_identity_gtin_exemption_check",
        "product_identity_decision": decision,
        "latest_seller_central_capture": live_capture,
        "seller_central_live_checks": live_checks,
        "product_identity_evidence_tasks": evidence_tasks,
        "gtin_exemption_packet": gtin_packet,
        "gtin_exemption_evidence_pack": evidence_pack,
        "gtin_exemption_store_runbook": runbook,
        "gtin_exemption_evidence_refs": evidence_refs,
        "gtin_exemption_application_checks": exemption_application_checks,
        "blockers": blockers,
        "blocked_external_actions": [
            "seller_central_product_identity_submit",
            "gtin_exemption_submit",
            "seller_central_upload_submit",
            "listing_publish",
            "feed_submit",
            "ads_campaign_launch",
        ],
        "safe_next_step": next_step,
        "hard_rule": "Never fabricate UPC/EAN/GTIN; use legal GS1 codes or an approved Amazon GTIN exemption only.",
    }


def export_amazon_10001_product_identity_check(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_product_identity_check_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    packet = build_amazon_10001_product_identity_check(root)
    packet["report_path"] = str(path)
    path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_amazon_10001_product_type_preflight(
    *,
    product_type: str = "SHIRT",
    seller_id: str = "SELLER_ID_TODO",
    marketplace_id: str = AMAZON_US_MARKETPLACE_ID,
    live_ptd_schema_loaded: bool = False,
    child_schema_validated: bool = False,
    parent_schema_validated: bool = False,
    variation_theme_validated: bool = False,
    browse_node_validated: bool = False,
    image_requirements_validated: bool = False,
) -> dict[str, Any]:
    check_status = {
        "product_type_recommendation": live_ptd_schema_loaded,
        "get_definitions_child": child_schema_validated,
        "get_definitions_parent": parent_schema_validated,
        "variation_theme": variation_theme_validated,
        "browse_node_or_item_type": browse_node_validated,
        "required_attributes": live_ptd_schema_loaded and child_schema_validated,
        "image_requirements": image_requirements_validated,
    }
    checks: list[dict[str, Any]] = []
    for item in AMAZON_10001_PRODUCT_TYPE_PRECHECKS:
        ready = bool(check_status.get(item["id"]))
        checks.append(
            {
                "id": item["id"],
                "label": item["label"],
                "status": "validated" if ready else "needs_live_ptd_schema",
                "required_action": item["required_action"],
            }
        )

    local_blockers = [
        item
        for item in AMAZON_10001_LOCAL_ATTRIBUTE_COVERAGE
        if item["status"]
        in {
            "blocked",
            "needs_identity_decision",
            "needs_live_ptd_schema",
            "ready_local_file_needs_public_url",
        }
    ]
    blockers = [
        {
            "gate": item["id"],
            "severity": "blocker",
            "reason": item["required_action"],
        }
        for item in checks
        if item["status"] != "validated"
    ]
    blockers.extend(
        {
            "gate": f"attribute:{item['attribute']}",
            "severity": "blocker" if item["status"] == "blocked" else "needs_validation",
            "reason": f"{item['attribute']} is {item['status']} from {item['source']}.",
        }
        for item in local_blockers
    )
    return {
        "packet_type": "amazon_10001_product_type_preflight",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "seller_id": seller_id,
        "marketplace_id": marketplace_id,
        "product_type": product_type,
        "requirements": "LISTING",
        "requirements_enforced": "ENFORCED",
        "locale": "en_US",
        "official_sources": list(AMAZON_PRODUCT_TYPE_OFFICIAL_SOURCES),
        "api_calls_to_run_when_authorized": [
            {
                "operation": "searchDefinitionsProductTypes",
                "purpose": "Confirm productType recommendation for 10001 T-shirt in Amazon US.",
                "required_inputs": ["keywords", "marketplaceIds", "sellerId", "locale"],
            },
            {
                "operation": "getDefinitionsProductType",
                "purpose": "Fetch child LISTING schema for SHIRT.",
                "required_inputs": [
                    "productType",
                    "marketplaceIds",
                    "sellerId",
                    "requirements",
                    "requirementsEnforced",
                    "locale",
                ],
                "parentageLevel": "CHILD",
            },
            {
                "operation": "getDefinitionsProductType",
                "purpose": "Fetch parent LISTING schema for SHIRT variation parent.",
                "required_inputs": [
                    "productType",
                    "marketplaceIds",
                    "sellerId",
                    "requirements",
                    "requirementsEnforced",
                    "locale",
                ],
                "parentageLevel": "PARENT",
            },
        ],
        "checks": checks,
        "local_attribute_coverage": list(AMAZON_10001_LOCAL_ATTRIBUTE_COVERAGE),
        "status": "validated_against_live_ptd" if not blockers else "needs_live_product_type_definitions",
        "blockers": blockers,
        "next_step": "Run Product Type Definitions calls after SP-API seller authorization; repair feed fields from the schema before any real submit.",
    }


def build_amazon_10001_ptd_schema_fetch_runbook(
    *,
    seller_id: str = "SELLER_ID_TODO",
    marketplace_id: str = AMAZON_US_MARKETPLACE_ID,
    product_type: str = "SHIRT",
    root: Path | None = None,
    sp_api_authorized: bool = False,
    seller_scoped_secret_ready: bool = False,
    child_schema_path: Path | None = None,
    parent_schema_path: Path | None = None,
    child_schema_validated: bool = False,
    parent_schema_validated: bool = False,
    variation_theme_validated: bool = False,
    required_attributes_validated: bool = False,
) -> dict[str, Any]:
    base_root = root or Path.cwd()
    schema_root = base_root / "outputs" / "amazon_10001_ptd_schemas"
    expected_child_schema = child_schema_path or schema_root / "amazon_us_shirt_child_listing_schema.json"
    expected_parent_schema = parent_schema_path or schema_root / "amazon_us_shirt_parent_listing_schema.json"
    validation_notes = schema_root / "amazon_us_shirt_schema_validation_notes.json"
    child_schema_target = expected_child_schema.as_posix()
    parent_schema_target = expected_parent_schema.as_posix()
    validation_notes_target = validation_notes.as_posix()
    child_schema_exists = expected_child_schema.exists()
    parent_schema_exists = expected_parent_schema.exists()
    blockers: list[dict[str, str]] = []
    if not sp_api_authorized:
        blockers.append(
            {
                "gate": "sp_api_authorization",
                "severity": "blocker",
                "reason": "Amazon US seller-scoped SP-API authorization is required before Product Type Definitions can be fetched.",
                "next_step": "Authorize the seller app for this Amazon US store route only.",
            }
        )
    if not seller_scoped_secret_ready:
        blockers.append(
            {
                "gate": "seller_scoped_secret",
                "severity": "blocker",
                "reason": "Seller-scoped LWA/AWS credentials are not stored for the Amazon US marketplace seller store.",
                "next_step": "Save credentials in the store-isolated secret vault; never reuse them across stores.",
            }
        )
    if not child_schema_exists:
        blockers.append(
            {
                "gate": "child_ptd_schema_file",
                "severity": "blocker",
                "reason": "The live Amazon US SHIRT child LISTING schema has not been saved locally.",
                "next_step": f"Fetch getDefinitionsProductType for CHILD and save {child_schema_target}.",
            }
        )
    if not parent_schema_exists:
        blockers.append(
            {
                "gate": "parent_ptd_schema_file",
                "severity": "blocker",
                "reason": "The live Amazon US SHIRT parent LISTING schema has not been saved locally.",
                "next_step": f"Fetch getDefinitionsProductType for PARENT and save {parent_schema_target}.",
            }
        )
    if not child_schema_validated:
        blockers.append(
            {
                "gate": "child_schema_validation",
                "severity": "blocker",
                "reason": "Child schema has not been checked against the 48 single SKUs and 8 bundle SKUs.",
                "next_step": "Validate required child attributes, enums, Product ID handling, image locator fields, and fulfillment fields.",
            }
        )
    if not parent_schema_validated:
        blockers.append(
            {
                "gate": "parent_schema_validation",
                "severity": "blocker",
                "reason": "Parent schema has not been checked for parent-only variation attributes.",
                "next_step": "Validate parent payload fields before generating parent feed messages.",
            }
        )
    if not variation_theme_validated:
        blockers.append(
            {
                "gate": "variation_theme",
                "severity": "blocker",
                "reason": "Amazon US accepted variation themes for SHIRT have not been confirmed.",
                "next_step": "Confirm SizeName-ColorName for singles and the safest theme for 4-pack bundle family.",
            }
        )
    if not required_attributes_validated:
        blockers.append(
            {
                "gate": "required_attributes",
                "severity": "blocker",
                "reason": "Required PTD attributes have not been matched to the 10001 product master.",
                "next_step": "Write validation notes for missing attributes, enums, and fields that require manual business input.",
            }
        )

    auth_ready = sp_api_authorized and seller_scoped_secret_ready
    schema_files_ready = child_schema_exists and parent_schema_exists
    validation_ready = (
        child_schema_validated
        and parent_schema_validated
        and variation_theme_validated
        and required_attributes_validated
    )
    if not auth_ready:
        status = "blocked_before_ptd_schema_fetch"
    elif not schema_files_ready:
        status = "needs_live_ptd_schema_files"
    elif not validation_ready:
        status = "needs_ptd_schema_validation"
    else:
        status = "ptd_schema_ready_for_feed_validation"

    return {
        "packet_type": "amazon_10001_ptd_schema_fetch_runbook",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "seller_id": seller_id,
        "marketplace_id": marketplace_id,
        "product_type": product_type,
        "official_sources": list(AMAZON_PRODUCT_TYPE_OFFICIAL_SOURCES),
        "status": status,
        "expected_schema_files": {
            "child_listing_schema": child_schema_target,
            "parent_listing_schema": parent_schema_target,
            "validation_notes": validation_notes_target,
        },
        "api_calls": [
            {
                "operation": "searchDefinitionsProductTypes",
                "purpose": "Confirm the best Amazon US product type for 10001 washed cotton T-shirts.",
                "parameters": {
                    "keywords": ["t shirt", "washed cotton shirt", "tee"],
                    "marketplaceIds": [marketplace_id],
                    "sellerId": seller_id,
                    "locale": "en_US",
                },
            },
            {
                "operation": "getDefinitionsProductType",
                "purpose": "Fetch enforced child LISTING schema for JSON_LISTINGS_FEED and Listings Items validation.",
                "parameters": {
                    "productType": product_type,
                    "marketplaceIds": [marketplace_id],
                    "sellerId": seller_id,
                    "requirements": "LISTING",
                    "requirementsEnforced": "ENFORCED",
                    "locale": "en_US",
                    "productTypeVersion": "LATEST",
                    "parentageLevel": "CHILD",
                },
                "save_to": child_schema_target,
            },
            {
                "operation": "getDefinitionsProductType",
                "purpose": "Fetch enforced parent LISTING schema for variation parent messages.",
                "parameters": {
                    "productType": product_type,
                    "marketplaceIds": [marketplace_id],
                    "sellerId": seller_id,
                    "requirements": "LISTING",
                    "requirementsEnforced": "ENFORCED",
                    "locale": "en_US",
                    "productTypeVersion": "LATEST",
                    "parentageLevel": "PARENT",
                },
                "save_to": parent_schema_target,
            },
        ],
        "validation_tasks": [
            {
                "id": "AMZ-10001-PTD-SCHEMA-01",
                "action": "Validate child required attributes against the 56 child SKUs and keep parent SKUs out of child payload validation.",
                "ready": child_schema_validated,
            },
            {
                "id": "AMZ-10001-PTD-SCHEMA-02",
                "action": "Validate parent required attributes for the single and 4-pack variation families.",
                "ready": parent_schema_validated,
            },
            {
                "id": "AMZ-10001-PTD-SCHEMA-03",
                "action": "Confirm accepted variation theme and exact enum values before final feed generation.",
                "ready": variation_theme_validated,
            },
            {
                "id": "AMZ-10001-PTD-SCHEMA-04",
                "action": "Write missing required attributes and enum repairs into validation notes.",
                "ready": required_attributes_validated,
            },
        ],
        "blockers": blockers,
        "automation_boundary": [
            "This runbook may fetch and save Product Type Definitions only after seller-scoped authorization is ready.",
            "It must not submit listings, upload feeds, change prices, start ads, or acknowledge policy prompts.",
            "Secret values must stay hidden; outputs may only contain presence/status, schema files, and validation notes.",
        ],
        "next_automation_step": "validate_feed_against_ptd_schema"
        if status == "ptd_schema_ready_for_feed_validation"
        else "repair_ptd_schema_fetch_blockers",
    }


def build_amazon_10001_variation_matrix(
    *,
    single_parent_sku: str = "68-DDNH-IM56",
    bundle_parent_sku: str = "TL10001-MIX4-PARENT",
) -> dict[str, Any]:
    single_children: list[dict[str, Any]] = []
    for color in AMAZON_10001_SINGLE_VARIATION_COLORS:
        for size in AMAZON_10001_SIZE_CODES:
            single_children.append(
                {
                    "sku": f"TL10001-{color['code']}-{size}",
                    "parent_sku": single_parent_sku,
                    "product_code": "10001",
                    "listing_family": "single_tshirt",
                    "relationship_type": "variation_child",
                    "variation_theme": "SizeName-ColorName",
                    "size": size,
                    "color": color["amazon_color"],
                    "source_color": color["source_color"],
                    "price_usd": 20.00,
                    "fulfillment": "FBM self warehouse",
                    "quantity": 10,
                    "asset_slug": color["asset_slug"],
                    "asset_status": color["asset_status"],
                    "image_public_url_status": "missing_public_url",
                    "product_identity_status": "blocked_until_gtin_or_exemption",
                    "product_type_status": "needs_live_product_type_definitions",
                }
            )

    bundle_children = [
        {
            "sku": f"TL10001-MIX4-{size}",
            "parent_sku": bundle_parent_sku,
            "product_code": "10001",
            "listing_family": "four_pack_bundle",
            "relationship_type": "variation_child",
            "variation_theme": "SizeName",
            "size": size,
            "color": "Mixed neutral 4-pack",
            "source_color": "混色4件套",
            "price_usd": 50.00,
            "fulfillment": "FBM self warehouse",
            "quantity": 5,
            "asset_slug": "four_pack_bundle",
            "asset_status": "needs_bundle_image",
            "image_public_url_status": "missing_public_url",
            "product_identity_status": "blocked_until_gtin_or_exemption",
            "product_type_status": "needs_live_product_type_definitions",
        }
        for size in AMAZON_10001_SIZE_CODES
    ]

    blockers: list[dict[str, str]] = []
    missing_color_images = sorted(
        {
            child["color"]
            for child in single_children
            if child["asset_status"] != "front_back_ready_local"
        }
    )
    if missing_color_images:
        blockers.append(
            {
                "gate": "color_variant_images",
                "severity": "needs_asset_work",
                "reason": "Missing color-level product images for: " + ", ".join(missing_color_images),
                "next_step": "Generate or locate white-background front/back images for every first-batch color before upload.",
            }
        )
    blockers.extend(
        [
            {
                "gate": "image_public_urls",
                "severity": "blocker",
                "reason": "Amazon feed needs image locators that Amazon can fetch; local JPG paths are not enough.",
                "next_step": "Publish approved images to a stable HTTPS asset host and map URLs per color/SKU.",
            },
            {
                "gate": "product_identity",
                "severity": "blocker",
                "reason": "All parent/child SKUs remain blocked until legal GS1 GTIN or Amazon GTIN exemption exists.",
                "next_step": "Complete GTIN exemption packet or map legal GS1 identifiers per listing family.",
            },
            {
                "gate": "product_type_definitions",
                "severity": "blocker",
                "reason": "Parent/child variation attributes must be checked against live Amazon US SHIRT PTD schema.",
                "next_step": "Run PTD calls after SP-API authorization and repair required attributes before submit.",
            },
        ]
    )
    return {
        "packet_type": "amazon_10001_variation_matrix",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "parents": [
            {
                "sku": single_parent_sku,
                "listing_family": "single_tshirt",
                "relationship_type": "variation_parent",
                "variation_theme": "SizeName-ColorName",
                "price_policy": "children_priced_at_20_usd",
            },
            {
                "sku": bundle_parent_sku,
                "listing_family": "four_pack_bundle",
                "relationship_type": "variation_parent",
                "variation_theme": "SizeName",
                "price_policy": "children_priced_at_50_usd",
            },
        ],
        "single_children": single_children,
        "bundle_children": bundle_children,
        "counts": {
            "single_parent_count": 1,
            "single_child_count": len(single_children),
            "bundle_parent_count": 1,
            "bundle_child_count": len(bundle_children),
            "total_sku_rows_without_backlog_colors": 2 + len(single_children) + len(bundle_children),
            "backlog_color_count": len(AMAZON_10001_COLOR_BACKLOG),
        },
        "backlog_colors": list(AMAZON_10001_COLOR_BACKLOG),
        "status": "needs_assets_and_compliance_before_submit",
        "blockers": blockers,
        "hard_rule": "Preserve the live canonical parents 68-DDNH-IM56 and TL10001-MIX4-PARENT. Single item and 4-pack must remain separate listing families; do not create another parent or mix package quantity into the single-item color/size family.",
    }


def build_amazon_10001_asset_manifest(root: Path | None = None) -> dict[str, Any]:
    base_root = root or Path.cwd()
    source_dir = (
        base_root
        / "outputs"
        / "amazon_10001_assets"
        / "flat_lay_source_2026-07-01"
        / "\u5e73\u94fa\u56fe"
    )
    generated_dir = base_root / "outputs" / "amazon_10001_assets" / "generated_2026-07-01"
    color_assets: list[dict[str, Any]] = []
    for item in AMAZON_10001_LOCAL_ASSET_FILES:
        front_path = source_dir / item["front"]
        back_path = source_dir / item["back"]
        color_assets.append(
            {
                "asset_slug": item["asset_slug"],
                "front_file": item["front"],
                "back_file": item["back"],
                "front_path": str(front_path),
                "back_path": str(back_path),
                "front_exists": front_path.exists(),
                "back_exists": back_path.exists(),
                "status": "front_back_ready_local" if front_path.exists() and back_path.exists() else "missing_local_file",
                "public_url_status": "missing_public_url",
            }
        )
    bundle_image = generated_dir / "amazon_10001_4pack_bundle_draft_main.jpg"
    contact_sheet = generated_dir / "amazon_10001_flat_lay_contact_sheet.jpg"
    missing_assets = [
        asset["asset_slug"]
        for asset in color_assets
        if asset["status"] != "front_back_ready_local"
    ]
    return {
        "packet_type": "amazon_10001_asset_manifest",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "source_dir": str(source_dir),
        "generated_dir": str(generated_dir),
        "color_assets": color_assets,
        "bundle_asset": {
            "asset_slug": "four_pack_bundle",
            "path": str(bundle_image),
            "exists": bundle_image.exists(),
            "status": "draft_ready_local" if bundle_image.exists() else "needs_bundle_image",
            "public_url_status": "missing_public_url",
        },
        "contact_sheet": {
            "path": str(contact_sheet),
            "exists": contact_sheet.exists(),
        },
        "status": "local_assets_ready_needs_public_urls" if not missing_assets else "needs_local_asset_work",
        "missing_assets": missing_assets,
        "next_step": "Publish approved product images to a stable HTTPS asset host, then map image locators into Amazon feed/SP-API draft.",
    }


def build_amazon_10001_gtin_exemption_evidence_pack(root: Path | None = None) -> dict[str, Any]:
    base_root = root or Path.cwd()
    manifest = build_amazon_10001_asset_manifest(base_root)
    packaging_dirs = [
        base_root / "outputs" / "amazon_10001_assets" / "gtin_exemption_evidence",
        base_root / "outputs" / "amazon_10001_assets" / "packaging_no_barcode",
        base_root / "outputs" / "amazon_10001_assets" / "ready",
    ]
    product_photo_candidates: list[dict[str, str]] = []
    for asset in manifest["color_assets"]:
        if asset["front_exists"]:
            product_photo_candidates.append(
                {
                    "kind": "product_front",
                    "asset_slug": str(asset["asset_slug"]),
                    "path": str(asset["front_path"]),
                    "status": "ready",
                }
            )
        if asset["back_exists"]:
            product_photo_candidates.append(
                {
                    "kind": "product_back",
                    "asset_slug": str(asset["asset_slug"]),
                    "path": str(asset["back_path"]),
                    "status": "ready",
                }
            )
    bundle_asset = manifest["bundle_asset"]
    if bundle_asset["exists"]:
        product_photo_candidates.append(
            {
                "kind": "bundle_draft",
                "asset_slug": str(bundle_asset["asset_slug"]),
                "path": str(bundle_asset["path"]),
                "status": "ready",
            }
        )
    contact_sheet = manifest["contact_sheet"]
    if contact_sheet["exists"]:
        product_photo_candidates.append(
            {
                "kind": "contact_sheet_reference",
                "asset_slug": "contact_sheet",
                "path": str(contact_sheet["path"]),
                "status": "ready",
            }
        )

    packaging_evidence: list[dict[str, str]] = []
    for directory in packaging_dirs:
        if not directory.exists():
            continue
        for file_path in sorted(directory.iterdir()):
            if not file_path.is_file() or file_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            name = file_path.name.lower()
            if any(token in name for token in ("barcode", "no-barcode", "nobarcode", "packaging", "package", "tag", "label", "hangtag", "吊牌", "包装", "条码", "无条码")):
                packaging_evidence.append(
                    {
                        "kind": "packaging_no_barcode",
                        "path": str(file_path),
                        "status": "ready",
                    }
                )

    selected_product_photos = product_photo_candidates[:9]
    blockers: list[dict[str, str]] = []
    if len(selected_product_photos) < 2:
        blockers.append(
            {
                "gate": "product_photos",
                "severity": "blocker",
                "reason": "Amazon GTIN exemption evidence needs at least 2 product photos.",
                "next_step": "Keep at least front and back product photos in the 10001 asset folder.",
            }
        )
    if not packaging_evidence:
        blockers.append(
            {
                "gate": "packaging_no_barcode_evidence",
                "severity": "blocker",
                "reason": "No packaging/tag/no-barcode evidence image has been found.",
                "next_step": "Add a clear packaging/tag/no-barcode photo under outputs/amazon_10001_assets/gtin_exemption_evidence.",
            }
        )
    return {
        "packet_type": "amazon_10001_gtin_exemption_evidence_pack",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "status": "ready_for_store_runbook" if not blockers else "needs_packaging_no_barcode_evidence",
        "product_photo_candidates_count": len(product_photo_candidates),
        "selected_product_photos_count": len(selected_product_photos),
        "selected_product_photos": selected_product_photos,
        "packaging_dirs": [str(path) for path in packaging_dirs],
        "packaging_evidence_count": len(packaging_evidence),
        "packaging_evidence": packaging_evidence,
        "blockers": blockers,
        "next_step": "Open the GTIN exemption store runbook when this pack is ready; otherwise capture the missing packaging/no-barcode evidence.",
    }


def build_amazon_10001_image_url_mapping(
    *,
    asset_base_url: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    manifest = build_amazon_10001_asset_manifest(root)
    base_url = (asset_base_url or "HTTPS_ASSET_HOST_TODO/amazon/10001").rstrip("/")
    manifest_by_slug = {
        str(asset["asset_slug"]): asset
        for asset in manifest["color_assets"]
    }
    color_urls: list[dict[str, Any]] = []
    for color in AMAZON_10001_SINGLE_VARIATION_COLORS:
        slug = color["asset_slug"]
        asset = manifest_by_slug.get(slug, {})
        color_urls.append(
            {
                "asset_slug": slug,
                "main_image_locator": f"{base_url}/{slug}/front.jpg",
                "other_image_locator_1": f"{base_url}/{slug}/back.jpg",
                "local_front_path": str(asset.get("front_path") or ""),
                "local_back_path": str(asset.get("back_path") or ""),
                "local_status": str(asset.get("status") or color["asset_status"]),
                "url_status": "placeholder_needs_public_host" if asset_base_url is None else "mapped_to_public_host",
            }
        )
    bundle_urls = {
        "asset_slug": "four_pack_bundle",
        "main_image_locator": f"{base_url}/four_pack_bundle/main.jpg",
        "local_path": manifest["bundle_asset"]["path"],
        "local_status": manifest["bundle_asset"]["status"],
        "url_status": "placeholder_needs_public_host" if asset_base_url is None else "mapped_to_public_host",
    }
    return {
        "packet_type": "amazon_10001_image_url_mapping",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "asset_base_url": base_url,
        "status": "needs_public_asset_host" if asset_base_url is None else "image_urls_mapped",
        "color_urls": color_urls,
        "bundle_url": bundle_urls,
        "hard_rule": "Do not submit local file paths to Amazon; image locators must be stable HTTPS URLs Amazon can fetch.",
    }


def build_amazon_10001_ready_image_upload_manifest_summary(root: Path | None = None) -> dict[str, Any]:
    base_root = root or Path.cwd()
    output_dir = base_root / "outputs"
    candidates = sorted(
        output_dir.glob("amazon_10001_ready_image_upload_manifest_*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if output_dir.exists() else []
    manifest_path = candidates[0] if candidates else None
    rows: list[dict[str, str]] = []
    if manifest_path:
        try:
            with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = [dict(row) for row in csv.DictReader(handle)]
        except (OSError, csv.Error):
            rows = []
    html_path = None
    if manifest_path:
        candidate_html = manifest_path.with_suffix(".html")
        if candidate_html.exists():
            html_path = candidate_html
    file_fields = [
        "main_image_file",
        "other_image_1_back",
        "other_image_2_size_chart",
        "other_image_3_feature",
    ]
    missing_files: list[str] = []
    seen_files: set[str] = set()
    for row in rows:
        for field in file_fields:
            raw = str(row.get(field) or "").strip()
            if not raw or raw in seen_files:
                continue
            seen_files.add(raw)
            local_path = Path(raw)
            if not local_path.is_absolute():
                local_path = base_root / local_path
            if not local_path.exists():
                missing_files.append(raw)
    colors = sorted({str(row.get("color_name") or "").strip() for row in rows if str(row.get("color_name") or "").strip()})
    sizes = sorted({str(row.get("size_name") or "").strip() for row in rows if str(row.get("size_name") or "").strip()})
    skus = sorted({str(row.get("sku") or "").strip() for row in rows if str(row.get("sku") or "").strip()})
    status = (
        "local_web_upload_manifest_ready_for_seller_central_web_upload"
        if manifest_path and rows and not missing_files
        else "local_web_upload_manifest_has_missing_files"
        if manifest_path and rows and missing_files
        else "missing_local_web_upload_manifest"
    )
    return {
        "packet_type": "amazon_10001_ready_image_upload_manifest_summary",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "status": status,
        "manifest_path": str(manifest_path) if manifest_path else "",
        "html_path": str(html_path) if html_path else "",
        "sku_count": len(skus),
        "color_count": len(colors),
        "size_count": len(sizes),
        "colors": colors,
        "sizes": sizes,
        "row_count": len(rows),
        "missing_file_count": len(missing_files),
        "missing_files": missing_files[:20],
        "sample_rows": rows[:6],
        "web_upload_ready": bool(manifest_path and rows and not missing_files),
        "external_submit_allowed": False,
        "next_step": (
            "Use the manifest while editing the existing parent/variation draft in Seller Central: upload the listed local images per SKU/color, then record evidence. For bulk/API paths, replace local files with public HTTPS URLs first."
            if manifest_path and rows and not missing_files
            else "Regenerate the ready image manifest and confirm every local image file exists before Seller Central web upload."
            if manifest_path
            else "Run the ready image manifest builder so the operator has a color/SKU image checklist for Seller Central web upload."
        ),
        "hard_rule": "This manifest is a local Seller Central web-upload checklist. It does not prove Amazon fetched HTTPS images and does not authorize submit, publish, price, inventory, ads, coupon, payment, shipment, or account-security actions.",
    }


def build_amazon_10001_web_image_upload_evidence_summary(root: Path | None = None) -> dict[str, Any]:
    base_root = root or Path.cwd()
    manifest = build_amazon_10001_ready_image_upload_manifest_summary(base_root)
    manifest_rows = [row for row in manifest.get("sample_rows", []) if isinstance(row, dict)]
    manifest_path = Path(str(manifest.get("manifest_path") or ""))
    if manifest_path.exists():
        try:
            with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
                manifest_rows = [dict(row) for row in csv.DictReader(handle)]
        except (OSError, csv.Error):
            manifest_rows = []
    expected_skus = [str(row.get("sku") or "").strip() for row in manifest_rows if str(row.get("sku") or "").strip()]
    color_by_sku = {
        str(row.get("sku") or "").strip(): str(row.get("color_name") or "").strip()
        for row in manifest_rows
        if str(row.get("sku") or "").strip()
    }
    required_slots = ["main_image", "back_image", "size_chart", "feature_image"]
    slot_field_map = {
        "main_image_file": "main_image",
        "other_image_1_back": "back_image",
        "other_image_2_size_chart": "size_chart",
        "other_image_3_feature": "feature_image",
    }
    required_slots_by_sku = {
        str(row.get("sku") or "").strip(): [
            slot_name
            for field_name, slot_name in slot_field_map.items()
            if str(row.get(field_name) or "").strip()
        ] or list(required_slots)
        for row in manifest_rows
        if str(row.get("sku") or "").strip()
    }
    latest_by_sku: dict[str, dict[str, Any]] = {}
    try:
        from .storage import read_records
        records = read_records(base_root, "execution_result")
    except Exception:  # noqa: BLE001 - evidence is optional in offline checks.
        records = []
    for record in sorted(records, key=lambda item: item.created_at, reverse=True):
        fields = record.fields if isinstance(record.fields, dict) else {}
        if str(fields.get("task_package_type") or "") != "amazon_10001_web_image_upload_evidence":
            continue
        if not bool(fields.get("execution_evidence_complete")):
            continue
        raw_skus = fields.get("uploaded_skus")
        if isinstance(raw_skus, list):
            uploaded_skus = [str(item).strip() for item in raw_skus if str(item).strip()]
        else:
            uploaded_skus = [
                item.strip()
                for item in str(raw_skus or fields.get("sku") or "").replace(";", ",").split(",")
                if item.strip()
            ]
        raw_slots = fields.get("image_slots_uploaded")
        if isinstance(raw_slots, list):
            image_slots_uploaded = [str(item).strip() for item in raw_slots if str(item).strip()]
        else:
            image_slots_uploaded = [
                item.strip()
                for item in str(raw_slots or fields.get("image_slot_uploaded") or ",".join(required_slots)).replace(";", ",").split(",")
                if item.strip()
            ]
        image_slots_uploaded = list(dict.fromkeys(image_slots_uploaded))
        for sku in uploaded_skus:
            if expected_skus and sku not in expected_skus:
                continue
            existing = latest_by_sku.get(sku, {})
            merged_slots = list(
                dict.fromkeys(
                    [
                        *(
                            existing.get("image_slots_uploaded", [])
                            if isinstance(existing.get("image_slots_uploaded"), list)
                            else []
                        ),
                        *image_slots_uploaded,
                    ]
                )
            )
            required_for_sku = required_slots_by_sku.get(sku) or list(required_slots)
            missing_slots = [slot for slot in required_for_sku if slot not in merged_slots]
            latest_by_sku[sku] = {
                "sku": sku,
                "color_name": str(fields.get("color_name") or color_by_sku.get(sku) or ""),
                "record_id": record.record_id,
                "created_at": record.created_at,
                "image_slot_status": str(fields.get("image_slot_status") or "uploaded_visible_in_web_draft"),
                "image_slots_uploaded": merged_slots,
                "required_slots": required_for_sku,
                "missing_slots": missing_slots,
                "slot_completion_status": "complete" if not missing_slots else "partial",
                "evidence_ref": str(fields.get("amazon_10001_web_image_upload_evidence_ref") or fields.get("after_screenshot_ref") or ""),
                "external_submit_blocked_ref": str(fields.get("amazon_10001_external_submit_blocked_ref") or ""),
            }
    uploaded_skus = sorted(latest_by_sku)
    complete_skus = sorted([sku for sku, item in latest_by_sku.items() if not item.get("missing_slots")])
    partial_skus = sorted([sku for sku, item in latest_by_sku.items() if item.get("missing_slots")])
    pending_skus = [sku for sku in expected_skus if sku not in complete_skus]
    no_evidence_skus = [sku for sku in expected_skus if sku not in latest_by_sku]
    uploaded_colors = sorted({color_by_sku.get(sku, "") for sku in uploaded_skus if color_by_sku.get(sku, "")})
    pending_colors = sorted({color_by_sku.get(sku, "") for sku in pending_skus if color_by_sku.get(sku, "")})
    status = (
        "all_manifest_skus_have_complete_web_image_evidence"
        if expected_skus and not pending_skus and not partial_skus
        else "partial_web_image_slot_evidence_recorded"
        if uploaded_skus
        else "no_web_image_upload_evidence_recorded"
    )
    return {
        "packet_type": "amazon_10001_web_image_upload_evidence_summary",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "status": status,
        "manifest_status": manifest.get("status"),
        "manifest_path": manifest.get("manifest_path", ""),
        "expected_sku_count": len(expected_skus),
        "uploaded_sku_count": len(uploaded_skus),
        "complete_sku_count": len(complete_skus),
        "partial_sku_count": len(partial_skus),
        "pending_sku_count": len(pending_skus),
        "uploaded_skus": uploaded_skus,
        "complete_skus": complete_skus,
        "partial_skus": partial_skus,
        "pending_skus": pending_skus[:60],
        "no_evidence_skus": no_evidence_skus[:60],
        "uploaded_colors": uploaded_colors,
        "pending_colors": pending_colors,
        "latest_evidence_by_sku": latest_by_sku,
        "external_submit_allowed": False,
        "next_step": (
            "All manifest SKUs have complete local web image-slot evidence. Rerun final gates and continue Product Identity/PTD/inventory checks before any submit."
            if expected_skus and not pending_skus and not partial_skus
            else "Continue Seller Central web image upload for partial or pending SKUs, then write back screenshot evidence without clicking Submit/Publish."
            if expected_skus
            else "Generate the ready-image manifest before recording web image upload evidence."
        ),
        "hard_rule": "This evidence summary only tracks Seller Central web-draft image-slot proof. It does not authorize or perform Save, Submit, Publish, price, inventory, ads, coupon, shipment, payment, refund, or account-security actions.",
    }


def build_amazon_10001_image_public_url_check(
    *,
    asset_base_url: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    mapping = build_amazon_10001_image_url_mapping(asset_base_url=asset_base_url, root=root)
    hosting_plan = build_amazon_10001_asset_hosting_plan(asset_base_url=asset_base_url, root=root)
    base_url_check = hosting_plan["base_url_check"]
    locator_rows = [
        {
            "asset_slug": item["asset_slug"],
            "role": "main_image_locator",
            "url": item["main_image_locator"],
            "valid_base_url": bool(base_url_check["valid_for_amazon"]),
        }
        for item in mapping["color_urls"]
    ]
    locator_rows.extend(
        {
            "asset_slug": item["asset_slug"],
            "role": "other_image_locator_1",
            "url": item["other_image_locator_1"],
            "valid_base_url": bool(base_url_check["valid_for_amazon"]),
        }
        for item in mapping["color_urls"]
    )
    locator_rows.append(
        {
            "asset_slug": "four_pack_bundle",
            "role": "main_image_locator",
            "url": mapping["bundle_url"]["main_image_locator"],
            "valid_base_url": bool(base_url_check["valid_for_amazon"]),
        }
    )
    blockers: list[dict[str, str]] = []
    if not base_url_check["valid_for_amazon"]:
        blockers.append(
            {
                "gate": "asset_base_url",
                "status": str(base_url_check["status"]),
                "reason": str(base_url_check["reason"]),
                "next_step": "Configure a real public HTTPS asset base URL such as the production CDN/R2/CloudFront URL.",
            }
        )
    if hosting_plan["missing_local_files"]:
        blockers.append(
            {
                "gate": "local_image_files",
                "status": "missing_local_files",
                "reason": f"{len(hosting_plan['missing_local_files'])} local source files are missing before upload.",
                "next_step": "Regenerate or restore the missing 10001 flat-lay and bundle image files before uploading.",
            }
        )
    expected_count = (len(AMAZON_10001_SINGLE_VARIATION_COLORS) * 2) + 1
    if len(locator_rows) != expected_count:
        blockers.append(
            {
                "gate": "locator_count",
                "status": "unexpected_locator_count",
                "reason": f"Expected {expected_count} Amazon image locators, got {len(locator_rows)}.",
                "next_step": "Repair color/bundle image mapping before final upload.",
            }
        )
    return {
        "packet_type": "amazon_10001_image_public_url_check",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "status": "image_public_url_mapping_ready_for_owner_review" if not blockers else "blocked_before_image_url_mapping",
        "asset_base_url": asset_base_url or "",
        "base_url_check": base_url_check,
        "locator_count": len(locator_rows),
        "expected_locator_count": expected_count,
        "locators": locator_rows,
        "missing_local_files": hosting_plan["missing_local_files"],
        "missing_verified_local_asset_slugs": [
            item["asset_slug"]
            for item in mapping["color_urls"]
            if item["local_status"] != "front_back_ready_local"
        ],
        "blockers": blockers,
        "external_submit_allowed": False,
        "next_step": (
            "Use these HTTPS locators in the mapped Amazon template only after owner review."
            if not blockers
            else blockers[0]["next_step"]
        ),
        "hard_rule": "This check verifies mapping readiness only. It does not upload files, submit feeds, publish listings, or prove Amazon has fetched the images.",
    }


def _default_amazon_public_image_fetcher(url: str, timeout_seconds: float = 5.0) -> dict[str, Any]:
    request = urlrequest.Request(
        url,
        method="HEAD",
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; TeeLabImageCheck/1.0)",
            "Accept": "image/*,*/*;q=0.8",
        },
    )
    try:
        with urlrequest.urlopen(request, timeout=timeout_seconds) as response:
            status_code = int(getattr(response, "status", 0) or 0)
            content_type = str(response.headers.get("Content-Type") or "")
            content_length = str(response.headers.get("Content-Length") or "")
    except urlerror.HTTPError as exc:
        status_code = int(exc.code or 0)
        content_type = str(exc.headers.get("Content-Type") or "")
        content_length = str(exc.headers.get("Content-Length") or "")
    except Exception as exc:  # noqa: BLE001 - report fetch failure to the operator.
        return {
            "ok": False,
            "status_code": 0,
            "content_type": "",
            "content_length": "",
            "error": str(exc),
        }
    ok = 200 <= status_code < 400 and content_type.lower().startswith("image/")
    return {
        "ok": ok,
        "status_code": status_code,
        "content_type": content_type,
        "content_length": content_length,
        "error": "" if ok else "URL did not return a successful image response.",
    }


def build_amazon_10001_image_public_fetch_check(
    *,
    asset_base_url: str | None = None,
    root: Path | None = None,
    fetcher: Any | None = None,
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    url_check = build_amazon_10001_image_public_url_check(asset_base_url=asset_base_url, root=root)
    blockers: list[dict[str, str]] = []
    fetch_results: list[dict[str, Any]] = []
    url_blockers = [item for item in url_check["blockers"] if item.get("gate") != "local_image_files"]
    if url_blockers:
        blockers.append(
            {
                "gate": "image_url_mapping",
                "status": url_check["status"],
                "reason": "Image URL mapping is not ready for public fetch verification.",
                "next_step": url_blockers[0].get("next_step", url_check["next_step"]),
            }
        )
    else:
        actual_fetcher = fetcher or _default_amazon_public_image_fetcher
        for locator in url_check["locators"]:
            url = str(locator["url"])
            result = actual_fetcher(url, timeout_seconds) if fetcher is None else actual_fetcher(url)
            row = {
                "asset_slug": locator["asset_slug"],
                "role": locator["role"],
                "url": url,
                **result,
            }
            fetch_results.append(row)
        failed = [row for row in fetch_results if not row.get("ok")]
        if failed:
            blockers.append(
                {
                    "gate": "image_public_fetch",
                    "status": "fetch_failed",
                    "reason": f"{len(failed)} of {len(fetch_results)} image URLs did not return a successful image response.",
                    "next_step": "Confirm CDN/R2/CloudFront public permissions, content type, object paths, and cache propagation.",
                }
            )
    return {
        "packet_type": "amazon_10001_image_public_fetch_check",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "status": "image_public_fetch_ready_for_owner_review" if not blockers else "blocked_before_image_public_fetch",
        "asset_base_url": asset_base_url or "",
        "locator_count": url_check["locator_count"],
        "checked_count": len(fetch_results),
        "passed_count": sum(1 for row in fetch_results if row.get("ok")),
        "failed_count": sum(1 for row in fetch_results if not row.get("ok")),
        "fetch_results": fetch_results,
        "url_check": url_check,
        "blockers": blockers,
        "external_submit_allowed": False,
        "next_step": (
            "Image URLs are publicly fetchable; keep them for owner review and final upload gates."
            if not blockers
            else blockers[0]["next_step"]
        ),
        "hard_rule": "This check only verifies public image fetchability. It does not upload files, submit feeds, publish listings, or prove Amazon accepted the images.",
    }


def load_latest_amazon_10001_image_public_fetch_check(root: Path) -> dict[str, Any] | None:
    output_dir = root / "outputs"
    candidates = sorted(
        output_dir.glob("amazon_10001_image_public_fetch_check_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("packet_type") == "amazon_10001_image_public_fetch_check":
            return {
                **payload,
                "report_path": str(path),
            }
    return None


def load_latest_amazon_10001_image_public_url_check(root: Path) -> dict[str, Any] | None:
    output_dir = root / "outputs"
    candidates = sorted(
        output_dir.glob("amazon_10001_image_public_url_check_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("packet_type") == "amazon_10001_image_public_url_check":
            return {
                **payload,
                "report_path": str(path),
            }
    return None


def load_latest_amazon_10001_store_execution_readiness(root: Path) -> dict[str, Any] | None:
    output_dir = root / "outputs"
    candidates = sorted(
        output_dir.glob("amazon_10001_store_execution_readiness*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("packet_type") == "amazon_10001_store_execution_readiness":
            return {
                **payload,
                "report_path": str(path),
            }
    return None


def validate_amazon_image_asset_base_url(asset_base_url: str | None) -> dict[str, Any]:
    if not asset_base_url:
        return {
            "status": "missing_asset_base_url",
            "valid_for_amazon": False,
            "reason": "No public HTTPS asset base URL configured.",
        }
    parsed = urlparse(asset_base_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        return {
            "status": "invalid_scheme",
            "valid_for_amazon": False,
            "reason": "Amazon image locators must use https URLs.",
        }
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        return {
            "status": "local_host_not_fetchable",
            "valid_for_amazon": False,
            "reason": "Amazon cannot fetch localhost or local-network image URLs.",
        }
    if "todo" in asset_base_url.lower() or "example.com" in host:
        return {
            "status": "placeholder_url",
            "valid_for_amazon": False,
            "reason": "Placeholder/example URLs must be replaced with the real asset host before upload.",
        }
    return {
        "status": "base_url_ready",
        "valid_for_amazon": True,
        "reason": "Base URL is syntactically acceptable for Amazon image locator mapping.",
    }


def build_amazon_10001_asset_hosting_plan(
    *,
    asset_base_url: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    manifest = build_amazon_10001_asset_manifest(root)
    url_check = validate_amazon_image_asset_base_url(asset_base_url)
    upload_tasks: list[dict[str, Any]] = []
    for asset in manifest["color_assets"]:
        slug = asset["asset_slug"]
        upload_tasks.extend(
            [
                {
                    "asset_slug": slug,
                    "role": "front_main",
                    "local_path": asset["front_path"],
                    "exists": asset["front_exists"],
                    "target_relative_path": f"{slug}/front.jpg",
                    "target_url": f"{(asset_base_url or 'HTTPS_ASSET_HOST_TODO/amazon/10001').rstrip('/')}/{slug}/front.jpg",
                },
                {
                    "asset_slug": slug,
                    "role": "back_secondary",
                    "local_path": asset["back_path"],
                    "exists": asset["back_exists"],
                    "target_relative_path": f"{slug}/back.jpg",
                    "target_url": f"{(asset_base_url or 'HTTPS_ASSET_HOST_TODO/amazon/10001').rstrip('/')}/{slug}/back.jpg",
                },
            ]
        )
    bundle_asset = manifest["bundle_asset"]
    upload_tasks.append(
        {
            "asset_slug": "four_pack_bundle",
            "role": "bundle_main",
            "local_path": bundle_asset["path"],
            "exists": bundle_asset["exists"],
            "target_relative_path": "four_pack_bundle/main.jpg",
            "target_url": f"{(asset_base_url or 'HTTPS_ASSET_HOST_TODO/amazon/10001').rstrip('/')}/four_pack_bundle/main.jpg",
        }
    )
    missing_local_files = [
        task["target_relative_path"]
        for task in upload_tasks
        if not task["exists"]
    ]
    status = (
        "ready_to_upload_to_asset_host"
        if url_check["valid_for_amazon"] and not missing_local_files
        else "needs_public_asset_host"
        if not url_check["valid_for_amazon"]
        else "needs_local_asset_work"
    )
    return {
        "packet_type": "amazon_10001_asset_hosting_plan",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "status": status,
        "asset_base_url": asset_base_url or "",
        "base_url_check": url_check,
        "upload_task_count": len(upload_tasks),
        "upload_tasks": upload_tasks,
        "missing_local_files": missing_local_files,
        "submit_allowed": False,
        "next_step": "Upload each local file to the target URL path, then regenerate image URL mapping with the real HTTPS base URL.",
    }


def build_amazon_10001_asset_provider_readiness(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ or os.environ
    groups: list[dict[str, Any]] = []
    ready_providers: list[str] = []
    for group in AMAZON_10001_ASSET_PROVIDER_ENV_GROUPS:
        missing = [key for key in group["required_env"] if not env.get(key)]
        provider_ready = not missing
        if provider_ready:
            ready_providers.append(group["provider"])
        groups.append(
            {
                "provider": group["provider"],
                "status": "ready" if provider_ready else "missing_env",
                "required_env": [
                    {
                        "name": key,
                        "present": bool(env.get(key)),
                        "value_visible": False,
                    }
                    for key in group["required_env"]
                ],
                "missing": missing,
                "cli": group["cli"],
                "endpoint_template": group["endpoint_template"],
            }
        )
    return {
        "packet_type": "amazon_10001_asset_provider_readiness",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "status": "ready" if ready_providers else "missing_provider_credentials",
        "ready_providers": ready_providers,
        "groups": groups,
        "hard_rule": "Never expose access keys or secrets in reports; only report whether required variables are present.",
    }


def build_amazon_10001_asset_upload_command_plan(
    *,
    provider: str = "cloudflare_r2_s3_compatible",
    asset_base_url: str | None = None,
    environ: Mapping[str, str] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    env = environ or os.environ
    readiness = build_amazon_10001_asset_provider_readiness(env)
    provider_status = next(
        (group for group in readiness["groups"] if group["provider"] == provider),
        None,
    )
    hosting_plan = build_amazon_10001_asset_hosting_plan(asset_base_url=asset_base_url or env.get("ASSET_PUBLIC_BASE_URL"), root=root)
    if provider_status is None:
        return {
            "packet_type": "amazon_10001_asset_upload_command_plan",
            "status": "unknown_provider",
            "provider": provider,
            "known_providers": [group["provider"] for group in readiness["groups"]],
            "submit_allowed": False,
        }
    commands: list[dict[str, str]] = []
    bucket = (
        env.get("R2_BUCKET")
        if provider == "cloudflare_r2_s3_compatible"
        else env.get("ASSET_S3_BUCKET")
        if provider == "aws_s3_cloudfront"
        else env.get("S3_BUCKET")
    ) or "BUCKET_TODO"
    endpoint = (
        f"https://{env.get('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"
        if provider == "cloudflare_r2_s3_compatible" and env.get("R2_ACCOUNT_ID")
        else env.get("S3_ENDPOINT_URL")
        if provider == "generic_s3_compatible"
        else ""
    )
    for task in hosting_plan["upload_tasks"]:
        local_path = str(task["local_path"])
        destination = f"s3://{bucket}/amazon/10001/{task['target_relative_path']}"
        if provider == "aws_s3_cloudfront":
            command = f'aws s3 cp "{local_path}" "{destination}" --content-type image/jpeg'
        else:
            endpoint_part = f' --endpoint-url "{endpoint or "ENDPOINT_URL_TODO"}"'
            command = f'aws s3 cp "{local_path}" "{destination}" --content-type image/jpeg{endpoint_part}'
        commands.append(
            {
                "asset_slug": str(task["asset_slug"]),
                "role": str(task["role"]),
                "command": command,
                "target_url": str(task["target_url"]),
            }
        )
    blockers: list[str] = []
    if provider_status["status"] != "ready":
        blockers.append("provider_credentials_missing")
    if not hosting_plan["base_url_check"]["valid_for_amazon"]:
        blockers.append("asset_base_url_not_ready")
    if hosting_plan["missing_local_files"]:
        blockers.append("missing_local_files")
    return {
        "packet_type": "amazon_10001_asset_upload_command_plan",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "provider": provider,
        "status": "ready_to_run_upload_commands" if not blockers else "blocked_before_upload",
        "provider_status": provider_status,
        "asset_hosting_status": hosting_plan["status"],
        "command_count": len(commands),
        "commands": commands,
        "blockers": blockers,
        "submit_allowed": False,
        "hard_rule": "Commands are a local operator plan only; do not run upload commands until credentials and final public base URL are confirmed.",
    }


def _amazon_marketplace_value(value: Any, marketplace_id: str) -> dict[str, Any]:
    return {"value": value, "marketplace_id": marketplace_id}


def _amazon_language_value(value: str, marketplace_id: str) -> dict[str, Any]:
    return {"value": value, "language_tag": "en_US", "marketplace_id": marketplace_id}


def _amazon_10001_base_attributes(marketplace_id: str) -> dict[str, Any]:
    return {
        "brand": [_amazon_marketplace_value("TeeLab", marketplace_id)],
        "condition_type": [_amazon_marketplace_value("new_new", marketplace_id)],
        "material": [_amazon_marketplace_value("Cotton", marketplace_id)],
        "fabric_type": [_amazon_marketplace_value("100% Cotton", marketplace_id)],
        "fit_type": [_amazon_marketplace_value("Oversized Fit", marketplace_id)],
        "bullet_point": [
            _amazon_language_value("230g vintage washed cotton fabric with a soft heavyweight feel.", marketplace_id),
            _amazon_language_value("Oversized crewneck cut for everyday streetwear styling.", marketplace_id),
            _amazon_language_value("Prepared for FBM self-warehouse fulfillment on Amazon US.", marketplace_id),
        ],
        "product_description": [
            _amazon_language_value(
                "TeeLab 10001 is a 230g vintage washed 100% cotton short sleeve T-shirt prepared for the Amazon US marketplace seller route. This draft is blocked from real publish until Product Identity, image URLs, and Product Type Definitions validation are complete.",
                marketplace_id,
            )
        ],
    }


def build_amazon_10001_parent_child_json_feed_draft(
    *,
    seller_id: str = "SELLER_ID_TODO",
    marketplace_id: str = AMAZON_US_MARKETPLACE_ID,
    asset_base_url: str | None = None,
) -> dict[str, Any]:
    matrix = build_amazon_10001_variation_matrix()
    url_mapping = build_amazon_10001_image_url_mapping(asset_base_url=asset_base_url)
    color_url_by_slug = {item["asset_slug"]: item for item in url_mapping["color_urls"]}
    messages: list[dict[str, Any]] = []
    message_id = 1

    for parent in matrix["parents"]:
        item_name = (
            "TeeLab Men's Vintage Washed Cotton T-Shirt, Oversized Crewneck, Size and Color Variations"
            if parent["listing_family"] == "single_tshirt"
            else "TeeLab Men's Vintage Washed Cotton T-Shirt 4 Pack, Oversized Crewneck, Size Variations"
        )
        attributes = _amazon_10001_base_attributes(marketplace_id)
        attributes.update(
            {
                "item_name": [_amazon_language_value(item_name, marketplace_id)],
                "parentage_level": [_amazon_marketplace_value("parent", marketplace_id)],
                "variation_theme": [_amazon_marketplace_value(parent["variation_theme"], marketplace_id)],
            }
        )
        messages.append(
            {
                "messageId": message_id,
                "sku": parent["sku"],
                "operationType": "UPDATE",
                "productType": "SHIRT",
                "requirements": "LISTING",
                "attributes": attributes,
                "tk_preflight": {
                    "relationship_type": parent["relationship_type"],
                    "listing_family": parent["listing_family"],
                    "submit_allowed": False,
                    "status": "parent_draft_needs_ptd_validation",
                },
            }
        )
        message_id += 1

    for child in matrix["single_children"]:
        urls = color_url_by_slug[child["asset_slug"]]
        attributes = _amazon_10001_base_attributes(marketplace_id)
        attributes.update(
            {
                "item_name": [
                    _amazon_language_value(
                        f"TeeLab Men's Vintage Washed Cotton T-Shirt, {child['color']}, {child['size']}, Oversized Crewneck, 100% Cotton",
                        marketplace_id,
                    )
                ],
                "parentage_level": [_amazon_marketplace_value("child", marketplace_id)],
                "variation_theme": [_amazon_marketplace_value(child["variation_theme"], marketplace_id)],
                "child_parent_sku_relationship": [
                    {
                        "parent_sku": child["parent_sku"],
                        "marketplace_id": marketplace_id,
                    }
                ],
                "color": [_amazon_marketplace_value(child["color"], marketplace_id)],
                "size": [_amazon_marketplace_value(child["size"], marketplace_id)],
                "main_product_image_locator": [_amazon_marketplace_value(urls["main_image_locator"], marketplace_id)],
                "other_product_image_locator": [_amazon_marketplace_value(urls["other_image_locator_1"], marketplace_id)],
                "purchasable_offer": [
                    {
                        "currency": "USD",
                        "marketplace_id": marketplace_id,
                        "our_price": [{"schedule": [{"value_with_tax": child["price_usd"]}]}],
                    }
                ],
                "fulfillment_availability": [
                    {"fulfillment_channel_code": "DEFAULT", "quantity": child["quantity"]}
                ],
            }
        )
        messages.append(
            {
                "messageId": message_id,
                "sku": child["sku"],
                "operationType": "UPDATE",
                "productType": "SHIRT",
                "requirements": "LISTING",
                "attributes": attributes,
                "tk_preflight": {
                    "relationship_type": child["relationship_type"],
                    "listing_family": child["listing_family"],
                    "submit_allowed": False,
                    "asset_status": child["asset_status"],
                    "image_url_status": urls["url_status"],
                    "product_identity_status": child["product_identity_status"],
                    "product_type_status": child["product_type_status"],
                },
            }
        )
        message_id += 1

    bundle_url = url_mapping["bundle_url"]
    for child in matrix["bundle_children"]:
        attributes = _amazon_10001_base_attributes(marketplace_id)
        attributes.update(
            {
                "item_name": [
                    _amazon_language_value(
                        f"TeeLab Men's Vintage Washed Cotton T-Shirt 4 Pack, Mixed Colors, {child['size']}, Oversized Crewneck, 100% Cotton",
                        marketplace_id,
                    )
                ],
                "parentage_level": [_amazon_marketplace_value("child", marketplace_id)],
                "variation_theme": [_amazon_marketplace_value(child["variation_theme"], marketplace_id)],
                "child_parent_sku_relationship": [
                    {
                        "parent_sku": child["parent_sku"],
                        "marketplace_id": marketplace_id,
                    }
                ],
                "color": [_amazon_marketplace_value(child["color"], marketplace_id)],
                "size": [_amazon_marketplace_value(child["size"], marketplace_id)],
                "main_product_image_locator": [_amazon_marketplace_value(bundle_url["main_image_locator"], marketplace_id)],
                "purchasable_offer": [
                    {
                        "currency": "USD",
                        "marketplace_id": marketplace_id,
                        "our_price": [{"schedule": [{"value_with_tax": child["price_usd"]}]}],
                    }
                ],
                "fulfillment_availability": [
                    {"fulfillment_channel_code": "DEFAULT", "quantity": child["quantity"]}
                ],
            }
        )
        messages.append(
            {
                "messageId": message_id,
                "sku": child["sku"],
                "operationType": "UPDATE",
                "productType": "SHIRT",
                "requirements": "LISTING",
                "attributes": attributes,
                "tk_preflight": {
                    "relationship_type": child["relationship_type"],
                    "listing_family": child["listing_family"],
                    "submit_allowed": False,
                    "asset_status": child["asset_status"],
                    "image_url_status": bundle_url["url_status"],
                    "product_identity_status": child["product_identity_status"],
                    "product_type_status": child["product_type_status"],
                },
            }
        )
        message_id += 1

    blockers = [
        "Image locators use placeholders until a stable HTTPS asset host is configured.",
        "Product Identity remains blocked until legal GS1 GTINs or Amazon GTIN exemption.",
        "Parent/child attributes must be validated against live Amazon Product Type Definitions schema.",
        "This feed is draft-only and must not be submitted externally without owner confirmation.",
    ]
    return {
        "header": {
            "sellerId": seller_id,
            "version": "2.0",
            "issueLocale": "en_US",
        },
        "messages": messages,
        "tk_preflight": {
            "packet_type": "amazon_10001_parent_child_json_feed_draft",
            "submit_allowed": False,
            "route": dict(AMAZON_10001_BULK_ROUTE),
            "message_count": len(messages),
            "parent_count": len(matrix["parents"]),
            "single_child_count": len(matrix["single_children"]),
            "bundle_child_count": len(matrix["bundle_children"]),
            "image_url_mapping_status": url_mapping["status"],
            "blockers": blockers,
        },
    }


def build_amazon_10001_seller_central_alignment() -> dict[str, Any]:
    return {
        "packet_type": "amazon_10001_seller_central_alignment",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "observed_store_state": {
            "store": "BI ZHENG",
            "marketplace": "United States",
            "page": "Manage All Inventory",
            "visible_actions": ["Add newer version", "Add a variation", "Add a product"],
            "visible_tabs": ["All listings", "Complete drafts", "Activate listings", "Enhance listings", "Review listing changes"],
            "visible_columns": [
                "Listing status",
                "Product details",
                "Performance",
                "Inventory",
                "Price and shipping cost",
                "Estimated fees",
            ],
            "current_store_signal": "Existing backpack listing shows FBM/FBA inventory and price fields; 10001 T-shirt must fit the same inventory, pricing, fee, and status model.",
        },
        "usable_paths": [
            {
                "path": "seller_central_manual",
                "entry": "Add a product / Add a variation",
                "fit": "Good for one-off validation and checking how the store asks for fields.",
                "limit": "Too slow for 58 parent/child rows; use only as browser verification.",
            },
            {
                "path": "seller_central_spreadsheet",
                "entry": "Add Products > Spreadsheet > Download blank template",
                "fit": "Best store-compatible path before SP-API is authorized.",
                "limit": "Requires downloading the Amazon US category template; internal seed CSV is not final upload file.",
            },
            {
                "path": "sp_api_json_listings_feed",
                "entry": "JSON_LISTINGS_FEED",
                "fit": "Best long-term automation path once developer authorization exists.",
                "limit": "Must pass Product Type Definitions schema and validate-only before submit.",
            },
        ],
        "internal_artifacts_and_fit": [
            {
                "artifact": "amazon_10001_bulk_upload_seed_2026-07-01.csv",
                "fit": "Internal source-of-truth seed for parent/child rows.",
                "store_compatibility": "not_final_upload_template",
                "next_step": "Map columns to the downloaded Amazon inventory file template for Clothing > Men > T-Shirts.",
            },
            {
                "artifact": "amazon_10001_parent_child_json_feed_draft_2026-07-01.json",
                "fit": "Draft JSON_LISTINGS_FEED payload for SP-API route.",
                "store_compatibility": "validate_only_after_ptd",
                "next_step": "Run Product Type Definitions, then feed validation; do not submit directly.",
            },
            {
                "artifact": "amazon_10001_image_url_mapping_2026-07-01.json",
                "fit": "Maps local product images to stable HTTPS image locator slots.",
                "store_compatibility": "blocked_until_public_urls",
                "next_step": "Upload approved images to asset host and replace placeholders.",
            },
        ],
        "field_mapping_policy": {
            "do_not_assume": [
                "Do not assume generic CSV headers equal Amazon inventory template headers.",
                "Do not assume JSON_LISTINGS_FEED attributes equal flat-file template columns.",
                "Do not upload local image paths; use HTTPS image locators only.",
                "Do not publish without Product Identity, PTD validation, and owner confirmation.",
            ],
            "must_map_from_store_template": [
                "item_sku",
                "parent_child",
                "parent_sku",
                "relationship_type",
                "variation_theme",
                "item_name",
                "brand_name",
                "color_name",
                "size_name",
                "standard_price",
                "quantity",
                "main_image_url",
                "other_image_url1",
                "fulfillment_channel",
                "product_id",
                "product_id_type",
            ],
        },
        "status": "needs_amazon_template_download_before_real_upload",
        "next_step": "Use the live store to download the Amazon US clothing/T-shirt inventory template, then generate a template-specific upload file from the seed rows.",
        "official_sources": list(AMAZON_SELLER_CENTRAL_ALIGNMENT_SOURCES),
    }


def _normalize_template_column(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        .replace(".", "_")
    )


def build_amazon_10001_inventory_template_mapping(
    downloaded_columns: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    normalized_to_original = {
        _normalize_template_column(column): column
        for column in (downloaded_columns or [])
        if str(column).strip()
    }
    mappings: list[dict[str, Any]] = []
    for field in AMAZON_10001_TEMPLATE_COLUMN_CANDIDATES:
        matched_column = ""
        for alias in field["aliases"]:
            normalized_alias = _normalize_template_column(str(alias))
            if normalized_alias in normalized_to_original:
                matched_column = normalized_to_original[normalized_alias]
                break
        mappings.append(
            {
                "internal_field": field["internal_field"],
                "required": field["required"],
                "source": field["source"],
                "candidate_aliases": list(field["aliases"]),
                "template_column": matched_column,
                "status": "mapped" if matched_column else "needs_template_column",
            }
        )
    required_missing = [
        item["internal_field"]
        for item in mappings
        if item["required"] and item["status"] != "mapped"
    ]
    optional_missing = [
        item["internal_field"]
        for item in mappings
        if not item["required"] and item["status"] != "mapped"
    ]
    return {
        "packet_type": "amazon_10001_inventory_template_mapping",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "downloaded_template_present": bool(downloaded_columns),
        "downloaded_column_count": len(downloaded_columns or []),
        "status": "mapped_ready_for_template_rows" if downloaded_columns and not required_missing else "needs_downloaded_inventory_template",
        "mappings": mappings,
        "required_missing": required_missing,
        "optional_missing": optional_missing,
        "hard_rule": "Generate a final Seller Central upload file only after the live Amazon US clothing/T-shirt template columns are available.",
        "next_step": "Download the live Seller Central inventory file template, then pass its headers through this mapper.",
    }


def build_amazon_10001_inventory_template_rows(
    downloaded_columns: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    mapping = build_amazon_10001_inventory_template_mapping(downloaded_columns)
    if mapping["required_missing"]:
        return {
            "packet_type": "amazon_10001_inventory_template_rows",
            "status": "blocked_by_unmapped_template_columns",
            "mapping": mapping,
            "rows": [],
        }
    matrix = build_amazon_10001_variation_matrix()
    url_mapping = build_amazon_10001_image_url_mapping()
    color_url_by_slug = {item["asset_slug"]: item for item in url_mapping["color_urls"]}
    field_to_column = {
        item["internal_field"]: item["template_column"]
        for item in mapping["mappings"]
        if item["template_column"]
    }

    def blank_row() -> dict[str, str]:
        return {column: "" for column in downloaded_columns}

    def set_value(row: dict[str, str], field: str, value: Any) -> None:
        column = field_to_column.get(field)
        if column:
            row[column] = "" if value is None else str(value)

    rows: list[dict[str, str]] = []
    for parent in matrix["parents"]:
        row = blank_row()
        set_value(row, "sku", parent["sku"])
        set_value(row, "parent_child", "Parent")
        set_value(row, "relationship_type", "")
        set_value(row, "variation_theme", parent["variation_theme"])
        set_value(
            row,
            "item_name",
            "TeeLab Men's Vintage Washed Cotton T-Shirt"
            if parent["listing_family"] == "single_tshirt"
            else "TeeLab Men's Vintage Washed Cotton T-Shirt 4 Pack",
        )
        set_value(row, "brand", "TeeLab")
        set_value(row, "fulfillment_channel", "DEFAULT")
        rows.append(row)

    for child in matrix["single_children"]:
        urls = color_url_by_slug[child["asset_slug"]]
        row = blank_row()
        set_value(row, "sku", child["sku"])
        set_value(row, "parent_sku", child["parent_sku"])
        set_value(row, "parent_child", "Child")
        set_value(row, "relationship_type", "Variation")
        set_value(row, "variation_theme", child["variation_theme"])
        set_value(row, "item_name", f"TeeLab Men's Vintage Washed Cotton T-Shirt, {child['color']}, {child['size']}")
        set_value(row, "brand", "TeeLab")
        set_value(row, "color", child["color"])
        set_value(row, "size", child["size"])
        set_value(row, "price_usd", f"{child['price_usd']:.2f}")
        set_value(row, "quantity", child["quantity"])
        set_value(row, "fulfillment_channel", "DEFAULT")
        set_value(row, "main_image_locator", urls["main_image_locator"])
        set_value(row, "other_image_locator_1", urls["other_image_locator_1"])
        rows.append(row)

    bundle_url = url_mapping["bundle_url"]
    for child in matrix["bundle_children"]:
        row = blank_row()
        set_value(row, "sku", child["sku"])
        set_value(row, "parent_sku", child["parent_sku"])
        set_value(row, "parent_child", "Child")
        set_value(row, "relationship_type", "Variation")
        set_value(row, "variation_theme", child["variation_theme"])
        set_value(row, "item_name", f"TeeLab Men's Vintage Washed Cotton T-Shirt 4 Pack, {child['size']}")
        set_value(row, "brand", "TeeLab")
        set_value(row, "color", child["color"])
        set_value(row, "size", child["size"])
        set_value(row, "price_usd", f"{child['price_usd']:.2f}")
        set_value(row, "quantity", child["quantity"])
        set_value(row, "fulfillment_channel", "DEFAULT")
        set_value(row, "main_image_locator", bundle_url["main_image_locator"])
        rows.append(row)

    return {
        "packet_type": "amazon_10001_inventory_template_rows",
        "status": "template_rows_ready_needs_business_blockers",
        "mapping": mapping,
        "rows": rows,
        "row_count": len(rows),
        "submit_allowed": False,
        "blockers": [
            "Template rows still contain image URL placeholders until a public asset host is configured.",
            "Product ID and Product ID Type remain empty until legal GS1 GTINs or Amazon GTIN exemption.",
            "Rows require Seller Central upload validation before publish.",
        ],
    }


def _read_amazon_text_template_columns(path: Path) -> tuple[list[str], str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    if not first_line:
        return [], "empty_text"
    delimiter = "\t" if "\t" in first_line else ","
    row = next(csv.reader([first_line], delimiter=delimiter))
    return [cell.strip() for cell in row if cell.strip()], "tsv_text" if delimiter == "\t" else "csv_text"


def _read_xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    xml = archive.read("xl/sharedStrings.xml")
    root = ElementTree.fromstring(xml)
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings: list[str] = []
    for item in root.findall("x:si", namespace):
        text_parts = [node.text or "" for node in item.findall(".//x:t", namespace)]
        strings.append("".join(text_parts))
    return strings


def _read_xlsx_first_sheet_columns(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if "xl/worksheets/sheet1.xml" not in names:
            return []
        shared_strings = _read_xlsx_shared_strings(archive)
        root = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    first_row = root.find(".//x:sheetData/x:row", namespace)
    if first_row is None:
        return []
    columns: list[str] = []
    for cell in first_row.findall("x:c", namespace):
        cell_type = cell.attrib.get("t")
        value_node = cell.find("x:v", namespace)
        inline_node = cell.find("x:is/x:t", namespace)
        value = ""
        if cell_type == "s" and value_node is not None:
            index = int(value_node.text or "0")
            value = shared_strings[index] if 0 <= index < len(shared_strings) else ""
        elif cell_type == "inlineStr" and inline_node is not None:
            value = inline_node.text or ""
        elif value_node is not None:
            value = value_node.text or ""
        if value.strip():
            columns.append(value.strip())
    return columns


def read_amazon_inventory_template_columns(template_path: Path) -> dict[str, Any]:
    path = Path(template_path)
    if not path.exists():
        return {
            "packet_type": "amazon_inventory_template_columns",
            "path": str(path),
            "status": "missing_file",
            "format": "unknown",
            "columns": [],
            "column_count": 0,
        }
    suffix = path.suffix.lower()
    try:
        if suffix == ".xlsx" or zipfile.is_zipfile(path):
            columns = _read_xlsx_first_sheet_columns(path)
            detected_format = "xlsx"
        elif suffix in {".csv", ".tsv", ".txt", ".xls"}:
            if suffix == ".xls" and not path.read_bytes()[:16].startswith((b"item_", b"sku", b"\xef\xbb\xbf")):
                return {
                    "packet_type": "amazon_inventory_template_columns",
                    "path": str(path),
                    "status": "unsupported_legacy_xls",
                    "format": "binary_xls",
                    "columns": [],
                    "column_count": 0,
                    "next_step": "Open the Amazon template and save/export it as .xlsx or tab-delimited .txt, then rerun the mapper.",
                }
            columns, detected_format = _read_amazon_text_template_columns(path)
        else:
            columns, detected_format = _read_amazon_text_template_columns(path)
    except Exception as exc:
        return {
            "packet_type": "amazon_inventory_template_columns",
            "path": str(path),
            "status": "read_error",
            "format": suffix.lstrip(".") or "unknown",
            "columns": [],
            "column_count": 0,
            "error": str(exc),
        }
    return {
        "packet_type": "amazon_inventory_template_columns",
        "path": str(path),
        "status": "headers_ready" if columns else "no_headers_found",
        "format": detected_format,
        "columns": columns,
        "column_count": len(columns),
    }


def build_amazon_10001_inventory_template_file_mapping(template_path: Path) -> dict[str, Any]:
    columns_packet = read_amazon_inventory_template_columns(template_path)
    mapping = build_amazon_10001_inventory_template_mapping(columns_packet["columns"])
    rows_packet = (
        build_amazon_10001_inventory_template_rows(columns_packet["columns"])
        if columns_packet["status"] == "headers_ready"
        else {
            "packet_type": "amazon_10001_inventory_template_rows",
            "status": "blocked_by_template_header_read",
            "rows": [],
        }
    )
    return {
        "packet_type": "amazon_10001_inventory_template_file_mapping",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "template_columns": columns_packet,
        "mapping": mapping,
        "rows_packet": rows_packet,
        "status": rows_packet["status"],
        "submit_allowed": False,
    }


def find_amazon_inventory_template_candidates(download_dir: Path | None = None) -> list[dict[str, Any]]:
    directory = download_dir or (Path.home() / "Downloads")
    if not directory.exists():
        return []
    name_tokens = (
        "amazon",
        "inventory",
        "template",
        "flat",
        "listing",
        "clothing",
        "shirt",
        "feed",
        "browse",
        "category",
        "库存",
        "模板",
        "上传",
        "服装",
    )
    allowed_suffixes = {".txt", ".tsv", ".csv", ".xlsx", ".xls"}
    candidates: list[dict[str, Any]] = []
    for path in directory.iterdir():
        if not path.is_file() or path.suffix.lower() not in allowed_suffixes:
            continue
        lower_name = path.name.lower()
        if not any(token in lower_name for token in name_tokens):
            continue
        stat = path.stat()
        candidates.append(
            {
                "path": str(path),
                "name": path.name,
                "suffix": path.suffix.lower(),
                "size_bytes": stat.st_size,
                "modified_timestamp": stat.st_mtime,
            }
        )
    return sorted(candidates, key=lambda item: item["modified_timestamp"], reverse=True)


def build_amazon_10001_latest_downloaded_template_mapping(
    download_dir: Path | None = None,
) -> dict[str, Any]:
    candidates = find_amazon_inventory_template_candidates(download_dir)
    if not candidates:
        return {
            "packet_type": "amazon_10001_latest_downloaded_template_mapping",
            "route": dict(AMAZON_10001_BULK_ROUTE),
            "download_dir": str(download_dir or (Path.home() / "Downloads")),
            "status": "no_downloaded_template_found",
            "candidates": [],
            "next_step": "Download the Amazon US Clothing/T-shirt inventory template from Seller Central Spreadsheet flow.",
            "submit_allowed": False,
        }
    latest = candidates[0]
    mapping = build_amazon_10001_inventory_template_file_mapping(Path(latest["path"]))
    return {
        "packet_type": "amazon_10001_latest_downloaded_template_mapping",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "download_dir": str(download_dir or (Path.home() / "Downloads")),
        "status": mapping["status"],
        "latest_candidate": latest,
        "candidate_count": len(candidates),
        "candidates": candidates[:10],
        "mapping": mapping,
        "submit_allowed": False,
        "next_step": "Review mapped rows and business blockers before creating any Seller Central upload.",
    }


def build_amazon_10001_seller_central_template_download_runbook(
    *,
    download_dir: Path | None = None,
    seller_central_logged_in: bool = False,
) -> dict[str, Any]:
    latest_template = build_amazon_10001_latest_downloaded_template_mapping(download_dir)
    template_ready = latest_template["status"] == "template_rows_ready_needs_business_blockers"
    blockers: list[dict[str, str]] = []
    if not seller_central_logged_in:
        blockers.append(
            {
                "gate": "seller_central_session",
                "severity": "needs_store_session",
                "reason": "A live Amazon US Seller Central session is required to download the official template.",
                "next_step": "Open the fixed Amazon US BitBrowser/Seller Central profile; stop at 2FA, captcha, or account-security prompts.",
            }
        )
    if not template_ready:
        blockers.append(
            {
                "gate": "downloaded_template",
                "severity": "blocker",
                "reason": "No mapped Amazon US Clothing/T-shirt template is currently available in Downloads.",
                "next_step": "Use Seller Central Add Products > Spreadsheet / Upload Products flow to download the Clothing/T-shirt template.",
            }
        )
    steps = [
        {
            "id": "AMZ-10001-TPL-01",
            "surface": "Seller Central",
            "action": "Open Catalog > Add Products via Upload, then choose the Spreadsheet tab.",
            "agent_mode": "browser_assist",
            "safe_to_automate": seller_central_logged_in,
        },
        {
            "id": "AMZ-10001-TPL-02",
            "surface": "Seller Central",
            "action": "Choose Amazon US marketplace and Clothing > Men > Shirts > T-Shirts / SHIRT where available.",
            "agent_mode": "guided_select",
            "safe_to_automate": seller_central_logged_in,
        },
        {
            "id": "AMZ-10001-TPL-03",
            "surface": "Seller Central",
            "action": "Download the blank inventory template as .txt/.xlsx if offered.",
            "agent_mode": "download_file",
            "safe_to_automate": seller_central_logged_in,
        },
        {
            "id": "AMZ-10001-TPL-04",
            "surface": "Local Downloads watcher",
            "action": "Scan Downloads, read headers, map columns, and create a 58-row upload candidate only if headers are readable.",
            "agent_mode": "local_verify",
            "safe_to_automate": True,
        },
        {
            "id": "AMZ-10001-TPL-05",
            "surface": "Local mapper",
            "action": "Keep final upload disabled until Product Identity, HTTPS images, PTD schema, and owner gates pass.",
            "agent_mode": "gated_build",
            "safe_to_automate": True,
        },
    ]
    return {
        "packet_type": "amazon_10001_seller_central_template_download_runbook",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "status": "template_downloaded_and_mapped" if template_ready else "needs_seller_central_template_download",
        "latest_template_status": latest_template["status"],
        "latest_template": latest_template,
        "download_dir": str(download_dir or (Path.home() / "Downloads")),
        "seller_central_entry": {
            "primary_url": "https://sellercentral.amazon.com/listing/upload",
            "fallback_navigation": "Catalog > Add Products via Upload > Spreadsheet",
            "official_help_url": "https://sellercentral.amazon.com/help/hub/reference/external/201576670?locale=en-US",
            "boundary": "Open/navigation only; do not upload a file or submit anything from this runbook.",
        },
        "steps": steps,
        "blockers": blockers,
        "automation_boundary": [
            "The agent may navigate and download the blank template inside the fixed Amazon US seller session.",
            "The agent must stop at login, 2FA, captcha, account-security, billing, policy acknowledgement, or irreversible upload prompts.",
            "The agent must not upload a final file from this runbook; it only downloads and validates the blank template.",
        ],
        "next_automation_step": "map_downloaded_template" if template_ready else "download_live_seller_central_template",
    }


def build_amazon_10001_template_ptd_execution_bridge(
    *,
    download_dir: Path | None = None,
    seller_id: str = "SELLER_ID_TODO",
    sp_api_authorized: bool = False,
    seller_scoped_secret_ready: bool = False,
    product_type_schema_validated: bool = False,
    image_public_urls_ready: bool = False,
    product_identity_ready: bool = False,
) -> dict[str, Any]:
    ptd = build_amazon_10001_product_type_preflight(
        seller_id=seller_id,
        live_ptd_schema_loaded=product_type_schema_validated,
        child_schema_validated=product_type_schema_validated,
        parent_schema_validated=product_type_schema_validated,
        variation_theme_validated=product_type_schema_validated,
        browse_node_validated=product_type_schema_validated,
        image_requirements_validated=product_type_schema_validated,
    )
    ptd_schema_fetch_runbook = build_amazon_10001_ptd_schema_fetch_runbook(
        seller_id=seller_id,
        sp_api_authorized=sp_api_authorized,
        seller_scoped_secret_ready=seller_scoped_secret_ready,
        child_schema_validated=product_type_schema_validated,
        parent_schema_validated=product_type_schema_validated,
        variation_theme_validated=product_type_schema_validated,
        required_attributes_validated=product_type_schema_validated,
    )
    latest_template = build_amazon_10001_latest_downloaded_template_mapping(download_dir)
    template_download_runbook = build_amazon_10001_seller_central_template_download_runbook(
        download_dir=download_dir,
        seller_central_logged_in=False,
    )
    template_ready = latest_template["status"] == "template_rows_ready_needs_business_blockers"
    blockers: list[dict[str, str]] = []
    if not sp_api_authorized:
        blockers.append(
            {
                "gate": "sp_api_authorization",
                "severity": "blocker",
                "reason": "SP-API authorization is required to fetch Product Type Definitions and validate JSON listing payloads.",
                "next_step": "Authorize the Amazon US seller-scoped developer app before PTD validation.",
            }
        )
    if not seller_scoped_secret_ready:
        blockers.append(
            {
                "gate": "seller_scoped_secret",
                "severity": "blocker",
                "reason": "Seller-scoped credentials are not ready for Amazon US.",
                "next_step": "Store LWA/AWS credentials for this Amazon US store only; do not share across stores.",
            }
        )
    if not product_type_schema_validated:
        blockers.append(
            {
                "gate": "product_type_definitions",
                "severity": "blocker",
                "reason": "Amazon US SHIRT Product Type Definitions are not validated for parent/child variation and required attributes.",
                "next_step": "Run searchDefinitionsProductTypes and getDefinitionsProductType for parent and child LISTING schemas.",
            }
        )
    if not template_ready:
        blockers.append(
            {
                "gate": "seller_central_template",
                "severity": "blocker",
                "reason": "No mapped live Amazon US Clothing/T-shirt inventory template is available.",
                "next_step": "Download the live Seller Central Clothing/T-shirt template, then rerun the template mapper.",
            }
        )
    if not image_public_urls_ready:
        blockers.append(
            {
                "gate": "image_public_urls",
                "severity": "blocker",
                "reason": "Amazon upload/feed needs stable HTTPS image URLs, not local file paths.",
                "next_step": "Upload approved 10001 images to the selected HTTPS asset host and regenerate image URL mapping.",
            }
        )
    if not product_identity_ready:
        blockers.append(
            {
                "gate": "product_identity",
                "severity": "blocker",
                "reason": "Legal GS1 GTIN or Amazon GTIN exemption is not ready.",
                "next_step": "Finish Product Identity decision, GTIN exemption evidence, and owner confirmation before external submit.",
            }
        )

    actions = [
        {
            "id": "AMZ-10001-BRIDGE-01",
            "owner": "Store Integration Operator",
            "surface": "SP-API",
            "action": "Fetch Product Type Definitions for Amazon US SHIRT parent and child LISTING schemas.",
            "ready": sp_api_authorized and seller_scoped_secret_ready,
        },
        {
            "id": "AMZ-10001-BRIDGE-02",
            "owner": "Listing Operator",
            "surface": "Seller Central",
            "action": "Download the live Clothing/T-shirt inventory template and map headers.",
            "ready": template_ready,
        },
        {
            "id": "AMZ-10001-BRIDGE-03",
            "owner": "Asset Operator",
            "surface": "Asset host",
            "action": "Publish 10001 images to HTTPS and regenerate image locators.",
            "ready": image_public_urls_ready,
        },
        {
            "id": "AMZ-10001-BRIDGE-04",
            "owner": "Compliance Operator",
            "surface": "Seller Central",
            "action": "Finish Product Identity through legal GS1 GTIN or approved Amazon GTIN exemption.",
            "ready": product_identity_ready,
        },
        {
            "id": "AMZ-10001-BRIDGE-05",
            "owner": "Feed Runner",
            "surface": "Feed/SP-API",
            "action": "Generate final template-specific upload file or JSON_LISTINGS_FEED only after all upstream gates are ready.",
            "ready": not blockers,
        },
    ]
    return {
        "packet_type": "amazon_10001_template_ptd_execution_bridge",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "status": "ready_for_final_upload_build" if not blockers else "blocked_before_final_upload_build",
        "ptd_status": "ptd_schema_validated" if product_type_schema_validated else ptd["status"],
        "ptd_preflight": ptd,
        "ptd_schema_fetch_runbook": ptd_schema_fetch_runbook,
        "ptd_schema_fetch_status": ptd_schema_fetch_runbook["status"],
        "latest_template_status": latest_template["status"],
        "latest_template": latest_template,
        "template_download_runbook": template_download_runbook,
        "actions": actions,
        "blockers": blockers,
        "submit_allowed": False,
        "hard_rule": "Do not create a final Seller Central upload or JSON feed submission until PTD, live template, image URLs, Product Identity, and owner gates are all ready.",
        "next_automation_step": "build_final_upload_file" if not blockers else "repair_template_ptd_bridge_blockers",
    }


def load_amazon_10001_final_gate_blocker_evidence(root: Path) -> dict[str, dict[str, str]]:
    try:
        from .storage import read_records
    except Exception:  # noqa: BLE001 - final gate matrix must stay available in standalone scripts.
        return {}
    evidence_by_gate: dict[str, dict[str, str]] = {}
    try:
        records = read_records(root, "execution_result")
    except Exception:  # noqa: BLE001 - local evidence is optional, not a hard matrix dependency.
        return {}
    for record in sorted(records, key=lambda item: item.created_at, reverse=True):
        fields = record.fields if isinstance(record.fields, dict) else {}
        if str(fields.get("task_package_type") or "") != "amazon_10001_final_gate_blocker":
            continue
        if not bool(fields.get("execution_evidence_complete")):
            continue
        gate = str(fields.get("amazon_10001_final_gate_blocker") or fields.get("final_gate_blocker") or "").strip()
        if not gate or gate in evidence_by_gate:
            continue
        evidence_by_gate[gate] = {
            "gate": gate,
            "status": "evidence_recorded",
            "record_id": record.record_id,
            "created_at": record.created_at,
            "local_api_result_ref": str(fields.get("amazon_10001_local_api_result_ref") or ""),
            "snapshot_ref": str(fields.get("amazon_10001_final_gate_snapshot_ref") or ""),
            "external_submit_blocked_ref": str(fields.get("amazon_10001_external_submit_blocked_ref") or ""),
        }
    return evidence_by_gate


def load_amazon_10001_gtin_evidence_review(root: Path) -> dict[str, str]:
    try:
        from .storage import read_records
    except Exception:  # noqa: BLE001 - final gate matrix must stay available in standalone scripts.
        return {}
    required_refs = [
        "amazon_10001_gtin_product_identity_page_ref",
        "amazon_10001_gtin_product_photos_ref",
        "amazon_10001_gtin_no_barcode_evidence_ref",
        "amazon_10001_gtin_approval_or_gs1_ref",
        "amazon_10001_external_submit_blocked_ref",
    ]
    try:
        records = read_records(root, "execution_result")
    except Exception:  # noqa: BLE001 - local evidence is optional, not a hard matrix dependency.
        return {}
    for record in sorted(records, key=lambda item: item.created_at, reverse=True):
        fields = record.fields if isinstance(record.fields, dict) else {}
        if not bool(fields.get("execution_evidence_complete")):
            continue
        route_key = str(fields.get("route_key") or fields.get("cloud_route_key") or "")
        product_id = str(fields.get("product_id") or "")
        if route_key and route_key != AMAZON_10001_BULK_ROUTE["route_key"]:
            continue
        if product_id and product_id != "10001":
            continue
        source_package = str(fields.get("source_package") or "")
        action_id = str(fields.get("action_id") or "")
        action_type = str(fields.get("action_type") or "")
        refs_present = all(str(fields.get(key) or "").strip() for key in required_refs)
        is_gtin_review = (
            source_package == "amazon_10001_gtin_evidence_review"
            or action_id == "amazon-10001-gtin-evidence-review"
            or (
                action_type == "amazon_product_identity_preflight"
                and str(fields.get("task_package_type") or "") == "listing_preflight"
                and refs_present
            )
        )
        if not is_gtin_review or not refs_present:
            continue
        return {
            "status": "product_identity_ready_for_owner_review",
            "record_id": record.record_id,
            "created_at": record.created_at,
            "product_identity_page_ref": str(fields.get("amazon_10001_gtin_product_identity_page_ref") or ""),
            "product_photos_ref": str(fields.get("amazon_10001_gtin_product_photos_ref") or ""),
            "no_barcode_evidence_ref": str(fields.get("amazon_10001_gtin_no_barcode_evidence_ref") or ""),
            "approval_or_gs1_ref": str(fields.get("amazon_10001_gtin_approval_or_gs1_ref") or ""),
            "external_submit_blocked_ref": str(fields.get("amazon_10001_external_submit_blocked_ref") or ""),
        }
    return {}


def amazon_10001_final_gate_checker(gate: str) -> dict[str, Any]:
    checkers: dict[str, dict[str, Any]] = {
        "seller_central_template_candidate": {
            "checker_id": "template_watcher",
            "local_api": "/api/amazon/10001/template-watcher",
            "output": "amazon_10001_template_upload_candidate.csv",
            "success_statuses": ["candidate_structure_ready_upload_still_blocked"],
            "next_plugin_action": "Scan Amazon Template Download",
            "evidence_field": "seller_central_template_candidate_ref",
        },
        "image_https_mapping": {
            "checker_id": "image_public_url_check",
            "local_api": "/api/amazon/10001/image-public-url-check",
            "output": "amazon_10001_image_public_url_check.json",
            "success_statuses": ["image_public_url_mapping_ready_for_owner_review"],
            "next_plugin_action": "Check Amazon Image URLs",
            "evidence_field": "amazon_10001_image_https_mapping_ref",
        },
        "image_public_fetch": {
            "checker_id": "image_public_fetch_check",
            "local_api": "/api/amazon/10001/image-public-fetch-check",
            "output": "amazon_10001_image_public_fetch_check.json",
            "success_statuses": ["image_public_fetch_ready_for_owner_review"],
            "next_plugin_action": "Verify Uploaded Images",
            "evidence_field": "amazon_10001_image_public_fetch_ref",
        },
        "product_identity": {
            "checker_id": "product_identity_gtin_exemption_check",
            "local_api": "/api/amazon/10001/product-identity-check",
            "output": "amazon_10001_product_identity_check.json",
            "success_statuses": ["product_identity_ready_for_owner_review"],
            "next_plugin_action": "Check Product Identity / GTIN Exemption",
            "evidence_field": "amazon_10001_product_identity_ref",
        },
        "product_type_definitions": {
            "checker_id": "ptd_schema_fetch_runbook",
            "local_api": "/api/amazon/10001/final-upload-gates",
            "output": "amazon_10001_final_upload_gate_matrix.json",
            "success_statuses": ["ptd_schema_ready_for_feed_validation"],
            "next_plugin_action": "Check Final Upload Gates",
            "evidence_field": "amazon_10001_ptd_schema_ref",
        },
        "inventory_listing_visibility": {
            "checker_id": "store_execution_readiness",
            "local_api": "/api/amazon/10001/store-execution-readiness",
            "output": "amazon_10001_store_execution_readiness.json",
            "success_statuses": ["listing_visible"],
            "next_plugin_action": "Check Amazon Store Readiness",
            "evidence_field": "amazon_10001_inventory_visibility_ref",
        },
        "owner_confirmation": {
            "checker_id": "owner_final_gate_review",
            "local_api": "/api/amazon/10001/final-upload-gates",
            "output": "amazon_10001_final_upload_gate_matrix.json",
            "success_statuses": ["confirmed"],
            "next_plugin_action": "Check Final Upload Gates",
            "evidence_field": "amazon_10001_owner_final_review_ref",
        },
    }
    return dict(checkers.get(gate, {
        "checker_id": "final_upload_gate_matrix",
        "local_api": "/api/amazon/10001/final-upload-gates",
        "output": "amazon_10001_final_upload_gate_matrix.json",
        "success_statuses": ["ready"],
        "next_plugin_action": "Check Final Upload Gates",
        "evidence_field": "amazon_10001_final_gate_blocker_ref",
    }))


def build_amazon_10001_final_upload_gate_matrix(
    root: Path | None = None,
    *,
    download_dir: Path | None = None,
    asset_base_url: str | None = None,
    asset_public_urls_confirmed: bool = False,
    image_public_fetch_confirmed: bool = False,
    sp_api_authorized: bool = False,
    seller_scoped_secret_ready: bool = False,
    product_type_schema_validated: bool = False,
    has_legal_gs1_gtin: bool = False,
    gtin_exemption_approved: bool = False,
    brand_decision: str = "",
    packaging_evidence_ready: bool = False,
    inventory_tshirt_listing_found: bool = False,
    owner_confirmed_external_submit: bool = False,
) -> dict[str, Any]:
    base_root = root or Path.cwd()
    blocker_evidence = load_amazon_10001_final_gate_blocker_evidence(base_root)
    gtin_evidence_review = load_amazon_10001_gtin_evidence_review(base_root)
    if gtin_evidence_review:
        gtin_exemption_approved = True
        packaging_evidence_ready = True
        brand_decision = brand_decision or "generic"
    template_watcher = build_amazon_10001_downloaded_template_watcher_result(base_root, download_dir)
    candidate_qa = template_watcher.get("candidate_qa") if isinstance(template_watcher.get("candidate_qa"), dict) else {}
    template_ready = str(candidate_qa.get("status") or "") == "candidate_structure_ready_upload_still_blocked"
    asset_plan = build_amazon_10001_asset_hosting_plan(asset_base_url=asset_base_url, root=base_root)
    latest_image_url_check = load_latest_amazon_10001_image_public_url_check(base_root)
    latest_image_fetch_check = load_latest_amazon_10001_image_public_fetch_check(base_root)
    latest_url_check_from_fetch = (
        latest_image_fetch_check.get("url_check")
        if isinstance(latest_image_fetch_check, dict) and isinstance(latest_image_fetch_check.get("url_check"), dict)
        else {}
    )
    latest_url_check = latest_image_url_check if isinstance(latest_image_url_check, dict) else latest_url_check_from_fetch
    latest_base_url_check = latest_url_check.get("base_url_check") if isinstance(latest_url_check.get("base_url_check"), dict) else {}
    ready_image_upload_manifest = build_amazon_10001_ready_image_upload_manifest_summary(base_root)
    local_web_upload_note = (
        "Local Seller Central web-upload manifest is ready; use it for manual image upload evidence, but bulk/API image gates still require public HTTPS fetch checks."
        if ready_image_upload_manifest.get("web_upload_ready")
        else "Local Seller Central web-upload manifest is not ready; regenerate ready images or fix missing files before manual image upload."
    )
    image_mapping_ready = bool(
        asset_public_urls_confirmed
        or asset_plan["base_url_check"]["valid_for_amazon"]
        or latest_base_url_check.get("valid_for_amazon")
        or (
            isinstance(latest_image_url_check, dict)
            and latest_image_url_check.get("status") == "image_public_url_mapping_ready_for_owner_review"
        )
    )
    image_fetch_ready = bool(
        image_public_fetch_confirmed
        or (
            isinstance(latest_image_fetch_check, dict)
            and latest_image_fetch_check.get("status") == "image_public_fetch_ready_for_owner_review"
            and int(latest_image_fetch_check.get("checked_count") or 0) >= 13
            and int(latest_image_fetch_check.get("failed_count") or 0) == 0
        )
    )
    identity_decision = build_amazon_10001_product_identity_decision(
        has_legal_gs1_gtin=has_legal_gs1_gtin,
        gtin_exemption_approved=gtin_exemption_approved,
        brand_decision=brand_decision,
        packaging_evidence_ready=packaging_evidence_ready,
        owner_confirmed_external_submit=owner_confirmed_external_submit,
    )
    identity_blockers = [
        item
        for item in identity_decision["blockers"]
        if str(item.get("gate") or "") != "owner_confirmation"
    ]
    identity_ready = not identity_blockers
    ptd_runbook = build_amazon_10001_ptd_schema_fetch_runbook(
        root=base_root,
        sp_api_authorized=sp_api_authorized,
        seller_scoped_secret_ready=seller_scoped_secret_ready,
        child_schema_validated=product_type_schema_validated,
        parent_schema_validated=product_type_schema_validated,
        variation_theme_validated=product_type_schema_validated,
        required_attributes_validated=product_type_schema_validated,
    )
    ptd_ready = ptd_runbook["status"] == "ptd_schema_ready_for_feed_validation"
    latest_store_readiness = load_latest_amazon_10001_store_execution_readiness(base_root)
    latest_inventory_visible = bool(
        isinstance(latest_store_readiness, dict)
        and latest_store_readiness.get("inventory_tshirt_listing_found")
    )
    inventory_listing_ready = bool(inventory_tshirt_listing_found or latest_inventory_visible)
    gate_sources: dict[str, dict[str, str]] = {
        "seller_central_template_candidate": {
            "status": str(candidate_qa.get("status") or "waiting_for_candidate"),
            "ref": str(template_watcher.get("upload_candidate_path") or template_watcher.get("latest_candidate") or ""),
        },
        "image_https_mapping": {
            "status": str(
                (latest_image_url_check or {}).get("status")
                or latest_base_url_check.get("status")
                or asset_plan["status"]
            ),
            "ref": str((latest_image_url_check or {}).get("report_path") or ""),
        },
        "image_public_fetch": {
            "status": str((latest_image_fetch_check or {}).get("status") or "missing_public_fetch_check"),
            "ref": str((latest_image_fetch_check or {}).get("report_path") or ""),
        },
        "product_identity": {
            "status": str(gtin_evidence_review.get("status") or identity_decision["status"]),
            "ref": str(gtin_evidence_review.get("record_id") or identity_decision.get("selected_path") or ""),
        },
        "product_type_definitions": {
            "status": str(ptd_runbook["status"]),
            "ref": str(ptd_runbook.get("schema_dir") or ""),
        },
        "inventory_listing_visibility": {
            "status": str((latest_store_readiness or {}).get("status") or ("listing_visible" if inventory_listing_ready else "listing_not_visible")),
            "ref": str((latest_store_readiness or {}).get("report_path") or ""),
        },
        "owner_confirmation": {
            "status": "confirmed" if owner_confirmed_external_submit else "missing_owner_confirmation",
            "ref": "",
        },
    }
    gate_defs = [
        {
            "gate": "seller_central_template_candidate",
            "ready": template_ready,
            "status": str(candidate_qa.get("status") or "waiting_for_candidate"),
            "reason": "Live Amazon US Clothing/T-shirt template must be downloaded, mapped, and structurally checked.",
            "next_step": "Download the Seller Central template and run Scan Amazon Template Download.",
        },
        {
            "gate": "image_https_mapping",
            "ready": image_mapping_ready,
            "status": "ready" if image_mapping_ready else asset_plan["status"],
            "reason": "Amazon needs stable public HTTPS image locators for every child and bundle asset.",
            "next_step": "Upload the 10001 images to the selected HTTPS asset host and confirm the URLs are publicly fetchable. If using Seller Central web UI first, follow the local ready-image manifest and then record upload evidence.",
            "local_web_upload_note": local_web_upload_note,
            "local_web_upload_manifest": ready_image_upload_manifest,
        },
        {
            "gate": "image_public_fetch",
            "ready": image_fetch_ready,
            "status": "ready" if image_fetch_ready else str((latest_image_fetch_check or {}).get("status") or "missing_public_fetch_check"),
            "reason": "The latest uploaded image verification must prove all 13 public HTTPS image URLs return image content.",
            "next_step": "After uploading images to the asset host, click Verify Uploaded Images in the BitBrowser plugin. For Seller Central web upload, use the local manifest first, then capture image-slot evidence because local upload does not satisfy public fetch.",
            "local_web_upload_note": local_web_upload_note,
            "local_web_upload_manifest": ready_image_upload_manifest,
        },
        {
            "gate": "product_identity",
            "ready": identity_ready,
            "status": identity_decision["status"],
            "reason": "Listing must use legal GS1 GTINs or an approved Amazon GTIN exemption; fake UPC/EAN is blocked.",
            "next_step": "Finish GS1 assignment or Amazon US Clothing GTIN exemption evidence and approval.",
        },
        {
            "gate": "product_type_definitions",
            "ready": ptd_ready,
            "status": ptd_runbook["status"],
            "reason": "Amazon US SHIRT parent/child required attributes and variation enums must be validated from PTD.",
            "next_step": "Fetch and validate Product Type Definitions for the seller-scoped Amazon US route.",
        },
        {
            "gate": "inventory_listing_visibility",
            "ready": inventory_listing_ready,
            "status": "listing_visible" if inventory_listing_ready else "listing_not_visible",
            "reason": "Store operations, inventory quantity, ads, and promotions should not run until 10001 appears in Manage All Inventory.",
            "next_step": "Use the BitBrowser extension to capture Manage All Inventory after the draft/listing exists.",
        },
        {
            "gate": "owner_confirmation",
            "ready": owner_confirmed_external_submit,
            "status": "confirmed" if owner_confirmed_external_submit else "missing_owner_confirmation",
            "reason": "External upload, publish, price, inventory, promotion, and ads actions need explicit owner confirmation.",
            "next_step": "Route the final upload candidate through the approval queue before touching Seller Central submit controls.",
        },
    ]
    for item in gate_defs:
        gate = str(item.get("gate") or "")
        checker = amazon_10001_final_gate_checker(gate)
        evidence = blocker_evidence.get(gate) if isinstance(blocker_evidence.get(gate), dict) else {}
        item["checker"] = checker
        item["checker_id"] = str(checker.get("checker_id") or "")
        item["local_api"] = str(checker.get("local_api") or "")
        item["output"] = str(checker.get("output") or "")
        item["next_plugin_action"] = str(checker.get("next_plugin_action") or "")
        item["success_statuses"] = list(checker.get("success_statuses") or [])
        source = gate_sources.get(gate, {})
        item["checker_result_status"] = str(source.get("status") or item.get("status") or "")
        item["checker_result_ref"] = str(source.get("ref") or "")
        item["checker_result_passed"] = bool(item["ready"])
        item["blocker_evidence_status"] = "evidence_recorded_needs_gate_recheck" if evidence else "missing"
        item["blocker_evidence_ref"] = str(evidence.get("record_id") or "") if evidence else ""
        item["blocker_evidence_recorded_at"] = str(evidence.get("created_at") or "") if evidence else ""
        if evidence and not item["ready"]:
            item["next_step"] = (
                f"Evidence for {gate} was recorded by the plugin; rerun {item['next_plugin_action'] or item['local_api']} and only clear the gate when the checker passes."
            )
    blockers = [
        {
            "gate": item["gate"],
            "status": item["status"],
            "reason": item["reason"],
            "next_step": item["next_step"],
            "blocker_evidence_status": item["blocker_evidence_status"],
            "blocker_evidence_ref": item["blocker_evidence_ref"],
            "checker_id": item["checker_id"],
            "checker_result_status": item["checker_result_status"],
            "checker_result_ref": item["checker_result_ref"],
            "checker_result_passed": item["checker_result_passed"],
            "local_api": item["local_api"],
            "output": item["output"],
            "next_plugin_action": item["next_plugin_action"],
            "success_statuses": item["success_statuses"],
            "local_web_upload_note": str(item.get("local_web_upload_note") or ""),
            "local_web_upload_manifest": item.get("local_web_upload_manifest") if isinstance(item.get("local_web_upload_manifest"), dict) else {},
        }
        for item in gate_defs
        if not item["ready"]
    ]
    all_gates_ready = not blockers
    return {
        "packet_type": "amazon_10001_final_upload_gate_matrix",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "status": "ready_for_owner_review_before_external_upload" if all_gates_ready else "blocked_before_external_upload",
        "store_usable_for_external_upload": False,
        "external_submit_allowed": False,
        "gates": gate_defs,
        "blockers": blockers,
        "handled_final_gate_blockers": list(blocker_evidence.values()),
        "template_watcher": template_watcher,
        "asset_hosting_plan": asset_plan,
        "ready_image_upload_manifest": ready_image_upload_manifest,
        "image_public_url_check": latest_image_url_check,
        "image_public_fetch_check": latest_image_fetch_check,
        "product_identity_decision": identity_decision,
        "gtin_evidence_review": gtin_evidence_review,
        "ptd_schema_fetch_runbook": ptd_runbook,
        "store_execution_readiness": latest_store_readiness,
        "blocked_external_actions": [
            "seller_central_upload_submit",
            "listing_publish",
            "feed_submit",
            "price_update",
            "inventory_quantity_update",
            "promotion_submit",
            "ads_campaign_launch",
        ],
        "safe_next_step": (
            "All structural gates are ready; send the final candidate to owner review before any external Seller Central upload."
            if all_gates_ready
            else blockers[0]["next_step"]
        ),
        "hard_rule": "This matrix can make a candidate ready for owner review, but it never authorizes external submit by itself.",
    }


def build_amazon_10001_execution_preflight(
    *,
    seller_id: str = "SELLER_ID_TODO",
    sp_api_authorized: bool = False,
    seller_scoped_secret_ready: bool = False,
    product_type_schema_validated: bool = False,
    has_legal_gs1_gtin: bool = False,
    gtin_exemption_approved: bool = False,
    brand_decision: str = "",
    packaging_evidence_ready: bool = False,
    owner_confirmed_external_submit: bool = False,
) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    if not sp_api_authorized:
        blockers.append(
            {
                "gate": "sp_api_authorization",
                "severity": "blocker",
                "reason": "Amazon SP-API developer app and seller authorization are not confirmed for this store route.",
                "next_step": "Connect Amazon US seller authorization before Product Type Definitions, Listings Items, or Feeds API calls.",
            }
        )
    if not seller_scoped_secret_ready:
        blockers.append(
            {
                "gate": "seller_scoped_secret",
                "severity": "blocker",
                "reason": "LWA refresh token and AWS signing credentials are not stored as an isolated Amazon US self-operated store secret.",
                "next_step": "Store credentials per seller/store route; do not reuse credentials across stores.",
            }
        )
    if not product_type_schema_validated:
        blockers.append(
            {
                "gate": "product_type_schema",
                "severity": "blocker",
                "reason": "10001 feed attributes have not been validated against current Amazon Product Type Definitions.",
                "next_step": "Call Product Type Definitions for Amazon US and validate SHIRT/T-shirt attributes before submit.",
            }
        )
    if not (has_legal_gs1_gtin or gtin_exemption_approved):
        blockers.append(
            {
                "gate": "product_identity",
                "severity": "blocker",
                "reason": "No legal GS1 UPC/GTIN or approved Amazon GTIN exemption is available.",
                "next_step": "Apply for GTIN exemption or map legal GS1 codes; do not fabricate UPC/EAN/GTIN.",
            }
        )
    if not owner_confirmed_external_submit:
        blockers.append(
            {
                "gate": "owner_confirmation",
                "severity": "confirmation_required",
                "reason": "Real external feed submission has not been confirmed by the responsible owner.",
                "next_step": "Keep this as a local draft until the owner confirms a real Amazon submission.",
            }
        )

    submit_allowed = not blockers
    return {
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "seller_id": seller_id,
        "marketplace_id": AMAZON_US_MARKETPLACE_ID,
        "sku": "TL10001-BLK-S",
        "status": "ready_for_feed_submission" if submit_allowed else "blocked_before_external_submit",
        "can_create_local_draft": True,
        "can_run_schema_validation": sp_api_authorized and seller_scoped_secret_ready,
        "can_run_validation_preview": sp_api_authorized
        and seller_scoped_secret_ready
        and product_type_schema_validated
        and (has_legal_gs1_gtin or gtin_exemption_approved),
        "can_submit_feed": submit_allowed,
        "blockers": blockers,
        "required_gates": list(AMAZON_10001_SUBMISSION_GATES),
        "safe_now": [
            "export_product_master_csv",
            "export_json_listings_feed_draft",
            "export_video_learning_notes",
            "classify_processing_report_samples",
            "prepare_owner_confirmation_packet",
        ],
    }


def build_amazon_10001_submission_package(
    *,
    seller_id: str = "SELLER_ID_TODO",
    sp_api_authorized: bool = False,
    seller_scoped_secret_ready: bool = False,
    product_type_schema_validated: bool = False,
    has_legal_gs1_gtin: bool = False,
    gtin_exemption_approved: bool = False,
    brand_decision: str = "",
    packaging_evidence_ready: bool = False,
    owner_confirmed_external_submit: bool = False,
) -> dict[str, Any]:
    preflight = build_amazon_10001_execution_preflight(
        seller_id=seller_id,
        sp_api_authorized=sp_api_authorized,
        seller_scoped_secret_ready=seller_scoped_secret_ready,
        product_type_schema_validated=product_type_schema_validated,
        has_legal_gs1_gtin=has_legal_gs1_gtin,
        gtin_exemption_approved=gtin_exemption_approved,
        owner_confirmed_external_submit=owner_confirmed_external_submit,
    )
    product_identity_decision = build_amazon_10001_product_identity_decision(
        has_legal_gs1_gtin=has_legal_gs1_gtin,
        gtin_exemption_approved=gtin_exemption_approved,
        brand_decision=brand_decision,
        packaging_evidence_ready=packaging_evidence_ready,
        owner_confirmed_external_submit=owner_confirmed_external_submit,
    )
    gtin_exemption_evidence_pack = build_amazon_10001_gtin_exemption_evidence_pack()
    gtin_exemption_runbook = build_amazon_10001_gtin_exemption_store_runbook(
        brand_decision=brand_decision or "generic",
        packaging_evidence_ready=packaging_evidence_ready if packaging_evidence_ready else None,
        seller_central_logged_in=False,
    )
    feed = build_amazon_10001_json_listings_feed(seller_id=seller_id)
    feed["tk_preflight"]["submit_allowed"] = bool(preflight["can_submit_feed"])
    feed["tk_preflight"]["blockers"] = [item["reason"] for item in preflight["blockers"]]
    secret_readiness = build_amazon_sp_api_secret_readiness()
    store_authorization_runbook = build_amazon_10001_store_authorization_runbook(
        seller_id=seller_id,
        sp_api_app_ready=sp_api_authorized,
        sp_api_roles_ready=sp_api_authorized,
        owner_confirmed_authorization=owner_confirmed_external_submit,
    )
    gtin_packet = build_amazon_10001_gtin_exemption_packet()
    product_type_preflight = build_amazon_10001_product_type_preflight(seller_id=seller_id)
    ptd_schema_fetch_runbook = build_amazon_10001_ptd_schema_fetch_runbook(
        seller_id=seller_id,
        sp_api_authorized=sp_api_authorized,
        seller_scoped_secret_ready=seller_scoped_secret_ready,
        child_schema_validated=product_type_schema_validated,
        parent_schema_validated=product_type_schema_validated,
        variation_theme_validated=product_type_schema_validated,
        required_attributes_validated=product_type_schema_validated,
    )
    variation_matrix = build_amazon_10001_variation_matrix()
    asset_manifest = build_amazon_10001_asset_manifest()
    image_url_mapping = build_amazon_10001_image_url_mapping()
    asset_hosting_plan = build_amazon_10001_asset_hosting_plan()
    asset_provider_readiness = build_amazon_10001_asset_provider_readiness()
    asset_upload_command_plan = build_amazon_10001_asset_upload_command_plan()
    parent_child_feed_draft = build_amazon_10001_parent_child_json_feed_draft(seller_id=seller_id)
    seller_central_alignment = build_amazon_10001_seller_central_alignment()
    inventory_template_mapping = build_amazon_10001_inventory_template_mapping()
    latest_downloaded_template_mapping = build_amazon_10001_latest_downloaded_template_mapping()
    downloaded_template_watcher_result = build_amazon_10001_downloaded_template_watcher_result(Path.cwd())
    template_download_runbook = build_amazon_10001_seller_central_template_download_runbook()
    template_ptd_execution_bridge = build_amazon_10001_template_ptd_execution_bridge(
        seller_id=seller_id,
        sp_api_authorized=sp_api_authorized,
        seller_scoped_secret_ready=seller_scoped_secret_ready,
        product_type_schema_validated=product_type_schema_validated,
        image_public_urls_ready=False,
        product_identity_ready=has_legal_gs1_gtin or gtin_exemption_approved,
    )
    feed["tk_preflight"]["product_type_preflight_status"] = product_type_preflight["status"]
    feed["tk_preflight"]["variation_matrix_status"] = variation_matrix["status"]
    feed["tk_preflight"]["asset_manifest_status"] = asset_manifest["status"]
    feed["tk_preflight"]["parent_child_feed_message_count"] = parent_child_feed_draft["tk_preflight"]["message_count"]
    feed["tk_preflight"]["blockers"].extend(
        str(item["reason"]) for item in product_type_preflight["blockers"][:6]
    )
    feed["tk_preflight"]["blockers"].extend(
        str(item["reason"]) for item in variation_matrix["blockers"][:4]
    )
    return {
        "package_type": "amazon_json_listings_feed_preflight_package",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "preflight": preflight,
        "secret_readiness": secret_readiness,
        "store_authorization_runbook": store_authorization_runbook,
        "product_identity_decision": product_identity_decision,
        "product_identity_evidence_tasks": build_amazon_10001_product_identity_evidence_tasks(product_identity_decision),
        "gtin_exemption_evidence_pack": gtin_exemption_evidence_pack,
        "gtin_exemption_store_runbook": gtin_exemption_runbook,
        "gtin_exemption_packet": gtin_packet,
        "product_type_preflight": product_type_preflight,
        "ptd_schema_fetch_runbook": ptd_schema_fetch_runbook,
        "variation_matrix": variation_matrix,
        "asset_manifest": asset_manifest,
        "image_url_mapping": image_url_mapping,
        "asset_hosting_plan": asset_hosting_plan,
        "asset_provider_readiness": asset_provider_readiness,
        "asset_upload_command_plan": asset_upload_command_plan,
        "parent_child_feed_draft": parent_child_feed_draft,
        "seller_central_alignment": seller_central_alignment,
        "inventory_template_mapping": inventory_template_mapping,
        "latest_downloaded_template_mapping": latest_downloaded_template_mapping,
        "template_ptd_execution_bridge": template_ptd_execution_bridge,
        "feed_type": "JSON_LISTINGS_FEED",
        "content_type": "application/json; charset=UTF-8",
        "feed": feed,
        "next_automation_step": "submit_via_feeds_api" if preflight["can_submit_feed"] else "repair_preflight_blockers",
    }


def build_amazon_10001_repair_queue(preflight: dict[str, Any]) -> list[dict[str, str]]:
    queue: list[dict[str, str]] = []
    for index, blocker in enumerate(preflight.get("blockers") or [], start=1):
        if not isinstance(blocker, dict):
            continue
        gate = str(blocker.get("gate") or "unknown")
        queue.append(
            {
                "id": f"AMZ-10001-REPAIR-{index:02d}",
                "sku": "TL10001-BLK-S",
                "gate": gate,
                "severity": str(blocker.get("severity") or "blocker"),
                "reason": str(blocker.get("reason") or ""),
                "next_step": str(blocker.get("next_step") or ""),
                "owner": next(
                    (item["owner"] for item in AMAZON_10001_SUBMISSION_GATES if item["gate"] == gate),
                    "AI Listing Operator",
                ),
            }
        )
    return queue


def build_amazon_10001_json_listings_feed(
    *,
    seller_id: str = "SELLER_ID_TODO",
    marketplace_id: str = AMAZON_US_MARKETPLACE_ID,
) -> dict[str, Any]:
    """Build an Amazon listings JSON feed draft.

    This is intentionally a draft/preflight artifact. The product type and
    attributes must be validated against Product Type Definitions before a real
    feed submission, and Product Identity remains blocked until GTIN exemption
    or a legal GS1 code is ready.
    """

    return {
        "header": {
            "sellerId": seller_id,
            "version": "2.0",
            "issueLocale": "en_US",
        },
        "messages": [
            {
                "messageId": 1,
                "sku": "TL10001-BLK-S",
                "operationType": "UPDATE",
                "productType": "SHIRT",
                "requirements": "LISTING",
                "attributes": {
                    "item_name": [
                        {
                            "value": "TeeLab Men's Short Sleeve T-Shirt, Black, S, Oversized Fit, Casual, Crewneck, 100% Cotton",
                            "language_tag": "en_US",
                            "marketplace_id": marketplace_id,
                        }
                    ],
                    "brand": [{"value": "TeeLab", "marketplace_id": marketplace_id}],
                    "condition_type": [{"value": "new_new", "marketplace_id": marketplace_id}],
                    "color": [{"value": "Black", "marketplace_id": marketplace_id}],
                    "size": [{"value": "S", "marketplace_id": marketplace_id}],
                    "material": [{"value": "Cotton", "marketplace_id": marketplace_id}],
                    "fabric_type": [{"value": "100% Cotton", "marketplace_id": marketplace_id}],
                    "fit_type": [{"value": "Oversized Fit", "marketplace_id": marketplace_id}],
                    "bullet_point": [
                        {
                            "value": "230g vintage washed cotton fabric with a soft heavyweight feel.",
                            "language_tag": "en_US",
                            "marketplace_id": marketplace_id,
                        },
                        {
                            "value": "Casual oversized crewneck cut for everyday streetwear styling.",
                            "language_tag": "en_US",
                            "marketplace_id": marketplace_id,
                        },
                        {
                            "value": "Single black size S test SKU prepared for FBM self-warehouse fulfillment.",
                            "language_tag": "en_US",
                            "marketplace_id": marketplace_id,
                        },
                    ],
                    "product_description": [
                        {
                            "value": "TeeLab 10001 is a 230g vintage washed 100% cotton short sleeve T-shirt prepared for the Amazon US marketplace seller route. This first draft uses FBM self-warehouse fulfillment and is blocked from publish until Product Identity is resolved with a legal GS1 code or approved Amazon GTIN exemption.",
                            "language_tag": "en_US",
                            "marketplace_id": marketplace_id,
                        }
                    ],
                    "purchasable_offer": [
                        {
                            "currency": "USD",
                            "marketplace_id": marketplace_id,
                            "our_price": [{"schedule": [{"value_with_tax": 20.00}]}],
                        }
                    ],
                    "fulfillment_availability": [
                        {"fulfillment_channel_code": "DEFAULT", "quantity": 10}
                    ],
                },
            }
        ],
        "tk_preflight": {
            "submit_allowed": False,
            "route": dict(AMAZON_10001_BULK_ROUTE),
            "blockers": [
                "Product Identity is 3 of 5 in the live Seller Central draft.",
                "Do not fabricate UPC/EAN/GTIN.",
                "Validate productType and all attributes with Product Type Definitions before submission.",
                "Use legal GS1 code or approved Amazon GTIN exemption before publish.",
            ],
            "selected_tools": list(AMAZON_FASTTRACK_TOOLS),
            "video_learning_sources": list(AMAZON_VIDEO_LEARNING_SOURCES),
        },
    }


def export_amazon_10001_json_feed_draft(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_json_listings_feed_draft_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_json_listings_feed(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_submission_package(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_submission_preflight_package_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    package = build_amazon_10001_submission_package()
    package["repair_queue"] = build_amazon_10001_repair_queue(package["preflight"])
    package["repair_queue"].extend(
        build_amazon_10001_product_type_repair_queue(package["product_type_preflight"])
    )
    package["repair_queue"].extend(
        build_amazon_10001_variation_repair_queue(package["variation_matrix"])
    )
    path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_amazon_10001_variation_repair_queue(variation_matrix: dict[str, Any]) -> list[dict[str, str]]:
    queue: list[dict[str, str]] = []
    for index, blocker in enumerate(variation_matrix.get("blockers") or [], start=1):
        if not isinstance(blocker, dict):
            continue
        queue.append(
            {
                "id": f"AMZ-10001-VAR-REPAIR-{index:02d}",
                "sku": "68-DDNH-IM56",
                "gate": str(blocker.get("gate") or "variation_matrix"),
                "severity": str(blocker.get("severity") or "blocker"),
                "reason": str(blocker.get("reason") or ""),
                "next_step": str(blocker.get("next_step") or ""),
                "owner": "AI Listing Operator",
            }
        )
    return queue


def export_amazon_10001_variation_matrix(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_variation_matrix_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_variation_matrix(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_variation_matrix_csv(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_variation_matrix_{actual_date}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    matrix = build_amazon_10001_variation_matrix()
    fields = [
        "sku",
        "parent_sku",
        "listing_family",
        "relationship_type",
        "variation_theme",
        "size",
        "color",
        "price_usd",
        "fulfillment",
        "quantity",
        "asset_status",
        "product_identity_status",
        "product_type_status",
        "image_public_url_status",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for parent in matrix["parents"]:
            row = {field: "" for field in fields}
            row.update(
                {
                    "sku": parent["sku"],
                    "listing_family": parent["listing_family"],
                    "relationship_type": parent["relationship_type"],
                    "variation_theme": parent["variation_theme"],
                    "product_identity_status": "blocked_until_gtin_or_exemption",
                    "product_type_status": "needs_live_product_type_definitions",
                    "image_public_url_status": "missing_public_url",
                }
            )
            writer.writerow(row)
        for child in [*matrix["single_children"], *matrix["bundle_children"]]:
            writer.writerow({field: child.get(field, "") for field in fields})
    return path


def export_amazon_10001_asset_manifest(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_asset_manifest_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_asset_manifest(root), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_image_url_mapping(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_image_url_mapping_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_image_url_mapping(root=root), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_image_public_url_check(
    root: Path,
    run_date: str | None = None,
    *,
    asset_base_url: str | None = None,
) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_image_public_url_check_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            build_amazon_10001_image_public_url_check(asset_base_url=asset_base_url, root=root),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_image_public_fetch_check(
    root: Path,
    run_date: str | None = None,
    *,
    asset_base_url: str | None = None,
) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_image_public_fetch_check_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            build_amazon_10001_image_public_fetch_check(asset_base_url=asset_base_url, root=root),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_asset_hosting_plan(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_asset_hosting_plan_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_asset_hosting_plan(root=root), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_asset_upload_tasks_csv(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_asset_upload_tasks_{actual_date}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    plan = build_amazon_10001_asset_hosting_plan(root=root)
    fields = ["asset_slug", "role", "local_path", "exists", "target_relative_path", "target_url"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for task in plan["upload_tasks"]:
            writer.writerow({field: task.get(field, "") for field in fields})
    return path


def export_amazon_10001_asset_provider_readiness(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_asset_provider_readiness_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_asset_provider_readiness(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_asset_upload_command_plan(
    root: Path,
    run_date: str | None = None,
    *,
    provider: str = "cloudflare_r2_s3_compatible",
    asset_base_url: str | None = None,
) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_asset_upload_command_plan_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            build_amazon_10001_asset_upload_command_plan(
                provider=provider,
                asset_base_url=asset_base_url,
                root=root,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_parent_child_json_feed_draft(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_parent_child_json_feed_draft_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_parent_child_json_feed_draft(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_bulk_upload_seed_csv(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_bulk_upload_seed_{actual_date}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    matrix = build_amazon_10001_variation_matrix()
    url_mapping = build_amazon_10001_image_url_mapping(root=root)
    color_url_by_slug = {item["asset_slug"]: item for item in url_mapping["color_urls"]}
    fields = [
        "sku",
        "parent_sku",
        "relationship_type",
        "listing_family",
        "product_type",
        "variation_theme",
        "item_name",
        "brand",
        "color",
        "size",
        "price_usd",
        "quantity",
        "fulfillment_channel",
        "main_image_locator",
        "other_image_locator_1",
        "asset_status",
        "image_url_status",
        "product_identity_status",
        "product_type_status",
        "submit_allowed",
    ]
    rows: list[dict[str, Any]] = []
    for parent in matrix["parents"]:
        rows.append(
            {
                "sku": parent["sku"],
                "parent_sku": "",
                "relationship_type": parent["relationship_type"],
                "listing_family": parent["listing_family"],
                "product_type": "SHIRT",
                "variation_theme": parent["variation_theme"],
                "item_name": "TeeLab Men's Vintage Washed Cotton T-Shirt" if parent["listing_family"] == "single_tshirt" else "TeeLab Men's Vintage Washed Cotton T-Shirt 4 Pack",
                "brand": "TeeLab",
                "color": "",
                "size": "",
                "price_usd": "",
                "quantity": "",
                "fulfillment_channel": "DEFAULT",
                "main_image_locator": "",
                "other_image_locator_1": "",
                "asset_status": "",
                "image_url_status": "not_required_parent",
                "product_identity_status": "blocked_until_gtin_or_exemption",
                "product_type_status": "needs_live_product_type_definitions",
                "submit_allowed": "false",
            }
        )
    for child in matrix["single_children"]:
        urls = color_url_by_slug[child["asset_slug"]]
        rows.append(
            {
                "sku": child["sku"],
                "parent_sku": child["parent_sku"],
                "relationship_type": child["relationship_type"],
                "listing_family": child["listing_family"],
                "product_type": "SHIRT",
                "variation_theme": child["variation_theme"],
                "item_name": f"TeeLab Men's Vintage Washed Cotton T-Shirt, {child['color']}, {child['size']}",
                "brand": "TeeLab",
                "color": child["color"],
                "size": child["size"],
                "price_usd": f"{child['price_usd']:.2f}",
                "quantity": child["quantity"],
                "fulfillment_channel": "DEFAULT",
                "main_image_locator": urls["main_image_locator"],
                "other_image_locator_1": urls["other_image_locator_1"],
                "asset_status": child["asset_status"],
                "image_url_status": urls["url_status"],
                "product_identity_status": child["product_identity_status"],
                "product_type_status": child["product_type_status"],
                "submit_allowed": "false",
            }
        )
    bundle_url = url_mapping["bundle_url"]
    for child in matrix["bundle_children"]:
        rows.append(
            {
                "sku": child["sku"],
                "parent_sku": child["parent_sku"],
                "relationship_type": child["relationship_type"],
                "listing_family": child["listing_family"],
                "product_type": "SHIRT",
                "variation_theme": child["variation_theme"],
                "item_name": f"TeeLab Men's Vintage Washed Cotton T-Shirt 4 Pack, {child['size']}",
                "brand": "TeeLab",
                "color": child["color"],
                "size": child["size"],
                "price_usd": f"{child['price_usd']:.2f}",
                "quantity": child["quantity"],
                "fulfillment_channel": "DEFAULT",
                "main_image_locator": bundle_url["main_image_locator"],
                "other_image_locator_1": "",
                "asset_status": child["asset_status"],
                "image_url_status": bundle_url["url_status"],
                "product_identity_status": child["product_identity_status"],
                "product_type_status": child["product_type_status"],
                "submit_allowed": "false",
            }
        )
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def export_amazon_10001_seller_central_alignment(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_seller_central_alignment_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_seller_central_alignment(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_inventory_template_mapping(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_inventory_template_mapping_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_inventory_template_mapping(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_inventory_template_rows_preview(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_inventory_template_rows_preview_{actual_date}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    preview_columns = [
        "item_sku",
        "parent_sku",
        "parent_child",
        "relationship_type",
        "variation_theme",
        "item_name",
        "brand_name",
        "color_name",
        "size_name",
        "standard_price",
        "quantity",
        "fulfillment_channel",
        "main_image_url",
        "other_image_url1",
        "product_id",
        "product_id_type",
    ]
    packet = build_amazon_10001_inventory_template_rows(preview_columns)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=preview_columns)
        writer.writeheader()
        writer.writerows(packet["rows"])
    return path


def export_amazon_10001_inventory_template_file_mapping(
    root: Path,
    template_path: Path,
    run_date: str | None = None,
) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_inventory_template_file_mapping_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            build_amazon_10001_inventory_template_file_mapping(template_path),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_inventory_template_upload_csv(
    root: Path,
    template_path: Path,
    run_date: str | None = None,
) -> Path:
    actual_date = run_date or date.today().isoformat()
    packet = build_amazon_10001_inventory_template_file_mapping(template_path)
    columns = packet["template_columns"]["columns"]
    path = root / "outputs" / f"amazon_10001_inventory_template_upload_candidate_{actual_date}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        if packet["rows_packet"].get("rows"):
            writer.writerows(packet["rows_packet"]["rows"])
    return path


def export_amazon_10001_latest_downloaded_template_mapping(
    root: Path,
    download_dir: Path | None = None,
    run_date: str | None = None,
) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_latest_downloaded_template_mapping_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            build_amazon_10001_latest_downloaded_template_mapping(download_dir),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_latest_downloaded_template_upload_csv(
    root: Path,
    download_dir: Path | None = None,
    run_date: str | None = None,
) -> Path | None:
    latest = build_amazon_10001_latest_downloaded_template_mapping(download_dir)
    candidate = latest.get("latest_candidate")
    if not isinstance(candidate, dict) or not candidate.get("path"):
        return None
    return export_amazon_10001_inventory_template_upload_csv(
        root,
        Path(str(candidate["path"])),
        run_date,
    )


def build_amazon_10001_template_upload_candidate_qa(rows_packet: Mapping[str, Any] | None) -> dict[str, Any]:
    packet = rows_packet or {}
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []

    def row_value(row: Mapping[str, Any], *keys: str) -> str:
        normalized = {str(key).lower(): value for key, value in row.items()}
        for key in keys:
            value = normalized.get(key.lower())
            if value is not None:
                return str(value)
        return ""

    sku_values = [row_value(row, "item_sku", "sku") for row in rows if isinstance(row, dict)]
    parent_child_values = [
        row_value(row, "parent_child", "parentage", "parent-child").strip().lower()
        for row in rows
        if isinstance(row, dict)
    ]
    if not rows and int(packet.get("row_count") or 0) == 0:
        return {
            "packet_type": "amazon_10001_template_upload_candidate_qa",
            "status": "waiting_for_candidate",
            "row_count": 0,
            "parent_count": 0,
            "child_count": 0,
            "required_skus_present": False,
            "submit_allowed": False,
            "missing_checks": ["downloaded_seller_central_template"],
            "business_blockers": [
                "product_identity_gtin_or_exemption",
                "https_image_urls",
                "product_type_definitions_validation",
                "owner_confirmation_before_upload",
            ],
            "upload_allowed": False,
            "next_step": "Download the live Amazon US Clothing/T-shirt inventory template before candidate QA.",
        }
    parent_count = sum(1 for value in parent_child_values if value == "parent")
    child_count = sum(1 for value in parent_child_values if value == "child")
    missing_checks: list[str] = []
    if int(packet.get("row_count") or len(rows)) != 98:
        missing_checks.append("expected_98_rows")
    if parent_count != 2:
        missing_checks.append("expected_2_parent_rows")
    if child_count != 96:
        missing_checks.append("expected_96_child_rows")
    for expected_sku in ["68-DDNH-IM56", "TL10001-MIX4-PARENT", "TL10001-BLK-S", "TL10001-MIX4-S"]:
        if expected_sku not in sku_values:
            missing_checks.append(f"missing_sku_{expected_sku.lower()}")
    if packet.get("submit_allowed") is not False:
        missing_checks.append("submit_allowed_must_remain_false")
    business_blockers = [
        "product_identity_gtin_or_exemption",
        "https_image_urls",
        "product_type_definitions_validation",
        "owner_confirmation_before_upload",
    ]
    return {
        "packet_type": "amazon_10001_template_upload_candidate_qa",
        "status": "candidate_structure_ready_upload_still_blocked" if not missing_checks else "candidate_structure_needs_repair",
        "row_count": int(packet.get("row_count") or len(rows)),
        "parent_count": parent_count,
        "child_count": child_count,
        "required_skus_present": not any(item.startswith("missing_sku_") for item in missing_checks),
        "submit_allowed": False,
        "missing_checks": missing_checks,
        "business_blockers": business_blockers,
        "upload_allowed": False,
        "next_step": (
            "Repair candidate row structure before using the file."
            if missing_checks
            else "Candidate row structure is ready; repair GTIN/exemption, HTTPS images, PTD validation, and owner confirmation before any upload."
        ),
    }


def build_amazon_10001_downloaded_template_watcher_result(
    root: Path,
    download_dir: Path | None = None,
    run_date: str | None = None,
) -> dict[str, Any]:
    actual_date = run_date or date.today().isoformat()
    latest = build_amazon_10001_latest_downloaded_template_mapping(download_dir)
    upload_path: Path | None = None
    if latest.get("status") == "template_rows_ready_needs_business_blockers":
        upload_path = export_amazon_10001_latest_downloaded_template_upload_csv(root, download_dir, actual_date)
    rows_packet = (
        latest.get("mapping", {}).get("rows_packet", {})
        if isinstance(latest.get("mapping"), dict)
        else {}
    )
    candidate_qa = build_amazon_10001_template_upload_candidate_qa(rows_packet if rows_packet else None)
    business_blockers = [
        "product_identity_gtin_or_exemption",
        "https_image_urls",
        "product_type_definitions_validation",
        "owner_confirmation_before_upload",
    ]
    if latest.get("status") != "template_rows_ready_needs_business_blockers":
        business_blockers.insert(0, "downloaded_seller_central_template")
    return {
        "packet_type": "amazon_10001_downloaded_template_watcher_result",
        "route": dict(AMAZON_10001_BULK_ROUTE),
        "download_dir": str(download_dir or (Path.home() / "Downloads")),
        "latest_template_status": latest.get("status"),
        "candidate_count": latest.get("candidate_count", 0),
        "latest_candidate": latest.get("latest_candidate"),
        "upload_candidate_created": bool(upload_path),
        "upload_candidate_path": upload_path.as_posix() if upload_path else "",
        "upload_candidate_download_url": (
            "/download/amazon-10001-template-upload-candidate.csv" if upload_path else ""
        ),
        "upload_candidate_row_count": rows_packet.get("row_count", 0),
        "candidate_qa": candidate_qa,
        "submit_allowed": False,
        "business_blockers": business_blockers,
        "next_step": (
            "Review the generated candidate file and repair Product Identity, HTTPS images, PTD validation, and owner gates before any Seller Central upload."
            if upload_path
            else "Download the live Amazon US Clothing/T-shirt inventory template, then rerun the watcher."
        ),
        "latest_template": latest,
    }


def export_amazon_10001_downloaded_template_watcher_result(
    root: Path,
    download_dir: Path | None = None,
    run_date: str | None = None,
) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_downloaded_template_watcher_result_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            build_amazon_10001_downloaded_template_watcher_result(root, download_dir, actual_date),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def build_amazon_10001_product_type_repair_queue(product_type_preflight: dict[str, Any]) -> list[dict[str, str]]:
    queue: list[dict[str, str]] = []
    for index, blocker in enumerate(product_type_preflight.get("blockers") or [], start=1):
        if not isinstance(blocker, dict):
            continue
        queue.append(
            {
                "id": f"AMZ-10001-PTD-REPAIR-{index:02d}",
                "sku": "TL10001-BLK-S",
                "gate": str(blocker.get("gate") or "product_type_definitions"),
                "severity": str(blocker.get("severity") or "blocker"),
                "reason": str(blocker.get("reason") or ""),
                "next_step": str(product_type_preflight.get("next_step") or ""),
                "owner": "AI Listing Operator",
            }
        )
    return queue


def export_amazon_10001_product_type_preflight(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_product_type_preflight_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_product_type_preflight(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_store_authorization_runbook(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_store_authorization_runbook_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_store_authorization_runbook(root=root), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_ptd_schema_fetch_runbook(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_ptd_schema_fetch_runbook_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_ptd_schema_fetch_runbook(root=root), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_template_ptd_execution_bridge(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_template_ptd_execution_bridge_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_template_ptd_execution_bridge(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_final_upload_gate_matrix(
    root: Path,
    run_date: str | None = None,
    *,
    asset_base_url: str | None = None,
) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_final_upload_gate_matrix_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            build_amazon_10001_final_upload_gate_matrix(root, asset_base_url=asset_base_url),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_seller_central_template_download_runbook(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_seller_central_template_download_runbook_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_seller_central_template_download_runbook(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_gtin_exemption_packet(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_gtin_exemption_packet_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_gtin_exemption_packet(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_product_identity_decision(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_product_identity_decision_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_product_identity_decision(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_product_identity_evidence_tasks_csv(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_product_identity_evidence_tasks_{actual_date}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["id", "route_key", "gate", "task", "output", "owner", "status"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(build_amazon_10001_product_identity_evidence_tasks())
    return path


def export_amazon_10001_gtin_exemption_store_runbook(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_gtin_exemption_store_runbook_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_gtin_exemption_store_runbook(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_amazon_10001_gtin_exemption_evidence_pack(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_gtin_exemption_evidence_pack_{actual_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_amazon_10001_gtin_exemption_evidence_pack(root), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def classify_amazon_feed_processing_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    issues = report.get("issues")
    if not isinstance(issues, list):
        issues = []
    classified: list[dict[str, Any]] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        message = str(issue.get("message") or "")
        attribute = str(issue.get("attributeName") or "")
        categories = issue.get("categories")
        category_text = " ".join(str(item) for item in categories) if isinstance(categories, list) else ""
        combined = f"{message} {attribute} {category_text}".lower()
        if any(token in combined for token in ("template type that is supported", "tab-delimited text file", "unsupported excel template")):
            issue_type = "file_container"
        elif any(token in combined for token in ("import designation", "import_designation", "origem da mercadoria")):
            issue_type = "import_designation"
        elif any(token in combined for token in ("country of origin", "country_of_origin")):
            issue_type = "country_of_origin"
        elif any(token in combined for token in ("conditiontype", "condition type", "condition_type")):
            issue_type = "condition_type"
        elif any(token in combined for token in ("gtin", "upc", "ean", "product id", "externally_assigned_product_identifier")):
            issue_type = "product_identity"
        elif "brand" in combined:
            issue_type = "brand"
        elif "image" in combined:
            issue_type = "image"
        elif "price" in combined or "purchasable_offer" in combined:
            issue_type = "price_offer"
        elif "variation" in combined or "relationship" in combined:
            issue_type = "variation"
        elif "required" in combined or "missing" in combined or "incomplete" in combined:
            issue_type = "missing_attribute"
        else:
            issue_type = "unknown"
        classified.append(
            {
                "sku": str(issue.get("sku") or ""),
                "message_id": str(issue.get("messageId") or ""),
                "code": str(issue.get("code") or ""),
                "severity": str(issue.get("severity") or ""),
                "attribute": attribute,
                "issue_type": issue_type,
                "message": message,
            }
        )
    return classified


def export_amazon_video_learning_notes(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_video_learning_notes_{actual_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    source_lines = [
        f"- [{item['name']}]({item['url']}): {item['lesson']}"
        for item in AMAZON_VIDEO_LEARNING_SOURCES
    ]
    action_lines = [f"- {item}" for item in VIDEO_DERIVED_FAST_ACTIONS]
    path.write_text(
        "\n".join(
            [
                "# Amazon video/tutorial learning notes",
                "",
                "Scope: Amazon US marketplace seller route for 10001 T-shirt. Public videos and tutorials are used to learn the real operator flow; they do not override Product Identity, GTIN exemption, brand, or account-safety rules.",
                "",
                "## Sources",
                *source_lines,
                "",
                "## Actions extracted for tk智能体",
                *action_lines,
                "",
                "## Operational rule",
                "",
                "Use product master -> upload/feed/SP-API -> processing report -> repair queue. Browser automation is only a fallback verification surface.",
            ]
        ),
        encoding="utf-8",
    )
    return path


def amazon_10001_bulk_context_lines(limit: int = 8) -> list[str]:
    plan = build_amazon_10001_bulk_listing_plan()
    variation_matrix = build_amazon_10001_variation_matrix()
    counts = variation_matrix["counts"]
    core_lines = [
        "Amazon 10001 bulk listing path: use product master -> Amazon feed/SP-API -> processing_report_repair; browser is fallback verification only.",
        "Existing tools selected: Amazon official SP-API SDK, official listings-feed-schema-v2, and optional python-amazon-sp-api wrapper.",
        "Video/tutorial learning added: Amazon Seller University bulk upload, Seller Central inventory-file help, and Miaoshou ERP Amazon listing flow.",
        "Current live test SKU TL10001-BLK-S has Description/Product Details/Offer/Safety ready; Product Identity remains blocked.",
        "Single item price is US$20.00, 4-pack target is US$50.00, fulfillment is FBM self warehouse, not FBA.",
        f"Variation matrix prepared: {counts['single_child_count']} single child SKUs and {counts['bundle_child_count']} 4-pack child SKUs; single and bundle families stay separate.",
        "Do not fabricate UPC/EAN/GTIN; publish requires legal GS1 code or Amazon GTIN exemption.",
    ]
    priority_stages = {"product_master", "channel_template_mapping", "feed_or_sp_api_submit", "processing_report_repair"}
    stage_lines = [
        f"{stage['stage']}: {stage['purpose']}"
        for stage in plan["bulk_listing_stages"]
        if stage["stage"] in priority_stages
    ]
    extra_stage_lines = [
        f"{stage['stage']}: {stage['purpose']}"
        for stage in plan["bulk_listing_stages"]
        if stage["stage"] not in priority_stages
    ]
    lines = core_lines + stage_lines + extra_stage_lines
    return lines[:limit]


def render_amazon_10001_bulk_listing_panel(*, compact: bool = False) -> str:
    plan = build_amazon_10001_bulk_listing_plan()
    preflight = build_amazon_10001_execution_preflight()
    secret_readiness = build_amazon_sp_api_secret_readiness()
    product_identity_decision = build_amazon_10001_product_identity_decision()
    product_identity_tasks = build_amazon_10001_product_identity_evidence_tasks(product_identity_decision)
    gtin_exemption_evidence_pack = build_amazon_10001_gtin_exemption_evidence_pack()
    gtin_exemption_runbook = build_amazon_10001_gtin_exemption_store_runbook()
    gtin_packet = build_amazon_10001_gtin_exemption_packet()
    product_type_preflight = build_amazon_10001_product_type_preflight()
    ptd_schema_fetch_runbook = build_amazon_10001_ptd_schema_fetch_runbook()
    variation_matrix = build_amazon_10001_variation_matrix()
    asset_manifest = build_amazon_10001_asset_manifest()
    asset_hosting_plan = build_amazon_10001_asset_hosting_plan()
    asset_provider_readiness = build_amazon_10001_asset_provider_readiness()
    asset_upload_command_plan = build_amazon_10001_asset_upload_command_plan()
    parent_child_feed_draft = build_amazon_10001_parent_child_json_feed_draft()
    seller_central_alignment = build_amazon_10001_seller_central_alignment()
    inventory_template_mapping = build_amazon_10001_inventory_template_mapping()
    latest_downloaded_template_mapping = build_amazon_10001_latest_downloaded_template_mapping()
    downloaded_template_watcher_result = build_amazon_10001_downloaded_template_watcher_result(Path.cwd())
    template_download_runbook = build_amazon_10001_seller_central_template_download_runbook()
    template_ptd_execution_bridge = build_amazon_10001_template_ptd_execution_bridge()
    final_upload_gate_matrix = build_amazon_10001_final_upload_gate_matrix(Path.cwd())
    store_authorization_runbook = build_amazon_10001_store_authorization_runbook()
    stage_limit = 4 if compact else len(plan["bulk_listing_stages"])
    stages_html = "".join(
        (
            "<li>"
            f"<strong>{html.escape(stage['stage'])}</strong>"
            f"<span>{html.escape(stage['purpose'])}</span>"
            "</li>"
        )
        for stage in plan["bulk_listing_stages"][:stage_limit]
    )
    blocked_html = "".join(
        (
            "<span>"
            f"{html.escape(field['field'])}: "
            f"{html.escape(field['notes'])}"
            "</span>"
        )
        for field in plan["blocked_fields"]
    )
    todo_html = "".join(
        f"<span>{html.escape(field['field'])}: {html.escape(field['notes'])}</span>"
        for field in plan["todo_fields"]
    )
    required_html = "".join(
        f"<span>{html.escape(item.replace('_', ' '))}</span>"
        for item in plan["required_before_publish"]
    )
    gate_html = "".join(
        (
            "<span>"
            f"{html.escape(item['gate'].replace('_', ' '))}: "
            f"{html.escape(item['severity'])}"
            "</span>"
        )
        for item in preflight["blockers"][:5]
    )
    gtin_blocker_html = "".join(
        (
            "<span>"
            f"{html.escape(item['id'].replace('_', ' '))}: "
            f"{html.escape(item['status'])}"
            "</span>"
        )
        for item in gtin_packet["blockers"][:4]
    )
    runbook_step_html = "".join(
        (
            "<span>"
            f"{html.escape(item['id'])}: "
            f"{html.escape(item['agent_mode'])}"
            "</span>"
        )
        for item in gtin_exemption_runbook["steps"][:4]
    )
    identity_task_html = "".join(
        (
            "<span>"
            f"{html.escape(item['gate'].replace('_', ' '))}: "
            f"{html.escape(item['status'])}"
            "</span>"
        )
        for item in product_identity_tasks[:4]
    )
    ptd_blocker_html = "".join(
        (
            "<span>"
            f"{html.escape(item['gate'].replace('_', ' '))}: "
            f"{html.escape(item['severity'])}"
            "</span>"
        )
        for item in product_type_preflight["blockers"][:5]
    )
    ptd_runbook_step_html = "".join(
        (
            "<span>"
            f"{html.escape(item['operation'])}: "
            f"{html.escape(item['purpose'])}"
            "</span>"
        )
        for item in ptd_schema_fetch_runbook["api_calls"][:3]
    )
    store_auth_step_html = "".join(
        (
            "<span>"
            f"{html.escape(item['id'])}: "
            f"{'ready' if item['ready'] else 'pending'}"
            "</span>"
        )
        for item in store_authorization_runbook["steps"][:5]
    )
    variation_counts = variation_matrix["counts"]
    variation_blocker_html = "".join(
        (
            "<span>"
            f"{html.escape(item['gate'].replace('_', ' '))}: "
            f"{html.escape(item['severity'])}"
            "</span>"
        )
        for item in variation_matrix["blockers"][:5]
    )
    bridge_blocker_html = "".join(
        (
            "<span>"
            f"{html.escape(item['gate'].replace('_', ' '))}: "
            f"{html.escape(item['severity'])}"
            "</span>"
        )
        for item in template_ptd_execution_bridge["blockers"][:5]
    )
    final_gate_html = "".join(
        (
            "<span>"
            f"{html.escape(item['gate'].replace('_', ' '))}: "
            f"{html.escape(item['status'])}; "
            f"{html.escape(str(item.get('checker_id') or 'checker'))}="
            f"{html.escape(str(item.get('checker_result_status') or 'unknown'))}"
            "</span>"
        )
        for item in final_upload_gate_matrix["blockers"][:6]
    )
    return f"""
    <section class="amazon-bulk-listing-panel" aria-label="Amazon bulk listing path">
      <div class="amazon-bulk-listing-head">
        <span>Amazon bulk listing path</span>
        <strong>Feed/SP-API first, browser fallback only</strong>
        <p>10001 is ready for an ERP-style listing workflow. The live Seller Central draft is still blocked by Product Identity, so the next step is a clean product master, Amazon feed/SP-API mapping, then processing-report repair.</p>
      </div>
      <div class="amazon-bulk-listing-grid">
        <div><b>Primary path</b><span>{html.escape(plan["primary_execution_surface"])}</span></div>
        <div><b>Browser role</b><span>{html.escape(plan["browser_execution_surface"])}</span></div>
        <div><b>Single / 4-pack</b><span>$20.00 / $50.00</span></div>
        <div><b>Fulfillment</b><span>FBM self warehouse</span></div>
      </div>
      <div class="amazon-bulk-listing-warning">
        <b>Product Identity blocked</b>
        <p>Do not fabricate UPC/EAN/GTIN. Publish requires a legal GS1 code or an approved Amazon GTIN exemption for this route.</p>
        <div>{blocked_html}{todo_html}{required_html}</div>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>Execution preflight</b>
        <p>Status: {html.escape(preflight["status"])}. Local draft is ready; real Feed/SP-API submission remains gated.</p>
        <div>{gate_html}</div>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>Product identity decision</b>
        <p>Status: {html.escape(product_identity_decision["status"])}. Recommended first path: {html.escape(product_identity_decision["recommended_path"])}; selected path: {html.escape(product_identity_decision["selected_path"])}.</p>
        <div>{identity_task_html}</div>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>GTIN exemption packet</b>
        <p>Status: {html.escape(gtin_packet["status"])}. Images are checked from the local 10001 asset folder; the packet still blocks fake Product IDs.</p>
        <div>{gtin_blocker_html}</div>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>GTIN exemption evidence pack</b>
        <p>Status: {html.escape(gtin_exemption_evidence_pack["status"])}. Selected {gtin_exemption_evidence_pack["selected_product_photos_count"]} product photos; packaging/no-barcode evidence files: {gtin_exemption_evidence_pack["packaging_evidence_count"]}.</p>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>GTIN exemption store runbook</b>
        <p>Status: {html.escape(gtin_exemption_runbook["status"])}. Seller Central flow is prepared, but the agent stops at account security, irreversible submit, or missing evidence.</p>
        <div>{runbook_step_html}</div>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>SP-API secret readiness</b>
        <p>Status: {html.escape(secret_readiness["status"])}. Values are hidden; only presence is checked per Amazon US store route.</p>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>Amazon store authorization runbook</b>
        <p>Status: {html.escape(store_authorization_runbook["status"])}. BitBrowser profile, browser extension, SP-API app, roles, and seller-scoped secrets must all stay isolated to the Amazon US marketplace seller store.</p>
        <div>{store_auth_step_html}</div>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>Product Type Definitions preflight</b>
        <p>Status: {html.escape(product_type_preflight["status"])}. SHIRT/LISTING schema must be pulled for Amazon US before Feed/SP-API submit.</p>
        <div>{ptd_blocker_html}</div>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>PTD schema fetch runbook</b>
        <p>Status: {html.escape(ptd_schema_fetch_runbook["status"])}. The agent will fetch searchDefinitionsProductTypes and getDefinitionsProductType after store-scoped SP-API authorization, save parent/child schema files, then validate the 10001 feed draft before upload.</p>
        <div>{ptd_runbook_step_html}</div>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>Template/PTD execution bridge</b>
        <p>Status: {html.escape(template_ptd_execution_bridge["status"])}. It connects SP-API PTD, live Seller Central template, image URLs, and Product Identity before final upload build.</p>
        <div>{bridge_blocker_html}</div>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>Final upload gate matrix</b>
        <p>Status: {html.escape(final_upload_gate_matrix["status"])}. This is the one-screen truth table for whether 10001 can move from local candidate to owner review before any Seller Central upload.</p>
        <div>{final_gate_html}</div>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>Variation matrix</b>
        <p>Status: {html.escape(variation_matrix["status"])}. Prepared {variation_counts["single_child_count"]} single child SKUs and {variation_counts["bundle_child_count"]} 4-pack child SKUs; single and 4-pack families stay separate.</p>
        <div>{variation_blocker_html}</div>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>Image asset manifest</b>
        <p>Status: {html.escape(asset_manifest["status"])}. Local 6-color front/back flat-lay images are checked; Amazon still needs stable public image URLs.</p>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>Asset hosting plan</b>
        <p>Status: {html.escape(asset_hosting_plan["status"])}. Prepared {asset_hosting_plan["upload_task_count"]} upload tasks for image hosting; non-HTTPS, localhost, and placeholder URLs are blocked.</p>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>Asset provider readiness</b>
        <p>Status: {html.escape(asset_provider_readiness["status"])}. Upload command plan: {html.escape(asset_upload_command_plan["status"])} with {asset_upload_command_plan["command_count"]} commands prepared but blocked until credentials and final HTTPS base URL are ready.</p>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>Parent-child feed draft</b>
        <p>Status: draft only. Prepared {parent_child_feed_draft["tk_preflight"]["message_count"]} JSON feed messages and a bulk-upload CSV seed; submit remains disabled until URL, GTIN/exemption, PTD, and owner gates pass.</p>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>Seller Central alignment</b>
        <p>Status: {html.escape(seller_central_alignment["status"])}. The CSV is a store-mapping seed, not the final Amazon upload template; download the live Clothing/T-shirt template before real upload.</p>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>Seller Central template download runbook</b>
        <p>Status: {html.escape(template_download_runbook["status"])}. The agent can navigate the live Spreadsheet / Add products via upload flow, download the blank template, then local-verify headers before any upload build.</p>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>Inventory template mapping</b>
        <p>Status: {html.escape(inventory_template_mapping["status"])}. Required template columns still need the live Seller Central inventory file header before a final upload file can be generated.</p>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>Downloads template watcher</b>
        <p>Status: {html.escape(latest_downloaded_template_mapping["status"])}. The agent scans Downloads for the newest Amazon inventory/template file and maps it only when headers are readable.</p>
      </div>
      <div class="amazon-bulk-listing-gates">
        <b>Downloaded template upload candidate</b>
        <p>Status: {'created' if downloaded_template_watcher_result["upload_candidate_created"] else 'waiting_for_template'}. Rows: {html.escape(str(downloaded_template_watcher_result["upload_candidate_row_count"]))}. File: {html.escape(downloaded_template_watcher_result["upload_candidate_path"] or "not generated yet")}.</p>
        <p>Download: {html.escape(downloaded_template_watcher_result["upload_candidate_download_url"] or "not available yet")}</p>
        <p>QA: {html.escape(str(downloaded_template_watcher_result.get("candidate_qa", {}).get("status") or "waiting_for_candidate"))}; parents={html.escape(str(downloaded_template_watcher_result.get("candidate_qa", {}).get("parent_count") or 0))}; children={html.escape(str(downloaded_template_watcher_result.get("candidate_qa", {}).get("child_count") or 0))}.</p>
      </div>
      <ol class="amazon-bulk-listing-stages">{stages_html}</ol>
    </section>
    """


def export_amazon_10001_listing_master_csv(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    path = root / "outputs" / f"amazon_10001_listing_master_{actual_date}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["field", "value", "status", "notes"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in AMAZON_10001_SINGLE_FIELDS:
            writer.writerow(item.to_dict())
    return path
