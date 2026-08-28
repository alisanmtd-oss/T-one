from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REGISTRY_PATH = Path("config") / "platform_digitization_registry.json"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_platform_id(value: Any) -> str:
    text = str(value or "").strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    raw = str(value or "").strip()
    if not normalized and not raw:
        return "unknown"
    canonical = {
        "douyin_ecommerce",
        "douyin",
        "kuaishou_shop",
        "kuaishou",
        "xiaohongshu",
        "wechat_channels",
        "weixin_channels",
        "taobao_tmall",
        "jd",
        "jingdong",
        "pinduoduo",
        "pdd",
        "1688",
    }
    if normalized in canonical:
        if normalized == "weixin_channels":
            return "wechat_channels"
        if normalized == "jingdong":
            return "jd"
        if normalized == "pdd":
            return "pinduoduo"
        return normalized
    if any(token in raw for token in ["抖音电商", "抖店", "抖音小店"]):
        return "douyin_ecommerce"
    if raw == "抖音" or "douyin" in normalized:
        return "douyin"
    if any(token in raw for token in ["快手小店", "快手电商"]):
        return "kuaishou_shop"
    if raw == "快手" or "kuaishou" in normalized or "kwai" in normalized:
        return "kuaishou"
    if "小红书" in raw or "xiaohongshu" in normalized or "rednote" in normalized:
        return "xiaohongshu"
    if any(token in raw for token in ["视频号", "微信小店"]):
        return "wechat_channels"
    if "wechat_channels" in normalized or "weixin_channels" in normalized:
        return "wechat_channels"
    if any(token in raw for token in ["淘宝", "天猫"]):
        return "taobao_tmall"
    if "taobao" in normalized or "tmall" in normalized or "tao_bao" in normalized:
        return "taobao_tmall"
    if "京东" in raw or normalized in {"jd", "jingdong"} or "jing_dong" in normalized:
        return "jd"
    if "拼多多" in raw or "pinduoduo" in normalized or normalized == "pdd":
        return "pinduoduo"
    if "1688" in normalized or "阿里巴巴中国站" in raw or "阿里巴巴国内站" in raw:
        return "1688"
    if "tiktok_shop" in normalized or "tik_tok_shop" in normalized or normalized in {"tt_shop", "tk_shop"}:
        return "tiktok_shop"
    if "tiktok" in normalized or "tik_tok" in normalized:
        return "tiktok_shop"
    if "amazon" in normalized or normalized in {"amz"}:
        return "amazon"
    if "shein" in normalized:
        return "shein"
    if "shopee" in normalized:
        return "shopee"
    if "lazada" in normalized:
        return "lazada"
    if "walmart" in normalized:
        return "walmart"
    if "ebay" in normalized:
        return "ebay"
    if "etsy" in normalized:
        return "etsy"
    if "aliexpress" in normalized or "ali_express" in normalized:
        return "aliexpress"
    if "rakuten" in normalized:
        return "rakuten"
    if "emag" in normalized or "e_mag" in normalized:
        return "emag"
    if "coupang" in normalized:
        return "coupang"
    if "wildberries" in normalized or "wild_berries" in normalized:
        return "wildberries"
    if "ozon" in normalized:
        return "ozon"
    if "shopify" in normalized:
        return "shopify"
    if "woocommerce" in normalized or "woo_commerce" in normalized:
        return "woocommerce"
    return normalized


def load_platform_digitization_registry(root: Path, *, strict: bool = False) -> dict[str, Any]:
    path = root / REGISTRY_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        if strict:
            raise
        return {}
    return payload if isinstance(payload, dict) else {}


def platform_definitions_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in _safe_list(registry.get("platforms")):
        if not isinstance(item, dict):
            continue
        platform_id = normalize_platform_id(item.get("platform_id") or item.get("label"))
        if platform_id:
            result[platform_id] = item
    return result


def find_platform_definition(registry: dict[str, Any], value: Any) -> dict[str, Any] | None:
    by_id = platform_definitions_by_id(registry)
    platform_id = normalize_platform_id(value)
    if platform_id in by_id:
        return by_id[platform_id]
    text = str(value or "").strip().lower()
    for item in by_id.values():
        label = str(item.get("label") or "").strip().lower()
        if label and label in text:
            return item
    return None


