from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .account import DEFAULT_MODEL_TIER, add_model, list_models
from .credential_store import credential_available, provider_credential_ref, save_credential
from .kimi_k3_local import blocker_message, preflight_kimi_k3
from .llm import LLMClient


CATALOG_PATH = Path("config") / "ai_provider_catalog.json"
VERIFICATION_PATH = Path("config") / "ai_provider_verification_state.json"
SAFE_PROVIDER_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _receipt_freshness(
    receipt: dict[str, Any] | None,
    verification: dict[str, Any],
) -> tuple[str, str]:
    if not receipt:
        return "not_tested", ""
    policy = (
        verification.get("verification_policy")
        if isinstance(verification.get("verification_policy"), dict)
        else {}
    )
    if not policy.get("enforce_receipt_freshness"):
        return "current", ""
    now = datetime.now(timezone.utc)
    explicit_valid_until = _parse_timestamp(receipt.get("valid_until"))
    if explicit_valid_until is not None:
        return (
            ("current", explicit_valid_until.isoformat().replace("+00:00", "Z"))
            if now <= explicit_valid_until
            else ("stale", explicit_valid_until.isoformat().replace("+00:00", "Z"))
        )
    tested_at = _parse_timestamp(
        receipt.get("tested_at")
        or receipt.get("recorded_at")
        or verification.get("audited_at")
    )
    if tested_at is None:
        return "stale", ""
    try:
        max_age_hours = max(1, int(policy.get("max_age_hours") or 24))
    except (TypeError, ValueError):
        max_age_hours = 24
    valid_until = tested_at + timedelta(hours=max_age_hours)
    return (
        ("current", valid_until.isoformat().replace("+00:00", "Z"))
        if now <= valid_until
        else ("stale", valid_until.isoformat().replace("+00:00", "Z"))
    )


