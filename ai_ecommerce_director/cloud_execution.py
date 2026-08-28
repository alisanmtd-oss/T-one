from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import account as account_center
from .channel_routes import (
    build_platform_activity_execution_plan,
    infer_store_ownership_for_route,
    normalize_store_model_for_route as normalize_channel_store_model_for_route,
    store_ownership_label,
    store_route_missing_prerequisites,
)
from .storage import append_record, read_records
from .types import IntakeRecord
from .project_facts import private_project_section


CLOUD_EXECUTION_ACTION_TYPES: set[str] = {
    "store_connection_setup",
    "amazon_listing_preflight",
    "listing_draft",
    "pricing_promotion_draft",
    "after_sales_review_draft",
    "ads_test_plan_draft",
    "publish_listing",
    "update_listing",
    "set_discount",
    "launch_ad",
    "publish_video_via_aip",
    "upload_asset",
    "delist_product",
}


CLOUD_EXECUTION_TASK_TYPES: set[str] = {
    "cloud_store_action",
    "cloud_store_backend_action",
    "cloud_ads_backend_action",
    "cloud_content_catalog_action",
    "cloud_read_only_collection_action",
}


ADS_ACTION_TYPES: set[str] = {
    "ads_test_plan_draft",
    "launch_ad",
    "update_ad_budget",
}


CONTENT_CATALOG_ACTION_TYPES: set[str] = {
    "upload_asset",
    "publish_video_via_aip",
    "content_catalog_sync",
    "catalog_feed_draft",
}


READ_ONLY_COLLECTION_ACTION_TYPES: set[str] = {
    "store_connection_setup",
    "review_store_sales_metrics",
    "analyze_ads_roas",
    "collect_store_data",
}


BLOCKED_EXTERNAL_BOUNDARIES: list[str] = [
    "login_or_captcha",
    "payment_or_subscription",
    "save_password_or_token",
    "change_store_security_settings",
    "submit_external_action_without_confirmation",
]


def should_create_cloud_execution_task(action: dict[str, Any]) -> bool:
    action_type = str(action.get("action_type") or "").strip()
    if action_type in CLOUD_EXECUTION_ACTION_TYPES:
        return True
    if str(action.get("cloud_task_package_type") or "").strip():
        return bool(action.get("requires_confirmation"))
    if action_type in {"amazon_listing_preflight", "amazon_product_identity_preflight"}:
        return bool(action.get("requires_confirmation"))
    text = " ".join(
        str(action.get(key) or "")
        for key in ["title", "reason", "next_step", "action_type"]
    ).lower()
    external_hints = [
        "publish",
        "listing",
        "discount",
        "campaign",
        "ads",
        "authorization",
        "refund",
        "ship",
        "上传",
        "发布",
        "上架",
        "改价",
        "折扣",
        "活动",
        "投放",
        "广告",
        "授权",
        "退款",
        "发货",
    ]
    return bool(action.get("requires_confirmation")) and any(hint in text for hint in external_hints)


def append_cloud_execution_task(
    root: Path,
    action: dict[str, Any],
    *,
    approved_at: str,
    approval_note: str = "",
) -> IntakeRecord | None:
    if not should_create_cloud_execution_task(action):
        return None
    task = build_cloud_execution_task(root, action, approved_at=approved_at, approval_note=approval_note)
    append_record(root, task)
    action["cloud_execution_task_id"] = task.fields["task_queue_id"]
    action["cloud_route_key"] = task.fields["route_key"]
    action["cloud_execution_status"] = task.fields["status"]
    action["cloud_task_package_type"] = task.fields["task_package_type"]
    action["cloud_task_package_label"] = task.fields["task_package_label"]
    action["cloud_execution_readiness"] = task.fields["execution_readiness"]
    action["cloud_execution_readiness_label"] = task.fields["execution_readiness_label"]
    action["cloud_execution_identity_ref"] = task.fields["execution_identity_ref"]
    action["execution_mode"] = "isolated_cloud_plugin_after_confirmation"
    action["next_step"] = (
        f"已生成{task.fields['task_package_label']}；"
        f"当前判断：{task.fields['execution_readiness_label']}。"
        "后台待执行包只在对应店铺环境里处理，遇到登录、验证码、付费或真实提交边界会停下。"
    )
    return task


def activity_plan_from_action(action: dict[str, Any]) -> dict[str, Any]:
    plan = action.get("activity_execution_plan")
    if isinstance(plan, dict):
        return plan
    payload = action.get("payload")
    if isinstance(payload, dict):
        plan = payload.get("activity_execution_plan")
    return plan if isinstance(plan, dict) else {}


def route_parts_from_key(route_key: Any) -> dict[str, str]:
    raw = str(route_key or "").strip()
    if not raw:
        return {}
    parts = [part.strip() for part in raw.split(":")]
    if len(parts) < 3:
        return {}
    return {
        "platform": parts[0],
        "country": parts[1].upper() or "GLOBAL",
        "store_model": normalize_store_model_for_route(parts[2]),
    }


def action_route_key(action: dict[str, Any], plan: dict[str, Any] | None = None) -> str:
    route_plan = plan if isinstance(plan, dict) else activity_plan_from_action(action)
    return first_present(
        action.get("cloud_route_key"),
        action.get("route_key"),
        route_plan.get("route_key"),
    )


