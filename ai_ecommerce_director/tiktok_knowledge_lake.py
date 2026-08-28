from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from .storage import append_record
from .types import IntakeRecord


CONFIG_PATH = Path("config") / "tiktok_knowledge_lake.json"
REPORT_PREFIX = "tiktok_knowledge_lake_pilot"


@dataclass(slots=True)
class TikTokKnowledgeLakePilotResult:
    run_date: str
    source_documents: list[IntakeRecord]
    collection_jobs: list[IntakeRecord]
    task_queue: list[IntakeRecord]
    quality_metrics: list[IntakeRecord]
    strategy_memories: list[IntakeRecord]
    report_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "source_documents": [record.to_dict() for record in self.source_documents],
            "collection_jobs": [record.to_dict() for record in self.collection_jobs],
            "task_queue": [record.to_dict() for record in self.task_queue],
            "quality_metrics": [record.to_dict() for record in self.quality_metrics],
            "strategy_memories": [record.to_dict() for record in self.strategy_memories],
            "report_path": str(self.report_path),
        }


def run_tiktok_knowledge_lake_pilot(root: Path, run_date: str | None = None) -> TikTokKnowledgeLakePilotResult:
    root = root.resolve()
    run_date = run_date or date.today().isoformat()
    config = ensure_config(root)
    now = datetime.now(timezone.utc).isoformat()

    source_documents = [build_source_document(source, run_date, now) for source in config["source_registry"]]
    for record in source_documents:
        append_record(root, record)

    collection_jobs = [build_collection_job(job, run_date, now) for job in config["pilot_jobs"]]
    for record in collection_jobs:
        append_record(root, record)

    task_queue = [build_task_queue_record(job, run_date, now) for job in config["pilot_jobs"]]
    for record in task_queue:
        append_record(root, record)

    quality_metrics = [build_quality_metric(metric, run_date, now) for metric in config["quality_metrics"]]
    for record in quality_metrics:
        append_record(root, record)

    strategy_memories = [build_strategy_memory(memory, run_date, now) for memory in config["strategy_memories"]]
    for record in strategy_memories:
        append_record(root, record)

    report = render_pilot_report(config, run_date, source_documents, collection_jobs, task_queue)
    report_path = root / "outputs" / f"{REPORT_PREFIX}_{run_date}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    return TikTokKnowledgeLakePilotResult(
        run_date=run_date,
        source_documents=source_documents,
        collection_jobs=collection_jobs,
        task_queue=task_queue,
        quality_metrics=quality_metrics,
        strategy_memories=strategy_memories,
        report_path=report_path,
    )


def ensure_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_PATH
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    config = default_config()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return config


