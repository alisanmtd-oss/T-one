from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha1, sha256
from pathlib import Path
from typing import Any

from .storage import append_record, read_records
from .types import IntakeRecord


DEFAULT_COURSE_SOURCES = [
    Path("outputs") / "course_originals" / "五节课程原文合集_2026-06-09.md",
    Path("outputs") / "course_originals" / "体系文档原文合集_2026-06-09.md",
]

RISK_ONLY_TERMS = [
    "补单",
    "刷单",
    "刷评",
    "动销干预",
    "虚拟仓",
    "低价高邮",
    "测评单",
    "买评",
    "规避审核",
]

COMPLIANCE_RISK_TERMS = [
    "仿牌",
    "侵权",
    "TRO",
    "二审",
    "封店",
    "专利",
    "商标",
    "版权",
    "投诉",
]

CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("product_selection", ["选品", "爆品", "类目", "小类目", "新品", "榜单", "商品卡", "BSR", "New Release"]),
    ("platform_data", ["TikTok Shop", "FastMoss", "Kalodata", "Amazon", "Etsy", "Walmart", "SHEIN", "Temu"]),
    ("viral_content", ["视频", "素材", "脚本", "钩子", "运镜", "剪辑", "字幕", "场景", "达人视频"]),
    ("influencer", ["达人", "粉丝", "均播", "报价", "寄样", "出视频", "联盟", "BD"]),
    ("listing", ["Listing", "标题", "主图", "卖点", "详情图", "价格", "标签", "转化"]),
    ("ads", ["广告", "投流", "GMV Max", "ROAS", "ROI", "CPA", "CTR", "CVR", "预算"]),
    ("store_ops", ["店铺", "订单", "售后", "退货", "退款", "发货", "折扣", "活动", "直播"]),
    ("risk_compliance", ["风险", "侵权", "专利", "商标", "版权", "违规", "封店", "二审", "投诉", "禁词"]),
    ("supply_chain", ["供应链", "工厂", "库存", "成本", "克重", "物流", "备货", "发货"]),
    ("commerce_os", ["Global Commerce OS", "Commerce Brain", "Data Lake", "Learning Engine", "Knowledge Graph", "Agent Registry", "无人化"]),
]

CONCEPT_RULES: list[tuple[str, list[str]]] = [
    ("TikTok Shop", ["TikTok Shop", "TK", "tiktok"]),
    ("FastMoss", ["FastMoss", "fastmoss"]),
    ("Kalodata", ["Kalodata", "kalodata"]),
    ("Amazon", ["Amazon", "亚马逊", "BSR"]),
    ("Viral Video", ["爆款视频", "视频", "脚本", "钩子", "运镜"]),
    ("Creator / Influencer", ["达人", "红人", "creator", "influencer", "均播"]),
    ("Product Card", ["商品卡", "店铺入口", "买家端"]),
    ("Category Depth", ["小类目", "二级类目", "三级类目", "四级类目", "全品类"]),
    ("Risk Word Bank", ["侵权", "禁词", "专利", "商标", "版权", "TRO"]),
    ("Store Operations", ["订单", "退货", "退款", "发货", "折扣", "活动"]),
    ("Ads Control", ["投流", "广告", "ROAS", "GMV Max", "预算"]),
    ("Learning Engine", ["学习引擎", "Learning Engine", "训练", "复盘"]),
]


@dataclass(slots=True)
class CourseCorpusImportResult:
    run_date: str
    source_documents: list[IntakeRecord]
    source_chunks: list[IntakeRecord]
    knowledge_items: list[IntakeRecord]
    evidence_claims: list[IntakeRecord]
    learning_events: list[IntakeRecord]
    knowledge_nodes: list[IntakeRecord]
    knowledge_edges: list[IntakeRecord]
    concept_weights: list[IntakeRecord]
    signals: list[IntakeRecord]
    hypotheses: list[IntakeRecord]
    plans: list[IntakeRecord]
    tasks: list[IntakeRecord]
    strategy_memories: list[IntakeRecord]
    training_samples_path: Path
    report_path: Path
    manifest_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "source_document_count": len(self.source_documents),
            "source_chunk_count": len(self.source_chunks),
            "knowledge_item_count": len(self.knowledge_items),
            "evidence_claim_count": len(self.evidence_claims),
            "learning_event_count": len(self.learning_events),
            "knowledge_node_count": len(self.knowledge_nodes),
            "knowledge_edge_count": len(self.knowledge_edges),
            "concept_weight_count": len(self.concept_weights),
            "signal_count": len(self.signals),
            "hypothesis_count": len(self.hypotheses),
            "plan_count": len(self.plans),
            "task_count": len(self.tasks),
            "strategy_memory_count": len(self.strategy_memories),
            "training_samples_path": str(self.training_samples_path),
            "report_path": str(self.report_path),
            "manifest_path": str(self.manifest_path),
        }


