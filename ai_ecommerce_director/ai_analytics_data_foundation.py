from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .business_action_metrics import validate_business_action_metric_dictionary

REGISTRY_PATH = Path("config") / "ai_analytics_data_foundation_registry.json"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_ai_analytics_data_foundation_registry(root: Path, *, strict: bool = False) -> dict[str, Any]:
    path = root / REGISTRY_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        if strict:
            raise
        return {}
    return payload if isinstance(payload, dict) else {}


def _metric_family_entries(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _safe_list(registry.get("metric_families")) if isinstance(item, dict)]


_TIME_DIMENSIONS = {"timestamp", "date", "event_time", "hour", "day", "week", "month", "quarter", "year", "custom_range"}


def _metric_unit(metric_id: str) -> str:
    """Return a conservative unit without inventing a platform-specific scale."""

    metric = str(metric_id or "").casefold()
    if any(token in metric for token in ("_rate", "_ratio", "margin", "ctr", "cvr", "acos", "roas", "coverage")):
        return "ratio"
    if metric.endswith("_minutes") or "time_minutes" in metric:
        return "minutes"
    if metric.endswith("_hours"):
        return "hours"
    if metric.endswith("_seconds") or "latency_seconds" in metric:
        return "seconds"
    if metric.endswith("_days") or metric in {"days_of_cover", "storage_age_days", "delivery_days"}:
        return "days"
    if metric.endswith("_rank"):
        return "ordinal_rank"
    if any(
        token in metric
        for token in (
            "revenue",
            "amount",
            "cost",
            "spend",
            "sales",
            "gmv",
            "commission",
            "fee",
            "payout",
            "profit",
            "price_band",
            "budget",
            "cash_lockup",
            "impact_value",
            "target_change",
        )
    ) and metric not in {"sales_velocity", "estimated_monthly_sales"}:
        return "currency_with_currency_dimension"
    if any(token in metric for token in ("score", "confidence", "rating_average", "forecast_bias")):
        return "documented_score_scale"
    if any(token in metric for token in ("stock", "inventory", "capacity", "units", "moq", "reorder_point")):
        return "units"
    if metric in {
        "traffic",
        "sessions",
        "visits",
        "impressions",
        "clicks",
        "likes",
        "comments",
        "saves",
        "shares",
        "followers",
        "inquiries",
        "replies",
        "bounces",
        "meetings",
        "orders",
        "paid_orders",
        "valid_orders",
        "search_volume",
        "estimated_monthly_sales",
        "sales_velocity",
    } or metric.endswith(("_count", "_views", "_clicks", "_orders")):
        return "count"
    return "platform_native_or_derived_value"


def _metric_aggregation_rule(metric_id: str, unit: str) -> str:
    metric = str(metric_id or "").casefold()
    if metric.startswith("forecast_"):
        return "evaluate_per_forecast_horizon_do_not_sum"
    if unit in {"ratio", "documented_score_scale", "ordinal_rank"} or metric in {"cpc", "cpm"}:
        return "recompute_from_source_components_do_not_sum"
    if any(token in metric for token in ("stock", "inventory_remaining", "followers", "reorder_point", "days_of_cover")):
        return "last_non_null_within_window"
    if unit == "platform_native_or_derived_value":
        return "metric_specific_with_lineage_no_implicit_sum"
    return "sum_within_identical_currency_scope_and_dimensions"


