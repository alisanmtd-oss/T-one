from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any

from .selection_intelligence import (
    CategoryNode,
    is_empty_or_weak_selection_record,
    is_verification_page_record,
    load_category_nodes,
    load_selection_config,
    record_matches_category,
    record_product_name,
    record_url,
)
from .storage import append_record, read_records
from .tk_overnight import build_tk_snapshot, read_tk_overnight_run_log
from .types import IntakeRecord


HEALTH_REPORT_PREFIX = "tk_supervision_health"
BLOCKER_STATUSES = {
    "verification_required",
    "logged_in_capture_required",
    "manual_gate",
    "visible_capture_required",
    "fetch_failed",
    "failed",
    "mismatched_page",
}
TK_PLATFORMS = {"tiktok", "tiktok shop", "fastmoss", "kalodata"}


@dataclass(slots=True)
class TkSupervisionHealthResult:
    run_date: str
    since_hours: int
    status: str
    report: str
    report_path: Path
    json_path: Path
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "since_hours": self.since_hours,
            "status": self.status,
            "metrics": self.metrics,
            "report": self.report,
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
        }


def run_tk_supervision_health(root: Path, run_date: str | None = None, *, since_hours: int = 24) -> TkSupervisionHealthResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    snapshot = build_tk_snapshot(root)
    runs = read_tk_overnight_run_log(root, since_hours=since_hours)
    collection_jobs = read_records(root, "collection_job")
    ranking_records = read_records(root, "platform_ranking_signal")
    categories = load_category_nodes(load_selection_config(root))

    blocker_summary = summarize_blockers(collection_jobs)
    priority_blockers = summarize_priority_blockers(collection_jobs)
    compliant_policy = build_compliant_collection_policy()
    category_health = build_category_depth_health(categories, ranking_records)
    evidence_health = build_evidence_health(snapshot, runs)
    source_health = build_source_health(collection_jobs, ranking_records)
    evidence_recovery_plan = build_evidence_recovery_plan(priority_blockers, category_health, source_health, evidence_health)
    bug_flags = detect_bug_flags(snapshot, blocker_summary, category_health, evidence_health, source_health)
    status = "PASS" if not bug_flags else "ATTENTION"

    metrics = {
        "status": status,
        "snapshot": snapshot,
        "blockers": blocker_summary,
        "priority_blockers": priority_blockers,
        "category_health": category_health,
        "evidence_health": evidence_health,
        "source_health": source_health,
        "evidence_recovery_plan": evidence_recovery_plan,
        "bug_flags": bug_flags,
        "compliant_collection_policy": compliant_policy,
    }
    persist_health_records(root, report_date, since_hours, metrics)
    report = build_health_report(report_date, since_hours, metrics)
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{HEALTH_REPORT_PREFIX}_{report_date}.md"
    json_path = output_dir / f"{HEALTH_REPORT_PREFIX}_{report_date}.json"
    report_path.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return TkSupervisionHealthResult(report_date, since_hours, status, report, report_path, json_path, metrics)


