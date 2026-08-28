from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .api_connectors import run_api_sources
from .autonomous_loop import run_autonomous_loop
from .browser_operator import run_browser_operator
from .daily_runner import run_daily_director
from .idle_learning import run_idle_learning
from .learning_sources import run_learning_sources
from .patent_search import run_patent_search_agent
from .platform_autopilot import run_platform_autopilot
from .selection_intelligence import run_selection_intelligence
from .selection_meeting import run_selection_meeting
from .product_lifecycle import run_product_lifecycle_analysis
from .launch_control import run_launch_control_analysis
from .budget_planning import run_budget_planning_analysis
from .operation_closure import run_operation_closure_analysis
from .storage import read_records
from .store_protection import apply_store_protection
from .types import IntakeRecord
from .video_policy import allows_tiktok_video_strategy
from .visual_creative import run_visual_creative_director


AUTONOMOUS_CONFIG = Path("config") / "autonomous_mode.json"
AUTONOMOUS_REPORT_PREFIX = "autonomous_run"
ACTION_QUEUE_PREFIX = "action_queue"

SENSITIVE_ACTIONS = [
    "login",
    "captcha",
    "verification",
    "publish_listing",
    "update_listing",
    "delist_product",
    "update_price",
    "update_inventory",
    "set_discount",
    "join_campaign",
    "contact_creator",
    "send_message",
    "upload_asset",
    "publish_video_via_aip",
    "bind_tk_aip_publisher_account",
    "buy_ip",
    "change_browser_profile",
    "change_store_setting",
    "payment",
    "ship_order",
    "appeal",
    "authorize_app",
]


@dataclass(slots=True)
class AutonomousRunResult:
    run_date: str
    statuses: list[dict[str, Any]]
    action_queue: list[dict[str, Any]]
    report: str
    report_path: Path
    action_queue_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "statuses": self.statuses,
            "action_queue": self.action_queue,
            "report": self.report,
            "report_path": str(self.report_path),
            "action_queue_path": str(self.action_queue_path),
        }


