from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any

from .storage import append_record
from .tk_case_learning import run_tk_case_learning_analysis
from .types import IntakeRecord


REPORT_PREFIX = "supervised_ai_council"
SELECTION_RECORD_TYPES = {
    "platform_ranking_signal",
    "hot_link",
    "viral_content_signal",
    "creator_spike_event",
    "creative_snapshot",
    "query_snapshot",
    "collection_job",
}


COUNCIL_EMPLOYEES = [
    {
        "agent_id": "agn_chief_of_staff_v1",
        "name": "AI Chief of Staff",
        "focus": "会议纪律、任务优先级、是否需要人工确认。",
    },
    {
        "agent_id": "agn_ecommerce_director_v1",
        "name": "AI Ecommerce Director",
        "focus": "商业判断：能不能做、为什么做、下一步怎么验证。",
    },
    {
        "agent_id": "agn_product_intelligence_v1",
        "name": "Product Intelligence",
        "focus": "商品、类目、价格、排名、生命周期。",
    },
    {
        "agent_id": "agn_competitor_intelligence_v1",
        "name": "Competitor Intelligence",
        "focus": "同行店铺、竞品链接、榜单变化、差评痛点。",
    },
    {
        "agent_id": "agn_viral_content_intelligence_v1",
        "name": "Viral Content Intelligence",
        "focus": "TikTok 视频、钩子、镜头、剪辑、评论购买意图。",
    },
    {
        "agent_id": "agn_influencer_intelligence_v1",
        "name": "Influencer Intelligence",
        "focus": "达人类型、均播、互动、联系方式、合作价值。",
    },
    {
        "agent_id": "agn_keyword_intelligence_v1",
        "name": "Keyword Intelligence",
        "focus": "平台关键词、长尾词、身份词、搜索意图。",
    },
    {
        "agent_id": "agn_listing_intelligence_v1",
        "name": "Listing Intelligence",
        "focus": "标题、卖点、主图、价格、平台标签。",
    },
    {
        "agent_id": "agn_risk_intelligence_v1",
        "name": "Risk Intelligence",
        "focus": "IP、商标、版权、禁限售、平台规则。",
    },
    {
        "agent_id": "agn_data_review_analyst_v1",
        "name": "Data Review Analyst",
        "focus": "数据缺口、证据质量、重复数据、是否可信。",
    },
]


@dataclass(slots=True)
class SupervisedCouncilResult:
    run_date: str
    records_reviewed: int
    video_records: int
    meeting_record: IntakeRecord
    task_records: list[IntakeRecord]
    normalized_video_records: list[IntakeRecord]
    video_analysis_result: Any
    report_path: Path
    json_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "records_reviewed": self.records_reviewed,
            "video_records": self.video_records,
            "meeting_record": self.meeting_record.to_dict(),
            "task_records": [record.to_dict() for record in self.task_records],
            "normalized_video_records": [record.to_dict() for record in self.normalized_video_records],
            "video_analysis_result": self.video_analysis_result.to_dict() if hasattr(self.video_analysis_result, "to_dict") else {},
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
        }


def run_supervised_ai_council(root: Path, run_date: str | None = None, limit: int = 40) -> SupervisedCouncilResult:
    root = root.resolve()
    run_date = run_date or date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    record_cards = selection_platform_record_cards(root, limit=limit)
    normalized_video_records = normalize_video_records(root, record_cards, run_date)
    analyses = [analyze_record(card) for card in record_cards]
    transcript = build_supervised_transcript(record_cards, analyses)
    supervisor_verdict = build_supervisor_verdict(record_cards, analyses)
    meeting_record = build_meeting_record(run_date, now, record_cards, transcript, supervisor_verdict)
    append_record(root, meeting_record)

    task_records = build_task_records(record_cards, analyses, run_date, now)
    for task in task_records:
        append_record(root, task)

    video_analysis_result = run_tk_case_learning_analysis(root, run_date)
    report = render_council_report(run_date, record_cards, analyses, transcript, supervisor_verdict, video_analysis_result)
    report_path, json_path = write_outputs(root, run_date, report, record_cards, analyses, transcript, supervisor_verdict)
    return SupervisedCouncilResult(
        run_date=run_date,
        records_reviewed=len(record_cards),
        video_records=len([card for card in record_cards if card["is_video"]]),
        meeting_record=meeting_record,
        task_records=task_records,
        normalized_video_records=normalized_video_records,
        video_analysis_result=video_analysis_result,
        report_path=report_path,
        json_path=json_path,
    )


