from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any

from .storage import append_record, read_records
from .types import IntakeRecord


DISTILLATION_VERSION = "commerce-knowledge-distillation-v1"


RECORD_TYPES_TO_DISTILL = [
    "knowledge_item",
    "source_chunk",
    "strategy_memory",
    "learning_event",
    "industry_research_asset",
    "money_case",
    "platform_ranking_signal",
    "viral_content_signal",
    "video_breakdown",
    "video_script",
    "influencer_cooperation",
    "review_insight",
    "store_metric_snapshot",
    "store_health_event",
    "tk_rule_update",
    "compliance_term",
    "ip_image_risk",
    "feedback_ticket",
    "evidence_claim",
]


BUSINESS_TAXONOMY: list[tuple[str, list[str]]] = [
    ("amazon.listing_offer", ["ASIN", "SKU", "variation", "Featured Offer", "Buying Options", "listing"]),
    ("amazon.fulfillment", ["Amazon FBM", "Amazon FBA", "ship-from", "delivery promise", "Deliver by"]),
    ("amazon.advertising", ["Sponsored Products", "Amazon Ads", "ACOS", "TACOS", "advertised products"]),
    ("amazon.api_authorization", ["SP-API", "Selling Partner API", "LWA", "role", "403"]),
    ("product.selection", ["选品", "爆品", "榜单", "类目", "小类目", "新品", "商品卡", "BSR", "new release"]),
    ("product.lifecycle", ["生命周期", "起盘", "测品", "放量", "衰退", "备货", "清仓", "拉长"]),
    ("viral.video_script", ["视频", "素材", "脚本", "钩子", "运镜", "剪辑", "字幕", "高光帧", "CTA"]),
    ("viral.creator_content", ["达人视频", "种草", "收割", "官方号", "渠道号", "发视频", "音乐"]),
    ("influencer.crm", ["达人", "均播", "粉丝", "报价", "寄样", "出视频", "合作", "联系方式"]),
    ("listing.optimization", ["Listing", "标题", "主图", "详情图", "卖点", "五点", "标签", "转化"]),
    ("ads.launch_control", ["投流", "广告", "GMV Max", "ROAS", "ROI", "CPA", "CTR", "CVR", "预算", "冷启动"]),
    ("store.operations", ["店铺", "订单", "退货", "退款", "售后", "发货", "折扣", "活动", "直播"]),
    ("supply_chain.inventory", ["供应链", "工厂", "库存", "成本", "克重", "物流", "仓库", "补货"]),
    ("finance.tax_accounting", ["财务", "结算", "利润", "报表", "税", "成本", "回款", "现金流"]),
    ("ai.company_system", ["Global Commerce OS", "Commerce Brain", "Data Lake", "知识图谱", "Learning Engine", "Agent", "智能体"]),
]


GRAY_MARKET_TERMS: dict[str, str] = {
    "补单": "fake_order",
    "刷单": "fake_order",
    "刷评": "fake_review",
    "买评": "fake_review",
    "测评单": "fake_review",
    "虚拟仓": "misleading_fulfillment",
    "低价高邮": "misleading_pricing",
    "规避审核": "review_evasion",
    "绕过审核": "review_evasion",
    "绕审核": "review_evasion",
    "动销干预": "manipulated_sales",
    "刷流量": "fake_traffic",
}


IP_TRO_TERMS: dict[str, str] = {
    "侵权": "ip_infringement",
    "仿牌": "counterfeit_or_brand_confusion",
    "TRO": "tro_freeze_risk",
    "tro": "tro_freeze_risk",
    "商标": "trademark",
    "版权": "copyright",
    "专利": "patent",
    "品牌词": "brand_term",
    "封店": "account_enforcement",
    "二审": "account_review",
    "申诉": "appeal",
}


LUCK_TERMS = ["运气", "碰运气", "偶然", "突然爆", "玄学", "不知道为什么", "凑巧", "误打误撞"]