def run_autonomous_director(root: Path, run_date: str | None = None) -> AutonomousRunResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    config = load_autonomous_config(root)
    statuses: list[dict[str, Any]] = []

    if not config.get("enabled", True):
        statuses.append({"step": "autonomous_mode", "status": "disabled"})
    else:
        steps = config.get("steps", {}) if isinstance(config.get("steps"), dict) else {}
        if steps.get("api_sources", True):
            api_result = run_api_sources(root, report_date)
            statuses.append(
                {
                    "step": "api_sources",
                    "status": "completed",
                    "sources": api_result.statuses,
                    "saved_records": len(api_result.records),
                    "report_path": str(api_result.report_path),
                }
            )
        if steps.get("platform_autopilot", True):
            platform_result = run_platform_autopilot(
                root,
                report_date,
                open_browser=bool(config.get("open_browser", False)),
                collect_public=bool(config.get("collect_public_pages", True)),
            )
            statuses.append(
                {
                    "step": "platform_autopilot",
                    "status": "completed",
                    "sources": platform_result.statuses,
                    "saved_records": len(platform_result.records),
                    "report_path": str(platform_result.report_path),
                }
            )
        if steps.get("browser_operator", True):
            browser_result = run_browser_operator(root, report_date)
            statuses.append(
                {
                    "step": "browser_operator",
                    "status": "completed",
                    "sources": browser_result.statuses,
                    "saved_records": sum(int(item.get("captured_pages", 0) or 0) for item in browser_result.statuses),
                    "report_path": str(browser_result.report_path),
                }
            )
        if steps.get("learning_sources", True):
            learning_result = run_learning_sources(root, report_date)
            statuses.append(
                {
                    "step": "learning_sources",
                    "status": "completed",
                    "sources": learning_result.statuses,
                    "saved_records": len(learning_result.records),
                    "report_path": str(learning_result.report_path),
                }
            )
        if steps.get("patent_search", True):
            patent_result = run_patent_search_agent(root, report_date)
            statuses.append(
                {
                    "step": "patent_search",
                    "status": "completed",
                    "sources": patent_result.statuses,
                    "saved_records": len(patent_result.records),
                    "report_path": str(patent_result.report_path),
                }
            )
        if steps.get("selection_intelligence", True):
            selection_result = run_selection_intelligence(root, report_date)
            statuses.append(
                {
                    "step": "selection_intelligence",
                    "status": "completed",
                    "saved_records": 0,
                    "categories": len(selection_result.categories),
                    "movements": len(selection_result.movements),
                    "new_release_candidates": len(selection_result.new_release_candidates),
                    "report_path": str(selection_result.report_path),
                }
            )
        if steps.get("selection_meeting", True):
            meeting_result = run_selection_meeting(root, report_date)
            statuses.append(
                {
                    "step": "selection_meeting",
                    "status": "completed",
                    "saved_records": 0,
                    "participants": len(meeting_result.participants),
                    "llm_used": meeting_result.llm_used,
                    "report_path": str(meeting_result.report_path),
                }
            )
        if steps.get("product_lifecycle", True):
            lifecycle_result = run_product_lifecycle_analysis(root, report_date)
            statuses.append(
                {
                    "step": "product_lifecycle",
                    "status": "completed",
                    "saved_records": 0,
                    "plans": len(lifecycle_result.plans),
                    "report_path": str(lifecycle_result.report_path),
                }
            )
        if steps.get("launch_control", True):
            launch_result = run_launch_control_analysis(root, report_date)
            statuses.append(
                {
                    "step": "launch_control",
                    "status": "completed",
                    "saved_records": 0,
                    "plans": len(launch_result.plans),
                    "report_path": str(launch_result.report_path),
                }
            )
        if steps.get("budget_planning", True):
            budget_result = run_budget_planning_analysis(root, report_date)
            statuses.append(
                {
                    "step": "budget_planning",
                    "status": "completed",
                    "saved_records": 0,
                    "plans": len(budget_result.plans),
                    "total_budget": budget_result.summary.get("total_budget", 0),
                    "report_path": str(budget_result.report_path),
                }
            )
        if steps.get("operation_closure", True):
            closure_result = run_operation_closure_analysis(root, report_date)
            statuses.append(
                {
                    "step": "operation_closure",
                    "status": "completed",
                    "saved_records": 0,
                    "ready": closure_result.summary.get("ready", 0),
                    "partial": closure_result.summary.get("partial", 0),
                    "missing": closure_result.summary.get("missing", 0),
                    "report_path": str(closure_result.report_path),
                }
            )
        if steps.get("daily_director", True):
            daily_result = run_daily_director(
                root,
                report_date,
                collect=bool(config.get("daily_collect", True)),
                use_llm=bool(config.get("use_llm", True)),
                collect_api_sources=bool(steps.get("api_sources", False)),
            )
            statuses.append(
                {
                    "step": "daily_director",
                    "status": "completed",
                    "saved_records": len(daily_result.collected_records),
                    "llm_used": daily_result.llm_used,
                    "strategy_report_path": str(daily_result.strategy_report_path),
                    "daily_report_path": str(daily_result.daily_report_path),
                }
            )
        if steps.get("visual_creative", True):
            visual_result = run_visual_creative_director(root, report_date)
            statuses.append(
                {
                    "step": "visual_creative",
                    "status": "completed",
                    "saved_records": 0,
                    "product_briefs": len(visual_result.product_briefs),
                    "report_path": str(visual_result.report_path),
                }
            )
        if steps.get("idle_learning", True):
            idle_result = run_idle_learning(root, report_date)
            statuses.append(
                {
                    "step": "idle_learning",
                    "status": "completed",
                    "tracks": idle_result.statuses,
                    "saved_memories": len(idle_result.memories),
                    "report_path": str(idle_result.report_path),
                }
            )
        if steps.get("autonomous_loop", True):
            loop_result = run_autonomous_loop(root, report_date)
            statuses.append(
                {
                    "step": "autonomous_loop",
                    "status": "completed",
                    "scheduler_tasks": len(loop_result.scheduler_tasks),
                    "signals": len(loop_result.signals),
                    "hypotheses": len(loop_result.hypotheses),
                    "experiments": len(loop_result.experiments),
                    "execution_tasks": len(loop_result.execution_tasks),
                    "report_path": str(loop_result.report_path),
                    "state_path": str(loop_result.state_path),
                }
            )

    action_queue = build_action_queue(root, config, report_date)
    action_queue_path = write_action_queue(root, report_date, action_queue)
    report = build_autonomous_report_v2(report_date, statuses, action_queue, config)
    report_path = write_autonomous_report(root, report_date, report)
    return AutonomousRunResult(report_date, statuses, action_queue, report, report_path, action_queue_path)


def load_autonomous_config(root: Path) -> dict[str, Any]:
    path = root / AUTONOMOUS_CONFIG
    if not path.exists():
        return default_autonomous_config()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else default_autonomous_config()


