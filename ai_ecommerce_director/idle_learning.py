from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .storage import append_record, read_records
from .types import IntakeRecord


IDLE_LEARNING_CONFIG = Path("config") / "idle_learning.json"
IDLE_LEARNING_REPORT_PREFIX = "idle_learning"


@dataclass(slots=True)
class IdleLearningResult:
    run_date: str
    statuses: list[dict[str, Any]]
    memories: list[IntakeRecord]
    report: str
    report_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "statuses": self.statuses,
            "saved_memories": len(self.memories),
            "memories": [record.to_dict() for record in self.memories],
            "report": self.report,
            "report_path": str(self.report_path),
        }


def run_idle_learning(root: Path, run_date: str | None = None) -> IdleLearningResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    config = load_idle_learning_config(root)
    if not config.get("enabled", True):
        report = build_idle_learning_report(report_date, [{"track": "idle_learning", "status": "disabled"}], [])
        path = write_idle_learning_report(root, report_date, report)
        return IdleLearningResult(report_date, [{"track": "idle_learning", "status": "disabled"}], [], report, path)

    records = read_records(root)
    statuses: list[dict[str, Any]] = []
    memories: list[IntakeRecord] = []
    for track in learning_tracks(config):
        if not track.get("enabled", True):
            statuses.append({"track": track.get("id"), "status": "skipped", "reason": "track disabled"})
            continue
        memory = build_track_memory(report_date, track, records)
        append_record(root, memory)
        memories.append(memory)
        statuses.append(
            {
                "track": track.get("id"),
                "status": "memorized",
                "records_seen": int(memory.fields.get("records_seen") or 0),
                "memory_key": memory.fields.get("memory_key"),
            }
        )

    report = build_idle_learning_report(report_date, statuses, memories)
    path = write_idle_learning_report(root, report_date, report)
    return IdleLearningResult(report_date, statuses, memories, report, path)


def load_idle_learning_config(root: Path) -> dict[str, Any]:
    path = root / IDLE_LEARNING_CONFIG
    if not path.exists():
        return default_idle_learning_config()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_idle_learning_config()
    return payload if isinstance(payload, dict) else default_idle_learning_config()


def default_idle_learning_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "status": "disabled_by_default",
        "safe_mode": True,
        "cadence": "run whenever auto-mode runs; schedule hourly when external automation is enabled",
        "principles": [
            "Only observe, analyze, remember, and draft.",
            "Never bypass login, CAPTCHA, slider, paywall, or platform anti-bot controls.",
            "Never publish, delist, change price, contact creators, ship orders, refund, pay, authorize apps, or change store settings without human confirmation.",
        ],
        "tracks": [
            {
                "id": "product_market_learning",
                "name": "Product and category learning",
                "record_types": ["platform_ranking_signal", "hot_link", "collection_job", "store_metric_snapshot"],
                "question": "Which products, categories, countries, platforms, and time windows are becoming more worth testing?",
            },
            {
                "id": "viral_content_learning",
                "name": "Viral content and script learning",
                "record_types": ["viral_content_signal", "video_breakdown", "video_script", "creator_spike_event"],
                "question": "Which hooks, scenes, emotions, creator types, edit structures, and CTAs should we copy or avoid?",
            },
            {
                "id": "review_pain_learning",
                "name": "Reviews, complaints, and product-pain learning",
                "record_types": ["review_insight", "store_health_event", "store_operation_event"],
                "question": "Which competitor pain points and own-store complaints should change product, listing, script, or service strategy?",
            },
            {
                "id": "risk_compliance_learning",
                "name": "IP, prohibited-term, and platform-rule learning",
                "record_types": ["ip_image_risk", "compliance_term", "tk_rule_update"],
                "question": "Which words, images, characters, brands, claims, patents, and policy changes should block or slow automation?",
            },
            {
                "id": "industry_operator_learning",
                "name": "Industry operator learning",
                "record_types": ["industry_research_asset", "selection_playbook", "money_case", "influencer_cooperation"],
                "question": "Which outside lessons and real cases should become operating rules for the AI Ecommerce Director?",
            },
            {
                "id": "paid_ads_roi_learning",
                "name": "Paid ads, breakeven ROI, and cold-start learning",
                "record_types": ["store_metric_snapshot", "video_script", "viral_content_signal", "video_breakdown", "money_case", "industry_research_asset"],
                "question": "What breakeven ROI, ROAS, budget pacing, cold-start material test, and harvest timing rules should control paid ads?",
            },
            {
                "id": "live_room_operator_learning",
                "name": "Live room control, link, and discount learning",
                "record_types": ["store_metric_snapshot", "store_operation_event", "video_script", "industry_research_asset", "money_case"],
                "question": "When should live control add product links, change discount rhythm, push coupons, protect margin, or stop a live-room tactic?",
            },
            {
                "id": "ai_video_production_learning",
                "name": "AI video, real-shot, and mixed-edit learning",
                "record_types": ["viral_content_signal", "video_breakdown", "video_script", "industry_research_asset", "ip_image_risk", "compliance_term"],
                "question": "Which Seedance 2.0, real-shot, editing, voiceover, and mixed-cut workflows produce high-quality compliant ecommerce videos?",
            },
        ],
    }


