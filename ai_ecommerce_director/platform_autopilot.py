from __future__ import annotations

import json
import webbrowser
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .daily_runner import build_records_from_source, fetch_public_page
from .competitor_monitor import build_competitor_watch_sources
from .product_matcher import compare_product_text
from .product_targets import build_product_target_sources
from .selection_intelligence import SELECTION_CONFIG, build_selection_category_sources
from .storage import append_record, read_records
from .types import IntakeRecord


PLATFORM_AUTOPILOT_CONFIG = Path("config") / "platform_autopilot.json"
PLATFORM_AUTOPILOT_REPORT_PREFIX = "platform_autopilot"

VERIFICATION_SIGNALS = [
    "captcha",
    "security check",
    "verify you are human",
    "verify to continue",
    "verification",
    "slider",
    "滑块",
    "验证码",
    "人机验证",
    "安全验证",
    "请完成验证",
]


@dataclass(slots=True)
class PlatformRunResult:
    run_date: str
    statuses: list[dict[str, Any]]
    records: list[IntakeRecord]
    report: str
    report_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "statuses": self.statuses,
            "records": [record.to_dict() for record in self.records],
            "report": self.report,
            "report_path": str(self.report_path),
        }


def run_platform_autopilot(
    root: Path,
    run_date: str | None = None,
    *,
    open_browser: bool = True,
    collect_public: bool = True,
) -> PlatformRunResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    config = load_platform_autopilot_config(root)
    sources = list(config.get("sources", [])) if isinstance(config.get("sources", []), list) else []
    if should_include_selection_category_sources(root, config):
        sources.extend(build_selection_category_sources(root))
    sources.extend(build_product_target_sources(root))
    sources.extend(build_competitor_watch_sources(root))
    statuses: list[dict[str, Any]] = []
    records: list[IntakeRecord] = []

    for raw_source in sources:
        if not isinstance(raw_source, dict):
            continue
        status, source_records = run_platform_source(
            root,
            raw_source,
            report_date,
            open_browser=open_browser,
            collect_public=collect_public,
        )
        statuses.append(status)
        records.extend(source_records)

    report = build_platform_report(report_date, statuses, records)
    report_path = write_platform_report(root, report_date, report)
    return PlatformRunResult(report_date, statuses, records, report, report_path)


def load_platform_autopilot_config(root: Path) -> dict[str, Any]:
    path = root / PLATFORM_AUTOPILOT_CONFIG
    if not path.exists():
        return {"safe_mode": True, "sources": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"safe_mode": True, "sources": []}


def should_include_selection_category_sources(root: Path, config: dict[str, Any]) -> bool:
    """Keep broad category discovery opt-in for autopilot reports."""
    generated_sources = config.get("generated_sources")
    if isinstance(generated_sources, dict) and "selection_categories" in generated_sources:
        return bool(generated_sources.get("selection_categories"))
    if "include_selection_category_sources" in config:
        return bool(config.get("include_selection_category_sources"))
    return (root / SELECTION_CONFIG).exists()