SOURCE_TIER_BY_RECORD_TYPE: dict[str, tuple[str, int]] = {
    "money_case": ("own_real_case", 98),
    "store_metric_snapshot": ("own_store_truth", 96),
    "order_item": ("own_store_truth", 96),
    "return_rma": ("own_store_truth", 94),
    "refund_record": ("own_store_truth", 94),
    "platform_ranking_signal": ("platform_observed", 86),
    "viral_content_signal": ("platform_observed", 84),
    "video_breakdown": ("platform_observed", 84),
    "video_script": ("derived_creative", 78),
    "influencer_cooperation": ("partner_operational_data", 90),
    "review_insight": ("customer_voice", 88),
    "tk_rule_update": ("platform_rule", 90),
    "compliance_term": ("risk_rule", 82),
    "ip_image_risk": ("risk_rule", 84),
    "knowledge_item": ("course_or_strategy_memory", 74),
    "source_chunk": ("raw_course_or_strategy", 72),
    "strategy_memory": ("internal_strategy_memory", 70),
    "industry_research_asset": ("research_asset", 68),
    "feedback_ticket": ("operator_feedback", 82),
}


@dataclass(slots=True)
class KnowledgeDistillationResult:
    run_date: str
    source_records_scanned: int
    distillation_items: list[IntakeRecord]
    quarantine_records: list[IntakeRecord]
    word_bank_entries: list[IntakeRecord]
    strategy_memories: list[IntakeRecord]
    report_path: Path
    manifest_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "source_records_scanned": self.source_records_scanned,
            "distillation_item_count": len(self.distillation_items),
            "quarantine_record_count": len(self.quarantine_records),
            "word_bank_entry_count": len(self.word_bank_entries),
            "strategy_memory_count": len(self.strategy_memories),
            "report_path": str(self.report_path),
            "manifest_path": str(self.manifest_path),
        }


def run_knowledge_distillation(
    root: Path,
    *,
    run_date: str | None = None,
    max_records: int = 2500,
) -> KnowledgeDistillationResult:
    root = root.resolve()
    day = run_date or date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    source_records = collect_source_records(root, max_records=max_records)
    distillation_items: list[IntakeRecord] = []
    quarantine_records: list[IntakeRecord] = []
    word_entries_by_key: dict[str, IntakeRecord] = {}
    seen_item_keys: set[str] = set()

    for record in source_records:
        text = record_text(record)
        if len(text.strip()) < 8:
            continue
        classification = classify_distillation_text(text, record)
        item_key = stable_id("kdst_", record.record_type, record.record_id, text[:600], classification["primary_taxonomy"])
        if item_key in seen_item_keys:
            continue
        seen_item_keys.add(item_key)

        item = IntakeRecord(
            record_type="knowledge_distillation_item",
            source="knowledge_distillation",
            raw_text=text,
            fields={
                "distillation_item_id": item_key,
                "source_record_type": record.record_type,
                "source_record_id": record.record_id,
                "source_record_source": record.source,
                "taxonomy_path": classification["taxonomy_path"],
                "primary_taxonomy": classification["primary_taxonomy"],
                "case_nature": classification["case_nature"],
                "evidence_tier": classification["evidence_tier"],
                "knowledge_score": classification["knowledge_score"],
                "risk_score": classification["risk_score"],
                "risk_class": classification["risk_class"],
                "automation_policy": classification["automation_policy"],
                "allowed_uses": classification["allowed_uses"],
                "blocked_uses": classification["blocked_uses"],
                "requires_owner_review": classification["requires_owner_review"],
                "luck_possible": classification["luck_possible"],
                "matched_terms": classification["matched_terms"],
                "distilled_summary": summarize_for_distillation(text),
                "dedupe_key": stable_id("ddp_", normalize_for_dedupe(text)[:900]),
                "distillation_version": DISTILLATION_VERSION,
                "created_at_utc": now,
            },
            score={
                "priority": classification["knowledge_score"],
                "risk_score": classification["risk_score"],
                "training_weight": classification["training_weight"],
            },
            director_notes=director_notes_for_classification(classification),
            review_status=classification["review_status"],
            confidence=classification["confidence"],
        )
        append_record(root, item)
        distillation_items.append(item)

        if classification["risk_class"] in {"gray_market", "ip_tro_account_risk"}:
            quarantine = build_quarantine_record(item, classification, now)
            append_record(root, quarantine)
            quarantine_records.append(quarantine)

        for entry in build_word_bank_entries(item, classification, now):
            key = str(entry.fields.get("word_bank_key"))
            if key not in word_entries_by_key:
                append_record(root, entry)
                word_entries_by_key[key] = entry

    strategy_memories = build_distillation_strategy_memories(root, day, now, distillation_items, quarantine_records)
    report_path = output_dir / f"KNOWLEDGE_DISTILLATION_REPORT_{day}.md"
    report_path.write_text(
        build_distillation_report(day, source_records, distillation_items, quarantine_records, list(word_entries_by_key.values())),
        encoding="utf-8",
    )
    manifest_path = output_dir / f"knowledge_distillation_manifest_{day}.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_date": day,
                "generated_at_utc": now,
                "distillation_version": DISTILLATION_VERSION,
                "source_records_scanned": len(source_records),
                "distillation_items": len(distillation_items),
                "quarantine_records": len(quarantine_records),
                "word_bank_entries": len(word_entries_by_key),
                "strategy_memories": len(strategy_memories),
                "report_path": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return KnowledgeDistillationResult(
        run_date=day,
        source_records_scanned=len(source_records),
        distillation_items=distillation_items,
        quarantine_records=quarantine_records,
        word_bank_entries=list(word_entries_by_key.values()),
        strategy_memories=strategy_memories,
        report_path=report_path,
        manifest_path=manifest_path,
    )


