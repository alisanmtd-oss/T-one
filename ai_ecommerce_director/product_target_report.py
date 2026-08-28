from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .product_targets import load_product_targets
from .storage import read_records
from .types import IntakeRecord


PRODUCT_TARGET_REPORT_PREFIX = "product_target_report"


@dataclass(slots=True)
class ProductTargetReportResult:
    run_date: str
    reports: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"run_date": self.run_date, "reports": self.reports}


def run_product_target_reports(root: Path, run_date: str | None = None) -> ProductTargetReportResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    targets = [
        target
        for target in load_product_targets(root).get("targets", [])
        if isinstance(target, dict) and target.get("enabled", True)
    ]
    records = read_records(root)
    reports: list[dict[str, Any]] = []
    for target in targets:
        content = build_product_target_report(target, records, report_date)
        path = write_product_target_report(root, target, report_date, content)
        reports.append({"target_id": target.get("id"), "target_name": target.get("name"), "report_path": str(path), "content": content})
    return ProductTargetReportResult(report_date, reports)


def build_product_target_report(target: dict[str, Any], records: list[IntakeRecord], run_date: str) -> str:
    related = [record for record in records if record_matches_target(target, record)]
    collection_jobs_all = [record for record in related if record.record_type == "collection_job"]
    gate_records = [record for record in related if is_verification_or_gate_record(record)]
    real_candidates = [
        record
        for record in related
        if record.record_type != "collection_job" and not is_verification_or_gate_record(record) and not is_empty_or_weak_capture(record)
    ]
    real_records = [record for record in real_candidates if is_hard_market_evidence(record)]
    soft_records = [record for record in real_candidates if record not in real_records]
    weak_records = [
        record
        for record in related
        if record.record_type != "collection_job" and not is_verification_or_gate_record(record) and is_empty_or_weak_capture(record)
    ]
    linked_records = [record for record in real_records if record_url(record)]
    risk_records = [record for record in related if record.record_type in {"ip_image_risk", "compliance_term"}]
    ranking_records = sorted(
        [record for record in real_records if record.record_type == "platform_ranking_signal"],
        key=lambda record: (
            platform_report_priority(record),
            int(record.fields.get("rank_position") or record.fields.get("rank") or 9999)
            if str(record.fields.get("rank_position") or record.fields.get("rank") or "").isdigit()
            else 9999,
            -float(record.score.get("priority", 0) or 0),
        ),
    )[:12]
    video_scripts = unique_records(
        [record for record in related if record.record_type == "video_script"],
        lambda record: f"{record.fields.get('script_type')}|{record.fields.get('script_lines')}",
    )[:8]
    creative_records = unique_records(
        [record for record in related if record.record_type == "creative_inspiration"],
        lambda record: f"{record.fields.get('creative_angle')}|{record.fields.get('original_shot_plan')}",
    )[:6]
    collection_jobs = collection_jobs_all[:10]
    keyword_text = ", ".join(str(item) for item in target.get("keywords", [])[:12])
    score = estimate_target_score(real_records, ranking_records, video_scripts, collection_jobs_all, gate_records)
    core_tk_records = core_tk_evidence_records(real_records)
    lines = [
        f"# Product Target Report: {target.get('name')}",
        "",
        f"- Date: {run_date}",
        f"- Market: {target.get('market') or 'US'}",
        f"- Platforms: {', '.join(str(item) for item in target.get('platforms', [])) or '-'}",
        f"- Keywords: {keyword_text or '-'}",
        "",
        "## Boss Takeaway",
        "",
        *boss_takeaway_lines_clean(target, score, real_records, core_tk_records, video_scripts, gate_records),
        "",
        "## Executive View",
        "",
        f"- Product score: {score}/100.",
        f"- Matched records in data lake: {len(related)}.",
        f"- Real captured data rows: {len(real_records)}.",
        f"- Soft records / drafts: {len(soft_records)}.",
        f"- Weak / empty platform captures: {len(weak_records)}.",
        f"- Matched ranking/product signals: {len(ranking_records)}.",
        f"- Product/video/store links available: {len(linked_records)}.",
        f"- Video scripts prepared: {len(video_scripts)}.",
        f"- Pending platform collection jobs: {len(collection_jobs_all)}.",
        f"- Login / verification / capture blockers: {len(gate_records)}.",
        f"- Risk/compliance records: {len(risk_records)}.",
        f"- Current decision: {decision_label_clean(target_decision(score, real_records, [], gate_records))}",
        "",
        "## Data Coverage By Platform",
        "",
        *platform_coverage_lines(real_records, collection_jobs_all, gate_records),
        "",
        "## What Is Still Missing",
        "",
        *missing_data_lines(target, real_records, collection_jobs_all),
        "",
        "## Core TK Signals",
        "",
        *core_tk_evidence_lines(core_tk_records),
        "",
        "<details>",
        "<summary>More ranking / marketplace observations</summary>",
        "",
        "## Ranking And Marketplace Signals",
        "",
    ]
    if ranking_records:
        for index, record in enumerate(ranking_records[:8], start=1):
            fields = record.fields
            title = fields.get("product_name") or fields.get("page_title") or fields.get("url") or record.record_id
            rank = fields.get("rank_position") or fields.get("rank") or "-"
            marketplace = fields.get("marketplace") or fields.get("source_platform") or "-"
            url = fields.get("url") or fields.get("product_url") or ""
            lines.append(f"{index}. [{marketplace}] Rank {rank}: {title}")
            if url:
                lines.append(f"   URL: {compact_url(str(url))}")
    else:
        lines.append("- No matched marketplace ranking rows yet. Open the pending platform jobs and capture product cards/ranking rows.")
    lines.extend(["", "</details>", "", "## Listing Direction", ""])
    lines.extend(listing_direction_lines(target, ranking_records))
    lines.extend(["", "## Image Direction", ""])
    lines.extend(image_direction_lines(target))
    lines.extend(["", "## Video Scripts", ""])
    if video_scripts:
        for record in video_scripts:
            fields = record.fields
            lines.append(f"### {fields.get('title') or fields.get('script_type') or 'Script'}")
            lines.append(f"- Owner: {fields.get('content_owner') or '-'}")
            lines.append(f"- Hook: {fields.get('hook_text') or '-'}")
            lines.append(f"- Script: {fields.get('script_lines') or '-'}")
            lines.append(f"- Shot order: {fields.get('shot_order') or '-'}")
            lines.append(f"- Music rule: {fields.get('music_rule') or 'Use commercially safe music only.'}")
            lines.append("")
    else:
        lines.append("- No script assets yet. Run Visual Creative Director for this target.")
    if creative_records:
        lines.extend(["## Creative Memory / Original Ideas", ""])
        for record in creative_records:
            fields = record.fields
            idea_text = fields.get("creative_prompt") or fields.get("original_shot_plan") or "-"
            lines.append(f"- {fields.get('creative_angle') or fields.get('product_name')}: {compact_report_text(idea_text)}")
    lines.extend(["", "<details>", "<summary>Pending collection entrances</summary>", "", "## Pending Collection Entrances", ""])
    if collection_jobs:
        for job in collection_jobs[:8]:
            fields = job.fields
            lines.append(f"- {fields.get('source_platform')}: {fields.get('keyword') or '-'} | {fields.get('data_category') or '-'}")
            if fields.get("url"):
                lines.append(f"  {compact_url(str(fields.get('url')))}")
        if len(collection_jobs) > 8:
            lines.append(f"- ... {len(collection_jobs) - 8} more pending entrances hidden in detail view.")
    else:
        lines.append("- No pending collection jobs.")
    lines.extend(["", "</details>"])
    if linked_records:
        lines.extend(["", "<details>", "<summary>Captured product / video / store links</summary>", "", "## Product / Video / Store Links Already Captured", ""])
        sorted_links = sorted(
            linked_records,
            key=lambda item: (
                platform_report_priority(item),
                -float(item.score.get("priority", 0) or 0),
                item.created_at,
            ),
        )
        for record in sorted_links[:8]:
            lines.append(f"- [{platform_label(record)}] {compact_report_text(record_title(record), 120)}")
            lines.append(f"  {compact_url(record_url(record))}")
        if len(sorted_links) > 8:
            lines.append(f"- ... {len(sorted_links) - 8} lower-priority links hidden.")
        lines.extend(["", "</details>"])
    if risk_records:
        lines.extend(["", "## IP / Compliance Notes", ""])
        for record in risk_records[:8]:
            fields = record.fields
            risk = fields.get("risk_level") or fields.get("status") or fields.get("visibilityRecommendation") or "-"
            name = fields.get("matched_right") or fields.get("risk_element") or fields.get("term") or fields.get("product_name") or record.record_id
            lines.append(f"- {risk}: {compact_report_text(name, 140)}")
    lines.extend(
        [
            "",
            "## Risk And Next Actions",
            "",
        ]
    )
    lines.extend(risk_next_action_lines(target))
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"




