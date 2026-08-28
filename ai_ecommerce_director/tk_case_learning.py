from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from .scoring import score_record
from .storage import append_record, read_records, write_report
from .types import IntakeRecord


TK_CASE_LEARNING_CONFIG = Path("config") / "tk_case_learning.json"


PRODUCT_THEMES = [
    "washed t shirt",
    "heavyweight t shirt",
    "oversized t shirt",
    "blue collar dad shirt",
    "dog dad shirt",
    "fishing shirt",
    "christian shirt",
    "mechanic shirt",
    "truck driver shirt",
    "workwear hat",
    "trucker hat",
    "melatonin gummies",
    "amino acid cleanser",
    "retinol serum",
    "hydrating toner",
    "hair growth oil",
    "portable blender",
    "magnetic power bank",
    "car phone holder",
    "neck fan",
    "heated vest",
    "posture corrector",
    "pet grooming glove",
    "dog anxiety bed",
    "cat water fountain",
    "camping lantern",
    "fishing tackle box",
    "gym shaker bottle",
    "waist trainer",
    "nail gel kit",
    "makeup organizer",
    "travel compression bag",
    "kitchen slicer",
    "silicone food container",
    "baby sensory toy",
    "teacher gift",
    "nurse gift",
    "veteran gift",
    "patriotic decor",
    "halloween shirt",
    "christmas pajama",
    "father's day gift",
    "mother's day gift",
    "valentine gift",
    "easter basket",
    "4th of july shirt",
    "home workout equipment",
    "desk organizer",
    "LED mirror",
    "waterproof phone pouch",
]


CONTENT_ANGLES = [
    "first 2 second hook",
    "problem solution demo",
    "before after",
    "unboxing",
    "street reaction",
    "dad gift emotional story",
    "identity recognition",
    "comment reply video",
    "product card conversion",
    "creator try on",
    "close up detail shot",
    "factory quality proof",
    "comparison with cheap version",
    "routine video",
    "POV story",
    "customer review proof",
    "limited time discount",
    "bundle offer",
    "day in the life",
    "viral sound remix",
]


@dataclass(slots=True)
class TkCaseLearningResult:
    run_date: str
    requested: int
    created_jobs: int
    existing_jobs: int
    report_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "requested": self.requested,
            "created_jobs": self.created_jobs,
            "existing_jobs": self.existing_jobs,
            "report_path": str(self.report_path),
        }


@dataclass(slots=True)
class TkCaseAnalysisResult:
    run_date: str
    videos_seen: int
    breakdowns_created: int
    scripts_created: int
    memories_created: int
    report_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "videos_seen": self.videos_seen,
            "breakdowns_created": self.breakdowns_created,
            "scripts_created": self.scripts_created,
            "memories_created": self.memories_created,
            "report_path": str(self.report_path),
        }


MARKETS = ["US", "UK", "CA", "AU", "DE", "FR", "JP", "KR", "MX", "BR", "SG", "MY", "TH", "VN", "PH", "ID"]


DISCOVERY_PATHS = [
    "buyer shop search",
    "product card video",
    "creator profile spike",
    "comment purchase signal",
    "new product launch",
    "same product competitor",
    "low price competitor",
    "premium brand competitor",
]


CREATOR_ARCHETYPES = [
    "micro creator",
    "mid tier creator",
    "shop owner video",
    "factory proof video",
    "lifestyle creator",
    "profession niche creator",
]


def seed_tk_case_learning_pool(root: Path, limit: int = 1000, run_date: str | None = None) -> TkCaseLearningResult:
    run_date = run_date or date.today().isoformat()
    existing_keys = {
        str(record.fields.get("case_learning_key") or "")
        for record in read_records(root, "collection_job")
        if record.fields.get("case_learning_key")
    }
    created = 0
    existing = 0
    for source in build_case_learning_sources(limit):
        if source["case_learning_key"] in existing_keys:
            existing += 1
            continue
        record = build_collection_job_record(source, run_date)
        append_record(root, record)
        created += 1
    write_case_learning_config(root, limit)
    report = render_case_learning_report(root, run_date, limit, created, existing)
    report_path = write_report(root, f"tk_case_learning_{run_date}", report)
    return TkCaseLearningResult(run_date, limit, created, existing, report_path)


