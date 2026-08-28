from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .storage import append_record, read_records, update_record
from .task_execution_runtime import append_business_event
from .types import IntakeRecord


RECORD_TYPE = "operating_expense_entry"
PENDING = "pending_confirmation"
POSTED = "posted"
VOIDED = "voided"

AMOUNT_PATTERNS = (
    re.compile(
        r"(?P<currency>USD|CNY|RMB|EUR|GBP|MXN|JPY|CAD|AUD)\s*"
        r"(?P<amount>\d+(?:,\d{3})*(?:\.\d{1,4})?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<symbol>[$¥￥€£])\s*(?P<amount>\d+(?:,\d{3})*(?:\.\d{1,4})?)"
    ),
    re.compile(
        r"(?P<amount>\d+(?:,\d{3})*(?:\.\d{1,4})?)\s*"
        r"(?P<currency>美元|美金|人民币|元|欧元|英镑|墨西哥比索|日元)",
        re.IGNORECASE,
    ),
)

CURRENCY_ALIASES = {
    "$": "USD",
    "USD": "USD",
    "美元": "USD",
    "美金": "USD",
    "¥": "CNY",
    "￥": "CNY",
    "CNY": "CNY",
    "RMB": "CNY",
    "人民币": "CNY",
    "元": "CNY",
    "€": "EUR",
    "EUR": "EUR",
    "欧元": "EUR",
    "£": "GBP",
    "GBP": "GBP",
    "英镑": "GBP",
    "MXN": "MXN",
    "墨西哥比索": "MXN",
    "JPY": "JPY",
    "日元": "JPY",
    "CAD": "CAD",
    "AUD": "AUD",
}

CATEGORY_KEYWORDS = (
    ("network_ip", ("网络ip", "网络 ip", "住宅ip", "住宅 ip", "代理ip", "proxy", "ip费")),
    ("software_subscription", ("软件", "订阅", "会员", "saas", "插件")),
    ("advertising_topup", ("广告充值", "广告费", "投流", "ad spend", "广告预算")),
    ("sample", ("样品", "寄样", "sample")),
    ("logistics", ("物流", "运费", "快递", "仓储", "清关", "shipping")),
    ("procurement", ("采购", "进货", "货款", "原料", "打样")),
    ("payment_withdrawal_fee", ("提现费", "收款手续费", "通道费", "paypal费", "连连费", "万里汇费")),
    ("fx_loss", ("汇损", "汇兑损失", "换汇损失", "fx loss")),
    ("bank_fee", ("银行手续费", "转账手续费", "电汇费", "wire fee")),
    ("tax", ("税费", "增值税", "vat", "销售税", "所得税", "关税")),
    ("office", ("办公", "房租", "水电", "设备", "耗材")),
)

EXPENSE_INTENT = (
    "记录费用",
    "记一笔",
    "记账",
    "入账",
    "报销",
    "帮我记录",
    "记录进去",
    "费用",
    "付款",
    "买了",
    "支付了",
    "转账记录",
)
CONFIRM_INTENT = ("确认入账", "确认这笔", "确认费用", "确认记账")
EXPORT_INTENT = ("导出费用", "导出账本", "导出本月费用", "导出费用表", "导出表格")
SNAPSHOT_INTENT = ("费用汇总", "费用账本", "本月费用", "看账本", "日常费用")
SELF_TRANSFER_HINTS = (
    "转到自己",
    "自己账户",
    "账户互转",
    "内部转账",
    "提现到银行卡",
    "提现到自己",
    "余额提现",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any, limit: int = 500) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _context(payload: dict[str, Any]) -> dict[str, str]:
    page_context = payload.get("page_context")
    page_context = page_context if isinstance(page_context, dict) else {}
    return {
        "project_id": _safe_text(payload.get("project_id") or page_context.get("project_id"), 120),
        "task_id": _safe_text(payload.get("task_id") or payload.get("id") or page_context.get("task_id"), 120),
        "conversation_id": _safe_text(
            payload.get("conversation_id")
            or page_context.get("conversation_id")
            or payload.get("task_id")
            or payload.get("id"),
            120,
        ),
        "store_binding_id": _safe_text(
            payload.get("store_binding_id")
            or payload.get("store_id")
            or page_context.get("store_binding_id")
            or page_context.get("store_id"),
            160,
        ),
        "browser_profile_id": _safe_text(
            payload.get("browser_profile_id") or page_context.get("browser_profile_id"), 160
        ),
    }