def run_platform_source(
    root: Path,
    source: dict[str, Any],
    run_date: str,
    *,
    open_browser: bool,
    collect_public: bool,
) -> tuple[dict[str, Any], list[IntakeRecord]]:
    source_id = str(source.get("id") or source.get("name") or "unnamed-platform").strip()
    if not source.get("enabled", False):
        return {"source_id": source_id, "status": "skipped", "reason": "source disabled"}, []

    url = str(source.get("url") or "").strip()
    if not url:
        return {"source_id": source_id, "status": "missing_url", "reason": "platform URL is missing"}, []

    opened = open_browser_url(url) if open_browser else False
    if source.get("requires_login"):
        job_record = save_collection_job_record(root, source, run_date, "manual_gate", "Login, slider, or verification requires human action.")
        return {
            "source_id": source_id,
            "status": "manual_gate",
            "url": url,
            "opened": opened,
            "reason": "Login, slider, or verification requires human action. Use the extension after passing it.",
            "verification_policy": "pause_for_human",
            "saved_records": 1,
            "record": job_record.to_dict(),
        }, [job_record]

    if not collect_public:
        job_record = save_collection_job_record(root, source, run_date, "opened_only", "Opened source but public collection is disabled.")
        return {"source_id": source_id, "status": "opened_only", "url": url, "opened": opened, "saved_records": 1, "record": job_record.to_dict()}, [job_record]

    try:
        page = fetch_public_page(url)
    except Exception as exc:  # noqa: BLE001 - source-level status belongs in report.
        job_record = save_collection_job_record(root, source, run_date, "fetch_failed", str(exc))
        return {"source_id": source_id, "status": "failed", "url": url, "opened": opened, "reason": str(exc), "saved_records": 1, "record": job_record.to_dict()}, [job_record]

    barrier = detect_verification_barrier(page.title, page.text)
    if barrier:
        job_record = save_collection_job_record(root, source, run_date, "verification_required", barrier)
        return {
            "source_id": source_id,
            "status": "verification_required",
            "url": url,
            "opened": opened,
            "reason": barrier,
            "verification_policy": "pause_for_human",
            "saved_records": 1,
            "record": job_record.to_dict(),
        }, [job_record]

    records = build_records_from_source(source, page, run_date)
    validation = validate_page_against_source(source, page)
    if should_defer_visible_capture(source, records, validation):
        job_record = save_collection_job_record(
            root,
            source,
            run_date,
            "visible_capture_required",
            "No product/video/creator rows were visible in the public fetch. Use the already logged-in FastMoss/Kalodata/TikTok tab and capture the visible ranking rows.",
        )
        return {
            "source_id": source_id,
            "status": "visible_capture_required",
            "url": url,
            "opened": opened,
            "title": page.title,
            "validation": validation,
            "reason": "Selection bridge page did not expose usable product/video/creator rows.",
            "saved_records": 1,
            "record": job_record.to_dict(),
        }, [job_record]

    saved_records: list[IntakeRecord] = []
    skipped_mismatches = 0
    for record in records:
        record.metadata["platform_autopilot_validation"] = validation
        match = compare_product_text(source, record.fields)
        record.metadata["product_match"] = match.to_dict()
        if should_skip_mismatched_target_record(source, match.to_dict()):
            skipped_mismatches += 1
            continue
        if source.get("reference_image"):
            record.fields["reference_image"] = source.get("reference_image")
        if source.get("product_family"):
            record.fields.setdefault("product_family", source.get("product_family"))
        if source.get("monitoring_scope"):
            record.fields["monitoring_scope"] = source.get("monitoring_scope")
        if source.get("product_target_id"):
            record.fields["product_target_id"] = source.get("product_target_id")
        if source.get("product_target_name"):
            record.fields["product_target_name"] = source.get("product_target_name")
        if source.get("data_category"):
            record.fields["data_category"] = source.get("data_category")
        if source.get("keyword"):
            record.fields.setdefault("target_keyword", source.get("keyword"))
        if already_saved_platform_record(root, source_id, record, run_date):
            continue
        append_record(root, record)
        saved_records.append(record)
    if records and not saved_records and skipped_mismatches:
        job_record = save_collection_job_record(
            root,
            source,
            run_date,
            "mismatched_page",
            "Captured rows did not match the monitored product and were not saved as product evidence.",
        )
        return {
            "source_id": source_id,
            "status": "mismatched_page",
            "url": url,
            "opened": opened,
            "title": page.title,
            "validation": validation,
            "saved_records": 1,
            "skipped_mismatches": skipped_mismatches,
            "record": job_record.to_dict(),
        }, [job_record]
    return {
        "source_id": source_id,
        "status": "collected",
        "url": url,
        "opened": opened,
        "title": page.title,
        "validation": validation,
        "product_match": records[0].metadata.get("product_match") if records else None,
        "saved_records": len(saved_records),
        "duplicate_records": len(records) - len(saved_records),
        "records": [record.to_dict() for record in saved_records[:10]],
        "record": saved_records[0].to_dict() if saved_records else None,
    }, saved_records


