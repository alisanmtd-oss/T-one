from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .account import DEFAULT_MODEL_TIER, add_model, list_models
from .credential_store import credential_available, provider_credential_ref, save_credential
from .llm import LLMClient


CATALOG_PATH = Path("config") / "ai_provider_catalog.json"
VERIFICATION_PATH = Path("config") / "ai_provider_verification_state.json"
SAFE_PROVIDER_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")


def load_provider_catalog(root: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads((root / CATALOG_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    providers = payload.get("providers") if isinstance(payload, dict) else []
    return [dict(item) for item in providers if isinstance(item, dict) and item.get("id")]


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
    allowed = {"available", "configured", "verified", "blocked", "unsupported"}
    catalog_states = payload.get("catalog_provider_states")
    receipts = payload.get("live_receipts")
    if not isinstance(catalog_states, list) or not isinstance(receipts, list):
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
    rows: list[dict[str, Any]] = []
    for item in configured:
        row = dict(item)
        receipt = receipts.get((str(row.get("name") or ""), str(row.get("model") or "")))
        status = str((receipt or {}).get("status") or "")
        if status == "ok":
            state = "verified"
        elif receipt:
            state = "blocked"
        elif row.get("ready"):
            state = "configured"
        else:
            state = "configured"
        row.update({
            "verification_state": state,
            "connection_test_status": status or "not_tested",
            "connection_test_code": str((receipt or {}).get("code") or ""),
            "connection_test_error": str((receipt or {}).get("error") or ""),
            "connection_test_http_status": int((receipt or {}).get("status_code") or 0),
            "connection_test_latency_ms": int((receipt or {}).get("latency_ms") or 0),
            "last_tested_at": str(verification.get("audited_at") or "") if receipt else "",
            "verified_modalities": ["text"] if status == "ok" else [],
            "unknown_modalities": ["image", "audio", "video", "files", "tool_use"],
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
    catalog = []
    for item in load_provider_catalog(root):
        state = catalog_states.get(str(item.get("id") or ""), {})
        catalog.append({
            **item,
            "verification_state": str(state.get("state") or "available"),
            "verified_models": list(state.get("verified_models") or []),
            "configured_models": list(state.get("configured_models") or []),
            "verification_blocker": str(state.get("blocker") or ""),
        })
    return {
        "catalog": catalog,
        "configured": configured,
        "ready_count": sum(1 for item in configured if item.get("ready")),
        "configured_count": len(configured),
        "verified_count": sum(1 for item in configured if item.get("verification_state") == "verified"),
        "blocked_count": sum(1 for item in configured if item.get("verification_state") == "blocked"),
        "verification_audited_at": str(verification.get("audited_at") or ""),
    }


def configure_provider(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    catalog = {str(item.get("id")): item for item in load_provider_catalog(root)}
    preset_id = str(payload.get("preset_id") or "").strip().lower()
    preset = catalog.get(preset_id)
    if not preset:
        raise ValueError("请选择受支持的 AI 供应商预设。")

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
    return results[0]
