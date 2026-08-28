from __future__ import annotations

import hashlib
import csv
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .daily_runner import fetch_public_page
from .parser import normalize_fields
from .scoring import score_record
from .storage import append_record, read_records
from .types import IntakeRecord


LEARNING_SOURCES_CONFIG = Path("config") / "learning_sources.json"
LEARNING_REPORT_PREFIX = "learning_sources"
LEARNING_WORKBOOK_PREFIX = "learning_case_workbook"
DISTILLATION_VERSION = "web-case-distillation-v1"
LEARNING_WORKBOOK_HEADERS = [
    "序号",
    "知识分类",
    "问题/要点",
    "来源",
    "来源链接",
    "可信度",
    "答案/结论",
    "可执行步骤",
    "完整度",
    "风险提示",
    "使用边界",
    "负责模块",
    "下一步",
    "是否需要人工确认",
]

TRUST_SCORE_BY_SOURCE_TYPE = {
    "own_sales_case": 98,
    "top_seller_case": 94,
    "official_case_study": 88,
    "official_seller_education": 82,
    "official_trend_report": 80,
    "vendor_tool_export": 72,
    "public_learning_source": 58,
    "forum_or_social": 42,
}

GRAY_RISK_TERMS = [
    "补单",
    "刷单",
    "刷评",
    "买评",
    "虚拟仓",
    "规避审核",
    "绕过审核",
    "测评卡",
    "黑科技",
    "强开",
    "养号",
    "卡审",
]

COMPLIANCE_RISK_TERMS = [
    "侵权",
    "TRO",
    "tro",
    "商标",
    "版权",
    "专利",
    "仿牌",
    "封店",
    "二审",
    "投诉",
    "禁词",
    "违规",
    "假货",
]

CATEGORY_RULES = [
    ("risk_case", [*GRAY_RISK_TERMS, *COMPLIANCE_RISK_TERMS]),
    ("viral_video_case", ["video", "tiktok", "素材", "脚本", "hook", "钩子", "运镜", "达人", "creator", "shorts", "reels"]),
    ("money_case", ["roi", "roas", "gmv", "profit", "sales", "销量", "亏", "赚", "成本", "转化"]),
    ("product_selection_case", ["product research", "选品", "爆品", "榜单", "category", "类目", "new release", "bsr"]),
    ("listing_case", ["listing", "标题", "keyword", "seo", "主图", "卖点", "review", "评论"]),
    ("ads_case", ["ads", "advertising", "ppc", "投流", "预算", "cpa", "ctr", "cvr"]),
    ("supply_chain_case", ["factory", "supplier", "库存", "发货", "物流", "fulfillment"]),
]


@dataclass(slots=True)
class LearningRunResult:
    run_date: str
    statuses: list[dict[str, Any]]
    records: list[IntakeRecord]
    report: str
    report_path: Path
    workbook_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "statuses": self.statuses,
            "saved_records": len(self.records),
            "records": [record.to_dict() for record in self.records],
            "report": self.report,
            "report_path": str(self.report_path),
            "workbook_path": str(self.workbook_path) if self.workbook_path else None,
        }


def run_learning_sources(root: Path, run_date: str | None = None) -> LearningRunResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    config = load_learning_sources(root)
    statuses: list[dict[str, Any]] = []
    records: list[IntakeRecord] = []
    if config.get("enabled") is False:
        statuses.append(
            {
                "source_id": "legacy_learning_sources",
                "status": "disabled",
                "reason": str(
                    config.get("disabled_reason")
                    or "Legacy learning source collection is disabled pending reviewed admission."
                ),
            }
        )
        report = build_learning_report(report_date, statuses, records)
        report_path = write_learning_report(root, report_date, report)
        return LearningRunResult(report_date, statuses, records, report, report_path, None)
    sources = config.get("sources", [])
    if not isinstance(sources, list):
        sources = []

    for source in sources:
        if not isinstance(source, dict):
            continue
        status, record = collect_learning_source(root, source, report_date)
        statuses.append(status)
        if record:
            records.append(record)

    report = build_learning_report(report_date, statuses, records)
    report_path = write_learning_report(root, report_date, report)
    workbook_path = write_learning_workbook(root, report_date)
    return LearningRunResult(report_date, statuses, records, report, report_path, workbook_path)