def should_defer_visible_capture(source: dict[str, Any], records: list[IntakeRecord], validation: dict[str, Any]) -> bool:
    if not source.get("selection_bridge"):
        return False
    if any((record.metadata or {}).get("extraction_mode") == "ranking_item" for record in records):
        return False
    if any(record_has_hard_visible_fields(record) for record in records):
        return False
    return validation.get("status") == "needs_review" or bool(records)


def record_has_hard_visible_fields(record: IntakeRecord) -> bool:
    fields = record.fields
    hard_keys = [
        "rank_position",
        "product_url",
        "video_url",
        "creator_handle",
        "shop_name",
        "sales",
        "gmv",
        "sales_7d_visible",
        "gmv_7d_visible",
        "total_sales_visible",
    ]
    return any(str(fields.get(key) or "").strip() for key in hard_keys)


def should_skip_mismatched_target_record(source: dict[str, Any], product_match: dict[str, Any]) -> bool:
    if not source.get("product_target_id"):
        return False
    return product_match.get("status") == "different_product"


def save_collection_job_record(root: Path, source: dict[str, Any], run_date: str, status: str, reason: str) -> IntakeRecord:
    source_id = str(source.get("id") or source.get("name") or source.get("url") or "unnamed-platform").strip()
    source_url = str(source.get("url") or "")
    for record in read_records(root, "collection_job"):
        fields = record.fields
        if (
            str(fields.get("source_id") or "") == source_id
            and str(fields.get("run_date") or "") == run_date
            and str(fields.get("source_status") or "") == status
            and str(fields.get("url") or "") == source_url
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
        "keyword": source.get("keyword") or source.get("target_keyword") or "",
        "url": source_url,
        "data_category": source.get("data_category") or source.get("ranking_type") or "platform_source",
        "record_type_to_collect": source.get("record_type") or "platform_ranking_signal",
        "source_status": status,
        "source_reason": reason,
        "run_date": run_date,
        "requires_login": bool(source.get("requires_login", False)),
        "may_trigger_verification": bool(source.get("may_trigger_verification", False)),
        "next_step": "Open the saved source, pass any human verification yourself, then use the capture extension or rerun collection.",
    }
    record = IntakeRecord(
        record_type="collection_job",
        fields=fields,
        raw_text=json.dumps(fields, ensure_ascii=False),
        source="platform_autopilot_fallback",
        score={"priority": 55},
        director_notes=["Saved fallback search task because live platform data could not be collected directly."],
    )
    append_record(root, record)
    return record


def already_saved_platform_record(root: Path, source_id: str, record: IntakeRecord, run_date: str) -> bool:
    fields = record.fields
    source_url = str(fields.get("ranking_page") or fields.get("page_url") or fields.get("url") or "")
    asin = str(fields.get("product_asin") or "")
    rank = str(fields.get("rank_position") or "")
    product_name = str(fields.get("product_name") or "")
    for existing in read_records(root, record.record_type):
        metadata = existing.metadata or {}
        existing_fields = existing.fields or {}
        if str(metadata.get("automation_run_date") or existing.created_at[:10]) != run_date:
            continue
        if metadata.get("automation_source_id") != source_id:
            continue
        if source_url and source_url not in {
            str(existing_fields.get("ranking_page") or ""),
            str(existing_fields.get("page_url") or ""),
            str(existing_fields.get("url") or ""),
        }:
            continue
        if asin and asin == str(existing_fields.get("product_asin") or ""):
            return True
        if rank and product_name and rank == str(existing_fields.get("rank_position") or "") and product_name == str(existing_fields.get("product_name") or ""):
            return True
    return False

def open_browser_url(url: str) -> bool:
    try:
        return bool(webbrowser.open(url, new=2, autoraise=False))
    except Exception:
        return False


def detect_verification_barrier(title: str, text: str) -> str:
    haystack = f"{title}\n{text}".lower()
    for signal in VERIFICATION_SIGNALS:
        if signal.lower() in haystack:
            return f"页面疑似出现验证：{signal}。请人工通过后继续。"
    return ""


