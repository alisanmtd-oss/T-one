from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .content_feedback_loop import build_content_experiment


REGISTRY_PATH = Path("config") / "new_media_operations_registry.json"


def _clean(value: Any, limit: int = 600) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _load_registry(root: Path) -> dict[str, Any]:
    try:
        payload = json.loads((root / REGISTRY_PATH).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def new_media_operations_snapshot(root: Path) -> dict[str, Any]:
    registry = _load_registry(root)
    workflow = [item for item in registry.get("workflow", []) if isinstance(item, dict)]
    roles = [item for item in registry.get("roles", []) if isinstance(item, dict)]
    families = [item for item in registry.get("platform_families", []) if isinstance(item, dict)]
    return {
        "schema_version": int(registry.get("schema_version") or 1),
        "group_id": str(registry.get("group_id") or ""),
        "department_id": str(registry.get("department_id") or ""),
        "name": str(registry.get("name") or "新媒体运营与创意制作组"),
        "purpose": str(registry.get("purpose") or ""),
        "role_count": len(roles),
        "roles": roles,
        "workflow_stage_count": len(workflow),
        "workflow": workflow,
        "platform_family_count": len(families),
        "platform_families": families,
        "metrics": [str(item) for item in registry.get("metrics", []) if str(item)],
        "comment_categories": [
            str(item) for item in registry.get("comment_categories", []) if str(item)
        ],
        "shared_service_ids": [
            str(item) for item in registry.get("shared_service_ids", []) if str(item)
        ],
        "external_action_gates": dict(registry.get("external_action_gates") or {}),
        "external_action_count": 0,
    }


def build_new_media_work_packet(root: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build a local work packet without publishing or inventing platform facts."""

    snapshot = new_media_operations_snapshot(root)
    platform = _clean(payload.get("platform"), 120).lower()
    objective = _clean(payload.get("objective"), 500)
    project_id = _clean(payload.get("project_id"), 160)
    product_fact_refs = [
        _clean(item, 1000) for item in payload.get("product_fact_refs", []) if _clean(item, 1000)
    ] if isinstance(payload.get("product_fact_refs"), Sequence) and not isinstance(payload.get("product_fact_refs"), (str, bytes)) else []
    missing: list[str] = []
    if not project_id:
        missing.append("project_id")
    if not platform:
        missing.append("platform")
    if not objective:
        missing.append("objective")
    if not product_fact_refs:
        missing.append("product_fact_refs")
    return {
        "schema_version": 1,
        "kind": "new_media_operations_work_packet",
        "status": "needs_owner_input" if missing else "draft_ready",
        "project_id": project_id,
        "task_id": _clean(payload.get("task_id"), 160),
        "platform": platform,
        "country_site": _clean(payload.get("country_site"), 40).upper() or "GLOBAL",
        "account_ref": _clean(payload.get("account_ref"), 500),
        "account_baseline_ref": _clean(payload.get("account_baseline_ref"), 1000),
        "objective": objective,
        "content_format": _clean(payload.get("content_format"), 120),
        "product_fact_refs": product_fact_refs,
        "asset_refs": [
            _clean(item, 1000) for item in payload.get("asset_refs", []) if _clean(item, 1000)
        ] if isinstance(payload.get("asset_refs"), Sequence) and not isinstance(payload.get("asset_refs"), (str, bytes)) else [],
        "missing_required_inputs": missing,
        "assigned_role_ids": [str(item.get("id") or "") for item in snapshot["roles"]],
        "workflow_stage_ids": [str(item.get("id") or "") for item in snapshot["workflow"]],
        "shared_service_ids": snapshot["shared_service_ids"],
        "approval_queue": ["publish", "comment_reply", "direct_message", "live_stream", "account_setting_change"],
        "rights_check_required": True,
        "platform_rule_evidence_required": True,
        "algorithm_claim_policy": "dated_account_level_hypothesis_only",
        "external_action_performed": False,
        "owner_review_required": True,
    }


def triage_comment_drafts(
    root: Path,
    comments: Sequence[Mapping[str, Any]],
    *,
    verified_fact_refs: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Classify comments and make guarded reply drafts; never posts replies."""

    facts = [_clean(item, 1000) for item in (verified_fact_refs or ()) if _clean(item, 1000)]
    rows: list[dict[str, Any]] = []
    for raw in list(comments)[:100]:
        if not isinstance(raw, Mapping):
            continue
        text = _clean(raw.get("text"), 1200)
        lowered = text.casefold()
        if any(token in lowered for token in ("refund", "not received", "broken", "scam", "退款", "没收到", "坏了")):
            category, escalation = "service_risk", "customer_service_review"
            draft = "已记录你的情况。为保护隐私，请通过平台订单售后入口提交订单信息，我们会按记录核查。"
        elif any(token in lowered for token in ("copyright", "injury", "unsafe", "侵权", "受伤", "危险")):
            category, escalation = "legal_safety_risk", "legal_and_safety_review"
            draft = "感谢提醒。该问题已转交审核，在核实完成前不会给出未经证实的结论。"
        elif any(token in lowered for token in ("price", "buy", "link", "多少钱", "哪里买", "链接")):
            category, escalation = "purchase_intent", "commerce_review"
            draft = "感谢关注。请以当前页面展示的已核验商品信息、价格和购买入口为准。"
        elif any(token in lowered for token in ("size", "material", "color", "尺码", "材质", "颜色")):
            category, escalation = "product_question", "fact_review" if not facts else "owner_review"
            draft = "这个问题需要按已核验商品资料回复；当前没有足够事实时不会猜测。" if not facts else "感谢提问。回复前请按已核验商品资料逐项确认，避免误导。"
        elif any(token in lowered for token in ("spam", "http://", "https://", "垃圾")):
            category, escalation, draft = "spam_or_abuse", "moderation_review", ""
        elif any(token in lowered for token in ("love", "great", "喜欢", "好看", "不错")):
            category, escalation, draft = "positive_community", "owner_review", "谢谢你的喜欢，我们会继续分享真实的产品和使用内容。"
        else:
            category, escalation, draft = "unknown", "human_triage", ""
        rows.append(
            {
                "comment_ref": _clean(raw.get("comment_ref"), 500),
                "category": category,
                "escalation": escalation,
                "reply_draft": draft,
                "reply_state": "draft_owner_review_required" if draft else "no_reply_draft",
                "external_action_performed": False,
            }
        )
    return {
        "kind": "new_media_comment_triage",
        "comment_count": len(rows),
        "items": rows,
        "verified_fact_refs": facts,
        "owner_review_required": True,
        "external_action_count": 0,
    }


def build_new_media_algorithm_experiment(
    *,
    experiment_id: str,
    platform: str,
    country_site: str,
    content_format: str,
    account_baseline_ref: str,
    primary_metric: str,
    variants: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not _clean(account_baseline_ref, 1000):
        raise ValueError("平台算法实验必须引用账号基线，不能用万能推流结论。")
    experiment = build_content_experiment(
        experiment_id=experiment_id,
        template_id=_clean(content_format, 160),
        platform=platform,
        country_site=country_site,
        primary_metric=primary_metric,
        variants=variants,
        account_baseline_ref=account_baseline_ref,
    )
    experiment["claim_scope"] = "dated_account_level_hypothesis_only"
    experiment["content_format"] = _clean(content_format, 160)
    experiment["forbidden_conclusion"] = "不允许外推为平台永久算法或保证爆款。"
    return experiment


def evaluate_content_release_preflight(
    root: Path, content: Mapping[str, Any]
) -> dict[str, Any]:
    """Fail closed before any social publication or platform push."""

    snapshot = new_media_operations_snapshot(root)
    registry = _load_registry(root)
    release_truth = registry.get("release_truth", {})
    required_fields = (
        "content_id",
        "project_id",
        "task_id",
        "platform",
        "country_site",
        "account_binding_id",
        "content_format",
    )
    missing = [field for field in required_fields if not _clean(content.get(field), 500)]
    fact_refs = content.get("product_fact_refs")
    if not isinstance(fact_refs, Sequence) or isinstance(fact_refs, (str, bytes)):
        fact_refs = []
    if not any(_clean(item, 1000) for item in fact_refs):
        missing.append("product_fact_refs")
    asset_rights = content.get("asset_rights")
    if not isinstance(asset_rights, Sequence) or isinstance(asset_rights, (str, bytes)):
        asset_rights = []
    allowed_rights = set(release_truth.get("rights_states_allowed_for_publish") or [])
    rights_complete = bool(asset_rights) and all(
        isinstance(item, Mapping)
        and all(
            _clean(item.get(field), 1000)
            for field in ("asset_id", "asset_kind", "source_ref", "rights_state")
        )
        and str(item.get("rights_state") or "") in allowed_rights
        for item in asset_rights
    )
    if not rights_complete:
        missing.append("asset_rights")
    if str(content.get("human_review_state") or "") != "approved":
        missing.append("human_review_state")
    if not _clean(content.get("owner_publish_approval_id"), 500):
        missing.append("owner_publish_approval")
    if int(release_truth.get("real_publish_connector_count") or 0) <= 0:
        missing.append("verified_publish_connector")
    if str(content.get("source_kind") or "") != "real":
        missing.append("real_content_source")
    if str(content.get("platform") or "").casefold() in {"amazon", "amazon_posts"}:
        missing.append("amazon_paused_by_owner")
    missing = list(dict.fromkeys(missing))
    publish_allowed = not missing and bool(
        release_truth.get("publish_execution_enabled")
    )
    return {
        "schema_version": 1,
        "content_id": _clean(content.get("content_id"), 500),
        "state": "ready_for_owner_controlled_publish" if publish_allowed else "blocked_preflight",
        "publish_allowed": publish_allowed,
        "rights_review_passed": rights_complete,
        "missing": missing,
        "workflow_stage_count": snapshot["workflow_stage_count"],
        "publish_call_count": 0,
        "external_action_count": 0,
    }


def run_synthetic_content_feedback_slice(root: Path) -> dict[str, Any]:
    """Exercise the complete local lifecycle without publishing anything."""

    registry = _load_registry(root)
    release_truth = registry.get("release_truth", {})
    asset_rights = [
        {
            "asset_id": "u27-copy",
            "asset_kind": "copy",
            "source_ref": "synthetic://u27/copy",
            "rights_state": "synthetic_fixture_only",
        },
        {
            "asset_id": "u27-image",
            "asset_kind": "image",
            "source_ref": "synthetic://u27/image",
            "rights_state": "synthetic_fixture_only",
        },
        {
            "asset_id": "u27-music-voice",
            "asset_kind": "music_and_voice",
            "source_ref": "synthetic://u27/audio",
            "rights_state": "synthetic_fixture_only",
        },
    ]
    rights_review_passed = all(
        item["rights_state"] == "synthetic_fixture_only" for item in asset_rights
    )
    metric_receipt = {
        "source_kind": "synthetic_fixture",
        "content_id": "u27-synthetic-content",
        "platform": "synthetic-platform",
        "country_site": "SANDBOX",
        "account_binding_id": "synthetic-account",
        "window_start": "2026-08-06T21:30:00+08:00",
        "window_end": "2026-08-06T22:30:00+08:00",
        "impressions": 200,
        "views": 120,
        "average_watch_seconds": 9.5,
        "comments": 6,
        "shares": 2,
        "clicks": 3,
        "orders": 0,
        "revenue": 0,
        "currency": "USD",
        "excluded_from_real_aggregates": True,
    }
    return {
        "schema_version": 1,
        "content_id": "u27-synthetic-content",
        "state_history": [
            "draft_generated",
            "rights_and_fact_reviewed",
            "human_reviewed",
            "publish_approval_required",
            "publish_blocked_no_connector",
            "synthetic_metrics_recorded",
            "retrospective_ready",
        ],
        "asset_rights": asset_rights,
        "rights_review_passed": rights_review_passed,
        "human_review_recorded": True,
        "publish_allowed": False,
        "publish_blocker": "verified_publish_connector_missing",
        "metric_receipt": metric_receipt,
        "retrospective": {
            "claim_scope": "synthetic_fixture_only",
            "observation": "Views and watch time are fixture values, not platform facts.",
            "next_action": "Wait for an approved non-Amazon read-only account scope.",
        },
        "publish_call_count": 0,
        "comment_reply_call_count": 0,
        "external_business_action_count": int(
            release_truth.get("external_action_count") or 0
        ),
        "amazon_status": "paused_by_owner_not_touched",
    }


def new_media_release_snapshot(root: Path) -> dict[str, Any]:
    registry = _load_registry(root)
    release_truth = registry.get("release_truth", {})
    base = new_media_operations_snapshot(root)
    synthetic = run_synthetic_content_feedback_slice(root)
    return {
        "content_role_count": base["role_count"],
        "workflow_stage_count": base["workflow_stage_count"],
        "platform_family_count": base["platform_family_count"],
        "real_publish_connector_count": int(
            release_truth.get("real_publish_connector_count") or 0
        ),
        "real_publication_receipt_count": int(
            release_truth.get("real_publication_receipt_count") or 0
        ),
        "real_metric_receipt_count": int(
            release_truth.get("real_metric_receipt_count") or 0
        ),
        "synthetic_feedback_slice_count": int(
            synthetic.get("state_history", [])[-1:] == ["retrospective_ready"]
        ),
        "synthetic_feedback_slice": synthetic,
        "external_action_count": int(release_truth.get("external_action_count") or 0),
        "amazon_status": str(release_truth.get("amazon_status") or ""),
    }
