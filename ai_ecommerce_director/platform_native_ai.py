from __future__ import annotations

import copy
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REGISTRY_PATH = Path("config") / "platform_native_ai_registry.json"
RUNTIME_PATH = Path("data") / "platform_native_ai_runtime.json"
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,159}$")
_RUNTIME_LOCK = threading.RLock()
_SECRET_KEYS = {
    "api_key",
    "apikey",
    "password",
    "client_secret",
    "clientsecret",
    "access_token",
    "accesstoken",
    "refresh_token",
    "refreshtoken",
    "cookie",
    "session",
    "session_cookie",
    "sessioncookie",
}
_RAW_PII_KEYS = {
    "email",
    "email_address",
    "phone",
    "phone_number",
    "client_ip_address",
    "ip_address",
    "user_agent",
}
_RUN_RECORD_FIELDS = {
    "tenant_id",
    "project_id",
    "store_binding_id",
    "platform",
    "tool_id",
    "country_site",
    "commerce_mode",
    "ownership",
    "execution_identity_id",
    "action",
    "product_fact_refs",
    "input_notes",
}
_METRIC_FIELDS = {
    "reviewed_field_count",
    "missing_gate_count",
    "output_claim_count",
    "manual_edit_count",
}
_DISPLAY_NAMES = {
    "seller_assistant": "TikTok Shop Seller Assistant",
    "ai_homepage": "TikTok Shop AI Homepage",
    "smart_listing_optimizer": "TikTok Shop Smart Listing Optimizer",
    "ai_video_maker": "TikTok Shop AI Video Maker",
    "content_studio": "TikTok Shop Content Studio",
    "ai_photo_maker": "TikTok Shop AI Photo Maker",
    "video_assistant": "TikTok Shop Video Assistant",
    "product_intelligent_analysis": "TikTok Shop Product Intelligent Analysis",
    "video_precheck": "TikTok Shop Video Pre-check",
    "tw_ai_product_image": "Shopee TW AI Product Image",
    "tw_ai_try_on": "Shopee TW AI Try-on",
    "tw_ai_store_customer_service": "Shopee TW AI Store Customer Service",
    "vn_ai_product_content_suggestion": "Shopee VN AI Product Content Suggestion",
    "th_ai_terms_and_seller_center_control": "Shopee TH AI/AIGC Control",
    "id_shopee_video_ai_labeling": "Shopee ID AI Content Disclosure",
    "meta_ai_business_assistant": "Meta AI Business Assistant",
    "generative_ai_ad_transparency": "Meta Generative AI Ad Transparency",
    "symphony_creative_studio": "TikTok Symphony Creative Studio",
    "symphony_agent": "TikTok Symphony Agent",
    "dreamina_seedance_2_0_in_symphony": "Seedance 2.0 in TikTok Symphony",
    "ai_max_for_search": "Google Ads AI Max for Search",
    "asset_studio": "Google Ads Asset Studio",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and item.strip()]