def default_config() -> dict[str, Any]:
    return {
        "safe_mode": True,
        "goal": "Build a compliant TikTok commerce video intelligence lake with evidence lineage, not a black-box crawler.",
        "pilot_window_days": 30,
        "pilot_targets": {
            "video_metadata_records": 10000,
            "deep_video_breakdowns": 1000,
            "default_storage_mode": "metadata_keyframes_asr_ocr_pointer",
        },
        "source_registry": [
            {
                "source_id": "tiktok_shop_partner_center_own_shop",
                "priority": "S",
                "rail": "first_party_authorized",
                "platform": "TikTok Shop",
                "auth_mode": "seller_oauth_or_partner_authorization",
                "allowed_content": ["own_store_products", "orders", "inventory", "after_sales", "settlement"],
                "forbidden_content": ["competitor_private_data", "login_bypass", "captcha_bypass"],
                "record_types": ["store_operation_event", "store_metric_snapshot", "review_insight"],
            },
            {
                "source_id": "amazon_sp_api_own_shop",
                "priority": "S",
                "rail": "first_party_authorized",
                "platform": "Amazon",
                "auth_mode": "lwa_oauth_sigv4",
                "allowed_content": ["own_catalog", "pricing", "reports", "orders", "inventory", "returns"],
                "forbidden_content": ["unauthorized_competitor_seller_data"],
                "record_types": ["store_operation_event", "store_metric_snapshot", "platform_ranking_signal"],
            },
            {
                "source_id": "tiktok_display_api_creator_authorized",
                "priority": "S",
                "rail": "creator_authorized",
                "platform": "TikTok",
                "auth_mode": "creator_oauth",
                "allowed_content": ["authorized_creator_profile", "authorized_creator_video_list"],
                "forbidden_content": ["unauthorized_video_download"],
                "record_types": ["viral_content_signal", "video_breakdown"],
            },
            {
                "source_id": "tiktok_research_tools",
                "priority": "A",
                "rail": "official_research",
                "platform": "TikTok",
                "auth_mode": "approved_research_access",
                "allowed_content": ["public_video_metadata", "public_comments", "public_shop_research_fields"],
                "forbidden_content": ["full_coverage_assumption", "unauthorized_binary_video_storage"],
                "record_types": ["viral_content_signal", "video_comment", "video_comment_intelligence"],
            },
            {
                "source_id": "tiktok_commercial_content_api",
                "priority": "A",
                "rail": "official_commercial_content",
                "platform": "TikTok",
                "auth_mode": "developer_api_access",
                "allowed_content": ["ads", "paid_partnerships", "brand_names", "creator_usernames", "commercial_video_url", "cover_url"],
                "forbidden_content": ["misrepresenting_ads_as_organic_truth"],
                "record_types": ["creative_snapshot", "viral_content_signal", "commercial_disclosure"],
            },
            {
                "source_id": "tiktok_creative_center",
                "priority": "A",
                "rail": "official_public_tools",
                "platform": "TikTok",
                "auth_mode": "public_or_logged_in_view",
                "allowed_content": ["top_ads", "top_products", "trend_pages"],
                "forbidden_content": ["login_bypass", "captcha_bypass"],
                "record_types": ["creative_snapshot", "platform_ranking_signal"],
            },
            {
                "source_id": "fastmoss_kalodata_vendor_import",
                "priority": "B",
                "rail": "licensed_vendor_or_manual_export",
                "platform": "FastMoss/Kalodata",
                "auth_mode": "account_export_or_contract_api",
                "allowed_content": ["product_rankings", "creator_rankings", "video_links", "shop_rankings", "comments_if_contract_allows"],
                "forbidden_content": ["using_vendor_data_beyond_license"],
                "record_types": ["platform_ranking_signal", "hot_link", "viral_content_signal", "creator_spike_event"],
            },
            {
                "source_id": "public_page_metadata_allowed",
                "priority": "B",
                "rail": "robots_allowed_public_metadata",
                "platform": "Public Web",
                "auth_mode": "no_login_public_metadata",
                "allowed_content": ["robots_allowed_metadata", "url_evidence", "page_snapshot"],
                "forbidden_content": ["robots_disallowed_paths", "search_page_bypass", "shop_private_pages"],
                "record_types": ["source_document", "source_chunk", "evidence_claim"],
            },
        ],
        "pilot_jobs": [
            {
                "job_id": "pilot_own_shop_truth",
                "title": "First-party store truth source",
                "rail": "first_party_authorized",
                "cadence": "hourly_or_event_driven",
                "target_records": 1000,
                "data_tables": ["SourceDocument", "Store", "Order", "Review", "StoreMetricSnapshot", "EvidenceClaim"],
                "outputs": ["own_store_sales_truth", "refund_signal", "review_pain_point_signal"],
            },
            {
                "job_id": "pilot_commercial_video_samples",
                "title": "Commercial and viral video sample lake",
                "rail": "official_research_and_ads",
                "cadence": "daily_budget",
                "target_records": 10000,
                "deep_breakdowns": 1000,
                "data_tables": ["Video", "VideoScene", "VideoHighlightFrame", "VideoComment", "VideoCommentIntelligence"],
                "outputs": ["hook_library", "cta_library", "creator_pattern", "comment_purchase_signal"],
            },
            {
                "job_id": "pilot_vendor_competitor_bridge",
                "title": "FastMoss/Kalodata competitor bridge",
                "rail": "licensed_vendor_or_manual_export",
                "cadence": "daily_snapshot_diff",
                "target_records": 3000,
                "data_tables": ["CompetitorSnapshot", "ListingSnapshot", "PriceHistory", "PlatformRankingSignal"],
                "outputs": ["fastest_growing_products", "fastest_growing_creators", "ranking_delta"],
            },
            {
                "job_id": "pilot_video_deep_breakdown",
                "title": "Deep breakdown queue for high-value videos only",
                "rail": "processing_plane",
                "cadence": "priority_queue",
                "target_records": 1000,
                "data_tables": ["RawExtractionRun", "VideoScene", "VideoHighlightFrame", "EvidenceClaim", "KnowledgeScore"],
                "outputs": ["0_2s_hook", "shot_script", "asr", "ocr", "keyframes", "replication_plan"],
            },
        ],
        "quality_metrics": [
            {"metric_name": "lineage_completeness", "target_value": 0.98, "pipeline_area": "evidence"},
            {"metric_name": "dedupe_cluster_precision", "target_value": 0.9, "pipeline_area": "dedupe"},
            {"metric_name": "deep_breakdown_success_rate", "target_value": 0.85, "pipeline_area": "video"},
            {"metric_name": "policy_reject_before_fetch_rate", "target_value": 1.0, "pipeline_area": "policy"},
            {"metric_name": "unauthorized_binary_video_storage", "target_value": 0.0, "pipeline_area": "compliance"},
        ],
        "strategy_memories": [
            {
                "memory_key": "tiktok_lake_no_black_box_crawling",
                "rule": "Do not build an all-network crawler. Use authorized, official, licensed, or robots-allowed sources only.",
            },
            {
                "memory_key": "tiktok_lake_no_raw_video_by_default",
                "rule": "For videos without explicit storage rights, keep URL, metadata, cover, screenshots/keyframes, ASR/OCR, claims, and vectors; do not default to storing full video binaries.",
            },
            {
                "memory_key": "tiktok_lake_deep_breakdown_only_for_high_value",
                "rule": "Run deep video breakdown only on high-value samples. Cold samples stay as shallow metadata or pointer-only records.",
            },
            {
                "memory_key": "tiktok_lake_evidence_before_memory",
                "rule": "StrategyMemory must be backed by SourceDocument, SourceChunk, EvidenceClaim, and KnowledgeScore.",
            },
        ],
    }


