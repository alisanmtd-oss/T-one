from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any

from .storage import DATA_DIR, merge_duplicate_record, read_jsonl_lines, record_dedupe_key, record_path, write_records
from .types import IntakeRecord


DATA_LAKE_CLEANUP_VERSION = "data-lake-cleanup-v1"


CATEGORY_BY_RECORD_TYPE = {
    "platform_ranking_signal": "product_market_intelligence",
    "hot_link": "product_market_intelligence",
    "review_insight": "review_and_pain_point",
    "competitor_snapshot": "competitor_intelligence",
    "listing_snapshot": "listing_intelligence",
    "price_history": "product_market_intelligence",
    "query_snapshot": "keyword_intelligence",
    "viral_content_signal": "viral_content_intelligence",
    "video_script": "viral_content_intelligence",
    "video_scene": "viral_content_intelligence",
    "video_highlight_frame": "viral_content_intelligence",
    "video_comment": "viral_content_intelligence",
    "video_comment_intelligence": "viral_content_intelligence",
    "creative_inspiration": "creative_intelligence",
    "creative_snapshot": "creative_intelligence",
    "creative_pattern": "creative_intelligence",
    "influencer_cooperation": "influencer_intelligence",
    "social_account_profile": "social_account_intelligence",
    "video_publish_plan": "social_account_intelligence",
    "store_metric_snapshot": "own_store_operations",
    "order_item": "own_store_operations",
    "return_rma": "own_store_operations",
    "refund_record": "own_store_operations",
    "finance_transaction": "finance_operations",
    "settlement": "finance_operations",
    "payout": "finance_operations",
    "invoice": "finance_operations",
    "account_health": "risk_compliance",
    "performance_alert": "risk_compliance",
    "ip_image_risk": "risk_compliance",
    "compliance_term": "risk_compliance",
    "banned_term": "risk_compliance",
    "ip_registry": "risk_compliance",
    "policy_snapshot": "risk_compliance",
    "policy_document": "risk_compliance",
    "policy_rule": "risk_compliance",
    "policy_diff": "risk_compliance",
    "enforcement_event": "risk_compliance",
    "appeal_case": "risk_compliance",
    "supply_chain": "supply_chain",
    "supplier": "supply_chain",
    "factory": "supply_chain",
    "warehouse": "supply_chain",
    "inventory_ledger": "supply_chain",
    "pod_admin_snapshot": "pod_operations",
    "culture_label": "culture_and_seasonality",
    "seasonal_event": "culture_and_seasonality",
    "selection_playbook": "strategy_playbook",
    "strategy_memory": "knowledge_learning",
    "knowledge_item": "knowledge_learning",
    "knowledge_edge": "knowledge_learning",
    "knowledge_concept_weight": "knowledge_learning",
    "conversation_import": "knowledge_learning",
    "learning_event": "knowledge_learning",
    "knowledge_node": "knowledge_learning",
    "knowledge_revision": "knowledge_learning",
    "knowledge_score_record": "knowledge_learning",
    "knowledge_provenance": "knowledge_learning",
    "industry_research_asset": "knowledge_learning",
    "knowledge_distillation_item": "knowledge_learning",
    "word_bank_entry": "knowledge_learning",
    "risk_intelligence_quarantine": "risk_compliance",
    "agent_registry": "agent_governance",
    "agent_evaluation": "agent_governance",
    "model_registry": "agent_governance",
    "prompt_version": "agent_governance",
    "eval_case": "agent_governance",
    "eval_run": "agent_governance",
    "judge_result": "agent_governance",
    "feedback_ticket": "feedback_and_improvement",
    "signal_event": "autonomous_loop",
    "signal_snapshot": "autonomous_loop",
    "signal_threshold": "autonomous_loop",
    "signal_alert": "autonomous_loop",
    "signal_weight": "autonomous_loop",
    "hypothesis": "autonomous_loop",
    "hypothesis_evidence": "autonomous_loop",
    "hypothesis_score": "autonomous_loop",
    "experiment": "autonomous_loop",
    "experiment_run": "autonomous_loop",
    "experiment_variant": "autonomous_loop",
    "experiment_metric": "autonomous_loop",
    "experiment_stop_rule": "autonomous_loop",
    "experiment_scale_rule": "autonomous_loop",
    "experiment_outcome": "autonomous_loop",
    "pattern_weight": "autonomous_loop",
    "pattern_history": "autonomous_loop",
    "strategy_adjustment": "autonomous_loop",
    "priority_score": "autonomous_loop",
    "priority_rebalance_log": "autonomous_loop",
    "task_queue": "automation_queue",
    "task_priority": "automation_queue",
    "backlog": "automation_queue",
    "approval_request": "automation_queue",
    "execution_result": "automation_queue",
    "agent_action_log": "automation_queue",
    "collection_job": "collection_pipeline",
    "source_document": "collection_pipeline",
    "raw_asset": "collection_pipeline",
    "source_chunk": "collection_pipeline",
    "import_batch": "collection_pipeline",
    "raw_extraction_run": "collection_pipeline",
    "ingestion_run": "collection_pipeline",
    "lineage_event": "collection_pipeline",
    "event_inbox": "collection_pipeline",
    "event_dedup": "collection_pipeline",
    "dead_letter": "collection_pipeline",
}


