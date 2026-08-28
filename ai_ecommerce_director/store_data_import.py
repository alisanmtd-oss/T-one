from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .bulk_import import ColumnMapping, map_columns, row_to_fields
from .parser import FIELD_ALIASES, normalize_fields
from .scoring import score_record
from .storage import append_record, write_report
from .store_metrics import summarize_store_metrics
from .types import IntakeRecord


@dataclass(slots=True)
class StoreDataPasteResult:
    rows_read: int
    records_created: int
    report_path: Path
    dashboard: dict[str, Any]
    records: list[IntakeRecord]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows_read": self.rows_read,
            "records_created": self.records_created,
            "report_path": str(self.report_path),
            "dashboard": self.dashboard,
            "records": [record.to_dict() for record in self.records],
        }


def import_pasted_store_data(root: Path, payload: dict[str, Any]) -> StoreDataPasteResult:
    raw_text = str(payload.get("raw_text") or payload.get("text") or "").strip()
    if not raw_text:
        raise ValueError("没有检测到可读取的店铺后台数据。负责人确认授权报表来源后，后台 AI 再整理到经营大盘。")

    defaults = {
        "marketplace": str(payload.get("marketplace") or payload.get("platform") or "").strip(),
        "source_platform": str(payload.get("marketplace") or payload.get("platform") or "").strip(),
        "store_id": str(payload.get("store_id") or "").strip(),
        "store_name": str(payload.get("store_name") or "").strip(),
        "country_code": str(payload.get("country_code") or payload.get("country") or "").strip(),
        "currency": str(payload.get("currency") or "").strip(),
        "report_type": str(payload.get("report_type") or "manual_paste").strip(),
        "metric_date": str(payload.get("metric_date") or "").strip(),
        "snapshot_start": str(payload.get("snapshot_start") or "").strip(),
        "snapshot_end": str(payload.get("snapshot_end") or payload.get("metric_date") or "").strip(),
    }
    rows = parse_pasted_table(raw_text)
    parsed_rows = rows if rows else [parse_metric_cards(raw_text)]
    records: list[IntakeRecord] = []

    mapping: list[ColumnMapping] = []
    if rows:
        headers = list(rows[0].keys())
        mapping = map_columns(headers, default_store_data_mapping(), 0.55)
    for index, row in enumerate(parsed_rows, start=1):
        if rows:
            fields, confidence = row_to_fields(row, mapping)
        else:
            fields = normalize_fields(row)
            confidence = 0.78
        fields = apply_metric_defaults(fields, defaults)
        if not has_metric_value(fields):
            continue
        score, notes = score_record("store_metric_snapshot", fields)
        record = IntakeRecord(
            record_type="store_metric_snapshot",
            fields=fields,
            raw_text=json.dumps({"row": row, "source": "manual_store_data_paste"}, ensure_ascii=False),
            source="manual_store_data_paste",
            score=score,
            director_notes=notes,
            confidence=confidence,
            metadata={"paste_row": index, "report_type": defaults["report_type"]},
        )
        append_record(root, record)
        records.append(record)

    dashboard = summarize_store_metrics(root)
    report = build_store_data_paste_report(raw_text, defaults, len(parsed_rows), records, dashboard)
    report_path = write_report(root, f"store_data_paste_{date.today().isoformat()}", report)
    return StoreDataPasteResult(len(parsed_rows), len(records), report_path, dashboard, records)


