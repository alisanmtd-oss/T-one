from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse
from uuid import uuid4

from .competitor_monitor import save_reference_image
from .storage import append_record
from .types import IntakeRecord


PRODUCT_TARGETS_CONFIG = Path("config") / "product_targets.json"
ALL_RESEARCH_PLATFORMS = [
    "Amazon",
    "TikTok Shop",
    "TikTok Video",
    "Etsy",
    "Walmart",
    "eBay",
    "SHEIN",
]
TIKTOK_SELECTION_BRIDGES = [
    {
        "provider": "FastMoss",
        "source_platform": "FastMoss",
        "base_url": "https://www.fastmoss.com/zh/e-commerce/search",
        "data_category": "fastmoss_tiktok_product_rank",
        "ranking_type": "FastMoss TikTok Product / Creator / Video Ranking",
        "search_instruction": "Use FastMoss internal search/ranking filters for the keyword, then capture ranking tables, product cards, creator/video rows, and outbound TikTok Shop links.",
    },
    {
        "provider": "Kalodata",
        "source_platform": "Kalodata",
        "base_url": "https://www.kalodata.com/",
        "data_category": "kalodata_tiktok_product_rank",
        "ranking_type": "Kalodata TikTok Product / Creator / Video Ranking",
        "search_instruction": "Use Kalodata internal search/ranking filters for the keyword, then capture ranking tables, product cards, creator/video rows, and outbound TikTok Shop links.",
    },
]
NON_ECOMMERCE_PRODUCT_PLATFORMS = {
    "Google",
    "Google Shopping",
    "YouTube",
    "Instagram",
}

BUILTIN_KEYWORD_TRANSLATIONS = {
    "香水": ["perfume", "fragrance", "eau de parfum", "cologne", "body mist", "travel perfume", "women perfume", "men cologne"],
    "男士香水": ["men cologne", "men perfume", "men fragrance", "eau de toilette for men"],
    "女士香水": ["women perfume", "women fragrance", "eau de parfum for women", "body mist for women"],
    "洗面奶": ["facial cleanser", "face wash", "foaming cleanser", "gentle cleanser"],
    "氨基酸洗面奶": ["amino acid cleanser", "amino acid face wash", "gentle amino acid cleanser", "foaming facial cleanser"],
    "褪黑素": ["melatonin", "melatonin gummies", "sleep gummies", "sleep supplement"],
    "保健品": ["supplement", "health supplement", "vitamin", "wellness supplement"],
    "水洗t恤": ["washed t shirt", "vintage washed tee", "garment dyed t shirt", "heavyweight washed tee"],
    "水洗T恤": ["washed t shirt", "vintage washed tee", "garment dyed t shirt", "heavyweight washed tee"],
    "帽子": ["hat", "baseball cap", "snapback hat", "trucker hat"],
    "棒球帽": ["baseball cap", "dad hat", "snapback cap", "embroidered cap"],
    "狗爹": ["dog dad", "dog dad shirt", "dog dad hat"],
    "钓鱼": ["fishing", "fishing shirt", "fishing hat", "fishing gift"],
    "蓝领": ["blue collar", "blue collar shirt", "blue collar dad"],
    "手机膜": [
        "phone screen protector",
        "screen protector",
        "tempered glass screen protector",
        "privacy screen protector",
        "iphone screen protector",
        "samsung screen protector",
        "camera lens protector",
        "installation frame screen protector",
        "anti spy screen protector",
    ],
    "钢化膜": [
        "tempered glass screen protector",
        "phone screen protector",
        "iphone tempered glass",
        "samsung tempered glass",
        "camera lens protector",
    ],
    "屏幕保护膜": [
        "screen protector",
        "phone screen protector",
        "tempered glass screen protector",
        "privacy screen protector",
    ],
}


def load_product_targets(root: Path) -> dict[str, Any]:
    path = root / PRODUCT_TARGETS_CONFIG
    if not path.exists():
        return {"targets": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"targets": []}
    payload.setdefault("targets", [])
    return payload


