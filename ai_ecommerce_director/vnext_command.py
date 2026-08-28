from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .execution_loop import apply_approval_decision
from .product_data_intake import save_product_data_intake
from .task_execution_runtime import create_task_run
from .workspace_runtime import load_workspace_config


def _text(value: Any, limit: int = 1000) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _available_tasks(root: Path) -> list[dict[str, Any]]:
    workspace = load_workspace_config(root)
    tasks: list[dict[str, Any]] = []
    for project in workspace.get("projects", []):
        if not isinstance(project, dict):
            continue
        project_id = _text(project.get("id"), 80).lower()
        for task in project.get("tasks", []):
            if not isinstance(task, dict) or not task.get("id"):
                continue
            tasks.append({**task, "project_id": project_id})
    return tasks


def _select_task(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    tasks = _available_tasks(root)
    requested = _text(payload.get("task_id"), 80).lower()
    if requested:
        task = next((item for item in tasks if _text(item.get("id"), 80).lower() == requested), None)
        if task is None:
            raise ValueError("The requested T-one task does not exist in this local workspace.")
        return task
    # Amazon is intentionally paused. Prefer a generic, creative, advertising,
    # or B2B task so the default composer never resumes Amazon by accident.
    task = next(
        (
            item
            for item in tasks
            if _text(item.get("platform"), 80).lower() not in {"amazon", "amazon_us"}
        ),
        None,
    )
    if task is None:
        raise ValueError("No non-Amazon task is available. Add a project task in Settings first.")
    return task


def run_desktop_command(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    message = _text(payload.get("message"), 4000)
    files = payload.get("files") if isinstance(payload.get("files"), list) else []
    if not message and not files:
        raise ValueError("Enter an instruction or attach a file.")
    task = _select_task(root, payload)
    project_id = _text(task.get("project_id"), 80).lower()
    intake: dict[str, Any] | None = None
    if files:
        intake = save_product_data_intake(
            root,
            {
                "project_id": project_id,
                "files": files,
                "manual": {},
            },
        )
    context_refs = dict((intake or {}).get("context_refs") or {})
    stable_payload = json.dumps(
        {
            "task_id": task.get("id"),
            "message": message,
            "intake_id": (intake or {}).get("intake_id"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    run = create_task_run(
        root,
        {
            "task_id": task.get("id"),
            "message": message or "Read the attached product material and wait for the next instruction.",
            "surface": "t_one_vnext_desktop",
            "idempotency_key": "vnext-" + hashlib.sha256(stable_payload.encode("utf-8")).hexdigest(),
            **context_refs,
        },
        actor="desktop-owner",
    )
    run_status = _text(run.get("status"), 120)
    pending_approval_id = (
        _text(run.get("approval_action_id"), 240)
        if run_status == "needs_confirmation"
        else ""
    )
    return {
        "ok": True,
        "task": {
            "id": _text(task.get("id"), 80),
            "name": _text(task.get("name"), 240),
            "project_id": project_id,
            "platform": _text(task.get("platform"), 80),
            "country": _text(task.get("country") or task.get("country_site"), 80),
            "store_binding_id": _text(task.get("store_binding_id"), 160),
            "execution_identity_id": _text(task.get("execution_identity_id"), 300),
        },
        "intake": {
            "intake_id": _text((intake or {}).get("intake_id"), 160),
            "saved_file_count": int((intake or {}).get("saved_file_count") or 0),
            "manifest_path": _text((intake or {}).get("manifest_path"), 500),
        },
        "run": {
            "id": _text(run.get("id"), 160),
            "status": run_status,
            "mode": _text(run.get("mode"), 80),
            "label": _text(run.get("label"), 240),
            "approval_action_id": pending_approval_id,
            "store_scope_key": _text(run.get("store_scope_key"), 500),
            "context_refs": run.get("context_refs") if isinstance(run.get("context_refs"), dict) else {},
        },
        "external_action_performed": False,
    }


def decide_desktop_approval(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    action_id = _text(payload.get("action_id"), 240)
    decision = _text(payload.get("decision"), 40).lower()
    if not action_id:
        raise ValueError("Approval action id is required.")
    if decision not in {"approve", "reject", "skip"}:
        raise ValueError("Only approve, reject, or skip is allowed from the desktop review card.")
    result = apply_approval_decision(
        root,
        {
            "action_id": action_id,
            "decision": decision,
            "note": _text(payload.get("note"), 500),
        },
    )
    action = result.get("action") if isinstance(result.get("action"), dict) else {}
    run = result.get("task_run") if isinstance(result.get("task_run"), dict) else {}
    return {
        "ok": True,
        "decision": decision,
        "action": {
            "action_id": _text(action.get("action_id"), 240),
            "status": _text(action.get("status"), 160),
        },
        "run": {
            "id": _text(run.get("id"), 160),
            "status": _text(run.get("status"), 160),
        },
        "external_action_performed": False,
    }