def build_source_document(source: dict[str, Any], run_date: str, now: str) -> IntakeRecord:
    payload = json.dumps(source, ensure_ascii=False, sort_keys=True)
    checksum = sha256(payload.encode("utf-8")).hexdigest()
    source_id = stable_id("src_", source["source_id"])
    fields = {
        "source_id": source_id,
        "source_type": "manual",
        "source_name": source["source_id"],
        "source_uri": f"config://{CONFIG_PATH.as_posix()}#{source['source_id']}",
        "platform": source["platform"],
        "country": "global",
        "collected_at_utc": now,
        "source_timezone": "UTC",
        "collected_by": "tiktok_knowledge_lake_pilot",
        "raw_storage_path": f"data/raw/source_registry/{run_date}/{source['source_id']}.json",
        "checksum": checksum,
        "parser_version": "tiktok-knowledge-lake-v1",
        "is_verified": True,
        "status": "captured",
        "priority": source["priority"],
        "rail": source["rail"],
        "auth_mode": source["auth_mode"],
        "allowed_content": source["allowed_content"],
        "forbidden_content": source["forbidden_content"],
        "record_types": source["record_types"],
    }
    return IntakeRecord(
        record_type="source_document",
        fields=fields,
        raw_text=payload,
        source="tiktok_knowledge_lake.source_registry",
        score={"priority": source_priority_score(source["priority"]), "source_reliability": source_reliability(source["priority"])},
        director_notes=["Registered compliant TikTok knowledge-lake source. Fetching still requires its auth and policy check."],
        confidence=0.9,
        metadata={"lake_layer": "bronze", "safe_mode": True},
    )