def build_cloud_execution_task(
    root: Path,
    action: dict[str, Any],
    *,
    approved_at: str,
    approval_note: str = "",
) -> IntakeRecord:
    original_plan = activity_plan_from_action(action)
    original_route = action_route_key(action, original_plan)
    original_route_parts = route_parts_from_key(original_route)
    store_profile = match_store_profile(root, action)
    package = classify_cloud_execution_package(action, root)
    platform = first_present(
        store_profile.get("platform_id"),
        store_profile.get("platform_label"),
        action.get("platform_id"),
        action.get("platform"),
        action.get("marketplace"),
        original_route_parts.get("platform"),
        original_plan.get("channel_id"),
        default="unknown_channel",
    )
    country = first_present(
        store_profile.get("country_code"),
        action.get("country"),
        action.get("country_code"),
        original_route_parts.get("country"),
        original_plan.get("country_code"),
        default="GLOBAL",
    ).upper()
    store_name = first_present(
        store_profile.get("store_name"),
        action.get("store_name"),
        action.get("store"),
        action.get("store_id"),
        original_plan.get("store_name"),
        default="store_pending",
    )
    store_model = normalize_store_model_for_route(
        first_present(
            store_profile.get("shop_type"),
            action.get("store_model"),
            action.get("shop_type"),
            original_route_parts.get("store_model"),
            original_plan.get("store_model"),
        )
    )
    store_ownership = infer_store_ownership_for_route(
        {
            **original_plan,
            **action,
            **store_profile,
            "store_model": store_model,
        }
    )
    store_ownership_text = store_ownership_label(store_ownership)
    route_key = route_key_from_parts(platform, country, store_model)
    store_identity_fingerprint = identity_fingerprint(
        "store_scope",
        route_key,
        store_name,
        first_present(store_profile.get("store_external_id"), action.get("store_external_id")),
        first_present(store_profile.get("sub_store_name"), action.get("sub_store_name")),
    )
    action_id = str(action.get("action_id") or "").strip() or stable_hash(json.dumps(action, ensure_ascii=False))[:12]
    task_id = "cloud_exec_" + stable_hash(f"{route_key}:{action_id}")[:16]
    package_scope_fingerprint = identity_fingerprint(
        "package_scope",
        route_key,
        package["task_package_type"],
        package["action_surface"],
    )
    ads_identity_fingerprint = (
        identity_fingerprint(
            "ads_scope",
            route_key,
            store_identity_fingerprint,
            first_present(store_profile.get("ads_account_id"), action.get("ads_account_id")),
            first_present(store_profile.get("business_center_id"), action.get("business_center_id")),
        )
        if package["task_package_type"] == "ads_backend"
        else "ads_scope_not_applicable"
    )
    execution_identity_ref = "cloud_profile_" + stable_hash(
        f"{route_key}:{package_scope_fingerprint}:{store_identity_fingerprint}:{ads_identity_fingerprint}"
    )[:12]
    now = datetime.now(timezone.utc).isoformat()
    readiness = cloud_execution_readiness(package, store_profile, action)
    activity_plan = cloud_activity_execution_plan(
        root,
        {
            **action,
            "route_key": route_key,
            "platform": platform,
            "country": country,
            "store_model": store_model,
            "store_ownership": store_ownership,
            "store_name": store_name,
        },
    )
    developer_capability_plan = (
        activity_plan.get("developer_capability_plan")
        if isinstance(activity_plan.get("developer_capability_plan"), dict)
        else {}
    )
    activity_requirements = activity_execution_requirements(action, activity_plan, package, developer_capability_plan)
    required_evidence = merge_unique(package["required_evidence"], activity_requirements.get("required_evidence"))
    contract = merge_evidence_contract(package["evidence_contract"], activity_requirements)
    payload = {
        "action": sanitize_action_for_cloud(action),
        "approval": {
            "approved_at": approved_at,
            "approval_note": approval_note[:500],
            "confirmation_required": True,
            "external_execution_before_confirmation": False,
        },
        "route": {
            "route_key": route_key,
            "channel_id": channel_id(platform),
            "country_code": country,
            "store_model": store_model,
            "store_ownership": store_ownership,
            "store_ownership_label": store_ownership_text,
            "store_name": store_name,
            "store_external_ref": masked_present(store_profile.get("store_external_id") or action.get("store_external_id")),
            "internal_sub_store_note_status": "registered"
            if first_present(store_profile.get("sub_store_name"), action.get("sub_store_name"))
            else "missing",
        },
        "execution_scope": {
            "task_package_type": package["task_package_type"],
            "task_package_label": package["task_package_label"],
            "action_surface": package["action_surface"],
            "execution_readiness": readiness["execution_readiness"],
            "execution_readiness_label": readiness["execution_readiness_label"],
            "missing_prerequisites": readiness["missing_prerequisites"],
            "operator_hint": readiness["operator_hint"],
            "store_ownership": store_ownership,
            "store_ownership_label": store_ownership_text,
            "developer_capability_domains": developer_capability_plan.get("requested_domains") or [],
            "developer_capability_surfaces": developer_capability_plan.get("execution_surfaces") or [],
            "cloud_package_policy": developer_capability_plan.get("cloud_package_policy") or "",
        },
        "execution_identity": {
            "identity_ref": execution_identity_ref,
            "identity_type": "isolated_cloud_plugin_profile",
            "one_store_one_identity": True,
            "identity_match_required": True,
            "package_scope_fingerprint": package_scope_fingerprint,
            "task_package_type": package["task_package_type"],
            "action_surface": package["action_surface"],
            "store_ownership": store_ownership,
            "store_ownership_label": store_ownership_text,
            "route_scope_fingerprint": identity_fingerprint("route_scope", route_key),
            "store_identity_fingerprint": store_identity_fingerprint,
            "ads_identity_fingerprint": ads_identity_fingerprint,
            "credential_policy": "no_password_cookie_token_in_task_payload",
            "ads_account_status": "registered" if first_present(store_profile.get("ads_account_id"), action.get("ads_account_id")) else "missing",
            "business_center_status": "registered" if first_present(store_profile.get("business_center_id"), action.get("business_center_id")) else "missing",
        },
        "execution_mode": "isolated_cloud_plugin_after_confirmation",
        "allowed_steps": package["allowed_steps"],
        "blocked_boundaries": BLOCKED_EXTERNAL_BOUNDARIES,
        "required_evidence": required_evidence,
        "evidence_contract": contract,
        "activity_execution_requirements": activity_requirements,
        "activity_execution_plan": activity_plan,
        "developer_capability_plan": developer_capability_plan,
        "operator_note": "后台待执行包只拿这个任务包和路径，不拿密码、登录凭证、密钥或客户隐私。",
    }
    return IntakeRecord(
        record_type="task_queue",
        fields={
            "task_queue_id": task_id,
            "task_type": package["task_type"],
            "task_package_type": package["task_package_type"],
            "task_package_label": package["task_package_label"],
            "source_event_inbox_id": f"approval_center:{action_id}",
            "target_agent_id": package["target_agent_id"],
            "source_action_id": action_id,
            "route_key": route_key,
            "execution_identity_ref": execution_identity_ref,
            "package_scope_fingerprint": package_scope_fingerprint,
            "store_identity_fingerprint": store_identity_fingerprint,
            "ads_identity_fingerprint": ads_identity_fingerprint,
            "status": readiness["status"],
            "execution_readiness": readiness["execution_readiness"],
            "execution_readiness_label": readiness["execution_readiness_label"],
            "missing_prerequisites": readiness["missing_prerequisites"],
            "priority": safe_int(action.get("priority") or action.get("risk_score") or 80),
            "created_at_utc": now,
            "not_before_utc": approved_at or now,
            "payload": payload,
            "activity_plan_status": activity_plan.get("plan_status") if activity_plan else "",
            "activity_plan_missing_prerequisites": activity_plan.get("missing_prerequisites") if activity_plan else [],
            "store_ownership": store_ownership,
            "store_ownership_label": store_ownership_text,
            "developer_capability_domains": developer_capability_plan.get("requested_domains") if developer_capability_plan else [],
            "developer_capability_status": developer_capability_plan.get("capability_status") if developer_capability_plan else "",
            "requires_confirmation": True,
            "external_execution_before_confirmation": False,
            "store_name": store_name,
            "platform": first_present(store_profile.get("platform_label"), action.get("platform"), platform),
            "country": country,
        },
        raw_text=json.dumps(payload, ensure_ascii=False),
        source="approval_center.cloud_execution",
        score={"priority": safe_int(action.get("priority") or 80), "execution_risk": "external_store_action"},
        director_notes=[
            f"{package['task_package_label']} created after approval; it is not an external execution record.",
            "One store, one route, one isolated backend task identity.",
            readiness["operator_hint"],
        ],
        review_status="pending_execution",
    )


def cloud_activity_execution_plan(root: Path, action: dict[str, Any]) -> dict[str, Any]:
    action_type = str(action.get("action_type") or "").strip()
    text = " ".join(
        str(action.get(key) or "")
        for key in ["title", "reason", "next_step", "activity_type", "campaign_type"]
    ).lower()
    should_plan = action_type in {
        "pricing_promotion_draft",
        "ads_test_plan_draft",
        "set_discount",
        "launch_ad",
        "update_ad_budget",
    } or any(
        signal in text
        for signal in [
            "discount",
            "promotion",
            "coupon",
            "campaign",
            "voucher",
            "free shipping",
            "ads",
            "ad budget",
            "折扣",
            "优惠",
            "活动",
            "广告",
        ]
    )
    if not should_plan:
        return {}
    profile = account_center.load_profile(root)
    stores = profile.get("stores") if isinstance(profile.get("stores"), list) else []
    try:
        return build_platform_activity_execution_plan(root, action, stores)
    except Exception as exc:  # noqa: BLE001 - task creation must stay resilient.
        return {
            "ok": False,
            "plan_status": "activity_plan_failed",
            "missing_prerequisites": ["activity_plan_review"],
            "error": str(exc)[:240],
        }


