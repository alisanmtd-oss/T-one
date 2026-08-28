from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any

from .commerce_schema import COMMERCE_KNOWLEDGE_GRAPH_SCHEMA
from .storage import append_record, read_records
from .types import IntakeRecord


KNOWLEDGE_CATEGORIES: list[tuple[str, list[str]]] = [
    ("platform_rule", ["平台规则", "规则", "二审", "封店", "账号健康", "gmv max", "商品卡", "policy", "appeal"]),
    ("influencer_experience", ["达人", "粉丝", "均播", "报价", "寄样", "出视频", "出单", "roi", "creator", "influencer"]),
    ("viral_case", ["爆款视频", "视频", "脚本", "钩子", "高光帧", "场景", "运镜", "剪辑", "viral", "hook"]),
    ("success_case", ["赚钱", "赚了", "爆单", "roi", "利润", "成功案例", "出单", "top1", "top 1"]),
    ("failure_case", ["失败", "亏损", "亏了", "拉黑", "不发视频", "失败案例", "踩坑", "封了"]),
    ("risk_case", ["侵权", "tro", "专利", "商标", "版权", "仿牌", "违禁", "投诉", "risk", "patent"]),
    ("supply_chain_case", ["供应链", "工厂", "库存", "克重", "成本", "发货", "生产", "物流", "sla"]),
    ("product_signal", ["选品", "产品", "品类", "sku", "生命周期", "新品榜", "bsr", "new release"]),
    ("keyword_signal", ["关键词", "长尾词", "seo", "标签", "identity word", "keyword"]),
    ("listing_signal", ["listing", "标题", "主图", "卖点", "五点", "价格", "转化率", "图片"]),
    ("store_ops", ["订单", "退货", "退款", "广告", "投流", "财务", "roas", "店铺", "直播", "折扣"]),
    ("strategy", ["global commerce os", "commerce brain", "data lake", "learning engine", "knowledge graph", "agent framework", "ai collaboration center"]),
]

SOURCE_TRUST_SCORES: dict[str, int] = {
    "top_seller": 95,
    "top1_seller": 95,
    "own_store_data": 94,
    "real_money_case": 92,
    "official_platform": 90,
    "creator_cooperation": 84,
    "competitor_page": 78,
    "selection_platform": 76,
    "external_ai_review": 72,
    "web_ai_response": 72,
    "course": 70,
    "wechat_chat": 58,
    "forum": 45,
    "forum_bluff": 20,
    "unknown": 45,
}

ENTITY_LINKS: dict[str, list[tuple[str, str]]] = {
    "dog dad": [("United States", "market"), ("Father's Day", "holiday"), ("pet creators", "creator_type"), ("T-shirt", "product_family"), ("identity niche", "audience")],
    "blue collar": [("United States", "market"), ("Father's Day", "holiday"), ("workwear creators", "creator_type"), ("T-shirt", "product_family"), ("identity niche", "audience")],
    "fishing": [("outdoor creators", "creator_type"), ("Father's Day", "holiday"), ("gift buyer", "audience"), ("T-shirt", "product_family")],
    "christian": [("faith community", "audience"), ("United States", "market"), ("gift buyer", "audience"), ("T-shirt", "product_family")],
    "pod": [("factory flow", "operation"), ("designer", "role"), ("blank product", "product_data"), ("private customization", "risk_policy")],
    "tiktok shop": [("buyer-side shop", "data_source"), ("viral video", "content"), ("creator", "growth_channel"), ("product card", "conversion_path")],
    "amazon": [("BSR", "ranking"), ("New Releases", "ranking"), ("PPC", "ads"), ("reviews", "pain_point_source")],
    "data lake": [("Product DB", "database"), ("Video DB", "database"), ("Influencer DB", "database"), ("Keyword DB", "database"), ("Review DB", "database")],
    "commerce brain": [("Knowledge Base", "system_layer"), ("Learning Engine", "system_layer"), ("Agent Framework", "system_layer")],
    "commerce data schema": [("Product", "data_schema"), ("Creator", "data_schema"), ("Video", "data_schema"), ("Keyword", "data_schema"), ("Listing", "data_schema"), ("Store", "data_schema"), ("Order", "data_schema"), ("Supplier", "data_schema")],
    "learning engine": [("Knowledge Graph", "system_layer"), ("Knowledge Score", "system_layer"), ("Concept Weight", "system_layer"), ("Strategy Memory", "system_layer")],
    "knowledge graph": [("Product", "node_type"), ("Creator", "node_type"), ("Video", "node_type"), ("Keyword", "node_type"), ("Listing", "node_type")],
    "agent registry": [("Agent Responsibility", "governance"), ("Agent Permission", "governance"), ("Agent Version", "governance"), ("Automation Level", "governance")],
}

