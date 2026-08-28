from __future__ import annotations

import json
import webbrowser
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote_plus, urlparse

from .storage import append_record, read_records, update_record
from .types import IntakeRecord


TK_EVIDENCE_RECOVERY_PREFIX = "tk_evidence_recovery"


@dataclass(slots=True)
class TkEvidenceRecoveryResult:
    run_date: str
    selected_tasks: list[dict[str, Any]]
    created_jobs: list[IntakeRecord]
    skipped_tasks: list[dict[str, Any]]
    opened_urls: list[str]
    report: str
    report_path: Path
    json_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "selected_tasks": self.selected_tasks,
            "created_jobs": [record.to_dict() for record in self.created_jobs],
            "skipped_tasks": self.skipped_tasks,
            "opened_urls": self.opened_urls,
            "report": self.report,
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
        }


def run_tk_evidence_recovery(
    root: Path,
    run_date: str | None = None,
    *,
    limit: int = 8,
    open_browser: bool = False,
) -> TkEvidenceRecoveryResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    tasks = select_recovery_tasks(root, limit=max(1, limit))
    created_jobs: list[IntakeRecord] = []
    skipped_tasks: list[dict[str, Any]] = []
    opened_urls: list[str] = []

    for task in tasks:
        url = str(task.get("url") or "").strip()
        if not url:
            skipped_tasks.append({**task, "skip_reason": "没有固定入口，保留为人工/员工判断任务。"})
            continue
        if open_browser and open_browser_url(url):
            opened_urls.append(url)
        created_jobs.append(save_recovery_collection_job(root, task, report_date, opened=open_browser and url in opened_urls))

    report = build_recovery_report(report_date, tasks, created_jobs, skipped_tasks, opened_urls, open_browser=open_browser)
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{TK_EVIDENCE_RECOVERY_PREFIX}_{report_date}.md"
    json_path = output_dir / f"{TK_EVIDENCE_RECOVERY_PREFIX}_{report_date}.json"
    report_path.write_text(report, encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "run_date": report_date,
                "selected_tasks": tasks,
                "created_jobs": [record.to_dict() for record in created_jobs],
                "skipped_tasks": skipped_tasks,
                "opened_urls": opened_urls,
                "open_browser": open_browser,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return TkEvidenceRecoveryResult(report_date, tasks, created_jobs, skipped_tasks, opened_urls, report, report_path, json_path)


def select_recovery_tasks(root: Path, *, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in read_records(root, "task_queue"):
        fields = record.fields or {}
        if str(fields.get("task_type") or "") != "tk_evidence_recovery":
            continue
        status = str(fields.get("status") or "").strip().lower()
        if status in {"done", "closed", "success", "cancelled"}:
            continue
        rows.append(
            {
                "record_id": record.record_id,
                "task_queue_id": fields.get("task_queue_id") or record.record_id,
                "title": fields.get("task_title") or fields.get("collection_target") or "",
                "platform": normalize_platform(str(fields.get("platform") or fields.get("platform_list") or "")),
                "url": fields.get("url") or "",
                "priority": int(fields.get("priority") or record.score.get("priority") or 80),
                "source_status": fields.get("source_status") or fields.get("status") or "",
                "next_step": fields.get("next_step") or "",
                "required_success_fields": fields.get("required_success_fields") or [],
                "forbidden": fields.get("forbidden") or [],
                "created_at": record.created_at,
            }
        )
    rows.sort(key=lambda item: (-int(item.get("priority") or 0), str(item.get("created_at") or "")))
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in rows:
        key = (str(item.get("platform") or ""), str(item.get("url") or ""), str(item.get("title") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def save_recovery_collection_job(root: Path, task: dict[str, Any], run_date: str, *, opened: bool) -> IntakeRecord:
    source_id = stable_id("tk_recovery_source_", task.get("platform"), task.get("url"), task.get("title"))
    url = str(task.get("url") or "")
    source_status = "logged_in_capture_required"
    existing = find_existing_recovery_job(root, source_id, url, run_date, source_status)
    fields = {
        "source_id": source_id,
        "collection_target": task.get("title") or "",
        "platform_list": task.get("platform") or "",
        "source_platform": task.get("platform") or "",
        "product_name": infer_product_name_from_task(task),
        "url": url,
        "data_category": infer_data_category(task),
        "record_type_to_collect": infer_record_type(task),
        "source_status": source_status,
        "source_reason": "TK补证据后台任务已把健康检查转成可采集入口；必须用已登录 Chrome/BitBrowser 或只读采集插件采集可见商品/视频/达人行。",
        "run_date": run_date,
        "requires_login": True,
        "may_trigger_verification": True,
        "selection_bridge": is_selection_bridge(task),
        "bridge_provider": normalize_platform(str(task.get("platform") or "")),
        "follow_tiktok_product_links": True,
        "opened_by_recovery_runner": opened,
        "task_queue_id": task.get("task_queue_id") or "",
        "required_success_fields": task.get("required_success_fields") or [],
        "forbidden": task.get("forbidden") or [],
        "next_step": (
            "使用已经登录的 Chrome/FastMoss/Kalodata/TikTok Shop 买家入口打开此链接，采集页面里的商品卡、排名、达人、视频和跳转 TK 商品链接；"
            "采不到真实商品/视频/达人指标时继续保持卡点，不算通过。"
        ),
    }
    if existing:
        existing.fields.update(fields)
        existing.raw_text = json.dumps(existing.fields, ensure_ascii=False)
        existing.score["priority"] = int(task.get("priority") or 80)
        update_record(root, existing)
        return existing
    record = IntakeRecord(
        record_type="collection_job",
        fields=fields,
        raw_text=json.dumps(fields, ensure_ascii=False),
        source="tk_evidence_recovery_runner",
        score={"priority": int(task.get("priority") or 80)},
        director_notes=[
            "Recovery runner converted a TK health task into an executable collection job.",
            "This is not market evidence. It only creates the next safe capture step.",
            "Do not count Amazon rows, homepages, verification pages, loading pages, or empty search shells as TK evidence.",
        ],
        confidence=0.94,
    )
    append_record(root, record)
    return record


def find_existing_recovery_job(root: Path, source_id: str, url: str, run_date: str, source_status: str) -> IntakeRecord | None:
    for record in read_records(root, "collection_job"):
        fields = record.fields or {}
        if (
            str(fields.get("source_id") or "") == source_id
            and str(fields.get("url") or "") == url
            and str(fields.get("run_date") or "") == run_date
            and str(fields.get("source_status") or "") == source_status
        ):
            return record
    return None


def build_recovery_report(
    run_date: str,
    tasks: list[dict[str, Any]],
    created_jobs: list[IntakeRecord],
    skipped_tasks: list[dict[str, Any]],
    opened_urls: list[str],
    *,
    open_browser: bool,
) -> str:
    lines = [
        f"# TK补证据执行报告 - {run_date}",
        "",
        "## 老板先看",
        "",
        f"- 本轮读取补证据任务：{len(tasks)} 个。",
        f"- 已转成采集任务：{len(created_jobs)} 个。",
        f"- 无固定入口/跳过：{len(skipped_tasks)} 个。",
        f"- 是否打开浏览器：{'是' if open_browser else '否'}；打开链接：{len(opened_urls)} 个。",
        "- 重要：这些采集任务不算真实 TK 数据，只是下一步补证据入口。",
        "- 通过标准：必须新增真实 TikTok/FastMoss/Kalodata/TikTok Shop 商品、视频或达人证据，且含链接和可见指标。",
        "",
        "## 本轮补证据任务",
        "",
    ]
    if not tasks:
        lines.append("- 暂无 tk_evidence_recovery 队列。先运行 tk-health-check 生成补证据任务。")
    for task in tasks:
        lines.append(f"- P{task.get('priority')} / {task.get('platform')} / {task.get('title')} -> {task.get('url') or '无固定入口'}")
    lines.extend(["", "## 已创建采集入口", ""])
    if not created_jobs:
        lines.append("- 暂无新采集入口。")
    for record in created_jobs:
        fields = record.fields or {}
        lines.append(f"- {fields.get('source_platform')} / {fields.get('collection_target')} / {fields.get('source_status')} -> {fields.get('url')}")
    lines.extend(["", "## 不允许冒充通过", ""])
    lines.extend(
        [
            "- 打开 FastMoss / Kalodata 首页，不算证据。",
            "- TikTok Security Check、滑块、验证码、加载页，不算证据。",
            "- Amazon 商品不能替代 TK 视频和达人证据。",
            "- 只有采到商品链接、视频链接/达人、排名/销量/播放/评论等可见指标，才可以进入真实证据。",
        ]
    )
    lines.extend(["", f"生成时间：{datetime.now(timezone.utc).isoformat()}"])
    return "\n".join(lines).rstrip() + "\n"


def infer_product_name(title: str) -> str:
    cleaned = title.replace("Fill TK category evidence:", "").replace("Latest round added no hard TK product/video evidence", "").strip()
    return cleaned[:120]


def infer_product_name_from_task(task: dict[str, Any]) -> str:
    title = str(task.get("title") or "")
    url = str(task.get("url") or "")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ["keyword", "q"]:
        value = query.get(key, [""])[0]
        if value:
            return unquote_plus(value).strip()[:120]
    return infer_product_name(title)


def infer_data_category(task: dict[str, Any]) -> str:
    title = str(task.get("title") or "").lower()
    url = str(task.get("url") or "").lower()
    if "category" in title or "类目" in title or "all buyer shop" in title:
        return "tiktok_category_product_recovery"
    if "viral video" in title or "media-source/video" in url:
        return "tiktok_video_evidence_recovery"
    if "creator" in title or "influencer" in title or "达人" in title:
        return "tiktok_creator_evidence_recovery"
    return "tiktok_product_rank_recovery"


def infer_record_type(task: dict[str, Any]) -> str:
    title = str(task.get("title") or "").lower()
    url = str(task.get("url") or "").lower()
    if "category" in title or "类目" in title or "all buyer shop" in title:
        return "platform_ranking_signal"
    if "viral video" in title or "media-source/video" in url:
        return "viral_content_signal"
    if "creator" in title or "influencer" in title or "达人" in title:
        return "creator_spike_event"
    return "platform_ranking_signal"


def is_selection_bridge(task: dict[str, Any]) -> bool:
    text = f"{task.get('platform')} {task.get('url')}".lower()
    return any(name in text for name in ["fastmoss", "kalodata", "tiktok"])


def normalize_platform(value: str) -> str:
    text = value.lower()
    if "fastmoss" in text:
        return "FastMoss"
    if "kalodata" in text:
        return "Kalodata"
    if "tiktok" in text:
        return "TikTok Shop"
    return value.strip() or "TikTok Shop"


def open_browser_url(url: str) -> bool:
    try:
        return bool(webbrowser.open(url, new=2, autoraise=False))
    except Exception:
        return False


def stable_id(prefix: str, *parts: Any) -> str:
    return prefix + sha1("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:18]
