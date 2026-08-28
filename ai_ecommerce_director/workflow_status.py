from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from .api_connectors import load_api_sources
from .autonomous_runner import load_autonomous_config
from .llm import LLMClient
from .platform_autopilot import load_platform_autopilot_config
from .pod_admin import build_pod_admin_snapshot, load_pod_admin_config
from .storage import read_records
from .web_ai_bridge import load_web_ai_config


def build_workflow_status(root: Path) -> dict[str, Any]:
    """Audit the agent workflow so the UI can show what is real and what is not wired yet."""
    root = root.resolve()
    records = read_records(root)
    record_counts = count_records(records)
    stages = [
        service_stage(root),
        chat_feed_stage(record_counts),
        api_sources_stage(root),
        platform_patrol_stage(root),
        multi_ai_stage(root),
        reports_stage(root),
        auto_mode_stage(root),
        extension_stage(root),
        pod_stage(root, record_counts),
        collection_stage(record_counts),
        compliance_stage(record_counts),
        reviews_stage(record_counts),
        store_profile_stage(record_counts),
        action_queue_stage(root),
    ]
    blocking_items = [
        {
            "stage_id": stage["id"],
            "name": stage["name"],
            "status": stage["status"],
            "next_action": stage["next_action"],
        }
        for stage in stages
        if stage["status"] in {"needs_config", "blocked", "empty"}
    ]
    ready_count = len([stage for stage in stages if stage["status"] == "ready"])
    partial_count = len([stage for stage in stages if stage["status"] == "partial"])
    needs_config_count = len([stage for stage in stages if stage["status"] in {"needs_config", "blocked", "empty"}])
    return {
        "run_date": date.today().isoformat(),
        "root": str(root),
        "overall_status": overall_status(stages),
        "summary": {
            "stages": len(stages),
            "ready": ready_count,
            "partial": partial_count,
            "needs_config": needs_config_count,
            "records": len(records),
        },
        "record_counts": record_counts,
        "stages": stages,
        "blocking_items": blocking_items,
        "safety_policy": {
            "mode": "read_only_until_confirmed",
            "can_do_now": [
                "read configured public/API sources",
                "save captured page data",
                "generate reports",
                "generate video/listing/creator drafts",
                "create action queue",
            ],
            "requires_human_confirmation": [
                "login or slider verification",
                "publish or update listing",
                "change price, inventory, discount, or campaign",
                "contact creators",
                "upload assets",
                "buy IP nodes or change browser profiles",
                "ship orders, payments, appeals, authorizations",
            ],
        },
    }