ENTITY_PATTERNS: list[tuple[str, str]] = [
    ("Dog Dad", "dog dad"),
    ("Blue Collar", "blue collar"),
    ("Fishing", "fishing"),
    ("Christian", "christian"),
    ("Father's Day", "father's day"),
    ("T-shirt", "t-shirt"),
    ("Washed Tee", "washed tee"),
    ("POD", "pod"),
    ("TikTok Shop", "tiktok shop"),
    ("Amazon", "amazon"),
    ("FastMoss", "fastmoss"),
    ("Kalodata", "kalodata"),
    ("Data Lake", "data lake"),
    ("Commerce Brain", "commerce brain"),
    ("Commerce Data Schema", "commerce data schema"),
    ("Data Schema", "commerce data schema"),
    ("Product Schema", "product schema"),
    ("Creator Schema", "creator schema"),
    ("Video Schema", "video schema"),
    ("Listing Schema", "listing schema"),
    ("Knowledge Score", "knowledge score"),
    ("Knowledge Graph", "knowledge graph"),
    ("Learning Engine", "learning engine"),
    ("Agent Registry", "agent registry"),
    ("AI Collaboration Center", "ai collaboration center"),
]


@dataclass(slots=True)
class KnowledgeImportResult:
    import_record: IntakeRecord
    knowledge_items: list[IntakeRecord]
    knowledge_edges: list[IntakeRecord]
    concept_weights: list[IntakeRecord]
    learning_memory: IntakeRecord

    def to_dict(self) -> dict[str, Any]:
        return {
            "import_record": self.import_record.to_dict(),
            "knowledge_items": [record.to_dict() for record in self.knowledge_items],
            "knowledge_edges": [record.to_dict() for record in self.knowledge_edges],
            "concept_weights": [record.to_dict() for record in self.concept_weights],
            "learning_memory": self.learning_memory.to_dict(),
            "knowledge_item_count": len(self.knowledge_items),
            "knowledge_edge_count": len(self.knowledge_edges),
            "concept_weight_count": len(self.concept_weights),
        }


