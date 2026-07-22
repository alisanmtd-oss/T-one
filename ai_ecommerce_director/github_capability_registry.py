from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


CONFIG_PATH = Path("config") / "github_capability_registry.json"
WORKSPACE_PATH = Path("config") / "workspace_projects.json"
RUNTIME_PATH = Path("data") / "github_tool_admission_runtime.json"

DECISION_ORDER = {
    "adopt_reference": 0,
    "pilot_isolated": 1,
    "reference_only": 2,
    "watch": 3,
    "reject_mainline": 4,
}

PROFILE_CATEGORIES = {
    "b2b": {
        "b2b_sales_agent",
        "crm",
        "customer_support",
        "outreach",
        "public_web_research",
        "privacy",
        "agent_eval",
        "agent_observability",
        "workflow_automation",
        "supply_chain_security",
        "mcp_security",
        "mcp_discovery",
    },
    "creative_video": {
        "video_processing",
        "video_analysis",
        "speech_transcription",
        "programmatic_video",
        "timeline_exchange",
        "audio_analysis",
        "video_editor",
        "content_calibration_workflow",
        "desktop_computer_use_agent",
        "workflow_editor_framework",
        "agent_eval",
        "supply_chain_security",
    },
    "ad_agent": {
        "agent_eval",
        "agent_observability",
        "workflow_automation",
        "content_calibration_workflow",
        "mcp_security",
        "supply_chain_security",
    },
    "tiktok_shop": {
        "commerce_skills",
        "commerce_official",
        "browser_automation",
        "browser_diagnostics",
        "desktop_computer_use_agent",
        "workflow_editor_framework",
        "agent_eval",
        "supply_chain_security",
    },
    "shein": {
        "commerce_skills",
        "commerce_official",
        "browser_automation",
        "browser_diagnostics",
        "agent_eval",
        "supply_chain_security",
    },
    "shopee": {
        "commerce_skills",
        "commerce_official",
        "browser_automation",
        "browser_diagnostics",
        "agent_eval",
        "supply_chain_security",
    },
    "general": {
        "agent_framework",
        "agent_runtime",
        "agent_memory",
        "agent_eval",
        "agent_observability",
        "workflow_automation",
        "supply_chain_security",
        "mcp_security",
        "mcp_discovery",
        "privacy",
    },
}