def collect_source_records(root: Path, *, max_records: int) -> list[IntakeRecord]:
    records: list[IntakeRecord] = []
    for record_type in RECORD_TYPES_TO_DISTILL:
        records.extend(read_records(root, record_type))
    records.sort(key=lambda record: record.created_at, reverse=True)
    return records[:max_records]


def record_text(record: IntakeRecord) -> str:
    parts = [record.raw_text or ""]
    for key in ["summary", "title", "claim_text", "memory_key", "hypothesis_text", "task_title", "notes"]:
        value = record.fields.get(key)
        if isinstance(value, str):
            parts.append(value)
    return "\n".join(part for part in parts if part).strip()


def classify_distillation_text(text: str, record: IntakeRecord) -> dict[str, Any]:
    lowered = text.lower()
    taxonomy = [
        taxonomy_key
        for taxonomy_key, terms in BUSINESS_TAXONOMY
        if any(term.lower() in lowered for term in terms)
    ] or ["general.operating_knowledge"]

    gray_matches = {term: label for term, label in GRAY_MARKET_TERMS.items() if term.lower() in lowered}
    ip_matches = {term: label for term, label in IP_TRO_TERMS.items() if risk_term_matches(term, lowered)}
    luck_possible = any(term.lower() in lowered for term in LUCK_TERMS)
    source_tier, base_score = SOURCE_TIER_BY_RECORD_TYPE.get(record.record_type, ("unverified_memory", 58))
    if record.record_type == "evidence_claim":
        evidence_state = str(record.fields.get("evidence_state") or "unverified_claim")
        source_tier, base_score = {
            "live_store_fact": ("verified_live_store_claim", 98),
            "official_policy": ("verified_official_claim", 94),
            "buyer_page_observation": ("current_public_observation", 90),
            "historical_store_fact": ("time_bounded_store_claim", 82),
            "third_party_observation": ("third_party_observation", 68),
            "inference": ("inference", 55),
            "draft": ("draft_not_live", 45),
            "unverified_claim": ("unverified_claim", 40),
        }.get(evidence_state, ("unverified_claim", 40))

    evidence_bonus = 0
    if re.search(r"\b\d+(\.\d+)?%|\b\d+\s*(单|条|个|天|小时|美金|美元)|\$\d+|ROI|ROAS|CPA|CTR|CVR", text, re.I):
        evidence_bonus += 10
    if any(word in text for word in ["真实", "案例", "实操", "后台", "截图", "数据", "链接", "榜单", "店铺"]):
        evidence_bonus += 8
    if luck_possible:
        evidence_bonus -= 14

    risk_class = "normal"
    automation_policy = "strategy_training_allowed"
    review_status = "approved_for_training"
    allowed_uses = ["train_strategy", "generate_report", "create_validation_task"]
    blocked_uses = ["none"]
    requires_owner_review = False
    training_weight = "high"

    if gray_matches:
        risk_class = "gray_market"
        automation_policy = "risk_intelligence_only_no_execution"
        review_status = "quarantined_gray_market"
        allowed_uses = [
            "recognize_abuse_pattern",
            "detect_competitor_or_account_risk",
            "build_warning_terms",
            "prepare_manual_risk_review",
        ]
        blocked_uses = [
            "write_or_execute_fake_order_sop",
            "write_or_execute_fake_review_sop",
            "evade_platform_review",
            "mislead_buyer_or_platform",
            "auto_apply_to_store",
        ]
        requires_owner_review = True
        training_weight = "risk-only"
    elif ip_matches:
        risk_class = "ip_tro_account_risk"
        automation_policy = "executive_war_room_only"
        review_status = "high_risk_manual_review"
        allowed_uses = [
            "risk_awareness",
            "ip_screening",
            "account_health_defense",
            "appeal_or_takedown_planning",
            "owner_level_scenario_review",
        ]
        blocked_uses = [
            "auto_publish_confirmed_ip",
            "auto_sync_high_risk_channel",
            "copy_brand_logo_or_artwork",
            "bypass_platform_policy",
        ]
        requires_owner_review = True
        training_weight = "risk-controlled"

    case_nature = infer_case_nature(text, record, luck_possible, risk_class)
    risk_score = 92 if risk_class == "gray_market" else 76 if risk_class == "ip_tro_account_risk" else 42 if ip_matches else 18
    if luck_possible:
        risk_score = min(100, risk_score + 12)
    knowledge_score = max(20, min(98, base_score + evidence_bonus - (18 if risk_class == "gray_market" else 0)))

    return {
        "taxonomy_path": taxonomy,
        "primary_taxonomy": taxonomy[0],
        "case_nature": case_nature,
        "evidence_tier": source_tier,
        "knowledge_score": knowledge_score,
        "risk_score": risk_score,
        "risk_class": risk_class,
        "automation_policy": automation_policy,
        "allowed_uses": allowed_uses,
        "blocked_uses": blocked_uses,
        "requires_owner_review": requires_owner_review,
        "luck_possible": luck_possible,
        "matched_terms": {
            "gray_market": gray_matches,
            "ip_tro_account_risk": ip_matches,
            "luck": [term for term in LUCK_TERMS if term.lower() in lowered],
        },
        "review_status": review_status,
        "training_weight": training_weight,
        "confidence": round(max(0.35, min(0.98, knowledge_score / 100)), 3),
    }