def classify_cloud_execution_package(
    action: dict[str, Any], root: Path | None = None
) -> dict[str, Any]:
    action_type = str(action.get("action_type") or "").strip()
    text = " ".join(
        str(action.get(key) or "")
        for key in ["action_type", "title", "reason", "next_step", "platform", "store_name"]
    ).lower()
    source_package = str(action.get("source_package") or "").strip()
    explicit_package_type = str(action.get("cloud_task_package_type") or "").strip()
    private_binding = private_project_section("cloud_execution", root)
    explicit_source_packages = {
        str(item).strip()
        for item in private_binding.get("explicit_source_packages", [])
        if str(item).strip()
    }
    if explicit_package_type and (not source_package or source_package in explicit_source_packages):
        explicit_label = str(action.get("cloud_task_package_label") or "").strip() or explicit_package_type
        explicit_agent = str(action.get("target_agent_id") or "").strip() or "cloud_store_executor"
        explicit_steps = action.get("allowed_steps") if isinstance(action.get("allowed_steps"), list) else []
        explicit_evidence = action.get("required_evidence") if isinstance(action.get("required_evidence"), list) else []
        return {
            "task_type": "cloud_store_backend_action",
            "task_package_type": explicit_package_type,
            "task_package_label": explicit_label,
            "target_agent_id": explicit_agent,
            "action_surface": str(action.get("action_surface") or explicit_package_type).strip(),
            "allowed_steps": [str(item) for item in explicit_steps]
            or [
                "open_matching_cloud_profile",
                "read_explicit_task_package_scope",
                "collect_required_local_evidence",
                "stop_before_save_publish_submit_launch_coupon_price_inventory_ship_refund_payment_or_account_security",
                "write_result_back_to_erp",
            ],
            "required_evidence": [str(item) for item in explicit_evidence]
            or [
                "before_screenshot_ref",
                "after_screenshot_ref",
                "cloud_execution_log",
                "erp_result_payload",
                "rollback_status",
            ],
            "evidence_contract": evidence_contract(explicit_package_type),
        }
    source_packages = (
        private_binding.get("source_packages")
        if isinstance(private_binding.get("source_packages"), dict)
        else {}
    )
    package_binding = source_packages.get(source_package)
    if isinstance(package_binding, dict):
        package_type = str(package_binding.get("task_package_type") or "").strip()
        contract_type = str(package_binding.get("contract_type") or package_type).strip()
        required_evidence = [
            str(item) for item in package_binding.get("required_evidence", []) if str(item).strip()
        ]
        contract = evidence_contract(contract_type)
        contract_result_fields = [
            str(item)
            for item in package_binding.get("contract_required_result_fields", [])
            if str(item).strip()
        ]
        if contract_result_fields:
            contract["required_result_fields"] = merge_unique(
                contract.get("required_result_fields"), contract_result_fields
            )
        completion_suffix = str(package_binding.get("completion_rule_suffix") or "").strip()
        if completion_suffix:
            contract["completion_rule"] = (
                str(contract.get("completion_rule") or "") + "; " + completion_suffix
            ).strip("; ")
        return {
            "task_type": "cloud_store_backend_action",
            "task_package_type": package_type,
            "task_package_label": str(package_binding.get("task_package_label") or package_type),
            "target_agent_id": str(package_binding.get("target_agent_id") or "cloud_store_executor"),
            "action_surface": str(package_binding.get("action_surface") or package_type),
            "allowed_steps": [
                str(item) for item in package_binding.get("allowed_steps", []) if str(item).strip()
            ],
            "required_evidence": required_evidence,
            "evidence_contract": contract,
        }
    if is_amazon_listing_preflight_package(action_type, text):
        return {
            "task_type": "cloud_store_backend_action",
            "task_package_type": "listing_preflight",
            "task_package_label": "商品上架预检任务",
            "target_agent_id": "cloud_listing_preflight_executor",
            "action_surface": "seller_center_product_identity_or_sp_api_preflight",
            "allowed_steps": [
                "open_matching_cloud_profile",
                "read_current_listing_or_product_identity_state",
                "check_product_type_recommendation_and_schema",
                "check_item_type_keyword",
                "check_brand_registry_or_brand_authorization",
                "check_gtin_or_product_id_exemption",
                "check_variation_image_offer_readiness",
                "capture_before_screenshot",
                "stop_before_save_publish_submit_or_launch_ads",
                "write_preflight_result_back_to_erp",
            ],
            "required_evidence": [
                "product_identity_screenshot",
                "amazon_product_type_schema_ref",
                "amazon_item_type_keyword_ref",
                "amazon_brand_registry_status_ref",
                "amazon_gtin_or_exemption_ref",
                "amazon_variation_matrix_ref",
                "amazon_image_readiness_ref",
                "amazon_offer_readiness_ref",
                "amazon_preflight_blocker_summary",
                "cloud_execution_log",
                "erp_result_payload",
                "rollback_status",
            ],
            "evidence_contract": evidence_contract("listing_preflight"),
        }
    if action_type in ADS_ACTION_TYPES or any(signal in text for signal in ["ads", "广告", "投放", "roas", "campaign budget"]):
        return {
            "task_type": "cloud_ads_backend_action",
            "task_package_type": "ads_backend",
            "task_package_label": "广告后台任务",
            "target_agent_id": "cloud_ads_executor",
            "action_surface": "ads_backend_or_business_center",
            "allowed_steps": [
                "open_matching_ads_or_business_profile",
                "read_current_ads_state",
                "prepare_ads_campaign_or_budget_draft",
                "capture_before_screenshot",
                "stop_at_final_external_submit_until_executor_gate",
                "capture_after_screenshot_and_log_result",
                "write_result_back_to_erp",
            ],
            "required_evidence": [
                "ads_account_or_business_context_screenshot",
                "before_screenshot_ref",
                "campaign_or_budget_draft_screenshot",
                "after_screenshot_ref",
                "cloud_execution_log",
                "official_backend_confirmation_or_draft_id",
                "erp_result_payload",
                "rollback_status",
            ],
            "evidence_contract": evidence_contract("ads_backend"),
        }
    if action_type in CONTENT_CATALOG_ACTION_TYPES or any(signal in text for signal in ["catalog", "content", "asset", "video", "目录", "素材", "视频"]):
        return {
            "task_type": "cloud_content_catalog_action",
            "task_package_type": "content_catalog",
            "task_package_label": "内容目录任务",
            "target_agent_id": "cloud_content_catalog_executor",
            "action_surface": "content_catalog_or_creator_backend",
            "allowed_steps": [
                "open_matching_catalog_or_content_profile",
                "read_catalog_or_asset_state",
                "prepare_catalog_listing_or_asset_draft",
                "capture_before_screenshot",
                "stop_at_final_external_submit_until_executor_gate",
                "capture_after_screenshot_and_log_result",
                "write_result_back_to_erp",
            ],
            "required_evidence": [
                "catalog_or_asset_before_screenshot",
                "before_screenshot_ref",
                "draft_asset_or_catalog_screenshot",
                "after_screenshot_ref",
                "cloud_execution_log",
                "official_backend_confirmation_or_draft_id",
                "erp_result_payload",
                "rollback_status",
            ],
            "evidence_contract": evidence_contract("content_catalog"),
        }
    if action_type in READ_ONLY_COLLECTION_ACTION_TYPES or any(signal in text for signal in ["read-only", "readonly", "只读", "采集", "读取", "同步数据"]):
        return {
            "task_type": "cloud_read_only_collection_action",
            "task_package_type": "read_only_collection",
            "task_package_label": "只读采集任务",
            "target_agent_id": "cloud_read_only_collector",
            "action_surface": "authorized_report_or_visible_backend",
            "allowed_steps": [
                "open_matching_cloud_profile",
                "read_current_store_state",
                "collect_visible_or_authorized_data",
                "capture_source_evidence",
                "write_result_back_to_erp",
            ],
            "required_evidence": [
                "source_screenshot_or_report_name",
                "collected_fields_summary",
                "cloud_execution_log",
                "erp_result_payload",
                "rollback_status",
            ],
            "evidence_contract": evidence_contract("read_only_collection"),
        }
    return {
        "task_type": "cloud_store_backend_action",
        "task_package_type": "store_backend",
        "task_package_label": "店铺后台任务",
        "target_agent_id": "cloud_store_executor",
        "action_surface": "seller_center_or_store_backend",
        "allowed_steps": [
            "open_matching_cloud_profile",
            "read_current_store_state",
            "prepare_store_backend_change",
            "capture_before_screenshot",
            "stop_at_final_external_submit_until_executor_gate",
            "capture_after_screenshot_and_log_result",
            "write_result_back_to_erp",
        ],
        "required_evidence": [
            "before_screenshot",
            "before_screenshot_ref",
            "after_screenshot",
            "after_screenshot_ref",
            "cloud_execution_log",
            "official_backend_confirmation_or_draft_id",
            "erp_result_payload",
            "rollback_status",
        ],
        "evidence_contract": evidence_contract("store_backend"),
    }


def is_amazon_listing_preflight_package(action_type: str, text: str) -> bool:
    if action_type in {"amazon_listing_preflight", "amazon_product_identity_preflight"}:
        return True
    if action_type not in {"listing_draft", "publish_listing", "update_listing"}:
        return False
    amazon_signal = any(signal in text for signal in ["amazon", "seller central", "sellercentral"])
    listing_signal = any(
        signal in text
        for signal in [
            "product identity",
            "product type",
            "item type",
            "brand registry",
            "upc",
            "gtin",
            "product id exemption",
            "listing",
            "上架",
            "商品",
            "品牌",
            "条码",
        ]
    )
    non_listing_signal = any(signal in text for signal in ["coupon", "deal", "discount", "ads", "advertising", "campaign", "广告", "活动", "折扣"])
    return amazon_signal and listing_signal and not non_listing_signal


