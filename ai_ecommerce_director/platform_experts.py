from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Mapping


REGISTRY_PATH = Path("config") / "platform_expert_registry.json"
REQUIRED_EXPERT_IDS = {
    "expert-amazon-marketplace",
    "expert-ebay-marketplace",
    "expert-etsy-marketplace",
    "expert-ozon-marketplace",
    "expert-coupang-marketplace",
    "expert-rakuten-ichiba-marketplace",
    "expert-emag-marketplace",
    "expert-mercado-libre-marketplace",
    "expert-tiktok-shop",
    "expert-shein-marketplace",
    "expert-lazada-marketplace",
    "expert-shopee-marketplace",
    "expert-walmart-marketplace",
    "expert-aliexpress-marketplace",
    "expert-google-independent-commerce",
    "expert-b2b-export-sales",
    "expert-b2b-platform-sales",
    "expert-b2b-outbound-development",
    "expert-social-content-growth",
}
REQUIRED_ROUTE_DIMENSIONS = {"platform", "country_site", "store_model", "ownership"}
REQUIRED_MODEL_SLOTS = {"reasoning", "copy", "image", "video", "ads", "data"}
FORBIDDEN_SECRET_KEY_PARTS = {
    "api_key",
    "apikey",
    "password",
    "secret",
    "access_token",
    "refresh_token",
    "private_key",
}
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{12,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{12,}\b", re.IGNORECASE),
)
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
NON_EXECUTABLE_SITE_CODES = {"SEA", "SOUTHEAST_ASIA", "SOUTHEAST ASIA"}
OFFICIAL_FULL_MANAGED_MODES = {
    "official_full_managed",
    "supply_obm_official_full_managed",
}

PLATFORM_ALIASES = {
    "amazon_marketplace": "amazon",
    "tiktok_shop": "tiktok",
    "tiktokshop": "tiktok",
    "shein_marketplace": "shein",
    "google": "google_ads",
    "merchant_center": "google_merchant_center",
    "google_merchant": "google_merchant_center",
    "b2b": "b2b_export",
    "b2b_marketplace": "b2b_platform",
    "b2b_platform_sales": "b2b_platform",
    "customer_development": "b2b_outbound",
    "outbound": "b2b_outbound",
    "social_media": "tiktok",
}

# These aliases are intentionally limited to explicit platform names.  Generic
# words such as "商品", "店铺" or "广告" must never silently select TikTok (or
# any other marketplace) for an unbound conversation.
PLATFORM_CHAT_INTENT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "platform": "aliexpress",
        "display_name": "AliExpress 速卖通",
        "expert_id": "expert-aliexpress-marketplace",
        "aliases": ("全球速卖通", "速卖通", "aliexpress", "ali express"),
    },
    {
        "platform": "shopee",
        "display_name": "Shopee 虾皮",
        "expert_id": "expert-shopee-marketplace",
        "aliases": ("shopee", "虾皮"),
    },
    {
        "platform": "walmart",
        "display_name": "Walmart 沃尔玛",
        "expert_id": "expert-walmart-marketplace",
        "aliases": ("walmart", "沃尔玛"),
    },
    {
        "platform": "tiktok",
        "display_name": "TikTok Shop",
        "expert_id": "expert-tiktok-shop",
        "aliases": ("tiktok shop", "tiktokshop", "tk shop", "tk小店"),
    },
    {
        "platform": "amazon",
        "display_name": "Amazon",
        "expert_id": "expert-amazon-marketplace",
        "aliases": ("amazon", "亚马逊"),
    },
    {
        "platform": "shein",
        "display_name": "SHEIN",
        "expert_id": "expert-shein-marketplace",
        "aliases": ("shein", "希音"),
    },
    {
        "platform": "lazada",
        "display_name": "Lazada",
        "expert_id": "expert-lazada-marketplace",
        "aliases": ("lazada",),
    },
    {
        "platform": "etsy",
        "display_name": "Etsy",
        "expert_id": "expert-etsy-marketplace",
        "aliases": ("etsy",),
    },
    {
        "platform": "ebay",
        "display_name": "eBay",
        "expert_id": "expert-ebay-marketplace",
        "aliases": ("ebay", "e-bay"),
    },
    {
        "platform": "ozon",
        "display_name": "Ozon",
        "expert_id": "expert-ozon-marketplace",
        "aliases": ("ozon", "озон"),
    },
    {
        "platform": "coupang",
        "display_name": "Coupang 酷澎",
        "expert_id": "expert-coupang-marketplace",
        "aliases": ("coupang", "酷澎"),
    },
    {
        "platform": "rakuten",
        "display_name": "Rakuten 乐天市场",
        "expert_id": "expert-rakuten-ichiba-marketplace",
        "aliases": ("rakuten ichiba", "rakuten", "乐天市场", "乐天"),
    },
    {
        "platform": "emag",
        "display_name": "eMAG",
        "expert_id": "expert-emag-marketplace",
        "aliases": ("emag", "e-mag"),
    },
    {
        "platform": "mercado_libre",
        "display_name": "Mercado Libre",
        "expert_id": "expert-mercado-libre-marketplace",
        "aliases": ("mercado libre", "mercadolibre", "美客多"),
    },
)

