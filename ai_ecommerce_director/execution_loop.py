from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .cloud_execution import (
    action_route_key,
    activity_plan_from_action,
    append_cloud_execution_task,
    load_cloud_execution_tasks,
    route_parts_from_key,
    sanitize_action_for_cloud,
)
from .storage import append_record, read_records, update_record
from .store_metrics import summarize_store_metrics
from .types import IntakeRecord


ACTION_QUEUE_PREFIX = "action_queue_"
CLOUD_EXECUTION_RUNNABLE_STATUSES = {"waiting_owner_manual_execution"}
CLOUD_EXECUTION_WAITING_MANUAL_STATUSES = {"waiting_owner_manual_execution", "waiting_cloud_executor"}
CLOUD_EXECUTION_BLOCKED_STATUSES = {"waiting_ads_account", "waiting_platform_store", "waiting_read_source"}
CLOUD_EXECUTION_COMPLETED_STATUSES = {
    "execution_result_recorded",
    "manual_executed",
    "executed_recorded",
    "rejected",
    "skipped",
    "cancelled",
}


@dataclass(slots=True)
class ApprovalCenterPayload:
    queue_path: Path | None
    actions: list[dict[str, Any]]
    pending: list[dict[str, Any]]
    approved: list[dict[str, Any]]
    rejected: list[dict[str, Any]]
    skipped: list[dict[str, Any]]
    executed: list[dict[str, Any]]
    results: list[IntakeRecord]
    memories: list[IntakeRecord]
    cloud_tasks: list[IntakeRecord]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "queuePath": str(self.queue_path) if self.queue_path else "",
            "actions": self.actions,
            "pending": self.pending,
            "approved": self.approved,
            "rejected": self.rejected,
            "skipped": self.skipped,
            "executed": self.executed,
            "results": [record.to_dict() for record in self.results],
            "memories": [record.to_dict() for record in self.memories],
            "cloudTasks": [record.to_dict() for record in self.cloud_tasks],
            "summary": self.summary,
        }


def build_approval_center(root: Path) -> ApprovalCenterPayload:
    queue_path = latest_action_queue_path(root)
    actions = load_action_queue_file(queue_path) if queue_path else []
    pending = [
        item
        for item in actions
        if action_state(item) in {"pending_confirmation", "approved_pending_manual_execution", "execution_needs_evidence"}
    ]
    approved = [item for item in actions if action_state(item) == "approved_pending_manual_execution"]
    rejected = [item for item in actions if action_state(item) == "rejected"]
    skipped = [item for item in actions if action_state(item) == "skipped"]
    executed = [item for item in actions if action_state(item) in {"manual_executed", "executed_recorded"}]
    results = sorted(read_records(root, "execution_result"), key=lambda record: record.created_at, reverse=True)
    raw_cloud_tasks = load_cloud_execution_tasks(root)
    actions_by_id = {str(item.get("action_id") or ""): item for item in actions if item.get("action_id")}
    cloud_tasks = [
        record
        for record in raw_cloud_tasks
        if cloud_task_matches_active_action(record, actions_by_id)
    ]
    memories = sorted(
        [
            record
            for record in read_records(root, "strategy_memory")
            if str(record.fields.get("memory_type") or "").lower() in {"execution_learning", "action_result", "closed_loop"}
        ],
        key=lambda record: record.created_at,
        reverse=True,
    )
    summary = {
        "queue_count": len(actions),
        "pending_count": len(pending),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "skipped_count": len(skipped),
        "closed_without_execution_count": len(rejected) + len(skipped),
        "executed_count": len(executed),
        "result_count": len(results),
        "memory_count": len(memories),
        "cloud_task_count": len(cloud_tasks),
        "cloud_waiting_count": len(
            [record for record in cloud_tasks if str(record.fields.get("status") or "") in CLOUD_EXECUTION_WAITING_MANUAL_STATUSES]
        ),
        "execution_needs_evidence_count": len([item for item in actions if action_state(item) == "execution_needs_evidence"])
        + len([record for record in cloud_tasks if str(record.fields.get("status") or "") == "execution_needs_evidence"]),
        "evidence_complete_count": len([record for record in results if bool(record.fields.get("execution_evidence_complete"))]),
        "queue_date": queue_path.stem.replace(ACTION_QUEUE_PREFIX, "") if queue_path else "",
    }
    return ApprovalCenterPayload(queue_path, actions, pending, approved, rejected, skipped, executed, results, memories, cloud_tasks, summary)


def cloud_task_matches_active_action(record: IntakeRecord, actions_by_id: dict[str, dict[str, Any]]) -> bool:
    """Keep current task packages visible, but hide stale waiting packages from closed drafts."""
    fields = record.fields
    status = str(fields.get("status") or "").strip()
    source_action_id = str(
        fields.get("source_action_id")
        or fields.get("approval_action_id")
        or fields.get("task_action_id")
        or fields.get("action_id")
        or ""
    ).strip()
    if not source_action_id:
        return status not in CLOUD_EXECUTION_WAITING_MANUAL_STATUSES
    action = actions_by_id.get(source_action_id)
    if not action:
        return status not in CLOUD_EXECUTION_WAITING_MANUAL_STATUSES
    state = action_state(action)
    if state in {"rejected", "skipped"}:
        return False
    return True


def approval_payload_action_ids(payload: dict[str, Any]) -> list[str]:
    raw_ids = payload.get("action_ids")
    if raw_ids is None:
        raw_ids = payload.get("action_refs")
    ids: list[str] = []
    if isinstance(raw_ids, list):
        ids.extend(str(item).strip() for item in raw_ids)
    elif isinstance(raw_ids, str):
        ids.extend(part.strip() for part in raw_ids.split(","))
    action_id = str(payload.get("action_id") or "").strip()
    if action_id:
        ids.append(action_id)
    return list(dict.fromkeys(item for item in ids if item))


def expected_statuses_from_payload(payload: dict[str, Any]) -> set[str]:
    raw = payload.get("expected_statuses")
    if raw is None:
        raw = payload.get("expected_status")
    statuses: list[str] = []
    if isinstance(raw, list):
        statuses.extend(str(item).strip() for item in raw)
    elif isinstance(raw, str):
        statuses.extend(part.strip() for part in raw.split(","))
    return {status for status in statuses if status}


