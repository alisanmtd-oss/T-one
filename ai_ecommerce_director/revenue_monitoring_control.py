from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .autonomous_loop import load_autonomous_loop_config
from .storage import read_records


POLICY_RELATIVE_PATH = Path("config") / "revenue_monitoring_policy.json"
STATE_RELATIVE_PATH = Path("data") / "revenue_monitoring_runtime.json"
MAX_ROWS = 300
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
GLOBAL_COVERAGE = {"global", "all", "all_platforms", "global_24h", "24h_global", "full_coverage"}
SENSITIVE_KEYS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "api_key",
    "password",
    "cookie",
    "authorization",
    "private_payload",
    "customer_pii",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(default)
    return value if isinstance(value, dict) else dict(default)


def _policy(root: Path) -> dict[str, Any]:
    default = {
        "schema_version": 1,
        "scope": "non_amazon_local_preflight_only",
        "required_route": [
            "tenant_id",
            "project_id",
            "task_id",
            "revenue_objective_id",
            "execution_identity_id",
            "source_connector_ref",
            "evidence_metric_code",
            "stop_rule_id",
        ],
        "scope_kinds": ["project_task", "store"],
        "local_actions": ["inspect_scheduler", "prepare_monitor_plan"],
        "blocked_actions": [
            "enable_schedule",
            "run_external_monitor",
            "fetch_private_data",
            "write_platform",
            "send_alert",
        ],
        "stop_rules": [
            {
                "id": "stop-after-3-consecutive-failures",
                "trigger": "consecutive_failures_gte_3",
                "action": "stop_and_require_owner_review",
            }
        ],
        "hard_boundaries": ["no_global_24h_or_all_platform_coverage_claim"],
    }
    value = _read_json(root / POLICY_RELATIVE_PATH, default)
    if not isinstance(value.get("required_route"), list):
        raise ValueError("Revenue monitoring policy is missing required_route.")
    return value


def _state(root: Path) -> dict[str, Any]:
    value = _read_json(
        root / STATE_RELATIVE_PATH,
        {"schema_version": 1, "audits": [], "failures": [], "reviews": []},
    )
    for key in ("audits", "failures", "reviews"):
        if not isinstance(value.get(key), list):
            value[key] = []
    value["schema_version"] = 1
    return value


