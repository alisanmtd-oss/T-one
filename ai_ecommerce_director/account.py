from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .credential_store import credential_available


# Local account/profile for the operator front-end. This is a *local gate*, not
# internet-grade auth: the PIN is stored only as a salted SHA-256 hash and the
# session is a cookie token derived from it. For public / multi-user deployment
# this would need real auth + HTTPS. Store API secrets are never kept here — only
# the env-var name that holds each store's key is recorded.

PROFILE_FILENAME = "account_profile.json"

# Operator-facing features the user can choose to pin on the home. id -> (label, url).
FEATURE_CATALOG: list[dict[str, str]] = [
    {"id": "selection", "label": "选品结果", "url": "/selection"},
    {"id": "product_scout", "label": "六维选品打分", "url": "/product-scout"},
    {"id": "competitor", "label": "同行监控", "url": "/selection"},
    {"id": "big_screen", "label": "实时大屏", "url": "/realtime-big-screen"},
    {"id": "report", "label": "今日报告", "url": "/report"},
    {"id": "video", "label": "视频发布", "url": "/chat?intent=tk_content"},
    {"id": "influencer", "label": "私有达人库", "url": "/chat?intent=tk_content"},
    {"id": "lifecycle", "label": "生命周期 / 备货", "url": "/store-erp"},
    {"id": "launch", "label": "起盘控盘", "url": "/chat?intent=launch"},
    {"id": "budget", "label": "预算计划", "url": "/chat?intent=ads_budget"},
    {"id": "pod", "label": "POD专属通道", "url": "/chat?intent=pod"},
    {"id": "pod_ip", "label": "POD审核结果", "url": "/chat?intent=pod_risk"},
    {"id": "targets", "label": "设置监控商品", "url": "/product-intake"},
    {"id": "chat", "label": "店铺AI顾问", "url": "/chat"},
    {"id": "approvals", "label": "待确认动作", "url": "/chat?intent=approval"},
]

# Recommended feature ids per seller mode.
RECOMMENDED_FEATURES: dict[str, list[str]] = {
    "selection": ["selection", "product_scout", "competitor", "targets", "big_screen", "report", "chat", "approvals"],
    "launch": ["video", "influencer", "launch", "budget", "selection", "big_screen", "chat", "approvals"],
    "factory": ["lifecycle", "selection", "launch", "budget", "targets", "big_screen", "chat", "approvals"],
    "brand": ["influencer", "video", "selection", "competitor", "big_screen", "chat", "approvals"],
    "pod": ["pod", "selection", "competitor", "big_screen", "chat", "approvals"],
}

# Model tiers for non-technical users: a one-click choice that maps to a
# combination of models. Picking a tier re-prioritizes the multi_ai routes
# (existing providers stay as fallback, so a missing key never breaks anything).
MODEL_TIERS: dict[str, dict[str, Any]] = {
    "recommended": {
        "label": "推荐（均衡）",
        "desc": "不懂 AI 就选这个：速度、质量、成本平衡。",
        "providers": ["zhipu-glm-flash", "gemini-flash", "deepseek-official", "claude-sonnet", "openai-gpt-mini", "zhipu-glm-plus"],
    },
    "economy": {
        "label": "普通（省钱快速）",
        "desc": "优先免费 / 低成本模型，量大、日常够用。",
        "providers": ["zhipu-glm-free-flash", "gemini-free-flash", "deepseek-official", "zhipu-glm-flash", "openai-gpt-mini", "gemini-flash"],
    },
    "elite": {
        "label": "精英（最强质量）",
        "desc": "优先最强模型做关键策略 / 判断，更费额度。",
        "providers": ["openai-gpt-main", "claude-sonnet", "gemini-flash", "zhipu-glm-plus", "deepseek-pro", "zhipu-glm-vision"],
    },
}
DEFAULT_MODEL_TIER = "recommended"
MULTI_AI_FILENAME = "multi_ai.json"


def apply_model_tier(root: Path, tier: str) -> str:
    """Re-prioritize multi_ai.json routes to the chosen tier. Existing providers
    are kept as fallback so an unconfigured tier model never breaks routing."""
    tier = tier if tier in MODEL_TIERS else DEFAULT_MODEL_TIER
    path = root / "config" / MULTI_AI_FILENAME
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return tier
    providers = data.get("providers") if isinstance(data.get("providers"), list) else []
    names = {str(p.get("name") or p.get("id")) for p in providers if isinstance(p, dict)}
    # Providers the user tagged with this tier (e.g. added via the UI) lead, then
    # the built-in tier list — so newly added models auto-join their tier.
    tagged = [str(p.get("name") or p.get("id")) for p in providers if isinstance(p, dict) and p.get("tier") == tier]
    preferred: list[str] = []
    for name in tagged + MODEL_TIERS[tier]["providers"]:
        if name in names and name not in preferred:
            preferred.append(name)
    routes = data.get("routes") if isinstance(data.get("routes"), dict) else {}
    if not routes:
        routes = {"default": []}
    for key, value in list(routes.items()):
        original = value if isinstance(value, list) else []
        routes[key] = preferred + [name for name in original if name not in preferred]
    data["routes"] = routes
    data["active_model_tier"] = tier
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return tier


