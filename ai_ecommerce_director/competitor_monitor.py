from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse
from uuid import uuid4


MONITOR_CONFIG = Path("config") / "competitor_watch.json"
REFERENCE_IMAGE_DIR = Path("data") / "competitor_reference_images"


def load_monitor_config(root: Path) -> dict[str, Any]:
    path = root / MONITOR_CONFIG
    if not path.exists():
        return default_monitor_config()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return default_monitor_config()
    payload.setdefault("keywords", [])
    payload.setdefault("competitor_links", [])
    payload.setdefault("brand_targets", [])
    return payload


def default_monitor_config() -> dict[str, Any]:
    return {
        "notes": [
            "No API mode: keywords and competitor links are converted into public page checks.",
            "Reference images are saved locally for product-family matching and future visual AI analysis.",
            "Login, slider, and captcha pages are marked as manual gates.",
        ],
        "keywords": [],
        "competitor_links": [],
        "brand_targets": [],
    }


def save_monitor_config(root: Path, payload: dict[str, Any]) -> Path:
    path = root / MONITOR_CONFIG
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def add_monitor_item(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    config = load_monitor_config(root)
    item_type = str(payload.get("type") or "keyword").strip().lower()
    now = datetime.now().isoformat(timespec="seconds")
    reference_image = save_reference_image(root, str(payload.get("image_data_url") or ""))
    base_item = {
        "id": uuid4().hex[:12],
        "enabled": True,
        "created_at": now,
        "platform": str(payload.get("platform") or "").strip() or "Multi-platform",
        "market": str(payload.get("market") or "").strip() or "US",
        "product_family": str(payload.get("product_family") or "").strip(),
        "notes": str(payload.get("notes") or "").strip(),
        "reference_image": reference_image,
    }
    if item_type == "brand":
        brand_name = str(payload.get("brand_name") or payload.get("brand") or payload.get("name") or "").strip()
        if not brand_name:
            raise ValueError("Brand name is required.")
        item = {
            **base_item,
            "brand_name": brand_name,
            "product_line": str(payload.get("product_line") or payload.get("product_family") or "").strip(),
            "regions": normalize_monitor_list(payload.get("regions")) or ["US"],
            "platforms": normalize_monitor_list(payload.get("platforms")) or ["Amazon", "TikTok Shop", "Walmart", "Google"],
            "known_store_names": normalize_monitor_list(payload.get("known_store_names")),
            "official_domains": normalize_monitor_list(payload.get("official_domains")),
            "authorized_store_keywords": normalize_monitor_list(payload.get("authorized_store_keywords")),
        }
        config.setdefault("brand_targets", []).append(item)
    elif item_type == "link":
        url = str(payload.get("url") or "").strip()
        if not url:
            raise ValueError("Competitor link is required.")
        item = {**base_item, "url": url, "name": str(payload.get("name") or url).strip()}
        config.setdefault("competitor_links", []).append(item)
    else:
        keyword = str(payload.get("keyword") or "").strip()
        if not keyword:
            raise ValueError("Keyword is required.")
        item = {**base_item, "keyword": keyword}
        config.setdefault("keywords", []).append(item)
    save_monitor_config(root, config)
    return item


def save_reference_image(root: Path, data_url: str) -> str:
    if not data_url:
        return ""
    allowed = {
        "data:image/png;base64,": ".png",
        "data:image/jpeg;base64,": ".jpg",
        "data:image/webp;base64,": ".webp",
    }
    suffix = ""
    raw_payload = ""
    for prefix, ext in allowed.items():
        if data_url.startswith(prefix):
            suffix = ext
            raw_payload = data_url[len(prefix) :]
            break
    if not suffix:
        raise ValueError("Only PNG, JPG, and WEBP reference images are supported.")
    raw = base64.b64decode(raw_payload)
    if len(raw) > 8_000_000:
        raise ValueError("Reference image is too large. Please use an image under 8 MB.")
    image_dir = root / REFERENCE_IMAGE_DIR
    image_dir.mkdir(parents=True, exist_ok=True)
    path = image_dir / f"{uuid4().hex}{suffix}"
    path.write_bytes(raw)
    return str(path)


def build_competitor_watch_sources(root: Path) -> list[dict[str, Any]]:
    config = load_monitor_config(root)
    sources: list[dict[str, Any]] = []
    for item in config.get("keywords", []):
        if isinstance(item, dict) and item.get("enabled", True):
            sources.extend(keyword_sources(item))
    for item in config.get("competitor_links", []):
        if isinstance(item, dict) and item.get("enabled", True):
            sources.append(link_source(item))
    for item in config.get("brand_targets", []):
        if isinstance(item, dict) and item.get("enabled", True):
            sources.extend(brand_sources(item))
    return sources


def normalize_monitor_list(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value or "").replace("\r", "\n").replace(",", "\n").replace("，", "\n").split("\n")
    return [str(item).strip() for item in raw if str(item).strip()]


def brand_sources(item: dict[str, Any]) -> list[dict[str, Any]]:
    brand = str(item.get("brand_name") or "").strip()
    if not brand:
        return []
    product_line = str(item.get("product_line") or item.get("product_family") or "").strip()
    query_core = " ".join(part for part in [brand, product_line] if part).strip()
    platforms = " ".join(platform.lower() for platform in normalize_monitor_list(item.get("platforms")))
    regions = expand_regions(normalize_monitor_list(item.get("regions")) or ["US"])
    sources: list[dict[str, Any]] = []
    for market in regions:
        market_code = str(market.get("code") or "US")
        if "amazon" in platforms or "multi" in platforms:
            domain = str(market.get("amazon_domain") or "www.amazon.com")
            sources.append(brand_source_base(item, {
                "id": f"brand-{item.get('id', brand)}-amazon-{market_code.lower()}",
                "name": f"{brand} / Amazon {market_code} / {product_line or 'all products'}",
                "record_type": "platform_ranking_signal",
                "source_platform": "Amazon",
                "marketplace": "Amazon",
                "market": market_code,
                "ranking_type": "Brand Product Search",
                "url": f"https://{domain}/s?k={quote_plus(query_core)}",
                "keyword": query_core,
                "data_category": "brand_marketplace_search",
            }))
        if ("walmart" in platforms or "multi" in platforms) and market_code == "US":
            sources.append(brand_source_base(item, {
                "id": f"brand-{item.get('id', brand)}-walmart-us",
                "name": f"{brand} / Walmart US / {product_line or 'all products'}",
                "record_type": "platform_ranking_signal",
                "source_platform": "Walmart",
                "marketplace": "Walmart",
                "market": "US",
                "ranking_type": "Brand Product Search",
                "url": f"https://www.walmart.com/search?q={quote_plus(query_core)}",
                "keyword": query_core,
                "data_category": "brand_marketplace_search",
            }))
        if "tiktok" in platforms or "tk" in platforms or "multi" in platforms:
            sources.append(brand_source_base(item, {
                "id": f"brand-{item.get('id', brand)}-tiktok-{market_code.lower()}",
                "name": f"{brand} / TikTok search {market_code} / {product_line or 'all products'}",
                "record_type": "platform_ranking_signal",
                "source_platform": "TikTok Shop Buyer",
                "marketplace": "TikTok Shop",
                "market": market_code,
                "ranking_type": "Buyer Video / Shop Search",
                "url": f"https://www.tiktok.com/search?q={quote_plus(query_core + ' shop')}",
                "keyword": query_core,
                "data_category": "brand_buyer_video_shop_search",
                "requires_login": True,
                "may_trigger_verification": True,
                "headless": False,
                "incognito": True,
                "initial_wait_seconds": 18,
                "reload_if_stalled": True,
                "keep_open_on_gate": True,
                "keep_open_after_run": True,
            }))
        if "google" in platforms or "multi" in platforms:
            country_query = str(market.get("search_hint") or market_code)
            sources.append(brand_source_base(item, {
                "id": f"brand-{item.get('id', brand)}-google-{market_code.lower()}",
                "name": f"{brand} / Google discovery {market_code} / stores and authorized dealers",
                "record_type": "industry_research_asset",
                "source_platform": "Google",
                "marketplace": "Google Search",
                "market": market_code,
                "ranking_type": "Brand Store / Authorized Seller Discovery",
                "url": f"https://www.google.com/search?q={quote_plus(query_core + ' official store authorized seller ' + country_query)}",
                "keyword": query_core,
                "data_category": "brand_store_discovery",
            }))
    for index, domain in enumerate(normalize_monitor_list(item.get("official_domains"))):
        sources.append(brand_source_base(item, {
            "id": f"brand-{item.get('id', brand)}-official-{index + 1}",
            "name": f"{brand} / official domain {index + 1}",
            "record_type": "industry_research_asset",
            "source_platform": "Brand Site",
            "marketplace": "DTC",
            "ranking_type": "Official Brand Site",
            "url": ensure_url(domain),
            "data_category": "brand_official_site",
        }))
    return sources


def brand_source_base(item: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    source.setdefault("requires_login", False)
    source.setdefault("enabled", True)
    source.update(
        {
            "monitoring_scope": "brand_target",
            "brand_target_id": item.get("id"),
            "brand_name": item.get("brand_name"),
            "product_line": item.get("product_line", ""),
            "product_family": item.get("product_family", ""),
            "known_store_names": item.get("known_store_names", []),
            "authorized_store_keywords": item.get("authorized_store_keywords", []),
            "reference_image": item.get("reference_image", ""),
            "notes": item.get("notes", ""),
        }
    )
    return source


def expand_regions(regions: list[str]) -> list[dict[str, str]]:
    region_map = {
        "US": [{"code": "US", "amazon_domain": "www.amazon.com", "search_hint": "United States"}],
        "EU": [
            {"code": "DE", "amazon_domain": "www.amazon.de", "search_hint": "Germany"},
            {"code": "UK", "amazon_domain": "www.amazon.co.uk", "search_hint": "United Kingdom"},
            {"code": "FR", "amazon_domain": "www.amazon.fr", "search_hint": "France"},
            {"code": "ES", "amazon_domain": "www.amazon.es", "search_hint": "Spain"},
            {"code": "IT", "amazon_domain": "www.amazon.it", "search_hint": "Italy"},
        ],
        "EUROPE": [
            {"code": "DE", "amazon_domain": "www.amazon.de", "search_hint": "Germany"},
            {"code": "UK", "amazon_domain": "www.amazon.co.uk", "search_hint": "United Kingdom"},
            {"code": "FR", "amazon_domain": "www.amazon.fr", "search_hint": "France"},
            {"code": "ES", "amazon_domain": "www.amazon.es", "search_hint": "Spain"},
            {"code": "IT", "amazon_domain": "www.amazon.it", "search_hint": "Italy"},
        ],
        "JP": [{"code": "JP", "amazon_domain": "www.amazon.co.jp", "search_hint": "Japan"}],
        "JAPAN": [{"code": "JP", "amazon_domain": "www.amazon.co.jp", "search_hint": "Japan"}],
        "LATIN AMERICA": [
            {"code": "MX", "amazon_domain": "www.amazon.com.mx", "search_hint": "Mexico Latin America"},
            {"code": "BR", "amazon_domain": "www.amazon.com.br", "search_hint": "Brazil Latin America"},
        ],
    }
    expanded: list[dict[str, str]] = []
    for region in regions:
        key = str(region).strip().upper()
        expanded.extend(region_map.get(key, [{"code": key, "amazon_domain": "www.amazon.com", "search_hint": key}]))
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for item in expanded:
        code = item["code"]
        if code in seen:
            continue
        seen.add(code)
        unique.append(item)
    return unique


def ensure_url(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        return ""
    if clean.startswith(("http://", "https://")):
        return clean
    return "https://" + clean


def keyword_sources(item: dict[str, Any]) -> list[dict[str, Any]]:
    keyword = str(item.get("keyword") or "").strip()
    if not keyword:
        return []
    encoded = quote_plus(keyword)
    base = source_base(item)
    platform = str(item.get("platform") or "Amazon").lower()
    sources = []
    if "amazon" in platform or "multi" in platform:
        sources.append(
        {
            **base,
            "id": f"kw-amazon-{item.get('id', encoded)}",
            "name": f"Amazon keyword: {keyword}",
            "record_type": "platform_ranking_signal",
            "source_platform": "Amazon",
            "marketplace": "Amazon",
            "ranking_type": "Focused Keyword Search",
            "url": f"https://www.amazon.com/s?k={encoded}",
            "expected_keywords": [keyword.split()[0]],
            "keyword": keyword,
        }
        )
    if "etsy" in platform or "multi" in platform:
        sources.append(
        {
            **base,
            "id": f"kw-etsy-{item.get('id', encoded)}",
            "name": f"Etsy keyword: {keyword}",
            "record_type": "platform_ranking_signal",
            "source_platform": "Etsy",
            "marketplace": "Etsy",
            "ranking_type": "Keyword Search",
            "url": f"https://www.etsy.com/search?q={encoded}",
            "expected_keywords": [keyword.split()[0]],
            "keyword": keyword,
        }
        )
    return sources


def link_source(item: dict[str, Any]) -> dict[str, Any]:
    url = str(item.get("url") or "").strip()
    platform = infer_platform(url)
    record_type = "review_insight" if platform == "Amazon" and "/dp/" in url else "hot_link"
    return {
        **source_base(item),
        "id": f"competitor-{item.get('id', 'link')}",
        "name": str(item.get("name") or url),
        "record_type": record_type,
        "source_platform": platform,
        "marketplace": platform,
        "ranking_type": "Competitor Link",
        "url": url,
        "expected_keywords": [],
    }


def source_base(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": True,
        "requires_login": False,
        "monitoring_scope": "focused_target",
        "monitor_item_id": item.get("id"),
        "keyword": item.get("keyword", ""),
        "product_family": item.get("product_family", ""),
        "reference_image": item.get("reference_image", ""),
        "notes": item.get("notes", ""),
    }


def infer_platform(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "amazon" in host:
        return "Amazon"
    if "etsy" in host:
        return "Etsy"
    if "tiktok" in host:
        return "TikTok"
    if "walmart" in host:
        return "Walmart"
    if "shein" in host:
        return "SHEIN"
    if "youtube" in host:
        return "YouTube"
    if "instagram" in host:
        return "Instagram"
    return host or "Competitor"