def count_records(records: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        counts[record.record_type] = counts.get(record.record_type, 0) + 1
    return counts


def service_stage(root: Path) -> dict[str, Any]:
    return stage(
        "service",
        "Local service",
        "ready",
        "The local dashboard service is running and can render this workflow audit.",
        "Keep using the desktop launcher, then check this page first when something feels empty.",
        {"root": str(root)},
    )


def chat_feed_stage(record_counts: dict[str, int]) -> dict[str, Any]:
    total = sum(record_counts.values())
    status = "ready" if total else "empty"
    return stage(
        "chat_feed",
        "Chat and data feed",
        status,
        f"{total} records are saved in the local training database.",
        "Feed real cases, creator results, hot links, review pain points, and store records from the chat page.",
        {"record_counts": record_counts},
    )


def api_sources_stage(root: Path) -> dict[str, Any]:
    sources = load_api_sources(root)
    enabled = [source for source in sources if source.get("enabled")]
    runnable = [
        source
        for source in enabled
        if source.get("auth_type") not in {"oauth", "signed"}
        and (not source.get("requires_api_key", True) or bool(source.get("api_key") or source.get("api_key_env")))
    ]
    if runnable:
        status = "ready"
        summary = f"{len(runnable)} API sources are enabled and look runnable."
        next_action = "Run API sources, then compare saved records against the source platform."
    elif enabled:
        status = "partial"
        summary = f"{len(enabled)} API sources are enabled, but they may need keys, OAuth, or signed request integration."
        next_action = "Add API keys or OAuth/signed integration details before expecting live data."
    elif sources:
        status = "needs_config"
        summary = f"{len(sources)} API source templates exist, but none are enabled."
        next_action = "Enable the sources you paid for and set the matching environment keys."
    else:
        status = "needs_config"
        summary = "No API sources are configured."
        next_action = "Create config/api_sources.json with read-only ranking, review, video, and own-shop sources."
    return stage(
        "api_sources",
        "API data sources",
        status,
        summary,
        next_action,
        {
            "configured": len(sources),
            "enabled": len(enabled),
            "runnable_candidates": len(runnable),
            "sources": summarize_sources(sources),
        },
        "/api-sources",
    )


def platform_patrol_stage(root: Path) -> dict[str, Any]:
    config = load_platform_autopilot_config(root)
    sources = config.get("sources", []) if isinstance(config.get("sources"), list) else []
    enabled = [source for source in sources if isinstance(source, dict) and source.get("enabled")]
    public_enabled = [source for source in enabled if not source.get("requires_login") and source.get("url")]
    gated_enabled = [source for source in enabled if source.get("requires_login") or source.get("may_trigger_verification")]
    if public_enabled:
        status = "ready"
        summary = f"{len(public_enabled)} public platform pages can be collected; {len(gated_enabled)} login-gated pages will pause for human verification."
        next_action = "Run platform patrol and verify the report against the pages it opened."
    elif enabled:
        status = "partial"
        summary = f"{len(enabled)} platform sources are enabled, but they require login/manual verification or URLs."
        next_action = "Open gated pages manually, pass verification yourself, then capture with the extension."
    elif sources:
        status = "needs_config"
        summary = f"{len(sources)} platform patrol templates exist, but none are enabled."
        next_action = "Enable Amazon BS/NEW, buyer-side TikTok Shop video/product-card monitoring, and the product research tools you want watched."
    else:
        status = "needs_config"
        summary = "No platform patrol sources are configured."
        next_action = "Add Amazon, TikTok Shop, FastMoss, Kalodata, EchoTik, Etsy, and Walmart observation URLs."
    return stage(
        "platform_patrol",
        "Platform patrol",
        status,
        summary,
        next_action,
        {
            "configured": len(sources),
            "enabled": len(enabled),
            "public_enabled": len(public_enabled),
            "manual_gate_enabled": len(gated_enabled),
            "safe_mode": config.get("safe_mode", True),
            "sources": summarize_sources(sources),
        },
        "/platform-autopilot",
    )


def multi_ai_stage(root: Path) -> dict[str, Any]:
    status_payload = LLMClient(root=root, task="strategy").status().to_dict()
    web_config = load_web_ai_config(root)
    web_providers = [
        item
        for item in web_config.get("providers", [])
        if isinstance(item, dict) and item.get("enabled", True)
    ]
    status_payload["web_ai_bridge"] = {
        "enabled": bool(web_config.get("enabled", True)),
        "providers": [str(item.get("name") or item.get("id") or "") for item in web_providers],
    }
    ready = int(status_payload.get("ready", 0) or 0)
    configured = int(status_payload.get("configured", 0) or 0)
    if ready:
        status = "ready"
        summary = f"{ready}/{configured} AI providers are ready."
        next_action = "Use the AI chat and autopilot reports; route video analysis to the strongest vision/data model you configure."
    elif web_config.get("enabled", True) and web_providers:
        status = "partial"
        summary = f"API providers are not ready, but web AI project mode is available for {len(web_providers)} providers."
        next_action = "Use Web AI Project to copy task packages into ChatGPT, Claude, or Gemini web projects."
    elif configured:
        status = "needs_config"
        summary = f"{configured} AI providers are configured, but none are ready."
        next_action = "Enable at least one provider and set its API key environment variable."
    else:
        status = "needs_config"
        summary = "No AI providers are configured."
        next_action = "Add OpenAI, Claude, Gemini, DeepSeek, Zhipu, or a local OpenAI-compatible model."
    return stage("multi_ai", "Multi-AI brain", status, summary, next_action, status_payload, "/multi-ai")


def reports_stage(root: Path) -> dict[str, Any]:
    today_path = root / "outputs" / f"daily_report_{date.today().isoformat()}.md"
    report_paths = sorted((root / "outputs").glob("daily_report_*.md")) if (root / "outputs").exists() else []
    status = "ready" if today_path.exists() else ("partial" if report_paths else "empty")
    summary = "Today's report exists." if today_path.exists() else f"{len(report_paths)} older daily reports found."
    return stage(
        "reports",
        "Reports",
        status,
        summary,
        "Run the daily report after adding or collecting data.",
        {"today_report": str(today_path), "report_count": len(report_paths)},
        "/report",
    )


def auto_mode_stage(root: Path) -> dict[str, Any]:
    config = load_autonomous_config(root)
    enabled = bool(config.get("enabled", True))
    safe_mode = bool(config.get("safe_mode", True))
    status = "ready" if enabled and safe_mode else ("blocked" if enabled and not safe_mode else "needs_config")
    summary = "Autonomous mode is enabled in safe read-only mode." if status == "ready" else "Autonomous mode needs review."
    return stage(
        "auto_mode",
        "Safe auto workflow",
        status,
        summary,
        "Run it to generate read-only reports and an action queue; approve sensitive actions manually.",
        {"enabled": enabled, "safe_mode": safe_mode, "steps": config.get("steps", {})},
        "/auto-mode",
    )


def extension_stage(root: Path) -> dict[str, Any]:
    extension_dir = root / "browser_extension" / "ai_ecommerce_director_capture"
    manifest = extension_dir / "manifest.json"
    package = root / "outputs" / "AI_Ecommerce_Director_Capture_Extension.zip"
    if manifest.exists() and package.exists():
        status = "ready"
        summary = "Browser capture extension exists and a downloadable zip has been built."
    elif manifest.exists():
        status = "partial"
        summary = "Browser capture extension exists, but the downloadable zip has not been built yet."
    else:
        status = "needs_config"
        summary = "Browser capture extension files are missing."
    return stage(
        "extension",
        "Browser extension",
        status,
        summary,
        "Download/install the extension in Chrome or BitBrowser, then capture real platform pages.",
        {"manifest": str(manifest), "package": str(package), "package_exists": package.exists()},
        "/plugin",
    )


def pod_stage(root: Path, record_counts: dict[str, int]) -> dict[str, Any]:
    config = load_pod_admin_config(root)
    details: dict[str, Any] = {
        "enabled": config.enabled,
        "project_path": str(config.project_path or ""),
        "snapshot_records": record_counts.get("pod_admin_snapshot", 0),
    }
    try:
        snapshot, _ = build_pod_admin_snapshot(root, persist=False)
        details["status"] = snapshot.status
        details["base_url"] = snapshot.status.get("base_url", "")
    except Exception as exc:  # noqa: BLE001 - status page should explain connector errors.
        details["error"] = str(exc)
    if config.enabled and details.get("base_url"):
        status = "ready"
        summary = "POD admin connector can read the configured local admin endpoint."
    elif config.enabled:
        status = "partial"
        summary = "POD admin connector is enabled, but no reachable admin endpoint was detected."
    else:
        status = "needs_config"
        summary = "POD admin connector is not enabled yet."
    return stage(
        "pod_admin",
        "POD admin connector",
        status,
        summary,
        "Start the POD admin server, then generate a read-only POD snapshot.",
        details,
        "/pod-admin",
    )


def collection_stage(record_counts: dict[str, int]) -> dict[str, Any]:
    count = record_counts.get("collection_job", 0)
    return stage(
        "collection_jobs",
        "Collection jobs",
        "ready" if count else "empty",
        f"{count} platform data collection jobs are stored.",
        "Create jobs for Amazon BS/NEW, buyer-side TikTok Shop videos/product cards, viral videos, reviews, and own-store data.",
        {"count": count},
        "/data?type=collection_job",
    )


def compliance_stage(record_counts: dict[str, int]) -> dict[str, Any]:
    count = record_counts.get("compliance_term", 0)
    return stage(
        "compliance",
        "Forbidden words and IP risk library",
        "ready" if count else "empty",
        f"{count} compliance risk records are stored.",
        "Keep adding trademarks, platform restricted words, and safe replacement phrasing.",
        {"count": count},
        "/data?type=compliance_term",
    )


def reviews_stage(record_counts: dict[str, int]) -> dict[str, Any]:
    count = record_counts.get("review_insight", 0)
    return stage(
        "reviews",
        "Review and complaint intelligence",
        "ready" if count else "empty",
        f"{count} review/pain-point records are stored.",
        "Collect competitor bad reviews and your own complaints, then generate listing/product fixes.",
        {"count": count},
        "/data?type=review_insight",
    )


def store_profile_stage(record_counts: dict[str, int]) -> dict[str, Any]:
    count = record_counts.get("store_profile", 0)
    return stage(
        "store_profiles",
        "Store profile library",
        "ready" if count else "empty",
        f"{count} store profile records are stored.",
        "Add each store's platform, country, currency, timezone, BitBrowser profile, IP region, and fulfillment model.",
        {"count": count},
        "/data?type=store_profile",
    )


def action_queue_stage(root: Path) -> dict[str, Any]:
    today_path = root / "outputs" / f"action_queue_{date.today().isoformat()}.json"
    queue_count = 0
    pending_count = 0
    if today_path.exists():
        try:
            payload = json.loads(today_path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                queue_count = len(payload)
                pending_count = len([item for item in payload if isinstance(item, dict) and item.get("requires_confirmation")])
        except json.JSONDecodeError:
            pass
    status = "ready" if queue_count else "empty"
    return stage(
        "action_queue",
        "Action queue",
        status,
        f"{queue_count} actions are queued today; {pending_count} require human confirmation.",
        "Run safe auto workflow after new data collection, then review pending actions before store execution.",
        {"path": str(today_path), "queue_count": queue_count, "pending_confirmation": pending_count},
        "/auto-mode",
    )


def summarize_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        rows.append(
            {
                "id": source.get("id") or source.get("name") or "",
                "provider": source.get("provider") or source.get("source_platform") or source.get("marketplace") or "",
                "enabled": bool(source.get("enabled")),
                "auth_type": source.get("auth_type") or "",
                "requires_login": bool(source.get("requires_login") or source.get("may_trigger_verification")),
                "url": source.get("url") or source.get("base_url") or "",
            }
        )
    return rows


def overall_status(stages: list[dict[str, Any]]) -> str:
    if any(stage["status"] == "blocked" for stage in stages):
        return "blocked"
    if any(stage["status"] in {"needs_config", "empty"} for stage in stages):
        return "needs_config"
    if any(stage["status"] == "partial" for stage in stages):
        return "partial"
    return "ready"


def stage(
    stage_id: str,
    name: str,
    status: str,
    summary: str,
    next_action: str,
    details: dict[str, Any],
    url: str = "",
) -> dict[str, Any]:
    return {
        "id": stage_id,
        "name": name,
        "status": status,
        "summary": summary,
        "next_action": next_action,
        "details": details,
        "url": url,
    }
