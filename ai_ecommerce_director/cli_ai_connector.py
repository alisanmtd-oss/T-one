from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .non_api_ai_bridge import (
    build_non_api_ai_handoff,
    record_non_api_ai_result,
    redact_sensitive_text,
)
from .workspace_runtime import (
    SAFE_ID,
    ensure_project_local_folder,
    load_workspace_config,
    workspace_item_context,
)


SUPPORTED_PROVIDER_ID = "codex-cli"
LUNA_ROUTE_ID = "codex-luna-cli"
LUNA_MODEL_ID = "gpt-5.6-luna"
SUPPORTED_ROUTES = {
    SUPPORTED_PROVIDER_ID: "",
    LUNA_ROUTE_ID: LUNA_MODEL_ID,
}
RUN_TIMEOUT_SECONDS = 300


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _discover_codex_cli() -> Path | None:
    candidates: list[str] = []
    if os.name == "nt":
        candidates.extend(
            value
            for value in (shutil.which("codex.cmd"), shutil.which("codex.exe"))
            if value
        )
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(str(Path(appdata) / "npm" / "codex.cmd"))
    else:
        resolved = shutil.which("codex")
        if resolved:
            candidates.append(resolved)
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.is_file() and path.name.lower() in {"codex", "codex.cmd", "codex.exe"}:
            return path.resolve()
    return None


def _probe(command: list[str], *, timeout: int = 15) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, str(exc)
    output = "\n".join(
        item.strip() for item in (completed.stdout, completed.stderr) if item.strip()
    )
    safe_output, _count = redact_sensitive_text(output)
    return int(completed.returncode), safe_output[:2000]


def cli_ai_connector_snapshot(root: Path, *, live_probe: bool = True) -> dict[str, Any]:
    executable = _discover_codex_cli()
    snapshot: dict[str, Any] = {
        "ok": True,
        "provider_id": SUPPORTED_PROVIDER_ID,
        "installed": executable is not None,
        "executable": str(executable or ""),
        "version": "",
        "authenticated": False,
        "authentication_status": "not_checked" if not live_probe else "unknown",
        "ready": False,
        "transport": "local_subprocess_stdin_jsonl",
        "sandbox": "read-only",
        "external_store_actions": 0,
    }
    if executable is None or not live_probe:
        return snapshot
    version_code, version_output = _probe([str(executable), "--version"])
    login_code, login_output = _probe([str(executable), "login", "status"])
    authenticated = login_code == 0 and "logged in" in login_output.casefold()
    snapshot.update(
        {
            "version": version_output.splitlines()[0] if version_code == 0 else "",
            "authenticated": authenticated,
            "authentication_status": "authenticated" if authenticated else "not_authenticated",
            "ready": version_code == 0 and authenticated,
            "probe_error": "" if version_code == 0 and login_code == 0 else login_output or version_output,
        }
    )
    return snapshot


def _find_project(root: Path, project_id: str) -> dict[str, Any]:
    normalized = str(project_id or "").strip().lower()
    if not SAFE_ID.fullmatch(normalized):
        raise ValueError("请选择有效的 T One 项目。")
    for project in load_workspace_config(root).get("projects", []):
        if isinstance(project, dict) and str(project.get("id") or "").strip().lower() == normalized:
            return dict(project)
    raise ValueError("所选项目不存在，不能启动 CLI 回传。")


def _agent_message_from_events(stdout: str) -> tuple[str, str, list[dict[str, Any]]]:
    final_text = ""
    thread_id = ""
    events: list[dict[str, Any]] = []
    for line in str(stdout or "").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        events.append(event)
        if event.get("type") == "thread.started":
            thread_id = str(event.get("thread_id") or "")
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            final_text = str(item.get("text") or "").strip()
    return final_text, thread_id, events