@dataclass(slots=True)
class DataLakeCleanupResult:
    run_id: str
    applied: bool
    backup_dir: str
    total_input_records: int
    total_output_records: int
    duplicates_removed: int
    invalid_lines: int
    files_processed: int
    record_type_summary: dict[str, dict[str, Any]]
    category_summary: dict[str, int]
    report_path: Path
    index_path: Path
    invalid_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "applied": self.applied,
            "backup_dir": self.backup_dir,
            "total_input_records": self.total_input_records,
            "total_output_records": self.total_output_records,
            "duplicates_removed": self.duplicates_removed,
            "invalid_lines": self.invalid_lines,
            "files_processed": self.files_processed,
            "record_type_summary": self.record_type_summary,
            "category_summary": self.category_summary,
            "report_path": str(self.report_path),
            "index_path": str(self.index_path),
            "invalid_path": str(self.invalid_path),
        }


def run_data_lake_cleanup(root: Path, *, apply: bool = True) -> DataLakeCleanupResult:
    root = root.resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    data_dir = root / DATA_DIR
    output_dir = root / "outputs"
    backup_dir = output_dir / f"data_lake_cleanup_backup_{run_id}"
    invalid_path = output_dir / f"data_lake_cleanup_invalid_{run_id}.jsonl"
    report_path = output_dir / f"data_lake_cleanup_report_{run_id}.md"
    index_path = output_dir / f"data_lake_index_{run_id}.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    grouped: dict[str, list[IntakeRecord]] = defaultdict(list)
    invalid_lines: list[dict[str, Any]] = []
    input_counter: Counter[str] = Counter()
    file_count = 0

    for path in sorted(data_dir.glob("*.jsonl")):
        file_count += 1
        record_type_from_file = path.stem
        for line_number, line in enumerate(read_jsonl_lines(path), start=1):
            clean = line.lstrip("\ufeff").strip()
            if not clean:
                continue
            try:
                payload = json.loads(clean)
                if not isinstance(payload, dict):
                    raise ValueError("JSONL line is not an object")
                record = IntakeRecord.from_dict(payload)
            except Exception as exc:  # noqa: BLE001 - cleanup report must quarantine bad rows.
                invalid_lines.append(
                    {
                        "file": str(path),
                        "line_number": line_number,
                        "record_type_from_file": record_type_from_file,
                        "error": str(exc)[:300],
                        "preview": clean[:500],
                    }
                )
                continue
            cleaned = classify_record(record)
            grouped[cleaned.record_type].append(cleaned)
            input_counter[cleaned.record_type] += 1

    cleaned_by_type: dict[str, list[IntakeRecord]] = {}
    record_type_summary: dict[str, dict[str, Any]] = {}
    category_counter: Counter[str] = Counter()
    total_in = 0
    total_out = 0

    for record_type, records in sorted(grouped.items()):
        deduped = dedupe_records(records)
        cleaned_by_type[record_type] = deduped
        total_in += len(records)
        total_out += len(deduped)
        categories = Counter(str(item.metadata.get("data_lake_category") or classify_record_type(item.record_type)) for item in deduped)
        category_counter.update(categories)
        record_type_summary[record_type] = {
            "category": classify_record_type(record_type),
            "input_records": len(records),
            "output_records": len(deduped),
            "duplicates_removed": len(records) - len(deduped),
            "category_breakdown": dict(categories),
        }

    if apply:
        backup_existing_files(data_dir, backup_dir)
        for record_type, records in cleaned_by_type.items():
            write_records(root, record_type, records)

    write_invalid_lines(invalid_path, invalid_lines)
    write_data_lake_index(index_path, run_id, cleaned_by_type, record_type_summary, category_counter, apply)
    report = build_cleanup_report(run_id, apply, backup_dir, record_type_summary, category_counter, total_in, total_out, invalid_lines)
    report_path.write_text(report, encoding="utf-8-sig")

    return DataLakeCleanupResult(
        run_id=run_id,
        applied=apply,
        backup_dir=str(backup_dir) if apply else "",
        total_input_records=total_in,
        total_output_records=total_out,
        duplicates_removed=total_in - total_out,
        invalid_lines=len(invalid_lines),
        files_processed=file_count,
        record_type_summary=record_type_summary,
        category_summary=dict(category_counter),
        report_path=report_path,
        index_path=index_path,
        invalid_path=invalid_path,
    )


