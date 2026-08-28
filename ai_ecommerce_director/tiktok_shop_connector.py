from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .types import IntakeRecord
from .tiktok_shop_route_guard import build_tiktok_shop_fact

# TikTok Shop official Partner API connector.
#
# Credit / reference: the request structure and signing follow the official
# TikTok Shop Open Platform (API v202309+). Implementation informed by the
# open-source SDK EcomPHP/tiktokshop-php (Apache-2.0) — used here as an API
# reference and reimplemented in Python with attribution, per the authors' OK.
# This connector calls the OFFICIAL API only (no scraping, no anti-bot bypass).

TIKTOK_SHOP_BASE_URL = "https://open-api.tiktokglobalshop.com"

# Credentials live in environment variables (never in plaintext config).
ENV_APP_KEY = "TIKTOK_SHOP_APP_KEY"
ENV_APP_SECRET = "TIKTOK_SHOP_APP_SECRET"
ENV_ACCESS_TOKEN = "TIKTOK_SHOP_ACCESS_TOKEN"
ENV_SHOP_CIPHER = "TIKTOK_SHOP_CIPHER"
ENV_SHOP_ID = "TIKTOK_SHOP_ID"
ENV_REGION = "TIKTOK_SHOP_REGION"
ENV_SELLER_TYPE = "TIKTOK_SHOP_SELLER_TYPE"
ENV_CURRENCY = "TIKTOK_SHOP_CURRENCY"
ENV_TIMEZONE = "TIKTOK_SHOP_TIMEZONE"
ENV_CONNECTOR_BINDING_ID = "TIKTOK_SHOP_CONNECTOR_BINDING_ID"


def load_config(root: Path | None = None) -> dict[str, str]:
    return {
        "app_key": os.environ.get(ENV_APP_KEY, ""),
        "app_secret": os.environ.get(ENV_APP_SECRET, ""),
        "access_token": os.environ.get(ENV_ACCESS_TOKEN, ""),
        "shop_cipher": os.environ.get(ENV_SHOP_CIPHER, ""),
        "shop_id": os.environ.get(ENV_SHOP_ID, ""),
        "region": os.environ.get(ENV_REGION, ""),
        "seller_type": os.environ.get(ENV_SELLER_TYPE, ""),
        "currency": os.environ.get(ENV_CURRENCY, ""),
        "timezone": os.environ.get(ENV_TIMEZONE, ""),
        "connector_binding_id": os.environ.get(ENV_CONNECTOR_BINDING_ID, ""),
        "base_url": os.environ.get("TIKTOK_SHOP_BASE_URL", TIKTOK_SHOP_BASE_URL),
    }


def is_configured(config: dict[str, str] | None = None) -> bool:
    config = config or load_config()
    return all(
        bool(config.get(field))
        for field in (
            "app_key",
            "app_secret",
            "access_token",
            "shop_cipher",
            "shop_id",
            "region",
            "seller_type",
            "currency",
            "timezone",
            "connector_binding_id",
        )
    )


def sign_request(app_secret: str, path: str, params: dict[str, Any], body: str = "") -> str:
    """TikTok Shop request signature (HMAC-SHA256), official v202309 scheme:
    sort params (excluding sign & access_token) by key, concatenate key+value,
    prepend the path, append the raw body, wrap with app_secret on both ends."""
    filtered = {k: v for k, v in params.items() if k not in {"sign", "access_token"} and v is not None}
    concatenated = "".join(f"{key}{filtered[key]}" for key in sorted(filtered))
    base_string = f"{path}{concatenated}{body}"
    wrapped = f"{app_secret}{base_string}{app_secret}"
    return hmac.new(app_secret.encode("utf-8"), wrapped.encode("utf-8"), hashlib.sha256).hexdigest()