def import_conversation_knowledge(
    root: Path,
    text: str,
    *,
    source_type: str = "unknown",
    source_name: str = "",
    provider: str = "",
    task: str = "",
    operator_notes: str = "",
) -> KnowledgeImportResult:
    clean_text = str(text or "").strip()
    if not clean_text:
        raise ValueError("Conversation text is empty.")

    chunks = split_knowledge_chunks(clean_text)
    import_key = sha1(f"{source_type}|{source_name}|{provider}|{task}|{clean_text[:4000]}".encode("utf-8")).hexdigest()[:18]
    now = datetime.now(timezone.utc).isoformat()
    import_record = IntakeRecord(
        record_type="conversation_import",
        source=f"knowledge_import:{source_type}",
        raw_text=clean_text,
        fields={
            "import_key": import_key,
            "source_type": source_type,
            "source_name": source_name,
            "provider": provider,
            "task": task,
            "operator_notes": operator_notes,
            "chunk_count": len(chunks),
            "imported_at": now,
        },
        score={"priority": source_trust_score(source_type), "source_type": source_type},
        director_notes=["Conversation imported into the Knowledge Capture Layer."],
    )
    append_record(root, import_record)

    items: list[IntakeRecord] = []
    edges: list[IntakeRecord] = []
    for index, chunk in enumerate(chunks, start=1):
        categories = classify_knowledge(chunk)
        entities = extract_entities(chunk)
        score = score_knowledge(chunk, source_type, categories, entities)
        item_key = sha1(f"{import_key}|{index}|{chunk[:1200]}".encode("utf-8")).hexdigest()[:20]
        fields = {
            "item_key": item_key,
            "source_import_id": import_record.record_id,
            "source_type": source_type,
            "source_name": source_name,
            "provider": provider,
            "task": task,
            "categories": categories,
            "primary_category": categories[0] if categories else "unknown",
            "knowledge_score": score["knowledge_score"],
            "credibility_score": score["credibility_score"],
            "evidence_score": score["evidence_score"],
            "knowledge_score_version": "knowledge-score-v1",
            "quality_signals": score["quality_signals"],
            "pollution_risk": pollution_risk(score, source_type),
            "reviewer_verdict": reviewer_verdict(score, source_type),
            "entities": entities,
            "content_excerpt": chunk[:1200],
            "review_status": "trusted" if score["knowledge_score"] >= 85 else "review" if score["knowledge_score"] >= 62 else "low_confidence",
            "imported_at": now,
        }
        item_record = IntakeRecord(
            record_type="knowledge_item",
            source=f"knowledge_import:{source_type}",
            raw_text=chunk,
            fields=fields,
            score={"priority": score["knowledge_score"], "training_weight": training_weight(score["knowledge_score"])},
            director_notes=knowledge_notes(categories, source_type, score["knowledge_score"]),
            confidence=round(score["knowledge_score"] / 100, 3),
        )
        append_record(root, item_record)
        items.append(item_record)
        for edge in build_knowledge_edges(item_key, entities, source_type, score["knowledge_score"]):
            edge_record = IntakeRecord(
                record_type="knowledge_edge",
                source=f"knowledge_import:{source_type}",
                raw_text=json.dumps(edge, ensure_ascii=False),
                fields=edge,
                score={"priority": edge["weight"], "edge_type": edge["relation"]},
                director_notes=["Knowledge graph edge inferred from imported conversation."],
                confidence=round(edge["weight"] / 100, 3),
            )
            append_record(root, edge_record)
            edges.append(edge_record)

    concept_weights = update_concept_weights(root, now)
    learning_memory = build_knowledge_learning_memory(root, now)
    append_record(root, learning_memory)
    return KnowledgeImportResult(import_record, items, edges, concept_weights, learning_memory)


