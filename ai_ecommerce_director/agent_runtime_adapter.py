from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ADAPTER_CONFIG_PATH = Path("config") / "agent_runtime_adapters.json"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,191}$")
SECRET_KEY = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|refresh[_-]?token|secret|password|"
    r"passphrase|authorization|cookie|credential|private[_-]?key)"
)
SECRET_VALUE = re.compile(
    r"(?i)(?:\bbearer\s+[A-Za-z0-9._~+/-]{8,}|\bsk-[A-Za-z0-9_-]{8,}|"
    r"\bgh[pousr]_[A-Za-z0-9]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)
BLOCKED_REQUEST_KEYS = {
    "yolo",
    "gateway",
    "cron",
    "messaging",
    "skill_write",
    "plugin_load",
    "remote_mcp",
    "terminal",
    "browser",
    "computer_use",
    "external_write",
    "external_side_effect",
}
ALLOWED_ACTION_CLASSES = {"local_analysis", "draft", "public_read"}
SAFE_BUSINESS_OBJECT_KEYS = {
    "object_type",
    "object_id",
    "version_ref",
    "source_ref",
    "project_id",
    "store_binding_id",
}


class RuntimeAdapterError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    text = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _required_id(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value or not SAFE_ID.fullmatch(value):
        raise RuntimeAdapterError(f"{key} is required and must be a safe scoped identifier.")
    return value


def _safe_text(value: Any, *, field: str, limit: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        raise RuntimeAdapterError(f"{field} is required.")
    if len(text) > limit:
        raise RuntimeAdapterError(f"{field} exceeds {limit} characters.")
    if SECRET_VALUE.search(text):
        raise RuntimeAdapterError(f"{field} contains a credential-like value.")
    return text


def _find_secret(value: Any, path: str = "request") -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if SECRET_KEY.search(str(key)):
                return child
            found = _find_secret(item, child)
            if found:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found = _find_secret(item, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(value, str) and SECRET_VALUE.search(value):
        return path
    return None


def _safe_source_refs(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > 20:
        raise RuntimeAdapterError("source_refs must be a list with at most 20 entries.")
    refs: list[str] = []
    for item in value:
        ref = str(item or "").strip().replace("\\", "/")
        if not ref or len(ref) > 240 or ref.startswith(("/", "//")) or ":" in ref.split("/")[0]:
            raise RuntimeAdapterError("source_refs must contain safe relative references.")
        if any(part in {"", ".", ".."} for part in ref.split("/")):
            raise RuntimeAdapterError("source_refs may not traverse directories.")
        if SECRET_VALUE.search(ref):
            raise RuntimeAdapterError("source_refs contains a credential-like value.")
        refs.append(ref)
    return refs


def _safe_capability_refs(value: Any) -> dict[str, list[str]]:
    """Keep only bounded identifiers; capability references never grant tools."""

    if value in (None, ""):
        return {"agents": [], "skills": []}
    if not isinstance(value, dict):
        raise RuntimeAdapterError("capability_refs must be an object.")
    result: dict[str, list[str]] = {"agents": [], "skills": []}
    for key, limit in (("agents", 2), ("skills", 3)):
        raw = value.get(key) or []
        if not isinstance(raw, list) or len(raw) > limit:
            raise RuntimeAdapterError(
                f"capability_refs.{key} must contain at most {limit} entries."
            )
        seen: set[str] = set()
        for item in raw:
            ref = " ".join(str(item or "").split()).strip()
            folded = ref.casefold()
            if not ref or len(ref) > 160 or SECRET_VALUE.search(ref):
                raise RuntimeAdapterError(f"capability_refs.{key} contains an unsafe value.")
            if folded in seen:
                continue
            seen.add(folded)
            result[key].append(ref)
    return result


def load_agent_runtime_adapter_config(root: Path) -> dict[str, Any]:
    path = Path(root) / ADAPTER_CONFIG_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise RuntimeAdapterError(f"Runtime adapter config is unavailable: {exc}") from exc
    adapters = payload.get("adapters") if isinstance(payload, dict) else None
    selected = str(payload.get("selected_adapter") or "") if isinstance(payload, dict) else ""
    if not isinstance(adapters, list) or not selected:
        raise RuntimeAdapterError("Runtime adapter config is incomplete.")
    adapter = next((item for item in adapters if item.get("id") == selected), None)
    if not isinstance(adapter, dict):
        raise RuntimeAdapterError("Selected runtime adapter does not exist.")
    source = adapter.get("source") if isinstance(adapter.get("source"), dict) else {}
    for key in ("repository", "version", "commit", "tree", "license", "license_sha256"):
        if not str(source.get(key) or "").strip():
            raise RuntimeAdapterError(f"Selected runtime adapter source.{key} is missing.")
    if adapter.get("enabled_toolsets") != []:
        raise RuntimeAdapterError("The isolated pilot must expose zero Hermes toolsets.")
    blocked = {str(item) for item in adapter.get("blocked_features") or []}
    if not BLOCKED_REQUEST_KEYS.issubset(blocked | {"external_side_effect"}):
        missing = sorted((BLOCKED_REQUEST_KEYS - {"external_side_effect"}) - blocked)
        raise RuntimeAdapterError(f"Runtime adapter blocked_features is incomplete: {missing}")
    return {"catalog": payload, "adapter": adapter}


def runtime_adapter_snapshot(root: Path) -> dict[str, Any]:
    loaded = load_agent_runtime_adapter_config(root)
    adapter = loaded["adapter"]
    return {
        "selected_adapter": adapter["id"],
        "status": adapter.get("status"),
        "source": dict(adapter["source"]),
        "enabled_toolsets": [],
        "blocked_features": list(adapter.get("blocked_features") or []),
        "business_control_plane": "t_one",
        "external_action_count": 0,
    }


def prepare_runtime_request(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeAdapterError("Runtime request must be an object.")
    secret_path = _find_secret(payload)
    if secret_path:
        raise RuntimeAdapterError(f"Runtime request contains a forbidden credential field: {secret_path}")
    for key in BLOCKED_REQUEST_KEYS:
        if payload.get(key) not in (None, False, 0, "", [], {}):
            raise RuntimeAdapterError(f"Runtime pilot forbids {key}.")

    loaded = load_agent_runtime_adapter_config(root)
    adapter = loaded["adapter"]
    tenant_id = _required_id(payload, "tenant_id")
    project_id = _required_id(payload, "project_id")
    task_id = _required_id(payload, "task_id")
    task_run_id = _required_id(payload, "task_run_id")
    provider_id = _required_id(payload, "provider_id")
    model_id = _required_id(payload, "model_id")
    idempotency_key = _required_id(payload, "idempotency_key")
    platform = _required_id(payload, "platform").lower()
    if platform == "amazon":
        raise RuntimeAdapterError("Amazon remains paused by the owner.")
    action_class = str(payload.get("action_class") or "").strip().lower()
    if action_class not in ALLOWED_ACTION_CLASSES:
        raise RuntimeAdapterError("The isolated pilot only accepts local_analysis, draft, or public_read.")
    instruction = _safe_text(payload.get("instruction"), field="instruction", limit=8000)

    country_site = str(payload.get("country_site") or "").strip().upper()
    store_binding_id = str(payload.get("store_binding_id") or "").strip()
    execution_identity_id = str(payload.get("execution_identity_id") or "").strip()
    if platform not in {"general", "public_web", "creative"}:
        if not country_site or not store_binding_id or not execution_identity_id:
            raise RuntimeAdapterError(
                "Platform-scoped work requires country_site, store_binding_id, and execution_identity_id."
            )
        if not all(SAFE_ID.fullmatch(item) for item in (country_site, store_binding_id, execution_identity_id)):
            raise RuntimeAdapterError("Store execution scope contains an unsafe identifier.")

    object_refs: list[dict[str, str]] = []
    raw_objects = payload.get("business_object_refs") or []
    if not isinstance(raw_objects, list) or len(raw_objects) > 20:
        raise RuntimeAdapterError("business_object_refs must be a list with at most 20 entries.")
    for raw in raw_objects:
        if not isinstance(raw, dict):
            raise RuntimeAdapterError("business_object_refs entries must be objects.")
        item = {
            key: str(raw.get(key) or "").strip()
            for key in SAFE_BUSINESS_OBJECT_KEYS
            if str(raw.get(key) or "").strip()
        }
        if not item.get("object_type") or not item.get("object_id"):
            raise RuntimeAdapterError("Each business object needs object_type and object_id.")
        if item.get("project_id") and item["project_id"] != project_id:
            raise RuntimeAdapterError("Cross-project business objects are forbidden.")
        if item.get("store_binding_id") and item["store_binding_id"] != store_binding_id:
            raise RuntimeAdapterError("Cross-store business objects are forbidden.")
        if _find_secret(item, "business_object_ref"):
            raise RuntimeAdapterError("Business object reference contains credential-like data.")
        object_refs.append(item)

    scope = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "task_id": task_id,
        "platform": platform,
        "country_site": country_site,
        "store_binding_id": store_binding_id,
        "execution_identity_id": execution_identity_id,
    }
    scope_hash = _sha256(scope)
    request_id = "runtime-" + _sha256(
        {"adapter": adapter["id"], "task_run_id": task_run_id, "idempotency_key": idempotency_key, "scope": scope}
    )[:24]
    capability_refs = _safe_capability_refs(payload.get("capability_refs"))
    request = {
        "schema_version": 1,
        "request_id": request_id,
        "created_at": _now_iso(),
        "adapter_id": adapter["id"],
        "runtime_source": dict(adapter["source"]),
        "provider_id": provider_id,
        "model_id": model_id,
        "task_run_id": task_run_id,
        "idempotency_key": idempotency_key,
        "action_class": action_class,
        "instruction": instruction,
        "scope": scope,
        "scope_hash": scope_hash,
        "source_refs": _safe_source_refs(payload.get("source_refs")),
        "business_object_refs": object_refs,
        "capability_refs": capability_refs,
        "runtime_policy": {
            "enabled_toolsets": [],
            "maximum_iterations": 1,
            "network": "loopback_model_fixture_only",
            "external_actions_allowed": False,
            "blocked_features": list(adapter.get("blocked_features") or []),
        },
    }
    request["runtime_prompt"] = (
        "T-one 已完成权限和范围校验。只处理以下本地草稿任务；不得调用工具、访问外网、修改文件或执行外部动作。\n"
        + _canonical({
            "request_id": request_id,
            "instruction": instruction,
            "scope": scope,
            "source_refs": request["source_refs"],
            "business_object_refs": object_refs,
            "capability_refs": capability_refs,
        })
    )
    request["request_hash"] = _sha256({k: v for k, v in request.items() if k not in {"created_at", "request_hash"}})
    return request


def prepare_task_run_runtime_request(
    root: Path,
    run: dict[str, Any],
    *,
    provider_id: str,
    model_id: str,
    idempotency_key: str = "",
) -> dict[str, Any]:
    """Translate one durable T-one task run into the narrow runtime envelope."""
    if not isinstance(run, dict) or not str(run.get("id") or "").strip():
        raise RuntimeAdapterError("A durable T-one task run is required.")
    mode = str(run.get("mode") or "").strip().lower()
    if mode != "analysis":
        raise RuntimeAdapterError("Only T-one analysis runs may enter the isolated runtime pilot.")
    plan = run.get("orchestration_plan") if isinstance(run.get("orchestration_plan"), dict) else {}
    action_class = str(plan.get("action_class") or "local_analysis").strip().lower()
    if action_class not in ALLOWED_ACTION_CLASSES:
        raise RuntimeAdapterError("The T-one task run requests an action class forbidden by the pilot.")
    context = run.get("context_refs") if isinstance(run.get("context_refs"), dict) else {}
    capability_context = (
        run.get("capability_context")
        if isinstance(run.get("capability_context"), dict)
        else {}
    )
    return prepare_runtime_request(
        root,
        {
            "tenant_id": str(run.get("tenant_id") or "local"),
            "project_id": str(run.get("project_id") or ""),
            "task_id": str(run.get("task_id") or ""),
            "task_run_id": str(run.get("id") or ""),
            "provider_id": provider_id,
            "model_id": model_id,
            "idempotency_key": idempotency_key or str(run.get("idempotency_key") or run.get("id") or ""),
            "platform": str(run.get("platform") or "general"),
            "country_site": str(run.get("country") or ""),
            "store_binding_id": str(run.get("store_binding_id") or ""),
            "execution_identity_id": str(run.get("execution_identity_id") or ""),
            "action_class": action_class,
            "instruction": str(run.get("instruction") or ""),
            "source_refs": list(context.get("source_refs") or []),
            "business_object_refs": list(context.get("business_object_refs") or []),
            "capability_refs": {
                "agents": list(capability_context.get("selected_agent_refs") or []),
                "skills": list(capability_context.get("selected_skill_refs") or []),
            },
        },
    )


def validate_runtime_result(request: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise RuntimeAdapterError("Runtime result must be an object.")
    secret_path = _find_secret(result, "result")
    if secret_path:
        raise RuntimeAdapterError(f"Runtime result contains credential-like data: {secret_path}")
    expected = {
        "request_id": request.get("request_id"),
        "adapter_id": request.get("adapter_id"),
        "provider_id": request.get("provider_id"),
        "model_id": request.get("model_id"),
        "scope_hash": request.get("scope_hash"),
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise RuntimeAdapterError(f"Runtime result {key} does not match the request.")
    if result.get("tool_names") not in ([], None) or int(result.get("tool_call_count") or 0) != 0:
        raise RuntimeAdapterError("The isolated runtime returned a tool call.")
    if int(result.get("external_action_count") or 0) != 0:
        raise RuntimeAdapterError("The isolated runtime reported an external action.")
    final_text = _safe_text(result.get("final_text"), field="final_text", limit=12000)
    return {
        "receipt_ref": f"{request['request_id']}:receipt",
        "status": "runtime_analysis_complete",
        "recorded_at": _now_iso(),
        "request_id": request["request_id"],
        "request_hash": request["request_hash"],
        "adapter_id": request["adapter_id"],
        "runtime_version": str(result.get("runtime_version") or ""),
        "runtime_commit": str(result.get("runtime_commit") or ""),
        "provider_id": request["provider_id"],
        "model_id": request["model_id"],
        "task_run_id": request["task_run_id"],
        "scope": dict(request["scope"]),
        "scope_hash": request["scope_hash"],
        "result_summary": final_text,
        "result_sha256": _sha256(final_text),
        "source_refs": list(request.get("source_refs") or []),
        "business_object_refs": list(request.get("business_object_refs") or []),
        "tool_call_count": 0,
        "external_action_count": 0,
        "external_side_effect_observed": False,
        "process_cleanup_verified": bool(result.get("process_cleanup_verified")),
    }
