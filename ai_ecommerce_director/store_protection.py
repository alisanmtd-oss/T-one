from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .storage import read_records
from .types import IntakeRecord


STORE_PROTECTION_CONFIG = Path("config") / "store_protection_policy.json"

STORE_IMPACT_ACTIONS = {
    "login",
    "captcha_or_slider",
    "download_reports",
    "copy_store_backend_tables",
    "publish_listing",
    "update_listing",
    "delist_product",
    "refund_customer",
    "publish_video_via_aip",
    "bind_tk_aip_publisher_account",
    "update_price",
    "update_inventory",
    "set_discount",
    "join_campaign",
    "contact_creator",
    "send_message",
    "upload_asset",
    "change_store_setting",
    "payment",
    "ship_order",
    "start_experiment",
    "appeal",
    "authorize_app",
    "launch_ad",
    "update_ad_budget",
    "pause_ad",
    "add_live_product_link",
    "change_live_discount",
    "issue_coupon",
}

READ_ONLY_MANUAL_GATE_ACTIONS = {
    "login",
    "captcha_or_slider",
    "download_reports",
    "copy_store_backend_tables",
}


def load_store_protection_policy(root: Path) -> dict[str, Any]:
    path = root / STORE_PROTECTION_CONFIG
    if not path.exists():
        return default_store_protection_policy()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_store_protection_policy()
    if not isinstance(payload, dict):
        return default_store_protection_policy()
    return payload


def default_store_protection_policy() -> dict[str, Any]:
    return {
        "default_mode": "protected_legacy_store",
        "rules": {
            "experimental_new_store": {
                "execution_allowed_after_confirmation": True,
                "max_automation_level": "L3",
                "description": "New or test store. AI may draft and queue experiments; human confirmation is still required for external actions.",
            },
            "protected_legacy_store": {
                "execution_allowed_after_confirmation": False,
                "max_automation_level": "L2",
                "description": "Existing store or unknown store. AI may analyze and draft only; store-impacting changes require explicit protection override.",
            },
            "locked_revenue_store": {
                "execution_allowed_after_confirmation": False,
                "max_automation_level": "L1",
                "description": "Stable, old, high-GMV, or active-ad store. AI must not alter ads, listing, price, discounts, inventory, links, or live-room settings.",
            },
        },
        "never_auto_execute": sorted(STORE_IMPACT_ACTIONS),
    }


def store_profile_index(root: Path) -> dict[str, IntakeRecord]:
    index: dict[str, IntakeRecord] = {}
    for record in read_records(root, "store_profile"):
        fields = record.fields
        for key in ["store_id", "store_name", "seller_name"]:
            value = str(fields.get(key) or "").strip().lower()
            if value:
                index[value] = record
    return index


def apply_store_protection(root: Path, action: dict[str, Any], record: IntakeRecord) -> dict[str, Any]:
    action_type = str(action.get("action_type") or "")
    if action_type not in STORE_IMPACT_ACTIONS:
        return action

    policy = load_store_protection_policy(root)
    profile = resolve_store_profile(root, record)
    mode = classify_store_mode(profile, policy)
    rule = policy.get("rules", {}).get(mode, {})
    protected = dict(action)
    protected["store_protection_mode"] = mode
    protected["store_protection_level"] = rule.get("max_automation_level") or "L2"
    protected["store_protection_reason"] = protection_reason(mode, profile, record)
    protected["requires_confirmation"] = True

    if action_type in READ_ONLY_MANUAL_GATE_ACTIONS:
        protected["execution_allowed_after_confirmation"] = True
        protected["status"] = "pending_confirmation"
        protected["reason"] = (
            "Read-only or manual-gate store access. Human must complete login/verification or confirm the visible page first; "
            "after that AI may read/copy/download data for analysis only, with no store changes."
        )
        return protected

    if mode == "experimental_new_store" and bool(rule.get("execution_allowed_after_confirmation", True)):
        protected["execution_allowed_after_confirmation"] = True
        protected["status"] = "pending_confirmation"
        protected["reason"] = (
            "Experimental/new store: AI may prepare this store-impacting action, but it still needs human confirmation and stop-loss review."
        )
        return protected

    protected["execution_allowed_after_confirmation"] = False
    protected["status"] = "blocked_protected_store" if mode == "protected_legacy_store" else "blocked_locked_store"
    protected["reason"] = (
        f"Store protection active ({mode}). AI can analyze and draft only. "
        "Do not change ads, listing, price, inventory, discounts, live links, coupons, uploads, or account settings without an explicit protection override."
    )
    return protected


def resolve_store_profile(root: Path, record: IntakeRecord) -> IntakeRecord | None:
    fields = record.fields
    index = store_profile_index(root)
    for key in ["store_id", "target_store", "store_name", "seller_name"]:
        value = str(fields.get(key) or "").strip().lower()
        if value and value in index:
            return index[value]
    metadata = record.metadata or {}
    for key in ["store_id", "target_store", "store_name"]:
        value = str(metadata.get(key) or "").strip().lower()
        if value and value in index:
            return index[value]
    return None


def classify_store_mode(profile: IntakeRecord | None, policy: dict[str, Any]) -> str:
    if profile is None:
        return str(policy.get("default_mode") or "protected_legacy_store")
    fields = profile.fields
    if truthy(fields.get("active_ads")) or truthy(fields.get("stable_revenue")) or truthy(fields.get("high_gmv")):
        return "locked_revenue_store"

    explicit = str(fields.get("store_protection_mode") or fields.get("protection_level") or fields.get("automation_mode") or "").strip().lower()
    if explicit in {"experimental", "new", "test", "sandbox", "experimental_new_store"}:
        return "experimental_new_store"
    if explicit in {"locked", "revenue", "stable", "vip", "locked_revenue_store"}:
        return "locked_revenue_store"
    if explicit in {"protected", "old", "legacy", "protected_legacy_store"}:
        return "protected_legacy_store"

    lifecycle = str(fields.get("store_lifecycle") or fields.get("store_stage") or "").strip().lower()
    if lifecycle in {"new", "test", "sandbox", "pilot", "experimental"}:
        return "experimental_new_store"
    if lifecycle in {"old", "legacy", "stable", "mature"}:
        return "protected_legacy_store"

    return str(policy.get("default_mode") or "protected_legacy_store")


def protection_reason(mode: str, profile: IntakeRecord | None, record: IntakeRecord) -> str:
    if profile is None:
        return "No matching store profile found, so this is treated as an existing/protected store by default."
    store_name = profile.fields.get("store_id") or profile.fields.get("store_name") or "matched store"
    if mode == "experimental_new_store":
        return f"{store_name} is marked as a new/test store. Experiments can be queued, but confirmation and stop-loss rules still apply."
    if mode == "locked_revenue_store":
        return f"{store_name} is marked stable/high-GMV/active-ads. AI must not disturb ads, listings, pricing, discounts, or live-room settings."
    return f"{store_name} is protected as an existing store. AI may draft only unless you explicitly override protection."


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是", "对", "active", "running"}