def default_store_data_mapping() -> dict[str, str]:
    mapping = {
        "Period Start": "snapshot_start",
        "Period End": "snapshot_end",
        "Settlement ID": "settlement_id",
        "Payout ID": "settlement_id",
        "Statement ID": "settlement_id",
        "Order ID": "settlement_id",
        "Currency": "currency",
        "Net Sales": "net_revenue",
        "Net Revenue": "net_revenue",
        "Settlement Amount": "settlement_amount",
        "Payout Amount": "settlement_amount",
        "Amount Paid": "settlement_amount",
        "Platform Fee": "platform_fee",
        "Marketplace Fee": "platform_fee",
        "Commission": "commission_fee",
        "Referral Fee": "commission_fee",
        "Transaction Fee": "transaction_fee",
        "Payment Fee": "transaction_fee",
        "Shipping Fee": "shipping_fee",
        "Shipping Cost": "shipping_fee",
        "Tax": "tax_amount",
        "Tax Amount": "tax_amount",
        "Adjustment": "adjustment_amount",
        "Reserve": "reserve_amount",
    }
    mapping.update(
        {
            "Date": "metric_date",
            "Time": "metric_date",
            "日期": "metric_date",
            "时间": "metric_date",
            "Platform": "marketplace",
            "Marketplace": "marketplace",
            "平台": "marketplace",
            "Shop": "store_name",
            "Store": "store_name",
            "店铺": "store_id",
            "店铺ID": "store_id",
            "Country": "country_code",
            "国家": "country_code",
            "Product": "product_name",
            "商品": "product_name",
            "SKU": "sku",
            "Seller SKU": "seller_sku",
            "ASIN": "asin",
            "Orders": "order_count",
            "订单": "order_count",
            "订单数": "order_count",
            "Units": "unit_count",
            "销量": "unit_count",
            "件数": "unit_count",
            "Sales": "total_revenue",
            "GMV": "total_revenue",
            "销售额": "total_revenue",
            "成交金额": "total_revenue",
            "Ad Spend": "ad_spend",
            "广告花费": "ad_spend",
            "广告消耗": "ad_spend",
            "Cost": "ad_spend",
            "Spend": "ad_spend",
            "ROAS": "roi",
            "Refunds": "refund_count",
            "退款单数": "refund_count",
            "Refund Amount": "refund_amount",
            "退款金额": "refund_amount",
            "Returns": "return_count",
            "退货": "return_count",
            "退货数": "return_count",
        }
    )
    return mapping