def evidence_contract(task_package_type: str) -> dict[str, Any]:
    common_fields = [
        "cloud_execution_log_summary",
        "erp_writeback_status",
        "owner_confirmation_status",
        "rollback_status",
    ]
    if task_package_type == "read_only_collection":
        required_fields = ["before_screenshot_ref", *common_fields]
        completion_rule = "source_evidence_and_log_then_erp_writeback; no external side effect allowed"
    elif task_package_type == "listing_preflight":
        required_fields = [
            "before_screenshot_ref",
            "after_screenshot_ref",
            "amazon_product_type_schema_ref",
            "amazon_item_type_keyword_ref",
            "amazon_brand_registry_status_ref",
            "amazon_gtin_or_exemption_ref",
            "amazon_variation_matrix_ref",
            "amazon_preflight_blocker_summary",
            *common_fields,
        ]
        completion_rule = "listing_preflight_evidence_and_blocker_summary_required; no save publish submit or ad launch allowed"
    elif task_package_type == "amazon_10001_owner_review":
        required_fields = [
            "before_screenshot_ref",
            "after_screenshot_ref",
            "amazon_10001_listing_review_ref",
            "amazon_10001_ads_keywords_ref",
            "amazon_10001_promotion_profit_ref",
            "amazon_10001_settlement_cashflow_ref",
            "amazon_10001_cost_input_values_ref",
            "amazon_10001_external_submit_blocked_ref",
            *common_fields,
        ]
        completion_rule = "amazon_10001_owner_review_four_module_evidence_required; no upload publish ads coupon price inventory shipment payment or account security action allowed"
    elif task_package_type == "amazon_10001_repair_followup":
        required_fields = [
            "before_screenshot_ref",
            "after_screenshot_ref",
            "amazon_10001_repair_module_ref",
            "amazon_10001_repair_blocker_summary_ref",
            "amazon_10001_external_submit_blocked_ref",
            *common_fields,
        ]
        completion_rule = "amazon_10001_repair_followup_module_evidence_required; no save publish submit ad launch coupon price inventory shipment payment or account security action allowed"
    elif task_package_type == "amazon_10001_final_gate_blocker":
        required_fields = [
            "before_screenshot_ref",
            "after_screenshot_ref",
            "amazon_10001_final_gate_blocker_ref",
            "amazon_10001_local_api_result_ref",
            "amazon_10001_final_gate_snapshot_ref",
            "amazon_10001_external_submit_blocked_ref",
            *common_fields,
        ]
        completion_rule = "amazon_10001_final_gate_blocker_evidence_required; only local evidence and local API checks are allowed; no external Amazon save publish submit ad launch coupon price inventory shipment payment or account security action"
    else:
        required_fields = [
            "execution_draft_id",
            "before_screenshot_ref",
            "after_screenshot_ref",
            *common_fields,
        ]
        completion_rule = "draft_id_before_after_log_erp_writeback_owner_confirmation_and_rollback_status_required"
    return {
        "required_result_fields": required_fields,
        "completion_rule": completion_rule,
        "external_submit_policy": "stop_before_final_external_submit; if submitted by owner, write evidence and rollback status",
        "rollback_status_allowed": [
            "not_needed",
            "rollback_ready",
            "rollback_completed",
            "rollback_blocked",
            "needs_rollback",
        ],
    }