def load_learning_sources(root: Path) -> dict[str, Any]:
    path = root / LEARNING_SOURCES_CONFIG
    if not path.exists():
        return {"safe_mode": True, "sources": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"safe_mode": True, "sources": []}


def collect_learning_source(root: Path, source: dict[str, Any], run_date: str) -> tuple[dict[str, Any], IntakeRecord | None]:
    source_id = str(source.get("id") or source.get("url") or "unnamed-learning-source").strip()
    if not source.get("enabled", False):
        return {"source_id": source_id, "status": "skipped", "reason": "source disabled"}, None
    if source.get("requires_login", False):
        return {"source_id": source_id, "status": "manual_gate", "reason": "source requires login or human verification"}, None
    url = str(source.get("url") or "").strip()
    if not url:
        return {"source_id": source_id, "status": "missing_url", "reason": "source URL is missing"}, None
    if already_learned_today(root, source_id, url, run_date):
        return {"source_id": source_id, "status": "skipped", "reason": "already learned today", "url": url}, None

    try:
        page = fetch_public_page(url)
    except Exception as exc:  # noqa: BLE001 - source-level failure belongs in the learning report.
        return {"source_id": source_id, "status": "failed", "url": url, "reason": str(exc)}, None

    record = build_learning_record(source, page, run_date)
    append_record(root, record)
    distilled_records = persist_learning_distillation(root, record, source, page, run_date)
    distillation_fields = distilled_records[0].fields if distilled_records else {}
    return {
        "source_id": source_id,
        "status": "learned",
        "url": url,
        "title": page.title,
        "saved_record_id": record.record_id,
        "link_count": len(page.links),
        "text_length": len(page.text),
        "distilled_records": len(distilled_records),
        "knowledge_category": distillation_fields.get("knowledge_category"),
        "trust_score": distillation_fields.get("trust_score"),
        "risk_only_training": distillation_fields.get("risk_only_training"),
        "risk_flags": distillation_fields.get("risk_flags") or [],
    }, record


def already_learned_today(root: Path, source_id: str, url: str, run_date: str) -> bool:
    for record in read_records(root, "industry_research_asset"):
        metadata = record.metadata or {}
        fields = record.fields or {}
        if metadata.get("learning_source_id") != source_id:
            continue
        if fields.get("source_url") != url:
            continue
        if str(metadata.get("learning_run_date") or record.created_at[:10]) == run_date:
            return True
    return False


def build_learning_record(source: dict[str, Any], page: Any, run_date: str) -> IntakeRecord:
    source_name = str(source.get("name") or page.title or source.get("id") or page.url)
    source_type = str(source.get("source_type") or "public_learning_source")
    focus = ", ".join(str(item) for item in source.get("focus", []) if str(item).strip()) if isinstance(source.get("focus"), list) else str(source.get("focus") or "")
    fields = normalize_fields(
        {
            "research_asset_type": source.get("research_asset_type") or source_type,
            "industry_scope": source.get("industry_scope") or "cross_border_ecommerce",
            "source_name": source_name,
            "source_url": page.url,
            "page_title": page.title,
            "page_text": page.text[:10000],
            "page_links": page.links[:40],
            "knowledge_node": focus or source_name,
            "keyword_cluster": source.get("keyword_cluster") or focus,
            "opportunity": source.get("opportunity") or f"Extract reusable ecommerce operating lessons from {source_name}.",
            "validation_task": source.get("validation_task") or "Map lessons into Product Intelligence, Keyword Hunter, Listing Builder, Viral Content Intelligence, Influencer Hunter, and Risk Director.",
            "update_frequency": source.get("update_frequency") or "daily",
            "marketplace": source.get("marketplace") or "",
        }
    )
    score, notes = score_record("industry_research_asset", fields)
    return IntakeRecord(
        record_type="industry_research_asset",
        fields=fields,
        raw_text=json.dumps({"source": source.get("id"), "url": page.url, "title": page.title, "run_date": run_date}, ensure_ascii=False),
        source="learning_sources",
        score=score,
        director_notes=notes,
        metadata={
            "learning_source_id": source.get("id"),
            "learning_run_date": run_date,
            "automation_mode": "safe_read_only_learning",
        },
    )


