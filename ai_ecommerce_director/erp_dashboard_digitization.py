from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REGISTRY_RELATIVE_PATH = Path("config") / "erp_dashboard_benchmark_registry.json"


REQUIRED_PERFORMANCE_KEYS = {
    "orders",
    "paid_orders",
    "valid_orders",
    "refund_order_count",
    "revenue",
    "paid_sales_amount",
    "valid_sales_amount",
    "buyer_paid_amount",
    "refund_amount",
    "expected_payout",
    "expected_profit",
    "profit_rate",
}

REQUIRED_SIDEBAR_GROUPS = {
    "今日实时",
    "利润分析",
    "运营分析",
    "TikTok 洞察",
    "财务结算",
    "店铺健康",
    "仓库分析",
}

REQUIRED_RANKING_BLOCKS = {
    "排行榜Top10",
    "热销产品Top50",
}

REQUIRED_OPERATION_PAGES = {
    "product_activity_analysis",
}

REQUIRED_PRODUCT_ACTIVITY_KEYS = {
    "product_count",
    "active_product_count",
    "active_product_ratio",
    "sold_product_count",
    "product_activity_rate",
    "new_active_product_count",
    "new_active_product_ratio",
}

REQUIRED_REALTIME_BIG_SCREEN_LAYOUTS = {
    "realtime_data_big_screen",
}

REQUIRED_REALTIME_BIG_SCREEN_PANELS = {
    "hot_store_top10",
    "hot_product_top10",
    "world_order_map",
    "realtime_order_stream",
    "gmv_trend",
    "order_count_trend",
    "self_operated_platform_trend",
}

REQUIRED_REALTIME_BIG_SCREEN_CONTROLS = {
    "timezone",
    "currency",
    "order_scope",
    "filters",
    "fullscreen_preview",
}


def load_erp_dashboard_benchmark_registry(root: Path, *, strict: bool = False) -> dict[str, Any]:
    """Load the local ERP benchmark registry.

    This registry is only a benchmark/gap map learned from user-provided screenshots.
    It must not be treated as a live ERP connection or proof that any account/store
    backend has been read.
    """

    path = root / REGISTRY_RELATIVE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        if strict:
            raise
        return {}
    return payload if isinstance(payload, dict) else {}


def erp_dashboard_benchmark_snapshot(root: Path) -> dict[str, Any]:
    registry = load_erp_dashboard_benchmark_registry(root)
    metrics = [
        item
        for item in registry.get("performance_metrics", [])
        if isinstance(item, dict)
    ]
    sidebar_groups = [
        item
        for item in registry.get("sidebar_modules", [])
        if isinstance(item, dict)
    ]
    ranking_blocks = [
        item
        for item in registry.get("ranking_blocks", [])
        if isinstance(item, dict)
    ]
    operation_pages = [
        item
        for item in registry.get("operation_analysis_pages", [])
        if isinstance(item, dict)
    ]
    realtime_layouts = [
        item
        for item in registry.get("realtime_big_screen_layouts", [])
        if isinstance(item, dict)
    ]
    product_activity_page = next(
        (item for item in operation_pages if item.get("key") == "product_activity_analysis"),
        {},
    )
    realtime_big_screen = next(
        (item for item in realtime_layouts if item.get("key") == "realtime_data_big_screen"),
        {},
    )
    product_activity_fields = [
        item
        for item in product_activity_page.get("metric_fields", [])
        if isinstance(item, dict)
    ] if isinstance(product_activity_page, dict) else []
    realtime_panels = [
        item
        for item in realtime_big_screen.get("panels", [])
        if isinstance(item, dict)
    ] if isinstance(realtime_big_screen, dict) else []
    truth_policy = registry.get("truth_policy") if isinstance(registry.get("truth_policy"), dict) else {}
    return {
        "schema_version": registry.get("schema_version") or "",
        "registry_kind": registry.get("registry_kind") or "",
        "benchmark_only": bool(truth_policy.get("benchmark_only")),
        "no_backend_access_claimed": bool(truth_policy.get("no_backend_access_claimed")),
        "no_scraping": bool(truth_policy.get("no_scraping")),
        "no_account_or_store_action": bool(truth_policy.get("no_account_or_store_action")),
        "performance_metric_keys": [str(item.get("key") or "") for item in metrics if item.get("key")],
        "sidebar_groups": [str(item.get("group") or "") for item in sidebar_groups if item.get("group")],
        "ranking_blocks": [str(item.get("name") or "") for item in ranking_blocks if item.get("name")],
        "operation_pages": [str(item.get("key") or "") for item in operation_pages if item.get("key")],
        "product_activity_metric_keys": [str(item.get("key") or "") for item in product_activity_fields if item.get("key")],
        "product_activity_record_types": list(product_activity_page.get("record_types") or []) if isinstance(product_activity_page, dict) else [],
        "realtime_big_screen_layouts": [str(item.get("key") or "") for item in realtime_layouts if item.get("key")],
        "realtime_big_screen_panels": [str(item.get("key") or "") for item in realtime_panels if item.get("key")],
        "realtime_big_screen_controls": list(realtime_big_screen.get("global_controls") or []) if isinstance(realtime_big_screen, dict) else [],
        "gap_count": sum(len(item.get("missing") or []) for item in sidebar_groups + ranking_blocks),
    }