def _save_state(root: Path, state: dict[str, Any]) -> None:
    path = root / STATE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    for key in ("audits", "failures", "reviews"):
        state[key] = list(state.get(key) or [])[-MAX_ROWS:]
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _sensitive_field(value: Any, path: str = "request") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().casefold()
            if normalized in SENSITIVE_KEYS or normalized.endswith("_secret"):
                return f"{path}.{key}"
            found = _sensitive_field(child, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _sensitive_field(child, f"{path}[{index}]")
            if found:
                return found
    return None


def _clean_identifier(value: Any, label: str, *, required: bool = False) -> str:
    text = str(value or "").strip()
    if not text and not required:
        return ""
    if not IDENTIFIER.fullmatch(text):
        raise ValueError(f"{label} must be a stable internal identifier.")
    return text


def _legacy_scheduler_snapshot(root: Path) -> dict[str, Any]:
    loop_config = load_autonomous_loop_config(root)
    jobs = [item for item in loop_config.get("scheduler_jobs", []) if isinstance(item, dict)]
    job_ids = {str(item.get("id") or "") for item in jobs}
    records: list[dict[str, Any]] = []
    for record in read_records(root, "task_queue"):
        fields = record.fields if isinstance(record.fields, dict) else {}
        task_type = str(fields.get("task_type") or "")
        if task_type not in job_ids:
            continue
        payload = fields.get("payload") if isinstance(fields.get("payload"), dict) else {}
        records.append(
            {
                "task_type": task_type,
                "status": str(fields.get("status") or "unknown"),
                "created_at": str(fields.get("created_at_utc") or record.created_at or ""),
                "qualified": all(
                    str(payload.get(field) or "").strip()
                    for field in (
                        "project_id",
                        "task_id",
                        "revenue_objective_id",
                        "source_connector_ref",
                        "stop_rule_id",
                    )
                ),
            }
        )
    return {
        "jobs": jobs,
        "job_count": len(jobs),
        "enabled_job_count": sum(1 for item in jobs if item.get("enabled", True)),
        "legacy_disabled_job_count": sum(
            1 for item in jobs if item.get("disabled_reason") == "legacy_unbound_template"
        ),
        "historical_record_count": len(records),
        "historical_unbound_count": sum(1 for item in records if not item["qualified"]),
        "qualified_historical_count": sum(1 for item in records if item["qualified"]),
        "historical_queued_unbound_count": sum(
            1 for item in records if not item["qualified"] and item["status"] == "queued"
        ),
    }


def revenue_monitoring_snapshot(root: Path) -> dict[str, Any]:
    policy = _policy(root)
    state = _state(root)
    legacy = _legacy_scheduler_snapshot(root)
    return {
        "schema_version": 1,
        "scope": policy.get("scope"),
        "required_route": list(policy.get("required_route") or []),
        "scope_kinds": list(policy.get("scope_kinds") or []),
        "local_actions": list(policy.get("local_actions") or []),
        "blocked_actions": list(policy.get("blocked_actions") or []),
        "stop_rules": list(policy.get("stop_rules") or []),
        "hard_boundaries": list(policy.get("hard_boundaries") or []),
        "legacy_scheduler": legacy,
        "effective_monitor_count": 0,
        "verified_source_count": 0,
        "external_run_count": 0,
        "platform_write_count": 0,
        "message_send_count": 0,
        "audits": list(state.get("audits") or [])[-20:][::-1],
        "failures": list(state.get("failures") or [])[-20:][::-1],
        "reviews": list(state.get("reviews") or [])[-20:][::-1],
    }


def _base(status: str, *, allowed: bool, missing: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "missing": list(missing or []),
        "local_action_allowed": allowed,
        "schedule_enabled": False,
        "external_monitor_run": False,
        "private_data_fetched": False,
        "platform_write_performed": False,
        "message_sent": False,
        "external_action_count": 0,
    }


def evaluate_revenue_monitoring_request(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ValueError("Revenue monitoring request must be an object.")
    if _sensitive_field(request):
        result = _base("blocked_sensitive_input", allowed=False)
        result["error"] = "Raw credentials and private payloads are not accepted."
        return result
    snapshot = revenue_monitoring_snapshot(root)
    action = str(request.get("action") or "inspect_scheduler").strip().casefold()
    coverage = str(request.get("coverage_claim") or "exact_scope").strip().casefold()
    if coverage in GLOBAL_COVERAGE:
        result = _base(
            "blocked_unverifiable_coverage_claim",
            allowed=False,
            missing=["exact_revenue_bound_scope"],
        )
        result["error"] = "A global 24-hour or all-platform coverage claim is not executable or verifiable."
        return result
    if action == "inspect_scheduler":
        result = _base("legacy_scheduler_review_ready", allowed=True)
        result["legacy_scheduler"] = snapshot["legacy_scheduler"]
        result["stop_rules"] = snapshot["stop_rules"]
        result["missing"] = ["qualified_revenue_bound_monitor", "verified_source_receipt"]
        return result
    if action in set(snapshot["blocked_actions"]):
        result = _base(
            "blocked_external_action",
            allowed=False,
            missing=["separate_owner_action", "qualified_monitor_plan", "verified_source"],
        )
        result["error"] = "Scheduling, external reads, platform writes and alerts require a separately approved qualified monitor."
        return result
    if action != "prepare_monitor_plan":
        raise ValueError("Unknown revenue monitoring action.")
    scope_kind = str(request.get("scope_kind") or "project_task").strip().casefold()
    if scope_kind not in set(snapshot["scope_kinds"]):
        result = _base("blocked_invalid_scope_kind", allowed=False, missing=["valid_scope_kind"])
        return result
    required = list(snapshot["required_route"])
    if scope_kind == "store":
        required.append("store_binding_id")
    missing = [field for field in required if not str(request.get(field) or "").strip()]
    if missing:
        return _base("blocked_missing_monitor_route", allowed=False, missing=missing)
    stop_rule_id = str(request.get("stop_rule_id") or "")
    stop_rule_ids = {str(item.get("id") or "") for item in snapshot["stop_rules"] if isinstance(item, dict)}
    if stop_rule_id not in stop_rule_ids:
        return _base("blocked_unknown_stop_rule", allowed=False, missing=["reviewed_stop_rule"])
    packet = {
        field: _clean_identifier(request.get(field), field, required=True)
        for field in required
    }
    packet.update(
        {
            "scope_kind": scope_kind,
            "coverage_claim": "exact_scope_only",
            "source_state": "reference_only_not_verified",
            "schedule_state": "not_enabled",
            "external_run_state": "not_performed",
            "owner_authorization_required": True,
        }
    )
    result = _base("local_monitor_plan_ready", allowed=True)
    result["monitor_plan"] = packet
    return result


def run_revenue_monitoring_audit(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    request = payload.get("request") if isinstance(payload.get("request"), dict) else payload
    result = evaluate_revenue_monitoring_request(root, request)
    safe_request = {
        key: request.get(key)
        for key in (
            "action",
            "coverage_claim",
            "scope_kind",
            "tenant_id",
            "project_id",
            "task_id",
            "store_binding_id",
            "revenue_objective_id",
            "execution_identity_id",
            "source_connector_ref",
            "evidence_metric_code",
            "stop_rule_id",
        )
        if request.get(key) not in (None, "")
    }
    audit = {
        "id": f"revenue-monitoring-audit-{uuid4().hex[:16]}",
        "created_at": _now(),
        "actor": str(actor or "owner")[:120],
        "request": safe_request,
        "result": result,
    }
    state = _state(root)
    state["audits"].append(audit)
    _save_state(root, state)
    return {"ok": True, "audit": audit}


def record_revenue_monitoring_failure(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    audit_id = _clean_identifier(payload.get("audit_id"), "audit_id", required=True)
    state = _state(root)
    audit = next((item for item in state["audits"] if item.get("id") == audit_id), None)
    if not audit:
        raise ValueError("Revenue monitoring audit not found.")
    status = str((audit.get("result") or {}).get("status") or "unknown")
    if status in {"local_monitor_plan_ready"}:
        raise ValueError("A ready local plan is not a failure; no external run was attempted.")
    failure = {
        "id": f"revenue-monitoring-failure-{uuid4().hex[:16]}",
        "created_at": _now(),
        "actor": str(actor or "owner")[:120],
        "audit_id": audit_id,
        "failure_code": status,
        "failure_stage": "local_preflight",
        "schedule_enabled": False,
        "external_monitor_run": False,
        "stop_applied": True,
        "stop_reason": "preflight_failed_no_external_run",
        "owner_review_required": True,
    }
    state["failures"].append(failure)
    _save_state(root, state)
    return {"ok": True, "failure": failure}


def record_revenue_monitoring_review(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    audit_id = _clean_identifier(payload.get("audit_id"), "audit_id", required=True)
    state = _state(root)
    if not any(item.get("id") == audit_id for item in state["audits"]):
        raise ValueError("Revenue monitoring audit not found.")
    review = {
        "id": f"revenue-monitoring-review-{uuid4().hex[:16]}",
        "created_at": _now(),
        "actor": str(actor or "owner")[:120],
        "audit_id": audit_id,
        "evidence_source": str(payload.get("evidence_source") or "formal_app_manual")[:120],
        "evidence_ref": str(payload.get("evidence_ref") or f"formal-app:{audit_id}")[:240],
        "schedule_enable_observed": False,
        "external_monitor_run_observed": False,
        "private_data_fetch_observed": False,
        "platform_write_observed": False,
        "message_send_observed": False,
        "causal_conclusion": "inconclusive",
    }
    state["reviews"].append(review)
    _save_state(root, state)
    return {"ok": True, "review": review}