def build_case_learning_sources(limit: int = 1000) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for theme in PRODUCT_THEMES:
        for angle in CONTENT_ANGLES:
            for market in MARKETS:
                for discovery_path in DISCOVERY_PATHS:
                    for creator_type in CREATOR_ARCHETYPES:
                        query = f"{theme} {angle} {market} {discovery_path} {creator_type} tiktok shop"
                        sources.append(
                            {
                                "case_learning_key": f"tk-case:{theme}:{angle}:{market}:{discovery_path}:{creator_type}",
                                "product_theme": theme,
                                "content_angle": angle,
                                "market": market,
                                "discovery_path": discovery_path,
                                "creator_type": creator_type,
                                "query": query,
                                "tiktok_search_url": f"https://www.tiktok.com/search?q={quote_plus(query)}",
                                "google_search_url": f"https://www.google.com/search?q={quote_plus('site:tiktok.com/@ ' + query)}",
                                "fastmoss_hint": f"https://www.fastmoss.com/zh/search?keyword={quote_plus(theme)}",
                            }
                        )
                        if len(sources) >= limit:
                            return sources
    return sources


def build_collection_job_record(source: dict[str, Any], run_date: str) -> IntakeRecord:
    fields = {
        "case_learning_key": source["case_learning_key"],
        "collection_target": "tk_viral_product_video_case",
        "source_platform": "TikTok",
        "marketplace": "TikTok Shop",
        "product_theme": source["product_theme"],
        "content_angle": source["content_angle"],
        "market": source.get("market") or "",
        "discovery_path": source.get("discovery_path") or "",
        "creator_type": source.get("creator_type") or "",
        "target_keyword": source["query"],
        "url": source["tiktok_search_url"],
        "google_search_url": source["google_search_url"],
        "fastmoss_hint": source["fastmoss_hint"],
        "record_type_to_create": "viral_content_signal",
        "analysis_route": "video_breakdown_and_product_script",
        "automation_level": "L0_read_only_then_L2_draft",
        "allowed_actions": [
            "open_public_search",
            "read_visible_video_metadata",
            "save_video_url",
            "draft_video_breakdown",
            "draft_product_script",
            "update_strategy_memory",
        ],
        "forbidden_actions": [
            "bypass_captcha_or_slider",
            "login_without_confirmation",
            "download_private_video",
            "contact_creator",
            "publish_or_change_store",
        ],
        "learning_status": "queued",
        "required_outputs": [
            "viral_reason_analysis",
            "timeline_breakdown",
            "hook_analysis",
            "shot_and_editing_script",
            "audience_emotion_scene_analysis",
            "comment_purchase_signal",
            "store_owned_script",
            "influencer_brief_script",
            "replication_plan",
        ],
        "learning_run_date": run_date,
    }
    score, notes = score_record("collection_job", fields)
    return IntakeRecord(
        record_type="collection_job",
        fields=fields,
        raw_text=json.dumps(source, ensure_ascii=False),
        source="tk_case_learning_seed",
        score=score,
        director_notes=notes,
        metadata={"tk_case_learning": True, "automation_mode": "safe_public_learning"},
    )


def write_case_learning_config(root: Path, limit: int) -> Path:
    path = root / TK_CASE_LEARNING_CONFIG
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "enabled": True,
        "safe_mode": True,
        "target_case_count": limit,
        "batch_mode": "continuous_no_global_cap",
        "required_per_video_outputs": [
            "video_breakdown",
            "video_script",
            "viral_reason_report",
            "strategy_memory",
        ],
        "notes": [
            "Seeded TK product-video case learning jobs. This is a continuous batch, not a global cap.",
            "Jobs are not fake cases; they are search tasks waiting for public collection, plugin capture, platform tool capture, or user-fed real links.",
            "Every real video case must be turned into video_breakdown, video_script, viral_reason_report and strategy memory.",
            "Do not bypass login, captcha, slider, payment, authorization or platform restrictions.",
            "Real external actions stay pending confirmation.",
        ],
        "product_themes": PRODUCT_THEMES,
        "content_angles": CONTENT_ANGLES,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def tk_case_learning_summary(root: Path) -> dict[str, Any]:
    jobs = [record for record in read_records(root, "collection_job") if record.fields.get("case_learning_key")]
    viral = read_records(root, "viral_content_signal")
    creator_spikes = read_records(root, "creator_spike_event")
    breakdowns = read_records(root, "video_breakdown")
    scripts = read_records(root, "video_script")
    memories = [record for record in read_records(root, "strategy_memory") if record.fields.get("memory_type") == "tk_content_strategy"]
    video_sources = viral_video_sources(root)
    breakdown_keys = linked_video_keys(breakdowns)
    script_keys = linked_video_keys(scripts)
    pending = [item for item in video_sources if item["key"] not in breakdown_keys or item["key"] not in script_keys]
    return {
        "queuedJobs": len(jobs),
        "viralCases": len(viral),
        "creatorSpikeCases": len(creator_spikes),
        "realVideoCases": len(video_sources),
        "videoBreakdowns": len(breakdowns),
        "productScripts": len(scripts),
        "strategyMemories": len(memories),
        "pendingVideoAnalyses": len(pending),
        "latestJobs": [compact_job(record) for record in sorted(jobs, key=lambda item: item.created_at, reverse=True)[:20]],
        "latestPendingVideos": pending[:20],
    }