def save_product_targets(root: Path, payload: dict[str, Any]) -> Path:
    path = root / PRODUCT_TARGETS_CONFIG
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def add_product_target(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    config = load_product_targets(root)
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("Product target name is required.")
    keywords = expand_product_keywords(name, payload.get("keywords"))
    competitor_links = normalize_list(payload.get("competitor_links"))
    if not keywords and name:
        keywords = [name]
    platforms = normalize_platforms(payload.get("platforms")) or list(ALL_RESEARCH_PLATFORMS)
    target = {
        "id": uuid4().hex[:12],
        "enabled": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "name": name,
        "brand_name": str(payload.get("brand_name") or "").strip(),
        "product_family": str(payload.get("product_family") or name).strip(),
        "platforms": platforms,
        "market": str(payload.get("market") or "US").strip(),
        "countries": normalize_list(payload.get("countries")) or [str(payload.get("market") or "US").strip()],
        "known_stores": normalize_list(payload.get("known_stores")),
        "official_domains": normalize_list(payload.get("official_domains")),
        "keywords": keywords,
        "original_keywords": normalize_list(payload.get("keywords")) or [name],
        "keyword_language": "mixed_or_translated" if contains_cjk(name) or any(contains_cjk(item) for item in keywords) else "original",
        "competitor_links": competitor_links,
        "reference_image": save_reference_image(root, str(payload.get("image_data_url") or "")),
        "notes": str(payload.get("notes") or "").strip(),
        "data_categories": [
            "market_overview",
            "amazon_keyword",
            "competitor_link",
            "buyer_video",
            "reviews",
            "listing",
            "visual_creative",
            "risk",
        ],
    }
    config.setdefault("targets", []).append(target)
    save_product_targets(root, config)
    seed_product_target_collection_jobs(root, target)
    return target


def remove_product_target(root: Path, target_id: str) -> dict[str, Any]:
    config = load_product_targets(root)
    targets = [item for item in config.get("targets", []) if isinstance(item, dict)]
    before = len(targets)
    config["targets"] = [item for item in targets if str(item.get("id") or "") != str(target_id)]
    if len(config["targets"]) == before:
        raise ValueError(f"Product target not found: {target_id}")
    save_product_targets(root, config)
    return config


def normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value or "").replace("\r", "\n").replace(",", "\n").split("\n")
    return [str(item).strip() for item in raw if str(item).strip()]


def normalize_platforms(value: Any) -> list[str]:
    aliases = {
        "tk": "TikTok Shop",
        "tiktok": "TikTok Shop",
        "tiktok shop": "TikTok Shop",
        "tiktok video": "TikTok Video",
        "tiktok videos": "TikTok Video",
        "tk video": "TikTok Video",
        "tk videos": "TikTok Video",
        "amazon": "Amazon",
        "etsy": "Etsy",
        "walmart": "Walmart",
        "ebay": "eBay",
        "shein": "SHEIN",
        "google": "Google",
        "google shopping": "Google Shopping",
        "youtube": "YouTube",
        "instagram": "Instagram",
        "ig": "Instagram",
    }
    platforms: list[str] = []
    for item in normalize_list(value):
        label = aliases.get(item.strip().lower(), item.strip())
        if label in NON_ECOMMERCE_PRODUCT_PLATFORMS:
            continue
        if label in ALL_RESEARCH_PLATFORMS and label not in platforms:
            platforms.append(label)
    return platforms


def expand_product_keywords(name: str, raw_keywords: Any) -> list[str]:
    seeds = normalize_list(raw_keywords) or [name]
    expanded: list[str] = []
    for seed in [name, *seeds]:
        add_unique(expanded, seed)
        for keyword in translations_for(seed):
            add_unique(expanded, keyword)
        for keyword in decomposed_keywords(seed):
            add_unique(expanded, keyword)
    if contains_cjk(name) and not any(not contains_cjk(item) for item in expanded):
        add_unique(expanded, name)
    return expanded[:30]


def translations_for(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    lowered = text.lower()
    results: list[str] = []
    for key, translations in BUILTIN_KEYWORD_TRANSLATIONS.items():
        if key.lower() in lowered or key in text:
            for keyword in translations:
                add_unique(results, keyword)
    return results


def add_unique(items: list[str], value: Any) -> None:
    clean = str(value or "").strip()
    if clean and clean.lower() not in {item.lower() for item in items}:
        items.append(clean)


def contains_cjk(value: Any) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in str(value or ""))