def run_course_corpus_import(
    root: Path,
    *,
    run_date: str | None = None,
    source_paths: list[Path] | None = None,
    min_training_samples: int = 100,
) -> CourseCorpusImportResult:
    root = root.resolve()
    day = run_date or date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    paths = source_paths or [root / item for item in DEFAULT_COURSE_SOURCES]
    resolved_paths = [path if path.is_absolute() else root / path for path in paths]

    source_documents: list[IntakeRecord] = []
    chunks: list[IntakeRecord] = []
    items: list[IntakeRecord] = []
    claims: list[IntakeRecord] = []
    events: list[IntakeRecord] = []
    nodes_by_key: dict[str, IntakeRecord] = {}
    edge_records: list[IntakeRecord] = []
    signals: list[IntakeRecord] = []
    hypotheses: list[IntakeRecord] = []
    plans: list[IntakeRecord] = []
    tasks: list[IntakeRecord] = []
    memories: list[IntakeRecord] = []
    concept_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    risk_items: list[IntakeRecord] = []

    for path in resolved_paths:
        text = read_text(path)
        digest = file_sha256(path)
        source_kind = "course_original" if "课程" in path.name else "strategy_original"
        source_id = stable_id("src_", path.name, digest)
        source_doc = IntakeRecord(
            record_type="source_document",
            source="course_corpus_import",
            raw_text=text,
            fields={
                "source_id": source_id,
                "source_name": path.name,
                "source_path": str(path),
                "file_name": path.name,
                "checksum": digest,
                "content_sha256": digest,
                "source_kind": source_kind,
                "imported_at_utc": now,
                "language": "zh-CN",
                "storage_policy": "raw_original_preserved",
                "derivative_policy": "summaries_and_tasks_saved_separately",
            },
            score={"priority": 90 if source_kind == "course_original" else 94, "layer": "source_document"},
            director_notes=["Original corpus preserved before any summary, classification, or strategy derivation."],
            confidence=0.95,
        )
        append_record(root, source_doc)
        source_documents.append(source_doc)

        for chunk_index, chunk in enumerate(split_source_chunks(text), start=1):
            chunk_id = stable_id("chk_", source_id, chunk_index, chunk[:500])
            title = infer_title(chunk, chunk_index)
            chunk_record = IntakeRecord(
                record_type="source_chunk",
                source="course_corpus_import",
                raw_text=chunk,
                fields={
                    "source_chunk_id": chunk_id,
                    "source_id": source_id,
                    "source_name": path.name,
                    "source_kind": source_kind,
                    "chunk_index": chunk_index,
                    "title": title,
                    "text_sha1": sha1(chunk.encode("utf-8")).hexdigest(),
                    "char_count": len(chunk),
                    "imported_at_utc": now,
                },
                score={"priority": 78, "layer": "source_chunk"},
                director_notes=["Chunk keeps original wording and becomes the smallest evidence unit."],
                confidence=0.9,
            )
            append_record(root, chunk_record)
            chunks.append(chunk_record)

            categories = classify_chunk(chunk)
            concepts = extract_concepts(chunk)
            for category in categories:
                category_counter[category] += 1
            for concept in concepts:
                concept_counter[concept] += 1
            risk_only = contains_risk_only_terms(chunk)
            quality = score_chunk(chunk, source_kind, categories, concepts, risk_only=risk_only)
            item_key = stable_id("kitem_", chunk_id, ",".join(categories), ",".join(concepts))
            item = IntakeRecord(
                record_type="knowledge_item",
                source="course_corpus_import",
                raw_text=chunk,
                fields={
                    "item_key": item_key,
                    "source_document_id": source_id,
                    "source_chunk_id": chunk_id,
                    "source_kind": source_kind,
                    "title": title,
                    "primary_category": categories[0],
                    "categories": categories,
                    "concepts": concepts,
                    "entities": concepts,
                    "knowledge_score": quality["knowledge_score"],
                    "credibility_score": quality["credibility_score"],
                    "evidence_score": quality["evidence_score"],
                    "risk_score": quality["risk_score"],
                    "knowledge_score_version": "course-corpus-v1",
                    "quality_signals": quality["quality_signals"],
                    "risk_only_training": risk_only,
                    "execution_policy": "risk_recognition_only" if risk_only else "strategy_training_allowed",
                    "summary": summarize_chunk(chunk),
                    "source_excerpt": compact(chunk, 900),
                    "imported_at_utc": now,
                },
                score={"priority": quality["knowledge_score"], "training_weight": quality["training_weight"]},
                director_notes=knowledge_director_notes(categories, risk_only),
                review_status="risk_review" if risk_only else "approved_for_training",
                confidence=round(quality["knowledge_score"] / 100, 3),
            )
            append_record(root, item)
            items.append(item)
            if risk_only:
                risk_items.append(item)

            claim = build_evidence_claim(item, chunk_record, quality, now)
            append_record(root, claim)
            claims.append(claim)

            event = build_learning_event(item, now)
            append_record(root, event)
            events.append(event)

            for concept in concepts:
                node_record = nodes_by_key.get(concept.lower())
                if node_record is None:
                    node_record = build_knowledge_node(concept, now)
                    append_record(root, node_record)
                    nodes_by_key[concept.lower()] = node_record

            edge_records.extend(build_edges_for_item(root, item, concepts, categories, now))

            if should_generate_signal(item):
                signal = build_signal_event(item, now)
                append_record(root, signal)
                signals.append(signal)
                hypothesis = build_hypothesis(signal, item, now)
                append_record(root, hypothesis)
                hypotheses.append(hypothesis)
                plan = build_execution_plan(hypothesis, item, now)
                append_record(root, plan)
                plans.append(plan)
                task = build_task_queue(plan, item, now)
                append_record(root, task)
                tasks.append(task)

    concept_weights = build_concept_weights(root, concept_counter, category_counter, now)
    memories.extend(build_strategy_memories(root, items, risk_items, category_counter, concept_counter, now, day))

    training_samples = build_training_samples(items, min_training_samples=min_training_samples)
    outputs = root / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    sample_path = outputs / f"course_import_training_samples_{day}.jsonl"
    with sample_path.open("w", encoding="utf-8") as handle:
        for sample in training_samples:
            handle.write(json.dumps(sample, ensure_ascii=False) + "\n")

    report = build_import_report(
        day=day,
        source_documents=source_documents,
        chunks=chunks,
        items=items,
        claims=claims,
        events=events,
        nodes=list(nodes_by_key.values()),
        edges=edge_records,
        concept_weights=concept_weights,
        signals=signals,
        hypotheses=hypotheses,
        plans=plans,
        tasks=tasks,
        memories=memories,
        samples=training_samples,
        risk_items=risk_items,
    )
    report_path = outputs / f"COURSE_IMPORT_TRAINING_REPORT_{day}.md"
    report_path.write_text(report, encoding="utf-8")
    manifest_path = outputs / f"course_import_training_manifest_{day}.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_date": day,
                "generated_at_utc": now,
                "source_paths": [str(path) for path in resolved_paths],
                "counts": {
                    "source_documents": len(source_documents),
                    "source_chunks": len(chunks),
                    "knowledge_items": len(items),
                    "evidence_claims": len(claims),
                    "learning_events": len(events),
                    "knowledge_nodes": len(nodes_by_key),
                    "knowledge_edges": len(edge_records),
                    "concept_weights": len(concept_weights),
                    "signals": len(signals),
                    "hypotheses": len(hypotheses),
                    "plans": len(plans),
                    "tasks": len(tasks),
                    "strategy_memories": len(memories),
                    "training_samples": len(training_samples),
                    "risk_only_items": len(risk_items),
                },
                "report_path": str(report_path),
                "training_samples_path": str(sample_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return CourseCorpusImportResult(
        run_date=day,
        source_documents=source_documents,
        source_chunks=chunks,
        knowledge_items=items,
        evidence_claims=claims,
        learning_events=events,
        knowledge_nodes=list(nodes_by_key.values()),
        knowledge_edges=edge_records,
        concept_weights=concept_weights,
        signals=signals,
        hypotheses=hypotheses,
        plans=plans,
        tasks=tasks,
        strategy_memories=memories,
        training_samples_path=sample_path,
        report_path=report_path,
        manifest_path=manifest_path,
    )


def read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Course source file not found: {path}")
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def split_source_chunks(text: str, *, target_chars: int = 1300, max_chars: int = 2100) -> list[str]:
    clean = text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    clean = re.sub(r"\n{4,}", "\n\n\n", clean).strip()
    blocks = [block.strip() for block in re.split(r"\n(?=#{1,3}\s)|\n\s*\n", clean) if block.strip()]
    chunks: list[str] = []
    current = ""
    for block in blocks:
        if len(block) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(split_long_block(block, target_chars=target_chars))
            continue
        if current and len(current) + len(block) > target_chars:
            chunks.append(current.strip())
            current = block
        else:
            current = f"{current}\n\n{block}".strip()
    if current:
        chunks.append(current.strip())
    return chunks


def split_long_block(block: str, *, target_chars: int) -> list[str]:
    sentences = [item.strip() for item in re.split(r"(?<=[。！？!?；;])\s*", block) if item.strip()]
    if len(sentences) <= 1:
        return [block[index : index + target_chars].strip() for index in range(0, len(block), target_chars)]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > target_chars:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current}{sentence}".strip()
    if current:
        chunks.append(current.strip())
    return chunks