def validate_erp_dashboard_benchmark_registry(root: Path) -> list[str]:
    snapshot = erp_dashboard_benchmark_snapshot(root)
    errors: list[str] = []
    if snapshot["registry_kind"] != "erp_dashboard_benchmark_registry":
        errors.append("registry_kind must be erp_dashboard_benchmark_registry")
    for key in ("benchmark_only", "no_backend_access_claimed", "no_scraping", "no_account_or_store_action"):
        if not snapshot.get(key):
            errors.append(f"truth_policy.{key} must be true")
    missing_metrics = REQUIRED_PERFORMANCE_KEYS.difference(snapshot["performance_metric_keys"])
    if missing_metrics:
        errors.append("missing performance metrics: " + ", ".join(sorted(missing_metrics)))
    missing_groups = REQUIRED_SIDEBAR_GROUPS.difference(snapshot["sidebar_groups"])
    if missing_groups:
        errors.append("missing sidebar groups: " + ", ".join(sorted(missing_groups)))
    missing_blocks = REQUIRED_RANKING_BLOCKS.difference(snapshot["ranking_blocks"])
    if missing_blocks:
        errors.append("missing ranking blocks: " + ", ".join(sorted(missing_blocks)))
    missing_pages = REQUIRED_OPERATION_PAGES.difference(snapshot["operation_pages"])
    if missing_pages:
        errors.append("missing operation pages: " + ", ".join(sorted(missing_pages)))
    missing_product_activity = REQUIRED_PRODUCT_ACTIVITY_KEYS.difference(snapshot["product_activity_metric_keys"])
    if missing_product_activity:
        errors.append("missing product activity metrics: " + ", ".join(sorted(missing_product_activity)))
    if "product_activity_snapshot" not in snapshot["product_activity_record_types"]:
        errors.append("product_activity_snapshot must be a product activity record type")
    missing_realtime_layouts = REQUIRED_REALTIME_BIG_SCREEN_LAYOUTS.difference(snapshot["realtime_big_screen_layouts"])
    if missing_realtime_layouts:
        errors.append("missing realtime big screen layouts: " + ", ".join(sorted(missing_realtime_layouts)))
    missing_realtime_panels = REQUIRED_REALTIME_BIG_SCREEN_PANELS.difference(snapshot["realtime_big_screen_panels"])
    if missing_realtime_panels:
        errors.append("missing realtime big screen panels: " + ", ".join(sorted(missing_realtime_panels)))
    missing_realtime_controls = REQUIRED_REALTIME_BIG_SCREEN_CONTROLS.difference(snapshot["realtime_big_screen_controls"])
    if missing_realtime_controls:
        errors.append("missing realtime big screen controls: " + ", ".join(sorted(missing_realtime_controls)))
    return errors