def _extract_amount(text: str) -> tuple[float | None, str, str]:
    for pattern in AMOUNT_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        raw_amount = str(match.group("amount") or "").replace(",", "")
        try:
            amount = round(float(raw_amount), 4)
        except ValueError:
            continue
        raw_currency = match.groupdict().get("currency") or match.groupdict().get("symbol") or ""
        return amount, CURRENCY_ALIASES.get(str(raw_currency).upper(), CURRENCY_ALIASES.get(str(raw_currency), "")), match.group(0)
    return None, "", ""


def _extract_fee(text: str) -> tuple[float, str]:
    match = re.search(
        r"(?:手续费|通道费|提现费|汇损|fee)\D{0,12}"
        r"(?:(USD|CNY|RMB|EUR|GBP|MXN|[$¥￥€£])\s*)?"
        r"(\d+(?:,\d{3})*(?:\.\d{1,4})?)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return 0.0, ""
    try:
        amount = round(float(match.group(2).replace(",", "")), 4)
    except ValueError:
        return 0.0, ""
    token = str(match.group(1) or "")
    return amount, CURRENCY_ALIASES.get(token.upper(), CURRENCY_ALIASES.get(token, ""))


def _extract_date(text: str) -> tuple[str, bool]:
    today = date.today()
    if "昨天" in text:
        return (today - timedelta(days=1)).isoformat(), False
    if "今天" in text:
        return today.isoformat(), False
    match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?", text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat(), False
        except ValueError:
            pass
    match = re.search(r"(?<!\d)(\d{1,2})[-/.月](\d{1,2})日?", text)
    if match:
        try:
            return date(today.year, int(match.group(1)), int(match.group(2))).isoformat(), False
        except ValueError:
            pass
    return today.isoformat(), True


def _category(text: str) -> str:
    lowered = text.lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword.lower() in lowered for keyword in keywords):
            return category
    return "miscellaneous"


def _attachment_material(semantic: dict[str, Any] | None) -> tuple[str, list[dict[str, str]]]:
    if not isinstance(semantic, dict):
        return "", []
    text_parts: list[str] = []
    refs: list[dict[str, str]] = []
    for item in semantic.get("files", []):
        if not isinstance(item, dict):
            continue
        source_ref = _safe_text(item.get("source_ref"), 500)
        refs.append(
            {
                "name": Path(source_ref).name or _safe_text(item.get("name"), 180),
                "sha256": _safe_text(item.get("sha256"), 80),
                "source_ref": source_ref,
            }
        )
        pdf = item.get("pdf")
        if isinstance(pdf, dict):
            values = pdf.get("candidate_key_values")
            if isinstance(values, dict):
                text_parts.extend(f"{key}: {value}" for key, value in values.items())
        for layer in ("observations", "inferences", "drafts"):
            for statement in item.get(layer, []):
                if isinstance(statement, dict):
                    text_parts.append(_safe_text(statement.get("statement"), 1000))
    return "\n".join(part for part in text_parts if part), refs


def _fingerprint(fields: dict[str, Any], raw_text: str) -> str:
    attachment_hashes = [
        str(item.get("sha256") or "")
        for item in fields.get("attachment_refs", [])
        if isinstance(item, dict) and item.get("sha256")
    ]
    material = {
        "occurred_at": fields.get("occurred_at"),
        "amount": fields.get("amount"),
        "currency": fields.get("currency"),
        "entry_type": fields.get("entry_type"),
        "category": fields.get("category"),
        "project_id": fields.get("project_id"),
        "task_id": fields.get("task_id"),
        "store_binding_id": fields.get("store_binding_id"),
        "attachments": sorted(attachment_hashes),
        "raw_text_sha256": hashlib.sha256(raw_text.strip().encode("utf-8")).hexdigest(),
    }
    return hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _find_by_entry_id(root: Path, entry_id: str) -> IntakeRecord | None:
    target = entry_id.strip().upper()
    for record in read_records(root, RECORD_TYPE):
        if str(record.fields.get("entry_id") or "").upper() == target:
            return record
    return None


