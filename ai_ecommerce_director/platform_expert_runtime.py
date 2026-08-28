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

from .ai_provider_catalog import provider_catalog_snapshot
from .platform_experts import (
    UnsupportedExpertRoute,
    list_platform_experts,
    load_platform_expert_registry,
    recommend_platform_expert,
)
from .user_training_memory import UserTrainingMemoryError, resolve_user_training_memory


RUNTIME_PATH = Path("data") / "platform_expert_runtime.json"
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,159}$")
_LOCK = threading.RLock()
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
    "session_cookie",
}
_PII_KEYS = {"email", "email_address", "phone", "phone_number", "ip_address", "user_agent"}
_SAFE_REQUEST_FIELDS = {
    "tenant_id",
    "project_id",
    "task_id",
    "store_binding_id",
    "execution_identity_id",
    "platform",
    "capability",
    "country_site",
    "store_model",
    "ownership",
    "action",
    "product_fact_refs",
}
_EXTERNAL_ACTIONS = {
    "connect_account",
    "open_authenticated_surface",
    "call_platform_api",
    "upload_asset",
    "apply_change",
    "send_message",
    "submit",
    "publish",
}
_METRICS = {"reviewed_boundary_count", "missing_gate_count", "draft_field_count", "error_count"}
_PROVIDER_PREFIXES = {
    "openai": ("openai",),
    "anthropic": ("claude", "anthropic"),
    "google-gemini": ("gemini", "google"),
    "deepseek": ("deepseek",),
    "zhipu": ("zhipu",),
    "qwen-dashscope": ("qwen", "dashscope"),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _sensitive_paths(value: Any, path: str = "request") -> tuple[list[str], list[str]]:
    secrets: list[str] = []
    pii: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            normalised = _normalise(key)
            if normalised in _SECRET_KEYS:
                secrets.append(child)
            if normalised in _PII_KEYS:
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


def _provider_family_readiness(root: Path) -> dict[str, dict[str, Any]]:
    configured = provider_catalog_snapshot(root).get("configured", [])
    rows = [item for item in configured if isinstance(item, Mapping)]
    result: dict[str, dict[str, Any]] = {}
    for family, prefixes in _PROVIDER_PREFIXES.items():
        matches = [
            item
            for item in rows
            if any(str(item.get("name") or "").casefold().startswith(prefix) for prefix in prefixes)
        ]
        ready = [item for item in matches if item.get("ready")]
        result[family] = {
            "family": family,
            "configured_model_count": len(matches),
            "ready_model_count": len(ready),
            "ready": bool(ready),
            "ready_model_names": [str(item.get("name") or "") for item in ready],
        }
    return result


def _expert_catalog(root: Path) -> list[dict[str, Any]]:
    registry = load_platform_expert_registry(root)
    readiness = _provider_family_readiness(root)
    result: list[dict[str, Any]] = []
    for expert in list_platform_experts(registry):
        platforms = [str(item) for item in expert.get("platforms", []) if str(item).strip()]
        if "amazon" in {_normalise(item) for item in platforms}:
            continue
        slots: dict[str, Any] = {}
        for slot_id, slot in expert.get("model_slots", {}).items():
            if not isinstance(slot, Mapping):
                continue
            candidates = []
            for candidate in slot.get("candidates", []):
                if not isinstance(candidate, Mapping):
                    continue
                provider_id = str(candidate.get("provider_id") or "")
                candidates.append(
                    {
                        **copy.deepcopy(dict(candidate)),
                        "local_readiness": copy.deepcopy(
                            readiness.get(
                                provider_id,
                                {
                                    "family": provider_id,
                                    "configured_model_count": 0,
                                    "ready_model_count": 0,
                                    "ready": False,
                                    "ready_model_names": [],
                                },
                            )
                        ),
                    }
                )
            slots[str(slot_id)] = {
                "task_types": copy.deepcopy(slot.get("task_types") or []),
                "candidates": candidates,
            }
        result.append(
            {
                "id": str(expert.get("id") or ""),
                "name": str(expert.get("name") or ""),
                "summary": str(expert.get("summary") or ""),
                "platforms": platforms,
                "job_modules": copy.deepcopy(expert.get("job_modules") or []),
                "routing": copy.deepcopy(expert.get("routing") or {}),
                "default_capabilities": copy.deepcopy(expert.get("default_capabilities") or {}),
                "model_slots": slots,
                "learning_loop": copy.deepcopy(expert.get("learning_loop") or {}),
                "execution_boundaries": copy.deepcopy(expert.get("execution_boundaries") or {}),
                "real_store_connection_state": "blocked_connector",
                "external_execution_available": False,
            }
        )
    return result


def _load_runtime(root: Path) -> dict[str, Any]:
    path = root / RUNTIME_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return {
        "schema_version": 1,
        "runs": [dict(item) for item in payload.get("runs", []) if isinstance(item, dict)][-200:],
        "reviews": [dict(item) for item in payload.get("reviews", []) if isinstance(item, dict)][-200:],
        "updated_at": str(payload.get("updated_at") or ""),
    }


def _write_runtime(root: Path, runtime: Mapping[str, Any]) -> None:
    path = root / RUNTIME_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "runs": list(runtime.get("runs") or [])[-200:],
        "reviews": list(runtime.get("reviews") or [])[-200:],
        "updated_at": _now_iso(),
    }
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _safe_request(request: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in request.items():
        if key not in _SAFE_REQUEST_FIELDS:
            continue
        if isinstance(value, str):
            result[key] = value[:500]
        elif key == "product_fact_refs" and isinstance(value, list):
            result[key] = [str(item)[:160] for item in value[:30] if str(item).strip()]
    return result


def evaluate_platform_expert_request(root: Path, request: Mapping[str, Any]) -> dict[str, Any]:
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
    platform = str(request.get("platform") or "").strip()
    if _normalise(platform) in {"amazon", "amazon_marketplace"}:
        result.update({"status": "blocked_scope_excluded", "missing": ["non_amazon_platform"]})
        return result
    capability = str(request.get("capability") or "").strip()
    country_site = str(request.get("country_site") or "").strip().upper()
    store_model = str(request.get("store_model") or "").strip()
    ownership = str(request.get("ownership") or "").strip()
    action = _normalise(request.get("action"))
    try:
        recommendation = recommend_platform_expert(
            load_platform_expert_registry(root),
            platform=platform,
            capability=capability,
            country_site=country_site,
            store_model=store_model,
            ownership=ownership,
        )
    except UnsupportedExpertRoute as exc:
        result.update(
            {
                "status": "blocked_non_executable_route",
                "missing": ["exact_country_site_or_supported_store_mode"],
                "error": str(exc),
                "next_stage": "select_exact_supported_route",
            }
        )
        return result
    if recommendation is None:
        result.update(
            {
                "status": "blocked_route_not_supported",
                "missing": ["matching_expert_route"],
                "next_stage": "check_platform_site_mode_ownership_and_capability",
            }
        )
        return result
    readiness = _provider_family_readiness(root)
    slot = copy.deepcopy(recommendation.get("model_slot") or {})
    for candidate in slot.get("candidates", []):
        if isinstance(candidate, dict):
            candidate["local_readiness"] = copy.deepcopy(
                readiness.get(str(candidate.get("provider_id") or ""), {"ready": False, "ready_model_count": 0, "ready_model_names": []})
            )
    capabilities = recommendation.get("default_capabilities") or {}
    learning_consumers = [str(recommendation.get("expert_id") or "")]
    if isinstance(capabilities, Mapping):
        learning_consumers.extend(str(item) for item in capabilities.get("skills", []) if str(item).strip())
        learning_consumers.extend(str(item) for item in capabilities.get("agents", []) if str(item).strip())
    try:
        learning_memory = resolve_user_training_memory(root, learning_consumers)
    except UserTrainingMemoryError as exc:
        learning_memory = {
            "consumer_ids": learning_consumers,
            "route_ids": [],
            "source_ids": [],
            "materials": [],
            "memory_refs": [],
            "regression_ids": [],
            "raw_text_loaded": False,
            "raw_public_reuse_allowed": False,
            "external_action_authorized": False,
            "preserved_paused": False,
            "status": "blocked_missing_or_invalid_memory_registry",
            "error": str(exc),
        }
    result["recommendation"] = {
        **copy.deepcopy(recommendation),
        "model_slot": slot,
        "learning_memory": copy.deepcopy(learning_memory),
    }
    if action in _EXTERNAL_ACTIONS:
        result.update(
            {
                "status": "blocked_external_action",
                "missing": [
                    "verified_store_scoped_connector",
                    "current_account_entitlement",
                    "item_level_owner_approval",
                    "platform_receipt_and_readback",
                ],
                "next_stage": "owner_authorized_connector_workflow",
            }
        )
        return result
    if action == "inspect_route":
        result.update(
            {
                "status": "expert_route_review_ready",
                "local_action_allowed": True,
                "next_stage": "review_expert_model_tools_and_boundaries",
            }
        )
        return result
    if action != "prepare_local_job_packet":
        result.update({"status": "blocked_unsupported_action", "missing": ["supported_action"]})
        return result
    required = ["tenant_id", "project_id", "store_binding_id", "execution_identity_id"]
    missing = [field for field in required if not str(request.get(field) or "").strip()]
    if missing:
        result.update({"status": "blocked_missing_route", "missing": missing, "next_stage": "select_real_task_and_store_route"})
        return result
    route_values = [
        request.get("tenant_id"),
        request.get("project_id"),
        request.get("store_binding_id"),
        platform,
        country_site,
        store_model,
        ownership,
        request.get("execution_identity_id"),
    ]
    if any(not SAFE_ID.fullmatch(_normalise(value)) for value in route_values):
        result.update({"status": "blocked_invalid_route", "missing": ["safe_route_ids"]})
        return result
    result["route_key"] = ":".join(_normalise(value) for value in route_values)
    result.update(
        {
            "status": "local_expert_job_packet_ready",
            "local_action_allowed": True,
            "next_stage": "task_model_analysis_or_human_review",
            "job_packet": {
                "expert_id": recommendation.get("expert_id"),
                "capability": recommendation.get("capability"),
                "model_slot": slot,
                "default_capabilities": copy.deepcopy(recommendation.get("default_capabilities") or {}),
                "learning_memory": copy.deepcopy(learning_memory),
                "product_fact_refs": copy.deepcopy(request.get("product_fact_refs") or []),
                "model_call_state": "not_run_in_expert_router",
                "platform_action_state": "not_authorized",
                "output_state": "not_generated",
            },
        }
    )
    return result


def platform_expert_control_snapshot(root: Path) -> dict[str, Any]:
    runtime = _load_runtime(root)
    experts = _expert_catalog(root)
    return {
        "schema_version": 1,
        "scope": "non_amazon_expert_local_control_plane",
        "experts": experts,
        "expert_count": len(experts),
        "platform_count": len({platform for expert in experts for platform in expert.get("platforms", [])}),
        "ready_provider_families": [
            family for family, state in _provider_family_readiness(root).items() if state.get("ready")
        ],
        "verified_store_connection_count": 0,
        "external_action_count": 0,
        "runs": list(reversed(runtime["runs"][-20:])),
        "reviews": list(reversed(runtime["reviews"][-20:])),
        "registry_or_model_readiness_grants_platform_authorization": False,
        "updated_at": runtime.get("updated_at") or "",
    }


def run_platform_expert_audit(
    root: Path, payload: Mapping[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    request = payload.get("request") if isinstance(payload.get("request"), Mapping) else payload
    evaluation = evaluate_platform_expert_request(root, request)
    record = {
        "id": f"expert-run-{uuid.uuid4().hex[:16]}",
        "created_at": _now_iso(),
        "created_by": str(actor or "owner")[:80],
        "request": _safe_request(request),
        "result": evaluation,
        "external_action_performed": False,
        "authorization_granted": False,
    }
    with _LOCK:
        runtime = _load_runtime(root)
        runtime["runs"].append(record)
        _write_runtime(root, runtime)
    return {"ok": True, "run": record}


def record_platform_expert_review(
    root: Path, payload: Mapping[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    run_id = str(payload.get("run_id") or "").strip().lower()
    if not SAFE_ID.fullmatch(run_id):
        raise ValueError("请选择有效的平台专家审计记录。")
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
        if key not in _METRICS or isinstance(value, bool):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric < 0:
            raise ValueError("平台专家证据指标不能为负数。")
        metrics[key] = numeric
    if not metrics:
        raise ValueError("至少提供一个证据指标。")
    secrets, pii = _sensitive_paths(payload)
    if secrets or pii:
        raise ValueError("复盘不得包含凭据或原始个人数据。")
    with _LOCK:
        runtime = _load_runtime(root)
        run = next((item for item in runtime["runs"] if str(item.get("id") or "") == run_id), None)
        if run is None:
            raise ValueError("平台专家审计记录不存在。")
        record = {
            "id": f"expert-review-{uuid.uuid4().hex[:16]}",
            "run_id": run_id,
            "created_at": _now_iso(),
            "created_by": str(actor or "owner")[:80],
            "evidence_source": evidence_source,
            "evidence_ref": evidence_ref[:500],
            "window_start": window_start[:80],
            "window_end": window_end[:80],
            "metrics": metrics,
            "model_output_observed": False,
            "platform_execution_observed": False,
            "causal_conclusion": "inconclusive",
            "evidence_state": "local_expert_route_audit_only",
        }
        runtime["reviews"].append(record)
        _write_runtime(root, runtime)
    return {"ok": True, "review": record}