def activity_execution_requirements(
    action: dict[str, Any],
    activity_plan: dict[str, Any],
    package: dict[str, Any],
    developer_capability_plan: dict[str, Any],
) -> dict[str, Any]:
    route = activity_plan if activity_plan else {}
    channel = channel_id(first_present(route.get("channel_id"), action.get("platform_id"), action.get("platform")))
    country = str(first_present(route.get("country_code"), action.get("country"), action.get("country_code"), default="GLOBAL")).upper()
    store_model = normalize_store_model_for_route(first_present(route.get("store_model"), action.get("store_model"), action.get("shop_type")))
    store_ownership = infer_store_ownership_for_route(
        {
            **action,
            **route,
            "store_model": store_model,
        }
    )
    activity_type = str(first_present(route.get("activity_type"), action.get("activity_type"), action.get("campaign_type"), action.get("action_type"))).lower()
    action_type = str(action.get("action_type") or "").strip()
    action_text = " ".join(
        str(value or "")
        for value in [
            action.get("action_type"),
            action.get("title"),
            action.get("reason"),
            action.get("next_step"),
            action.get("activity_type"),
            action.get("campaign_type"),
            " ".join(str(item) for item in route.get("site_activity_focus", []) if item),
        ]
    ).lower()
    requested_domains = [
        str(item or "").lower()
        for item in developer_capability_plan.get("requested_domains", [])
        if str(item or "").strip()
    ]
    includes_ads = bool(route.get("includes_ads")) or package.get("task_package_type") == "ads_backend" or "ads" in requested_domains
    is_tiktok = channel in {"tiktok", "tiktok_shop", "tiktokshop"} or "tiktok" in action_text
    is_shopee = channel == "shopee" or "shopee" in action_text
    is_lazada = channel == "lazada" or "lazada" in action_text
    is_amazon = channel == "amazon" or "amazon" in action_text
    is_walmart = channel == "walmart" or "walmart" in action_text
    is_shopify = channel == "shopify" or "shopify" in action_text
    is_woocommerce = channel == "woocommerce" or "woo commerce" in action_text or "woo" in action_text
    is_independent_store = is_shopify or is_woocommerce
    is_campaign_channel = is_tiktok or is_shopee or is_lazada or is_amazon or is_walmart or is_independent_store
    is_listing_preflight = package.get("task_package_type") == "listing_preflight" or action_type in {
        "amazon_listing_preflight",
        "amazon_product_identity_preflight",
    }
    is_amazon_owner_review = str(action.get("source_package") or "") == "amazon_10001_owner_review_package"
    is_amazon_gtin_evidence_review = str(action.get("source_package") or "") == "amazon_10001_gtin_evidence_review"
    requirements: dict[str, Any] = {
        "route_key": first_present(route.get("route_key"), action.get("route_key")),
        "channel_id": channel,
        "country_code": country,
        "store_model": store_model,
        "store_ownership": store_ownership,
        "store_ownership_label": store_ownership_label(store_ownership),
        "activity_type": activity_type,
        "required_preflight_checks": [
            "open_matching_store_identity",
            "store_ownership_checked",
            "capture_before_screenshot",
            "owner_confirmation",
        ],
        "required_materials": [],
        "required_draft_outputs": [],
        "required_evidence": [],
        "required_result_fields": [],
        "activity_surface_requirements": {
            "external_submit_allowed": False,
            "owner_confirmation_required": True,
            "stop_before_submit": True,
            "single_store_identity_required": True,
            "store_ownership_required": True,
        },
        "external_submit_allowed": False,
        "owner_confirmation_required": True,
        "stop_before_submit": True,
    }
    if is_amazon_owner_review:
        requirements["activity_type"] = "amazon_10001_owner_review"
        requirements["required_preflight_checks"].extend(
            [
                "amazon_10001_owner_review_package_loaded",
                "amazon_10001_listing_copy_reviewed",
                "amazon_10001_image_mapping_reviewed",
                "amazon_10001_cost_input_values_checked",
                "amazon_10001_ads_keywords_reviewed",
                "amazon_10001_coupon_scenario_reviewed",
                "amazon_10001_settlement_formula_reviewed",
                "seller_central_external_submit_still_blocked",
            ]
        )
        requirements["required_materials"].extend(
            [
                "amazon_10001_owner_review_package_ref",
                "amazon_10001_listing_title_bullets_search_terms",
                "amazon_10001_ads_keyword_budget_draft",
                "amazon_10001_coupon_profit_scenario",
                "amazon_10001_settlement_cashflow_formula",
                "amazon_10001_cost_assumption_or_real_cost_sheet",
            ]
        )
        requirements["required_draft_outputs"].extend(
            [
                "amazon_10001_listing_review_decision",
                "amazon_10001_ads_review_decision",
                "amazon_10001_promotion_review_decision",
                "amazon_10001_settlement_review_decision",
                "amazon_10001_blocker_resolution_checklist",
            ]
        )
        requirements["required_evidence"].extend(
            [
                "amazon_10001_owner_review_package_screenshot",
                "amazon_10001_listing_review_ref",
                "amazon_10001_ads_keywords_ref",
                "amazon_10001_promotion_profit_ref",
                "amazon_10001_settlement_cashflow_ref",
                "amazon_10001_cost_input_values_ref",
                "amazon_10001_external_submit_blocked_ref",
            ]
        )
        requirements["required_result_fields"].extend(
            [
                "amazon_10001_listing_review_ref",
                "amazon_10001_ads_keywords_ref",
                "amazon_10001_promotion_profit_ref",
                "amazon_10001_settlement_cashflow_ref",
                "amazon_10001_cost_input_values_ref",
                "amazon_10001_external_submit_blocked_ref",
            ]
        )
        requirements["activity_surface_requirements"].update(
            {
                "seller_central_upload_allowed": False,
                "listing_publish_allowed": False,
                "ads_launch_allowed": False,
                "coupon_submit_allowed": False,
                "price_update_allowed": False,
                "inventory_update_allowed": False,
            }
        )
        return dedupe_requirement_lists(requirements)
    if is_amazon_gtin_evidence_review:
        requirements["activity_type"] = "amazon_10001_gtin_evidence_review"
        requirements["required_preflight_checks"].extend(
            [
                "amazon_10001_gtin_evidence_review_scope_loaded",
                "amazon_product_identity_page_captured",
                "amazon_gtin_or_product_id_exemption_checked",
                "amazon_10001_product_photos_checked",
                "amazon_10001_no_barcode_evidence_checked",
                "amazon_10001_gtin_approval_or_legal_gs1_checked",
                "seller_central_external_submit_still_blocked",
            ]
        )
        requirements["required_materials"].extend(
            [
                "seller_central_product_identity_page",
                "gtin_exemption_product_photos_2_to_9",
                "packaging_or_product_no_barcode_evidence",
                "approved_gtin_exemption_capture_or_legal_gs1_proof",
            ]
        )
        requirements["required_draft_outputs"].extend(
            [
                "amazon_10001_gtin_evidence_review_decision",
                "amazon_10001_product_identity_blocker_summary",
                "amazon_10001_next_upload_candidate_gate",
            ]
        )
        requirements["required_evidence"].extend(
            [
                "amazon_10001_gtin_product_identity_page_ref",
                "amazon_10001_gtin_product_photos_ref",
                "amazon_10001_gtin_no_barcode_evidence_ref",
                "amazon_10001_gtin_approval_or_gs1_ref",
                "amazon_10001_external_submit_blocked_ref",
            ]
        )
        requirements["required_result_fields"].extend(
            [
                "amazon_10001_gtin_product_identity_page_ref",
                "amazon_10001_gtin_product_photos_ref",
                "amazon_10001_gtin_no_barcode_evidence_ref",
                "amazon_10001_gtin_approval_or_gs1_ref",
                "amazon_10001_external_submit_blocked_ref",
            ]
        )
        requirements["activity_surface_requirements"].update(
            {
                "seller_central_submit_allowed": False,
                "product_id_exemption_apply_allowed": False,
                "listing_publish_allowed": False,
                "ads_launch_allowed": False,
                "price_update_allowed": False,
            }
        )
        return dedupe_requirement_lists(requirements)
    if is_amazon and is_listing_preflight:
        requirements["activity_type"] = "amazon_listing_preflight"
        requirements["required_preflight_checks"].extend(
            [
                "amazon_sp_api_authorization_checked",
                "seller_central_access_checked",
                "amazon_product_type_recommendation_checked",
                "amazon_product_type_schema_checked",
                "amazon_listing_restrictions_checked",
                "amazon_item_type_keyword_checked",
                "amazon_brand_registry_or_brand_authorization_checked",
                "amazon_gtin_or_product_id_exemption_checked",
                "amazon_variation_theme_checked",
                "amazon_image_readiness_checked",
                "amazon_offer_readiness_checked",
                "amazon_ads_eligibility_blocked_until_listable_asin",
            ]
        )
        requirements["required_materials"].extend(
            [
                "product_title",
                "product_type",
                "color_size_variation_matrix",
                "image_ready_color_set",
                "brand_route_decision",
                "gtin_or_product_id_exemption_decision",
                "offer_price_shipping_return_inputs",
            ]
        )
        requirements["required_draft_outputs"].extend(
            [
                "amazon_listing_preflight_report",
                "amazon_product_identity_field_map",
                "amazon_variation_sku_matrix_draft",
                "amazon_blocker_resolution_plan",
                "amazon_ads_wait_until_asin_sku_ready_note",
            ]
        )
        requirements["required_evidence"].extend(
            [
                "amazon_product_type_schema_ref",
                "amazon_listing_restrictions_ref",
                "amazon_item_type_keyword_ref",
                "amazon_brand_registry_status_ref",
                "amazon_gtin_or_exemption_ref",
                "amazon_variation_matrix_ref",
                "amazon_image_readiness_ref",
                "amazon_offer_readiness_ref",
                "amazon_preflight_blocker_summary",
            ]
        )
        requirements["required_result_fields"].extend(
            [
                "amazon_product_type_schema_ref",
                "amazon_item_type_keyword_ref",
                "amazon_brand_registry_status_ref",
                "amazon_gtin_or_exemption_ref",
                "amazon_variation_matrix_ref",
                "amazon_preflight_blocker_summary",
            ]
        )
        return dedupe_requirement_lists(requirements)

    if not is_campaign_channel:
        return dedupe_requirement_lists(requirements)

    requirements["required_preflight_checks"].extend(
        [
            "platform_activity_rule_checked",
            "campaign_calendar_checked",
            "store_country_and_model_checked",
            "store_ownership_scope_checked",
            "margin_guardrail_checked",
            "inventory_sla_checked",
        ]
    )
    requirements["required_evidence"].extend(
        [
            "platform_activity_rule_ref",
            "margin_inventory_check_ref",
            "store_country_model_ref",
            "store_ownership_scope_ref",
        ]
    )
    requirements["required_result_fields"].extend(
        [
            "platform_activity_rule_ref",
            "margin_inventory_check_ref",
            "store_ownership_scope_ref",
        ]
    )
    if country in {"MY", "TH", "SG", "VN", "PH", "ID"} or is_shopee or is_lazada:
        requirements["required_preflight_checks"].extend(
            [
                "country_site_rule_checked",
                "local_currency_margin_checked",
                "local_delivery_sla_checked",
                "local_payment_or_cod_scope_checked",
            ]
        )
        requirements["required_evidence"].extend(
            [
                "country_campaign_calendar_ref",
                "local_currency_margin_ref",
                "local_delivery_sla_ref",
                "local_payment_cod_ref",
            ]
        )
        requirements["required_result_fields"].extend(
            [
                "country_campaign_calendar_ref",
                "local_currency_margin_ref",
                "local_delivery_sla_ref",
                "local_payment_cod_ref",
            ]
        )
    if is_amazon:
        requirements["required_preflight_checks"].extend(
            [
                "amazon_marketplace_site_checked",
                "amazon_sp_api_authorization_checked",
                "seller_central_access_checked",
                "buy_box_price_checked",
                "fba_or_mfn_stock_sla_checked",
            ]
        )
        requirements["required_materials"].extend(
            [
                "asin_sku_mapping_ref",
                "amazon_marketplace_terms_ref",
                "fee_and_acos_margin_ref",
            ]
        )
        requirements["required_evidence"].extend(
            [
                "amazon_marketplace_site_ref",
                "sp_api_authorization_ref",
                "seller_central_access_ref",
                "buy_box_price_ref",
                "fba_mfn_stock_sla_ref",
            ]
        )
        requirements["required_result_fields"].extend(
            [
                "amazon_marketplace_site_ref",
                "sp_api_authorization_ref",
                "seller_central_access_ref",
                "buy_box_price_ref",
                "fba_mfn_stock_sla_ref",
            ]
        )
    if is_walmart:
        requirements["required_preflight_checks"].extend(
            [
                "walmart_marketplace_site_checked",
                "walmart_marketplace_seller_authorization_checked",
                "walmart_seller_center_access_checked",
                "walmart_buy_box_price_checked",
                "walmart_stock_fulfillment_sla_checked",
            ]
        )
        requirements["required_materials"].extend(
            [
                "walmart_item_sku_mapping_ref",
                "walmart_marketplace_terms_ref",
                "price_fee_shipping_margin_ref",
            ]
        )
        requirements["required_evidence"].extend(
            [
                "walmart_marketplace_site_ref",
                "walmart_seller_authorization_ref",
                "walmart_seller_center_access_ref",
                "walmart_buy_box_price_ref",
                "walmart_stock_fulfillment_sla_ref",
            ]
        )
        requirements["required_result_fields"].extend(
            [
                "walmart_marketplace_site_ref",
                "walmart_seller_authorization_ref",
                "walmart_seller_center_access_ref",
                "walmart_buy_box_price_ref",
                "walmart_stock_fulfillment_sla_ref",
            ]
        )
    if is_shopify:
        requirements["required_preflight_checks"].extend(
            [
                "shopify_store_instance_checked",
                "shopify_app_scope_checked",
                "shopify_write_discounts_scope_checked",
                "shopify_discount_combination_checked",
                "shopify_payment_tax_shipping_checked",
            ]
        )
        requirements["required_materials"].extend(
            [
                "shopify_store_domain_ref",
                "shopify_discount_terms_ref",
                "shopify_product_collection_scope_ref",
                "shopify_margin_tax_shipping_ref",
            ]
        )
        requirements["required_evidence"].extend(
            [
                "shopify_store_instance_ref",
                "shopify_app_scope_ref",
                "shopify_discount_combination_ref",
                "shopify_payment_tax_shipping_ref",
            ]
        )
        requirements["required_result_fields"].extend(
            [
                "shopify_store_instance_ref",
                "shopify_app_scope_ref",
                "shopify_discount_combination_ref",
                "shopify_payment_tax_shipping_ref",
            ]
        )
    if is_woocommerce:
        requirements["required_preflight_checks"].extend(
            [
                "woocommerce_store_instance_checked",
                "woocommerce_rest_key_or_plugin_scope_checked",
                "woocommerce_coupon_stack_checked",
                "woocommerce_shipping_zone_checked",
                "woocommerce_payment_tax_shipping_checked",
            ]
        )
        requirements["required_materials"].extend(
            [
                "woocommerce_store_url_ref",
                "woocommerce_coupon_terms_ref",
                "woocommerce_shipping_zone_ref",
                "woocommerce_margin_tax_shipping_ref",
            ]
        )
        requirements["required_evidence"].extend(
            [
                "woocommerce_store_instance_ref",
                "woocommerce_rest_key_plugin_scope_ref",
                "woocommerce_coupon_stack_ref",
                "woocommerce_shipping_zone_ref",
            ]
        )
        requirements["required_result_fields"].extend(
            [
                "woocommerce_store_instance_ref",
                "woocommerce_rest_key_plugin_scope_ref",
                "woocommerce_coupon_stack_ref",
                "woocommerce_shipping_zone_ref",
            ]
        )
    if is_shopee:
        requirements["required_preflight_checks"].extend(
            [
                "shopee_shop_access_token_checked",
                "shopee_merchant_or_shop_permission_checked",
                "shopee_shop_id_route_checked",
            ]
        )
        requirements["required_materials"].extend(
            [
                "shopee_shop_voucher_terms_ref",
                "shopee_free_shipping_terms_ref",
                "localized_product_price_ref",
            ]
        )
        requirements["required_evidence"].extend(
            [
                "shopee_shop_permission_ref",
                "shopee_shop_id_route_ref",
            ]
        )
        requirements["required_result_fields"].extend(
            [
                "shopee_shop_permission_ref",
                "shopee_shop_id_route_ref",
            ]
        )
    if is_lazada:
        requirements["required_preflight_checks"].extend(
            [
                "lazada_seller_authorization_code_checked",
                "lazada_seller_access_token_checked",
                "lazada_seller_id_route_checked",
                "lazada_seller_voucher_api_permission_checked",
            ]
        )
        requirements["required_materials"].extend(
            [
                "lazada_seller_voucher_terms_ref",
                "lazada_free_shipping_terms_ref",
                "seller_id_mapping_ref",
            ]
        )
        requirements["required_evidence"].extend(
            [
                "lazada_seller_authorization_ref",
                "lazada_seller_id_route_ref",
                "seller_voucher_api_permission_ref",
            ]
        )
        requirements["required_result_fields"].extend(
            [
                "lazada_seller_authorization_ref",
                "lazada_seller_id_route_ref",
                "seller_voucher_api_permission_ref",
            ]
        )

    if includes_ads or any(signal in activity_type + " " + action_text for signal in ["gmv max", "gmv_max", "shop_ads", "ad ", "ads", "roas"]):
        requirements["required_preflight_checks"].extend(
            [
                "ads_account_registered",
                "business_center_registered",
                "shop_ads_budget_guardrail",
                "break_even_roas_checked",
                "creative_scorecard_checked",
                "owner_confirmation",
            ]
        )
        requirements["required_materials"].extend(
            [
                "minimum_three_creatives",
                "product_proof_creative",
                "hook_first_two_seconds",
                "offer_angle_creative",
                "creator_or_ugc_asset",
                "product_card_or_cta_ready",
                "ip_music_claims_review",
            ]
        )
        requirements["required_draft_outputs"].extend(
            [
                "gmv_max_or_shop_ads_draft",
                "budget_ladder_draft",
                "pause_rules_draft",
                "creative_rotation_plan",
            ]
        )
        requirements["required_evidence"].extend(
            [
                "creative_pack_ref",
                "budget_ladder_ref",
                "pause_rules_ref",
                "ad_account_context_ref",
            ]
        )
        requirements["required_result_fields"].extend(
            [
                "creative_pack_ref",
                "budget_ladder_ref",
                "pause_rules_ref",
                "ad_account_context_ref",
            ]
        )

    if any(signal in activity_type + " " + action_text for signal in ["affiliate", "creator", "达人", "联盟", "creator_coupon", "live_coupon"]):
        requirements["required_preflight_checks"].extend(
            [
                "affiliate_permission_checked",
                "creator_commission_checked",
                "creator_scope_checked",
            ]
        )
        requirements["required_materials"].extend(
            [
                "creator_brief_ref",
                "commission_plan_ref",
                "product_sample_or_offer_ref",
            ]
        )
        requirements["required_draft_outputs"].extend(
            [
                "affiliate_or_creator_coupon_draft",
                "creator_brief_draft",
            ]
        )
        requirements["required_evidence"].extend(["creator_brief_ref", "commission_plan_ref"])
        requirements["required_result_fields"].extend(["creator_brief_ref", "commission_plan_ref"])

    if any(signal in activity_type + " " + action_text for signal in ["coupon", "voucher", "discount", "promotion", "free_shipping", "free shipping", "免邮", "优惠", "折扣"]):
        requirements["required_preflight_checks"].extend(
            [
                "coupon_stack_checked",
                "free_shipping_margin_checked",
                "campaign_price_confirmed",
                "inventory_sla_checked",
            ]
        )
        requirements["required_draft_outputs"].extend(
            [
                "coupon_or_voucher_draft",
                "free_shipping_draft",
                "stacking_rules_ref",
            ]
        )
        requirements["required_evidence"].extend(
            [
                "coupon_stack_ref",
                "free_shipping_margin_ref",
                "campaign_price_ref",
            ]
        )
        requirements["required_result_fields"].extend(
            [
                "coupon_stack_ref",
                "free_shipping_margin_ref",
                "campaign_price_ref",
            ]
        )
        if is_shopee or is_lazada:
            requirements["required_draft_outputs"].extend(
                [
                    "seller_or_shop_voucher_draft",
                    "bundle_deal_or_product_discount_draft",
                    "localized_campaign_terms_draft",
                ]
            )
            requirements["required_evidence"].extend(
                [
                    "voucher_stack_ref",
                    "localized_campaign_terms_ref",
                ]
            )
            requirements["required_result_fields"].extend(
                [
                    "voucher_stack_ref",
                    "localized_campaign_terms_ref",
                ]
            )
        if is_shopify:
            requirements["required_preflight_checks"].extend(
                [
                    "shopify_discount_code_or_automatic_type_checked",
                    "shopify_discount_function_scope_checked",
                    "shopify_free_shipping_rate_checked",
                    "shopify_rollback_plan_checked",
                ]
            )
            requirements["required_draft_outputs"].extend(
                [
                    "shopify_discount_code_draft",
                    "shopify_automatic_discount_draft",
                    "shopify_free_shipping_discount_draft",
                    "shopify_discount_combination_rules_draft",
                    "shopify_rollback_plan_draft",
                ]
            )
            requirements["required_evidence"].extend(
                [
                    "shopify_discount_type_ref",
                    "shopify_discount_function_scope_ref",
                    "shopify_free_shipping_rate_ref",
                    "shopify_rollback_plan_ref",
                ]
            )
            requirements["required_result_fields"].extend(
                [
                    "shopify_discount_type_ref",
                    "shopify_discount_function_scope_ref",
                    "shopify_free_shipping_rate_ref",
                    "shopify_rollback_plan_ref",
                ]
            )
        if is_woocommerce:
            requirements["required_preflight_checks"].extend(
                [
                    "woocommerce_coupon_type_checked",
                    "woocommerce_usage_restrictions_checked",
                    "woocommerce_free_shipping_method_checked",
                    "woocommerce_sale_price_scope_checked",
                    "woocommerce_rollback_plan_checked",
                ]
            )
            requirements["required_draft_outputs"].extend(
                [
                    "woocommerce_coupon_draft",
                    "woocommerce_sale_price_draft",
                    "woocommerce_free_shipping_coupon_draft",
                    "woocommerce_coupon_stack_rules_draft",
                    "woocommerce_rollback_plan_draft",
                ]
            )
            requirements["required_evidence"].extend(
                [
                    "woocommerce_coupon_type_ref",
                    "woocommerce_usage_restrictions_ref",
                    "woocommerce_free_shipping_method_ref",
                    "woocommerce_sale_price_scope_ref",
                    "woocommerce_rollback_plan_ref",
                ]
            )
            requirements["required_result_fields"].extend(
                [
                    "woocommerce_coupon_type_ref",
                    "woocommerce_usage_restrictions_ref",
                    "woocommerce_free_shipping_method_ref",
                    "woocommerce_sale_price_scope_ref",
                    "woocommerce_rollback_plan_ref",
                ]
            )

    if (is_amazon or is_walmart) and any(
        signal in activity_type + " " + action_text
        for signal in ["coupon", "voucher", "discount", "promotion", "deal", "price_discount", "rollbacks", "rollback"]
    ):
        requirements["required_preflight_checks"].extend(
            [
                "marketplace_promotion_eligibility_checked",
                "buy_box_or_competitive_price_checked",
                "fee_margin_stack_checked",
                "stock_fulfillment_sla_checked",
            ]
        )
        requirements["required_draft_outputs"].extend(
            [
                "marketplace_coupon_or_deal_draft",
                "price_discount_draft",
                "promotion_stack_rules_draft",
            ]
        )
        requirements["required_evidence"].extend(
            [
                "marketplace_promotion_eligibility_ref",
                "competitive_price_ref",
                "fee_margin_stack_ref",
                "stock_fulfillment_sla_ref",
            ]
        )
        requirements["required_result_fields"].extend(
            [
                "marketplace_promotion_eligibility_ref",
                "competitive_price_ref",
                "fee_margin_stack_ref",
                "stock_fulfillment_sla_ref",
            ]
        )
        if is_amazon:
            requirements["required_preflight_checks"].extend(
                [
                    "amazon_coupon_or_deal_eligibility_checked",
                    "seller_central_promotion_terms_checked",
                ]
            )
            requirements["required_draft_outputs"].extend(
                [
                    "amazon_coupon_or_deal_draft",
                    "amazon_seller_central_terms_draft",
                ]
            )
            requirements["required_evidence"].extend(
                [
                    "amazon_coupon_deal_eligibility_ref",
                    "amazon_seller_central_terms_ref",
                ]
            )
            requirements["required_result_fields"].extend(
                [
                    "amazon_coupon_deal_eligibility_ref",
                    "amazon_seller_central_terms_ref",
                ]
            )
        if is_walmart:
            requirements["required_preflight_checks"].extend(
                [
                    "walmart_promotion_price_rule_checked",
                    "walmart_marketplace_promotion_terms_checked",
                ]
            )
            requirements["required_draft_outputs"].extend(
                [
                    "walmart_promotion_or_price_discount_draft",
                    "walmart_marketplace_terms_draft",
                ]
            )
            requirements["required_evidence"].extend(
                [
                    "walmart_promotion_price_rule_ref",
                    "walmart_marketplace_terms_ref",
                ]
            )
            requirements["required_result_fields"].extend(
                [
                    "walmart_promotion_price_rule_ref",
                    "walmart_marketplace_terms_ref",
                ]
            )

    if (is_amazon or is_walmart) and (
        includes_ads
        or any(signal in activity_type + " " + action_text for signal in ["sponsored", "ads", "ad ", "acos", "roas", "campaign"])
    ):
        if is_amazon:
            requirements["required_preflight_checks"].extend(
                [
                    "amazon_ads_authorization_checked",
                    "amazon_ads_profile_checked",
                    "sponsored_products_budget_guardrail",
                    "acos_break_even_checked",
                ]
            )
            requirements["required_draft_outputs"].extend(
                [
                    "amazon_sponsored_products_campaign_draft",
                    "amazon_ads_budget_ladder_draft",
                    "amazon_ads_pause_rules_draft",
                ]
            )
            requirements["required_evidence"].extend(
                [
                    "amazon_ads_authorization_ref",
                    "amazon_ads_profile_ref",
                    "acos_budget_guardrail_ref",
                ]
            )
            requirements["required_result_fields"].extend(
                [
                    "amazon_ads_authorization_ref",
                    "amazon_ads_profile_ref",
                    "acos_budget_guardrail_ref",
                ]
            )
        if is_walmart:
            requirements["required_preflight_checks"].extend(
                [
                    "walmart_connect_authorization_checked",
                    "walmart_connect_advertiser_checked",
                    "walmart_connect_budget_guardrail",
                    "walmart_roas_break_even_checked",
                ]
            )
            requirements["required_draft_outputs"].extend(
                [
                    "walmart_connect_sponsored_products_campaign_draft",
                    "walmart_connect_budget_ladder_draft",
                    "walmart_connect_pause_rules_draft",
                ]
            )
            requirements["required_evidence"].extend(
                [
                    "walmart_connect_authorization_ref",
                    "walmart_connect_advertiser_ref",
                    "walmart_connect_budget_guardrail_ref",
                ]
            )
            requirements["required_result_fields"].extend(
                [
                    "walmart_connect_authorization_ref",
                    "walmart_connect_advertiser_ref",
                    "walmart_connect_budget_guardrail_ref",
                ]
            )

    if is_independent_store and (
        includes_ads
        or any(signal in activity_type + " " + action_text for signal in ["ads", "ad ", "meta", "google", "tiktok", "roas", "campaign"])
    ):
        requirements["required_preflight_checks"].extend(
            [
                "external_ads_account_separate_from_store_checked",
                "pixel_or_catalog_mapping_checked",
                "utm_and_landing_page_checked",
                "ad_budget_guardrail_checked",
            ]
        )
        requirements["required_draft_outputs"].extend(
            [
                "independent_store_ads_brief_draft",
                "external_ads_budget_ladder_draft",
                "landing_page_utm_plan_draft",
            ]
        )
        requirements["required_evidence"].extend(
            [
                "external_ads_account_ref",
                "pixel_catalog_mapping_ref",
                "landing_page_utm_ref",
                "independent_store_ad_budget_guardrail_ref",
            ]
        )
        requirements["required_result_fields"].extend(
            [
                "external_ads_account_ref",
                "pixel_catalog_mapping_ref",
                "landing_page_utm_ref",
                "independent_store_ad_budget_guardrail_ref",
            ]
        )

    if "semi_managed" in store_model:
        requirements["required_preflight_checks"].append("semi_managed_scope_confirmed")
        requirements["required_evidence"].append("fulfillment_scope_ref")
        requirements["required_result_fields"].append("fulfillment_scope_ref")
    if store_model == "tiktok_accu_local":
        requirements["required_preflight_checks"].append("accu_partner_scope_confirmed")
        requirements["required_evidence"].append("accu_scope_ref")
        requirements["required_result_fields"].append("accu_scope_ref")

    return dedupe_requirement_lists(requirements)