# Keep the UI report ASCII-first so mixed Chinese encodings from browser captures
# never become mojibake in the boss summary.
def decision_label_clean(decision: str) -> str:
    labels = {
        "not_ready_collect_more_data": "Not ready: collect real TK data first",
        "watch_but_clear_login_or_verification_first": "Watch: clear login/verification gates first",
        "ready_for_multi_ai_review_and_small_test_plan": "Ready for multi-AI review and small-budget test plan",
        "watch_and_collect_tiktok_video_evidence": "Watch: keep collecting TK video and creator evidence",
        "low_confidence_do_not_scale": "Low confidence: do not scale",
    }
    return labels.get(decision, decision)


def boss_takeaway_lines_clean(
    target: dict[str, Any],
    score: int,
    real_records: list[IntakeRecord],
    core_tk_records: list[IntakeRecord],
    video_scripts: list[IntakeRecord],
    gate_records: list[IntakeRecord],
) -> list[str]:
    tk_count = len(core_tk_records)
    video_count = sum(1 for record in real_records if is_valid_video_evidence(record))
    creator_count = sum(1 for record in real_records if is_valid_creator_or_store_evidence(record))
    decision = target_decision(score, real_records, [], gate_records)
    lines = [
        f"- Verdict: {decision_label_clean(decision)}.",
        f"- TK evidence: core={tk_count}; videos={video_count}; creators/stores={creator_count}; script drafts={len(video_scripts)}.",
    ]
    if score >= 80 and tk_count and video_count:
        lines.append("- Boss action: enter the multi-AI selection meeting and prepare a small-budget test plan. Do not scale directly.")
    elif tk_count and video_count:
        lines.append("- Boss action: keep watching and collecting. Prioritize video scripts, creator quality, review pain points, and real product detail pages.")
    else:
        lines.append("- Boss action: do not decide yet. Collect TK product ranks, videos, creators, and reviews; do not let Amazon replace TK evidence.")
    if gate_records:
        lines.append(f"- Risk/gates: {len(gate_records)} entrances still need login, verification, or manual confirmation. Do not bypass verification.")
    product_family = target.get("product_family") or target.get("name") or "this product"
    lines.append(f"- Content focus: for {product_family}, extract the 0-2s hook, product proof, real scene, review pain point, and CTA.")
    return lines


