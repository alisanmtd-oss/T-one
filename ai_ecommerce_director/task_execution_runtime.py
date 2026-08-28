from __future__ import annotations

import json
import hashlib
import math
import re
import sqlite3
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .business_action_metrics import resolve_business_action_metric_contract
from .platform_experts import (
    detect_country_site,
    detect_explicit_platform_intent,
    infer_platform_capability,
    platform_scope_is_generic,
)
from .workspace_runtime import load_workspace_config, task_local_folder
from .workspace_schema import find_task_context


RUNS_PATH = Path("data") / "task_execution_runs.json"
RUNS_DB_PATH = Path("data") / "task_execution_runtime.sqlite3"
SYNTHETIC_CAPACITY_RESULT_PATH = (
    Path("outputs") / "c4_g08_synthetic_capacity_latest.json"
)
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,95}$")
DEFAULT_LEASE_SECONDS = 45
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 15
MAX_RETRY_BACKOFF_SECONDS = 300
DEFAULT_TOOL_WORKER_COUNT = 4
DEFAULT_TOOL_PENDING_LIMIT = 8
DEFAULT_RECOVERY_BATCH_LIMIT = 32
DEFAULT_RECOVERY_POLL_SECONDS = 2
QUEUE_PRIORITIES = {
    "order_critical": 100,
    "account_risk": 90,
    "inventory_critical": 80,
    "customer_service": 70,
    "listing_write": 60,
    "promotion_ads_write": 50,
    "browser_interactive": 40,
    "b2b_growth": 30,
    "content_generation": 20,
    "research_read": 10,
}
SAFE_EXECUTION_PAYLOAD_FIELDS = (
    "requested_action",
    "surface",
    "input_path",
    "tenant_id",
    "workspace_id",
    "project_id",
    "task_id",
    "platform",
    "country",
    "country_site",
    "store_model",
    "ownership",
    "route_key",
    "store_binding_id",
    "store_id",
    "execution_identity_id",
    "execution_domain",
    "browser_provider",
    "browser_profile",
    "browser_profile_seq",
    "browser_profile_sequence",
    "profile_id",
    "store_surface_connector_script",
    "product_id",
    "product_name",
    "model_provider",
    "allow_external_vision",
    "platform_expert_id",
    "platform_route_source",
    "platform_capability",
    "template_id",
    "generation_route_id",
    "creative_run_id",
)
SAFE_BUSINESS_OBJECT_REFERENCE_KEYS = (
    "object_type",
    "object_id",
    "version_ref",
    "source_ref",
)
CREATIVE_FEEDBACK_SOURCES = {
    "platform_analytics_export",
    "owner_dashboard",
    "api_read",
    "manual_verified",
}
CREATIVE_FEEDBACK_METRICS = {
    "impressions",
    "views",
    "three_second_views",
    "likes",
    "comments",
    "shares",
    "saves",
    "clicks",
    "orders",
    "spend",
    "revenue",
    "refunds",
}
CREATIVE_MONETARY_METRICS = {"spend", "revenue", "refunds"}
ACTIVE_RUN_STATUSES = ("queued", "running", "analysis_pending")
BUSINESS_EVENT_KINDS = ("fact", "observation", "inference", "draft")
BUSINESS_EVENT_SECRET = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|"
    r"password|passphrase|private[_-]?key)\s*[:=]"
)
_LOCK = threading.RLock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any, limit: int = 2000) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _utc_now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc_now(value).isoformat()


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _utc_now(datetime.fromisoformat(text))
    except ValueError:
        return None


def _bounded_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _retry_delay_seconds(attempt_count: Any) -> int:
    attempts = _bounded_int(attempt_count, 1, 20, 1)
    delay = DEFAULT_RETRY_BACKOFF_SECONDS * (2 ** max(0, attempts - 1))
    return min(delay, MAX_RETRY_BACKOFF_SECONDS)


def _queue_class(run: dict[str, Any]) -> str:
    explicit = str(run.get("queue_class") or "").strip().lower()
    if explicit in QUEUE_PRIORITIES:
        return explicit
    action = str(run.get("action") or "").strip().lower()
    surface = str(run.get("surface") or "").strip().lower()
    domain = str(run.get("execution_domain") or "").strip().lower()
    if action == "open_store_surface":
        if surface == "orders":
            return "order_critical"
        if surface == "inventory":
            return "inventory_critical"
        if surface in {"ads", "coupons"}:
            return "promotion_ads_write"
        return "browser_interactive"
    if domain == "crm" or action.startswith("create_b2b") or action.startswith("open_b2b"):
        return "b2b_growth"
    if domain == "creative" or action in {
        "analyze_video_path",
        "create_video_prompt_pack",
        "open_video_editor",
        "open_creative_output",
    }:
        return "content_generation"
    return "research_read"


def _queue_priority(run: dict[str, Any]) -> int:
    return QUEUE_PRIORITIES[_queue_class(run)]


def _synthetic_capacity_probe_summary(root: Path) -> dict[str, Any]:
    path = root / SYNTHETIC_CAPACITY_RESULT_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {
            "validated": False,
            "record_count": 0,
            "synthetic_store_scope_count": 0,
            "evidence_path": str(SYNTHETIC_CAPACITY_RESULT_PATH).replace("\\", "/"),
        }
    valid = bool(
        isinstance(payload, dict)
        and payload.get("ok") is True
        and int(payload.get("record_count") or 0) >= 100_000
        and int(payload.get("synthetic_store_scope_count") or 0) >= 100_000
        and payload.get("synthetic_100k_queue_depth_validated") is True
        and payload.get("production_capacity_validated") is False
        and payload.get("production_100k_store_sla_validated") is False
        and int(payload.get("external_action_count") or 0) == 0
        and str(payload.get("boundary") or "")
        == "synthetic_queue_depth_only_not_production_100k_store_capacity"
    )
    return {
        "validated": valid,
        "record_count": int(payload.get("record_count") or 0) if valid else 0,
        "synthetic_store_scope_count": (
            int(payload.get("synthetic_store_scope_count") or 0) if valid else 0
        ),
        "generated_at": str(payload.get("generated_at") or "") if valid else "",
        "insertion_seconds": float(payload.get("insertion_seconds") or 0) if valid else 0,
        "selection_seconds": float(payload.get("selection_seconds") or 0) if valid else 0,
        "restart_recovery_verified": bool(
            valid
            and isinstance(payload.get("checks"), dict)
            and payload["checks"].get("process_restart_restored_depth") is True
        ),
        "fencing_verified": bool(
            valid
            and isinstance(payload.get("checks"), dict)
            and payload["checks"].get("stale_worker_blocked") is True
        ),
        "production_capacity_validated": False,
        "evidence_path": str(SYNTHETIC_CAPACITY_RESULT_PATH).replace("\\", "/"),
    }


def runtime_worker_policy(root: Path) -> dict[str, Any]:
    path = root / "config" / "task_runtime_policy.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        payload = {}
    pool = payload.get("local_tool_worker_pool") if isinstance(payload, dict) else {}
    pool = pool if isinstance(pool, dict) else {}
    max_workers = _bounded_int(
        pool.get("max_workers"), 1, 16, DEFAULT_TOOL_WORKER_COUNT
    )
    max_pending = _bounded_int(
        pool.get("max_pending_in_memory"), 0, 64, DEFAULT_TOOL_PENDING_LIMIT
    )
    synthetic_probe = _synthetic_capacity_probe_summary(root)
    return {
        "max_workers": max_workers,
        "max_pending_in_memory": max_pending,
        "max_submitted_in_memory": max_workers + max_pending,
        "recovery_batch_limit": _bounded_int(
            pool.get("recovery_batch_limit"), 1, 100, DEFAULT_RECOVERY_BATCH_LIMIT
        ),
        "poll_seconds": _bounded_int(
            pool.get("poll_seconds"), 1, 30, DEFAULT_RECOVERY_POLL_SECONDS
        ),
        "capacity_validated": False,
        "synthetic_capacity_probe": synthetic_probe,
        "capacity_boundary": (
            "single_host_synthetic_100k_queue_depth_tested_not_100k_production_validated"
            if synthetic_probe["validated"]
            else "single_host_bounded_pool_not_100k_load_tested"
        ),
    }