def _find_by_fingerprint(root: Path, fingerprint: str) -> IntakeRecord | None:
    for record in read_records(root, RECORD_TYPE):
        if record.fields.get("expense_fingerprint") == fingerprint:
            return record
    return None


def _append_event(
    root: Path,
    fields: dict[str, Any],
    *,
    kind: str,
    statement: str,
    actor: str,
) -> dict[str, Any]:
    source_refs = [
        str(item.get("source_ref") or "")
        for item in fields.get("attachment_refs", [])
        if isinstance(item, dict) and item.get("source_ref")
    ]
    return append_business_event(
        root,
        {
            "event_type": "operating_expense_recorded",
            "kind": kind,
            "workspace_id": "local-workspace",
            "project_id": fields.get("project_id"),
            "task_id": fields.get("task_id"),
            "conversation_id": fields.get("conversation_id"),
            "actor": actor,
            "statement": statement,
            "confidence": fields.get("confidence") or "owner_review_required",
            "status": fields.get("status"),
            "source_refs": source_refs,
            "business_object_refs": [
                {
                    "object_type": RECORD_TYPE,
                    "object_id": fields.get("entry_id"),
                    "version_ref": fields.get("updated_at") or fields.get("created_at"),
                    "source_ref": source_refs[0] if source_refs else "",
                }
            ],
            "payload": {
                "entry_id": fields.get("entry_id"),
                "entry_type": fields.get("entry_type"),
                "category": fields.get("category"),
                "amount": fields.get("amount"),
                "currency": fields.get("currency"),
                "fee_amount": fields.get("fee_amount"),
                "count_in_expense": fields.get("count_in_expense"),
                "status": fields.get("status"),
            },
        },
        actor=actor,
    )


