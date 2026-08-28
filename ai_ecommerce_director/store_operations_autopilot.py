from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .execution_loop import latest_action_queue_path, load_action_queue_file, write_action_queue_file
from .storage import append_record, read_records
from .store_protection import apply_store_protection
from .types import IntakeRecord


STORE_OPS_REPORT_PREFIX = "store_operations_autopilot"


@dataclass(slots=True)
class StoreOperationsAutopilotResult:
    run_date: str
    platform: str
    country: str
    store_id: str
    runbook_records: list[IntakeRecord]
    task_records: list[IntakeRecord]
    action_queue: list[dict[str, Any]]
    action_queue_path: Path
    report: str
    report_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "platform": self.platform,
            "country": self.country,
            "store_id": self.store_id,
            "runbook_records": [record.to_dict() for record in self.runbook_records],
            "task_records": [record.to_dict() for record in self.task_records],
            "action_queue": self.action_queue,
            "action_queue_path": str(self.action_queue_path),
            "report": self.report,
            "report_path": str(self.report_path),
            "summary": {
                "runbook_count": len(self.runbook_records),
                "task_count": len(self.task_records),
                "action_count": len(self.action_queue),
                "pending_external_count": len([item for item in self.action_queue if item.get("requires_confirmation")]),
            },
        }