def run_cli_ai_roundtrip(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    route_id = str(payload.get("provider_id") or SUPPORTED_PROVIDER_ID).strip().lower()
    if route_id not in SUPPORTED_ROUTES:
        raise ValueError("当前真实 CLI 闭环只支持 Codex CLI 及其已验证模型路由。")
    model = SUPPORTED_ROUTES[route_id]
    requested_model = str(payload.get("model") or model).strip()
    if requested_model != model:
        raise ValueError("请选择已验证的 Codex CLI 模型路由。")
    if payload.get("owner_confirmed") is not True:
        raise ValueError("本次外部 AI 调用需要负责人明确确认。")

    raw_message = str(payload.get("message") or "").strip()
    if not raw_message:
        raise ValueError("请输入要发送给 Codex CLI 的项目任务。")
    safe_message, redaction_count = redact_sensitive_text(raw_message)
    project = _find_project(root, str(payload.get("project_id") or ""))
    project_id = str(project.get("id") or "").strip().lower()
    task_id = str(payload.get("task_id") or "cli-roundtrip").strip().lower()[:80]
    project_folder, relative_project_folder = ensure_project_local_folder(root, project)
    workspace_context = workspace_item_context(root, "project", project_id)

    snapshot = cli_ai_connector_snapshot(root, live_probe=True)
    if not snapshot.get("ready"):
        raise ValueError(
            "Codex CLI 尚未达到可调用状态："
            + str(snapshot.get("probe_error") or snapshot.get("authentication_status") or "unknown")
        )
    executable = Path(str(snapshot["executable"]))

    handoff = build_non_api_ai_handoff(
        root,
        {
            "provider_id": SUPPORTED_PROVIDER_ID,
            "project_id": project_id,
            "task_id": task_id,
            "message": safe_message,
            "requested_action": (
                f"codex_exec_read_only:{model}" if model else "codex_exec_read_only"
            ),
            "approved_auto_delivery": True,
        },
    )["handoff"]
    now = _utc_now()
    digest = hashlib.sha256(
        f"{project_id}|{task_id}|{handoff['id']}|{now}".encode("utf-8")
    ).hexdigest()
    run_id = f"{route_id}-{digest[:16]}"
    run_dir = project_folder / "runs" / "codex_cli" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    input_path = run_dir / "input.json"
    events_path = run_dir / "events.jsonl"
    receipt_path = project_folder / "receipts" / f"{run_id}.json"
    local_result_path = project_folder / "results" / f"{run_id}.json"

    prompt = (
        "You are responding to a T One project task. Do not modify files, do not call external "
        "business systems, and do not perform store, advertising, payment, shipping, publishing, "
        "or outreach actions. Return a concise final answer in Chinese.\n\n"
        f"项目：{project.get('name') or project_id}\n"
        f"任务：{task_id}\n"
        f"项目资料入口：{workspace_context['entry_manifest']}\n"
        "只在当前项目目录内按需读取入口清单指向的 inputs、attachments、knowledge、memory；"
        "不要遍历项目目录之外。\n\n"
        f"{safe_message}"
    )
    input_record = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": now,
        "provider_id": SUPPORTED_PROVIDER_ID,
        "route_id": route_id,
        "model": model,
        "project_id": project_id,
        "task_id": task_id,
        "message": safe_message,
        "redaction_count": redaction_count,
        "handoff_id": handoff["id"],
        "local_project_folder": relative_project_folder,
        "workspace_context": workspace_context,
        "owner_confirmed": True,
        "sandbox": "read-only",
    }
    input_path.write_text(
        json.dumps(input_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    command = [
        str(executable),
        "exec",
        "--json",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--color",
        "never",
        "-C",
        str(project_folder),
    ]
    if model:
        command.extend(["--model", model])
    command.append("-")
    started_at = _utc_now()
    try:
        completed = subprocess.run(
            command,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=RUN_TIMEOUT_SECONDS,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        stdout, _stdout_redactions = redact_sensitive_text(completed.stdout)
        stderr, _stderr_redactions = redact_sensitive_text(completed.stderr)
        exit_code = int(completed.returncode)
        final_text, thread_id, events = _agent_message_from_events(stdout)
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout, _stdout_redactions = redact_sensitive_text(str(exc.stdout or ""))
        stderr, _stderr_redactions = redact_sensitive_text(str(exc.stderr or ""))
        exit_code = -1
        final_text, thread_id, events = _agent_message_from_events(stdout)
        timed_out = True

    events_path.write_text(stdout, encoding="utf-8")
    turn_completed = any(event.get("type") == "turn.completed" for event in events)
    completed_before_process_timeout = bool(final_text and turn_completed)
    error_text = ""
    if timed_out and not completed_before_process_timeout:
        error_text = f"Codex CLI 在 {RUN_TIMEOUT_SECONDS} 秒内没有完成。"
    elif exit_code != 0 and not completed_before_process_timeout:
        error_text = stderr.strip() or f"Codex CLI 退出码 {exit_code}。"
    elif not final_text:
        error_text = "Codex CLI 已结束，但 JSONL 事件中没有最终回复。"

    recorded = record_non_api_ai_result(
        root,
        {
            "handoff_id": handoff["id"],
            "result_text": final_text,
            "error_text": error_text,
            "status": "received" if final_text and not error_text else "failed",
            "external_action_performed": True,
            "source_receipt": {
                "command": (
                    f"codex exec --model {model} --json --ephemeral --sandbox read-only -"
                    if model
                    else "codex exec --json --ephemeral --sandbox read-only -"
                ),
                "exit_code": exit_code,
                "external_thread_url": f"codex://thread/{thread_id}" if thread_id else "",
                "window_title": str(snapshot.get("version") or "Codex CLI"),
                "captured_by": "t_one_codex_cli_connector",
            },
        },
    )
    finished_at = _utc_now()
    receipt = {
        "schema_version": 1,
        "run_id": run_id,
        "provider_id": SUPPORTED_PROVIDER_ID,
        "route_id": route_id,
        "model": model,
        "project_id": project_id,
        "task_id": task_id,
        "handoff_id": handoff["id"],
        "thread_id": thread_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "turn_completed": turn_completed,
        "completed_before_process_timeout": completed_before_process_timeout,
        "event_count": len(events),
        "status": "completed" if final_text and not error_text else "failed",
        "input_path": _safe_relative(input_path, root),
        "events_path": _safe_relative(events_path, root),
        "result_path": _safe_relative(local_result_path, root),
        "bridge_result_path": str(recorded.get("result", {}).get("result_path") or ""),
        "sandbox": "read-only",
        "external_ai_call_count": 1,
        "external_store_action_count": 0,
    }
    local_result = {
        **receipt,
        "result_text": final_text,
        "error_text": error_text,
        "review_status": "needs_owner_review",
        "fact_status": "unverified_external_ai_output",
    }
    local_result_path.write_text(
        json.dumps(local_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "ok": bool(final_text and not error_text),
        "run": local_result,
        "connector": snapshot,
        "handoff": handoff,
        "bridge_result": recorded.get("result") or {},
        "message": final_text or error_text,
    }