def core_tk_evidence_records(real_records: list[IntakeRecord]) -> list[IntakeRecord]:
    tk_records = [
        record
        for record in real_records
        if is_valid_core_tk_evidence(record)
    ]
    return sorted(
        unique_records(tk_records, lambda record: f"{evidence_source_label(record)}|{record_title(record)}|{record_url(record)}"),
        key=lambda item: (
            platform_report_priority(item),
            -float(item.score.get("priority", 0) or 0),
            item.created_at,
        ),
    )[:6]


def core_tk_evidence_lines(records: list[IntakeRecord]) -> list[str]:
    if not records:
        return ["- No hard TK / FastMoss / Kalodata evidence yet."]
    lines: list[str] = []
    for index, record in enumerate(records, start=1):
        fields = record.fields
        label = evidence_source_label(record)
        title = compact_report_text(record_title(record), 130)
        metrics = visible_metric_summary(fields)
        lines.append(f"{index}. [{label}] {title}")
        if metrics:
            lines.append(f"   - Metrics: {metrics}")
        url = record_url(record)
        if url:
            lines.append(f"   - Link: {compact_url(url)}")
        screenshot = fields.get("screenshot_path") or (record.metadata or {}).get("screenshot_path")
        if screenshot:
            lines.append(f"   - Screenshot: {screenshot}")
    return lines


def visible_metric_summary(fields: dict[str, Any]) -> str:
    pairs = [
        ("rank", fields.get("rank_position") or fields.get("rank")),
        ("price", fields.get("price") or fields.get("price_visible")),
        ("7d sales", fields.get("sales_7d_visible") or fields.get("recent_7d_sales") or fields.get("sales")),
        ("7d GMV", fields.get("gmv_7d_visible") or fields.get("recent_7d_gmv") or fields.get("gmv") or fields.get("revenue")),
        ("total sales", fields.get("total_sales_visible")),
        ("total GMV", fields.get("total_gmv_visible")),
        ("creator rate", fields.get("creator_order_rate_visible")),
        ("store", fields.get("store_name") or fields.get("shop_name")),
        ("creator", fields.get("creator_handle")),
    ]
    return "; ".join(f"{name}={value}" for name, value in pairs if str(value or "").strip())


def platform_coverage_lines(real_records: list[IntakeRecord], collection_jobs: list[IntakeRecord], gate_records: list[IntakeRecord]) -> list[str]:
    platforms = sorted({platform_label(record) for record in [*real_records, *collection_jobs, *gate_records] if platform_label(record)})
    if not platforms:
        return ["- No platform coverage yet."]
    lines: list[str] = []
    for platform in platforms:
        platform_real_records = [record for record in real_records if platform_label(record) == platform]
        search_lead_count = sum(1 for record in platform_real_records if is_search_only_video_url(record_url(record)))
        if "tiktok video search" in platform.lower():
            real_count = sum(1 for record in platform_real_records if is_valid_video_evidence(record))
        else:
            real_count = len(platform_real_records)
        pending_count = sum(1 for record in collection_jobs if platform_label(record) == platform)
        gate_count = sum(1 for record in gate_records if platform_label(record) == platform)
        status = "captured" if real_count else "pending"
        if gate_count:
            status = "blocked_or_needs_login"
        lead_text = f", search_leads={search_lead_count}" if search_lead_count else ""
        lines.append(f"- {platform}: real={real_count}{lead_text}, pending={pending_count}, blockers={gate_count}, status={status}.")
    return lines


def platform_report_priority(record: IntakeRecord) -> int:
    label = platform_label(record).lower()
    category = str(record.fields.get("data_category") or record.fields.get("ranking_type") or "").lower()
    if any(signal in label or signal in category for signal in ["tiktok", "fastmoss", "kalodata"]):
        return 0
    if "amazon" in label or "amazon" in category:
        return 1
    return 2


def compact_url(url: str, limit: int = 120) -> str:
    if not url:
        return ""
    if len(url) <= limit:
        return url
    if "amazon.com/" in url and "/dp/" in url:
        prefix, _, rest = url.partition("/dp/")
        asin = rest.split("/", 1)[0].split("?", 1)[0]
        return f"{prefix}/dp/{asin}"
    clean_url = url.split("?", 1)[0]
    if len(clean_url) <= limit:
        return clean_url
    return clean_url[: limit - 3] + "..."