STORE_OPERATION_STEPS: list[dict[str, Any]] = [
    {
        "step_id": "store_access",
        "agent": "AI Store Access Operator",
        "name": "店铺登录与环境确认",
        "goal": "打开正确店铺窗口、确认国家/平台/店铺、记录是否已登录和是否需要人工验证。",
        "auto_level": "L0",
        "auto_tasks": ["identify_browser_profile", "check_logged_in_status", "record_manual_gate"],
        "pending_actions": ["login", "captcha_or_slider"],
        "never_auto": ["bypass_captcha", "save_plaintext_password", "change_account_security"],
    },
    {
        "step_id": "store_data_capture",
        "agent": "AI Store Data Analyst",
        "name": "店铺数据读取",
        "goal": "读取或导入销售、订单、退货、退款、广告、结算、商品销量和账号健康数据。",
        "auto_level": "L0-L2",
        "auto_tasks": ["capture_store_dashboard_read_only", "classify_store_metrics", "update_realtime_dashboard"],
        "pending_actions": ["download_reports", "copy_store_backend_tables"],
        "never_auto": ["export_customer_pii_to_external_ai", "change_report_settings"],
    },
    {
        "step_id": "listing_prepare",
        "agent": "AI Listing Operator",
        "name": "Listing 上架准备",
        "goal": "生成标题、卖点、图片要求、价格建议、合规词检查和平台字段映射。",
        "auto_level": "L2",
        "auto_tasks": ["generate_listing_draft", "scan_banned_terms", "prepare_image_requirements"],
        "pending_actions": ["publish_listing", "update_listing"],
        "never_auto": ["publish_confirmed_ip", "copy_competitor_listing"],
    },
    {
        "step_id": "pricing_promotion",
        "agent": "AI Promotion Operator",
        "name": "价格、折扣和活动",
        "goal": "计算保本 ROI、建议优惠、活动报名草稿和止损线。",
        "auto_level": "L2",
        "auto_tasks": ["calculate_breakeven_roi", "draft_discount_plan", "draft_campaign_plan"],
        "pending_actions": ["set_discount", "join_campaign", "update_price"],
        "never_auto": ["price_change_without_margin_check", "join_campaign_without_inventory_check"],
    },
    {
        "step_id": "content_publish",
        "agent": "AI Content Publishing Operator",
        "name": "素材与视频发布",
        "goal": "生成店铺自有脚本、达人脚本、标题标签、音乐检查、AIP 发布包。",
        "auto_level": "L2",
        "auto_tasks": ["generate_store_video_script", "generate_creator_video_brief", "check_music_copyright_and_mix"],
        "pending_actions": ["upload_asset", "publish_video_via_aip", "bind_tk_aip_publisher_account"],
        "never_auto": ["publish_unreviewed_video", "use_unlicensed_music", "cover_voice_with_bgm"],
    },
    {
        "step_id": "ads_operation",
        "agent": "AI Advertising Operator",
        "name": "广告与投流",
        "goal": "读取广告数据、计算 ROAS、生成冷启动/扩量/止损建议。",
        "auto_level": "L2",
        "auto_tasks": ["analyze_ads_roas", "draft_cold_start_plan", "draft_scale_or_stop_rule"],
        "pending_actions": ["launch_ad", "update_ad_budget", "pause_ad"],
        "never_auto": ["change_active_old_store_ads_without_override", "scale_without_stop_loss"],
    },
    {
        "step_id": "live_operation",
        "agent": "AI Live Room Operator",
        "name": "直播中控和挂品",
        "goal": "准备直播挂品、折扣、库存、话术、收割节奏和异常提醒。",
        "auto_level": "L2",
        "auto_tasks": ["draft_live_product_sequence", "draft_live_discount_plan", "check_live_inventory"],
        "pending_actions": ["add_live_product_link", "change_live_discount", "issue_coupon"],
        "never_auto": ["change_live_running_offer_without_confirmation"],
    },
    {
        "step_id": "order_fulfillment",
        "agent": "AI OMS Operator",
        "name": "订单、库存和发货",
        "goal": "读取订单、库存和物流异常，生成发货/补货/异常处理建议。",
        "auto_level": "L1-L2",
        "auto_tasks": ["classify_orders", "detect_stockout_risk", "draft_fulfillment_exception_plan"],
        "pending_actions": ["update_inventory", "ship_order"],
        "never_auto": ["ship_wrong_order", "change_inventory_without_stock_evidence"],
    },
    {
        "step_id": "customer_service",
        "agent": "AI Customer Service Operator",
        "name": "客服和售后",
        "goal": "分类咨询、投诉、差评、退货退款原因，生成回复草稿和改进建议。",
        "auto_level": "L2",
        "auto_tasks": ["triage_customer_ticket", "draft_customer_reply", "extract_complaint_pattern"],
        "pending_actions": ["send_message", "refund_customer"],
        "never_auto": ["promise_compensation_without_policy", "refund_without_order_review"],
    },
    {
        "step_id": "finance_settlement",
        "agent": "AI Finance Operator",
        "name": "财务、结算和利润",
        "goal": "整理平台费用、广告、物流、退款、税务字段和利润复盘。",
        "auto_level": "L1-L2",
        "auto_tasks": ["reconcile_settlement_report", "calculate_profit_snapshot", "draft_tax_accounting_questions"],
        "pending_actions": ["payment"],
        "never_auto": ["pay_invoice", "move_money", "submit_tax_filing"],
    },
    {
        "step_id": "risk_compliance",
        "agent": "AI Risk Operator",
        "name": "风控、侵权和平台规则",
        "goal": "扫描侵权、违禁词、政策风险、账号健康、二审和申诉材料。",
        "auto_level": "L1-L2",
        "auto_tasks": ["scan_ip_risk", "scan_policy_terms", "draft_appeal_package"],
        "pending_actions": ["delist_product", "appeal", "authorize_app"],
        "never_auto": ["publish_confirmed_ip", "authorize_unknown_app", "submit_appeal_without_review"],
    },
    {
        "step_id": "closed_loop_review",
        "agent": "AI Data Review Analyst",
        "name": "执行复盘和策略记忆",
        "goal": "把执行结果、销售变化、ROI、退货投诉和失败原因写入长期记忆。",
        "auto_level": "L5-internal",
        "auto_tasks": ["write_execution_memory", "update_strategy_weight", "generate_next_day_plan"],
        "pending_actions": [],
        "never_auto": ["hide_failed_result", "delete_evidence"],
    },
]


