from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .execution_loop import latest_action_queue_path, load_action_queue_file
from .llm import LLMClient
from .pod_admin import load_pod_admin_config
from .storage import read_records


REPORT_PREFIX = "operation_closure"

STEP_DISPLAY_NAMES = {
    "product_target": "设置重点商品",
    "market_category": "查看市场类目机会",
    "competitor_same_product": "监控同品竞品",
    "review_pain": "分析评论差评和痛点",
    "viral_content": "拆解 TK 爆款视频",
    "creative_production": "生成图片/视频素材方向",
    "listing_builder": "生成 Listing 和主图建议",
    "compliance_ip": "检查侵权/违禁/平台风险",
    "supply_chain": "核算成本库存和履约",
    "store_setup": "检查店铺账号和 IP 隔离",
    "store_data": "导入店铺销售/订单/广告数据",
    "budget_roi": "预算 ROI 和回本计划",
    "launch_plate": "起盘控盘和生命周期",
    "ads_live_campaign": "广告直播折扣活动",
    "influencer_crm": "达人库和合作 ROI",
    "video_publishing": "视频账号发布计划",
    "orders_returns_finance": "订单退货财务",
    "lifecycle_stock": "生命周期和补货",
    "strategy_memory": "策略复盘和记忆",
    "pod_board": "POD 独立通道",
    "approval_execution": "待确认动作和安全执行",
}


@dataclass(slots=True)
class OperationClosureResult:
    run_date: str
    steps: list[dict[str, Any]]
    summary: dict[str, Any]
    report: str
    report_path: Path
    json_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "steps": self.steps,
            "summary": self.summary,
            "report": self.report,
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
        }


def run_operation_closure_analysis(root: Path, run_date: str | None = None) -> OperationClosureResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    payload = build_operation_closure_payload(root, report_date)
    report = build_operation_closure_report(report_date, payload["steps"], payload["summary"])
    report_path = write_operation_closure_report(root, report_date, report)
    json_path = write_operation_closure_json(root, report_date, payload)
    return OperationClosureResult(report_date, payload["steps"], payload["summary"], report, report_path, json_path)