def selection_platform_record_cards(root: Path, limit: int = 40) -> list[dict[str, Any]]:
    from .storage import read_records

    records: list[IntakeRecord] = []
    for record_type in SELECTION_RECORD_TYPES:
        records.extend(read_records(root, record_type))
    cards = [record_card(record) for record in records if is_selection_related(record)]
    cards.sort(key=lambda item: (not item["is_video"], -int(item["priority"]), item["created_at"]), reverse=False)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for card in cards:
        key = card["video_url"] or card["url"] or f"{card['record_type']}:{card['label']}:{card['platform']}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(card)
        if len(deduped) >= limit:
            break
    return deduped


def record_card(record: IntakeRecord) -> dict[str, Any]:
    fields = record.fields
    url = first_text(fields.get("url"), fields.get("page_url"), fields.get("product_url"), fields.get("source_url"))
    video_url = first_text(fields.get("video_url"), fields.get("source_video_url"))
    if not video_url and "tiktok.com" in url.lower() and "/video/" in url.lower():
        video_url = url
    platform = first_text(fields.get("source_platform"), fields.get("marketplace"), fields.get("platform"), fields.get("bridge_provider"), "Unknown")
    label = first_text(
        fields.get("product_name"),
        fields.get("product_theme"),
        fields.get("title"),
        fields.get("keyword"),
        fields.get("normalized_query"),
        fields.get("collection_target"),
        fields.get("page_title"),
        "Untitled signal",
    )
    is_video = bool(video_url) or record.record_type in {"viral_content_signal", "creator_spike_event", "creative_snapshot"}
    if "amazon" in platform.lower() and not video_url:
        is_video = False
    return {
        "record_id": record.record_id,
        "record_type": record.record_type,
        "created_at": record.created_at,
        "platform": platform,
        "label": label,
        "url": url,
        "video_url": video_url,
        "is_video": is_video,
        "priority": int(float(record.score.get("priority") or 0)),
        "source": record.source,
        "fields": compact_fields(fields),
        "missing_data": missing_data(fields, is_video),
    }


def is_selection_related(record: IntakeRecord) -> bool:
    text = json.dumps(record.fields, ensure_ascii=False).lower() + " " + record.source.lower() + " " + record.record_type
    hints = [
        "fastmoss",
        "kalodata",
        "echotik",
        "tiktok",
        "tik tok",
        "tk",
        "amazon",
        "etsy",
        "walmart",
        "shein",
        "shopify",
        "selection",
        "ranking",
        "product",
        "creator",
        "video",
    ]
    return any(hint in text for hint in hints)


def compact_fields(fields: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "product_name",
        "product_theme",
        "keyword",
        "normalized_query",
        "ranking_type",
        "rank_position",
        "growth_rate",
        "current_views",
        "baseline_avg_views",
        "creator_handle",
        "shop_name",
        "price",
        "rating",
        "review_count",
        "comment_insights",
    ]
    return {key: fields.get(key) for key in keys if fields.get(key) not in (None, "", [])}


def missing_data(fields: dict[str, Any], is_video: bool) -> list[str]:
    missing: list[str] = []
    if is_video:
        for key, label in [
            ("video_url", "video_url"),
            ("creator_handle", "creator"),
            ("current_views", "views"),
            ("hook", "hook"),
            ("comment_insights", "comments"),
        ]:
            if not fields.get(key) and not (key == "video_url" and fields.get("url")):
                missing.append(label)
    else:
        for key, label in [
            ("product_name", "product"),
            ("url", "url"),
            ("rank_position", "rank"),
            ("growth_rate", "growth"),
        ]:
            if not fields.get(key) and not fields.get("page_url") and label == "url":
                missing.append(label)
            elif label != "url" and not fields.get(key):
                missing.append(label)
    return missing


