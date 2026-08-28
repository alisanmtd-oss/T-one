from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .product_targets import build_tiktok_buyer_product_target_sources, build_tiktok_selection_bridge_product_target_sources
from .storage import append_record, read_records
from .types import IntakeRecord


BROWSER_OPERATOR_CONFIG = Path("config") / "browser_operator.json"
BROWSER_OPERATOR_REPORT_PREFIX = "browser_operator"


@dataclass(slots=True)
class BrowserOperatorResult:
    run_date: str
    statuses: list[dict[str, Any]]
    report: str
    report_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "statuses": self.statuses,
            "report": self.report,
            "report_path": str(self.report_path),
        }


def run_browser_operator(root: Path, run_date: str | None = None) -> BrowserOperatorResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    config = load_browser_operator_config(root)
    statuses: list[dict[str, Any]] = []
    sources = config.get("sources", [])
    if not isinstance(sources, list):
        sources = []
    sources = [
        *sources,
        *build_tiktok_selection_bridge_product_target_sources(root),
        *build_tiktok_buyer_product_target_sources(root),
    ]
    if bool(config.get("logged_in_capture_only") or config.get("use_logged_in_browser_only")):
        for source in sources:
            if not isinstance(source, dict):
                continue
            statuses.append(save_logged_in_capture_required(root, source, report_date))
        report = build_browser_operator_report(report_date, statuses)
        report_path = write_browser_operator_report(root, report_date, report)
        return BrowserOperatorResult(report_date, statuses, report, report_path)
    for source in sources:
        if not isinstance(source, dict):
            continue
        statuses.append(run_browser_source(root, source, report_date))
    report = build_browser_operator_report(report_date, statuses)
    report_path = write_browser_operator_report(root, report_date, report)
    return BrowserOperatorResult(report_date, statuses, report, report_path)


def load_browser_operator_config(root: Path) -> dict[str, Any]:
    path = root / BROWSER_OPERATOR_CONFIG
    if not path.exists():
        return {"enabled": True, "logged_in_capture_only": True, "sources": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"enabled": True, "logged_in_capture_only": True, "sources": []}


def save_logged_in_capture_required(root: Path, source: dict[str, Any], run_date: str) -> dict[str, Any]:
    source_id = str(source.get("id") or source.get("url") or "browser-source").strip()
    if not source.get("enabled", True):
        return {"source_id": source_id, "status": "skipped", "reason": "source disabled"}
    url = str(source.get("url") or "").strip()
    status = {
        "source_id": source_id,
        "status": "logged_in_capture_required",
        "url": url,
        "returncode": 0,
        "captured_pages": 0,
        "clicked": 0,
        "reason": "Use the already logged-in Chrome or BitBrowser tab, then capture the visible page with the AI Ecommerce Director extension. The browser operator will not open a separate unlogged profile.",
        "details": {"logged_in_capture_only": True},
    }
    status["record"] = save_browser_collection_job(root, source, run_date, status).to_dict()
    return status


def run_browser_source(root: Path, source: dict[str, Any], run_date: str) -> dict[str, Any]:
    source_id = str(source.get("id") or source.get("url") or "browser-source").strip()
    if not source.get("enabled", False):
        return {"source_id": source_id, "status": "skipped", "reason": "source disabled"}
    url = str(source.get("url") or "").strip()
    if not url:
        return {"source_id": source_id, "status": "missing_url", "reason": "source URL is missing"}
    collection_goal = str(source.get("collection_goal") or "")
    if not collection_goal:
        collection_goal = "buyer_video_shop_competitors" if "tiktok" in url.lower() else "browser_collection"
    script_path = root / "scripts" / "browser_click_collect.js"
    if not script_path.exists():
        return {"source_id": source_id, "status": "failed", "reason": f"missing script: {script_path}"}
    args = [
        "node",
        str(script_path),
        "--root",
        str(root),
        "--source-id",
        source_id,
        "--url",
        url,
        "--record-type",
        str(source.get("record_type") or "platform_ranking_signal"),
        "--source-platform",
        str(source.get("source_platform") or "browser"),
        "--marketplace",
        str(source.get("marketplace") or source.get("source_platform") or "browser"),
        "--collection-goal",
        collection_goal,
        "--data-category",
        str(source.get("data_category") or ""),
        "--search-keyword",
        str(source.get("search_keyword") or source.get("keyword") or ""),
        "--product-target-id",
        str(source.get("product_target_id") or ""),
        "--product-target-name",
        str(source.get("product_target_name") or ""),
        "--product-family",
        str(source.get("product_family") or ""),
        "--reference-image",
        str(source.get("reference_image") or ""),
        "--bridge-provider",
        str(source.get("bridge_provider") or ""),
        "--selection-bridge",
        "true" if source.get("selection_bridge") else "false",
        "--follow-tiktok-product-links",
        "true" if source.get("follow_tiktok_product_links") else "false",
        "--max-clicks",
        str(int(source.get("max_clicks", 3) or 3)),
        "--initial-wait-seconds",
        str(int(source.get("initial_wait_seconds", 14) or 14)),
        "--verification-wait-seconds",
        str(int(source.get("verification_wait_seconds", 0) or 0)),
        "--run-date",
        run_date,
        "--server",
        str(source.get("server") or "http://127.0.0.1:8765"),
    ]
    if bool(source.get("keep_open_on_gate", "tiktok" in url.lower())):
        args.append("--keep-open-on-gate")
    if bool(source.get("keep_open_after_run", False)):
        args.append("--keep-open-after-run")
    if bool(source.get("incognito", False)):
        args.append("--incognito")
    if source.get("headless", False):
        args.append("--headless")
    try:
        completed = subprocess.run(
            args,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=int(source.get("timeout_seconds", 120) or 120),
            check=False,
        )
    except Exception as exc:  # noqa: BLE001 - return source-level status.
        return {"source_id": source_id, "status": "failed", "url": url, "reason": str(exc)}
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    try:
        payload = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        payload = {"raw_stdout": stdout}
    status = {
        "source_id": source_id,
        "status": payload.get("status") or ("completed" if completed.returncode == 0 else "failed"),
        "url": url,
        "returncode": completed.returncode,
        "captured_pages": payload.get("captured_pages", 0),
        "clicked": payload.get("clicked", 0),
        "reason": payload.get("reason") or stderr,
        "details": payload,
    }
    if status["status"] in {"manual_gate", "failed"}:
        status["record"] = save_browser_collection_job(root, source, run_date, status).to_dict()
    return status