def infer_title(chunk: str, index: int) -> str:
    for line in chunk.splitlines():
        line = line.strip(" #\t-")
        if 4 <= len(line) <= 90:
            return line
    return f"chunk-{index:04d}"


def classify_chunk(text: str) -> list[str]:
    lower = text.lower()
    categories = [
        category
        for category, words in CATEGORY_RULES
        if any(word.lower() in lower for word in words)
    ]
    return categories or ["general_course_knowledge"]


def extract_concepts(text: str) -> list[str]:
    lower = text.lower()
    concepts = [concept for concept, words in CONCEPT_RULES if any(word.lower() in lower for word in words)]
    for match in re.findall(r"\b[A-Z][A-Za-z0-9&' /+-]{2,38}\b", text):
        candidate = match.strip(" .,:;()[]")
        if len(candidate) >= 3 and candidate not in concepts and len(candidate.split()) <= 5:
            concepts.append(candidate)
    return list(dict.fromkeys(concepts))[:18]


def contains_risk_only_terms(text: str) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in RISK_ONLY_TERMS)


def score_chunk(
    text: str,
    source_kind: str,
    categories: list[str],
    concepts: list[str],
    *,
    risk_only: bool,
) -> dict[str, Any]:
    credibility = 82 if source_kind == "course_original" else 88
    evidence = 46
    signals: list[str] = []
    if re.search(r"\b\d+(\.\d+)?%|\b\d+\s*(单|条|个|天|小时|美金|美元)|\$\d+|ROI|ROAS|CPA|CTR|CVR", text, re.I):
        evidence += 16
        signals.append("numeric_or_threshold_detail")
    if any(word in text for word in ["案例", "实操", "后台", "截图", "数据", "榜单", "店铺"]):
        evidence += 14
        signals.append("operational_case_detail")
    if any(category in categories for category in ["viral_content", "product_selection", "ads", "store_ops"]):
        evidence += 8
        signals.append("operator_relevant")
    if risk_only:
        evidence += 10
        signals.append("risk_abuse_recognition")
    concept_bonus = min(10, len(concepts) * 2)
    risk_penalty = 0 if risk_only else 0
    knowledge_score = max(25, min(98, round(credibility * 0.48 + evidence * 0.37 + concept_bonus - risk_penalty)))
    has_compliance_risk = any(term.lower() in text.lower() for term in COMPLIANCE_RISK_TERMS)
    risk_score = 80 if risk_only else 45 if has_compliance_risk else 25 if "risk_compliance" in categories else 12
    return {
        "knowledge_score": knowledge_score,
        "credibility_score": credibility,
        "evidence_score": min(100, evidence),
        "risk_score": risk_score,
        "quality_signals": signals or ["text_only_needs_video_or_platform_evidence"],
        "training_weight": "risk-only" if risk_only else "high" if knowledge_score >= 75 else "medium",
    }