def compact_job(record: IntakeRecord) -> dict[str, Any]:
    fields = record.fields
    return {
        "id": record.record_id,
        "productTheme": fields.get("product_theme") or "",
        "contentAngle": fields.get("content_angle") or "",
        "url": fields.get("url") or "",
        "status": fields.get("learning_status") or "queued",
    }


def render_case_learning_report(root: Path, run_date: str, limit: int, created: int, existing: int) -> str:
    summary = tk_case_learning_summary(root)
    lines = [
        "# TK Case Learning Pool",
        "",
        f"Date: {run_date}",
        f"Requested jobs: {limit}",
        f"Created jobs: {created}",
        f"Existing jobs: {existing}",
        "",
        "## Current Memory",
        "",
        f"- Queued learning jobs: {summary['queuedJobs']}",
        f"- Viral cases saved: {summary['viralCases']}",
        f"- Creator spike cases saved: {summary['creatorSpikeCases']}",
        f"- Real video cases waiting/learned: {summary['realVideoCases']}",
        f"- Video breakdowns saved: {summary['videoBreakdowns']}",
        f"- Product scripts saved: {summary['productScripts']}",
        f"- Pending video analyses: {summary['pendingVideoAnalyses']}",
        f"- Strategy memories saved: {summary['strategyMemories']}",
        "",
        "## Safety",
        "",
        "- Allowed: public reading, visible metadata capture, URL saving, video breakdown drafts, product script drafts, strategy memory updates.",
        "- Not allowed: captcha/slider bypass, unconfirmed login, creator contact, store publishing, price changes, campaign signup, payments.",
        "",
    ]
    return "\n".join(lines)


def run_tk_case_learning_analysis(root: Path, run_date: str | None = None) -> TkCaseAnalysisResult:
    run_date = run_date or date.today().isoformat()
    video_sources = viral_video_sources(root)
    breakdown_keys = linked_video_keys(read_records(root, "video_breakdown"))
    script_keys = linked_video_script_keys(read_records(root, "video_script"))
    memory_keys = linked_video_keys(read_records(root, "strategy_memory"))
    breakdowns_created = 0
    scripts_created = 0
    memories_created = 0
    report_sections = [
        "# TK Video Case Learning Analysis",
        "",
        f"Date: {run_date}",
        f"Real video cases scanned: {len(video_sources)}",
        "",
    ]
    for source in video_sources:
        if source["key"] not in breakdown_keys:
            append_record(root, build_video_breakdown_record(source, run_date))
            breakdown_keys.add(source["key"])
            breakdowns_created += 1
        for script_type in ["store_owned", "influencer_brief"]:
            script_key = f"{source['key']}:{script_type}"
            if script_key not in script_keys:
                append_record(root, build_video_script_record(source, run_date, script_type))
                script_keys.add(script_key)
                scripts_created += 1
        if source["key"] not in memory_keys:
            append_record(root, build_strategy_memory_record(source, run_date))
            memory_keys.add(source["key"])
            memories_created += 1
        report_sections.extend(render_video_case_report_section(source))
    if not video_sources:
        report_sections.extend(
            [
                "## No Real Video Cases Yet",
                "",
                "Feed or capture real TikTok/FastMoss/Kalodata/EchoTik video links first. The system will not invent fake cases.",
                "",
            ]
        )
    report_path = write_report(root, f"tk_video_case_analysis_{run_date}", "\n".join(report_sections))
    return TkCaseAnalysisResult(run_date, len(video_sources), breakdowns_created, scripts_created, memories_created, report_path)