def risk_term_matches(term: str, lowered_text: str) -> bool:
    normalized = term.lower()
    if normalized == "tro":
        return re.search(r"(?<![a-z0-9])tro(?![a-z0-9])", lowered_text, re.I) is not None
    return normalized in lowered_text


def infer_case_nature(text: str, record: IntakeRecord, luck_possible: bool, risk_class: str) -> str:
    if risk_class == "gray_market":
        return "abuse_pattern_quarantined"
    if risk_class == "ip_tro_account_risk":
        return "risk_control_case"
    if luck_possible:
        return "luck_possible_needs_validation"
    if record.record_type in {"money_case", "store_metric_snapshot", "influencer_cooperation"}:
        return "real_operational_case"
    if any(word in text for word in ["失败", "亏损", "没出单", "退货", "投诉"]):
        return "failure_case"
    if any(word in text for word in ["赚", "ROI", "ROAS", "爆", "增长", "出单"]):
        return "success_pattern_candidate"
    if record.record_type in {"platform_ranking_signal", "viral_content_signal", "review_insight"}:
        return "platform_signal"
    return "general_playbook"


def build_quarantine_record(item: IntakeRecord, classification: dict[str, Any], now: str) -> IntakeRecord:
    quarantine_id = stable_id("qrn_", item.fields.get("distillation_item_id"), classification["risk_class"])
    return IntakeRecord(
        record_type="risk_intelligence_quarantine",
        source="knowledge_distillation",
        raw_text=item.raw_text,
        fields={
            "quarantine_id": quarantine_id,
            "source_distillation_item_id": item.fields.get("distillation_item_id"),
            "risk_class": classification["risk_class"],
            "automation_policy": classification["automation_policy"],
            "matched_terms": classification["matched_terms"],
            "allowed_uses": classification["allowed_uses"],
            "blocked_uses": classification["blocked_uses"],
            "requires_owner_review": True,
            "review_queue": "owner_risk_war_room" if classification["risk_class"] == "ip_tro_account_risk" else "abuse_pattern_quarantine",
            "created_at_utc": now,
        },
        score={"priority": classification["risk_score"], "risk_score": classification["risk_score"]},
        director_notes=[
            "Risk knowledge is preserved for recognition, defense and executive review only.",
            "Do not convert this record into an execution SOP or autonomous store action.",
        ],
        review_status=classification["review_status"],
        confidence=classification["confidence"],
    )