def build_operation_closure_payload(root: Path, run_date: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    records = read_records(root)
    record_counts = count_records(records)
    context = {
        "root": root,
        "record_counts": record_counts,
        "output_prefixes": output_prefixes(root),
        "configs": config_flags(root),
        "ai_status": LLMClient(root=root, task="strategy").status().to_dict(),
        "pending_actions": len([item for item in load_action_queue_file(latest_action_queue_path(root)) if item.get("requires_confirmation")]),
    }
    steps = [evaluate_step(step, context) for step in operation_steps()]
    summary = summarize_steps(steps, record_counts)
    return {"run_date": run_date or date.today().isoformat(), "summary": summary, "steps": steps}


def operation_steps() -> list[dict[str, Any]]:
    return [
        step(
            "product_target",
            "01 Product Target Setup",
            "Monitored product setup",
            ["product_targets_config"],
            ["platform_ranking_signal", "hot_link"],
            ["product name", "same-product reference image", "target countries", "target platforms", "keywords", "competitor links", "budget goal"],
            ["Create product target", "match same product", "separate broad category research from exact product monitoring"],
            ["product target record", "collection jobs", "same-product competitor list"],
            "L0-L2",
            "/chat?intent=product_data",
        ),
        step(
            "market_category",
            "02 Market Map",
            "Category and ranking intelligence",
            ["platform_ranking_signal"],
            ["selection_intelligence_report", "selection_meeting_report"],
            ["platform", "country", "category path L1-L4", "ranking type", "rank", "price", "sales/GMV", "new release flag"],
            ["score market size", "find fast growth", "separate big category from exact product"],
            ["category opportunity score", "new-release watch list", "rank movement alert"],
            "L0-L2",
            "/chat?intent=product_data",
        ),
        step(
            "competitor_same_product",
            "03 Same-Product Competitor Monitor",
            "Exact competitor matching",
            ["platform_ranking_signal", "hot_link"],
            ["product_targets_config"],
            ["product URL", "image/reference image", "brand", "seller/shop", "price", "variants", "country", "platform"],
            ["decide whether competitor is same product", "dedupe links", "track shop/network/authorized stores"],
            ["same-product competitor board", "brand/store map", "monitor add/remove queue"],
            "L0-L3",
            "/chat?intent=product_data&focus=competitor",
        ),
        step(
            "review_pain",
            "04 Review Pain Intelligence",
            "Competitor and own-store review mining",
            ["review_insight"],
            ["feedback_ticket", "store_metric_snapshot"],
            ["rating", "negative reason", "return reason", "defect area", "customer quote", "suggested fix", "affected SKU"],
            ["cluster complaints", "convert pain to product/listing/content fixes", "watch own complaints separately"],
            ["pain-point report", "listing fix draft", "factory/service improvement task"],
            "L0-L3",
            "/chat?intent=feedback",
        ),
        step(
            "viral_content",
            "05 Viral Content Intelligence",
            "Video, creator, hook, script, shot analysis",
            ["viral_content_signal", "video_breakdown"],
            ["hot_link", "tk_case_learning_report", "creator_spike_event"],
            ["video URL", "platform", "views growth", "0-3s hook", "scene", "shots", "subtitle", "voiceover", "CTA", "comments"],
            ["break down why it went viral", "extract hook/scene/script", "map to product audience"],
            ["store-owned script", "creator brief", "shot list", "replication strategy"],
            "L0-L2",
            "/chat?intent=tk_content",
        ),
        step(
            "creative_production",
            "06 Creative Production",
            "Images, AI video, mixed edit, music and material pipeline",
            ["video_script", "creative_inspiration"],
            ["visual_creative_report", "video_publish_plan"],
            ["script type", "shot list", "hook", "voiceover", "music policy", "audio mix", "Seedance prompt", "real-shot must-have"],
            ["generate original material ideas from memory", "avoid copying competitor video", "check music and audio mix"],
            ["shooting brief", "AI image prompt", "Seedance 2.0 video prompt", "mixed-edit order"],
            "L0-L3",
            "/chat?intent=tk_content",
        ),
        step(
            "listing_builder",
            "07 Listing Builder",
            "Title, bullets, tags, main image, detail image and price draft",
            ["platform_ranking_signal", "review_insight"],
            ["compliance_term", "ip_image_risk", "visual_creative_report"],
            ["platform", "keyword", "title pattern", "price range", "5 bullets", "tags", "image angle", "FAQ", "restricted terms"],
            ["build listing draft", "localize by country", "check forbidden words and IP risk"],
            ["listing draft", "image brief", "price/coupon draft", "FAQ"],
            "L0-L3",
            "/chat?intent=product_data",
        ),
        step(
            "compliance_ip",
            "08 Compliance/IP/Patent Risk",
            "Forbidden terms, trademark, copyright, TRO and platform rule control",
            ["compliance_term", "ip_image_risk"],
            ["tk_rule_update", "patent_search_report"],
            ["risk term", "brand/right owner", "image element", "confidence", "source", "allowed private/public/channel sync"],
            ["scan listing/script/image/video", "separate borderline from confirmed IP", "queue review before public sync"],
            ["risk label", "safe replacement", "private-only/public/reject recommendation"],
            "L0-L3",
            "/chat?intent=risk",
        ),
        step(
            "supply_chain",
            "09 Supply Chain and Unit Economics",
            "Cost, inventory, SKU, lead time, factory and fulfillment readiness",
            ["supply_chain"],
            ["pod_admin_snapshot", "store_metric_snapshot"],
            ["unit cost", "MOQ", "inventory", "color/size", "weight", "lead time", "factory", "shipping cost", "target margin"],
            ["check if product can be sold now", "estimate margin", "stop scaling when stock/lead time cannot carry it"],
            ["stock plan", "replenishment draft", "margin warning", "factory dispatch suggestion"],
            "L0-L3",
            "/chat?intent=product_data",
        ),
        step(
            "store_setup",
            "10 Store Account and IP Isolation",
            "Store profile, legal entity, browser profile and login path",
            ["store_profile"],
            ["store_health_event", "social_account_profile"],
            ["platform", "country", "store id", "legal entity", "email/phone owner", "browser profile", "IP node", "risk status"],
            ["separate new/test/protected stores", "avoid touching old active stores", "document login and verification gates"],
            ["store map", "protection level", "manual gate note", "safe operation scope"],
            "L0-L3",
            "/store-erp",
        ),
        step(
            "store_data",
            "11 Store Data Import and Realtime Board",
            "Sales, orders, ad, return, finance and country/platform/store dashboard",
            ["store_metric_snapshot"],
            ["financial_report", "sales_dashboard"],
            ["snapshot time", "platform local time", "country", "store", "product", "orders", "GMV", "ad spend", "returns", "refunds", "fees"],
            ["separate own-store data from competitor data", "forecast trends", "trigger budget and stock adjustment"],
            ["realtime board", "K-line trend", "return alert", "finance summary"],
            "L0-L2",
            "/realtime-big-screen",
        ),
        step(
            "budget_roi",
            "12 Budget, ROI and Payback",
            "Total product budget plan and adjustable allocation",
            ["budget_planning_report"],
            ["store_metric_snapshot", "platform_ranking_signal", "supply_chain"],
            ["total budget", "store count", "platforms", "country", "duration", "margin", "ROAS", "payback days"],
            ["forecast ROI", "split TK/Amazon/multi-platform budget", "hold/increase/cut with guardrails"],
            ["budget allocation", "payback forecast", "approval draft", "stop-loss line"],
            "L0-L3",
            "/store-erp",
        ),
        step(
            "launch_plate",
            "13 Launch and Plate Control",
            "Seed, test, scale, harvest, cooldown strategy",
            ["launch_control_report"],
            ["product_lifecycle_report", "video_script", "influencer_cooperation", "store_metric_snapshot"],
            ["stage", "TK horse-race signal", "Amazon buying signal", "inventory", "refund rate", "ROAS", "content decay"],
            ["decide seed/test/scale/harvest/pause", "control live links, discount and budget rhythm"],
            ["launch plan", "plate-control rules", "live-room rhythm", "stop-loss rules"],
            "L0-L3",
            "/chat?intent=product_data",
        ),
        step(
            "ads_live_campaign",
            "14 Ads, Live, Discount and Campaign Operations",
            "GMV Max, PPC, live room, coupons and event signup",
            ["store_operation_event", "store_metric_snapshot"],
            ["budget_planning_report", "launch_control_report"],
            ["campaign", "discount", "ad objective", "budget", "break-even ROI", "live link time", "result"],
            ["draft actions only", "measure result after action", "protect old stores and active ads"],
            ["ad/coupon/live draft", "ROI diagnosis", "execution result record"],
            "L0-L4 after approval",
            "/chat?intent=approval",
        ),
        step(
            "influencer_crm",
            "15 Influencer CRM and BD",
            "Creator discovery, samples, outreach, video result and ROI memory",
            ["influencer_cooperation"],
            ["creator_spike_event", "viral_content_signal"],
            ["creator handle", "followers", "avg views", "engagement", "quote", "sample cost", "posted", "orders", "ROI"],
            ["score A/B/C creators", "find viral creator changes", "decide sample/observe/blacklist"],
            ["creator rating", "follow-up queue", "sample plan", "ROI memory"],
            "L0-L3",
            "/chat?intent=tk_content",
        ),
        step(
            "video_publishing",
            "16 Video Publishing Workflow",
            "Official account, channel account, AIP publisher, music and title/tag package",
            ["social_account_profile", "video_publish_plan"],
            ["video_script", "creative_inspiration"],
            ["store", "official account", "4 channel accounts", "AIP provider", "title", "tags", "music copyright", "audio mix", "publish time"],
            ["prepare publish package", "check music volume/copyright", "queue real posting for approval"],
            ["publish package", "AIP binding task", "music check", "posting approval"],
            "L0-L4 after approval",
            "/chat?intent=tk_content",
        ),
        step(
            "orders_returns_finance",
            "17 Orders, Returns and Finance",
            "Order, return, settlement and platform fee loop",
            ["store_metric_snapshot"],
            ["pod_admin_snapshot", "execution_result"],
            ["order count", "return/refund count", "settlement", "fees", "shipping", "tax", "reserve", "profit"],
            ["find loss products", "separate ad loss from return loss", "prepare finance report"],
            ["profit diagnosis", "refund alert", "settlement summary", "cash cycle note"],
            "L0-L3",
            "/realtime-big-screen",
        ),
        step(
            "lifecycle_stock",
            "18 Lifecycle and Replenishment",
            "ABCD lifecycle, stock and product extension",
            ["product_lifecycle_report"],
            ["supply_chain", "review_insight", "store_metric_snapshot"],
            ["stage", "rank movement", "units 7d", "inventory", "lead time", "return rate", "review pain"],
            ["classify A/B/C/D", "build test/replenishment/clearance plan", "extend lifecycle with variants"],
            ["stock plan", "replenishment qty", "extension plan", "pause/clearance trigger"],
            "L0-L3",
            "/chat?intent=product_data",
        ),
        step(
            "strategy_memory",
            "19 Strategy Memory and AI Meeting",
            "What worked, failed, when to repeat, when not to repeat",
            ["strategy_memory"],
            ["selection_playbook", "autonomous_report", "operation_closure_report"],
            ["observation", "worked before", "failed before", "valid condition", "cannot do", "next trigger"],
            ["turn every result into reusable memory", "let multiple AI models discuss when available"],
            ["daily meeting note", "strategy memory", "next task list"],
            "L0-L2",
            "/dashboard",
        ),
        step(
            "pod_board",
            "20 POD Board",
            "Separate POD admin/factory/channel board while allowing POD sales in own dashboard",
            ["pod_admin_snapshot"],
            ["ip_image_risk", "supply_chain", "store_metric_snapshot"],
            ["blank", "design", "order", "factory job", "inventory", "channel status", "designer settlement", "IP status"],
            ["keep POD business separate", "only show POD-bound sales in own store board", "sync channels after approval"],
            ["POD snapshot", "factory risk", "channel sync draft", "IP review result"],
            "L0-L3",
            "/chat?intent=pod",
        ),
        step(
            "approval_execution",
            "21 Approval and Execution Safety",
            "Human approval queue, execution records and store protection",
            ["action_queue"],
            ["execution_result", "store_health_event"],
            ["action type", "store protection", "requires confirmation", "approval decision", "executed result", "rollback note"],
            ["never hide sensitive actions", "log what was done", "protect old/stable stores"],
            ["pending approvals", "executed action log", "rollback checklist"],
            "L0-L5 gradual",
            "/chat?intent=approval",
        ),
    ]


def step(
    step_id: str,
    phase: str,
    name: str,
    required_signals: list[str],
    optional_signals: list[str],
    must_capture_fields: list[str],
    ai_decisions: list[str],
    outputs: list[str],
    automation_level: str,
    page: str,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "phase": phase,
        "name": name,
        "required_signals": required_signals,
        "optional_signals": optional_signals,
        "must_capture_fields": must_capture_fields,
        "ai_decisions": ai_decisions,
        "outputs": outputs,
        "automation_level": automation_level,
        "page": page,
        "approval_gates": approval_gates_for_step(step_id),
    }


def evaluate_step(step_def: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    required = step_def["required_signals"]
    optional = step_def["optional_signals"]
    required_status = [signal_status(signal, context) for signal in required]
    optional_status = [signal_status(signal, context) for signal in optional]
    ready_required = [item for item in required_status if item["ready"]]
    ready_optional = [item for item in optional_status if item["ready"]]
    if required and len(ready_required) == len(required):
        status = "ready"
    elif ready_required or ready_optional:
        status = "partial"
    else:
        status = "missing"
    missing = [
        f"{item['label']} ({item['kind']})"
        for item in required_status
        if not item["ready"]
    ]
    if status == "missing" and optional_status:
        missing.extend(f"optional: {item['label']}" for item in optional_status[:3] if not item["ready"])
    detail = {
        **step_def,
        "status": status,
        "ready_required": len(ready_required),
        "required_count": len(required),
        "ready_optional": len(ready_optional),
        "optional_count": len(optional),
        "missing_details": missing[:8],
        "evidence": [item for item in [*required_status, *optional_status] if item["ready"]][:8],
        "next_action": next_action_for_step(step_def, status, missing),
    }
    return detail


def signal_status(signal: str, context: dict[str, Any]) -> dict[str, Any]:
    record_counts: dict[str, int] = context["record_counts"]
    prefixes: set[str] = context["output_prefixes"]
    configs: dict[str, bool] = context["configs"]
    if signal.endswith("_report"):
        ready = signal in prefixes
        return {"signal": signal, "label": signal.replace("_", " "), "kind": "report", "ready": ready, "count": 1 if ready else 0}
    if signal.endswith("_config"):
        ready = bool(configs.get(signal, False))
        return {"signal": signal, "label": signal.replace("_", " "), "kind": "config", "ready": ready, "count": 1 if ready else 0}
    if signal == "action_queue":
        count = int(context.get("pending_actions") or 0)
        ready = count > 0 or "autonomous_report" in prefixes
        return {"signal": signal, "label": "approval/action queue", "kind": "queue", "ready": ready, "count": count}
    count = int(record_counts.get(signal, 0) or 0)
    return {"signal": signal, "label": signal, "kind": "record", "ready": count > 0, "count": count}


def next_action_for_step(step_def: dict[str, Any], status: str, missing: list[str]) -> str:
    if status == "ready":
        return "继续每日观察；只把异常、机会和结果写入策略记忆。"
    if status == "partial":
        return f"补齐缺口：{', '.join(missing[:3])}。"
    return f"先补基础数据：{', '.join(missing[:3]) or '必要记录/配置'}。"


def approval_gates_for_step(step_id: str) -> list[str]:
    gates = {
        "listing_builder": ["publish/update listing", "price change", "image upload"],
        "ads_live_campaign": ["change ad budget", "join campaign", "set discount", "change live product links"],
        "influencer_crm": ["contact creator", "send sample", "pay creator"],
        "video_publishing": ["bind AIP", "upload/publish video", "use copyrighted music"],
        "orders_returns_finance": ["refund", "ship", "change settlement/payment"],
        "pod_board": ["sync channel listing", "factory dispatch", "private/public visibility change"],
        "approval_execution": ["any real external platform action"],
    }
    return gates.get(step_id, ["analysis and draft are automatic; real external changes require approval when applicable"])


def summarize_steps(steps: list[dict[str, Any]], record_counts: dict[str, int]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for item in steps:
        status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1
    missing_steps = [item for item in steps if item["status"] == "missing"]
    partial_steps = [item for item in steps if item["status"] == "partial"]
    return {
        "step_count": len(steps),
        "ready": status_counts.get("ready", 0),
        "partial": status_counts.get("partial", 0),
        "missing": status_counts.get("missing", 0),
        "overall_status": "ready" if not missing_steps and not partial_steps else ("partial" if not missing_steps else "needs_detail"),
        "top_missing": [
            {
                "id": item["id"],
                "name": item["name"],
                "next_action": item["next_action"],
            }
            for item in [*missing_steps, *partial_steps][:12]
        ],
        "record_counts": record_counts,
    }


def build_operation_closure_report(run_date: str, steps: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        f"# 运营闭环检查报告 - {run_date}",
        "",
        "## 给老板看的结论",
        f"- 全链路环节：{summary['step_count']} 个",
        f"- 已具备：{summary['ready']} 个",
        f"- 部分具备：{summary['partial']} 个",
        f"- 缺基础数据：{summary['missing']} 个",
        f"- 当前状态：{operation_status_label(summary['overall_status'])}",
        "",
        "## 今天先补什么",
    ]
    gaps = summary.get("top_missing", [])
    if not gaps:
        lines.append("- 暂无大缺口，继续每日监控和复盘。")
    for gap in gaps:
        lines.append(f"- {display_step_name(gap['id'], gap['name'])}：{gap['next_action']}")
    lines.extend(["", "## 后台排查明细"])
    for item in steps:
        lines.append(
            f"- {display_step_name(item['id'], item['name'])} | {step_status_label(item['status'])} | "
            f"基础数据 {item['ready_required']}/{item['required_count']} | "
            f"{item['next_action']}"
        )
    lines.extend(
        [
            "",
            "## 安全边界",
            "- AI 可以自动观察、打分、写草稿、出报告、排队动作。",
            "- 发布、改价、退款、发货、授权、上传、投放等真实动作，必须进入待确认队列。",
        ]
    )
    return "\n".join(lines) + "\n"


def display_step_name(step_id: str, fallback: str) -> str:
    return STEP_DISPLAY_NAMES.get(step_id, fallback)


def step_status_label(status: str) -> str:
    return {
        "ready": "可用",
        "partial": "部分可用",
        "missing": "缺数据",
    }.get(status, status)


def operation_status_label(status: str) -> str:
    return {
        "ready": "可以继续日常运行",
        "partial": "能跑，但需要补关键数据",
        "needs_detail": "先补基础数据再判断",
    }.get(status, status)


def write_operation_closure_report(root: Path, run_date: str, content: str) -> Path:
    path = root / "outputs" / f"{REPORT_PREFIX}_{run_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_operation_closure_json(root: Path, run_date: str, payload: dict[str, Any]) -> Path:
    path = root / "outputs" / f"{REPORT_PREFIX}_{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"run_date": run_date, **payload}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def latest_operation_closure_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    if not output_dir.exists():
        return "No operation closure report yet.", None
    paths = sorted(output_dir.glob(f"{REPORT_PREFIX}_*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not paths:
        return "No operation closure report yet.", None
    return paths[0].read_text(encoding="utf-8"), paths[0]


def count_records(records: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        counts[record.record_type] = counts.get(record.record_type, 0) + 1
    return counts


def output_prefixes(root: Path) -> set[str]:
    output_dir = root / "outputs"
    if not output_dir.exists():
        return set()
    prefixes: set[str] = set()
    mapping = {
        "selection_intelligence_": "selection_intelligence_report",
        "selection_meeting_": "selection_meeting_report",
        "tk_case_learning_": "tk_case_learning_report",
        "visual_creative_": "visual_creative_report",
        "patent_search_": "patent_search_report",
        "budget_planning_": "budget_planning_report",
        "launch_control_": "launch_control_report",
        "product_lifecycle_": "product_lifecycle_report",
        "autonomous_run_": "autonomous_report",
        "operation_closure_": "operation_closure_report",
    }
    for path in output_dir.glob("*.md"):
        for prefix, label in mapping.items():
            if path.name.startswith(prefix):
                prefixes.add(label)
    return prefixes


def config_flags(root: Path) -> dict[str, bool]:
    pod_config = load_pod_admin_config(root)
    return {
        "product_targets_config": (root / "config" / "product_targets.json").exists(),
        "platform_autopilot_config": (root / "config" / "platform_autopilot.json").exists(),
        "api_sources_config": (root / "config" / "api_sources.json").exists(),
        "budget_plans_config": (root / "config" / "budget_plans.json").exists(),
        "pod_admin_config": bool(pod_config.enabled),
    }