def save_browser_collection_job(root: Path, source: dict[str, Any], run_date: str, status: dict[str, Any]) -> IntakeRecord:
    source_status = str(status.get("status") or "manual_gate")
    reason = str(status.get("reason") or "")
    url = str(source.get("url") or "")
    keep_open_on_gate = bool(source.get("keep_open_on_gate", "tiktok" in url.lower()))
    source_id = str(source.get("id") or source.get("url") or "browser-source").strip()
    for record in read_records(root, "collection_job"):
        fields = record.fields
        if (
            str(fields.get("source_id") or "") == source_id
            and str(fields.get("run_date") or "") == run_date
            and str(fields.get("source_status") or "") == source_status
            and str(fields.get("url") or "") == url
        ):
            return record
    fields = {
        "source_id": source_id,
        "collection_target": source.get("name") or source.get("id") or source.get("url"),
        "platform_list": source.get("source_platform") or source.get("marketplace") or "",
        "product_name": source.get("product_target_name") or source.get("product_family") or source.get("name") or "",
        "product_family": source.get("product_family") or "",
        "product_target_id": source.get("product_target_id") or "",
        "product_target_name": source.get("product_target_name") or "",
        "keyword": source.get("keyword") or "",
        "url": url,
        "data_category": source.get("data_category") or "browser_collection",
        "record_type_to_collect": source.get("record_type") or "platform_ranking_signal",
        "source_status": source_status,
        "source_reason": reason,
        "run_date": run_date,
        "selection_bridge": bool(source.get("selection_bridge", False)),
        "bridge_provider": source.get("bridge_provider") or "",
        "follow_tiktok_product_links": bool(source.get("follow_tiktok_product_links", False)),
        "requires_login": bool(source.get("requires_login", False)),
        "may_trigger_verification": bool(source.get("may_trigger_verification", False)),
        "keep_open_on_gate": keep_open_on_gate,
        "verification_wait_seconds": int(source.get("verification_wait_seconds", 0) or 0),
        "next_step": (
            "The browser window was kept open. Pass verification/login manually, then rerun browser collection for this source."
            if source_status == "manual_gate"
            else "Use the already logged-in Chrome or BitBrowser tab, open/search this source, then click the AI Ecommerce Director extension to capture visible product, ranking, creator, video, and store data."
            if source_status == "logged_in_capture_required"
            else "Review the source and rerun collection after fixing the browser/platform issue."
        ),
    }
    priority = 78 if source_status == "logged_in_capture_required" else 75 if source_status == "manual_gate" else 55
    record = IntakeRecord(
        record_type="collection_job",
        fields=fields,
        raw_text=json.dumps(fields, ensure_ascii=False),
        source="browser_operator_fallback",
        score={"priority": priority},
        director_notes=[
            "Browser operator saved this source because collection could not finish automatically.",
            "Use existing logged-in Chrome/BitBrowser sessions for paid selection tools and store backends.",
            "Do not bypass platform verification; continue only after human verification is complete.",
        ],
    )
    append_record(root, record)
    return record


def build_browser_operator_report(run_date: str, statuses: list[dict[str, Any]]) -> str:
    lines = [
        "# Browser Operator Report",
        "",
        f"Date: {run_date}",
        "",
        "## Boundary",
        "",
        "- AI can open pages, click visible public links/cards, capture page text/links/screenshots, and save records.",
        "- AI must not bypass login, slider, captcha, payments, authorization, or account settings.",
        "",
        "## Status",
        "",
    ]
    if not statuses:
        lines.append("- No browser operator sources configured.")
    for status in statuses:
        lines.append(
            f"- {status.get('source_id')}: {status.get('status')} | "
            f"captured {status.get('captured_pages', 0)} | clicked {status.get('clicked', 0)} | "
            f"{status.get('reason') or status.get('url') or ''}"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_browser_operator_report(root: Path, run_date: str, content: str) -> Path:
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{BROWSER_OPERATOR_REPORT_PREFIX}_{run_date}.md"
    path.write_text(content, encoding="utf-8")
    return path
