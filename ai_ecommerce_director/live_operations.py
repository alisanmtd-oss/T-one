from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


STATE_PATH = Path("data") / "real_world" / "live_operations.json"
_LOCK = threading.RLock()
_HOST_MODES = {"human", "digital_human", "unattended"}
_SESSION_STATES = {"scheduled", "ready_for_owner_review", "ended", "cancelled"}
_CONTROL_DRAFT_ACTIONS = {
    "pin_product",
    "change_product",
    "coupon_draft",
    "pace_note",
    "script_step_note",
    "comment_reply_draft",
    "moderation_note",
    "live_risk_flag",
    "human_takeover_note",
    "digital_host_pause_note",
    "stop_loss_note",
    "end_live_note",
}
_RECEIPT_METRIC_KEYS = (
    "duration_seconds",
    "duration_minutes",
    "viewer_count",
    "unique_viewers",
    "peak_concurrent_viewers",
    "average_watch_seconds",
    "likes",
    "comments",
    "shares",
    "new_followers",
    "product_clicks",
    "add_to_cart",
    "orders",
    "gmv",
    "refund_orders",
    "creator_commission",
    "ad_spend",
)
_CAPABILITY_MANIFEST = {
    "state": "reserved_local_control_only",
    "external_action_allowed": False,
    "layers": [
        {
            "id": "live_control_room",
            "name": "直播中控",
            "purpose": "排期、脚本节奏、商品讲解、优惠草稿、评论观察、止损和人工接管。",
        },
        {
            "id": "host_assist",
            "name": "主播辅助",
            "purpose": "给真人主播/场控提供脚本、话术、节奏提醒和复盘建议。",
        },
        {
            "id": "digital_host",
            "name": "数字人主播",
            "purpose": "仅登记头像、声音、脚本、素材权利和披露要求；未复核前不能发声或开播。",
        },
        {
            "id": "unattended_live",
            "name": "全无人直播",
            "purpose": "未来能力预留；必须有平台允许、人工接管、风控阈值和负责人审批。",
        },
        {
            "id": "post_live_review",
            "name": "直播复盘",
            "purpose": "用平台导出或人工记录回传观看、时长、互动、商品点击、订单和 GMV。",
        },
    ],
    "hard_gates": [
        "no_start_or_stop_live_without_verified_connector_and_owner_approval",
        "no_public_speech_audio_video_without_rights_and_policy_review",
        "no_pin_product_coupon_price_or_ad_action_without_owner_review",
        "no_customer_pii_or_comment_auto_reply_without_moderation_gate",
        "human_takeover_protocol_required_for_digital_or_unattended_live",
    ],
    "default_metrics": [
        "live_duration_minutes",
        "viewer_count",
        "peak_concurrent_viewers",
        "average_watch_seconds",
        "likes",
        "comments",
        "shares",
        "new_followers",
        "product_clicks",
        "add_to_cart",
        "orders",
        "gmv",
        "refund_orders",
        "creator_commission",
        "ad_spend",
    ],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean(value: Any, limit: int = 240) -> str:
    return str(value or "").strip()[:limit]


def _load(root: Path) -> dict[str, Any]:
    path = root / STATE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    sessions = payload.get("sessions")
    payload["sessions"] = sessions if isinstance(sessions, list) else []
    payload.setdefault("schema_version", 1)
    return payload


def _save(root: Path, payload: dict[str, Any]) -> None:
    path = root / STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _find_session(payload: dict[str, Any], session_id: str) -> dict[str, Any]:
    normalized = _clean(session_id, 100)
    for item in payload.get("sessions", []):
        if isinstance(item, dict) and item.get("id") == normalized:
            return item
    raise ValueError("找不到这个直播计划。")


def live_operations_snapshot(root: Path, project_id: str = "") -> dict[str, Any]:
    with _LOCK:
        payload = _load(root)
    normalized_project = _clean(project_id, 120)
    sessions = [
        dict(item)
        for item in payload.get("sessions", [])
        if isinstance(item, dict)
        and (not normalized_project or item.get("project_id") == normalized_project)
    ]
    sessions.sort(key=lambda item: str(item.get("scheduled_at") or ""), reverse=True)
    return {
        "ok": True,
        "schema_version": int(payload.get("schema_version") or 1),
        "session_count": len(sessions),
        "scheduled_count": sum(1 for item in sessions if item.get("status") == "scheduled"),
        "ended_count": sum(1 for item in sessions if item.get("status") == "ended"),
        "digital_human_count": sum(
            1 for item in sessions if item.get("host_mode") == "digital_human"
        ),
        "unattended_count": sum(
            1 for item in sessions if item.get("host_mode") == "unattended"
        ),
        "external_action_count": 0,
        "capability_manifest": _CAPABILITY_MANIFEST,
        "supported_control_actions": sorted(_CONTROL_DRAFT_ACTIONS),
        "execution_state": "本地中控预留；未连接真实直播间，不能自动开播、发声、挂品、发券或投流。",
        "sessions": sessions[:50],
        "truth_boundary": "本地计划、预检、中控草稿和导入复盘可用；未连接平台时不代表已开播、已挂品、已发券或已成交。",
    }


def schedule_live_session(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    project_id = _clean(request.get("project_id"), 120)
    platform = _clean(request.get("platform"), 80)
    scheduled_at = _clean(request.get("scheduled_at"), 80)
    title = _clean(request.get("title"), 180)
    if not project_id:
        raise ValueError("请选择直播所属项目。")
    if not platform:
        raise ValueError("请选择直播平台。")
    if not scheduled_at:
        raise ValueError("请填写直播排期。")
    if not title:
        raise ValueError("请填写直播主题。")
    host_mode = _clean(request.get("host_mode"), 40) or "human"
    if host_mode not in _HOST_MODES:
        raise ValueError("直播方式必须是人工、数字人或无人直播。")
    now = _now()
    session = {
        "id": "live-" + uuid4().hex[:16],
        "created_at": now,
        "updated_at": now,
        "project_id": project_id,
        "platform": platform,
        "country_site": _clean(request.get("country_site"), 40),
        "store_binding_id": _clean(request.get("store_binding_id"), 120),
        "channel_account_id": _clean(request.get("channel_account_id"), 120),
        "title": title,
        "scheduled_at": scheduled_at,
        "host_mode": host_mode,
        "automation_level": _clean(request.get("automation_level"), 60)
        or ("human_assisted" if host_mode == "human" else "reserved_gate_only"),
        "expected_duration_minutes": _clean(request.get("expected_duration_minutes"), 40),
        "runbook_ref": _clean(request.get("runbook_ref"), 240),
        "offer_plan_ref": _clean(request.get("offer_plan_ref"), 240),
        "moderation_policy_ref": _clean(request.get("moderation_policy_ref"), 240),
        "human_takeover_ref": _clean(request.get("human_takeover_ref"), 240),
        "digital_avatar_asset_ref": _clean(request.get("digital_avatar_asset_ref"), 240),
        "digital_voice_asset_ref": _clean(request.get("digital_voice_asset_ref"), 240),
        "disclosure_script_ref": _clean(request.get("disclosure_script_ref"), 240),
        "status": "scheduled",
        "product_refs": [
            _clean(item, 160) for item in request.get("product_refs", []) if _clean(item, 160)
        ][:100],
        "script_ref": _clean(request.get("script_ref"), 240),
        "rights_evidence_refs": [
            _clean(item, 240)
            for item in request.get("rights_evidence_refs", [])
            if _clean(item, 240)
        ][:50],
        "connector_verified": bool(request.get("connector_verified") is True),
        "owner_approved_external_action": False,
        "external_action_count": 0,
        "control_drafts": [],
        "receipt": None,
    }
    with _LOCK:
        payload = _load(root)
        payload["sessions"].append(session)
        payload["updated_at"] = now
        _save(root, payload)
    return {"ok": True, "session": session, "external_action_count": 0}


def preflight_live_session(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        payload = _load(root)
        session = _find_session(payload, request.get("session_id"))
        missing: list[str] = []
        if not session.get("store_binding_id"):
            missing.append("exact_store_binding")
        if not session.get("channel_account_id"):
            missing.append("exact_live_channel_account")
        if not session.get("product_refs"):
            missing.append("product_refs")
        if not session.get("script_ref"):
            missing.append("script_ref")
        if session.get("host_mode") in {"digital_human", "unattended"}:
            if not session.get("rights_evidence_refs"):
                missing.append("voice_likeness_script_and_media_rights_evidence")
            if not session.get("digital_avatar_asset_ref"):
                missing.append("digital_avatar_asset_ref")
            if not session.get("digital_voice_asset_ref"):
                missing.append("digital_voice_asset_ref")
            if not session.get("disclosure_script_ref"):
                missing.append("ai_host_disclosure_script")
            if not session.get("human_takeover_ref"):
                missing.append("human_takeover_protocol")
            if not session.get("connector_verified"):
                missing.append("verified_live_connector")
            missing.append("platform_policy_and_owner_review")
        elif not session.get("connector_verified"):
            missing.append("verified_live_connector")
        status = "ready_for_owner_review" if not missing else "blocked"
        session["preflight"] = {
            "checked_at": _now(),
            "status": status,
            "missing": missing,
            "external_action_count": 0,
        }
        if status == "ready_for_owner_review":
            session["status"] = "ready_for_owner_review"
        session["updated_at"] = _now()
        payload["updated_at"] = session["updated_at"]
        _save(root, payload)
        return {
            "ok": status == "ready_for_owner_review",
            "status": status,
            "missing": missing,
            "session": dict(session),
            "external_action_count": 0,
        }


def save_live_control_draft(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    action = _clean(request.get("action"), 80)
    if action not in _CONTROL_DRAFT_ACTIONS:
        raise ValueError("请选择受支持的直播中控草稿动作。")
    with _LOCK:
        payload = _load(root)
        session = _find_session(payload, request.get("session_id"))
        if session.get("status") in {"ended", "cancelled"}:
            raise ValueError("已结束或取消的直播不能新增中控草稿。")
        draft = {
            "id": "live-control-" + uuid4().hex[:14],
            "created_at": _now(),
            "action": action,
            "target_ref": _clean(request.get("target_ref"), 180),
            "note": _clean(request.get("note"), 800),
            "status": "owner_review_required",
            "external_action_performed": False,
            "execution_boundary": "local_draft_only_not_sent_to_platform",
        }
        session.setdefault("control_drafts", []).append(draft)
        session["updated_at"] = _now()
        payload["updated_at"] = session["updated_at"]
        _save(root, payload)
    return {
        "ok": True,
        "draft": draft,
        "external_action_count": 0,
        "message": "直播中控草稿已保存；未向平台发送。",
    }


def record_live_receipt(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    source_ref = _clean(request.get("source_ref"), 300)
    if not source_ref:
        raise ValueError("请提供直播后台、平台导出或人工复盘的来源引用。")
    metrics = request.get("metrics") if isinstance(request.get("metrics"), dict) else {}
    safe_metrics: dict[str, float] = {}
    for key in _RECEIPT_METRIC_KEYS:
        value = metrics.get(key)
        if value is None:
            continue
        try:
            safe_metrics[key] = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"直播指标 {key} 必须是数字。") from exc
    with _LOCK:
        payload = _load(root)
        session = _find_session(payload, request.get("session_id"))
        receipt = {
            "recorded_at": _now(),
            "source_ref": source_ref,
            "source_kind": _clean(request.get("source_kind"), 80) or "manual_observation",
            "metrics": safe_metrics,
            "fact_status": "imported_observation",
            "external_action_count": 0,
        }
        session["receipt"] = receipt
        session["status"] = "ended"
        session["updated_at"] = _now()
        payload["updated_at"] = session["updated_at"]
        _save(root, payload)
    return {"ok": True, "receipt": receipt, "external_action_count": 0}


def validate_live_state(root: Path) -> list[str]:
    errors: list[str] = []
    payload = _load(root)
    seen: set[str] = set()
    for item in payload.get("sessions", []):
        if not isinstance(item, dict):
            errors.append("session_not_object")
            continue
        session_id = _clean(item.get("id"), 100)
        if not session_id or session_id in seen:
            errors.append("missing_or_duplicate_session_id")
        seen.add(session_id)
        if item.get("host_mode") not in _HOST_MODES:
            errors.append(f"{session_id}:invalid_host_mode")
        if item.get("status") not in _SESSION_STATES:
            errors.append(f"{session_id}:invalid_status")
        if int(item.get("external_action_count") or 0) != 0:
            errors.append(f"{session_id}:external_action_count_nonzero")
    return errors