def summarize_chunk(text: str) -> str:
    lines = [line.strip(" -#\t") for line in text.splitlines() if len(line.strip()) >= 6]
    if not lines:
        return compact(text, 160)
    summary = "；".join(lines[:2])
    return compact(summary, 260)


def knowledge_director_notes(categories: list[str], risk_only: bool) -> list[str]:
    notes = [f"课程语料分类：{', '.join(categories)}。"]
    if risk_only:
        notes.append("命中高风险/灰产词，只进入风险识别与风控训练，不进入执行 SOP。")
    if "viral_content" in categories:
        notes.append("视频内容知识需要后续补画面节点：钩子、运镜、剪辑、字幕、CTA、评论区。")
    if "product_selection" in categories:
        notes.append("选品知识需要后续用 TikTok / FastMoss / Kalodata / Amazon 真实数据交叉验证。")
    return notes


def build_evidence_claim(item: IntakeRecord, chunk: IntakeRecord, quality: dict[str, Any], now: str) -> IntakeRecord:
    claim_text = str(item.fields.get("summary") or "")
    claim_id = stable_id("claim_", item.fields.get("item_key"), chunk.fields.get("source_chunk_id"))
    return IntakeRecord(
        record_type="evidence_claim",
        source="course_corpus_import",
        raw_text=item.raw_text,
        fields={
            "evidence_claim_id": claim_id,
            "claim_text": claim_text,
            "claim_type": item.fields.get("primary_category"),
            "source_id": chunk.fields.get("source_id"),
            "source_chunk_id": chunk.fields.get("source_chunk_id"),
            "source_document_id": item.fields.get("source_document_id"),
            "extractor_name": "course_corpus_import",
            "extractor_version": "course-corpus-v1",
            "confidence": round(float(quality["knowledge_score"]) / 100, 3),
            "risk_only_training": item.fields.get("risk_only_training"),
            "created_at_utc": now,
        },
        score={"priority": quality["knowledge_score"], "layer": "evidence_claim"},
        director_notes=["Evidence claim created from exact source chunk."],
        confidence=round(float(quality["knowledge_score"]) / 100, 3),
    )


def build_learning_event(item: IntakeRecord, now: str) -> IntakeRecord:
    event_id = stable_id("lev_", item.fields.get("item_key"), item.fields.get("primary_category"))
    return IntakeRecord(
        record_type="learning_event",
        source="course_corpus_import",
        raw_text=item.raw_text,
        fields={
            "learning_event_id": event_id,
            "event_type": "course_knowledge_imported",
            "source_item_key": item.fields.get("item_key"),
            "source_chunk_id": item.fields.get("source_chunk_id"),
            "primary_category": item.fields.get("primary_category"),
            "categories": item.fields.get("categories"),
            "concepts": item.fields.get("concepts"),
            "weight_delta": 0.12 if not item.fields.get("risk_only_training") else 0.04,
            "risk_only_training": item.fields.get("risk_only_training"),
            "created_at_utc": now,
        },
        score={"priority": item.score.get("priority", 60), "layer": "learning_event"},
        director_notes=["Learning event generated so repeated concepts can raise future weights."],
        confidence=item.confidence,
    )


def build_knowledge_node(concept: str, now: str) -> IntakeRecord:
    node_id = stable_id("node_", concept.lower())
    return IntakeRecord(
        record_type="knowledge_node",
        source="course_corpus_import",
        raw_text=concept,
        fields={
            "node_id": node_id,
            "normalized_name": concept.lower(),
            "display_name": concept,
            "node_type": infer_node_type(concept),
            "source": "course_corpus_import",
            "created_at_utc": now,
        },
        score={"priority": 72, "layer": "knowledge_node"},
        director_notes=["Knowledge graph node created from imported course corpus."],
        confidence=0.8,
    )