GENERIC_CHAT_PLATFORM_SCOPES = {
    "",
    "general",
    "generic",
    "new_conversation",
    "project_workflow",
    "workstream",
}

COUNTRY_SITE_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("US", ("美国站", "美国", " us ", " usa ")),
    ("CA", ("加拿大站", "加拿大", " ca ")),
    ("MX", ("墨西哥站", "墨西哥", " mx ")),
    ("GB", ("英国站", "英国", " uk ", " gb ")),
    ("SG", ("新加坡站", "新加坡", " sg ")),
    ("MY", ("马来西亚站", "马来西亚", " my ")),
    ("TH", ("泰国站", "泰国", " th ")),
    ("VN", ("越南站", "越南", " vn ")),
    ("PH", ("菲律宾站", "菲律宾", " ph ")),
    ("ID", ("印尼站", "印度尼西亚", "印尼", " id ")),
    ("TW", ("台湾站", "台湾", " tw ")),
    ("BR", ("巴西站", "巴西", " br ")),
    ("KR", ("韩国站", "韩国", " kr ")),
    ("JP", ("日本站", "日本", " jp ")),
    ("RO", ("罗马尼亚站", "罗马尼亚", "罗马尼亚市场", " ro ")),
    ("HU", ("匈牙利站", "匈牙利", "匈牙利市场", " hu ")),
    ("BG", ("保加利亚站", "保加利亚", "保加利亚市场", " bg ")),
)
STORE_MODEL_ALIASES = {
    "local_store": "local",
    "local_seller": "local",
    "cross_border_seller": "cross_border",
    "semi_managed_crossborder": "semi_managed",
    "semi_managed_local": "semi_managed",
}
OWNERSHIP_ALIASES = {
    "self_store": "self_owned",
    "platform_store": "teelab_owned",
    "teelab_platform": "teelab_owned",
}
MODEL_SLOT_BY_CAPABILITY = {
    "listing": "copy",
    "customer_service": "copy",
    "outreach": "copy",
    "activity": "ads",
    "affiliate": "ads",
    "ads": "ads",
    "image": "image",
    "creative": "image",
    "video": "video",
    "editing": "video",
    "orders": "data",
    "inventory": "data",
    "finance": "data",
    "competitor": "data",
    "analytics": "data",
    "attribution": "data",
    "lead_generation": "data",
    "enrichment": "data",
    "crm": "data",
    "fulfillment": "reasoning",
    "learning": "reasoning",
}


class UnsupportedExpertRoute(ValueError):
    """Raised when a route is a known non-executable business mode or region."""


def _normalise_id(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _normalise_platform(value: Any) -> str:
    platform = _normalise_id(value)
    return PLATFORM_ALIASES.get(platform, platform)


def _normalise_store_model(value: Any) -> str:
    mode = _normalise_id(value)
    return STORE_MODEL_ALIASES.get(mode, mode)


def _normalise_ownership(value: Any) -> str:
    ownership = _normalise_id(value)
    return OWNERSHIP_ALIASES.get(ownership, ownership)


def _explicit_alias_matches(text: str, alias: str) -> list[int]:
    lowered = text.casefold()
    candidate = alias.casefold()
    if not candidate:
        return []
    if re.fullmatch(r"[a-z0-9 -]+", candidate):
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(candidate)}(?![a-z0-9])")
        return [match.start() for match in pattern.finditer(lowered)]
    matches: list[int] = []
    start = 0
    while True:
        index = lowered.find(candidate, start)
        if index < 0:
            return matches
        matches.append(index)
        start = index + len(candidate)