def save_autonomous_config(root: Path, config: dict[str, Any]) -> Path:
    path = root / AUTONOMOUS_CONFIG
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def default_autonomous_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "safe_mode": True,
        "open_browser": False,
        "collect_public_pages": True,
        "daily_collect": True,
        "use_llm": True,
        "steps": {
            "api_sources": False,
            "platform_autopilot": True,
            "browser_operator": True,
            "learning_sources": True,
            "patent_search": True,
            "selection_intelligence": True,
            "selection_meeting": True,
            "product_lifecycle": True,
            "launch_control": True,
            "budget_planning": True,
            "operation_closure": True,
            "daily_director": True,
            "visual_creative": True,
            "idle_learning": True,
            "autonomous_loop": True,
        },
    }


def build_action_queue(root: Path, config: dict[str, Any], run_date: str) -> list[dict[str, Any]]:
    records = read_records(root)
    queue: list[dict[str, Any]] = []
    priority_records = sorted(records, key=lambda item: float(item.score.get("priority", 0) or 0), reverse=True)[:40]
    for record in priority_records:
        queue.extend(apply_store_protection(root, action, record) for action in actions_for_record(record, run_date))
    queue.append(
        {
            "action_id": f"daily-report-review-{run_date}",
            "action_type": "review_report",
            "status": "auto_completed",
            "requires_confirmation": False,
            "title": "Review generated daily report",
            "reason": "Autonomous mode generated reports and queued sensitive execution steps separately.",
            "source_record_id": "",
            "run_date": run_date,
        }
    )
    return dedupe_actions(queue)