def decomposed_keywords(value: Any) -> list[str]:
    text = " ".join(str(value or "").replace("!", " ").replace(".", " ").split())
    if not text or contains_cjk(text):
        return []
    lowered = text.lower()
    words = [word.strip("'\"()[]{}:,;/\\") for word in lowered.split()]
    stop = {
        "the",
        "and",
        "for",
        "with",
        "full",
        "set",
        "new",
        "men",
        "women",
        "husband",
        "hunter",
        "official",
        "limited",
        "edition",
    }
    product_terms = [
        "snapback hat",
        "snapback cap",
        "black snapback",
        "baseball cap",
        "trucker hat",
        "dad hat",
        "anniversary hat",
        "embroidered hat",
        "black cap",
    ]
    results: list[str] = []
    for phrase in product_terms:
        if all(part in words for part in phrase.split()):
            add_unique(results, phrase)
    if "snapback" in words:
        add_unique(results, "snapback hat")
        add_unique(results, "black snapback" if "black" in words or "blk" in words else "snapback cap")
    if "hat" in words or "hats" in words:
        add_unique(results, "hat")
        add_unique(results, "baseball cap")
    if "cap" in words:
        add_unique(results, "cap")
    if "perfume" in words or "fragrance" in words:
        add_unique(results, "perfume")
        add_unique(results, "fragrance")
    meaningful = [word for word in words if len(word) >= 3 and word not in stop]
    if meaningful:
        add_unique(results, " ".join(meaningful[:4]))
    if len(meaningful) >= 2:
        add_unique(results, " ".join(meaningful[-3:]))
    brandish = []
    original_words = text.split()
    for word in original_words[:5]:
        clean = word.strip("'\"()[]{}:,;/\\")
        if clean and (clean.isupper() or any(char.isdigit() for char in clean)):
            brandish.append(clean)
    if brandish:
        add_unique(results, " ".join(brandish[:3]))
        if "snapback" in words:
            add_unique(results, f"{brandish[0]} snapback")
        if "hat" in words or "hats" in words:
            add_unique(results, f"{brandish[0]} hat")
    if "concrete" in words and "jungle" in words:
        add_unique(results, "concrete jungle hat")
        add_unique(results, "concrete jungle snapback")
    if "anniversary" in words:
        add_unique(results, "anniversary snapback")
        add_unique(results, "anniversary hat")
    return results[:14]


def build_product_target_sources(root: Path) -> list[dict[str, Any]]:
    config = load_product_targets(root)
    sources: list[dict[str, Any]] = []
    for target in config.get("targets", []):
        if isinstance(target, dict) and target.get("enabled", True):
            sources.extend(sources_for_target(target))
    return sources