def parse_pasted_table(raw_text: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if len(lines) < 2:
        return []
    delimiter = "\t" if any("\t" in line for line in lines[:3]) else ","
    if delimiter == "," and not any("," in line for line in lines[:3]):
        return []
    try:
        reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
        if not reader.fieldnames or len(reader.fieldnames) < 2:
            return []
        rows = [
            {str(key).strip(): str(value or "").strip() for key, value in row.items() if key}
            for row in reader
            if any(str(value or "").strip() for value in row.values())
        ]
    except csv.Error:
        return []
    return rows


def parse_metric_cards(raw_text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    alias_map = metric_alias_map()
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    for line in lines:
        parsed = parse_metric_line(line, alias_map)
        fields.update(parsed)
    for index, line in enumerate(lines[:-1]):
        if has_number(line):
            continue
        canonical = alias_map.get(normalize_label(line))
        if canonical and lines[index + 1]:
            fields.setdefault(canonical, lines[index + 1])
    return normalize_fields(fields)


def parse_metric_line(line: str, alias_map: dict[str, str]) -> dict[str, Any]:
    clean = re.sub(r"\s+", " ", line).strip()
    for separator in [":", "：", "\t", "  "]:
        if separator in clean:
            left, right = clean.split(separator, 1)
            canonical = alias_map.get(normalize_label(left))
            if canonical and right.strip():
                return {canonical: right.strip()}
    result: dict[str, Any] = {}
    for label, canonical in alias_map.items():
        if label and label in normalize_label(clean):
            match = re.search(r"[-$￥¥€£]?\s*\d[\d,]*(?:\.\d+)?%?", clean)
            if match:
                result[canonical] = match.group(0)
    return result


def metric_alias_map() -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for field, aliases in FIELD_ALIASES.items():
        if field in {
            "marketplace",
            "source_platform",
            "store_id",
            "store_name",
            "country_code",
            "currency",
            "metric_date",
            "snapshot_start",
            "snapshot_end",
            "report_type",
            "total_revenue",
            "net_revenue",
            "settlement_amount",
            "order_count",
            "orders",
            "unit_count",
            "ad_spend",
            "refund_amount",
            "refund_count",
            "return_count",
            "platform_fee",
            "commission_fee",
            "transaction_fee",
            "shipping_fee",
            "tax_amount",
            "adjustment_amount",
            "reserve_amount",
            "roi",
        }:
            alias_map[normalize_label(field)] = field
            for alias in aliases:
                alias_map[normalize_label(alias)] = field
    alias_map.update(
        {
            "gmv": "total_revenue",
            "sales": "total_revenue",
            "revenue": "total_revenue",
            "orders": "order_count",
            "ordercount": "order_count",
            "units": "unit_count",
            "unitssold": "unit_count",
            "spend": "ad_spend",
            "cost": "ad_spend",
            "adcost": "ad_spend",
            "roas": "roi",
            "refunds": "refund_count",
            "returns": "return_count",
            "销售额": "total_revenue",
            "成交金额": "total_revenue",
            "订单数": "order_count",
            "订单": "order_count",
            "销量": "unit_count",
            "件数": "unit_count",
            "广告花费": "ad_spend",
            "广告消耗": "ad_spend",
            "退款金额": "refund_amount",
            "退款单数": "refund_count",
            "退货数": "return_count",
            "退货": "return_count",
        }
    )
    return alias_map


def apply_metric_defaults(fields: dict[str, Any], defaults: dict[str, str]) -> dict[str, Any]:
    merged = dict(fields)
    for key, value in defaults.items():
        if value and not merged.get(key):
            merged[key] = value
    if not merged.get("marketplace") and merged.get("source_platform"):
        merged["marketplace"] = merged["source_platform"]
    if not merged.get("source_platform") and merged.get("marketplace"):
        merged["source_platform"] = merged["marketplace"]
    if not merged.get("metric_date") and not merged.get("snapshot_end"):
        merged["metric_date"] = date.today().isoformat()
    return normalize_fields(merged)


def has_metric_value(fields: dict[str, Any]) -> bool:
    metric_keys = {
        "total_revenue",
        "gmv",
        "order_count",
        "orders",
        "unit_count",
        "sales_count",
        "ad_spend",
        "refund_amount",
        "refund_count",
        "return_count",
        "settlement_amount",
        "platform_fee",
        "commission_fee",
        "transaction_fee",
        "shipping_fee",
        "tax_amount",
    }
    return bool((fields.get("marketplace") or fields.get("source_platform")) and any(fields.get(key) not in {"", None} for key in metric_keys))


def build_store_data_paste_report(
    raw_text: str,
    defaults: dict[str, str],
    rows_read: int,
    records: list[IntakeRecord],
    dashboard: dict[str, Any],
) -> str:
    summary = dashboard.get("summary", {})
    return "\n".join(
        [
            "# Manual Store Data Paste Import",
            "",
            f"- Marketplace: {defaults.get('marketplace') or '-'}",
            f"- Store: {defaults.get('store_id') or defaults.get('store_name') or '-'}",
            f"- Report type: {defaults.get('report_type') or '-'}",
            f"- Rows parsed: {rows_read}",
            f"- Records saved: {len(records)}",
            "",
            "## Current Dashboard Totals",
            f"- Revenue: {summary.get('revenue', 0)}",
            f"- Orders: {summary.get('orders', 0)}",
            f"- Units: {summary.get('units', 0)}",
            f"- Ad spend: {summary.get('ad_spend', 0)}",
            f"- ROAS: {summary.get('roas')}",
            f"- Refund amount: {summary.get('refund_amount', 0)}",
            f"- Returns: {summary.get('return_count', 0)}",
            "",
            "## Source Preview",
            raw_text[:1500],
            "",
        ]
    )


def normalize_label(value: Any) -> str:
    return re.sub(r"[\s_\-()/（）:：]+", "", str(value or "").strip().lower())


def has_number(value: str) -> bool:
    return bool(re.search(r"\d", value))