def classify_record(record: IntakeRecord) -> IntakeRecord:
    metadata = dict(record.metadata or {})
    category = classify_record_type(record.record_type, record.fields)
    metadata["data_lake_category"] = category
    metadata["cleanup_version"] = DATA_LAKE_CLEANUP_VERSION
    metadata["cleanup_seen_at"] = datetime.now(timezone.utc).isoformat()
    fields = dict(record.fields or {})
    fields.setdefault("data_lake_category", category)
    return IntakeRecord(
        record_id=record.record_id,
        record_type=record.record_type,
        created_at=record.created_at,
        source=record.source,
        raw_text=record.raw_text,
        fields=fields,
        score=record.score,
        director_notes=record.director_notes,
        review_status=record.review_status,
        confidence=record.confidence,
        metadata=metadata,
    )


def classify_record_type(record_type: str, fields: dict[str, Any] | None = None) -> str:
    if record_type in CATEGORY_BY_RECORD_TYPE:
        return CATEGORY_BY_RECORD_TYPE[record_type]
    text = json.dumps(fields or {}, ensure_ascii=False).lower()
    if any(term in text for term in ["tiktok", "video", "hook", "creator"]):
        return "viral_content_intelligence"
    if any(term in text for term in ["amazon", "bsr", "new release", "rank"]):
        return "product_market_intelligence"
    if any(term in text for term in ["refund", "return", "order", "roas", "gmv"]):
        return "own_store_operations"
    if any(term in text for term in ["ip", "trademark", "copyright", "tro", "patent"]):
        return "risk_compliance"
    if any(term in text for term in ["factory", "supplier", "warehouse", "inventory"]):
        return "supply_chain"
    return "uncategorized"


def dedupe_records(records: list[IntakeRecord]) -> list[IntakeRecord]:
    by_key: dict[str, IntakeRecord] = {}
    order: list[str] = []
    for record in records:
        key = record_dedupe_key(record) or exact_record_key(record)
        if key in by_key:
            by_key[key] = merge_duplicate_record(by_key[key], record)
            by_key[key] = classify_record(by_key[key])
        else:
            by_key[key] = record
            order.append(key)
    return [by_key[key] for key in order]


def exact_record_key(record: IntakeRecord) -> str:
    payload = {
        "record_type": record.record_type,
        "source": record.source,
        "raw_text": normalize_text(record.raw_text),
        "fields": normalize_json_value(record.fields),
    }
    digest = sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return f"{record.record_type}:exact:{digest}"