def learning_tracks(config: dict[str, Any]) -> list[dict[str, Any]]:
    tracks = config.get("tracks")
    if isinstance(tracks, list) and tracks:
        return [track for track in tracks if isinstance(track, dict)]
    return list(default_idle_learning_config()["tracks"])


def build_track_memory(run_date: str, track: dict[str, Any], records: list[IntakeRecord]) -> IntakeRecord:
    track_id = str(track.get("id") or "idle_learning")
    record_types = {str(item) for item in track.get("record_types", []) if str(item).strip()}
    related = [record for record in records if record.record_type in record_types]
    latest = sorted(related, key=lambda item: item.created_at, reverse=True)[:12]
    high_priority = sorted(related, key=lambda item: float(item.score.get("priority", 0) or 0), reverse=True)[:5]
    fields = {
        "memory_key": f"idle-learning:{run_date}:{track_id}",
        "memory_type": "idle_learning",
        "learning_track": track_id,
        "learning_track_name": track.get("name") or track_id,
        "learning_question": track.get("question") or "",
        "records_seen": len(related),
        "latest_signals": [record_summary(record) for record in latest],
        "highest_priority_signals": [record_summary(record) for record in high_priority],
        "what_we_learned": infer_learning(track_id, related),
        "what_to_do": infer_next_actions(track_id, related),
        "what_not_to_do": safety_rules_for_track(track_id),
        "valid_when": valid_when_for_track(track_id),
        "next_learning_tasks": infer_next_learning_tasks(track_id, related),
        "automation_level": "L0-L2: observe, analyze, remember, draft; external execution stays in confirmation queue",
    }
    return IntakeRecord(
        record_type="strategy_memory",
        fields=fields,
        raw_text=f"Idle learning memory for {track_id} on {run_date}",
        source="idle_learning",
        score={"priority": 72 if related else 40, "training_weight": "medium" if related else "low"},
        director_notes=[str(fields["what_we_learned"])[:500]],
    )


def record_summary(record: IntakeRecord) -> dict[str, Any]:
    fields = record.fields
    return {
        "type": record.record_type,
        "name": (
            fields.get("product_name")
            or fields.get("page_title")
            or fields.get("source_name")
            or fields.get("video_url")
            or fields.get("creator_handle")
            or fields.get("store_id")
            or fields.get("risk_element")
            or fields.get("term")
            or record.record_id[:8]
        ),
        "platform": fields.get("marketplace") or fields.get("source_platform") or record.source,
        "priority": record.score.get("priority"),
        "created_at": record.created_at,
    }


def infer_learning(track_id: str, related: list[IntakeRecord]) -> str:
    if not related:
        return "No fresh evidence yet. Keep watching configured sources and wait for real signals before making strategy claims."
    count_text = f"{len(related)} related records"
    if track_id == "product_market_learning":
        return f"{count_text} show the product brain should compare broad category trend with precise monitored targets before recommending tests."
    if track_id == "viral_content_learning":
        return f"{count_text} show content strategy must preserve hook, scene, emotion, shot structure, creator type, comment intent, and CTA as separate fields."
    if track_id == "review_pain_learning":
        return f"{count_text} show review pain points and own-store complaints should directly change listing copy, product QA, scripts, and customer-service drafts."
    if track_id == "risk_compliance_learning":
        return f"{count_text} show risk checks must happen before listing, visual creative, video script, and channel sync drafts."
    if track_id == "industry_operator_learning":
        return f"{count_text} show outside education is useful only when converted into a validation task, operating rule, or measurable store experiment."
    if track_id == "paid_ads_roi_learning":
        return f"{count_text} show ads strategy should start from breakeven ROI, creative cold-start evidence, ROAS decay, and harvest timing instead of spending blindly."
    if track_id == "live_room_operator_learning":
        return f"{count_text} show live-room operations need a controlled rhythm: link timing, discount ladder, coupon push, margin guardrail, and stop-loss rule."
    if track_id == "ai_video_production_learning":
        return f"{count_text} show video production should combine real product proof with AI-generated supporting shots, keeping hook, edit rhythm, CTA, and IP safety explicit."
    return f"{count_text} were summarized into long-term strategy memory."


