from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from .commerce_schema import AGENT_REGISTRY
from .task_execution_runtime import append_business_event, business_event_projection
from .workspace_runtime import load_workspace_config
from .workspace_schema import normalize_workspace_config


MODEL_PATH = Path("config") / "organization_operating_model.json"
MANAGEMENT_ACTIONS = {
    "owner_goal_set",
    "goal_decomposed",
    "priority_set",
    "work_assigned",
    "evidence_checked",
    "coaching_recorded",
    "blocker_escalated",
    "cross_group_handoff",
    "retrospective_recorded",
}
ORGANIZATION_ACTORS = {
    "group-operating-brain-pmo",
    "business-group-lead",
    "department-supervisor",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _agent_id(value: Any) -> str:
    return "-".join(part for part in re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).split() if part)


def _workspace_tasks(workspace: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}
    for project in workspace.get("projects", []):
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id") or "")
        for task in project.get("tasks", []):
            if isinstance(task, dict) and task.get("id"):
                tasks[str(task["id"])] = {**task, "project_id": project_id}
    return tasks


def _team_members(root: Path) -> dict[str, dict[str, Any]]:
    try:
        from .account import team_state

        state = team_state(root)
    except (OSError, TypeError, ValueError):
        return {}
    return {
        str(item.get("login_id") or ""): item
        for item in state.get("subaccounts", [])
        if isinstance(item, dict) and str(item.get("login_id") or "")
    }