PAUSED_PLATFORMS = {"amazon"}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_github_capability_registry(root: Path) -> dict[str, Any]:
    path = root / CONFIG_PATH
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json_object(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _workspace_tasks(root: Path) -> list[dict[str, Any]]:
    payload = _load_json_object(root / WORKSPACE_PATH)
    rows: list[dict[str, Any]] = []
    for project in payload.get("projects") or []:
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id") or "")
        project_name = str(project.get("name") or project_id or "项目")
        for task in project.get("tasks") or []:
            if isinstance(task, dict) and task.get("id"):
                rows.append(
                    {
                        "project_id": project_id,
                        "project_name": project_name,
                        "task_id": str(task.get("id") or ""),
                        "task_name": str(task.get("name") or task.get("id") or "任务"),
                        "platform": str(task.get("platform") or "general"),
                        "country": str(task.get("country") or task.get("country_site") or ""),
                    }
                )
        for workstream in project.get("workstreams") or []:
            if isinstance(workstream, dict) and workstream.get("id"):
                rows.append(
                    {
                        "project_id": project_id,
                        "project_name": project_name,
                        "task_id": str(workstream.get("id") or ""),
                        "task_name": str(workstream.get("name") or workstream.get("id") or "任务"),
                        "platform": str(workstream.get("platform") or "general"),
                        "country": str(workstream.get("country") or workstream.get("country_site") or ""),
                    }
                )
        for channel in project.get("channels") or []:
            if not isinstance(channel, dict):
                continue
            for store in channel.get("stores") or []:
                if not isinstance(store, dict):
                    continue
                for task in store.get("tasks") or []:
                    if isinstance(task, dict) and task.get("id"):
                        rows.append(
                            {
                                "project_id": project_id,
                                "project_name": project_name,
                                "task_id": str(task.get("id") or ""),
                                "task_name": str(task.get("name") or task.get("id") or "任务"),
                                "platform": str(task.get("platform") or channel.get("platform") or "general"),
                                "country": str(task.get("country") or channel.get("country_site") or ""),
                                "store_binding_id": str(store.get("id") or ""),
                            }
                        )
    return rows


def _task_context(root: Path, task_id: str = "") -> dict[str, Any]:
    tasks = _workspace_tasks(root)
    if task_id:
        for task in tasks:
            if task["task_id"] == task_id:
                return task
    return tasks[0] if tasks else {
        "project_id": "",
        "project_name": "T-one",
        "task_id": "",
        "task_name": "未选择任务",
        "platform": "general",
        "country": "",
    }


def _profile_categories(platform: str) -> set[str]:
    normalized = str(platform or "general").strip().casefold()
    return set(PROFILE_CATEGORIES.get(normalized) or PROFILE_CATEGORIES["general"])


def _candidate_for_repo(root: Path, repo: str) -> dict[str, Any] | None:
    normalized_repo = str(repo or "").strip().lower()
    for item in _candidate_rows(load_github_capability_registry(root)):
        if str(item.get("repo") or "").strip().lower() == normalized_repo:
            return item
    return None


def _candidate_default_surface(row: dict[str, Any]) -> str:
    allowed = row.get("allowed_surfaces") if isinstance(row.get("allowed_surfaces"), list) else []
    return str(allowed[0]) if allowed else "schema_reference"


def _task_candidate_state(task: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    platform = str(task.get("platform") or "general").casefold()
    category = str(row.get("category") or "other")
    decision = str(row.get("decision") or "watch")
    if platform in PAUSED_PLATFORMS:
        return {
            "status": "paused_by_owner",
            "allowed_for_task": False,
            "reason": "Amazon 相关工作已由负责人暂停，不能请求资料、调用 API 或接入工具。",
        }
    if category not in _profile_categories(platform):
        return {
            "status": "out_of_scope_for_agent",
            "allowed_for_task": False,
            "reason": "该仓库类别不属于当前智能体/任务的可见工具范围。",
        }
    if decision == "pilot_isolated":
        return {
            "status": "pilot_requires_checks",
            "allowed_for_task": False,
            "reason": "只可准备隔离试点；许可证、固定版本、安全扫描和隔离 worker 全部通过前不能运行。",
        }
    if decision in {"adopt_reference", "reference_only"}:
        return {
            "status": "local_reference_ready",
            "allowed_for_task": True,
            "reason": "只允许 clean-room 参考、离线设计或本地草稿，不安装、不运行、不接凭据。",
        }
    return {
        "status": "blocked_or_watch",
        "allowed_for_task": False,
        "reason": "当前分级不允许进入该智能体运行时。",
    }


def github_tool_admission_snapshot(root: Path, task_id: str = "") -> dict[str, Any]:
    payload = load_github_capability_registry(root)
    task = _task_context(root, task_id)
    rows = summarize_github_capabilities(root)
    scoped: list[dict[str, Any]] = []
    for row in rows:
        state = _task_candidate_state(task, row)
        if state["status"] == "out_of_scope_for_agent":
            continue
        scoped.append(
            {
                "repo": row["repo"],
                "category": row["category"],
                "decision": row["decision"],
                "decision_label": row["decision_label"],
                "license": row["license"],
                "fit": row["fit"],
                "default_surface": _candidate_default_surface(row),
                "allowed_surfaces": row["allowed_surfaces"],
                "status": state["status"],
                "allowed_for_task": state["allowed_for_task"],
                "reason": state["reason"],
            }
        )
    counts = Counter(str(item["status"]) for item in scoped)
    runtime = _load_json_object(root / RUNTIME_PATH)
    records = runtime.get("records") if isinstance(runtime.get("records"), list) else []
    return {
        "schema_version": 1,
        "updated_at": str(payload.get("updated_at") or ""),
        "task": task,
        "tasks": _workspace_tasks(root),
        "candidate_count": len(rows),
        "visible_candidate_count": len(scoped),
        "reference_ready_count": counts.get("local_reference_ready", 0),
        "pilot_pending_count": counts.get("pilot_requires_checks", 0),
        "blocked_count": counts.get("blocked_or_watch", 0) + counts.get("paused_by_owner", 0),
        "installation_count": 0,
        "credential_access_count": 0,
        "external_action_count": 0,
        "candidates": scoped[:80],
        "recent_records": list(reversed(records[-8:])),
    }


def evaluate_expert_github_tool_request(
    root: Path,
    payload: dict[str, Any],
    *,
    actor: str = "owner",
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("GitHub tool admission payload must be an object.")
    task = _task_context(root, str(payload.get("task_id") or ""))
    repo = str(payload.get("repo") or "").strip()
    requested_surface = str(payload.get("requested_surface") or "").strip()
    action = str(payload.get("action") or "review_reference").strip()
    candidate = _candidate_for_repo(root, repo)
    if candidate is None:
        evaluation = evaluate_github_candidate(root, repo, requested_surface=requested_surface)
        result = {
            "status": "blocked_unknown_repository",
            "allowed": False,
            "reasons": evaluation.get("reasons") or [],
        }
    else:
        if not requested_surface:
            requested_surface = _candidate_default_surface(candidate)
        state = _task_candidate_state(task, candidate)
        request_install = action in {"install", "run", "install_or_run"} or bool(payload.get("request_install"))
        request_real_external_action = action in {"run", "execute", "install_or_run"} or bool(
            payload.get("request_real_external_action")
        )
        evaluation = evaluate_github_candidate(
            root,
            repo,
            requested_surface=requested_surface,
            request_install=request_install,
            request_store_credentials=bool(payload.get("request_store_credentials")),
            request_real_external_action=request_real_external_action,
            security_scan_passed=bool(payload.get("security_scan_passed")),
            license_review_passed=bool(payload.get("license_review_passed")),
            pin_verified=bool(payload.get("pin_verified")),
            isolated_worker_confirmed=bool(payload.get("isolated_worker_confirmed")),
        )
        reasons = list(evaluation.get("reasons") or [])
        if not state["allowed_for_task"]:
            reasons.insert(0, state["reason"])
        allowed = bool(evaluation.get("allowed")) and state["allowed_for_task"] and not request_install
        if action == "prepare_isolated_pilot" and str(candidate.get("decision") or "") == "pilot_isolated":
            allowed = bool(evaluation.get("allowed")) and state["status"] == "pilot_requires_checks"
        status = "local_reference_review_ready" if allowed else "blocked_admission"
        if allowed and action == "prepare_isolated_pilot":
            status = "isolated_pilot_packet_ready"
        result = {
            "status": status,
            "allowed": allowed,
            "reasons": reasons or [state["reason"]],
        }
    record = {
        "id": "github-tool-admission-" + uuid4().hex[:20],
        "created_at": _now(),
        "actor": str(actor or "owner"),
        "task": task,
        "request": {
            "repo": repo,
            "requested_surface": requested_surface,
            "action": action,
        },
        "result": {
            **result,
            "installation_count": 0,
            "credential_access_count": 0,
            "external_action_count": 0,
        },
    }
    runtime_path = root / RUNTIME_PATH
    runtime = _load_json_object(runtime_path)
    records = runtime.get("records") if isinstance(runtime.get("records"), list) else []
    records.append(record)
    runtime = {
        "schema_version": 1,
        "updated_at": record["created_at"],
        "records": records[-200:],
    }
    _write_json_object(runtime_path, runtime)
    return {
        "ok": True,
        "admission": record,
        "message": (
            "本地准入通过；只生成参考/试点回执，安装、凭据和外部动作均为 0。"
            if result["allowed"]
            else "准入已阻断；未安装、未运行、未接触凭据，外部动作 0。"
        ),
    }


def _candidate_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = payload.get("candidates", [])
    if not isinstance(candidates, list):
        return []
    return [item for item in candidates if isinstance(item, dict)]


def summarize_github_capabilities(
    root: Path,
    *,
    decisions: set[str] | None = None,
    category: str = "",
) -> list[dict[str, Any]]:
    payload = load_github_capability_registry(root)
    labels = payload.get("decision_labels", {})
    labels = labels if isinstance(labels, dict) else {}
    rows: list[dict[str, Any]] = []
    for item in _candidate_rows(payload):
        decision = str(item.get("decision") or "watch").strip()
        item_category = str(item.get("category") or "other").strip()
        if decisions is not None and decision not in decisions:
            continue
        if category and item_category != category:
            continue
        allowed = item.get("allowed_surfaces", [])
        blocked = item.get("blocked_surfaces", [])
        rows.append(
            {
                "repo": str(item.get("repo") or "unknown/unknown"),
                "category": item_category,
                "decision": decision,
                "decision_label": str(labels.get(decision) or decision),
                "source_trust": str(item.get("source_trust") or "unknown"),
                "license": str(item.get("license") or "UNASSERTED"),
                "last_verified_push": str(item.get("last_verified_push") or ""),
                "fit": str(item.get("fit") or ""),
                "allowed_surfaces": [str(value) for value in allowed if value] if isinstance(allowed, list) else [],
                "blocked_surfaces": [str(value) for value in blocked if value] if isinstance(blocked, list) else [],
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            DECISION_ORDER.get(str(row["decision"]), 99),
            str(row["category"]),
            str(row["repo"]).lower(),
        ),
    )


def evaluate_github_candidate(
    root: Path,
    repo: str,
    *,
    requested_surface: str = "schema_reference",
    request_install: bool = False,
    request_store_credentials: bool = False,
    request_real_external_action: bool = False,
    security_scan_passed: bool = False,
    license_review_passed: bool = False,
    pin_verified: bool = False,
    isolated_worker_confirmed: bool = False,
) -> dict[str, Any]:
    payload = load_github_capability_registry(root)
    policy = payload.get("policy", {})
    policy = policy if isinstance(policy, dict) else {}
    normalized_repo = str(repo or "").strip().lower()
    candidate = next(
        (
            item
            for item in _candidate_rows(payload)
            if str(item.get("repo") or "").strip().lower() == normalized_repo
        ),
        None,
    )
    if candidate is None:
        return {
            "repo": repo,
            "allowed": False,
            "decision": str(policy.get("unknown_repository_decision") or "block_unknown"),
            "reasons": ["未知仓库默认阻断，必须先核验来源、许可证、依赖、Skill 和网络权限。"],
        }

    reasons: list[str] = []
    allowed_surfaces = candidate.get("allowed_surfaces", [])
    allowed_surfaces = allowed_surfaces if isinstance(allowed_surfaces, list) else []
    blocked_surfaces = candidate.get("blocked_surfaces", [])
    blocked_surfaces = blocked_surfaces if isinstance(blocked_surfaces, list) else []
    decision = str(candidate.get("decision") or "watch")

    if decision in {"watch", "reject_mainline"}:
        reasons.append("当前分级不允许进入主线运行时。")
    if requested_surface in blocked_surfaces:
        reasons.append(f"请求面 {requested_surface} 被显式禁止。")
    if requested_surface and requested_surface not in allowed_surfaces:
        reasons.append(f"请求面 {requested_surface} 不在允许清单。")
    if request_install and not bool(policy.get("auto_install_allowed", False)):
        reasons.append("项目禁止从 GitHub 自动安装。")
    if request_store_credentials and not bool(policy.get("store_credentials_allowed", False)):
        reasons.append("GitHub 候选不得接触店铺凭据。")
    if request_real_external_action and not bool(policy.get("real_external_actions_allowed", False)):
        reasons.append("GitHub 候选不得直接执行真实外部动作。")
    if decision == "pilot_isolated":
        if bool(policy.get("security_scan_required_before_pilot", True)) and not security_scan_passed:
            reasons.append("隔离试点前的依赖/Skill 安全扫描尚未通过。")
        if bool(policy.get("license_review_required_before_pilot", True)) and not license_review_passed:
            reasons.append("隔离试点前的许可证复核尚未通过。")
        if bool(policy.get("pin_commit_or_release_required", True)) and not pin_verified:
            reasons.append("隔离试点尚未固定并核验 release/commit。")
        if bool(policy.get("isolated_worker_required", True)) and not isolated_worker_confirmed:
            reasons.append("隔离 worker 与最小文件/工具/网络权限尚未确认。")

    return {
        "repo": str(candidate.get("repo") or repo),
        "allowed": not reasons,
        "decision": decision,
        "requested_surface": requested_surface,
        "reasons": reasons or ["仅允许在登记的只读/隔离范围内使用。"],
        "security_scan_required": bool(policy.get("security_scan_required_before_pilot", True)),
        "license_review_required": bool(policy.get("license_review_required_before_pilot", True)),
        "pin_required": bool(policy.get("pin_commit_or_release_required", True)),
        "isolated_worker_required": bool(policy.get("isolated_worker_required", True)),
    }


def build_github_capability_report(root: Path, limit: int = 18) -> str:
    payload = load_github_capability_registry(root)
    rows = summarize_github_capabilities(root)
    counts = Counter(str(row["decision"]) for row in rows)
    labels = payload.get("decision_labels", {})
    labels = labels if isinstance(labels, dict) else {}
    lines = [
        "## GitHub 能力候选安全摘要",
        "",
        f"- 已核验 {len(rows)} 个与 Amazon、B2B、Agent、浏览器、CRM、采集、评测和供应链安全相关的仓库。",
        "- GitHub 热度不等于准入；未知仓库默认阻断，所有候选禁止自动安装、禁止接触店铺凭据、禁止直接执行真实外部动作。",
        "- 进入隔离试点前必须复核许可证、固定 release/commit、扫描依赖与 Skill，并限制文件、工具和网络权限。",
        "",
    ]
    if not rows:
        lines.append("- 暂无 GitHub 能力候选配置。")
        return "\n".join(lines).rstrip() + "\n"

    count_parts = []
    for decision in DECISION_ORDER:
        if counts.get(decision):
            count_parts.append(f"{labels.get(decision, decision)} {counts[decision]}")
    lines.append("- 分级：" + "；".join(count_parts) + "。")
    lines.append("")
    for row in rows[: max(0, limit)]:
        date_note = f"；最近核验更新 {row['last_verified_push']}" if row["last_verified_push"] else ""
        lines.append(
            f"- {row['repo']}：{row['decision_label']}；{row['fit']}"
            f"（许可证 {row['license']}{date_note}）"
        )
    if len(rows) > limit:
        lines.append(f"- 其余 {len(rows) - limit} 个候选保留在机器可读准入表中，不在页面展开。")
    return "\n".join(lines).rstrip() + "\n"