def viral_video_sources(root: Path) -> list[dict[str, Any]]:
    records = read_records(root, "viral_content_signal") + read_records(root, "creator_spike_event")
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in sorted(records, key=lambda item: item.created_at):
        fields = record.fields
        url = str(fields.get("video_url") or fields.get("url") or fields.get("page_url") or "").strip()
        if not url:
            continue
        key = normalize_video_key(url)
        if key in seen:
            continue
        seen.add(key)
        product_theme = str(fields.get("product_theme") or fields.get("product_name") or fields.get("keyword") or "unknown product").strip()
        comments = str(fields.get("comment_insights") or fields.get("comments") or fields.get("review_signal") or "").strip()
        hook = str(fields.get("hook") or fields.get("hook_text") or fields.get("title") or "").strip()
        source = {
            "key": key,
            "url": url,
            "record_type": record.record_type,
            "product_theme": product_theme,
            "creator": str(fields.get("creator_handle") or fields.get("creator") or fields.get("shop_name") or "").strip(),
            "platform": str(fields.get("source_platform") or fields.get("marketplace") or "TikTok").strip(),
            "views": fields.get("current_views") or fields.get("latest_video_views") or fields.get("views") or "",
            "previous_views": fields.get("previous_views") or fields.get("baseline_avg_views") or "",
            "growth_window": fields.get("growth_window") or "",
            "comments": comments,
            "hook": hook,
            "scene": str(fields.get("scene") or fields.get("video_scene") or "").strip(),
            "raw_fields": fields,
        }
        sources.append(source)
    return sources


def linked_video_keys(records: list[IntakeRecord]) -> set[str]:
    keys: set[str] = set()
    for record in records:
        fields = record.fields
        raw_key = fields.get("source_video_key") or fields.get("video_case_key")
        url = fields.get("source_video_url") or fields.get("video_url") or fields.get("url")
        key = str(raw_key or "").strip() or normalize_video_key(str(url or ""))
        if key:
            keys.add(key)
    return keys


def linked_video_script_keys(records: list[IntakeRecord]) -> set[str]:
    keys: set[str] = set()
    for record in records:
        fields = record.fields
        video_key = str(fields.get("source_video_key") or fields.get("video_case_key") or "").strip()
        if not video_key:
            video_key = normalize_video_key(str(fields.get("source_video_url") or fields.get("video_url") or fields.get("url") or ""))
        script_type = str(fields.get("script_type") or "store_owned").strip() or "store_owned"
        if video_key:
            keys.add(f"{video_key}:{script_type}")
    return keys


def normalize_video_key(url: str) -> str:
    return url.strip().split("?")[0].rstrip("/").lower()


def build_video_breakdown_record(source: dict[str, Any], run_date: str) -> IntakeRecord:
    fields = {
        "source_video_key": source["key"],
        "memory_key": f"tk-video-case:{source['key']}",
        "source_video_url": source["url"],
        "video_url": source["url"],
        "product_theme": source["product_theme"],
        "creator_handle": source["creator"],
        "analysis_status": "draft_from_visible_metadata",
        "timeline_structure": "0-2s hook, 2-5s product/scene reveal, 5-10s proof or emotional turn, 10-15s product card or comment CTA. Needs frame-level verification after video is viewable.",
        "hook_text": source["hook"] or "Extract exact hook from title/subtitle/first frame after video review.",
        "hook_type": infer_hook_type(source),
        "audience_profile": infer_audience_profile(source),
        "scene": source["scene"] or infer_scene(source),
        "emotion": infer_emotion(source),
        "comment_insights": source["comments"] or "Collect top comments: need this, where to buy, gift reason, objection, size/quality question.",
        "viral_reason": infer_viral_reason(source),
        "editing_notes": "Capture shot rhythm, zoom/detail shots, text overlay placement, cut speed, product card timing, sound/voiceover fit.",
        "replicate_plan": build_replicate_plan(source),
        "required_next_step": "Open the real video, verify frame-by-frame timeline, then replace draft assumptions with exact shots and subtitles.",
        "learning_run_date": run_date,
    }
    score, notes = score_record("video_breakdown", fields)
    return IntakeRecord(
        record_type="video_breakdown",
        fields=fields,
        raw_text=json.dumps({"source": source, "draft_policy": "visible_metadata_first_then_frame_verification"}, ensure_ascii=False),
        source="tk_case_learning_analysis",
        score=score,
        director_notes=notes,
        metadata={"source_video_key": source["key"], "auto_generated_draft": True},
    )