def missing_data_lines(target: dict[str, Any], real_records: list[IntakeRecord], collection_jobs: list[IntakeRecord]) -> list[str]:
    platforms = [str(item) for item in target.get("platforms", [])]
    captured_platforms = {platform_label(record) for record in real_records}
    missing = [platform for platform in platforms if platform not in captured_platforms]
    tk_records = [record for record in real_records if platform_report_priority(record) == 0]
    video_records = [
        record
        for record in real_records
        if is_valid_video_evidence(record)
    ]
    creator_records = [
        record
        for record in real_records
        if is_valid_creator_or_store_evidence(record)
    ]
    lines: list[str] = []
    if missing:
        lines.append(f"- Missing or weak captured data: {', '.join(missing)}.")
    if collection_jobs:
        lines.append("- Open pending entrances with the already logged-in browser, capture product cards, ranking rows, creator/video rows, prices, GMV/sales if visible, comments, and outbound product links.")
    if not tk_records:
        lines.append("- TikTok-side product evidence is missing: collect buyer-side TikTok Shop, FastMoss or Kalodata rows before using Amazon conclusions.")
    if not any(record.record_type == "review_insight" for record in real_records):
        lines.append("- Review pain points are still weak: collect bad reviews and complaint keywords before final listing/image decisions.")
    if not video_records:
        lines.append("- TikTok viral content evidence is still weak: collect buyer-side videos or FastMoss/Kalodata video rows before content strategy.")
    if not creator_records:
        lines.append("- Creator / influencer evidence is missing: collect creator handle, average views, engagement and content quality before seeding samples.")
    if not lines:
        lines.append("- Core data is present. Next step is multi-AI review and experiment planning.")
    return lines


def target_decision(score: int, real_records: list[IntakeRecord], collection_jobs: list[IntakeRecord], gate_records: list[IntakeRecord]) -> str:
    if len(real_records) < 5:
        return "not_ready_collect_more_data"
    if gate_records and len(collection_jobs) > len(real_records):
        return "watch_but_clear_login_or_verification_first"
    if score >= 80:
        return "ready_for_multi_ai_review_and_small_test_plan"
    if score >= 60:
        return "watch_and_collect_tiktok_video_evidence"
    return "low_confidence_do_not_scale"




def risk_next_action_lines(target: dict[str, Any]) -> list[str]:
    text = " ".join([str(target.get("name") or ""), *(str(item) for item in target.get("keywords", []))]).lower()
    if "screen protector" in text or "tempered glass" in text:
        return [
            "- Avoid absolute claims such as unbreakable, 100% shatterproof, or medical/safety guarantees.",
            "- Use compatible-with wording for phone models; do not imply official Apple/Samsung authorization unless verified.",
            "- Do not copy competitor photos, creator footage, music, characters, brand marks, or packaging layout.",
            "- Next: capture FastMoss/Kalodata/TikTok buyer-side product/video rows, then rerun this report to compare platform demand and creator scripts.",
        ]
    if "shirt" in text or "tee" in text or "t-shirt" in text or "apparel" in text:
        return [
            "- Avoid copying competitor print designs, brand logos, slogans, tags, packaging layout, model photos, or creator footage.",
            "- Verify fabric weight, wash process, size chart, shrinkage, colorfastness, and care-label claims before listing.",
            "- Separate blank apparel opportunity from printed-design opportunity; IP risk is usually higher on printed graphics and slogans.",
            "- Next: collect TikTok buyer-side videos and FastMoss/Kalodata creator rows, then compare content hooks, fit scenes, and buyer comments.",
        ]
    if "cleanser" in text or "skin" in text or "supplement" in text or "melatonin" in text:
        return [
            "- Avoid medical, treatment, cure, sleep-disorder, acne-cure, or guaranteed efficacy claims unless legally reviewed.",
            "- Collect ingredient, review pain point, return complaint, and compliance evidence before listing or ad copy.",
            "- Do not copy competitor packaging, clinical before/after claims, certification badges, or influencer footage.",
            "- Next: collect bad reviews and TikTok buyer-side videos, then generate compliant listing and script angles.",
        ]
    return [
        "- Avoid copying competitor photos, creator footage, music, characters, brand marks, slogans, or packaging layout.",
        "- Verify price, margin, logistics, compliance, and review pain points before scaling.",
        "- Next: capture FastMoss/Kalodata/TikTok buyer-side product/video rows, then rerun this report to compare platform demand and creator scripts.",
    ]


def platform_label(record: IntakeRecord) -> str:
    fields = record.fields
    source_platform = str(fields.get("source_platform") or fields.get("platform") or "").strip()
    marketplace = str(fields.get("marketplace") or "").strip()
    source_lower = source_platform.lower()
    if any(token in source_lower for token in ["fastmoss", "kalodata", "tiktok video", "tiktok shop buyer", "tiktok shop intelligence"]):
        return source_platform
    return str(marketplace or source_platform or record.source or "-").strip()


def evidence_source_label(record: IntakeRecord) -> str:
    fields = record.fields
    source_platform = str(fields.get("source_platform") or fields.get("platform") or "").strip()
    marketplace = str(fields.get("marketplace") or "").strip()
    if source_platform and marketplace and source_platform.lower() != marketplace.lower():
        return f"{source_platform} / {marketplace}"
    return platform_label(record)