def persist_learning_distillation(root: Path, asset_record: IntakeRecord, source: dict[str, Any], page: Any, run_date: str) -> list[IntakeRecord]:
    text = distillation_text(asset_record, page, source)
    if not text.strip():
        return []

    source_id = str(source.get("id") or page.url or asset_record.record_id)
    source_type = str(source.get("research_asset_type") or source.get("source_type") or "public_learning_source")
    category = classify_learning_category(text, source)
    risk_flags = detect_risk_flags(text)
    has_gray_risk = any(flag["risk_type"] == "grey_tactic" for flag in risk_flags)
    has_compliance_risk = any(flag["risk_type"] == "compliance_risk" for flag in risk_flags)
    trust_score = trust_score_for_source(source)
    tags = extract_training_tags(text, source)
    modules = module_targets(category)
    created_at = datetime.now(timezone.utc).isoformat()
    distillation_id = stable_id("webdist_", source_id, page.url, run_date, DISTILLATION_VERSION)

    if has_gray_risk:
        allowed_use = "risk_awareness_only"
        execution_policy = "risk_recognition_only"
        human_review_required = True
        risk_only_training = True
    elif has_compliance_risk:
        allowed_use = "risk_playbook_reference"
        execution_policy = "human_review_strategy_only"
        human_review_required = True
        risk_only_training = False
    else:
        allowed_use = "strategy_reference"
        execution_policy = "read_only_strategy_training"
        human_review_required = False
        risk_only_training = False

    summary = build_distillation_summary(text, category, risk_flags)
    actionable_sop = build_actionable_sop(category, risk_only_training, has_compliance_risk)
    distilled = IntakeRecord(
        record_type="web_case_distillation",
        fields=normalize_fields(
            {
                "distillation_id": distillation_id,
                "source_asset_id": asset_record.record_id,
                "source_name": asset_record.fields.get("source_name"),
                "source_url": asset_record.fields.get("source_url"),
                "source_type": source_type,
                "marketplace": asset_record.fields.get("marketplace"),
                "knowledge_category": category,
                "training_tags": tags,
                "applicable_modules": modules,
                "trust_score": trust_score,
                "risk_flags": risk_flags,
                "risk_only_training": risk_only_training,
                "allowed_use": allowed_use,
                "execution_policy": execution_policy,
                "human_review_required": human_review_required,
                "distilled_summary": summary,
                "actionable_sop": actionable_sop,
                "created_at_utc": created_at,
                "distillation_version": DISTILLATION_VERSION,
            }
        ),
        raw_text=json.dumps(
            {
                "source_asset_id": asset_record.record_id,
                "source_url": asset_record.fields.get("source_url"),
                "summary": summary,
            },
            ensure_ascii=False,
        ),
        source="learning_sources_distillation",
        score={"priority": max(10, min(100, trust_score)), "trust": trust_score, "risk": 100 if has_gray_risk else 70 if has_compliance_risk else 10},
        director_notes=[f"Distilled public learning source as {category}."],
        confidence=trust_score / 100,
        metadata={"learning_run_date": run_date, "source_asset_id": asset_record.record_id},
    )

    knowledge_item = IntakeRecord(
        record_type="knowledge_item",
        fields=normalize_fields(
            {
                "item_key": stable_id("knowledge_", source_id, page.url, category),
                "title": f"{asset_record.fields.get('source_name') or page.title} / {category}",
                "primary_category": category,
                "categories": [category],
                "concepts": tags,
                "knowledge_score": trust_score,
                "credibility_score": trust_score,
                "risk_score": 100 if has_gray_risk else 70 if has_compliance_risk else 10,
                "risk_only_training": risk_only_training,
                "execution_policy": execution_policy,
                "summary": summary,
                "source_excerpt": compact(text, 360),
                "source_asset_id": asset_record.record_id,
            }
        ),
        raw_text=summary,
        source="learning_sources_distillation",
        score={"priority": trust_score, "trust": trust_score},
        metadata={"learning_run_date": run_date},
    )

    learning_event = IntakeRecord(
        record_type="learning_event",
        fields=normalize_fields(
            {
                "learning_event_id": stable_id("learn_evt_", distillation_id),
                "event_type": "web_case_distilled",
                "source_item_key": knowledge_item.fields["item_key"],
                "knowledge_category": category,
                "weight_delta": 0 if risk_only_training else round(trust_score / 1000, 3),
                "created_at_utc": created_at,
            }
        ),
        raw_text=summary,
        source="learning_sources_distillation",
        score={"priority": trust_score},
        metadata={"learning_run_date": run_date},
    )

    strategy_memory = IntakeRecord(
        record_type="strategy_memory",
        fields=normalize_fields(
            {
                "memory_key": f"web-learning:{source_id}:{run_date}",
                "memory_type": "web_case_learning",
                "summary": summary,
                "what_was_observed": compact(text, 500),
                "what_can_be_used": actionable_sop,
                "what_cannot_be_done": "Do not auto-execute grey tactics, IP-risk actions, account-risk actions, posting, pricing, refunds, shipping, authorization, or external contact.",
                "valid_conditions": "Use only when source is allowed, evidence is saved, risk is checked, and high-impact actions enter the approval queue.",
                "next_review_trigger": "Review again when the same concept appears in 3+ sources, a real store result confirms it, or platform rules change.",
                "source_asset_id": asset_record.record_id,
                "created_at_utc": created_at,
            }
        ),
        raw_text=summary,
        source="learning_sources_distillation",
        score={"priority": trust_score, "trust": trust_score},
        metadata={"learning_run_date": run_date},
    )

    records = [distilled, knowledge_item, learning_event, strategy_memory]
    for tag in tags[:8]:
        weight = 0 if risk_only_training else round(max(0.1, trust_score / 100), 3)
        records.append(
            IntakeRecord(
                record_type="knowledge_concept_weight",
                fields=normalize_fields(
                    {
                        "concept_key": stable_id("concept_", tag.lower()),
                        "normalized_entity": tag.lower(),
                        "entity": tag,
                        "occurrence_count": 1,
                        "concept_weight": weight,
                        "source_distillation_id": distillation_id,
                        "concept_status": "quarantined_risk_learning" if risk_only_training else "active_learning",
                    }
                ),
                raw_text=summary,
                source="learning_sources_distillation",
                score={"priority": int(weight * 100)},
                metadata={"learning_run_date": run_date},
            )
        )

    for record in records:
        append_record(root, record)
    return records