def build_video_script_record(source: dict[str, Any], run_date: str, script_type: str) -> IntakeRecord:
    store_owned = script_type == "store_owned"
    fields = {
        "source_video_key": source["key"],
        "script_key": f"{source['key']}:{script_type}",
        "source_video_url": source["url"],
        "video_url": source["url"],
        "script_type": script_type,
        "product_theme": source["product_theme"],
        "target_store": "TBD" if store_owned else "",
        "creator_type": "" if store_owned else infer_creator_type(source),
        "hook": source["hook"] or infer_script_hook(source),
        "shot_list": build_shot_list(source, store_owned=store_owned),
        "voiceover_or_subtitles": build_voiceover(source, store_owned=store_owned),
        "cta": "Show product card at the emotional proof moment; CTA should match the comment purchase reason.",
        "why_it_can_work": infer_viral_reason(source),
        "production_notes": "Use the real winning video's structure, but change product, scene, people, wording and brand assets so it is not a copy.",
        "learning_run_date": run_date,
    }
    score, notes = score_record("video_script", fields)
    return IntakeRecord(
        record_type="video_script",
        fields=fields,
        raw_text=json.dumps({"source": source, "script_type": script_type}, ensure_ascii=False),
        source="tk_case_learning_analysis",
        score=score,
        director_notes=notes,
        metadata={"source_video_key": source["key"], "auto_generated_draft": True},
    )


def build_strategy_memory_record(source: dict[str, Any], run_date: str) -> IntakeRecord:
    fields = {
        "source_video_key": source["key"],
        "source_video_url": source["url"],
        "memory_type": "tk_content_strategy",
        "product_theme": source["product_theme"],
        "decision_stage": "case_learning",
        "winning_pattern": infer_viral_reason(source),
        "do": build_replicate_plan(source),
        "do_not": "Do not copy the exact creator, exact subtitles, copyrighted music, brand marks, celebrity/team/IP elements, or private account content.",
        "review_after": "After 3-5 replicated videos or 72 hours of posting data.",
        "learning_run_date": run_date,
    }
    score, notes = score_record("strategy_memory", fields)
    return IntakeRecord(
        record_type="strategy_memory",
        fields=fields,
        raw_text=json.dumps(source, ensure_ascii=False),
        source="tk_case_learning_analysis",
        score=score,
        director_notes=notes,
        metadata={"source_video_key": source["key"], "auto_generated_draft": True},
    )


def render_video_case_report_section(source: dict[str, Any]) -> list[str]:
    return [
        f"## {source['product_theme']} · {source['url']}",
        "",
        f"- Creator/source: {source['creator'] or source['platform']}",
        f"- Views/growth: {source['views'] or 'unknown'} / {source['growth_window'] or 'unknown window'}",
        f"- Why it may be viral: {infer_viral_reason(source)}",
        f"- Hook type: {infer_hook_type(source)}",
        f"- Audience: {infer_audience_profile(source)}",
        f"- Scene/emotion: {infer_scene(source)} / {infer_emotion(source)}",
        f"- Store-owned script: {build_shot_list(source, store_owned=True)}",
        f"- Influencer brief: {build_shot_list(source, store_owned=False)}",
        f"- Replication plan: {build_replicate_plan(source)}",
        "",
    ]


def infer_hook_type(source: dict[str, Any]) -> str:
    text = " ".join([source.get("hook", ""), source.get("comments", ""), source.get("product_theme", "")]).lower()
    if any(word in text for word in ["dad", "blue collar", "mechanic", "nurse", "teacher", "veteran"]):
        return "identity_recognition"
    if any(word in text for word in ["before", "after", "problem", "fix", "solution"]):
        return "problem_solution"
    if any(word in text for word in ["gift", "buying for", "husband", "father", "mom"]):
        return "gift_emotion"
    if any(word in text for word in ["cheap", "compare", "dupe", "better"]):
        return "comparison_proof"
    return "curiosity_or_product_demo"


def infer_audience_profile(source: dict[str, Any]) -> str:
    text = source.get("product_theme", "").lower()
    if "dad" in text or "blue collar" in text or "mechanic" in text or "truck" in text:
        return "US working-class men/families, gift buyers, identity-driven buyers."
    if "dog" in text or "pet" in text or "cat" in text:
        return "Pet owners, gift buyers, emotionally attached companion buyers."
    if any(word in text for word in ["cleanser", "serum", "toner", "beauty", "makeup"]):
        return "Beauty/skincare buyers comparing results, texture, routine and proof."
    if any(word in text for word in ["power bank", "phone", "charger"]):
        return "Practical tech buyers who respond to convenience, proof and problem solving."
    return "TikTok Shop buyers who respond to visible proof, emotion, identity or useful product demos."


