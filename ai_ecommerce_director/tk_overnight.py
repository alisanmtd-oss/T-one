from __future__ import annotations

import json
from hashlib import sha1
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .browser_operator import run_browser_operator
from .ecommerce_director_agent import run_ecommerce_director_analysis
from .idle_learning import run_idle_learning
from .operation_closure import run_operation_closure_analysis
from .platform_autopilot import load_platform_autopilot_config, run_platform_source
from .product_target_report import run_product_target_reports
from .product_targets import (
    build_tiktok_buyer_product_target_sources,
    build_tiktok_selection_bridge_product_target_sources,
    load_product_targets,
)
from .selection_intelligence import run_selection_intelligence
from .selection_meeting import run_selection_meeting
from .storage import append_record, read_records
from .tk_case_learning import run_tk_case_learning_analysis, seed_tk_case_learning_pool
from .types import IntakeRecord
from .visual_creative import run_visual_creative_director


TK_OVERNIGHT_REPORT_PREFIX = "tk_overnight_report"


@dataclass(slots=True)
class TkOvernightResult:
    run_date: str
    statuses: list[dict[str, Any]]
    report: str
    report_path: Path
    json_path: Path
    employee_scores: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "statuses": self.statuses,
            "report": self.report,
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
            "employee_scores": self.employee_scores,
        }


@dataclass(slots=True)
class TkOvernightReviewResult:
    run_date: str
    rounds: int
    report: str
    report_path: Path
    json_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "rounds": self.rounds,
            "report": self.report,
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
        }


def run_tk_overnight_round(root: Path, run_date: str | None = None, *, case_limit: int = 300) -> TkOvernightResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    run_started_at = datetime.now(timezone.utc).isoformat()
    sources = build_tk_overnight_sources(root)
    statuses: list[dict[str, Any]] = []

    for source in sources:
        status, _records = run_platform_source(
            root,
            source,
            report_date,
            open_browser=False,
            collect_public=True,
        )
        statuses.append(status)

    case_result = seed_tk_case_learning_pool(root, limit=case_limit, run_date=report_date)
    browser_result = run_browser_operator(root, report_date)
    visual_result = run_visual_creative_director(root, report_date)
    case_analysis = run_tk_case_learning_analysis(root, report_date)
    target_reports = run_product_target_reports(root, report_date)
    selection_result = run_selection_intelligence(root, report_date)
    meeting_result = run_selection_meeting(root, report_date)

    snapshot = build_tk_snapshot(root)
    employee_scores = score_ai_employees(snapshot)
    retraining_tasks = build_employee_retraining_plan(root, snapshot, employee_scores, report_date)
    idle_learning_result = run_idle_learning(root, report_date)
    closure_result = run_operation_closure_analysis(root, report_date)
    director_agent_result = run_ecommerce_director_analysis(root, build_tk_overnight_agent_payload(report_date, snapshot, employee_scores, retraining_tasks))
    run_finished_at = datetime.now(timezone.utc).isoformat()
    report = build_tk_overnight_report(
        root=root,
        run_date=report_date,
        snapshot=snapshot,
        statuses=statuses,
        employee_scores=employee_scores,
        case_result=case_result.to_dict(),
        browser_result=browser_result.to_dict(),
        visual_report_path=str(visual_result.report_path),
        case_analysis=case_analysis.to_dict(),
        target_reports=target_reports.to_dict(),
        selection_report_path=str(selection_result.report_path),
        meeting_report_path=str(meeting_result.report_path),
        idle_learning_report_path=str(idle_learning_result.report_path),
        operation_closure_report_path=str(closure_result.report_path),
        director_agent_report_path=str(director_agent_result.report_path),
        director_agent_run_id=director_agent_result.agent_run_id,
        retraining_tasks=retraining_tasks,
    )
    report_path = write_tk_overnight_report(root, report_date, report)
    json_path = write_tk_overnight_json(
        root,
        report_date,
        {
            "run_date": report_date,
            "run_started_at": run_started_at,
            "run_finished_at": run_finished_at,
            "snapshot": snapshot,
            "statuses": statuses,
            "employee_scores": employee_scores,
            "case_result": case_result.to_dict(),
            "browser_result": browser_result.to_dict(),
            "visual_report_path": str(visual_result.report_path),
            "case_analysis": case_analysis.to_dict(),
            "target_reports": target_reports.to_dict(),
            "selection_report_path": str(selection_result.report_path),
            "meeting_report_path": str(meeting_result.report_path),
            "idle_learning_report_path": str(idle_learning_result.report_path),
            "operation_closure_report_path": str(closure_result.report_path),
            "director_agent_report_path": str(director_agent_result.report_path),
            "director_agent_run_id": director_agent_result.agent_run_id,
            "retraining_tasks": retraining_tasks,
        },
    )
    append_tk_overnight_run_log(
        root,
        {
            "run_date": report_date,
            "run_started_at": run_started_at,
            "run_finished_at": run_finished_at,
            "snapshot": snapshot,
            "employee_scores": employee_scores,
            "retraining_tasks": retraining_tasks,
            "report_path": str(report_path),
            "json_path": str(json_path),
            "director_agent_run_id": director_agent_result.agent_run_id,
            "director_agent_report_path": str(director_agent_result.report_path),
            "status_counts": count_statuses(statuses),
        },
    )
    return TkOvernightResult(report_date, statuses, report, report_path, json_path, employee_scores)


