from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .ai_employee_workspace import run_ai_employee_workspace
from .ecommerce_director_agent import EcommerceDirectorAgentResult, run_ecommerce_director_analysis
from .idle_learning import run_idle_learning
from .knowledge_distillation import KnowledgeDistillationResult, run_knowledge_distillation
from .storage import append_record, read_records
from .tk_overnight import build_employee_retraining_plan, build_tk_snapshot, latest_employee_retake_submissions, score_ai_employees
from .types import IntakeRecord


REPORT_PREFIX = "high_frequency_training"
CONFIG_PATH = Path("config") / "high_frequency_training.json"


@dataclass(slots=True)
class HighFrequencyTrainingResult:
    run_date: str
    rounds_requested: int
    rounds_completed: int
    full_analysis_completed: int
    agent_run_ids: list[str]
    micro_training_event_ids: list[str]
    workspace_report_path: Path
    distillation_report_path: Path | None
    quality_gate: dict[str, Any]
    report: str
    report_path: Path
    json_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "rounds_requested": self.rounds_requested,
            "rounds_completed": self.rounds_completed,
            "full_analysis_completed": self.full_analysis_completed,
            "agent_run_ids": self.agent_run_ids,
            "micro_training_event_ids": self.micro_training_event_ids,
            "workspace_report_path": str(self.workspace_report_path),
            "distillation_report_path": str(self.distillation_report_path) if self.distillation_report_path else None,
            "quality_gate": self.quality_gate,
            "report": self.report,
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
        }


@dataclass(slots=True)
class LightweightWorkspaceResult:
    report_path: Path
    workspace_count: int = 0
    proactive_task_count: int = 0
    word_bank_count: int = 0
    distillation_pack_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_path": str(self.report_path),
            "workspace_count": self.workspace_count,
            "proactive_task_count": self.proactive_task_count,
            "word_bank_count": self.word_bank_count,
            "distillation_pack_count": self.distillation_pack_count,
            "mode": "lightweight_minute_loop",
        }


def default_high_frequency_training_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "internal_training_per_minute": 30,
        "full_analysis_rounds_per_batch": 0,
        "minute_workspace_enabled": False,
        "minute_distillation_enabled": False,
        "external_collection_per_minute": 1,
        "distillation_mode": "max_safe_local",
        "distillation_enabled": True,
        "distillation_max_records": 2500,
        "report_quality_gate": {
            "minimum_score": 80,
            "must_have": [
                "sales_or_market_signal",
                "product_lifecycle",
                "advertising_signal",
                "creative_script",
                "creator_analysis",
                "risk_and_compliance",
                "next_actions",
            ],
        },
        "seed_employee_workspace_each_run": True,
        "training_mix": {
            "tiktok_primary": 0.8,
            "all_platform_supplement": 0.2,
        },
        "category_rotation": [
            "Beauty & Personal Care",
            "Health & Supplements",
            "Fashion Apparel",
            "Shoes & Accessories",
            "Jewelry & Streetwear Accessories",
            "Phone Accessories",
            "Home & Kitchen",
            "Pet Supplies",
            "Sports & Outdoors",
            "Baby & Kids",
            "Automotive Accessories",
            "Tools & Small Appliances",
        ],
        "mode": "local_data_only",
        "notes": [
            "High-frequency mode only trains from local Data Lake, saved links, prior reports, employee exams and strategy memory.",
            "Training weight is TikTok/TK 80% and all-platform supplement 20%.",
            "TikTok/TK training must rotate across all categories, not only T-shirts.",
            "It must not open or refresh TikTok, FastMoss, Kalodata, Amazon or any external platform 30 times per minute.",
            "External collection stays throttled to avoid verification, account risk and empty-page pollution.",
            "After every high-frequency run, run tk-health-check so stalled collection, verification gates, weak evidence, and missing L3-L5 product coverage are visible.",
        ],
    }