def infer_scene(source: dict[str, Any]) -> str:
    text = source.get("product_theme", "").lower()
    if any(word in text for word in ["mechanic", "blue collar", "truck", "workwear"]):
        return "garage, truck, job site, warehouse, workbench"
    if "fishing" in text:
        return "dock, lake, boat, outdoor morning routine"
    if any(word in text for word in ["cleanser", "serum", "toner"]):
        return "bathroom mirror, skincare routine, close-up texture shot"
    if "dog" in text or "pet" in text:
        return "home entry, couch, yard, pet close-up"
    return "daily life scene plus close-up product proof"


def infer_emotion(source: dict[str, Any]) -> str:
    hook_type = infer_hook_type(source)
    return {
        "identity_recognition": "recognition, pride, belonging",
        "problem_solution": "relief, surprise, control",
        "gift_emotion": "love, gratitude, family warmth",
        "comparison_proof": "trust, smart purchase, value",
    }.get(hook_type, "curiosity, confidence, desire")


def infer_creator_type(source: dict[str, Any]) -> str:
    profile = infer_audience_profile(source)
    if "working-class" in profile:
        return "blue-collar lifestyle creator or real worker creator"
    if "Pet owners" in profile:
        return "pet owner creator with real home scenes"
    if "Beauty" in profile:
        return "beauty routine creator with close-up skin/product proof"
    return "niche creator who naturally uses this product in daily life"


def infer_script_hook(source: dict[str, Any]) -> str:
    product = source.get("product_theme") or "this product"
    hook_type = infer_hook_type(source)
    if hook_type == "identity_recognition":
        return f"Nobody talks about people who actually need {product}."
    if hook_type == "gift_emotion":
        return f"I found the gift they would never ask for: {product}."
    if hook_type == "problem_solution":
        return f"I did not expect {product} to fix this so fast."
    return f"I kept seeing {product} for a reason."


def infer_viral_reason(source: dict[str, Any]) -> str:
    hook_type = infer_hook_type(source)
    comments = source.get("comments") or ""
    reason = {
        "identity_recognition": "It likely connects product proof with a strong identity group, so viewers feel seen and tag/buy for themselves or family.",
        "problem_solution": "It likely makes the pain point and solution visible in the first seconds, reducing doubt quickly.",
        "gift_emotion": "It likely turns the product into a gift/emotional reason, which creates comment purchase intent.",
        "comparison_proof": "It likely earns trust by comparing value, quality or result against a weaker alternative.",
    }.get(hook_type, "It likely combines fast visible proof, simple product card timing and a clear reason to buy.")
    if comments:
        reason += f" Comment signal: {comments[:180]}"
    return reason


def build_replicate_plan(source: dict[str, Any]) -> str:
    product = source.get("product_theme") or "the product"
    scene = infer_scene(source)
    return (
        f"Replicate the structure for {product}: keep the first-2-second hook, shoot in {scene}, "
        "show one close-up proof shot, one human/emotional shot, one product-card CTA, and create 3 variants: "
        "store-owned demo, influencer daily-life version, and comment-reply version."
    )


def build_shot_list(source: dict[str, Any], *, store_owned: bool) -> str:
    scene = infer_scene(source)
    product = source.get("product_theme") or "product"
    if store_owned:
        return (
            f"0-2s hook text over {scene}; 2-5s hand-held close-up of {product}; "
            "5-9s show detail/quality/result; 9-13s show buyer use case; 13-16s product card CTA."
        )
    return (
        f"0-2s creator appears naturally in {scene}; 2-5s creator problem/reason; "
        f"5-10s creator uses {product}; 10-14s emotional/result proof; 14-17s soft CTA with product card."
    )


def build_voiceover(source: dict[str, Any], *, store_owned: bool) -> str:
    hook = source.get("hook") or infer_script_hook(source)
    if store_owned:
        return f"{hook} / Here is the detail most people miss / This is why buyers keep asking where to get it."
    return f"{hook} / I tried it in my real routine / This is the part that made me understand why it is selling."