def _member_state(login_id: str, members: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not login_id:
        return {"login_id": "", "status": "unassigned"}
    member = members.get(login_id)
    if not member:
        return {"login_id": login_id, "status": "missing_account"}
    return {
        "login_id": login_id,
        "display_name": str(member.get("display_name") or login_id),
        "status": "active" if member.get("active", True) else "inactive",
        "project_scope": str(member.get("project_scope") or "all"),
        "task_scope": str(member.get("task_scope") or "all"),
    }


def _require_manager_scope(
    session: dict[str, Any],
    project_id: str,
    task_id: str = "",
) -> None:
    if session.get("is_owner"):
        return
    permissions = {str(item) for item in session.get("permissions", []) if str(item)}
    if not {"team.manage", "admin.team"}.intersection(permissions):
        raise PermissionError("当前账号没有管理分配权限。")
    scope = str(session.get("project_scope") or "all")
    allowed_projects = {item.strip() for item in scope.split(",") if item.strip()}
    if scope != "all" and project_id not in allowed_projects:
        raise PermissionError("管理动作超出当前账号的项目范围。")
    task_scope = str(session.get("task_scope") or "all")
    allowed_tasks = {item.strip() for item in task_scope.split(",") if item.strip()}
    if task_scope != "all" and task_id not in allowed_tasks:
        raise PermissionError("管理动作超出当前账号的任务范围。")


def _resolve_organization_scope(
    model: dict[str, Any],
    *,
    business_group_id: Any = "",
    department_id: Any = "",
    project_id: Any = "",
) -> tuple[str, str]:
    group_id = _clean(business_group_id, 120)
    department = _clean(department_id, 120)
    project = _clean(project_id, 120)
    groups = {
        str(item.get("id") or ""): item
        for item in model.get("business_groups", [])
        if isinstance(item, dict) and str(item.get("id") or "")
    }
    if group_id and group_id not in groups:
        raise ValueError("事业组不存在。")

    department_groups: dict[str, str] = {}
    project_groups: dict[str, str] = {}
    for candidate_group_id, group in groups.items():
        for candidate_department in group.get("departments", []):
            if not isinstance(candidate_department, dict):
                continue
            candidate_department_id = str(candidate_department.get("id") or "")
            if candidate_department_id:
                department_groups[candidate_department_id] = candidate_group_id
        for candidate_project_id in group.get("project_ids", []):
            clean_project_id = str(candidate_project_id or "")
            if clean_project_id:
                project_groups[clean_project_id] = candidate_group_id

    department_group_id = department_groups.get(department, "") if department else ""
    if department and not department_group_id:
        raise ValueError("部门不存在。")
    if group_id and department_group_id and department_group_id != group_id:
        raise ValueError("部门不属于指定事业组。")

    project_group_id = project_groups.get(project, "") if project else ""
    if group_id and project_group_id and project_group_id != group_id:
        raise ValueError("项目不属于指定事业组。")
    if department_group_id and project_group_id and department_group_id != project_group_id:
        raise ValueError("部门与项目不属于同一事业组。")

    resolved_group_id = group_id or department_group_id or project_group_id
    return resolved_group_id, department


def _known_agents() -> dict[str, dict[str, Any]]:
    agents = {
        _agent_id(item.get("agent")): {
            "id": _agent_id(item.get("agent")),
            "name": str(item.get("agent") or ""),
            "version": str(item.get("version") or ""),
            "permissions": [str(value) for value in item.get("permissions", []) if str(value)],
            "automation_level": str(item.get("automation_level") or ""),
        }
        for item in AGENT_REGISTRY
        if isinstance(item, dict) and _agent_id(item.get("agent"))
    }
    for actor in ORGANIZATION_ACTORS:
        agents.setdefault(
            actor,
            {
                "id": actor,
                "name": actor.replace("-", " "),
                "version": "organization-v1",
                "permissions": ["read_scoped_events", "draft_management_actions"],
                "automation_level": "L0-L2",
            },
        )
    return agents


def _event_index(root: Path) -> dict[str, dict[str, Any]]:
    projection = business_event_projection(root, limit=1000)
    return {
        str(item.get("event_id") or ""): item
        for item in projection.get("events", [])
        if isinstance(item, dict) and str(item.get("event_id") or "")
    }


def _task_group_index(model: dict[str, Any], tasks: dict[str, dict[str, Any]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for group in model.get("business_groups", []):
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("id") or "")
        projects = {str(item) for item in group.get("project_ids", []) if str(item)}
        for task_id, task in tasks.items():
            if str(task.get("project_id") or "") in projects:
                index[task_id] = group_id
    return index


def organization_operating_snapshot(
    root: Path,
    workspace_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    model = _load_json(root / MODEL_PATH)
    workspace = (
        normalize_workspace_config(workspace_config)
        if isinstance(workspace_config, dict)
        else load_workspace_config(root)
    )
    tasks = _workspace_tasks(workspace)
    members = _team_members(root)
    task_group = _task_group_index(model, tasks)
    events = business_event_projection(root, limit=500)
    management_events = [
        event
        for event in events.get("events", [])
        if isinstance(event, dict)
        and str((event.get("payload") or {}).get("management_action") or "")
        in MANAGEMENT_ACTIONS
    ]
    handoff_events = [
        event
        for event in events.get("events", [])
        if isinstance(event, dict)
        and str((event.get("payload") or {}).get("handoff_id") or "")
    ]
    handoff_acknowledgements = {
        str((event.get("payload") or {}).get("handoff_id") or ""): event
        for event in handoff_events
        if str((event.get("payload") or {}).get("handoff_state") or "")
        == "acknowledged"
    }
    known_agents = _known_agents()
    service_names = {
        str(item.get("id") or ""): str(item.get("name") or item.get("id") or "")
        for item in model.get("shared_services", [])
        if isinstance(item, dict) and str(item.get("id") or "")
    }
    handoffs: list[dict[str, Any]] = []
    for event in handoff_events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if str(payload.get("handoff_state") or "") != "open":
            continue
        handoff_id = str(payload.get("handoff_id") or "")
        acknowledgement = handoff_acknowledgements.get(handoff_id)
        source_agent_id = str(payload.get("source_agent_id") or "")
        destination_agent_id = str(payload.get("destination_agent_id") or "")
        shared_service_ids = list(payload.get("shared_service_ids") or [])
        task_id = str(event.get("task_id") or "")
        handoffs.append(
            {
                "handoff_id": handoff_id,
                "project_id": str(event.get("project_id") or ""),
                "task_id": task_id,
                "task_name": str((tasks.get(task_id) or {}).get("name") or task_id),
                "source_agent_id": source_agent_id,
                "source_agent_name": str(
                    (known_agents.get(source_agent_id) or {}).get("name") or source_agent_id
                ),
                "destination_agent_id": destination_agent_id,
                "destination_agent_name": str(
                    (known_agents.get(destination_agent_id) or {}).get("name")
                    or destination_agent_id
                ),
                "shared_service_ids": shared_service_ids,
                "shared_service_names": [
                    service_names.get(str(service_id), str(service_id))
                    for service_id in shared_service_ids
                ],
                "expected_output": str(payload.get("expected_output") or ""),
                "acceptance_criteria": list(payload.get("acceptance_criteria") or []),
                "input_event_ids": list(payload.get("input_event_ids") or []),
                "state": "acknowledged" if acknowledgement else "open",
                "created_event_id": str(event.get("event_id") or ""),
                "created_at": str(event.get("created_at") or ""),
                "acknowledged_event_id": str((acknowledgement or {}).get("event_id") or ""),
                "acknowledged_summary": str((acknowledgement or {}).get("statement") or ""),
                "acknowledgement_mode": str(
                    ((acknowledgement or {}).get("payload") or {}).get(
                        "acknowledgement_mode"
                    )
                    or ""
                ),
            }
        )
    latest_assignment_by_task: dict[str, dict[str, Any]] = {}
    for event in management_events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        task_id = str(event.get("task_id") or "")
        if payload.get("management_action") == "work_assigned" and task_id:
            latest_assignment_by_task.setdefault(task_id, event)

    group_rows: list[dict[str, Any]] = []
    missing_management_roles: list[dict[str, str]] = []
    for group in model.get("business_groups", []):
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("id") or "")
        project_ids = [str(item) for item in group.get("project_ids", []) if str(item)]
        lead = _member_state(str(group.get("lead_login_id") or ""), members)
        if lead["status"] != "active":
            missing_management_roles.append(
                {"level": "business_group_lead", "scope_id": group_id, "status": lead["status"]}
            )
        departments: list[dict[str, Any]] = []
        for department in group.get("departments", []):
            if not isinstance(department, dict):
                continue
            department_id = str(department.get("id") or "")
            platforms = {str(item) for item in department.get("platforms", []) if str(item)}
            supervisor = _member_state(
                str(department.get("supervisor_login_id") or ""), members
            )
            if supervisor["status"] != "active":
                missing_management_roles.append(
                    {"level": "department_supervisor", "scope_id": department_id, "status": supervisor["status"]}
                )
            department_tasks = [
                {
                    "id": task_id,
                    "name": str(task.get("name") or task_id),
                    "project_id": str(task.get("project_id") or ""),
                    "platform": str(task.get("platform") or ""),
                    "status": str(task.get("status") or ""),
                    "assignment": (
                        latest_assignment_by_task.get(task_id, {}).get("payload") or {}
                    ),
                }
                for task_id, task in tasks.items()
                if str(task.get("project_id") or "") in project_ids
                and str(task.get("platform") or "") in platforms
            ]
            departments.append(
                {
                    "id": department_id,
                    "name": str(department.get("name") or department_id),
                    "supervisor": supervisor,
                    "platforms": sorted(platforms),
                    "shared_service_ids": [
                        str(item) for item in department.get("shared_service_ids", []) if str(item)
                    ],
                    "platform_families": [
                        str(item) for item in department.get("platform_families", []) if str(item)
                    ],
                    "role_ids": [
                        str(item) for item in department.get("role_ids", []) if str(item)
                    ],
                    "workflow_stage_ids": [
                        str(item) for item in department.get("workflow_stage_ids", []) if str(item)
                    ],
                    "metric_ids": [
                        str(item) for item in department.get("metric_ids", []) if str(item)
                    ],
                    "boundaries": [
                        str(item) for item in department.get("boundaries", []) if str(item)
                    ],
                    "task_count": len(department_tasks),
                    "tasks": department_tasks,
                }
            )
        group_rows.append(
            {
                "id": group_id,
                "name": str(group.get("name") or group_id),
                "project_ids": project_ids,
                "lead": lead,
                "department_count": len(departments),
                "task_count": sum(item["task_count"] for item in departments),
                "departments": departments,
                "management_event_count": sum(
                    1
                    for event in management_events
                    if str((event.get("payload") or {}).get("business_group_id") or "")
                    == group_id
                ),
            }
        )

    shared_services = [
        {
            "id": str(item.get("id") or ""),
            "name": str(item.get("name") or item.get("id") or "共享服务"),
            "approval_policy": str(item.get("approval_policy") or ""),
            "consumer_department_ids": sorted(
                {
                    str(department.get("id") or "")
                    for group in model.get("business_groups", [])
                    if isinstance(group, dict)
                    for department in group.get("departments", [])
                    if isinstance(department, dict)
                    and str(item.get("id") or "")
                    in {str(value) for value in department.get("shared_service_ids", [])}
                }
            ),
        }
        for item in model.get("shared_services", [])
        if isinstance(item, dict)
    ]
    return {
        "schema_version": 1,
        "organization_name": str(model.get("organization_name") or "T-one 集团经营组织"),
        "hierarchy": model.get("hierarchy") or [],
        "event_projection_source": str(events.get("source") or ""),
        "business_group_count": len(group_rows),
        "department_count": sum(item["department_count"] for item in group_rows),
        "shared_service_count": len(shared_services),
        "active_member_count": sum(1 for item in members.values() if item.get("active", True)),
        "management_event_count": len(management_events),
        "agent_handoff_count": len(handoffs),
        "open_agent_handoff_count": sum(1 for item in handoffs if item["state"] == "open"),
        "agent_handoffs": handoffs,
        "known_agents": list(known_agents.values()),
        "missing_management_roles": missing_management_roles,
        "business_groups": group_rows,
        "shared_services": shared_services,
        "task_group_index": task_group,
        "external_action_count": 0,
    }


def record_management_action(
    root: Path,
    payload: dict[str, Any],
    *,
    actor_session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    action = _clean(payload.get("action"), 80).lower()
    if action not in MANAGEMENT_ACTIONS:
        raise ValueError("管理动作类型无效。")
    workspace = load_workspace_config(root)
    tasks = _workspace_tasks(workspace)
    task_id = _clean(payload.get("task_id"), 120)
    project_id = _clean(payload.get("project_id"), 120)
    if task_id:
        task = tasks.get(task_id)
        if not task:
            raise ValueError("管理动作对应的任务不存在。")
        actual_project_id = str(task.get("project_id") or "")
        if project_id and project_id != actual_project_id:
            raise ValueError("管理动作的项目与任务不匹配。")
        project_id = actual_project_id
    session = actor_session or {"is_owner": True, "login_id": "owner"}
    _require_manager_scope(session, project_id, task_id)
    summary = _clean(payload.get("summary"), 1000)
    if not summary:
        raise ValueError("管理动作需要可读说明。")
    model = _load_json(root / MODEL_PATH)
    group_id, department_id = _resolve_organization_scope(
        model,
        business_group_id=payload.get("business_group_id"),
        department_id=payload.get("department_id"),
        project_id=project_id,
    )
    kind = "draft" if action in {"owner_goal_set", "goal_decomposed", "priority_set", "work_assigned", "cross_group_handoff"} else "observation"
    return append_business_event(
        root,
        {
            "event_type": "organization_management_action",
            "kind": kind,
            "workspace_id": str(workspace.get("workspace_id") or ""),
            "project_id": project_id,
            "task_id": task_id,
            "conversation_id": task_id,
            "actor": str(session.get("login_id") or "owner"),
            "statement": summary,
            "status": "owner_review_required" if kind == "draft" else "recorded",
            "source_refs": payload.get("evidence_refs") or [],
            "payload": {
                "management_action": action,
                "business_group_id": group_id,
                "department_id": department_id,
                "assignee_id": _clean(payload.get("assignee_id"), 120),
                "priority": _clean(payload.get("priority"), 40),
                "external_side_effect_observed": False,
            },
        },
        actor=str(session.get("login_id") or "owner"),
    )


def _clean_string_list(value: Any, *, limit: int, item_limit: int = 240) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError(f"列表最多允许 {limit} 项。")
    output: list[str] = []
    for item in value:
        clean = _clean(item, item_limit)
        if clean and clean not in output:
            output.append(clean)
    return output


def create_agent_handoff(
    root: Path,
    payload: dict[str, Any],
    *,
    actor_session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    workspace = load_workspace_config(root)
    tasks = _workspace_tasks(workspace)
    task_id = _clean(payload.get("task_id"), 120)
    project_id = _clean(payload.get("project_id"), 120)
    task = tasks.get(task_id)
    if not task:
        raise ValueError("智能体交接对应的任务不存在。")
    actual_project_id = str(task.get("project_id") or "")
    if project_id and project_id != actual_project_id:
        raise ValueError("智能体交接的项目与任务不匹配。")
    project_id = actual_project_id
    session = actor_session or {"is_owner": True, "login_id": "owner"}
    _require_manager_scope(session, project_id, task_id)

    agents = _known_agents()
    source_agent_id = _agent_id(payload.get("source_agent_id"))
    destination_agent_id = _agent_id(payload.get("destination_agent_id"))
    if source_agent_id not in agents or destination_agent_id not in agents:
        raise ValueError("交接双方必须来自当前 Agent 注册表或组织管理角色。")
    if source_agent_id == destination_agent_id:
        raise ValueError("交接来源与接收智能体不能相同。")

    model = _load_json(root / MODEL_PATH)
    group_id, department_id = _resolve_organization_scope(
        model,
        business_group_id=payload.get("business_group_id"),
        department_id=payload.get("department_id"),
        project_id=project_id,
    )
    known_services = {
        str(item.get("id") or "")
        for item in model.get("shared_services", [])
        if isinstance(item, dict) and str(item.get("id") or "")
    }
    shared_service_ids = _clean_string_list(payload.get("shared_service_ids"), limit=12, item_limit=120)
    unknown_services = sorted(set(shared_service_ids) - known_services)
    if unknown_services:
        raise ValueError("交接引用了不存在的共享能力。")

    event_index = _event_index(root)
    input_event_ids = _clean_string_list(payload.get("input_event_ids"), limit=20, item_limit=120)
    for event_id in input_event_ids:
        event = event_index.get(event_id)
        if not event:
            raise ValueError("交接输入事件不存在。")
        if str(event.get("project_id") or "") != project_id:
            raise PermissionError("交接输入事件超出当前项目范围。")
        event_task = str(event.get("task_id") or "")
        if event_task and event_task != task_id:
            raise PermissionError("交接输入事件超出当前任务范围。")

    expected_output = _clean(payload.get("expected_output"), 1000)
    acceptance_criteria = _clean_string_list(
        payload.get("acceptance_criteria"), limit=12, item_limit=500
    )
    if not expected_output or not acceptance_criteria:
        raise ValueError("智能体交接必须写清预期输出和验收标准。")
    handoff_id = "agent-handoff-" + uuid4().hex[:20]
    return append_business_event(
        root,
        {
            "event_type": "agent_handoff_created",
            "kind": "draft",
            "workspace_id": str(workspace.get("workspace_id") or ""),
            "project_id": project_id,
            "task_id": task_id,
            "conversation_id": task_id,
            "actor": str(session.get("login_id") or "owner"),
            "statement": _clean(
                payload.get("summary")
                or f"{source_agent_id} 向 {destination_agent_id} 交接：{expected_output}",
                1500,
            ),
            "status": "owner_review_required",
            "source_refs": input_event_ids,
            "payload": {
                "management_action": "cross_group_handoff",
                "handoff_id": handoff_id,
                "handoff_state": "open",
                "source_agent_id": source_agent_id,
                "destination_agent_id": destination_agent_id,
                "business_group_id": group_id,
                "department_id": department_id,
                "shared_service_ids": shared_service_ids,
                "input_event_ids": input_event_ids,
                "expected_output": expected_output,
                "acceptance_criteria": acceptance_criteria,
                "external_side_effect_observed": False,
            },
        },
        actor=str(session.get("login_id") or "owner"),
    )


def acknowledge_agent_handoff(
    root: Path,
    payload: dict[str, Any],
    *,
    actor_session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    handoff_id = _clean(payload.get("handoff_id"), 120)
    snapshot = organization_operating_snapshot(root)
    handoff = next(
        (
            item
            for item in snapshot.get("agent_handoffs", [])
            if isinstance(item, dict) and str(item.get("handoff_id") or "") == handoff_id
        ),
        None,
    )
    if not handoff:
        raise ValueError("智能体交接不存在。")
    if handoff.get("state") == "acknowledged":
        raise ValueError("智能体交接已经确认，不能重复确认。")
    project_id = str(handoff.get("project_id") or "")
    task_id = str(handoff.get("task_id") or "")
    session = actor_session or {
        "is_owner": True,
        "login_id": str(handoff.get("destination_agent_id") or ""),
        "agent_runtime": "t-one-owned-runtime",
    }
    _require_manager_scope(session, project_id, task_id)
    destination_agent_id = _agent_id(payload.get("destination_agent_id"))
    if destination_agent_id != str(handoff.get("destination_agent_id") or ""):
        raise PermissionError("只有交接指定的接收智能体可以确认。")
    runtime_id = _clean(session.get("agent_runtime"), 120)
    if _agent_id(session.get("login_id")) != destination_agent_id or not runtime_id:
        raise PermissionError("负责人可以发起接收请求，但不能冒充接收智能体写回执。")
    output_event_ids = _clean_string_list(payload.get("output_event_ids"), limit=20, item_limit=120)
    event_index = _event_index(root)
    for event_id in output_event_ids:
        event = event_index.get(event_id)
        if not event or str(event.get("project_id") or "") != project_id:
            raise PermissionError("交接回执引用了不存在或跨项目的输出事件。")
        if str(event.get("task_id") or "") != task_id:
            raise PermissionError("交接回执输出事件超出当前任务范围。")
    summary = _clean(payload.get("summary"), 1000)
    if not summary:
        raise ValueError("智能体交接确认必须包含可读回执。")
    return append_business_event(
        root,
        {
            "event_type": "agent_handoff_acknowledged",
            "kind": "observation",
            "workspace_id": str(load_workspace_config(root).get("workspace_id") or ""),
            "project_id": project_id,
            "task_id": task_id,
            "conversation_id": task_id,
            "actor": destination_agent_id,
            "statement": summary,
            "status": "acknowledged",
            "source_refs": [str(handoff.get("created_event_id") or ""), *output_event_ids],
            "payload": {
                "management_action": "evidence_checked",
                "handoff_id": handoff_id,
                "handoff_state": "acknowledged",
                "source_agent_id": str(handoff.get("source_agent_id") or ""),
                "destination_agent_id": destination_agent_id,
                "acknowledgement_mode": "local_agent_runtime",
                "runtime_id": runtime_id,
                "triggered_by": _clean(session.get("triggered_by"), 120),
                "output_event_ids": output_event_ids,
                "external_side_effect_observed": False,
            },
        },
        actor=destination_agent_id,
    )


def evaluate_management_cycle_preflight(
    root: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed before treating a management cycle as really staffed."""

    model = _load_json(root / MODEL_PATH)
    snapshot = organization_operating_snapshot(root)
    required_fields = (
        "cycle_id",
        "business_group_id",
        "department_id",
        "project_id",
        "task_id",
        "owner_directive_ref",
        "goal",
    )
    missing = [field for field in required_fields if not _clean(payload.get(field), 1000)]
    if str(payload.get("source_kind") or "") != "real":
        missing.append("real_cycle_source")

    group_id = _clean(payload.get("business_group_id"), 120)
    department_id = _clean(payload.get("department_id"), 120)
    project_id = _clean(payload.get("project_id"), 120)
    try:
        resolved_group, resolved_department = _resolve_organization_scope(
            model,
            business_group_id=group_id,
            department_id=department_id,
            project_id=project_id,
        )
    except ValueError as exc:
        missing.append("valid_organization_scope")
        resolved_group, resolved_department = "", ""
        scope_error = str(exc)
    else:
        scope_error = ""

    group = next(
        (
            item
            for item in snapshot.get("business_groups", [])
            if isinstance(item, dict) and str(item.get("id") or "") == resolved_group
        ),
        {},
    )
    department = next(
        (
            item
            for item in group.get("departments", [])
            if isinstance(item, dict)
            and str(item.get("id") or "") == resolved_department
        ),
        {},
    )
    if str((group.get("lead") or {}).get("status") or "") != "active":
        missing.append("active_business_group_lead")
    if str((department.get("supervisor") or {}).get("status") or "") != "active":
        missing.append("active_department_supervisor")

    workspace_tasks = _workspace_tasks(load_workspace_config(root))
    task_id = _clean(payload.get("task_id"), 120)
    task = workspace_tasks.get(task_id)
    if not task or str(task.get("project_id") or "") != project_id:
        missing.append("task_in_exact_project_scope")
    missing = list(dict.fromkeys(missing))
    return {
        "schema_version": 1,
        "cycle_id": _clean(payload.get("cycle_id"), 120),
        "state": "ready_for_staffed_cycle" if not missing else "blocked_preflight",
        "cycle_start_allowed": not missing,
        "business_group_id": resolved_group,
        "department_id": resolved_department,
        "project_id": project_id,
        "task_id": task_id,
        "scope_error": scope_error,
        "missing": missing,
        "external_action_count": 0,
    }


def run_synthetic_management_cycle(root: Path) -> dict[str, Any]:
    """Exercise the full hierarchy locally without inventing staffed managers."""

    model = _load_json(root / MODEL_PATH)
    truth = model.get("management_cycle_truth", {})
    required_cycle = [
        item
        for item in truth.get("required_cycle", [])
        if isinstance(item, dict)
        and _clean(item.get("action"), 120)
        and _clean(item.get("actor_level"), 120)
    ]
    scope = {
        "workspace_id": "synthetic-u28-workspace",
        "project_id": "synthetic-u28-project",
        "task_id": "synthetic-u28-task",
        "business_group_id": "commerce-and-brand-growth",
        "department_id": "content-and-social",
    }
    receipts = [
        {
            "sequence": index,
            "action": str(item.get("action") or ""),
            "actor_level": str(item.get("actor_level") or ""),
            "source_kind": "synthetic_fixture",
            "scope": dict(scope),
            "external_action_count": 0,
        }
        for index, item in enumerate(required_cycle, start=1)
    ]
    service_ids = [
        str(item.get("id") or "")
        for item in model.get("shared_services", [])
        if isinstance(item, dict) and str(item.get("id") or "")
    ]
    return {
        "schema_version": 1,
        "cycle_id": "u28-synthetic-management-cycle",
        "source_kind": "synthetic_fixture",
        "state_history": [item["action"] for item in receipts],
        "actor_level_history": [item["actor_level"] for item in receipts],
        "receipts": receipts,
        "scope": scope,
        "scope_immutable": bool(receipts)
        and all(item.get("scope") == scope for item in receipts),
        "shared_service_ids": service_ids,
        "shared_services_reused_not_duplicated": len(service_ids)
        == len(set(service_ids)),
        "real_staffed_cycle": False,
        "external_business_action_count": int(truth.get("external_action_count") or 0),
        "amazon_status": str(truth.get("amazon_status") or ""),
    }


def organization_management_cycle_snapshot(root: Path) -> dict[str, Any]:
    model = _load_json(root / MODEL_PATH)
    truth = model.get("management_cycle_truth", {})
    organization = organization_operating_snapshot(root)
    synthetic = run_synthetic_management_cycle(root)
    active_leads = sum(
        1
        for group in organization.get("business_groups", [])
        if isinstance(group, dict)
        and str((group.get("lead") or {}).get("status") or "") == "active"
    )
    active_supervisors = sum(
        1
        for group in organization.get("business_groups", [])
        if isinstance(group, dict)
        for department in group.get("departments", [])
        if isinstance(department, dict)
        and str((department.get("supervisor") or {}).get("status") or "")
        == "active"
    )
    return {
        "business_group_count": int(organization.get("business_group_count") or 0),
        "department_count": int(organization.get("department_count") or 0),
        "shared_service_count": int(organization.get("shared_service_count") or 0),
        "active_business_group_lead_count": active_leads,
        "active_department_supervisor_count": active_supervisors,
        "real_staffed_cycle_receipt_count": int(
            truth.get("real_staffed_cycle_receipt_count") or 0
        ),
        "synthetic_management_cycle_count": int(
            synthetic.get("state_history", [])[-1:] == ["retrospective_recorded"]
        ),
        "synthetic_management_cycle": synthetic,
        "external_action_count": int(truth.get("external_action_count") or 0),
        "amazon_status": str(truth.get("amazon_status") or ""),
    }
