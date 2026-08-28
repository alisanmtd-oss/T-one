from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any

from .storage import append_record
from .types import IntakeRecord


REPORT_PREFIX = "FEISHU_LEARNING_SOURCE_REGISTER"


@dataclass(slots=True)
class FeishuLearningRegisterResult:
    run_date: str
    source_documents: list[IntakeRecord]
    tasks: list[IntakeRecord]
    strategy_memory: IntakeRecord
    report_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "source_document_count": len(self.source_documents),
            "task_count": len(self.tasks),
            "strategy_memory_id": self.strategy_memory.record_id,
            "report_path": str(self.report_path),
            "sources": [record.fields for record in self.source_documents],
        }


def register_feishu_learning_sources(
    root: Path,
    urls: list[str],
    *,
    run_date: str | None = None,
) -> FeishuLearningRegisterResult:
    root = root.resolve()
    day = run_date or date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    unique_urls = dedupe_urls(urls)
    source_documents: list[IntakeRecord] = []
    tasks: list[IntakeRecord] = []

    for index, url in enumerate(unique_urls, start=1):
        source_id = stable_id("feishu_src_", url)
        source_kind = infer_source_kind(url)
        title = f"{source_kind['label']} {index}"
        source_record = IntakeRecord(
            record_type="source_document",
            source="feishu_learning_import",
            raw_text=json.dumps(
                {
                    "url": url,
                    "status": "waiting_authorized_export",
                    "reason": "Feishu content requires logged-in browser access or exported file with images.",
                },
                ensure_ascii=False,
            ),
            fields={
                "source_id": source_id,
                "source_name": title,
                "source_url": url,
                "source_kind": source_kind["kind"],
                "checksum": stable_id("pending_", url),
                "content_sha256": "",
                "language": "zh-CN",
                "import_status": "waiting_authorized_export",
                "required_export_formats": ["docx", "pdf", "txt", "md"],
                "required_assets": ["embedded_images", "screenshots", "tables", "attachments"],
                "target_pipeline": "course_corpus_import",
                "storage_policy": "do_not_summarize_until_original_text_is_available",
                "imported_at_utc": now,
            },
            score={"priority": 92, "layer": "source_document_pointer"},
            director_notes=[
                "Pointer saved only. Content has not been learned yet because the original document text is unavailable.",
                "After export, run course-corpus-import so the content becomes source chunks, knowledge items, evidence claims, learning events and strategy memory.",
            ],
            review_status="waiting_source_export",
            confidence=0.55,
        )
        append_record(root, source_record)
        source_documents.append(source_record)

        task_record = IntakeRecord(
            record_type="task_queue",
            source="feishu_learning_import",
            raw_text=source_record.raw_text,
            fields={
                "task_queue_id": stable_id("feishu_task_", source_id),
                "task_type": "feishu_course_learning_import",
                "task_title": f"Import and learn {title}",
                "target_agent_id": "AI Data Review Analyst",
                "source_document_id": source_id,
                "source_url": url,
                "status": "waiting_source_export",
                "priority_score": 92,
                "expected_output": [
                    "Preserve the original transcript/document text first.",
                    "Split by lesson and practical operation node.",
                    "Extract product-selection rules, video scripts, creator rules, ad rules, store operation rules and risk rules.",
                    "Generate separate teacher-homework mind map and internal AI-training mind map.",
                    "Create evidence-backed LearningEvent records instead of loose notes.",
                ],
                "blocked_until": "doc_export_or_browser_access_available",
                "created_at_utc": now,
            },
            score={"priority": 92, "layer": "task_queue"},
            director_notes=["This is a learning task, not a store operation task."],
            review_status="waiting_source_export",
            confidence=0.7,
        )
        append_record(root, task_record)
        tasks.append(task_record)

    memory = build_strategy_memory(unique_urls, now, day)
    append_record(root, memory)
    report = build_report(day, source_documents, tasks)
    report_path = write_report(root, day, report)
    return FeishuLearningRegisterResult(day, source_documents, tasks, memory, report_path)