def record_title(record: IntakeRecord) -> str:
    fields = record.fields
    return str(
        fields.get("product_name")
        or fields.get("product_title")
        or fields.get("product_title_visible")
        or fields.get("page_title")
        or fields.get("video_title")
        or fields.get("creator_handle")
        or fields.get("collection_target")
        or record.record_id
    )


def record_url(record: IntakeRecord) -> str:
    fields = record.fields
    for key in ["product_url", "video_url", "url", "page_url", "profile_url", "source_url"]:
        value = str(fields.get(key) or "").strip()
        if value.startswith("http"):
            return value
    return ""


def is_verification_or_gate_record(record: IntakeRecord) -> bool:
    text = " ".join(
        [
            record.raw_text,
            str(record.fields.get("source_status") or ""),
            str(record.fields.get("collection_status") or ""),
            str(record.fields.get("blocked_by") or ""),
            str(record.fields.get("page_title") or ""),
            str(record.fields.get("notes") or ""),
        ]
    ).lower()
    markers = ["verification", "captcha", "security check", "logged_in_capture_required", "login required", "blocked"]
    return any(marker in text for marker in markers)


def is_empty_or_weak_capture(record: IntakeRecord) -> bool:
    fields = record.fields or {}
    metadata = record.metadata or {}
    text = " ".join(
        str(fields.get(key) or "")
        for key in ["page_text", "visible_growth_signal", "page_title", "product_name", "source_reason"]
    ).lower()
    if any(marker in text for marker in ["暂无数据", "\u6682\u65e0\u6570\u636e", "loading", "no data", "not found"]):
        return True
    validation = metadata.get("platform_autopilot_validation") if isinstance(metadata, dict) else None
    product_match = metadata.get("product_match") if isinstance(metadata, dict) else None
    if isinstance(validation, dict) and validation.get("status") == "needs_review":
        return True
    if isinstance(product_match, dict) and product_match.get("status") == "different_product":
        return True
    if record.record_type == "platform_ranking_signal":
        has_product_signal = any(
            str(fields.get(key) or "").strip()
            for key in ["rank_position", "sales", "gmv", "creator_handle", "video_url", "product_url", "product_asin"]
        )
        if not has_product_signal and any(term in text for term in ["fastmoss", "kalodata", "商品搜索", "analytics"]):
            return True
    return False


def is_hard_market_evidence(record: IntakeRecord) -> bool:
    if record.record_type not in {
        "platform_ranking_signal",
        "viral_content_signal",
        "creator_spike_event",
        "influencer_cooperation",
        "influencer_profile",
        "review_insight",
        "hot_link",
    }:
        return False
    fields = record.fields or {}
    hard_keys = [
        "rank_position",
        "rank",
        "sales",
        "gmv",
        "revenue",
        "price",
        "price_visible",
        "product_url",
        "video_url",
        "creator_handle",
        "shop_name",
        "store_name",
        "comment_count",
        "view_count",
        "views",
        "current_views",
        "latest_video_views",
        "comment_insights",
        "product_asin",
        "sales_7d_visible",
        "gmv_7d_visible",
        "total_sales_visible",
        "total_gmv_visible",
        "creator_order_rate_visible",
        "store_sales_visible",
        "rating_visible",
    ]
    if any(str(fields.get(key) or "").strip() for key in hard_keys):
        return True
    links = fields.get("page_links")
    if isinstance(links, list):
        return any("shop.tiktok.com" in str(link).lower() or "amazon.com" in str(link).lower() for link in links)
    return False


def is_valid_video_evidence(record: IntakeRecord) -> bool:
    fields = record.fields or {}
    url = str(fields.get("video_url") or record_url(record) or "").strip()
    if is_search_only_video_url(url):
        return False
    if is_direct_video_url(url):
        return record.record_type in {
            "viral_content_signal",
            "video_breakdown",
            "review_insight",
            "screenshot_reference",
            "influencer_profile",
        }
    if is_tiktok_shop_product_video_row(record):
        return True
    if record.record_type == "video_breakdown" and (
        fields.get("shot_timeline")
        or fields.get("hook_type")
        or fields.get("viral_reason")
        or fields.get("why_it_works")
    ):
        lower_url = url.lower()
        return "shop.tiktok.com/view/product/" in lower_url or "shop.tiktok.com/us/pdp/" in lower_url
    return False


def is_valid_creator_or_store_evidence(record: IntakeRecord) -> bool:
    fields = record.fields or {}
    url = str(fields.get("video_url") or record_url(record) or "").strip()
    creator = str(fields.get("creator_handle") or "").strip()
    shop = str(fields.get("shop_name") or fields.get("store_name") or "").strip()
    if not creator and not shop:
        return False
    if is_search_only_video_url(url):
        return False
    if record.record_type in {"influencer_profile", "influencer_cooperation", "creator_spike_event"}:
        return True
    if is_tiktok_shop_product_video_row(record):
        return True
    if shop and any(
        str(fields.get(key) or "").strip()
        for key in ["sales", "gmv", "total_sales_visible", "store_sales_visible", "rating_visible"]
    ):
        return True
    return False