def build_edges_for_item(
    root: Path,
    item: IntakeRecord,
    concepts: list[str],
    categories: list[str],
    now: str,
) -> list[IntakeRecord]:
    records: list[IntakeRecord] = []
    primary = concepts[0] if concepts else str(item.fields.get("primary_category"))
    for concept in concepts[1:8]:
        edge_id = stable_id("edge_", primary.lower(), "co_occurs_with", concept.lower())
        record = IntakeRecord(
            record_type="knowledge_edge",
            source="course_corpus_import",
            raw_text=json.dumps({"source": primary, "target": concept}, ensure_ascii=False),
            fields={
                "edge_key": edge_id,
                "source_item_key": item.fields.get("item_key"),
                "source_entity": primary,
                "target_entity": concept,
                "source_node_id": stable_id("node_", primary.lower()),
                "target_node_id": stable_id("node_", concept.lower()),
                "edge_type": "co_occurs_with",
                "relation": "co_occurs_with",
                "categories": categories,
                "weight": item.score.get("priority", 60),
                "created_at_utc": now,
            },
            score={"priority": item.score.get("priority", 60), "layer": "knowledge_edge"},
            director_notes=["Course concept co-occurrence edge."],
            confidence=item.confidence,
        )
        append_record(root, record)
        records.append(record)
    return records


def should_generate_signal(item: IntakeRecord) -> bool:
    categories = set(item.fields.get("categories") or [])
    return bool(categories & {"product_selection", "viral_content", "influencer", "ads", "store_ops", "risk_compliance", "commerce_os"})


def build_signal_event(item: IntakeRecord, now: str) -> IntakeRecord:
    item_key = str(item.fields.get("item_key"))
    category = str(item.fields.get("primary_category"))
    signal_id = stable_id("sig_", item_key, category)
    value = float(item.fields.get("knowledge_score") or item.score.get("priority") or 60)
    risk = float(item.fields.get("risk_score") or 0)
    return IntakeRecord(
        record_type="signal_event",
        source="course_corpus_import.signal_engine",
        raw_text=item.raw_text,
        fields={
            "signal_id": signal_id,
            "engine_type": "course_signal_engine",
            "entity_type": "course_knowledge_item",
            "entity_id": item_key,
            "entity_label": item.fields.get("summary"),
            "platform": "Global Commerce OS",
            "country": "global",
            "metric_name": f"{category}_training_signal",
            "baseline_value": 50,
            "current_value": value,
            "delta": round(value - 50, 2),
            "velocity": round((value - 50) / 50, 4),
            "risk_score": risk,
            "confidence": item.confidence,
            "source_record_id": item.record_id,
            "timestamp": now,
        },
        score={"priority": int(min(100, value)), "layer": "signal_event"},
        director_notes=["Signal generated from course corpus; it must be validated with platform/store evidence before execution."],
        confidence=item.confidence,
    )


def build_hypothesis(signal: IntakeRecord, item: IntakeRecord, now: str) -> IntakeRecord:
    category = str(item.fields.get("primary_category"))
    hypothesis_id = stable_id("hyp_", signal.fields.get("signal_id"), category)
    risk = float(item.fields.get("risk_score") or 0) / 100
    confidence = float(item.confidence)
    expected_profit = expected_profit_for_category(category)
    priority = round(expected_profit * confidence * 0.62 * (1 - min(risk, 0.85)) / 100, 2)
    return IntakeRecord(
        record_type="hypothesis",
        source="course_corpus_import.hypothesis_generator",
        raw_text=item.raw_text,
        fields={
            "hypothesis_id": hypothesis_id,
            "signal_id": signal.fields.get("signal_id"),
            "opportunity_type": category,
            "hypothesis_text": hypothesis_text_for_item(item),
            "related_entities": item.fields.get("concepts"),
            "expected_profit": expected_profit,
            "risk_score": round(risk, 3),
            "confidence_score": confidence,
            "priority_score": priority,
            "status": "risk_learning_only" if item.fields.get("risk_only_training") else "needs_platform_validation",
            "created_at_utc": now,
        },
        score={"priority": int(min(100, max(20, priority))), "layer": "hypothesis"},
        director_notes=["Hypothesis is a training/validation candidate, not an approval to operate stores."],
        confidence=confidence,
    )


def build_execution_plan(hypothesis: IntakeRecord, item: IntakeRecord, now: str) -> IntakeRecord:
    plan_id = stable_id("plan_", hypothesis.fields.get("hypothesis_id"))
    risk_only = bool(item.fields.get("risk_only_training"))
    next_steps = risk_plan_steps(item) if risk_only else validation_plan_steps(item)
    return IntakeRecord(
        record_type="execution_plan",
        source="course_corpus_import.planner",
        raw_text=json.dumps(next_steps, ensure_ascii=False),
        fields={
            "plan_id": plan_id,
            "hypothesis_id": hypothesis.fields.get("hypothesis_id"),
            "plan_type": "risk_recognition_training" if risk_only else "evidence_validation_training",
            "automation_level": "L0-L2",
            "requires_human_confirmation": True,
            "allowed_execution": "read_only_and_draft_only",
            "blocked_actions": [
                "publish_listing",
                "change_price",
                "launch_ads",
                "refund",
                "ship_order",
                "bypass_captcha",
                "black_box_scrape",
            ],
            "next_steps": next_steps,
            "created_at_utc": now,
        },
        score={"priority": hypothesis.score.get("priority", 50), "layer": "execution_plan"},
        director_notes=["Plan generated as a validation workflow. External actions stay approval-gated."],
        confidence=hypothesis.confidence,
    )