def actions_for_record(record: IntakeRecord, run_date: str) -> list[dict[str, Any]]:
    fields = record.fields
    label = record_label(record)
    actions: list[dict[str, Any]] = []
    if record.record_type in {"viral_content_signal", "video_breakdown", "hot_link", "platform_ranking_signal"}:
        video_allowed = allows_tiktok_video_strategy(record)
        if video_allowed:
            actions.append(auto_action(record, run_date, "generate_video_breakdown", f"Generate TikTok content breakdown for {label}"))
            actions.append(auto_action(record, run_date, "generate_video_script", f"Generate TikTok store-owned and influencer scripts for {label}"))
        actions.append(auto_action(record, run_date, "generate_product_image_brief", f"Generate main/detail/model image brief for {label}"))
        if video_allowed:
            actions.append(auto_action(record, run_date, "generate_ai_image_video_prompts", f"Generate AI image and TikTok short-video prompts for {label}"))
        else:
            actions.append(auto_action(record, run_date, "generate_ai_image_prompts", f"Generate AI image prompts for {label}"))
        actions.append(pending_action(record, run_date, "publish_listing", f"Publish or update listing for {label}"))
        upload_title = f"Upload generated images/TikTok videos for {label}" if video_allowed else f"Upload generated images for {label}"
        actions.append(pending_action(record, run_date, "upload_asset", upload_title))
        if video_allowed:
            actions.append(pending_action(record, run_date, "contact_creator", f"Contact TikTok creators for {label}"))
    if record.record_type == "video_script":
        if not allows_tiktok_video_strategy(record):
            return actions
        channel = record.score.get("script_channel", fields.get("script_type", "video_script"))
        actions.append(auto_action(record, run_date, "prepare_shooting_brief", f"Prepare shooting brief for {label} ({channel})"))
        actions.append(auto_action(record, run_date, "prepare_tk_publish_package", f"Prepare TikTok publish package for {label} ({channel})"))
        actions.append(auto_action(record, run_date, "check_music_copyright_and_mix", f"Check music copyright and audio mix for {label}"))
        actions.append(pending_action(record, run_date, "upload_asset", f"Upload or assign produced video asset for {label}"))
        actions.append(pending_action(record, run_date, "publish_video_via_aip", f"Publish video through confirmed AIP account for {label}"))
    if record.record_type == "social_account_profile":
        actions.append(auto_action(record, run_date, "validate_video_account_matrix", f"Validate store video account matrix for {label}"))
        actions.append(auto_action(record, run_date, "check_music_policy_for_account", f"Attach music copyright rules to video account {label}"))
        if record.score.get("requires_aip_binding"):
            actions.append(pending_action(record, run_date, "bind_tk_aip_publisher_account", f"Bind/verify AIP publishing permission for {label}"))
    if record.record_type == "video_publish_plan":
        if not allows_tiktok_video_strategy(record):
            return actions
        actions.append(auto_action(record, run_date, "check_video_publish_package", f"Check video publish package for {label}"))
        actions.append(auto_action(record, run_date, "check_music_copyright_and_mix", f"Check music copyright and audio mix for {label}"))
        actions.append(pending_action(record, run_date, "publish_video_via_aip", f"Publish prepared video through AIP after confirmation: {label}"))
    if record.record_type == "creative_inspiration":
        actions.append(auto_action(record, run_date, "turn_memory_into_original_material_brief", f"Turn creative memory into original material brief for {label}"))
        actions.append(auto_action(record, run_date, "check_creative_ip_reuse_boundary", f"Check IP/reuse boundary for original creative {label}"))
        actions.append(auto_action(record, run_date, "prepare_ai_image_video_prompt", f"Prepare AI image/video prompt for original creative {label}"))
        actions.append(pending_action(record, run_date, "upload_asset", f"Upload produced creative asset after review for {label}"))
    if record.record_type == "ai_video_prompt_training":
        actions.append(auto_action(record, run_date, "index_video_prompt_training_pack", f"Index reusable AI video prompt training pack for {label}"))
        actions.append(auto_action(record, run_date, "check_video_prompt_guardrails", f"Check AI video prompt guardrails for {label}"))
        actions.append(auto_action(record, run_date, "prepare_seedance_prompt_variants", f"Prepare Seedance 2.0 prompt variants for {label}"))
    if record.record_type == "industry_research_asset":
        asset_type = record.score.get("research_asset_type", fields.get("research_asset_type", "research"))
        actions.append(auto_action(record, run_date, "update_research_library", f"Update industry research library for {label} ({asset_type})"))
        actions.append(auto_action(record, run_date, "generate_validation_tasks", f"Generate validation tasks from research asset {label}"))
        actions.append(auto_action(record, run_date, "map_to_director_modules", f"Map research asset {label} to product/content/influencer/listing modules"))
    if record.record_type == "collection_job":
        actions.append(auto_action(record, run_date, "collect_platform_data_read_only", f"Collect read-only platform data for {label}"))
        actions.append(auto_action(record, run_date, "route_collected_data_to_ai", f"Route collected data to the best AI analysis module for {label}"))
        actions.append(auto_action(record, run_date, "save_collection_results", f"Save collection outputs into the matching intelligence libraries for {label}"))
    if record.record_type == "compliance_term":
        actions.append(auto_action(record, run_date, "scan_compliance_terms", f"Scan drafts and scripts for compliance term {label}"))
        actions.append(auto_action(record, run_date, "suggest_safe_replacements", f"Suggest safe replacements for {label}"))
        actions.append(pending_action(record, run_date, "publish_listing", f"Publish only after compliance review for {label}"))
    if record.record_type == "ip_image_risk":
        actions.append(auto_action(record, run_date, "scan_all_platform_ip_risk", f"Scan all-platform listings, images, videos, ads, scripts, and designs for IP risk {label}"))
        actions.append(auto_action(record, run_date, "scan_pod_image_ip_risk", f"Scan POD listings and designs for image/IP risk {label}"))
        actions.append(auto_action(record, run_date, "draft_safe_design_rule", f"Draft safe design rules for image/IP risk {label}"))
        if record.score.get("authorized_for_listing"):
            actions.append(auto_action(record, run_date, "archive_ip_authorization", f"Archive authorization proof and allowed listing scope for {label}"))
        else:
            actions.append(pending_action(record, run_date, "review_ip_authorization", f"Review brand/IP authorization before listing or keeping live: {label}"))
            if record.score.get("requires_delist_review"):
                actions.append(pending_action(record, run_date, "delist_product", f"Delist only if authorization is missing or TRO/platform notice requires removal: {label}"))
    if record.record_type == "review_insight":
        actions.append(auto_action(record, run_date, "extract_review_pain_points", f"Extract review pain points for {label}"))
        actions.append(auto_action(record, run_date, "draft_product_listing_content_fixes", f"Draft product/listing/content fixes for {label}"))
        actions.append(pending_action(record, run_date, "update_listing", f"Apply listing or product changes for {label}"))
    if record.record_type == "feedback_ticket":
        actions.append(auto_action(record, run_date, "triage_feedback_ticket", f"Triage feedback ticket for {label}"))
        actions.append(auto_action(record, run_date, "draft_fix_or_feature_spec", f"Draft fix or feature spec for {label}"))
        actions.append(auto_action(record, run_date, "route_feedback_to_module", f"Route feedback to module owner for {label}"))
    if record.record_type == "influencer_cooperation":
        actions.append(auto_action(record, run_date, "score_creator", f"Update creator score for {label}"))
        actions.append(pending_action(record, run_date, "contact_creator", f"Follow up with creator {label}"))
    if record.record_type == "supply_chain":
        actions.append(auto_action(record, run_date, "check_supply_fit", f"Check launch fit for supply item {label}"))
        actions.append(pending_action(record, run_date, "update_inventory", f"Update inventory or procurement plan for {label}"))
    if record.record_type == "store_health_event":
        actions.append(auto_action(record, run_date, "risk_review", f"Review store health risk for {label}"))
        actions.append(pending_action(record, run_date, "appeal", f"Submit appeal or store health action for {label}"))
    if record.record_type == "store_operation_event":
        actions.append(auto_action(record, run_date, "document_operation_path", f"Document backend operation path for {label}"))
        actions.append(pending_action(record, run_date, "set_discount", f"Execute promotion/discount operation for {label}"))
    if record.record_type == "pod_admin_snapshot":
        actions.append(auto_action(record, run_date, "pod_snapshot_review", f"Review POD fulfillment snapshot for {label}"))
        actions.append(pending_action(record, run_date, "ship_order", f"Execute POD shipment/factory operation for {label}"))
    if record.record_type == "store_metric_snapshot":
        actions.append(auto_action(record, run_date, "review_store_sales_metrics", f"Review sales, orders, refunds, returns, and ROAS for {label}"))
        actions.append(auto_action(record, run_date, "draft_ads_returns_finance_diagnosis", f"Draft ads/returns/finance diagnosis for {label}"))
    if record.record_type == "experiment_run":
        actions.append(auto_action(record, run_date, "check_experiment_guardrails", f"Check experiment guardrails for {label}"))
        actions.append(auto_action(record, run_date, "prepare_metric_monitor", f"Prepare metric monitor for {label}"))
        actions.append(pending_action(record, run_date, "start_experiment", f"Start controlled experiment only after confirmation: {label}"))
    if record.record_type == "task_queue":
        status = str(fields.get("status") or "")
        task_type = str(fields.get("task_type") or label)
        if status == "waiting_approval":
            actions.append(pending_action(record, run_date, "approve_task_queue_item", f"Approve queued autonomous task: {task_type}"))
        else:
            actions.append(auto_action(record, run_date, "review_task_queue_item", f"Review queued autonomous task: {task_type}"))
    return actions