def build_collection_job(job: dict[str, Any], run_date: str, now: str) -> IntakeRecord:
    fields = {
        "collection_job_id": stable_id("col_", job["job_id"], run_date),
        "case_learning_key": f"tiktok-lake:{job['job_id']}:{run_date}",
        "collection_target": job["title"],
        "data_category": "tiktok_video_knowledge_lake",
        "source_platform": "TikTok",
        "marketplace": "TikTok Shop",
        "target_keyword": job["title"],
        "cadence": job["cadence"],
        "rail": job["rail"],
        "target_records": job["target_records"],
        "deep_breakdowns": job.get("deep_breakdowns", 0),
        "data_tables": job["data_tables"],
        "required_outputs": job["outputs"],
        "allowed_actions": ["create_local_tasks", "import_authorized_or_exported_data", "draft_breakdown", "write_evidence_claims"],
        "forbidden_actions": ["bypass_captcha_or_slider", "bypass_login", "ignore_robots", "store_unauthorized_full_video", "publish_store_action"],
        "automation_level": "L0_read_only_to_L2_draft",
        "learning_status": "queued",
        "created_at_utc": now,
        "run_date": run_date,
    }
    return IntakeRecord(
        record_type="collection_job",
        fields=fields,
        raw_text=json.dumps(job, ensure_ascii=False),
        source="tiktok_knowledge_lake.pilot_jobs",
        score={"priority": 92 if "video" in job["title"].lower() else 85},
        director_notes=["Pilot job created from TikTok knowledge-lake plan. It is a local queue item, not an external action."],
        confidence=0.88,
        metadata={"pilot": True, "safe_mode": True},
    )


def build_task_queue_record(job: dict[str, Any], run_date: str, now: str) -> IntakeRecord:
    fields = {
        "task_queue_id": stable_id("tsk_", "tiktok_lake", job["job_id"], run_date),
        "task_type": "tiktok_knowledge_lake_pilot",
        "target_agent_id": "agn_viral_content_intelligence_v1",
        "target_entity_type": "collection_job",
        "target_entity_id": stable_id("col_", job["job_id"], run_date),
        "priority": 95 if "video" in job["title"].lower() else 86,
        "status": "queued",
        "approval_required": False,
        "safe_mode": True,
        "created_at_utc": now,
        "payload": {
            "title": job["title"],
            "rail": job["rail"],
            "outputs": job["outputs"],
            "data_tables": job["data_tables"],
        },
    }
    return IntakeRecord(
        record_type="task_queue",
        fields=fields,
        raw_text=json.dumps(job, ensure_ascii=False),
        source="tiktok_knowledge_lake.task_queue",
        score={"priority": fields["priority"]},
        director_notes=["Task is safe local planning. Any real platform access remains governed by source auth and policy."],
        confidence=0.9,
    )


def build_quality_metric(metric: dict[str, Any], run_date: str, now: str) -> IntakeRecord:
    fields = {
        "quality_metric_snapshot_id": stable_id("qms_", metric["pipeline_area"], metric["metric_name"], run_date),
        "pipeline_area": metric["pipeline_area"],
        "metric_name": metric["metric_name"],
        "metric_value": 0,
        "target_value": metric["target_value"],
        "measured_at_utc": now,
        "status": "baseline_pending",
        "notes": "Baseline target created before the first 30-day pilot run.",
    }
    return IntakeRecord(
        record_type="quality_metric_snapshot",
        fields=fields,
        raw_text=json.dumps(metric, ensure_ascii=False),
        source="tiktok_knowledge_lake.quality_metrics",
        score={"priority": 82},
        director_notes=["Quality metric target for the TikTok knowledge-lake pilot."],
        confidence=0.86,
    )