def sources_for_target(target: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    target_id = str(target.get("id") or "")
    platforms = normalize_platforms(target.get("platforms")) or ["Amazon"]
    platform_sequence = list(platforms)
    if "TikTok Shop" in platforms and "TikTok Video" not in platform_sequence:
        platform_sequence.insert(platform_sequence.index("TikTok Shop") + 1, "TikTok Video")
    for keyword in normalize_list(target.get("keywords"))[:12]:
        for platform in platform_sequence:
            source = product_search_source(target, platform, keyword, target_id)
            if source:
                sources.append(source)
    if "TikTok Shop" in platforms:
        sources.extend(tiktok_selection_bridge_sources_for_target(target))
    for index, url in enumerate(normalize_list(target.get("competitor_links"))):
        platform = "Amazon" if "amazon" in url.lower() else "Competitor"
        sources.append(base_source(target, {
            "id": f"target-{target_id}-competitor-{index + 1}",
            "name": f"{target.get('name')} / competitor link {index + 1}",
            "record_type": "review_insight" if platform == "Amazon" and "/dp/" in url.lower() else "hot_link",
            "source_platform": platform,
            "marketplace": platform,
            "ranking_type": "Product Target Competitor Link",
            "url": url,
            "data_category": "competitor_link",
        }))
    return sources


def tiktok_selection_bridge_sources_for_target(target: dict[str, Any]) -> list[dict[str, Any]]:
    target_id = str(target.get("id") or "")
    sources: list[dict[str, Any]] = []
    for keyword in normalize_list(target.get("keywords"))[:5]:
        encoded = quote_plus(keyword)
        for bridge in TIKTOK_SELECTION_BRIDGES:
            provider = bridge["provider"]
            payload = {
                "id": f"target-{target_id}-{provider.lower()}-bridge-{encoded[:40]}",
                "name": f"{target.get('name')} / {provider} TK data bridge / {keyword}",
                "record_type": "platform_ranking_signal",
                "source_platform": bridge["source_platform"],
                "marketplace": "TikTok Shop Intelligence",
                "ranking_type": bridge["ranking_type"],
                "url": bridge["base_url"].format(keyword=encoded),
                "keyword": keyword,
                "data_category": bridge["data_category"],
                "expected_keywords": expected_keywords(keyword),
                "selection_bridge": True,
                "bridge_provider": provider,
                "search_keyword": keyword,
                "manual_search_required": True,
                "search_instruction": bridge.get("search_instruction", ""),
                "follow_tiktok_product_links": True,
                "link_follow_policy": "Prefer product/detail/shop links on the selection platform, especially links that open TikTok Shop product pages.",
                "may_trigger_verification": True,
                "headless": False,
                "initial_wait_seconds": 18,
                "verification_wait_seconds": 900,
                "keep_open_on_gate": True,
                "keep_open_after_run": True,
                "timeout_seconds": 1020,
                "notes": (
                    f"Use {provider} as a TikTok data bridge when TikTok Shop buyer-side pages trigger verification. "
                    f"Search keyword: {keyword}. Collect product ranking, creator, video, sales/GMV, comments, and any outbound TikTok product links."
                ),
            }
            sources.append(base_source(target, payload))
    return sources


def product_search_source(target: dict[str, Any], platform: str, keyword: str, target_id: str) -> dict[str, Any] | None:
    if platform not in ALL_RESEARCH_PLATFORMS:
        return None
    platform_key = platform.lower().replace(" ", "_")
    encoded = quote_plus(keyword)
    text_platform = platform.lower()
    if platform == "Amazon":
        payload = {
            "record_type": "platform_ranking_signal",
            "source_platform": "Amazon",
            "marketplace": "Amazon",
            "ranking_type": "Product Target Keyword Search",
            "url": f"https://www.amazon.com/s?k={encoded}",
            "data_category": "amazon_keyword",
        }
    elif platform == "TikTok Shop":
        payload = {
            "record_type": "platform_ranking_signal",
            "source_platform": "TikTok Shop Buyer",
            "marketplace": "TikTok Shop",
            "ranking_type": "Buyer Product Search",
            "url": f"https://shop.tiktok.com/us/search?q={encoded}",
            "data_category": "tiktok_shop_keyword",
            "may_trigger_verification": True,
            "headless": False,
            "keep_open_after_run": True,
        }
    elif platform == "TikTok Video":
        payload = {
            "record_type": "viral_content_signal",
            "source_platform": "TikTok",
            "marketplace": "TikTok",
            "ranking_type": "TikTok Video Search",
            "url": f"https://www.tiktok.com/search?q={encoded}",
            "data_category": "tiktok_video_keyword",
            "may_trigger_verification": True,
            "headless": False,
            "keep_open_after_run": True,
        }
    elif platform == "Etsy":
        payload = {
            "record_type": "platform_ranking_signal",
            "source_platform": "Etsy",
            "marketplace": "Etsy",
            "ranking_type": "Etsy Search",
            "url": f"https://www.etsy.com/search?q={encoded}",
            "data_category": "etsy_keyword",
        }
    elif platform == "Walmart":
        payload = {
            "record_type": "platform_ranking_signal",
            "source_platform": "Walmart",
            "marketplace": "Walmart",
            "ranking_type": "Walmart Search",
            "url": f"https://www.walmart.com/search?q={encoded}",
            "data_category": "walmart_keyword",
        }
    elif platform == "eBay":
        payload = {
            "record_type": "platform_ranking_signal",
            "source_platform": "eBay",
            "marketplace": "eBay",
            "ranking_type": "eBay Search",
            "url": f"https://www.ebay.com/sch/i.html?_nkw={encoded}",
            "data_category": "ebay_keyword",
        }
    elif platform == "SHEIN":
        payload = {
            "record_type": "platform_ranking_signal",
            "source_platform": "SHEIN",
            "marketplace": "SHEIN",
            "ranking_type": "SHEIN Search",
            "url": f"https://us.shein.com/pdsearch/{encoded}/",
            "data_category": "shein_keyword",
            "may_trigger_verification": True,
        }
    elif platform == "Google Shopping":
        payload = {
            "record_type": "platform_ranking_signal",
            "source_platform": "Google Shopping",
            "marketplace": "Google Shopping",
            "ranking_type": "Google Shopping Search",
            "url": f"https://www.google.com/search?tbm=shop&q={encoded}",
            "data_category": "google_shopping_keyword",
        }
    elif platform == "YouTube":
        payload = {
            "record_type": "viral_content_signal",
            "source_platform": "YouTube",
            "marketplace": "YouTube",
            "ranking_type": "YouTube Shorts/Search",
            "url": f"https://www.youtube.com/results?search_query={encoded}+review",
            "data_category": "youtube_keyword",
        }
    elif platform == "Instagram":
        payload = {
            "record_type": "viral_content_signal",
            "source_platform": "Instagram",
            "marketplace": "Instagram",
            "ranking_type": "Instagram Reels Search",
            "url": f"https://www.google.com/search?q=site%3Ainstagram.com%2Freel+{encoded}",
            "data_category": "instagram_keyword",
        }
    else:
        return None
    payload.update(
        {
            "id": f"target-{target_id}-{platform_key}-{quote_plus(keyword)[:44]}",
            "name": f"{target.get('name')} / {platform} / {keyword}",
            "keyword": keyword,
            "expected_keywords": expected_keywords(keyword),
        }
    )
    return base_source(target, payload)


def expected_keywords(keyword: str) -> list[str]:
    parts = [part for part in keyword.replace("+", " ").split() if len(part) >= 3]
    return parts[:3] or [keyword]


def seed_product_target_collection_jobs(root: Path, target: dict[str, Any]) -> None:
    for source in sources_for_target(target):
        source_platform = source.get("source_platform") or source.get("marketplace") or ""
        marketplace = source.get("marketplace") or source_platform
        selection_bridge = bool(source.get("selection_bridge", False))
        platform_instruction = (
            "Open the already logged-in FastMoss / Kalodata page in Chrome or BitBrowser, search the keyword inside the tool, collect ranking rows, product cards, creators, videos, GMV/sales, comments, and visible TikTok Shop product links. Keep the browser open if verification appears."
            if selection_bridge
            else "Open this ecommerce-platform URL in the already logged-in Chrome or BitBrowser tab, wait until product cards/ranking rows load, collect visible product/video/shop cards, then classify same-product matches against the target and reference image."
        )
        fields = {
            "collection_target": source.get("name"),
            "source_platform": source_platform,
            "marketplace": marketplace,
            "platform_list": source_platform,
            "product_name": target.get("name"),
            "product_family": target.get("product_family"),
            "product_target_id": target.get("id"),
            "product_target_name": target.get("name"),
            "keyword": source.get("keyword"),
            "url": source.get("url"),
            "data_category": source.get("data_category"),
            "ranking_type": source.get("ranking_type"),
            "source_status": "pending_collection",
            "collection_status": "pending",
            "collection_mode": "selection_platform_bridge" if selection_bridge else "visible_browser_capture",
            "search_keyword": source.get("search_keyword") or source.get("keyword"),
            "manual_search_required": bool(source.get("manual_search_required", False)),
            "search_instruction": source.get("search_instruction") or "",
            "record_type_to_collect": source.get("record_type"),
            "requires_login": bool(source.get("requires_login", False)),
            "may_trigger_verification": bool(source.get("may_trigger_verification", False)),
            "selection_bridge": selection_bridge,
            "bridge_provider": source.get("bridge_provider") or "",
            "follow_tiktok_product_links": bool(source.get("follow_tiktok_product_links", False)),
            "keep_open_on_gate": bool(source.get("keep_open_on_gate", False)),
            "keep_open_after_run": bool(source.get("keep_open_after_run", False)),
            "verification_wait_seconds": int(source.get("verification_wait_seconds", 0) or 0),
            "open_instruction": platform_instruction,
            "capture_goal": "product_cards ranking_rows creator_rows video_rows comments outbound_product_links same_product_match",
            "minimum_fields_required": "product_name, product_url, price, rank/sales/gmv if visible, image_url or screenshot, source_platform, keyword",
            "next_step": (
                platform_instruction
            ),
        }
        append_record(
            root,
            IntakeRecord(
                record_type="collection_job",
                fields=fields,
                raw_text=json.dumps(fields, ensure_ascii=False),
                source="product_target_setup",
                score={"priority": 65},
                director_notes=["Search job created from product target keyword expansion."],
            ),
        )


def build_tiktok_buyer_product_target_sources(root: Path) -> list[dict[str, Any]]:
    config = load_product_targets(root)
    sources: list[dict[str, Any]] = []
    for target in config.get("targets", []):
        if not isinstance(target, dict) or not target.get("enabled", True):
            continue
        platforms = " ".join(str(item).lower() for item in target.get("platforms", []))
        if "tiktok" not in platforms and "tk" not in platforms:
            continue
        sources.extend(tiktok_buyer_sources_for_target(target))
    return sources


def build_tiktok_selection_bridge_product_target_sources(root: Path) -> list[dict[str, Any]]:
    config = load_product_targets(root)
    sources: list[dict[str, Any]] = []
    for target in config.get("targets", []):
        if not isinstance(target, dict) or not target.get("enabled", True):
            continue
        platforms = normalize_platforms(target.get("platforms"))
        if "TikTok Shop" not in platforms:
            continue
        sources.extend(tiktok_selection_bridge_sources_for_target(target))
    return sources


def tiktok_buyer_sources_for_target(target: dict[str, Any]) -> list[dict[str, Any]]:
    target_id = str(target.get("id") or "")
    sources: list[dict[str, Any]] = []
    buyer_links = [
        url
        for url in normalize_list(target.get("competitor_links"))
        if is_tiktok_buyer_url(url)
    ]
    for index, url in enumerate(buyer_links):
        sources.append(tiktok_buyer_base_source(target, {
            "id": f"target-{target_id}-tiktok-buyer-link-{index + 1}",
            "name": f"{target.get('name')} / TikTok buyer video-shop competitor link {index + 1}",
            "url": url,
            "data_category": "buyer_video_shop_competitor",
            "collection_goal": "buyer_video_shop_competitors",
            "entry_type": "creator_video_product_card_or_shop_link",
            "max_clicks": 8,
        }))
    for keyword in normalize_list(target.get("keywords"))[:5]:
        sources.append(tiktok_buyer_base_source(target, {
            "id": f"target-{target_id}-tiktok-video-search-{quote_plus(keyword)[:40]}",
            "name": f"{target.get('name')} / TikTok video search / {keyword}",
            "url": f"https://www.tiktok.com/search?q={quote_plus(keyword)}",
            "keyword": keyword,
            "record_type": "viral_content_signal",
            "data_category": "buyer_video_shop_competitor",
            "collection_goal": "buyer_video_search_to_shop_competitors",
            "entry_type": "buyer_video_search",
            "max_clicks": 8,
        }))
    if not sources:
        sources.append(tiktok_buyer_base_source(target, {
            "id": f"target-{target_id}-tiktok-buyer-entry",
            "name": f"{target.get('name')} / TikTok buyer-side shop entry",
            "url": "https://shop.tiktok.com/us?source=product_detail&enter_method=left_panel_logo&first_entrance=video_detail&first_entrance_position=product_card&first_entrance_tt_scene=tt_seo",
            "data_category": "buyer_video_shop_competitor",
            "collection_goal": "buyer_video_shop_competitors",
            "entry_type": "buyer_shop_video_entry",
            "max_clicks": 8,
        }))
    return sources


def tiktok_buyer_base_source(target: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    return {
        **payload,
        "enabled": True,
        "record_type": payload.get("record_type") or "platform_ranking_signal",
        "source_platform": "TikTok Shop Buyer",
        "marketplace": "TikTok Shop",
        "product_target_id": str(target.get("id") or ""),
        "product_target_name": str(target.get("name") or ""),
        "product_family": str(target.get("product_family") or target.get("name") or ""),
        "reference_image": str(target.get("reference_image") or ""),
        "monitoring_scope": "product_target",
        "requires_login": True,
        "may_trigger_verification": True,
        "headless": False,
        "incognito": True,
        "initial_wait_seconds": 18,
        "verification_wait_seconds": 900,
        "keep_open_on_gate": True,
        "keep_open_after_run": True,
        "timeout_seconds": 1020,
        "notes": "Buyer-side TikTok video/profile/product-card/shop collection for same-product competitor discovery. Do not use seller center for product research.",
    }


def is_tiktok_buyer_url(url: str) -> bool:
    hostname = (urlparse(str(url or "")).hostname or "").lower()
    return "tiktok.com" in hostname


def base_source(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    merged = {
        "enabled": True,
        "requires_login": False,
        "monitoring_scope": "product_target",
        "product_target_id": target.get("id"),
        "product_target_name": target.get("name"),
        "product_family": target.get("product_family") or target.get("name"),
        "reference_image": target.get("reference_image", ""),
        "market": target.get("market", "US"),
        "notes": target.get("notes", ""),
    }
    merged.update(source)
    return merged