def merge_evidence_contract(contract: dict[str, Any], activity_requirements: dict[str, Any]) -> dict[str, Any]:
    merged = dict(contract)
    merged["required_result_fields"] = merge_unique(
        contract.get("required_result_fields"),
        activity_requirements.get("required_result_fields"),
    )
    if activity_requirements.get("required_result_fields"):
        merged["completion_rule"] = (
            str(contract.get("completion_rule") or "")
            + "; activity_specific_materials_and_policy_evidence_required"
        ).strip("; ")
    return merged


def dedupe_requirement_lists(requirements: dict[str, Any]) -> dict[str, Any]:
    for key in [
        "required_preflight_checks",
        "required_materials",
        "required_draft_outputs",
        "required_evidence",
        "required_result_fields",
    ]:
        requirements[key] = merge_unique(requirements.get(key))
    return requirements


def merge_unique(*values: Any) -> list[Any]:
    result: list[Any] = []
    for value in values:
        if not value:
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            if item not in result:
                result.append(item)
    return result


def cloud_execution_readiness(
    package: dict[str, Any],
    store_profile: dict[str, Any],
    action: dict[str, Any],
) -> dict[str, Any]:
    plan = activity_plan_from_action(action)
    has_store_route = bool(store_profile) or bool(
        first_present(
            action.get("store_name"),
            action.get("store"),
            action.get("store_id"),
            plan.get("store_name"),
        )
    )
    if not has_store_route and package["task_package_type"] != "read_only_collection":
        return {
            "status": "waiting_platform_store",
            "execution_readiness": "needs_platform_store",
            "execution_readiness_label": "缺店铺",
            "missing_prerequisites": ["platform_store"],
            "operator_hint": "后台还没有匹配到真实平台店铺；只能做候选和草稿，不能进入外部后台执行。",
        }
    route_missing = cloud_store_route_missing_prerequisites(store_profile) if store_profile else []
    if route_missing and package["task_package_type"] != "read_only_collection":
        return {
            "status": "waiting_platform_store",
            "execution_readiness": "needs_platform_store",
            "execution_readiness_label": "缺店铺",
            "missing_prerequisites": route_missing,
            "operator_hint": "后台店铺还缺真实平台店铺身份或授权范围；内部子店铺 / 业务线只作备注，不能生成可执行上架、拉单或投放任务。",
        }
    if route_missing and package["task_package_type"] == "read_only_collection":
        return {
            "status": "waiting_read_source",
            "execution_readiness": "draft_only",
            "execution_readiness_label": "只能草稿",
            "missing_prerequisites": route_missing,
            "operator_hint": "只读采集还缺平台店铺身份或授权范围；先保留读取清单和草稿，不把内部备注当成执行身份。",
        }
    if package["task_package_type"] == "ads_backend":
        has_ads_identity = bool(first_present(store_profile.get("ads_account_id"), action.get("ads_account_id"))) and bool(
            first_present(store_profile.get("business_center_id"), action.get("business_center_id"))
        )
        if not has_ads_identity:
            return {
                "status": "waiting_ads_account",
                "execution_readiness": "needs_ads_account",
                "execution_readiness_label": "缺广告账号",
                "missing_prerequisites": ["ads_account", "business_center"],
                "operator_hint": "广告动作必须先登记广告账号和广告归属主体；当前只保留广告草稿和止损线。",
            }
    if package["task_package_type"] == "listing_preflight":
        publish_blockers = amazon_listing_publish_blockers(action)
        return {
            "status": "waiting_owner_manual_execution",
            "execution_readiness": "preflight_ready_publish_blocked" if publish_blockers else "preflight_ready",
            "execution_readiness_label": "可预检，不能发布" if publish_blockers else "可预检",
            "missing_prerequisites": publish_blockers,
            "operator_hint": (
                "后台执行身份只做 Amazon 商品上架前置检查和截图回写；"
                "品牌、UPC/GTIN、类目或 ASIN/SKU 未通过前，不保存正式草稿、不发布、不启动广告。"
            ),
        }
    if package["task_package_type"] == "read_only_collection" and not has_store_route:
        return {
            "status": "waiting_read_source",
            "execution_readiness": "draft_only",
            "execution_readiness_label": "只能草稿",
            "missing_prerequisites": ["readable_store_or_report_source"],
            "operator_hint": "只读采集还缺可读取店铺或报表来源；先生成读取清单，等待负责人打开来源。",
        }
    return {
        "status": "waiting_owner_manual_execution",
        "execution_readiness": "ready_after_confirmation",
        "execution_readiness_label": "已确认，待负责人手动执行",
        "missing_prerequisites": [],
        "operator_hint": "负责人已登记确认，系统只准备后台待执行包；仍需负责人按官方后台手动执行并回写证据，不自动提交外部平台。",
    }


