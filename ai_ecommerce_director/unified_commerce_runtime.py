from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .communications_connector_control import communications_connector_snapshot
from .skill_agents import list_skill_agents


CONTRACT_PATH = Path("config") / "unified_commerce_runtime.json"
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
CONNECTED_STATES = {"verified", "live_verified", "core_available"}
SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "client_secret",
    "cookie",
    "password",
    "refresh_token",
    "secret",
    "session_cookie",
    "token",
}
EXTERNAL_ACTION_CLASSES = {
    "external_write",
    "money_or_budget",
    "credential_or_authorization",
}


def load_unified_commerce_contract(root: Path) -> dict[str, Any]:
    path = root.resolve() / CONTRACT_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise ValueError(f"统一运行时契约不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("统一运行时契约不是有效 JSON。") from exc
    errors = validate_unified_commerce_contract(payload)
    if errors:
        raise ValueError("统一运行时契约无效：" + "; ".join(errors))
    return payload


def validate_unified_commerce_contract(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["root_must_be_object"]
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("schema_version_must_be_1")
    connectors = payload.get("connector_catalog")
    if not isinstance(connectors, list) or not connectors:
        errors.append("connector_catalog_required")
        connectors = []
    connector_ids: set[str] = set()
    for index, connector in enumerate(connectors):
        prefix = f"connector[{index}]"
        if not isinstance(connector, dict):
            errors.append(f"{prefix}_must_be_object")
            continue
        connector_id = str(connector.get("id") or "")
        if not IDENTIFIER.fullmatch(connector_id):
            errors.append(f"{prefix}_invalid_id")
        elif connector_id in connector_ids:
            errors.append(f"{prefix}_duplicate_id")
        connector_ids.add(connector_id)
        for key in ("name", "kind", "status", "source"):
            if not str(connector.get(key) or "").strip():
                errors.append(f"{prefix}_{key}_required")
        capabilities = connector.get("capabilities")
        if not isinstance(capabilities, list) or not capabilities:
            errors.append(f"{prefix}_capabilities_required")
        if any(not isinstance(item, str) or not item for item in capabilities or []):
            errors.append(f"{prefix}_invalid_capability")
    profiles = payload.get("task_profiles")
    if not isinstance(profiles, dict) or not profiles:
        errors.append("task_profiles_required")
        profiles = {}
    action_classes = payload.get("action_classes")
    if not isinstance(action_classes, dict) or not action_classes:
        errors.append("action_classes_required")
        action_classes = {}
    for task_id, profile in profiles.items():
        prefix = f"task_profile[{task_id}]"
        if not IDENTIFIER.fullmatch(str(task_id)) or not isinstance(profile, dict):
            errors.append(f"{prefix}_invalid")
            continue
        if profile.get("default_action_class") not in action_classes:
            errors.append(f"{prefix}_unknown_action_class")
        for key in ("connector_kinds", "capabilities", "required_scope"):
            if not isinstance(profile.get(key), list):
                errors.append(f"{prefix}_{key}_must_be_array")
        required_by_action = profile.get("required_scope_by_action")
        if required_by_action is not None:
            if not isinstance(required_by_action, dict):
                errors.append(f"{prefix}_required_scope_by_action_must_be_object")
            else:
                for action_name, required in required_by_action.items():
                    if action_name not in action_classes:
                        errors.append(f"{prefix}_required_scope_by_action_unknown_action")
                    if not isinstance(required, list) or any(
                        not isinstance(item, str) or not item for item in required or []
                    ):
                        errors.append(
                            f"{prefix}_required_scope_by_action_{action_name}_must_be_array"
                        )
        skill_agent_ids = profile.get("skill_agent_ids")
        if skill_agent_ids is not None and (
            not isinstance(skill_agent_ids, list)
            or any(
                not isinstance(item, str) or not IDENTIFIER.fullmatch(item)
                for item in skill_agent_ids
            )
        ):
            errors.append(f"{prefix}_skill_agent_ids_must_be_identifier_array")
    return errors


def unified_commerce_runtime_snapshot(root: Path) -> dict[str, Any]:
    root = root.resolve()
    contract = load_unified_commerce_contract(root)
    communications = communications_connector_snapshot(root)
    communication_by_id = {
        str(item.get("id") or ""): item
        for item in communications.get("connectors", [])
        if isinstance(item, dict)
    }
    integration_by_id = _integration_hub_connectors(root)
    connectors: list[dict[str, Any]] = []
    for configured in contract["connector_catalog"]:
        item = dict(configured)
        adapter = item.get("adapter") if isinstance(item.get("adapter"), dict) else {}
        adapter_type = str(adapter.get("type") or "")
        adapter_id = str(adapter.get("id") or "")
        actual: dict[str, Any] = {}
        if adapter_type == "communications":
            actual = communication_by_id.get(adapter_id, {})
        elif adapter_type == "integration_hub":
            actual = integration_by_id.get(adapter_id, {})
        status = str(actual.get("status") or item.get("status") or "unknown")
        connector = {
            "id": item["id"],
            "name": item["name"],
            "kind": item["kind"],
            "status": status,
            "source": item["source"],
            "integration_modes": list(item.get("integration_modes") or []),
            "capabilities": list(item.get("capabilities") or []),
            "required_scope": list(item.get("required_scope") or []),
            "connected": status in CONNECTED_STATES,
            "verified_binding_count": int(actual.get("verified_binding_count") or 0),
            "external_action_count": 0,
        }
        if connector["connected"] and adapter_type == "communications" and connector["verified_binding_count"] < 1:
            connector["connected"] = False
        connectors.append(connector)
    agents = list_skill_agents(root)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "product": dict(contract["product"]),
        "core_flow": list(contract["core_flow"]),
        "data_domains": list(contract["data_domains"]),
        "action_classes": dict(contract["action_classes"]),
        "hard_boundaries": list(contract["hard_boundaries"]),
        "connector_count": len(connectors),
        "connected_connector_count": sum(1 for item in connectors if item["connected"]),
        "unconnected_connector_count": sum(1 for item in connectors if not item["connected"]),
        "skill_agent_count": len(agents),
        "runnable_skill_agent_count": sum(1 for item in agents if item.get("executable") and item.get("enabled")),
        "connectors": connectors,
        "task_profiles": sorted(contract["task_profiles"]),
        "external_action_count": 0,
    }


def plan_unified_commerce_task(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("任务计划请求必须是对象。")
    sensitive = _find_sensitive_key(payload)
    if sensitive:
        raise ValueError(f"任务计划不能包含原始凭据：{sensitive}")
    contract = load_unified_commerce_contract(root)
    task_type = str(payload.get("task_type") or "").strip()
    profile = contract["task_profiles"].get(task_type)
    if not isinstance(profile, dict):
        raise ValueError("未知 task_type；请使用统一运行时登记的任务类型。")
    requested_action = str(payload.get("action_class") or profile["default_action_class"]).strip()
    action_contract = contract["action_classes"].get(requested_action)
    if not isinstance(action_contract, dict):
        raise ValueError("未知 action_class。")
    scope = payload.get("scope") if isinstance(payload.get("scope"), dict) else {}
    clean_scope = _clean_scope(scope)
    required_by_action = (
        profile.get("required_scope_by_action")
        if isinstance(profile.get("required_scope_by_action"), dict)
        else {}
    )
    required_scope = list(
        required_by_action.get(requested_action) or profile["required_scope"]
    )
    missing_scope = [key for key in required_scope if not clean_scope.get(key)]
    snapshot = unified_commerce_runtime_snapshot(root)
    connector_kinds = set(profile["connector_kinds"])
    capabilities = set(profile["capabilities"])
    eligible = [
        item
        for item in snapshot["connectors"]
        if item["kind"] in connector_kinds
        and capabilities.intersection(item["capabilities"])
    ]
    connected = [item for item in eligible if item["connected"]]
    external_side_effect = bool(action_contract.get("external_side_effect"))
    if missing_scope:
        status = "blocked_scope"
    elif requested_action in {"local_analysis", "draft", "public_read"}:
        status = "ready_local_or_public" if connected or requested_action in {"local_analysis", "draft"} else "blocked_connector"
    else:
        status = "ready_for_owner_preflight" if connected else "blocked_connector"
    skills = _matching_skills(root, capabilities, profile.get("skill_agent_ids"))
    return {
        "schema_version": 1,
        "task_type": task_type,
        "action_class": requested_action,
        "status": status,
        "scope": clean_scope,
        "required_scope": required_scope,
        "missing_scope": missing_scope,
        "required_capabilities": sorted(capabilities),
        "eligible_connectors": [_connector_plan_view(item) for item in eligible],
        "connected_connectors": [_connector_plan_view(item) for item in connected],
        "skill_agents": skills,
        "approval": str(action_contract.get("approval") or "unknown"),
        "approval_required": external_side_effect,
        "execution_allowed": False,
        "external_action_count": 0,
        "steps": _plan_steps(status, requested_action, external_side_effect),
        "message": _plan_message(status, missing_scope, requested_action),
    }


def _integration_hub_connectors(root: Path) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads((root / "config" / "integration_hub.json").read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        str(item.get("id") or ""): item
        for item in payload.get("connectors", [])
        if isinstance(item, dict)
    }


def _find_sensitive_key(value: Any, path: str = "request") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in SENSITIVE_KEYS or normalized.endswith("_secret"):
                return f"{path}.{key}"
            found = _find_sensitive_key(child, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_sensitive_key(child, f"{path}[{index}]")
            if found:
                return found
    return None


def _clean_scope(scope: dict[str, Any]) -> dict[str, str]:
    clean: dict[str, str] = {}
    for key, value in scope.items():
        name = str(key or "").strip()
        text = str(value or "").strip()
        if not name or not text:
            continue
        if not IDENTIFIER.fullmatch(name) or not IDENTIFIER.fullmatch(text):
            raise ValueError(f"scope.{name or 'unknown'} 必须是稳定标识符，不能放原始客户或凭据数据。")
        clean[name] = text
    return clean


def _matching_skills(
    root: Path,
    capabilities: set[str],
    exact_ids: Any = None,
) -> list[dict[str, Any]]:
    requested_ids = (
        {str(item) for item in exact_ids}
        if isinstance(exact_ids, list)
        else None
    )
    tokens = {token for capability in capabilities for token in capability.split("_") if len(token) >= 3}
    matches: list[dict[str, Any]] = []
    for skill in list_skill_agents(root):
        if requested_ids is not None and str(skill.get("id") or "") not in requested_ids:
            continue
        searchable = " ".join(str(skill.get(key) or "") for key in ("id", "name", "agent_module")).lower()
        if requested_ids is not None or tokens.intersection(searchable.split()) or any(token in searchable for token in tokens):
            matches.append(
                {
                    "id": skill.get("id"),
                    "name": skill.get("name"),
                    "kind": skill.get("kind"),
                    "executable": bool(skill.get("executable")),
                    "enabled": bool(skill.get("enabled")),
                }
            )
    if requested_ids is not None:
        matches.sort(key=lambda item: list(exact_ids).index(str(item.get("id"))))
    return matches[:20]


def _connector_plan_view(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "name": item["name"],
        "kind": item["kind"],
        "status": item["status"],
        "connected": item["connected"],
        "capabilities": item["capabilities"],
    }


def _plan_steps(status: str, action_class: str, external_side_effect: bool) -> list[dict[str, str]]:
    steps = [
        {"id": "scope", "state": "blocked" if status == "blocked_scope" else "ready"},
        {"id": "data_read", "state": "blocked" if status in {"blocked_scope", "blocked_connector"} else "ready"},
        {"id": "ai_skill_processing", "state": "ready" if status != "blocked_scope" else "waiting"},
        {"id": "draft", "state": "ready" if action_class in {"draft", "local_analysis", "public_read"} and status != "blocked_scope" else "waiting"},
        {"id": "approval", "state": "required" if external_side_effect else "not_required"},
        {"id": "execution", "state": "not_executed"},
        {"id": "effect_verification", "state": "waiting"},
        {"id": "receipt_and_learning", "state": "waiting"},
    ]
    return steps


def _plan_message(status: str, missing_scope: list[str], action_class: str) -> str:
    if status == "blocked_scope":
        return "缺少精确任务范围：" + ", ".join(missing_scope)
    if status == "blocked_connector":
        return "范围完整，但没有已验证连接器；可以继续准备资料和草稿，不能声称已读取或执行外部系统。"
    if status == "ready_for_owner_preflight":
        return "连接和范围满足预检条件；本次只生成计划，实际外部动作仍需负责人确认。"
    if action_class == "draft":
        return "可以生成本地草稿；未授权数据保持未知，草稿不会自动发送或发布。"
    return "可以执行本地分析或公开资料处理；本次没有外部动作。"


__all__ = [
    "load_unified_commerce_contract",
    "plan_unified_commerce_task",
    "unified_commerce_runtime_snapshot",
    "validate_unified_commerce_contract",
]
