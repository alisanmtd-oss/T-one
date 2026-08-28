"""Project-level AI pairing and Skill auto-download policy."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Any

from .multi_ai_collaboration import MAX_PARTICIPANTS, multi_ai_collaboration_snapshot
from .skill_package_store import (
    install_project_skill_package,
    skill_package_store_snapshot,
)
from .workspace_runtime import (
    SAFE_ID,
    load_workspace_config,
    workspace_item_context,
)
from .workspace_schema import find_task_context


PROFILE_PATH = Path("data") / "project_capability_profiles.json"
_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read(root: Path) -> dict[str, Any]:
    try:
        payload = json.loads((root / PROFILE_PATH).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        payload = {}
    except (OSError, ValueError) as exc:
        raise ValueError("Project capability profiles are not readable.") from exc
    profiles = payload.get("profiles") if isinstance(payload, dict) else None
    return {
        "schema_version": 1,
        "updated_at": str(payload.get("updated_at") or "") if isinstance(payload, dict) else "",
        "profiles": profiles if isinstance(profiles, dict) else {},
    }


def _write(root: Path, payload: dict[str, Any]) -> None:
    path = root / PROFILE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _projects(root: Path) -> list[dict[str, str]]:
    return [
        {
            "id": str(item.get("id") or "").strip().lower(),
            "name": str(item.get("name") or item.get("id") or "").strip(),
        }
        for item in load_workspace_config(root).get("projects", [])
        if isinstance(item, dict) and SAFE_ID.fullmatch(str(item.get("id") or "").strip().lower())
    ]


def project_ai_participant_ids(root: Path, project_id: str) -> list[str]:
    project_id = str(project_id or "").strip().lower()
    profile = _read(Path(root).resolve())["profiles"].get(project_id, {})
    return [
        str(item).strip().lower()
        for item in profile.get("participant_ids", [])
        if str(item).strip()
    ] if isinstance(profile, dict) else []


def project_capability_profile_snapshot(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    saved = _read(root)
    ai = multi_ai_collaboration_snapshot(root, live_probe=False)
    participants = [
        {
            "id": str(item.get("id") or ""),
            "name": str(item.get("name") or item.get("id") or ""),
            "kind": str(item.get("kind") or ""),
            "model": str(item.get("model") or ""),
            "installed": bool(item.get("installed")),
            "ready": bool(item.get("ready")),
            "callable": bool(item.get("callable")),
            "status": str(item.get("status") or "unknown"),
        }
        for item in ai.get("participants", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    ]
    projects = []
    for project in _projects(root):
        profile = saved["profiles"].get(project["id"], {})
        projects.append(
            {
                **project,
                "participant_ids": [
                    str(item)
                    for item in profile.get("participant_ids", [])
                    if str(item).strip()
                ] if isinstance(profile, dict) else [],
                "auto_download_skills": bool(
                    profile.get("auto_download_skills")
                ) if isinstance(profile, dict) else False,
            }
        )
    return {
        "ok": True,
        "projects": projects,
        "participants": participants,
        "max_participants": MAX_PARTICIPANTS,
        "minimum_multi_ai_participants": 2,
        "skill_storage": skill_package_store_snapshot(root),
        "external_ai_calls": 0,
        "external_downloads": 0,
        "external_store_actions": 0,
    }


def save_project_capability_profile(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    root = Path(root).resolve()
    project_id = str(payload.get("project_id") or "").strip().lower()
    projects = {item["id"] for item in _projects(root)}
    if not SAFE_ID.fullmatch(project_id) or project_id not in projects:
        raise ValueError("项目不存在，不能保存 AI 组合。")
    raw_ids = payload.get("participant_ids")
    if not isinstance(raw_ids, list):
        raise ValueError("AI 组合必须是列表。")
    participant_ids = list(
        dict.fromkeys(str(item or "").strip().lower() for item in raw_ids if str(item or "").strip())
    )
    if participant_ids and len(participant_ids) < 2:
        raise ValueError("项目多 AI 组合至少选择 2 个 AI；不使用时可全部取消。")
    if len(participant_ids) > MAX_PARTICIPANTS:
        raise ValueError(f"每个项目最多搭配 {MAX_PARTICIPANTS} 个 AI。")
    available = {
        str(item.get("id") or "")
        for item in multi_ai_collaboration_snapshot(root, live_probe=False).get("participants", [])
        if isinstance(item, dict)
    }
    missing = [item for item in participant_ids if item not in available]
    if missing:
        raise ValueError("AI 未登记：" + "、".join(missing))
    now = _now()
    with _LOCK:
        state = _read(root)
        state["profiles"][project_id] = {
            "participant_ids": participant_ids,
            "auto_download_skills": payload.get("auto_download_skills") is True,
            "updated_at": now,
            "updated_by": str(actor or "owner")[:80],
        }
        state["updated_at"] = now
        _write(root, state)
    return {
        "ok": True,
        "project_id": project_id,
        **state["profiles"][project_id],
        "message": "项目 AI 组合与 Skill 按需下载策略已保存。",
        "external_ai_calls": 0,
        "external_downloads": 0,
        "external_store_actions": 0,
    }


def prepare_task_skill_packages(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Prepare selected task Skills using the owning project's download policy."""

    root = Path(root).resolve()
    task_id = str(payload.get("task_id") or "").strip().lower()
    if not SAFE_ID.fullmatch(task_id):
        raise ValueError("任务编号无效。")
    context = find_task_context(load_workspace_config(root), task_id)
    if context is None:
        raise ValueError("任务不存在。")
    project_id = str(context[0].get("id") or "").strip().lower()
    raw_skills = payload.get("skill_ids")
    if not isinstance(raw_skills, list):
        raise ValueError("Skill 列表无效。")
    skill_ids = list(
        dict.fromkeys(
            str(item or "").strip().lower()
            for item in raw_skills
            if SAFE_ID.fullmatch(str(item or "").strip().lower())
        )
    )[:100]
    profile = _read(root)["profiles"].get(project_id, {})
    auto_download = bool(
        profile.get("auto_download_skills")
    ) if isinstance(profile, dict) and project_id else False
    results = [
        install_project_skill_package(
            root, project_id or "standalone", skill_id, allow_download=auto_download
        )
        for skill_id in skill_ids
    ]
    task_workspace = workspace_item_context(root, "task", task_id)
    project_workspace = (
        workspace_item_context(root, "project", project_id) if project_id else None
    )
    return {
        "ok": True,
        "task_id": task_id,
        "project_id": project_id,
        "auto_download_skills": auto_download,
        "prepared_count": len(results),
        "downloaded_count": sum(1 for item in results if item.get("downloaded")),
        "download_required_count": sum(
            1 for item in results if item.get("state") == "download_required"
        ),
        "project_copy_count": 0,
        "results": results,
        "workspace_context": {
            "project": project_workspace,
            "task": task_workspace,
            "discovery_order": [
                *([project_workspace["entry_manifest"]] if project_workspace else []),
                task_workspace["entry_manifest"],
            ],
            "copy_policy": "reference_canonical_files_do_not_duplicate",
        },
        "external_downloads": sum(1 for item in results if item.get("downloaded")),
        "external_store_actions": 0,
    }
