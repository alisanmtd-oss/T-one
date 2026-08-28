from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .dashboard_source_admission import dashboard_source_is_admitted
from .storage import read_records
from .types import IntakeRecord


VIRTUAL_STORE_MARKERS = {
    "demo",
    "sample",
    "virtual",
    "mock",
    "test",
    "tk-us-test",
    "aelfric",
    "culture kings",
    "iherb",
}

UTC_TIMEZONE_ALIASES = {"", "utc", "z", "gmt", "etc/utc", "etc/gmt"}


def safe_zoneinfo(value: str | None) -> timezone | ZoneInfo:
    """Return a timezone object even on Windows builds without the tzdata package."""
    timezone_name = str(value or "UTC").strip() or "UTC"
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        if timezone_name.casefold() in UTC_TIMEZONE_ALIASES:
            return timezone.utc
        return timezone.utc

STORE_IDENTITY_KEYS = [
    "store_id",
    "shop_id",
    "store_name",
    "shop_name",
    "browser_profile",
    "profile_name",
    "account_name",
    "source",
    "data_source",
    "source_file",
    "import_source",
]

BUSINESS_VALUE_KEYS = [
    "revenue",
    "net_revenue",
    "orders",
    "paid_orders",
    "valid_orders",
    "units",
    "ad_spend",
    "refund_amount",
    "buyer_paid_amount",
    "expected_payout",
    "expected_profit",
    "settlement_amount",
    "return_count",
    "refund_count",
    "refund_order_count",
]


def has_virtual_store_marker(*values: Any) -> bool:
    haystack = " ".join(str(value or "") for value in values).lower()
    return any(marker in haystack for marker in VIRTUAL_STORE_MARKERS)


def metric_scope_value_matches(value: str, allowed: list[str]) -> bool:
    if not allowed:
        return True
    lowered = str(value or "").strip().lower()
    if not lowered:
        return False
    return any(item == lowered or item in lowered or lowered in item for item in allowed if item)


def summarize_store_metrics(
    root: Path,
    start: str | None = None,
    end: str | None = None,
    platform: str | None = None,
    store: str | None = None,
    country: str | None = None,
    grain: str | None = None,
    allowed_platforms: Iterable[str] | None = None,
    allowed_stores: Iterable[str] | None = None,
) -> dict[str, Any]:
    start_dt, end_dt = resolve_window(start, end)
    platform_filter = (platform or "all").strip().lower()
    store_filter = (store or "all").strip().lower()
    country_filter = (country or "all").strip().lower()
    platform_scope_enabled = allowed_platforms is not None
    store_scope_enabled = allowed_stores is not None
    platform_allow = [item.strip().lower() for item in allowed_platforms or [] if str(item or "").strip()]
    store_allow = [item.strip().lower() for item in allowed_stores or [] if str(item or "").strip()]
    grain = normalize_grain(grain)
    records = [
        record
        for record in read_records(root, "store_metric_snapshot")
        if is_real_store_metric_record(record)
        and record_in_window(record, start_dt, end_dt)
        and (platform_filter in {"", "all"} or platform_name(record).lower() == platform_filter)
        and (store_filter in {"", "all"} or store_name(record).lower() == store_filter)
        and (country_filter in {"", "all"} or country_keys_match(region_name(record), country_filter))
        and (
            not platform_scope_enabled
            or (
                bool(platform_allow)
                and metric_scope_value_matches(platform_name(record), platform_allow)
            )
        )
        and (
            not store_scope_enabled
            or (
                bool(store_allow)
                and metric_scope_value_matches(store_name(record), store_allow)
            )
        )
    ]

    summary = empty_metric_bucket("All Platforms")
    by_platform: dict[str, dict[str, Any]] = {}
    by_store: dict[str, dict[str, Any]] = {}
    by_product: dict[str, dict[str, Any]] = {}
    by_region: dict[str, dict[str, Any]] = {}
    by_hour: dict[str, dict[str, Any]] = {}
    candle_records: list[tuple[datetime, IntakeRecord, dict[str, float]]] = []
    for record in records:
        fields = record.fields
        platform_label = platform_name(record)
        store_label = store_name(record)
        product_label = product_name(record)
        region_label = region_name(record)
        hour_label = hour_bucket(record)
        values = extract_metric_values(fields)
        candle_records.append((record_metric_datetime(record), record, values))
        add_values(summary, values)
        add_values(by_platform.setdefault(platform_label, empty_metric_bucket(platform_label)), values)
        store_bucket = by_store.setdefault(store_label, empty_metric_bucket(store_label))
        store_bucket["platform"] = platform_label
        add_values(store_bucket, values)
        if product_label:
            product_bucket = by_product.setdefault(product_label, empty_metric_bucket(product_label))
            product_bucket["platform"] = platform_label
            product_bucket["store"] = store_label
            product_bucket["sku"] = str(fields.get("sku") or fields.get("seller_sku") or fields.get("asin") or "").strip()
            add_values(product_bucket, values)
        if region_label:
            region_bucket = by_region.setdefault(region_label, empty_metric_bucket(region_label))
            add_values(region_bucket, values)
        add_values(by_hour.setdefault(hour_label, empty_metric_bucket(hour_label)), values)

    finalize_bucket(summary)
    platform_rows = sorted((finalize_bucket(bucket) for bucket in by_platform.values()), key=lambda item: item["revenue"], reverse=True)
    store_rows = sorted((finalize_bucket(bucket) for bucket in by_store.values()), key=lambda item: item["revenue"], reverse=True)
    product_rows = sorted((finalize_bucket(bucket) for bucket in by_product.values()), key=lambda item: (item["units"], item["revenue"]), reverse=True)[:50]
    region_rows = sorted((finalize_bucket(bucket) for bucket in by_region.values()), key=lambda item: item["revenue"], reverse=True)[:20]
    hourly_trend = sorted((finalize_bucket(bucket) for bucket in by_hour.values()), key=lambda item: item["name"])
    sales_candles = build_sales_candles(candle_records, grain=grain, selected_country=country)
    forecast = forecast_sales_trend(sales_candles)
    latest_records = sorted(records, key=lambda item: item.created_at, reverse=True)[:25]

    return {
        "filters": {
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "platform": platform or "all",
            "store": store or "all",
            "country": country or "all",
            "grain": grain,
        },
        "summary": summary,
        "platforms": platform_rows,
        "stores": store_rows,
        "products": product_rows,
        "regions": region_rows,
        "hourly_trend": hourly_trend,
        "sales_candles": sales_candles,
        "forecast": forecast,
        "records": [compact_record(record) for record in latest_records],
        "available_platforms": available_platforms(root),
        "available_stores": available_stores(root),
        "available_countries": available_countries(root),
    }


def resolve_window(start: str | None, end: str | None) -> tuple[datetime, datetime]:
    today = date.today()
    start_dt = parse_datetime(start) if start else datetime.combine(today, time.min, tzinfo=timezone.utc)
    end_dt = parse_datetime(end, end_of_day=True) if end else datetime.combine(today, time.max, tzinfo=timezone.utc)
    if end_dt < start_dt:
        start_dt, end_dt = end_dt, start_dt
    return start_dt, end_dt


def record_in_window(record: IntakeRecord, start_dt: datetime, end_dt: datetime) -> bool:
    fields = record.fields
    raw_dt = fields.get("snapshot_end") or fields.get("metric_date") or fields.get("snapshot_start") or record.created_at
    metric_dt = parse_datetime(str(raw_dt)) if raw_dt else parse_datetime(record.created_at)
    return start_dt <= metric_dt <= end_dt


def extract_metric_values(fields: dict[str, Any]) -> dict[str, float]:
    revenue = number(fields.get("total_revenue")) or number(fields.get("gmv")) or number(fields.get("sales_amount")) or 0
    orders = number(fields.get("order_count")) or number(fields.get("orders")) or 0
    paid_orders = number(fields.get("paid_order_count")) or number(fields.get("paid_orders")) or number(fields.get("payment_order_count")) or 0
    valid_orders = number(fields.get("valid_order_count")) or number(fields.get("valid_orders")) or number(fields.get("effective_order_count")) or 0
    units = number(fields.get("unit_count")) or number(fields.get("units")) or number(fields.get("units_sold")) or number(fields.get("sales_count")) or 0
    ad_spend = number(fields.get("ad_spend")) or 0
    refund_amount = number(fields.get("refund_amount")) or 0
    paid_sales_amount = number(fields.get("paid_sales_amount")) or number(fields.get("paid_revenue")) or number(fields.get("payment_sales_amount")) or 0
    valid_sales_amount = number(fields.get("valid_sales_amount")) or number(fields.get("effective_sales_amount")) or number(fields.get("net_sales_amount")) or 0
    buyer_paid_amount = number(fields.get("buyer_paid_amount")) or number(fields.get("buyer_actual_paid")) or number(fields.get("buyer_payment_amount")) or 0
    expected_payout = number(fields.get("expected_payout")) or number(fields.get("estimated_payout")) or number(fields.get("estimated_settlement_amount")) or 0
    expected_profit = number(fields.get("expected_profit")) or number(fields.get("estimated_profit")) or number(fields.get("estimated_gross_profit")) or 0
    settlement_amount = number(fields.get("settlement_amount")) or 0
    platform_fee = number(fields.get("platform_fee")) or 0
    commission_fee = number(fields.get("commission_fee")) or 0
    transaction_fee = number(fields.get("transaction_fee")) or 0
    payment_fee = number(fields.get("payment_fee")) or 0
    activity_service_fee = number(fields.get("activity_service_fee")) or 0
    affiliate_creator_fee = number(fields.get("affiliate_creator_fee")) or 0
    shipping_fee = number(fields.get("shipping_fee")) or 0
    warehouse_storage_fee = number(fields.get("warehouse_storage_fee")) or 0
    tax_amount = number(fields.get("tax_amount")) or 0
    tax_withholding = number(fields.get("tax_withholding")) or 0
    refund_return_reserve = number(fields.get("refund_return_reserve")) or 0
    adjustment_amount = number(fields.get("adjustment_amount")) or 0
    reserve_amount = number(fields.get("reserve_amount")) or 0
    return_count = number(fields.get("return_count")) or 0
    refund_count = number(fields.get("refund_count")) or 0
    refund_order_count = number(fields.get("refund_order_count")) or number(fields.get("refunded_order_count")) or number(fields.get("refund_orders")) or 0
    net_revenue = number(fields.get("net_revenue"))
    if net_revenue is None:
        net_revenue = settlement_amount if settlement_amount else revenue - refund_amount
    fee_total = (
        platform_fee
        + commission_fee
        + transaction_fee
        + payment_fee
        + activity_service_fee
        + affiliate_creator_fee
        + shipping_fee
        + warehouse_storage_fee
        + tax_amount
        + tax_withholding
        + refund_return_reserve
        + reserve_amount
    )
    return {
        "revenue": revenue,
        "net_revenue": net_revenue,
        "orders": orders,
        "paid_orders": paid_orders,
        "valid_orders": valid_orders,
        "units": units,
        "ad_spend": ad_spend,
        "refund_amount": refund_amount,
        "paid_sales_amount": paid_sales_amount,
        "valid_sales_amount": valid_sales_amount,
        "buyer_paid_amount": buyer_paid_amount,
        "expected_payout": expected_payout,
        "expected_profit": expected_profit,
        "settlement_amount": settlement_amount,
        "platform_fee": platform_fee,
        "commission_fee": commission_fee,
        "transaction_fee": transaction_fee,
        "payment_fee": payment_fee,
        "activity_service_fee": activity_service_fee,
        "affiliate_creator_fee": affiliate_creator_fee,
        "shipping_fee": shipping_fee,
        "warehouse_storage_fee": warehouse_storage_fee,
        "tax_amount": tax_amount,
        "tax_withholding": tax_withholding,
        "refund_return_reserve": refund_return_reserve,
        "adjustment_amount": adjustment_amount,
        "reserve_amount": reserve_amount,
        "fee_total": fee_total,
        "return_count": return_count,
        "refund_count": refund_count,
        "refund_order_count": refund_order_count,
    }


def is_real_store_metric_record(record: IntakeRecord) -> bool:
    """Only real uploaded/imported business metrics should power seller dashboards."""
    if record.record_type != "store_metric_snapshot":
        return False
    if not dashboard_source_is_admitted(record):
        return False
    fields = record.fields
    labels = [store_name(record), *(str(fields.get(key) or "") for key in STORE_IDENTITY_KEYS)]
    if has_virtual_store_marker(*labels):
        return False
    values = extract_metric_values(fields)
    return any(abs(float(values.get(key, 0) or 0)) > 0 for key in BUSINESS_VALUE_KEYS)


def metric_bucket_has_business_value(bucket: dict[str, Any]) -> bool:
    identity_values = [
        bucket.get("store"),
        bucket.get("store_name"),
        bucket.get("store_id"),
        bucket.get("shop_id"),
        bucket.get("shop_name"),
        bucket.get("browser_profile"),
        bucket.get("profile_name"),
        bucket.get("account_name"),
        bucket.get("source"),
        bucket.get("data_source"),
        bucket.get("source_file"),
        bucket.get("import_source"),
    ]
    # Generic buckets use "name" for store/platform/region/product. Only treat it
    # as a store identity when the bucket is not clearly a product bucket.
    if not any(str(value or "").strip() for value in identity_values) and not any(
        bucket.get(key) for key in ("sku", "product", "product_name")
    ):
        identity_values.append(bucket.get("name"))
    if has_virtual_store_marker(*identity_values):
        return False
    return any(abs(float(bucket.get(key, 0) or 0)) > 0 for key in BUSINESS_VALUE_KEYS)


def real_store_metric_records(root: Path) -> list[IntakeRecord]:
    return [
        record
        for record in read_records(root, "store_metric_snapshot")
        if is_real_store_metric_record(record)
    ]


def empty_metric_bucket(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "platform": "",
        "revenue": 0.0,
        "net_revenue": 0.0,
        "orders": 0.0,
        "paid_orders": 0.0,
        "valid_orders": 0.0,
        "units": 0.0,
        "ad_spend": 0.0,
        "refund_amount": 0.0,
        "paid_sales_amount": 0.0,
        "valid_sales_amount": 0.0,
        "buyer_paid_amount": 0.0,
        "expected_payout": 0.0,
        "expected_profit": 0.0,
        "settlement_amount": 0.0,
        "platform_fee": 0.0,
        "commission_fee": 0.0,
        "transaction_fee": 0.0,
        "payment_fee": 0.0,
        "activity_service_fee": 0.0,
        "affiliate_creator_fee": 0.0,
        "shipping_fee": 0.0,
        "warehouse_storage_fee": 0.0,
        "tax_amount": 0.0,
        "tax_withholding": 0.0,
        "refund_return_reserve": 0.0,
        "adjustment_amount": 0.0,
        "reserve_amount": 0.0,
        "fee_total": 0.0,
        "return_count": 0.0,
        "refund_count": 0.0,
        "refund_order_count": 0.0,
        "roas": None,
        "profit_rate": None,
        "return_rate": 0.0,
        "refund_rate": 0.0,
    }


def add_values(bucket: dict[str, Any], values: dict[str, float]) -> None:
    for key, value in values.items():
        bucket[key] = float(bucket.get(key, 0) or 0) + float(value or 0)


def finalize_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    revenue = float(bucket.get("revenue", 0) or 0)
    orders = float(bucket.get("orders", 0) or 0)
    ad_spend = float(bucket.get("ad_spend", 0) or 0)
    return_count = float(bucket.get("return_count", 0) or 0)
    refund_count = float(bucket.get("refund_count", 0) or 0)
    bucket["roas"] = round(revenue / ad_spend, 4) if ad_spend > 0 else None
    expected_profit = float(bucket.get("expected_profit", 0) or 0)
    payout_base = float(bucket.get("expected_payout", 0) or 0) or float(bucket.get("buyer_paid_amount", 0) or 0) or revenue
    bucket["profit_rate"] = round(expected_profit / payout_base, 4) if payout_base > 0 and expected_profit else None
    bucket["return_rate"] = round(return_count / orders, 4) if orders > 0 else 0.0
    bucket["refund_rate"] = round(refund_count / orders, 4) if orders > 0 else 0.0
    for key in [
        "revenue",
        "net_revenue",
        "ad_spend",
        "refund_amount",
        "paid_sales_amount",
        "valid_sales_amount",
        "buyer_paid_amount",
        "expected_payout",
        "expected_profit",
        "settlement_amount",
        "platform_fee",
        "commission_fee",
        "transaction_fee",
        "payment_fee",
        "activity_service_fee",
        "affiliate_creator_fee",
        "shipping_fee",
        "warehouse_storage_fee",
        "tax_amount",
        "tax_withholding",
        "refund_return_reserve",
        "adjustment_amount",
        "reserve_amount",
        "fee_total",
    ]:
        bucket[key] = round(float(bucket.get(key, 0) or 0), 2)
    for key in ["orders", "paid_orders", "valid_orders", "units", "return_count", "refund_count", "refund_order_count"]:
        bucket[key] = int(round(float(bucket.get(key, 0) or 0)))
    return bucket


def available_platforms(root: Path) -> list[str]:
    platforms = {platform_name(record) for record in real_store_metric_records(root)}
    return sorted(platform for platform in platforms if platform)


def available_stores(root: Path) -> list[str]:
    stores = {store_name(record) for record in real_store_metric_records(root)}
    return sorted(store for store in stores if store and store != "Unassigned Store")


def available_countries(root: Path) -> list[str]:
    countries = {region_name(record) for record in real_store_metric_records(root)}
    return sorted(country for country in countries if country)


def compact_record(record: IntakeRecord) -> dict[str, Any]:
    fields = record.fields
    values = extract_metric_values(fields)
    return {
        "record_id": record.record_id,
        "created_at": record.created_at,
        "platform": platform_name(record),
        "store": store_name(record),
        "product": product_name(record),
        "region": region_name(record),
        "snapshot_start": fields.get("snapshot_start") or fields.get("metric_date") or "",
        "snapshot_end": fields.get("snapshot_end") or fields.get("metric_date") or "",
        **values,
    }


def platform_name(record: IntakeRecord) -> str:
    fields = record.fields
    return str(fields.get("marketplace") or fields.get("source_platform") or fields.get("platform") or "Unknown").strip()


def store_name(record: IntakeRecord) -> str:
    fields = record.fields
    return str(fields.get("store_id") or fields.get("store_name") or fields.get("seller_name") or "Unassigned Store").strip()


def product_name(record: IntakeRecord) -> str:
    fields = record.fields
    return str(
        fields.get("product_name")
        or fields.get("title")
        or fields.get("sku")
        or fields.get("seller_sku")
        or fields.get("asin")
        or ""
    ).strip()


def region_name(record: IntakeRecord) -> str:
    fields = record.fields
    return str(
        fields.get("country")
        or fields.get("region")
        or fields.get("buyer_country")
        or fields.get("ship_to_country")
        or fields.get("market")
        or ""
    ).strip()


def hour_bucket(record: IntakeRecord) -> str:
    metric_dt = record_metric_datetime(record)
    return metric_dt.strftime("%Y-%m-%d %H:00")