def run_store_operations_autopilot(
    root: Path,
    run_date: str | None = None,
    *,
    platform: str = "TikTok Shop",
    country: str = "US",
    store_id: str = "UNASSIGNED-STORE",
    store_mode: str = "protected_legacy_store",
) -> StoreOperationsAutopilotResult:
    root = root.resolve()
    actual_date = run_date or date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    ensure_store_profile(root, store_id=store_id, platform=platform, country=country, store_mode=store_mode, now=now)

    runbook_records = [
        build_runbook_record(step, actual_date, now, platform=platform, country=country, store_id=store_id)
        for step in STORE_OPERATION_STEPS
    ]
    task_records = [
        build_task_record(step, actual_date, now, platform=platform, country=country, store_id=store_id)
        for step in STORE_OPERATION_STEPS
    ]
    for record in [*runbook_records, *task_records]:
        append_record(root, record)

    new_actions = build_store_action_queue(root, runbook_records, actual_date, platform=platform, country=country, store_id=store_id)
    action_queue_path, merged_actions = merge_action_queue(root, actual_date, new_actions)
    report = build_store_ops_report(actual_date, platform, country, store_id, runbook_records, task_records, new_actions)
    report_path = write_store_ops_report(root, actual_date, report)
    return StoreOperationsAutopilotResult(
        run_date=actual_date,
        platform=platform,
        country=country,
        store_id=store_id,
        runbook_records=runbook_records,
        task_records=task_records,
        action_queue=merged_actions,
        action_queue_path=action_queue_path,
        report=report,
        report_path=report_path,
    )


def build_store_ops_payload(root: Path) -> dict[str, Any]:
    records = read_records(root)
    # Use today's action queue if present, otherwise fall back to the most
    # recent one. Runs (especially overnight) write the queue under their run
    # date, so hard-coding today's date hid all pending approvals the morning
    # after a run.
    action_queue_path = latest_action_queue_path(root)
    actions = load_action_queue_file(action_queue_path)
    store_profiles = [record for record in records if record.record_type == "store_profile"]
    ops_records = [
        record
        for record in records
        if record.record_type == "store_operation_event" and str(record.source).startswith("store_operations_autopilot")
    ]
    task_records = [
        record
        for record in records
        if record.record_type == "task_queue" and str(record.source).startswith("store_operations_autopilot")
    ]
    sensitive_actions = [item for item in actions if item.get("requires_confirmation")]
    return {
        "steps": STORE_OPERATION_STEPS,
        "storeProfiles": [record.to_dict() for record in sorted(store_profiles, key=lambda item: item.created_at, reverse=True)[:30]],
        "operationRunbooks": [record.to_dict() for record in sorted(ops_records, key=lambda item: item.created_at, reverse=True)[:40]],
        "tasks": [record.to_dict() for record in sorted(task_records, key=lambda item: item.created_at, reverse=True)[:40]],
        "pendingActions": sensitive_actions[:80],
        "actionQueuePath": str(action_queue_path) if action_queue_path and action_queue_path.exists() else "",
        "summary": {
            "step_count": len(STORE_OPERATION_STEPS),
            "store_profile_count": len(store_profiles),
            "runbook_count": len(ops_records),
            "task_count": len(task_records),
            "pending_external_count": len(sensitive_actions),
            "safe_auto_count": sum(len(step.get("auto_tasks", [])) for step in STORE_OPERATION_STEPS),
        },
    }