def amazon_listing_publish_blockers(action: dict[str, Any]) -> list[str]:
    text = " ".join(
        str(action.get(key) or "")
        for key in [
            "title",
            "reason",
            "next_step",
            "observed_status",
            "listing_status",
            "product_identity_status",
        ]
    ).lower()
    explicit = action.get("listing_blockers") or action.get("publish_blockers") or action.get("missing_prerequisites")
    blockers = [str(item).strip() for item in explicit if str(item).strip()] if isinstance(explicit, list) else []
    if any(signal in text for signal in ["brand registry", "brand_registry", "品牌", "teelab"]):
        blockers.append("amazon_brand_registry_or_brand_authorization")
    if any(signal in text for signal in ["upc", "gtin", "product id exemption", "product_id_exemption", "条码", "豁免"]):
        blockers.append("amazon_gtin_or_product_id_exemption")
    if any(signal in text for signal in ["item type", "item_type", "boys", "women", "novelty", "类目"]):
        blockers.append("amazon_item_type_keyword_recheck")
    if any(
        signal in text
        for signal in [
            "itemtype=undefined",
            "recommendedbrowsenodeid=undefined",
            "displaypath=undefined",
            "category_route_undefined",
            "category route undefined",
            "category route is undefined",
            "类目路径",
            "类目来源",
        ]
    ):
        blockers.append("amazon_category_route_undefined")
    if any(
        signal in text
        for signal in [
            "variant images: 0",
            "images: 0",
            "variant_color_images_incomplete",
            "color images incomplete",
            "color image mapping incomplete",
            "颜色变体图片",
            "颜色图片",
            "图片映射不完整",
        ]
    ):
        blockers.append("amazon_variant_color_images_incomplete")
    if any(signal in text for signal in ["ready to submit", "ready_to_submit_guarded", "ready 草稿"]):
        blockers.append("amazon_ready_to_submit_guarded")
    if any(
        signal in text
        for signal in [
            "girls",
            "visible_path_gender_mismatch",
            "duplicate_value_requires_visible_path_guard",
            "visible path is boys/women/girls/novelty",
        ]
    ):
        blockers.append("amazon_item_type_keyword_recheck")
    return list(dict.fromkeys(blockers))


