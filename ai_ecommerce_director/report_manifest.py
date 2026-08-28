from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .types import IntakeRecord


def write_report_manifest(
    root: Path,
    report_type: str,
    run_date: str,
    report_paths: dict[str, Path | str],
    records: Iterable[IntakeRecord],
    *,
    parser_version: str,
    scope: dict[str, Any] | None = None,
    exclusion_summary: dict[str, Any] | None = None,
    seller_safe_summary: dict[str, Any] | None = None,
    input_record_limit_per_type: int = 200,
) -> Path:
    root = root.resolve()
    record_list = list(records)
    path = root / "outputs" / f"report_manifest_{report_type}_{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "report_id": stable_report_id(report_type, run_date),
        "report_type": report_type,
        "run_date": run_date,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "parser_version": parser_version,
        "report_paths": {key: path_for_manifest(root, value) for key, value in report_paths.items()},
        "scope": scope or {},
        "input_record_counts": input_record_counts(record_list),
        "input_records": input_record_ids(record_list, input_record_limit_per_type),
        "input_record_limit_per_type": input_record_limit_per_type,
        "source_batches": source_batch_summary(record_list),
        "exclusion_summary": exclusion_summary or {},
        "seller_safe_summary": seller_safe_summary or {},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def stable_report_id(report_type: str, run_date: str) -> str:
    clean_type = "_".join(str(report_type or "report").lower().split())
    clean_date = str(run_date or "unknown").replace("-", "")
    return f"rpt_{clean_type}_{clean_date}"


def path_for_manifest(root: Path, value: Path | str) -> str:
    path = Path(value)
    try:
        return path.resolve().relative_to(root).as_posix()
    except (OSError, ValueError):
        return str(value)


def input_record_counts(records: Iterable[IntakeRecord]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        counts[record.record_type] += 1
    return dict(sorted(counts.items()))


def input_record_ids(records: Iterable[IntakeRecord], limit_per_type: int) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for record in records:
        ids = grouped[record.record_type]
        if len(ids) < limit_per_type:
            ids.append(record.record_id)
    return dict(sorted(grouped.items()))


def source_batch_summary(records: Iterable[IntakeRecord], limit: int = 80) -> list[dict[str, Any]]:
    batches: dict[str, dict[str, Any]] = {}
    for record in records:
        fields = record.fields or {}
        metadata = record.metadata or {}
        platform = first_text(fields, "marketplace", "source_platform", "platform", "platform_list")
        source_url = first_text(fields, "source_url", "url", "page_url", "product_url", "video_url")
        source_id = first_text(fields, "source_id", "automation_source_id", "collection_job_id")
        import_batch_id = first_text(metadata, "import_batch_id", "batch_id", "automation_run_id")
        key_parts = [record.record_type, record.source, platform, source_url, source_id, import_batch_id]
        key = "|".join(key_parts)
        batch_id = "src_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
        if batch_id not in batches:
            batches[batch_id] = {
                "source_batch_id": batch_id,
                "record_type": record.record_type,
                "source": record.source,
                "platform": platform,
                "source_url": source_url,
                "source_id": source_id,
                "import_batch_id": import_batch_id,
                "record_count": 0,
                "first_created_at": record.created_at,
                "last_created_at": record.created_at,
            }
        batch = batches[batch_id]
        batch["record_count"] += 1
        batch["first_created_at"] = min(str(batch["first_created_at"]), record.created_at)
        batch["last_created_at"] = max(str(batch["last_created_at"]), record.created_at)
    return sorted(batches.values(), key=lambda item: (-int(item["record_count"]), item["source_batch_id"]))[:limit]


def first_text(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (str, int, float, bool)) and str(value).strip():
            return str(value).strip()
    return ""