def _signed_url(config: dict[str, str], path: str, extra_params: dict[str, Any] | None = None) -> str:
    params: dict[str, Any] = {
        "app_key": config["app_key"],
        "timestamp": str(int(time.time())),
    }
    if config.get("shop_cipher"):
        params["shop_cipher"] = config["shop_cipher"]
    if extra_params:
        params.update({k: v for k, v in extra_params.items() if v is not None})
    params["sign"] = sign_request(config["app_secret"], path, params)
    return f"{config['base_url'].rstrip('/')}{path}?{urllib.parse.urlencode(params)}"


def fetch_products(config: dict[str, str] | None = None, *, page_size: int = 50, timeout: int = 15) -> list[dict[str, Any]]:
    """Pull the shop's product list from the official API. Returns [] if not
    configured (no credentials) — never fabricates data."""
    config = config or load_config()
    if not is_configured(config):
        return []
    path = "/product/202309/products/search"
    url = _signed_url(config, path, {"page_size": page_size})
    body = json.dumps({"page_size": page_size}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "x-tts-access-token": config["access_token"]},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    products = (((data or {}).get("data") or {}).get("products")) or []
    return [p for p in products if isinstance(p, dict)]


def map_products_to_records(
    products: list[dict[str, Any]],
    *,
    run_date: str | None = None,
    shop_context: dict[str, Any] | None = None,
) -> list[IntakeRecord]:
    """Map official-API products to platform_ranking_signal records. They carry
    product_url + price so they count as hard TK evidence in build_tk_snapshot."""
    run_date = run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    records: list[IntakeRecord] = []
    for product in products:
        product_id = str(product.get("id") or product.get("product_id") or "").strip()
        title = str(product.get("title") or product.get("product_name") or "").strip()
        if not product_id and not title:
            continue
        skus = product.get("skus") if isinstance(product.get("skus"), list) else []
        price = ""
        for sku in skus:
            if isinstance(sku, dict):
                price_obj = sku.get("price") if isinstance(sku.get("price"), dict) else {}
                price = str(price_obj.get("sale_price") or price_obj.get("tax_exclusive_price") or "").strip()
                if price:
                    break
        fields = {
            "source_platform": "TikTok Shop",
            "data_category": "tiktok_shop_official_product",
            "product_name": title,
            "product_url": f"https://shop.tiktok.com/view/product/{product_id}" if product_id else "",
            "external_product_id": product_id,
            "price_visible": price,
            "status": str(product.get("status") or ""),
        }
        provenance: dict[str, Any]
        if shop_context:
            provenance = build_tiktok_shop_fact(
                fact_class="first_party_shop_fact",
                fact_name="official_product_api_record",
                value={"product_id": product_id, "status": fields["status"], "price": price},
                evidence_ref=str(shop_context.get("evidence_ref") or "authorized-product-api-response"),
                observed_at=str(shop_context.get("observed_at") or datetime.now(timezone.utc).isoformat()),
                shop_context=shop_context,
                attribution_definition=str(shop_context.get("attribution_definition") or "official product catalog snapshot; no advertising attribution"),
            )
            fields.update(
                {
                    "shop_id": str(shop_context.get("shop_id") or ""),
                    "country_site": str(shop_context.get("region") or ""),
                    "seller_type": str(shop_context.get("seller_type") or ""),
                    "currency": str(shop_context.get("currency") or ""),
                    "timezone": str(shop_context.get("timezone") or ""),
                }
            )
        else:
            provenance = build_tiktok_shop_fact(
                fact_class="official_api_unscoped_observation",
                fact_name="official_api_payload_without_shop_provenance",
                value={"product_id": product_id, "status": fields["status"], "price": price},
                evidence_ref="unscoped-official-api-payload",
                observed_at=run_date,
            )
        records.append(
            IntakeRecord(
                record_type="platform_ranking_signal",
                fields={k: v for k, v in fields.items() if v},
                raw_text=json.dumps({"product_id": product_id, "title": title, "date": run_date}, ensure_ascii=False),
                source="tiktok_shop_official_api",
                score={"priority": 70},
                director_notes=["Pulled from TikTok Shop official API (compliant, no scraping)."],
                metadata={"connector": "tiktok_shop_official", "fact_provenance": provenance},
            )
        )
    return records