def match_store_profile(root: Path, action: dict[str, Any]) -> dict[str, Any]:
    profile = account_center.load_profile(root)
    stores = profile.get("stores") if isinstance(profile.get("stores"), list) else []
    if not stores:
        return {}
    plan = activity_plan_from_action(action)
    route_key = action_route_key(action, plan)
    route_parts = route_parts_from_key(route_key)
    action_platform = normalize_match_value(
        first_present(
            action.get("platform"),
            action.get("platform_id"),
            action.get("marketplace"),
            route_parts.get("platform"),
            plan.get("channel_id"),
        )
    )
    action_store = normalize_match_value(
        first_present(
            action.get("store_name"),
            action.get("store"),
            action.get("store_id"),
            plan.get("store_name"),
        )
    )
    action_country = normalize_match_value(
        first_present(action.get("country"), action.get("country_code"), route_parts.get("country"), plan.get("country_code"))
    )
    action_store_model = normalize_store_model_for_route(
        first_present(action.get("store_model"), action.get("shop_type"), route_parts.get("store_model"), plan.get("store_model"))
    )
    scored: list[tuple[int, dict[str, Any]]] = []
    for store in stores:
        score = 0
        store_route_key = route_key_from_parts(
            first_present(store.get("platform_id"), store.get("platform_label"), store.get("marketplace")),
            store.get("country_code"),
            normalize_store_model_for_route(store.get("shop_type")),
        )
        if route_key and store_route_key == route_key:
            score += 10
        platform_values = [
            store.get("platform_id"),
            store.get("platform_label"),
            store.get("marketplace"),
        ]
        store_values = [
            store.get("store_name"),
            store.get("store_external_id"),
            store.get("sub_store_name"),
        ]
        country = normalize_match_value(store.get("country_code"))
        if action_platform and any(action_platform in normalize_match_value(value) or normalize_match_value(value) in action_platform for value in platform_values if value):
            score += 3
        if action_store and any(action_store in normalize_match_value(value) or normalize_match_value(value) in action_store for value in store_values if value):
            score += 5
        if action_country and country and action_country == country:
            score += 2
        store_model = normalize_store_model_for_route(store.get("shop_type"))
        if action_store_model and action_store_model != "store_model_pending" and store_model == action_store_model:
            score += 2
        if score:
            scored.append((score, store))
    if not scored:
        return {}
    return sorted(scored, key=lambda item: item[0], reverse=True)[0][1]


def load_cloud_execution_tasks(root: Path, *, limit: int | None = None) -> list[IntakeRecord]:
    records = [
        record
        for record in read_records(root, "task_queue")
        if str(record.fields.get("task_type") or "") in CLOUD_EXECUTION_TASK_TYPES
    ]
    records = sorted(records, key=lambda record: record.created_at, reverse=True)
    return records[:limit] if limit else records


def sanitize_action_for_cloud(action: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    blocked_fragments = ["password", "credential", "secret", "token", "cookie", "api_key", "key_env", "email", "phone", "legal"]
    for key, value in action.items():
        lowered = str(key).lower()
        if any(fragment in lowered for fragment in blocked_fragments):
            continue
        if lowered in {"store_external_id", "platform_store_id", "shop_id", "seller_id"}:
            safe[f"{key}_status"] = "registered" if value else "missing"
            continue
        if lowered == "sub_store_name":
            safe["internal_sub_store_note_status"] = "registered" if value else "missing"
            continue
        if lowered in {"ads_account_id", "business_center_id"}:
            safe[f"{key}_status"] = "registered" if value else "missing"
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[key] = value
        elif isinstance(value, list):
            safe[key] = [str(item)[:180] for item in value[:12]]
        elif isinstance(value, dict):
            safe[key] = {str(k): str(v)[:180] for k, v in list(value.items())[:20] if not any(fragment in str(k).lower() for fragment in blocked_fragments)}
    return safe


def cloud_store_route_missing_prerequisites(store: dict[str, Any]) -> list[str]:
    missing = store_route_missing_prerequisites(store)
    method = str(store.get("connection_method") or "").strip()
    if method != "official_authorization":
        missing = [item for item in missing if item != "authorization_scope"]
    return missing


def normalize_store_model_for_route(shop_type: Any) -> str:
    return normalize_channel_store_model_for_route(shop_type)


def route_key_from_parts(platform: Any, country: Any, store_model: Any) -> str:
    return f"{channel_id(platform)}:{str(country or 'GLOBAL').strip().upper() or 'GLOBAL'}:{str(store_model or 'store_model_pending').strip()}"


def channel_id(platform: Any) -> str:
    raw = str(platform or "channel").strip().lower()
    mapping = {
        "tiktok shop": "tiktok_shop",
        "tiktok_shop": "tiktok_shop",
        "amazon sp-api": "amazon",
        "amazon": "amazon",
        "shopify": "shopify",
        "walmart": "walmart",
        "etsy": "etsy",
        "shein": "shein",
        "shein marketplace": "shein",
        "shopee": "shopee",
        "lazada": "lazada",
        "woocommerce": "woocommerce",
        "meta ads": "meta_ads",
        "meta ads / facebook marketing api": "meta_ads",
        "facebook marketing api": "meta_ads",
    }
    if raw in mapping:
        return mapping[raw]
    return re.sub(r"[^a-z0-9]+", "_", raw).strip("_") or "channel"


def first_present(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def masked_present(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    compact = "".join(ch for ch in text if ch.isalnum())
    if len(compact) <= 4:
        return "registered"
    return f"registered_tail_{html.escape(compact[-4:])}"


def identity_fingerprint(prefix: str, *values: Any) -> str:
    normalized = "|".join(normalize_match_value(value) for value in values if str(value or "").strip())
    if not normalized:
        normalized = "pending"
    return f"{prefix}_{stable_hash(normalized)[:16]}"


def normalize_match_value(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower().replace("_", " ").replace("-", " "))


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0