def load_provider_catalog(root: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads((root / CATALOG_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    providers = payload.get("providers") if isinstance(payload, dict) else []
    normalized: list[dict[str, Any]] = []
    for item in providers:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        row = dict(item)
        row["integration_state"] = str(row.get("integration_state") or "configurable")
        row["model_families"] = [
            str(value)
            for value in row.get("model_families", [])
            if str(value).strip()
        ]
        row["capability_slots"] = [
            str(value)
            for value in row.get("capability_slots", [])
            if str(value).strip()
        ]
        normalized.append(row)
    return normalized


def load_provider_verification(root: Path) -> dict[str, Any]:
    try:
        # Windows PowerShell 5 needs a BOM to auto-detect UTF-8, while Python's
        # plain ``utf-8`` codec exposes that BOM to json.loads as U+FEFF.
        # ``utf-8-sig`` accepts both BOM and BOM-less UTF-8 files.
        payload = json.loads((root / VERIFICATION_PATH).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    allowed = {"available", "configured", "verified", "stale", "blocked", "unsupported"}
    catalog_states = payload.get("catalog_provider_states")
    receipts = payload.get("live_receipts")
    if not isinstance(catalog_states, list) or not isinstance(receipts, list):
        return {}
    modality_receipts = payload.get("modality_receipts", [])
    if not isinstance(modality_receipts, list):
        return {}
    if any(
        not isinstance(item, dict) or str(item.get("state") or "") not in allowed
        for item in catalog_states
    ):
        return {}
    return payload


def _merge_model_verification(
    configured: list[dict[str, Any]],
    verification: dict[str, Any],
) -> list[dict[str, Any]]:
    receipts = {
        (str(item.get("provider") or ""), str(item.get("model") or "")): item
        for item in verification.get("live_receipts", [])
        if isinstance(item, dict)
    }
    allowed_modalities = ("text", "image", "audio", "video", "files", "tool_use")
    modality_receipts: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in verification.get("modality_receipts", []):
        if not isinstance(item, dict):
            continue
        key = (str(item.get("provider") or ""), str(item.get("model") or ""))
        if not all(key):
            continue
        modality_receipts.setdefault(key, []).append(item)
    rows: list[dict[str, Any]] = []
    for item in configured:
        row = dict(item)
        credential_ready = bool(row.get("ready"))
        model_key = (str(row.get("name") or ""), str(row.get("model") or ""))
        receipt = receipts.get(model_key)
        exact_modality_receipts = modality_receipts.get(model_key, [])
        status = str((receipt or {}).get("status") or "")
        historical_modalities = ["text"] if status == "ok" else []
        modality_test_statuses: dict[str, str] = {}
        for modality_receipt in exact_modality_receipts:
            modality_status = str(modality_receipt.get("status") or "")
            for modality in modality_receipt.get("modalities", []):
                modality_name = str(modality or "")
                if modality_name not in allowed_modalities:
                    continue
                modality_test_statuses[modality_name] = modality_status or "unknown"
                if modality_status == "ok" and modality_name not in historical_modalities:
                    historical_modalities.append(modality_name)
        historical_modalities = [
            modality for modality in allowed_modalities if modality in historical_modalities
        ]
        freshness, valid_until = _receipt_freshness(receipt, verification)
        verified_modalities = historical_modalities if freshness == "current" else []
        deployment_state = str(row.get("deployment_state") or "")
        if deployment_state.startswith("blocked_"):
            state = "blocked"
        elif receipt and freshness == "stale":
            state = "stale"
        elif status == "ok" and verified_modalities:
            state = "verified"
        elif receipt:
            state = "blocked"
        else:
            state = "configured"
        runtime_eligible = bool(credential_ready and state == "verified")
        historical_state = (
            "verified"
            if status == "ok"
            else "blocked"
            if receipt
            else "not_tested"
        )
        reasoning_options = [
            str(value)
            for value in (receipt or {}).get("reasoning_options", [])
            if str(value).strip()
        ]
        speed_options = [
            str(value)
            for value in (receipt or {}).get("speed_options", [])
            if str(value).strip()
        ]
        strategy_evidence_state = (
            "exact_receipt"
            if freshness == "current" and (reasoning_options or speed_options)
            else "unknown_default_only"
        )
        if not reasoning_options:
            reasoning_options = ["standard"]
        if not speed_options:
            speed_options = ["standard"]
        row.update({
            "credential_ready": credential_ready,
            "runtime_eligible": runtime_eligible,
            "ready": runtime_eligible,
            "verification_state": state,
            "historical_verification_state": historical_state,
            "receipt_freshness": freshness,
            "receipt_valid_until": valid_until,
            "connection_test_status": status or "not_tested",
            "connection_test_code": str(
                (receipt or {}).get("code") or deployment_state
            ),
            "connection_test_error": str(
                (receipt or {}).get("error")
                or row.get("deployment_blocker")
                or ""
            ),
            "connection_test_http_status": int((receipt or {}).get("status_code") or 0),
            "connection_test_latency_ms": int((receipt or {}).get("latency_ms") or 0),
            "last_tested_at": str(verification.get("audited_at") or "") if receipt or exact_modality_receipts else "",
            "verified_modalities": verified_modalities,
            "historically_verified_modalities": historical_modalities,
            "unknown_modalities": [
                modality
                for modality in ("image", "audio", "video", "files", "tool_use")
                if modality not in verified_modalities and modality not in modality_test_statuses
            ],
            "modality_test_statuses": modality_test_statuses,
            "modality_receipt_refs": [
                str(item.get("evidence") or "")
                for item in exact_modality_receipts
                if item.get("evidence")
            ],
            "reasoning_options": reasoning_options,
            "speed_options": speed_options,
            "strategy_evidence_state": strategy_evidence_state,
            "selection_blocker": (
                "verification_receipt_stale"
                if state == "stale"
                else "current_probe_failed"
                if state == "blocked"
                else "credential_or_runtime_not_ready"
                if not credential_ready
                else "current_exact_receipt_missing"
                if not runtime_eligible
                else ""
            ),
            "rate_and_cost_state": "unknown",
        })
        rows.append(row)
    return rows


def provider_catalog_snapshot(root: Path) -> dict[str, Any]:
    verification = load_provider_verification(root)
    configured = _merge_model_verification(list_models(root), verification)
    catalog_states = {
        str(item.get("provider_id") or ""): item
        for item in verification.get("catalog_provider_states", [])
        if isinstance(item, dict)
    }
    configured_by_name = {
        str(item.get("name") or ""): item for item in configured if item.get("name")
    }
    catalog = []
    for item in load_provider_catalog(root):
        state = catalog_states.get(str(item.get("id") or ""), {})
        configured_names = list(state.get("configured_models") or [])
        exact_models = [
            configured_by_name[name]
            for name in configured_names
            if name in configured_by_name
        ]
        verified_models = [
            str(model.get("name") or "")
            for model in exact_models
            if model.get("runtime_eligible")
        ]
        historical_verified_models = [
            str(model.get("name") or "")
            for model in exact_models
            if model.get("historical_verification_state") == "verified"
        ]
        if verified_models:
            provider_state = "verified"
        elif any(model.get("verification_state") == "blocked" for model in exact_models):
            provider_state = "blocked"
        elif any(model.get("verification_state") == "stale" for model in exact_models):
            provider_state = "stale"
        elif configured_names:
            provider_state = "configured"
        else:
            provider_state = str(state.get("state") or "available")
        catalog.append({
            **item,
            "verification_state": provider_state,
            "verified_models": verified_models,
            "historically_verified_models": historical_verified_models,
            "configured_models": configured_names,
            "verification_blocker": str(state.get("blocker") or ""),
        })
    modality_counts = {
        modality: sum(
            1
            for item in configured
            if modality in list(item.get("verified_modalities") or [])
        )
        for modality in ("text", "image", "audio", "video", "files", "tool_use")
    }
    historical_modality_counts = {
        modality: sum(
            1
            for item in configured
            if modality in list(item.get("historically_verified_modalities") or [])
        )
        for modality in ("text", "image", "audio", "video", "files", "tool_use")
    }
    credential_ready_count = sum(
        1 for item in configured if item.get("credential_ready")
    )
    runtime_eligible_count = sum(
        1 for item in configured if item.get("runtime_eligible")
    )
    return {
        "catalog": catalog,
        "catalog_provider_count": len(catalog),
        "configurable_provider_count": sum(
            1 for item in catalog if item.get("integration_state") != "future_adapter"
        ),
        "future_adapter_count": sum(
            1 for item in catalog if item.get("integration_state") == "future_adapter"
        ),
        "model_family_slot_count": sum(
            len(item.get("model_families") or []) for item in catalog
        ),
        "configured": configured,
        "ready_count": runtime_eligible_count,
        "credential_ready_count": credential_ready_count,
        "runtime_eligible_count": runtime_eligible_count,
        "configured_count": len(configured),
        "verified_count": sum(1 for item in configured if item.get("verification_state") == "verified"),
        "historically_verified_count": sum(
            1
            for item in configured
            if item.get("historical_verification_state") == "verified"
        ),
        "stale_receipt_count": sum(
            1 for item in configured if item.get("receipt_freshness") == "stale"
        ),
        "blocked_count": sum(1 for item in configured if item.get("verification_state") == "blocked"),
        "modality_counts": modality_counts,
        "historical_modality_counts": historical_modality_counts,
        "verification_audited_at": str(verification.get("audited_at") or ""),
        "verification_policy": dict(verification.get("verification_policy") or {}),
    }


def configure_provider(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    catalog = {str(item.get("id")): item for item in load_provider_catalog(root)}
    preset_id = str(payload.get("preset_id") or "").strip().lower()
    preset = catalog.get(preset_id)
    if not preset:
        raise ValueError("请选择受支持的 AI 供应商预设。")
    if str(preset.get("integration_state") or "configurable") == "future_adapter":
        raise ValueError("该 AI 公司目前只预留了位置，运行时适配器尚未接入，不能保存为可用模型。")
    if preset_id == "kimi-k3-local":
        preflight = preflight_kimi_k3(root)
        if not preflight.get("live_verified"):
            raise ValueError(
                "Kimi K3 尚未在本机或私有集群运行："
                + blocker_message(preflight)
            )

    provider_name = str(payload.get("name") or f"{preset_id}-user").strip().lower()
    if not SAFE_PROVIDER_ID.fullmatch(provider_name):
        raise ValueError("供应商名称只能使用小写字母、数字、点、下划线或短横线。")
    base_url = str(payload.get("base_url") or preset.get("base_url") or "").strip()
    model = str(payload.get("model") or preset.get("default_model") or "").strip()
    api_format = str(payload.get("api_format") or preset.get("api_format") or "openai").strip().lower()
    api_key_env = str(preset.get("api_key_env") or "").strip().upper()
    credential_ref = provider_credential_ref(provider_name) if api_key_env else ""
    if not base_url or not model:
        raise ValueError("接口地址和模型 ID 必须填写；模型 ID 以供应商控制台当前显示为准。")
    if not (base_url.startswith("https://") or base_url.startswith("http://127.0.0.1") or base_url.startswith("http://localhost")):
        raise ValueError("远程 AI API 必须使用 HTTPS；HTTP 只允许本机 127.0.0.1/localhost。")
    if api_format not in {"openai", "anthropic"}:
        raise ValueError("当前统一运行时只接受 OpenAI 兼容或 Anthropic 兼容协议。")

    api_key = str(payload.get("api_key") or "").strip()
    key_status: dict[str, Any] = {
        "credential_ref": credential_ref,
        "persist_status": "not_required",
        "enabled_providers": [provider_name],
    }
    if api_key_env and api_key:
        key_status = {
            **save_credential(root, credential_ref, api_key),
            "enabled_providers": [provider_name],
        }
    elif api_key_env and not credential_available(
        root,
        credential_ref=credential_ref,
        api_key_env=api_key_env,
    ):
        raise ValueError("该供应商需要 API Key。请输入后再保存，或先在本机配置对应环境变量。")
    provider = add_model(
        root,
        name=provider_name,
        label=str(payload.get("label") or preset.get("label") or provider_name),
        base_url=base_url.rstrip("/"),
        model=model,
        api_key_env=api_key_env,
        credential_ref=credential_ref,
        api_format=api_format,
        tier=str(payload.get("tier") or DEFAULT_MODEL_TIER),
    )
    return {
        "provider": {key: value for key, value in provider.items() if key != "api_key"},
        "key_status": key_status,
    }


def test_provider(root: Path, provider_name: str) -> dict[str, Any]:
    provider_name = str(provider_name or "").strip()
    if not provider_name:
        raise ValueError("请选择要测试的模型。")
    results = LLMClient(root=root, task="chat", provider=provider_name).test_connections(task="chat")
    if not results:
        return {
            "provider": provider_name,
            "status": "not_ready",
            "error": "模型未启用、缺少本机 API Key，或没有完整的接口地址/模型 ID。",
        }
    result = results[0]
    record_provider_test_result(root, result)
    return result


def record_provider_test_result(root: Path, result: dict[str, Any]) -> None:
    """Persist one exact health-check receipt so a successful probe is selectable."""

    provider = str(result.get("provider") or "").strip()
    model = str(result.get("model") or "").strip()
    if not provider or not model:
        return
    path = root / VERIFICATION_PATH
    verification = load_provider_verification(root)
    if not verification:
        verification = {
            "schema_version": 2,
            "catalog_provider_states": [],
            "live_receipts": [],
            "modality_receipts": [],
        }
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    receipt = {
        key: result[key]
        for key in (
            "provider",
            "model",
            "status",
            "code",
            "error",
            "status_code",
            "latency_ms",
            "reasoning_options",
            "speed_options",
        )
        if key in result
    }
    receipt["tested_at"] = now
    receipts = [
        item
        for item in verification.get("live_receipts", [])
        if isinstance(item, dict)
        and (
            str(item.get("provider") or "") != provider
            or str(item.get("model") or "") != model
        )
    ]
    receipts.append(receipt)
    verification["live_receipts"] = receipts
    verification["audited_at"] = now
    policy = verification.setdefault("verification_policy", {})
    policy.setdefault("enforce_receipt_freshness", True)
    policy.setdefault("max_age_hours", 24)
    policy.setdefault("require_exact_receipt_for_runtime_eligibility", True)
    counts = verification.setdefault("scope_counts", {})
    counts["live_text_health_checks"] = len(receipts)
    counts["verified_text_models"] = sum(
        str(item.get("status") or "") == "ok" for item in receipts
    )
    counts["blocked_live_tests"] = sum(
        str(item.get("status") or "") != "ok" for item in receipts
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )
