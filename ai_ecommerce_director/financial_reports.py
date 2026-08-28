from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .bulk_import import ImportSummary, import_table
from .platform_settlement_finance import (
    build_inventory_cash_plan,
    finance_settlement_snapshot,
    import_platform_settlement_statement,
    load_platform_fee_registry,
    platform_fee_registry_snapshot,
    reconcile_estimate_with_statement,
    run_fictional_finance_demo,
    save_pre_operation_estimate,
)
from .storage import write_report
from .store_metrics import summarize_store_metrics


FINANCIAL_REPORT_DIR = Path("data") / "financial_reports"


@dataclass(slots=True)
class FinancialImportResult:
    summary: ImportSummary
    dashboard: dict[str, Any]
    report_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "dashboard": self.dashboard,
            "report_path": str(self.report_path),
        }


def import_financial_report(
    root: Path,
    file_path: Path,
    *,
    marketplace: str = "",
    store_id: str = "",
    report_type: str = "",
    worksheet: str | None = None,
) -> FinancialImportResult:
    mapping = default_financial_mapping()
    summary = import_table(
        root,
        file_path,
        "store_metric_snapshot",
        worksheet=worksheet,
        explicit_mapping=mapping,
        confidence_threshold=0.55,
        update_on_duplicate=True,
    )
    enrich_imported_records(root, marketplace=marketplace, store_id=store_id, report_type=report_type, file_path=file_path)
    dashboard = summarize_store_metrics(root)
    report = build_financial_import_report(summary, dashboard, file_path, marketplace, store_id, report_type)
    report_path = write_report(root, f"financial_import_{date.today().isoformat()}", report)
    return FinancialImportResult(summary, dashboard, report_path)


def default_financial_mapping() -> dict[str, str]:
    return {
        "Date": "metric_date",
        "日期": "metric_date",
        "Period Start": "snapshot_start",
        "Period End": "snapshot_end",
        "Settlement ID": "settlement_id",
        "Payout ID": "settlement_id",
        "Statement ID": "settlement_id",
        "Order ID": "settlement_id",
        "Marketplace": "marketplace",
        "Platform": "marketplace",
        "Store": "store_name",
        "Store ID": "store_id",
        "Shop Name": "store_name",
        "Currency": "currency",
        "Sales": "total_revenue",
        "Revenue": "total_revenue",
        "GMV": "total_revenue",
        "Total Sales": "total_revenue",
        "Net Sales": "net_revenue",
        "Net Revenue": "net_revenue",
        "Settlement Amount": "settlement_amount",
        "Payout Amount": "settlement_amount",
        "Amount Paid": "settlement_amount",
        "Orders": "order_count",
        "Order Count": "order_count",
        "Units": "unit_count",
        "Units Sold": "unit_count",
        "Ad Spend": "ad_spend",
        "Advertising Cost": "ad_spend",
        "Refund": "refund_amount",
        "Refund Amount": "refund_amount",
        "Refunds": "refund_count",
        "Returns": "return_count",
        "Platform Fee": "platform_fee",
        "Marketplace Fee": "platform_fee",
        "Commission": "commission_fee",
        "Referral Fee": "commission_fee",
        "Transaction Fee": "transaction_fee",
        "Payment Fee": "transaction_fee",
        "Shipping Fee": "shipping_fee",
        "Shipping Cost": "shipping_fee",
        "Activity Fee": "activity_service_fee",
        "Campaign Fee": "activity_service_fee",
        "Service Fee": "activity_service_fee",
        "Affiliate Fee": "affiliate_creator_fee",
        "Creator Fee": "affiliate_creator_fee",
        "Payment Fee": "payment_fee",
        "Warehouse Storage Fee": "warehouse_storage_fee",
        "Storage Fee": "warehouse_storage_fee",
        "Tax Withholding": "tax_withholding",
        "Refund Reserve": "refund_return_reserve",
        "Return Reserve": "refund_return_reserve",
        "Tax": "tax_amount",
        "Tax Amount": "tax_amount",
        "Adjustment": "adjustment_amount",
        "Reserve": "reserve_amount",
    }


def enrich_imported_records(root: Path, *, marketplace: str, store_id: str, report_type: str, file_path: Path) -> None:
    from .storage import read_records, write_records
    from .scoring import score_record

    records = read_records(root, "store_metric_snapshot")
    changed = False
    for record in records:
        if str(record.metadata.get("file_path") or "") != str(file_path):
            continue
        if marketplace and not record.fields.get("marketplace"):
            record.fields["marketplace"] = marketplace
        if marketplace and not record.fields.get("source_platform"):
            record.fields["source_platform"] = marketplace
        if store_id and not record.fields.get("store_id"):
            record.fields["store_id"] = store_id
        if report_type and not record.fields.get("report_type"):
            record.fields["report_type"] = report_type
        record.score, record.director_notes = score_record(record.record_type, record.fields)
        changed = True
    if changed:
        write_records(root, "store_metric_snapshot", records)


def build_financial_import_report(
    summary: ImportSummary,
    dashboard: dict[str, Any],
    file_path: Path,
    marketplace: str,
    store_id: str,
    report_type: str,
) -> str:
    total = dashboard.get("summary", {})
    return "\n".join(
        [
            "# Financial Report Import",
            "",
            f"- File: {file_path}",
            f"- Marketplace: {marketplace or '-'}",
            f"- Store: {store_id or '-'}",
            f"- Report type: {report_type or '-'}",
            f"- Rows read: {summary.rows_read}",
            f"- Created: {summary.created}",
            f"- Duplicates: {summary.duplicates}",
            f"- Skipped: {summary.skipped}",
            "",
            "## Current Dashboard Totals",
            f"- Revenue: {total.get('revenue', 0)}",
            f"- Net revenue: {total.get('net_revenue', 0)}",
            f"- Settlement amount: {total.get('settlement_amount', 0)}",
            f"- Orders: {total.get('orders', 0)}",
            f"- Ad spend: {total.get('ad_spend', 0)}",
            f"- Refund amount: {total.get('refund_amount', 0)}",
            f"- Fee total: {total.get('fee_total', 0)}",
            f"- ROAS: {total.get('roas')}",
            "",
        ]
    )


def copy_financial_upload(root: Path, source_path: Path) -> Path:
    target_dir = root / FINANCIAL_REPORT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source_path.name
    target.write_bytes(source_path.read_bytes())
    return target