def platform_digitization_snapshot(root: Path) -> dict[str, Any]:
    registry = load_platform_digitization_registry(root)
    by_id = platform_definitions_by_id(registry)
    return {
        "schema_version": registry.get("schema_version"),
        "updated_at": registry.get("updated_at"),
        "truth_policy": registry.get("truth_policy") if isinstance(registry.get("truth_policy"), dict) else {},
        "platform_count": len(by_id),
        "platform_ids": sorted(by_id),
        "registry_path": str(REGISTRY_PATH).replace("\\", "/"),
    }


def platform_card_metric_keys(registry: dict[str, Any], platform: Any) -> list[str]:
    definition = find_platform_definition(registry, platform) or {}
    keys = definition.get("default_card_metric_keys")
    if isinstance(keys, list) and keys:
        return [str(item) for item in keys if str(item or "").strip()]
    defaults = registry.get("default_dashboard_metrics")
    if isinstance(defaults, list):
        return [str(item.get("key")) for item in defaults if isinstance(item, dict) and item.get("key")]
    return ["revenue", "orders_units", "parent_skus", "traffic", "returns_refunds", "settlement", "fees"]


def platform_supports_metric_by_default(registry: dict[str, Any], platform: Any, metric_key: str) -> bool:
    definition = find_platform_definition(registry, platform) or {}
    blocked = {str(item) for item in _safe_list(definition.get("explicitly_not_default"))}
    return metric_key not in blocked


def validate_platform_digitization_registry(root: Path) -> list[str]:
    errors: list[str] = []
    registry = load_platform_digitization_registry(root, strict=True)
    if not registry.get("truth_policy", {}).get("no_fake_connection"):
        errors.append("truth_policy.no_fake_connection must be true")
    platforms = _safe_list(registry.get("platforms"))
    if len(platforms) < 10:
        errors.append("platforms must include the main marketplace set")
    seen: set[str] = set()
    for item in platforms:
        if not isinstance(item, dict):
            errors.append("platform entry must be an object")
            continue
        platform_id = normalize_platform_id(item.get("platform_id"))
        if not platform_id or platform_id == "unknown":
            errors.append("platform_id is required")
            continue
        if platform_id in seen:
            errors.append(f"duplicate platform_id: {platform_id}")
        seen.add(platform_id)
        if not item.get("primary_objects"):
            errors.append(f"{platform_id}: primary_objects required")
        if not item.get("dashboard_groups"):
            errors.append(f"{platform_id}: dashboard_groups required")
        sku_policy = item.get("sku_policy") if isinstance(item.get("sku_policy"), dict) else {}
        if not sku_policy.get("count_parent_only"):
            errors.append(f"{platform_id}: sku_policy.count_parent_only must be true")
        if str(item.get("digitization_status") or "") not in {
            "schema_defined_pending_evidence",
            "imported_local_statement",
            "manual_owner_verified",
            "authorized_api_read",
            "authorized_browser_read",
            "blocked_missing_authorization",
        }:
            errors.append(f"{platform_id}: invalid digitization_status")
        forbidden_status_words = {"connected", "running", "synced"}
        serialized = json.dumps(item, ensure_ascii=False).lower()
        for word in forbidden_status_words:
            if f'"{word}"' in serialized:
                errors.append(f"{platform_id}: must not claim {word}")
    shein = find_platform_definition(registry, "shein") or {}
    if "ad_roas" not in set(_safe_list(shein.get("explicitly_not_default"))):
        errors.append("shein: ad_roas must be explicitly not default")
    tiktok = find_platform_definition(registry, "tiktok shop") or {}
    if str(tiktok.get("live_policy") or "") != "first_class_metric_group":
        errors.append("tiktok_shop: live_policy must be first_class_metric_group")
    if "video" not in set(_safe_list(tiktok.get("primary_objects"))):
        errors.append("tiktok_shop: video object required")
    tiktok_objects = set(_safe_list(tiktok.get("primary_objects")))
    for required in {"affiliate_creator", "creator_profile", "affiliate_plan", "sample_request", "authorized_creator_content"}:
        if required not in tiktok_objects:
            errors.append(f"tiktok_shop: {required} object required")
    tiktok_keys = set(platform_card_metric_keys(registry, "tiktok shop"))
    for required in {"affiliate_gmv_commission", "creator_collaboration", "creator_samples_content", "live_duration"}:
        if required not in tiktok_keys:
            errors.append(f"tiktok_shop: {required} card metric required")
    return errors
