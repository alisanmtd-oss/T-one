from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import append_record, read_records
from .types import IntakeRecord


REGISTRY_PATH = Path("config") / "web_ai_bridge.json"
OUTBOX_DIR = Path("outputs") / "non_api_ai_bridge"
LEDGER_PATH = OUTBOX_DIR / "handoff_ledger.jsonl"
DELIVERY_ATTEMPT_LEDGER_PATH = OUTBOX_DIR / "delivery_attempts.jsonl"
REVIEW_LEDGER_PATH = OUTBOX_DIR / "review_ledger.jsonl"
RESULT_DIR = OUTBOX_DIR / "results"

SAFE_PROVIDER_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,79}$")
SAFE_HANDOFF_ID = re.compile(r"^non-api-ai-[a-f0-9]{16}$")
SAFE_RESULT_ID = re.compile(r"^non-api-ai-[a-f0-9]{16}-result-[a-f0-9]{10}$")
SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(api[_ -]?key|token|password|secret|cookie|session)\s*[:=]\s*([^\s,;，；]+)"),
    re.compile(r"(?i)(authorization)\s*:\s*(bearer\s+)?([^\s,;，；]+)"),
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _listify(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def redact_sensitive_text(text: str) -> tuple[str, int]:
    redacted = str(text or "")
    count = 0
    for pattern in SENSITIVE_PATTERNS:
        redacted, changed = pattern.subn(lambda match: f"{match.group(1)}=[redacted]", redacted)
        count += changed
    return redacted, count


def _task_scope_prompt_lines(
    root: Path,
    project_id: str,
    task_id: str,
    instruction: str,
) -> list[str]:
    """Resolve bounded store and Agent/Skill context for one external-AI turn."""

    if not project_id or not task_id:
        return []
    try:
        from .capability_context_manager import resolve_task_capability_context
        from .task_execution_runtime import latest_shein_order_context_line
        from .workspace_runtime import load_workspace_config
        from .workspace_schema import find_task_context

        context = find_task_context(load_workspace_config(root), task_id)
    except (OSError, TypeError, ValueError):
        return []
    if context is None:
        return []
    project, channel, store, task = context
    if str(project.get("id") or "").strip().lower() != project_id.strip().lower():
        return []

    project_name = str(project.get("name") or project_id).strip()[:160]
    task_name = str(task.get("name") or task_id).strip()[:160]
    platform = str(
        (channel or {}).get("platform") or task.get("platform") or "未指定"
    ).strip()[:80]
    country_site = str(
        (channel or {}).get("country_site")
        or task.get("country_site")
        or task.get("country")
        or "未指定"
    ).strip()[:40]
    lines = [
        f"当前项目：{project_name}（{project_id}）",
        f"当前任务：{task_name}（{task_id}）",
        f"平台与站点：{platform} / {country_site}",
    ]
    if isinstance(store, dict):
        store_name = str(store.get("name") or "未命名店铺").strip()[:160]
        binding_id = str(store.get("id") or task.get("store_binding_id") or "").strip()[:100]
        external_id = str(
            store.get("external_id") or store.get("store_external_id") or ""
        ).strip()[:100]
        status = str(store.get("status") or "unknown").strip()[:80]
        mode = str(store.get("store_model") or store.get("store_mode") or "未指定").strip()[:80]
        lines.extend(
            [
                f"当前店铺：{store_name}",
                f"店铺绑定 ID：{binding_id or '未指定'}",
                f"平台店铺编号：{external_id or '未指定'}",
                f"店铺模式与连接状态：{mode} / {status}",
            ]
        )

    toolkit = task.get("toolkit") if isinstance(task.get("toolkit"), dict) else {}
    configured_agents = [
        str(item).strip() for item in toolkit.get("agents", []) if str(item).strip()
    ]
    configured_skills = [
        str(item).strip() for item in toolkit.get("skills", []) if str(item).strip()
    ]
    lines.append(
        "任务已配置能力：Agent="
        + ("、".join(configured_agents) or "none")
        + "；Skill="
        + ("、".join(configured_skills) or "none")
    )
    capability = resolve_task_capability_context(root, task, instruction)
    compact_lines = capability.get("compact_context_lines")
    if isinstance(compact_lines, list):
        lines.extend(
            str(item).strip()[:800]
            for item in compact_lines[:2]
            if str(item).strip()
        )
    order_line = latest_shein_order_context_line(root, task_id)
    if order_line:
        lines.append(str(order_line).strip()[:1200])
    lines.append(
        "使用边界：按上述任务已选 Agent 职责和 Skill 流程协助分析；"
        "不得声称已调用未连接工具，不得执行发布、改价、退款、发货或其他店铺写入。"
    )
    return lines


def load_non_api_ai_registry(root: Path) -> dict[str, Any]:
    payload = _load_json(root / REGISTRY_PATH)
    providers: list[dict[str, Any]] = []
    for item in payload.get("providers", []):
        if not isinstance(item, dict):
            continue
        provider_id = str(item.get("id") or "").strip().lower()
        if not SAFE_PROVIDER_ID.fullmatch(provider_id):
            continue
        bridge_type = str(
            item.get("bridge_type")
            or ("desktop_gui" if item.get("local_app_path") else "web_gui")
        ).strip()
        delivery_modes = _listify(item.get("delivery_modes"))
        if not delivery_modes:
            delivery_modes = [bridge_type]
        capabilities = _listify(item.get("capabilities"))
        if not capabilities:
            capabilities = ["open_target", "prepare_handoff_prompt"]
        current_status = str(item.get("current_status") or "").strip() or (
            "registered_not_verified" if item.get("enabled", True) else "disabled"
        )
        providers.append(
            {
                **item,
                "id": provider_id,
                "name": str(item.get("name") or provider_id),
                "enabled": bool(item.get("enabled", True)),
                "bridge_type": bridge_type,
                "delivery_modes": delivery_modes,
                "capabilities": capabilities,
                "current_status": current_status,
                "automation_verified": current_status == "verified_local_automation"
                or bool(item.get("automation_verified") is True),
                "external_action_authorized": bool(item.get("external_action_authorized") is True),
            }
        )
    return {
        "schema_version": int(payload.get("schema_version") or 1),
        "enabled": bool(payload.get("enabled", False)),
        "project_name": str(payload.get("project_name") or "T-one"),
        "safety_mode": str(payload.get("safety_mode") or "read_only_until_human_confirmation"),
        "notes": _listify(payload.get("notes")),
        "providers": providers,
        "tasks": [dict(item) for item in payload.get("tasks", []) if isinstance(item, dict)],
    }


def non_api_ai_bridge_snapshot(root: Path) -> dict[str, Any]:
    registry = load_non_api_ai_registry(root)
    providers = registry["providers"]
    enabled = [item for item in providers if item.get("enabled")]
    verified = [item for item in enabled if item.get("automation_verified")]
    manually_verified = [
        item
        for item in enabled
        if str(item.get("current_status") or "").startswith("manually_verified_")
    ]
    result_records = read_records(root, "external_ai_result")
    bridge_results = [
        record
        for record in result_records
        if str(record.source or "").startswith("non_api_ai_bridge:")
    ]
    recovery = non_api_ai_bridge_recovery_snapshot(root)
    durable_result_count = int(recovery.get("result_count") or 0)
    pending_owner_review_count = (
        int(recovery.get("pending_owner_review_count") or 0)
        if durable_result_count
        else len([record for record in bridge_results if record.review_status != "approved"])
    )
    approved_for_task_use_count = int(
        recovery.get("approved_for_task_use_count") or 0
    )

    def durable_review_status(record: IntakeRecord) -> str:
        relative_path = str(record.fields.get("result_path") or "").strip()
        if relative_path:
            payload = _load_json(root / relative_path)
            status = str(payload.get("review_status") or "").strip()
            if status:
                return status
        return record.review_status

    mode_counts: dict[str, int] = {}
    for item in enabled:
        for mode in item.get("delivery_modes", []):
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
    return {
        "ok": True,
        "schema_version": registry["schema_version"],
        "enabled": registry["enabled"],
        "safety_mode": registry["safety_mode"],
        "provider_count": len(providers),
        "enabled_provider_count": len(enabled),
        "verified_automation_count": len(verified),
        "manually_verified_existing_login_count": len(manually_verified),
        "api_key_required_count": sum(1 for item in enabled if item.get("requires_api_key")),
        "no_api_provider_count": sum(1 for item in enabled if not item.get("requires_api_key")),
        "external_action_authorized_count": sum(
            1 for item in enabled if item.get("external_action_authorized")
        ),
        "returned_result_count": durable_result_count or len(bridge_results),
        "pending_owner_review_result_count": pending_owner_review_count,
        "approved_for_task_use_result_count": approved_for_task_use_count,
        "restart_recovery_verified": bool(recovery.get("restart_recovery_verified")),
        "recovery_integrity_ok": bool(recovery.get("ok")),
        "delivery_mode_counts": mode_counts,
        "recent_results": [
            {
                "record_id": record.record_id,
                "created_at": record.created_at,
                "handoff_id": str(record.fields.get("handoff_id") or ""),
                "provider_id": str(record.fields.get("provider_id") or ""),
                "task_id": str(record.fields.get("task_id") or ""),
                "review_status": durable_review_status(record),
                "fact_status": str(record.fields.get("fact_status") or ""),
                "result_path": str(record.fields.get("result_path") or ""),
            }
            for record in sorted(bridge_results, key=lambda item: item.created_at, reverse=True)[:5]
        ],
        "providers": [
            {
                "id": item["id"],
                "name": item["name"],
                "enabled": item["enabled"],
                "bridge_type": item["bridge_type"],
                "delivery_modes": item["delivery_modes"],
                "capabilities": item["capabilities"],
                "current_status": item["current_status"],
                "automation_verified": item["automation_verified"],
                "external_action_authorized": item["external_action_authorized"],
                "url": str(item.get("url") or ""),
                "local_app_path": str(item.get("local_app_path") or ""),
                "cli_command": str(item.get("cli_command") or ""),
                "project_hint": str(item.get("project_hint") or ""),
                "manual_verification": (
                    dict(item.get("manual_verification"))
                    if isinstance(item.get("manual_verification"), dict)
                    else {}
                ),
            }
            for item in enabled
        ],
    }


def _find_provider(root: Path, provider_id: str) -> dict[str, Any]:
    normalized = str(provider_id or "").strip().lower()
    for provider in load_non_api_ai_registry(root)["providers"]:
        if provider["id"] == normalized and provider.get("enabled"):
            return provider
    raise ValueError("请选择已登记且启用的无 API AI 入口。")


def _load_handoff(root: Path, handoff_id: str) -> tuple[Path, dict[str, Any]]:
    normalized = str(handoff_id or "").strip()
    if not SAFE_HANDOFF_ID.fullmatch(normalized):
        raise ValueError("请选择有效的外部 AI 交接包编号。")
    handoff_path = root / OUTBOX_DIR / f"{normalized}.json"
    try:
        handoff = json.loads(handoff_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ValueError("找不到这个外部 AI 交接包。") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("外部 AI 交接包无法解析，请先修复回执文件。") from exc
    if not isinstance(handoff, dict) or handoff.get("id") != normalized:
        raise ValueError("外部 AI 交接包内容与编号不一致。")
    return handoff_path, handoff


def _load_result(root: Path, result_id: str) -> tuple[Path, dict[str, Any]]:
    normalized = str(result_id or "").strip()
    if not SAFE_RESULT_ID.fullmatch(normalized):
        raise ValueError("请选择有效的外部 AI 返回结果编号。")
    result_path = root / RESULT_DIR / f"{normalized}.json"
    try:
        result = json.loads(result_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ValueError("找不到这个外部 AI 返回结果。") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("外部 AI 返回结果无法解析，请先修复回执文件。") from exc
    if not isinstance(result, dict) or result.get("id") != normalized:
        raise ValueError("外部 AI 返回结果内容与编号不一致。")
    return result_path, result


def build_non_api_ai_handoff(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    provider = _find_provider(root, str(payload.get("provider_id") or ""))
    raw_message = str(payload.get("message") or "").strip()
    if not raw_message:
        raise ValueError("请先输入要交给外部 AI 的消息。")
    safe_message, redaction_count = redact_sensitive_text(raw_message)
    project_id = str(payload.get("project_id") or "").strip()
    task_id = str(payload.get("task_id") or "").strip()
    requested_action = str(payload.get("requested_action") or "send_message").strip()
    approved_auto_delivery = bool(payload.get("approved_auto_delivery") is True)
    automation_ready = bool(provider.get("automation_verified"))
    external_authorized = bool(provider.get("external_action_authorized"))
    can_auto_deliver = automation_ready and external_authorized and approved_auto_delivery
    missing: list[str] = []
    if not automation_ready:
        missing.append("connector_automation_not_verified")
    if not external_authorized:
        missing.append("external_action_not_authorized")
    if not approved_auto_delivery:
        missing.append("owner_auto_delivery_confirmation_missing")
    now = _utc_now()
    task_scope_lines = _task_scope_prompt_lines(
        root, project_id, task_id, safe_message
    )
    digest = hashlib.sha256(
        json.dumps(
            {
                "provider_id": provider["id"],
                "project_id": project_id,
                "task_id": task_id,
                "message": safe_message,
                "requested_action": requested_action,
                "created_at": now,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    handoff_id = f"non-api-ai-{digest[:16]}"
    handoff = {
        "id": handoff_id,
        "created_at": now,
        "provider_id": provider["id"],
        "provider_name": provider["name"],
        "bridge_type": provider["bridge_type"],
        "delivery_modes": provider["delivery_modes"],
        "requested_action": requested_action,
        "project_id": project_id,
        "task_id": task_id,
        "task_context_available": bool(task_scope_lines),
        "task_context_lines": task_scope_lines,
        "message": safe_message,
        "redaction_count": redaction_count,
        "project_hint": provider.get("project_hint") or "",
        "target": {
            "url": str(provider.get("url") or ""),
            "local_app_path": str(provider.get("local_app_path") or ""),
            "cli_command": str(provider.get("cli_command") or ""),
        },
        "status": "ready_for_verified_automation_delivery" if can_auto_deliver else "owner_review_required",
        "can_auto_deliver": can_auto_deliver,
        "external_action_performed": False,
        "external_action_authorized": external_authorized,
        "automation_verified": automation_ready,
        "missing": missing,
        "receipt_policy": "must_record_thread_url_or_window_title_response_hash_and_error_feedback_after_delivery",
        "return_contract": {
            "endpoint": "/api/v1/non-api-ai-bridge/results",
            "required_fields": ["handoff_id", "result_text or error_text", "source_receipt"],
            "default_review_status": "needs_owner_review",
            "fact_status": "unverified_external_ai_output",
            "memory_write": "blocked_until_owner_approval",
        },
        "prompt_packet": (
            f"来源：T-one 无 API AI Bridge\n"
            f"目标 AI：{provider['name']}\n"
            f"对话范围：只限当前项目、任务和店铺，不与其他任务混用。\n\n"
            + (
                "\n".join(task_scope_lines)
                if task_scope_lines
                else f"项目：{project_id or '未指定'}\n任务：{task_id or '未指定'}"
            )
            + f"\n\n用户本轮请求：\n{safe_message}"
        ),
    }
    outbox = root / OUTBOX_DIR
    outbox.mkdir(parents=True, exist_ok=True)
    handoff_path = outbox / f"{handoff_id}.json"
    handoff["handoff_path"] = handoff_path.relative_to(root).as_posix()
    handoff_path.write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (root / LEDGER_PATH).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({k: handoff[k] for k in ("id", "created_at", "provider_id", "status", "missing")}, ensure_ascii=False) + "\n")
    return {"ok": True, "handoff": handoff}


def evaluate_non_api_ai_delivery(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Persist a delivery preflight without opening or controlling an external AI.

    This function intentionally performs no connector action.  It gives the UI
    and a future reviewed connector a durable, restart-safe explanation of why
    delivery is blocked or which separately implemented connector may proceed.
    """

    handoff_path, handoff = _load_handoff(root, str(payload.get("handoff_id") or ""))
    provider = _find_provider(root, str(handoff.get("provider_id") or ""))
    owner_session_authorized = bool(payload.get("owner_session_authorized") is True)
    blockers: list[str] = []
    if not provider.get("automation_verified"):
        blockers.append("connector_automation_not_verified")
    if not provider.get("external_action_authorized"):
        blockers.append("external_action_not_authorized")
    if not owner_session_authorized:
        blockers.append("owner_session_authorization_missing")
    if not provider.get("connector_implementation_verified"):
        blockers.append("verified_connector_execution_not_implemented")
    status = "blocked_owner_input" if blockers else "ready_for_separate_connector_execution"
    now = _utc_now()
    digest = hashlib.sha256(
        json.dumps(
            {
                "handoff_id": handoff["id"],
                "provider_id": provider["id"],
                "owner_session_authorized": owner_session_authorized,
                "blockers": blockers,
                "evaluated_at": now,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    attempt = {
        "id": f"delivery-preflight-{digest[:16]}",
        "event": "delivery_preflight",
        "evaluated_at": now,
        "handoff_id": handoff["id"],
        "provider_id": provider["id"],
        "status": status,
        "blockers": blockers,
        "owner_session_authorized": owner_session_authorized,
        "external_action_performed": False,
        "external_action_count": 0,
    }
    ledger_path = root / DELIVERY_ATTEMPT_LEDGER_PATH
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(attempt, ensure_ascii=False) + "\n")
    handoff["latest_delivery_preflight"] = {
        key: attempt[key]
        for key in (
            "id",
            "evaluated_at",
            "status",
            "blockers",
            "external_action_performed",
        )
    }
    if blockers:
        handoff["status"] = "delivery_blocked_owner_input"
    handoff_path.write_text(
        json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "ok": not blockers,
        **attempt,
        "message": (
            "发送前检查未通过；未打开、粘贴或发送到任何外部 AI。"
            if blockers
            else "发送前检查通过；仍须由单独且已验收的连接器执行。"
        ),
    }


def record_non_api_ai_result(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    handoff_path, handoff = _load_handoff(root, str(payload.get("handoff_id") or ""))
    raw_result_text = str(
        payload.get("result_text")
        or payload.get("response_text")
        or payload.get("output_text")
        or ""
    ).strip()
    raw_error_text = str(payload.get("error_text") or payload.get("error") or "").strip()
    if not raw_result_text and not raw_error_text:
        raise ValueError("请提供外部 AI 的返回内容或错误信息。")
    result_text, result_redactions = redact_sensitive_text(raw_result_text)
    error_text, error_redactions = redact_sensitive_text(raw_error_text)
    source_receipt = payload.get("source_receipt") if isinstance(payload.get("source_receipt"), dict) else {}
    receipt = {
        "external_thread_url": str(
            source_receipt.get("external_thread_url")
            or payload.get("external_thread_url")
            or ""
        ).strip(),
        "window_title": str(
            source_receipt.get("window_title")
            or payload.get("window_title")
            or ""
        ).strip(),
        "command": str(source_receipt.get("command") or payload.get("command") or "").strip(),
        "exit_code": source_receipt.get("exit_code", payload.get("exit_code")),
        "response_hash": str(
            source_receipt.get("response_hash")
            or payload.get("response_hash")
            or hashlib.sha256((result_text or error_text).encode("utf-8")).hexdigest()
        ),
        "captured_by": str(source_receipt.get("captured_by") or payload.get("captured_by") or "manual_or_verified_connector"),
        "evidence_path": str(
            source_receipt.get("evidence_path")
            or payload.get("evidence_path")
            or ""
        ).strip(),
        "delivery_method": str(
            source_receipt.get("delivery_method")
            or payload.get("delivery_method")
            or ""
        ).strip(),
        "browser_session_mode": str(
            source_receipt.get("browser_session_mode")
            or payload.get("browser_session_mode")
            or ""
        ).strip(),
        "attachment_paths": _listify(
            source_receipt.get("attachment_paths")
            or payload.get("attachment_paths")
        ),
    }
    status = str(payload.get("status") or ("failed" if error_text else "received")).strip()
    now = _utc_now()
    digest = hashlib.sha256(
        json.dumps(
            {
                "handoff_id": handoff["id"],
                "provider_id": handoff.get("provider_id"),
                "result_text": result_text,
                "error_text": error_text,
                "received_at": now,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    result_id = f"{handoff['id']}-result-{digest[:10]}"
    result_path = root / RESULT_DIR / f"{result_id}.json"
    result = {
        "id": result_id,
        "handoff_id": handoff["id"],
        "received_at": now,
        "provider_id": str(handoff.get("provider_id") or ""),
        "provider_name": str(handoff.get("provider_name") or ""),
        "project_id": str(handoff.get("project_id") or ""),
        "task_id": str(handoff.get("task_id") or ""),
        "status": status,
        "result_text": result_text,
        "error_text": error_text,
        "redaction_count": result_redactions + error_redactions,
        "result_hash": hashlib.sha256((result_text or error_text).encode("utf-8")).hexdigest(),
        "source_receipt": receipt,
        "fact_status": "unverified_external_ai_output",
        "review_status": "needs_owner_review",
        "memory_write_status": "blocked_until_owner_approval",
        "external_action_performed": bool(payload.get("external_action_performed") is True),
        "result_path": result_path.relative_to(root).as_posix(),
    }
    project_id = str(result.get("project_id") or "").strip().lower()
    project_folder = root / "projects" / project_id
    if SAFE_PROVIDER_ID.fullmatch(project_id) and project_folder.is_dir():
        local_id = f"browser-ai-{result['provider_id']}-{digest[:12]}"
        project_result_path = project_folder / "results" / f"{local_id}.json"
        project_receipt_path = project_folder / "receipts" / f"{local_id}.json"
        result["project_result_path"] = project_result_path.relative_to(root).as_posix()
        result["project_receipt_path"] = project_receipt_path.relative_to(root).as_posix()
        project_result_path.parent.mkdir(parents=True, exist_ok=True)
        project_receipt_path.parent.mkdir(parents=True, exist_ok=True)
        project_result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        project_receipt_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "run_id": local_id,
                    "provider_id": result["provider_id"],
                    "project_id": project_id,
                    "task_id": result["task_id"],
                    "handoff_id": handoff["id"],
                    "received_at": now,
                    "status": status,
                    "result_path": result["project_result_path"],
                    "bridge_result_path": result["result_path"],
                    "source_receipt": receipt,
                    "external_ai_call_count": 1,
                    "external_store_action_count": 0,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    handoff["latest_result"] = {
        "id": result_id,
        "received_at": now,
        "status": status,
        "review_status": result["review_status"],
        "result_path": result["result_path"],
    }
    handoff["status"] = "result_received_needs_owner_review"
    handoff_path.write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    record = IntakeRecord(
        record_type="external_ai_result",
        source=f"non_api_ai_bridge:{result['provider_id']}",
        raw_text=result_text or error_text,
        fields={
            "handoff_id": handoff["id"],
            "result_id": result_id,
            "provider_id": result["provider_id"],
            "provider_name": result["provider_name"],
            "project_id": result["project_id"],
            "task_id": result["task_id"],
            "status": status,
            "fact_status": result["fact_status"],
            "memory_write_status": result["memory_write_status"],
            "result_path": result["result_path"],
            "source_receipt": receipt,
        },
        review_status="needs_owner_review",
        confidence=0.2,
        metadata={
            "handoff_path": handoff_path.relative_to(root).as_posix(),
            "external_action_performed": result["external_action_performed"],
        },
    )
    append_record(root, record)
    with (root / LEDGER_PATH).open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "id": result_id,
                    "event": "result_received",
                    "handoff_id": handoff["id"],
                    "received_at": now,
                    "provider_id": result["provider_id"],
                    "status": status,
                    "review_status": result["review_status"],
                    "result_path": result["result_path"],
                    "record_id": record.record_id,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    return {
        "ok": True,
        "result": result,
        "record": record.to_dict(),
        "message": "外部 AI 结果已回传并进入负责人复核；未写成事实、未进入自动记忆。",
    }


def review_non_api_ai_result(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    result_path, result = _load_result(root, str(payload.get("result_id") or ""))
    decision = str(payload.get("decision") or "").strip()
    if decision not in {"approve_for_task_use", "reject"}:
        raise ValueError("负责人复核只能选择 approve_for_task_use 或 reject。")
    reviewer = str(payload.get("reviewer") or "").strip().lower()
    if reviewer not in {"owner", "responsible_owner"}:
        raise ValueError("外部 AI 返回内容必须由负责人明确复核。")
    reviewed_at = _utc_now()
    review_status = "approved_for_task_use" if decision == "approve_for_task_use" else "rejected"
    result["review_status"] = review_status
    result["reviewed_at"] = reviewed_at
    result["reviewed_by"] = reviewer
    result["review_note"] = str(payload.get("note") or "").strip()
    result["fact_status"] = "unverified_external_ai_output"
    result["memory_write_status"] = (
        "blocked_until_separate_admission"
        if decision == "approve_for_task_use"
        else "blocked_rejected"
    )
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    handoff_path, handoff = _load_handoff(root, str(result.get("handoff_id") or ""))
    latest_result = (
        handoff.get("latest_result")
        if isinstance(handoff.get("latest_result"), dict)
        else {}
    )
    if str(latest_result.get("id") or "") == result["id"]:
        latest_result["review_status"] = review_status
        latest_result["reviewed_at"] = reviewed_at
        handoff["latest_result"] = latest_result
    handoff["status"] = f"result_{review_status}"
    handoff_path.write_text(
        json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    review_event = {
        "event": "result_reviewed",
        "reviewed_at": reviewed_at,
        "handoff_id": handoff["id"],
        "result_id": result["id"],
        "provider_id": result.get("provider_id") or "",
        "decision": decision,
        "review_status": review_status,
        "reviewed_by": reviewer,
        "fact_status": result["fact_status"],
        "memory_write_status": result["memory_write_status"],
        "external_action_performed": False,
    }
    review_ledger = root / REVIEW_LEDGER_PATH
    review_ledger.parent.mkdir(parents=True, exist_ok=True)
    with review_ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(review_event, ensure_ascii=False) + "\n")
    append_record(
        root,
        IntakeRecord(
            record_type="external_ai_result_review",
            source=f"non_api_ai_bridge:{result.get('provider_id') or ''}",
            raw_text=result.get("review_note") or decision,
            fields=review_event,
            review_status=review_status,
            confidence=1.0,
            metadata={
                "result_path": result_path.relative_to(root).as_posix(),
                "handoff_path": handoff_path.relative_to(root).as_posix(),
            },
        ),
    )
    return {
        "ok": True,
        "result": result,
        "review": review_event,
        "message": "复核已写回；仅允许任务内参考，仍未晋升为事实或长期记忆。",
    }


def non_api_ai_bridge_recovery_snapshot(root: Path) -> dict[str, Any]:
    """Rebuild local bridge lifecycle state from durable files after restart."""

    outbox = root / OUTBOX_DIR
    result_dir = root / RESULT_DIR
    handoffs: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    malformed_files: list[str] = []
    relationship_errors: list[str] = []
    orphan_results: list[str] = []

    for path in sorted(outbox.glob("non-api-ai-*.json")) if outbox.exists() else []:
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            malformed_files.append(path.relative_to(root).as_posix())
            continue
        handoff_id = str(payload.get("id") or "") if isinstance(payload, dict) else ""
        if not SAFE_HANDOFF_ID.fullmatch(handoff_id) or path.stem != handoff_id:
            malformed_files.append(path.relative_to(root).as_posix())
            continue
        handoffs[handoff_id] = payload

    for path in sorted(result_dir.glob("*.json")) if result_dir.exists() else []:
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            malformed_files.append(path.relative_to(root).as_posix())
            continue
        if not isinstance(payload, dict):
            malformed_files.append(path.relative_to(root).as_posix())
            continue
        result_id = str(payload.get("id") or "")
        handoff_id = str(payload.get("handoff_id") or "")
        results.append(payload)
        if handoff_id not in handoffs:
            orphan_results.append(result_id or path.name)
            continue
        handoff = handoffs[handoff_id]
        if str(payload.get("provider_id") or "") != str(handoff.get("provider_id") or ""):
            relationship_errors.append(result_id or path.name)

    delivery_events: list[dict[str, Any]] = []
    delivery_ledger = root / DELIVERY_ATTEMPT_LEDGER_PATH
    if delivery_ledger.exists():
        for line_number, line in enumerate(
            delivery_ledger.read_text(encoding="utf-8-sig").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                malformed_files.append(
                    f"{delivery_ledger.relative_to(root).as_posix()}:{line_number}"
                )
                continue
            if isinstance(event, dict):
                delivery_events.append(event)

    external_action_count = sum(
        1 for item in results if item.get("external_action_performed") is True
    ) + sum(
        int(item.get("external_action_count") or 0) for item in delivery_events
    )
    relationship_error_count = len(relationship_errors)
    orphan_result_count = len(orphan_results)
    malformed_file_count = len(malformed_files)
    integrity_ok = not (
        relationship_error_count or orphan_result_count or malformed_file_count
    )
    return {
        "ok": integrity_ok,
        "restart_recovery_verified": integrity_ok and bool(handoffs),
        "handoff_count": len(handoffs),
        "result_count": len(results),
        "pending_owner_review_count": sum(
            1 for item in results if item.get("review_status") == "needs_owner_review"
        ),
        "approved_for_task_use_count": sum(
            1 for item in results if item.get("review_status") == "approved_for_task_use"
        ),
        "delivery_preflight_count": len(delivery_events),
        "blocked_delivery_preflight_count": sum(
            1 for item in delivery_events if item.get("status") == "blocked_owner_input"
        ),
        "orphan_result_count": orphan_result_count,
        "relationship_error_count": relationship_error_count,
        "malformed_file_count": malformed_file_count,
        "external_action_count": external_action_count,
        "latest_handoffs": sorted(
            handoffs.values(), key=lambda item: str(item.get("created_at") or ""), reverse=True
        )[:5],
        "errors": {
            "orphan_results": orphan_results,
            "relationship_errors": relationship_errors,
            "malformed_files": malformed_files,
        },
    }