def infer_next_actions(track_id: str, related: list[IntakeRecord]) -> list[str]:
    if not related:
        return ["Keep collecting public/read-only sources, monitored products, competitor links, reviews, videos, and store metrics."]
    if track_id == "product_market_learning":
        return [
            "Score candidates by platform, country, category depth, growth, competition, price band, review pain, supply fit, and risk.",
            "Separate broad market scan from precise monitored-product scan.",
        ]
    if track_id == "viral_content_learning":
        return [
            "For every useful video, save hook, 0-2s opening, shot list, scene, emotion, creator type, CTA, comments, and replication plan.",
            "Generate both store-owned script and influencer brief, then queue human approval for execution.",
        ]
    if track_id == "review_pain_learning":
        return [
            "Convert repeated complaints into product changes, listing clarification, FAQ, script proof points, and customer-service draft replies.",
            "Flag defects that can create refunds, returns, account health issues, or bad reviews.",
        ]
    if track_id == "risk_compliance_learning":
        return [
            "Block confirmed IP/prohibited risks from public automation; route borderline cases to observation or manual review.",
            "Keep authorized branded goods separate from unauthorized copying.",
        ]
    if track_id == "industry_operator_learning":
        return [
            "Turn each lesson into a validation task instead of treating education content as truth.",
            "Prefer real money cases and seller data over generic courses.",
        ]
    if track_id == "paid_ads_roi_learning":
        return [
            "Calculate breakeven ROI from price, cost, fees, shipping, refund rate, and ad spend before scaling.",
            "Cold-start multiple low-budget creatives first; only raise budget after product-card clicks, add-to-cart, orders, and ROAS pass the guardrail.",
            "Separate testing budget from harvesting budget, and stop creatives when ROAS decays or refund rate rises.",
        ]
    if track_id == "live_room_operator_learning":
        return [
            "Define live-room link sequence: warm-up product, main product, bundle/upsell, then coupon or limited discount.",
            "Set discount ladder by margin: awareness discount, test discount, harvest discount, and stop-loss floor.",
            "Use live comments, product-card clicks, order spikes, and refund risk to decide when to push or pause links.",
        ]
    if track_id == "ai_video_production_learning":
        return [
            "Use Seedance 2.0 as the preferred AI video generator for reference-driven ecommerce shots, then edit with real product proof.",
            "Create a mixed-cut recipe: real product close-up, AI scene or motion shot, model/lifestyle proof, subtitle hook, CTA end card.",
            "Run IP, celebrity, brand, music, voice, and platform-claim checks before any AI video is published or sent to creators.",
        ]
    return ["Summarize, remember, and wait for confirmation before external execution."]


def safety_rules_for_track(track_id: str) -> list[str]:
    rules = [
        "Do not invent sales, ranking, creator, review, or policy data.",
        "Do not perform external store actions without human confirmation.",
    ]
    if track_id == "risk_compliance_learning":
        rules.append("Do not auto-publish confirmed IP or prohibited content.")
    if track_id == "viral_content_learning":
        rules.append("Do not copy exact competitor assets, copyrighted characters, brand marks, or celebrity likeness.")
    if track_id == "paid_ads_roi_learning":
        rules.append("Do not change ad budget, campaign objective, bid, discount, or product price without confirmation.")
    if track_id == "live_room_operator_learning":
        rules.append("Do not add live product links, change discounts, issue coupons, or alter live-room settings without confirmation.")
    if track_id == "ai_video_production_learning":
        rules.append("Do not generate or publish videos using unauthorized celebrity likeness, real-person identity, brand IP, copyrighted characters, music, or competitor footage.")
    return rules