def create_operating_expense_draft(
    root: Path,
    payload: dict[str, Any],
    *,
    semantic: dict[str, Any] | None = None,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    message = _safe_text(payload.get("message") or payload.get("note"), 4000)
    attachment_text, attachment_refs = _attachment_material(semantic)
    parse_text = "\n".join(part for part in (message, attachment_text) if part)
    if not parse_text and not attachment_refs:
        raise ValueError("请提供费用说明、金额，或上传转账/付款凭证。")

    amount, currency, matched_amount = _extract_amount(parse_text)
    fee_amount, fee_currency = _extract_fee(parse_text)
    if not currency and fee_currency:
        currency = fee_currency
    occurred_at, inferred_date = _extract_date(parse_text)
    lowered = parse_text.lower()
    self_transfer = any(hint in lowered for hint in SELF_TRANSFER_HINTS)
    ambiguous_transfer = "转账" in lowered and not any(
        word in lowered for word in ("采购", "货款", "运费", "广告", "软件", "样品", "ip", "税费", "服务费")
    )
    entry_type = "transfer" if self_transfer or ambiguous_transfer else "expense"
    count_in_expense = entry_type == "expense"
    unknown_fields: list[str] = []
    if amount is None:
        unknown_fields.append("amount")
    if not currency:
        unknown_fields.append("currency")
    if ambiguous_transfer and not self_transfer:
        unknown_fields.append("transaction_purpose")
    if attachment_refs and not attachment_text:
        unknown_fields.append("attachment_amount_requires_review")
    context = _context(payload)
    entry_id = "EXP-" + datetime.now().strftime("%Y%m%d") + "-" + uuid4().hex[:6].upper()
    created_at = _now_iso()
    fields: dict[str, Any] = {
        "entry_id": entry_id,
        "occurred_at": occurred_at,
        "occurred_at_inferred": inferred_date,
        "amount": amount,
        "currency": currency,
        "entry_type": entry_type,
        "category": "internal_transfer" if entry_type == "transfer" else _category(parse_text),
        "vendor_payee": _safe_text(payload.get("vendor_payee") or payload.get("payee"), 200),
        "payment_method": _safe_text(payload.get("payment_method"), 120),
        **context,
        "source_kind": "attachment_observation" if attachment_refs else "owner_text",
        "attachment_refs": attachment_refs,
        "note": message,
        "matched_amount_text": matched_amount,
        "fee_amount": fee_amount,
        "fee_currency": fee_currency or currency,
        "status": PENDING,
        "confidence": "owner_review_required",
        "count_in_expense": count_in_expense,
        "unknown_fields": sorted(set(unknown_fields)),
        "created_at": created_at,
        "updated_at": created_at,
        "confirmed_by": "",
        "confirmed_at": "",
        "truth_precedence": "confirmed_receipt_or_statement",
        "external_actions": [],
    }
    fields["expense_fingerprint"] = _fingerprint(fields, parse_text)
    existing = _find_by_fingerprint(root, fields["expense_fingerprint"])
    if existing:
        return {
            "ok": True,
            "duplicate": True,
            "entry": existing.fields,
            "record_id": existing.record_id,
            "external_actions": [],
        }

    record = IntakeRecord(
        record_type=RECORD_TYPE,
        fields=fields,
        raw_text=message,
        source="local_expense_intake",
        review_status="owner_review_required",
        confidence=0.5 if attachment_refs else 0.7,
        metadata={
            "external_action_count": 0,
            "attachment_count": len(attachment_refs),
            "sensitive_payment_data_stored": False,
        },
    )
    append_record(root, record)
    _append_event(
        root,
        fields,
        kind="draft",
        statement=f"日常费用草稿 {entry_id} 已生成，等待负责人确认。",
        actor=actor,
    )
    return {
        "ok": True,
        "duplicate": False,
        "entry": fields,
        "record_id": record.record_id,
        "external_actions": [],
    }


def confirm_operating_expense(
    root: Path,
    payload: dict[str, Any],
    *,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    entry_id = _safe_text(payload.get("entry_id"), 80).upper()
    if not entry_id:
        raise ValueError("确认入账时必须提供费用编号。")
    record = _find_by_entry_id(root, entry_id)
    if not record:
        raise ValueError(f"没有找到费用草稿：{entry_id}")
    if record.fields.get("status") == POSTED:
        return {"ok": True, "idempotent": True, "entry": record.fields, "external_actions": []}
    if record.fields.get("status") == VOIDED:
        raise ValueError("已作废的费用不能确认入账。")

    fields = dict(record.fields)
    for key in ("amount", "currency", "occurred_at", "category", "entry_type"):
        value = payload.get(key)
        if value not in (None, ""):
            fields[key] = float(value) if key == "amount" else _safe_text(value, 160)
    if not isinstance(fields.get("amount"), (int, float)) or float(fields["amount"]) <= 0:
        raise ValueError("金额缺失或无效，请补充后再确认。")
    if not fields.get("currency"):
        raise ValueError("币种缺失，请补充后再确认。")
    if fields.get("entry_type") == "transfer" and "count_in_expense" not in payload:
        fields["count_in_expense"] = False
    elif "count_in_expense" in payload:
        fields["count_in_expense"] = bool(payload.get("count_in_expense"))
    fields["status"] = POSTED
    fields["confidence"] = "owner_confirmed"
    fields["confirmed_by"] = actor
    fields["confirmed_at"] = _now_iso()
    fields["updated_at"] = fields["confirmed_at"]
    fields["unknown_fields"] = [
        item
        for item in fields.get("unknown_fields", [])
        if item not in {"amount", "currency", "transaction_purpose", "attachment_amount_requires_review"}
    ]
    record.fields = fields
    record.review_status = "approved"
    record.confidence = 1.0
    update_record(root, record)
    _append_event(
        root,
        fields,
        kind="fact",
        statement=f"日常费用 {entry_id} 已由负责人确认入账。",
        actor=actor,
    )
    return {"ok": True, "idempotent": False, "entry": fields, "external_actions": []}


def operating_expense_snapshot(
    root: Path,
    *,
    project_id: str = "",
    task_id: str = "",
    status: str = "",
    start_date: str = "",
    end_date: str = "",
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for record in read_records(root, RECORD_TYPE):
        fields = dict(record.fields)
        if project_id and fields.get("project_id") != project_id:
            continue
        if task_id and fields.get("task_id") != task_id:
            continue
        if status and fields.get("status") != status:
            continue
        occurred_at = str(fields.get("occurred_at") or "")
        if start_date and occurred_at < start_date:
            continue
        if end_date and occurred_at > end_date:
            continue
        fields["record_id"] = record.record_id
        entries.append(fields)
    entries.sort(key=lambda item: (str(item.get("occurred_at") or ""), str(item.get("created_at") or "")), reverse=True)
    totals: dict[str, float] = {}
    category_totals: dict[str, dict[str, float]] = {}
    fee_totals: dict[str, float] = {}
    for fields in entries:
        if fields.get("status") != POSTED:
            continue
        currency = str(fields.get("currency") or "UNKNOWN")
        if fields.get("count_in_expense"):
            amount = float(fields.get("amount") or 0.0)
            totals[currency] = round(totals.get(currency, 0.0) + amount, 4)
            category = str(fields.get("category") or "uncategorized")
            category_currency_totals = category_totals.setdefault(category, {})
            category_currency_totals[currency] = round(
                category_currency_totals.get(currency, 0.0) + amount,
                4,
            )
        fee = float(fields.get("fee_amount") or 0.0)
        if fee > 0:
            fee_currency = str(fields.get("fee_currency") or currency or "UNKNOWN")
            fee_totals[fee_currency] = round(fee_totals.get(fee_currency, 0.0) + fee, 4)
    return {
        "ok": True,
        "entries": entries,
        "count": len(entries),
        "pending_count": sum(item.get("status") == PENDING for item in entries),
        "posted_expense_totals": totals,
        "posted_expense_totals_by_category_currency": category_totals,
        "posted_fee_totals": fee_totals,
        "truth_precedence": "confirmed_receipt_or_statement",
        "external_actions": [],
    }


def export_operating_expenses(
    root: Path,
    payload: dict[str, Any] | None = None,
    *,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    data = dict(payload or {})
    snapshot = operating_expense_snapshot(
        root,
        project_id=_safe_text(data.get("project_id"), 120),
        task_id=_safe_text(data.get("task_id"), 120),
        status=_safe_text(data.get("status"), 80),
        start_date=_safe_text(data.get("start_date"), 20),
        end_date=_safe_text(data.get("end_date"), 20),
    )
    output_dir = root / "outputs" / "finance"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"operating_expenses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    columns = [
        "entry_id",
        "occurred_at",
        "status",
        "entry_type",
        "category",
        "amount",
        "currency",
        "fee_amount",
        "fee_currency",
        "count_in_expense",
        "vendor_payee",
        "payment_method",
        "project_id",
        "task_id",
        "store_binding_id",
        "browser_profile_id",
        "source_kind",
        "note",
        "confirmed_by",
        "confirmed_at",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(snapshot["entries"])
    append_business_event(
        root,
        {
            "event_type": "operating_expense_exported",
            "kind": "observation",
            "workspace_id": "local-workspace",
            "project_id": data.get("project_id"),
            "task_id": data.get("task_id"),
            "conversation_id": data.get("conversation_id") or data.get("task_id"),
            "actor": actor,
            "statement": "日常费用账本已导出为本地 CSV 文件。",
            "confidence": "system_verified",
            "status": "exported_local_only",
            "source_refs": [str(path.relative_to(root)).replace("\\", "/")],
            "business_object_refs": [],
            "payload": {"row_count": snapshot["count"]},
        },
        actor=actor,
    )
    return {
        "ok": True,
        "path": str(path),
        "relative_path": str(path.relative_to(root)).replace("\\", "/"),
        "row_count": snapshot["count"],
        "external_actions": [],
    }


def _entry_summary(entry: dict[str, Any]) -> str:
    amount = entry.get("amount")
    amount_text = f"{amount:g} {entry.get('currency')}" if isinstance(amount, (int, float)) and entry.get("currency") else "金额/币种待补"
    scope = entry.get("store_binding_id") or entry.get("project_id") or "公司共享"
    transfer_note = "；内部转账本金不计成本" if entry.get("entry_type") == "transfer" else ""
    return (
        f"{entry.get('entry_id')}｜{entry.get('occurred_at')}｜{entry.get('category')}｜"
        f"{amount_text}｜范围：{scope}{transfer_note}"
    )


def maybe_handle_operating_expense_chat(
    root: Path,
    payload: dict[str, Any],
    *,
    semantic: dict[str, Any] | None = None,
    actor: str = "desktop-owner",
) -> dict[str, Any] | None:
    message = _safe_text(payload.get("message"), 4000)
    compact = message.lower()
    if any(token in compact for token in CONFIRM_INTENT):
        match = re.search(r"EXP-\d{8}-[A-Z0-9]{6}", message, re.IGNORECASE)
        if not match:
            return {
                "mode": "finance_expense",
                "reply": "请把待确认费用编号一起发给我，例如：确认入账 EXP-20260724-ABC123。",
                "records": [],
                "actions": [],
                "external_actions": [],
                "privacy": {"scope": "local_ledger_only", "protected": True, "model": "local_rules"},
            }
        confirmation_payload: dict[str, Any] = {"entry_id": match.group(0)}
        amount, currency, _matched_amount = _extract_amount(message)
        if amount is not None:
            confirmation_payload["amount"] = amount
        if currency:
            confirmation_payload["currency"] = currency
        result = confirm_operating_expense(root, confirmation_payload, actor=actor)
        entry = result["entry"]
        return {
            "mode": "finance_expense",
            "reply": "已确认入账：\n" + _entry_summary(entry),
            "records": [entry],
            "actions": [],
            "external_actions": [],
            "privacy": {"scope": "local_ledger_only", "protected": True, "model": "local_rules"},
        }
    if any(token in compact for token in EXPORT_INTENT):
        result = export_operating_expenses(root, {**payload, **_context(payload)}, actor=actor)
        return {
            "mode": "finance_expense",
            "reply": f"已导出 {result['row_count']} 条本地账本记录：{result['relative_path']}",
            "records": [result],
            "actions": [],
            "external_actions": [],
            "privacy": {"scope": "local_ledger_only", "protected": True, "model": "local_rules"},
        }
    if any(token in compact for token in SNAPSHOT_INTENT):
        context = _context(payload)
        result = operating_expense_snapshot(
            root, project_id=context["project_id"], task_id=context["task_id"]
        )
        totals = "；".join(
            f"{currency} {amount:g}" for currency, amount in result["posted_expense_totals"].items()
        ) or "暂无已确认费用"
        return {
            "mode": "finance_expense",
            "reply": f"账本共 {result['count']} 条，待确认 {result['pending_count']} 条；已确认费用：{totals}。",
            "records": result["entries"][:20],
            "actions": [],
            "external_actions": [],
            "privacy": {"scope": "local_ledger_only", "protected": True, "model": "local_rules"},
        }
    explicit_finance = str(
        payload.get("record_type") or payload.get("intent") or ""
    ).strip().lower() in {
        "operating_expense_entry",
        "operating_expense",
        "finance_expense",
    }
    if explicit_finance or any(token in compact for token in EXPENSE_INTENT):
        result = create_operating_expense_draft(root, payload, semantic=semantic, actor=actor)
        entry = result["entry"]
        unknowns = "、".join(entry.get("unknown_fields") or [])
        reply = "已找到同一笔待确认记录：" if result.get("duplicate") else "已生成待确认费用草稿："
        reply += "\n" + _entry_summary(entry)
        if unknowns:
            reply += f"\n仍需确认：{unknowns}。"
        reply += f"\n核对无误后回复：确认入账 {entry['entry_id']}"
        return {
            "mode": "finance_expense",
            "reply": reply,
            "records": [entry],
            "actions": [],
            "external_actions": [],
            "privacy": {"scope": "local_ledger_only", "protected": True, "model": "local_rules"},
            "attachment_semantic_status": str((semantic or {}).get("status") or ""),
        }
    return None