def build_strategy_memory(memory: dict[str, Any], run_date: str, now: str) -> IntakeRecord:
    fields = {
        "memory_key": memory["memory_key"],
        "memory_type": "policy",
        "topic": "tiktok_knowledge_lake",
        "rule": memory["rule"],
        "what_cannot_be_done": memory["rule"],
        "condition": "Applies before any TikTok video, shop, creator, competitor, or vendor data enters StrategyMemory.",
        "review_after": "When official API access or vendor contract terms change.",
        "created_at_utc": now,
        "run_date": run_date,
    }
    return IntakeRecord(
        record_type="strategy_memory",
        fields=fields,
        raw_text=json.dumps(memory, ensure_ascii=False),
        source="tiktok_knowledge_lake.guardrails",
        score={"priority": 96, "risk_guardrail": True},
        director_notes=["Core guardrail for compliant video intelligence and local knowledge-lake learning."],
        confidence=0.95,
    )


def render_pilot_report(
    config: dict[str, Any],
    run_date: str,
    source_documents: list[IntakeRecord],
    collection_jobs: list[IntakeRecord],
    task_queue: list[IntakeRecord],
) -> str:
    s_count = len([item for item in source_documents if item.fields.get("priority") == "S"])
    a_count = len([item for item in source_documents if item.fields.get("priority") == "A"])
    b_count = len([item for item in source_documents if item.fields.get("priority") == "B"])
    deep_target = int(config["pilot_targets"]["deep_video_breakdowns"])
    metadata_target = int(config["pilot_targets"]["video_metadata_records"])
    lines = [
        "# TikTok Knowledge Lake Pilot Report",
        "",
        f"Date: {run_date}",
        "",
        "## Boss Summary",
        "",
        "This is now a governed data-lake pilot, not a black-box crawler. The system will prioritize authorized own-shop data, official TikTok/Amazon sources, licensed vendor exports, and robots-allowed public metadata. It will not bypass login, CAPTCHA, robots restrictions, or store unauthorized full video binaries by default.",
        "",
        f"30-day pilot target: {metadata_target:,} video metadata records and {deep_target:,} deep video breakdowns.",
        "",
        "## Source Rails",
        "",
        f"- S sources: {s_count} first-party or creator-authorized sources.",
        f"- A sources: {a_count} official research, ads, or public tool sources.",
        f"- B sources: {b_count} vendor/export or robots-allowed metadata sources.",
        "",
        "## What Gets Stored",
        "",
        "- Bronze: SourceDocument, RawAsset, SourceChunk, raw API/export/page evidence.",
        "- Silver: Video, Creator, Product, Store, Review, VideoScene, VideoComment.",
        "- Gold: EvidenceClaim, KnowledgeScore, KnowledgeEdge, SignalEvent, StrategyMemory.",
        "",
        "## Safety Rules",
        "",
        "- Do not bypass login, slider, CAPTCHA, or robots restrictions.",
        "- Do not assume official research APIs are full coverage.",
        "- Do not store full video binaries by default without explicit rights.",
        "- Do not let third-party estimated data overwrite own-store truth.",
        "- Do not write StrategyMemory without SourceDocument, SourceChunk, EvidenceClaim, and KnowledgeScore.",
        "",
        "## Pilot Jobs Queued",
        "",
    ]
    for record in collection_jobs:
        fields = record.fields
        lines.append(f"- {fields['collection_target']}: {fields['target_records']} target records, {fields.get('deep_breakdowns', 0)} deep breakdowns, cadence {fields['cadence']}.")
    lines.extend(
        [
            "",
            "## Task Queue",
            "",
            f"{len(task_queue)} safe local planning tasks were queued. They do not perform real platform actions.",
            "",
            "## Acceptance Gate",
            "",
            "The pilot is accepted only when the system can replay every field from evidence, dedupe repeated videos, score source quality, summarize hooks/CTA/comments, and send only high-confidence opportunities into the experiment queue.",
        ]
    )
    return "\n".join(lines)


def source_priority_score(priority: str) -> int:
    return {"S": 98, "A": 90, "B": 76, "C": 40}.get(priority, 50)


def source_reliability(priority: str) -> float:
    return {"S": 1.0, "A": 0.85, "B": 0.65, "C": 0.2}.get(priority, 0.4)


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    return prefix + sha256(raw.encode("utf-8")).hexdigest()[:16]