def _load_multi_ai(root: Path) -> tuple[Path, dict[str, Any]]:
    path = root / "config" / MULTI_AI_FILENAME
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, json.JSONDecodeError):
        data = {}
    return path, data


def list_models(root: Path) -> list[dict[str, Any]]:
    """All configured models with ready-state (key present) for display."""
    _, data = _load_multi_ai(root)
    providers = data.get("providers") if isinstance(data.get("providers"), list) else []
    result: list[dict[str, Any]] = []
    for p in providers:
        if not isinstance(p, dict):
            continue
        env = str(p.get("api_key_env") or "")
        credential_ref = str(p.get("credential_ref") or "")
        requires_api_key = bool(p.get("requires_api_key") or env or credential_ref)
        result.append({
            "name": str(p.get("name") or p.get("id") or ""),
            "label": str(p.get("label") or p.get("name") or p.get("id") or ""),
            "model": str(p.get("model") or ""),
            "base_url": str(p.get("base_url") or ""),
            "api_key_env": env,
            "credential_ref": credential_ref,
            "tier": str(p.get("tier") or ""),
            "tasks": [str(task) for task in p.get("tasks", [])] if isinstance(p.get("tasks"), list) else [],
            "priority": int(p.get("priority") or 100),
            "enabled": bool(p.get("enabled", False)),
            "ready": bool(
                p.get("enabled", False)
                and p.get("base_url")
                and p.get("model")
                and (
                    credential_available(
                        root,
                        credential_ref=credential_ref,
                        api_key_env=env,
                    )
                    if requires_api_key
                    else True
                )
            ),
            "added_via_ui": bool(p.get("added_via_ui")),
        })
    return result