def build_task_queue(plan: IntakeRecord, item: IntakeRecord, now: str) -> IntakeRecord:
    task_id = stable_id("task_", plan.fields.get("plan_id"), item.fields.get("item_key"))
    category = str(item.fields.get("primary_category"))
    return IntakeRecord(
        record_type="task_queue",
        source="course_corpus_import.task_queue",
        raw_text=plan.raw_text,
        fields={
            "task_queue_id": task_id,
            "task_type": "course_validation_task",
            "target_agent_id": target_agent_for_category(category),
            "task_title": f"验证课程知识：{compact(str(item.fields.get('summary')), 80)}",
            "source_plan_id": plan.fields.get("plan_id"),
            "source_item_key": item.fields.get("item_key"),
            "status": "queued_for_training",
            "priority_score": item.score.get("priority", 50),
            "expected_output": "提交证据链：平台链接/截图/视频节点/达人或商品数据/风险判断/简短结论。",
            "created_at_utc": now,
        },
        score={"priority": item.score.get("priority", 50), "layer": "task_queue"},
        director_notes=["Queued for AI employees to validate; do not execute store-changing actions."],
        confidence=item.confidence,
    )


def build_concept_weights(
    root: Path,
    concept_counter: Counter[str],
    category_counter: Counter[str],
    now: str,
) -> list[IntakeRecord]:
    records: list[IntakeRecord] = []
    total = max(1, sum(concept_counter.values()))
    for concept, count in concept_counter.most_common(80):
        weight = min(100, round(45 + (count / total) * 260 + min(18, count * 2)))
        concept_key = stable_id("cw_", concept.lower())
        record = IntakeRecord(
            record_type="knowledge_concept_weight",
            source="course_corpus_import.learning_engine",
            raw_text=concept,
            fields={
                "concept_key": concept_key,
                "entity": concept,
                "normalized_entity": concept.lower(),
                "node_type": infer_node_type(concept),
                "occurrence_count": count,
                "concept_weight": weight,
                "concept_status": "core_memory" if weight >= 80 else "watchlist" if weight >= 62 else "weak_signal",
                "top_categories": [{"category": key, "count": value} for key, value in category_counter.most_common(8)],
                "next_action": "Raise learning and validation priority if this concept appears again in platform data, videos, reviews, or own-store reports.",
                "updated_at": now,
                "learning_engine_version": "course-corpus-v1",
            },
            score={"priority": weight, "training_weight": "high" if weight >= 70 else "medium"},
            director_notes=["Concept weight updated from course corpus frequency."],
            confidence=round(weight / 100, 3),
        )
        append_record(root, record)
        records.append(record)
    return records


def build_strategy_memories(
    root: Path,
    items: list[IntakeRecord],
    risk_items: list[IntakeRecord],
    category_counter: Counter[str],
    concept_counter: Counter[str],
    now: str,
    day: str,
) -> list[IntakeRecord]:
    memories: list[IntakeRecord] = []
    top_categories = [{"category": key, "count": value} for key, value in category_counter.most_common(10)]
    top_concepts = [{"concept": key, "count": value} for key, value in concept_counter.most_common(12)]
    payloads = [
        {
            "memory_key": f"course-corpus-import:{day}:core",
            "memory_type": "course_corpus_import",
            "summary": "五节课程和体系文档已作为第一批正式训练语料入湖；后续所有 AI 员工必须用证据链而不是散乱聊天记忆学习。",
            "top_categories": top_categories,
            "top_concepts": top_concepts,
            "next_action": "让 Product / Viral Content / Influencer / Listing / Risk 员工按任务队列补真实平台证据。",
        },
        {
            "memory_key": f"course-corpus-import:{day}:risk-only",
            "memory_type": "course_risk_guardrail",
            "summary": "课程中命中的高风险/灰产词只进入风险识别库，不允许转成自动补单、刷单、规避审核或侵权执行 SOP。",
            "risk_item_count": len(risk_items),
            "risk_terms": RISK_ONLY_TERMS,
            "next_action": "风控员工把这些词加入违禁词/风险词/人工复审规则，运营员工不得执行。",
        },
    ]
    for payload in payloads:
        record = IntakeRecord(
            record_type="strategy_memory",
            source="course_corpus_import",
            raw_text=json.dumps(payload, ensure_ascii=False),
            fields={**payload, "created_at_utc": now},
            score={"priority": 88, "training_weight": "highest"},
            director_notes=["Long-term strategy memory created from course corpus import."],
            confidence=0.9,
        )
        append_record(root, record)
        memories.append(record)
    return memories