def auto_action(record: IntakeRecord, run_date: str, action_type: str, title: str) -> dict[str, Any]:
    return {
        "action_id": f"{action_type}-{record.record_id[:10]}",
        "action_type": action_type,
        "status": "auto_completed",
        "requires_confirmation": False,
        "title": title,
        "reason": "Allowed autonomous action: analysis, scoring, report, draft, or read-only review.",
        "source_record_id": record.record_id,
        "record_type": record.record_type,
        "priority": record.score.get("priority", 0),
        "run_date": run_date,
    }


def pending_action(record: IntakeRecord, run_date: str, action_type: str, title: str) -> dict[str, Any]:
    return {
        "action_id": f"{action_type}-{record.record_id[:10]}",
        "action_type": action_type,
        "status": "pending_confirmation",
        "requires_confirmation": True,
        "title": title,
        "reason": "Sensitive store/platform action. Autonomous mode prepared the task but will not execute it without user confirmation.",
        "source_record_id": record.record_id,
        "record_type": record.record_type,
        "priority": record.score.get("priority", 0),
        "run_date": run_date,
    }


def dedupe_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for action in actions:
        action_id = str(action.get("action_id") or "")
        if action_id in seen:
            continue
        seen.add(action_id)
        result.append(action)
    return result


def record_label(record: IntakeRecord) -> str:
    fields = record.fields
    for key in ["feedback_text", "module_area", "hypothesis", "task_type", "creative_angle", "publish_title", "target_account_handle", "account_handle", "aip_provider", "term", "pain_point", "review_source", "collection_target", "platform_list", "product_name", "product_theme", "content_theme", "opportunity", "knowledge_node", "brand_name", "content_account", "competitor_site_url", "video_url", "creator_handle", "store_id", "platform_name", "url"]:
        value = fields.get(key)
        if value:
            return str(value)[:120]
    return record.record_id[:8]