def ensure_action_status_is_current(action: dict[str, Any], expected_statuses: set[str], action_id: str) -> None:
    if not expected_statuses:
        return
    state = action_state(action)
    if state not in expected_statuses:
        raise ValueError(f"Action queue changed; refresh before deciding: {action_id}:{state}")


def apply_approval_decision(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    action_ids = approval_payload_action_ids(payload)
    action_id = action_ids[0] if action_ids else ""
    decision = str(payload.get("decision") or "").strip()
    note = str(payload.get("note") or "").strip()
    if not action_id:
        raise ValueError("Missing action_id.")
    if decision not in {"approve", "reject", "mark_executed", "skip"}:
        raise ValueError("Unsupported decision.")
    expected_statuses = expected_statuses_from_payload(payload)
    if len(action_ids) > 1:
        if decision == "mark_executed":
            raise ValueError("Execution result can only be recorded for one action at a time.")
        queue_path = latest_action_queue_path(root)
        if not queue_path:
            raise ValueError("No action queue found. Run auto mode first.")
        actions = load_action_queue_file(queue_path)
        actions_by_id = {str(item.get("action_id") or ""): item for item in actions if item.get("action_id")}
        missing = [item for item in action_ids if item not in actions_by_id]
        if missing:
            raise ValueError("Action not found: " + ", ".join(missing))
        for item in action_ids:
            ensure_action_status_is_current(actions_by_id[item], expected_statuses, item)
        results = []
        for item in action_ids:
            child_payload = dict(payload)
            child_payload.pop("action_ids", None)
            child_payload.pop("action_refs", None)
            child_payload["action_id"] = item
            results.append(apply_approval_decision(root, child_payload))
        first = results[0]
        first["actions"] = [result["action"] for result in results]
        first["results"] = [result.get("result") for result in results if result.get("result")]
        first["memories"] = [result.get("memory") for result in results if result.get("memory")]
        first["cloud_tasks"] = [result.get("cloud_task") for result in results if result.get("cloud_task")]
        first["batch_count"] = len(results)
        first["summary"] = build_approval_center(root).summary
        feedback = dict(first.get("decision_feedback") or {})
        if feedback:
            feedback["message"] = f"{feedback.get('message') or ''} Batch recorded {len(results)} grouped actions.".strip()
            first["decision_feedback"] = feedback
        return first

    queue_path = latest_action_queue_path(root)
    if not queue_path:
        raise ValueError("No action queue found. Run auto mode first.")
    actions = load_action_queue_file(queue_path)
    action = find_action(actions, action_id)
    if not action:
        raise ValueError(f"Action not found: {action_id}")
    ensure_action_status_is_current(action, expected_statuses, action_id)

    now = datetime.now(timezone.utc).isoformat()
    safe_note = redact_sensitive_text(note, limit=500)
    action.setdefault("approval_history", [])
    history_item = {"decision": decision, "note": safe_note, "at": now}
    action["approval_history"].append(history_item)
    action["last_reviewed_at"] = now
    action["review_note"] = safe_note

    result_record: IntakeRecord | None = None
    memory_record: IntakeRecord | None = None
    result_task: IntakeRecord | None = None
    if decision == "approve":
        action["status"] = "approved_pending_manual_execution"
        action["requires_confirmation"] = True
        action["approval_note"] = safe_note
        action["next_step"] = "Human manually executes this in the protected store/platform, then records the result here."
        result_task = append_cloud_execution_task(root, action, approved_at=now, approval_note=safe_note)
    elif decision == "reject":
        action["status"] = "rejected"
        action["requires_confirmation"] = False
        action["rejection_note"] = safe_note
        memory_record = append_decision_memory(root, action, decision, safe_note)
    elif decision == "skip":
        action["status"] = "skipped"
        action["requires_confirmation"] = False
        action["skip_note"] = safe_note
        memory_record = append_decision_memory(root, action, decision, safe_note)
    elif decision == "mark_executed":
        current_state = action_state(action)
        if current_state not in {"approved_pending_manual_execution", "execution_needs_evidence"}:
            raise ValueError(
                "请先确认草稿：该动作还没批准，不能标记为已执行。"
                "请先在「待确认动作」里批准（approve），人工执行后再回来记录结果。"
                " (Execution result can only be recorded after the action is approved or waiting for evidence.)"
            )
        executed_at = str(payload.get("executed_at_utc") or now).strip() or now
        action["executed_at"] = executed_at
        action["execution_note"] = safe_note
        result_record = append_execution_result(root, action, payload, note, executed_at)
        action.update(action_execution_evidence_fields(result_record.fields))
        if bool(result_record.fields.get("execution_evidence_complete")):
            action["status"] = "manual_executed"
            action["requires_confirmation"] = False
        else:
            action["status"] = "execution_needs_evidence"
            action["requires_confirmation"] = True
            action["next_step"] = "Execution was reported, but evidence/writeback/rollback fields are incomplete. Add missing proof before closing this action."
        memory_record = append_execution_memory(root, action, result_record)

    write_action_queue_file(queue_path, actions)
    task_run_sync: dict[str, Any] | None = None
    task_run_id = str(action.get("task_run_id") or "").strip()
    if task_run_id:
        from .task_execution_runtime import record_task_approval_decision

        task_run_sync = record_task_approval_decision(
            root,
            task_run_id,
            action,
            decision,
            note=safe_note,
        )
    response = {
        "action": action,
        "queuePath": str(queue_path),
        "result": result_record.to_dict() if result_record else None,
        "memory": memory_record.to_dict() if memory_record else None,
        "cloud_task": result_task.to_dict() if decision == "approve" and result_task else None,
        "task_run": task_run_sync,
        "summary": build_approval_center(root).summary,
    }
    response["decision_feedback"] = approval_decision_feedback(decision, action, result_record, result_task)
    if decision == "mark_executed":
        cloud_task = find_cloud_execution_task(
            root,
            task_id=str(action.get("cloud_execution_task_id") or payload.get("cloud_execution_task_id") or ""),
            action_id=action_id,
        )
        if cloud_task:
            updated_task = update_cloud_execution_task_from_result(root, cloud_task, response)
            response["cloud_task"] = updated_task.to_dict()
            response["summary"] = build_approval_center(root).summary
    return response


def record_cloud_execution_result(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    task_id = str(payload.get("task_queue_id") or payload.get("cloud_execution_task_id") or "").strip()
    requested_action_id = str(payload.get("action_id") or payload.get("source_action_id") or "").strip()
    cloud_task = find_cloud_execution_task(root, task_id=task_id, action_id=requested_action_id)
    if not cloud_task:
        raise ValueError("Cloud execution task not found.")
    task_action_id = str(cloud_task.fields.get("source_action_id") or "").strip()
    if requested_action_id and task_action_id and requested_action_id != task_action_id:
        raise ValueError("Cloud task does not match the supplied action_id.")
    action_id = task_action_id or requested_action_id
    if not action_id:
        raise ValueError("Cloud execution task is missing source_action_id.")

    defaults = cloud_result_defaults_from_task(cloud_task)
    note = first_present(
        payload.get("note"),
        payload.get("cloud_execution_log_summary"),
        payload.get("cloud_execution_log"),
        "Cloud executor wrote back execution evidence.",
    )
    result_payload = {
        **defaults,
        **payload,
        "action_id": action_id,
        "decision": "mark_executed",
        "note": note,
        "result_source": "cloud_executor_callback",
    }
    result = apply_approval_decision(root, result_payload)
    updated_task = update_cloud_execution_task_from_result(root, cloud_task, result)
    result["cloud_task"] = updated_task.to_dict()
    result["summary"] = build_approval_center(root).summary
    return result


def find_cloud_execution_task(root: Path, *, task_id: str = "", action_id: str = "") -> IntakeRecord | None:
    for record in load_cloud_execution_tasks(root):
        fields = record.fields
        if task_id and str(fields.get("task_queue_id") or "") == task_id:
            return record
        if action_id and str(fields.get("source_action_id") or "") == action_id:
            return record
    return None


def list_cloud_execution_task_packages(root: Path, filters: dict[str, Any]) -> dict[str, Any]:
    route_key = task_filter_value(filters.get("route_key"))
    identity_ref = task_filter_value(filters.get("execution_identity_ref") or filters.get("identity_ref"))
    store_identity_fingerprint = task_filter_value(filters.get("store_identity_fingerprint"))
    ads_identity_fingerprint = task_filter_value(filters.get("ads_identity_fingerprint"))
    task_package_type = task_filter_value(filters.get("task_package_type") or filters.get("package_type"))
    task_id = task_filter_value(filters.get("task_queue_id") or filters.get("cloud_execution_task_id"))
    include_blocked = task_filter_bool(filters.get("include_blocked"))
    include_completed = task_filter_bool(filters.get("include_completed"))
    include_machine_fields = task_filter_bool(filters.get("include_machine_fields"))
    limit = task_filter_limit(filters.get("limit"), default=50, maximum=100)
    if not any([route_key, identity_ref, store_identity_fingerprint, task_id]):
        raise ValueError("Cloud executor task pull needs route_key plus isolated identity, execution_identity_ref, store_identity_fingerprint, or task_queue_id.")
    if route_key and not any([identity_ref, store_identity_fingerprint, task_id]):
        raise ValueError("Cloud executor route pull needs execution_identity_ref or store_identity_fingerprint to prevent same-route store mixing.")

    packages: list[dict[str, Any]] = []
    for record in load_cloud_execution_tasks(root):
        fields = record.fields
        status = str(fields.get("status") or "").strip()
        if task_id and str(fields.get("task_queue_id") or "") != task_id:
            continue
        if route_key and str(fields.get("route_key") or "") != route_key:
            continue
        if identity_ref and str(fields.get("execution_identity_ref") or "") != identity_ref:
            continue
        if store_identity_fingerprint and str(fields.get("store_identity_fingerprint") or "") != store_identity_fingerprint:
            continue
        if ads_identity_fingerprint and str(fields.get("ads_identity_fingerprint") or "") != ads_identity_fingerprint:
            continue
        if task_package_type and str(fields.get("task_package_type") or "") != task_package_type:
            continue
        if (
            str(fields.get("task_package_type") or "") == "ads_backend"
            and not any([task_id, identity_ref, ads_identity_fingerprint])
        ):
            raise ValueError(
                "Ads backend task pull needs execution_identity_ref or ads_identity_fingerprint "
                "to prevent same-store ad account mixing."
            )
        if not include_completed and status in CLOUD_EXECUTION_COMPLETED_STATUSES:
            continue
        if not include_blocked and status not in CLOUD_EXECUTION_RUNNABLE_STATUSES:
            continue
        packages.append(cloud_task_package_for_executor(record, include_machine_fields=include_machine_fields))
        if len(packages) >= limit:
            break

    return {
        "count": len(packages),
        "tasks": packages,
        "filters": {
            "route_key": route_key,
            "execution_identity_ref": identity_ref,
            "store_identity_fingerprint": store_identity_fingerprint,
            "ads_identity_fingerprint": ads_identity_fingerprint,
            "task_package_type": task_package_type,
            "task_queue_id": task_id,
            "include_blocked": include_blocked,
            "include_completed": include_completed,
            "include_machine_fields": include_machine_fields,
            "limit": limit,
        },
    }


def cloud_task_package_for_executor(record: IntakeRecord, *, include_machine_fields: bool = False) -> dict[str, Any]:
    fields = record.fields
    payload = fields.get("payload") if isinstance(fields.get("payload"), dict) else {}
    action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
    approval = payload.get("approval") if isinstance(payload.get("approval"), dict) else {}
    machine_execution_mode = str(payload.get("execution_mode") or fields.get("execution_mode") or "isolated_cloud_plugin_after_confirmation")
    safe_payload = {
        "action": sanitize_action_for_cloud(action),
        "approval": {
            "approved_at": str(approval.get("approved_at") or ""),
            "confirmation_required": bool(approval.get("confirmation_required", True)),
            "external_execution_before_confirmation": bool(approval.get("external_execution_before_confirmation", False)),
        },
        "route": safe_cloud_payload_section(payload.get("route")),
        "execution_scope": safe_cloud_payload_section(payload.get("execution_scope")),
        "execution_identity": safe_cloud_payload_section(payload.get("execution_identity")),
        "execution_mode": customer_safe_execution_mode(machine_execution_mode),
        "allowed_steps": safe_cloud_payload_list(payload.get("allowed_steps")),
        "blocked_boundaries": safe_cloud_payload_list(payload.get("blocked_boundaries")),
        "required_evidence": safe_cloud_payload_list(payload.get("required_evidence")),
        "evidence_contract": safe_cloud_payload_section(payload.get("evidence_contract")),
        "activity_execution_requirements": safe_cloud_payload_section(payload.get("activity_execution_requirements")),
        "activity_execution_plan": safe_cloud_payload_section(payload.get("activity_execution_plan")),
        "developer_capability_plan": safe_cloud_payload_section(payload.get("developer_capability_plan")),
    }
    if include_machine_fields:
        safe_payload["machine_execution_mode"] = machine_execution_mode
    return {
        "record_id": record.record_id,
        "created_at": record.created_at,
        "task_queue_id": str(fields.get("task_queue_id") or ""),
        "task_type": str(fields.get("task_type") or ""),
        "task_package_type": str(fields.get("task_package_type") or ""),
        "task_package_label": str(fields.get("task_package_label") or ""),
        "target_agent_id": str(fields.get("target_agent_id") or ""),
        "source_action_id": str(fields.get("source_action_id") or ""),
        "route_key": str(fields.get("route_key") or ""),
        "execution_identity_ref": str(fields.get("execution_identity_ref") or ""),
        "store_identity_fingerprint": str(fields.get("store_identity_fingerprint") or ""),
        "ads_identity_fingerprint": str(fields.get("ads_identity_fingerprint") or ""),
        "status": str(fields.get("status") or ""),
        "execution_readiness": str(fields.get("execution_readiness") or ""),
        "execution_readiness_label": str(fields.get("execution_readiness_label") or ""),
        "execution_mode": customer_safe_execution_mode(machine_execution_mode),
        "missing_prerequisites": safe_cloud_payload_list(fields.get("missing_prerequisites")),
        "priority": fields.get("priority") or 0,
        "not_before_utc": str(fields.get("not_before_utc") or ""),
        "platform": str(fields.get("platform") or ""),
        "country": str(fields.get("country") or ""),
        "store_name": str(fields.get("store_name") or ""),
        "payload": safe_payload,
    }


def customer_safe_execution_mode(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "后台待执行包，确认后才处理，提交前停住"
    lowered = raw.lower()
    if "isolated_cloud_plugin" in lowered or "cloud_plugin" in lowered:
        return "后台待执行包，确认后才处理，提交前停住"
    if "draft_then_confirmation" in lowered:
        return "先生成草稿，再由负责人确认"
    if "manual_recorded" in lowered:
        return "负责人已手动执行并回写结果"
    return redact_sensitive_text(raw, limit=120)


def safe_cloud_payload_section(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    blocked_fragments = {"password", "credential", "secret", "token", "cookie", "api_key", "key_env", "email", "phone", "legal"}
    safe: dict[str, Any] = {}
    for key, item in list(value.items())[:40]:
        key_text = str(key)
        if any(fragment in key_text.lower() for fragment in blocked_fragments):
            continue
        safe[key_text] = redact_result_value(item)
    return safe


def safe_cloud_payload_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [redact_sensitive_text(item, limit=180) for item in value[:30]]


def task_filter_value(value: Any) -> str:
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "").strip()


def task_filter_bool(value: Any) -> bool:
    if isinstance(value, list):
        value = value[0] if value else ""
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def task_filter_limit(value: Any, *, default: int, maximum: int) -> int:
    if isinstance(value, list):
        value = value[0] if value else ""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if parsed <= 0:
        return default
    return min(parsed, maximum)


def cloud_result_defaults_from_task(task: IntakeRecord) -> dict[str, Any]:
    fields = task.fields
    payload = fields.get("payload") if isinstance(fields.get("payload"), dict) else {}
    route = payload.get("route") if isinstance(payload.get("route"), dict) else {}
    evidence_contract = payload.get("evidence_contract") if isinstance(payload.get("evidence_contract"), dict) else {}
    requirements = payload.get("activity_execution_requirements") if isinstance(payload.get("activity_execution_requirements"), dict) else {}
    required_result_fields = []
    if str(fields.get("task_package_type") or "") in {"amazon_10001_owner_review", "amazon_10001_repair_followup"}:
        required_result_fields = (
            evidence_contract.get("required_result_fields")
            or requirements.get("required_result_fields")
            or []
        )
    return {
        "platform": fields.get("platform") or route.get("channel_id") or "",
        "store": fields.get("store_name") or route.get("store_name") or "",
        "country": fields.get("country") or route.get("country_code") or "",
        "task_package_type": fields.get("task_package_type") or "",
        "evidence_contract_required_fields": required_result_fields if isinstance(required_result_fields, list) else [],
    }


def update_cloud_execution_task_from_result(root: Path, task: IntakeRecord, result: dict[str, Any]) -> IntakeRecord:
    result_payload = result.get("result") if isinstance(result.get("result"), dict) else {}
    result_fields = result_payload.get("fields") if isinstance(result_payload.get("fields"), dict) else {}
    feedback = result.get("decision_feedback") if isinstance(result.get("decision_feedback"), dict) else {}
    missing_evidence = feedback.get("missing_evidence") if isinstance(feedback.get("missing_evidence"), list) else []
    now = datetime.now(timezone.utc).isoformat()
    evidence_complete = bool(result_fields.get("execution_evidence_complete"))
    next_step = str(feedback.get("next_step") or "").strip()
    if not next_step:
        if evidence_complete:
            next_step = (
                "\u6267\u884c\u7ed3\u679c\u5df2\u95ed\u73af\uff1a\u622a\u56fe/\u7f16\u53f7\u3001ERP\u56de\u5199\u3001"
                "\u8d1f\u8d23\u4eba\u6700\u7ec8\u786e\u8ba4\u548c\u56de\u6eda\u72b6\u6001\u90fd\u5df2\u8bb0\u5f55\u3002"
            )
        elif missing_evidence:
            next_step = "\u6267\u884c\u8bc1\u636e\u5f85\u8865\uff1a\u8bf7\u8865\u9f50" + "\u3001".join(str(item) for item in missing_evidence[:6])
        else:
            next_step = (
                "\u6267\u884c\u8bc1\u636e\u5f85\u8865\uff1a\u8bf7\u8865\u9f50\u622a\u56fe\u3001ERP\u56de\u5199\u3001"
                "\u8d1f\u8d23\u4eba\u786e\u8ba4\u6216\u56de\u6eda\u72b6\u6001\u540e\u518d\u95ed\u73af\u3002"
            )
    task.fields.update(
        {
            "status": "execution_result_recorded" if evidence_complete else "execution_needs_evidence",
            "result_record_id": result_payload.get("record_id") or "",
            "result_outcome": result_fields.get("outcome") or "",
            "cloud_execution_finished_at": result_fields.get("executed_at") or now,
            "erp_writeback_status": result_fields.get("erp_writeback_status") or "",
            "owner_confirmation_status": result_fields.get("owner_confirmation_status") or "",
            "execution_evidence_complete": evidence_complete,
            "execution_draft_id": result_fields.get("execution_draft_id") or "",
            "before_screenshot_ref": result_fields.get("before_screenshot_ref") or "",
            "after_screenshot_ref": result_fields.get("after_screenshot_ref") or "",
            "rollback_status": result_fields.get("rollback_status") or "",
            "rollback_note": result_fields.get("rollback_note") or "",
            "decision_feedback": feedback,
            "missing_evidence": missing_evidence,
            "customer_next_step": next_step,
            "next_step": next_step,
        }
    )
    notes = list(task.director_notes)
    notes.append("Cloud executor result was written back to the approval center and ERP evidence view.")
    task.director_notes = list(dict.fromkeys(notes))
    task.review_status = "execution_recorded"
    update_record(root, task)
    return task


def latest_action_queue_path(root: Path) -> Path | None:
    output_dir = root / "outputs"
    if not output_dir.exists():
        return None
    today_path = output_dir / f"action_queue_{date.today().isoformat()}.json"
    if today_path.exists():
        return today_path
    paths = sorted(output_dir.glob("action_queue_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return paths[0] if paths else None


def load_action_queue_file(path: Path | None) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def write_action_queue_file(path: Path, actions: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary_path.write_text(
            json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def find_action(actions: list[dict[str, Any]], action_id: str) -> dict[str, Any] | None:
    for action in actions:
        if str(action.get("action_id") or "") == action_id:
            return action
    return None


def action_state(action: dict[str, Any]) -> str:
    return str(action.get("status") or "").strip() or "pending_confirmation"


def append_execution_result(root: Path, action: dict[str, Any], payload: dict[str, Any], note: str, executed_at: str) -> IntakeRecord:
    scope = execution_scope_defaults_from_action(action, payload)
    before = summarize_store_metrics(
        root,
        platform=str(scope.get("platform") or "all"),
        store=str(scope.get("store_name") or "all"),
        country=str(scope.get("country") or "all"),
        grain="day",
    )["summary"]
    after_metrics = parse_after_metrics(payload)
    outcome = classify_outcome(before, after_metrics)
    evidence_fields = parse_execution_evidence(payload)
    fields = {
        "action_id": action.get("action_id"),
        "action_type": action.get("action_type"),
        "action_title": action.get("title"),
        "source_record_id": action.get("source_record_id"),
        "source_package": first_present(payload.get("source_package"), action.get("source_package")),
        "task_package_type": first_present(
            payload.get("task_package_type"),
            action.get("task_package_type"),
            action.get("cloud_task_package_type"),
        ),
        "task_package_label": first_present(
            payload.get("task_package_label"),
            action.get("task_package_label"),
            action.get("cloud_task_package_label"),
        ),
        "record_type": action.get("record_type"),
        "route_key": scope.get("route_key") or "",
        "cloud_route_key": scope.get("route_key") or "",
        "store_id": scope.get("store_name") or "",
        "store_name": scope.get("store_name") or "",
        "platform": scope.get("platform") or "",
        "country": scope.get("country") or "",
        "store_model": scope.get("store_model") or "",
        "execution_identity_ref": scope.get("execution_identity_ref") or "",
        "cloud_execution_task_id": scope.get("cloud_execution_task_id") or "",
        "store_identity_fingerprint": scope.get("store_identity_fingerprint") or "",
        "ads_identity_fingerprint": scope.get("ads_identity_fingerprint") or "",
        "product_id": first_present(payload.get("product_id"), action.get("product_id")),
        "product_name": payload.get("product_name") or "",
        "executed_at": executed_at,
        "execution_mode": "manual_recorded",
        "execution_note": redact_sensitive_text(note, limit=500),
        **evidence_fields,
        "before_revenue": before.get("revenue", 0),
        "before_orders": before.get("orders", 0),
        "before_roas": before.get("roas"),
        **after_metrics,
        "outcome": outcome["outcome"],
        "learning_summary": outcome["summary"],
        "next_rule": outcome["next_rule"],
    }
    record = IntakeRecord(
        record_type="execution_result",
        fields=fields,
        raw_text=json.dumps(
            {
                "action": sanitize_action_for_result(action),
                "note": redact_sensitive_text(note, limit=500),
                "execution_scope": {
                    "route_key": scope.get("route_key") or "",
                    "platform": scope.get("platform") or "",
                    "country": scope.get("country") or "",
                    "store_name": scope.get("store_name") or "",
                    "store_model": scope.get("store_model") or "",
                    "execution_identity_ref": scope.get("execution_identity_ref") or "",
                },
                "after_metrics": after_metrics,
                "execution_evidence": evidence_fields,
            },
            ensure_ascii=False,
        ),
        source="approval_center",
        score={"priority": outcome["priority"], "outcome_score": outcome["score"]},
        director_notes=[outcome["summary"], outcome["next_rule"]],
        review_status="approved",
    )
    append_record(root, record)
    return record


def execution_scope_defaults_from_action(action: dict[str, Any], payload: dict[str, Any]) -> dict[str, str]:
    plan = activity_plan_from_action(action)
    route_key = first_present(
        payload.get("cloud_route_key"),
        payload.get("route_key"),
        action_route_key(action, plan),
        action.get("cloud_route_key"),
        action.get("route_key"),
    )
    route_parts = route_parts_from_key(route_key)
    platform = first_present(
        payload.get("platform"),
        action.get("platform"),
        action.get("platform_id"),
        action.get("marketplace"),
        plan.get("channel_id"),
        route_parts.get("platform"),
    )
    country = first_present(
        payload.get("country"),
        payload.get("country_code"),
        action.get("country"),
        action.get("country_code"),
        plan.get("country_code"),
        route_parts.get("country"),
    ).upper()
    store_name = first_present(
        payload.get("store"),
        payload.get("store_id"),
        payload.get("store_name"),
        action.get("store_name"),
        action.get("store"),
        action.get("store_id"),
        plan.get("store_name"),
    )
    store_model = first_present(
        payload.get("store_model"),
        action.get("store_model"),
        action.get("shop_type"),
        plan.get("store_model"),
        route_parts.get("store_model"),
    )
    return {
        "route_key": route_key,
        "platform": platform,
        "country": country,
        "store_name": store_name,
        "store_model": store_model,
        "execution_identity_ref": first_present(payload.get("execution_identity_ref"), action.get("cloud_execution_identity_ref")),
        "cloud_execution_task_id": first_present(payload.get("cloud_execution_task_id"), action.get("cloud_execution_task_id")),
        "store_identity_fingerprint": first_present(payload.get("store_identity_fingerprint"), action.get("store_identity_fingerprint")),
        "ads_identity_fingerprint": first_present(payload.get("ads_identity_fingerprint"), action.get("ads_identity_fingerprint")),
    }


def task_required_result_fields(payload: dict[str, Any]) -> list[str]:
    contract = payload.get("evidence_contract") if isinstance(payload.get("evidence_contract"), dict) else {}
    candidates = (
        payload.get("evidence_contract_required_fields")
        or payload.get("required_result_fields")
        or contract.get("required_result_fields")
        or []
    )
    if not isinstance(candidates, list):
        return []
    return list(dict.fromkeys(str(item or "").strip() for item in candidates if str(item or "").strip()))


def task_specific_evidence_fields(payload: dict[str, Any], required_fields: list[str]) -> dict[str, Any]:
    blocked = {
        "execution_draft_id",
        "before_screenshot_ref",
        "after_screenshot_ref",
        "cloud_execution_log_summary",
        "erp_writeback_status",
        "erp_writeback_note",
        "owner_confirmation_status",
        "rollback_status",
        "rollback_note",
        "execution_evidence_complete",
        "required_result_fields",
        "evidence_contract_required_fields",
    }
    allowed_prefixes = ("amazon_10001_", "task_package_", "store_page_", "plugin_")
    fields: dict[str, Any] = {}
    for key in required_fields:
        if key in blocked or not key.startswith(allowed_prefixes):
            continue
        raw_value = first_present(payload.get(key), payload.get(f"{key}_ref"), payload.get(f"{key}_path"))
        if "ref" in key or "screenshot" in key:
            fields[key] = sanitize_evidence_ref(raw_value)
        else:
            fields[key] = redact_sensitive_text(raw_value, limit=500)
    return fields


def required_field_value_present(fields: dict[str, Any], key: str) -> bool:
    value = str(fields.get(key) or "").strip()
    if key == "erp_writeback_status":
        return value in {"writeback_success", "已回写ERP", "宸插洖鍐橢RP"}
    if key == "owner_confirmation_status":
        return value in {"confirmed", "负责人已确认", "璐熻矗浜哄凡纭"}
    if key == "rollback_status":
        return value in {
            "not_needed",
            "rollback_ready",
            "rollback_completed",
            "rollback_blocked",
            "不需要回滚",
            "已准备回滚",
            "已完成回滚",
            "已阻断外部提交",
            "涓嶉渶瑕佸洖婊?",
            "宸插噯澶囧洖婊?",
            "宸插畬鎴愬洖婊?",
            "宸查樆鏂閮ㄦ彁浜?",
        }
    return bool(value)

def parse_execution_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    required_fields = task_required_result_fields(payload)
    draft_id = redact_sensitive_text(
        first_present(payload.get("execution_draft_id"), payload.get("draft_id"), payload.get("official_draft_id")),
        limit=120,
    )
    before_screenshot = sanitize_evidence_ref(
        first_present(payload.get("before_screenshot_ref"), payload.get("before_screenshot"), payload.get("before_screenshot_path"))
    )
    after_screenshot = sanitize_evidence_ref(
        first_present(payload.get("after_screenshot_ref"), payload.get("after_screenshot"), payload.get("after_screenshot_path"))
    )
    execution_log = redact_sensitive_text(
        first_present(payload.get("cloud_execution_log_summary"), payload.get("cloud_execution_log"), payload.get("execution_log")),
        limit=800,
    )
    erp_status = normalize_choice(
        payload.get("erp_writeback_status"),
        allowed={
            "not_started": "未回写",
            "draft_saved": "草稿已保存",
            "writeback_ready": "可回写",
            "writeback_success": "已回写ERP",
            "writeback_failed": "回写失败",
            "blocked": "已阻断",
        },
        default="未回写",
    )
    owner_status = normalize_choice(
        payload.get("owner_confirmation_status"),
        allowed={
            "not_confirmed": "负责人未确认",
            "confirmed": "负责人已确认",
            "needs_recheck": "需要复核",
            "rejected": "负责人拒绝",
        },
        default="负责人未确认",
    )
    erp_note = redact_sensitive_text(payload.get("erp_writeback_note"), limit=500)
    rollback_status = normalize_choice(
        payload.get("rollback_status"),
        allowed={
            "not_needed": "不需要回滚",
            "rollback_ready": "已准备回滚",
            "rollback_completed": "已完成回滚",
            "rollback_blocked": "已阻断外部提交",
            "needs_rollback": "需要回滚",
        },
        default="未记录回滚状态",
    )
    rollback_note = redact_sensitive_text(payload.get("rollback_note"), limit=500)
    rollback_ok = rollback_status in {"不需要回滚", "已准备回滚", "已完成回滚", "已阻断外部提交"}
    fields = {
        "execution_draft_id": draft_id,
        "before_screenshot_ref": before_screenshot,
        "after_screenshot_ref": after_screenshot,
        "cloud_execution_log_summary": execution_log,
        "erp_writeback_status": erp_status,
        "erp_writeback_note": erp_note,
        "owner_confirmation_status": owner_status,
        "rollback_status": rollback_status,
        "rollback_note": rollback_note,
        "required_result_fields": required_fields,
    }
    fields.update(task_specific_evidence_fields(payload, required_fields))
    if required_fields:
        evidence_complete = all(required_field_value_present(fields, key) for key in required_fields)
    else:
        evidence_complete = all(
            [
                draft_id,
                before_screenshot,
                after_screenshot,
                execution_log,
                erp_status == "已回写ERP",
                owner_status == "负责人已确认",
                rollback_ok,
            ]
        )
    fields["execution_evidence_complete"] = evidence_complete
    return fields

def action_execution_evidence_fields(fields: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "execution_draft_id",
        "before_screenshot_ref",
        "after_screenshot_ref",
        "cloud_execution_log_summary",
        "erp_writeback_status",
        "erp_writeback_note",
        "owner_confirmation_status",
        "rollback_status",
        "rollback_note",
        "execution_evidence_complete",
        "required_result_fields",
    ]
    result = {key: fields.get(key) for key in keys}
    required_fields = fields.get("required_result_fields") if isinstance(fields.get("required_result_fields"), list) else []
    for key in required_fields:
        if isinstance(key, str) and key.startswith(("amazon_10001_", "task_package_", "store_page_", "plugin_")):
            result[key] = fields.get(key)
    return result


def approval_decision_feedback(
    decision: str,
    action: dict[str, Any],
    result_record: IntakeRecord | None,
    result_task: IntakeRecord | None,
) -> dict[str, Any]:
    status = action_state(action)
    if decision == "approve":
        message = "已生成后台隔离任务包，负责人仍需在官方后台手动执行，系统不会自动提交外部平台。"
        if not result_task:
            message = "已进入待负责人执行；当前动作不需要后台隔离任务包。"
        return {
            "title": "已进入待执行",
            "status_label": "已确认待执行",
            "message": message,
            "next_step": "执行后必须回写截图、ERP状态、负责人最终确认和回滚状态。",
            "missing_evidence": [],
        }
    if decision == "reject":
        return {
            "title": "已拒绝",
            "status_label": "已拒绝",
            "message": "不会执行真实外部动作；系统只保留拒绝原因和学习记录。",
            "next_step": "后台 AI 后续会避开同类风险，继续整理只读证据和草稿。",
            "missing_evidence": [],
        }
    if decision == "skip":
        return {
            "title": "已暂缓",
            "status_label": "已暂缓",
            "message": "当前动作继续保留为草稿和证据，不会执行真实外部动作。",
            "next_step": "补齐规则、店铺数据或负责人意见后再确认。",
            "missing_evidence": [],
        }
    if decision == "mark_executed":
        fields = result_record.fields if result_record else {}
        missing = execution_evidence_missing_labels(fields)
        if status == "manual_executed" and not missing:
            return {
                "title": "执行结果已闭环",
                "status_label": "证据回写完整",
                "message": "截图、ERP回写、负责人最终确认和回滚状态都已记录。",
                "next_step": "后续由后台 AI 复盘效果，不会再次提交平台动作。",
                "missing_evidence": [],
            }
        return {
            "title": "执行证据待补",
            "status_label": "待补执行证据",
            "message": "已记录负责人执行结果，但缺少闭环证据；不会标记完成。",
            "next_step": "请补齐：" + "、".join(missing[:6]) if missing else "请复核执行证据后再闭环。",
            "missing_evidence": missing,
        }
    return {
        "title": "已记录",
        "status_label": status,
        "message": "负责人决定已记录；没有执行真实外部动作。",
        "next_step": "刷新确认中心查看最新状态。",
        "missing_evidence": [],
    }

def execution_evidence_missing_labels(fields: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    required_fields = fields.get("required_result_fields") if isinstance(fields.get("required_result_fields"), list) else []
    if required_fields:
        for key in required_fields:
            key_text = str(key or "").strip()
            if key_text and not required_field_value_present(fields, key_text):
                missing.append(key_text)
        return list(dict.fromkeys(missing))
    checks = [
        ("execution_draft_id", "官方后台草稿/活动编号"),
        ("before_screenshot_ref", "执行前截图"),
        ("after_screenshot_ref", "执行后截图"),
        ("cloud_execution_log_summary", "执行日志摘要"),
    ]
    for key, label in checks:
        if not str(fields.get(key) or "").strip():
            missing.append(label)
    if str(fields.get("erp_writeback_status") or "").strip() != "已回写ERP":
        missing.append("ERP成功回写")
    if str(fields.get("owner_confirmation_status") or "").strip() != "负责人已确认":
        missing.append("负责人最终确认")
    if str(fields.get("rollback_status") or "").strip() not in {"不需要回滚", "已准备回滚", "已完成回滚", "已阻断外部提交"}:
        missing.append("可接受的回滚状态")
    return list(dict.fromkeys(missing))

def sanitize_action_for_result(action: dict[str, Any]) -> dict[str, Any]:
    safe_action = sanitize_action_for_cloud(action)
    return {key: redact_result_value(value) for key, value in safe_action.items()}


def redact_result_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_sensitive_text(value, limit=500)
    if isinstance(value, list):
        return [redact_result_value(item) for item in value[:20]]
    if isinstance(value, dict):
        return {str(key): redact_result_value(item) for key, item in list(value.items())[:30]}
    return value


def sanitize_evidence_ref(value: Any) -> str:
    text = redact_sensitive_text(value, limit=220)
    if not text:
        return ""
    text = text.replace("\\", "/").strip()
    blocked_fragments = ["password", "secret", "token", "cookie", "api_key", "apikey", "credential"]
    if any(fragment in text.lower() for fragment in blocked_fragments):
        return "[已隐藏敏感路径]"
    return text


def redact_sensitive_text(value: Any, *, limit: int = 500) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    replacements = [
        (r"(?i)(password|passwd|pwd)\s*[:=]\s*[^,\s;]+", r"\1=[已隐藏]"),
        (r"(?i)(access[_-]?token|refresh[_-]?token|token|cookie|secret|api[_-]?key|apikey|credential)\s*[:=]\s*[^,\s;]+", r"\1=[已隐藏]"),
        (r"sk-[A-Za-z0-9_\-]{12,}", "sk-[已隐藏]"),
        (r"(?i)Bearer\s+[A-Za-z0-9._\-]+", "Bearer [已隐藏]"),
    ]
    result = text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result)
    result = re.sub(
        r"(?i)isolated_cloud_plugin_after_confirmation",
        "后台待执行包，确认后才处理，提交前停住",
        result,
    )
    result = re.sub(
        r"(?i)draft_then_confirmation_or_isolated_cloud_plugin",
        "先出草稿，再确认；需要后台时走后台待执行包",
        result,
    )
    result = re.sub(r"(?i)api_or_cloud_plugin_after_confirmation", "平台连接或后台任务包草稿；确认后才执行", result)
    result = re.sub(r"(?i)isolated_cloud_plugin(_profile)?", "后台待执行包", result)
    result = result.replace("浜戠闅旂鎻掍欢", "后台待执行包").replace("浜戠鎻掍欢", "后台待执行包")
    return result[:limit]


def normalize_choice(value: Any, *, allowed: dict[str, str], default: str) -> str:
    text = str(value or "").strip()
    if not text:
        return default
    lowered = text.lower()
    if lowered in allowed:
        return allowed[lowered]
    if text in allowed.values():
        return text
    return redact_sensitive_text(text, limit=80) or default


def first_present(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def append_execution_memory(root: Path, action: dict[str, Any], result_record: IntakeRecord) -> IntakeRecord:
    fields = result_record.fields
    memory_key = f"execution:{fields.get('action_id')}:{fields.get('executed_at')}"
    memory = IntakeRecord(
        record_type="strategy_memory",
        fields={
            "memory_key": memory_key,
            "memory_type": "execution_learning",
            "strategy_stage": fields.get("action_type") or "store_action",
            "recommendation": fields.get("learning_summary") or "",
            "valid_when": [
                f"platform={fields.get('platform') or 'all'}",
                f"store={fields.get('store_id') or 'all'}",
                f"action_type={fields.get('action_type') or ''}",
            ],
            "what_not_to_do": ["Do not repeat on protected/old stores without fresh confirmation.", "Do not scale before checking ROAS, refunds, and returns."],
            "source_action_id": fields.get("action_id"),
            "source_execution_result_id": result_record.record_id,
            "rule_summary": fields.get("next_rule") or "",
        },
        raw_text=json.dumps({"action": action, "execution_result": result_record.to_dict()}, ensure_ascii=False),
        source="approval_center",
        score={"priority": 80},
        director_notes=["Execution result was converted into strategy memory."],
        review_status="approved",
    )
    append_record(root, memory)
    return memory


def append_decision_memory(root: Path, action: dict[str, Any], decision: str, note: str) -> IntakeRecord:
    now = datetime.now(timezone.utc).isoformat()
    memory = IntakeRecord(
        record_type="strategy_memory",
        fields={
            "memory_key": f"decision:{action.get('action_id')}:{decision}",
            "memory_type": "closed_loop",
            "strategy_stage": action.get("action_type") or "approval",
            "recommendation": f"{decision}: {action.get('title')}. {note}".strip(),
            "valid_when": [f"action_type={action.get('action_type') or ''}"],
            "what_not_to_do": ["Do not execute rejected or skipped actions automatically."],
            "source_action_id": action.get("action_id"),
            "decided_at": now,
        },
        raw_text=json.dumps({"action": action, "decision": decision, "note": note}, ensure_ascii=False),
        source="approval_center",
        score={"priority": 60},
        director_notes=["Approval decision was saved as strategy memory."],
        review_status="approved",
    )
    append_record(root, memory)
    return memory


def parse_after_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "after_revenue": number(payload.get("after_revenue")),
        "after_orders": int(number(payload.get("after_orders")) or 0),
        "after_ad_spend": number(payload.get("after_ad_spend")),
        "after_refund_amount": number(payload.get("after_refund_amount")),
        "after_return_count": int(number(payload.get("after_return_count")) or 0),
        "after_roas": number(payload.get("after_roas")),
    }


def classify_outcome(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_revenue = float(before.get("revenue") or 0)
    after_revenue = float(after.get("after_revenue") or 0)
    before_orders = float(before.get("orders") or 0)
    after_orders = float(after.get("after_orders") or 0)
    after_roas = after.get("after_roas")
    revenue_delta = after_revenue - before_revenue
    order_delta = after_orders - before_orders
    if after_revenue <= 0 and after_orders <= 0:
        return {
            "outcome": "unknown",
            "score": 45,
            "priority": 55,
            "summary": "已记录执行，但缺少执行后的销售、订单或 ROAS 数据，暂时不能判断效果。",
            "next_rule": "补录执行后 4-72 小时数据，再判断是否放大、复制或停止。",
        }
    if revenue_delta > 0 and order_delta >= 0 and (after_roas is None or float(after_roas or 0) >= 1.2):
        return {
            "outcome": "positive",
            "score": 85,
            "priority": 90,
            "summary": f"执行后销售额增加 {revenue_delta:.2f}，订单变化 {order_delta:.0f}，可进入小规模复制或放大观察。",
            "next_rule": "优先复制到同类新店或测试店；放大前继续观察退款、退货、ROAS 和差评。",
        }
    if revenue_delta < 0 or (after_roas is not None and float(after_roas or 0) < 1):
        return {
            "outcome": "negative",
            "score": 25,
            "priority": 80,
            "summary": f"执行后销售或 ROAS 未达预期，销售额变化 {revenue_delta:.2f}，需要停止放大并复盘原因。",
            "next_rule": "暂停复制，检查素材、价格、Listing、广告预算、库存、评论和履约问题。",
        }
    return {
        "outcome": "neutral",
        "score": 60,
        "priority": 70,
        "summary": f"执行后变化不明显，销售额变化 {revenue_delta:.2f}，先继续观察。",
        "next_rule": "继续观察一个周期；没有明显改善时，不要在老店放大。",
    }

def number(value: Any) -> float:
    if value in {"", None}:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    clean = "".join(ch for ch in str(value) if ch.isdigit() or ch in ".-")
    if not clean or clean in {"-", ".", "-."}:
        return 0.0
    try:
        return float(clean)
    except ValueError:
        return 0.0