def ensure_store_profile(root: Path, *, store_id: str, platform: str, country: str, store_mode: str, now: str) -> None:
    if not store_id:
        return
    normalized = store_id.strip().lower()
    for record in read_records(root, "store_profile"):
        if str(record.fields.get("store_id") or "").strip().lower() == normalized:
            return
    lifecycle = "new" if store_mode in {"experimental", "new", "test", "sandbox", "experimental_new_store"} else "old"
    profile = IntakeRecord(
        record_type="store_profile",
        fields={
            "store_id": store_id,
            "marketplace": platform,
            "country_code": country,
            "store_lifecycle": lifecycle,
            "store_protection_mode": store_mode,
            "credential_storage_policy": "No plaintext password. Use user-managed browser profile or credential vault reference only.",
            "browser_profile_policy": "Use already logged-in Chrome or BitBrowser profile. Do not open unlogged duplicate profile for store work.",
            "created_by": "store_operations_autopilot",
            "created_at_utc": now,
        },
        raw_text=f"Store profile placeholder for {store_id}; no password stored.",
        source="store_operations_autopilot.profile",
        score={"priority": 88, "store_mode": store_mode},
        director_notes=[
            "No plaintext password is stored.",
            "Unknown/old stores stay protected. New test stores can queue execution after confirmation.",
        ],
    )
    append_record(root, profile)


def build_runbook_record(
    step: dict[str, Any],
    run_date: str,
    now: str,
    *,
    platform: str,
    country: str,
    store_id: str,
) -> IntakeRecord:
    fields = {
        "operation_runbook_id": f"ops-{run_date}-{step['step_id']}-{store_id}",
        "store_id": store_id,
        "marketplace": platform,
        "source_platform": platform,
        "country_code": country,
        "operation_type": step["step_id"],
        "operation_name": step["name"],
        "operator_agent": step["agent"],
        "automation_level": step["auto_level"],
        "operation_path": " > ".join([platform, store_id, step["name"]]),
        "auto_tasks": step.get("auto_tasks", []),
        "pending_actions": step.get("pending_actions", []),
        "never_auto": step.get("never_auto", []),
        "status": "runbook_ready",
        "run_date": run_date,
        "created_at_utc": now,
        "guardrail": "External store actions enter approval center; login/security/payment/customer-impact actions are never bypassed.",
    }
    return IntakeRecord(
        record_type="store_operation_event",
        fields=fields,
        raw_text=json.dumps({"step": step, "store_id": store_id, "platform": platform, "country": country}, ensure_ascii=False),
        source="store_operations_autopilot.runbook",
        score={"priority": 86, "automation_level": step["auto_level"]},
        director_notes=[
            step["goal"],
            "This runbook gives the AI employee hands and feet while keeping real store actions auditable.",
        ],
    )


def build_task_record(
    step: dict[str, Any],
    run_date: str,
    now: str,
    *,
    platform: str,
    country: str,
    store_id: str,
) -> IntakeRecord:
    has_external = bool(step.get("pending_actions"))
    fields = {
        "task_queue_id": f"tsk-storeops-{run_date}-{step['step_id']}-{store_id}",
        "task_type": f"store_ops_{step['step_id']}",
        "target_agent_id": step["agent"],
        "platform": platform,
        "store_id": store_id,
        "country_code": country,
        "status": "waiting_approval" if has_external else "queued",
        "priority": 90 if has_external else 74,
        "instruction": step["goal"],
        "auto_tasks": step.get("auto_tasks", []),
        "pending_actions": step.get("pending_actions", []),
        "never_auto": step.get("never_auto", []),
        "run_date": run_date,
        "created_at_utc": now,
    }
    return IntakeRecord(
        record_type="task_queue",
        fields=fields,
        raw_text=json.dumps(fields, ensure_ascii=False),
        source="store_operations_autopilot.task_queue",
        score={"priority": fields["priority"], "requires_confirmation": has_external},
        director_notes=[
            "AI may finish internal reading, analysis, drafts, reports and checks.",
            "External store actions remain queued until the boss confirms the action and the store protection mode allows it.",
        ],
    )