def is_valid_core_tk_evidence(record: IntakeRecord) -> bool:
    source = evidence_source_label(record).lower()
    if platform_report_priority(record) != 0 and not any(name in source for name in ["tiktok", "fastmoss", "kalodata"]):
        return False
    fields = record.fields or {}
    if is_valid_video_evidence(record) or is_valid_creator_or_store_evidence(record):
        return True
    if record.record_type == "platform_ranking_signal":
        return any(
            str(fields.get(key) or "").strip()
            for key in [
                "rank_position",
                "rank",
                "price",
                "sales",
                "gmv",
                "product_url",
                "sales_7d_visible",
                "gmv_7d_visible",
                "total_sales_visible",
                "total_gmv_visible",
                "rating_visible",
            ]
        )
    if record.record_type == "review_insight":
        url = record_url(record)
        return bool(url and not is_search_only_video_url(url))
    return False


def is_direct_video_url(url: str) -> bool:
    lower = url.lower()
    return (
        ("tiktok.com/@" in lower and "/video/" in lower)
        or "m.tiktok.com/v/" in lower
        or "tikwm.com/video/" in lower
        or "douyin.com/" in lower
        or ("fastmoss.com/" in lower and "/media-source/video/" in lower)
    )


def is_search_only_video_url(url: str) -> bool:
    lower = url.lower()
    return "tiktok.com/search" in lower or "/search/video" in lower


def is_tiktok_shop_product_video_row(record: IntakeRecord) -> bool:
    fields = record.fields or {}
    url = str(fields.get("video_url") or record_url(record) or "").lower()
    category = str(fields.get("data_category") or "").lower()
    has_video_metric = any(str(fields.get(key) or "").strip() for key in ["views", "view_count", "latest_video_views"])
    has_creator = bool(str(fields.get("creator_handle") or "").strip())
    is_product_page = "shop.tiktok.com/view/product/" in url or "shop.tiktok.com/us/pdp/" in url
    return is_product_page and has_creator and has_video_metric and "video" in category


def record_matches_target(target: dict[str, Any], record: IntakeRecord) -> bool:
    fields = record.fields
    target_id = str(target.get("id") or "")
    direct_target_match = bool(target_id and str(fields.get("product_target_id") or "") == target_id)
    target_name = str(target.get("name") or "").strip().lower()
    meta = target_match_meta(target)
    normalized_target_name = meta["normalized_name"]
    if target_name and normalize_match_text(fields.get("product_target_name")) == normalized_target_name:
        return True
    haystack = cached_record_haystack(record)
    if meta["is_screen_protector"] and is_screen_protector_non_same_product(haystack):
        return False
    if normalized_target_name and normalized_target_name in haystack:
        return True
    if target_phrase_matches(target, haystack):
        return True
    if direct_target_match:
        # Keep planned collection jobs tied to the target, but do not let stale
        # or wrongly-tagged marketplace rows pollute the product report.
        return record.record_type == "collection_job"
    return False


TARGET_MATCH_STOPWORDS = {
    "acid",
    "clean",
    "gentle",
    "shop",
    "store",
    "amazon",
    "tiktok",
    "product",
    "market",
    "keyword",
    "search",
    "women",
    "woman",
    "mens",
    "men",
    "with",
    "pack",
    "case",
    "phone",
    "bundle",
    "offer",
    "free",
}


_NORMALIZE_MATCH_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")


def normalize_match_text(value: Any) -> str:
    text = str(value or "").lower()
    text = _NORMALIZE_MATCH_RE.sub(" ", text)
    return " ".join(text.split())


# Building a record's match "haystack" runs regex normalization over a dozen
# fields. The auto-mode page matches the same records against several targets,
# so we memoize the haystack per record (identity-keyed) for the duration of a
# page render. reset_target_haystack_cache() is called when a render starts; a
# size cap bounds memory for pages that do not reset it.
_TARGET_HAYSTACK_LOCK = threading.Lock()
_TARGET_HAYSTACK_CACHE: dict[int, tuple[IntakeRecord, str]] = {}
_TARGET_HAYSTACK_CACHE_MAX = 200_000


def reset_target_haystack_cache() -> None:
    with _TARGET_HAYSTACK_LOCK:
        _TARGET_HAYSTACK_CACHE.clear()
    with _TARGET_META_LOCK:
        _TARGET_META_CACHE.clear()


def cached_record_haystack(record: IntakeRecord) -> str:
    record_id = id(record)
    with _TARGET_HAYSTACK_LOCK:
        cached = _TARGET_HAYSTACK_CACHE.get(record_id)
        if cached is not None and cached[0] is record:
            return cached[1]
    haystack = record_target_haystack(record.fields)
    with _TARGET_HAYSTACK_LOCK:
        if len(_TARGET_HAYSTACK_CACHE) >= _TARGET_HAYSTACK_CACHE_MAX:
            _TARGET_HAYSTACK_CACHE.clear()
        _TARGET_HAYSTACK_CACHE[record_id] = (record, haystack)
    return haystack