def split_knowledge_chunks(text: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n|(?=^#{1,3}\s)", text, flags=re.MULTILINE) if block.strip()]
    chunks: list[str] = []
    for block in blocks:
        if len(block) <= 1600:
            chunks.append(block)
            continue
        sentences = re.split(r"(?<=[。.!?？])\s+", block)
        current = ""
        for sentence in sentences:
            if len(current) + len(sentence) > 1400 and current:
                chunks.append(current.strip())
                current = sentence
            else:
                current = f"{current}\n{sentence}".strip()
        if current:
            chunks.append(current.strip())
    return chunks[:120]


def classify_knowledge(text: str) -> list[str]:
    lower = text.lower()
    matched: list[str] = []
    for category, keywords in KNOWLEDGE_CATEGORIES:
        if any(keyword.lower() in lower for keyword in keywords):
            matched.append(category)
    return matched or ["general_knowledge"]


def source_trust_score(source_type: str) -> int:
    return SOURCE_TRUST_SCORES.get(str(source_type or "unknown").lower(), SOURCE_TRUST_SCORES["unknown"])


def score_knowledge(text: str, source_type: str, categories: list[str], entities: list[str]) -> dict[str, Any]:
    credibility = source_trust_score(source_type)
    lower = text.lower()
    evidence = 35
    signals: list[str] = []
    if re.search(r"\broi\b|\broas\b|\b\d+(\.\d+)?%\b|\$\d+|\b\d+\s*(单|orders|views|播放|销量)\b", lower):
        evidence += 18
        signals.append("numeric_evidence")
    if "http://" in lower or "https://" in lower:
        evidence += 8
        signals.append("source_url")
    if any(word in lower for word in ["真实", "实测", "店铺", "订单", "报表", "top1", "top 1"]):
        evidence += 10
        signals.append("field_evidence")
    if any(word in lower for word in ["听说", "可能", "感觉", "吹牛", "课程"]):
        evidence -= 6
        signals.append("weak_evidence_language")
    if "吹牛" in lower or str(source_type).lower() == "forum_bluff":
        credibility = min(credibility, 20)
        signals.append("pollution_warning")
    category_bonus = 8 if any(category in categories for category in ["success_case", "failure_case", "platform_rule", "risk_case"]) else 4
    entity_bonus = min(10, len(entities) * 2)
    knowledge_score = max(20, min(100, round(credibility * 0.55 + evidence * 0.30 + category_bonus + entity_bonus)))
    return {
        "knowledge_score": knowledge_score,
        "credibility_score": credibility,
        "evidence_score": max(0, min(100, evidence)),
        "quality_signals": signals or ["needs_more_evidence"],
    }


def reviewer_verdict(score: dict[str, Any], source_type: str) -> str:
    knowledge_score = int(score.get("knowledge_score") or 0)
    if knowledge_score >= 88:
        return "promote_to_core_memory"
    if knowledge_score >= 72:
        return "usable_with_monitoring"
    if pollution_risk(score, source_type) >= 65:
        return "quarantine_until_verified"
    return "review_before_training"


def pollution_risk(score: dict[str, Any], source_type: str) -> int:
    signals = set(score.get("quality_signals") or [])
    risk = 100 - int(score.get("credibility_score") or 0)
    if "pollution_warning" in signals:
        risk += 30
    if "weak_evidence_language" in signals:
        risk += 12
    if str(source_type or "").lower() in {"forum", "forum_bluff", "unknown"}:
        risk += 10
    return max(0, min(100, risk))


def extract_entities(text: str) -> list[str]:
    lower = text.lower()
    entities: list[str] = []
    for display, pattern in ENTITY_PATTERNS:
        if pattern in lower:
            entities.append(display)
    for match in re.findall(r"\b[A-Z][A-Za-z0-9&' -]{2,35}\b", text):
        if match.lower() not in {item.lower() for item in entities} and len(match.split()) <= 4:
            entities.append(match.strip())
    return list(dict.fromkeys(entities))[:30]


def build_knowledge_edges(item_key: str, entities: list[str], source_type: str, score: int) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    seen: set[str] = set()
    normalized = {entity.lower(): entity for entity in entities}
    for entity in entities:
        relation_targets = ENTITY_LINKS.get(entity.lower(), [])
        for target, relation in relation_targets:
            edge_key = sha1(f"{entity.lower()}|{relation}|{target.lower()}".encode("utf-8")).hexdigest()[:20]
            if edge_key in seen:
                continue
            seen.add(edge_key)
            edges.append(
                {
                    "edge_key": edge_key,
                    "source_item_key": item_key,
                    "source_entity": entity,
                    "target_entity": target,
                    "relation": relation,
                    "source_node_type": infer_node_type(entity),
                    "target_node_type": infer_node_type(target, relation),
                    "graph_schema_version": COMMERCE_KNOWLEDGE_GRAPH_SCHEMA["version"],
                    "source_type": source_type,
                    "weight": max(35, min(100, score)),
                }
            )
    for left, right in zip(entities, entities[1:]):
        edge_key = sha1(f"{left.lower()}|co_occurs_with|{right.lower()}".encode("utf-8")).hexdigest()[:20]
        if edge_key in seen or left.lower() == right.lower():
            continue
        seen.add(edge_key)
        edges.append(
            {
                "edge_key": edge_key,
                "source_item_key": item_key,
                "source_entity": normalized.get(left.lower(), left),
                "target_entity": normalized.get(right.lower(), right),
                "relation": "co_occurs_with",
                "source_node_type": infer_node_type(left),
                "target_node_type": infer_node_type(right),
                "graph_schema_version": COMMERCE_KNOWLEDGE_GRAPH_SCHEMA["version"],
                "source_type": source_type,
                "weight": max(30, min(85, score - 8)),
            }
        )
    return edges[:40]


def infer_node_type(entity: str, relation: str = "") -> str:
    lower = str(entity or "").lower()
    relation_lower = str(relation or "").lower()
    if relation_lower in {"holiday"} or "day" in lower or "christmas" in lower or "halloween" in lower:
        return "holiday"
    if relation_lower in {"market"} or lower in {"united states", "canada", "mexico", "japan", "germany", "france"}:
        return "country"
    if relation_lower in {"creator_type", "growth_channel"} or "creator" in lower:
        return "creator"
    if relation_lower in {"product_family", "product_data"} or any(word in lower for word in ["tee", "t-shirt", "product", "blank"]):
        return "product"
    if relation_lower in {"system_layer", "data_schema", "governance"}:
        return "system_layer"
    if "risk" in lower or "ip" in lower or "patent" in lower:
        return "risk"
    if "keyword" in lower:
        return "keyword"
    if "video" in lower:
        return "video"
    if "amazon" in lower or "tiktok" in lower or "walmart" in lower or "etsy" in lower:
        return "platform"
    return "strategy"


def update_concept_weights(root: Path, updated_at: str | None = None) -> list[IntakeRecord]:
    items = read_records(root, "knowledge_item")
    edges = read_records(root, "knowledge_edge")
    buckets: dict[str, dict[str, Any]] = {}
    related: dict[str, Counter[str]] = defaultdict(Counter)

    for item in items:
        fields = item.fields
        score = int(fields.get("knowledge_score") or item.score.get("priority") or 0)
        credibility = int(fields.get("credibility_score") or 0)
        source_type = str(fields.get("source_type") or "unknown")
        categories = fields.get("categories") if isinstance(fields.get("categories"), list) else []
        entities = fields.get("entities") if isinstance(fields.get("entities"), list) else []
        for entity in entities:
            name = str(entity).strip()
            if not name:
                continue
            key = name.lower()
            bucket = buckets.setdefault(
                key,
                {
                    "entity": name,
                    "scores": [],
                    "credibility_scores": [],
                    "source_types": Counter(),
                    "trusted_hits": 0,
                    "categories": Counter(),
                    "item_keys": [],
                },
            )
            bucket["scores"].append(score)
            bucket["credibility_scores"].append(credibility)
            bucket["source_types"][source_type] += 1
            bucket["trusted_hits"] += 1 if score >= 85 or credibility >= 85 else 0
            bucket["item_keys"].append(fields.get("item_key"))
            for category in categories:
                bucket["categories"][str(category)] += 1

    for edge in edges:
        source_entity = str(edge.fields.get("source_entity") or "").strip()
        target_entity = str(edge.fields.get("target_entity") or "").strip()
        if source_entity and target_entity:
            related[source_entity.lower()][target_entity] += 1
            related[target_entity.lower()][source_entity] += 1

    records: list[IntakeRecord] = []
    now = updated_at or datetime.now(timezone.utc).isoformat()
    for key, bucket in sorted(buckets.items()):
        scores = bucket["scores"]
        occurrence_count = len(scores)
        average_score = round(sum(scores) / max(1, occurrence_count), 2)
        credibility_scores = bucket["credibility_scores"]
        average_credibility = round(sum(credibility_scores) / max(1, len(credibility_scores)), 2)
        max_score = max(scores) if scores else 0
        source_count = len(bucket["source_types"])
        trusted_hits = int(bucket["trusted_hits"])
        repeated_bonus = min(35, max(0, occurrence_count - 1) * 7)
        source_bonus = min(18, source_count * 4)
        trusted_bonus = min(18, trusted_hits * 5)
        concept_weight = max(1, min(100, round(average_score * 0.45 + average_credibility * 0.30 + repeated_bonus + source_bonus + trusted_bonus)))
        if concept_weight >= 85:
            status = "core_memory"
            next_action = "Raise monitoring priority and ask agents to consider this concept in product, keyword, video, and listing decisions."
        elif concept_weight >= 68:
            status = "watchlist"
            next_action = "Keep collecting more platform, video, review, and own-store evidence before making hard decisions."
        else:
            status = "weak_signal"
            next_action = "Do not train strategy strongly yet; wait for stronger evidence or trusted source confirmation."

        concept_key = sha1(key.encode("utf-8")).hexdigest()[:18]
        fields = {
            "concept_key": concept_key,
            "entity": bucket["entity"],
            "normalized_entity": key,
            "node_type": infer_node_type(bucket["entity"]),
            "occurrence_count": occurrence_count,
            "source_type_count": source_count,
            "trusted_hits": trusted_hits,
            "average_knowledge_score": average_score,
            "average_credibility_score": average_credibility,
            "max_knowledge_score": max_score,
            "concept_weight": concept_weight,
            "concept_status": status,
            "source_types": [{"source_type": name, "count": count} for name, count in bucket["source_types"].most_common()],
            "top_categories": [{"category": name, "count": count} for name, count in bucket["categories"].most_common(8)],
            "related_entities": [{"entity": name, "count": count} for name, count in related.get(key, Counter()).most_common(12)],
            "sample_item_keys": [item_key for item_key in bucket["item_keys"][:12] if item_key],
            "next_action": next_action,
            "updated_at": now,
            "learning_engine_version": "learning-engine-v1",
        }
        record = IntakeRecord(
            record_type="knowledge_concept_weight",
            source="knowledge_learning_engine",
            raw_text=json.dumps(fields, ensure_ascii=False),
            fields=fields,
            score={"priority": concept_weight, "training_weight": training_weight(concept_weight)},
            director_notes=["Learning Engine updated concept weight from knowledge items, source quality, repetition, and graph links."],
            confidence=round(concept_weight / 100, 3),
        )
        append_record(root, record)
        records.append(record)
    return records


def build_knowledge_learning_memory(root: Path, created_at: str | None = None) -> IntakeRecord:
    items = read_records(root, "knowledge_item")
    edges = read_records(root, "knowledge_edge")
    concept_weights = read_records(root, "knowledge_concept_weight")
    category_counts: Counter[str] = Counter()
    entity_counts: Counter[str] = Counter()
    trusted_count = 0
    for item in items:
        fields = item.fields
        for category in fields.get("categories", []) if isinstance(fields.get("categories"), list) else []:
            category_counts[str(category)] += 1
        for entity in fields.get("entities", []) if isinstance(fields.get("entities"), list) else []:
            entity_counts[str(entity)] += 1
        if float(fields.get("knowledge_score") or 0) >= 85:
            trusted_count += 1
    repeated = [{"entity": key, "count": value} for key, value in entity_counts.most_common(20) if value >= 2]
    top_concepts = sorted(
        concept_weights,
        key=lambda record: int(record.fields.get("concept_weight") or record.score.get("priority") or 0),
        reverse=True,
    )[:20]
    run_date = date.today().isoformat()
    memory_key = f"knowledge-learning:{run_date}"
    fields = {
        "memory_key": memory_key,
        "memory_type": "knowledge_learning_engine",
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "knowledge_items": len(items),
        "knowledge_edges": len(edges),
        "concept_weights": len(concept_weights),
        "trusted_items": trusted_count,
        "top_categories": [{"category": key, "count": value} for key, value in category_counts.most_common(12)],
        "repeated_entities": repeated,
        "top_concept_weights": [
            {
                "entity": record.fields.get("entity"),
                "weight": record.fields.get("concept_weight"),
                "status": record.fields.get("concept_status"),
                "occurrence_count": record.fields.get("occurrence_count"),
            }
            for record in top_concepts
        ],
        "learning_signal": learning_signal_text(repeated, category_counts),
        "next_action": "Use repeated high-confidence entities and categories to raise monitoring priority, but keep low-confidence sources in review.",
    }
    return IntakeRecord(
        record_type="strategy_memory",
        source="knowledge_learning_engine",
        raw_text=json.dumps(fields, ensure_ascii=False),
        fields=fields,
        score={"priority": 82 if items else 35, "training_weight": "high" if repeated else "medium"},
        director_notes=["Knowledge learning engine summarized categories, repeated entities, and graph links."],
    )


def learning_signal_text(repeated: list[dict[str, Any]], categories: Counter[str]) -> str:
    if repeated:
        names = ", ".join(str(item["entity"]) for item in repeated[:6])
        return f"Repeated entities detected: {names}. Raise monitoring weight when repeated evidence comes from trusted sources."
    if categories:
        top = categories.most_common(1)[0][0]
        return f"Knowledge base is forming around {top}, but repeated entity evidence is still weak."
    return "No knowledge items yet. Import conversations, real cases, videos, reviews, and platform rules first."


def training_weight(score: int) -> str:
    if score >= 88:
        return "highest"
    if score >= 72:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def knowledge_notes(categories: list[str], source_type: str, score: int) -> list[str]:
    notes = [f"Knowledge classified as {', '.join(categories)} from {source_type}; score={score}."]
    if score < 62:
        notes.append("Keep this in review; source or evidence is not strong enough yet.")
    if "risk_case" in categories:
        notes.append("Risk knowledge should affect listing, image, video, and channel-sync guardrails.")
    if "viral_case" in categories:
        notes.append("Video knowledge should be linked to hook, scene, script, creator type, and replication plan.")
    return notes