def validate_page_against_source(source: dict[str, Any], page: Any) -> dict[str, Any]:
    expected_keywords = source.get("expected_keywords", [])
    if isinstance(expected_keywords, str):
        expected_keywords = [expected_keywords]
    expected_keywords = [str(item).strip() for item in expected_keywords if str(item).strip()]
    page_text = f"{page.title}\n{page.text}\n{json.dumps(page.metric_lines, ensure_ascii=False)}".lower()
    missing = [keyword for keyword in expected_keywords if keyword.lower() not in page_text]
    return {
        "status": "pass" if not missing else "needs_review",
        "expected_keywords": expected_keywords,
        "missing_keywords": missing,
        "metric_line_count": len(page.metric_lines),
        "link_count": len(page.links),
        "text_length": len(page.text),
    }


def build_platform_report(run_date: str, statuses: list[dict[str, Any]], records: list[IntakeRecord]) -> str:
    lines = [
        "# 平台自动巡检报告",
        "",
        f"日期：{run_date}",
        "",
        "## 安全边界",
        "",
        "- 可以自动打开页面、读取公开页面、生成选品/榜单/视频脚本报告。",
        "- 遇到登录、滑块、验证码、人机验证时只暂停并提示人工通过，不绕过验证。",
        "- 发布商品、改价、设置折扣、报名活动、联系达人、购买 IP、修改店铺设置都必须人工确认。",
        "",
        "## 平台状态",
        "",
    ]
    if not statuses:
        lines.append("- 暂无平台源。请在 `config/platform_autopilot.json` 添加 URL。")
    for status in statuses:
        lines.append(
            f"- {status.get('source_id')}：{status.get('status')}｜"
            f"{status.get('reason') or status.get('title') or status.get('url') or ''}"
        )
        validation = status.get("validation")
        if isinstance(validation, dict):
            missing = validation.get("missing_keywords") or []
            lines.append(
                f"  校验：{validation.get('status')}，指标行 {validation.get('metric_line_count', 0)}，"
                f"链接 {validation.get('link_count', 0)}，缺失关键词：{', '.join(missing) if missing else '无'}"
            )
        product_match = status.get("product_match")
        if isinstance(product_match, dict):
            shared = ", ".join(product_match.get("shared_terms") or [])
            lines.append(
                f"  Product match: {product_match.get('status')} "
                f"(score {product_match.get('score')})"
                f"{f' | shared: {shared}' if shared else ''}"
            )

    target_records = [record for record in records if record.fields.get("monitoring_scope") == "product_target"]
    focused_records = [record for record in records if record.fields.get("monitoring_scope") == "focused_target"]
    overview_records = [record for record in records if record.fields.get("monitoring_scope") not in {"focused_target", "product_target"}]

    lines.extend(["", "## Product Target Monitor", ""])
    if not target_records:
        lines.append("- No product target records in this run. Add a product in Product Targets.")
    for target_name, grouped in group_records_by_target(target_records).items():
        lines.append(f"### {target_name}")
        for record in grouped:
            fields = record.fields
            label = fields.get("product_name") or fields.get("page_title") or fields.get("url") or record.record_id[:8]
            match = record.metadata.get("product_match") if isinstance(record.metadata, dict) else None
            match_text = ""
            if isinstance(match, dict):
                match_text = f" | match {match.get('status')} ({match.get('score')})"
            category = fields.get("data_category") or "uncategorized"
            lines.append(f"- [{category}] {label} | priority {record.score.get('priority', 'TBD')}{match_text}")

    lines.extend(["", "## Focused Target Monitor", ""])
    if not focused_records:
        lines.append("- No focused target records in this run. Add keywords or competitor links in Competitor Monitor.")
    for record in focused_records:
        fields = record.fields
        label = fields.get("product_name") or fields.get("page_title") or fields.get("url") or record.record_id[:8]
        match = record.metadata.get("product_match") if isinstance(record.metadata, dict) else None
        match_text = ""
        if isinstance(match, dict):
            match_text = f" | match {match.get('status')} ({match.get('score')})"
        keyword = fields.get("target_keyword") or fields.get("product_family") or ""
        lines.append(f"- {label} | target {keyword} | priority {record.score.get('priority', 'TBD')}{match_text}")

    lines.extend(["", "## Market Overview", ""])
    if not overview_records:
        lines.append("- No broad market overview records in this run.")
    for record in overview_records:
        fields = record.fields
        label = fields.get("product_name") or fields.get("page_title") or fields.get("url") or record.record_id[:8]
        match = record.metadata.get("product_match") if isinstance(record.metadata, dict) else None
        match_text = ""
        if isinstance(match, dict):
            match_text = f"｜match {match.get('status')} ({match.get('score')})"
        lines.append(f"- {label}｜类型 {record.record_type}｜优先级 {record.score.get('priority', '待定')}{match_text}")

    lines.extend(["", "## 视频脚本方向", ""])
    themes = [
        str(record.fields.get("product_theme") or record.fields.get("product_name") or record.fields.get("page_title") or "").strip()
        for record in records
    ]
    themes = [theme for theme in themes if theme]
    if not themes:
        themes = ["Blue Collar Dad", "Dog Dad", "Fishing Dad"]
    for theme in themes[:5]:
        direction, script = script_direction_for_theme(theme)
        lines.append(f"- {theme}：{direction}")
        lines.append(f"- {theme} 脚本：{script}")

    return "\n".join(lines).rstrip() + "\n"