def record_target_haystack(fields: dict[str, Any]) -> str:
    return normalize_match_text(
        " ".join(
            str(fields.get(key) or "")
            for key in [
                "product_target_name",
                "product_name",
                "product_title",
                "page_title",
                "keyword",
                "target_keyword",
                "target_keywords",
                "search_keyword",
                "product_family",
                "script_lines",
                "shot_order",
                "creative_angle",
                "original_shot_plan",
            ]
        )
    )


# Per-target match metadata (normalized name, phrase signatures, screen-protector
# flag) depends only on the target, not the record, so we compute it once per
# target instead of once per (target x record). Cleared by reset_target_haystack_cache().
_TARGET_META_LOCK = threading.Lock()
_TARGET_META_CACHE: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
_TARGET_META_CACHE_MAX = 10_000


def target_match_meta(target: dict[str, Any]) -> dict[str, Any]:
    target_id = id(target)
    with _TARGET_META_LOCK:
        cached = _TARGET_META_CACHE.get(target_id)
        if cached is not None and cached[0] is target:
            return cached[1]
    phrases = [str(target.get("name") or ""), str(target.get("product_family") or "")]
    phrases.extend(str(item) for item in target.get("keywords", []) if str(item).strip())
    phrase_signatures = [(normalized, target_match_tokens(normalized)) for normalized in (normalize_match_text(phrase) for phrase in phrases)]
    screen_text = normalize_match_text(
        " ".join(
            [
                str(target.get("name") or ""),
                str(target.get("product_family") or ""),
                *(str(item) for item in target.get("keywords", [])),
            ]
        )
    )
    meta = {
        "normalized_name": normalize_match_text(str(target.get("name") or "").strip().lower()),
        "phrase_signatures": phrase_signatures,
        "is_screen_protector": (
            "screen protector" in screen_text
            or "tempered glass" in screen_text
            or "privacy screen protector" in screen_text
        ),
    }
    with _TARGET_META_LOCK:
        if len(_TARGET_META_CACHE) >= _TARGET_META_CACHE_MAX:
            _TARGET_META_CACHE.clear()
        _TARGET_META_CACHE[target_id] = (target, meta)
    return meta


def target_phrase_matches(target: dict[str, Any], haystack: str) -> bool:
    for normalized, tokens in target_match_meta(target)["phrase_signatures"]:
        if len(normalized) >= 5 and normalized in haystack:
            return True
        if len(tokens) >= 2 and sum(1 for token in tokens if token in haystack) >= 2:
            return True
        if len(tokens) == 1 and len(tokens[0]) >= 6 and tokens[0] in haystack:
            return True
    return False


def target_match_tokens(normalized_phrase: str) -> list[str]:
    tokens: list[str] = []
    for token in normalized_phrase.split():
        if token in TARGET_MATCH_STOPWORDS:
            continue
        if len(token) >= 4 or token in {"tee", "bra"}:
            tokens.append(token)
    return tokens


def is_screen_protector_target(target: dict[str, Any]) -> bool:
    return bool(target_match_meta(target)["is_screen_protector"])


def is_screen_protector_non_same_product(haystack: str) -> bool:
    if not any(token in haystack for token in ["screen protector", "tempered glass", "privacy screen protector", "camera lens protector"]):
        return True
    if "apple watch" in haystack or "iwatch" in haystack:
        return True
    accessory_case_markers = [
        "phone case",
        "phone cases",
        "case for iphone",
        "iphone 15 case",
        "iphone 16 case",
        "iphone 17 case",
        "clear magnetic phone cases",
        "compatible with magsafe",
        "shockproof protective",
        "rugged shockproof",
    ]
    primary_screen_markers = [
        "tempered glass screen protector",
        "privacy screen protector",
        "screen protector for iphone",
        "camera lens protector",
        "installation frame",
        "anti spy",
        "bubble free",
    ]
    if any(marker in haystack for marker in accessory_case_markers) and not any(marker in haystack for marker in primary_screen_markers):
        return True
    return False


def unique_records(records: list[IntakeRecord], key_fn: Any) -> list[IntakeRecord]:
    seen: set[str] = set()
    result: list[IntakeRecord] = []
    for record in records:
        key = str(key_fn(record)).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result


def estimate_target_score(
    real_records: list[IntakeRecord],
    ranking_records: list[IntakeRecord],
    video_scripts: list[IntakeRecord],
    collection_jobs: list[IntakeRecord],
    gate_records: list[IntakeRecord],
) -> int:
    tk_records = [
        record
        for record in real_records
        if platform_report_priority(record) == 0
    ]
    video_records = [
        record
        for record in real_records
        if is_valid_video_evidence(record)
    ]
    creator_records = [
        record
        for record in real_records
        if is_valid_creator_or_store_evidence(record)
    ]
    review_records = [record for record in real_records if record.record_type == "review_insight" or str(record.fields.get("comment_count") or "").strip()]
    score = 18
    score += min(len(real_records), 10) * 2
    score += min(len(tk_records), 8) * 5
    score += min(len(video_records), 4) * 7
    score += min(len(creator_records), 4) * 5
    score += min(len(review_records), 3) * 4
    score += min(len(video_scripts), 2) * 3
    if any(str(record.fields.get("rank_position") or record.fields.get("rank") or "").isdigit() and int(record.fields.get("rank_position") or record.fields.get("rank")) <= 10 for record in ranking_records):
        score += 5
    if collection_jobs:
        score += 2
    score -= min(len(gate_records), 12) * 2
    if not tk_records:
        score = min(score, 50)
    if not video_records:
        score = min(score, 62)
    if not creator_records:
        score = min(score, 72)
    if not review_records:
        score = min(score, 78)
    if gate_records and len(gate_records) > len(real_records):
        score = min(score, 68)
    return max(0, min(score, 100))