def _safe_execution_payload(
    payload: dict[str, Any],
    task: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = dict(task or {})
    source.update(payload)
    safe: dict[str, Any] = {}
    for key in SAFE_EXECUTION_PAYLOAD_FIELDS:
        value = source.get(key)
        if isinstance(value, bool):
            safe[key] = value
        elif isinstance(value, (int, float)):
            safe[key] = value
        elif value is not None:
            text = str(value).strip()
            if text:
                safe[key] = text[:1000]
    context_refs = _safe_context_refs(source)
    if context_refs:
        safe["context_refs"] = context_refs
    return safe


def _safe_string_refs(value: Any, *, limit: int = 20) -> list[str]:
    values = value if isinstance(value, list) else ([value] if value not in (None, "") else [])
    clean: list[str] = []
    for item in values:
        text = _clean_text(item, 500)
        if text and text not in clean:
            clean.append(text)
    return clean[:limit]


def _safe_business_object_refs(value: Any) -> list[dict[str, str] | str]:
    values = value if isinstance(value, list) else ([value] if value not in (None, "") else [])
    clean: list[dict[str, str] | str] = []
    for item in values[:20]:
        if isinstance(item, dict):
            reference = {
                key: _clean_text(item.get(key), 500)
                for key in SAFE_BUSINESS_OBJECT_REFERENCE_KEYS
                if _clean_text(item.get(key), 500)
            }
            if reference and reference not in clean:
                clean.append(reference)
            continue
        text = _clean_text(item, 500)
        if text and text not in clean:
            clean.append(text)
    return clean


def _safe_context_refs(payload: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    manifest = _clean_text(
        payload.get("attachment_manifest_ref") or payload.get("manifest_path"), 500
    )
    if manifest:
        manifest_path = Path(manifest)
        if manifest_path.is_absolute() or ".." in manifest_path.parts:
            raise ValueError("附件资料清单必须是当前工作区内的安全相对路径。")
        context["attachment_manifest_ref"] = manifest
    source_refs = _safe_string_refs(payload.get("source_refs"))
    if manifest and manifest not in source_refs:
        source_refs.insert(0, manifest)
    if source_refs:
        context["source_refs"] = source_refs[:20]
    object_refs = _safe_business_object_refs(payload.get("business_object_refs"))
    if object_refs:
        context["business_object_refs"] = object_refs
    assigned_agent_id = _clean_text(payload.get("assigned_agent_id"), 160)
    if assigned_agent_id:
        context["assigned_agent_id"] = assigned_agent_id
    for key in ("assigned_agent_refs", "skill_refs"):
        refs = _safe_string_refs(payload.get(key))
        if refs:
            context[key] = refs
    return context


def _unified_task_type(task: dict[str, Any], route: dict[str, Any]) -> str:
    platform = str(task.get("platform") or "").strip().lower()
    if platform == "b2b":
        return "b2b_sales_and_email"
    if platform in {"ad_agent", "advertising"}:
        return "advertising_optimization"
    if platform == "creative_video":
        return "social_content_operations"
    if any(str(task.get(key) or "").strip() for key in ("store_binding_id", "store_id")):
        return "store_operations"
    if str(route.get("action") or "") == "open_store_surface":
        return "store_operations"
    return "unified_data_analysis"


def _unified_action_class(instruction: str, route: dict[str, Any]) -> str:
    if str(route.get("mode") or "") != "confirmation":
        return "private_read" if str(route.get("action") or "") == "open_store_surface" else "local_analysis"
    lowered = instruction.casefold()
    if any(word in lowered for word in ("付款", "预算", "花费", "充值")):
        return "money_or_budget"
    if any(word in lowered for word in ("验证码", "密码", "银行验证", "身份验证", "oauth")):
        return "credential_or_authorization"
    return "external_write"


def _orchestration_plan(
    root: Path,
    task: dict[str, Any],
    route: dict[str, Any],
    instruction: str,
    context_refs: dict[str, Any],
) -> dict[str, Any]:
    scope = {
        key: str(value).strip()
        for key, value in {
            "tenant_id": task.get("tenant_id") or "local",
            "workspace_id": task.get("workspace_id") or "local-workspace",
            "project_id": task.get("project_id"),
            "platform": task.get("platform"),
            "country_site": task.get("country") or task.get("country_site"),
            "store_binding_id": task.get("store_binding_id"),
            "store_model": task.get("store_model"),
            "ownership": task.get("ownership"),
            "execution_identity_id": task.get("execution_identity_id"),
        }.items()
        if str(value or "").strip()
    }
    task_type = _unified_task_type(task, route)
    action_class = _unified_action_class(instruction, route)
    try:
        from .unified_commerce_runtime import plan_unified_commerce_task

        plan = plan_unified_commerce_task(
            root,
            {"task_type": task_type, "action_class": action_class, "scope": scope},
        )
    except (OSError, TypeError, ValueError) as exc:
        plan = {
            "schema_version": 1,
            "task_type": task_type,
            "action_class": action_class,
            "status": "contract_unavailable",
            "scope": scope,
            "approval_required": str(route.get("mode") or "") == "confirmation",
            "execution_allowed": False,
            "external_action_count": 0,
            "skill_agents": [],
            "message": _clean_text(exc, 500),
        }
    plan["assigned_agent_id"] = str(context_refs.get("assigned_agent_id") or "")
    plan["assigned_agent_refs"] = list(context_refs.get("assigned_agent_refs") or [])
    plan["skill_refs"] = list(context_refs.get("skill_refs") or [])
    plan["business_object_refs"] = list(context_refs.get("business_object_refs") or [])
    plan["source_refs"] = list(context_refs.get("source_refs") or [])
    plan["execution_allowed"] = False
    plan["external_action_count"] = 0
    return plan


def _enqueue_confirmation_action(root: Path, run: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    from .execution_loop import write_action_queue_file

    queue_path = root / "outputs" / f"action_queue_{date.today().isoformat()}.json"
    if queue_path.exists():
        try:
            existing_payload = json.loads(queue_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                "现有审批队列无法安全读取；已保留原文件并停止写入。"
            ) from exc
        if not isinstance(existing_payload, list) or not all(
            isinstance(item, dict) for item in existing_payload
        ):
            raise ValueError("现有审批队列结构无效；已保留原文件并停止写入。")
        actions = list(existing_payload)
    else:
        actions = []
    action_id = f"task-run:{run['id']}:approval"
    existing = next(
        (item for item in actions if str(item.get("action_id") or "") == action_id), None
    )
    if existing is not None:
        return existing, queue_path
    refs = run.get("context_refs") if isinstance(run.get("context_refs"), dict) else {}
    plan = run.get("orchestration_plan") if isinstance(run.get("orchestration_plan"), dict) else {}
    action = {
        "action_id": action_id,
        "action_type": "t_one_external_action",
        "title": _clean_text(run.get("instruction"), 120) or "T-one 外部动作待确认",
        "description": _clean_text(run.get("reason"), 500),
        "reason": _clean_text(run.get("reason"), 500),
        "status": "pending_confirmation",
        "requires_confirmation": True,
        "approval_scope": "single_action_single_use",
        "approval_state": "not_approved",
        "external_submit_allowed": False,
        "external_execution_before_confirmation": False,
        "external_execution_observed": False,
        "task_run_id": str(run.get("id") or ""),
        "task_id": str(run.get("task_id") or ""),
        "tenant_id": str(run.get("tenant_id") or "local"),
        "workspace_id": str(run.get("workspace_id") or "local-workspace"),
        "project_id": str(run.get("project_id") or ""),
        "platform": str(run.get("platform") or ""),
        "country": str(run.get("country") or ""),
        "store_model": str(run.get("store_model") or ""),
        "ownership": str(run.get("ownership") or ""),
        "route_key": str(run.get("route_key") or ""),
        "store_binding_id": str(run.get("store_binding_id") or ""),
        "execution_identity_id": str(run.get("execution_identity_id") or ""),
        "assigned_agent_id": str(refs.get("assigned_agent_id") or ""),
        "source_refs": list(refs.get("source_refs") or []),
        "business_object_refs": list(refs.get("business_object_refs") or []),
        "attachment_manifest_ref": str(refs.get("attachment_manifest_ref") or ""),
        "action_class": str(plan.get("action_class") or "external_write"),
        "idempotency_key": str(run.get("idempotency_key") or action_id),
        "requested_at": str(run.get("created_at") or _now_iso()),
        "receipt_refs": [],
        "next_step": "负责人先确认这一个精确动作；确认只创建人工执行任务，不会自动操作外部平台。",
    }
    actions.append(action)
    write_action_queue_file(queue_path, actions)
    return action, queue_path


def _execution_domain(task: dict[str, Any], route: dict[str, Any] | None = None) -> str:
    explicit = str(task.get("execution_domain") or "").strip().lower()
    if explicit:
        return explicit
    route = route if isinstance(route, dict) else {}
    action = str(route.get("action") or "").strip().lower()
    surface = str(route.get("surface") or "").strip().lower()
    if action == "open_store_surface":
        if surface == "ads":
            return "ads"
        if surface == "coupons":
            return "promotion"
        return "seller_center"
    if action in {"create_b2b_sales_execution_pack", "open_b2b_customer_pool"}:
        return "crm"
    if action in {
        "analyze_video_path",
        "create_video_prompt_pack",
        "open_video_editor",
        "open_creative_output",
    }:
        return "creative"
    return "ai_analysis" if action == "model_analysis" else "local_tool"


def _store_scope_key(
    task: dict[str, Any], route: dict[str, Any] | None = None
) -> str:
    values = (
        str(task.get("tenant_id") or "local").strip().lower(),
        str(task.get("workspace_id") or "local-workspace").strip().lower(),
        str(task.get("project_id") or "").strip().lower(),
        str(task.get("platform") or "").strip().lower(),
        str(task.get("country") or task.get("country_site") or "GLOBAL").strip().upper(),
        str(task.get("store_model") or "").strip().lower(),
        str(task.get("ownership") or "").strip().lower(),
        str(task.get("store_binding_id") or "").strip().lower(),
        str(task.get("store_id") or "").strip().lower(),
        str(task.get("execution_identity_id") or "").strip().lower(),
        str(task.get("browser_profile_seq") or task.get("browser_profile_sequence") or "").strip(),
        _execution_domain(task, route),
    )
    return "|".join(values)


def _active_fingerprint(
    task: dict[str, Any],
    route: dict[str, Any],
    instruction: str,
) -> str:
    material = json.dumps(
        {
            "scope": _store_scope_key(task, route),
            "task_id": task.get("id"),
            "mode": route.get("mode"),
            "action": route.get("action"),
            "surface": route.get("surface"),
            "instruction": instruction,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _lease_expired(run: dict[str, Any], now: datetime) -> bool:
    expires_at = _parse_iso(run.get("lease_expires_at"))
    return expires_at is None or expires_at <= _utc_now(now)


def _task(root: Path, task_id: str) -> dict[str, Any]:
    task_id = str(task_id or "").strip().lower()
    if not SAFE_ID.fullmatch(task_id):
        raise ValueError("任务编号无效。")
    workspace = load_workspace_config(root)
    found = find_task_context(workspace, task_id)
    if found is not None:
        project, channel, store, item = found
        task = dict(item)
        task.setdefault("tenant_id", str(workspace.get("tenant_id") or "local"))
        task.setdefault("workspace_id", str(workspace.get("workspace_id") or "local-workspace"))
        task.setdefault("project_id", str(project.get("id") or ""))
        if isinstance(channel, dict):
            task.setdefault("platform", str(channel.get("platform") or ""))
            task.setdefault(
                "country_site",
                str(channel.get("country_site") or channel.get("country") or "GLOBAL"),
            )
        if isinstance(store, dict):
            for key in (
                "store_model",
                "ownership",
                "route_key",
                "execution_identity_id",
                "credential_ref_type",
                "browser_provider",
                "browser_profile_id",
                "browser_profile_sequence",
                "browser_profile_seq",
                "store_surface_connector_script",
            ):
                if not task.get(key) and store.get(key) not in (None, ""):
                    task[key] = store.get(key)
            if not task.get("store_binding_id"):
                task["store_binding_id"] = str(store.get("id") or "")
            if not task.get("store_id"):
                task["store_id"] = str(store.get("external_id") or store.get("id") or "")
        return task
    raise ValueError("任务不存在。")


def _legacy_runs(root: Path) -> list[dict[str, Any]]:
    path = root / RUNS_PATH
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise RuntimeError(f"无法读取旧任务运行记录：{path}") from exc
    except ValueError as exc:
        raise RuntimeError(f"旧任务运行记录已损坏，已停止迁移：{path}") from exc
    rows = payload.get("runs") if isinstance(payload, dict) else []
    return [dict(item) for item in rows if isinstance(item, dict)]


def _database_path(root: Path) -> Path:
    path = root / RUNS_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect(root: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        _database_path(root),
        timeout=30,
        isolation_level=None,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=30000")
    for attempt in range(8):
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            break
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == 7:
                connection.close()
                raise
            time.sleep(0.05 * (attempt + 1))
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS task_runs (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            id TEXT NOT NULL UNIQUE,
            task_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            store_scope_key TEXT NOT NULL,
            active_fingerprint TEXT NOT NULL,
            idempotency_key TEXT UNIQUE,
            lease_owner TEXT NOT NULL DEFAULT '',
            lease_expires_at TEXT NOT NULL DEFAULT '',
            fencing_token INTEGER NOT NULL DEFAULT 0,
            next_retry_at TEXT NOT NULL DEFAULT '',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            dead_lettered_at TEXT NOT NULL DEFAULT '',
            last_error_code TEXT NOT NULL DEFAULT '',
            retry_backoff_seconds INTEGER NOT NULL DEFAULT 0,
            queue_class TEXT NOT NULL DEFAULT 'research_read',
            queue_priority INTEGER NOT NULL DEFAULT 10,
            tenant_id TEXT NOT NULL DEFAULT 'local',
            platform TEXT NOT NULL DEFAULT '',
            execution_domain TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_task_runs_task_seq
            ON task_runs(task_id, seq DESC);
        CREATE INDEX IF NOT EXISTS idx_task_runs_recovery
            ON task_runs(mode, status, lease_expires_at, seq);
        CREATE INDEX IF NOT EXISTS idx_task_runs_store_status
            ON task_runs(store_scope_key, status, lease_expires_at);
        CREATE INDEX IF NOT EXISTS idx_task_runs_fingerprint
            ON task_runs(active_fingerprint, status);
        CREATE TABLE IF NOT EXISTS task_run_events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            actor TEXT NOT NULL DEFAULT '',
            fencing_token INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES task_runs(id)
        );
        CREATE INDEX IF NOT EXISTS idx_task_run_events_run_seq
            ON task_run_events(run_id, seq);
        CREATE TABLE IF NOT EXISTS business_events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL,
            workspace_id TEXT NOT NULL DEFAULT '',
            project_id TEXT NOT NULL DEFAULT '',
            task_id TEXT NOT NULL DEFAULT '',
            conversation_id TEXT NOT NULL DEFAULT '',
            run_id TEXT NOT NULL DEFAULT '',
            actor TEXT NOT NULL DEFAULT '',
            statement TEXT NOT NULL,
            confidence TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'recorded',
            created_at TEXT NOT NULL,
            source_refs_json TEXT NOT NULL,
            business_object_refs_json TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_business_events_project_seq
            ON business_events(project_id, seq DESC);
        CREATE INDEX IF NOT EXISTS idx_business_events_task_seq
            ON business_events(task_id, seq DESC);
        CREATE INDEX IF NOT EXISTS idx_business_events_conversation_seq
            ON business_events(conversation_id, seq DESC);
        CREATE INDEX IF NOT EXISTS idx_business_events_run_seq
            ON business_events(run_id, seq DESC);
        CREATE TABLE IF NOT EXISTS runtime_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(task_runs)").fetchall()
    }
    runtime_columns = {
        "next_retry_at": "TEXT NOT NULL DEFAULT ''",
        "attempt_count": "INTEGER NOT NULL DEFAULT 0",
        "max_attempts": f"INTEGER NOT NULL DEFAULT {DEFAULT_MAX_ATTEMPTS}",
        "dead_lettered_at": "TEXT NOT NULL DEFAULT ''",
        "last_error_code": "TEXT NOT NULL DEFAULT ''",
        "retry_backoff_seconds": "INTEGER NOT NULL DEFAULT 0",
        "queue_class": "TEXT NOT NULL DEFAULT 'research_read'",
        "queue_priority": "INTEGER NOT NULL DEFAULT 10",
        "tenant_id": "TEXT NOT NULL DEFAULT 'local'",
        "platform": "TEXT NOT NULL DEFAULT ''",
        "execution_domain": "TEXT NOT NULL DEFAULT ''",
    }
    for name, definition in runtime_columns.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE task_runs ADD COLUMN {name} {definition}")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_task_runs_retry_due "
        "ON task_runs(mode, status, queue_priority DESC, next_retry_at, lease_expires_at, seq)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_task_runs_queue_fairness "
        "ON task_runs(mode, status, queue_priority DESC, tenant_id, seq)"
    )
    _migrate_legacy_runs(connection, root)
    return connection


def _encode_run(run: dict[str, Any]) -> str:
    return json.dumps(run, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _decode_run(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    try:
        payload = json.loads(str(row["payload_json"] or "{}"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"任务运行记录 {row['id']} 已损坏，已停止执行。") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"任务运行记录 {row['id']} 结构无效，已停止执行。")
    had_queue_class = bool(str(payload.get("queue_class") or "").strip())
    for key, default in (
        ("next_retry_at", ""),
        ("attempt_count", 0),
        ("max_attempts", DEFAULT_MAX_ATTEMPTS),
        ("dead_lettered_at", ""),
        ("last_error_code", ""),
        ("retry_backoff_seconds", 0),
        ("queue_class", "research_read"),
        ("queue_priority", 10),
        ("tenant_id", "local"),
        ("platform", ""),
        ("execution_domain", ""),
    ):
        if key not in payload:
            payload[key] = row[key] if key in row.keys() else default
    if not had_queue_class:
        payload["queue_class"] = _queue_class({**payload, "queue_class": ""})
        payload["queue_priority"] = _queue_priority(payload)
    return payload


def _insert_run(connection: sqlite3.Connection, run: dict[str, Any]) -> None:
    idempotency_key = str(run.get("idempotency_key") or "").strip() or None
    connection.execute(
        """
        INSERT INTO task_runs (
            id, task_id, mode, status, store_scope_key, active_fingerprint,
            idempotency_key, lease_owner, lease_expires_at, fencing_token,
            next_retry_at, attempt_count, max_attempts, dead_lettered_at,
            last_error_code, retry_backoff_seconds, queue_class, queue_priority,
            tenant_id, platform, execution_domain,
            created_at, updated_at, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(run.get("id") or ""),
            str(run.get("task_id") or ""),
            str(run.get("mode") or ""),
            str(run.get("status") or ""),
            str(run.get("store_scope_key") or ""),
            str(run.get("active_fingerprint") or ""),
            idempotency_key,
            str(run.get("lease_owner") or ""),
            str(run.get("lease_expires_at") or ""),
            int(run.get("fencing_token") or 0),
            str(run.get("next_retry_at") or ""),
            int(run.get("attempt_count") or 0),
            int(run.get("max_attempts") or DEFAULT_MAX_ATTEMPTS),
            str(run.get("dead_lettered_at") or ""),
            str(run.get("last_error_code") or ""),
            int(run.get("retry_backoff_seconds") or 0),
            _queue_class(run),
            _queue_priority(run),
            str(run.get("tenant_id") or "local"),
            str(run.get("platform") or ""),
            str(run.get("execution_domain") or ""),
            str(run.get("created_at") or _now_iso()),
            str(run.get("updated_at") or _now_iso()),
            _encode_run(run),
        ),
    )


def _save_run(
    connection: sqlite3.Connection,
    run: dict[str, Any],
    *,
    worker_id: str = "",
    fencing_token: int | None = None,
) -> bool:
    parameters: list[Any] = [
        str(run.get("task_id") or ""),
        str(run.get("mode") or ""),
        str(run.get("status") or ""),
        str(run.get("store_scope_key") or ""),
        str(run.get("active_fingerprint") or ""),
        str(run.get("idempotency_key") or "").strip() or None,
        str(run.get("lease_owner") or ""),
        str(run.get("lease_expires_at") or ""),
        int(run.get("fencing_token") or 0),
        str(run.get("next_retry_at") or ""),
        int(run.get("attempt_count") or 0),
        int(run.get("max_attempts") or DEFAULT_MAX_ATTEMPTS),
        str(run.get("dead_lettered_at") or ""),
        str(run.get("last_error_code") or ""),
        int(run.get("retry_backoff_seconds") or 0),
        _queue_class(run),
        _queue_priority(run),
        str(run.get("tenant_id") or "local"),
        str(run.get("platform") or ""),
        str(run.get("execution_domain") or ""),
        str(run.get("updated_at") or _now_iso()),
        _encode_run(run),
        str(run.get("id") or ""),
    ]
    where = "id = ?"
    if worker_id or fencing_token is not None:
        if not worker_id or fencing_token is None:
            raise ValueError("工作进程与 fencing token 必须同时提供。")
        where += " AND lease_owner = ? AND fencing_token = ?"
        parameters.extend([worker_id, int(fencing_token)])
    cursor = connection.execute(
        f"""
        UPDATE task_runs SET
            task_id = ?, mode = ?, status = ?, store_scope_key = ?,
            active_fingerprint = ?, idempotency_key = ?, lease_owner = ?,
            lease_expires_at = ?, fencing_token = ?, next_retry_at = ?,
            attempt_count = ?, max_attempts = ?, dead_lettered_at = ?,
            last_error_code = ?, retry_backoff_seconds = ?, queue_class = ?,
            queue_priority = ?, tenant_id = ?, platform = ?, execution_domain = ?,
            updated_at = ?, payload_json = ?
        WHERE {where}
        """,
        parameters,
    )
    return cursor.rowcount == 1


def _append_event(
    connection: sqlite3.Connection,
    run: dict[str, Any],
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO task_run_events (
            run_id, event_type, actor, fencing_token, created_at, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(run.get("id") or ""),
            event_type,
            str(run.get("actor") or ""),
            int(run.get("fencing_token") or 0),
            _now_iso(),
            json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
        ),
    )


def _safe_business_event_statement(value: Any) -> str:
    statement = _clean_text(value, 2000)
    if not statement:
        raise ValueError("业务事件缺少可读说明。")
    if BUSINESS_EVENT_SECRET.search(statement):
        raise ValueError("业务事件不得保存密钥、令牌或密码。")
    return statement


def _decode_business_event(row: sqlite3.Row) -> dict[str, Any]:
    def load_list(column: str) -> list[Any]:
        try:
            value = json.loads(str(row[column] or "[]"))
        except (TypeError, ValueError):
            return []
        return value if isinstance(value, list) else []

    try:
        payload = json.loads(str(row["payload_json"] or "{}"))
    except (TypeError, ValueError):
        payload = {}
    return {
        "seq": int(row["seq"] or 0),
        "event_id": str(row["event_id"] or ""),
        "kind": str(row["kind"] or ""),
        "workspace_id": str(row["workspace_id"] or ""),
        "project_id": str(row["project_id"] or ""),
        "task_id": str(row["task_id"] or ""),
        "conversation_id": str(row["conversation_id"] or ""),
        "run_id": str(row["run_id"] or ""),
        "actor": str(row["actor"] or ""),
        "statement": str(row["statement"] or ""),
        "confidence": str(row["confidence"] or ""),
        "status": str(row["status"] or ""),
        "created_at": str(row["created_at"] or ""),
        "source_refs": load_list("source_refs_json"),
        "business_object_refs": load_list("business_object_refs_json"),
        "payload": payload if isinstance(payload, dict) else {},
    }


def _append_business_event(
    connection: sqlite3.Connection,
    payload: dict[str, Any],
    *,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    kind = str(payload.get("kind") or "").strip().lower()
    if kind not in BUSINESS_EVENT_KINDS:
        raise ValueError("业务事件类型必须是 fact、observation、inference 或 draft。")
    statement = _safe_business_event_statement(payload.get("statement"))
    event_id = _clean_text(payload.get("event_id"), 120) or (
        "business-event-" + uuid.uuid4().hex[:20]
    )
    if not SAFE_ID.fullmatch(event_id):
        raise ValueError("业务事件编号无效。")
    source_refs = _safe_string_refs(payload.get("source_refs"), limit=20)
    business_object_refs = _safe_business_object_refs(
        payload.get("business_object_refs")
    )
    event_payload = payload.get("payload")
    event_payload = event_payload if isinstance(event_payload, dict) else {}
    event_type = _clean_text(
        payload.get("event_type") or event_payload.get("event_type"), 120
    ).lower()
    if event_type:
        event_payload["event_type"] = event_type
        database_path = Path(
            str(connection.execute("PRAGMA database_list").fetchone()[2] or "")
        )
        database_root = database_path.parent.parent
        action_contract = resolve_business_action_metric_contract(
            database_root,
            event_type,
        )
        registry_exists = (
            database_root
            / "config"
            / "ai_analytics_data_foundation_registry.json"
        ).exists()
        if registry_exists and not action_contract:
            raise ValueError(f"业务动作类型尚未登记数据口径：{event_type}")
        if action_contract:
            event_payload["action_contract"] = action_contract
        else:
            event_payload["action_contract_status"] = "registry_unavailable"
    serialized_payload = json.dumps(event_payload, ensure_ascii=False, sort_keys=True)
    if BUSINESS_EVENT_SECRET.search(serialized_payload):
        raise ValueError("业务事件载荷不得保存密钥、令牌或密码。")
    record = {
        "event_id": event_id,
        "kind": kind,
        "workspace_id": _clean_text(payload.get("workspace_id"), 120),
        "project_id": _clean_text(payload.get("project_id"), 120),
        "task_id": _clean_text(payload.get("task_id"), 120),
        "conversation_id": _clean_text(
            payload.get("conversation_id") or payload.get("task_id"), 120
        ),
        "run_id": _clean_text(payload.get("run_id"), 120),
        "actor": _clean_text(payload.get("actor") or actor, 120),
        "statement": statement,
        "confidence": _clean_text(payload.get("confidence"), 40),
        "status": _clean_text(payload.get("status") or "recorded", 80),
        "created_at": _clean_text(payload.get("created_at"), 80) or _now_iso(),
        "source_refs": source_refs,
        "business_object_refs": business_object_refs,
        "payload": event_payload,
    }
    connection.execute(
        """
        INSERT INTO business_events (
            event_id, kind, workspace_id, project_id, task_id, conversation_id,
            run_id, actor, statement, confidence, status, created_at,
            source_refs_json, business_object_refs_json, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["event_id"], record["kind"], record["workspace_id"],
            record["project_id"], record["task_id"], record["conversation_id"],
            record["run_id"], record["actor"], record["statement"],
            record["confidence"], record["status"], record["created_at"],
            json.dumps(record["source_refs"], ensure_ascii=False, sort_keys=True),
            json.dumps(record["business_object_refs"], ensure_ascii=False, sort_keys=True),
            serialized_payload,
        ),
    )
    return record


def append_business_event(
    root: Path,
    payload: dict[str, Any],
    *,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    """Append one durable, provenance-aware business event without external action."""

    with _LOCK:
        connection = _connect(root)
        try:
            connection.execute("BEGIN IMMEDIATE")
            record = _append_business_event(connection, payload, actor=actor)
            connection.commit()
            return record
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def business_event_projection(
    root: Path,
    *,
    project_id: str = "",
    task_id: str = "",
    conversation_id: str = "",
    run_id: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    """Return the shared read model used by both conversations and dashboards."""

    clauses: list[str] = []
    parameters: list[Any] = []
    for column, value in (
        ("project_id", project_id),
        ("task_id", task_id),
        ("conversation_id", conversation_id),
        ("run_id", run_id),
    ):
        clean = _clean_text(value, 120)
        if clean:
            clauses.append(f"{column} = ?")
            parameters.append(clean)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    bounded_limit = _bounded_int(limit, 1, 500, 100)
    with _LOCK:
        connection = _connect(root)
        try:
            rows = connection.execute(
                "SELECT * FROM business_events"
                + where
                + " ORDER BY seq DESC LIMIT ?",
                (*parameters, bounded_limit),
            ).fetchall()
        finally:
            connection.close()
    events = [_decode_business_event(row) for row in rows]
    counts = {kind: 0 for kind in BUSINESS_EVENT_KINDS}
    action_contract_counts: dict[str, int] = {}
    action_type_counts: dict[str, int] = {}
    metric_touch_counts: dict[str, int] = {}
    unmapped_typed_event_count = 0
    for event in events:
        counts[event["kind"]] = counts.get(event["kind"], 0) + 1
        event_payload = event.get("payload")
        event_payload = event_payload if isinstance(event_payload, dict) else {}
        event_type = _clean_text(event_payload.get("event_type"), 120)
        action_contract = event_payload.get("action_contract")
        action_contract = (
            action_contract if isinstance(action_contract, dict) else {}
        )
        if event_type:
            action_type_counts[event_type] = action_type_counts.get(event_type, 0) + 1
            contract_id = _clean_text(action_contract.get("contract_id"), 120)
            if contract_id:
                action_contract_counts[contract_id] = (
                    action_contract_counts.get(contract_id, 0) + 1
                )
                for metric_id in action_contract.get("metric_ids", []):
                    clean_metric_id = _clean_text(metric_id, 120)
                    if clean_metric_id:
                        metric_touch_counts[clean_metric_id] = (
                            metric_touch_counts.get(clean_metric_id, 0) + 1
                        )
            else:
                unmapped_typed_event_count += 1
    return {
        "schema_version": 1,
        "source": "data/task_execution_runtime.sqlite3#business_events",
        "filters": {
            "project_id": _clean_text(project_id, 120),
            "task_id": _clean_text(task_id, 120),
            "conversation_id": _clean_text(conversation_id, 120),
            "run_id": _clean_text(run_id, 120),
        },
        "counts": counts,
        "action_projection": {
            "typed_event_count": sum(action_type_counts.values()),
            "unmapped_typed_event_count": unmapped_typed_event_count,
            "action_type_counts": action_type_counts,
            "contract_counts": action_contract_counts,
            "metric_touch_counts": metric_touch_counts,
        },
        "total": len(events),
        "latest_event_at": str(events[0].get("created_at") or "") if events else "",
        "events": events,
    }


def _run_business_event_payload(
    run: dict[str, Any],
    *,
    kind: str,
    statement: str,
    status: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context_refs = (
        run.get("context_refs") if isinstance(run.get("context_refs"), dict) else {}
    )
    return {
        "kind": kind,
        "workspace_id": str(run.get("workspace_id") or ""),
        "project_id": str(run.get("project_id") or ""),
        "task_id": str(run.get("task_id") or ""),
        "conversation_id": str(run.get("task_id") or ""),
        "run_id": str(run.get("id") or ""),
        "actor": str(run.get("actor") or "runtime"),
        "statement": statement,
        "status": status,
        "source_refs": list(context_refs.get("source_refs") or []),
        "business_object_refs": list(
            context_refs.get("business_object_refs") or []
        ),
        "event_type": event_type,
        "payload": {"event_type": event_type, **(payload or {})},
    }


def _migrate_legacy_runs(connection: sqlite3.Connection, root: Path) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        migrated = connection.execute(
            "SELECT value FROM runtime_metadata WHERE key = 'legacy_json_migrated'"
        ).fetchone()
        if migrated is None:
            for legacy in _legacy_runs(root):
                run = dict(legacy)
                run.setdefault("store_scope_key", "legacy|" + str(run.get("task_id") or ""))
                run.setdefault("active_fingerprint", "legacy-" + str(run.get("id") or uuid.uuid4().hex))
                run.setdefault("idempotency_key", "")
                run.setdefault("fencing_token", 0)
                run.setdefault("created_at", str(run.get("updated_at") or _now_iso()))
                run.setdefault("updated_at", str(run.get("created_at") or _now_iso()))
                try:
                    _insert_run(connection, run)
                    _append_event(connection, run, "legacy_imported")
                except sqlite3.IntegrityError:
                    continue
            connection.execute(
                "INSERT INTO runtime_metadata(key, value) VALUES('legacy_json_migrated', ?)",
                (_now_iso(),),
            )
        repaired = connection.execute(
            "SELECT value FROM runtime_metadata WHERE key = 'legacy_store_surface_evidence_repaired_v1'"
        ).fetchone()
        if repaired is None:
            rows = connection.execute(
                "SELECT * FROM task_runs WHERE store_scope_key LIKE 'legacy|%' AND status = 'completed'"
            ).fetchall()
            for row in rows:
                run = _decode_run(row)
                if run is None or str(run.get("action") or "") != "open_store_surface":
                    continue
                result_message = str(run.get("result_message") or "")
                if not result_message.startswith("已打开 BitBrowser"):
                    continue
                run.update(
                    {
                        "status": "needs_input",
                        "result_message": "",
                        "error": "历史打开记录缺少 CDP 页面验证证据，已撤销成功标记；请重新打开并复核店铺页面。",
                        "historical_correction": "unverified_store_surface",
                        "updated_at": _now_iso(),
                    }
                )
                _save_run(connection, run)
                _append_event(
                    connection,
                    run,
                    "historical_success_reclassified",
                    {"original_result_message": result_message},
                )
            connection.execute(
                "INSERT INTO runtime_metadata(key, value) VALUES('legacy_store_surface_evidence_repaired_v1', ?)",
                (_now_iso(),),
            )
        queue_indexed = connection.execute(
            "SELECT value FROM runtime_metadata WHERE key = 'queue_priority_columns_backfilled_v1'"
        ).fetchone()
        if queue_indexed is None:
            for row in connection.execute("SELECT * FROM task_runs ORDER BY seq").fetchall():
                run = _decode_run(row)
                if run is not None:
                    _save_run(connection, run)
            connection.execute(
                "INSERT INTO runtime_metadata(key, value) VALUES('queue_priority_columns_backfilled_v1', ?)",
                (_now_iso(),),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        connection.close()
        raise




def classify_task_instruction(
    task: dict[str, Any],
    instruction: str,
    *,
    requested_action: str = "",
    surface: str = "",
) -> dict[str, Any]:
    text = _clean_text(instruction)
    lowered = text.casefold()
    platform = str(task.get("platform") or "").strip().lower()
    requested_action = str(requested_action or "").strip().lower()
    surface = str(surface or "").strip().lower()
    explicit_platform = detect_explicit_platform_intent(text)

    # The owner explicitly paused Amazon.  A generic chat that names Amazon
    # must not silently revive that workstream or enqueue a store action.
    if explicit_platform and explicit_platform["platform"] == "amazon" and platform != "amazon":
        return {
            "mode": "input",
            "action": "amazon_paused_by_owner",
            "label": "Amazon 当前已按负责人要求暂停",
            "reason": "不会继续 Amazon 研究、店铺连接或执行；只有负责人明确恢复后才会继续。",
        }

    def has_unnegated_phrase(phrase: str) -> bool:
        start = 0
        while True:
            index = lowered.find(phrase, start)
            if index < 0:
                return False
            clause_start = 0
            for delimiter in ("。", "！", "？", ";", "；", "\n", "但是", "不过", "然而", "但"):
                position = lowered.rfind(delimiter, 0, index)
                if position >= 0:
                    clause_start = max(clause_start, position + len(delimiter))
            prefix = lowered[clause_start:index]
            negated = any(
                marker in prefix
                for marker in (
                    "不执行",
                    "不要",
                    "无需",
                    "不需要",
                    "禁止",
                    "不得",
                    "不做",
                    "不操作",
                    "不能",
                    "仅检查",
                    "只检查",
                    "仅分析",
                    "只分析",
                    "只读",
                )
            )
            if not negated:
                return True
            start = index + len(phrase)

    confirmation_phrases = (
        "发布商品",
        "提交商品",
        "删除商品",
        "改价",
        "修改价格",
        "启动广告",
        "发布广告",
        "提交广告",
        "创建优惠券",
        "提交优惠",
        "提交活动",
        "确认发货",
        "执行发货",
        "退款",
        "付款",
        "验证码",
        "修改密码",
        "银行验证",
        "身份验证",
    )
    if any(has_unnegated_phrase(phrase) for phrase in confirmation_phrases):
        return {
            "mode": "confirmation",
            "action": "external_action_confirmation",
            "label": "已进入待确认队列",
            "reason": "该指令会改变外部店铺、资金、账号安全或履约状态，不能静默执行。",
        }

    allowed_requested_actions = {
        "open_store_surface",
        "create_b2b_sales_execution_pack",
        "open_b2b_customer_pool",
        "open_b2b_output",
        "create_video_prompt_pack",
        "open_video_editor",
        "open_creative_output",
        "select_and_analyze_video",
        "analyze_video_path",
    }
    if requested_action in allowed_requested_actions:
        if requested_action == "select_and_analyze_video":
            return {
                "mode": "input",
                "action": requested_action,
                "label": "需要选择本地视频",
                "reason": "选择文件后才会开始关键帧、镜头和创意裂变分析。",
            }
        return {
            "mode": "tool",
            "action": requested_action,
            "surface": surface,
            "label": "已加入本机执行队列",
        }

    if platform and platform not in {"general", "b2b", "creative_video"}:
        store_words = (
            "打开店铺",
            "进入店铺",
            "打开后台",
            "seller center",
            "seller central",
        )
        surface_map = (
            (("打开订单", "查看订单", "进入订单"), "orders"),
            (("打开广告", "查看广告", "进入广告"), "ads"),
            (("打开优惠", "查看优惠", "打开活动", "查看活动"), "coupons"),
            (
                (
                    "打开库存",
                    "查看库存",
                    "进入库存",
                    "打开商品",
                    "查看商品",
                    "打开 listing",
                    "查看 listing",
                    "打开链接",
                ),
                "inventory",
            ),
        )
        chosen_surface = "home"
        matched = any(word in lowered for word in store_words)
        for words, candidate in surface_map:
            if any(word in lowered for word in words):
                chosen_surface = candidate
                matched = True
                break
        if matched:
            return {
                "mode": "tool",
                "action": "open_store_surface",
                "surface": chosen_surface,
                "label": f"已加入 {platform.upper()} 店铺连接检查队列",
            }

    if platform == "b2b":
        if any(word in lowered for word in ("打开客户池", "打开客户名单", "查看客户池")):
            return {
                "mode": "tool",
                "action": "open_b2b_customer_pool",
                "label": "已加入客户池打开队列",
            }
        if any(word in lowered for word in ("继续获客", "整理客户", "生成执行包", "生成获客包")):
            return {
                "mode": "tool",
                "action": "create_b2b_sales_execution_pack",
                "label": "已加入 B2B 本地执行队列",
            }

    if platform == "creative_video":
        if "视频" in lowered and any(word in lowered for word in ("分析", "拆解", "反推")):
            return {
                "mode": "input",
                "action": "select_and_analyze_video",
                "label": "需要选择本地视频",
                "reason": "选择视频后开始关键帧、镜头、提示词和创意裂变分析。",
            }
        if any(word in lowered for word in ("生成提示词", "生成分镜", "提示词包")):
            return {
                "mode": "tool",
                "action": "create_video_prompt_pack",
                "label": "已加入提示词与分镜生成队列",
            }
        if any(word in lowered for word in ("打开剪辑", "打开 capcut", "打开capcut", "打开剪映")):
            return {
                "mode": "tool",
                "action": "open_video_editor",
                "label": "已加入剪辑软件打开队列",
            }
        if any(word in lowered for word in ("打开产物", "查看产物", "打开输出")):
            return {
                "mode": "tool",
                "action": "open_creative_output",
                "label": "已加入视觉产物打开队列",
            }

    return {
        "mode": "analysis",
        "action": "model_analysis",
        "label": "交给当前任务模型分析",
    }


def create_task_run(
    root: Path,
    payload: dict[str, Any],
    *,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    task_id = str(payload.get("task_id") or "").strip().lower()
    task = _task(root, task_id)
    instruction = _clean_text(payload.get("message") or payload.get("instruction"))
    if not instruction:
        raise ValueError("请输入任务指令。")
    effective_task = dict(task)
    original_platform = str(task.get("platform") or "").strip().lower()
    explicit_platform = detect_explicit_platform_intent(instruction)
    bound_store = any(
        str(task.get(key) or "").strip()
        for key in ("store_binding_id", "store_id", "execution_identity_id")
    )
    platform_route_source = "task_scope"
    if explicit_platform and (platform_scope_is_generic(original_platform) or not bound_store):
        inferred_platform = explicit_platform["platform"]
        if inferred_platform != original_platform:
            effective_task["platform"] = inferred_platform
            effective_task["country"] = detect_country_site(instruction)
            effective_task["country_site"] = effective_task["country"]
            effective_task["store_model"] = ""
            effective_task["route_key"] = ""
        platform_route_source = "explicit_chat_intent"
    route = classify_task_instruction(
        task,
        instruction,
        requested_action=str(payload.get("requested_action") or ""),
        surface=str(payload.get("surface") or ""),
    )
    from .capability_context_manager import resolve_task_capability_context

    capability_task = dict(effective_task)
    # Per-run capability hints are allowed, but the persisted task owns its
    # project/platform/store scope.  A chat payload must not silently replace
    # that execution identity while selecting an Agent or Skill.
    for key in ("skill_refs", "assigned_agent_refs", "assigned_agent_id"):
        if payload.get(key):
            capability_task[key] = payload[key]
    capability_task["toolkit"] = task.get("toolkit") if isinstance(task.get("toolkit"), dict) else {}
    capability_context = resolve_task_capability_context(
        root.resolve(), capability_task, instruction
    )
    context_refs = _safe_context_refs({**task, **payload})
    context_refs.pop("assigned_agent_refs", None)
    context_refs.pop("skill_refs", None)
    if capability_context["selected_agent_refs"]:
        context_refs["assigned_agent_refs"] = list(capability_context["selected_agent_refs"])
        if not context_refs.get("assigned_agent_id"):
            context_refs["assigned_agent_id"] = str(
                capability_context["selected_agent_refs"][0]
            )
    if capability_context["selected_skill_refs"]:
        context_refs["skill_refs"] = list(capability_context["selected_skill_refs"])
    orchestration_plan = _orchestration_plan(
        root, effective_task, route, instruction, context_refs
    )
    status_by_mode = {
        "tool": "queued",
        "analysis": "analysis_pending",
        "confirmation": "needs_confirmation",
        "input": "needs_input",
    }
    now_dt = _utc_now()
    now = _iso(now_dt)
    runtime_instance_id = _clean_text(payload.get("_runtime_instance_id"), 120)
    analysis_lease = (
        _iso(now_dt + timedelta(seconds=DEFAULT_LEASE_SECONDS))
        if route["mode"] == "analysis" and runtime_instance_id
        else ""
    )
    run = {
        "id": "run-" + uuid.uuid4().hex[:16],
        "task_id": task_id,
        "task_name": str(task.get("name") or ""),
        "platform": str(effective_task.get("platform") or ""),
        "country": str(effective_task.get("country") or effective_task.get("country_site") or ""),
        "store_id": str(task.get("store_id") or ""),
        "tenant_id": str(task.get("tenant_id") or "local"),
        "workspace_id": str(task.get("workspace_id") or "local-workspace"),
        "project_id": str(task.get("project_id") or ""),
        "store_binding_id": str(task.get("store_binding_id") or ""),
        "execution_identity_id": str(task.get("execution_identity_id") or ""),
        "execution_domain": _execution_domain(effective_task, route),
        "store_model": str(effective_task.get("store_model") or ""),
        "ownership": str(effective_task.get("ownership") or ""),
        "route_key": str(effective_task.get("route_key") or ""),
        "product_id": str(task.get("product_id") or ""),
        "instruction": instruction,
        "mode": route["mode"],
        "action": route["action"],
        "surface": str(route.get("surface") or ""),
        "label": str(route.get("label") or ""),
        "reason": str(route.get("reason") or ""),
        "status": status_by_mode[route["mode"]],
        "actor": _clean_text(actor, 80),
        "created_at": now,
        "updated_at": now,
        "result_message": "",
        "error": "",
        "evidence_paths": [],
        "context_refs": context_refs,
        "orchestration_plan": orchestration_plan,
        "capability_context": capability_context,
        "assigned_agent_id": str(context_refs.get("assigned_agent_id") or ""),
        "approval_action_id": "",
        "approval_queue_path": "",
        "receipt_refs": [],
        "result_receipt": {},
        "execution_payload": _safe_execution_payload(payload),
        "store_scope_key": _store_scope_key(effective_task, route),
        "active_fingerprint": _active_fingerprint(effective_task, route, instruction),
        "original_task_platform": original_platform,
        "platform_route_source": platform_route_source,
        "platform_expert_id": str(explicit_platform.get("expert_id") or "") if explicit_platform else "",
        "platform_capability": infer_platform_capability(instruction) if explicit_platform else "",
        "idempotency_key": _clean_text(payload.get("idempotency_key"), 200),
        "fencing_token": 0,
        "attempt_count": 0,
        "max_attempts": _bounded_int(
            task.get("max_attempts"), 1, 10, DEFAULT_MAX_ATTEMPTS
        ),
        "recovery_count": 0,
        "next_retry_at": "",
        "dead_lettered_at": "",
        "last_error_code": "",
        "retry_backoff_seconds": 0,
        "queue_class": "",
        "queue_priority": 0,
        "lease_owner": runtime_instance_id if analysis_lease else "",
        "lease_expires_at": analysis_lease,
        "heartbeat_at": now if analysis_lease else "",
    }
    run["queue_class"] = _queue_class(run)
    run["queue_priority"] = _queue_priority(run)
    with _LOCK:
        connection = _connect(root)
        try:
            connection.execute("BEGIN IMMEDIATE")
            explicit_key = str(run.get("idempotency_key") or "").strip()
            if explicit_key:
                existing = connection.execute(
                    "SELECT * FROM task_runs WHERE idempotency_key = ?",
                    (explicit_key,),
                ).fetchone()
                if existing is not None:
                    connection.commit()
                    return dict(_decode_run(existing) or {})
            pending_retries = connection.execute(
                "SELECT * FROM task_runs WHERE active_fingerprint = ? AND status = 'needs_retry'",
                (run["active_fingerprint"],),
            ).fetchall()
            for retry_row in pending_retries:
                retry_run = _decode_run(retry_row)
                if retry_run is None:
                    continue
                retry_run["status"] = "superseded"
                retry_run["next_retry_at"] = ""
                retry_run["retry_backoff_seconds"] = 0
                retry_run["superseded_by_run_id"] = run["id"]
                retry_run["updated_at"] = now
                if _save_run(connection, retry_run):
                    _append_event(
                        connection,
                        retry_run,
                        "superseded_by_manual_retry",
                        {"replacement_run_id": run["id"]},
                    )
            active = connection.execute(
                """
                SELECT * FROM task_runs
                WHERE active_fingerprint = ? AND status IN (?, ?, ?)
                ORDER BY seq DESC LIMIT 1
                """,
                (run["active_fingerprint"], *ACTIVE_RUN_STATUSES),
            ).fetchone()
            if active is not None:
                connection.commit()
                return dict(_decode_run(active) or {})
            route_payload = dict(payload)
            route_payload.update(
                {
                    "platform": run["platform"],
                    "country": run["country"],
                    "country_site": run["country"],
                    "store_model": run["store_model"],
                    "route_key": run["route_key"],
                    "platform_expert_id": run["platform_expert_id"],
                    "platform_route_source": run["platform_route_source"],
                    "platform_capability": run["platform_capability"],
                }
            )
            run["execution_payload"] = _safe_execution_payload(route_payload, effective_task)
            _insert_run(connection, run)
            _append_event(
                connection,
                run,
                "created",
                {
                    "mode": run["mode"],
                    "action": run["action"],
                    "context_refs": run["context_refs"],
                    "task_type": str(orchestration_plan.get("task_type") or ""),
                    "action_class": str(orchestration_plan.get("action_class") or ""),
                    "plan_status": str(orchestration_plan.get("status") or ""),
                    "assigned_agent_id": run["assigned_agent_id"],
                },
            )
            _append_business_event(
                connection,
                _run_business_event_payload(
                    run,
                    kind="observation",
                    statement="任务已创建并完成本地路由；这条记录不代表外部平台已经执行。",
                    status=str(run.get("status") or "recorded"),
                    event_type="task_created",
                    payload={
                        "mode": run["mode"],
                        "action": run["action"],
                        "assigned_agent_id": run["assigned_agent_id"],
                        "external_side_effect_observed": False,
                    },
                ),
            )
            connection.commit()
            if run["mode"] == "confirmation":
                try:
                    action, queue_path = _enqueue_confirmation_action(root, run)
                    run["approval_action_id"] = str(action.get("action_id") or "")
                    run["approval_queue_path"] = queue_path.relative_to(root).as_posix()
                    run["updated_at"] = _now_iso()
                    if not _save_run(connection, run):
                        raise RuntimeError("待确认队列引用没有写回任务运行记录。")
                    _append_event(
                        connection,
                        run,
                        "approval_requested",
                        {
                            "approval_action_id": run["approval_action_id"],
                            "approval_queue_path": run["approval_queue_path"],
                            "external_execution_observed": False,
                        },
                    )
                    _append_business_event(
                        connection,
                        _run_business_event_payload(
                            run,
                            kind="draft",
                            statement="待确认动作已生成并进入本地审批队列；尚未执行外部动作。",
                            status="owner_review_required",
                            event_type="approval_requested",
                            payload={
                                "approval_action_id": run["approval_action_id"],
                                "external_side_effect_observed": False,
                            },
                        ),
                    )
                    connection.commit()
                except (OSError, RuntimeError, TypeError, ValueError) as exc:
                    run["status"] = "needs_configuration"
                    run["label"] = "待确认动作未能保存到本地队列"
                    run["error"] = _clean_text(exc, 1000)
                    run["updated_at"] = _now_iso()
                    _save_run(connection, run)
                    _append_event(
                        connection,
                        run,
                        "approval_queue_failed",
                        {"status": run["status"], "error": run["error"]},
                    )
                    connection.commit()
            return dict(run)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def update_task_run(
    root: Path,
    run_id: str,
    updates: dict[str, Any],
    *,
    worker_id: str = "",
    fencing_token: int | None = None,
) -> dict[str, Any]:
    run_id = str(run_id or "").strip().lower()
    if not SAFE_ID.fullmatch(run_id):
        raise ValueError("执行记录编号无效。")
    requested_status = _clean_text(updates.get("status"), 80).lower()
    allowed = {
        "status",
        "result_message",
        "error",
        "evidence_paths",
        "connector_evidence",
        "started_at",
        "finished_at",
        "model_provider",
        "model",
        "latency_ms",
        "fact_validated",
        "lease_owner",
        "lease_expires_at",
        "heartbeat_at",
        "last_started_at",
        "interrupted_at",
        "attempt_count",
        "recovery_count",
        "max_attempts",
        "next_retry_at",
        "dead_lettered_at",
        "last_error_code",
        "retry_backoff_seconds",
    }
    with _LOCK:
        connection = _connect(root)
        try:
            connection.execute("BEGIN IMMEDIATE")
            target_row = connection.execute(
                "SELECT * FROM task_runs WHERE id = ?", (run_id,)
            ).fetchone()
            target = _decode_run(target_row)
            if target is None:
                raise ValueError("执行记录不存在。")
            previous_status = str(target.get("status") or "").strip().lower()
            for key in allowed:
                if key not in updates:
                    continue
                if key == "evidence_paths":
                    values = updates.get(key) if isinstance(updates.get(key), list) else []
                    target[key] = [
                        _clean_text(item, 500)
                        for item in values
                        if _clean_text(item, 500)
                    ][:20]
                elif key == "connector_evidence":
                    raw_evidence = updates.get(key) if isinstance(updates.get(key), dict) else {}
                    clean_evidence: dict[str, Any] = {}
                    for evidence_key in (
                        "code",
                        "surface",
                        "observed_url",
                        "page_state",
                        "auth_required",
                        "browser_profile_seq",
                    ):
                        if evidence_key not in raw_evidence:
                            continue
                        value = raw_evidence.get(evidence_key)
                        if evidence_key == "auth_required":
                            clean_evidence[evidence_key] = bool(value)
                        elif evidence_key == "browser_profile_seq":
                            try:
                                clean_evidence[evidence_key] = max(0, int(value or 0))
                            except (TypeError, ValueError):
                                clean_evidence[evidence_key] = 0
                        else:
                            clean_value = _clean_text(value, 1000)
                            if evidence_key == "observed_url":
                                clean_value = clean_value.split("?", 1)[0].split("#", 1)[0]
                            if clean_value:
                                clean_evidence[evidence_key] = clean_value
                    target[key] = clean_evidence
                elif key == "latency_ms":
                    try:
                        target[key] = max(0, min(int(updates.get(key) or 0), 300_000))
                    except (TypeError, ValueError):
                        target[key] = 0
                elif key == "fact_validated":
                    target[key] = bool(updates.get(key))
                elif key in {
                    "attempt_count",
                    "recovery_count",
                    "fencing_token",
                    "retry_backoff_seconds",
                }:
                    try:
                        target[key] = max(0, int(updates.get(key) or 0))
                    except (TypeError, ValueError):
                        target[key] = 0
                elif key == "max_attempts":
                    target[key] = _bounded_int(
                        updates.get(key), 1, 10, DEFAULT_MAX_ATTEMPTS
                    )
                else:
                    target[key] = _clean_text(updates.get(key), 4000)
            now_dt = _utc_now()
            event_type = "updated"
            event_payload: dict[str, Any] = {"status": target.get("status")}
            if str(target.get("mode") or "") == "tool" and requested_status in {
                "failed",
                "needs_retry",
            }:
                attempts = max(0, int(target.get("attempt_count") or 0))
                max_attempts = _bounded_int(
                    target.get("max_attempts"), 1, 10, DEFAULT_MAX_ATTEMPTS
                )
                evidence = (
                    target.get("connector_evidence")
                    if isinstance(target.get("connector_evidence"), dict)
                    else {}
                )
                target["max_attempts"] = max_attempts
                target["last_error_code"] = _clean_text(
                    updates.get("last_error_code")
                    or evidence.get("code")
                    or "tool_execution_failed",
                    120,
                )
                target["lease_owner"] = ""
                target["lease_expires_at"] = ""
                target["heartbeat_at"] = ""
                if attempts >= max_attempts:
                    target["status"] = "dead_lettered"
                    target["dead_lettered_at"] = _iso(now_dt)
                    target["next_retry_at"] = ""
                    target["retry_backoff_seconds"] = 0
                    target["finished_at"] = str(target.get("finished_at") or _iso(now_dt))
                    event_type = "dead_lettered"
                    event_payload = {
                        "status": "dead_lettered",
                        "attempt_count": attempts,
                        "max_attempts": max_attempts,
                        "last_error_code": target["last_error_code"],
                    }
                else:
                    delay = _retry_delay_seconds(max(1, attempts))
                    target["status"] = "needs_retry"
                    target["next_retry_at"] = _iso(now_dt + timedelta(seconds=delay))
                    target["retry_backoff_seconds"] = delay
                    target["dead_lettered_at"] = ""
                    target["finished_at"] = ""
                    event_type = "retry_scheduled"
                    event_payload = {
                        "status": "needs_retry",
                        "attempt_count": attempts,
                        "max_attempts": max_attempts,
                        "retry_backoff_seconds": delay,
                        "next_retry_at": target["next_retry_at"],
                        "last_error_code": target["last_error_code"],
                    }
            elif requested_status in {
                "completed",
                "analysis_complete",
                "needs_input",
                "needs_configuration",
                "needs_confirmation",
                "cancelled",
                "superseded",
            }:
                target["next_retry_at"] = ""
                target["retry_backoff_seconds"] = 0
            terminal_receipt_statuses = {
                "completed",
                "analysis_complete",
                "failed",
                "cancelled",
                "dead_lettered",
            }
            final_status = str(target.get("status") or requested_status)
            if final_status in terminal_receipt_statuses:
                receipt_ref = f"task-run:{target['id']}:receipt:{final_status}"
                receipt_refs = [
                    _clean_text(item, 300)
                    for item in (
                        target.get("receipt_refs")
                        if isinstance(target.get("receipt_refs"), list)
                        else []
                    )
                    if _clean_text(item, 300)
                ][-19:]
                if receipt_ref not in receipt_refs:
                    receipt_refs.append(receipt_ref)
                target["receipt_refs"] = receipt_refs
                target_context = (
                    target.get("context_refs")
                    if isinstance(target.get("context_refs"), dict)
                    else {}
                )
                target["result_receipt"] = {
                    "receipt_ref": receipt_ref,
                    "status": final_status,
                    "result_message": _clean_text(target.get("result_message"), 2000),
                    "error": _clean_text(target.get("error"), 1000),
                    "evidence_paths": list(target.get("evidence_paths") or [])[:20],
                    "approval_action_id": str(target.get("approval_action_id") or ""),
                    "business_object_refs": list(
                        target_context.get("business_object_refs") or []
                    ),
                    "source_refs": list(
                        target_context.get("source_refs") or []
                    ),
                    "external_side_effect_observed": False,
                    "recorded_at": _now_iso(),
                }
                if event_type == "updated":
                    event_type = "result_receipt_recorded"
                event_payload.update(
                    {
                        "status": final_status,
                        "receipt_ref": receipt_ref,
                        "approval_action_id": str(target.get("approval_action_id") or ""),
                        "external_side_effect_observed": False,
                    }
                )
            target["updated_at"] = _iso(now_dt)
            if not _save_run(
                connection,
                target,
                worker_id=worker_id,
                fencing_token=fencing_token,
            ):
                raise RuntimeError("任务租约已失效，已阻止旧工作进程覆盖新结果。")
            _append_event(connection, target, event_type, event_payload)
            if final_status in terminal_receipt_statuses:
                business_kind = (
                    "inference" if final_status == "analysis_complete" else "fact"
                )
                statement = (
                    "模型分析结果已记录为推断；引用事实与外部执行仍需独立证据。"
                    if business_kind == "inference"
                    else f"任务结果回执已记录，状态为 {final_status}。"
                )
                _append_business_event(
                    connection,
                    _run_business_event_payload(
                        target,
                        kind=business_kind,
                        statement=statement,
                        status=final_status,
                        event_type=(
                            "task_analysis_recorded"
                            if business_kind == "inference"
                            else "task_result_recorded"
                        ),
                        payload={
                            "receipt_ref": str(
                                (target.get("result_receipt") or {}).get("receipt_ref")
                                or ""
                            ),
                            "external_side_effect_observed": False,
                        },
                    ),
                )
            elif (
                requested_status
                and final_status
                and final_status != previous_status
            ):
                _append_business_event(
                    connection,
                    _run_business_event_payload(
                        target,
                        kind="observation",
                        statement=(
                            f"任务状态已更新：{previous_status or 'unknown'} → "
                            f"{final_status}；这条记录不代表外部平台已经执行。"
                        ),
                        status=final_status,
                        event_type="task_status_changed",
                        payload={
                            "event_type": "task_status_changed",
                            "runtime_event_type": event_type,
                            "previous_status": previous_status,
                            "current_status": final_status,
                            "attempt_count": int(target.get("attempt_count") or 0),
                            "max_attempts": int(
                                target.get("max_attempts") or DEFAULT_MAX_ATTEMPTS
                            ),
                            "last_error_code": str(
                                target.get("last_error_code") or ""
                            ),
                            "next_retry_at": str(target.get("next_retry_at") or ""),
                            "external_side_effect_observed": False,
                        },
                    ),
                )
            connection.commit()
            return dict(target)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def record_task_approval_decision(
    root: Path,
    run_id: str,
    action: dict[str, Any],
    decision: str,
    *,
    note: str = "",
) -> dict[str, Any]:
    """Project an approval-center decision back onto its local task run.

    This function records state and evidence only.  It never executes an
    external action, submits a form, changes a budget, or uses a credential.
    """

    clean_run_id = str(run_id or "").strip().lower()
    clean_decision = str(decision or "").strip().lower()
    if not SAFE_ID.fullmatch(clean_run_id):
        raise ValueError("执行记录编号无效。")
    if clean_decision not in {"approve", "reject", "skip", "mark_executed"}:
        raise ValueError("审批决定无效。")
    action_id = _clean_text(action.get("action_id"), 240)
    if not action_id:
        raise ValueError("审批动作缺少 action_id。")
    with _LOCK:
        connection = _connect(root)
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM task_runs WHERE id = ?", (clean_run_id,)
            ).fetchone()
            target = _decode_run(row)
            if target is None:
                raise ValueError("审批动作对应的任务运行不存在。")
            expected_action_id = str(target.get("approval_action_id") or "")
            if expected_action_id and expected_action_id != action_id:
                raise ValueError("审批动作与任务运行不匹配。")
            action_status = _clean_text(action.get("status"), 120)
            status_by_decision = {
                "approve": "approved_pending_manual_execution",
                "reject": "rejected",
                "skip": "skipped",
                "mark_executed": (
                    "completed"
                    if action_status in {"manual_executed", "executed_recorded"}
                    else "execution_needs_evidence"
                ),
            }
            target["status"] = status_by_decision[clean_decision]
            target["approval_state"] = action_status
            target["approval_action_id"] = action_id
            history = (
                list(target.get("approval_history") or [])
                if isinstance(target.get("approval_history"), list)
                else []
            )
            history.append(
                {
                    "decision": clean_decision,
                    "status": action_status,
                    "note": _clean_text(note, 500),
                    "at": _now_iso(),
                }
            )
            target["approval_history"] = history[-20:]
            external_observed = (
                clean_decision == "mark_executed"
                and action_status in {"manual_executed", "executed_recorded"}
            )
            if external_observed:
                receipt_ref = f"task-run:{clean_run_id}:receipt:{action_id}"
                receipt_refs = [
                    _clean_text(item, 300)
                    for item in (
                        target.get("receipt_refs")
                        if isinstance(target.get("receipt_refs"), list)
                        else []
                    )
                    if _clean_text(item, 300)
                ]
                if receipt_ref not in receipt_refs:
                    receipt_refs.append(receipt_ref)
                target["receipt_refs"] = receipt_refs[-20:]
                context_refs = (
                    target.get("context_refs")
                    if isinstance(target.get("context_refs"), dict)
                    else {}
                )
                target["result_receipt"] = {
                    "receipt_ref": receipt_ref,
                    "status": "completed",
                    "approval_action_id": action_id,
                    "business_object_refs": list(
                        context_refs.get("business_object_refs") or []
                    ),
                    "source_refs": list(context_refs.get("source_refs") or []),
                    "execution_evidence_complete": bool(
                        action.get("execution_evidence_complete")
                    ),
                    "external_side_effect_observed": True,
                    "recorded_at": _now_iso(),
                }
            target["updated_at"] = _now_iso()
            if not _save_run(connection, target):
                raise RuntimeError("审批状态没有写回任务运行。")
            _append_event(
                connection,
                target,
                "approval_decision_recorded",
                {
                    "decision": clean_decision,
                    "action_id": action_id,
                    "action_status": action_status,
                    "run_status": target["status"],
                    "external_side_effect_observed": external_observed,
                },
            )
            _append_business_event(
                connection,
                _run_business_event_payload(
                    target,
                    kind="fact",
                    statement=f"负责人审批决定已记录：{clean_decision}。",
                    status=target["status"],
                    event_type="approval_decision_recorded",
                    payload={
                        "decision": clean_decision,
                        "action_id": action_id,
                        "external_side_effect_observed": external_observed,
                    },
                ),
            )
            connection.commit()
            return dict(target)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def _content_experiment_for_run(root: Path, run: dict[str, Any]) -> dict[str, Any] | None:
    workspace = root.resolve()
    for raw_path in reversed(run.get("evidence_paths") or []):
        candidate = Path(str(raw_path or ""))
        if candidate.suffix.lower() != ".json":
            continue
        candidate = candidate if candidate.is_absolute() else workspace / candidate
        try:
            resolved = candidate.resolve()
            resolved.relative_to(workspace)
            payload = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if (
            isinstance(payload, dict)
            and payload.get("prediction_status") == "immutable_blind_prediction"
            and payload.get("prediction_sha256")
        ):
            return payload
    return None


def record_creative_feedback(
    root: Path,
    payload: dict[str, Any],
    *,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    """Attach measured creative results to the exact completed local task run.

    This is an audit writeback only. It never publishes content, changes ad
    spend, or calls an external generation provider. Without a separately
    defined comparable experiment, the outcome intentionally stays
    ``inconclusive``.
    """
    run_id = str(payload.get("run_id") or "").strip().lower()
    if not SAFE_ID.fullmatch(run_id):
        raise ValueError("请输入有效的视觉任务运行记录编号。")
    asset_id = _clean_text(payload.get("asset_id") or payload.get("variant_id"), 200)
    variant_id = _clean_text(payload.get("variant_id"), 200)
    if not asset_id:
        raise ValueError("请输入素材或变体编号。")
    evidence_source = _clean_text(payload.get("evidence_source"), 80).lower()
    if evidence_source not in CREATIVE_FEEDBACK_SOURCES:
        raise ValueError("效果证据来源无效。")
    evidence_ref = _clean_text(payload.get("evidence_ref"), 1000)
    if not evidence_ref:
        raise ValueError("请输入可复核的证据文件、报表或只读页面引用。")
    window_start = _parse_iso(payload.get("window_start"))
    window_end = _parse_iso(payload.get("window_end"))
    measured_at = _parse_iso(payload.get("measured_at"))
    if window_start is None or window_end is None or measured_at is None:
        raise ValueError("请填写完整的统计开始、结束和采集时间。")
    if window_end < window_start:
        raise ValueError("统计结束时间不能早于开始时间。")

    raw_metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    metrics: dict[str, float | int] = {}
    for key, raw_value in raw_metrics.items():
        metric = str(key or "").strip().lower()
        if metric not in CREATIVE_FEEDBACK_METRICS or raw_value in (None, ""):
            continue
        if isinstance(raw_value, bool):
            raise ValueError(f"指标 {metric} 必须是非负数字。")
        try:
            value = float(str(raw_value).replace(",", ""))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"指标 {metric} 必须是非负数字。") from exc
        if not math.isfinite(value) or value < 0 or value > 1_000_000_000_000_000:
            raise ValueError(f"指标 {metric} 超出允许范围。")
        metrics[metric] = int(value) if value.is_integer() else round(value, 6)
    if not metrics:
        raise ValueError("至少填写一个可核验的效果指标。")
    currency = _clean_text(payload.get("currency"), 12).upper()
    if any(metric in metrics for metric in CREATIVE_MONETARY_METRICS) and not re.fullmatch(
        r"[A-Z]{3}", currency
    ):
        raise ValueError("包含花费、收入或退款时必须填写三位币种代码。")

    with _LOCK:
        connection = _connect(root)
        try:
            connection.execute("BEGIN IMMEDIATE")
            target = _decode_run(
                connection.execute("SELECT * FROM task_runs WHERE id = ?", (run_id,)).fetchone()
            )
            if target is None:
                raise ValueError("执行记录不存在。")
            if str(target.get("platform") or "") != "creative_video":
                raise ValueError("只能向视觉视频任务回写素材效果。")
            if str(target.get("status") or "") not in {"completed", "analysis_complete"}:
                raise ValueError("素材效果只能回写到已完成的视觉任务。")
            execution_payload = (
                target.get("execution_payload")
                if isinstance(target.get("execution_payload"), dict)
                else {}
            )
            feedback = {
                "id": "creative-feedback-" + uuid.uuid4().hex[:16],
                "run_id": run_id,
                "asset_id": asset_id,
                "variant_id": variant_id,
                "template_id": str(execution_payload.get("template_id") or ""),
                "generation_route_id": str(
                    execution_payload.get("generation_route_id") or "local_prompt_only"
                ),
                "evidence_source": evidence_source,
                "evidence_ref": evidence_ref,
                "window_start": _iso(window_start),
                "window_end": _iso(window_end),
                "measured_at": _iso(measured_at),
                "metrics": metrics,
                "currency": currency,
                "outcome_status": "inconclusive",
                "outcome_reason": "未绑定可比基线和实验定义，仅记录已观察指标。",
                "external_action_performed": False,
                "recorded_at": _now_iso(),
                "recorded_by": _clean_text(actor, 80),
                "scope": {
                    key: str(target.get(key) or "")
                    for key in (
                        "tenant_id",
                        "workspace_id",
                        "project_id",
                        "task_id",
                        "product_id",
                        "country",
                    )
                },
            }
            content_experiment = _content_experiment_for_run(root, target)
            if content_experiment is not None:
                from .content_feedback_loop import evaluate_content_observation

                feedback["content_experiment_observation"] = evaluate_content_observation(
                    content_experiment,
                    variant_id=variant_id or asset_id,
                    metrics=metrics,
                    evidence_ref=evidence_ref,
                    window_start=_iso(window_start),
                    window_end=_iso(window_end),
                )
            existing = (
                target.get("creative_feedback")
                if isinstance(target.get("creative_feedback"), list)
                else []
            )
            target["creative_feedback"] = [
                item for item in existing if isinstance(item, dict)
            ][-49:] + [feedback]
            target["updated_at"] = _now_iso()
            if not _save_run(connection, target):
                raise RuntimeError("素材效果回写失败。")
            _append_event(
                connection,
                target,
                "creative_feedback_recorded",
                {
                    "feedback_id": feedback["id"],
                    "asset_id": asset_id,
                    "outcome_status": feedback["outcome_status"],
                },
            )
            connection.commit()
            return {"run": dict(target), "feedback": feedback}
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def task_run(root: Path, run_id: str) -> dict[str, Any] | None:
    run_id = str(run_id or "").strip().lower()
    with _LOCK:
        connection = _connect(root)
        try:
            return _decode_run(
                connection.execute("SELECT * FROM task_runs WHERE id = ?", (run_id,)).fetchone()
            )
        finally:
            connection.close()


def task_run_context_lines_for_chat(
    root: Path,
    run_id: str,
    *,
    task_id: str = "",
    limit: int = 24,
) -> list[str]:
    """Build a bounded chat read model for one persisted task run.

    The caller must supply the run id.  When a task id is also supplied it
    must match the persisted run, which prevents a run from being projected
    into another task's chat context.
    """

    run = task_run(root.resolve(), run_id)
    if run is None:
        return []
    expected_task_id = str(task_id or "").strip().lower()
    actual_task_id = str(run.get("task_id") or "").strip().lower()
    if expected_task_id and expected_task_id != actual_task_id:
        return []

    bounded = max(1, min(int(limit or 24), 50))
    lines: list[str] = []
    refs = run.get("context_refs") if isinstance(run.get("context_refs"), dict) else {}
    object_refs = refs.get("business_object_refs")
    if isinstance(object_refs, list):
        for item in object_refs[:8]:
            if isinstance(item, dict):
                object_type = _clean_text(item.get("object_type"), 120)
                object_id = _clean_text(item.get("object_id"), 160)
                version_ref = _clean_text(item.get("version_ref"), 200)
                identity = ":".join(part for part in (object_type, object_id) if part)
                if identity:
                    suffix = f"（版本 {version_ref}）" if version_ref else ""
                    lines.append(f"结构化业务对象：{identity}{suffix}")
            else:
                text = _clean_text(item, 300)
                if text:
                    lines.append(f"结构化业务对象：{text}")

    source_refs = refs.get("source_refs")
    if isinstance(source_refs, list) and source_refs:
        sources = "；".join(_clean_text(item, 300) for item in source_refs[:6] if _clean_text(item, 300))
        if sources:
            lines.append(f"来源：{sources}")

    plan = run.get("orchestration_plan") if isinstance(run.get("orchestration_plan"), dict) else {}
    plan_parts = [
        _clean_text(plan.get("task_type"), 120),
        _clean_text(plan.get("action_class"), 120),
        _clean_text(plan.get("status"), 120),
    ]
    plan_summary = " · ".join(part for part in plan_parts if part)
    if plan_summary:
        lines.append(f"统一计划：{plan_summary}")
    if plan:
        lines.append(
            "执行边界：execution_allowed="
            f"{str(bool(plan.get('execution_allowed'))).lower()}；"
            f"external_action_count={int(plan.get('external_action_count') or 0)}"
        )

    capability_context = run.get("capability_context") if isinstance(run.get("capability_context"), dict) else {}
    compact_capabilities = capability_context.get("compact_context_lines")
    if isinstance(compact_capabilities, list):
        for item in compact_capabilities[:2]:
            text = _clean_text(item, 800)
            if text:
                lines.append(text)

    order_context = latest_shein_order_context_line(root, actual_task_id)
    if order_context:
        lines.append(order_context)

    manifest_ref = _clean_text(refs.get("attachment_manifest_ref"), 500)
    manifest_path: Path | None = None
    if manifest_ref:
        relative = Path(manifest_ref)
        if not relative.is_absolute() and ".." not in relative.parts:
            candidate = (root.resolve() / relative).resolve()
            try:
                candidate.relative_to(root.resolve())
            except ValueError:
                candidate = Path()
            if candidate.is_file():
                manifest_path = candidate
    if manifest_path is not None:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            manifest = {}
        if isinstance(manifest, dict):
            manifest_parts = [
                f"表格行={int(manifest.get('row_count') or 0)}",
                f"商品={int(manifest.get('product_count') or 0)}",
                f"变体={int(manifest.get('variant_count') or 0)}",
            ]
            dynamic_fields = manifest.get("dynamic_fields")
            if isinstance(dynamic_fields, list) and dynamic_fields:
                manifest_parts.append(
                    "动态字段="
                    + ",".join(
                        _clean_text(item, 80)
                        for item in dynamic_fields[:12]
                        if _clean_text(item, 80)
                    )
                )
            lines.append("附件清单：" + "；".join(manifest_parts))

        semantic_path = manifest_path.parent / "semantic-analysis.json"
        if semantic_path.is_file():
            try:
                semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
            except (OSError, TypeError, ValueError):
                semantic = {}
            if isinstance(semantic, dict):
                status = _clean_text(semantic.get("status"), 120)
                if status:
                    lines.append(f"附件语义路由：{status}")
                for key, label in (
                    ("observations", "可见观察"),
                    ("inferences", "待核推断"),
                    ("drafts", "待审草稿"),
                ):
                    values = semantic.get(key)
                    if not isinstance(values, list):
                        continue
                    for item in values[:6]:
                        statement = _clean_text(
                            item.get("statement") if isinstance(item, dict) else item,
                            500,
                        )
                        if statement:
                            lines.append(f"{label}：{statement}")
    return lines[:bounded]


def latest_shein_order_context_line(root: Path, task_id: str) -> str:
    """Project one exact task's latest PII-free order aggregate into AI context."""

    task_id = _clean_text(task_id, 96).lower()
    if not SAFE_ID.fullmatch(task_id):
        return ""
    try:
        task = _task(root, task_id)
        if str(task.get("platform") or "").strip().lower() != "shein":
            return ""
        path = task_local_folder(root, task) / "results" / "shein-order-summary-latest.json"
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if str(payload.get("task_id") or "").strip().lower() != task_id:
            return ""
        if str(payload.get("store_id") or "").strip() != str(task.get("store_id") or "").strip():
            return ""
        summary = payload.get("order_summary") if isinstance(payload.get("order_summary"), dict) else {}
        if summary.get("data_returned") is not True:
            return ""
        return (
            "SHEIN 只读订单汇总："
            f"店铺={_clean_text(payload.get('store_id'), 80)}；"
            f"日期={_clean_text(summary.get('window_start'), 24)} 至 {_clean_text(summary.get('window_end'), 24)}；"
            f"订单={max(0, int(summary.get('order_count') or 0))}；"
            f"商品件数={max(0, int(summary.get('unit_count') or 0))}；"
            f"商品总价={_clean_text(summary.get('gross_sales'), 40)}；"
            f"预计收入={_clean_text(summary.get('expected_income'), 40)}；"
            "不含订单号或客户个人信息；external_store_write_actions=0"
        )
    except (OSError, TypeError, ValueError):
        return ""


def task_run_events(
    root: Path,
    run_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    run_id = str(run_id or "").strip().lower()
    if not SAFE_ID.fullmatch(run_id):
        raise ValueError("Invalid task run id.")
    limit = max(1, min(int(limit or 50), 200))
    with _LOCK:
        connection = _connect(root)
        try:
            rows = connection.execute(
                "SELECT * FROM task_run_events WHERE run_id = ? ORDER BY seq DESC LIMIT ?",
                (run_id, limit),
            ).fetchall()
            events: list[dict[str, Any]] = []
            for row in rows:
                try:
                    payload = json.loads(str(row["payload_json"] or "{}"))
                except (TypeError, ValueError):
                    payload = {"decode_error": True}
                events.append(
                    {
                        "seq": int(row["seq"] or 0),
                        "run_id": str(row["run_id"] or ""),
                        "event_type": str(row["event_type"] or ""),
                        "actor": str(row["actor"] or ""),
                        "fencing_token": int(row["fencing_token"] or 0),
                        "created_at": str(row["created_at"] or ""),
                        "payload": payload if isinstance(payload, dict) else {},
                    }
                )
            return events
        finally:
            connection.close()


def recent_task_runs(root: Path, task_id: str, limit: int = 8) -> list[dict[str, Any]]:
    task_id = str(task_id or "").strip().lower()
    limit = max(1, min(int(limit or 8), 50))
    with _LOCK:
        connection = _connect(root)
        try:
            rows = connection.execute(
                "SELECT * FROM task_runs WHERE task_id = ? AND status != 'superseded' ORDER BY seq DESC LIMIT ?",
                (task_id, limit),
            ).fetchall()
            return [decoded for row in rows if (decoded := _decode_run(row)) is not None]
        finally:
            connection.close()


def claim_task_run(
    root: Path,
    run_id: str,
    worker_id: str,
    *,
    recovered: bool = False,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    run_id = str(run_id or "").strip().lower()
    worker_id = _clean_text(worker_id, 120)
    if not SAFE_ID.fullmatch(run_id) or not worker_id:
        raise ValueError("执行记录或工作进程编号无效。")
    current = _utc_now(now)
    with _LOCK:
        connection = _connect(root)
        try:
            connection.execute("BEGIN IMMEDIATE")
            target = _decode_run(
                connection.execute("SELECT * FROM task_runs WHERE id = ?", (run_id,)).fetchone()
            )
            if target is None:
                raise ValueError("执行记录不存在。")
            status = str(target.get("status") or "")
            if str(target.get("mode") or "") != "tool" or status not in {
                "queued",
                "running",
                "needs_retry",
            }:
                connection.commit()
                return None
            attempts = max(0, int(target.get("attempt_count") or 0))
            max_attempts = _bounded_int(
                target.get("max_attempts"), 1, 10, DEFAULT_MAX_ATTEMPTS
            )
            if status in {"running", "needs_retry"} and attempts >= max_attempts:
                if status == "running" and not _lease_expired(target, current):
                    connection.commit()
                    return None
                target["status"] = "dead_lettered"
                target["dead_lettered_at"] = _iso(current)
                target["next_retry_at"] = ""
                target["retry_backoff_seconds"] = 0
                target["lease_owner"] = ""
                target["lease_expires_at"] = ""
                target["updated_at"] = _iso(current)
                if _save_run(connection, target):
                    _append_event(
                        connection,
                        target,
                        "dead_lettered",
                        {
                            "attempt_count": attempts,
                            "max_attempts": max_attempts,
                            "reason": "retry_budget_exhausted",
                        },
                    )
                connection.commit()
                return None
            if status == "needs_retry":
                retry_at = _parse_iso(target.get("next_retry_at"))
                if retry_at is not None and retry_at > current:
                    connection.commit()
                    return None
            if status == "running" and not _lease_expired(target, current):
                connection.commit()
                return None
            occupied = connection.execute(
                """
                SELECT 1 FROM task_runs
                WHERE id != ? AND store_scope_key = ? AND status = 'running'
                  AND lease_expires_at > ? LIMIT 1
                """,
                (run_id, str(target.get("store_scope_key") or ""), _iso(current)),
            ).fetchone()
            if occupied is not None:
                connection.commit()
                return None
            target["status"] = "running"
            target["started_at"] = str(target.get("started_at") or _iso(current))
            target["last_started_at"] = _iso(current)
            target["heartbeat_at"] = _iso(current)
            target["lease_owner"] = worker_id
            target["next_retry_at"] = ""
            target["retry_backoff_seconds"] = 0
            target["lease_expires_at"] = _iso(
                current + timedelta(seconds=max(15, min(int(lease_seconds or DEFAULT_LEASE_SECONDS), 300)))
            )
            target["attempt_count"] = int(target.get("attempt_count") or 0) + 1
            target["fencing_token"] = int(target.get("fencing_token") or 0) + 1
            if recovered:
                target["recovery_count"] = int(target.get("recovery_count") or 0) + 1
            target["updated_at"] = _iso(current)
            if not _save_run(connection, target):
                raise RuntimeError("任务 claim 失败，记录已被其他工作进程修改。")
            _append_event(
                connection,
                target,
                "claimed",
                {"recovered": recovered, "worker_id": worker_id},
            )
            connection.commit()
            return dict(target)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def renew_task_run_lease(
    root: Path,
    run_id: str,
    worker_id: str,
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    fencing_token: int | None = None,
    now: datetime | None = None,
) -> bool:
    run_id = str(run_id or "").strip().lower()
    worker_id = _clean_text(worker_id, 120)
    current = _utc_now(now)
    with _LOCK:
        connection = _connect(root)
        try:
            connection.execute("BEGIN IMMEDIATE")
            target = _decode_run(
                connection.execute("SELECT * FROM task_runs WHERE id = ?", (run_id,)).fetchone()
            )
            if (
                target is None
                or str(target.get("status") or "") != "running"
                or str(target.get("lease_owner") or "") != worker_id
                or (
                    fencing_token is not None
                    and int(target.get("fencing_token") or 0) != int(fencing_token)
                )
            ):
                connection.rollback()
                return False
            target["heartbeat_at"] = _iso(current)
            target["lease_expires_at"] = _iso(
                current + timedelta(seconds=max(15, min(int(lease_seconds or DEFAULT_LEASE_SECONDS), 300)))
            )
            target["updated_at"] = _iso(current)
            if not _save_run(
                connection,
                target,
                worker_id=worker_id,
                fencing_token=int(target.get("fencing_token") or 0),
            ):
                connection.rollback()
                return False
            _append_event(connection, target, "lease_renewed")
            connection.commit()
            return True
        finally:
            connection.close()


def recoverable_task_runs(
    root: Path,
    *,
    now: datetime | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    current = _utc_now(now)
    limit = max(1, min(int(limit or 20), 100))
    candidate_limit = min(max(limit * 8, limit), 800)
    with _LOCK:
        connection = _connect(root)
        try:
            rows = connection.execute(
                """
                SELECT * FROM task_runs
                WHERE mode = 'tool' AND (
                    status = 'queued' OR
                    (status = 'needs_retry' AND (next_retry_at = '' OR next_retry_at <= ?)) OR
                    (status = 'running' AND (lease_expires_at = '' OR lease_expires_at <= ?))
                )
                ORDER BY queue_priority DESC, seq LIMIT ?
                """,
                (_iso(current), _iso(current), candidate_limit),
            ).fetchall()
            busy_store_keys = {
                str(row["store_scope_key"] or "")
                for row in connection.execute(
                    "SELECT DISTINCT store_scope_key FROM task_runs "
                    "WHERE status = 'running' AND lease_expires_at > ?",
                    (_iso(current),),
                ).fetchall()
            }
            candidates: list[dict[str, Any]] = []
            seen_store_keys: set[str] = set()
            for row in rows:
                decoded = _decode_run(row)
                if decoded is None:
                    continue
                store_key = str(decoded.get("store_scope_key") or "")
                if store_key in busy_store_keys or store_key in seen_store_keys:
                    continue
                decoded["queue_class"] = _queue_class(decoded)
                decoded["queue_priority"] = _queue_priority(decoded)
                candidates.append(decoded)
                seen_store_keys.add(store_key)

            selected: list[dict[str, Any]] = []
            for priority in sorted(
                {int(item.get("queue_priority") or 0) for item in candidates},
                reverse=True,
            ):
                priority_rows = [
                    item
                    for item in candidates
                    if int(item.get("queue_priority") or 0) == priority
                ]
                by_tenant: dict[str, list[dict[str, Any]]] = {}
                for item in priority_rows:
                    tenant_id = str(item.get("tenant_id") or "local")
                    by_tenant.setdefault(tenant_id, []).append(item)
                tenant_order = sorted(
                    by_tenant,
                    key=lambda tenant: str(by_tenant[tenant][0].get("created_at") or ""),
                )
                while tenant_order and len(selected) < limit:
                    next_order: list[str] = []
                    for tenant_id in tenant_order:
                        rows_for_tenant = by_tenant[tenant_id]
                        if rows_for_tenant:
                            selected.append(rows_for_tenant.pop(0))
                            if len(selected) >= limit:
                                break
                        if rows_for_tenant:
                            next_order.append(tenant_id)
                    tenant_order = next_order
                if len(selected) >= limit:
                    break
            return selected
        finally:
            connection.close()


def runtime_queue_snapshot(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    current = _utc_now(now)
    synthetic_probe = _synthetic_capacity_probe_summary(root)
    with _LOCK:
        connection = _connect(root)
        try:
            status_counts = {
                str(row["status"] or "unknown"): int(row["count"] or 0)
                for row in connection.execute(
                    "SELECT status, COUNT(*) AS count FROM task_runs GROUP BY status"
                ).fetchall()
            }
            queue_counts = {
                str(row["queue_class"] or "research_read"): int(row["count"] or 0)
                for row in connection.execute(
                    "SELECT queue_class, COUNT(*) AS count FROM task_runs "
                    "WHERE status IN ('queued', 'running', 'needs_retry') GROUP BY queue_class"
                ).fetchall()
            }
            ready_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM task_runs WHERE mode = 'tool' AND (
                        status = 'queued' OR
                        (status = 'needs_retry' AND (next_retry_at = '' OR next_retry_at <= ?)) OR
                        (status = 'running' AND (lease_expires_at = '' OR lease_expires_at <= ?))
                    )
                    """,
                    (_iso(current), _iso(current)),
                ).fetchone()[0]
            )
            retry_waiting_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM task_runs WHERE status = 'needs_retry' AND next_retry_at > ?",
                    (_iso(current),),
                ).fetchone()[0]
            )
            oldest_ready = connection.execute(
                """
                SELECT created_at FROM task_runs WHERE mode = 'tool' AND (
                    status = 'queued' OR
                    (status = 'needs_retry' AND (next_retry_at = '' OR next_retry_at <= ?)) OR
                    (status = 'running' AND (lease_expires_at = '' OR lease_expires_at <= ?))
                ) ORDER BY created_at LIMIT 1
                """,
                (_iso(current), _iso(current)),
            ).fetchone()
            return {
                "schema_version": 1,
                "generated_at": _iso(current),
                "storage": "sqlite_wal_single_host",
                "status_counts": status_counts,
                "queue_class_counts": queue_counts,
                "ready_count": ready_count,
                "retry_waiting_count": retry_waiting_count,
                "running_count": int(status_counts.get("running", 0)),
                "dead_letter_count": int(status_counts.get("dead_lettered", 0)),
                "oldest_ready_created_at": str(oldest_ready[0] or "") if oldest_ready else "",
                "capabilities": {
                    "durable_queue": True,
                    "explicit_idempotency_key": True,
                    "lease_and_fencing": True,
                    "same_store_serial_claim": True,
                    "retry_backoff": True,
                    "dead_letter": True,
                    "priority_classes": True,
                    "tenant_round_robin_within_priority": True,
                },
                "capacity_validated": False,
                "synthetic_capacity_probe": synthetic_probe,
                "capacity_boundary": (
                    "single_host_synthetic_100k_queue_depth_tested_not_100k_production_validated"
                    if synthetic_probe["validated"]
                    else "single_host_runtime_not_100k_load_tested"
                ),
                "worker_policy": runtime_worker_policy(root),
            }
        finally:
            connection.close()


def mark_stale_analysis_runs(
    root: Path,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    current = _utc_now(now)
    changed: list[dict[str, Any]] = []
    with _LOCK:
        connection = _connect(root)
        try:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT * FROM task_runs WHERE status = 'analysis_pending' AND (lease_expires_at = '' OR lease_expires_at <= ?)",
                (_iso(current),),
            ).fetchall()
            for row in rows:
                target = _decode_run(row)
                if target is None:
                    continue
                target["status"] = "needs_retry"
                target["error"] = "上次模型调用在桌面关闭或超时后中断；可从最近执行重新发送。"
                target["interrupted_at"] = _iso(current)
                target["lease_owner"] = ""
                target["lease_expires_at"] = ""
                target["updated_at"] = _iso(current)
                if _save_run(connection, target):
                    _append_event(connection, target, "analysis_stale")
                    changed.append(dict(target))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    return changed