def valid_when_for_track(track_id: str) -> str:
    return {
        "product_market_learning": "Valid when platform/category/product/country data has enough records to compare broad market and precise targets.",
        "viral_content_learning": "Valid when each case includes video link or captured page plus enough script, hook, scene, comment, or creator evidence.",
        "review_pain_learning": "Valid when reviews or complaints are grouped by repeated product, listing, fulfillment, service, or expectation gaps.",
        "risk_compliance_learning": "Valid when matched rights, prohibited terms, source, confidence, and authorization status are recorded.",
        "industry_operator_learning": "Valid when outside content is converted into a testable operating rule or validation task.",
        "paid_ads_roi_learning": "Valid when price, cost, platform fees, shipping, refund rate, ad spend, ROAS, creative ID, and conversion stage are recorded.",
        "live_room_operator_learning": "Valid when live session time, product-link timing, discount/coupon, clicks, orders, margin, comments, and refund risk are recorded.",
        "ai_video_production_learning": "Valid when video source, shot list, AI tool, prompt, real-shot assets, edit rhythm, CTA, rights status, and performance are recorded.",
    }.get(track_id, "Valid when enough real records support the memory.")


def infer_next_learning_tasks(track_id: str, related: list[IntakeRecord]) -> list[str]:
    if track_id == "product_market_learning":
        return ["Refresh Amazon BS/NEW and buyer-side TikTok Shop monitored products.", "Compare at least one broad category and one precise product target."]
    if track_id == "viral_content_learning":
        return ["Collect more product videos and creator videos.", "Write a script breakdown for every saved high-signal video."]
    if track_id == "review_pain_learning":
        return ["Collect competitor one-star reviews and own-store complaints.", "Group repeated pain points into fixable product/listing/script changes."]
    if track_id == "risk_compliance_learning":
        return ["Update trademark/patent/TRO/prohibited-term database.", "Scan new visuals and listing drafts before channel sync."]
    if track_id == "industry_operator_learning":
        return ["Read public seller education and real seller cases.", "Convert each useful lesson into a validation task."]
    if track_id == "paid_ads_roi_learning":
        return ["Collect ad spend, ROAS, CPA, creative ID, order count, refund rate, and breakeven ROI for each test.", "Compare cold-start creatives against harvested creatives before scaling."]
    if track_id == "live_room_operator_learning":
        return ["Collect live replay notes, link timing, discount ladder, coupon push time, product-card clicks, orders, and comments.", "Write a live-room stop-loss and harvest rule for each product."]
    if track_id == "ai_video_production_learning":
        return ["Collect strong product videos and split each into real-shot, AI-shot, edit, subtitle, voice, music, and CTA layers.", "Use Seedance 2.0 for AI support shots, then compare output against real-shot conversion."]
    return ["Keep learning from safe read-only sources."]


def build_idle_learning_report(run_date: str, statuses: list[dict[str, Any]], memories: list[IntakeRecord]) -> str:
    lines = [
        "# AI Ecommerce Director Idle Learning Report",
        "",
        f"Date: {run_date}",
        "",
        "## Principle",
        "",
        "- When no human task is assigned, the director keeps learning from safe read-only data, writes strategy memory, and queues drafts or recommendations only.",
        "- Store-impacting actions still require human confirmation.",
        "",
        "## Tracks",
        "",
    ]
    for status in statuses:
        lines.append(
            f"- {status.get('track')}: {status.get('status')} | records_seen={status.get('records_seen', 0)} | {status.get('reason') or status.get('memory_key') or ''}"
        )
    lines.extend(["", "## Strategy Memories", ""])
    if not memories:
        lines.append("- No strategy memories saved.")
    for memory in memories:
        fields = memory.fields
        lines.append(f"### {fields.get('learning_track_name')}")
        lines.append(f"- Question: {fields.get('learning_question')}")
        lines.append(f"- Learned: {fields.get('what_we_learned')}")
        lines.append("- Next:")
        for item in fields.get("next_learning_tasks", [])[:4]:
            lines.append(f"  - {item}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_idle_learning_report(root: Path, run_date: str, content: str) -> Path:
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{IDLE_LEARNING_REPORT_PREFIX}_{run_date}.md"
    path.write_text(content, encoding="utf-8")
    return path