def normalize_video_records(root: Path, cards: list[dict[str, Any]], run_date: str) -> list[IntakeRecord]:
    normalized: list[IntakeRecord] = []
    for card in cards:
        if not card["is_video"]:
            continue
        video_url = card["video_url"] or card["url"]
        if not video_url:
            continue
        fields = {
            "video_url": video_url,
            "source_video_url": video_url,
            "product_theme": card["label"],
            "product_name": card["label"],
            "source_platform": "TikTok" if "amazon" not in card["platform"].lower() else card["platform"],
            "marketplace": "TikTok Shop" if "amazon" not in card["platform"].lower() else card["platform"],
            "creator_handle": card["fields"].get("creator_handle") or "",
            "current_views": card["fields"].get("current_views") or "",
            "baseline_avg_views": card["fields"].get("baseline_avg_views") or "",
            "comment_insights": card["fields"].get("comment_insights") or "",
            "collection_source_record_id": card["record_id"],
            "learning_run_date": run_date,
        }
        record = IntakeRecord(
            record_type="viral_content_signal",
            fields=fields,
            raw_text=json.dumps(card, ensure_ascii=False),
            source="supervised_ai_council.normalized_video",
            score={"priority": max(card["priority"], 95), "analysis_status": "needs_video_breakdown"},
            director_notes=["Normalized selection-platform video signal. Viral Content Intelligence must break it down first."],
            confidence=0.82,
            metadata={"supervised_council": True, "video_first": True},
        )
        append_record(root, record)
        normalized.append(record)
    return normalized


def analyze_record(card: dict[str, Any]) -> dict[str, Any]:
    if card["is_video"]:
        decision = "video_first_deep_breakdown"
        next_action = "Open or import the visible video evidence, then extract 0-2s hook, shot list, ASR/OCR, comment purchase intent, creator fit, and replication script."
        responsible = "Viral Content Intelligence"
        reason = "Video signal is the highest-value TikTok evidence; product selection must not ignore content performance."
    elif "amazon" in card["platform"].lower():
        decision = "marketplace_benchmark"
        next_action = "Use it for price, reviews, BSR/New Release signal, image/listing benchmark and negative-review pain points; do not use it as TikTok video evidence."
        responsible = "Product Intelligence"
        reason = "Amazon is useful for listing and demand benchmark, but not for TikTok content scripts."
    else:
        decision = "selection_platform_review"
        next_action = "Validate product link, ranking movement, creator/store source, keyword match and whether a video evidence task is needed."
        responsible = "Competitor Intelligence"
        reason = "Selection-platform data needs dedupe, source score, and cross-platform validation before strategy memory."
    risk = "manual_review_needed" if any(word in card["label"].lower() for word in ["disney", "nike", "nfl", "barbie", "stanley"]) else "normal_watch"
    return {
        "record_id": card["record_id"],
        "label": card["label"],
        "decision": decision,
        "responsible": responsible,
        "reason": reason,
        "next_action": next_action,
        "risk": risk,
        "missing_data": card["missing_data"],
    }