def build_autonomous_report(run_date: str, statuses: list[dict[str, Any]], action_queue: list[dict[str, Any]], config: dict[str, Any]) -> str:
    return build_autonomous_report_v2(run_date, statuses, action_queue, config)


def build_autonomous_report_v2(run_date: str, statuses: list[dict[str, Any]], action_queue: list[dict[str, Any]], config: dict[str, Any]) -> str:
    auto_done = [item for item in action_queue if not item.get("requires_confirmation")]
    pending = [item for item in action_queue if item.get("requires_confirmation")]
    steps = config.get("steps") if isinstance(config.get("steps"), dict) else {}
    lines = [
        "# AI Ecommerce Director No-API Auto Mode Report",
        "",
        f"Date: {run_date}",
        "",
        "## Safety Boundary",
        "",
        "- Automatically allowed: public page reading, keyword monitoring, competitor-link monitoring, manual-capture analysis, POD read-only snapshots, scoring, reports, listing/script/creator drafts, and action queue generation.",
        "- Full safe autopilot: pasted/downloaded store data is automatically classified into orders, returns, ads, finance, sales dashboard, diagnosis, and strategy memory.",
        "- TK priority: TikTok Shop buyer-side search, product-card links, creator/video intelligence, FastMoss, and Kalodata are protected core channels and must not be replaced by Amazon.",
        "- Video autopilot: TikTok-side signals generate scripts, publish packages, music copyright checks, audio-mix checks, and AIP task queues automatically; real posting still needs confirmation.",
        "- Not automatically allowed: login bypass, captcha/slider bypass, publishing, delisting, price/inventory edits, discounts, campaign signups, creator outreach, payments, shipping, app authorization, or appeals.",
        "- Store protection: unknown stores are treated as existing/protected stores; old, stable, high-GMV, or active-ad stores are locked to analysis/draft mode unless you explicitly override protection.",
        "- New/test stores may queue controlled experiments after confirmation, but still need stop-loss rules for ads, discounts, live links, coupons, listing edits, and uploads.",
        "- Pages that require login or human verification are marked as manual gates. Use the browser extension to capture them after you pass verification yourself.",
        f"- safe_mode: {bool(config.get('safe_mode', True))}",
        f"- api_sources_enabled: {bool(steps.get('api_sources', False))}",
        f"- patent_search_enabled: {bool(steps.get('patent_search', True))}",
        f"- selection_intelligence_enabled: {bool(steps.get('selection_intelligence', True))}",
        f"- selection_meeting_enabled: {bool(steps.get('selection_meeting', True))}",
        f"- product_lifecycle_enabled: {bool(steps.get('product_lifecycle', True))}",
        f"- launch_control_enabled: {bool(steps.get('launch_control', True))}",
        f"- budget_planning_enabled: {bool(steps.get('budget_planning', True))}",
        f"- operation_closure_enabled: {bool(steps.get('operation_closure', True))}",
        "",
        "## Step Status",
        "",
    ]
    if not statuses:
        lines.append("- No autonomous steps ran.")
    for status in statuses:
        lines.append(f"- {status.get('step')}: {status.get('status')}, saved {status.get('saved_records', 0)} records")
    lines.extend(["", "## Auto Completed", ""])
    if not auto_done:
        lines.append("- No completed analysis tasks yet.")
    for action in auto_done[:30]:
        lines.append(f"- {action.get('title')} | {action.get('action_type')}")
    lines.extend(["", "## Waiting For Your Confirmation", ""])
    if not pending:
        lines.append("- No sensitive actions are waiting for confirmation.")
    for action in pending[:30]:
        lines.append(f"- {action.get('title')} | {action.get('action_type')} | priority {action.get('priority')}")
    return "\n".join(lines).rstrip() + "\n"


def write_action_queue(root: Path, run_date: str, actions: list[dict[str, Any]]) -> Path:
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{ACTION_QUEUE_PREFIX}_{run_date}.json"
    path.write_text(json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_autonomous_report(root: Path, run_date: str, content: str) -> Path:
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{AUTONOMOUS_REPORT_PREFIX}_{run_date}.md"
    path.write_text(content, encoding="utf-8")
    return path


def latest_autonomous_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    paths = sorted(output_dir.glob(f"{AUTONOMOUS_REPORT_PREFIX}_*.md"), reverse=True)
    if not paths:
        return "No autonomous report yet.", None
    path = paths[0]
    return path.read_text(encoding="utf-8"), path