def _platform_mention_is_negated(text: str, index: int) -> bool:
    clause_start = 0
    for delimiter in ("。", "！", "？", ";", "；", "\n", ",", "，"):
        position = text.rfind(delimiter, 0, index)
        if position >= 0:
            clause_start = max(clause_start, position + len(delimiter))
    prefix = text[clause_start:index].casefold()[-24:]
    return any(
        marker in prefix
        for marker in (
            "不是",
            "并非",
            "不要",
            "别用",
            "不能按",
            "不按",
            "排除",
            "not ",
            "instead of ",
        )
    )


def detect_explicit_platform_intents(message: str) -> list[dict[str, str]]:
    """Return unnegated, explicitly named platforms in mention order.

    The result is deliberately independent from the current task defaults so a
    generic conversation cannot inherit an unrelated marketplace by accident.
    """

    text = str(message or "")
    detected: list[tuple[int, dict[str, str]]] = []
    seen: set[str] = set()
    for spec in PLATFORM_CHAT_INTENT_SPECS:
        best_index: int | None = None
        for alias in spec["aliases"]:
            for index in _explicit_alias_matches(text, str(alias)):
                if not _platform_mention_is_negated(text, index):
                    best_index = index if best_index is None else min(best_index, index)
        platform = str(spec["platform"])
        if best_index is None or platform in seen:
            continue
        seen.add(platform)
        detected.append(
            (
                best_index,
                {
                    "platform": platform,
                    "display_name": str(spec["display_name"]),
                    "expert_id": str(spec["expert_id"]),
                },
            )
        )
    return [item for _, item in sorted(detected, key=lambda pair: pair[0])]


def detect_explicit_platform_intent(message: str) -> dict[str, str] | None:
    """Return one unambiguous explicit platform, otherwise ``None``."""

    intents = detect_explicit_platform_intents(message)
    return intents[0] if len(intents) == 1 else None


def platform_scope_is_generic(value: Any) -> bool:
    return _normalise_id(value) in GENERIC_CHAT_PLATFORM_SCOPES


def detect_country_site(message: str) -> str:
    text = f" {str(message or '').casefold()} "
    for code, aliases in COUNTRY_SITE_ALIASES:
        if any(alias.casefold() in text for alias in aliases):
            return code
    return ""


def infer_platform_capability(message: str) -> str:
    lowered = str(message or "").casefold()
    capability_hints = (
        ("ads", ("广告", "投流", "roas", "roi", "cpa", "gmv max", "ads")),
        ("activity", ("活动", "促销", "优惠券", "coupon", "campaign")),
        ("orders", ("订单", "order")),
        ("inventory", ("库存", "inventory", "stock")),
        ("customer_service", ("客服", "售后", "退款", "退货", "投诉", "差评")),
        ("competitor", ("竞品", "同行", "竞争对手", "competitor")),
        ("affiliate", ("达人", "联盟", "affiliate", "creator")),
        ("fulfillment", ("物流", "履约", "发货", "shipping", "fulfillment")),
    )
    for capability, hints in capability_hints:
        if any(hint in lowered for hint in hints):
            return capability
    return "listing"


def _list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and item.strip()]