def record_metric_datetime(record: IntakeRecord) -> datetime:
    fields = record.fields
    raw_dt = fields.get("snapshot_end") or fields.get("metric_date") or fields.get("snapshot_start") or record.created_at
    return parse_datetime(str(raw_dt)) if raw_dt else parse_datetime(record.created_at)


def normalize_grain(value: str | None) -> str:
    clean = (value or "day").strip().lower()
    if clean in {"hour", "hourly", "h"}:
        return "hour"
    return "day"


def build_sales_candles(
    candle_records: list[tuple[datetime, IntakeRecord, dict[str, float]]],
    grain: str = "day",
    selected_country: str | None = None,
) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for metric_dt, record, values in sorted(candle_records, key=lambda item: item[0]):
        tz_name = timezone_for_record(record, selected_country)
        local_dt = metric_dt.astimezone(safe_zoneinfo(tz_name))
        label = local_dt.strftime("%Y-%m-%d %H:00") if grain == "hour" else local_dt.strftime("%Y-%m-%d")
        revenue = float(values.get("revenue", 0) or 0)
        bucket = buckets.setdefault(
            label,
            {
                "label": label,
                "timezone": tz_name,
                "open": revenue,
                "high": revenue,
                "low": revenue,
                "close": revenue,
                "revenue": 0.0,
                "orders": 0.0,
                "units": 0.0,
                "ad_spend": 0.0,
                "refund_amount": 0.0,
                "record_count": 0,
            },
        )
        bucket["high"] = max(float(bucket["high"]), revenue)
        bucket["low"] = min(float(bucket["low"]), revenue)
        bucket["close"] = revenue
        bucket["revenue"] = float(bucket["revenue"]) + revenue
        bucket["orders"] = float(bucket["orders"]) + float(values.get("orders", 0) or 0)
        bucket["units"] = float(bucket["units"]) + float(values.get("units", 0) or 0)
        bucket["ad_spend"] = float(bucket["ad_spend"]) + float(values.get("ad_spend", 0) or 0)
        bucket["refund_amount"] = float(bucket["refund_amount"]) + float(values.get("refund_amount", 0) or 0)
        bucket["record_count"] = int(bucket["record_count"]) + 1
    candles = []
    for bucket in buckets.values():
        bucket["open"] = round(float(bucket["open"]), 2)
        bucket["high"] = round(float(bucket["high"]), 2)
        bucket["low"] = round(float(bucket["low"]), 2)
        bucket["close"] = round(float(bucket["close"]), 2)
        bucket["revenue"] = round(float(bucket["revenue"]), 2)
        bucket["orders"] = int(round(float(bucket["orders"])))
        bucket["units"] = int(round(float(bucket["units"])))
        bucket["ad_spend"] = round(float(bucket["ad_spend"]), 2)
        bucket["refund_amount"] = round(float(bucket["refund_amount"]), 2)
        candles.append(bucket)
    return sorted(candles, key=lambda item: item["label"])[-60:]


def forecast_sales_trend(candles: list[dict[str, Any]]) -> dict[str, Any]:
    if not candles:
        return {
            "direction": "insufficient_data",
            "next_revenue": 0.0,
            "next_orders": 0,
            "confidence": "low",
            "reason": "后台 AI 暂未读到足够销售数据；等订单、广告、退款或财务报表接入后会自动预测。",
        }
    recent = candles[-5:]
    revenues = [float(item.get("revenue", 0) or 0) for item in recent]
    orders = [float(item.get("orders", 0) or 0) for item in recent]
    baseline = sum(revenues) / len(revenues)
    if baseline <= 0 and not any(orders):
        return {
            "direction": "insufficient_data",
            "next_revenue": 0.0,
            "next_orders": 0,
            "confidence": "low",
            "reason": "后台 AI 暂未读到真实销售或订单数据；店铺报表接入后会自动预测。",
        }
    slope = revenues[-1] - revenues[0] if len(revenues) > 1 else 0.0
    next_revenue = max(0.0, baseline + slope / max(len(revenues) - 1, 1))
    next_orders = max(
        0,
        round(
            (sum(orders) / len(orders))
            + ((orders[-1] - orders[0]) / max(len(orders) - 1, 1) if len(orders) > 1 else 0)
        ),
    )
    if baseline <= 0:
        direction = "flat"
    elif slope / baseline >= 0.12:
        direction = "up"
    elif slope / baseline <= -0.12:
        direction = "down"
    else:
        direction = "flat"
    confidence = "medium" if len(candles) >= 5 else "low"
    reason_map = {
        "up": "最近销售曲线抬头，可以重点检查热销商品、库存和广告预算。",
        "down": "最近销售走弱，需要检查断货、价格、广告消耗、差评和平台流量变化。",
        "flat": "走势暂时平稳，适合观察单品和店铺之间的结构变化。",
    }
    return {
        "direction": direction,
        "next_revenue": round(next_revenue, 2),
        "next_orders": int(next_orders),
        "confidence": confidence,
        "reason": reason_map.get(direction, reason_map["flat"]),
    }


