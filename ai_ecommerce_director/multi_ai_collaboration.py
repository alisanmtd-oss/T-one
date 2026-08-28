from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .cli_ai_connector import cli_ai_connector_snapshot, run_cli_ai_roundtrip
from .llm import LLMClient, public_ai_error
from .non_api_ai_bridge import redact_sensitive_text
from .workspace_runtime import (
    SAFE_ID,
    ensure_project_local_folder,
    load_workspace_config,
    project_workspace_context,
)


MAX_PARTICIPANTS = 4
SAFE_PARTICIPANT_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,119}$")
ROLE_LABELS = {
    "operator": "执行分析",
    "reviewer": "独立复核",
    "analyst": "补充分析",
    "coordinator": "协调汇总",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _discover_claude_desktop() -> Path | None:
    if os.name != "nt":
        return None
    candidates = [
        Path(os.environ.get("LOCALAPPDATA") or "") / "Programs" / "Claude" / "claude.exe",
        Path(os.environ.get("LOCALAPPDATA") or "") / "Claude" / "claude.exe",
    ]
    windows_apps = Path("C:/Program Files/WindowsApps")
    try:
        candidates.extend(windows_apps.glob("Claude_*__pzs8sxrjxfjjc/app/claude.exe"))
    except OSError:
        pass
    # Microsoft Store package folders can deny directory enumeration even when
    # the exact executable is readable.  The per-user package data directory is
    # a stable, read-only installation signal for that distribution channel.
    candidates.append(
        Path(os.environ.get("LOCALAPPDATA") or "")
        / "Packages"
        / "Claude_pzs8sxrjxfjjc"
    )
    candidates.append(
        Path.home() / "AppData" / "Local" / "Packages" / "Claude_pzs8sxrjxfjjc"
    )
    return next((path.resolve() for path in candidates if path.is_file() or path.is_dir()), None)


def _discover_workbuddy_cli() -> dict[str, str]:
    """Find the installed vendor CLI without copying or modifying WorkBuddy."""

    if os.name != "nt":
        return {}
    app_root = Path.home() / "Desktop" / "WorkBuddyAI"
    app = app_root / "WorkBuddyAI.exe"
    cli = app_root / "resources" / "app.asar.unpacked" / "cli" / "bin" / "codebuddy"
    node_root = Path.home() / ".workbuddy" / "binaries" / "node" / "versions"
    try:
        node_candidates = sorted(
            node_root.glob("*/node.exe"), key=lambda item: item.parent.name, reverse=True
        )
    except OSError:
        node_candidates = []
    node = next((item for item in node_candidates if item.is_file()), None)
    if not app.is_file() or not cli.is_file() or node is None:
        return {}
    return {
        "app_path": str(app.resolve()),
        "cli_path": str(cli.resolve()),
        "node_path": str(node.resolve()),
    }


def _workbuddy_verification(root: Path) -> dict[str, Any]:
    state = _read_json(root / "config" / "workbuddy_cli_verification_state.json")
    verified_at = _parse_time(state.get("verified_at"))
    if (
        state.get("status") != "verified_callable"
        or not verified_at
        or verified_at < datetime.now(timezone.utc) - timedelta(hours=24)
    ):
        return {}
    return state


def _workbuddy_command(installation: dict[str, str], prompt: str) -> list[str]:
    return [
        installation["node_path"],
        installation["cli_path"],
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--no-session-persistence",
        "--permission-mode",
        "plan",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--strict-mcp-config",
    ]


def _parse_workbuddy_jsonl(output: str) -> tuple[str, str, bool]:
    text = ""
    model = ""
    tool_used = False
    for line in str(output or "").splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if not isinstance(item, dict):
            continue
        if item.get("type") == "system" and item.get("subtype") == "init":
            model = str(item.get("model") or model)
        if item.get("type") in {"tool_use", "tool_call"}:
            tool_used = True
        message = item.get("message") if isinstance(item.get("message"), dict) else {}
        content = message.get("content") if isinstance(message, dict) else []
        if isinstance(content, list):
            if any(
                isinstance(block, dict)
                and str(block.get("type") or "") in {"tool_use", "tool_call"}
                for block in content
            ):
                tool_used = True
            chunks = [
                str(block.get("text") or "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            if chunks:
                text = "\n".join(chunks).strip()
                model = str(message.get("model") or model)
        if item.get("type") == "result" and str(item.get("result") or "").strip():
            text = str(item.get("result") or "").strip()
    return text, model, tool_used


def verify_workbuddy_cli(root: Path) -> dict[str, Any]:
    """Perform one owner-triggered, no-tools roundtrip and persist a short receipt."""

    root = Path(root).resolve()
    installation = _discover_workbuddy_cli()
    if not installation:
        return {"ok": False, "status": "not_installed", "external_ai_call_count": 0}
    result = subprocess.run(
        _workbuddy_command(
            installation,
            "只返回 WORKBUDDY_READY。不要调用工具，不要读取文件，不要执行任何外部动作。",
        ),
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    response, model, tool_used = _parse_workbuddy_jsonl(result.stdout)
    ok = result.returncode == 0 and response == "WORKBUDDY_READY" and not tool_used
    now = _utc_now()
    state = {
        "schema_version": 1,
        "status": "verified_callable" if ok else "verification_failed",
        "verified_at": now,
        "app_version": "5.3.11.0",
        "cli_license_state": "vendor_binary_not_redistributed",
        "model": model,
        "tool_used": tool_used,
        "external_ai_call_count": 1,
        "external_store_action_count": 0,
    }
    state_path = root / "config" / "workbuddy_cli_verification_state.json"
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt_path = root / "outputs" / "workbuddy_cli" / "workbuddy-cli-verification-latest.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps({**state, "response": response}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"ok": ok, **state, "receipt_path": _safe_relative(receipt_path, root)}


def _parse_time(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _verified_api_models(root: Path) -> set[tuple[str, str]]:
    state = _read_json(root / "config" / "ai_provider_verification_state.json")
    max_age_hours = float(
        (state.get("verification_policy") or {}).get("max_age_hours") or 24
    )
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)
    latest_accepted = now + timedelta(minutes=5)
    audited_at = _parse_time(state.get("audited_at"))
    verified: set[tuple[str, str]] = set()
    if audited_at and cutoff <= audited_at <= latest_accepted:
        verified.update(
            {
                (
                    str(item.get("provider") or "").strip(),
                    str(item.get("model") or "").strip(),
                )
                for item in state.get("live_receipts", [])
                if isinstance(item, dict)
                and item.get("status") == "ok"
                and str(item.get("provider") or "").strip()
                and str(item.get("model") or "").strip()
            }
        )
    # A successful project-local collaboration result is also a precise, recent
    # provider/model receipt.  It does not upgrade any external business action.
    for result_path in root.glob("projects/*/runs/multi_ai/*/results.json"):
        record = _read_json(result_path)
        finished_at = _parse_time(record.get("finished_at"))
        if not finished_at or not cutoff <= finished_at <= latest_accepted:
            continue
        for item in record.get("results", []):
            if not isinstance(item, dict) or not item.get("ok"):
                continue
            provider = str(item.get("provider_id") or "").strip()
            model = str(item.get("model") or "").strip()
            if provider and model and provider != "codex-cli":
                verified.add((provider, model))
    return verified


def multi_ai_collaboration_snapshot(
    root: Path, *, live_probe: bool = True
) -> dict[str, Any]:
    root = Path(root).resolve()
    participants: list[dict[str, Any]] = []
    codex = cli_ai_connector_snapshot(root, live_probe=live_probe)
    participants.append(
        {
            "id": "codex-cli",
            "provider_id": "codex-cli",
            "name": "Codex CLI",
            "kind": "cli",
            "role": "operator",
            "model": str(codex.get("version") or ""),
            "installed": bool(codex.get("installed")),
            "ready": bool(codex.get("ready")),
            "callable": bool(codex.get("ready")),
            "status": (
                "verified_callable"
                if codex.get("ready")
                else str(codex.get("authentication_status") or "not_ready")
            ),
            "sandbox": "read-only",
        }
    )
    participants.append(
        {
            "id": "codex-luna-cli",
            "provider_id": "codex-cli",
            "name": "GPT-5.6 Luna · Codex",
            "kind": "cli",
            "role": "reviewer",
            "model": "gpt-5.6-luna",
            "installed": bool(codex.get("installed")),
            "ready": bool(codex.get("ready")),
            "callable": bool(codex.get("ready")),
            "status": (
                "verified_callable"
                if codex.get("ready")
                else str(codex.get("authentication_status") or "not_ready")
            ),
            "sandbox": "read-only",
        }
    )

    workbuddy = _discover_workbuddy_cli()
    workbuddy_verification = _workbuddy_verification(root)
    workbuddy_ready = bool(workbuddy and workbuddy_verification)
    participants.append(
        {
            "id": "workbuddy-cli",
            "provider_id": "workbuddy-cli",
            "name": "WorkBuddy AI / CodeBuddy",
            "kind": "workbuddy_cli",
            "role": "reviewer",
            "model": str(workbuddy_verification.get("model") or "fast-model"),
            "installed": bool(workbuddy),
            "ready": workbuddy_ready,
            "callable": workbuddy_ready,
            "status": (
                "verified_callable"
                if workbuddy_ready
                else "installed_requires_live_verification" if workbuddy else "not_installed"
            ),
            "installation_path": str(workbuddy.get("app_path") or ""),
            "sandbox": "plan_mode_no_mcp_no_tools_prompt",
        }
    )

    verified_models = _verified_api_models(root)
    status = LLMClient(root=root, task="chat").status()
    api_participants: list[dict[str, Any]] = []
    for provider in status.providers:
        if not provider.get("enabled") or not provider.get("ready"):
            continue
        name = str(provider.get("name") or "").strip()
        if not name:
            continue
        api_participants.append(
            {
                "id": f"api:{name}",
                "provider_id": name,
                "name": name,
                "kind": "api",
                "role": "reviewer" if name == "gemini-flash" else "analyst",
                "model": str(provider.get("model") or ""),
                "installed": True,
                "ready": True,
                "callable": True,
                "status": (
                    "verified_callable"
                    if (name, str(provider.get("model") or "")) in verified_models
                    else "configured_callable_requires_live_result"
                ),
                "sandbox": "no_tools_read_only_prompt",
            }
        )
    api_participants.sort(
        key=lambda item: (
            item["provider_id"] != "gemini-flash",
            (item["provider_id"], item["model"]) not in verified_models,
            item["provider_id"],
        )
    )
    participants.extend(api_participants)

    claude_path = _discover_claude_desktop()
    participants.append(
        {
            "id": "claude-desktop",
            "provider_id": "claude-desktop",
            "name": "Claude Desktop",
            "kind": "desktop_gui",
            "role": "reviewer",
            "model": "",
            "installed": claude_path is not None,
            "ready": False,
            "callable": False,
            "status": (
                "installed_no_automated_return_interface"
                if claude_path
                else "not_installed"
            ),
            "installation_path": str(claude_path or ""),
            "sandbox": "not_callable",
        }
    )

    recommended: list[str] = []
    if codex.get("ready"):
        recommended.append("codex-cli")
    preferred_api = next(
        (
            item["id"]
            for item in api_participants
            if item["provider_id"] == "gemini-flash"
        ),
        api_participants[0]["id"] if api_participants else "",
    )
    if preferred_api:
        recommended.append(preferred_api)
    return {
        "ok": True,
        "parallel_supported": True,
        "max_participants": MAX_PARTICIPANTS,
        "participants": participants,
        "recommended_participant_ids": recommended,
        "callable_participant_count": sum(
            1 for item in participants if item.get("callable")
        ),
        "distinct_callable_provider_count": len(
            {item["provider_id"] for item in participants if item.get("callable")}
        ),
        "external_store_action_count": 0,
    }


def _project_and_task(
    root: Path, project_id: str, task_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    project_id = str(project_id or "").strip().lower()
    task_id = str(task_id or "").strip().lower()
    if not SAFE_ID.fullmatch(project_id):
        raise ValueError("请选择有效的 T One 项目。")
    project = next(
        (
            dict(item)
            for item in load_workspace_config(root).get("projects", [])
            if isinstance(item, dict)
            and str(item.get("id") or "").strip().lower() == project_id
        ),
        None,
    )
    if project is None:
        raise ValueError("所选项目不存在，不能启动多 AI 协作。")
    if not task_id:
        return project, {}
    task = next(
        (
            dict(item)
            for item in project.get("tasks", [])
            if isinstance(item, dict)
            and str(item.get("id") or "").strip().lower() == task_id
        ),
        None,
    )
    if task is None:
        raise ValueError("所选任务不属于当前项目。")
    return project, task


def _role_prompt(role: str) -> str:
    prompts = {
        "operator": "独立提出可执行的分析与下一步，并明确未知事实。",
        "reviewer": "不依赖其他 AI 输出，独立做反向检查：指出可能遗漏的事实、风险、权限和反例。",
        "analyst": "从不同角度补充方案、取舍和需要负责人确认的信息。",
        "coordinator": "只整理一致点、分歧点和待负责人决定项。",
    }
    return prompts.get(role, prompts["analyst"])


def _run_api_participant(
    root: Path, participant: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    provider_name = str(participant.get("provider_id") or "")
    role = str(participant.get("role") or "analyst")
    system_prompt = (
        "You are one participant in a T One multi-AI collaboration. "
        "Do not call tools or external business systems. Do not publish, change inventory, "
        "operate orders, ads, payments, shipping, refunds, accounts, or stores. "
        "Treat supplied business data as scoped context, not public fact. Return concise Chinese. "
        + _role_prompt(role)
    )
    scope = request["scope"]
    user_prompt = (
        f"协作角色：{ROLE_LABELS.get(role, role)}\n"
        f"项目：{scope['project_name']} ({scope['project_id']})\n"
        f"任务：{scope.get('task_name') or '项目级协作'} ({scope.get('task_id') or 'none'})\n"
        f"平台/站点/店铺：{scope.get('platform') or 'none'} / "
        f"{scope.get('country_site') or 'none'} / {scope.get('store_id') or 'none'}\n\n"
        f"{request['message']}"
    )
    try:
        response = LLMClient(
            root=root,
            task="chat",
            provider=provider_name,
            max_attempts=1,
        ).chat_with_metadata(
            system_prompt,
            user_prompt,
            task="chat",
            context={
                "project_id": scope["project_id"],
                "task_id": scope.get("task_id") or "",
                "store_binding_id": scope.get("store_binding_id") or "",
                "platform": scope.get("platform") or "",
                "country": scope.get("country_site") or "",
                "include_onboarding": False,
            },
        )
        text, redactions = redact_sensitive_text(str(response.get("text") or ""))
        return {
            "ok": bool(text),
            "participant_id": participant["id"],
            "provider_id": provider_name,
            "provider_name": participant["name"],
            "role": role,
            "model": str(response.get("model") or participant.get("model") or ""),
            "latency_ms": int(response.get("latency_ms") or 0),
            "result_text": text[:24000],
            "error_text": "" if text else "AI 返回内容为空。",
            "redaction_count": redactions,
            "external_ai_call_count": 1,
            "external_store_action_count": 0,
        }
    except Exception as exc:  # noqa: BLE001 - provider failure is a collaboration result.
        error = public_ai_error(exc)
        safe_error, redactions = redact_sensitive_text(
            str(error.get("error") or "AI 调用失败。")
        )
        return {
            "ok": False,
            "participant_id": participant["id"],
            "provider_id": provider_name,
            "provider_name": participant["name"],
            "role": role,
            "model": str(participant.get("model") or ""),
            "result_text": "",
            "error_text": safe_error,
            "error_code": str(error.get("code") or "ai_call_failed"),
            "redaction_count": redactions,
            "external_ai_call_count": 1,
            "external_store_action_count": 0,
        }


def _run_codex_participant(
    root: Path, participant: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    scope = request["scope"]
    role = str(participant.get("role") or "operator")
    result = run_cli_ai_roundtrip(
        root,
        {
            "provider_id": str(participant.get("id") or "codex-cli"),
            "model": (
                str(participant.get("model") or "")
                if str(participant.get("id") or "") == "codex-luna-cli"
                else ""
            ),
            "project_id": scope["project_id"],
            "task_id": (
                f"multi-ai-{scope.get('task_id') or 'project'}-{role}"
            )[:80],
            "message": (
                f"协作角色：{ROLE_LABELS.get(role, role)}。{_role_prompt(role)}\n\n"
                + request["message"]
            ),
            "owner_confirmed": True,
        },
    )
    run = result.get("run") if isinstance(result.get("run"), dict) else {}
    return {
        "ok": bool(result.get("ok")),
        "participant_id": participant["id"],
        "provider_id": "codex-cli",
        "provider_name": participant["name"],
        "role": role,
        "model": str(
            run.get("model")
            or (result.get("connector") or {}).get("version")
            or ""
        ),
        "result_text": str(result.get("message") or "")[:24000]
        if result.get("ok")
        else "",
        "error_text": "" if result.get("ok") else str(result.get("message") or "Codex CLI 调用失败。"),
        "receipt_path": str(run.get("receipt_path") or ""),
        "result_path": str(run.get("result_path") or ""),
        "external_ai_call_count": int(run.get("external_ai_call_count") or 1),
        "external_store_action_count": 0,
    }


def _run_workbuddy_participant(
    root: Path, participant: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    installation = _discover_workbuddy_cli()
    role = str(participant.get("role") or "reviewer")
    scope = request["scope"]
    if not installation:
        return {
            "ok": False,
            "participant_id": participant["id"],
            "provider_id": "workbuddy-cli",
            "provider_name": participant["name"],
            "role": role,
            "result_text": "",
            "error_text": "WorkBuddy CLI 当前未安装。",
            "external_ai_call_count": 0,
            "external_store_action_count": 0,
        }
    prompt = (
        "你是 T One 多 AI 协作中的独立复核者。禁止调用任何工具、读取文件或连接 MCP；"
        "禁止登录或操作店铺、浏览器、订单、广告、付款、发货、退款、账号和库存。"
        "只根据下面已脱敏的任务摘要返回简洁中文，并明确未知事实。\n\n"
        f"项目：{scope['project_name']} ({scope['project_id']})\n"
        f"任务：{scope.get('task_name') or '项目级协作'} ({scope.get('task_id') or 'none'})\n"
        f"平台/站点/店铺：{scope.get('platform') or 'none'} / "
        f"{scope.get('country_site') or 'none'} / {scope.get('store_id') or 'none'}\n\n"
        f"{request['message']}"
    )
    try:
        completed = subprocess.run(
            _workbuddy_command(installation, prompt),
            cwd=str(root / "projects" / scope["project_id"]),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        response, model, tool_used = _parse_workbuddy_jsonl(completed.stdout)
        safe_text, redactions = redact_sensitive_text(response)
        ok = completed.returncode == 0 and bool(safe_text) and not tool_used
        return {
            "ok": ok,
            "participant_id": participant["id"],
            "provider_id": "workbuddy-cli",
            "provider_name": participant["name"],
            "role": role,
            "model": model or str(participant.get("model") or ""),
            "result_text": safe_text[:24000] if ok else "",
            "error_text": "" if ok else "WorkBuddy 返回为空、失败或尝试调用工具。",
            "redaction_count": redactions,
            "tool_used": tool_used,
            "external_ai_call_count": 1,
            "external_store_action_count": 0,
        }
    except (OSError, subprocess.SubprocessError) as exc:
        safe_error, redactions = redact_sensitive_text(str(exc))
        return {
            "ok": False,
            "participant_id": participant["id"],
            "provider_id": "workbuddy-cli",
            "provider_name": participant["name"],
            "role": role,
            "result_text": "",
            "error_text": safe_error or "WorkBuddy CLI 调用失败。",
            "redaction_count": redactions,
            "external_ai_call_count": 1,
            "external_store_action_count": 0,
        }


def _run_participant(
    root: Path, participant: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    started_at = _utc_now()
    if participant.get("kind") == "cli":
        result = _run_codex_participant(root, participant, request)
    elif participant.get("kind") == "workbuddy_cli":
        result = _run_workbuddy_participant(root, participant, request)
    elif participant.get("kind") == "api":
        result = _run_api_participant(root, participant, request)
    else:
        result = {
            "ok": False,
            "participant_id": participant["id"],
            "provider_id": participant["provider_id"],
            "provider_name": participant["name"],
            "role": participant.get("role") or "analyst",
            "result_text": "",
            "error_text": "当前适配器没有可验证的自动发送与回传接口。",
            "external_ai_call_count": 0,
            "external_store_action_count": 0,
        }
    result["started_at"] = started_at
    result["finished_at"] = _utc_now()
    return result


def _combined_message(results: list[dict[str, Any]]) -> str:
    sections = []
    for item in results:
        label = f"{item.get('provider_name') or item.get('provider_id')} · {ROLE_LABELS.get(str(item.get('role') or ''), item.get('role') or '协作')}"
        body = str(item.get("result_text") or item.get("error_text") or "没有返回内容。")
        state = "成功" if item.get("ok") else "失败"
        sections.append(f"【{label} · {state}】\n{body}")
    return "\n\n".join(sections)


def run_multi_ai_collaboration(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    root = Path(root).resolve()
    if payload.get("owner_confirmed") is not True:
        raise ValueError("本次多 AI 外部调用需要负责人明确确认。")
    raw_message = str(payload.get("message") or "").strip()
    if not raw_message:
        raise ValueError("请输入要交给多 AI 协作的任务。")
    safe_message, redaction_count = redact_sensitive_text(raw_message)
    project, task = _project_and_task(
        root,
        str(payload.get("project_id") or ""),
        str(payload.get("task_id") or ""),
    )
    snapshot = multi_ai_collaboration_snapshot(root, live_probe=True)
    participant_ids = payload.get("participant_ids")
    if not isinstance(participant_ids, list) or not participant_ids:
        from .project_capability_profiles import project_ai_participant_ids

        participant_ids = project_ai_participant_ids(
            root, str(project.get("id") or "")
        ) or snapshot.get("recommended_participant_ids") or []
    participant_ids = [str(item or "").strip().lower() for item in participant_ids]
    if len(participant_ids) < 2:
        raise ValueError("至少选择两个可调用的 AI 协作者。")
    if len(participant_ids) > MAX_PARTICIPANTS:
        raise ValueError(f"单次最多选择 {MAX_PARTICIPANTS} 个 AI 协作者。")
    if len(set(participant_ids)) != len(participant_ids):
        raise ValueError("同一协作者不能重复选择。")
    if any(not SAFE_PARTICIPANT_ID.fullmatch(item) for item in participant_ids):
        raise ValueError("AI 协作者标识无效。")
    available = {
        str(item.get("id") or ""): dict(item)
        for item in snapshot.get("participants", [])
        if isinstance(item, dict)
    }
    participants = []
    for participant_id in participant_ids:
        participant = available.get(participant_id)
        if participant is None:
            raise ValueError(f"AI 协作者不存在：{participant_id}")
        if not participant.get("callable") or not participant.get("ready"):
            raise ValueError(
                f"AI 协作者尚不可调用：{participant.get('name') or participant_id} / "
                f"{participant.get('status') or 'not_ready'}"
            )
        participants.append(participant)

    project_folder, relative_project_folder = ensure_project_local_folder(root, project)
    workspace_context = project_workspace_context(
        root, str(project.get("id") or ""), str(task.get("id") or "")
    )
    now = _utc_now()
    digest = hashlib.sha256(
        json.dumps(
            {
                "project_id": project["id"],
                "task_id": task.get("id") or "",
                "participant_ids": participant_ids,
                "message": safe_message,
                "created_at": now,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    run_id = f"multi-ai-{digest[:16]}"
    run_dir = project_folder / "runs" / "multi_ai" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    request_path = run_dir / "request.json"
    result_path = run_dir / "results.json"
    receipt_path = project_folder / "receipts" / f"{run_id}.json"
    scope = {
        "project_id": str(project.get("id") or ""),
        "project_name": str(project.get("name") or project.get("id") or ""),
        "task_id": str(task.get("id") or ""),
        "task_name": str(task.get("name") or ""),
        "platform": str(task.get("platform") or ""),
        "country_site": str(task.get("country") or task.get("country_site") or ""),
        "store_binding_id": str(task.get("store_binding_id") or ""),
        "store_id": str(task.get("store_id") or ""),
        "execution_identity_id": str(task.get("execution_identity_id") or ""),
    }
    request = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": now,
        "message": safe_message,
        "redaction_count": redaction_count,
        "participant_ids": participant_ids,
        "scope": scope,
        "workspace_context": workspace_context,
        "workspace_access": {
            "local_cli": "read_only_within_project_root",
            "remote_api": "supplied_summary_only_no_local_file_access",
        },
        "owner_confirmed": True,
        "parallel_dispatch": True,
        "external_store_action_count": 0,
    }
    request_path.write_text(
        json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(participants)) as pool:
        futures = {
            pool.submit(_run_participant, root, participant, request): participant
            for participant in participants
        }
        for future in as_completed(futures):
            participant = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - one provider must not hide peer results.
                error, error_redactions = redact_sensitive_text(str(exc))
                result = {
                    "ok": False,
                    "participant_id": participant["id"],
                    "provider_id": participant["provider_id"],
                    "provider_name": participant["name"],
                    "role": participant.get("role") or "analyst",
                    "result_text": "",
                    "error_text": error or "AI 协作者调用失败。",
                    "redaction_count": error_redactions,
                    "external_ai_call_count": 1,
                    "external_store_action_count": 0,
                }
            results.append(result)
    order = {participant_id: index for index, participant_id in enumerate(participant_ids)}
    results.sort(key=lambda item: order.get(str(item.get("participant_id") or ""), 999))
    successful = sum(1 for item in results if item.get("ok"))
    failed = len(results) - successful
    status = "completed" if successful == len(results) else "partial" if successful else "failed"
    combined = _combined_message(results)
    finished_at = _utc_now()
    result_record = {
        "schema_version": 1,
        "run_id": run_id,
        "status": status,
        "project_id": scope["project_id"],
        "task_id": scope["task_id"],
        "started_at": now,
        "finished_at": finished_at,
        "parallel_dispatch": True,
        "results": results,
        "combined_text": combined,
        "review_status": "needs_owner_review",
        "fact_status": "unverified_multi_ai_output",
        "memory_write_status": "blocked_until_owner_approval",
        "external_store_action_count": 0,
    }
    result_path.write_text(
        json.dumps(result_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    receipt = {
        "schema_version": 1,
        "run_id": run_id,
        "status": status,
        "project_id": scope["project_id"],
        "task_id": scope["task_id"],
        "participant_ids": participant_ids,
        "successful_participant_count": successful,
        "failed_participant_count": failed,
        "distinct_provider_count": len(
            {str(item.get("provider_id") or "") for item in results}
        ),
        "parallel_dispatch": True,
        "request_path": _safe_relative(request_path, root),
        "result_path": _safe_relative(result_path, root),
        "local_project_folder": relative_project_folder,
        "workspace_entry_manifest": workspace_context["project"]["entry_manifest"],
        "external_ai_call_count": sum(
            int(item.get("external_ai_call_count") or 0) for item in results
        ),
        "external_store_action_count": 0,
        "finished_at": finished_at,
    }
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "ok": successful > 0,
        "status": status,
        "run_id": run_id,
        "project_id": scope["project_id"],
        "task_id": scope["task_id"],
        "participant_count": len(results),
        "successful_participant_count": successful,
        "failed_participant_count": failed,
        "distinct_provider_count": receipt["distinct_provider_count"],
        "parallel_dispatch": True,
        "results": results,
        "message": combined,
        "request_path": receipt["request_path"],
        "result_path": receipt["result_path"],
        "receipt_path": _safe_relative(receipt_path, root),
        "external_ai_call_count": receipt["external_ai_call_count"],
        "external_store_action_count": 0,
    }