def build_word_bank_entries(item: IntakeRecord, classification: dict[str, Any], now: str) -> list[IntakeRecord]:
    entries: list[IntakeRecord] = []
    matched = classification["matched_terms"]
    for term, subtype in matched.get("gray_market", {}).items():
        entries.append(word_bank_entry(term, "gray_market_term", subtype, item, classification, now))
    for term, subtype in matched.get("ip_tro_account_risk", {}).items():
        term_type = "ip_risk_term" if subtype in {"ip_infringement", "trademark", "copyright", "patent", "brand_term"} else "account_risk_term"
        entries.append(word_bank_entry(term, term_type, subtype, item, classification, now))
    for concept in extract_keyword_candidates(item.raw_text):
        entries.append(word_bank_entry(concept, "commerce_keyword_candidate", "needs_platform_validation", item, classification, now))
    return entries


def word_bank_entry(
    term: str,
    term_type: str,
    subtype: str,
    item: IntakeRecord,
    classification: dict[str, Any],
    now: str,
) -> IntakeRecord:
    key = stable_id("wbe_", term.lower(), term_type, subtype)
    return IntakeRecord(
        record_type="word_bank_entry",
        source="knowledge_distillation",
        raw_text=term,
        fields={
            "word_bank_key": key,
            "term": term,
            "term_type": term_type,
            "subtype": subtype,
            "source_distillation_item_id": item.fields.get("distillation_item_id"),
            "primary_taxonomy": classification["primary_taxonomy"],
            "automation_policy": classification["automation_policy"],
            "risk_class": classification["risk_class"],
            "created_at_utc": now,
        },
        score={
            "priority": 95 if term_type in {"gray_market_term", "ip_risk_term", "account_risk_term"} else 58,
            "risk_score": classification["risk_score"],
        },
        director_notes=["Word bank entry generated from distilled knowledge."],
        review_status="risk_review" if term_type != "commerce_keyword_candidate" else "needs_platform_validation",
        confidence=classification["confidence"],
    )