def build_training_samples(items: list[IntakeRecord], *, min_training_samples: int) -> list[dict[str, Any]]:
    sorted_items = sorted(items, key=lambda record: int(record.score.get("priority") or 0), reverse=True)
    course_items = [item for item in sorted_items if item.fields.get("source_kind") == "course_original"]
    strategy_items = [item for item in sorted_items if item.fields.get("source_kind") == "strategy_original"]
    pool = (course_items[: max(20, min_training_samples // 2)] + strategy_items[: max(30, min_training_samples // 2)] + sorted_items)
    samples: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in pool:
        key = str(item.fields.get("item_key"))
        if key in seen:
            continue
        seen.add(key)
        categories = item.fields.get("categories") or []
        risk_only = bool(item.fields.get("risk_only_training"))
        samples.append(
            {
                "sample_id": stable_id("sample_", key),
                "source_item_key": key,
                "source_chunk_id": item.fields.get("source_chunk_id"),
                "source_kind": item.fields.get("source_kind"),
                "task_type": "risk_classification" if risk_only else "operator_reasoning",
                "instruction": sample_instruction(categories, risk_only),
                "input": compact(item.raw_text, 1200),
                "expected_output": sample_expected_output(item),
                "labels": {
                    "categories": categories,
                    "concepts": item.fields.get("concepts") or [],
                    "risk_only_training": risk_only,
                    "execution_policy": item.fields.get("execution_policy"),
                },
            }
        )
        if len(samples) >= min_training_samples:
            break
    return samples


def sample_instruction(categories: list[str], risk_only: bool) -> str:
    if risk_only:
        return "请识别这段课程内容中的风险/灰产/侵权点，只输出风控规则、禁用动作和人工复审要求，不能写成执行 SOP。"
    if "viral_content" in categories:
        return "请把这段课程内容拆成视频脚本训练样本：钩子、场景、运镜、剪辑、CTA、需要补的平台证据。"
    if "product_selection" in categories:
        return "请把这段课程内容拆成选品判断样本：平台、类目、指标、证据缺口、下一步验证动作。"
    if "ads" in categories:
        return "请把这段课程内容拆成投流/预算判断样本：保本线、冷启动、放量、止损、需要人工确认的动作。"
    return "请把这段课程内容转成 AI 电商运营总监可学习的结构化知识，并标出证据缺口。"


def sample_expected_output(item: IntakeRecord) -> dict[str, Any]:
    return {
        "summary": item.fields.get("summary"),
        "primary_category": item.fields.get("primary_category"),
        "concepts": item.fields.get("concepts"),
        "knowledge_score": item.fields.get("knowledge_score"),
        "risk_score": item.fields.get("risk_score"),
        "execution_policy": item.fields.get("execution_policy"),
        "must_collect_next": next_evidence_for_item(item),
    }


def build_import_report(**payload: Any) -> str:
    day = payload["day"]
    source_documents: list[IntakeRecord] = payload["source_documents"]
    chunks: list[IntakeRecord] = payload["chunks"]
    items: list[IntakeRecord] = payload["items"]
    claims: list[IntakeRecord] = payload["claims"]
    events: list[IntakeRecord] = payload["events"]
    nodes: list[IntakeRecord] = payload["nodes"]
    edges: list[IntakeRecord] = payload["edges"]
    concept_weights: list[IntakeRecord] = payload["concept_weights"]
    signals: list[IntakeRecord] = payload["signals"]
    hypotheses: list[IntakeRecord] = payload["hypotheses"]
    plans: list[IntakeRecord] = payload["plans"]
    tasks: list[IntakeRecord] = payload["tasks"]
    memories: list[IntakeRecord] = payload["memories"]
    samples: list[dict[str, Any]] = payload["samples"]
    risk_items: list[IntakeRecord] = payload["risk_items"]
    category_counts = Counter()
    for item in items:
        for category in item.fields.get("categories", []):
            category_counts[str(category)] += 1
    top_concepts = sorted(concept_weights, key=lambda record: int(record.fields.get("concept_weight") or 0), reverse=True)[:15]
    top_items = sorted(items, key=lambda record: int(record.score.get("priority") or 0), reverse=True)[:12]
    lines = [
        "# COURSE IMPORT TRAINING REPORT",
        "",
        f"日期：{day}",
        "",
        "## 结论",
        "",
        "- 两份核心语料已经按“原文保存 -> 分块 -> 知识点 -> 证据声明 -> 学习事件 -> 信号 -> 假设 -> 计划 -> 任务 -> 长期记忆”的链路处理。",
        "- 高风险词只进入风险识别和人工复审，不会变成自动执行动作。",
        "- 这次是文字/逐字稿级学习；视频画面节点仍需等桌面/Chrome 控制恢复后补充。",
        "",
        "## 入湖数量",
        "",
        f"- SourceDocument：{len(source_documents)}",
        f"- SourceChunk：{len(chunks)}",
        f"- KnowledgeItem：{len(items)}",
        f"- EvidenceClaim：{len(claims)}",
        f"- LearningEvent：{len(events)}",
        f"- KnowledgeNode：{len(nodes)}",
        f"- KnowledgeEdge：{len(edges)}",
        f"- ConceptWeight：{len(concept_weights)}",
        f"- Signal：{len(signals)}",
        f"- Hypothesis：{len(hypotheses)}",
        f"- Plan：{len(plans)}",
        f"- TaskQueue：{len(tasks)}",
        f"- StrategyMemory：{len(memories)}",
        f"- TrainingSample：{len(samples)}",
        "",
        "## 原始文件",
        "",
    ]
    for doc in source_documents:
        lines.append(f"- {doc.fields.get('file_name')} | SHA256 {doc.fields.get('checksum')} | {doc.fields.get('source_path')}")
    lines.extend(["", "## 分类分布", ""])
    for category, count in category_counts.most_common():
        lines.append(f"- {category}: {count}")
    lines.extend(["", "## 核心概念权重", ""])
    for record in top_concepts:
        lines.append(
            f"- {record.fields.get('entity')}：权重 {record.fields.get('concept_weight')}，出现 {record.fields.get('occurrence_count')} 次，状态 {record.fields.get('concept_status')}"
        )
    lines.extend(["", "## 高价值知识样本", ""])
    for item in top_items:
        lines.append(
            f"- [{item.fields.get('primary_category')}] {item.fields.get('summary')} | 分数 {item.fields.get('knowledge_score')} | 策略 {item.fields.get('execution_policy')}"
        )
    lines.extend(["", "## 风险隔离", ""])
    lines.append(f"- 命中风险隔离知识点：{len(risk_items)}")
    for item in risk_items[:12]:
        lines.append(f"- {item.fields.get('summary')} | 只用于 {item.fields.get('execution_policy')}")
    lines.extend(["", "## 生成给 AI 员工的任务", ""])
    for task in tasks[:18]:
        lines.append(f"- {task.fields.get('target_agent_id')}：{task.fields.get('task_title')}")
    lines.extend(
        [
            "",
            "## 下一步必须补的证据",
            "",
            "- 逐节课打开视频，按逐字稿节点补老师实操页面、榜单、后台数据、案例截图。",
            "- TikTok 优先补商品页、视频页、达人页、评论区和商品卡证据；Amazon 只能做补充验证。",
            "- 对每个课程案例补销售数据、生命周期、广告数据、素材脚本、达人素材分析。",
            "- 生成老师作业版继续保持“纯课程”，内部训练版才加入 AI 体系和员工任务。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def validation_plan_steps(item: IntakeRecord) -> list[str]:
    categories = set(item.fields.get("categories") or [])
    steps = ["保留原文证据块，不修改老师原话。"]
    if "product_selection" in categories:
        steps.extend(["去 TikTok Shop / FastMoss / Kalodata 找同品真实榜单。", "补商品链接、排名、销量/GMV、价格和评论痛点。"])
    if "viral_content" in categories:
        steps.extend(["只看 TikTok / FastMoss / Kalodata 视频证据。", "补 0-2 秒钩子、运镜、场景、字幕、音乐、CTA、评论区购买信号。"])
    if "influencer" in categories:
        steps.extend(["补达人昵称、粉丝、均播、互动率、报价、联系方式和合作记录。"])
    if "ads" in categories:
        steps.extend(["补保本 ROI、预算、素材冷启动、止损和放量条件。"])
    if "store_ops" in categories:
        steps.extend(["补店铺订单、退款、退货、折扣、活动、售后和发货数据。"])
    if len(steps) == 1:
        steps.append("补平台链接、截图、指标和 AI 员工复盘结论。")
    return steps


def risk_plan_steps(item: IntakeRecord) -> list[str]:
    return [
        "抽取命中的风险词、灰产词、侵权词或平台违规动作。",
        "写入风控词库和人工复审规则。",
        "训练 AI 员工识别这些词，但禁止自动执行、绕过审核或形成操作 SOP。",
        "如涉及真实店铺动作，必须进入老板确认队列。",
    ]


def next_evidence_for_item(item: IntakeRecord) -> list[str]:
    if item.fields.get("risk_only_training"):
        return ["风险词命中证据", "平台规则来源", "人工复审结论"]
    return validation_plan_steps(item)[1:5]


def hypothesis_text_for_item(item: IntakeRecord) -> str:
    category = item.fields.get("primary_category")
    summary = item.fields.get("summary")
    if item.fields.get("risk_only_training"):
        return f"如果课程内容命中风险词，则必须转为风控识别规则，而不是执行 SOP：{summary}"
    if category == "viral_content":
        return f"如果课程中的视频打法被真实 TikTok 爆款验证，则可沉淀为脚本模板：{summary}"
    if category == "product_selection":
        return f"如果课程选品判断能在 TK/选品平台找到真实增长证据，则可进入小额测品：{summary}"
    return f"这条课程知识需要用真实平台数据验证后再进入运营策略：{summary}"


def expected_profit_for_category(category: str) -> float:
    return {
        "product_selection": 1200,
        "viral_content": 1500,
        "influencer": 1000,
        "ads": 900,
        "store_ops": 700,
        "commerce_os": 600,
        "risk_compliance": 350,
    }.get(category, 450)


def target_agent_for_category(category: str) -> str:
    return {
        "product_selection": "AI Product & Competitor Analyst",
        "viral_content": "AI Viral Content Intelligence",
        "influencer": "AI Influencer Hunter",
        "listing": "AI Listing Builder",
        "ads": "AI Advertising Director",
        "store_ops": "AI OMS Director",
        "risk_compliance": "AI Risk Director",
        "commerce_os": "AI Chief of Staff",
    }.get(category, "AI Data Review Analyst")


def infer_node_type(concept: str) -> str:
    lowered = concept.lower()
    if any(word in lowered for word in ["tiktok", "amazon", "fastmoss", "kalodata", "etsy", "walmart", "shein"]):
        return "platform"
    if any(word in lowered for word in ["video", "hook", "viral", "素材", "脚本"]):
        return "video_pattern"
    if any(word in lowered for word in ["creator", "influencer", "达人"]):
        return "creator"
    if any(word in lowered for word in ["risk", "侵权", "禁词", "patent", "trademark"]):
        return "risk"
    if any(word in lowered for word in ["learning", "engine", "agent", "data lake", "commerce"]):
        return "system_layer"
    return "concept"


def compact(text: str, length: int) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    return clean if len(clean) <= length else clean[: length - 3] + "..."


def stable_id(prefix: str, *parts: Any) -> str:
    value = "|".join(str(part) for part in parts)
    return prefix + sha1(value.encode("utf-8")).hexdigest()[:18]