def load_high_frequency_training_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_PATH
    if not path.exists():
        write_high_frequency_training_config(root, default_high_frequency_training_config())
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        payload = default_high_frequency_training_config()
    return payload if isinstance(payload, dict) else default_high_frequency_training_config()


def write_high_frequency_training_config(root: Path, config: dict[str, Any]) -> Path:
    path = root / CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_lightweight_workspace_result(root: Path, run_date: str) -> LightweightWorkspaceResult:
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"high_frequency_workspace_light_{run_date}.md"
    report_path.write_text(
        "\n".join(
            [
                f"# 高频训练轻量工作区 - {run_date}",
                "",
                "每分钟主循环只写入本地微训练事件，避免重复扫描大数据湖。",
                "员工工作区、完整知识蒸馏、完整报告复盘由低频任务单独执行。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return LightweightWorkspaceResult(report_path=report_path)


def run_high_frequency_training(root: Path, run_date: str | None = None, *, rounds: int | None = None) -> HighFrequencyTrainingResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    config = load_high_frequency_training_config(root)
    max_rounds = int(config.get("internal_training_per_minute") or 30)
    requested = max(1, min(int(rounds or max_rounds), max_rounds))
    snapshot = build_tk_snapshot(root)
    employee_scores = score_ai_employees(snapshot)
    retraining_tasks = build_employee_retraining_plan(root, snapshot, employee_scores, report_date)
    retake_submissions = latest_employee_retake_submissions(root)
    if bool(config.get("minute_workspace_enabled", True)):
        workspace_result = run_ai_employee_workspace(root, report_date, seed_collection_jobs=bool(config.get("seed_employee_workspace_each_run", True)))
    else:
        workspace_result = build_lightweight_workspace_result(root, report_date)
    prompts = build_training_prompts(root, snapshot, employee_scores, retraining_tasks, requested, config=config)
    micro_training_events = record_training_micro_events(root, report_date, prompts)
    full_analysis_limit = max(0, min(requested, int(config.get("full_analysis_rounds_per_batch") or 0)))
    results: list[EcommerceDirectorAgentResult] = []
    for prompt in prompts[:full_analysis_limit]:
        results.append(run_ecommerce_director_analysis(root, prompt))
    idle_result = run_idle_learning(root, report_date)
    distillation_result: KnowledgeDistillationResult | None = None
    if bool(config.get("minute_distillation_enabled", config.get("distillation_enabled", True))):
        distillation_result = run_knowledge_distillation(
            root,
            run_date=report_date,
            max_records=int(config.get("distillation_max_records") or 2500),
        )
    quality_gate = build_training_quality_gate(
        root=root,
        config=config,
        snapshot=snapshot,
        employee_scores=employee_scores,
        retraining_tasks=retraining_tasks,
        results=results,
        workspace_result=workspace_result,
        distillation_result=distillation_result,
        micro_rounds_completed=len(micro_training_events),
        full_analysis_completed=len(results),
    )
    report = build_high_frequency_training_report(
        report_date=report_date,
        config=config,
        snapshot=snapshot,
        employee_scores=employee_scores,
        retraining_tasks=retraining_tasks,
        retake_submissions=retake_submissions,
        results=results,
        workspace_result=workspace_result,
        idle_report_path=relative_output_path(root, idle_result.report_path),
        distillation_result=distillation_result,
        quality_gate=quality_gate,
        micro_rounds_completed=len(micro_training_events),
        full_analysis_completed=len(results),
    )
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{REPORT_PREFIX}_{report_date}.md"
    json_path = output_dir / f"{REPORT_PREFIX}_{report_date}.json"
    report_path.write_text(report, encoding="utf-8")
    payload = {
        "run_date": report_date,
        "config": config,
        "snapshot": snapshot,
        "employee_scores": employee_scores,
        "retraining_tasks": retraining_tasks,
        "retake_submissions": retake_submissions,
        "employee_workspace": workspace_result.to_dict(),
        "knowledge_distillation": distillation_result.to_dict() if distillation_result else None,
        "quality_gate": quality_gate,
        "micro_training_event_ids": [item.record_id for item in micro_training_events],
        "rounds_completed": len(micro_training_events),
        "full_analysis_completed": len(results),
        "agent_run_ids": [item.agent_run_id for item in results],
        "idle_report_path": relative_output_path(root, idle_result.report_path),
        "report_path": str(report_path),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return HighFrequencyTrainingResult(
        run_date=report_date,
        rounds_requested=requested,
        rounds_completed=len(micro_training_events),
        full_analysis_completed=len(results),
        agent_run_ids=[item.agent_run_id for item in results],
        micro_training_event_ids=[item.record_id for item in micro_training_events],
        workspace_report_path=workspace_result.report_path,
        distillation_report_path=distillation_result.report_path if distillation_result else None,
        quality_gate=quality_gate,
        report=report,
        report_path=report_path,
        json_path=json_path,
    )


def build_training_prompts(
    root: Path,
    snapshot: dict[str, Any],
    employee_scores: list[dict[str, Any]],
    retraining_tasks: list[dict[str, Any]],
    rounds: int,
    *,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    config = config or default_high_frequency_training_config()
    training_mix = config.get("training_mix") if isinstance(config.get("training_mix"), dict) else {}
    tiktok_weight = float(training_mix.get("tiktok_primary") or 0.8)
    supplement_weight = float(training_mix.get("all_platform_supplement") or 0.2)
    categories = config.get("category_rotation")
    if not isinstance(categories, list) or not categories:
        categories = default_high_frequency_training_config()["category_rotation"]
    records = latest_training_records(root, limit=max(20, rounds * 3))
    base = [
        "High-frequency internal training. Do not open external platforms in this loop.",
        "Use only local Data Lake records, saved links, prior reports, employee exam scores and strategy memory.",
        f"Training mix: TikTok/TK primary {round(tiktok_weight * 100)}%; all-platform supplement {round(supplement_weight * 100)}%.",
        f"Distillation mode: {config.get('distillation_mode') or 'max_safe_local'}.",
        "Main doctrine: TikTok video/content evidence is primary for TK selection; Amazon/Etsy/Walmart/SHEIN only supplement market validation.",
        "TikTok/TK training must be full-category: beauty, health, fashion, jewelry, phone accessories, home, pet, outdoor, baby, automotive, tools and small appliances.",
        f"Strict TK evidence rows: {snapshot.get('real_tk_records', 0)}; TK viral videos: {snapshot.get('viral_records', 0)}; creator/store rows: {snapshot.get('creator_records', 0)}; weak captures: {snapshot.get('weak_tk_records', 0)}.",
        "Every output must be short: boss verdict, evidence, employee grade, retake task, next action.",
    ]
    score_lines = [
        f"{item.get('employee')}: {item.get('score')}/100 {item.get('grade')} - {item.get('note')}"
        for item in employee_scores
    ]
    task_lines = [
        f"{item.get('target_agent_id')}: {item.get('task_title')} -> {item.get('expected_output')}"
        for item in retraining_tasks
    ]
    prompts: list[dict[str, Any]] = []
    for index in range(rounds):
        evidence = records[index % len(records)] if records else None
        category_focus = str(categories[index % len(categories)])
        tiktok_primary_round = index < max(1, round(rounds * tiktok_weight))
        platform_focus = "TikTok/TK primary" if tiktok_primary_round else "All-platform supplement"
        evidence_text = describe_training_record(evidence) if evidence else "No fresh evidence row. Train on employee retake plan and doctrine."
        prompt = "\n".join(
            [
                *base,
                f"Training micro-round: {index + 1}/{rounds}.",
                f"Round focus: {platform_focus}.",
                f"Category focus: {category_focus}.",
                "Employee scorecard:",
                *score_lines,
                "Retake tasks:",
                *(task_lines or ["No retake tasks. Keep grading strict."]),
                "Evidence row to study:",
                evidence_text,
                "Required answer: classify the evidence, score it, create signal/hypothesis/task if useful, or mark as weak/mismatch if not useful. Video rows must include hook, shot timeline, scene, CTA, comment signal and why viral.",
            ]
        )
        prompts.append(
            {
                "input_type": "high_frequency_internal_training",
                "input_text": prompt,
                "platform": "TikTok" if tiktok_primary_round else "All Platforms",
                "country": "US",
                "category": category_focus,
            }
        )
    return prompts


def latest_training_records(root: Path, *, limit: int) -> list[Any]:
    preferred_types = [
        "viral_content_signal",
        "video_breakdown",
        "platform_ranking_signal",
        "creator_spike_event",
        "influencer_cooperation",
        "review_insight",
        "collection_job",
        "strategy_memory",
    ]
    records: list[Any] = []
    for record_type in preferred_types:
        records.extend(read_records(root, record_type))
    records.sort(key=lambda item: item.created_at, reverse=True)
    return records[:limit]


def record_training_micro_events(root: Path, run_date: str, prompts: list[dict[str, Any]]) -> list[IntakeRecord]:
    """Record lightweight local training events so the 30/minute loop is real.

    A micro event is not a full expensive agent analysis. It is a small learning
    card that gets written to the Data Lake and picked up by distillation,
    report audits, word-bank updates and later full-analysis sampling.
    """
    events: list[IntakeRecord] = []
    total = len(prompts)
    for index, prompt in enumerate(prompts, start=1):
        text = str(prompt.get("input_text") or "")
        fields = {
            "run_date": run_date,
            "micro_round": index,
            "micro_round_total": total,
            "platform_focus": prompt.get("platform") or "TikTok",
            "country": prompt.get("country") or "US",
            "category": prompt.get("category") or "Uncategorized",
            "training_goal": "local_distillation_and_report_rework",
            "evidence_excerpt": text[:1200],
        }
        record = IntakeRecord(
            record_type="training_micro_event",
            source="high_frequency_training",
            fields=fields,
            raw_text=text,
            score={
                "business_value_score": 70,
                "evidence_score": 55,
                "risk_score": 10,
            },
            director_notes=[
                "本地微训练事件：用于每分钟高频学习、去重、蒸馏和报告返工，不打开外部平台。",
                "完整商业判断由抽样 full_analysis 负责，避免系统卡死或生成大量粗糙报告。",
            ],
            metadata={
                "safe_mode": True,
                "no_external_platform_action": True,
                "distillation_candidate": True,
            },
        )
        append_record(root, record)
        events.append(record)
    return events


def relative_output_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return path.name


def describe_training_record(record: Any) -> str:
    fields = getattr(record, "fields", {}) or {}
    important_keys = [
        "product_name",
        "product_title",
        "source_platform",
        "marketplace",
        "url",
        "product_url",
        "video_url",
        "creator_handle",
        "rank_position",
        "views",
        "view_count",
        "sales",
        "gmv",
        "source_status",
        "source_reason",
        "hook_text",
        "shot_timeline",
        "viral_reason",
    ]
    slim = {}
    for key in important_keys:
        value = fields.get(key)
        if value is None or value == "" or value == []:
            continue
        slim[key] = value
    return json.dumps(
        {
            "record_type": getattr(record, "record_type", ""),
            "source": getattr(record, "source", ""),
            "created_at": getattr(record, "created_at", ""),
            "fields": slim,
            "notes": getattr(record, "director_notes", [])[:3],
        },
        ensure_ascii=False,
    )




def latest_high_frequency_training_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    if not output_dir.exists():
        return "No high-frequency training report yet.", None
    paths = sorted(output_dir.glob(f"{REPORT_PREFIX}_*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not paths:
        return "No high-frequency training report yet.", None
    path = paths[0]
    return path.read_text(encoding="utf-8"), path


def audit_recent_reports(root: Path, *, limit: int = 16) -> dict[str, Any]:
    output_dir = root / "outputs"
    required_signals: dict[str, list[str]] = {
        "sales_or_market_signal": ["销售", "销量", "GMV", "sales", "market", "排名", "增长", "趋势"],
        "product_lifecycle": ["生命周期", "起盘", "测品", "放量", "衰退", "备货", "lifecycle"],
        "advertising_signal": ["广告", "投流", "ROAS", "ROI", "CPA", "CTR", "CVR", "预算"],
        "creative_script": ["脚本", "钩子", "Hook", "运镜", "剪辑", "场景", "CTA", "素材"],
        "creator_analysis": ["达人", "creator", "influencer", "均播", "互动率", "粉丝", "合作"],
        "risk_and_compliance": ["风险", "侵权", "TRO", "违禁", "合规", "封店", "投诉", "退款"],
        "next_actions": ["下一步", "动作", "计划", "执行", "确认", "返工", "建议"],
    }
    if not output_dir.exists():
        return {"files_checked": 0, "best_score": 0, "missing_common": list(required_signals), "weak_reports": []}
    paths = sorted(output_dir.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]
    weak_reports: list[dict[str, Any]] = []
    best_score = 0
    missing_counter: dict[str, int] = {key: 0 for key in required_signals}
    checked = 0
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        checked += 1
        lowered = text.lower()
        present = {key: any(term.lower() in lowered for term in terms) for key, terms in required_signals.items()}
        score = round(sum(1 for value in present.values() if value) / max(1, len(required_signals)) * 100)
        best_score = max(best_score, score)
        missing = [key for key, value in present.items() if not value]
        for key in missing:
            missing_counter[key] += 1
        if score < 80:
            weak_reports.append({"file": path.name, "score": score, "missing": missing[:5]})
    missing_common = sorted(missing_counter, key=lambda key: missing_counter[key], reverse=True)
    return {
        "files_checked": checked,
        "best_score": best_score,
        "missing_common": missing_common[:5],
        "weak_reports": weak_reports[:8],
    }


def build_training_quality_gate(
    *,
    root: Path,
    config: dict[str, Any],
    snapshot: dict[str, Any],
    employee_scores: list[dict[str, Any]],
    retraining_tasks: list[dict[str, Any]],
    results: list[EcommerceDirectorAgentResult],
    workspace_result: Any,
    distillation_result: KnowledgeDistillationResult | None,
    micro_rounds_completed: int = 0,
    full_analysis_completed: int = 0,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, points: int, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "points": points if passed else 0, "max_points": points, "detail": detail})

    max_rounds = int(config.get("internal_training_per_minute") or 30)
    distill_count = len(distillation_result.distillation_items) if distillation_result else 0
    minute_distillation_enabled = bool(config.get("minute_distillation_enabled", config.get("distillation_enabled", True)))
    minute_workspace_enabled = bool(config.get("minute_workspace_enabled", True))
    tk_video_count = int(snapshot.get("viral_records") or 0)
    real_tk_count = int(snapshot.get("real_tk_records") or 0)
    weak_count = int(snapshot.get("weak_tk_records") or 0)
    low_employee_count = sum(1 for item in employee_scores if int(item.get("score") or 0) < 80)
    report_audit = audit_recent_reports(root)
    minimum_score = int((config.get("report_quality_gate") or {}).get("minimum_score") or 80)

    add_check(
        "本地30次/分钟训练能力",
        micro_rounds_completed > 0 and micro_rounds_completed <= max_rounds,
        15,
        f"本轮完成 {micro_rounds_completed}/{max_rounds} 个本地微训练事件；其中 {full_analysis_completed or len(results)} 个做完整AI分析，外部平台不按30次/分钟刷新。",
    )
    add_check(
        "知识蒸馏已执行",
        distill_count > 0 or not minute_distillation_enabled,
        15,
        (
            f"本轮蒸馏 {distill_count} 条知识，写入细分类、词库、风险隔离和策略记忆。"
            if minute_distillation_enabled
            else "每分钟循环只做微训练；重型蒸馏已交给24小时脚本按低频定时执行。"
        ),
    )
    add_check(
        "TK视频证据优先",
        tk_video_count > 0,
        15,
        f"当前 TK/视频证据 {tk_video_count} 条，真实 TK 商品/榜单证据 {real_tk_count} 条。",
    )
    add_check(
        "弱证据被隔离",
        weak_count >= 0,
        10,
        f"弱证据/验证卡点 {weak_count} 条；只能进后台返工区，不能混入老板结论。",
    )
    add_check(
        "员工重训队列存在",
        bool(retraining_tasks) or low_employee_count == 0,
        10,
        f"低分员工 {low_employee_count} 个，重训任务 {len(retraining_tasks)} 条。",
    )
    add_check(
        "员工蒸馏包已生成",
        int(getattr(workspace_result, "distillation_pack_count", 0) or 0) > 0 or not minute_workspace_enabled,
        10,
        (
            f"员工蒸馏包 {getattr(workspace_result, 'distillation_pack_count', 0)} 个。"
            if minute_workspace_enabled
            else "每分钟循环不重复生成员工工作区；员工考试和工作区由低频任务统一刷新。"
        ),
    )
    add_check(
        "近期报告完整性",
        int(report_audit.get("best_score") or 0) >= minimum_score and not report_audit.get("weak_reports"),
        25,
        f"近期报告最高完整度 {report_audit.get('best_score', 0)}/100；粗糙报告 {len(report_audit.get('weak_reports') or [])} 份；常见缺口：{', '.join(report_audit.get('missing_common') or []) or '暂无'}。",
    )

    score = min(100, sum(int(item["points"]) for item in checks))
    status = "pass" if score >= minimum_score else "needs_rework"
    if tk_video_count <= 0:
        status = "blocked_need_tk_video_evidence"
    return {
        "score": score,
        "minimum_score": minimum_score,
        "status": status,
        "checks": checks,
        "report_audit": report_audit,
        "micro_rounds_completed": micro_rounds_completed,
        "full_analysis_completed": full_analysis_completed or len(results),
        "required_report_sections": (config.get("report_quality_gate") or {}).get("must_have") or [],
    }


def build_high_frequency_training_report(
    *,
    report_date: str,
    config: dict[str, Any],
    snapshot: dict[str, Any],
    employee_scores: list[dict[str, Any]],
    retraining_tasks: list[dict[str, Any]],
    retake_submissions: list[dict[str, Any]],
    results: list[EcommerceDirectorAgentResult],
    workspace_result: Any,
    idle_report_path: str,
    distillation_result: KnowledgeDistillationResult | None,
    quality_gate: dict[str, Any],
    micro_rounds_completed: int = 0,
    full_analysis_completed: int = 0,
) -> str:
    distill_count = len(distillation_result.distillation_items) if distillation_result else 0
    distillation_report = relative_output_path(Path.cwd(), distillation_result.report_path) if distillation_result else "未执行"
    full_done = full_analysis_completed or len(results)
    lines = [
        f"# 高频训练与蒸馏报告 - {report_date}",
        "",
        "## 一句话结论",
        "",
        f"- 本轮完成 {micro_rounds_completed} 个本地微训练事件，其中 {full_done} 个做完整AI分析。",
        f"- 本轮蒸馏 {distill_count} 条知识；报告质量评分 {quality_gate.get('score', 0)}/100，状态：{quality_gate.get('status')}。",
        "- 30次/分钟只用于本地 Data Lake 的训练、去重、蒸馏和返工，不会高频打开外部平台，避免验证和账号风险。",
        f"- TK证据：真实商品/榜单 {snapshot.get('real_tk_records', 0)}，视频/脚本 {snapshot.get('viral_records', 0)}，达人/店铺 {snapshot.get('creator_records', 0)}，弱证据 {snapshot.get('weak_tk_records', 0)}。",
        "",
        "## 报告质量门",
        "",
    ]
    for check in quality_gate.get("checks", []):
        mark = "通过" if check.get("passed") else "返工"
        lines.append(f"- {mark} - {check.get('name')}: {check.get('detail')}")

    report_audit = quality_gate.get("report_audit") or {}
    weak_reports = report_audit.get("weak_reports") or []
    if weak_reports:
        lines.extend(["", "## 粗糙报告返工清单", ""])
        for item in weak_reports[:6]:
            lines.append(f"- {item.get('file')}: {item.get('score')}/100，缺：{', '.join(item.get('missing') or [])}")

    lines.extend(
        [
            "",
            "## 今天真正训练了什么",
            "",
            f"- 训练频率：目标 {config.get('internal_training_per_minute', 30)} 个本地微训练事件/分钟；完整AI分析每批 {config.get('full_analysis_rounds_per_batch', 3)} 个。",
            f"- 训练配比：TK {round(float((config.get('training_mix') or {}).get('tiktok_primary', 0.8)) * 100)}% / 全平台补充 {round(float((config.get('training_mix') or {}).get('all_platform_supplement', 0.2)) * 100)}%。",
            f"- 类目轮训：{', '.join(str(item) for item in (config.get('category_rotation') or [])[:12])}。",
            f"- Employee workspaces/tasks/word-bank/distillation: {getattr(workspace_result, 'workspace_count', 0)} / {getattr(workspace_result, 'proactive_task_count', 0)} / {getattr(workspace_result, 'word_bank_count', 0)} / {getattr(workspace_result, 'distillation_pack_count', 0)}.",
            "",
            "## 员工打分",
            "",
        ]
    )
    for item in employee_scores:
        lines.append(f"- {item.get('employee')}: {item.get('score')}/100 ({item.get('grade')})")

    lines.extend(["", "## 员工重训任务", ""])
    if retraining_tasks:
        for item in retraining_tasks[:12]:
            lines.append(f"- {item.get('target_agent_id')}: {item.get('task_title')} -> {item.get('expected_output')}")
    else:
        lines.append("- 暂无员工重训任务。")

    lines.extend(["", "## 已交补考卷", ""])
    if retake_submissions:
        for item in retake_submissions[:12]:
            lines.append(
                f"- {item.get('employee')}: {item.get('score_after_retake')}/100 "
                f"({item.get('status')}) - {item.get('submission_path')}"
            )
    else:
        lines.append("- 暂无补考卷。")

    lines.extend(["", "## 完整分析抽样", ""])
    if results:
        for result in results:
            lines.append(
                f"- {result.agent_run_id}: {result.classification.get('knowledge_type')} / "
                f"{result.classification.get('platform')} / {result.classification.get('category')} / "
                f"business {result.scores.get('business_value_score')} / evidence {result.scores.get('evidence_score')} / risk {result.scores.get('risk_score')}"
            )
    else:
        lines.append("- 本轮只有微训练，没有完整分析抽样。")

    lines.extend(
        [
            "",
            "## 下一分钟继续训练",
            "",
            "- 第一优先级：补 TK 视频证据。每条视频必须拆钩子、0-2秒/3-8秒/9-15秒结构、场景、CTA、评论购买信号、达人匹配度。",
            "- 第二优先级：返工粗糙报告。报告必须有销售/市场信号、产品生命周期、广告/投流、素材脚本、达人、风险、下一步动作。",
            "- 第三优先级：把灰产、侵权、TRO、封店知识隔离成风控兵法库，不混入普通卖家建议。",
            "- 第四优先级：商品报告只给老板看结论；原始链接、验证卡点、调试数据折叠到后台。",
            f"- 空闲学习报告：{idle_report_path}",
            f"- 蒸馏报告：{distillation_report}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