def script_direction_for_theme(theme: str) -> tuple[str, str]:
    normalized = theme.lower()
    if any(term in normalized for term in ["cleanser", "face wash", "facial", "skincare", "skin care", "amino"]):
        return (
            "开头 2 秒展示洗后紧绷/敏感肌痛点，中段展示泡沫、质地、冲洗后肤感，结尾强调温和清洁和日常早晚使用；避免医疗、祛痘治愈、修复屏障等过强功效承诺。",
            "My face wash always left my skin tight. I switched to a gentle amino-acid cleanser: soft foam, clean rinse, no stripped feeling.",
        )
    if any(term in normalized for term in ["tee", "t-shirt", "shirt", "washed", "cotton", "oversized"]):
        return (
            "开头 2 秒先给穿搭/版型/面料钩子，中段展示水洗质感、上身效果、细节，结尾用自用或送礼理由 CTA。",
            "This is the washed tee I keep reaching for: soft cotton, relaxed fit, and that vintage look without trying too hard.",
        )
    if any(term in normalized for term in ["supplement", "melatonin", "vitamin", "gummy"]):
        return (
            "开头 2 秒展示日常习惯场景，中段展示包装、剂型和使用方式，结尾强调体验和合规 CTA；避免治疗、改善疾病或保证效果。",
            "This is part of my night routine now: simple, easy to take, and it fits right next to my wind-down habits.",
        )
    return (
        "开头 2 秒先给痛点钩子，中段展示产品细节或使用场景，结尾用自用理由做 CTA。",
        "I did not expect this product to become part of my daily routine, but the details make it easy to understand why.",
    )


def group_records_by_target(records: list[IntakeRecord]) -> dict[str, list[IntakeRecord]]:
    grouped: dict[str, list[IntakeRecord]] = {}
    for record in records:
        name = str(record.fields.get("product_target_name") or record.fields.get("product_family") or "Unnamed target")
        grouped.setdefault(name, []).append(record)
    return grouped


def write_platform_report(root: Path, run_date: str, content: str) -> Path:
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{PLATFORM_AUTOPILOT_REPORT_PREFIX}_{run_date}.md"
    path.write_text(content, encoding="utf-8")
    return path


def latest_platform_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    paths = sorted(output_dir.glob(f"{PLATFORM_AUTOPILOT_REPORT_PREFIX}_*.md"), reverse=True)
    if not paths:
        return "还没有平台自动巡检报告。", None
    path = paths[0]
    return path.read_text(encoding="utf-8"), path
