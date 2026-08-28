from __future__ import annotations

import hashlib
import json
import re
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .non_api_ai_bridge import build_non_api_ai_handoff, record_non_api_ai_result


JOB_DIR = Path("runtime_data") / "browser_ai_jobs"
HEARTBEAT_PATH = Path("runtime_data") / "browser_ai_extension_heartbeat.json"
CONVERSATION_REGISTRY_PATH = Path("runtime_data") / "browser_ai_conversations.json"
SUPPORTED_PROVIDERS = {
    "chatgpt-browser": "chatgpt",
    "gemini-browser": "gemini",
}
NATIVE_SCRIPT = Path("scripts") / "browser_ai_native_roundtrip.ps1"
JOB_TTL_SECONDS = 15 * 60
HEARTBEAT_TTL_SECONDS = 90

_BROWSER_AI_UI_PLACEHOLDERS = {
    "正在思考",
    "思考中",
    "继续追问",
    "停止生成",
    "重新生成",
    "chatgpt也可能会犯错",
    "thinking",
    "continue",
    "askfollowup",
    "stopgenerating",
    "regenerate",
}


def _clean_browser_ai_result_text(value: Any) -> str:
    """Remove browser controls while requiring at least one real response line."""
    substantive_lines: list[str] = []
    for raw_line in str(value or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        canonical = re.sub(r"[\s。….!！?？:：]+", "", line).casefold()
        if canonical in _BROWSER_AI_UI_PLACEHOLDERS:
            continue
        substantive_lines.append(line)
    return "\n".join(substantive_lines).strip()


def _capability_context_lines(handoff: dict[str, Any]) -> list[str]:
    return [
        str(item)
        for item in handoff.get("task_context_lines", [])
        if str(item).startswith(("任务已配置能力", "本轮按需能力"))
    ]


def _extension_version_key(value: Any) -> tuple[int, ...]:
    parts = [int(item) for item in re.findall(r"\d+", str(value or ""))[:4]]
    return tuple(parts) if parts else (0,)


def _conversation_key(provider_id: str, project_id: str, task_id: str) -> str:
    return ":".join(
        (
            str(project_id or "").strip().lower() or "unscoped-project",
            str(task_id or "").strip().lower() or "unscoped-task",
            str(provider_id or "").strip().lower(),
        )
    )


def _safe_thread_url(provider_id: str, value: Any) -> str:
    url = str(value or "").strip()
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    if parsed.scheme != "https":
        return ""
    host = parsed.hostname or ""
    if provider_id == "chatgpt-browser":
        return (
            f"https://{host}{parsed.path}"
            if host == "chatgpt.com" and "/c/" in parsed.path
            else ""
        )
    if provider_id == "gemini-browser":
        return (
            f"https://{host}{parsed.path}"
            if host == "gemini.google.com" and parsed.path.startswith("/app/")
            else ""
        )
    return ""


def _conversation_url(root: Path, conversation_key: str, provider_id: str) -> str:
    registry = _read_json(root / CONVERSATION_REGISTRY_PATH)
    entries = registry.get("entries") if isinstance(registry.get("entries"), dict) else {}
    record = entries.get(conversation_key) if isinstance(entries.get(conversation_key), dict) else {}
    return _safe_thread_url(provider_id, record.get("external_thread_url"))


def _remember_conversation(
    root: Path,
    *,
    conversation_key: str,
    provider_id: str,
    project_id: str,
    task_id: str,
    external_thread_url: str,
) -> None:
    safe_url = _safe_thread_url(provider_id, external_thread_url)
    if not safe_url:
        return
    path = root / CONVERSATION_REGISTRY_PATH
    registry = _read_json(path)
    entries = registry.get("entries") if isinstance(registry.get("entries"), dict) else {}
    entries[conversation_key] = {
        "provider_id": provider_id,
        "project_id": project_id,
        "task_id": task_id,
        "external_thread_url": safe_url,
        "updated_at": _utc_now(),
    }
    _write_json_atomic(
        path,
        {"schema_version": 1, "entries": entries, "updated_at": _utc_now()},
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _job_path(root: Path, job_id: str) -> Path:
    normalized = str(job_id or "").strip()
    if not normalized.startswith("browser-ai-") or not normalized.replace("-", "").isalnum():
        raise ValueError("Invalid browser AI job id.")
    return root / JOB_DIR / f"{normalized}.json"


def record_browser_ai_heartbeat(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    providers = payload.get("providers") if isinstance(payload.get("providers"), dict) else {}
    clean: dict[str, dict[str, Any]] = {}
    for surface in ("chatgpt", "gemini"):
        item = providers.get(surface) if isinstance(providers.get(surface), dict) else {}
        clean[surface] = {
            "tab_found": bool(item.get("tab_found")),
            "composer_found": bool(item.get("composer_found")),
            "page_title": str(item.get("page_title") or "")[:200],
        }
    heartbeat_path = root / HEARTBEAT_PATH
    existing = _read_json(heartbeat_path)
    existing_version = str(existing.get("extension_version") or "")
    incoming_version = str(payload.get("extension_version") or "")[:40]
    try:
        existing_age = max(
            0.0,
            time.time() - datetime.fromisoformat(str(existing.get("received_at") or "")).timestamp(),
        )
    except ValueError:
        existing_age = float("inf")
    if (
        existing_age <= HEARTBEAT_TTL_SECONDS
        and _extension_version_key(existing_version) > _extension_version_key(incoming_version)
    ):
        return {
            "ok": True,
            "heartbeat": existing,
            "ignored_older_extension": True,
            "ignored_extension_version": incoming_version,
        }
    extension_instance_id = str(payload.get("extension_instance_id") or "").strip().lower()
    if not re.fullmatch(r"[a-p]{32}", extension_instance_id):
        extension_instance_id = ""
    heartbeat = {
        "schema_version": 1,
        "received_at": _utc_now(),
        "extension_version": incoming_version,
        "extension_instance_id": extension_instance_id,
        "browser_session_mode": "existing_logged_profile",
        "providers": clean,
    }
    _write_json_atomic(heartbeat_path, heartbeat)
    return {"ok": True, "heartbeat": heartbeat}


def browser_ai_connector_snapshot(root: Path) -> dict[str, Any]:
    heartbeat = _read_json(root / HEARTBEAT_PATH)
    received_at = str(heartbeat.get("received_at") or "")
    try:
        age_seconds = max(
            0.0,
            time.time() - datetime.fromisoformat(received_at).timestamp(),
        )
    except ValueError:
        age_seconds = float("inf")
    heartbeat_live = age_seconds <= HEARTBEAT_TTL_SECONDS
    providers = heartbeat.get("providers") if isinstance(heartbeat.get("providers"), dict) else {}
    bridge = _read_json(root / "config" / "web_ai_bridge.json")
    configured_providers = {
        str(item.get("id") or ""): item
        for item in bridge.get("providers", [])
        if isinstance(item, dict)
    }
    native_runtime_available = sys.platform == "win32" and (root / NATIVE_SCRIPT).is_file()
    availability = {}
    for provider_id, surface in SUPPORTED_PROVIDERS.items():
        state = providers.get(surface) if isinstance(providers.get(surface), dict) else {}
        configured = configured_providers.get(provider_id, {})
        native_verified = bool(
            native_runtime_available
            and configured.get("automation_verified") is True
            and configured.get("connector_implementation_verified") is True
            and configured.get("external_action_authorized") is True
        )
        extension_ready = bool(
            heartbeat_live and state.get("tab_found") and state.get("composer_found")
        )
        availability[provider_id] = {
            "provider_id": provider_id,
            "surface": surface,
            "ready": native_verified or extension_ready,
            "native_visible_verified": native_verified,
            "extension_dom_ready": extension_ready,
            "default_delivery_method": (
                "chrome_extension_content_script"
                if extension_ready
                else "windows_uia_visible_keyboard"
            ),
            "tab_found": bool(state.get("tab_found")),
            "composer_found": bool(state.get("composer_found")),
            "page_title": str(state.get("page_title") or ""),
        }
    return {
        "ok": True,
        "status": "connected_existing_login" if any(item["ready"] for item in availability.values()) else "not_connected",
        "heartbeat_live": heartbeat_live,
        "heartbeat_age_seconds": None if age_seconds == float("inf") else round(age_seconds, 1),
        "browser_session_mode": "existing_logged_profile",
        "native_runtime_available": native_runtime_available,
        "connection_rechecked_per_run": True,
        "providers": availability,
        "cookie_or_password_read": False,
        "new_browser_profile_created": False,
    }


def queue_browser_ai_roundtrip(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    provider_id = str(payload.get("provider_id") or "").strip()
    if provider_id not in SUPPORTED_PROVIDERS:
        raise ValueError("Only verified ChatGPT Browser and Gemini Browser connectors are supported.")
    if payload.get("owner_confirmed") is not True:
        raise ValueError("Owner confirmation is required before sending to an external web AI.")
    message = str(payload.get("message") or "").strip()
    if not message:
        raise ValueError("Please enter a message for the external web AI.")
    snapshot = browser_ai_connector_snapshot(root)
    verification_mode = payload.get("verification_mode") is True
    if not verification_mode and not snapshot["providers"][provider_id]["ready"]:
        raise ValueError("The existing logged-in browser tab is not connected to T One.")

    handoff_result = build_non_api_ai_handoff(
        root,
        {
            "provider_id": provider_id,
            "project_id": str(payload.get("project_id") or ""),
            "task_id": str(payload.get("task_id") or "browser-ai-roundtrip"),
            "message": message,
            "requested_action": "send_message_and_read_visible_response",
            "approved_auto_delivery": True,
        },
    )
    handoff = handoff_result["handoff"]
    if not verification_mode and not handoff.get("can_auto_deliver"):
        raise ValueError("The browser connector has not completed automation verification.")

    created_at = _utc_now()
    project_id = str(payload.get("project_id") or "")
    task_id = str(payload.get("task_id") or "browser-ai-roundtrip")
    conversation_key = _conversation_key(provider_id, project_id, task_id)
    digest = hashlib.sha256(
        f"{provider_id}|{handoff['id']}|{created_at}|{secrets.token_hex(8)}".encode("utf-8")
    ).hexdigest()[:20]
    job_id = f"browser-ai-{digest}"
    job = {
        "schema_version": 1,
        "id": job_id,
        "claim_token": secrets.token_urlsafe(24),
        "provider_id": provider_id,
        "surface": SUPPORTED_PROVIDERS[provider_id],
        "project_id": project_id,
        "task_id": task_id,
        "conversation_key": conversation_key,
        "conversation_url": _conversation_url(root, conversation_key, provider_id),
        "handoff_id": handoff["id"],
        "prompt": str(handoff.get("prompt_packet") or handoff.get("message") or ""),
        "status": "pending",
        "created_at": created_at,
        "updated_at": created_at,
        "expires_at_epoch": time.time() + JOB_TTL_SECONDS,
        "verification_mode": verification_mode,
        "external_store_action_count": 0,
        "task_context_shared": bool(handoff.get("task_context_available")),
        "capability_context_lines": _capability_context_lines(handoff),
    }
    _write_json_atomic(_job_path(root, job_id), job)
    return {"ok": True, "job": {k: v for k, v in job.items() if k != "claim_token"}}


def claim_next_browser_ai_job(root: Path, surface: str) -> dict[str, Any]:
    normalized_surface = str(surface or "").strip().lower()
    if normalized_surface not in SUPPORTED_PROVIDERS.values():
        raise ValueError("Unsupported browser AI surface.")
    now = time.time()
    job_dir = root / JOB_DIR
    if not job_dir.exists():
        return {"ok": True, "job": None}
    for path in sorted(job_dir.glob("browser-ai-*.json"), key=lambda item: item.stat().st_mtime):
        job = _read_json(path)
        if job.get("surface") != normalized_surface or job.get("status") not in {"pending", "claimed"}:
            continue
        if float(job.get("expires_at_epoch") or 0) < now:
            job["status"] = "expired"
            job["updated_at"] = _utc_now()
            _write_json_atomic(path, job)
            continue
        job["status"] = "claimed"
        job["claimed_at"] = _utc_now()
        job["updated_at"] = job["claimed_at"]
        _write_json_atomic(path, job)
        return {
            "ok": True,
            "job": {
                "id": job["id"],
                "claim_token": job["claim_token"],
                "surface": job["surface"],
                "prompt": job["prompt"],
                "conversation_key": str(job.get("conversation_key") or ""),
                "conversation_url": str(job.get("conversation_url") or ""),
            },
        }
    return {"ok": True, "job": None}


def complete_browser_ai_job(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path = _job_path(root, str(payload.get("job_id") or ""))
    job = _read_json(path)
    if not job or not secrets.compare_digest(
        str(job.get("claim_token") or ""), str(payload.get("claim_token") or "")
    ):
        raise ValueError("Browser AI job receipt token is invalid.")
    if job.get("status") == "completed":
        return {"ok": True, "job": job, "deduplicated": True}
    raw_result_text = str(payload.get("result_text") or "").strip()
    result_text = _clean_browser_ai_result_text(raw_result_text)
    error_text = str(payload.get("error_text") or "").strip()
    if raw_result_text and not result_text and not error_text:
        error_text = (
            "Browser AI returned only a loading/control placeholder; "
            "no completed response was captured."
        )
    if not result_text and not error_text:
        raise ValueError("Browser AI returned neither result text nor error text.")
    external_thread_url = _safe_thread_url(
        str(job.get("provider_id") or ""), payload.get("external_thread_url")
    )
    if result_text and external_thread_url:
        _remember_conversation(
            root,
            conversation_key=str(job.get("conversation_key") or ""),
            provider_id=str(job.get("provider_id") or ""),
            project_id=str(job.get("project_id") or ""),
            task_id=str(job.get("task_id") or ""),
            external_thread_url=external_thread_url,
        )
    recorded = record_non_api_ai_result(
        root,
        {
            "handoff_id": job["handoff_id"],
            "result_text": result_text,
            "error_text": error_text,
            "status": "received" if result_text else "failed",
            "external_action_performed": True,
            "source_receipt": {
                "external_thread_url": external_thread_url,
                "window_title": str(payload.get("window_title") or ""),
                "captured_by": "t_one_existing_login_browser_extension",
                "delivery_method": "chrome_extension_content_script",
                "browser_session_mode": "existing_logged_profile",
            },
        },
    )
    job["status"] = "completed" if result_text else "failed"
    job["updated_at"] = _utc_now()
    job["result_id"] = str(recorded.get("result", {}).get("id") or "")
    job["result_text"] = result_text
    job["error_text"] = error_text
    job["external_thread_url"] = external_thread_url
    job["delivery_method"] = "chrome_extension_content_script"
    job["browser_session_mode"] = "existing_logged_profile"
    job["submission_confirmed"] = bool(result_text)
    job["conversation_reused"] = bool(
        external_thread_url
        and str(job.get("conversation_url") or "") == external_thread_url
    )
    job.pop("claim_token", None)
    _write_json_atomic(path, job)
    return {"ok": True, "job": job, "recorded": recorded}


def run_native_browser_ai_roundtrip(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    provider_id = str(payload.get("provider_id") or "").strip()
    if provider_id not in SUPPORTED_PROVIDERS:
        raise ValueError("Only ChatGPT Browser and Gemini Browser are supported.")
    if payload.get("owner_confirmed") is not True:
        raise ValueError("Owner confirmation is required before sending to an external web AI.")
    message = str(payload.get("message") or "").strip()
    if not message:
        raise ValueError("Please enter a message for the external web AI.")
    script = root / NATIVE_SCRIPT
    if sys.platform != "win32" or not script.is_file():
        raise RuntimeError("The visible Windows browser connector is unavailable on this machine.")

    project_id = str(payload.get("project_id") or "").strip()
    task_id = str(payload.get("task_id") or "browser-ai-roundtrip").strip()
    handoff = build_non_api_ai_handoff(
        root,
        {
            "provider_id": provider_id,
            "project_id": project_id,
            "task_id": task_id,
            "message": message,
            "requested_action": "send_message_and_read_visible_response",
            "approved_auto_delivery": True,
        },
    )["handoff"]
    run_id = f"native-{hashlib.sha256((handoff['id'] + _utc_now()).encode('utf-8')).hexdigest()[:18]}"
    run_dir = root / JOB_DIR / "native"
    prompt_path = run_dir / f"{run_id}.prompt.txt"
    output_path = run_dir / f"{run_id}.result.json"
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_text = str(
        handoff.get("prompt_packet")
        if handoff.get("task_context_available")
        else handoff.get("message") or message
    ).strip()
    prompt_path.write_text(prompt_text, encoding="utf-8")
    conversation_key = _conversation_key(provider_id, project_id, task_id)
    conversation_url = _conversation_url(root, conversation_key, provider_id)
    timeout_seconds = min(max(int(payload.get("timeout_seconds") or 180), 30), 360)
    try:
        command = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-Provider",
            SUPPORTED_PROVIDERS[provider_id],
            "-PromptPath",
            str(prompt_path),
            "-OutputPath",
            str(output_path),
            "-ProfileHint",
            str(payload.get("profile_hint") or "(AI)"),
            "-ConversationKey",
            conversation_key,
        ]
        if conversation_url:
            command.extend(["-ConversationUrl", conversation_url])
        command.extend(["-TimeoutSeconds", str(timeout_seconds)])
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 20,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "Timed out before the existing browser AI thread produced a confirmed visible response."
        ) from exc
    native = _read_json(output_path)
    if completed.returncode != 0 or native.get("ok") is not True:
        error = str(native.get("error") or completed.stderr or "Visible browser AI roundtrip failed.").strip()
        raise RuntimeError(error)
    if native.get("submission_confirmed") is not True:
        raise RuntimeError("The visible browser page did not confirm that the prompt entered a real AI thread.")
    result_text = _clean_browser_ai_result_text(native.get("result_text"))
    if not result_text:
        raise RuntimeError(
            "Browser AI returned only a loading/control placeholder; "
            "no completed response was captured."
        )
    external_thread_url = _safe_thread_url(
        provider_id, native.get("external_thread_url")
    )
    _remember_conversation(
        root,
        conversation_key=conversation_key,
        provider_id=provider_id,
        project_id=project_id,
        task_id=task_id,
        external_thread_url=external_thread_url,
    )
    recorded = record_non_api_ai_result(
        root,
        {
            "handoff_id": handoff["id"],
            "result_text": result_text,
            "status": "received",
            "external_action_performed": True,
            "source_receipt": {
                "external_thread_url": external_thread_url,
                "window_title": str(native.get("window_title") or ""),
                "captured_by": "t_one_windows_uia_visible_connector",
                "delivery_method": "windows_uia_visible_keyboard",
                "browser_session_mode": "existing_logged_profile",
                "conversation_key": conversation_key,
                "conversation_reused": bool(native.get("conversation_reused")),
            },
        },
    )
    result = recorded.get("result") if isinstance(recorded.get("result"), dict) else {}
    return {
        "ok": True,
        "status": "completed",
        "message": result_text,
        "job": {
            "id": run_id,
            "provider_id": provider_id,
            "result_id": str(result.get("id") or ""),
            "result_path": str(result.get("project_result_path") or result.get("result_path") or ""),
            "receipt_path": str(result.get("project_receipt_path") or ""),
            "delivery_method": "windows_uia_visible_keyboard",
            "browser_session_mode": "existing_logged_profile",
            "external_store_action_count": 0,
            "submission_confirmed": True,
            "conversation_key": conversation_key,
            "conversation_reused": bool(native.get("conversation_reused")),
            "external_thread_url": external_thread_url,
            "task_context_shared": bool(handoff.get("task_context_available")),
            "capability_context_lines": _capability_context_lines(handoff),
        },
    }


def run_browser_ai_roundtrip(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    requested_mode = str(payload.get("delivery_mode") or "").strip()
    if requested_mode and requested_mode not in {"native_visible", "extension_dom"}:
        raise ValueError("Unsupported browser AI delivery mode.")
    if requested_mode:
        delivery_mode = requested_mode
    else:
        provider_id = str(payload.get("provider_id") or "").strip()
        snapshot = browser_ai_connector_snapshot(root)
        provider = snapshot.get("providers", {}).get(provider_id, {})
        delivery_mode = (
            "extension_dom" if provider.get("extension_dom_ready") else "native_visible"
        )
    if delivery_mode != "extension_dom":
        return run_native_browser_ai_roundtrip(root, payload)
    queued = queue_browser_ai_roundtrip(root, payload)
    job_id = queued["job"]["id"]
    deadline = time.monotonic() + min(max(float(payload.get("timeout_seconds") or 240), 10), 360)
    while time.monotonic() < deadline:
        job = _read_json(_job_path(root, job_id))
        if job.get("status") in {"completed", "failed", "expired"}:
            if job.get("status") == "completed":
                return {
                    "ok": True,
                    "status": "completed",
                    "message": str(job.get("result_text") or ""),
                    "job": job,
                }
            raise RuntimeError(str(job.get("error_text") or f"Browser AI job {job.get('status')}"))
        time.sleep(0.35)
    raise RuntimeError("Timed out waiting for the existing logged-in browser AI response.")
