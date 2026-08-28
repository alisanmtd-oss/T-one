from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from .b2b_document_approval import APPROVAL_REQUIRED_FIELDS, B2B_APPROVAL_ACTIONS


AUTHORITATIVE_MASTER = "b2b_10001_master_sales_pipeline_2026-07-11_0506.csv"
APPAREL_SCOPE = "apparel_wholesale"
EQUIPMENT_SCOPE = "equipment_cross_sell"
FALSE_VALUES = {"", "0", "false", "no", "none", "null", "not_sent", "pending", "unknown"}
STAGE_PRIORITY = {
    "approved_to_send": 0,
    "pending_owner_review": 1,
    "lead_added_pending_owner_review": 2,
    "tool_added_for_research_queue": 3,
}
EQUIPMENT_SIGNAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("printing_process", re.compile(r"\b(?:dtg|dtf|direct[- ]to[- ]garment|printer|printing machine)\b|直喷|印花设备|打印机", re.I)),
    ("capacity_or_expansion", re.compile(r"\b(?:capacity|throughput|expand|expansion|second machine|replacement|production bottleneck)\b|扩产|产能|第二台|替换设备", re.I)),
    ("operating_pain", re.compile(r"\b(?:outsourc|labor cost|lead[- ]time|downtime|maintenance|quality issue|equipment pain)\b|外包|人工成本|交期压力|停机|维护|质量问题", re.I)),
    ("dealer_or_distributor", re.compile(r"\b(?:machine dealer|equipment dealer|printer distributor|machine distributor)\b|设备代理|机器代理", re.I)),
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() not in FALSE_VALUES


def _read_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return [dict(row) for row in csv.DictReader(stream)]
    except (OSError, csv.Error):
        return []


@lru_cache(maxsize=128)
def _latest_for_directory_state(
    outputs_path: str, pattern: str, directory_mtime_ns: int
) -> Path | None:
    """Resolve a latest path once for one concrete directory state."""

    del directory_mtime_ns  # It is intentionally part of the cache key.
    latest: Path | None = None
    latest_mtime_ns = -1
    for candidate in Path(outputs_path).glob(pattern):
        try:
            candidate_mtime_ns = candidate.stat().st_mtime_ns
        except OSError:
            continue
        if candidate_mtime_ns > latest_mtime_ns:
            latest = candidate
            latest_mtime_ns = candidate_mtime_ns
    return latest


def _latest(root: Path, pattern: str) -> Path | None:
    outputs = root / "outputs"
    try:
        directory_mtime_ns = outputs.stat().st_mtime_ns
    except OSError:
        return None
    return _latest_for_directory_state(
        str(outputs.resolve()), pattern, directory_mtime_ns
    )


def master_pipeline_path(root: Path) -> Path | None:
    canonical = root / "outputs" / AUTHORITATIVE_MASTER
    return canonical if canonical.exists() else _latest(root, "b2b_10001_master_sales_pipeline_*.csv")


def _company_key(row: dict[str, str]) -> str:
    company = re.sub(r"[^a-z0-9]+", "", str(row.get("company") or row.get("lead_company") or "").lower())
    return str(row.get("pipeline_id") or "").strip().lower() or company