def normalize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): normalize_json_value(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [normalize_json_value(item) for item in value]
    if isinstance(value, str):
        return normalize_text(value)
    return value


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def backup_existing_files(data_dir: Path, backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(data_dir.glob("*.jsonl")):
        target = backup_dir / path.name
        target.write_bytes(path.read_bytes())


def write_invalid_lines(path: Path, invalid_lines: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig") as handle:
        for item in invalid_lines:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def write_data_lake_index(
    path: Path,
    run_id: str,
    records_by_type: dict[str, list[IntakeRecord]],
    record_type_summary: dict[str, dict[str, Any]],
    category_counter: Counter[str],
    applied: bool,
) -> None:
    payload = {
        "run_id": run_id,
        "applied": applied,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": dict(category_counter),
        "record_types": record_type_summary,
        "category_to_record_types": category_to_record_types(records_by_type),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def category_to_record_types(records_by_type: dict[str, list[IntakeRecord]]) -> dict[str, list[str]]:
    buckets: dict[str, set[str]] = defaultdict(set)
    for record_type, records in records_by_type.items():
        if not records:
            buckets[classify_record_type(record_type)].add(record_type)
            continue
        for record in records:
            buckets[str(record.metadata.get("data_lake_category") or classify_record_type(record_type))].add(record_type)
    return {category: sorted(types) for category, types in sorted(buckets.items())}


def build_cleanup_report(
    run_id: str,
    applied: bool,
    backup_dir: Path,
    record_type_summary: dict[str, dict[str, Any]],
    category_counter: Counter[str],
    total_in: int,
    total_out: int,
    invalid_lines: list[dict[str, Any]],
) -> str:
    duplicate_count = total_in - total_out
    top_duplicates = sorted(record_type_summary.items(), key=lambda item: int(item[1].get("duplicates_removed") or 0), reverse=True)[:12]
    lines = [
        f"# Data Lake Cleanup Report - {run_id}",
        "",
        "## Summary",
        f"- Applied: {applied}",
        f"- Input records: {total_in}",
        f"- Output records: {total_out}",
        f"- Duplicates merged: {duplicate_count}",
        f"- Invalid lines quarantined: {len(invalid_lines)}",
        f"- Backup directory: {backup_dir if applied else '-'}",
        "",
        "## Mind Map",
        "```mermaid",
        "mindmap",
        "  root((Data Lake))",
        "    Product Market Intelligence",
        "      Amazon BSR New Release",
        "      TikTok Shop Product",
        "      Ranking Signals",
        "    Viral Content Intelligence",
        "      Video",
        "      Hook",
        "      Creator",
        "      Script",
        "    Store Operations",
        "      Sales",
        "      Orders",
        "      Returns",
        "      Ads",
        "      Finance",
        "    Risk Compliance",
        "      IP",
        "      Trademark",
        "      Copyright",
        "      TRO",
        "    Knowledge Learning",
        "      StrategyMemory",
        "      KnowledgeGraph",
        "      FeedbackTicket",
        "      ConceptWeight",
        "    Autonomous Loop",
        "      Signal",
        "      Hypothesis",
        "      Experiment",
        "      Reinforcement",
        "```",
        "",
        "## Category Summary",
    ]
    for category, count in category_counter.most_common():
        lines.append(f"- {category}: {count}")
    lines.extend(["", "## Record Type Summary"])
    for record_type, summary in sorted(record_type_summary.items()):
        lines.append(
            f"- {record_type}: {summary['input_records']} -> {summary['output_records']} "
            f"(merged {summary['duplicates_removed']}), category={summary['category']}"
        )
    lines.extend(["", "## Duplicate Hotspots"])
    for record_type, summary in top_duplicates:
        if int(summary.get("duplicates_removed") or 0) <= 0:
            continue
        lines.append(f"- {record_type}: merged {summary['duplicates_removed']}")
    lines.extend(["", "## Invalid Data"])
    if invalid_lines:
        for item in invalid_lines[:20]:
            lines.append(f"- {Path(str(item['file'])).name}:{item['line_number']} - {item['error']}")
        if len(invalid_lines) > 20:
            lines.append(f"- ... {len(invalid_lines) - 20} more quarantined lines")
    else:
        lines.append("- No invalid JSONL lines found.")
    lines.extend(
        [
            "",
            "## Next Rules",
            "- New records should keep `data_lake_category` so reports can filter by business area.",
            "- Re-run cleanup after large imports, browser captures, platform scans, or AI meetings.",
            "- Duplicates are merged, not blindly deleted; original files are backed up before apply mode.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def latest_data_lake_cleanup_report(root: Path) -> tuple[str, Path | None]:
    paths = sorted((root / "outputs").glob("data_lake_cleanup_report_*.md"), reverse=True)
    if not paths:
        return "No Data Lake cleanup report yet.", None
    path = paths[0]
    return path.read_text(encoding="utf-8-sig"), path
