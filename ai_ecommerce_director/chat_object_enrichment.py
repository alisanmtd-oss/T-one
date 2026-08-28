from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .browser_environments import browser_environment_snapshot
from .task_execution_runtime import append_business_event
from .workspace_schema import iter_project_stores


BROWSER_ENVIRONMENT_REF = re.compile(
    r"(?i)(?:比特(?:浏览器|窗口|环境)?|bit\s*browser|bitbrowser|browser\s*profile|浏览器环境)\s*[-#：:]?\s*(\d{1,5})"
)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _read_json(path: Path, default: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default
    return value


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _detect_bitbrowser_sequences(message: str) -> list[int]:
    sequences: list[int] = []
    for match in BROWSER_ENVIRONMENT_REF.finditer(message or ""):
        sequence = _as_int(match.group(1))
        if sequence and sequence not in sequences:
            sequences.append(sequence)
    return sequences


def _safe_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(profile, dict):
        return {}
    tags = profile.get("tags") if isinstance(profile.get("tags"), list) else []
    return {
        "id": _clean(profile.get("id"), 160),
        "sequence": _as_int(profile.get("sequence")),
        "name": _clean(profile.get("name"), 120),
        "group_id": _clean(profile.get("group_id"), 120),
        "tags": [_clean(item, 80) for item in tags[:12] if _clean(item, 80)],
    }


def _bitbrowser_provider(snapshot: dict[str, Any]) -> dict[str, Any]:
    providers = snapshot.get("providers") if isinstance(snapshot.get("providers"), list) else []
    for provider in providers:
        if isinstance(provider, dict) and str(provider.get("id") or "").lower() == "bitbrowser":
            return {
                "id": "bitbrowser",
                "name": _clean(provider.get("name"), 80) or "比特浏览器",
                "status": _clean(provider.get("status"), 80),
                "installed": bool(provider.get("installed")),
                "supports_automatic_profile_open": bool(provider.get("supports_automatic_profile_open")),
                "requires_manual_security_checkpoint": True,
                "message": _clean(provider.get("message"), 200),
                "profiles": [
                    _safe_profile(item)
                    for item in provider.get("profiles", [])
                    if isinstance(item, dict)
                ],
            }
    return {
        "id": "bitbrowser",
        "name": "比特浏览器",
        "status": "unknown",
        "installed": False,
        "supports_automatic_profile_open": False,
        "requires_manual_security_checkpoint": True,
        "message": "未读取到比特浏览器状态",
        "profiles": [],
    }


def _profile_by_sequence(provider: dict[str, Any], sequence: int) -> dict[str, Any]:
    for profile in provider.get("profiles", []):
        if isinstance(profile, dict) and _as_int(profile.get("sequence")) == sequence:
            return profile
    return {}


def _store_uses_browser_sequence(store: dict[str, Any], provider: str, sequence: int) -> bool:
    if str(store.get("browser_provider") or "").strip().lower() == provider and _as_int(store.get("browser_profile_seq")) == sequence:
        return True
    execution_identity = str(store.get("execution_identity_id") or "").strip().lower()
    if execution_identity == f"browser:{provider}:{sequence}":
        return True
    external_id = str(store.get("external_id") or "").strip().lower()
    return f"{provider}-{sequence}" in external_id or f"{provider}:{sequence}" in external_id


def _task_summaries(store: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = store.get("tasks") if isinstance(store.get("tasks"), list) else []
    summaries: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        summaries.append(
            {
                "task_id": _clean(task.get("id"), 120),
                "task_name": _clean(task.get("name"), 120),
                "status": _clean(task.get("status"), 80),
                "conversation_role": _clean(task.get("conversation_role"), 80),
                "sidebar_visible": task.get("sidebar_visible", True) is not False,
            }
        )
    return summaries


def _match_workspace_routes(workspace: dict[str, Any], sequence: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    matched: list[dict[str, Any]] = []
    channel_gaps: list[dict[str, Any]] = []
    projects = workspace.get("projects") if isinstance(workspace.get("projects"), list) else []
    for project in projects:
        if not isinstance(project, dict):
            continue
        for channel, store in iter_project_stores(project):
            if not isinstance(channel, dict) or not isinstance(store, dict):
                continue
            if not _store_uses_browser_sequence(store, "bitbrowser", sequence):
                continue
            matched.append(
                {
                    "project_id": _clean(project.get("id"), 120),
                    "project_name": _clean(project.get("name"), 160),
                    "channel_id": _clean(channel.get("id"), 120),
                    "channel_name": _clean(channel.get("name"), 160),
                    "platform": _clean(channel.get("platform"), 80),
                    "country_site": _clean(channel.get("country_site"), 40),
                    "channel_status": _clean(channel.get("status"), 80),
                    "store_binding_id": _clean(store.get("id"), 120),
                    "store_name": _clean(store.get("name"), 160),
                    "store_status": _clean(store.get("status"), 80),
                    "store_model": _clean(store.get("store_model"), 80),
                    "ownership": _clean(store.get("ownership"), 80),
                    "route_key": _clean(store.get("route_key"), 160),
                    "external_id": _clean(store.get("external_id"), 160),
                    "browser_provider": "bitbrowser",
                    "browser_profile_seq": sequence,
                    "execution_identity_id": _clean(store.get("execution_identity_id"), 160),
                    "credential_ref_type": _clean(store.get("credential_ref_type"), 80),
                    "execution_domains": [
                        _clean(item, 80)
                        for item in (store.get("execution_domains") if isinstance(store.get("execution_domains"), list) else [])
                        if _clean(item, 80)
                    ],
                    "tasks": _task_summaries(store),
                    "amazon_owner_pause_respected": str(channel.get("platform") or "").lower() == "amazon",
                }
            )
        channels = project.get("channels") if isinstance(project.get("channels"), list) else []
        for channel in channels:
            if not isinstance(channel, dict):
                continue
            if channel.get("stores"):
                continue
            status = _clean(channel.get("status"), 80)
            if status != "needs_platform_store":
                continue
            channel_gaps.append(
                {
                    "project_id": _clean(project.get("id"), 120),
                    "project_name": _clean(project.get("name"), 160),
                    "channel_id": _clean(channel.get("id"), 120),
                    "channel_name": _clean(channel.get("name"), 160),
                    "platform": _clean(channel.get("platform"), 80),
                    "country_site": _clean(channel.get("country_site"), 40),
                    "status": status,
                    "required_dimensions": [
                        _clean(item, 80)
                        for item in (channel.get("required_dimensions") if isinstance(channel.get("required_dimensions"), list) else [])
                        if _clean(item, 80)
                    ],
                    "reason": "该平台已登记需求，但尚未绑定店铺/执行身份，不能从 BitBrowser profile 自动继承 Amazon 授权。",
                }
            )
    return matched, channel_gaps


def _candidate_fields(route: dict[str, Any]) -> list[dict[str, Any]]:
    fields = [
        ("project_id", route.get("project_id")),
        ("project_name", route.get("project_name")),
        ("channel_id", route.get("channel_id")),
        ("platform", route.get("platform")),
        ("country_site", route.get("country_site")),
        ("store_binding_id", route.get("store_binding_id")),
        ("store_name", route.get("store_name")),
        ("store_model", route.get("store_model")),
        ("ownership", route.get("ownership")),
        ("route_key", route.get("route_key")),
        ("browser_provider", route.get("browser_provider")),
        ("browser_profile_seq", route.get("browser_profile_seq")),
        ("execution_identity_id", route.get("execution_identity_id")),
        ("credential_ref_type", route.get("credential_ref_type")),
    ]
    return [
        {
            "field": field,
            "value": value,
            "status": "trusted_local_config_candidate",
            "evidence": "config/workspace_projects.json",
        }
        for field, value in fields
        if value not in (None, "")
    ]


def _credential_and_security_gates(message: str) -> list[dict[str, Any]]:
    mentions_credentials = any(keyword in message.lower() for keyword in ["账号", "邮箱", "密码", "mfa", "验证码", "email", "login"])
    gates = [
        {
            "field": "login_identifier_or_email",
            "status": "secure_vault_or_owner_visible_page_required",
            "auto_fill": False,
            "reason": "聊天可登记字段缺口，但不能从猜测或截图摘要中写成真实登录资料。",
        },
        {
            "field": "secret_or_mfa_material",
            "status": "never_plaintext_in_memory",
            "auto_fill": False,
            "reason": "口令、验证码、恢复方式只允许由负责人在安全凭据库或平台页面内处理。",
        },
        {
            "field": "store_platform_membership_inside_profile",
            "status": "visible_capture_required",
            "auto_fill": False,
            "reason": "一个浏览器环境可承载多个平台，但必须看到当前页面或已授权连接回执后才能确认。",
        },
    ]
    if mentions_credentials:
        gates.append(
            {
                "field": "credential_owner_review",
                "status": "required_before_persisting_any_sensitive_detail",
                "auto_fill": False,
                "reason": "用户消息提到账号/邮箱/口令类资料，因此只生成缺口和安全动作，不保存原始敏感值。",
            }
        )
    return gates


def _business_object_refs(routes: list[dict[str, Any]], sequence: int) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = [
        {
            "object_type": "browser_environment",
            "object_id": f"browser:bitbrowser:{sequence}",
            "source_ref": "config/workspace_projects.json",
        }
    ]
    for route in routes[:8]:
        refs.append(
            {
                "object_type": "store_binding",
                "object_id": str(route.get("store_binding_id") or ""),
                "source_ref": "config/workspace_projects.json",
            }
        )
    return [ref for ref in refs if ref.get("object_id")]


def _persist_observation(
    root: Path,
    *,
    sequence: int,
    routes: list[dict[str, Any]],
    context: dict[str, Any],
    actor: str,
) -> dict[str, Any] | None:
    if not routes:
        return None
    primary = routes[0]
    payload = {
        "event_type": "chat_object_enriched",
        "kind": "observation",
        "event_id": "chat-object-enrichment-" + uuid.uuid4().hex[:20],
        "workspace_id": "teelab-global-commerce",
        "project_id": str(primary.get("project_id") or context.get("project_id") or ""),
        "task_id": str(
            context.get("task_id")
            or (primary.get("tasks") or [{}])[0].get("task_id")
            or ""
        ),
        "conversation_id": str(context.get("conversation_id") or context.get("task_id") or ""),
        "actor": actor,
        "kind_confidence": "high",
        "statement": (
            f"聊天识别到 BitBrowser {sequence} 浏览器环境线索，并匹配到 "
            f"{len(routes)} 条本地店铺候选；仅登记结构化候选和门禁，外部动作 0。"
        ),
        "confidence": "high",
        "status": "candidate_ready_owner_gated",
        "source_refs": ["config/workspace_projects.json", "ai_ecommerce_director/chat_object_enrichment.py"],
        "business_object_refs": _business_object_refs(routes, sequence),
        "payload": {
            "browser_provider": "bitbrowser",
            "browser_profile_seq": sequence,
            "matched_store_ids": [route.get("store_binding_id") for route in routes if route.get("store_binding_id")],
            "candidate_fields": [item["field"] for item in _candidate_fields(primary)],
            "external_action_count": 0,
            "secrets_stored": False,
            "owner_confirmation_required_before_open": True,
        },
    }
    try:
        return append_business_event(root, payload, actor=actor)
    except Exception as exc:  # Keep chat useful even if the local event DB is locked.
        return {
            "event_error": _clean(exc, 240),
            "status": "observation_not_persisted",
        }


def enrich_chat_business_objects(
    root: Path,
    message: str,
    context: dict[str, Any] | None = None,
    *,
    actor: str = "desktop-owner",
    persist: bool = False,
    snapshot_provider: Callable[[Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Turn chat hints like “比特浏览器22” into safe business-object candidates.

    The function does not open browsers, read platform pages, store credentials,
    or call external services.  It only reads local workspace metadata and the
    existing browser-environment safe snapshot.
    """

    sequences = _detect_bitbrowser_sequences(message)
    if not sequences:
        return {
            "ok": False,
            "status": "no_enrichment_trigger",
            "external_action_count": 0,
            "secrets_stored": False,
        }

    root = Path(root)
    context = context or {}
    workspace = _read_json(root / "config" / "workspace_projects.json", {})
    sequence = sequences[0]
    snapshot_error = ""
    try:
        snapshot = (snapshot_provider or browser_environment_snapshot)(root)
    except Exception as exc:  # Snapshot is helpful but not required for local route matching.
        snapshot = {}
        snapshot_error = _clean(exc, 240)
    bitbrowser = _bitbrowser_provider(snapshot if isinstance(snapshot, dict) else {})
    profile = _profile_by_sequence(bitbrowser, sequence)
    routes, platform_gaps = _match_workspace_routes(workspace if isinstance(workspace, dict) else {}, sequence)
    primary_route = routes[0] if routes else {}
    profile_markers = " ".join(
        [
            str(profile.get("name") or ""),
            *[str(item) for item in (profile.get("tags") or [])],
        ]
    ).lower()
    amazon_context = (
        any(route.get("amazon_owner_pause_respected") for route in routes)
        or "amazon" in profile_markers
        or "amazon" in str(message or "").lower()
    )
    event = _persist_observation(root, sequence=sequence, routes=routes, context=context, actor=actor) if persist else None

    result = {
        "ok": True,
        "status": "candidate_ready" if routes else "browser_environment_unmatched",
        "generated_at": _now_iso(),
        "trigger": {
            "type": "browser_environment_reference",
            "provider": "bitbrowser",
            "profile_sequence": sequence,
            "message_saved": False,
            "message_redacted": True,
        },
        "recognized_objects": {
            "browser_environment": {
                "id": f"browser:bitbrowser:{sequence}",
                "provider": "bitbrowser",
                "profile_sequence": sequence,
                "provider_status": bitbrowser.get("status"),
                "provider_installed": bitbrowser.get("installed"),
                "supports_automatic_profile_open": bitbrowser.get("supports_automatic_profile_open"),
                "safe_profile": profile,
                "snapshot_error": snapshot_error,
            },
            "matched_store_routes": routes,
            "unbound_platform_candidates": platform_gaps,
        },
        "auto_fill_candidates": _candidate_fields(primary_route) if primary_route else [],
        "missing_or_owner_gated": _credential_and_security_gates(message),
        "recommended_next_actions": [] if amazon_context else [
            {
                "id": f"review-bitbrowser-{sequence}-candidates",
                "label": "先审核并应用本地候选字段",
                "status": "local_review_available" if routes else "needs_manual_mapping",
                "external_action": False,
            },
            {
                "id": f"open-bitbrowser-{sequence}",
                "label": f"打开 BitBrowser {sequence} 并读取可见页面",
                "status": "owner_confirmation_required",
                "external_action": True,
                "requires": ["负责人确认", "登录/MFA/验证码人工处理", "只读采集插件或可见页面回传"],
                "forbidden_without_confirmation": ["发布", "改价", "广告投放", "订单处理", "发货", "退款", "读取或保存口令"],
            },
            {
                "id": f"capture-visible-page-summary-{sequence}",
                "label": "把当前可见页面整理成店铺/平台/账号缺口候选",
                "status": "after_browser_open_and_owner_visible_page",
                "external_action": False,
            },
        ],
        "policy": {
            "chat_first": True,
            "one_browser_environment_may_host_multiple_platforms": True,
            "store_execution_identity_must_be_isolated": True,
            "external_action_count": 0,
            "secrets_stored": False,
            "amazon_owner_pause_respected": amazon_context,
            "owner_confirmation_required_before_open": True,
        },
        "business_event": event,
    }
    return result


def build_chat_object_enrichment_reply(result: dict[str, Any]) -> str:
    trigger = result.get("trigger") if isinstance(result.get("trigger"), dict) else {}
    sequence = _as_int(trigger.get("profile_sequence"))
    objects = result.get("recognized_objects") if isinstance(result.get("recognized_objects"), dict) else {}
    routes = objects.get("matched_store_routes") if isinstance(objects.get("matched_store_routes"), list) else []
    gaps = objects.get("unbound_platform_candidates") if isinstance(objects.get("unbound_platform_candidates"), list) else []
    browser = objects.get("browser_environment") if isinstance(objects.get("browser_environment"), dict) else {}
    profile = browser.get("safe_profile") if isinstance(browser.get("safe_profile"), dict) else {}

    lines = [f"我识别到你说的是 BitBrowser {sequence}，已经先按本地资料做了安全匹配。"]
    provider_status = browser.get("provider_status") or "unknown"
    lines.append(f"浏览器环境：provider=bitbrowser，profile={sequence}，本地状态={provider_status}；本轮没有打开浏览器，外部动作 0。")
    if profile:
        profile_name = profile.get("name") or f"环境 {sequence}"
        tags = "、".join(profile.get("tags") or []) or "无公开标签"
        lines.append(f"可见安全快照：{profile_name}，标签：{tags}。")

    if routes:
        lines.append("已能自动补的候选字段：")
        for route in routes[:3]:
            tasks = route.get("tasks") if isinstance(route.get("tasks"), list) else []
            first_task = tasks[0] if tasks else {}
            task_label = first_task.get("task_name") or first_task.get("task_id") or "未绑定任务"
            lines.append(
                "- "
                f"{route.get('project_name')} / {route.get('channel_name')} / {route.get('store_name')}："
                f"{route.get('platform')} {route.get('country_site')}，"
                f"{route.get('store_model')}，{route.get('ownership')}，"
                f"执行身份 {route.get('execution_identity_id')}，任务「{task_label}」。"
            )
    else:
        lines.append("本地工作区还没有把这个浏览器序号绑定到具体店铺，所以只能先记录为待映射浏览器环境。")

    if gaps:
        gap_labels = [
            f"{gap.get('channel_name')}({gap.get('status')})"
            for gap in gaps[:4]
            if gap.get("channel_name")
        ]
        if gap_labels:
            lines.append(
                "同项目里还有这些平台只登记了需求、没有店铺执行身份，不能自动继承这个浏览器授权："
                + "、".join(gap_labels)
                + "。"
            )

    profile_markers = " ".join(
        [
            str(profile.get("name") or ""),
            *[str(item) for item in (profile.get("tags") or [])],
        ]
    ).lower()
    policy = result.get("policy") if isinstance(result.get("policy"), dict) else {}
    amazon_context = (
        any(route.get("amazon_owner_pause_respected") for route in routes)
        or "amazon" in profile_markers
        or bool(policy.get("amazon_owner_pause_respected"))
    )
    if amazon_context:
        lines.append(
            "Amazon 当前仍按负责人指令暂停；Amazon 工作当前已按负责人要求暂停："
            "这里只做本地识别和候选补全，也不会借此恢复旧任务，"
            "不读取店铺、不研究、不处理上架、广告或订单；只有负责人明确说恢复 Amazon 后才继续。"
        )

    lines.append("账号邮箱、口令、验证码、MFA 和恢复方式不会明文保存；只能记录为“需要安全凭据库/负责人确认”的缺口。")
    lines.append("下一步如果你明确确认“打开 BitBrowser profile”，系统只应打开这个 profile 并只读采集可见页面，再把看到的平台、店铺、邮箱/账号缺口回填为待审核候选。")
    return "\n".join(lines)