def listing_direction_lines(target: dict[str, Any], ranking_records: list[IntakeRecord]) -> list[str]:
    name = str(target.get("name") or "Product")
    keywords = [str(item) for item in target.get("keywords", [])]
    if any("screen protector" in item.lower() for item in keywords):
        return [
            "- Title draft: Phone Screen Protector 3 Pack Tempered Glass with Alignment Frame, Bubble-Free Install, Camera Lens Protector Compatible with iPhone/Samsung.",
            "- Differentiation: exact model compatibility, 3-pack or 3+3 bundle, alignment frame, privacy option, camera lens protector.",
            "- Price test: $7.99 entry, $9.99 standard bundle, $12.99 privacy or 3+3 bundle.",
            "- Main proof: easy install, no bubbles, edge/cutout fit, clear touch feel, honest scratch/fingerprint proof.",
        ]
    top_title = str(ranking_records[0].fields.get("product_name") or "") if ranking_records else name
    return [
        f"- Title draft: {top_title or name} with clear product family, use case, bundle, and target platform keyword.",
        "- Differentiation: bundle value, proof image, clear size/spec, and review-pain-point solution.",
        "- Price test: create low, middle, and premium bundle tests before scaling ads.",
    ]


def image_direction_lines(target: dict[str, Any]) -> list[str]:
    keywords = " ".join(str(item).lower() for item in target.get("keywords", []))
    if "screen protector" in keywords or "tempered glass" in keywords:
        return [
            "- Main image: white background, package plus included protectors and alignment frame, model compatibility visible.",
            "- Detail image: edge/cutout fit, touch clarity, camera lens protector if included.",
            "- Install image: clean screen, align frame, one-press finish, bubble-free result.",
            "- Proof image: fingerprint/scratch/privacy-angle demonstration without exaggerated claims.",
        ]
    return [
        "- Main image: clean product-only white background.",
        "- Detail image: material/spec/feature proof.",
        "- Lifestyle image: real user scene that matches the target audience.",
    ]


def write_product_target_report(root: Path, target: dict[str, Any], run_date: str, content: str) -> Path:
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = safe_slug(str(target.get("id") or target.get("name") or "target"))
    path = output_dir / f"{PRODUCT_TARGET_REPORT_PREFIX}_{slug}_{run_date}.md"
    path.write_text(content, encoding="utf-8")
    return path


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_").lower()
    return slug or "target"


def compact_report_text(value: Any, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


# Clean report-label overrides. The original generated functions may contain
# legacy mojibake text; the report builder resolves these names at runtime.
def decision_label(decision: str) -> str:
    labels = {
        "not_ready_collect_more_data": "不够决策，先补真实数据",
        "watch_but_clear_login_or_verification_first": "先观察，优先处理登录/验证卡点",
        "ready_for_multi_ai_review_and_small_test_plan": "可进入多 AI 复盘并做小预算测试计划",
        "watch_and_collect_tiktok_video_evidence": "可观察，但必须继续补 TK 视频/达人证据",
        "low_confidence_do_not_scale": "低置信度，不能放量",
    }
    return labels.get(decision, decision)


def boss_takeaway_lines(
    target: dict[str, Any],
    score: int,
    real_records: list[IntakeRecord],
    core_tk_records: list[IntakeRecord],
    video_scripts: list[IntakeRecord],
    gate_records: list[IntakeRecord],
) -> list[str]:
    tk_count = len(core_tk_records)
    video_count = sum(
        1
        for record in real_records
        if is_valid_video_evidence(record)
    )
    creator_count = sum(
        1
        for record in real_records
        if is_valid_creator_or_store_evidence(record)
    )
    decision = target_decision(score, real_records, [], gate_records)
    lines = [
        f"- 结论：{decision_label(decision)}。",
        f"- TK核心证据：{tk_count} 条；视频证据：{video_count} 条；达人/店铺证据：{creator_count} 条；脚本草稿：{len(video_scripts)} 条。",
    ]
    if score >= 80 and tk_count and video_count:
        lines.append("- 老板动作：可以进入多 AI 选品会，做小预算测试计划；不要直接放量。")
    elif tk_count and video_count:
        lines.append("- 老板动作：先观察和补采，重点补视频脚本、达人质量、评论痛点和真实商品详情。")
    else:
        lines.append("- 老板动作：暂不决策，先补 TK 商品榜、视频、达人、评论，不用 Amazon 替代。")
    if gate_records:
        lines.append(f"- 风险/阻塞：{len(gate_records)} 个入口需要登录、验证或人工确认；不要绕过验证。")
    product_family = target.get("product_family") or target.get("name") or "this product"
    lines.append(f"- 内容重点：围绕 {product_family} 做 0-2 秒钩子、产品细节证明、真实场景、评论痛点和 CTA。")
    return lines