def summarize_blockers(collection_jobs: list[IntakeRecord]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_platform: dict[str, int] = {}
    examples: list[dict[str, Any]] = []
    pending = 0
    for record in collection_jobs:
        fields = record.fields or {}
        status = str(fields.get("source_status") or fields.get("status") or "").strip()
        platform = str(fields.get("source_platform") or fields.get("platform_list") or fields.get("marketplace") or "unknown").strip()
        if status:
            by_status[status] = by_status.get(status, 0) + 1
        if status in BLOCKER_STATUSES:
            by_platform[platform] = by_platform.get(platform, 0) + 1
            if len(examples) < 8:
                examples.append(
                    {
                        "status": status,
                        "platform": platform,
                        "target": fields.get("collection_target") or fields.get("product_target_name") or fields.get("product_name") or "",
                        "url": fields.get("url") or "",
                        "next_step": fields.get("next_step") or "",
                    }
                )
        if status in {"pending_collection", "pending_research", "queued"}:
            pending += 1
    return {
        "total_collection_jobs": len(collection_jobs),
        "pending": pending,
        "by_status": dict(sorted(by_status.items(), key=lambda item: item[1], reverse=True)),
        "blockers_by_platform": dict(sorted(by_platform.items(), key=lambda item: item[1], reverse=True)),
        "examples": examples,
    }


def summarize_priority_blockers(collection_jobs: list[IntakeRecord]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for record in collection_jobs:
        fields = record.fields or {}
        status = str(fields.get("source_status") or fields.get("status") or "").strip()
        platform = str(fields.get("source_platform") or fields.get("platform_list") or fields.get("marketplace") or "unknown").strip()
        target = str(fields.get("collection_target") or fields.get("product_target_name") or fields.get("product_name") or "").strip()
        url = str(fields.get("url") or "").strip()
        text = f"{platform} {target} {url}"
        if not status or not is_tk_source_text(text):
            continue
        if status not in BLOCKER_STATUSES and not status.startswith("pending"):
            continue
        candidates.append(
            {
                "status": status,
                "platform": normalize_platform_name(platform),
                "target": target,
                "url": url,
                "next_step": fields.get("next_step") or "Open with the already logged-in browser/session, capture visible product/video/creator rows, and rerun TK health check.",
                "source_id": fields.get("source_id") or "",
                "priority": priority_for_recovery(platform, status, target),
            }
        )
    candidates.sort(key=lambda item: (-int(item.get("priority") or 0), str(item.get("platform") or ""), str(item.get("target") or "")))
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in candidates:
        key = (str(item.get("platform") or ""), str(item.get("url") or ""), str(item.get("target") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= 20:
            break
    return deduped


def priority_for_recovery(platform: str, status: str, target: str) -> int:
    text = f"{platform} {status} {target}".lower()
    priority = 70
    if "tiktok shop buyer" in text:
        priority += 30
    elif "tiktok" in text:
        priority += 25
    elif "fastmoss" in text:
        priority += 20
    elif "kalodata" in text:
        priority += 20
    if "verification" in text or "manual_gate" in text or "logged_in" in text:
        priority += 8
    if "video" in text or "creator" in text or "达人" in text:
        priority += 6
    return min(priority, 100)


def build_evidence_recovery_plan(
    priority_blockers: list[dict[str, Any]],
    category_health: dict[str, Any],
    source_health: dict[str, Any],
    evidence_health: dict[str, Any],
) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    latest_stalled = int(evidence_health.get("latest_hard_tk_delta") or 0) <= 0 and int(evidence_health.get("latest_video_delta") or 0) <= 0
    if latest_stalled:
        tasks.append(
            build_recovery_task(
                "latest_round_stalled",
                "TikTok Evidence Collector",
                "Latest round added no hard TK product/video evidence",
                "TikTok / FastMoss / Kalodata",
                "",
                100,
                "Start from already logged-in FastMoss/Kalodata/TikTok Shop buyer pages and capture product/video/creator rows.",
            )
        )
    vendor_sources = source_health.get("vendor_and_tk_sources") if isinstance(source_health.get("vendor_and_tk_sources"), dict) else {}
    for platform in ["TikTok Shop", "FastMoss", "Kalodata"]:
        item = vendor_sources.get(platform, {})
        real_rows = int(item.get("real_rows") or 0)
        pending = int(item.get("pending_or_blocked") or 0)
        if real_rows < 5 or (platform == "Kalodata" and real_rows == 0):
            tasks.append(
                build_recovery_task(
                    f"{platform.lower().replace(' ', '_')}_source_gap",
                    "TK Source Collector",
                    f"{platform} needs real product/video/creator rows",
                    platform,
                    default_recovery_url(platform),
                    96 if platform == "TikTok Shop" else 92,
                    f"Current real rows: {real_rows}; pending/blockers: {pending}. Capture visible rank/product/video/creator evidence only.",
                )
            )
    for item in priority_blockers[:8]:
        tasks.append(
            build_recovery_task(
                f"blocked_{stable_id('', item.get('platform'), item.get('url'), item.get('target'))}",
                "TK Evidence Collector",
                str(item.get("target") or "Blocked TK collection task"),
                str(item.get("platform") or "TikTok"),
                str(item.get("url") or ""),
                int(item.get("priority") or 85),
                str(item.get("next_step") or ""),
                status=str(item.get("status") or ""),
            )
        )
    for item in (category_health.get("tk_uncovered_examples") or [])[:6]:
        tasks.append(
            build_recovery_task(
                f"tk_category_{stable_id('', item.get('platform'), item.get('category_path'))}",
                "Product Selection Analyst",
                f"Fill TK category evidence: {item.get('category_path')}",
                str(item.get("platform") or "TikTok Shop"),
                str(item.get("url") or ""),
                84,
                "Open the category/search in a logged-in normal browser when needed, capture visible product cards and video/creator links, then rerun health check.",
            )
        )
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for task in sorted(tasks, key=lambda item: -int(item.get("priority") or 0)):
        key = f"{task.get('platform')}|{task.get('url')}|{task.get('title')}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(task)
        if len(deduped) >= 16:
            break
    return {
        "status": "active" if deduped else "clear",
        "reason": "latest_round_stalled" if latest_stalled else "coverage_or_source_gap",
        "success_gate": "A task only passes after it creates hard platform_ranking_signal, viral_content_signal, or creator/store evidence with product/video/creator URL plus visible metric or rank.",
        "tasks": deduped,
    }


def build_recovery_task(
    task_id: str,
    agent: str,
    title: str,
    platform: str,
    url: str,
    priority: int,
    next_step: str,
    *,
    status: str = "queued",
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "agent": agent,
        "title": title,
        "platform": platform,
        "url": url,
        "priority": min(max(priority, 1), 100),
        "status": status,
        "next_step": next_step,
        "required_success_fields": [
            "product_url or video_url or creator_handle",
            "rank_position or sales or GMV or views or comment_count",
            "visible product title and source platform",
        ],
        "forbidden": [
            "Do not bypass login, slider, CAPTCHA, robots, or license limits.",
            "Do not count homepage/search shell/security check/loading page as evidence.",
            "Do not use Amazon rows as TK evidence.",
        ],
    }


def default_recovery_url(platform: str) -> str:
    if platform == "TikTok Shop":
        return "https://shop.tiktok.com/us?source=product_detail&enter_method=left_panel_logo&first_entrance=video_detail&first_entrance_position=product_card&first_entrance_tt_scene=tt_seo"
    if platform == "FastMoss":
        return "https://www.fastmoss.com/zh/e-commerce/search"
    if platform == "Kalodata":
        return "https://www.kalodata.com/explore"
    return ""


def build_category_depth_health(categories: list[CategoryNode], ranking_records: list[IntakeRecord]) -> dict[str, Any]:
    clean_records = [
        record
        for record in ranking_records
        if not is_verification_page_record(record) and not is_empty_or_weak_selection_record(record) and record_product_name(record) and record_url(record)
    ]
    by_depth: dict[str, int] = {"L1": 0, "L2": 0, "L3_L5": 0}
    coverage: list[dict[str, Any]] = []
    uncovered: list[dict[str, Any]] = []
    tk_nodes = 0
    tk_nodes_with_products = 0
    for category in categories:
        bucket = depth_bucket(category.depth)
        by_depth[bucket] = by_depth.get(bucket, 0) + 1
        matches = [record for record in clean_records if record_matches_category(record, category)]
        tk_match_count = sum(1 for record in matches if is_tk_platform(record))
        if is_tk_category(category):
            tk_nodes += 1
            if tk_match_count:
                tk_nodes_with_products += 1
        row = {
            "platform": category.platform,
            "category_path": category.category_path,
            "depth": category.depth,
            "depth_bucket": bucket,
            "url": category.url,
            "product_record_count": len(matches),
            "tk_product_record_count": tk_match_count,
            "sample_products": [
                {"product_name": record_product_name(record), "url": record_url(record)}
                for record in matches[:3]
            ],
        }
        coverage.append(row)
        if not matches:
            uncovered.append(row)
    l3_nodes = [item for item in coverage if item["depth_bucket"] == "L3_L5"]
    l3_with_products = [item for item in l3_nodes if int(item["product_record_count"] or 0) > 0]
    tk_uncovered = [item for item in uncovered if is_tk_source_text(f"{item['platform']} {item['category_path']}")]
    l3_uncovered = [item for item in uncovered if item["depth_bucket"] == "L3_L5"]
    return {
        "category_nodes": len(categories),
        "depth_counts": by_depth,
        "product_records_available": len(clean_records),
        "covered_category_nodes": len([item for item in coverage if int(item["product_record_count"] or 0) > 0]),
        "uncovered_category_nodes": len(uncovered),
        "l3_l5_nodes": len(l3_nodes),
        "l3_l5_nodes_with_products": len(l3_with_products),
        "tk_category_nodes": tk_nodes,
        "tk_category_nodes_with_products": tk_nodes_with_products,
        "tk_uncovered_examples": [
            {
                "platform": item["platform"],
                "category_path": item["category_path"],
                "depth": item["depth"],
                "url": item["url"],
            }
            for item in tk_uncovered[:10]
        ],
        "l3_l5_uncovered_examples": [
            {
                "platform": item["platform"],
                "category_path": item["category_path"],
                "depth": item["depth"],
                "url": item["url"],
            }
            for item in l3_uncovered[:10]
        ],
        "uncovered_examples": [
            {
                "platform": item["platform"],
                "category_path": item["category_path"],
                "depth": item["depth"],
                "url": item["url"],
            }
            for item in uncovered[:10]
        ],
    }


def build_evidence_health(snapshot: dict[str, Any], runs: list[dict[str, Any]]) -> dict[str, Any]:
    current_real = int(snapshot.get("real_tk_records") or 0)
    current_videos = int(snapshot.get("viral_records") or 0)
    current_creators = int(snapshot.get("creator_records") or 0)
    previous_real = current_real
    previous_videos = current_videos
    previous_creators = current_creators
    if runs:
        first_snapshot = runs[0].get("snapshot") if isinstance(runs[0], dict) else {}
        if isinstance(first_snapshot, dict):
            previous_real = int(first_snapshot.get("real_tk_records") or 0)
            previous_videos = int(first_snapshot.get("viral_records") or 0)
            previous_creators = int(first_snapshot.get("creator_records") or 0)
    latest_previous_real = current_real
    latest_previous_videos = current_videos
    latest_previous_creators = current_creators
    latest_run_started_at = ""
    latest_run_finished_at = ""
    if runs:
        latest_run_started_at = str(runs[-1].get("run_started_at") or "")
        latest_run_finished_at = str(runs[-1].get("run_finished_at") or "")
    if len(runs) >= 2:
        previous_snapshot = runs[-2].get("snapshot") if isinstance(runs[-2], dict) else {}
        if isinstance(previous_snapshot, dict):
            latest_previous_real = int(previous_snapshot.get("real_tk_records") or 0)
            latest_previous_videos = int(previous_snapshot.get("viral_records") or 0)
            latest_previous_creators = int(previous_snapshot.get("creator_records") or 0)
    return {
        "runs_in_window": len(runs),
        "hard_tk_records": current_real,
        "video_records": current_videos,
        "creator_records": current_creators,
        "weak_tk_records": int(snapshot.get("weak_tk_records") or 0),
        "window_hard_tk_delta": current_real - previous_real,
        "window_video_delta": current_videos - previous_videos,
        "window_creator_delta": current_creators - previous_creators,
        "hard_tk_delta": current_real - previous_real,
        "video_delta": current_videos - previous_videos,
        "creator_delta": current_creators - previous_creators,
        "latest_hard_tk_delta": current_real - latest_previous_real,
        "latest_video_delta": current_videos - latest_previous_videos,
        "latest_creator_delta": current_creators - latest_previous_creators,
        "latest_run_started_at": latest_run_started_at,
        "latest_run_finished_at": latest_run_finished_at,
        "minimum_required": {
            "hard_tk_records": 100,
            "video_records": 30,
            "creator_records": 30,
        },
    }


def build_source_health(collection_jobs: list[IntakeRecord], ranking_records: list[IntakeRecord]) -> dict[str, Any]:
    vendor_rows: dict[str, dict[str, int]] = {
        "FastMoss": {"real_rows": 0, "pending_or_blocked": 0},
        "Kalodata": {"real_rows": 0, "pending_or_blocked": 0},
        "TikTok Shop": {"real_rows": 0, "pending_or_blocked": 0},
    }
    for record in ranking_records:
        platform = platform_label(record)
        if platform not in vendor_rows:
            continue
        if is_hard_product_or_video_record(record):
            vendor_rows[platform]["real_rows"] += 1
    for record in collection_jobs:
        fields = record.fields or {}
        platform = normalize_platform_name(str(fields.get("source_platform") or fields.get("platform_list") or fields.get("marketplace") or ""))
        if platform not in vendor_rows:
            continue
        status = str(fields.get("source_status") or fields.get("status") or "")
        if status in BLOCKER_STATUSES or status.startswith("pending"):
            vendor_rows[platform]["pending_or_blocked"] += 1
    return {
        "vendor_and_tk_sources": vendor_rows,
        "policy": "FastMoss/Kalodata/TK seller data should use official API/export/authorized visible capture first. Public crawling is metadata-only and must not bypass login, CAPTCHA, slider, robots or license limits.",
    }




def build_compliant_collection_policy() -> dict[str, Any]:
    return {
        "fastmoss_kalodata": {
            "preferred": ["contract/API", "CSV/export", "logged-in visible capture from existing Chrome/BitBrowser session"],
            "public_crawler": "Only metadata/page availability checks when public and allowed; never treat homepage/search shell as evidence.",
            "required_success_fields": ["product card or ranking row", "product/video/creator URL", "rank/GMV/sales/view metric when visible", "category path or search keyword"],
            "forbidden": ["login bypass", "slider/CAPTCHA bypass", "license bypass", "bulk scraping disallowed paths"],
        },
        "tiktok_seller": {
            "preferred": ["own-store official/partner API", "seller-center report export", "logged-in visible capture after human verification"],
            "allowed": ["own store sales", "orders", "returns", "refunds", "ads", "settlement", "account health"],
            "forbidden": ["competitor private seller data", "auto-login", "verification bypass", "store actions without approval"],
        },
        "tiktok_buyer": {
            "preferred": ["buyer-side product/video pages after normal access", "FastMoss/Kalodata bridge", "official TikTok tools when available"],
            "required_success_fields": ["product URL", "video or creator signal", "visible product title", "buyer-side source link"],
            "forbidden": ["closing verification pages too early", "counting security check pages", "using Amazon as TK replacement"],
        },
    }


def persist_health_records(root: Path, run_date: str, since_hours: int, metrics: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for metric_name, value in [
        ("hard_tk_records", metrics["evidence_health"].get("hard_tk_records", 0)),
        ("video_records", metrics["evidence_health"].get("video_records", 0)),
        ("creator_records", metrics["evidence_health"].get("creator_records", 0)),
        ("collection_blockers", sum(int(v) for v in metrics["blockers"].get("blockers_by_platform", {}).values())),
        ("l3_l5_nodes_with_products", metrics["category_health"].get("l3_l5_nodes_with_products", 0)),
    ]:
        fields = {
            "quality_metric_snapshot_id": stable_id("qms_", run_date, str(since_hours), metric_name),
            "pipeline_area": "tk_supervision",
            "metric_name": metric_name,
            "measured_value": value,
            "measured_at_utc": now,
            "window_hours": since_hours,
            "status": metrics.get("status"),
        }
        append_record(
            root,
            IntakeRecord(
                record_type="quality_metric_snapshot",
                source="tk_supervision_health",
                fields=fields,
                raw_text=json.dumps(fields, ensure_ascii=False),
                score={"priority": 90},
                director_notes=["24h supervision metric. Used to detect stalled TK collection and category coverage gaps."],
                confidence=0.9,
            ),
        )
    for item in metrics.get("bug_flags", [])[:8]:
        fields = {
            "task_queue_id": stable_id("tk_health_task_", run_date, item.get("code", "")),
            "task_type": "tk_supervision_bugfix",
            "target_agent_id": "AI Data Reviewer",
            "task_title": item.get("message", ""),
            "status": "queued",
            "severity": item.get("severity"),
            "source_code": item.get("code"),
            "requires_confirmation": False,
            "automation_level": "L0-L2_read_analyze_queue_only",
            "created_at_utc": now,
        }
        append_record(
            root,
            IntakeRecord(
                record_type="task_queue",
                source="tk_supervision_health",
                fields=fields,
                raw_text=json.dumps(fields, ensure_ascii=False),
                score={"priority": 97 if item.get("severity") == "high" else 88},
                director_notes=["Health check found a blocker. Fix before calling the system production-ready."],
                confidence=0.92,
            ),
        )
    for item in metrics.get("evidence_recovery_plan", {}).get("tasks", [])[:16]:
        fields = {
            "task_queue_id": stable_id("tk_recovery_task_", run_date, item.get("task_id", "")),
            "task_type": "tk_evidence_recovery",
            "target_agent_id": item.get("agent") or "TK Evidence Collector",
            "task_title": item.get("title") or "",
            "status": "queued",
            "platform": item.get("platform") or "",
            "url": item.get("url") or "",
            "priority": item.get("priority") or 80,
            "source_status": item.get("status") or "",
            "next_step": item.get("next_step") or "",
            "required_success_fields": item.get("required_success_fields") or [],
            "forbidden": item.get("forbidden") or [],
            "requires_confirmation": False,
            "automation_level": "L0-L2_read_collect_queue_only",
            "created_at_utc": now,
        }
        append_record(
            root,
            IntakeRecord(
                record_type="task_queue",
                source="tk_supervision_health",
                fields=fields,
                raw_text=json.dumps(fields, ensure_ascii=False),
                score={"priority": int(item.get("priority") or 80)},
                director_notes=["Evidence recovery task generated because TK health check found missing or stalled hard evidence."],
                confidence=0.93,
            ),
        )
    for memory_key, rule in {
        "compliant_fastmoss_kalodata_collection": "FastMoss/Kalodata should use contract/API, export, or logged-in visible capture. Do not count homepage, search shell, loading page, or verification page as evidence.",
        "tk_seller_own_store_only": "TikTok seller-center automation may read own-store data after authorization/export/visible capture only; do not collect competitor private seller data or execute store actions without approval.",
        "category_depth_product_coverage": "Product selection must cover L1/L2 market radar and L3-L5 subcategory product cards; big-category-only reports fail the selection exam.",
        "tk_latest_round_evidence_gate": "Latest-round TK evidence delta must be tracked separately from 24h window totals. If the latest round adds 0 hard product/video/creator evidence, the loop is stalled even when historical totals are nonzero.",
    }.items():
        fields = {
            "memory_key": memory_key,
            "memory_type": "collection_governance",
            "rule": rule,
            "source": "tk_supervision_health",
            "updated_at_utc": now,
        }
        append_record(
            root,
            IntakeRecord(
                record_type="strategy_memory",
                source="tk_supervision_health",
                fields=fields,
                raw_text=json.dumps(fields, ensure_ascii=False),
                score={"priority": 95},
                director_notes=["Governance memory written from supervision health check."],
                confidence=0.94,
            ),
        )




def depth_bucket(depth: int) -> str:
    if depth <= 1:
        return "L1"
    if depth == 2:
        return "L2"
    return "L3_L5"


def is_tk_category(category: CategoryNode) -> bool:
    return is_tk_source_text(f"{category.platform} {category.category_path}")


def is_tk_source_text(value: str) -> bool:
    text = value.lower()
    return any(token in text for token in TK_PLATFORMS)


def is_tk_platform(record: IntakeRecord) -> bool:
    return platform_label(record) in {"FastMoss", "Kalodata", "TikTok Shop"}


def is_hard_product_or_video_record(record: IntakeRecord) -> bool:
    if is_verification_page_record(record) or is_empty_or_weak_selection_record(record):
        return False
    fields = record.fields or {}
    hard_keys = [
        "product_url",
        "video_url",
        "creator_handle",
        "rank_position",
        "sales",
        "gmv",
        "views",
        "shop_name",
    ]
    return bool(record_product_name(record)) and any(str(fields.get(key) or "").strip() for key in hard_keys)


def platform_label(record: IntakeRecord) -> str:
    fields = record.fields or {}
    return normalize_platform_name(str(fields.get("source_platform") or fields.get("marketplace") or fields.get("platform") or ""))


def normalize_platform_name(value: str) -> str:
    text = value.lower()
    if "fastmoss" in text:
        return "FastMoss"
    if "kalodata" in text:
        return "Kalodata"
    if "tiktok" in text:
        return "TikTok Shop"
    if "amazon" in text:
        return "Amazon"
    return value.strip() or "unknown"


def stable_id(prefix: str, *parts: Any) -> str:
    return prefix + sha1("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:18]


def latest_tk_supervision_health_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    if not output_dir.exists():
        return "No TK supervision health report yet.", None
    paths = sorted(output_dir.glob(f"{HEALTH_REPORT_PREFIX}_*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not paths:
        return "No TK supervision health report yet.", None
    path = paths[0]
    return path.read_text(encoding="utf-8"), path


# Keep these definitions last so they override an older report formatter whose
# Chinese text was damaged by an encoding round-trip.
def detect_bug_flags(
    snapshot: dict[str, Any],
    blockers: dict[str, Any],
    category_health: dict[str, Any],
    evidence_health: dict[str, Any],
    source_health: dict[str, Any],
) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    if int(evidence_health.get("runs_in_window") or 0) == 0:
        flags.append({"severity": "high", "code": "no_training_runs", "message": "24小时窗口内没有夜跑记录，需要确认自动化是否仍在运行。"})
    if int(evidence_health.get("latest_hard_tk_delta") or 0) <= 0 and int(evidence_health.get("latest_video_delta") or 0) <= 0:
        flags.append({"severity": "high", "code": "latest_round_no_new_hard_tk_evidence", "message": "最新一轮没有新增硬 TK 商品/视频证据，不能算真实市场数据进步。"})
    if int(snapshot.get("weak_tk_records") or 0) > int(snapshot.get("real_tk_records") or 0):
        flags.append({"severity": "medium", "code": "weak_evidence_overload", "message": "弱 TK 记录多于硬证据，报告必须继续过滤空页、首页、验证页和错品。"})
    if blockers.get("blockers_by_platform"):
        flags.append({"severity": "medium", "code": "collection_blockers_present", "message": "仍有登录、验证、可见采集或抓取失败卡点，需要继续追踪。"})
    if int(category_health.get("l3_l5_nodes") or 0) == 0:
        flags.append({"severity": "high", "code": "missing_subcategory_tree", "message": "类目树缺少 L3-L5 小类目，不能只看大类目。"})
    elif int(category_health.get("l3_l5_nodes_with_products") or 0) < max(1, int(category_health.get("l3_l5_nodes") or 0) // 4):
        flags.append({"severity": "medium", "code": "low_subcategory_product_coverage", "message": "L3-L5 小类目下面的商品记录不足，需要补商品卡和榜单行。"})
    vendor_sources = source_health.get("vendor_and_tk_sources") if isinstance(source_health.get("vendor_and_tk_sources"), dict) else {}
    for platform in ["FastMoss", "Kalodata", "TikTok Shop"]:
        item = vendor_sources.get(platform, {})
        if int(item.get("real_rows") or 0) == 0 and int(item.get("pending_or_blocked") or 0) > 0:
            flags.append({"severity": "medium", "code": f"{platform.lower().replace(' ', '_')}_no_real_rows", "message": f"{platform} 还有待采集/卡点，但没有真实商品或视频行入湖。"})
    return flags


def build_health_report(run_date: str, since_hours: int, metrics: dict[str, Any]) -> str:
    evidence = metrics["evidence_health"]
    category = metrics["category_health"]
    blockers = metrics["blockers"]
    source_health = metrics["source_health"]
    flags = metrics["bug_flags"]
    lines = [
        f"# TK 24小时监督健康自检 - {run_date}",
        "",
        "## 老板结论",
        "",
        f"- 状态：{metrics['status']}",
        f"- 最近 {since_hours} 小时：夜跑 {evidence['runs_in_window']} 轮，硬 TK 证据 {evidence['hard_tk_records']}（窗口新增 {evidence.get('window_hard_tk_delta', evidence.get('hard_tk_delta', 0))}，最新一轮 {evidence.get('latest_hard_tk_delta', 0)}），视频 {evidence['video_records']}（窗口新增 {evidence.get('window_video_delta', evidence.get('video_delta', 0))}，最新一轮 {evidence.get('latest_video_delta', 0)}），达人 {evidence['creator_records']}（窗口新增 {evidence.get('window_creator_delta', evidence.get('creator_delta', 0))}，最新一轮 {evidence.get('latest_creator_delta', 0)}）。",
        f"- 类目覆盖：类目节点 {category['category_nodes']}，L3-L5 小类目 {category['l3_l5_nodes']}，已有商品的小类目 {category['l3_l5_nodes_with_products']}。",
        f"- 卡点：{sum(int(v) for v in blockers.get('blockers_by_platform', {}).values())} 个登录/验证/可见采集/失败卡点。",
        "",
        "## 需要马上盯的点",
        "",
    ]
    if flags:
        for item in flags[:8]:
            lines.append(f"- [{item['severity']}] {item['message']}")
    else:
        lines.append("- 暂无红色卡点，但仍要继续追 TK 视频、达人和商品证据。")
    lines.extend(["", "## 合规采集策略", ""])
    lines.append("- FastMoss / Kalodata：优先 API、合同或导出；其次使用已登录 Chrome 或 BitBrowser 的可见页面采集；不能绕过登录、滑块、验证码、授权或许可范围。")
    lines.append("- TikTok 卖家后台：只采自己的店铺销售、订单、退货、广告、结算和账号健康；不采竞品私有卖家数据，不自动改店铺。")
    lines.append("- TikTok 买家端：必须有商品页、视频、达人、可见标题和来源链接；安全验证页、首页、搜索空壳不算证据。")
    lines.extend(["", "## 平台源状态", ""])
    for platform, item in source_health.get("vendor_and_tk_sources", {}).items():
        lines.append(f"- {platform}: 真实行 {item.get('real_rows', 0)}，待采/卡点 {item.get('pending_or_blocked', 0)}")
    recovery_tasks = metrics.get("evidence_recovery_plan", {}).get("tasks", [])
    lines.extend(["", "## 下一轮补证据队列", ""])
    if recovery_tasks:
        for item in recovery_tasks[:10]:
            lines.append(
                f"- P{item.get('priority')} / {item.get('platform')} / {item.get('agent')}: "
                f"{item.get('title')} -> {item.get('url') or '无固定入口'}"
            )
    else:
        lines.append("- 暂无补证据任务。")
    lines.extend(["", "## 小类目缺口样例", ""])
    examples = category.get("tk_uncovered_examples") or category.get("l3_l5_uncovered_examples") or category.get("uncovered_examples") or []
    if not examples:
        lines.append("- 暂无未覆盖样例。")
    for item in examples[:6]:
        lines.append(f"- L{item.get('depth')} {item.get('platform')} / {item.get('category_path')} -> 还缺商品卡或榜单行")
    lines.extend(["", "<details>", "<summary>详细卡点</summary>", ""])
    for item in blockers.get("examples", []):
        lines.append(f"- {item.get('platform')} | {item.get('status')} | {item.get('target')} | {item.get('url')}")
    lines.extend(["", "</details>"])
    return "\n".join(lines).rstrip() + "\n"