def build_metric_dictionary(registry: dict[str, Any]) -> list[dict[str, Any]]:
    """Build one metadata row per registered metric from canonical fact lineage.

    Metrics that are not a fact table's primary measure inherit the matching
    family's canonical fact sources and are explicitly marked derived. This
    keeps every metric queryable without pretending a derived value was read
    directly from a platform.
    """

    fact_tables = [item for item in _safe_list(registry.get("fact_tables")) if isinstance(item, dict)]
    time_grains = {str(item) for item in _safe_list(registry.get("time_grains"))}
    rows: list[dict[str, Any]] = []
    row_by_metric: dict[str, dict[str, Any]] = {}
    for family in _metric_family_entries(registry):
        family_id = str(family.get("id") or "").strip()
        family_metrics = [str(item) for item in _safe_list(family.get("metrics")) if str(item).strip()]
        family_metric_set = set(family_metrics)
        family_sources = [
            table
            for table in fact_tables
            if family_metric_set.intersection(str(item) for item in _safe_list(table.get("primary_metrics")))
        ]
        for metric_id in family_metrics:
            direct_sources = [
                table
                for table in fact_tables
                if metric_id in {str(item) for item in _safe_list(table.get("primary_metrics"))}
            ]
            sources = direct_sources or family_sources
            grains = [str(item) for table in sources for item in _safe_list(table.get("grain")) if str(item).strip()]
            default_grain = next((item for item in grains if item in time_grains), "event_time")
            default_dimensions = list(
                dict.fromkeys(item for item in grains if item not in _TIME_DIMENSIONS and item != default_grain)
            )
            unit = _metric_unit(metric_id)
            row = {
                    "metric_id": metric_id,
                    "family_id": family_id,
                    "family_ids": [family_id],
                    "unit": unit,
                    "default_grain": default_grain,
                    "default_dimensions": default_dimensions,
                    "source_record_types": [str(table.get("id")) for table in sources if str(table.get("id") or "").strip()],
                    "truth_level": (
                        "canonical_with_lineage"
                        if direct_sources
                        else "derived_with_formula_and_lineage"
                    ),
                    "nullable_reason": "missing_authorized_source_not_applicable_or_not_yet_mapped",
                    "owner_gate": False,
                    "aggregation_rule": _metric_aggregation_rule(metric_id, unit),
                    "source_mapping": "direct_primary_metric" if direct_sources else "family_derived_metric",
                }
            existing = row_by_metric.get(metric_id)
            if existing is None:
                row_by_metric[metric_id] = row
                rows.append(row)
                continue
            existing["family_ids"] = list(
                dict.fromkeys([*_safe_list(existing.get("family_ids")), family_id])
            )
            existing["source_record_types"] = list(
                dict.fromkeys(
                    [*_safe_list(existing.get("source_record_types")), *_safe_list(row.get("source_record_types"))]
                )
            )
            existing["default_dimensions"] = list(
                dict.fromkeys(
                    [*_safe_list(existing.get("default_dimensions")), *_safe_list(row.get("default_dimensions"))]
                )
            )
            if direct_sources:
                existing["truth_level"] = "canonical_with_lineage"
                existing["source_mapping"] = "direct_primary_metric"
    return rows