def build_supervised_transcript(cards: list[dict[str, Any]], analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    video_count = len([card for card in cards if card["is_video"]])
    transcript: list[dict[str, Any]] = []
    for employee in COUNCIL_EMPLOYEES:
        name = employee["name"]
        if name == "Viral Content Intelligence":
            statement = f"我要求视频优先。当前有 {video_count} 条视频/疑似视频信号，必须先拆 0-2 秒钩子、镜头、字幕、评论购买意图和复刻脚本。"
        elif name == "Data Review Analyst":
            missing = sum(len(item["missing_data"]) for item in analyses)
            statement = f"我发现还有 {missing} 个关键字段缺口。没有 video_url、播放量、评论或排名变化的记录只能进观察，不能写成结论。"
        elif name == "Risk Intelligence":
            risk_count = len([item for item in analyses if item["risk"] != "normal_watch"])
            statement = f"我会拦住 {risk_count} 条高风险或疑似 IP 记录。品牌、明星、球队、角色、专利和禁限售词必须先审。"
        elif name == "Product Intelligence":
            statement = "我负责把非视频选品平台数据拆成商品、价格、排名、评论、生命周期，不把大类目泛数据当精准商品结论。"
        elif name == "Competitor Intelligence":
            statement = "我负责逐条对照平台来源、商品链接、店铺链接、榜单类型和增长窗口，避免混入不相关商品。"
        elif name == "Influencer Intelligence":
            statement = "我只从视频和达人页里提达人，不凭商品卡猜达人。后续必须补联系方式、均播、互动率和合作记录。"
        elif name == "Keyword Intelligence":
            statement = "我会把每条商品拆成平台搜索词、身份词、长尾词和排除词，避免用一个中文词粗搜所有平台。"
        elif name == "Listing Intelligence":
            statement = "我只在竞品、评论和视频证据足够后生成 Listing 草稿，不直接改真实店铺标题、价格或图片。"
        elif name == "AI Chief of Staff":
            statement = "我负责会议秩序：每条记录必须有负责人、下一步和监督红线；所有真实外部动作进入确认队列。"
        else:
            statement = "我给最终判断：先看视频证据，再看商品榜单，再看供应链和风险。没有证据不放大。"
        transcript.append(
            {
                "agent_id": employee["agent_id"],
                "agent": name,
                "focus": employee["focus"],
                "statement": statement,
            }
        )
    return transcript


def build_supervisor_verdict(cards: list[dict[str, Any]], analyses: list[dict[str, Any]]) -> str:
    video_count = len([card for card in cards if card["is_video"]])
    return (
        f"Supervisor verdict: {len(cards)} selection-platform records reviewed, {video_count} video-priority records found. "
        "Every record must be analyzed by role, but TikTok/FastMoss/Kalodata video evidence gets first priority. "
        "No employee may publish, contact creators, change listings, download private video, bypass verification, or write final StrategyMemory without evidence."
    )


def build_meeting_record(
    run_date: str,
    now: str,
    cards: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
    supervisor_verdict: str,
) -> IntakeRecord:
    meeting_key = stable_key("supervised-council", run_date, len(cards), supervisor_verdict)
    fields = {
        "meeting_key": meeting_key,
        "task": "supervised_selection_platform_council",
        "task_name": "受监督选品平台数据会议",
        "provider": "local_supervised_agents",
        "record_count": len(cards),
        "video_record_count": len([card for card in cards if card["is_video"]]),
        "participant_count": len(transcript),
        "supervisor": "Codex",
        "supervisor_verdict": supervisor_verdict,
        "created_at_utc": now,
        "run_date": run_date,
    }
    return IntakeRecord(
        record_type="web_ai_meeting",
        fields=fields,
        raw_text=json.dumps({"records": cards, "transcript": transcript, "verdict": supervisor_verdict}, ensure_ascii=False),
        source="supervised_ai_council",
        score={"priority": 94, "review_type": "supervised_selection_platform_council"},
        director_notes=["Local supervised employee council. External real actions remain blocked until human confirmation."],
        confidence=0.92,
        metadata={"supervised": True, "video_first": True},
    )


def build_task_records(cards: list[dict[str, Any]], analyses: list[dict[str, Any]], run_date: str, now: str) -> list[IntakeRecord]:
    records: list[IntakeRecord] = []
    for card, analysis in zip(cards, analyses, strict=False):
        task_type = "video_deep_breakdown" if card["is_video"] else "selection_record_analysis"
        priority = 98 if card["is_video"] else max(70, min(90, card["priority"]))
        fields = {
            "task_queue_id": stable_key("tsk", task_type, card["record_id"], run_date),
            "task_type": task_type,
            "target_agent_id": responsible_agent_id(analysis["responsible"]),
            "target_entity_type": card["record_type"],
            "target_entity_id": card["record_id"],
            "priority": priority,
            "status": "queued",
            "approval_required": False,
            "safe_mode": True,
            "created_at_utc": now,
            "payload": {
                "label": card["label"],
                "platform": card["platform"],
                "url": card["video_url"] or card["url"],
                "decision": analysis["decision"],
                "next_action": analysis["next_action"],
                "missing_data": analysis["missing_data"],
                "forbidden_actions": [
                    "bypass_captcha_or_slider",
                    "download_private_video",
                    "contact_creator",
                    "publish_or_change_store",
                    "write_final_strategy_without_evidence",
                ],
            },
        }
        records.append(
            IntakeRecord(
                record_type="task_queue",
                fields=fields,
                raw_text=json.dumps({"card": card, "analysis": analysis}, ensure_ascii=False),
                source="supervised_ai_council.task_router",
                score={"priority": priority},
                director_notes=["Task created by supervised employee council. Video records are routed first."],
                confidence=0.9,
            )
        )
    return records


def responsible_agent_id(name: str) -> str:
    for employee in COUNCIL_EMPLOYEES:
        if employee["name"] == name:
            return employee["agent_id"]
    return "agn_ecommerce_director_v1"


def render_council_report(
    run_date: str,
    cards: list[dict[str, Any]],
    analyses: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
    supervisor_verdict: str,
    video_analysis_result: Any,
) -> str:
    lines = [
        "# Supervised AI Employee Council",
        "",
        f"Date: {run_date}",
        "",
        "## Boss Summary",
        "",
        supervisor_verdict,
        "",
        f"- Records reviewed: {len(cards)}",
        f"- Video-priority records: {len([card for card in cards if card['is_video']])}",
        f"- Video breakdowns created this run: {getattr(video_analysis_result, 'breakdowns_created', 0)}",
        f"- Video scripts created this run: {getattr(video_analysis_result, 'scripts_created', 0)}",
        "",
        "## Employee Discussion",
        "",
    ]
    for turn in transcript:
        lines.append(f"### {turn['agent']}")
        lines.append(turn["statement"])
        lines.append("")
    lines.extend(["## Record Routing", ""])
    for analysis in analyses[:30]:
        lines.append(
            f"- {analysis['label']}: {analysis['decision']} -> {analysis['responsible']}; next: {analysis['next_action']}"
        )
    if len(analyses) > 30:
        lines.append(f"- ... plus {len(analyses) - 30} more records in the JSON output.")
    lines.extend(
        [
            "",
            "## Supervisor Guardrails",
            "",
            "- Video is the priority for TikTok growth, especially FastMoss/Kalodata/TikTok Shop product-card and creator videos.",
            "- Amazon data is not video evidence. Use it for rankings, reviews, prices, listing and image benchmarks.",
            "- Every video must eventually output: hook, scene, camera movement, editing rhythm, subtitles/voiceover, comment intent, creator fit and replication script.",
            "- No real store action, creator outreach, publishing, delisting, price change, ad change or verification bypass without human confirmation.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(
    root: Path,
    run_date: str,
    report: str,
    cards: list[dict[str, Any]],
    analyses: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
    supervisor_verdict: str,
) -> tuple[Path, Path]:
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{REPORT_PREFIX}_{run_date}.md"
    json_path = output_dir / f"{REPORT_PREFIX}_{run_date}.json"
    report_path.write_text(report, encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "run_date": run_date,
                "records": cards,
                "analyses": analyses,
                "transcript": transcript,
                "supervisor_verdict": supervisor_verdict,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report_path, json_path


def first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def stable_key(*parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    return sha1(raw.encode("utf-8")).hexdigest()[:18]
