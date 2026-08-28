from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


TIKTOK_FACT_CLASSES = frozenset(
    {
        "first_party_shop_fact",
        "official_api_unscoped_observation",
        "official_public_rule",
        "public_observation",
        "vendor_estimate",
        "private_user_evidence",
    }
)
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
IANA_TIMEZONE_PATTERN = re.compile(r"^[A-Za-z]+(?:[._+-][A-Za-z0-9]+)*/[A-Za-z0-9]+(?:[._+-][A-Za-z0-9]+)*$")


class TikTokShopRouteError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _required(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise TikTokShopRouteError(f"missing_{field}", f"{field} is required")
    return result


def _validate_iana_timezone(value: Any) -> str:
    """Validate an IANA key without making Windows depend on an undeclared tzdata wheel."""
    timezone_name = _required(value, "timezone")
    if not IANA_TIMEZONE_PATTERN.fullmatch(timezone_name):
        raise TikTokShopRouteError("invalid_timezone", "timezone must be an IANA timezone")
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        try:
            ZoneInfo("UTC")
        except ZoneInfoNotFoundError:
            return "iana_syntax_only_tzdb_unavailable"
        raise TikTokShopRouteError("invalid_timezone", "timezone must be an IANA timezone") from exc
    return "iana_tzdb_verified"


def build_tiktok_shop_fact(
    *,
    fact_class: str,
    fact_name: str,
    value: Any,
    evidence_ref: str,
    observed_at: datetime | str,
    shop_context: Mapping[str, Any] | None = None,
    attribution_definition: str = "",
) -> dict[str, Any]:
    classification = _required(fact_class, "fact_class")
    if classification not in TIKTOK_FACT_CLASSES:
        raise TikTokShopRouteError("unsupported_fact_class", "fact_class is not recognized")
    context = dict(shop_context or {})
    route_fields = (
        "shop_id",
        "region",
        "seller_type",
        "currency",
        "timezone",
        "connector_binding_id",
    )
    if classification == "first_party_shop_fact":
        missing = [field for field in route_fields if not str(context.get(field) or "").strip()]
        if missing:
            raise TikTokShopRouteError("first_party_fact_missing_shop_provenance", ",".join(missing))
        currency = str(context["currency"]).strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise TikTokShopRouteError("invalid_currency", "currency must be an ISO-style three-letter code")
        timezone_validation = _validate_iana_timezone(context["timezone"])
        if not str(attribution_definition or "").strip():
            raise TikTokShopRouteError("missing_attribution_definition", "first-party metrics require attribution definition")
    fact = {
        "fact_class": classification,
        "fact_name": _required(fact_name, "fact_name"),
        "value": value,
        "evidence_ref": _required(evidence_ref, "evidence_ref"),
        "observed_at": str(observed_at),
        "shop_provenance": {field: str(context.get(field) or "").strip() for field in route_fields},
        "attribution_definition": str(attribution_definition or "").strip(),
        "timezone_validation": timezone_validation if classification == "first_party_shop_fact" else "not_required",
        "execution_authority": classification == "first_party_shop_fact",
        "may_override_first_party_shop_fact": classification == "first_party_shop_fact",
    }
    if classification in {"official_api_unscoped_observation", "official_public_rule", "public_observation", "vendor_estimate"}:
        fact["execution_authority"] = False
        fact["may_override_first_party_shop_fact"] = False
    return fact


def resolve_exact_tiktok_shop_binding(
    bindings: Sequence[Mapping[str, Any]],
    *,
    shop_id: str,
    region: str,
    seller_type: str,
    currency: str,
    timezone_name: str,
    connector_binding_id: str,
) -> dict[str, Any]:
    requested = {
        "shop_id": _required(shop_id, "shop_id"),
        "region": _required(region, "region").upper(),
        "seller_type": _required(seller_type, "seller_type").upper(),
        "currency": _required(currency, "currency").upper(),
        "timezone": _required(timezone_name, "timezone"),
        "connector_binding_id": _required(connector_binding_id, "connector_binding_id"),
    }
    if requested["region"] in {"SEA", "EU", "GLOBAL"}:
        raise TikTokShopRouteError("broad_region_not_executable", "select one exact TikTok Shop region")
    matches: list[dict[str, Any]] = []
    for binding in bindings:
        if not isinstance(binding, Mapping):
            continue
        candidate = {
            "shop_id": str(binding.get("shop_id") or "").strip(),
            "region": str(binding.get("region") or "").strip().upper(),
            "seller_type": str(binding.get("seller_type") or "").strip().upper(),
            "currency": str(binding.get("currency") or "").strip().upper(),
            "timezone": str(binding.get("timezone") or "").strip(),
            "connector_binding_id": str(binding.get("connector_binding_id") or "").strip(),
        }
        if candidate != requested:
            continue
        if str(binding.get("binding_source") or "").strip() != "authorized_shop_response":
            continue
        if not str(binding.get("evidence_ref") or "").strip() or not str(binding.get("verified_at") or "").strip():
            continue
        matches.append(dict(binding))
    if not matches:
        raise TikTokShopRouteError("exact_shop_binding_not_found", "no exact authorized TikTok Shop binding matched")
    if len(matches) > 1:
        raise TikTokShopRouteError("duplicate_exact_shop_binding", "multiple exact bindings must be reconciled before execution")
    return {
        **matches[0],
        "route_match": "exact_only",
        "fuzzy_matching_used": False,
        "default_first_store_used": False,
        "route_key": ":".join(requested.values()),
    }


def tiktok_shop_retry_policy(
    *,
    method: str,
    action: str,
    idempotency_key: str = "",
    ambiguous_result: bool = False,
) -> dict[str, Any]:
    normalized_method = _required(method, "method").upper()
    normalized_action = _required(action, "action")
    write_operation = normalized_method in WRITE_METHODS
    if write_operation:
        return {
            "action": normalized_action,
            "method": normalized_method,
            "operation_class": "write",
            "automatic_retry_allowed": False,
            "idempotency_key_present": bool(str(idempotency_key or "").strip()),
            "state": "blocked_missing_idempotency_key" if not str(idempotency_key or "").strip() else (
                "ambiguous_write_requires_readback_and_owner_review" if ambiguous_result else "single_attempt_owner_gated"
            ),
            "required_recovery": "read current shop state, preserve request/receipt, reconcile ambiguity, then request a new item-level approval",
            "external_action_executed": False,
        }
    return {
        "action": normalized_action,
        "method": normalized_method,
        "operation_class": "read",
        "automatic_retry_allowed": normalized_method == "GET",
        "max_transient_retries": 2 if normalized_method == "GET" else 0,
        "state": "bounded_read_retry_only" if normalized_method == "GET" else "no_automatic_retry",
        "external_action_executed": False,
    }