def ai_analytics_data_foundation_snapshot(root: Path) -> dict[str, Any]:
    registry = load_ai_analytics_data_foundation_registry(root)
    families = _metric_family_entries(registry)
    metric_ids: set[str] = set()
    for family in families:
        metric_ids.update(str(item) for item in _safe_list(family.get("metrics")) if str(item).strip())
    fact_tables = [item for item in _safe_list(registry.get("fact_tables")) if isinstance(item, dict)]
    product_testing_contract = (
        registry.get("product_selection_testing_contract")
        if isinstance(registry.get("product_selection_testing_contract"), dict)
        else {}
    )
    product_testing_fact_tables = [
        item
        for item in fact_tables
        if str(item.get("id") or "").startswith(("product_selection_", "product_test_"))
    ]
    product_testing_metric_ids: set[str] = set()
    for family in families:
        if str(family.get("id") or "") in {"product_selection_research", "product_testing"}:
            product_testing_metric_ids.update(
                str(item) for item in _safe_list(family.get("metrics")) if str(item).strip()
            )
    operating_contract = (
        registry.get("operating_intelligence_contract")
        if isinstance(registry.get("operating_intelligence_contract"), dict)
        else {}
    )
    operating_fact_table_ids = {
        "business_action_event_fact",
        "plan_target_fact",
        "forecast_fact",
        "recommendation_fact",
        "plan_adjustment_fact",
        "action_outcome_attribution_fact",
    }
    operating_fact_tables = [item for item in fact_tables if str(item.get("id") or "") in operating_fact_table_ids]
    operating_metric_ids: set[str] = set()
    for family in families:
        if str(family.get("id") or "") in {
            "business_action_events",
            "planning_targets_variance",
            "forecast_quality",
            "recommendation_plan_adjustment",
        }:
            operating_metric_ids.update(
                str(item) for item in _safe_list(family.get("metrics")) if str(item).strip()
            )
    truth_policy = registry.get("truth_policy") if isinstance(registry.get("truth_policy"), dict) else {}
    action_dictionary = (
        registry.get("business_action_metric_dictionary")
        if isinstance(registry.get("business_action_metric_dictionary"), dict)
        else {}
    )
    action_contracts = [
        item
        for item in _safe_list(action_dictionary.get("contracts"))
        if isinstance(item, dict)
    ]
    mapped_action_types = {
        str(event_type)
        for item in action_contracts
        for event_type in _safe_list(item.get("event_types"))
        if str(event_type).strip()
    }
    metric_dictionary = build_metric_dictionary(registry)
    required_metric_metadata = [
        str(item) for item in _safe_list(registry.get("required_metric_metadata")) if str(item).strip()
    ]
    complete_metric_metadata = [
        item
        for item in metric_dictionary
        if all(field in item and item.get(field) is not None for field in required_metric_metadata)
    ]
    metric_metadata_ids = {str(item.get("metric_id") or "") for item in metric_dictionary}
    return {
        "schema_version": registry.get("schema_version"),
        "registry_path": str(REGISTRY_PATH).replace("\\", "/"),
        "analysis_layer_count": len(_safe_list(registry.get("analysis_layers"))),
        "time_grain_count": len(_safe_list(registry.get("time_grains"))),
        "dimension_count": len(_safe_list(registry.get("core_dimensions"))),
        "dimension_ids": [str(item) for item in _safe_list(registry.get("core_dimensions"))],
        "fact_table_count": len(fact_tables),
        "metric_family_count": len(families),
        "metric_count": len(metric_ids),
        "metric_ids": sorted(metric_ids),
        "metric_dictionary": metric_dictionary,
        "metric_metadata_count": len(metric_dictionary),
        "complete_metric_metadata_count": len(complete_metric_metadata),
        "metric_metadata_with_source_count": sum(bool(item.get("source_record_types")) for item in metric_dictionary),
        "missing_metric_metadata_ids": sorted(metric_ids.difference(metric_metadata_ids)),
        "product_testing_stage_count": len(_safe_list(product_testing_contract.get("lifecycle_stages"))),
        "product_testing_route_count": len(_safe_list(product_testing_contract.get("test_routes"))),
        "product_testing_decision_count": len(_safe_list(product_testing_contract.get("decision_statuses"))),
        "product_testing_fact_table_count": len(product_testing_fact_tables),
        "product_testing_metric_count": len(product_testing_metric_ids),
        "product_testing_metric_ids": sorted(product_testing_metric_ids),
        "product_selection_testing_contract": product_testing_contract,
        "operating_hierarchy_count": len(_safe_list(operating_contract.get("hierarchy"))),
        "operating_action_field_count": len(_safe_list(operating_contract.get("every_action_event_requires"))),
        "operating_fact_table_count": len(operating_fact_tables),
        "operating_metric_count": len(operating_metric_ids),
        "operating_metric_ids": sorted(operating_metric_ids),
        "operating_intelligence_contract": operating_contract,
        "business_action_contract_count": len(action_contracts),
        "mapped_business_action_type_count": len(mapped_action_types),
        "truth_policy": truth_policy,
        "dashboard_policy": registry.get("dashboard_policy") if isinstance(registry.get("dashboard_policy"), dict) else {},
        "ai_analysis_contract": registry.get("ai_analysis_contract") if isinstance(registry.get("ai_analysis_contract"), dict) else {},
        "source_freshness_contract": registry.get("source_freshness_contract") if isinstance(registry.get("source_freshness_contract"), dict) else {},
        "commerce_scope_contract": registry.get("commerce_scope_contract") if isinstance(registry.get("commerce_scope_contract"), dict) else {},
        "platform_adaptation_contract": registry.get("platform_adaptation_contract") if isinstance(registry.get("platform_adaptation_contract"), dict) else {},
    }