def build_store_action_queue(
    root: Path,
    runbook_records: list[IntakeRecord],
    run_date: str,
    *,
    platform: str,
    country: str,
    store_id: str,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for record in runbook_records:
        step_id = str(record.fields.get("operation_type") or "")
        step = next((item for item in STORE_OPERATION_STEPS if item["step_id"] == step_id), {})
        for task in step.get("auto_tasks", []):
            actions.append(
                {
                    "action_id": f"{task}-{record.record_id[:10]}",
                    "action_type": task,
                    "status": "auto_completed",
                    "requires_confirmation": False,
                    "title": f"{step.get('agent')} can run: {task}",
                    "reason": "Internal/read-only/draft operation. No external store side effect.",
                    "source_record_id": record.record_id,
                    "record_type": record.record_type,
                    "platform": platform,
                    "country": country,
                    "store": store_id,
                    "priority": 70,
                    "run_date": run_date,
                    "automation_level": step.get("auto_level"),
                    "executor_agent": step.get("agent"),
                }
            )
        for action_type in step.get("pending_actions", []):
            action = {
                "action_id": f"{action_type}-{record.record_id[:10]}",
                "action_type": action_type,
                "status": "pending_confirmation",
                "requires_confirmation": True,
                "title": f"{step.get('agent')} request: {step.get('name')} / {action_type}",
                "reason": "External store/platform/customer/money action. AI prepared the operation package but cannot execute it without confirmation.",
                "source_record_id": record.record_id,
                "record_type": record.record_type,
                "platform": platform,
                "country": country,
                "store": store_id,
                "store_id": store_id,
                "priority": 92,
                "run_date": run_date,
                "automation_level": "L3_after_confirmation",
                "executor_agent": step.get("agent"),
                "rollback_plan": rollback_plan_for(action_type),
                "precheck_required": precheck_for(action_type),
                "never_auto": step.get("never_auto", []),
            }
            actions.append(apply_store_protection(root, action, record))
    return dedupe_actions(actions)


def merge_action_queue(root: Path, run_date: str, new_actions: list[dict[str, Any]]) -> tuple[Path, list[dict[str, Any]]]:
    path = root / "outputs" / f"action_queue_{run_date}.json"
    existing = load_action_queue_file(path)
    merged = dedupe_actions([*existing, *new_actions])
    write_action_queue_file(path, merged)
    return path, merged


def dedupe_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for action in actions:
        action_id = str(action.get("action_id") or "")
        if not action_id or action_id in seen:
            continue
        seen.add(action_id)
        result.append(action)
    return result


def rollback_plan_for(action_type: str) -> str:
    plans = {
        "publish_listing": "Keep draft/version snapshot; if approved listing performs badly or hits risk, pause listing and restore previous draft.",
        "update_listing": "Save before/after title, images, bullets and price; restore previous version if conversion, refund or policy risk worsens.",
        "update_price": "Save previous price and margin; restore previous price if conversion/ROAS drops or platform price rule warns.",
        "set_discount": "Save discount window and margin; stop promotion if breakeven ROI, stock or refund thresholds fail.",
        "join_campaign": "Record campaign terms, stock and margin; withdraw only if platform allows and risk threshold is hit.",
        "launch_ad": "Start with budget cap and stop-loss; pause if CPA/ROAS thresholds fail.",
        "update_ad_budget": "Use small step scaling; revert budget if ROAS declines or spend accelerates without orders.",
        "pause_ad": "Record reason and baseline; restart only after review if organic or GMV drops unexpectedly.",
        "ship_order": "Verify order, SKU, address, carrier and inventory before shipping; hold exceptions.",
        "refund_customer": "Verify order, policy, evidence and refund amount; record reason for learning.",
        "send_message": "Use reviewed reply draft; avoid promises, legal claims or compensation without policy.",
        "upload_asset": "Keep original file and reviewed version; remove if policy/music/IP issue appears.",
        "publish_video_via_aip": "Save title, tags, music, account and product card; remove or private if policy/IP/music issue appears.",
        "authorize_app": "Only authorize known apps/scopes; revoke if scope mismatch or security risk appears.",
    }
    return plans.get(action_type, "Record before/after state, owner confirmation, metrics and rollback note before execution.")


def precheck_for(action_type: str) -> list[str]:
    common = ["correct store/country/platform", "human approval note", "evidence record", "rollback note"]
    checks = {
        "login": ["use existing logged-in browser profile", "do not store plaintext password", "stop at captcha/security check"],
        "captcha_or_slider": ["human completes verification", "AI records manual gate only"],
        "publish_listing": ["IP/compliance pass", "images reviewed", "stock and margin checked", "platform fields complete"],
        "update_listing": ["before snapshot saved", "keyword/compliance check", "risk terms checked"],
        "set_discount": ["breakeven ROI checked", "margin checked", "inventory checked", "campaign dates checked"],
        "join_campaign": ["terms checked", "stock checked", "margin checked", "fulfillment SLA checked"],
        "launch_ad": ["budget cap", "CPA stop-loss", "audience/material plan", "old-store protection check"],
        "update_ad_budget": ["current ROAS/CPA", "budget cap", "scale step limit"],
        "ship_order": ["order and SKU match", "inventory available", "address/carrier validated"],
        "refund_customer": ["order evidence", "refund policy", "customer impact reviewed"],
        "publish_video_via_aip": ["AIP bound", "music safe", "product card correct", "caption/tags checked"],
        "authorize_app": ["app identity checked", "scope checked", "owner confirmation"],
    }
    return [*common, *checks.get(action_type, [])]


def build_store_ops_report(
    run_date: str,
    platform: str,
    country: str,
    store_id: str,
    runbook_records: list[IntakeRecord],
    task_records: list[IntakeRecord],
    actions: list[dict[str, Any]],
) -> str:
    pending = [item for item in actions if item.get("requires_confirmation")]
    auto_done = [item for item in actions if not item.get("requires_confirmation")]
    lines = [
        "# Store Operations Autopilot",
        "",
        f"Date: {run_date}",
        f"Store: {store_id}",
        f"Platform: {platform}",
        f"Country: {country}",
        "",
        "## Boss Summary",
        "",
        "- This module gives the AI Ecommerce Director practical hands and feet for store operations.",
        "- It can automatically read, classify, analyze, draft, report, check risk, and create operation packages.",
        "- It does not bypass login/captcha/security checks and does not execute customer, money, listing, ads, shipping or authorization actions without approval.",
        "- Old, stable, high-GMV or active-ad stores remain protected; new test stores can move to confirmed execution after approval.",
        "",
        "## Full Chain Coverage",
        "",
    ]
    for step in STORE_OPERATION_STEPS:
        lines.append(f"- {step['name']} ({step['agent']}): {step['goal']}")
    lines.extend(
        [
            "",
            "## Current Run",
            "",
            f"- Runbook records: {len(runbook_records)}",
            f"- Task queue records: {len(task_records)}",
            f"- Auto internal actions: {len(auto_done)}",
            f"- Pending external actions: {len(pending)}",
            "",
            "## Pending External Actions",
            "",
        ]
    )
    if pending:
        for action in pending[:40]:
            lines.append(
                f"- {action.get('action_type')}: {action.get('title')} | status={action.get('status')} | store_protection={action.get('store_protection_mode', '-')}"
            )
    else:
        lines.append("- No pending external actions.")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- Passwords are not stored in plaintext.",
            "- Existing logged-in Chrome/BitBrowser profiles should be used for store work.",
            "- Verification/captcha/slider stops the automation and becomes a manual gate.",
            "- Every external action needs before/after evidence and a rollback note.",
        ]
    )
    return "\n".join(lines)


def write_store_ops_report(root: Path, run_date: str, report: str) -> Path:
    path = root / "outputs" / f"{STORE_OPS_REPORT_PREFIX}_{run_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    return path