def build_strategy_memory(urls: list[str], now: str, day: str) -> IntakeRecord:
    payload = {
        "memory_key": f"feishu-learning-sources:{day}",
        "memory_type": "source_import_gate",
        "summary": "Feishu course/system documents were received as learning sources, but the original content must be exported or read through a working logged-in browser before real learning.",
        "source_count": len(urls),
        "source_urls": urls,
        "next_action": "Request exported docx/pdf/txt/md files or restore Chrome control, then run the course corpus import and regenerate detailed mind maps.",
        "created_at_utc": now,
    }
    return IntakeRecord(
        record_type="strategy_memory",
        source="feishu_learning_import",
        raw_text=json.dumps(payload, ensure_ascii=False),
        fields=payload,
        score={"priority": 90, "training_weight": "high"},
        director_notes=[
            "Do not claim these Feishu documents are learned until the original content is actually imported.",
        ],
        review_status="approved",
        confidence=0.85,
    )


def build_report(day: str, sources: list[IntakeRecord], tasks: list[IntakeRecord]) -> str:
    lines = [
        "# 飞书学习源登记报告",
        "",
        f"日期：{day}",
        "",
        "## 结论",
        "",
        "- 你发来的飞书链接已经登记进本地学习系统，优先级为高。",
        "- 目前还没有真正学到原文内容：飞书网页被登录/权限拦住，已登录 Chrome 控制通道当前也不可用。",
        "- 正确下一步：把每份飞书文档导出为 DOCX / PDF / TXT / Markdown，再接入课程语料入湖流程。",
        "",
        "## 学习源",
        "",
    ]
    for record in sources:
        lines.append(f"- {record.fields.get('source_name')}: {record.fields.get('source_url')}")
        lines.append(f"  - 状态：{record.fields.get('import_status')}")
        lines.append("  - 需要：带原文/逐字稿/图片/表格/附件的 docx / pdf / txt / md 文件")
    lines.extend(
        [
            "",
            "## 已分配给 AI 员工的任务",
            "",
        ]
    )
    for task in tasks:
        lines.append(f"- {task.fields.get('target_agent_id')}: {task.fields.get('task_title')}")
        lines.append(f"  - 状态：{task.fields.get('status')}")
    lines.extend(
        [
            "",
            "## 导入后必须产出的内容",
            "",
            "1. 保留每份文档原文，不先压缩总结。",
            "2. 按课程、章节、实操案例、数据节点拆分。",
            "3. 生成两套图：纯课程作业版，以及内部 AI 训练版。",
            "4. 每节课必须标注：选品规则、平台入口、数据指标、视频节点、达人打法、广告打法、风控规则。",
            "5. 写入 Data Lake：SourceDocument -> SourceChunk -> KnowledgeItem -> EvidenceClaim -> LearningEvent -> StrategyMemory。",
            "",
            "## 当前缺口",
            "",
            "- 缺原文：不能凭链接猜内容。",
            "- 缺视频画面节点：必须能看到视频或导出逐字稿/截图后再补。",
            "- 缺老师实操数据：后面要单独提取榜单、销量、广告、素材脚本、达人案例。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_report(root: Path, day: str, content: str) -> Path:
    out_dir = root / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{REPORT_PREFIX}_{day}.md"
    path.write_text(content, encoding="utf-8")
    return path


def dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        clean = str(url or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def infer_source_kind(url: str) -> dict[str, str]:
    if "/wiki/" in url:
        return {"kind": "feishu_wiki_pending_export", "label": "Feishu Wiki Source"}
    if "/docx/" in url:
        return {"kind": "feishu_docx_pending_export", "label": "Feishu Doc Source"}
    return {"kind": "feishu_pending_export", "label": "Feishu Source"}


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    return prefix + sha1(raw.encode("utf-8")).hexdigest()[:18]