def validate_ai_analytics_data_foundation_registry(root: Path) -> list[str]:
    errors: list[str] = []
    registry = load_ai_analytics_data_foundation_registry(root, strict=True)
    truth = registry.get("truth_policy") if isinstance(registry.get("truth_policy"), dict) else {}
    if not truth.get("no_fake_data"):
        errors.append("truth_policy.no_fake_data must be true")
    if not truth.get("raw_record_preservation_required"):
        errors.append("truth_policy.raw_record_preservation_required must be true")
    if not truth.get("canonical_metric_lineage_required"):
        errors.append("truth_policy.canonical_metric_lineage_required must be true")
    if truth.get("external_actions") != 0:
        errors.append("truth_policy.external_actions must be 0")
    if not truth.get("ai_analysis_must_include_source_window_and_confidence"):
        errors.append("truth_policy.ai_analysis_must_include_source_window_and_confidence must be true")

    snapshot = ai_analytics_data_foundation_snapshot(root)
    if snapshot["analysis_layer_count"] < 5:
        errors.append("analysis_layers must include raw, canonical, feature, ai analysis, and receipt layers")
    if snapshot["time_grain_count"] < 7:
        errors.append("time_grains must include hour/day/week/month/quarter/year/custom range")
    if snapshot["dimension_count"] < 45:
        errors.append("core_dimensions must include broad platform, product, customer, content, finance, and AI axes")
    if snapshot["fact_table_count"] < 15:
        errors.append("fact_tables must cover at least 15 operational fact tables")
    if snapshot["metric_family_count"] < 16:
        errors.append("metric_families must cover at least 16 data families")
    if snapshot["metric_count"] < 130:
        errors.append("metric catalog must include at least 130 distinct metrics")
    if snapshot["product_testing_stage_count"] < 10:
        errors.append("product testing lifecycle must cover candidate intake through post-decision review")
    if snapshot["product_testing_fact_table_count"] < 6:
        errors.append("product testing must include selection, plan, exposure, conversion, cash, and decision facts")
    if snapshot["product_testing_metric_count"] < 70:
        errors.append("product selection and testing must include at least 70 distinct metrics")
    if snapshot["operating_hierarchy_count"] < 6:
        errors.append("operating hierarchy must cover action, store, platform/site, product/country, business group, and group direction")
    if snapshot["operating_action_field_count"] < 20:
        errors.append("every action event must preserve identity, scope, state, approval, evidence, receipt, and trace fields")
    if snapshot["operating_fact_table_count"] < 6:
        errors.append("operating intelligence must include action, plan, forecast, recommendation, adjustment, and outcome facts")
    if snapshot["operating_metric_count"] < 70:
        errors.append("operating intelligence must include action, plan, forecast quality, recommendation, and outcome metrics")

    required_metrics = {
        "revenue",
        "orders",
        "paid_orders",
        "valid_orders",
        "refund_order_count",
        "ad_spend",
        "roas",
        "traffic",
        "homepage_views",
        "video_views",
        "social_engagement_count",
        "live_duration_minutes",
        "live_gmv",
        "creator_commission",
        "parent_sku_count",
        "child_sku_count_reference",
        "stock_units",
        "purchase_cost",
        "shipping_cost",
        "inquiries",
        "emails_sent",
        "bounces",
        "store_count",
        "account_count",
        "connector_available",
        "prohibited_count",
        "evidence_count",
        "candidate_score",
        "blue_ocean_score",
        "test_budget",
        "test_orders",
        "sales_velocity",
        "test_return_rate",
        "test_cash_lockup",
        "test_replenishment_cap",
        "decision_confidence",
        "decision_exit_count",
        "action_event_count",
        "action_failure_count",
        "receipt_coverage_rate",
        "plan_variance_rate",
        "plan_completion_rate",
        "forecast_p50",
        "forecast_mape",
        "forecast_drift_score",
        "recommendation_confidence",
        "plan_adjustment_count",
        "observed_profit_impact",
        "attribution_confidence",
    }
    missing = sorted(required_metrics.difference(snapshot["metric_ids"]))
    if missing:
        errors.append("required metrics missing: " + ", ".join(missing))

    grains = set(str(item) for item in _safe_list(registry.get("time_grains")))
    for required_grain in {"hour", "day", "week", "month", "quarter", "year", "custom_range"}:
        if required_grain not in grains:
            errors.append(f"time_grains missing {required_grain}")

    dimensions = set(str(item) for item in _safe_list(registry.get("core_dimensions")))
    for required_dimension in {"platform", "country_site", "store_mode", "ownership", "fulfillment_mode", "warehouse_country", "ship_from_country", "store_id", "parent_sku", "content_id", "live_session_id", "creator_id", "campaign_id", "customer_id", "task_run_id", "product_candidate_id", "product_test_id", "test_variant_id", "decision_status", "action_event_id", "action_scope", "plan_id", "forecast_id", "forecast_horizon", "recommendation_id", "receipt_id", "trace_id", "truth_level"}:
        if required_dimension not in dimensions:
            errors.append(f"core_dimensions missing {required_dimension}")

    fact_table_ids = {str(item.get("id")) for item in _safe_list(registry.get("fact_tables")) if isinstance(item, dict)}
    for required_table in {"live_session_fact", "creator_affiliate_fact", "ad_campaign_fact", "settlement_fee_fact", "product_selection_signal_fact", "product_test_plan_fact", "product_test_exposure_fact", "product_test_conversion_fact", "product_test_inventory_cash_fact", "product_test_decision_fact", "business_action_event_fact", "plan_target_fact", "forecast_fact", "recommendation_fact", "plan_adjustment_fact", "action_outcome_attribution_fact", "ai_task_execution_fact"}:
        if required_table not in fact_table_ids:
            errors.append(f"fact_tables missing {required_table}")

    contract = registry.get("ai_analysis_contract") if isinstance(registry.get("ai_analysis_contract"), dict) else {}
    references = set(str(item) for item in _safe_list(contract.get("every_answer_must_reference")))
    for required_ref in {"time_window", "source_record_count", "truth_level", "confidence", "missing_fields"}:
        if required_ref not in references:
            errors.append(f"ai_analysis_contract.every_answer_must_reference missing {required_ref}")
    blocked = set(str(item) for item in _safe_list(contract.get("blocked_outputs_without_approval")))
    for required_block in {"publish", "send_message", "launch_ad", "spend_budget", "place_order", "refund", "ship", "oauth_connect"}:
        if required_block not in blocked:
            errors.append(f"ai_analysis_contract.blocked_outputs_without_approval missing {required_block}")

    testing_contract = snapshot["product_selection_testing_contract"]
    required_plan_fields = set(str(item) for item in _safe_list(testing_contract.get("required_test_plan_fields")))
    for required_field in {"product_candidate_id", "product_test_id", "hypothesis", "budget_ceiling", "stock_ceiling", "pass_thresholds", "fail_thresholds", "stop_loss_rules", "owner_gate_status"}:
        if required_field not in required_plan_fields:
            errors.append(f"product_selection_testing_contract.required_test_plan_fields missing {required_field}")
    threshold_policy = testing_contract.get("threshold_policy") if isinstance(testing_contract.get("threshold_policy"), dict) else {}
    for required_true in {"platform_and_category_specific", "sample_thresholds_are_not_platform_facts", "missing_threshold_is_unknown", "scale_requires_owner_approval", "purchase_or_replenishment_requires_owner_approval"}:
        if not threshold_policy.get(required_true):
            errors.append(f"product_selection_testing_contract.threshold_policy.{required_true} must be true")
    if testing_contract.get("external_actions") != 0:
        errors.append("product_selection_testing_contract.external_actions must be 0")

    operating_contract = snapshot["operating_intelligence_contract"]
    action_fields = set(str(item) for item in _safe_list(operating_contract.get("every_action_event_requires")))
    for required_field in {"action_event_id", "occurred_at", "actor_id", "action_type", "action_scope", "target_object_id", "before_state_hash", "permission_state", "approval_state", "execution_state", "external_side_effect", "after_state_hash", "evidence_refs", "receipt_id", "trace_id"}:
        if required_field not in action_fields:
            errors.append(f"operating_intelligence_contract.every_action_event_requires missing {required_field}")
    forecast_policy = operating_contract.get("forecast_policy") if isinstance(operating_contract.get("forecast_policy"), dict) else {}
    for required_true in {"precision_is_measured_not_claimed", "point_forecast_requires_interval", "actual_result_required_for_accuracy_score", "forecast_without_source_lineage_is_blocked", "low_sample_or_high_drift_must_reduce_confidence", "forecast_cannot_execute_action"}:
        if not forecast_policy.get(required_true):
            errors.append(f"operating_intelligence_contract.forecast_policy.{required_true} must be true")
    direction_policy = operating_contract.get("dashboard_direction_policy") if isinstance(operating_contract.get("dashboard_direction_policy"), dict) else {}
    for required_true in {"store_view_is_micro_direction", "platform_site_view_is_rollup", "group_dashboard_is_macro_direction", "macro_recommendation_must_explain_store_and_platform_contributors", "store_recommendation_must_not_override_group_budget_or_risk_gate", "realtime_means_latest_local_or_authorized_data_not_unverified_external_live_data"}:
        if not direction_policy.get(required_true):
            errors.append(f"operating_intelligence_contract.dashboard_direction_policy.{required_true} must be true")
    if operating_contract.get("external_actions") != 0:
        errors.append("operating_intelligence_contract.external_actions must be 0")

    required_metadata = set(
        str(item) for item in _safe_list(registry.get("required_metric_metadata")) if str(item).strip()
    )
    if snapshot["metric_metadata_count"] != snapshot["metric_count"]:
        errors.append("metric dictionary must contain exactly one row per registered metric")
    if snapshot["complete_metric_metadata_count"] != snapshot["metric_count"]:
        errors.append("every metric dictionary row must contain all required metadata fields")
    for item in snapshot["metric_dictionary"]:
        metric_id = str(item.get("metric_id") or "unknown")
        missing_fields = sorted(field for field in required_metadata if field not in item or item.get(field) is None)
        if missing_fields:
            errors.append(f"metric {metric_id} missing metadata: {', '.join(missing_fields)}")
        if not _safe_list(item.get("source_record_types")):
            errors.append(f"metric {metric_id} must name at least one canonical source record type")

    freshness = snapshot["source_freshness_contract"]
    freshness_required = set(str(item) for item in _safe_list(freshness.get("required_fields")))
    for field in {"source_ref", "observed_at", "freshness_status", "truth_level", "source_record_count"}:
        if field not in freshness_required:
            errors.append(f"source_freshness_contract.required_fields missing {field}")
    if not freshness.get("stale_data_never_becomes_zero"):
        errors.append("source_freshness_contract.stale_data_never_becomes_zero must be true")
    if not freshness.get("missing_source_never_becomes_connected"):
        errors.append("source_freshness_contract.missing_source_never_becomes_connected must be true")

    commerce_scope = snapshot["commerce_scope_contract"]
    required_route_dimensions = set(
        str(item) for item in _safe_list(commerce_scope.get("required_route_dimensions"))
    )
    for field in {"platform", "country_site", "store_mode", "ownership"}:
        if field not in required_route_dimensions:
            errors.append(f"commerce_scope_contract.required_route_dimensions missing {field}")
    store_modes = {
        str(item.get("id") or ""): item
        for item in _safe_list(commerce_scope.get("store_modes"))
        if isinstance(item, dict)
    }
    for mode in {"local_store", "cross_border", "platform_co_ops", "teelab_owned", "official_full_managed"}:
        if mode not in store_modes:
            errors.append(f"commerce_scope_contract.store_modes missing {mode}")
    official_full_managed = store_modes.get("official_full_managed", {})
    if official_full_managed.get("selectable") is not False or official_full_managed.get("executable") is not False:
        errors.append("official_full_managed must remain recognition-only and non-executable")
    if commerce_scope.get("unbound_store_status") != "needs_platform_store":
        errors.append("commerce_scope_contract.unbound_store_status must be needs_platform_store")
    if not commerce_scope.get("unbound_store_excluded_from_operating_data"):
        errors.append("unbound stores must be excluded from operating data")
    direct_ship = commerce_scope.get("direct_ship_contract") if isinstance(commerce_scope.get("direct_ship_contract"), dict) else {}
    if direct_ship.get("store_mode") != "cross_border" or direct_ship.get("fulfillment_mode") != "cross_border_direct_ship_from_china":
        errors.append("direct ship must remain a cross_border fulfillment dimension, not a new store mode")
    errors.extend(validate_business_action_metric_dictionary(root))

    serialized = json.dumps(registry, ensure_ascii=False).lower()
    for word in {"connected", "running", "synced"}:
        if f'"{word}"' in serialized:
            errors.append(f"registry must not claim {word}")
    return errors