def timezone_for_record(record: IntakeRecord, selected_country: str | None = None) -> str:
    fields = record.fields
    explicit = str(fields.get("timezone") or fields.get("time_zone") or "").strip()
    if explicit:
        return explicit
    region = normalize_country_key(str(selected_country or region_name(record) or ""))
    marketplace = platform_name(record).lower()
    if region == "us" or "us" in marketplace:
        return "America/Los_Angeles"
    if region == "ca":
        return "America/Toronto"
    if region == "mx":
        return "America/Mexico_City"
    if region == "uk":
        return "Europe/London"
    if region == "de":
        return "Europe/Berlin"
    if region == "fr":
        return "Europe/Paris"
    if region == "jp":
        return "Asia/Tokyo"
    if region == "au":
        return "Australia/Sydney"
    if region in {"sg", "sea"}:
        return "Asia/Singapore"
    if region == "br":
        return "America/Sao_Paulo"
    return "UTC"


def country_keys_match(record_country: str, selected_country: str) -> bool:
    return normalize_country_key(record_country) == normalize_country_key(selected_country)


def normalize_country_key(value: str) -> str:
    lowered = str(value or "").strip().lower()
    aliases = {
        "united states": "us",
        "usa": "us",
        "美国": "us",
        "united kingdom": "uk",
        "great britain": "uk",
        "gb": "uk",
        "英国": "uk",
        "germany": "de",
        "德国": "de",
        "france": "fr",
        "法国": "fr",
        "japan": "jp",
        "日本": "jp",
        "korea": "kr",
        "south korea": "kr",
        "韩国": "kr",
        "australia": "au",
        "澳大利亚": "au",
        "brazil": "br",
        "巴西": "br",
        "canada": "ca",
        "加拿大": "ca",
        "mexico": "mx",
        "墨西哥": "mx",
        "southeast asia": "sea",
        "东南亚": "sea",
        "singapore": "sg",
        "新加坡": "sg",
    }
    return aliases.get(lowered, lowered)


def parse_datetime(value: str | None, end_of_day: bool = False) -> datetime:
    if not value:
        return datetime.combine(date.today(), time.max if end_of_day else time.min, tzinfo=timezone.utc)
    clean = str(value).strip().replace("Z", "+00:00")
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", clean):
            parsed_date = date.fromisoformat(clean)
            return datetime.combine(parsed_date, time.max if end_of_day else time.min, tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(clean)
    except ValueError:
        return datetime.combine(date.today(), time.max if end_of_day else time.min, tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    clean = str(value).strip()
    if not clean:
        return None
    multiplier = 1.0
    lowered = clean.lower()
    if lowered.endswith("k"):
        multiplier = 1_000.0
        clean = clean[:-1]
    elif lowered.endswith("m"):
        multiplier = 1_000_000.0
        clean = clean[:-1]
    clean = re.sub(r"[^0-9.\-]", "", clean)
    if clean in {"", "-", ".", "-."}:
        return None
    try:
        return float(clean) * multiplier
    except ValueError:
        return None