def _secret_errors(value: Any, path: str = "registry") -> list[str]:
    errors: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            normalised_key = key_text.strip().lower()
            if any(part in normalised_key for part in FORBIDDEN_SECRET_KEY_PARTS):
                errors.append(f"{path}.{key_text}: secret-bearing fields are forbidden")
            errors.extend(_secret_errors(item, f"{path}.{key_text}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_secret_errors(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        if any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
            errors.append(f"{path}: secret-like value is forbidden")
    return errors


def validate_platform_expert_registry(registry: Mapping[str, Any]) -> list[str]:
    """Return deterministic schema and policy errors without mutating the registry."""

    errors: list[str] = []
    if not isinstance(registry, Mapping):
        return ["registry: expected an object"]
    if registry.get("schema_version") != 1:
        errors.append("registry.schema_version: expected 1")
    if set(_list_of_strings(registry.get("required_route_dimensions"))) != REQUIRED_ROUTE_DIMENSIONS:
        errors.append("registry.required_route_dimensions: incomplete route contract")
    if set(_list_of_strings(registry.get("required_model_slots"))) != REQUIRED_MODEL_SLOTS:
        errors.append("registry.required_model_slots: expected reasoning/copy/image/video/ads/data")
    errors.extend(_secret_errors(registry))

    experts = registry.get("experts")
    if not isinstance(experts, list) or not experts:
        return errors + ["registry.experts: expected a non-empty list"]

    seen_ids: set[str] = set()
    for index, expert in enumerate(experts):
        path = f"registry.experts[{index}]"
        if not isinstance(expert, Mapping):
            errors.append(f"{path}: expected an object")
            continue
        expert_id = str(expert.get("id") or "").strip()
        if not SAFE_ID.fullmatch(expert_id):
            errors.append(f"{path}.id: invalid or missing expert id")
        elif expert_id in seen_ids:
            errors.append(f"{path}.id: duplicate expert id {expert_id}")
        seen_ids.add(expert_id)

        platforms = {_normalise_platform(item) for item in _list_of_strings(expert.get("platforms"))}
        if not platforms:
            errors.append(f"{path}.platforms: expected at least one platform")

        modules = set(_list_of_strings(expert.get("job_modules")))
        if not modules:
            errors.append(f"{path}.job_modules: expected at least one module")
        if "learning" not in modules:
            errors.append(f"{path}.job_modules: learning is required")

        routing = expert.get("routing")
        if not isinstance(routing, Mapping):
            errors.append(f"{path}.routing: expected an object")
        else:
            dimensions = set(_list_of_strings(routing.get("required_dimensions")))
            if dimensions != REQUIRED_ROUTE_DIMENSIONS:
                errors.append(f"{path}.routing.required_dimensions: incomplete route contract")
            blocked = {_normalise_store_model(item) for item in _list_of_strings(routing.get("blocked_store_models"))}
            if platforms.intersection({"tiktok", "shein"}) and "official_full_managed" not in blocked:
                errors.append(f"{path}.routing.blocked_store_models: official_full_managed must be blocked")
            routes = routing.get("routes")
            if not isinstance(routes, list) or not routes:
                errors.append(f"{path}.routing.routes: expected at least one route")
            else:
                for route_index, route in enumerate(routes):
                    route_path = f"{path}.routing.routes[{route_index}]"
                    if not isinstance(route, Mapping):
                        errors.append(f"{route_path}: expected an object")
                        continue
                    route_platform = _normalise_platform(route.get("platform"))
                    if route_platform not in platforms:
                        errors.append(f"{route_path}.platform: not declared by expert")
                    countries = {str(item).strip().upper() for item in _list_of_strings(route.get("country_sites"))}
                    if not countries:
                        errors.append(f"{route_path}.country_sites: expected at least one site")
                    if countries.intersection(NON_EXECUTABLE_SITE_CODES):
                        errors.append(f"{route_path}.country_sites: broad Southeast Asia routes are forbidden")
                    store_models = {_normalise_store_model(item) for item in _list_of_strings(route.get("store_models"))}
                    if not store_models:
                        errors.append(f"{route_path}.store_models: expected at least one mode")
                    if store_models.intersection(OFFICIAL_FULL_MANAGED_MODES):
                        errors.append(f"{route_path}.store_models: official full managed modes are non-executable")
                    ownerships = {_normalise_ownership(item) for item in _list_of_strings(route.get("ownerships"))}
                    if not ownerships:
                        errors.append(f"{route_path}.ownerships: expected at least one ownership")

        capabilities = expert.get("default_capabilities")
        if not isinstance(capabilities, Mapping):
            errors.append(f"{path}.default_capabilities: expected an object")
        else:
            for capability_kind in ("skills", "agents", "tools"):
                if not _list_of_strings(capabilities.get(capability_kind)):
                    errors.append(f"{path}.default_capabilities.{capability_kind}: expected at least one id")

        evidence = expert.get("evidence")
        if not isinstance(evidence, Mapping) or not _list_of_strings(evidence.get("registry_refs")):
            errors.append(f"{path}.evidence.registry_refs: expected at least one evidence reference")

        slots = expert.get("model_slots")
        if not isinstance(slots, Mapping) or set(slots) != REQUIRED_MODEL_SLOTS:
            errors.append(f"{path}.model_slots: expected exactly reasoning/copy/image/video/ads/data")
        else:
            for slot_id in sorted(REQUIRED_MODEL_SLOTS):
                slot = slots.get(slot_id)
                slot_path = f"{path}.model_slots.{slot_id}"
                if not isinstance(slot, Mapping):
                    errors.append(f"{slot_path}: expected an object")
                    continue
                if not _list_of_strings(slot.get("task_types")):
                    errors.append(f"{slot_path}.task_types: expected at least one task type")
                candidates = slot.get("candidates")
                if not isinstance(candidates, list) or not candidates:
                    errors.append(f"{slot_path}.candidates: expected at least one provider")
                    continue
                priorities: set[int] = set()
                for candidate_index, candidate in enumerate(candidates):
                    candidate_path = f"{slot_path}.candidates[{candidate_index}]"
                    if not isinstance(candidate, Mapping):
                        errors.append(f"{candidate_path}: expected an object")
                        continue
                    provider_id = str(candidate.get("provider_id") or "").strip()
                    if not SAFE_ID.fullmatch(provider_id):
                        errors.append(f"{candidate_path}.provider_id: invalid provider id")
                    priority = candidate.get("priority")
                    if not isinstance(priority, int) or priority < 1:
                        errors.append(f"{candidate_path}.priority: expected a positive integer")
                    elif priority in priorities:
                        errors.append(f"{candidate_path}.priority: duplicate priority {priority}")
                    priorities.add(priority) if isinstance(priority, int) else None

        learning = expert.get("learning_loop")
        if not isinstance(learning, Mapping):
            errors.append(f"{path}.learning_loop: expected an object")
        else:
            for key in ("inputs", "outputs", "review_triggers"):
                if not _list_of_strings(learning.get(key)):
                    errors.append(f"{path}.learning_loop.{key}: expected at least one value")

        boundaries = expert.get("execution_boundaries")
        if not isinstance(boundaries, Mapping):
            errors.append(f"{path}.execution_boundaries: expected an object")
        else:
            for key in ("read_only_without_authorization", "confirmation_required", "always_blocked"):
                if not _list_of_strings(boundaries.get(key)):
                    errors.append(f"{path}.execution_boundaries.{key}: expected at least one value")

    missing_experts = REQUIRED_EXPERT_IDS - seen_ids
    if missing_experts:
        errors.append(f"registry.experts: missing required experts {sorted(missing_experts)}")
    return errors


def load_platform_expert_registry(root: Path) -> dict[str, Any]:
    """Load and validate the platform expert registry."""

    path = root / REGISTRY_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Platform expert registry must be a JSON object")
    errors = validate_platform_expert_registry(payload)
    if errors:
        raise ValueError("Invalid platform expert registry: " + "; ".join(errors))
    return copy.deepcopy(payload)


def list_platform_experts(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return experts sorted for display without exposing mutable registry objects."""

    experts = [copy.deepcopy(item) for item in registry.get("experts", []) if isinstance(item, Mapping)]
    return sorted(experts, key=lambda item: (-int(item.get("sort_order") or 0), str(item.get("id") or "")))


def _validate_request_route(country_site: str, store_model: str) -> None:
    site = str(country_site or "").strip().upper()
    mode = _normalise_store_model(store_model)
    if site in NON_EXECUTABLE_SITE_CODES:
        raise UnsupportedExpertRoute("Southeast Asia is a grouping; use SG/MY/TH/VN/PH/ID")
    if mode in OFFICIAL_FULL_MANAGED_MODES or mode.endswith("official_full_managed"):
        raise UnsupportedExpertRoute("official_full_managed is recognition-only and cannot be routed")


def _route_matches(
    route: Mapping[str, Any],
    *,
    platform: str,
    country_site: str,
    store_model: str,
    ownership: str,
) -> bool:
    if _normalise_platform(route.get("platform")) != platform:
        return False
    if country_site:
        sites = {str(item).strip().upper() for item in _list_of_strings(route.get("country_sites"))}
        if "GLOBAL" not in sites and country_site not in sites:
            return False
    if store_model:
        modes = {_normalise_store_model(item) for item in _list_of_strings(route.get("store_models"))}
        if store_model not in modes:
            return False
    if ownership:
        ownerships = {_normalise_ownership(item) for item in _list_of_strings(route.get("ownerships"))}
        if ownership not in ownerships:
            return False
    return True


def recommend_model_slot(expert: Mapping[str, Any], task_type: str) -> dict[str, Any]:
    """Return the model capability slot for a job module or explicit slot id."""

    requested = _normalise_id(task_type)
    slot_id = requested if requested in REQUIRED_MODEL_SLOTS else MODEL_SLOT_BY_CAPABILITY.get(requested, "reasoning")
    slots = expert.get("model_slots") if isinstance(expert, Mapping) else None
    slot = slots.get(slot_id) if isinstance(slots, Mapping) else None
    if not isinstance(slot, Mapping):
        return {"slot": slot_id, "task_types": [], "candidates": []}
    return {
        "slot": slot_id,
        "task_types": copy.deepcopy(_list_of_strings(slot.get("task_types"))),
        "candidates": copy.deepcopy(slot.get("candidates") or []),
    }


def recommend_platform_experts(
    registry: Mapping[str, Any],
    *,
    platform: str,
    capability: str,
    country_site: str = "",
    store_model: str = "",
    ownership: str = "",
) -> list[dict[str, Any]]:
    """Recommend installable experts and a model slot for one isolated route."""

    normalised_platform = _normalise_platform(platform)
    normalised_capability = _normalise_id(capability)
    normalised_site = str(country_site or "").strip().upper()
    normalised_mode = _normalise_store_model(store_model)
    normalised_ownership = _normalise_ownership(ownership)
    _validate_request_route(normalised_site, normalised_mode)

    recommendations: list[dict[str, Any]] = []
    for expert in list_platform_experts(registry):
        platforms = {_normalise_platform(item) for item in _list_of_strings(expert.get("platforms"))}
        modules = {_normalise_id(item) for item in _list_of_strings(expert.get("job_modules"))}
        if normalised_platform not in platforms or normalised_capability not in modules:
            continue
        routing = expert.get("routing")
        routes = routing.get("routes") if isinstance(routing, Mapping) else []
        matched_route = next(
            (
                route
                for route in routes
                if isinstance(route, Mapping)
                and _route_matches(
                    route,
                    platform=normalised_platform,
                    country_site=normalised_site,
                    store_model=normalised_mode,
                    ownership=normalised_ownership,
                )
            ),
            None,
        )
        if matched_route is None:
            continue
        recommendations.append(
            {
                "expert_id": str(expert.get("id") or ""),
                "name": str(expert.get("name") or ""),
                "platform": normalised_platform,
                "capability": normalised_capability,
                "route": copy.deepcopy(dict(matched_route)),
                "model_slot": recommend_model_slot(expert, normalised_capability),
                "default_capabilities": copy.deepcopy(expert.get("default_capabilities") or {}),
                "sort_order": int(expert.get("sort_order") or 0),
            }
        )
    return sorted(recommendations, key=lambda item: (-item["sort_order"], item["expert_id"]))


def recommend_platform_expert(
    registry: Mapping[str, Any],
    *,
    platform: str,
    capability: str,
    country_site: str = "",
    store_model: str = "",
    ownership: str = "",
) -> dict[str, Any] | None:
    """Return the highest-priority expert recommendation, if one route matches."""

    recommendations = recommend_platform_experts(
        registry,
        platform=platform,
        capability=capability,
        country_site=country_site,
        store_model=store_model,
        ownership=ownership,
    )
    return recommendations[0] if recommendations else None