def build_distillation_strategy_memories(
    root: Path,
    day: str,
    now: str,
    items: list[IntakeRecord],
    quarantines: list[IntakeRecord],
) -> list[IntakeRecord]:
    taxonomy_counter = Counter(str(item.fields.get("primary_taxonomy")) for item in items)
    risk_counter = Counter(str(item.fields.get("risk_class")) for item in items)
    payloads = [
        {
            "memory_key": f"knowledge-distillation:{day}:taxonomy",
            "memory_type": "knowledge_distillation",
            "summary": "旧数据已重新蒸馏为精细分类知识库：合规打法进入训练，疑似运气进入验证，风险打法进入隔离。",
            "top_taxonomy": [{"taxonomy": key, "count": value} for key, value in taxonomy_counter.most_common(12)],
            "risk_classes": dict(risk_counter),
            "next_action": "新案例先归类、去重、评分，再决定进入训练、验证、复盘或风险隔离。",
        },
        {
            "memory_key": f"knowledge-distillation:{day}:risk-boundary",
            "memory_type": "risk_knowledge_boundary",
            "summary": "灰产动作只用于识别和防守；TRO/侵权/封店属于风控兵法库，只能老板级人工复审，不得自动执行。",
            "quarantine_count": len(quarantines),
            "blocked_actions": [
                "补单",
                "刷单",
                "买评",
                "虚拟仓误导",
                "规避审核",
                "自动发布确认侵权商品",
            ],
            "next_action": "Risk Director 每天复盘隔离库，更新风险词、侵权词、平台规则和申诉/止损预案。",
        },
    ]
    memories: list[IntakeRecord] = []
    for payload in payloads:
        record = IntakeRecord(
            record_type="strategy_memory",
            source="knowledge_distillation",
            raw_text=json.dumps(payload, ensure_ascii=False),
            fields={**payload, "created_at_utc": now},
            score={"priority": 92, "training_weight": "highest"},
            director_notes=["Distilled long-term memory with explicit safe-use boundaries."],
            review_status="approved",
            confidence=0.92,
        )
        append_record(root, record)
        memories.append(record)
    return memories


