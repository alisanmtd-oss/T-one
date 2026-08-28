from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import math
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .storage import append_record, read_records
from .task_execution_runtime import append_business_event, business_event_projection
from .types import IntakeRecord


REGISTRY_PATH = Path("config") / "platform_fee_settlement_registry.json"
COLLECTION_REGISTRY_PATH = Path("config") / "payment_collection_provider_registry.json"
DEFAULT_CURRENCY = "USD"
VALUE_STATUSES = {"estimate", "actual_statement", "fact", "observation", "inference", "unknown"}
FORBIDDEN_COLLECTION_KEYS = {
    "api_key",
    "client_secret",
    "access_token",
    "refresh_token",
    "password",
    "full_account_number",
    "bank_account_number",
    "routing_number",
    "card_number",
    "iban",
    "swift_secret",
}

SETTLEMENT_COMPONENTS = {
    "listing_fee",
    "commission_fee",
    "transaction_fee",
    "payment_fee",
    "fixed_order_fee",
    "regulatory_operating_fee",
    "currency_conversion_fee",
    "subscription_fee",
    "promoted_listing_fee",
    "activity_service_fee",
    "affiliate_creator_fee",
    "logistics_fee",
    "tax_withholding",
    "customs_duty_adjustment",
    "refund_return_reserve",
    "refundable_sample_refund",
}
EXTERNAL_COST_COMPONENTS = {
    "product_cost",
    "packaging_cost",
    "advertising_spend",
    "warehouse_storage_fee",
    "creator_sample_product_cost",
    "creator_sample_outbound_shipping",
}
POSITIVE_COMPONENTS = {
    "gross_revenue",
    "platform_subsidy",
    "refundable_sample_platform_fee_reversal",
    "other_adjustment",
}
CASH_RESERVE_COMPONENTS = {"refundable_sample_cash_reserve"}
NEGATIVE_COMPONENTS = SETTLEMENT_COMPONENTS | EXTERNAL_COST_COMPONENTS | {"seller_discount"}
REQUIRED_SCOPE_FIELDS = [
    "platform",
    "site",
    "store_mode",
    "category",
    "order_type",
    "activity",
    "promotion",
    "fulfillment",
    "warehouse_country",
    "ship_from_country",
    "effective_from",
    "effective_to",
    "currency",
    "tax_treatment",
    "evidence",
    "status",
    "seller_entity_jurisdiction",
    "seller_entity_type",
    "seller_tax_residency",
    "tax_registration_type",
    "tax_id_status",
    "product_condition",
    "seller_sales_address_region",
    "local_bank_account_status",
    "settlement_bank_jurisdiction",
    "marketplace_facilitator_status",
    "seller_nexus_status",
    "activity_rule_snapshot_id",
    "rule_as_of",
]
SETTLEMENT_RECONCILIATION_SCOPE_FIELDS = [
    "project_id",
    "platform",
    "site",
    "store_mode",
    "store_id",
    "product_id",
    "currency",
    "category",
    "order_type",
    "activity",
    "promotion",
    "fulfillment",
    "warehouse_country",
    "ship_from_country",
    "tax_treatment",
    "seller_entity_jurisdiction",
    "seller_entity_type",
    "seller_tax_residency",
    "tax_registration_type",
    "tax_id_status",
    "product_condition",
    "seller_sales_address_region",
    "settlement_bank_jurisdiction",
]
DEFAULT_FEE_COMPONENTS = [
    "gross_revenue",
    "product_cost",
    "packaging_cost",
    "seller_discount",
    "platform_subsidy",
    "commission_fee",
    "listing_fee",
    "transaction_fee",
    "payment_fee",
    "fixed_order_fee",
    "regulatory_operating_fee",
    "currency_conversion_fee",
    "subscription_fee",
    "promoted_listing_fee",
    "activity_service_fee",
    "affiliate_creator_fee",
    "creator_sample_product_cost",
    "creator_sample_outbound_shipping",
    "refundable_sample_cash_reserve",
    "refundable_sample_refund",
    "refundable_sample_platform_fee_reversal",
    "advertising_spend",
    "logistics_fee",
    "warehouse_storage_fee",
    "tax_withholding",
    "refund_return_reserve",
    "customs_duty_adjustment",
    "buyer_indirect_tax_collected",
    "seller_entity_tax_obligation",
    "other_adjustment",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _qty(value: Any, default: int = 0) -> int:
    number = _money(value)
    if number is None:
        return default
    return max(0, int(round(number)))


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None or not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


def _value_status(value: Any, default: str = "estimate") -> str:
    status = _clean(value, default).lower()
    return status if status in VALUE_STATUSES else default


def _scope(payload: dict[str, Any]) -> dict[str, Any]:
    scope = payload.get("scope") if isinstance(payload.get("scope"), dict) else payload
    platform = _clean(scope.get("platform"), "unknown")
    if platform.strip().lower() == "amazon":
        raise ValueError("Amazon 当前由负责人暂停；费用/结算能力不会读取或操作 Amazon 店铺。")
    return {
        "platform": platform,
        "site": _clean(scope.get("site") or scope.get("country_site") or scope.get("country"), "unknown").upper(),
        "store_mode": _clean(scope.get("store_mode") or scope.get("shop_type"), "unknown"),
        "category": _clean(scope.get("category"), "unknown"),
        "order_type": _clean(scope.get("order_type"), "unknown"),
        "activity": _clean(scope.get("activity"), "none"),
        "promotion": _clean(scope.get("promotion"), "none"),
        "fulfillment": _clean(scope.get("fulfillment"), "unknown"),
        "warehouse_country": _clean(scope.get("warehouse_country"), "unknown").upper(),
        "ship_from_country": _clean(scope.get("ship_from_country"), "unknown").upper(),
        "effective_from": _clean(scope.get("effective_from"), date.today().isoformat()),
        "effective_to": _clean(scope.get("effective_to"), ""),
        "currency": _clean(scope.get("currency"), DEFAULT_CURRENCY).upper(),
        "tax_treatment": _clean(scope.get("tax_treatment"), "unknown"),
        "evidence": scope.get("evidence") if isinstance(scope.get("evidence"), dict) else {},
        "status": _clean(scope.get("status"), "draft_estimate"),
        "seller_entity_jurisdiction": _clean(scope.get("seller_entity_jurisdiction"), "unknown").upper(),
        "seller_entity_type": _clean(scope.get("seller_entity_type"), "unknown").lower(),
        "seller_tax_residency": _clean(scope.get("seller_tax_residency"), "unknown").upper(),
        "tax_registration_type": _clean(scope.get("tax_registration_type"), "unknown").lower(),
        "tax_id_status": _clean(scope.get("tax_id_status"), "unknown").lower(),
        "product_condition": _clean(scope.get("product_condition"), "unknown").lower(),
        "seller_sales_address_region": _clean(
            scope.get("seller_sales_address_region"), "unknown"
        ).lower(),
        "local_bank_account_status": _clean(scope.get("local_bank_account_status"), "unknown").lower(),
        "settlement_bank_jurisdiction": _clean(
            scope.get("settlement_bank_jurisdiction"), "unknown"
        ).upper(),
        "marketplace_facilitator_status": _clean(scope.get("marketplace_facilitator_status"), "unknown").lower(),
        "seller_nexus_status": _clean(scope.get("seller_nexus_status"), "unknown").lower(),
        "activity_rule_snapshot_id": _clean(scope.get("activity_rule_snapshot_id")),
        "rule_as_of": _clean(scope.get("rule_as_of"), date.today().isoformat()),
        "project_id": _clean(scope.get("project_id") or payload.get("project_id")),
        "task_id": _clean(scope.get("task_id") or payload.get("task_id")),
        "conversation_id": _clean(scope.get("conversation_id") or payload.get("conversation_id") or payload.get("task_id")),
        "store_id": _clean(scope.get("store_id") or scope.get("store_binding_id") or payload.get("store_id")),
        "product_id": _clean(scope.get("product_id") or payload.get("product_id")),
    }


def _settlement_scope_mismatches(
    estimate_scope: dict[str, Any],
    statement_scope: dict[str, Any],
) -> list[str]:
    mismatches: list[str] = []
    for field in SETTLEMENT_RECONCILIATION_SCOPE_FIELDS:
        estimate_value = _clean(estimate_scope.get(field)).casefold()
        statement_value = _clean(statement_scope.get(field)).casefold()
        if (estimate_value or statement_value) and estimate_value != statement_value:
            mismatches.append(field)
    return mismatches


def registry_path(root: Path) -> Path:
    return root / REGISTRY_PATH


def load_platform_fee_registry(root: Path) -> dict[str, Any]:
    path = registry_path(root)
    if not path.exists():
        return {
            "schema_version": 1,
            "updated_at": _now_iso(),
            "purpose": "Platform fee and settlement rule registry.",
            "truth_rules": {},
            "required_scope_fields": list(REQUIRED_SCOPE_FIELDS),
            "fee_components": list(DEFAULT_FEE_COMPONENTS),
            "rules": [],
        }
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("平台费用与结算规则注册表必须是 JSON object。")
    return data


def platform_fee_registry_snapshot(root: Path) -> dict[str, Any]:
    registry = load_platform_fee_registry(root)
    rules = [item for item in registry.get("rules", []) if isinstance(item, dict)]
    coverage_matrix = [
        item for item in registry.get("coverage_matrix", []) if isinstance(item, dict)
    ]
    coverage_status_counts: dict[str, int] = defaultdict(int)
    for item in coverage_matrix:
        coverage_status_counts[_clean(item.get("status"), "schema_only_unknown")] += 1
    candidate_packages: list[dict[str, Any]] = []
    for item in registry.get("candidate_rule_packages", []):
        if not isinstance(item, dict):
            continue
        package = dict(item)
        relative_path = _clean(package.get("path"))
        package["exists"] = bool(relative_path and (root / relative_path).is_file())
        # Candidate packages are an evidence-review queue, never executable rules.
        package["executable"] = False
        candidate_packages.append(package)
    unknown = [
        item for item in rules
        if "unknown" in _clean(item.get("status")).lower()
        or any(
            isinstance(component, dict)
            and _value_status(component.get("value_status"), "unknown") == "unknown"
            for component in item.get("components", [])
        )
    ]
    return {
        "schema_version": registry.get("schema_version", 1),
        "registry_path": str(REGISTRY_PATH),
        "rule_count": len(rules),
        "unknown_rule_count": len(unknown),
        "required_scope_fields": list(registry.get("required_scope_fields") or REQUIRED_SCOPE_FIELDS),
        "fee_components": list(registry.get("fee_components") or DEFAULT_FEE_COMPONENTS),
        "tiktok_activity_components_separated": any(
            _clean(item.get("platform")).lower() == "tiktok shop"
            and _clean(item.get("activity")).lower() not in {"", "none"}
            for item in rules
        ),
        "external_action_count": 0,
        "coverage_matrix": coverage_matrix,
        "coverage_platform_count": len({_clean(item.get("platform")) for item in coverage_matrix}),
        "coverage_status_counts": dict(sorted(coverage_status_counts.items())),
        "coverage_status_taxonomy": dict(registry.get("coverage_status_taxonomy") or {}),
        "candidate_rule_packages": candidate_packages,
        "candidate_package_count": len(candidate_packages),
        "candidate_package_existing_count": sum(1 for item in candidate_packages if item.get("exists")),
        "candidate_package_missing_count": sum(1 for item in candidate_packages if not item.get("exists")),
        "advertising_cost_channels": list(registry.get("advertising_cost_channels") or []),
        "ledger_layers": list(registry.get("ledger_layers") or []),
        "rules": rules[:20],
    }


def collection_registry_path(root: Path) -> Path:
    return root / COLLECTION_REGISTRY_PATH


def load_payment_collection_provider_registry(root: Path) -> dict[str, Any]:
    path = collection_registry_path(root)
    if not path.exists():
        return {
            "schema_version": 1,
            "updated_at": _now_iso(),
            "purpose": "Collection providers between platform settlement and final bank receipt.",
            "truth_rules": {
                "platform_actual": "actual_platform_settlement",
                "final_cash_actual": "actual_bank_receipt",
                "statement_precedence": True,
                "fee_or_fx_without_dated_evidence": "unknown",
            },
            "providers": [],
        }
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("收款机构注册表必须是 JSON object。")
    return data


def payment_collection_provider_registry_snapshot(root: Path) -> dict[str, Any]:
    registry = load_payment_collection_provider_registry(root)
    providers = [
        dict(item)
        for item in registry.get("providers", [])
        if isinstance(item, dict)
    ]
    return {
        "schema_version": registry.get("schema_version", 1),
        "registry_path": str(COLLECTION_REGISTRY_PATH),
        "provider_count": len(providers),
        "providers": providers,
        "truth_rules": dict(registry.get("truth_rules") or {}),
        "oauth_connection_count": sum(1 for item in providers if item.get("oauth_connected") is True),
        "verified_fee_snapshot_count": sum(
            1 for item in providers if item.get("verified_fee_snapshot") is True
        ),
        "external_action_count": 0,
    }


def _reject_sensitive_collection_payload(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = _clean(raw_key).lower()
            if key in FORBIDDEN_COLLECTION_KEYS:
                raise ValueError(
                    f"{path}.{key} 不允许保存；这里只能记录账户别名和 account_last4。"
                )
            _reject_sensitive_collection_payload(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_sensitive_collection_payload(child, path=f"{path}[{index}]")


def _collection_provider(
    root: Path,
    provider_id: Any,
) -> dict[str, Any]:
    normalized = _clean(provider_id, "other").lower()
    registry = load_payment_collection_provider_registry(root)
    for item in registry.get("providers", []):
        if isinstance(item, dict) and _clean(item.get("provider_id")).lower() == normalized:
            return dict(item)
    raise ValueError("未知收款机构；请先在收款机构注册表中登记。")


def _collection_identity(payload: dict[str, Any]) -> tuple[str, str]:
    alias = _clean(payload.get("account_alias"))
    last4 = _clean(payload.get("account_last4"))
    if last4 and (len(last4) != 4 or not last4.isdigit()):
        raise ValueError("account_last4 只能是 4 位数字。")
    return alias, last4


def _collection_identity_key(provider_id: Any, alias: Any, last4: Any) -> str:
    return "::".join(
        [
            _clean(provider_id, "other").lower(),
            _clean(alias).lower(),
            _clean(last4),
        ]
    )


def _collection_fee_values(payload: dict[str, Any], prefix: str) -> dict[str, float | None]:
    return {
        "provider_receiving_fee": _money(payload.get(f"{prefix}provider_receiving_fee")),
        "provider_withholding": _money(payload.get(f"{prefix}provider_withholding")),
        "withdrawal_fee": _money(payload.get(f"{prefix}withdrawal_fee")),
        "intermediary_bank_fee": _money(payload.get(f"{prefix}intermediary_bank_fee")),
        "fixed_fee": _money(payload.get(f"{prefix}fixed_fee")),
        "other_fee": _money(payload.get(f"{prefix}other_fee")),
    }


def _parse_date(value: Any) -> date | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _selector_matches(expected: Any, actual: Any) -> bool:
    if expected is None:
        return True
    if isinstance(expected, list):
        return any(_selector_matches(item, actual) for item in expected)
    expected_text = _clean(expected).lower()
    if expected_text in {"", "*", "any"}:
        return True
    return expected_text == _clean(actual).lower()


def _rule_effective(rule: dict[str, Any], as_of: date) -> tuple[bool, str]:
    starts = _parse_date(rule.get("effective_from"))
    ends = _parse_date(rule.get("effective_to"))
    if starts and as_of < starts:
        return False, "not_yet_effective"
    if ends and as_of > ends:
        return False, "expired"
    stale_after_days = _qty(rule.get("stale_after_days"), 0)
    retrieved = _parse_date(rule.get("retrieved_at") or rule.get("evidence", {}).get("verified_at"))
    if stale_after_days and retrieved and as_of > retrieved + timedelta(days=stale_after_days):
        return False, "stale_evidence"
    return True, "effective"


def resolve_platform_finance_rules(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Resolve dated finance rules without treating guesses as platform truth."""
    scope = _scope(payload)
    registry = load_platform_fee_registry(root)
    rules = [item for item in registry.get("rules", []) if isinstance(item, dict)]
    as_of = _parse_date(scope.get("rule_as_of")) or date.today()
    selector_fields = [
        "platform",
        "site",
        "store_mode",
        "category",
        "order_type",
        "activity",
        "promotion",
        "fulfillment",
        "warehouse_country",
        "ship_from_country",
        "seller_entity_jurisdiction",
        "seller_entity_type",
        "seller_tax_residency",
        "tax_registration_type",
        "tax_id_status",
        "product_condition",
        "seller_sales_address_region",
        "currency",
        "local_bank_account_status",
        "settlement_bank_jurisdiction",
        "marketplace_facilitator_status",
        "seller_nexus_status",
    ]
    matched: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    component_rules: dict[str, dict[str, Any]] = {}
    ledger_entries: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for rule in rules:
        if not all(_selector_matches(rule.get(field), scope.get(field)) for field in selector_fields):
            continue
        effective, reason = _rule_effective(rule, as_of)
        if not effective:
            rejected.append({"rule_id": _clean(rule.get("id")), "reason": reason})
            continue
        evidence = rule.get("evidence") if isinstance(rule.get("evidence"), dict) else {}
        evidence_status = _clean(rule.get("evidence_status") or evidence.get("status"), "unknown").lower()
        status = _clean(rule.get("status"), "unknown").lower()
        if evidence_status not in {"verified_official", "verified_platform_statement"}:
            rejected.append({"rule_id": _clean(rule.get("id")), "reason": "evidence_not_verified"})
            continue
        if status not in {"active", "verified", "verified_partial"}:
            rejected.append({"rule_id": _clean(rule.get("id")), "reason": "rule_not_active"})
            continue
        matched.append(rule)
        for component in rule.get("components", []):
            if not isinstance(component, dict):
                continue
            name = _clean(component.get("component"))
            if not name:
                continue
            resolved = dict(component)
            resolved.update(
                {
                    "rule_id": _clean(rule.get("id")),
                    "rule_version": _clean(rule.get("rule_version")),
                    "evidence": evidence,
                    "evidence_status": evidence_status,
                    "effective_from": _clean(rule.get("effective_from")),
                    "effective_to": _clean(rule.get("effective_to")),
                }
            )
            if name not in component_rules:
                component_rules[name] = resolved
            layer = _clean(component.get("ledger_layer"), "platform_settlement")
            ledger_entries[layer].append(resolved)

    activity = _clean(scope.get("activity"), "none").lower()
    if activity not in {"", "none", "not_applicable", "fictional_activity_demo"}:
        if not scope.get("activity_rule_snapshot_id"):
            blockers.append("activity_rule_snapshot_missing")
        elif not any(
            _clean(rule.get("activity_rule_snapshot_id")) == _clean(scope.get("activity_rule_snapshot_id"))
            for rule in matched
        ):
            blockers.append("activity_rule_snapshot_not_verified")

    if scope.get("local_bank_account_status") == "verified_local" and not any(
        bool(rule.get("local_bank_changes_tax_rate")) for rule in matched
    ):
        warnings.append("local_bank_does_not_change_tax_without_explicit_official_rule")

    if scope.get("tax_id_status") == "unknown":
        warnings.append("tax_id_status_unknown")
    if scope.get("seller_entity_jurisdiction") == "UNKNOWN":
        warnings.append("seller_entity_jurisdiction_unknown")
    if not matched:
        blockers.append("no_verified_rule_for_exact_scope")

    return {
        "resolution_status": "blocked" if blockers else "verified_partial",
        "scope": scope,
        "matched_rule_ids": [_clean(item.get("id")) for item in matched],
        "rejected_rules": rejected,
        "component_rules": component_rules,
        "ledger_entries": dict(ledger_entries),
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "official_rule_derived_values_allowed": not blockers,
        "actual_platform_settlement_is_canonical": True,
        "external_action_count": 0,
    }


def _line(
    component: str,
    *,
    amount: float | None,
    value_status: str,
    source: str,
    sign: str = "deduction",
    notes: str = "",
    rate: float | None = None,
    base_amount: float | None = None,
    provenance: dict[str, Any] | None = None,
    ledger_layer: str = "platform_settlement",
) -> dict[str, Any]:
    return {
        "component": component,
        "amount": _round(amount),
        "rate": _round(rate, 6),
        "base_amount": _round(base_amount),
        "sign": sign,
        "value_status": _value_status(value_status),
        "source": source,
        "notes": notes,
        "provenance": provenance or {},
        "ledger_layer": ledger_layer,
    }


def _component_input(payload: dict[str, Any], component: str) -> dict[str, Any]:
    fee_lines = payload.get("fee_lines")
    if isinstance(fee_lines, list):
        for item in fee_lines:
            if isinstance(item, dict) and _clean(item.get("component")) == component:
                return item
    economics = payload.get("economics") if isinstance(payload.get("economics"), dict) else payload
    aliases = {
        "listing_fee": ("listing_fee", "insertion_fee"),
        "commission_fee": ("commission_fee", "commission"),
        "transaction_fee": ("transaction_fee", "transaction"),
        "payment_fee": ("payment_fee", "payment"),
        "fixed_order_fee": ("fixed_order_fee", "per_order_fee"),
        "regulatory_operating_fee": ("regulatory_operating_fee", "regulatory_fee"),
        "currency_conversion_fee": ("currency_conversion_fee", "conversion_fee"),
        "subscription_fee": ("subscription_fee", "monthly_subscription_fee"),
        "promoted_listing_fee": ("promoted_listing_fee", "offsite_ads_fee"),
        "activity_service_fee": ("activity_service_fee", "activity_fee"),
        "affiliate_creator_fee": (
            "affiliate_creator_fee",
            "affiliate_fee",
            "creator_fee",
            "affiliate_creator_commission",
        ),
        "advertising_spend": ("advertising_spend", "ad_spend"),
        "logistics_fee": ("logistics_fee", "shipping_fee", "fulfillment_fee"),
        "warehouse_storage_fee": ("warehouse_storage_fee", "storage_fee", "warehousing"),
        "tax_withholding": ("tax_withholding", "tax_amount", "tax"),
        "customs_duty_adjustment": ("customs_duty_adjustment", "customs_duty", "customs_adjustment"),
        "refund_return_reserve": ("refund_return_reserve", "refund_reserve", "return_reserve"),
        "other_adjustment": ("other_adjustment", "adjustment"),
    }
    for key in aliases.get(component, (component,)):
        if key in economics:
            return {
                "amount": economics.get(key),
                "source": "owner_input_unverified",
                "value_status": "estimate",
                "notes": "负责人输入，仅用于规划；不是平台规则或平台账单真值。",
            }
        rate_key = key + "_rate"
        if rate_key in economics:
            return {
                "rate": economics.get(rate_key),
                "source": "owner_input_unverified",
                "value_status": "estimate",
                "notes": "负责人输入，仅用于规划；不是平台规则或平台账单真值。",
            }
    return {}


def _amount_from_input(
    item: dict[str, Any],
    *,
    component: str,
    base_amount: float,
) -> tuple[float | None, float | None, str, str]:
    amount = _money(item.get("amount"))
    rate = _money(item.get("rate"))
    source = _clean(item.get("source"), "unknown")
    if amount is not None:
        return abs(amount), rate, source, _value_status(item.get("value_status"), "estimate")
    if rate is not None:
        return abs(base_amount * rate), rate, source, _value_status(item.get("value_status"), "estimate")
    if component == "other_adjustment":
        return 0.0, None, "default_zero", "estimate"
    return None, None, source, "unknown"


def _resolved_component_input(
    resolution: dict[str, Any],
    economics: dict[str, Any],
    component: str,
) -> dict[str, Any]:
    rules = resolution.get("component_rules") if isinstance(resolution.get("component_rules"), dict) else {}
    rule = rules.get(component) if isinstance(rules.get(component), dict) else None
    if not rule:
        return {}
    if component in {"activity_service_fee", "seller_discount", "platform_subsidy"} and any(
        str(item).startswith("activity_rule_snapshot_") for item in resolution.get("blockers", [])
    ):
        return {}
    calculation = _clean(rule.get("calculation"), "rate_or_fixed").lower()
    rate = _money(rule.get("rate"))
    fixed_amount = _money(rule.get("amount"))
    amount = fixed_amount
    base_field = _clean(rule.get("base_field"), "gross_revenue")
    base_amount = _money(economics.get(base_field))

    def missing(field: str) -> dict[str, Any]:
        return {
            "source": "verified_rule_missing_base",
            "rule": rule,
            "missing_base_field": field,
        }

    if calculation == "per_unit":
        count_field = _clean(rule.get("count_field"), "units")
        count = _money(economics.get(count_field))
        if count is None:
            return missing(count_field)
        if fixed_amount is None:
            return missing("verified_rule_fixed_amount")
        amount = abs(fixed_amount * count)
    elif calculation == "rate_plus_fixed":
        count_field = _clean(rule.get("count_field"), "order_count")
        count = _money(economics.get(count_field))
        if base_amount is None:
            return missing(base_field)
        if count is None:
            return missing(count_field)
        amount = abs(base_amount * (rate or 0.0) + count * (fixed_amount or 0.0))
    elif calculation == "progressive_tiers":
        if base_amount is None:
            return missing(base_field)
        amount = 0.0
        tiers = rule.get("tiers") if isinstance(rule.get("tiers"), list) else []
        if not tiers:
            return missing("verified_rule_tiers")
        for tier in tiers:
            if not isinstance(tier, dict):
                continue
            lower = _money(tier.get("above")) or 0.0
            upper = _money(tier.get("up_to"))
            tier_rate = _money(tier.get("rate"))
            if tier_rate is None or base_amount <= lower:
                continue
            tier_base = base_amount - lower if upper is None else min(base_amount, upper) - lower
            amount += max(0.0, tier_base) * tier_rate
        amount = abs(amount)
        rate = None
    elif calculation in {"band_rate", "band_fixed"}:
        decision_field = _clean(rule.get("decision_field"), base_field)
        decision_value = _money(economics.get(decision_field))
        if decision_value is None:
            return missing(decision_field)
        selected: dict[str, Any] | None = None
        for band in rule.get("bands", []):
            if not isinstance(band, dict):
                continue
            lower_inclusive = _money(band.get("min_inclusive"))
            lower_exclusive = _money(band.get("min_exclusive"))
            upper_inclusive = _money(band.get("max_inclusive"))
            upper_exclusive = _money(band.get("max_exclusive"))
            if lower_inclusive is not None and decision_value < lower_inclusive:
                continue
            if lower_exclusive is not None and decision_value <= lower_exclusive:
                continue
            if upper_inclusive is not None and decision_value > upper_inclusive:
                continue
            if upper_exclusive is not None and decision_value >= upper_exclusive:
                continue
            selected = band
            break
        if selected is None:
            return missing(f"{decision_field}:verified_rule_band")
        if calculation == "band_rate":
            if base_amount is None:
                return missing(base_field)
            rate = _money(selected.get("rate"))
            if rate is None:
                return missing("verified_rule_band_rate")
            amount = abs(base_amount * rate)
        else:
            count_field = _clean(rule.get("count_field"), "order_count")
            count = _money(economics.get(count_field))
            selected_amount = _money(selected.get("amount"))
            if count is None:
                return missing(count_field)
            if selected_amount is None:
                return missing("verified_rule_band_amount")
            amount = abs(selected_amount * count)
            rate = None
    elif amount is None and rate is not None:
        if base_amount is None:
            return missing(base_field)
        amount = abs(base_amount * rate)
    return {
        "amount": amount,
        "rate": rate,
        "source": "verified_platform_rule",
        "value_status": _clean(rule.get("value_status"), "fact"),
        "notes": _clean(rule.get("notes")),
        "rule": rule,
        "base_field": base_field,
        "base_amount": base_amount,
        "calculation": calculation,
    }


def _financial_ledger_layers(
    resolution: dict[str, Any],
    component_lines: list[dict[str, Any]],
) -> dict[str, Any]:
    rule_ledgers = resolution.get("ledger_entries") if isinstance(resolution.get("ledger_entries"), dict) else {}
    platform_withholding = [
        line for line in component_lines
        if line.get("component") in {"tax_withholding", "customs_duty_adjustment"}
        and line.get("amount") is not None
    ]
    return {
        "buyer_indirect_tax": {
            "settlement_effect": "excluded_unless_statement_says_otherwise",
            "entries": list(rule_ledgers.get("buyer_indirect_tax") or []),
        },
        "platform_seller_proceeds_withholding": {
            "settlement_effect": "deduction",
            "entries": platform_withholding + list(rule_ledgers.get("seller_proceeds_withholding") or []),
        },
        "import_customs": {
            "settlement_effect": "estimate_then_actual_reconciliation",
            "entries": list(rule_ledgers.get("import_customs") or []),
        },
        "seller_entity_tax_outside_platform": {
            "settlement_effect": "not_deducted_without_statement_line",
            "entries": list(rule_ledgers.get("seller_entity_tax_outside_platform") or []),
        },
        "platform_statement_truth": {
            "canonical_for_actuals": True,
            "entries": [],
        },
    }


def save_pre_operation_estimate(
    root: Path,
    payload: dict[str, Any],
    *,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    scope = _scope(payload)
    economics = payload.get("economics") if isinstance(payload.get("economics"), dict) else payload
    resolution = resolve_platform_finance_rules(root, {**payload, "scope": scope})
    units = max(1, _qty(economics.get("units") or economics.get("quantity"), 1))
    unit_price = _money(economics.get("unit_price") or economics.get("selling_price")) or 0.0
    unit_product_cost_input = _money(economics.get("unit_product_cost") or economics.get("product_cost"))
    unit_product_cost = unit_product_cost_input or 0.0
    unit_packaging_cost = _money(economics.get("unit_packaging_cost") or economics.get("packaging_cost")) or 0.0
    seller_discount_unit = _money(economics.get("seller_discount_unit")) or 0.0
    seller_discount_total = _money(economics.get("seller_discount_total"))
    platform_subsidy_total = _money(economics.get("platform_subsidy_total") or economics.get("platform_subsidy")) or 0.0

    gross_revenue = units * unit_price
    rule_economics = dict(economics)
    rule_economics.setdefault("gross_revenue", gross_revenue)
    rule_economics.setdefault("units", units)
    product_cost = units * unit_product_cost
    packaging_cost = units * unit_packaging_cost
    seller_discount = seller_discount_total if seller_discount_total is not None else units * seller_discount_unit
    component_lines: list[dict[str, Any]] = [
        _line("gross_revenue", amount=gross_revenue, value_status="estimate", source="owner_input", sign="positive"),
        _line("product_cost", amount=product_cost, value_status="estimate", source="owner_input", sign="external_cost"),
        _line("packaging_cost", amount=packaging_cost, value_status="estimate", source="owner_input", sign="external_cost"),
        _line("seller_discount", amount=seller_discount, value_status="estimate", source="owner_input", sign="deduction"),
        _line("platform_subsidy", amount=platform_subsidy_total, value_status="estimate", source="owner_input", sign="positive"),
    ]

    unknown_components: list[str] = []
    for component in [
        "listing_fee",
        "commission_fee",
        "transaction_fee",
        "payment_fee",
        "fixed_order_fee",
        "regulatory_operating_fee",
        "currency_conversion_fee",
        "subscription_fee",
        "promoted_listing_fee",
        "activity_service_fee",
        "affiliate_creator_fee",
        "advertising_spend",
        "logistics_fee",
        "warehouse_storage_fee",
        "tax_withholding",
        "customs_duty_adjustment",
        "refund_return_reserve",
        "other_adjustment",
    ]:
        item = _component_input(payload, component)
        if not item:
            item = _resolved_component_input(resolution, rule_economics, component)
        component_base = gross_revenue
        if (
            component == "affiliate_creator_fee"
            and _money(item.get("rate")) is not None
            and _money(item.get("amount")) is None
        ):
            affiliate_base = _money(economics.get("affiliate_attributed_sales"))
            if affiliate_base is None:
                amount = None
                rate = _money(item.get("rate"))
                source = _clean(item.get("source"), "unknown")
                value_status = "unknown"
                resolution["blockers"].append(
                    "affiliate_creator_fee_base_missing:affiliate_attributed_sales"
                )
            else:
                component_base = affiliate_base
                amount, rate, source, value_status = _amount_from_input(
                    item,
                    component=component,
                    base_amount=component_base,
                )
        else:
            amount, rate, source, value_status = _amount_from_input(
                item,
                component=component,
                base_amount=component_base,
            )
        if amount is None:
            unknown_components.append(component)
            if item.get("missing_base_field"):
                resolution["blockers"].append(
                    f"{component}_base_missing:{item['missing_base_field']}"
                )
        sign = "positive" if component in POSITIVE_COMPONENTS else ("external_cost" if component in EXTERNAL_COST_COMPONENTS else "deduction")
        rule = item.get("rule") if isinstance(item.get("rule"), dict) else {}
        component_lines.append(
            _line(
                component,
                amount=amount,
                rate=rate,
                base_amount=(
                    _money(item.get("base_amount"))
                    if item.get("base_amount") is not None
                    else (component_base if rate is not None else None)
                ),
                value_status=value_status,
                source=source,
                sign=sign,
                notes=_clean(item.get("notes")),
                provenance={
                    "rule_id": _clean(rule.get("rule_id")),
                    "rule_version": _clean(rule.get("rule_version")),
                    "evidence_status": _clean(rule.get("evidence_status")),
                    "evidence": rule.get("evidence") if isinstance(rule.get("evidence"), dict) else {},
                    "input_kind": "verified_rule" if source == "verified_platform_rule" else "owner_input_or_unknown",
                },
                ledger_layer=_clean(rule.get("ledger_layer"), "platform_settlement"),
            )
        )

    free_sample_units = _qty(economics.get("free_samples_sent"), 0)
    refundable_sample_orders = _qty(economics.get("refundable_sample_orders"), 0)
    planned_sample_units = free_sample_units + refundable_sample_orders
    sample_keys = {
        "free_samples_sent",
        "refundable_sample_orders",
        "sample_unit_product_cost",
        "sample_unit_outbound_shipping",
        "sample_outbound_shipping_total",
        "refundable_sample_refund_reserve",
        "refundable_sample_refund",
        "refundable_sample_platform_fee_reversal",
    }
    sample_plan_active = planned_sample_units > 0 or any(key in economics for key in sample_keys)
    if sample_plan_active:
        sample_unit_cost = _money(economics.get("sample_unit_product_cost"))
        sample_cost_source = "owner_input_unverified"
        if sample_unit_cost is None and unit_product_cost_input is not None:
            sample_unit_cost = unit_product_cost_input
            sample_cost_source = "owner_product_cost_fallback"
        sample_product_cost = (
            planned_sample_units * sample_unit_cost
            if planned_sample_units > 0 and sample_unit_cost is not None
            else (0.0 if planned_sample_units == 0 else None)
        )
        if sample_product_cost is None:
            unknown_components.append("creator_sample_product_cost")
            resolution["blockers"].append(
                "creator_sample_product_cost_base_missing:sample_unit_product_cost"
            )
        component_lines.append(
            _line(
                "creator_sample_product_cost",
                amount=sample_product_cost,
                value_status="estimate" if sample_product_cost is not None else "unknown",
                source=sample_cost_source if sample_product_cost is not None else "unknown",
                sign="external_cost",
                notes="免费样品与可退样品的货值成本；与广告费、平台佣金分账。",
                base_amount=sample_unit_cost,
                provenance={"input_kind": "owner_sample_plan"},
                ledger_layer="sample_and_creator_cost",
            )
        )

        sample_shipping_total = _money(economics.get("sample_outbound_shipping_total"))
        sample_unit_shipping = _money(economics.get("sample_unit_outbound_shipping"))
        if sample_shipping_total is None and sample_unit_shipping is not None:
            sample_shipping_total = planned_sample_units * sample_unit_shipping
        if sample_shipping_total is None and planned_sample_units > 0:
            unknown_components.append("creator_sample_outbound_shipping")
            resolution["blockers"].append("creator_sample_outbound_shipping_missing")
        component_lines.append(
            _line(
                "creator_sample_outbound_shipping",
                amount=sample_shipping_total if sample_shipping_total is not None else (0.0 if planned_sample_units == 0 else None),
                value_status="estimate" if sample_shipping_total is not None or planned_sample_units == 0 else "unknown",
                source="owner_input_unverified" if sample_shipping_total is not None else "unknown",
                sign="external_cost",
                notes="样品寄出运费；不得并入广告预算。",
                base_amount=sample_unit_shipping,
                provenance={"input_kind": "owner_sample_plan"},
                ledger_layer="sample_and_creator_cost",
            )
        )

        if refundable_sample_orders > 0:
            refundable_values = {
                "refundable_sample_cash_reserve": _money(economics.get("refundable_sample_refund_reserve")),
                "refundable_sample_refund": _money(economics.get("refundable_sample_refund")),
                "refundable_sample_platform_fee_reversal": _money(
                    economics.get("refundable_sample_platform_fee_reversal")
                ),
            }
            sample_notes = {
                "refundable_sample_cash_reserve": "可退样品达标退款的现金准备金；只影响现金占用，不重复扣减利润。",
                "refundable_sample_refund": "预计或账单中的可退样品退款；估算必须由负责人输入或平台规则支持。",
                "refundable_sample_platform_fee_reversal": "可退样品达标后平台费用冲回；只有平台规则或账单证据才能计入。",
            }
            for component, component_amount in refundable_values.items():
                if component_amount is None:
                    unknown_components.append(component)
                    resolution["blockers"].append(f"{component}_missing")
                sign = (
                    "positive"
                    if component == "refundable_sample_platform_fee_reversal"
                    else ("cash_reserve" if component in CASH_RESERVE_COMPONENTS else "deduction")
                )
                component_lines.append(
                    _line(
                        component,
                        amount=component_amount,
                        value_status="estimate" if component_amount is not None else "unknown",
                        source="owner_input_unverified" if component_amount is not None else "unknown",
                        sign=sign,
                        notes=sample_notes[component],
                        provenance={"input_kind": "owner_sample_plan_or_verified_rule"},
                        ledger_layer=(
                            "cash_reserve"
                            if component in CASH_RESERVE_COMPONENTS
                            else "platform_settlement"
                        ),
                    )
                )

    resolution["blockers"] = list(dict.fromkeys(resolution.get("blockers") or []))
    resolution["resolution_status"] = "blocked" if resolution["blockers"] else "verified_partial"
    resolution["official_rule_derived_values_allowed"] = not resolution["blockers"]

    line_by_component = {line["component"]: line for line in component_lines}

    def amount(component: str) -> float:
        value = line_by_component.get(component, {}).get("amount")
        return float(value or 0.0)

    estimated_platform_settlement = (
        amount("gross_revenue")
        - amount("seller_discount")
        + amount("platform_subsidy")
        - sum(amount(component) for component in SETTLEMENT_COMPONENTS)
        + amount("refundable_sample_platform_fee_reversal")
        + amount("other_adjustment")
    )
    contribution_before_ads = (
        estimated_platform_settlement
        - amount("product_cost")
        - amount("packaging_cost")
        - amount("warehouse_storage_fee")
        - amount("creator_sample_product_cost")
        - amount("creator_sample_outbound_shipping")
    )
    contribution_after_ads = contribution_before_ads - amount("advertising_spend")
    break_even_acos = contribution_before_ads / gross_revenue if gross_revenue > 0 and contribution_before_ads > 0 else None
    break_even_roas = gross_revenue / contribution_before_ads if contribution_before_ads > 0 else None
    cash_occupied = (
        amount("product_cost")
        + amount("packaging_cost")
        + amount("warehouse_storage_fee")
        + amount("advertising_spend")
        + amount("activity_service_fee")
        + amount("refund_return_reserve")
        + amount("creator_sample_product_cost")
        + amount("creator_sample_outbound_shipping")
        + max(
            amount("refundable_sample_cash_reserve"),
            amount("refundable_sample_refund"),
        )
    )
    inventory_economics = {
        **economics,
        "units": units,
        "unit_product_cost": unit_product_cost,
        "planned_sample_units": planned_sample_units,
        "cash_occupied": cash_occupied,
        "contribution_before_ads": contribution_before_ads,
    }
    inventory_plan = build_inventory_cash_plan(
        root,
        {
            **payload,
            "scope": scope,
            "economics": inventory_economics,
        },
        persist=True,
    )
    estimate_id = "settlement-estimate-" + uuid.uuid4().hex[:16]
    ledgers = _financial_ledger_layers(resolution, component_lines)
    fields = {
        "estimate_id": estimate_id,
        "value_status": "estimate",
        "scope": scope,
        "units": units,
        "unit_price": _round(unit_price),
        "component_lines": component_lines,
        "unknown_fee_components": unknown_components,
        "rule_resolution": resolution,
        "financial_ledger_layers": ledgers,
        "estimated_platform_settlement": _round(estimated_platform_settlement),
        "contribution_profit_before_ads": _round(contribution_before_ads),
        "contribution_profit_after_ads": _round(contribution_after_ads),
        "margin_before_ads": _round(contribution_before_ads / gross_revenue if gross_revenue else None, 4),
        "margin_after_ads": _round(contribution_after_ads / gross_revenue if gross_revenue else None, 4),
        "break_even_acos": _round(break_even_acos, 4),
        "break_even_roas": _round(break_even_roas, 4),
        "cash_occupied": _round(cash_occupied),
        "sample_and_affiliate_finance": {
            "free_sample_units": free_sample_units,
            "refundable_sample_orders": refundable_sample_orders,
            "planned_sample_units": planned_sample_units,
            "sample_product_cost": _round(amount("creator_sample_product_cost")),
            "sample_outbound_shipping": _round(amount("creator_sample_outbound_shipping")),
            "refundable_sample_cash_reserve": _round(amount("refundable_sample_cash_reserve")),
            "refundable_sample_refund": _round(amount("refundable_sample_refund")),
            "refundable_sample_platform_fee_reversal": _round(
                amount("refundable_sample_platform_fee_reversal")
            ),
            "affiliate_attributed_sales": _round(_money(economics.get("affiliate_attributed_sales"))),
            "affiliate_creator_fee": _round(amount("affiliate_creator_fee")),
            "sample_costs_are_separate_from_ads": True,
            "cash_reserve_is_not_profit_deduction": True,
        },
        "inventory_cash_plan": inventory_plan,
        "actual_platform_settlement_is_canonical": False,
        "sample_not_platform_rule": bool(payload.get("sample_not_platform_rule")),
        "external_action_count": 0,
    }
    record = IntakeRecord(
        record_type="platform_settlement_estimate",
        fields=fields,
        raw_text=json.dumps(fields, ensure_ascii=False, sort_keys=True),
        source="local_platform_finance_estimator",
        review_status="owner_review_required",
        confidence=0.65 if unknown_components else 0.85,
        metadata={"registry": str(REGISTRY_PATH), "external_action_count": 0},
    )
    append_record(root, record)
    event = append_business_event(
        root,
        {
            "event_type": "platform_finance_estimate_created",
            "kind": "draft",
            "project_id": scope.get("project_id"),
            "task_id": scope.get("task_id"),
            "conversation_id": scope.get("conversation_id"),
            "actor": actor,
            "statement": (
                f"已保存 {scope['platform']} {scope['site']} 的运营前费用/结算估算；"
                f"预计结算 {fields['estimated_platform_settlement']} {scope['currency']}；"
                f"未知费用 {len(unknown_components)} 项；外部动作 0。"
            ),
            "status": "owner_review_required",
            "business_object_refs": [
                {"type": "settlement_estimate", "id": estimate_id},
                {"type": "platform_fee_registry", "id": str(REGISTRY_PATH)},
            ],
            "payload": {
                "value_status": "estimate",
                "estimate_id": estimate_id,
                "unknown_fee_components": unknown_components,
                "external_action_count": 0,
            },
        },
        actor=actor,
    )
    return {"ok": True, "estimate": fields, "record_id": record.record_id, "event": event}


def build_inventory_cash_plan(
    root: Path,
    payload: dict[str, Any],
    *,
    persist: bool = True,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    scope = _scope(payload)
    economics = payload.get("economics") if isinstance(payload.get("economics"), dict) else payload
    units = max(1, _qty(economics.get("units"), 1))
    current_inventory = _qty(economics.get("current_inventory"), 0)
    lead_time_days = max(1, _qty(economics.get("lead_time_days"), 14))
    safety_stock_days = max(0, _qty(economics.get("safety_stock_days"), 7))
    activity_uplift = _money(economics.get("activity_uplift")) or 0.0
    return_rate = _money(economics.get("return_rate")) or 0.0
    unit_cost = _money(economics.get("unit_product_cost") or economics.get("product_cost")) or 0.0
    planned_sample_units = _qty(economics.get("planned_sample_units"), 0)
    base_daily_units = max(1.0, units / max(1.0, _money(economics.get("sales_window_days")) or 7.0))
    scenario_units = {
        "conservative": max(1, int(round(units * 0.7))),
        "base": units,
        "activity": max(1, int(round(units * (1.0 + max(0.0, activity_uplift))))),
    }
    demand_required_stock = int(round(base_daily_units * (lead_time_days + safety_stock_days) * (1.0 + max(0.0, activity_uplift))))
    required_stock = demand_required_stock + planned_sample_units
    expected_returns = int(round(demand_required_stock * max(0.0, return_rate)))
    reorder_qty = max(0, required_stock + expected_returns - current_inventory)
    purchase_cash_required = reorder_qty * unit_cost
    contribution_before_ads = _money(economics.get("contribution_before_ads")) or 0.0
    ad_spend_cap = max(0.0, contribution_before_ads)
    cash_occupied = _money(economics.get("cash_occupied"))
    if cash_occupied is None:
        cash_occupied = purchase_cash_required + ad_spend_cap
    plan = {
        "value_status": "estimate",
        "scenario_units": scenario_units,
        "lead_time_days": lead_time_days,
        "safety_stock_days": safety_stock_days,
        "activity_uplift": _round(activity_uplift, 4),
        "return_rate": _round(return_rate, 4),
        "current_inventory": current_inventory,
        "demand_required_stock": demand_required_stock,
        "planned_sample_units": planned_sample_units,
        "required_stock": required_stock,
        "expected_returns": expected_returns,
        "reorder_qty": reorder_qty,
        "purchase_cash_required": _round(purchase_cash_required),
        "ad_spend_cap": _round(ad_spend_cap),
        "activity_cash_reserve": _round(max(0.0, cash_occupied - purchase_cash_required)),
        "cash_occupied": _round(cash_occupied),
        "recommendation": (
            "需要补货并预留活动现金。"
            if reorder_qty > 0
            else "当前库存覆盖估算场景；继续等待真实销量/退货/账单回写。"
        ),
        "external_action_count": 0,
    }
    if persist:
        plan_id = "inventory-cash-plan-" + uuid.uuid4().hex[:16]
        fields = {"plan_id": plan_id, "scope": scope, **plan}
        record = IntakeRecord(
            record_type="inventory_cash_plan",
            fields=fields,
            raw_text=json.dumps(fields, ensure_ascii=False, sort_keys=True),
            source="local_platform_finance_estimator",
            review_status="owner_review_required",
            confidence=0.7,
            metadata={"external_action_count": 0},
        )
        append_record(root, record)
        append_business_event(
            root,
            {
                "event_type": "inventory_cash_plan_created",
                "kind": "draft",
                "project_id": scope.get("project_id"),
                "task_id": scope.get("task_id"),
                "conversation_id": scope.get("conversation_id"),
                "actor": actor,
                "statement": (
                    f"已保存库存/资金计划；建议补货 {reorder_qty} 件；"
                    f"采购现金 {plan['purchase_cash_required']} {scope['currency']}；外部动作 0。"
                ),
                "status": "owner_review_required",
                "business_object_refs": [{"type": "inventory_cash_plan", "id": plan_id}],
                "payload": {"value_status": "estimate", "external_action_count": 0},
            },
            actor=actor,
        )
        plan["plan_id"] = plan_id
        plan["record_id"] = record.record_id
    return plan


def import_platform_settlement_statement(
    root: Path,
    payload: dict[str, Any],
    *,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    scope = _scope(payload)
    lines_payload = payload.get("lines") if isinstance(payload.get("lines"), list) else []
    if not lines_payload:
        raise ValueError("请提供 settlement/bill 明细行；没有账单明细不能生成 actual_platform_settlement。")
    lines: list[dict[str, Any]] = []
    by_component: dict[str, float] = defaultdict(float)
    seen_line_ids: set[str] = set()
    for index, item in enumerate(lines_payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 行不是可解析的账单明细对象。")
        component = _clean(item.get("component") or item.get("fee_type") or item.get("type"), "other_adjustment")
        amount = _money(item.get("amount"))
        if amount is None:
            raise ValueError(f"第 {index} 行缺少可解析 amount。")
        currency = _clean(item.get("currency"), scope["currency"]).upper()
        if currency != scope["currency"]:
            raise ValueError(
                f"第 {index} 行币种 {currency} 与账单币种 {scope['currency']} 不一致；"
                "未提供可核验汇率时不能直接相加。"
            )
        line_id = _clean(item.get("line_id"), f"line-{index}")
        if line_id in seen_line_ids:
            raise ValueError(f"账单 line_id 重复：{line_id}。")
        seen_line_ids.add(line_id)
        line = {
            "line_id": line_id,
            "order_id": _clean(item.get("order_id")),
            "component": component,
            "amount": _round(amount),
            "currency": currency,
            "value_status": "actual_statement",
            "evidence_ref": _clean(item.get("evidence_ref") or item.get("source_ref")),
            "notes": _clean(item.get("notes")),
        }
        lines.append(line)
        by_component[component] += amount
    actual = _money(payload.get("actual_platform_settlement"))
    if actual is None:
        actual = sum(float(line["amount"] or 0.0) for line in lines)
    statement_id = _clean(payload.get("statement_id"), "settlement-" + uuid.uuid4().hex[:16])
    fields = {
        "statement_id": statement_id,
        "value_status": "actual_statement",
        "scope": scope,
        "currency": scope["currency"],
        "actual_platform_settlement": _round(actual),
        "component_actuals": {key: _round(value) for key, value in sorted(by_component.items())},
        "lines": lines,
        "canonical_for_actuals": True,
        "sample_not_platform_rule": bool(payload.get("sample_not_platform_rule")),
        "external_action_count": 0,
    }
    source_file = payload.get("source_file")
    if isinstance(source_file, dict):
        fields["source_file"] = {
            "filename": _clean(source_file.get("filename")),
            "sha256": _clean(source_file.get("sha256")),
            "row_count": int(source_file.get("row_count") or len(lines)),
        }
    record = IntakeRecord(
        record_type="platform_settlement_statement",
        fields=fields,
        raw_text=json.dumps(fields, ensure_ascii=False, sort_keys=True),
        source="local_platform_settlement_import",
        review_status="approved",
        confidence=0.9,
        metadata={"external_action_count": 0},
    )
    append_record(root, record)
    event = append_business_event(
        root,
        {
            "event_type": "platform_statement_imported",
            "kind": "fact",
            "project_id": scope.get("project_id"),
            "task_id": scope.get("task_id"),
            "conversation_id": scope.get("conversation_id"),
            "actor": actor,
            "statement": (
                f"已导入平台结算账单 {statement_id}；actual_platform_settlement "
                f"{fields['actual_platform_settlement']} {scope['currency']} 是实际结果真值；外部动作 0。"
            ),
            "status": "recorded",
            "business_object_refs": [{"type": "platform_settlement_statement", "id": statement_id}],
            "payload": {
                "value_status": "actual_statement",
                "statement_id": statement_id,
                "actual_platform_settlement": fields["actual_platform_settlement"],
                "external_action_count": 0,
            },
        },
        actor=actor,
    )
    return {"ok": True, "statement": fields, "record_id": record.record_id, "event": event}


_STATEMENT_FILE_MAX_BYTES = 10 * 1024 * 1024
_STATEMENT_COLUMN_ALIASES = {
    "lineid": "line_id",
    "line": "line_id",
    "行号": "line_id",
    "明细id": "line_id",
    "orderid": "order_id",
    "订单号": "order_id",
    "订单id": "order_id",
    "component": "component",
    "feetype": "component",
    "type": "component",
    "费用类型": "component",
    "项目": "component",
    "amount": "amount",
    "金额": "amount",
    "currency": "currency",
    "币种": "currency",
    "evidenceref": "evidence_ref",
    "sourceref": "evidence_ref",
    "凭证": "evidence_ref",
    "来源": "evidence_ref",
    "notes": "notes",
    "备注": "notes",
}


def _statement_column_key(value: Any) -> str:
    compact = "".join(character for character in _clean(value).casefold() if character.isalnum() or "\u4e00" <= character <= "\u9fff")
    return _STATEMENT_COLUMN_ALIASES.get(compact, _clean(value).strip().casefold().replace(" ", "_"))


def _decode_settlement_statement_file(payload: dict[str, Any]) -> tuple[str, bytes]:
    filename = Path(_clean(payload.get("filename"), "settlement.csv")).name
    suffix = Path(filename).suffix.casefold()
    if suffix not in {".csv", ".json"}:
        raise ValueError("结算单文件仅支持 CSV 或 JSON。")
    encoded = _clean(payload.get("content_base64"))
    if encoded.startswith("data:") and "," in encoded:
        encoded = encoded.split(",", 1)[1]
    try:
        content = base64.b64decode(encoded, validate=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("结算单文件不是有效的 Base64 数据。") from exc
    if not content:
        raise ValueError("结算单文件为空。")
    if len(content) > _STATEMENT_FILE_MAX_BYTES:
        raise ValueError("结算单文件超过 10 MB 上限。")
    return filename, content


def _parse_settlement_statement_lines(filename: str, content: bytes) -> list[dict[str, Any]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("结算单文件必须使用 UTF-8 编码。") from exc
    if Path(filename).suffix.casefold() == ".json":
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"结算单 JSON 无法解析：第 {exc.lineno} 行。") from exc
        rows = decoded.get("lines") if isinstance(decoded, dict) else decoded
        if not isinstance(rows, list):
            raise ValueError("结算单 JSON 必须是明细数组，或包含 lines 明细数组。")
    else:
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("结算单 CSV 缺少表头。")
        rows = list(reader)
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"第 {index} 行不是可解析的账单明细对象。")
        item = {
            _statement_column_key(key): value
            for key, value in row.items()
            if key is not None and _clean(value)
        }
        if not item:
            continue
        item.setdefault("line_id", f"file-line-{index}")
        normalized.append(item)
    if not normalized:
        raise ValueError("结算单文件没有可导入的明细行。")
    return normalized


def import_settlement_statement_file(
    root: Path,
    payload: dict[str, Any],
    *,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    """Import one owner-supplied local statement and optionally reconcile it.

    The file digest plus exact financial scope makes the operation repeat-safe.
    No network, store, payment, or bank action is performed.
    """

    filename, content = _decode_settlement_statement_file(payload)
    lines = _parse_settlement_statement_lines(filename, content)
    scope = _scope(payload)
    file_sha256 = hashlib.sha256(content).hexdigest().upper()
    scope_fingerprint = json.dumps(scope, ensure_ascii=False, sort_keys=True).encode("utf-8")
    import_fingerprint = hashlib.sha256(content + b"\0" + scope_fingerprint).hexdigest().upper()
    statement_id = _clean(payload.get("statement_id"), f"settlement-file-{import_fingerprint[:16]}")
    estimate_id = _clean(payload.get("estimate_id") or payload.get("estimate_record_id"))

    estimate_record = None
    if estimate_id:
        estimate_record = _find_record_by_field(
            root, "platform_settlement_estimate", "estimate_id", estimate_id
        )
        if estimate_record is None:
            raise ValueError("没有找到对应的运营前估算；文件尚未写入。")
        estimate_scope = (
            estimate_record.fields.get("scope")
            if isinstance(estimate_record.fields.get("scope"), dict)
            else {}
        )
        scope_mismatches = _settlement_scope_mismatches(estimate_scope, scope)
        if scope_mismatches:
            raise ValueError(
                "运营前估算与结算单文件不属于同一财务作用域："
                + ", ".join(scope_mismatches)
                + "；文件尚未写入。"
            )

    existing_statement = _find_record_by_field(
        root, "platform_settlement_statement", "statement_id", statement_id
    )
    if existing_statement is None:
        statement_result = import_platform_settlement_statement(
            root,
            {
                **payload,
                "scope": scope,
                "statement_id": statement_id,
                "lines": lines,
                "source_file": {
                    "filename": filename,
                    "sha256": file_sha256,
                    "row_count": len(lines),
                },
            },
            actor=actor,
        )
        statement = statement_result["statement"]
        statement_was_new = True
    else:
        statement = existing_statement.fields
        statement_was_new = False

    reconciliation = None
    reconciliation_was_new = False
    if estimate_id:
        for record in read_records(root, "platform_settlement_reconciliation"):
            if (
                _clean(record.fields.get("estimate_id")) == estimate_id
                and _clean(record.fields.get("statement_id")) == statement_id
            ):
                reconciliation = record.fields
                break
        if reconciliation is None:
            reconciliation = reconcile_estimate_with_statement(
                root,
                {"estimate_id": estimate_id, "statement_id": statement_id},
                actor=actor,
            )["reconciliation"]
            reconciliation_was_new = True

    if statement_was_new and reconciliation_was_new:
        status = "imported_and_reconciled"
    elif statement_was_new:
        status = "imported"
    elif reconciliation_was_new:
        status = "already_imported_and_reconciled"
    else:
        status = "already_imported_and_reconciled" if reconciliation else "already_imported"
    return {
        "ok": True,
        "status": status,
        "statement": statement,
        "reconciliation": reconciliation,
        "file": {
            "filename": filename,
            "sha256": file_sha256,
            "row_count": len(lines),
        },
        "external_action_count": 0,
    }


def _find_record_by_field(root: Path, record_type: str, field_name: str, value: str) -> IntakeRecord | None:
    for record in read_records(root, record_type):
        if _clean(record.fields.get(field_name)) == value or record.record_id == value:
            return record
    return None


def reconcile_estimate_with_statement(
    root: Path,
    payload: dict[str, Any],
    *,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    estimate_ref = _clean(payload.get("estimate_id") or payload.get("estimate_record_id"))
    statement_ref = _clean(payload.get("statement_id") or payload.get("statement_record_id"))
    if not estimate_ref or not statement_ref:
        raise ValueError("对账需要 estimate_id 和 statement_id。")
    estimate_record = _find_record_by_field(root, "platform_settlement_estimate", "estimate_id", estimate_ref)
    statement_record = _find_record_by_field(root, "platform_settlement_statement", "statement_id", statement_ref)
    if estimate_record is None:
        raise ValueError("没有找到对应的运营前估算。")
    if statement_record is None:
        raise ValueError("没有找到对应的平台结算账单。")
    estimate = estimate_record.fields
    statement = statement_record.fields
    estimate_scope = estimate.get("scope") if isinstance(estimate.get("scope"), dict) else {}
    statement_scope = statement.get("scope") if isinstance(statement.get("scope"), dict) else {}
    scope_mismatches = _settlement_scope_mismatches(estimate_scope, statement_scope)
    if scope_mismatches:
        raise ValueError(
            "运营前估算与平台结算账单不属于同一财务作用域："
            + ", ".join(scope_mismatches)
        )
    estimated_lines = {
        str(line.get("component")): float(line.get("amount") or 0.0)
        for line in estimate.get("component_lines", [])
        if isinstance(line, dict) and line.get("amount") is not None
    }
    actual_by_component = {
        str(key): float(value or 0.0)
        for key, value in (statement.get("component_actuals") or {}).items()
    }
    components = sorted(set(estimated_lines) | set(actual_by_component))
    line_diffs = []
    for component in components:
        estimated_amount = abs(estimated_lines.get(component, 0.0))
        actual_amount = abs(actual_by_component.get(component, 0.0))
        line_diffs.append(
            {
                "component": component,
                "estimated_amount": _round(estimated_amount),
                "actual_amount": _round(actual_amount),
                "difference": _round(actual_amount - estimated_amount),
                "reason": "unknown_until_owner_or_platform_rule_review",
                "value_status": "observation",
            }
        )
    estimated_settlement = float(estimate.get("estimated_platform_settlement") or 0.0)
    actual_settlement = float(statement.get("actual_platform_settlement") or 0.0)
    reconciliation_id = "settlement-recon-" + uuid.uuid4().hex[:16]
    fields = {
        "reconciliation_id": reconciliation_id,
        "estimate_id": estimate.get("estimate_id"),
        "statement_id": statement.get("statement_id"),
        "scope": (
            statement.get("scope")
            if isinstance(statement.get("scope"), dict)
            else (
                estimate.get("scope")
                if isinstance(estimate.get("scope"), dict)
                else {}
            )
        ),
        "value_status": "observation",
        "estimated_platform_settlement": _round(estimated_settlement),
        "actual_platform_settlement": _round(actual_settlement),
        "settlement_difference": _round(actual_settlement - estimated_settlement),
        "line_diffs": line_diffs,
        "rule_drift_candidates": [
            item for item in line_diffs
            if abs(float(item.get("difference") or 0.0)) > 0.01
        ],
        "actual_statement_canonical": True,
        "next_action": "差异原因必须回写规则、预算和备货计划；估算不得覆盖实际账单。",
        "external_action_count": 0,
    }
    record = IntakeRecord(
        record_type="platform_settlement_reconciliation",
        fields=fields,
        raw_text=json.dumps(fields, ensure_ascii=False, sort_keys=True),
        source="local_platform_settlement_reconciliation",
        review_status="owner_review_required",
        confidence=0.82,
        metadata={"external_action_count": 0},
    )
    append_record(root, record)
    scope = statement.get("scope") if isinstance(statement.get("scope"), dict) else {}
    event = append_business_event(
        root,
        {
            "event_type": "platform_settlement_reconciled",
            "kind": "observation",
            "project_id": scope.get("project_id"),
            "task_id": scope.get("task_id"),
            "conversation_id": scope.get("conversation_id") or scope.get("task_id"),
            "actor": actor,
            "statement": (
                f"已完成估算与平台账单对账；实际结算 {fields['actual_platform_settlement']} "
                f"覆盖估算真值，差异 {fields['settlement_difference']}；外部动作 0。"
            ),
            "status": "owner_review_required",
            "business_object_refs": [
                {"type": "platform_settlement_reconciliation", "id": reconciliation_id},
                {"type": "platform_settlement_estimate", "id": str(estimate.get("estimate_id") or "")},
                {"type": "platform_settlement_statement", "id": str(statement.get("statement_id") or "")},
            ],
            "payload": {
                "value_status": "observation",
                "actual_statement_canonical": True,
                "rule_drift_candidate_count": len(fields["rule_drift_candidates"]),
                "external_action_count": 0,
            },
        },
        actor=actor,
    )
    return {"ok": True, "reconciliation": fields, "record_id": record.record_id, "event": event}


def save_collection_payout_estimate(
    root: Path,
    payload: dict[str, Any],
    *,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    _reject_sensitive_collection_payload(payload)
    scope = _scope(payload)
    provider = _collection_provider(root, payload.get("provider_id"))
    account_alias, account_last4 = _collection_identity(payload)
    account_identity = _collection_identity_key(
        provider.get("provider_id"),
        account_alias,
        account_last4,
    )
    source_amount = _money(payload.get("source_platform_settlement_amount"))
    if source_amount is None:
        source_amount = _money(payload.get("actual_platform_settlement"))
    if source_amount is None:
        raise ValueError("请填写平台结算金额；没有该金额不能估算银行卡实收。")
    source_currency = _clean(payload.get("source_currency"), scope["currency"]).upper()
    bank_currency = _clean(payload.get("bank_currency"), source_currency).upper()
    fees = _collection_fee_values(payload, "expected_")
    reference_fx_rate = _money(payload.get("reference_fx_rate"))
    expected_fx_rate = _money(payload.get("expected_fx_rate"))
    evidence_ref = _clean(payload.get("evidence_ref"))
    unknown_components = [name for name, value in fees.items() if value is None]
    if source_currency != bank_currency and expected_fx_rate is None:
        unknown_components.append("expected_fx_rate")

    expected_bank_receipt: float | None = None
    fx_spread_loss: float | None = None
    if not unknown_components:
        net_source = source_amount - float(fees["provider_receiving_fee"] or 0.0) - float(
            fees["provider_withholding"] or 0.0
        )
        converted = (
            net_source
            if source_currency == bank_currency
            else net_source * float(expected_fx_rate or 0.0)
        )
        expected_bank_receipt = converted - sum(
            float(fees[name] or 0.0)
            for name in [
                "withdrawal_fee",
                "intermediary_bank_fee",
                "fixed_fee",
                "other_fee",
            ]
        )
        if (
            source_currency != bank_currency
            and reference_fx_rate is not None
            and expected_fx_rate is not None
        ):
            fx_spread_loss = net_source * max(0.0, reference_fx_rate - expected_fx_rate)

    estimate_id = "collection-estimate-" + uuid.uuid4().hex[:16]
    fields = {
        "estimate_id": estimate_id,
        "value_status": "estimate" if expected_bank_receipt is not None else "unknown",
        "scope": scope,
        "provider_id": provider.get("provider_id"),
        "provider_display_name": provider.get("display_name"),
        "provider_status": provider.get("status"),
        "oauth_connected": bool(provider.get("oauth_connected")),
        "account_alias": account_alias,
        "account_last4": account_last4,
        "account_identity": account_identity,
        "source_platform_settlement_amount": _round(source_amount),
        "source_currency": source_currency,
        "bank_currency": bank_currency,
        "expected_provider_receiving_fee": _round(fees["provider_receiving_fee"]),
        "expected_provider_withholding": _round(fees["provider_withholding"]),
        "reference_fx_rate": _round(reference_fx_rate, 8),
        "expected_fx_rate": _round(expected_fx_rate, 8),
        "expected_fx_spread_loss": _round(fx_spread_loss),
        "expected_withdrawal_fee": _round(fees["withdrawal_fee"]),
        "expected_intermediary_bank_fee": _round(fees["intermediary_bank_fee"]),
        "expected_fixed_fee": _round(fees["fixed_fee"]),
        "expected_other_fee": _round(fees["other_fee"]),
        "expected_bank_receipt": _round(expected_bank_receipt),
        "unknown_components": list(dict.fromkeys(unknown_components)),
        "evidence_ref": evidence_ref,
        "fee_values_are_owner_inputs": True,
        "actual_bank_receipt_is_canonical": False,
        "external_action_count": 0,
    }
    record = IntakeRecord(
        record_type="payment_collection_estimate",
        fields=fields,
        raw_text=json.dumps(fields, ensure_ascii=False, sort_keys=True),
        source="local_payment_collection_estimator",
        review_status="owner_review_required",
        confidence=0.65 if unknown_components else 0.8,
        metadata={
            "registry": str(COLLECTION_REGISTRY_PATH),
            "external_action_count": 0,
        },
    )
    append_record(root, record)
    event = append_business_event(
        root,
        {
            "event_type": "payment_collection_estimate_created",
            "kind": "draft",
            "project_id": scope.get("project_id"),
            "task_id": scope.get("task_id"),
            "conversation_id": scope.get("conversation_id"),
            "actor": actor,
            "statement": (
                f"已保存 {provider.get('display_name')} 到银行卡的本地估算；"
                f"预计实收 {fields['expected_bank_receipt']} {bank_currency}；"
                f"未知项 {len(fields['unknown_components'])}；外部动作 0。"
            ),
            "status": "owner_review_required",
            "business_object_refs": [
                {"type": "payment_collection_estimate", "id": estimate_id},
                {"type": "payment_collection_provider_registry", "id": str(COLLECTION_REGISTRY_PATH)},
            ],
            "payload": {
                "value_status": fields["value_status"],
                "estimate_id": estimate_id,
                "unknown_components": fields["unknown_components"],
                "external_action_count": 0,
            },
        },
        actor=actor,
    )
    return {"ok": True, "estimate": fields, "record_id": record.record_id, "event": event}


def import_collection_payout_statement(
    root: Path,
    payload: dict[str, Any],
    *,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    _reject_sensitive_collection_payload(payload)
    scope = _scope(payload)
    provider = _collection_provider(root, payload.get("provider_id"))
    account_alias, account_last4 = _collection_identity(payload)
    account_identity = _collection_identity_key(
        provider.get("provider_id"),
        account_alias,
        account_last4,
    )
    actual_bank_receipt = _money(payload.get("actual_bank_receipt"))
    evidence_ref = _clean(payload.get("evidence_ref"))
    if actual_bank_receipt is None:
        raise ValueError("请填写银行卡实际到账金额。")
    if not evidence_ref:
        raise ValueError("请提供收款机构账单或银行流水的凭证引用。")
    source_amount = _money(payload.get("source_platform_settlement_amount"))
    if source_amount is None:
        source_amount = _money(payload.get("actual_platform_settlement"))
    source_currency = _clean(payload.get("source_currency"), scope["currency"]).upper()
    bank_currency = _clean(payload.get("bank_currency"), source_currency).upper()
    fees = _collection_fee_values(payload, "actual_")
    reference_fx_rate = _money(payload.get("reference_fx_rate"))
    actual_fx_rate = _money(payload.get("actual_fx_rate"))
    statement_id = _clean(
        payload.get("statement_id"),
        "collection-statement-" + uuid.uuid4().hex[:16],
    )
    fields = {
        "statement_id": statement_id,
        "value_status": "actual_statement",
        "scope": scope,
        "provider_id": provider.get("provider_id"),
        "provider_display_name": provider.get("display_name"),
        "provider_status": provider.get("status"),
        "oauth_connected": bool(provider.get("oauth_connected")),
        "account_alias": account_alias,
        "account_last4": account_last4,
        "account_identity": account_identity,
        "source_platform_settlement_amount": _round(source_amount),
        "source_currency": source_currency,
        "bank_currency": bank_currency,
        "actual_provider_receiving_fee": _round(fees["provider_receiving_fee"]),
        "actual_provider_withholding": _round(fees["provider_withholding"]),
        "reference_fx_rate": _round(reference_fx_rate, 8),
        "actual_fx_rate": _round(actual_fx_rate, 8),
        "actual_withdrawal_fee": _round(fees["withdrawal_fee"]),
        "actual_intermediary_bank_fee": _round(fees["intermediary_bank_fee"]),
        "actual_fixed_fee": _round(fees["fixed_fee"]),
        "actual_other_fee": _round(fees["other_fee"]),
        "actual_bank_receipt": _round(actual_bank_receipt),
        "unknown_fee_components": [name for name, value in fees.items() if value is None],
        "evidence_ref": evidence_ref,
        "canonical_for_final_cash": True,
        "external_action_count": 0,
    }
    record = IntakeRecord(
        record_type="payment_collection_statement",
        fields=fields,
        raw_text=json.dumps(fields, ensure_ascii=False, sort_keys=True),
        source="local_payment_collection_statement_import",
        review_status="approved",
        confidence=0.92,
        metadata={"external_action_count": 0},
    )
    append_record(root, record)
    event = append_business_event(
        root,
        {
            "event_type": "payment_collection_statement_imported",
            "kind": "fact",
            "project_id": scope.get("project_id"),
            "task_id": scope.get("task_id"),
            "conversation_id": scope.get("conversation_id"),
            "actor": actor,
            "statement": (
                f"已导入 {provider.get('display_name')} / 银行流水 {statement_id}；"
                f"actual_bank_receipt {fields['actual_bank_receipt']} {bank_currency} "
                "是最终现金真值；外部动作 0。"
            ),
            "status": "recorded",
            "business_object_refs": [
                {"type": "payment_collection_statement", "id": statement_id}
            ],
            "payload": {
                "value_status": "actual_statement",
                "statement_id": statement_id,
                "actual_bank_receipt": fields["actual_bank_receipt"],
                "external_action_count": 0,
            },
        },
        actor=actor,
    )
    return {"ok": True, "statement": fields, "record_id": record.record_id, "event": event}


def reconcile_collection_payout(
    root: Path,
    payload: dict[str, Any],
    *,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    estimate_ref = _clean(payload.get("estimate_id") or payload.get("estimate_record_id"))
    statement_ref = _clean(payload.get("statement_id") or payload.get("statement_record_id"))
    if not estimate_ref or not statement_ref:
        raise ValueError("到账对账需要 estimate_id 和 statement_id。")
    estimate_record = _find_record_by_field(
        root,
        "payment_collection_estimate",
        "estimate_id",
        estimate_ref,
    )
    statement_record = _find_record_by_field(
        root,
        "payment_collection_statement",
        "statement_id",
        statement_ref,
    )
    if estimate_record is None:
        raise ValueError("没有找到对应的收款/提现估算。")
    if statement_record is None:
        raise ValueError("没有找到对应的收款机构或银行流水。")
    estimate = estimate_record.fields
    statement = statement_record.fields
    estimate_scope = estimate.get("scope") if isinstance(estimate.get("scope"), dict) else {}
    statement_scope = statement.get("scope") if isinstance(statement.get("scope"), dict) else {}
    mismatches: list[str] = []
    for field in ["project_id", "task_id"]:
        estimate_value = _clean(estimate_scope.get(field))
        statement_value = _clean(statement_scope.get(field))
        if estimate_value and statement_value and estimate_value != statement_value:
            mismatches.append(field)
    for field in ["provider_id", "account_identity", "source_currency", "bank_currency"]:
        estimate_value = _clean(estimate.get(field)).lower()
        statement_value = _clean(statement.get(field)).lower()
        if estimate_value and statement_value and estimate_value != statement_value:
            mismatches.append(field)
    if mismatches:
        raise ValueError(
            "收款到账估算与实收记录不属于同一条资金链路："
            + ", ".join(dict.fromkeys(mismatches))
        )
    expected_receipt = _money(estimate.get("expected_bank_receipt"))
    actual_receipt = _money(statement.get("actual_bank_receipt"))
    fee_diffs: list[dict[str, Any]] = []
    for component in [
        "provider_receiving_fee",
        "provider_withholding",
        "withdrawal_fee",
        "intermediary_bank_fee",
        "fixed_fee",
        "other_fee",
    ]:
        expected = _money(estimate.get(f"expected_{component}"))
        actual = _money(statement.get(f"actual_{component}"))
        fee_diffs.append(
            {
                "component": component,
                "expected_amount": _round(expected),
                "actual_amount": _round(actual),
                "difference": _round(actual - expected)
                if expected is not None and actual is not None
                else None,
                "value_status": "observation"
                if expected is not None and actual is not None
                else "unknown",
            }
        )
    reconciliation_id = "collection-recon-" + uuid.uuid4().hex[:16]
    scope = (
        statement.get("scope")
        if isinstance(statement.get("scope"), dict)
        else (
            estimate.get("scope")
            if isinstance(estimate.get("scope"), dict)
            else {}
        )
    )
    fields = {
        "reconciliation_id": reconciliation_id,
        "estimate_id": estimate.get("estimate_id"),
        "statement_id": statement.get("statement_id"),
        "scope": scope,
        "provider_id": statement.get("provider_id") or estimate.get("provider_id"),
        "account_identity": statement.get("account_identity") or estimate.get("account_identity"),
        "source_currency": statement.get("source_currency") or estimate.get("source_currency"),
        "bank_currency": statement.get("bank_currency") or estimate.get("bank_currency"),
        "value_status": "observation",
        "expected_bank_receipt": _round(expected_receipt),
        "actual_bank_receipt": _round(actual_receipt),
        "bank_receipt_difference": _round(actual_receipt - expected_receipt)
        if actual_receipt is not None and expected_receipt is not None
        else None,
        "fee_diffs": fee_diffs,
        "actual_bank_receipt_canonical": True,
        "next_action": (
            "把收款手续费、换汇、提现和中间行差异回写预算；"
            "actual_bank_receipt 永远覆盖估算。"
        ),
        "external_action_count": 0,
    }
    record = IntakeRecord(
        record_type="payment_collection_reconciliation",
        fields=fields,
        raw_text=json.dumps(fields, ensure_ascii=False, sort_keys=True),
        source="local_payment_collection_reconciliation",
        review_status="owner_review_required",
        confidence=0.88,
        metadata={"external_action_count": 0},
    )
    append_record(root, record)
    event = append_business_event(
        root,
        {
            "event_type": "payment_collection_reconciled",
            "kind": "observation",
            "project_id": scope.get("project_id"),
            "task_id": scope.get("task_id"),
            "conversation_id": scope.get("conversation_id") or scope.get("task_id"),
            "actor": actor,
            "statement": (
                f"已完成收款机构到银行卡的对账；实际实收 "
                f"{fields['actual_bank_receipt']} {fields['bank_currency']} 为真值；"
                f"差异 {fields['bank_receipt_difference']}；外部动作 0。"
            ),
            "status": "owner_review_required",
            "business_object_refs": [
                {"type": "payment_collection_reconciliation", "id": reconciliation_id},
                {"type": "payment_collection_estimate", "id": str(estimate.get("estimate_id") or "")},
                {"type": "payment_collection_statement", "id": str(statement.get("statement_id") or "")},
            ],
            "payload": {
                "value_status": "observation",
                "actual_bank_receipt_canonical": True,
                "external_action_count": 0,
            },
        },
        actor=actor,
    )
    return {"ok": True, "reconciliation": fields, "record_id": record.record_id, "event": event}


def finance_settlement_snapshot(
    root: Path,
    *,
    project_id: str = "",
    task_id: str = "",
    limit: int = 5,
) -> dict[str, Any]:
    def latest(record_type: str) -> list[dict[str, Any]]:
        rows = sorted(read_records(root, record_type), key=lambda item: item.created_at, reverse=True)
        if project_id or task_id:
            filtered: list[IntakeRecord] = []
            for record in rows:
                scope = record.fields.get("scope")
                if not isinstance(scope, dict):
                    continue
                if project_id and _clean(scope.get("project_id")) != _clean(project_id):
                    continue
                if task_id and _clean(scope.get("task_id")) != _clean(task_id):
                    continue
                filtered.append(record)
            rows = filtered
        return [
            {
                "record_id": record.record_id,
                "created_at": record.created_at,
                **record.fields,
            }
            for record in rows[:limit]
        ]

    projection = business_event_projection(
        root,
        project_id=project_id,
        task_id=task_id,
        conversation_id=task_id,
        limit=12,
    ) if task_id else {"total": 0, "events": []}
    latest_estimates = latest("platform_settlement_estimate")
    latest_statements = latest("platform_settlement_statement")
    latest_reconciliations = latest("platform_settlement_reconciliation")
    latest_inventory_cash_plans = latest("inventory_cash_plan")
    latest_collection_estimates = latest("payment_collection_estimate")
    latest_collection_statements = latest("payment_collection_statement")
    latest_collection_reconciliations = latest("payment_collection_reconciliation")

    # Import locally to keep the two ledgers independently usable while exposing
    # one project-scoped read model for the desktop finance surface.
    from .operating_expense_ledger import operating_expense_snapshot

    operating_expenses = operating_expense_snapshot(
        root,
        project_id=project_id,
        task_id=task_id,
    )
    platform_statement = latest_statements[0] if latest_statements else {}
    collection_statement = (
        latest_collection_statements[0] if latest_collection_statements else {}
    )
    platform_scope = platform_statement.get("scope")
    platform_currency = (
        _clean(platform_scope.get("currency"))
        if isinstance(platform_scope, dict)
        else ""
    )
    return {
        "schema_version": 1,
        "registry": platform_fee_registry_snapshot(root),
        "provider_registry": payment_collection_provider_registry_snapshot(root),
        "latest_estimates": latest_estimates,
        "latest_statements": latest_statements,
        "latest_reconciliations": latest_reconciliations,
        "latest_inventory_cash_plans": latest_inventory_cash_plans,
        "latest_collection_estimates": latest_collection_estimates,
        "latest_collection_statements": latest_collection_statements,
        "latest_collection_reconciliations": latest_collection_reconciliations,
        "operating_expenses": operating_expenses,
        "truth_layers": {
            "platform_operating_actual": {
                "source_record_type": "platform_settlement_statement",
                "canonical_field": "actual_platform_settlement",
                "latest_value": platform_statement.get(
                    "actual_platform_settlement"
                ),
                "currency": platform_currency,
                "canonical_when": "imported_platform_statement",
            },
            "cash_actual": {
                "source_record_type": "payment_collection_statement",
                "canonical_field": "actual_bank_receipt",
                "latest_value": collection_statement.get("actual_bank_receipt"),
                "currency": _clean(collection_statement.get("bank_currency")),
                "canonical_when": "imported_bank_receipt_with_evidence",
            },
            "management_operating_expense_actual": {
                "source_record_type": "operating_expense_entry",
                "canonical_field": "amount",
                "canonical_status": "posted_owner_confirmed",
                "totals_by_currency": operating_expenses.get(
                    "posted_expense_totals", {}
                ),
                "totals_by_category_currency": operating_expenses.get(
                    "posted_expense_totals_by_category_currency", {}
                ),
                "fee_totals_by_currency": operating_expenses.get(
                    "posted_fee_totals", {}
                ),
            },
        },
        "truth_layer_separation": {
            "cross_deduction": False,
            "rule": (
                "Platform settlement, bank receipt, and owner-confirmed "
                "management operating expenses remain separate ledgers."
            ),
        },
        "event_projection": projection,
        "external_action_count": 0,
    }


def run_fictional_finance_demo(
    root: Path,
    payload: dict[str, Any] | None = None,
    *,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    data = dict(payload or {})
    scope = {
        "platform": data.get("platform") or "TikTok Shop",
        "site": data.get("site") or "US",
        "store_mode": data.get("store_mode") or "local_store",
        "category": data.get("category") or "apparel",
        "order_type": data.get("order_type") or "activity_attributed_order",
        "activity": data.get("activity") or "fictional_activity_demo",
        "promotion": data.get("promotion") or "seller_coupon",
        "fulfillment": data.get("fulfillment") or "seller_fulfilled",
        "effective_from": data.get("effective_from") or date.today().isoformat(),
        "currency": data.get("currency") or "USD",
        "tax_treatment": data.get("tax_treatment") or "sample_unknown",
        "project_id": data.get("project_id") or "",
        "task_id": data.get("task_id") or "",
        "conversation_id": data.get("conversation_id") or data.get("task_id") or "",
        "product_id": data.get("product_id") or "fictional-sku-001",
        "evidence": {"source_type": "formal_app_fictional_demo", "status": "sample_not_platform_rule"},
        "status": "sample_not_platform_rule",
    }
    estimate_result = save_pre_operation_estimate(
        root,
        {
            "scope": scope,
            "sample_not_platform_rule": True,
            "economics": {
                "units": 20,
                "unit_price": 25,
                "unit_product_cost": 7,
                "unit_packaging_cost": 1,
                "seller_discount_unit": 2,
                "platform_subsidy_total": 10,
                "commission_fee_rate": 0.06,
                "transaction_fee_rate": 0.025,
                "payment_fee": 6,
                "activity_fee": 8,
                "affiliate_fee_rate": 0.04,
                "ad_spend": 60,
                "shipping_fee": 36,
                "storage_fee": 5,
                "tax": 0,
                "refund_reserve": 15,
                "current_inventory": 12,
                "lead_time_days": 12,
                "safety_stock_days": 5,
                "activity_uplift": 0.35,
                "return_rate": 0.08,
            },
        },
        actor=actor,
    )
    estimate = estimate_result["estimate"]
    statement_result = import_platform_settlement_statement(
        root,
        {
            "scope": scope,
            "statement_id": "fictional-statement-" + uuid.uuid4().hex[:10],
            "sample_not_platform_rule": True,
            "lines": [
                {"component": "gross_revenue", "amount": 500, "currency": "USD", "notes": "fictional GMV"},
                {"component": "seller_discount", "amount": -40, "currency": "USD"},
                {"component": "platform_subsidy", "amount": 12, "currency": "USD"},
                {"component": "commission_fee", "amount": -31, "currency": "USD"},
                {"component": "transaction_fee", "amount": -13, "currency": "USD"},
                {"component": "payment_fee", "amount": -6, "currency": "USD"},
                {"component": "activity_service_fee", "amount": -10, "currency": "USD"},
                {"component": "affiliate_creator_fee", "amount": -22, "currency": "USD"},
                {"component": "advertising_spend", "amount": -60, "currency": "USD"},
                {"component": "logistics_fee", "amount": -38, "currency": "USD"},
                {"component": "tax_withholding", "amount": 0, "currency": "USD"},
                {"component": "refund_return_reserve", "amount": -16, "currency": "USD"},
                {"component": "other_adjustment", "amount": 2, "currency": "USD"},
            ],
        },
        actor=actor,
    )
    reconciliation_result = reconcile_estimate_with_statement(
        root,
        {
            "estimate_id": estimate["estimate_id"],
            "statement_id": statement_result["statement"]["statement_id"],
        },
        actor=actor,
    )
    return {
        "ok": True,
        "estimate": estimate_result["estimate"],
        "statement": statement_result["statement"],
        "reconciliation": reconciliation_result["reconciliation"],
        "snapshot": finance_settlement_snapshot(
            root,
            project_id=str(scope.get("project_id") or ""),
            task_id=str(scope.get("task_id") or ""),
        ),
        "sample_not_platform_rule": True,
        "external_action_count": 0,
    }