def build_learning_report(run_date: str, statuses: list[dict[str, Any]], records: list[IntakeRecord]) -> str:
    lines = [
        "# AI Ecommerce Director Learning Sources Report",
        "",
        f"Date: {run_date}",
        "",
        "## Source Status",
        "",
    ]
    if not statuses:
        lines.append("- No learning sources are configured.")
    for status in statuses:
        lines.append(f"- {status.get('source_id')}: {status.get('status')} | {status.get('title') or status.get('reason') or status.get('url') or ''}")

    lines.extend(["", "## New Learning Assets", ""])
    if not records:
        lines.append("- No new learning assets were saved in this run.")
    for record in records:
        fields = record.fields
        lines.append(f"- {fields.get('source_name') or fields.get('page_title')}: {fields.get('research_asset_type')} | priority {record.score.get('priority')}")
        lines.append(f"  Validation: {fields.get('validation_task')}")
    lines.extend(["", "## Web Case Distillation", ""])
    distilled_statuses = [status for status in statuses if status.get("distilled_records")]
    if not distilled_statuses:
        lines.append("- No new web cases were distilled in this run.")
    for status in distilled_statuses:
        risk_count = len(status.get("risk_flags") or [])
        risk_label = "risk-only" if status.get("risk_only_training") else "normal"
        lines.append(
            f"- {status.get('source_id')}: {status.get('knowledge_category')} | trust {status.get('trust_score')} | {risk_label} | risk flags {risk_count}"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_learning_report(root: Path, run_date: str, content: str) -> Path:
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{LEARNING_REPORT_PREFIX}_{run_date}.md"
    path.write_text(content, encoding="utf-8")
    return path


def write_learning_workbook(root: Path, run_date: str) -> Path | None:
    rows = build_learning_workbook_rows(root, run_date)
    if not rows:
        return None
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{LEARNING_WORKBOOK_PREFIX}_{run_date}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=LEARNING_WORKBOOK_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def build_learning_workbook_rows(root: Path, run_date: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    records = select_learning_workbook_records(root, run_date)
    if not records:
        return build_asset_workbook_rows(root)
    for record in records:
        fields = record.fields or {}
        risk_flags = fields.get("risk_flags") if isinstance(fields.get("risk_flags"), list) else []
        modules = fields.get("applicable_modules") if isinstance(fields.get("applicable_modules"), list) else []
        trust_score = int(fields.get("trust_score") or 0)
        risk_text = "无明显风险"
        if risk_flags:
            risk_terms = ", ".join(str(flag.get("term") or "") for flag in risk_flags if isinstance(flag, dict))
            risk_text = f"需隔离/复核：{risk_terms}".strip()
        rows.append(
            {
                "序号": len(rows) + 1,
                "知识分类": human_category(str(fields.get("knowledge_category") or "")),
                "问题/要点": workbook_question(fields),
                "来源": fields.get("source_name") or "",
                "来源链接": fields.get("source_url") or "",
                "可信度": trust_score,
                "答案/结论": fields.get("distilled_summary") or "",
                "可执行步骤": fields.get("actionable_sop") or "",
                "完整度": completeness_label(trust_score, risk_flags),
                "风险提示": risk_text,
                "使用边界": fields.get("allowed_use") or "",
                "负责模块": " / ".join(str(item) for item in modules),
                "下一步": workbook_next_step(fields),
                "是否需要人工确认": "是" if fields.get("human_review_required") else "否",
            }
        )
    return rows


def build_asset_workbook_rows(root: Path, limit: int = 80) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    headers = LEARNING_WORKBOOK_HEADERS
    source_records = [
        *read_records(root, "industry_research_asset"),
        *read_records(root, "knowledge_item"),
    ]
    source_records = sorted(source_records, key=lambda record: record.created_at or "", reverse=True)[:limit]
    for record in source_records:
        fields = record.fields or {}
        source_name = str(fields.get("source_name") or fields.get("provider") or fields.get("research_asset_type") or record.source or "")
        source_url = str(fields.get("url") or fields.get("source_url") or "")
        category = str(fields.get("primary_category") or fields.get("knowledge_category") or fields.get("data_lake_category") or "")
        trust_score = int(fields.get("knowledge_score") or fields.get("trust_score") or fields.get("credibility_score") or 60)
        raw_text = str(record.raw_text or "")
        content_excerpt_raw = str(fields.get("content_excerpt") or "")
        raw_summary = compact(raw_text, 280)
        content_excerpt = compact(content_excerpt_raw, 360)
        knowledge_node = compact(str(fields.get("knowledge_node") or ""), 180)
        task_text = compact(str(fields.get("task") or ""), 140)
        heading = first_heading(content_excerpt_raw or raw_text)
        if "完整正文已通过知识引擎导入" in f"{content_excerpt}\n{raw_summary}":
            continue
        conclusion = compact(str(
            fields.get("opportunity")
            or fields.get("summary")
            or fields.get("what_we_learned")
            or content_excerpt
            or raw_summary
            or knowledge_node
            or fields.get("task")
            or ""
        ), 320)
        next_action = compact(str(
            fields.get("next_action")
            or fields.get("validation_task")
            or fields.get("recommendation")
            or "归并到后台知识库，由AI生成老板版结论、词库或待确认动作"
        ), 220)
        question = compact(str(
            fields.get("user_pain_point")
            or fields.get("knowledge_node")
            or heading
            or content_excerpt
            or raw_summary
            or fields.get("keyword_cluster")
            or task_text
            or "待整理知识点"
        ), 220)
        if is_low_signal_workbook_value(question):
            question = compact(f"{source_name}：{heading or content_excerpt or raw_summary or '待整理知识点'}", 240)
        if knowledge_node and not is_low_signal_workbook_value(knowledge_node) and knowledge_node not in question:
            question = compact(f"{knowledge_node} | {question}", 260)
        modules = fields.get("affected_agents") or fields.get("categories") or fields.get("agents") or []
        if not isinstance(modules, list):
            modules = [modules]
        rows.append(
            {
                headers[0]: len(rows) + 1,
                headers[1]: human_category(category),
                headers[2]: question,
                headers[3]: source_name,
                headers[4]: source_url,
                headers[5]: trust_score,
                headers[6]: conclusion,
                headers[7]: next_action,
                headers[8]: "可参考，需结合真实店铺数据复核",
                headers[9]: "无明显风险",
                headers[10]: "后台学习资料；前台只展示AI总结后的结论",
                headers[11]: " / ".join(str(item) for item in modules if str(item)),
                headers[12]: next_action or "由AI电商运营总监归并到报告、词库或待确认动作",
                headers[13]: "否",
            }
        )
    return rows


def select_learning_workbook_records(root: Path, run_date: str, limit: int = 80) -> list[IntakeRecord]:
    records = list(read_records(root, "web_case_distillation"))
    same_day = [
        record
        for record in records
        if str((record.metadata or {}).get("learning_run_date") or "") == run_date
    ]
    if same_day:
        return same_day[:limit]

    def sort_key(record: IntakeRecord) -> str:
        fields = record.fields or {}
        metadata = record.metadata or {}
        return str(
            fields.get("created_at_utc")
            or record.created_at
            or metadata.get("learning_run_date")
            or ""
        )

    return sorted(records, key=sort_key, reverse=True)[:limit]


def latest_learning_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    paths = sorted(output_dir.glob(f"{LEARNING_REPORT_PREFIX}_*.md"), reverse=True)
    if not paths:
        return "No learning sources report yet.", None
    path = paths[0]
    return path.read_text(encoding="utf-8"), path


def distillation_text(asset_record: IntakeRecord, page: Any, source: dict[str, Any]) -> str:
    fields = asset_record.fields
    parts = [
        str(source.get("name") or ""),
        str(fields.get("knowledge_node") or ""),
        str(fields.get("keyword_cluster") or ""),
        str(fields.get("opportunity") or ""),
        str(fields.get("validation_task") or ""),
        str(page.title or ""),
        str(page.text or ""),
    ]
    return "\n".join(part for part in parts if part).strip()


def classify_learning_category(text: str, source: dict[str, Any]) -> str:
    combined = f"{source.get('research_asset_type') or ''}\n{source.get('source_type') or ''}\n{text}".lower()
    best_category = "general_ecommerce_case"
    best_score = 0
    for category, keywords in CATEGORY_RULES:
        score = sum(1 for keyword in keywords if str(keyword).lower() in combined)
        if score > best_score:
            best_category = category
            best_score = score
    return best_category


def detect_risk_flags(text: str) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    for term in GRAY_RISK_TERMS:
        if term.lower() in text.lower():
            flags.append({"term": term, "risk_type": "grey_tactic"})
    for term in COMPLIANCE_RISK_TERMS:
        if term.lower() in text.lower():
            flags.append({"term": term, "risk_type": "compliance_risk"})
    return flags


def trust_score_for_source(source: dict[str, Any]) -> int:
    source_type = str(source.get("research_asset_type") or source.get("source_type") or "public_learning_source")
    return TRUST_SCORE_BY_SOURCE_TYPE.get(source_type, TRUST_SCORE_BY_SOURCE_TYPE["public_learning_source"])


def module_targets(category: str) -> list[str]:
    modules_by_category = {
        "viral_video_case": ["Viral Content Intelligence", "Content Director", "Influencer Intelligence"],
        "money_case": ["AI Ecommerce Director", "Advertising Director", "Finance Review"],
        "product_selection_case": ["Product Intelligence", "Competitor Intelligence", "Keyword Intelligence"],
        "listing_case": ["Listing Intelligence", "Keyword Intelligence", "Review Intelligence"],
        "ads_case": ["Advertising Director", "Content Director", "Risk Intelligence"],
        "risk_case": ["Risk Intelligence", "Compliance Review", "Admin War Room"],
        "supply_chain_case": ["Supply Chain Director", "OMS Director", "Factory Dispatch"],
    }
    return modules_by_category.get(category, ["AI Ecommerce Director", "Knowledge Engine"])


def extract_training_tags(text: str, source: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    focus = source.get("focus")
    if isinstance(focus, list):
        tags.extend(str(item).strip() for item in focus if str(item).strip())
    tags.extend(re.findall(r"#([A-Za-z0-9_\-\u4e00-\u9fff]{2,40})", text))
    important_terms = [
        "TikTok Shop",
        "Amazon",
        "Etsy",
        "Shopify",
        "POD",
        "creator",
        "video",
        "hook",
        "listing",
        "review",
        "ROI",
        "ROAS",
        "GMV",
        "keyword",
        "选品",
        "爆品",
        "达人",
        "素材",
        "脚本",
        "评论",
        "侵权",
        "TRO",
    ]
    lower_text = text.lower()
    for term in important_terms:
        if term.lower() in lower_text:
            tags.append(term)
    cleaned: list[str] = []
    for tag in tags:
        normalized = re.sub(r"\s+", " ", tag).strip()
        if normalized and normalized.lower() not in {item.lower() for item in cleaned}:
            cleaned.append(normalized)
    return cleaned[:24]


def build_distillation_summary(text: str, category: str, risk_flags: list[dict[str, str]]) -> str:
    first_sentence = compact(text, 260)
    if risk_flags:
        risk_terms = ", ".join(flag["term"] for flag in risk_flags[:8])
        return f"{category}: learned from source, but risk terms were detected ({risk_terms}). Use it for recognition, screening, and owner-reviewed strategy only. Evidence: {first_sentence}"
    return f"{category}: distilled reusable ecommerce learning from a public source. Evidence: {first_sentence}"


def build_actionable_sop(category: str, risk_only_training: bool, has_compliance_risk: bool) -> str:
    if risk_only_training:
        return "Quarantine this knowledge. Use it to recognize grey-market behavior, detect competitor risk, and improve guardrails. Never auto-execute it."
    if has_compliance_risk:
        return "Use as a risk playbook reference: check IP, policy, claim wording, account health, and require owner review before any external action."
    sop_by_category = {
        "viral_video_case": "Turn the case into hook, scene, creator type, product proof, comment signal, and CTA templates; test with small content batches first.",
        "money_case": "Extract price, cost, ROI/ROAS, budget, lifecycle, and stop-loss rules; only scale after own-store metrics confirm the pattern.",
        "product_selection_case": "Map category, rank movement, price band, review pain points, supply fit, and IP risk; send top candidates to product report.",
        "listing_case": "Extract title structure, keyword cluster, image angle, review objections, and conversion claims; generate listing drafts for approval.",
        "ads_case": "Extract budget pattern, creative angle, funnel stage, CPA/ROAS trigger, and stop-loss rule; create an experiment plan, not live ads.",
        "supply_chain_case": "Extract factory, inventory, shipping, SLA, landed-cost and defect-risk lessons; send to supply chain and OMS planning.",
    }
    return sop_by_category.get(category, "Classify the lesson, attach evidence, compare with own-store data, and create an approval-only task if useful.")


def human_category(category: str) -> str:
    labels = {
        "risk_case": "风险/合规案例",
        "viral_video_case": "爆款视频/素材案例",
        "money_case": "赚钱/ROI案例",
        "product_selection_case": "选品/榜单案例",
        "listing_case": "Listing/评论案例",
        "ads_case": "广告/投流案例",
        "supply_chain_case": "供应链/履约案例",
        "general_ecommerce_case": "通用电商案例",
        "general_knowledge": "通用电商知识",
        "general_course_knowledge": "课程通用知识",
        "commerce_os": "Commerce OS体系",
        "strategy": "战略/体系经验",
        "product": "产品/选品知识",
        "product_selection": "选品/类目经验",
        "product_signal": "产品增长信号",
        "content": "内容/素材知识",
        "viral_case": "爆款内容案例",
        "viral_content": "爆款内容知识",
        "creator": "达人/联盟知识",
        "influencer": "达人/联盟知识",
        "influencer_experience": "达人/联盟经验",
        "operations": "运营/SOP知识",
        "store_ops": "店铺运营经验",
        "compliance": "风控/合规知识",
        "platform_rule": "平台规则知识",
        "platform_data": "平台数据知识",
        "knowledge_learning": "学习/蒸馏知识",
        "listing": "Listing/评论知识",
        "listing_signal": "Listing信号",
        "keyword_signal": "关键词信号",
        "ads": "广告/投流知识",
        "success_case": "成功案例",
        "failure_case": "失败案例",
        "supply_chain": "供应链知识",
    }
    return labels.get(category, category or "未分类")


def workbook_question(fields: dict[str, Any]) -> str:
    category = str(fields.get("knowledge_category") or "")
    source_name = str(fields.get("source_name") or "该资料")
    prompts = {
        "risk_case": f"{source_name} 提到的风险是什么？应该如何隔离和识别？",
        "viral_video_case": f"{source_name} 里有什么可复用的视频钩子、场景和脚本？",
        "money_case": f"{source_name} 里有哪些利润、ROI、预算或生命周期经验？",
        "product_selection_case": f"{source_name} 里有哪些选品、榜单、类目或增长信号？",
        "listing_case": f"{source_name} 里有哪些标题、主图、关键词和评论痛点经验？",
        "ads_case": f"{source_name} 里有哪些投流、素材测试和止损放量规则？",
        "supply_chain_case": f"{source_name} 里有哪些库存、工厂、履约和物流经验？",
    }
    return prompts.get(category, f"{source_name} 里有哪些可沉淀的电商经验？")


def workbook_next_step(fields: dict[str, Any]) -> str:
    category = str(fields.get("knowledge_category") or "")
    if fields.get("risk_only_training"):
        return "只进入风险库；用于识别对手打法、风控词和封店/TRO预警，不生成执行动作。"
    if fields.get("human_review_required"):
        return "进入管理员复核；通过后只能生成方案或待确认动作。"
    next_steps = {
        "viral_video_case": "拆成 hook、镜头、场景、达人类型、CTA 和可复刻脚本，再进入 TK 内容策略。",
        "money_case": "补价格、成本、ROI、周期和止损线，再进入预算/实验计划。",
        "product_selection_case": "补平台排名、评论痛点、供货和侵权风险，再进入选品报告。",
        "listing_case": "生成标题、五点、主图方向和评论异议处理草稿，等待确认。",
        "ads_case": "生成小预算测试计划、素材变量、CPA/ROAS止损线，等待确认。",
        "supply_chain_case": "同步给库存、工厂、物流和SLA检查，不直接派单。",
    }
    return next_steps.get(category, "进入策略记忆；同类信号出现 3 次以上再提高权重。")


def completeness_label(trust_score: int, risk_flags: list[Any]) -> str:
    if risk_flags:
        return "需复核"
    if trust_score >= 85:
        return "完整"
    if trust_score >= 60:
        return "部分完整"
    return "低可信，仅参考"


def stable_id(prefix: str, *parts: Any) -> str:
    payload = "|".join(str(part or "") for part in parts)
    return prefix + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def compact(text: str, limit: int) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)].rstrip() + "..."


def first_heading(text: str) -> str:
    for line in str(text or "").splitlines():
        clean = re.sub(r"^[#\-\s]+", "", line).strip()
        if clean:
            return compact(clean, 120)
    return ""


def is_low_signal_workbook_value(text: str) -> bool:
    clean = str(text or "").strip()
    if not clean:
        return True
    if re.fullmatch(r"[a-f0-9]{12,}", clean):
        return True
    if re.fullmatch(r"[a-z0-9_:-]{3,}", clean):
        return True
    return False