def build_distillation_report(
    day: str,
    source_records: list[IntakeRecord],
    items: list[IntakeRecord],
    quarantines: list[IntakeRecord],
    word_entries: list[IntakeRecord],
) -> str:
    taxonomy_counter = Counter(str(item.fields.get("primary_taxonomy")) for item in items)
    nature_counter = Counter(str(item.fields.get("case_nature")) for item in items)
    risk_counter = Counter(str(item.fields.get("risk_class")) for item in items)
    top_items = sorted(items, key=lambda record: int(record.score.get("priority") or 0), reverse=True)[:20]
    risk_items = [item for item in items if item.fields.get("risk_class") != "normal"][:20]
    luck_items = [item for item in items if item.fields.get("luck_possible")][:12]
    lines = [
        "# KNOWLEDGE DISTILLATION REPORT",
        "",
        f"日期：{day}",
        "",
        "## 老板摘要",
        "",
        f"- 扫描旧记录：{len(source_records)} 条。",
        f"- 生成蒸馏知识：{len(items)} 条。",
        f"- 进入风险隔离：{len(quarantines)} 条。",
        f"- 更新词库：{len(word_entries)} 条。",
        "- 原则：合规打法进入训练；疑似运气进入验证；灰产进入隔离；TRO/侵权/封店进入老板级风控情报。",
        "",
        "## 分类总览",
        "",
    ]
    for taxonomy, count in taxonomy_counter.most_common():
        lines.append(f"- {taxonomy}: {count}")
    lines.extend(["", "## 案例性质", ""])
    for nature, count in nature_counter.most_common():
        lines.append(f"- {nature}: {count}")
    lines.extend(["", "## 风险分层", ""])
    for risk, count in risk_counter.most_common():
        lines.append(f"- {risk}: {count}")
    lines.extend(["", "## 高价值可训练知识", ""])
    for item in top_items:
        if item.fields.get("risk_class") != "normal":
            continue
        lines.append(
            f"- [{item.fields.get('primary_taxonomy')}] {item.fields.get('distilled_summary')} | "
            f"证据层 {item.fields.get('evidence_tier')} | 分数 {item.fields.get('knowledge_score')} | "
            f"策略 {item.fields.get('automation_policy')}"
        )
    lines.extend(["", "## 风险隔离和兵法库", ""])
    if not risk_items:
        lines.append("- 暂无。")
    for item in risk_items:
        lines.append(
            f"- [{item.fields.get('risk_class')}] {item.fields.get('distilled_summary')} | "
            f"策略 {item.fields.get('automation_policy')} | 禁止：{', '.join(item.fields.get('blocked_uses') or [])}"
        )
    lines.extend(["", "## 疑似运气/不可直接复制", ""])
    if not luck_items:
        lines.append("- 暂无。")
    for item in luck_items:
        lines.append(f"- {item.fields.get('distilled_summary')} | 必须补真实平台/店铺数据后再学习。")
    lines.extend(["", "## 词库更新", ""])
    for entry in word_entries[:60]:
        lines.append(f"- {entry.fields.get('term')} | {entry.fields.get('term_type')} | {entry.fields.get('subtype')}")
    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- 补单、刷单、买评、虚拟仓、规避审核：只做识别、防守和风险预警，不生成执行教程，不自动应用到店铺。",
            "- 侵权、TRO、封店：保留为风控知识和对手情报，可用于筛查、申诉、止损、授权判断和老板级复盘；不能自动发布确认侵权内容。",
            "- 疑似靠运气的案例：先进入验证队列，必须补销售、视频、达人、评论、广告或店铺数据。",
            "- 真实赚钱/失败案例：优先进入 Success DB / Failure DB，提取可复制条件和不可复制条件。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def summarize_for_distillation(text: str) -> str:
    lines = [line.strip(" -#\t") for line in text.splitlines() if len(line.strip()) >= 5]
    if not lines:
        return compact(text, 180)
    return compact("；".join(lines[:3]), 280)


def director_notes_for_classification(classification: dict[str, Any]) -> list[str]:
    notes = [
        f"蒸馏分类：{classification['primary_taxonomy']}；案例性质：{classification['case_nature']}。",
        f"自动化策略：{classification['automation_policy']}。",
    ]
    if classification["risk_class"] == "gray_market":
        notes.append("灰产知识只用于识别、防守和人工复审，不进入执行 SOP。")
    if classification["risk_class"] == "ip_tro_account_risk":
        notes.append("TRO/侵权/封店知识进入老板级风控情报，不允许自动发布或自动同步高风险渠道。")
    if classification["luck_possible"]:
        notes.append("疑似运气因素，必须用平台/店铺数据验证后才可提高权重。")
    return notes


def extract_keyword_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for match in re.findall(r"\b[A-Za-z][A-Za-z0-9&' /+-]{3,42}\b", text):
        candidate = " ".join(match.strip(" .,:;()[]").split())
        if 2 <= len(candidate.split()) <= 5 and not candidate.lower().startswith(("http", "roi", "roas")):
            candidates.append(candidate)
    for match in re.findall(r"[\u4e00-\u9fff]{2,8}(?:词|类目|达人|视频|脚本|主图|选品|风控|侵权|标题|标签)", text):
        candidates.append(match)
    return list(dict.fromkeys(candidates))[:10]


def normalize_for_dedupe(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def compact(text: str, length: int) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    return clean if len(clean) <= length else clean[: length - 3] + "..."


def stable_id(prefix: str, *parts: Any) -> str:
    value = "|".join(str(part) for part in parts)
    return prefix + sha1(value.encode("utf-8")).hexdigest()[:18]