def add_model(
    root: Path,
    *,
    name: str,
    base_url: str,
    model: str,
    api_key_env: str = "",
    credential_ref: str = "",
    api_format: str = "openai",
    tier: str = DEFAULT_MODEL_TIER,
    label: str = "",
    price_in_per_m: Any = None,
    price_out_per_m: Any = None,
) -> dict[str, Any]:
    name = (name or "").strip()
    base_url = (base_url or "").strip()
    model = (model or "").strip()
    if not name or not base_url or not model:
        raise ValueError("模型名、接口地址、模型ID 必填。")
    tier = tier if tier in MODEL_TIERS else DEFAULT_MODEL_TIER
    api_key_env = (api_key_env or "").strip()
    credential_ref = (credential_ref or "").strip().lower()

    def _price(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return None
    path, data = _load_multi_ai(root)
    providers = [p for p in (data.get("providers") or []) if isinstance(p, dict) and str(p.get("name") or p.get("id")) != name]
    provider = {
        "name": name,
        "label": (label or "").strip() or name,
        "base_url": base_url,
        "model": model,
        "api_key_env": api_key_env or None,
        "credential_ref": credential_ref or None,
        "requires_api_key": bool(api_key_env or credential_ref),
        "enabled": True,
        "api_format": (api_format or "openai").strip().lower() or "openai",
        "tasks": ["default", "chat", "strategy", "extraction", "listing"],
        "priority": 60,
        "tier": tier,
        "price_in_per_m": _price(price_in_per_m),
        "price_out_per_m": _price(price_out_per_m),
        "added_via_ui": True,
    }
    providers.append(provider)
    data["providers"] = providers
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    # Re-apply the active tier so the new model joins routing if it matches.
    apply_model_tier(root, str(data.get("active_model_tier") or DEFAULT_MODEL_TIER))
    return provider


# Platforms a store can be bound to (reserved). The actual key lives in an env var.
BINDABLE_PLATFORMS: list[dict[str, str]] = [
    {"id": "tiktok_shop", "label": "TikTok Shop", "key_env": "TIKTOK_SHOP_API_KEY"},
    {"id": "amazon", "label": "Amazon 店铺授权", "key_env": "AMAZON_SPAPI_KEY"},
    {"id": "shopify", "label": "Shopify", "key_env": "SHOPIFY_API_KEY"},
    {"id": "woocommerce", "label": "WooCommerce", "key_env": "WOOCOMMERCE_API_KEY"},
    {"id": "shein", "label": "SHEIN Marketplace", "key_env": "SHEIN_API_KEY"},
    {"id": "shopee", "label": "Shopee", "key_env": "SHOPEE_API_KEY"},
    {"id": "lazada", "label": "Lazada", "key_env": "LAZADA_API_KEY"},
    {"id": "walmart", "label": "Walmart", "key_env": "WALMART_API_KEY"},
    {"id": "etsy", "label": "Etsy", "key_env": "ETSY_API_KEY"},
    {"id": "ebay", "label": "eBay", "key_env": "EBAY_API_KEY"},
    {"id": "meta_ads", "label": "Meta Ads", "key_env": "META_ADS_API_KEY"},
    {"id": "fastmoss", "label": "FastMoss", "key_env": "FASTMOSS_API_KEY"},
    {"id": "kalodata", "label": "Kalodata", "key_env": "KALODATA_API_KEY"},
]


PERMISSION_CATALOG: list[dict[str, str]] = [
    {"id": "seller.dashboard.view", "label": "经营首页 / 结果报告", "group": "seller"},
    {"id": "store.data.view", "label": "店铺数据查看", "group": "store"},
    {"id": "store.data.import", "label": "店铺数据导入", "group": "store"},
    {"id": "selection.view", "label": "选品报告查看", "group": "selection"},
    {"id": "selection.run", "label": "发起选品 / 监控任务", "group": "selection"},
    {"id": "content.view", "label": "TK 内容策略查看", "group": "content"},
    {"id": "approval.view", "label": "待确认动作查看", "group": "approval"},
    {"id": "approval.submit", "label": "提交确认备注", "group": "approval"},
    {"id": "admin.manage_users", "label": "子账号 / 权限管理", "group": "admin"},
    {"id": "admin.data_lake", "label": "数据湖 / 原始证据", "group": "admin"},
    {"id": "admin.ai_setup", "label": "AI 模型 / API 设置", "group": "admin"},
    {"id": "admin.automation", "label": "采集训练 / 自动化任务", "group": "admin"},
]

DEFAULT_PERMISSION_GROUPS: list[dict[str, Any]] = [
    {
        "id": "owner",
        "name": "老板 / 超级管理员",
        "desc": "可以看全部数据、配置 AI、管理子账号和系统设置。",
        "permissions": [item["id"] for item in PERMISSION_CATALOG],
        "system": True,
    },
    {
        "id": "project_admin",
        "name": "项目管理员",
        "desc": "管理被分配的项目、店铺任务和项目成员，不能配置全局模型或查看其他项目。",
        "permissions": [
            "seller.dashboard.view",
            "store.data.view",
            "store.data.import",
            "selection.view",
            "selection.run",
            "content.view",
            "approval.view",
            "approval.submit",
            "admin.manage_users",
            "admin.automation",
        ],
        "system": True,
    },
    {
        "id": "operator",
        "name": "运营",
        "desc": "看经营结果、店铺数据、选品报告、内容策略和待确认动作。",
        "permissions": [
            "seller.dashboard.view",
            "store.data.view",
            "selection.view",
            "selection.run",
            "content.view",
            "approval.view",
            "approval.submit",
        ],
        "system": True,
    },
    {
        "id": "collector",
        "name": "采集员",
        "desc": "只负责导入数据、发起采集和查看采集结果，不看核心后台配置。",
        "permissions": [
            "seller.dashboard.view",
            "selection.view",
            "selection.run",
            "store.data.import",
        ],
        "system": True,
    },
    {
        "id": "finance",
        "name": "财务",
        "desc": "查看店铺经营、订单、退款、结算和报表，不参与发布动作。",
        "permissions": [
            "seller.dashboard.view",
            "store.data.view",
        ],
        "system": True,
    },
    {
        "id": "service",
        "name": "客服 / 售后",
        "desc": "查看售后、差评、投诉和待确认动作，不接触内部资料。",
        "permissions": [
            "seller.dashboard.view",
            "store.data.view",
            "approval.view",
            "approval.submit",
        ],
        "system": True,
    },
]


def profile_path(root: Path) -> Path:
    return root / "config" / PROFILE_FILENAME


def load_profile(root: Path) -> dict[str, Any]:
    try:
        return json.loads(profile_path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_profile(root: Path, profile: dict[str, Any]) -> dict[str, Any]:
    path = profile_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return profile


def profile_exists(root: Path) -> bool:
    profile = load_profile(root)
    return bool(profile.get("pin_hash"))


def _pin_digest(pin: str, salt: str) -> bytes:
    return hashlib.sha256(f"{salt}:{pin}".encode("utf-8")).digest()


def _legacy_hash_pin(pin: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{pin}".encode("utf-8")).hexdigest()


def _hash_pin(pin: str, salt: str) -> str:
    digest = base64.b32encode(_pin_digest(pin, salt)).decode("ascii").rstrip("=").lower()
    return f"v2${digest}"


def _pin_matches(pin: str, salt: str, stored_hash: str) -> bool:
    if secrets.compare_digest(_hash_pin(pin, salt), stored_hash):
        return True
    if not stored_hash.startswith("v2$"):
        return secrets.compare_digest(_legacy_hash_pin(pin, salt), stored_hash)
    return False


def _slug(value: str, fallback: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in (value or "").strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:48] or fallback


def _scope_values(value: Any) -> set[str]:
    if isinstance(value, list):
        raw = [str(item or "").strip() for item in value]
    else:
        raw = [item.strip() for item in re.split(r"[,;，；\n]+", str(value or ""))]
    values = {item for item in raw if item}
    return {"all"} if not values or "all" in {item.casefold() for item in values} else values


def _normalized_scope(value: Any) -> str:
    values = _scope_values(value)
    return "all" if "all" in values else ",".join(sorted(values, key=str.casefold))


def _scope_is_subset(requested: Any, allowed: Any) -> bool:
    requested_values = _scope_values(requested)
    allowed_values = _scope_values(allowed)
    if "all" in allowed_values:
        return True
    if "all" in requested_values:
        return False
    return requested_values.issubset(allowed_values)


def _valid_permissions(values: Any) -> list[str]:
    allowed = {item["id"] for item in PERMISSION_CATALOG}
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item in allowed and item not in result:
            result.append(item)
    return result


def _default_groups() -> list[dict[str, Any]]:
    return [dict(group, permissions=list(group["permissions"])) for group in DEFAULT_PERMISSION_GROUPS]


def ensure_team_defaults(profile: dict[str, Any]) -> dict[str, Any]:
    groups = profile.get("permission_groups")
    if not isinstance(groups, list):
        groups = []
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    existing = {str(group.get("id") or ""): group for group in groups if isinstance(group, dict)}
    for default in _default_groups():
        group = existing.get(default["id"])
        if isinstance(group, dict):
            default["name"] = str(group.get("name") or default["name"])
            default["desc"] = str(group.get("desc") or default["desc"])
            default["permissions"] = _valid_permissions(group.get("permissions")) or default["permissions"]
        merged.append(default)
        seen.add(default["id"])
    for group in groups:
        if not isinstance(group, dict):
            continue
        gid = str(group.get("id") or "").strip()
        if not gid or gid in seen:
            continue
        merged.append({
            "id": gid,
            "name": str(group.get("name") or gid),
            "desc": str(group.get("desc") or ""),
            "permissions": _valid_permissions(group.get("permissions")),
            "system": bool(group.get("system", False)),
        })
        seen.add(gid)
    profile["permission_groups"] = merged
    subs = profile.get("subaccounts")
    profile["subaccounts"] = [sub for sub in subs if isinstance(sub, dict)] if isinstance(subs, list) else []
    return profile


def create_profile(root: Path, name: str, pin: str) -> dict[str, Any]:
    name = (name or "运营").strip() or "运营"
    pin = (pin or "").strip()
    if len(pin) < 4:
        raise ValueError("PIN 至少 4 位。")
    salt = secrets.token_hex(8)
    profile = {
        "name": name,
        "salt": salt,
        "pin_hash": _hash_pin(pin, salt),
        "seller_mode": "selection",
        "features": list(RECOMMENDED_FEATURES["selection"]),
        "model_tier": DEFAULT_MODEL_TIER,
        "stores": [],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    ensure_team_defaults(profile)
    return save_profile(root, profile)


def team_state(root: Path) -> dict[str, Any]:
    profile = ensure_team_defaults(load_profile(root))
    save_profile(root, profile)
    return {
        "permissions": PERMISSION_CATALOG,
        "groups": profile.get("permission_groups", []),
        "subaccounts": [
            {
                key: value
                for key, value in subaccount.items()
                if key not in {"salt", "pin_hash"}
            }
            for subaccount in profile.get("subaccounts", [])
            if isinstance(subaccount, dict)
        ],
    }


def save_permission_group(
    root: Path,
    *,
    group_id: str = "",
    name: str,
    desc: str = "",
    permissions: list[str] | None = None,
) -> dict[str, Any]:
    profile = ensure_team_defaults(load_profile(root))
    name = (name or "").strip()
    if not name:
        raise ValueError("Please enter a permission group name.")
    gid = _slug(group_id or name, f"group-{secrets.token_hex(3)}")
    valid = _valid_permissions(permissions or [])
    if not valid:
        raise ValueError("Please choose at least one permission.")
    groups = [g for g in profile.get("permission_groups", []) if str(g.get("id")) != gid]
    groups.append({
        "id": gid,
        "name": name,
        "desc": (desc or "").strip(),
        "permissions": valid,
        "system": False,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    profile["permission_groups"] = groups
    save_profile(root, profile)
    return team_state(root)


def save_subaccount(
    root: Path,
    *,
    login_id: str,
    display_name: str,
    pin: str = "",
    group_id: str = "operator",
    platform_scope: str = "",
    store_scope: str = "",
    country_scope: str = "",
    project_scope: str = "",
    task_scope: str = "",
    parent_login_id: str = "owner",
    note: str = "",
    actor_session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = ensure_team_defaults(load_profile(root))
    login_id = _slug(login_id or display_name, "")
    display_name = (display_name or "").strip()
    if not login_id or not display_name:
        raise ValueError("Please enter login id and display name.")
    groups = {
        str(group.get("id") or ""): group
        for group in profile.get("permission_groups", [])
        if isinstance(group, dict)
    }
    if group_id not in groups or group_id == "owner":
        raise ValueError("Please choose a valid permission group.")
    if actor_session and not actor_session.get("is_owner"):
        actor_permissions = {
            str(item) for item in actor_session.get("permissions", []) if str(item).strip()
        }
        if "admin.manage_users" not in actor_permissions:
            raise ValueError("当前账号没有管理项目成员的权限。")
        target_permissions = {
            str(item) for item in groups[group_id].get("permissions", []) if str(item).strip()
        }
        if not target_permissions.issubset(actor_permissions):
            raise ValueError("不能给成员分配超出当前管理员范围的权限。")
        for requested, allowed, label in (
            (project_scope, actor_session.get("project_scope"), "项目"),
            (task_scope, actor_session.get("task_scope"), "任务/店铺"),
            (platform_scope, actor_session.get("platform_scope"), "平台"),
            (store_scope, actor_session.get("store_scope"), "店铺"),
            (country_scope, actor_session.get("country_scope"), "国家站点"),
        ):
            if not _scope_is_subset(requested, allowed):
                raise ValueError(f"不能给成员分配超出当前管理员范围的{label}。")
        parent_login_id = str(actor_session.get("login_id") or "owner")
    existing = next((s for s in profile.get("subaccounts", []) if str(s.get("login_id")) == login_id), {})
    salt = str(existing.get("salt") or secrets.token_hex(8))
    pin_hash = str(existing.get("pin_hash") or "")
    if pin:
        if len(pin.strip()) < 4:
            raise ValueError("Subaccount PIN must be at least 4 digits.")
        pin_hash = _hash_pin(pin.strip(), salt)
    elif not pin_hash:
        raise ValueError("A new subaccount needs a PIN.")
    subs = [s for s in profile.get("subaccounts", []) if str(s.get("login_id")) != login_id]
    subs.append({
        "login_id": login_id,
        "display_name": display_name,
        "group_id": group_id,
        "platform_scope": _normalized_scope(platform_scope),
        "store_scope": _normalized_scope(store_scope),
        "country_scope": _normalized_scope(country_scope),
        "project_scope": _normalized_scope(project_scope),
        "task_scope": _normalized_scope(task_scope),
        "parent_login_id": (parent_login_id or "owner").strip() or "owner",
        "note": (note or "").strip(),
        "active": bool(existing.get("active", True)),
        "salt": salt,
        "pin_hash": pin_hash,
        "created_at_utc": existing.get("created_at_utc") or datetime.now(timezone.utc).isoformat(),
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    profile["subaccounts"] = subs
    save_profile(root, profile)
    return team_state(root)


def set_subaccount_active(
    root: Path,
    login_id: str,
    active: bool,
    *,
    actor_session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = ensure_team_defaults(load_profile(root))
    login_id = _slug(login_id, "")
    found = False
    subs = []
    for sub in profile.get("subaccounts", []):
        if str(sub.get("login_id")) == login_id:
            if actor_session and not actor_session.get("is_owner"):
                actor_permissions = {
                    str(item)
                    for item in actor_session.get("permissions", [])
                    if str(item).strip()
                }
                if "admin.manage_users" not in actor_permissions:
                    raise ValueError("当前账号没有管理项目成员的权限。")
                if not _scope_is_subset(
                    sub.get("project_scope"), actor_session.get("project_scope")
                ) or not _scope_is_subset(
                    sub.get("task_scope"), actor_session.get("task_scope")
                ):
                    raise ValueError("不能修改超出当前管理员范围的成员。")
            sub = dict(sub)
            sub["active"] = bool(active)
            sub["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
            found = True
        subs.append(sub)
    if not found:
        raise ValueError("Subaccount not found.")
    profile["subaccounts"] = subs
    save_profile(root, profile)
    return team_state(root)


def verify_pin(root: Path, pin: str) -> bool:
    profile = load_profile(root)
    salt = str(profile.get("salt") or "")
    pin_hash = str(profile.get("pin_hash") or "")
    if not salt or not pin_hash:
        return False
    return _pin_matches((pin or "").strip(), salt, pin_hash)


def session_token(root: Path) -> str:
    profile = load_profile(root)
    base = f"{profile.get('pin_hash', '')}:{profile.get('salt', '')}:session"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _subaccount_by_login(profile: dict[str, Any], login_id: str) -> dict[str, Any] | None:
    login_id = _slug(login_id, "")
    for sub in profile.get("subaccounts", []) if isinstance(profile.get("subaccounts"), list) else []:
        if not isinstance(sub, dict):
            continue
        if str(sub.get("login_id") or "") == login_id:
            return sub
    return None


def verify_subaccount_pin(root: Path, login_id: str, pin: str) -> bool:
    profile = ensure_team_defaults(load_profile(root))
    sub = _subaccount_by_login(profile, login_id)
    if not sub or not sub.get("active", True):
        return False
    salt = str(sub.get("salt") or "")
    pin_hash = str(sub.get("pin_hash") or "")
    if not salt or not pin_hash:
        return False
    return _pin_matches((pin or "").strip(), salt, pin_hash)


def subaccount_session_token(root: Path, login_id: str) -> str:
    profile = ensure_team_defaults(load_profile(root))
    sub = _subaccount_by_login(profile, login_id) or {}
    base = f"{sub.get('pin_hash', '')}:{sub.get('salt', '')}:{sub.get('login_id', '')}:subaccount-session"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def is_owner_session(root: Path, cookie_token: str | None) -> bool:
    if not profile_exists(root) or not cookie_token:
        return False
    return secrets.compare_digest(str(cookie_token), session_token(root))


def current_session(root: Path, cookie_token: str | None) -> dict[str, Any] | None:
    if not profile_exists(root) or not cookie_token:
        return None
    profile = ensure_team_defaults(load_profile(root))
    if secrets.compare_digest(str(cookie_token), session_token(root)):
        return {
            "role": "owner",
            "is_owner": True,
            "display_name": str(profile.get("name") or "Owner"),
            "login_id": "owner",
            "group_id": "owner",
            "permissions": [item["id"] for item in PERMISSION_CATALOG],
            "platform_scope": "all",
            "store_scope": "all",
            "country_scope": "all",
            "project_scope": "all",
            "task_scope": "all",
            "active": True,
        }
    group_by_id = {str(group.get("id") or ""): group for group in profile.get("permission_groups", []) if isinstance(group, dict)}
    for sub in profile.get("subaccounts", []):
        if not isinstance(sub, dict) or not sub.get("active", True):
            continue
        token = subaccount_session_token(root, str(sub.get("login_id") or ""))
        if not secrets.compare_digest(str(cookie_token), token):
            continue
        group = group_by_id.get(str(sub.get("group_id") or ""), {})
        return {
            "role": "subaccount",
            "is_owner": False,
            "display_name": str(sub.get("display_name") or sub.get("login_id") or "Subaccount"),
            "login_id": str(sub.get("login_id") or ""),
            "group_id": str(sub.get("group_id") or ""),
            "permissions": _valid_permissions(group.get("permissions")) if isinstance(group, dict) else [],
            "platform_scope": str(sub.get("platform_scope") or "all"),
            "store_scope": str(sub.get("store_scope") or "all"),
            "country_scope": str(sub.get("country_scope") or "all"),
            "project_scope": str(sub.get("project_scope") or "all"),
            "task_scope": str(sub.get("task_scope") or "all"),
            "parent_login_id": str(sub.get("parent_login_id") or "owner"),
            "active": True,
        }
    return None


def is_authenticated(root: Path, cookie_token: str | None) -> bool:
    return current_session(root, cookie_token) is not None


# ---- R2-A 管理员模式解锁 ----
# 已登录的操作者再输一次管理员 PIN，才解锁管理员后台（解锁态带过期，存本地文件）。
# 这样把卖家视图（已登录）和管理员后台（已解锁）分开；以后升级到多账号角色（B）时，
# 只需把 is_admin 改成"看账号角色"，server.py 的门禁调用不用动。
ADMIN_UNLOCK_FILENAME = "admin_unlock.json"
ADMIN_UNLOCK_TTL_SECONDS = 2 * 60 * 60  # 解锁有效期 2 小时


def _admin_unlock_path(root: Path) -> Path:
    return root / "config" / ADMIN_UNLOCK_FILENAME


def unlock_admin(root: Path, pin: str) -> str | None:
    """验证管理员 PIN；成功则写入带过期的解锁令牌并返回，失败返回 None。"""
    if not verify_pin(root, pin):
        return None
    token = secrets.token_hex(16)
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ADMIN_UNLOCK_TTL_SECONDS)).isoformat()
    path = _admin_unlock_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"token": token, "expires_at": expires_at}), encoding="utf-8")
    return token


def is_admin_unlocked(root: Path, unlock_cookie: str | None) -> bool:
    if not unlock_cookie:
        return False
    try:
        data = json.loads(_admin_unlock_path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    token = str(data.get("token") or "")
    if not token or not secrets.compare_digest(str(unlock_cookie), token):
        return False
    try:
        if datetime.fromisoformat(str(data.get("expires_at") or "")) < datetime.now(timezone.utc):
            return False
    except ValueError:
        return False
    return True


def lock_admin(root: Path) -> None:
    try:
        _admin_unlock_path(root).unlink()
    except OSError:
        pass


def is_admin(root: Path, session_cookie: str | None, unlock_cookie: str | None) -> bool:
    """R2-A：管理员页面/接口要求"已登录 + 已用管理员 PIN 解锁"。"""
    return is_owner_session(root, session_cookie) and is_admin_unlocked(root, unlock_cookie)


def update_setup(
    root: Path,
    *,
    seller_mode: str | None = None,
    features: list[str] | None = None,
    model_tier: str | None = None,
) -> dict[str, Any]:
    profile = load_profile(root)
    if seller_mode and seller_mode in RECOMMENDED_FEATURES:
        profile["seller_mode"] = seller_mode
    if features is not None:
        valid = {item["id"] for item in FEATURE_CATALOG}
        profile["features"] = [f for f in features if f in valid]
    if model_tier and model_tier in MODEL_TIERS:
        profile["model_tier"] = model_tier
        apply_model_tier(root, model_tier)
    return save_profile(root, profile)


def bind_store(
    root: Path,
    platform_id: str,
    store_name: str,
    key_env: str = "",
    *,
    country_code: str = "",
    connection_method: str = "",
    business_center_id: str = "",
    ads_account_id: str = "",
    authorization_scopes: str | list[str] = "",
    shop_type: str = "",
    store_external_id: str = "",
    sub_store_name: str = "",
    store_ownership: str = "",
) -> dict[str, Any]:
    profile = load_profile(root)
    platform = next((p for p in BINDABLE_PLATFORMS if p["id"] == platform_id), None)
    if platform is None:
        raise ValueError("未知平台。")
    store_name = (store_name or "").strip()
    if not store_name:
        raise ValueError("请填写店铺名称。")
    if is_official_full_managed_shop_type(shop_type):
        raise ValueError("平台官方全托管只做识别标签，当前不接入；请改选 T One 代运营、T One 自营、设计师自运营、本土店、跨境店或半托管路线。")
    normalized_country = normalize_executable_country_code(country_code)
    normalized_shop_type = (shop_type or "").strip()
    normalized_external_id = (store_external_id or "").strip()
    env_name = (key_env or platform["key_env"]).strip()
    stores = profile.get("stores") if isinstance(profile.get("stores"), list) else []
    new_identity = store_binding_identity(
        platform_id,
        store_name,
        normalized_country,
        normalized_shop_type,
        normalized_external_id,
    )
    stores = [
        s
        for s in stores
        if store_binding_identity(
            str(s.get("platform_id") or ""),
            str(s.get("store_name") or ""),
            str(s.get("country_code") or ""),
            str(s.get("shop_type") or ""),
            str(s.get("store_external_id") or ""),
        )
        != new_identity
    ]
    if isinstance(authorization_scopes, list):
        scopes = [str(item).strip() for item in authorization_scopes if str(item).strip()]
    else:
        scope_text = str(authorization_scopes or "")
        scopes = [item.strip() for item in scope_text.replace("\n", ",").replace("，", ",").split(",") if item.strip()]
    stores.append({
        "platform_id": platform_id,
        "platform_label": platform["label"],
        "store_name": store_name,
        "country_code": normalized_country,
        "connection_method": (connection_method or "manual_report_or_authorized_connection").strip(),
        "business_center_id": (business_center_id or "").strip(),
        "ads_account_id": (ads_account_id or "").strip(),
        "authorization_scopes": scopes,
        "shop_type": normalized_shop_type,
        "store_ownership": normalize_store_ownership_for_binding(store_ownership, normalized_shop_type),
        "store_external_id": normalized_external_id,
        "sub_store_name": (sub_store_name or "").strip(),
        "key_env": env_name,
        "key_present": bool(os.environ.get(env_name)),
        "status": "reserved",
        "bound_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    profile["stores"] = stores
    return save_profile(root, profile)


def normalize_executable_country_code(value: str) -> str:
    text = str(value or "").strip()
    normalized = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "", text).upper()
    if normalized in {"SEA", "SOUTHEASTASIA", "东南亚", "LATAM", "LATINAMERICA", "拉美"}:
        raise ValueError("国家/站点必须填写具体站点，例如 US、SG、MY、TH、VN、PH、ID、MX 或 BR；区域分组不能作为可执行店铺。")
    return text.upper()


def store_binding_identity(
    platform_id: str,
    store_name: str,
    country_code: str = "",
    shop_type: str = "",
    store_external_id: str = "",
) -> tuple[str, str, str, str, str]:
    return (
        str(platform_id or "").strip().lower(),
        str(store_name or "").strip().lower(),
        str(country_code or "").strip().upper(),
        str(shop_type or "").strip().lower(),
        str(store_external_id or "").strip().lower(),
    )


def normalize_store_ownership_for_binding(value: str = "", shop_type: str = "") -> str:
    raw = str(value or "").strip().lower()
    model = str(shop_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    if raw in {"designer_self_store", "self_store", "designer_owned"}:
        return "designer_self_store"
    if raw in {"platform_store", "operator_store", "t_one_operator_store", "backend_platform_store"}:
        return "platform_store"
    if raw in {"t_one_owned", "owned"} or "t_one_owned" in model:
        return "t_one_owned"
    if raw in {"platform_co_ops", "co_ops"} or "platform_co_ops" in model:
        return "platform_co_ops"
    if raw in {"b2b_customer_store", "customer_store"}:
        return "b2b_customer_store"
    if "self_store" in model:
        return "designer_self_store"
    return "store_ownership_pending"


def is_official_full_managed_shop_type(value: str) -> bool:
    text = str(value or "").strip().lower()
    normalized = text.replace("-", "_").replace(" ", "_")
    return (
        "official_full_managed" in normalized
        or "full_managed" in normalized
        or "full_service" in normalized
        or "full managed" in text
        or "full service" in text
        or "官方全托管" in text
        or "平台全托管" in text
        or "全托管" in text
    )


# Social platforms that can be bound (reserved). Real tokens live in env vars;
# publishing always requires human confirmation (no auto-post).
BINDABLE_SOCIAL: list[dict[str, str]] = [
    {"id": "tiktok", "label": "TikTok（AIP 发布）", "key_env": "TIKTOK_CONTENT_API_TOKEN"},
    {"id": "instagram", "label": "Instagram", "key_env": "META_GRAPH_API_TOKEN"},
    {"id": "facebook", "label": "Facebook", "key_env": "META_GRAPH_API_TOKEN"},
    {"id": "youtube", "label": "YouTube", "key_env": "YOUTUBE_API_TOKEN"},
    {"id": "x", "label": "X / Twitter", "key_env": "X_API_TOKEN"},
    {"id": "pinterest", "label": "Pinterest", "key_env": "PINTEREST_API_TOKEN"},
    {"id": "linkedin", "label": "LinkedIn", "key_env": "LINKEDIN_API_TOKEN"},
]


def bind_social_account(root: Path, platform_id: str, handle: str, key_env: str = "") -> dict[str, Any]:
    profile = load_profile(root)
    platform = next((p for p in BINDABLE_SOCIAL if p["id"] == platform_id), None)
    if platform is None:
        raise ValueError("未知社媒平台。")
    handle = (handle or "").strip()
    if not handle:
        raise ValueError("请填写账号/主页。")
    env_name = (key_env or platform["key_env"]).strip()
    accounts = profile.get("social_accounts") if isinstance(profile.get("social_accounts"), list) else []
    accounts = [a for a in accounts if not (a.get("platform_id") == platform_id and a.get("handle") == handle)]
    accounts.append({
        "platform_id": platform_id,
        "platform_label": platform["label"],
        "handle": handle,
        "key_env": env_name,
        "key_present": bool(os.environ.get(env_name)),
        "status": "reserved",
        "publish_requires_confirmation": True,
        "bound_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    profile["social_accounts"] = accounts
    return save_profile(root, profile)


def register_website(root: Path, name: str, target: str, audit_score: Any = None) -> dict[str, Any]:
    name = (name or "").strip()
    target = (target or "").strip()
    if not target:
        raise ValueError("请填写网站路径或 URL。")
    profile = load_profile(root)
    sites = profile.get("websites") if isinstance(profile.get("websites"), list) else []
    sites = [s for s in sites if s.get("target") != target]
    sites.append({
        "name": name or target,
        "target": target,
        "audit_score": audit_score,
        "registered_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    profile["websites"] = sites
    return save_profile(root, profile)


def selected_features(root: Path) -> list[dict[str, str]]:
    profile = load_profile(root)
    chosen = profile.get("features") if isinstance(profile.get("features"), list) else []
    by_id = {item["id"]: item for item in FEATURE_CATALOG}
    return [by_id[f] for f in chosen if f in by_id]
