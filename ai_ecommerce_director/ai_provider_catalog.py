from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .account import DEFAULT_MODEL_TIER, add_model, list_models
from .credential_store import credential_available, provider_credential_ref, save_credential
from .llm import LLMClient


CATALOG_PATH = Path("config") / "ai_provider_catalog.json"
SAFE_PROVIDER_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")


def load_provider_catalog(root: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads((root / CATALOG_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    providers = payload.get("providers") if isinstance(payload, dict) else []
    return [dict(item) for item in providers if isinstance(item, dict) and item.get("id")]


def provider_catalog_snapshot(root: Path) -> dict[str, Any]:
    configured = list_models(root)
    return {
        "catalog": load_provider_catalog(root),
        "configured": configured,
        "ready_count": sum(1 for item in configured if item.get("ready")),
        "configured_count": len(configured),
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