def _sensitive_paths(value: Any, path: str = "request") -> tuple[list[str], list[str]]:
    secrets: list[str] = []
    pii: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            normalised = _normalise(key)
            if normalised in _SECRET_KEYS:
                secrets.append(child)
            if normalised in _RAW_PII_KEYS:
                pii.append(child)
            child_secrets, child_pii = _sensitive_paths(item, child)
            secrets.extend(child_secrets)
            pii.extend(child_pii)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            child_secrets, child_pii = _sensitive_paths(item, f"{path}[{index}]")
            secrets.extend(child_secrets)
            pii.extend(child_pii)
    return secrets, pii


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def validate_platform_native_ai_registry(registry: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if registry.get("schema_version") != 1:
        errors.append("registry.schema_version: expected 1")
    if registry.get("external_execution_default_allowed") is not False:
        errors.append("registry.external_execution_default_allowed: expected false")
    required = set(_strings(registry.get("required_route_dimensions")))
    expected = {
        "tenant_id",
        "project_id",
        "store_binding_id",
        "platform",
        "country_site",
        "commerce_mode",
        "ownership",
        "execution_identity_id",
    }
    if required != expected:
        errors.append("registry.required_route_dimensions: incomplete isolated route")
    if "amazon" not in {_normalise(item) for item in _strings(registry.get("excluded_platforms"))}:
        errors.append("registry.excluded_platforms: Amazon must remain excluded in this scope")
    actions = registry.get("actions")
    if not isinstance(actions, Mapping):
        errors.append("registry.actions: expected an object")
    else:
        for field in ("public_review", "store_scoped_local_draft", "external_or_account_scoped"):
            if not _strings(actions.get(field)):
                errors.append(f"registry.actions.{field}: expected at least one action")
    adapters = registry.get("source_adapters")
    if not isinstance(adapters, list) or not adapters:
        errors.append("registry.source_adapters: expected a non-empty list")
    curated = registry.get("curated_tools")
    if not isinstance(curated, list):
        errors.append("registry.curated_tools: expected a list")
    else:
        seen: set[str] = set()
        for index, item in enumerate(curated):
            if not isinstance(item, Mapping):
                errors.append(f"registry.curated_tools[{index}]: expected an object")
                continue
            platform = _normalise(item.get("platform"))
            tool_id = _normalise(item.get("tool_id"))
            identity = f"{platform}:{tool_id}"
            if not SAFE_ID.fullmatch(platform) or not SAFE_ID.fullmatch(tool_id):
                errors.append(f"registry.curated_tools[{index}]: invalid platform/tool id")
            if identity in seen:
                errors.append(f"registry.curated_tools[{index}]: duplicate {identity}")
            seen.add(identity)
            if not str(item.get("source_ref") or "").strip():
                errors.append(f"registry.curated_tools[{index}].source_ref: required")
    secrets, _pii = _sensitive_paths(registry, "registry")
    if secrets:
        errors.append("registry: secret-bearing fields are forbidden")
    return errors


def load_platform_native_ai_registry(root: Path) -> dict[str, Any]:
    registry = _load_json_object(root / REGISTRY_PATH)
    errors = validate_platform_native_ai_registry(registry)
    if errors:
        raise ValueError("Invalid platform native AI registry: " + "; ".join(errors))
    return copy.deepcopy(registry)


def _source_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError("Native AI source path escapes the workspace")
    return candidate


def _canonical_tool(payload: Mapping[str, Any]) -> dict[str, Any]:
    platform = _normalise(payload.get("platform"))
    tool_id = _normalise(payload.get("tool_id"))
    country_sites = _strings(payload.get("country_sites"))
    store_models = _strings(payload.get("store_models"))
    return {
        "id": f"{platform}:{tool_id}",
        "platform": platform,
        "tool_id": tool_id,
        "display_name": str(payload.get("display_name") or _DISPLAY_NAMES.get(tool_id) or tool_id),
        "classification": str(payload.get("classification") or "platform_native_ai"),
        "availability_state": str(payload.get("availability_state") or "documented_unconnected"),
        "live_connection_state": "blocked_connector",
        "country_sites": country_sites or ["COUNTRY_SITE_REQUIRES_AUTHORIZED_CHECK"],
        "store_models": store_models or ["STORE_MODEL_REQUIRES_AUTHORIZED_CHECK"],
        "seller_executable": bool(payload.get("seller_executable", True)),
        "inputs": _strings(payload.get("inputs")),
        "outputs": _strings(payload.get("outputs")),
        "editable_boundary": str(payload.get("editable_boundary") or "unknown_without_authorized_observation"),
        "submit_boundary": str(payload.get("submit_boundary") or "blocked_owner_input"),
        "metrics": copy.deepcopy(payload.get("metrics") or "unknown_without_store_scoped_evidence"),
        "failure_recovery": str(payload.get("failure_recovery") or "retain source facts and fall back to manual review"),
        "source_ref": str(payload.get("source_ref") or ""),
        "source_url": str(payload.get("source_url") or ""),
        "reviewed_at": str(payload.get("reviewed_at") or ""),
        "external_execution_available": False,
    }


def _tiktok_shop_tools(root: Path, adapter: Mapping[str, Any]) -> list[dict[str, Any]]:
    source = _load_json_object(_source_path(root, str(adapter.get("path") or "")))
    result: list[dict[str, Any]] = []
    for item in source.get(str(adapter.get("field") or ""), []):
        if not isinstance(item, Mapping):
            continue
        runtime_state = str(item.get("runtime_state") or "official_public_doc_only")
        result.append(
            _canonical_tool(
                {
                    "platform": "tiktok_shop",
                    "tool_id": item.get("id"),
                    "classification": "platform_native_ai",
                    "availability_state": (
                        "limited_unconnected"
                        if "select_sellers" in runtime_state or "early_test" in runtime_state
                        else "documented_unconnected"
                    ),
                    "country_sites": item.get("country_sites"),
                    "store_models": ["seller_or_creator_account_as_documented"],
                    "inputs": item.get("inputs"),
                    "outputs": item.get("outputs"),
                    "editable_boundary": item.get("editable_boundary"),
                    "submit_boundary": item.get("submit_boundary"),
                    "metrics": "unknown_without_store_scoped_experiment",
                    "failure_recovery": "retain source assets and facts; use manual workflow until an authorized live error is observed",
                    "source_ref": str(adapter.get("path") or ""),
                    "source_url": item.get("source_url"),
                    "reviewed_at": item.get("checked_on") or adapter.get("reviewed_at"),
                }
            )
        )
    return result


def _shopee_tools(root: Path, adapter: Mapping[str, Any]) -> list[dict[str, Any]]:
    source = _load_json_object(_source_path(root, str(adapter.get("path") or "")))
    result: list[dict[str, Any]] = []
    for item in source.get(str(adapter.get("field") or ""), []):
        if not isinstance(item, Mapping):
            continue
        result.append(
            _canonical_tool(
                {
                    "platform": "shopee",
                    "tool_id": item.get("feature_id"),
                    "classification": "platform_native_ai_or_aigc_control",
                    "availability_state": "documented_unconnected",
                    "country_sites": [str(item.get("country_site") or "")],
                    "store_models": [str(item.get("store_model") or "")],
                    "inputs": item.get("inputs"),
                    "outputs": item.get("outputs"),
                    "editable_boundary": item.get("editable_boundary"),
                    "submit_boundary": item.get("submittable_boundary"),
                    "metrics": item.get("metrics"),
                    "failure_recovery": item.get("failure_recovery"),
                    "source_ref": str(adapter.get("path") or ""),
                    "source_url": item.get("source_url"),
                    "reviewed_at": item.get("captured_at") or adapter.get("reviewed_at"),
                }
            )
        )
    return result


def _advertising_tools(root: Path, adapter: Mapping[str, Any]) -> list[dict[str, Any]]:
    source = _load_json_object(_source_path(root, str(adapter.get("path") or "")))
    included = {_normalise(item) for item in _strings(adapter.get("included_channels"))}
    result: list[dict[str, Any]] = []
    for channel in source.get("channels", []):
        if not isinstance(channel, Mapping):
            continue
        platform = _normalise(channel.get("id"))
        if platform not in included:
            continue
        native_ai = channel.get("native_ai") if isinstance(channel.get("native_ai"), Mapping) else {}
        for item in native_ai.get("surfaces", []):
            if not isinstance(item, Mapping):
                continue
            result.append(
                _canonical_tool(
                    {
                        "platform": platform,
                        "tool_id": item.get("id"),
                        "classification": item.get("kind") or native_ai.get("kind") or "platform_native_ai",
                        "availability_state": item.get("verified_live_availability") or item.get("availability") or "documented_unconnected",
                        "country_sites": ["COUNTRY_SITE_REQUIRES_AUTHORIZED_CHECK"],
                        "store_models": ["advertiser_account"],
                        "inputs": item.get("documented_inputs"),
                        "outputs": item.get("documented_outputs"),
                        "editable_boundary": item.get("editable_boundary"),
                        "submit_boundary": item.get("submit_boundary") or item.get("export_boundary"),
                        "metrics": item.get("effect_metrics") or item.get("measurement_boundary"),
                        "failure_recovery": item.get("failure_recovery"),
                        "source_ref": str(adapter.get("path") or ""),
                        "source_url": "",
                        "reviewed_at": adapter.get("reviewed_at"),
                    }
                )
            )
    return result


def platform_native_ai_catalog(root: Path) -> list[dict[str, Any]]:
    registry = load_platform_native_ai_registry(root)
    tools: list[dict[str, Any]] = []
    for adapter in registry.get("source_adapters", []):
        if not isinstance(adapter, Mapping):
            continue
        adapter_id = str(adapter.get("id") or "")
        if adapter_id == "tiktok_shop_native_ai_tools":
            tools.extend(_tiktok_shop_tools(root, adapter))
        elif adapter_id == "shopee_native_ai_catalog":
            tools.extend(_shopee_tools(root, adapter))
        elif adapter_id == "advertising_native_ai_surfaces":
            tools.extend(_advertising_tools(root, adapter))
    tools.extend(
        _canonical_tool(item)
        for item in registry.get("curated_tools", [])
        if isinstance(item, Mapping)
    )
    excluded = {_normalise(item) for item in _strings(registry.get("excluded_platforms"))}
    tools = [item for item in tools if item["platform"] not in excluded]
    identities = [item["id"] for item in tools]
    if len(identities) != len(set(identities)):
        raise ValueError("Platform native AI catalog contains duplicate tool identities")
    return sorted(tools, key=lambda item: (item["platform"], item["display_name"].casefold()))


def _load_runtime(root: Path) -> dict[str, Any]:
    try:
        payload = _load_json_object(root / RUNTIME_PATH)
    except (OSError, ValueError):
        payload = {}
    return {
        "schema_version": 1,
        "runs": [dict(item) for item in payload.get("runs", []) if isinstance(item, dict)][-200:],
        "feedback": [dict(item) for item in payload.get("feedback", []) if isinstance(item, dict)][-200:],
        "updated_at": str(payload.get("updated_at") or ""),
    }


def _write_runtime(root: Path, payload: Mapping[str, Any]) -> None:
    path = root / RUNTIME_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {
        "schema_version": 1,
        "runs": list(payload.get("runs") or [])[-200:],
        "feedback": list(payload.get("feedback") or [])[-200:],
        "updated_at": _now_iso(),
    }
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _safe_run_request(request: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in request.items():
        if key not in _RUN_RECORD_FIELDS:
            continue
        if isinstance(value, str):
            result[key] = value[:500]
        elif isinstance(value, list) and key == "product_fact_refs":
            result[key] = [str(item)[:160] for item in value[:30] if str(item).strip()]
    return result


def evaluate_platform_native_ai_request(
    request: Mapping[str, Any], registry: Mapping[str, Any], tools: list[Mapping[str, Any]]
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "blocked_invalid_request",
        "local_action_allowed": False,
        "external_execution_allowed": False,
        "external_action_performed": False,
        "authorization_granted": False,
        "missing": [],
        "route_key": "",
        "next_stage": "review_request",
    }
    secrets, pii = _sensitive_paths(request)
    if secrets:
        result.update({"status": "blocked_raw_credentials", "missing": secrets, "next_stage": "remove_secrets"})
        return result
    if pii:
        result.update({"status": "blocked_raw_pii", "missing": pii, "next_stage": "remove_personal_data"})
        return result
    platform = _normalise(request.get("platform"))
    tool_id = _normalise(request.get("tool_id"))
    action = _normalise(request.get("action"))
    if platform in {_normalise(item) for item in _strings(registry.get("excluded_platforms"))}:
        result.update({"status": "blocked_scope_excluded", "missing": ["non_amazon_platform"]})
        return result
    tool = next(
        (item for item in tools if _normalise(item.get("platform")) == platform and _normalise(item.get("tool_id")) == tool_id),
        None,
    )
    if tool is None:
        result.update({"status": "blocked_unknown_tool", "missing": ["reviewed_platform_tool"]})
        return result
    result["tool"] = copy.deepcopy(dict(tool))
    actions = registry.get("actions") if isinstance(registry.get("actions"), Mapping) else {}
    public_review = {_normalise(item) for item in _strings(actions.get("public_review"))}
    local_draft = {_normalise(item) for item in _strings(actions.get("store_scoped_local_draft"))}
    external = {_normalise(item) for item in _strings(actions.get("external_or_account_scoped"))}
    if action not in public_review | local_draft | external:
        result.update({"status": "blocked_unsupported_action", "missing": ["supported_action"]})
        return result
    if action in public_review:
        result.update(
            {
                "status": "public_capability_review_ready",
                "local_action_allowed": True,
                "next_stage": "review_source_scope_and_boundaries",
            }
        )
        return result
    country_site = str(request.get("country_site") or "").strip().upper()
    exact_sites = {str(item).strip().upper() for item in tool.get("country_sites", []) if str(item).strip()}
    site_matches = bool(country_site and country_site in exact_sites)
    if action in external:
        result.update(
            {
                "status": "blocked_external_action",
                "missing": [
                    "verified_store_scoped_connector",
                    "current_tool_entitlement",
                    "item_level_owner_approval",
                    "platform_receipt_and_readback",
                ],
                "next_stage": "owner_authorized_connector_workflow",
            }
        )
        return result
    required = _strings(registry.get("required_route_dimensions"))
    missing = [field for field in required if not str(request.get(field) or "").strip()]
    if missing:
        result.update({"status": "blocked_missing_route", "missing": missing, "next_stage": "select_real_store_route"})
        return result
    route_values = [request.get(field) for field in required]
    if any(not SAFE_ID.fullmatch(_normalise(value)) for value in route_values):
        result.update({"status": "blocked_invalid_route", "missing": ["safe_route_ids"]})
        return result
    result["route_key"] = ":".join(_normalise(value) for value in route_values)
    if not site_matches:
        result.update({"status": "blocked_site_scope_unknown", "missing": ["exact_country_site_evidence"], "next_stage": "verify_current_site_entitlement"})
        return result
    if not bool(tool.get("seller_executable")):
        result.update({"status": "blocked_not_seller_tool", "missing": ["seller_executable_surface"], "next_stage": "use_rules_and_human_review"})
        return result
    if str(tool.get("availability_state") or "") == "research_only":
        result.update({"status": "blocked_research_only", "missing": ["opened_authorized_tool_surface"]})
        return result
    result.update(
        {
            "status": "local_input_packet_ready",
            "local_action_allowed": True,
            "next_stage": "human_review_before_any_live_tool_use",
            "input_packet": {
                "tool_identity": tool.get("id"),
                "expected_inputs": copy.deepcopy(tool.get("inputs") or []),
                "expected_outputs": copy.deepcopy(tool.get("outputs") or []),
                "product_fact_refs": copy.deepcopy(request.get("product_fact_refs") or []),
                "input_notes": str(request.get("input_notes") or "")[:500],
                "output_state": "not_generated",
                "apply_state": "not_authorized",
            },
        }
    )
    return result


def platform_native_ai_control_snapshot(root: Path) -> dict[str, Any]:
    registry = load_platform_native_ai_registry(root)
    tools = platform_native_ai_catalog(root)
    runtime = _load_runtime(root)
    platforms = sorted({item["platform"] for item in tools})
    return {
        "schema_version": 1,
        "scope": str(registry.get("scope") or "non_amazon_local_control_plane"),
        "platforms": platforms,
        "tools": tools,
        "tool_count": len(tools),
        "documented_input_count": sum(len(item.get("inputs") or []) for item in tools),
        "documented_output_count": sum(len(item.get("outputs") or []) for item in tools),
        "verified_connection_count": 0,
        "external_action_count": 0,
        "runs": list(reversed(runtime["runs"][-20:])),
        "feedback": list(reversed(runtime["feedback"][-20:])),
        "excluded_platforms": _strings(registry.get("excluded_platforms")),
        "installation_or_documentation_grants_authorization": False,
        "updated_at": runtime.get("updated_at") or str(registry.get("updated_at") or ""),
    }


def run_platform_native_ai_audit(
    root: Path, payload: Mapping[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    request = payload.get("request") if isinstance(payload.get("request"), Mapping) else payload
    registry = load_platform_native_ai_registry(root)
    tools = platform_native_ai_catalog(root)
    evaluation = evaluate_platform_native_ai_request(request, registry, tools)
    record = {
        "id": f"native-ai-run-{uuid.uuid4().hex[:16]}",
        "created_at": _now_iso(),
        "created_by": str(actor or "owner")[:80],
        "request": _safe_run_request(request),
        "result": evaluation,
        "external_action_performed": False,
        "authorization_granted": False,
    }
    with _RUNTIME_LOCK:
        runtime = _load_runtime(root)
        runtime["runs"].append(record)
        _write_runtime(root, runtime)
    return {"ok": True, "run": record}


def record_platform_native_ai_feedback(
    root: Path, payload: Mapping[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    run_id = str(payload.get("run_id") or "").strip().lower()
    if not SAFE_ID.fullmatch(run_id):
        raise ValueError("请选择有效的平台原生 AI 审计记录。")
    evidence_source = _normalise(payload.get("evidence_source"))
    if evidence_source not in {"formal_app_manual", "official_public_read", "authorized_export"}:
        raise ValueError("证据来源无效。")
    evidence_ref = " ".join(str(payload.get("evidence_ref") or "").split()).strip()
    if len(evidence_ref) < 6:
        raise ValueError("必须提供可追溯的证据引用。")
    window_start = str(payload.get("window_start") or "").strip()
    window_end = str(payload.get("window_end") or "").strip()
    if not window_start or not window_end:
        raise ValueError("必须提供证据统计窗口。")
    raw_metrics = payload.get("metrics") if isinstance(payload.get("metrics"), Mapping) else {}
    metrics: dict[str, float] = {}
    for key, value in raw_metrics.items():
        if key not in _METRIC_FIELDS or isinstance(value, bool):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric < 0:
            raise ValueError("原生 AI 证据指标不能为负数。")
        metrics[key] = numeric
    if not metrics:
        raise ValueError("至少提供一个证据指标。")
    secrets, pii = _sensitive_paths(payload)
    if secrets or pii:
        raise ValueError("反馈不得包含凭据或原始个人数据。")
    with _RUNTIME_LOCK:
        runtime = _load_runtime(root)
        run = next((item for item in runtime["runs"] if str(item.get("id") or "") == run_id), None)
        if run is None:
            raise ValueError("平台原生 AI 审计记录不存在。")
        output_observed = bool(
            evidence_source == "authorized_export" and metrics.get("output_claim_count", 0) > 0
        )
        record = {
            "id": f"native-ai-feedback-{uuid.uuid4().hex[:16]}",
            "run_id": run_id,
            "created_at": _now_iso(),
            "created_by": str(actor or "owner")[:80],
            "evidence_source": evidence_source,
            "evidence_ref": evidence_ref[:500],
            "window_start": window_start[:80],
            "window_end": window_end[:80],
            "metrics": metrics,
            "platform_output_observed": output_observed,
            "external_execution_observed": False,
            "causal_conclusion": "inconclusive",
            "evidence_state": (
                "authorized_output_export_observation"
                if output_observed
                else "local_capability_audit_only"
            ),
        }
        runtime["feedback"].append(record)
        _write_runtime(root, runtime)
    return {"ok": True, "feedback": record}