def _company_name_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _dedupe(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        key = _company_key(row)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def resolve_sales_scope(task_context: dict[str, Any] | None = None, *, product_id: str = "10001") -> str:
    context = task_context if isinstance(task_context, dict) else {}
    explicit = str(context.get("sales_scope") or "").strip().lower()
    if explicit in {APPAREL_SCOPE, EQUIPMENT_SCOPE}:
        return explicit
    identity = " ".join(
        str(context.get(key) or "")
        for key in ("id", "name", "project_id", "project_type", "subtitle")
    ).lower()
    if any(token in identity for token in ("equipment", "machine", "dtg", "设备", "直喷")):
        return EQUIPMENT_SCOPE
    return APPAREL_SCOPE


def _equipment_signals(row: dict[str, str]) -> list[str]:
    searchable = " ".join(
        str(row.get(key) or "")
        for key in ("subject", "next_action", "next_stage_after_send", "draft_file", "market")
    )
    return [label for label, pattern in EQUIPMENT_SIGNAL_PATTERNS if pattern.search(searchable)]


def _scope_rows(rows: list[dict[str, str]], sales_scope: str) -> list[dict[str, str]]:
    if sales_scope != EQUIPMENT_SCOPE:
        return rows
    return [row for row in rows if _equipment_signals(row)]


def _quote_row_ready(row: dict[str, str]) -> bool:
    status = str(row.get("quote_status") or "").strip().lower()
    if status in FALSE_VALUES or status in {"not_ready", "blocked", "draft"}:
        return False
    required_values = (
        row.get("target_quantity") or row.get("requested_quantity"),
        row.get("ship_to_state") or row.get("destination_country"),
        row.get("warehouse_cost_confirmed"),
        row.get("shipping_cost_confirmed"),
        row.get("payment_terms_confirmed"),
    )
    return all(_truthy(value) for value in required_values)


def _row_truth_label(row: dict[str, str]) -> str:
    if _truthy(row.get("external_message_sent")) or row.get("manual_sent_at"):
        return "externally_confirmed"
    if str(row.get("current_stage") or "") == "approved_to_send":
        return "approved_not_executed"
    return "verified_current"


def _source_modified_at(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    except OSError:
        return ""


def _evidence_label(root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return str(path)


def _stored_path(root: Path, value: Any) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else root / path


def _past_due(value: Any, *, now: datetime | None = None) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    try:
        due = datetime.fromisoformat(raw)
    except ValueError:
        return False
    current = now or datetime.now().astimezone()
    if due.tzinfo is None:
        due = due.replace(tzinfo=current.tzinfo)
    return due < current


def _timeline_event(
    *,
    pipeline_id: str,
    company: str,
    event_type: str,
    sequence: int,
    status: str,
    detail: str,
    truth_label: str,
    evidence: str,
    source_updated_at: str,
    occurred_at: str = "",
    external_side_effect: bool = False,
) -> dict[str, Any]:
    return {
        "event_id": f"{pipeline_id}:{event_type}:{sequence}",
        "sequence": sequence,
        "pipeline_id": pipeline_id,
        "company": company,
        "type": event_type,
        "status": status,
        "detail": detail,
        "truth_label": truth_label,
        "occurred_at": occurred_at,
        "source_updated_at": source_updated_at,
        "evidence": evidence,
        "external_side_effect": external_side_effect,
    }


def account_timeline_snapshot(root: Path) -> list[dict[str, Any]]:
    """Build a source-linked timeline view for every canonical B2B account.

    This is a derived, read-only view.  Missing downstream evidence is left absent;
    draft, approval, send, reply and quotation states are never promoted into one
    another.
    """

    master = master_pipeline_path(root)
    rows = _dedupe(_read_csv(master))
    reply_path = _latest(root, "b2b_10001_reply_intake_queue_*.csv")
    quote_path = _latest(root, "b2b_10001_quote_tracker_*.csv")
    master_evidence = _evidence_label(root, master)
    reply_evidence = _evidence_label(root, reply_path)
    quote_evidence = _evidence_label(root, quote_path)
    master_updated = _source_modified_at(master)
    reply_updated = _source_modified_at(reply_path)
    quote_updated = _source_modified_at(quote_path)

    replies_by_pipeline: dict[str, list[dict[str, str]]] = defaultdict(list)
    replies_by_company: dict[str, list[dict[str, str]]] = defaultdict(list)
    for reply in _read_csv(reply_path):
        pipeline_key = str(reply.get("pipeline_id") or "").strip().lower()
        company_key = _company_name_key(str(reply.get("company") or ""))
        if pipeline_key:
            replies_by_pipeline[pipeline_key].append(reply)
        if company_key:
            replies_by_company[company_key].append(reply)

    quotes_by_company: dict[str, list[dict[str, str]]] = defaultdict(list)
    for quote in _read_csv(quote_path):
        company_key = _company_name_key(str(quote.get("lead_company") or quote.get("company") or ""))
        if company_key:
            quotes_by_company[company_key].append(quote)

    accounts: list[dict[str, Any]] = []
    for row in rows:
        pipeline_id = str(row.get("pipeline_id") or "")
        pipeline_key = pipeline_id.strip().lower()
        company = str(row.get("company") or "")
        company_key = _company_name_key(company)
        contact_path = str(row.get("contact_path") or "")
        events: list[dict[str, Any]] = [
            _timeline_event(
                pipeline_id=pipeline_id,
                company=company,
                event_type="pipeline",
                sequence=10,
                status=str(row.get("current_stage") or "unknown"),
                detail=str(row.get("next_action") or ""),
                truth_label=_row_truth_label(row),
                evidence=master_evidence,
                source_updated_at=master_updated,
            )
        ]

        draft_file = str(row.get("draft_file") or "").strip()
        if draft_file:
            draft_path = _stored_path(root, draft_file)
            events.append(
                _timeline_event(
                    pipeline_id=pipeline_id,
                    company=company,
                    event_type="draft",
                    sequence=20,
                    status="draft_reference_recorded",
                    detail="已记录内部草稿或批次草稿引用；没有外发证据。",
                    truth_label="draft",
                    evidence=draft_file,
                    source_updated_at=_source_modified_at(draft_path),
                )
            )

        if str(row.get("current_stage") or "") == "approved_to_send":
            events.append(
                _timeline_event(
                    pipeline_id=pipeline_id,
                    company=company,
                    event_type="approval",
                    sequence=30,
                    status="approved_not_executed",
                    detail="历史表记录为已批准，但没有精确收件人、渠道、草稿版本、附件和执行时间的当前确认；发送前必须逐条重新确认。",
                    truth_label="approved_not_executed",
                    evidence=master_evidence,
                    source_updated_at=master_updated,
                )
            )

        if str(row.get("current_stage") or "") == "tool_added_for_research_queue" or str(row.get("reply_status") or "") == "not_applicable":
            events.append(
                _timeline_event(
                    pipeline_id=pipeline_id,
                    company=company,
                    event_type="suppression",
                    sequence=35,
                    status="research_only_no_outreach",
                    detail="此记录仅作研究来源、渠道基准或工具入口，不进入外联队列。",
                    truth_label="verified_current",
                    evidence=master_evidence,
                    source_updated_at=master_updated,
                )
            )

        sent = _truthy(row.get("external_message_sent")) or bool(str(row.get("manual_sent_at") or "").strip())
        if sent:
            events.append(
                _timeline_event(
                    pipeline_id=pipeline_id,
                    company=company,
                    event_type="outreach",
                    sequence=40,
                    status="externally_sent",
                    detail="权威客户池存在外发证据。",
                    truth_label="externally_confirmed",
                    evidence=master_evidence,
                    source_updated_at=master_updated,
                    occurred_at=str(row.get("manual_sent_at") or ""),
                    external_side_effect=True,
                )
            )

        matched_replies: list[dict[str, str]] = []
        seen_reply_objects: set[int] = set()
        for reply in replies_by_pipeline.get(pipeline_key, []) + replies_by_company.get(company_key, []):
            identity = id(reply)
            if identity in seen_reply_objects:
                continue
            seen_reply_objects.add(identity)
            matched_replies.append(reply)
        for index, reply in enumerate(matched_replies, start=1):
            if not _truthy(reply.get("reply_received")):
                continue
            raw_reply = str(reply.get("raw_reply") or "").strip()
            events.append(
                _timeline_event(
                    pipeline_id=pipeline_id,
                    company=company,
                    event_type="reply",
                    sequence=50 + index,
                    status=str(reply.get("next_stage") or "reply_received"),
                    detail=raw_reply or "已记录客户回复；需求字段必须以客户原话为证据。",
                    truth_label="externally_confirmed",
                    evidence=reply_evidence,
                    source_updated_at=reply_updated,
                    external_side_effect=True,
                )
            )

        for index, quote in enumerate(quotes_by_company.get(company_key, []), start=1):
            ready = _quote_row_ready(quote)
            events.append(
                _timeline_event(
                    pipeline_id=pipeline_id,
                    company=company,
                    event_type="quotation",
                    sequence=60 + index,
                    status="ready_for_owner_review" if ready else str(quote.get("quote_status") or "not_ready"),
                    detail=str(quote.get("next_action") or "报价资料待补充。"),
                    truth_label="draft",
                    evidence=quote_evidence,
                    source_updated_at=quote_updated,
                )
            )

        accounts.append(
            {
                "pipeline_id": pipeline_id,
                "company": company,
                "market": str(row.get("market") or ""),
                "current_stage": str(row.get("current_stage") or ""),
                "truth_label": _row_truth_label(row),
                "send_channel": str(row.get("send_channel") or ""),
                "contact_path": contact_path,
                "contact_path_is_consent": False,
                "historical_reply_due_date": str(row.get("reply_due_date") or ""),
                "stale_reply_due": _past_due(row.get("reply_due_date")),
                "equipment_review_signals": _equipment_signals(row),
                "event_count": len(events),
                "events": sorted(events, key=lambda item: int(item["sequence"])),
            }
        )
    return accounts


def owner_review_queue(root: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    """Return stale historical approvals as a re-confirmation queue, never a send queue."""

    rows = _dedupe(_read_csv(master_pipeline_path(root)))
    quote_path = _latest(root, "b2b_10001_quote_tracker_*.csv")
    quotes_by_company = {
        _company_name_key(str(row.get("lead_company") or row.get("company") or "")): row
        for row in _read_csv(quote_path)
    }
    approved = [row for row in rows if str(row.get("current_stage") or "") == "approved_to_send"]
    ranked = sorted(
        approved,
        key=lambda row: (
            0 if str(row.get("market") or "").upper() == "US" else 1,
            0 if str(row.get("send_channel") or "") == "email" else 1,
            str(row.get("company") or "").lower(),
        ),
    )
    queue: list[dict[str, Any]] = []
    for rank, row in enumerate(ranked, start=1):
        company = str(row.get("company") or "")
        contact_path = str(row.get("contact_path") or "")
        draft_file = str(row.get("draft_file") or "")
        quote = quotes_by_company.get(_company_name_key(company), {})
        blockers = [
            "历史批准没有当前执行时间、精确收件人、渠道、草稿版本和附件版本的完整证据",
            "没有真实外发证据",
        ]
        if any(separator in contact_path for separator in (";", "||", " | ")):
            blockers.append("联系路径含多个候选，需选择唯一收件人或表单")
        if not draft_file:
            blockers.append("缺少草稿引用")
        elif not (_stored_path(root, draft_file) or Path()).exists():
            blockers.append("草稿引用文件当前不存在")
        if row.get("size_chart"):
            blockers.append("尺寸表来源与测量依据未完成验证，当前不得作为外发附件")
        if _past_due(row.get("reply_due_date")):
            blockers.append("旧回复截止日已过期，必须重新安排而不是假设已跟进")
        if not _quote_row_ready(quote):
            blockers.append("数量、目的地、成本、运费或付款条件不完整，不能正式报价")
        queue.append(
            {
                "priority_rank": rank,
                "pipeline_id": str(row.get("pipeline_id") or ""),
                "company": company,
                "market": str(row.get("market") or ""),
                "channel": str(row.get("send_channel") or ""),
                "contact_path": contact_path,
                "subject": str(row.get("subject") or ""),
                "draft_file": draft_file,
                "onepager": str(row.get("onepager") or ""),
                "color_card": str(row.get("color_card") or ""),
                "size_chart": str(row.get("size_chart") or ""),
                "historical_reply_due_date": str(row.get("reply_due_date") or ""),
                "historical_approval_state": "approved_not_executed",
                "current_execution_state": "blocked_pending_owner_reconfirmation",
                "quote_ready": _quote_row_ready(quote),
                "approval_state": "exact_immutable_approval_required",
                "approval_required_fields": list(APPROVAL_REQUIRED_FIELDS),
                "document_approval_actions": sorted(B2B_APPROVAL_ACTIONS),
                "needs_owner_confirmation": True,
                "blockers": blockers,
                "next_action": "逐条核对唯一收件人、渠道、草稿版本、附件、合规和计划发送时间；确认只适用于这一条记录。",
            }
        )
    return queue[:limit] if limit is not None else queue


def sales_snapshot(
    root: Path,
    *,
    product_id: str = "10001",
    task_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    master = master_pipeline_path(root)
    rows = _dedupe(_read_csv(master))
    sales_scope = resolve_sales_scope(task_context, product_id=product_id)
    scoped_rows = _scope_rows(rows, sales_scope)
    reply_path = _latest(root, "b2b_10001_reply_intake_queue_*.csv")
    quote_path = _latest(root, "b2b_10001_quote_tracker_*.csv")
    replies = _read_csv(reply_path)
    quotes = _read_csv(quote_path)

    scoped_pipeline_ids = {str(row.get("pipeline_id") or "").strip().lower() for row in scoped_rows}
    scoped_company_keys = {_company_name_key(str(row.get("company") or "")) for row in scoped_rows}
    master_pipeline_ids = {str(row.get("pipeline_id") or "").strip().lower() for row in rows}
    master_company_keys = {_company_name_key(str(row.get("company") or "")) for row in rows}
    mapped_replies = [
        row for row in replies
        if str(row.get("pipeline_id") or "").strip().lower() in master_pipeline_ids
        or _company_name_key(str(row.get("company") or "")) in master_company_keys
    ]
    orphan_replies = [row for row in replies if row not in mapped_replies]
    mapped_quotes = [
        row for row in quotes
        if _company_name_key(str(row.get("lead_company") or row.get("company") or "")) in master_company_keys
    ]
    orphan_quotes = [row for row in quotes if row not in mapped_quotes]
    scoped_replies = [
        row for row in replies
        if str(row.get("pipeline_id") or "").strip().lower() in scoped_pipeline_ids
        or _company_name_key(str(row.get("company") or "")) in scoped_company_keys
    ]
    scoped_quotes = [
        row for row in quotes
        if _company_name_key(str(row.get("lead_company") or row.get("company") or "")) in scoped_company_keys
    ] if sales_scope == APPAREL_SCOPE else []

    stage_counts = Counter(str(row.get("current_stage") or "unknown") for row in scoped_rows)
    sent_count = sum(1 for row in scoped_rows if _truthy(row.get("external_message_sent")) or row.get("manual_sent_at"))
    reply_count = sum(1 for row in scoped_replies if _truthy(row.get("reply_received")))
    quote_ready_count = sum(1 for row in scoped_quotes if _quote_row_ready(row))
    contactable_count = sum(1 for row in scoped_rows if str(row.get("contact_path") or "").strip())
    approved_count = int(stage_counts.get("approved_to_send", 0))
    account_timelines = account_timeline_snapshot(root)
    all_events = [event for account in account_timelines for event in account.get("events", [])]
    event_type_counts = Counter(str(event.get("type") or "unknown") for event in all_events)
    reconfirmation_queue = owner_review_queue(root)

    ranked = sorted(
        scoped_rows,
        key=lambda row: (
            STAGE_PRIORITY.get(str(row.get("current_stage") or ""), 9),
            0 if str(row.get("market") or "").upper() == "US" else 1,
            str(row.get("company") or "").lower(),
        ),
    )
    top_leads = [
        {
            "pipeline_id": str(row.get("pipeline_id") or ""),
            "company": str(row.get("company") or ""),
            "market": str(row.get("market") or ""),
            "stage": str(row.get("current_stage") or ""),
            "channel": str(row.get("send_channel") or ""),
            "contact_path": str(row.get("contact_path") or ""),
            "next_action": str(row.get("next_action") or ""),
            "truth_label": _row_truth_label(row),
            "equipment_review_signals": _equipment_signals(row),
        }
        for row in ranked[:12]
    ]

    if sales_scope == EQUIPMENT_SCOPE:
        scope_label = "直喷/DTG/DTF 设备交叉销售"
        blockers = [
            "设备关键词仅表示待复核信号，尚未证明客户有采购意图或技术适配。",
            "正式技术方案需补应用、材料、印花尺寸、班次产能、现有工艺、场地条件、目的国和验收标准。",
            "型号、价格、交期、认证、安装、培训、质保、备件、运费、税费和 ROI 均需当前证据与负责人确认。",
        ]
    else:
        scope_label = "10001 T 恤批发与样包"
        blockers = [
            "当前没有真实外发或客户回复证据。" if not sent_count and not reply_count else "",
            "正式报价仍需数量、颜色尺码、目的地、成本、运费、付款条件与有效期。" if not quote_ready_count else "",
            f"回复队列有 {len(orphan_replies)} 条、报价跟踪有 {len(orphan_quotes)} 条无法关联到 96 家权威客户池；关联前不得推进。" if orphan_replies or orphan_quotes else "",
        ]
        blockers = [item for item in blockers if item]

    return {
        "product_id": product_id if sales_scope == APPAREL_SCOPE else "",
        "sales_scope": sales_scope,
        "scope_label": scope_label,
        "master_path": str(master or ""),
        "authoritative_company_count": len(rows),
        "scope_candidate_count": len(scoped_rows),
        "equipment_review_signal_count": len(scoped_rows) if sales_scope == EQUIPMENT_SCOPE else sum(1 for row in rows if _equipment_signals(row)),
        "contactable_count": contactable_count,
        "approved_to_send_count": approved_count,
        "externally_sent_count": sent_count,
        "reply_count": reply_count,
        "reply_source_row_count": len(replies),
        "reply_mapped_row_count": len(mapped_replies),
        "reply_orphan_row_count": len(orphan_replies),
        "reply_orphan_companies": [str(row.get("company") or "") for row in orphan_replies],
        "quote_ready_count": quote_ready_count,
        "quote_source_row_count": len(quotes),
        "quote_mapped_row_count": len(mapped_quotes),
        "quote_orphan_row_count": len(orphan_quotes),
        "quote_orphan_companies": [str(row.get("lead_company") or row.get("company") or "") for row in orphan_quotes],
        "quote_blocked_count": (len(quotes) - quote_ready_count) if sales_scope == APPAREL_SCOPE else 0,
        "account_timeline_count": len(account_timelines),
        "account_timeline_event_count": len(all_events),
        "timeline_event_type_counts": dict(event_type_counts),
        "draft_reference_count": int(event_type_counts.get("draft", 0)),
        "research_only_count": int(event_type_counts.get("suppression", 0)),
        "owner_reconfirmation_count": len(reconfirmation_queue),
        "stale_reply_due_count": sum(1 for row in rows if _past_due(row.get("reply_due_date"))),
        "stage_counts": dict(stage_counts),
        "top_leads": top_leads,
        "reply_path": str(reply_path or ""),
        "quote_path": str(quote_path or ""),
        "external_send_allowed": False,
        "blockers": blockers,
        "guardrails": [
            "系统只生成研究、草稿、报价准备和待确认队列，不批量发送邮件/私信/WhatsApp。",
            "每次对外联系、正式报价、价格承诺、样品订单、合同、付款和交付承诺都需负责人逐条确认。",
            "报价、PI、合同承诺和付款动作的批准必须绑定 pipeline、动作、文档类型、不可变版本、SHA256、审批人身份/角色/权限、有效期，并且只能消费一次。",
            "客户时间线必须使用同一 pipeline/company 记录，不为 T 恤和设备重复创建客户。",
            "草稿、已批准未执行、已发送、已回复、已报价、已付款和已发货必须由不同证据状态表示。",
        ],
    }


def customer_timeline(root: Path, company: str) -> list[dict[str, Any]]:
    wanted = _company_name_key(company)
    matched = next(
        (account for account in account_timeline_snapshot(root) if _company_name_key(str(account.get("company") or "")) == wanted),
        None,
    )
    return list(matched.get("events", [])) if isinstance(matched, dict) else []


def write_sales_execution_pack(
    root: Path,
    *,
    product_id: str = "10001",
    task_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = sales_snapshot(root, product_id=product_id, task_context=task_context)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    output_dir = root / "outputs" / "b2b_sales_agent"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"b2b_sales_execution_pack_{stamp}.json"
    md_path = output_dir / f"b2b_sales_execution_pack_{stamp}.md"
    timeline_path = output_dir / f"b2b_customer_timeline_{stamp}.json"
    owner_queue_path = output_dir / f"b2b_owner_reconfirmation_queue_{stamp}.csv"
    timelines = account_timeline_snapshot(root)
    review_queue = owner_review_queue(root)
    rows = "\n".join(
        f"| {index} | {lead['company']} | {lead['market']} | {lead['stage']} | {lead['truth_label']} | {', '.join(lead['equipment_review_signals']) or '-'} | {lead['next_action']} |"
        for index, lead in enumerate(snapshot["top_leads"], start=1)
    ) or "| - | 暂无 | - | - | - | - | 先补充权威客户证据 |"
    title = "B2B 设备机会复核执行包" if snapshot["sales_scope"] == EQUIPMENT_SCOPE else "B2B T 恤批发销售执行包"
    markdown = f"""# {title}

生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}

## 真实状态

- 当前范围：{snapshot['scope_label']}
- 权威去重公司总数：{snapshot['authoritative_company_count']}
- 当前范围证据候选：{snapshot['scope_candidate_count']}
- 有公开联系路径：{snapshot['contactable_count']}
- 已批准但尚需核对执行证据：{snapshot['approved_to_send_count']}
- 已有真实外发证据：{snapshot['externally_sent_count']}
- 已收到回复：{snapshot['reply_count']}
- 回复队列映射：{snapshot['reply_mapped_row_count']} / {snapshot['reply_source_row_count']}；孤立记录 {snapshot['reply_orphan_row_count']}
- 报价资料完整：{snapshot['quote_ready_count']}
- 报价跟踪映射：{snapshot['quote_mapped_row_count']} / {snapshot['quote_source_row_count']}；孤立记录 {snapshot['quote_orphan_row_count']}
- 已建立客户时间线：{snapshot['account_timeline_count']} 家 / {snapshot['account_timeline_event_count']} 条证据事件
- 待负责人逐条重新确认：{snapshot['owner_reconfirmation_count']}
- 已过期旧回复截止日：{snapshot['stale_reply_due_count']}
- 权威文件：`{snapshot['master_path']}`

## 下一批负责人复核

| # | 公司 | 市场 | 当前阶段 | 事实标签 | 设备复核信号 | 下一步 |
|---:|---|---|---|---|---|---|
{rows}

## 当前阻塞

""" + ("\n".join(f"- {item}" for item in snapshot["blockers"]) or "- 无结构性阻塞；仍需逐条负责人复核。") + "\n\n## 执行边界\n\n" + "\n".join(f"- {item}" for item in snapshot["guardrails"]) + "\n"
    timeline_payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "derived_read_only_view": True,
        "external_actions_executed": 0,
        "account_count": len(timelines),
        "accounts": timelines,
    }
    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    timeline_path.write_text(json.dumps(timeline_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    queue_fields = [
        "priority_rank", "pipeline_id", "company", "market", "channel", "contact_path", "subject",
        "draft_file", "onepager", "color_card", "size_chart", "historical_reply_due_date",
        "historical_approval_state", "current_execution_state", "quote_ready",
        "approval_state", "approval_required_fields", "document_approval_actions",
        "needs_owner_confirmation", "blockers", "next_action",
    ]
    with owner_queue_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=queue_fields)
        writer.writeheader()
        for item in review_queue:
            row = dict(item)
            row["blockers"] = " | ".join(str(value) for value in item.get("blockers", []))
            row["approval_required_fields"] = " | ".join(str(value) for value in item.get("approval_required_fields", []))
            row["document_approval_actions"] = " | ".join(str(value) for value in item.get("document_approval_actions", []))
            writer.writerow({field: row.get(field, "") for field in queue_fields})
    return {
        "snapshot": snapshot,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "timeline_path": str(timeline_path),
        "owner_queue_path": str(owner_queue_path),
        "output_dir": str(output_dir),
    }