def run_tk_overnight_review(root: Path, run_date: str | None = None, *, since_hours: int = 12) -> TkOvernightReviewResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    runs = read_tk_overnight_run_log(root, since_hours=since_hours)
    retake_submissions = latest_employee_retake_submissions(root)
    report = build_tk_overnight_review_report(report_date, runs, since_hours, retake_submissions=retake_submissions)
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    window_label = review_window_label(since_hours)
    report_path = output_dir / f"tk_overnight_{window_label}_review_{report_date}.md"
    json_path = output_dir / f"tk_overnight_{window_label}_review_{report_date}.json"
    report_path.write_text(report, encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "run_date": report_date,
                "since_hours": since_hours,
                "window_label": window_label,
                "rounds": runs,
                "report_path": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return TkOvernightReviewResult(report_date, len(runs), report, report_path, json_path)


def review_window_label(since_hours: int) -> str:
    if since_hours <= 0:
        return "all"
    return f"{since_hours}h"


def read_tk_overnight_run_log(root: Path, *, since_hours: int | None = None) -> list[dict[str, Any]]:
    path = root / "outputs" / "tk_overnight_run_log.jsonl"
    if not path.exists():
        return []
    cutoff = None
    if since_hours:
        cutoff = datetime.now(timezone.utc).timestamp() - since_hours * 3600
    runs: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            item = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if cutoff:
            started = parse_iso_datetime(str(item.get("run_started_at") or ""))
            if started and started.timestamp() < cutoff:
                continue
        runs.append(item)
    return runs


def parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def latest_employee_retake_submissions(root: Path, *, limit: int = 12) -> list[dict[str, Any]]:
    latest_by_employee: dict[str, dict[str, Any]] = {}
    records = [
        record
        for record in read_records(root, "agent_review")
        if str(record.fields.get("review_type") or "").startswith("retake_submission")
    ]
    records.sort(key=lambda item: item.created_at, reverse=True)
    for record in records:
        fields = record.fields
        employee = str(fields.get("employee") or "").strip()
        if not employee or employee in latest_by_employee:
            continue
        latest_by_employee[employee] = {
            "employee": employee,
            "review_type": fields.get("review_type") or "",
            "score_after_retake": fields.get("score_after_retake") or record.score.get("priority") or "-",
            "status": fields.get("status") or "submitted",
            "submission_path": short_report_path(root, str(fields.get("submission_path") or "")),
            "created_at": fields.get("created_at") or record.created_at,
        }
        if len(latest_by_employee) >= limit:
            break
    return list(latest_by_employee.values())


def short_report_path(root: Path, raw_path: str) -> str:
    if not raw_path:
        return ""
    try:
        return str(Path(raw_path).resolve().relative_to(root.resolve())).replace("\\", "/")
    except (OSError, ValueError):
        marker = "outputs"
        normalized = raw_path.replace("\\", "/")
        if marker in normalized:
            return normalized[normalized.rfind(marker) :]
        return Path(normalized).name


def build_tk_overnight_review_report(
    run_date: str,
    runs: list[dict[str, Any]],
    since_hours: int,
    *,
    retake_submissions: list[dict[str, Any]] | None = None,
) -> str:
    latest = runs[-1] if runs else {}
    previous = runs[-2] if len(runs) >= 2 else {}
    latest_snapshot = latest.get("snapshot") if isinstance(latest.get("snapshot"), dict) else {}
    previous_snapshot = previous.get("snapshot") if isinstance(previous.get("snapshot"), dict) else {}
    max_real = max((int((run.get("snapshot") or {}).get("real_tk_records") or 0) for run in runs), default=0)
    max_viral = max((int((run.get("snapshot") or {}).get("viral_records") or 0) for run in runs), default=0)
    max_creators = max((int((run.get("snapshot") or {}).get("creator_records") or 0) for run in runs), default=0)
    latest_real = int(latest_snapshot.get("real_tk_records") or 0)
    latest_viral = int(latest_snapshot.get("viral_records") or 0)
    latest_creators = int(latest_snapshot.get("creator_records") or 0)
    real_delta = int(latest_snapshot.get("real_tk_records") or 0) - int(previous_snapshot.get("real_tk_records") or 0)
    viral_delta = int(latest_snapshot.get("viral_records") or 0) - int(previous_snapshot.get("viral_records") or 0)
    creator_delta = int(latest_snapshot.get("creator_records") or 0) - int(previous_snapshot.get("creator_records") or 0)
    weak_delta = int(latest_snapshot.get("weak_tk_records") or 0) - int(previous_snapshot.get("weak_tk_records") or 0)
    effective_rounds = count_effective_hard_evidence_rounds(runs)
    total_status_counts: dict[str, int] = {}
    for run in runs:
        counts = run.get("status_counts") if isinstance(run.get("status_counts"), dict) else {}
        for key, value in counts.items():
            total_status_counts[str(key)] = total_status_counts.get(str(key), 0) + int(value or 0)
    employee_scores = score_ai_employees(latest_snapshot) if latest_snapshot else []
    latest_retraining_tasks = latest.get("retraining_tasks") if isinstance(latest.get("retraining_tasks"), list) else []
    passed = latest_real >= 30 and latest_viral >= 10 and latest_creators >= 5
    if passed and real_delta <= 0 and viral_delta <= 0 and creator_delta <= 0 and weak_delta > 0:
        decision = "PASSABLE_BUT_STALLED_ON_WEAK_CAPTURES"
    elif passed and real_delta <= 0 and viral_delta <= 0 and creator_delta <= 0:
        decision = "PASSABLE_BUT_NO_NEW_HARD_EVIDENCE"
    else:
        decision = "PASSABLE_TK_STUDY" if passed else "RETAKE_TK_DATA_COLLECTION"
    lines = [
        f"# TK {since_hours}-Hour Product Selection Review - {run_date}",
        "",
        "## Boss Verdict",
        "",
        f"- Decision: {decision}.",
        f"- Review window: last {since_hours} hours.",
        f"- Rounds logged: {len(runs)}.",
        f"- Latest run started: {latest.get('run_started_at') or '-'}",
        f"- Latest run finished: {latest.get('run_finished_at') or '-'}",
        "",
        "## Evidence Scoreboard",
        "",
        f"- Latest strict real TK evidence rows: {latest_real}.",
        f"- Latest strict TK viral video rows: {latest_viral}.",
        f"- Latest strict creator/store rows: {latest_creators}.",
        f"- Historical high real/video/creator rows: {max_real}/{max_viral}/{max_creators}.",
        f"- Latest weak/empty captures: {latest_snapshot.get('weak_tk_records', 0)}.",
        f"- Latest hard-evidence delta: real {real_delta:+d}, video {viral_delta:+d}, creator {creator_delta:+d}.",
        f"- Latest weak-capture delta: {weak_delta:+d}.",
        f"- Effective hard-evidence rounds: {effective_rounds}/{len(runs)}.",
        f"- Latest login/verification/manual blockers: {latest_snapshot.get('blockers', 0)}.",
        f"- Latest pending TK collection jobs: {latest_snapshot.get('collection_jobs', 0)}.",
        "",
        "## Source Status Totals",
        "",
    ]
    if total_status_counts:
        for key, value in sorted(total_status_counts.items()):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- No source statuses logged yet.")
    lines.extend(["", "## AI Employee Final Scores", ""])
    if employee_scores:
        for item in employee_scores:
            lines.append(f"- {item.get('employee')}: {item.get('score')}/100 ({item.get('grade')}) - {item.get('note')}")
    else:
        lines.append("- No employee scores logged yet.")
    lines.extend(["", "## Retake Tasks I Assigned", ""])
    if latest_retraining_tasks:
        for task in latest_retraining_tasks[:12]:
            lines.append(f"- {task.get('target_agent_id')}: {task.get('task_title')} -> {task.get('expected_output')}")
    else:
        lines.append("- No retake tasks logged in the latest round.")
    lines.extend(["", "## Retake Papers Submitted", ""])
    if retake_submissions:
        for item in retake_submissions[:12]:
            lines.append(
                f"- {item.get('employee')}: {item.get('score_after_retake')}/100 "
                f"({item.get('status')}) - {item.get('submission_path')}"
            )
    else:
        lines.append("- No retake papers submitted yet.")
    lines.extend(
        [
            "",
            "## Hard Truth",
            "",
        ]
    )
    if passed:
        lines.append("- The TK loop has enough early hard evidence to enter a multi-AI selection meeting.")
        if decision == "PASSABLE_BUT_STALLED_ON_WEAK_CAPTURES":
            lines.append("- But the latest round only increased weak/empty captures. This is not real progress; keep collecting logged-in FastMoss/Kalodata/TikTok video evidence.")
        elif decision == "PASSABLE_BUT_NO_NEW_HARD_EVIDENCE":
            lines.append("- But the latest round did not add new hard TK product/video/creator evidence. Treat this as training progress, not market-data progress.")
    else:
        lines.append("- This is not a passing TK selection result yet. The system must keep collecting real TK product/video/creator evidence.")
        lines.append("- Amazon rows, generic tool homepages, loading pages, and scripts without real TK video evidence remain soft or weak records.")
    lines.extend(
        [
            "",
            "## Next Manual Gates",
            "",
            "- Use already logged-in Chrome / BitBrowser / selection-tool sessions for FastMoss, Kalodata and TikTok Shop buyer-side pages.",
            "- If TikTok verification appears, keep the page open for human verification, then rerun capture.",
            "- After real video links appear, every video must produce hook, shot timeline, edit logic, scene, emotion, comments, creator fit, owned-account script and influencer script.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def count_effective_hard_evidence_rounds(runs: list[dict[str, Any]]) -> int:
    count = 0
    previous_real = 0
    previous_viral = 0
    previous_creator = 0
    for run in runs:
        snapshot = run.get("snapshot") if isinstance(run.get("snapshot"), dict) else {}
        real = int(snapshot.get("real_tk_records") or 0)
        viral = int(snapshot.get("viral_records") or 0)
        creator = int(snapshot.get("creator_records") or 0)
        if real > previous_real or viral > previous_viral or creator > previous_creator:
            count += 1
        previous_real = real
        previous_viral = viral
        previous_creator = creator
    return count


def append_tk_overnight_run_log(root: Path, payload: dict[str, Any]) -> Path:
    path = root / "outputs" / "tk_overnight_run_log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    return path


def count_statuses(statuses: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for status in statuses:
        key = str(status.get("status") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def latest_tk_overnight_payload(root: Path) -> tuple[dict[str, Any], Path | None]:
    output_dir = root / "outputs"
    if not output_dir.exists():
        return {}, None
    paths = sorted(output_dir.glob(f"{TK_OVERNIGHT_REPORT_PREFIX}_*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(payload, dict):
            return payload, path
    return {}, None


def latest_tk_overnight_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    if not output_dir.exists():
        return "No TK overnight report yet.", None
    paths = sorted(output_dir.glob(f"{TK_OVERNIGHT_REPORT_PREFIX}_*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in paths:
        try:
            return path.read_text(encoding="utf-8"), path
        except OSError:
            continue
    return "No TK overnight report yet.", None


def build_tk_overnight_sources(root: Path) -> list[dict[str, Any]]:
    config_sources = []
    config = load_platform_autopilot_config(root)
    raw_sources = config.get("sources") if isinstance(config.get("sources"), list) else []
    for source in raw_sources:
        if isinstance(source, dict) and source.get("enabled", True) and source_is_tk_related(source):
            config_sources.append(source)
    product_sources = [
        *build_tiktok_selection_bridge_product_target_sources(root),
        *build_tiktok_buyer_product_target_sources(root),
    ]
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in [*config_sources, *product_sources]:
        source_id = str(source.get("id") or source.get("url") or source.get("name") or "")
        if not source_id or source_id in seen:
            continue
        seen.add(source_id)
        enriched = dict(source)
        enriched.setdefault("enabled", True)
        enriched.setdefault("keep_open_on_gate", True)
        enriched.setdefault("keep_open_after_run", True)
        enriched.setdefault("verification_wait_seconds", 900)
        sources.append(enriched)
    return sources


def source_is_tk_related(source: dict[str, Any]) -> bool:
    haystack = json.dumps(source, ensure_ascii=False).lower()
    return any(token in haystack for token in ["tiktok", "tik tok", "fastmoss", "kalodata", "tk shop"])


def build_tk_snapshot(root: Path) -> dict[str, Any]:
    records = read_records(root)
    targets = [
        target
        for target in load_product_targets(root).get("targets", [])
        if isinstance(target, dict) and target.get("enabled", True)
    ]
    tk_records = [record for record in records if record_is_tk_related(record)]
    collection_jobs = [record for record in tk_records if record.record_type == "collection_job"]
    blockers = [record for record in collection_jobs if job_is_blocked(record)]
    real_candidates = [record for record in tk_records if record.record_type != "collection_job" and not job_is_blocked(record)]
    weak_tk = [record for record in real_candidates if is_weak_or_empty_tk_evidence(record)]
    hard_tk = [record for record in real_candidates if record not in weak_tk and is_hard_tk_evidence(record)]
    soft_tk = [record for record in real_candidates if record not in weak_tk and record not in hard_tk]
    real_tk = hard_tk
    ranking = [record for record in real_tk if record.record_type == "platform_ranking_signal"]
    viral = [
        record
        for record in records
        if record.record_type == "viral_content_signal" and record_is_tk_related(record) and is_valid_tk_video_evidence(record)
    ]
    breakdowns = [
        record
        for record in records
        if record.record_type == "video_breakdown" and record_is_tk_related(record) and is_valid_tk_video_evidence(record)
    ]
    scripts = [record for record in records if record.record_type == "video_script" and record_is_tk_related(record)]
    creators = [
        record
        for record in records
        if record.record_type in {"creator_spike_event", "influencer_cooperation", "influencer_profile", "store_metric_snapshot"}
        and record_is_tk_related(record)
        and is_valid_tk_creator_or_store_evidence(record)
    ]
    bridge_jobs = [
        record
        for record in collection_jobs
        if any(token in json.dumps(record.fields, ensure_ascii=False).lower() for token in ["fastmoss", "kalodata"])
    ]
    buyer_jobs = [
        record
        for record in collection_jobs
        if any(token in json.dumps(record.fields, ensure_ascii=False).lower() for token in ["buyer_video", "tiktok video", "shop.tiktok.com"])
    ]
    links = latest_tk_links([*real_tk, *collection_jobs])
    return {
        "enabled_targets": len(targets),
        "target_names": [str(target.get("name") or "") for target in targets],
        "tk_records": len(tk_records),
        "real_tk_records": len(real_tk),
        "weak_tk_records": len(weak_tk),
        "soft_tk_records": len(soft_tk),
        "tk_ranking_records": len(ranking),
        "viral_records": len(viral),
        "video_breakdowns": len(breakdowns),
        "video_scripts": len(scripts),
        "creator_records": len(creators),
        "collection_jobs": len(collection_jobs),
        "bridge_jobs": len(bridge_jobs),
        "buyer_jobs": len(buyer_jobs),
        "blockers": len(blockers),
        "latest_links": links[:12],
    }


def record_is_tk_related(record: Any) -> bool:
    fields = getattr(record, "fields", {}) or {}
    text = " ".join(
        str(fields.get(key) or "")
        for key in [
            "source_platform",
            "marketplace",
            "platform",
            "platform_list",
            "data_category",
            "ranking_type",
            "url",
            "page_url",
            "product_url",
            "video_url",
            "profile_url",
            "collection_target",
            "bridge_provider",
        ]
    ).lower()
    text = f"{getattr(record, 'source', '')} {text}".lower()
    return any(token in text for token in ["tiktok", "tik tok", "tk shop", "fastmoss", "kalodata"])


def job_is_blocked(record: Any) -> bool:
    fields = getattr(record, "fields", {}) or {}
    text = " ".join(
        [
            str(fields.get("source_status") or ""),
            str(fields.get("collection_status") or ""),
            str(fields.get("source_reason") or ""),
            str(fields.get("next_step") or ""),
        ]
    ).lower()
    return any(token in text for token in ["verification", "captcha", "login", "logged_in_capture_required", "manual_gate", "blocked"])


def is_weak_or_empty_tk_evidence(record: Any) -> bool:
    fields = getattr(record, "fields", {}) or {}
    metadata = getattr(record, "metadata", {}) or {}
    page_text = str(fields.get("page_text") or fields.get("visible_growth_signal") or "").lower()
    validation = metadata.get("platform_autopilot_validation") if isinstance(metadata, dict) else None
    product_match = metadata.get("product_match") if isinstance(metadata, dict) else None
    if any(token in page_text for token in ["暂无数据", "\u6682\u65e0\u6570\u636e", "loading", "no data", "not found"]):
        return True
    if isinstance(validation, dict) and validation.get("status") == "needs_review":
        return True
    if isinstance(product_match, dict) and product_match.get("status") == "different_product":
        return True
    title = str(fields.get("page_title") or fields.get("product_name") or "").lower()
    if any(token in title for token in ["fastmoss", "kalodata"]) and not any(
        key in fields
        for key in [
            "rank_position",
            "sales",
            "gmv",
            "sales_7d_visible",
            "gmv_7d_visible",
            "total_sales_visible",
            "creator_handle",
            "video_url",
            "product_url",
        ]
    ):
        return True
    return False


def is_hard_tk_evidence(record: Any) -> bool:
    record_type = str(getattr(record, "record_type", "") or "")
    if record_type not in {
        "platform_ranking_signal",
        "viral_content_signal",
        "creator_spike_event",
        "influencer_cooperation",
        "influencer_profile",
        "store_metric_snapshot",
        "review_insight",
        "hot_link",
    }:
        return False
    fields = getattr(record, "fields", {}) or {}
    if record_type == "viral_content_signal":
        if is_valid_tk_video_evidence(record):
            return True
        # A real product/sales row (e.g. a fed FastMoss/Kalodata/TikTok Shop row)
        # can be classified as viral_content_signal even though it is not a video.
        # If it carries real commercial signals (gmv/sales/views/product url), still
        # count it as hard evidence instead of discarding it, so fed real data moves
        # the real_tk_records number. Fall through to the hard-signal check below.
    elif record_type in {"creator_spike_event", "influencer_cooperation", "influencer_profile", "store_metric_snapshot"}:
        return is_valid_tk_creator_or_store_evidence(record)
    hard_keys = [
        "rank_position",
        "rank",
        "sales",
        "sales_count",
        "gmv",
        "revenue",
        "price",
        "price_visible",
        "product_url",
        "shop_name",
        "store_name",
        "comment_count",
        "view_count",
        "views",
        "current_views",
        "latest_video_views",
        "comment_insights",
        "sales_7d_visible",
        "gmv_7d_visible",
        "total_sales_visible",
        "total_gmv_visible",
        "creator_order_rate_visible",
        "store_sales_visible",
    ]
    if any(str(fields.get(key) or "").strip() for key in hard_keys):
        return True
    links = fields.get("page_links")
    if isinstance(links, list):
        return any("shop.tiktok.com" in json.dumps(link, ensure_ascii=False).lower() for link in links if isinstance(link, dict))
    return False


def is_valid_tk_video_evidence(record: Any) -> bool:
    fields = getattr(record, "fields", {}) or {}
    url = str(fields.get("video_url") or first_url(fields) or "").strip()
    if is_search_only_tk_url(url):
        return False
    if is_direct_tk_video_url(url):
        return True
    if is_tiktok_shop_product_video_row(record):
        return True
    if str(getattr(record, "record_type", "") or "") == "video_breakdown" and (
        fields.get("shot_timeline") or fields.get("hook_type") or fields.get("viral_reason") or fields.get("why_it_works")
    ):
        lower_url = url.lower()
        return "shop.tiktok.com/view/product/" in lower_url or "shop.tiktok.com/us/pdp/" in lower_url
    return False


def is_valid_tk_creator_or_store_evidence(record: Any) -> bool:
    fields = getattr(record, "fields", {}) or {}
    record_type = str(getattr(record, "record_type", "") or "")
    url = str(fields.get("video_url") or first_url(fields) or "").strip()
    if is_search_only_tk_url(url):
        return False
    if record_type == "store_metric_snapshot":
        return bool(str(fields.get("store_name") or fields.get("shop_name") or "").strip())
    if is_tiktok_shop_product_video_row(record):
        return True
    return bool(str(fields.get("creator_handle") or fields.get("profile_url") or fields.get("store_name") or "").strip())


def is_direct_tk_video_url(url: str) -> bool:
    lower = url.lower()
    return (
        ("tiktok.com/@" in lower and "/video/" in lower)
        or "m.tiktok.com/v/" in lower
        or "tikwm.com/video/" in lower
        or "douyin.com/" in lower
        or ("fastmoss.com/" in lower and "/media-source/video/" in lower)
    )


def is_search_only_tk_url(url: str) -> bool:
    lower = url.lower()
    return "tiktok.com/search" in lower or "/search/video" in lower


def is_tiktok_shop_product_video_row(record: Any) -> bool:
    fields = getattr(record, "fields", {}) or {}
    url = str(fields.get("video_url") or first_url(fields) or "").lower()
    category = str(fields.get("data_category") or "").lower()
    has_video_metric = any(str(fields.get(key) or "").strip() for key in ["views", "view_count", "latest_video_views"])
    has_creator = bool(str(fields.get("creator_handle") or "").strip())
    is_product_page = "shop.tiktok.com/view/product/" in url or "shop.tiktok.com/us/pdp/" in url
    return is_product_page and has_creator and has_video_metric and "video" in category


def latest_tk_links(records: list[Any]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for record in sorted(records, key=lambda item: link_priority(item)):
        fields = getattr(record, "fields", {}) or {}
        url = first_url(fields)
        if not url or url in seen:
            continue
        seen.add(url)
        links.append(
            {
                "type": str(getattr(record, "record_type", "") or ""),
                "platform": str(fields.get("source_platform") or fields.get("marketplace") or ""),
                "title": compact(str(fields.get("product_name") or fields.get("product_title") or fields.get("page_title") or fields.get("collection_target") or url), 120),
                "url": url,
            }
        )
        if len(links) >= 20:
            break
    return links


def link_priority(record: Any) -> tuple[int, str]:
    fields = getattr(record, "fields", {}) or {}
    text = json.dumps(fields, ensure_ascii=False).lower()
    created = str(getattr(record, "created_at", "") or "")
    if str(getattr(record, "record_type", "") or "") == "collection_job":
        return (9, created)
    if is_valid_tk_video_evidence(record):
        return (0, created)
    if str(getattr(record, "record_type", "") or "") == "platform_ranking_signal" and any(
        token in text for token in ["fastmoss", "kalodata", "shop.tiktok.com", "tiktok shop"]
    ):
        return (1, created)
    if is_valid_tk_creator_or_store_evidence(record):
        return (2, created)
    if fields.get("product_target_id") and any(token in text for token in ["fastmoss", "kalodata", "tiktok", "shop.tiktok.com"]):
        return (3, created)
    if any(token in text for token in ["buyer_video", "shop.tiktok.com", "tiktok.com/search"]):
        return (4, created)
    if fields.get("case_learning_key"):
        return (5, created)
    return (6, created)


def first_url(fields: dict[str, Any]) -> str:
    for key in ["video_url", "product_url", "url", "page_url", "profile_url", "source_url", "google_search_url", "fastmoss_hint"]:
        value = str(fields.get(key) or "").strip()
        if value.startswith("http"):
            return value
    return ""


def build_tk_overnight_agent_payload(
    run_date: str,
    snapshot: dict[str, Any],
    employee_scores: list[dict[str, Any]],
    retraining_tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    failing = [item for item in employee_scores if item.get("grade") != "pass"]
    latest_links = snapshot.get("latest_links") if isinstance(snapshot.get("latest_links"), list) else []
    link_lines = [
        f"{item.get('platform') or item.get('type')}: {item.get('title')} {item.get('url')}"
        for item in latest_links[:8]
        if isinstance(item, dict)
    ]
    score_lines = [
        f"{item.get('employee')}: {item.get('score')}/100 {item.get('grade')} - {item.get('note')}"
        for item in employee_scores
    ]
    retrain_lines = [
        f"{item.get('target_agent_id')}: {item.get('task_title')} -> {item.get('expected_output')}"
        for item in retraining_tasks[:12]
    ]
    text = "\n".join(
        [
            f"TK overnight training round {run_date}.",
            "This is the user's practical product-selection exam. TikTok Shop buyer-side, FastMoss and Kalodata are the main evidence sources. Amazon is only supplementary.",
            f"Strict TK evidence rows: {snapshot.get('real_tk_records', 0)}.",
            f"TK viral video rows: {snapshot.get('viral_records', 0)}.",
            f"Creator/store rows: {snapshot.get('creator_records', 0)}.",
            f"Weak or empty captures: {snapshot.get('weak_tk_records', 0)}.",
            f"Pending TK collection jobs: {snapshot.get('collection_jobs', 0)}.",
            f"Enabled targets: {', '.join(str(item) for item in snapshot.get('target_names', [])) or '-'}",
            "Employee scores:",
            *score_lines,
            "Employees requiring retraining:",
            *[f"{item.get('employee')} {item.get('score')}/100" for item in failing],
            "Retraining tasks:",
            *(retrain_lines or ["No retraining tasks."]),
            "Latest TK links:",
            *(link_lines or ["No real TK links yet."]),
            "Required output: short boss report, employee exam grading, retraining plan, next data collection priorities, video-script learning requirements and safety gates.",
        ]
    )
    return {
        "input_type": "tk_overnight_training_round",
        "input_text": text,
        "platform": "TikTok",
        "country": "US",
        "category": "All Category Radar",
    }


def build_employee_retraining_plan(root: Path, snapshot: dict[str, Any], employee_scores: list[dict[str, Any]], run_date: str) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    tasks: list[dict[str, Any]] = []
    for item in employee_scores:
        employee = str(item.get("employee") or "Unknown AI Employee")
        score = int(item.get("score") or 0)
        grade = str(item.get("grade") or "")
        plan = employee_retraining_plan(employee, score, grade, snapshot)
        evaluation_id = stable_local_id("eval_", run_date, employee, score, grade)
        evaluation = IntakeRecord(
            record_type="agent_evaluation",
            source="tk_overnight.employee_exam",
            raw_text=json.dumps({"employee": employee, "score": score, "grade": grade, "plan": plan}, ensure_ascii=False),
            fields={
                "agent_evaluation_id": evaluation_id,
                "run_date": run_date,
                "employee": employee,
                "score": score,
                "grade": grade,
                "verdict": plan["verdict"],
                "weakness": plan["weakness"],
                "retraining_plan": plan["retraining_plan"],
                "next_exam": plan["next_exam"],
                "must_submit": plan["must_submit"],
                "created_at": now,
            },
            score={"priority": 100 - score, "employee_training": True},
            director_notes=["AI employee exam result created by the TK overnight supervisor."],
            confidence=0.9,
        )
        append_record(root, evaluation)
        if grade != "pass":
            task_fields = {
                "task_queue_id": stable_local_id("retrain_", run_date, employee, score, grade),
                "task_type": "ai_employee_retraining",
                "target_agent_id": employee,
                "task_title": plan["task_title"],
                "task_description": plan["retraining_plan"],
                "expected_output": plan["must_submit"],
                "status": "queued",
                "requires_confirmation": False,
                "automation_level": "internal_training_only",
                "source_exam_id": evaluation_id,
                "priority": 100 - score,
                "created_at_utc": now,
            }
            append_record(
                root,
                IntakeRecord(
                    record_type="task_queue",
                    source="tk_overnight.employee_exam",
                    raw_text=json.dumps(task_fields, ensure_ascii=False),
                    fields=task_fields,
                    score={"priority": task_fields["priority"], "employee_retraining": True},
                    director_notes=["Queued automatically because employee did not pass the TK practical exam."],
                    confidence=0.9,
                ),
            )
            tasks.append(task_fields)
    return tasks


def employee_retraining_plan(employee: str, score: int, grade: str, snapshot: dict[str, Any]) -> dict[str, str]:
    verdict = "pass" if grade == "pass" else "mandatory retake" if grade == "fail_retrain" else "targeted review"
    if "Viral Content" in employee:
        return {
            "verdict": verdict,
            "weakness": "Real TikTok video evidence and video-script breakdown are still not strong enough.",
            "task_title": "Retake TK video-script breakdown exam",
            "retraining_plan": "Collect or use real TikTok/FastMoss/Kalodata video evidence. For each useful video, break down 0-3s hook, shot timeline, camera movement, edit rhythm, scene, emotion, CTA, comment purchase signals, creator fit, owned-account script and influencer script.",
            "next_exam": "Submit 10 real TK video breakdowns with links, creator handle, views, comments and replication plan.",
            "must_submit": "10 video cards: link, product, creator, hook, timeline, scene, CTA, why viral, owned script, influencer script.",
        }
    if "Product Selection" in employee or "Ecommerce Director" in employee:
        return {
            "verdict": verdict,
            "weakness": "Selection evidence is not allowed to be Amazon-only; TK rank, video, creator and product links must be attached.",
            "task_title": "Retake TK-first product-selection evidence exam",
            "retraining_plan": "Separate Amazon supplemental evidence from TikTok primary evidence. Grade each monitored product by TK product/rank rows, viral videos, creators, comments, lifecycle, risk and expected ROI.",
            "next_exam": "Submit 3 category opportunities and 3 focused product reports using TK-first evidence.",
            "must_submit": "Short product report with TK sales/rank/video/creator evidence, lifecycle status, risk, go/no-go and next 72h test plan.",
        }
    if "Influencer" in employee:
        return {
            "verdict": verdict,
            "weakness": "Creator rows need contact route, average views, cooperation quality and ROI expectation.",
            "task_title": "Retake private creator-library grading exam",
            "retraining_plan": "Build creator cards from TikTok/FastMoss/Kalodata evidence. Score creator fit, average views, interaction quality, follower quality, contact route, sample cost, expected CPA and cooperation risk.",
            "next_exam": "Submit 30 creator candidates split into A/B/C with contact route and reason.",
            "must_submit": "Creator table: handle, platform, niche, avg views, engagement, contact, grade, sample priority, risk.",
        }
    if "Data Reviewer" in employee:
        return {
            "verdict": verdict,
            "weakness": "Must reject empty pages, loading pages, generic tool homepages and mismatched products.",
            "task_title": "Retake data-quality gate exam",
            "retraining_plan": "Audit every row. Mark as hard TK evidence, soft strategy note, weak empty capture, Amazon supplement or mismatched product. Do not let power banks appear in cleanser/T-shirt reports.",
            "next_exam": "Submit a deduped evidence scoreboard and list the top 20 bad rows to remove or quarantine.",
            "must_submit": "Evidence audit: counts by hard/soft/weak/mismatch, bad-row examples, dedupe actions and corrected report summary.",
        }
    if "Risk" in employee:
        return {
            "verdict": verdict,
            "weakness": "Needs sharper IP, prohibited-claim and private-vs-public listing decisions.",
            "task_title": "Retake compliance and IP scan exam",
            "retraining_plan": "Check trademarks, brand terms, celebrity/team/character risk, medical claims, counterfeit wording and marketplace prohibited terms. Borderline can be watched; confirmed IP cannot be public.",
            "next_exam": "Submit risk table for 20 products/videos and recommended visibility decision.",
            "must_submit": "Risk table: clear/borderline/confirmed_ip/prohibited, evidence, suggested action and allowed channel sync.",
        }
    return {
        "verdict": verdict,
        "weakness": f"Current score {score}/100. Needs more complete TK-first output.",
        "task_title": "Retake TK operation output exam",
        "retraining_plan": "Study the latest TK overnight requirements and resubmit concise, evidence-backed work. Keep all external actions gated.",
        "next_exam": "Submit a concise exam answer with evidence links, score and next action.",
        "must_submit": "Short report: conclusion, evidence, risks, next action and what not to do.",
    }


def stable_local_id(prefix: str, *parts: Any) -> str:
    return prefix + sha1("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:18]


def score_ai_employees(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    weak_penalty = min(int(snapshot["weak_tk_records"]) // 80, 12)
    blocker_penalty = min(int(snapshot["blockers"]) // 40, 8)
    scores = [
        employee_score(
            "AI Ecommerce Director",
            35 + min(snapshot["real_tk_records"], 20) + min(snapshot["viral_records"] * 3, 20) + min(snapshot["creator_records"] * 4, 20) - weak_penalty,
            "Must coordinate a full TK loop: product evidence + viral video + creator + report. It fails if video and creator are missing.",
        ),
        employee_score(
            "Product Selection Analyst",
            35 + min(snapshot["tk_ranking_records"], 30) + min(snapshot["viral_records"] * 2, 15) + min(snapshot["creator_records"] * 2, 10) - weak_penalty,
            "Needs real TikTok Shop/FastMoss/Kalodata product rank rows plus video/creator context, not Amazon-only rows.",
        ),
        employee_score(
            "TikTok Viral Content Analyst",
            30 + min(snapshot["viral_records"] * 3, 30) + min(snapshot["video_breakdowns"] * 2, 20) - weak_penalty,
            "Most important employee tonight. Must turn real TK videos into hook, shot, script, scene, CTA and viral-reason reports.",
        ),
        employee_score(
            "Influencer Hunter",
            25 + min(snapshot["creator_records"] * 5, 35) + min(snapshot["buyer_jobs"], 15) - blocker_penalty,
            "Needs creator rows, average views, engagement, contact route and cooperation quality.",
        ),
        employee_score(
            "Listing Builder",
            35 + min(snapshot["video_scripts"] * 3, 15) + min(snapshot["viral_records"] * 3, 20) + min(snapshot["real_tk_records"], 15),
            "Can draft listing and scripts, but should not finalize before TK demand, creator scripts and review pain points are real.",
        ),
        employee_score(
            "Risk Director",
            70,
            "Safety rules are clear: no bypass, no copy, no publishing or store change without confirmation.",
        ),
        employee_score(
            "Data Reviewer",
            20 + min(snapshot["real_tk_records"], 30) + min(snapshot["blockers"], 10) - weak_penalty - blocker_penalty,
            "Must keep grading harsh. If evidence is missing, the report must say missing instead of pretending.",
        ),
    ]
    return scores


def employee_score(name: str, raw_score: int, note: str) -> dict[str, Any]:
    score = max(0, min(100, raw_score))
    if score >= 80:
        grade = "pass"
    elif score >= 60:
        grade = "needs_review"
    else:
        grade = "fail_retrain"
    return {"employee": name, "score": score, "grade": grade, "note": note}


def build_tk_overnight_report(
    *,
    root: Path,
    run_date: str,
    snapshot: dict[str, Any],
    statuses: list[dict[str, Any]],
    employee_scores: list[dict[str, Any]],
    case_result: dict[str, Any],
    browser_result: dict[str, Any],
    visual_report_path: str,
    case_analysis: dict[str, Any],
    target_reports: dict[str, Any],
    selection_report_path: str,
    meeting_report_path: str,
    idle_learning_report_path: str,
    operation_closure_report_path: str,
    director_agent_report_path: str,
    director_agent_run_id: str,
    retraining_tasks: list[dict[str, Any]],
) -> str:
    real_ok = snapshot["real_tk_records"] >= 30 and snapshot["viral_records"] >= 10 and snapshot["creator_records"] >= 5
    decision = "PASSABLE_TK_STUDY" if real_ok else "RETAKE_TK_DATA_COLLECTION"
    lines = [
        f"# TK Overnight Product Selection Retake - {run_date}",
        "",
        "## Boss Summary",
        "",
        f"- Decision: {decision}.",
        f"- Enabled monitored products: {snapshot['enabled_targets']} ({', '.join(snapshot['target_names']) or '-'})",
        f"- Real TK evidence rows: {snapshot['real_tk_records']}.",
        f"- Soft TK records: {snapshot['soft_tk_records']} (scripts, strategy notes, or generic TK pages; useful, but not market evidence).",
        f"- Weak / empty TK captures: {snapshot['weak_tk_records']} (tool homepages, loading pages, or mismatched pages do not count as evidence).",
        f"- TK ranking/product rows: {snapshot['tk_ranking_records']}.",
        f"- TK viral video rows: {snapshot['viral_records']}.",
        f"- Video breakdowns: {snapshot['video_breakdowns']}; video scripts: {snapshot['video_scripts']}.",
        f"- Creator/influencer rows: {snapshot['creator_records']}.",
        f"- Pending TK collection jobs: {snapshot['collection_jobs']} (FastMoss/Kalodata bridge {snapshot['bridge_jobs']}, buyer/video entry {snapshot['buyer_jobs']}).",
        f"- Login / verification / manual capture blockers: {snapshot['blockers']}.",
        "",
        "## What This Means",
        "",
    ]
    if real_ok:
        lines.append("- The TK loop has enough early evidence for AI meeting review. Next step: compare videos, creators, comments and product links, then make test plan.")
    else:
        lines.append("- This is still not a passing TK selection report. The system prepared the TK-first queue and scripts, but real FastMoss/Kalodata/TikTok buyer-side product/video/creator rows are still weak.")
        lines.append("- Tonight's job is to keep pushing TK queues, not pretend Amazon data is enough.")
    lines.extend(
        [
            "",
            "## AI Employee Exam Scores",
            "",
        ]
    )
    for item in employee_scores:
        lines.append(f"- {item['employee']}: {item['score']}/100 ({item['grade']}) - {item['note']}")
    lines.extend(["", "## Retraining Plan I Assigned", ""])
    if retraining_tasks:
        for task in retraining_tasks[:12]:
            lines.append(f"- {task.get('target_agent_id')}: {task.get('task_title')}")
            lines.append(f"  Must submit: {task.get('expected_output')}")
    else:
        lines.append("- No retake tasks. All employees passed this round.")
    lines.extend(
        [
            "",
            "## Full-Spectrum Training Loop",
            "",
            f"- AI Ecommerce Director Agent V1 run: {director_agent_run_id}",
            f"- Agent V1 report: {director_agent_report_path}",
            f"- Idle learning report: {idle_learning_report_path}",
            f"- Operation closure report: {operation_closure_report_path}",
            "- Every round now trains product market, viral content, creator library, review pain, IP risk, ad ROI, live room logic, AI video production and 21-step operation closure.",
        ]
    )
    lines.extend(
        [
            "",
            "## TK Collection Entrances To Check First",
            "",
        ]
    )
    if snapshot["latest_links"]:
        for item in snapshot["latest_links"][:10]:
            lines.append(f"- [{item['platform'] or item['type']}] {item['title']}")
            lines.append(f"  {item['url']}")
    else:
        lines.append("- No TK links were available yet.")
    lines.extend(
        [
            "",
            "## Files Generated",
            "",
            f"- TK overnight report: outputs/{TK_OVERNIGHT_REPORT_PREFIX}_{run_date}.md",
            f"- TK case learning: {case_result.get('report_path')}",
            f"- Browser operator: {browser_result.get('report_path')}",
            f"- Visual creative/video scripts: {visual_report_path}",
            f"- TK case video analysis: {case_analysis.get('report_path')}",
            f"- Selection intelligence: {selection_report_path}",
            f"- Selection meeting: {meeting_report_path}",
            f"- AI Director Agent V1: {director_agent_report_path}",
            f"- Idle learning: {idle_learning_report_path}",
            f"- Operation closure: {operation_closure_report_path}",
        ]
    )
    reports = target_reports.get("reports") if isinstance(target_reports.get("reports"), list) else []
    if reports:
        lines.append("- Product target reports:")
        for report in reports:
            lines.append(f"  - {report.get('target_name')}: {report.get('report_path')}")
    lines.extend(
        [
            "",
            "## Non-Negotiable Retake Rules",
            "",
            "- TikTok video is the main exam subject. Amazon can supplement price/reviews only.",
            "- A report without TK sales/GMV/rank, video script, creator fit, comments and product links must be graded low.",
            "- Do not bypass captcha/slider or change real stores. Keep pages open and wait for human verification if needed.",
            "- Every useful TK video must become: hook, timeline, shot/editing script, audience, scene, emotion, comments, store-owned script, influencer script, replication plan.",
            "",
            "## Platform Run Status",
            "",
        ]
    )
    for status in statuses[:40]:
        lines.append(f"- {status.get('source_id')}: {status.get('status')} | {compact(status.get('reason') or status.get('title') or status.get('url') or '', 180)}")
    return "\n".join(lines).rstrip() + "\n"


def write_tk_overnight_report(root: Path, run_date: str, content: str) -> Path:
    path = root / "outputs" / f"{TK_OVERNIGHT_REPORT_PREFIX}_{run_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_tk_overnight_json(root: Path, run_date: str, payload: dict[str, Any]) -> Path:
    path = root / "outputs" / f"{TK_OVERNIGHT_REPORT_PREFIX}_{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def compact(value: Any, limit: int = 160) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
