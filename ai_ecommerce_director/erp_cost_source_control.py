from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


POLICY_RELATIVE_PATH = Path("config") / "erp_cost_source_control.json"
STATE_RELATIVE_PATH = Path("data") / "erp_cost_source_runtime.json"
ERP_REGISTRY_RELATIVE_PATH = Path("data") / "private" / "erp_connectors.json"
MAX_ROWS = 240
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
COUNTRY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,15}$")
CURRENCY = re.compile(r"^[A-Za-z]{3}$")
SENSITIVE_OR_VALUE_KEYS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "api_key",
    "password",
    "cookie",
    "authorization",
    "unit_cost",
    "cost_value",
    "cost_amount",
    "supplier_price",
    "invoice_amount",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path, default: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    return value


def _default_policy() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "scope": "non_amazon_local_read_only_preflight",
        "paused_scope": ["amazon_sp_api", "amazon_ads_api", "amazon_product_type_definitions"],
        "required_erp_route": [
            "tenant_id",
            "project_id",
            "store_binding_id",
            "platform",
            "country_site",
            "store_model",
            "ownership",
            "execution_identity_id",
            "erp_connector_ref",
        ],
        "required_cost_evidence": [
            "tenant_id",
            "project_id",
            "product_id",
            "variant_scope_ref",
            "currency",
            "cost_basis",
            "cost_source_type",
            "cost_source_ref",
            "verified_at_ref",
        ],
        "cost_source_types": [
            "product_import",
            "factory_bom",
            "erp_read_only",
            "supplier_quote",
            "fulfillment_invoice",
            "settlement_report",
        ],
        "cost_components": [],
        "local_actions": [
            "inspect_local_state",
            "prepare_non_amazon_erp_packet",
            "prepare_cost_source_packet",
        ],
        "blocked_actions": [
            "connect_erp",
            "fetch_erp_private_data",
            "save_cost_values",
            "claim_profit_ready",
            "run_amazon_sp_api",
            "run_amazon_ads_api",
            "run_amazon_ptd",
        ],
        "hard_boundaries": [],
    }


def _policy(root: Path) -> dict[str, Any]:
    value = _read_json(root / POLICY_RELATIVE_PATH, _default_policy())
    if not isinstance(value, dict) or not isinstance(value.get("required_erp_route"), list):
        raise ValueError("ERP and cost-source control policy is invalid.")
    return value


def _state(root: Path) -> dict[str, Any]:
    value = _read_json(
        root / STATE_RELATIVE_PATH,
        {"schema_version": 1, "audits": [], "reviews": []},
    )
    if not isinstance(value, dict):
        value = {"schema_version": 1, "audits": [], "reviews": []}
    for key in ("audits", "reviews"):
        if not isinstance(value.get(key), list):
            value[key] = []
    value["schema_version"] = 1
    return value


def _save_state(root: Path, state: dict[str, Any]) -> None:
    path = root / STATE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    for key in ("audits", "reviews"):
        state[key] = list(state.get(key) or [])[-MAX_ROWS:]
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _sensitive_or_value_field(value: Any, path: str = "request") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().casefold()
            if normalized in SENSITIVE_OR_VALUE_KEYS or normalized.endswith("_secret"):
                return f"{path}.{key}"
            found = _sensitive_or_value_field(child, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _sensitive_or_value_field(child, f"{path}[{index}]")
            if found:
                return found
    return None


def _clean_identifier(value: Any, label: str, *, required: bool = False) -> str:
    text = str(value or "").strip()
    if not text and not required:
        return ""
    if not IDENTIFIER.fullmatch(text):
        raise ValueError(f"{label} must be a stable internal identifier.")
    return text


def _workspace_snapshot(root: Path) -> dict[str, Any]:
    payload = _read_json(root / "config" / "workspace_projects.json", {})
    projects = payload.get("projects") if isinstance(payload, dict) else []
    if not isinstance(projects, list):
        projects = []
    non_amazon_channels: list[dict[str, Any]] = []
    non_amazon_stores: list[dict[str, Any]] = []
    for project in projects:
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id") or "")
        for channel in project.get("channels") or []:
            if not isinstance(channel, dict):
                continue
            platform = str(channel.get("platform") or "").strip().casefold()
            if not platform or platform == "amazon":
                continue
            stores = [item for item in channel.get("stores") or [] if isinstance(item, dict)]
            non_amazon_channels.append(
                {
                    "project_id": project_id,
                    "channel_id": str(channel.get("id") or ""),
                    "name": str(channel.get("name") or channel.get("id") or ""),
                    "platform": platform,
                    "country_site": str(channel.get("country_site") or "GLOBAL").upper(),
                    "status": str(channel.get("status") or "unknown"),
                    "store_count": len(stores),
                    "required_dimensions": [str(item) for item in channel.get("required_dimensions") or []],
                }
            )
            for store in stores:
                non_amazon_stores.append(
                    {
                        "project_id": project_id,
                        "channel_id": str(channel.get("id") or ""),
                        "store_binding_id": str(store.get("id") or ""),
                        "platform": platform,
                        "country_site": str(channel.get("country_site") or "GLOBAL").upper(),
                        "store_model": str(store.get("store_model") or ""),
                        "ownership": str(store.get("ownership") or ""),
                        "execution_identity_configured": bool(store.get("execution_identity_id")),
                        "erp_connector_ref_configured": bool(store.get("erp_connector_id")),
                    }
                )
    return {
        "non_amazon_channels": non_amazon_channels,
        "non_amazon_stores": non_amazon_stores,
        "non_amazon_channel_count": len(non_amazon_channels),
        "needs_platform_store_count": sum(
            1 for item in non_amazon_channels if item["status"] == "needs_platform_store"
        ),
        "non_amazon_store_count": len(non_amazon_stores),
    }


def _intent_snapshot(root: Path) -> dict[str, Any]:
    payload = _read_json(root / "config" / "channel_route_requests.json", {})
    requests = payload.get("requests") if isinstance(payload, dict) else []
    if not isinstance(requests, list):
        requests = []
    rows = []
    for item in requests:
        if not isinstance(item, dict):
            continue
        platform = str(item.get("channel_id") or "").strip().casefold()
        if platform == "amazon":
            continue
        rows.append(
            {
                "request_id": str(item.get("request_id") or ""),
                "platform": platform,
                "country_site": str(item.get("country_code") or "GLOBAL").upper(),
                "store_model": str(item.get("store_model") or ""),
                "intent": str(item.get("intent") or ""),
                "execution_ready": False,
            }
        )
    return {"rows": rows, "count": len(rows), "execution_ready_count": 0}


def _erp_registry_snapshot(root: Path) -> dict[str, Any]:
    payload = _read_json(root / ERP_REGISTRY_RELATIVE_PATH, {})
    connectors = payload.get("connectors") if isinstance(payload, dict) else []
    if not isinstance(connectors, list):
        connectors = []
    rows = []
    now = datetime.now(timezone.utc).astimezone()
    for item in connectors:
        if not isinstance(item, dict):
            continue
        platform = str(item.get("platform") or "").strip().casefold()
        if platform == "amazon":
            continue
        expires_text = str(item.get("verification_expires_at") or "")
        fresh = False
        try:
            expires = datetime.fromisoformat(expires_text.replace("Z", "+00:00"))
            fresh = expires.astimezone(timezone.utc) > now.astimezone(timezone.utc)
        except ValueError:
            fresh = False
        live = (
            str(item.get("verification_status") or "").casefold() == "live_verified"
            and fresh
        )
        rows.append(
            {
                "id": str(item.get("id") or ""),
                "platform": platform,
                "country_site": str(item.get("country_site") or "GLOBAL").upper(),
                "store_binding_id": str(item.get("store_binding_id") or ""),
                "status": "live_verified" if live else "verification_required",
                "fresh": live,
            }
        )
    return {
        "registry_file_present": (root / ERP_REGISTRY_RELATIVE_PATH).exists(),
        "rows": rows,
        "registered_count": len(rows),
        "live_verified_count": sum(1 for item in rows if item["fresh"]),
    }


def _cost_catalog_snapshot(root: Path) -> dict[str, Any]:
    catalogs = sorted((root / "data" / "product_intake").glob("**/catalog.json"))
    catalog_rows: list[dict[str, Any]] = []
    total_records = 0
    cost_filled = 0
    price_filled = 0
    inventory_filled = 0
    for path in catalogs:
        payload = _read_json(path, {})
        if not isinstance(payload, dict):
            continue
        records = [item for item in payload.get("records") or [] if isinstance(item, dict)]
        local_cost = 0
        local_price = 0
        local_inventory = 0
        for record in records:
            fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
            local_cost += int(bool(str(fields.get("cost") or "").strip()))
            local_price += int(bool(str(fields.get("price") or "").strip()))
            local_inventory += int(bool(str(fields.get("inventory") or "").strip()))
        total_records += len(records)
        cost_filled += local_cost
        price_filled += local_price
        inventory_filled += local_inventory
        catalog_rows.append(
            {
                "project_id": str(payload.get("project_id") or ""),
                "catalog_ref": str(path.relative_to(root)).replace("\\", "/"),
                "record_count": len(records),
                "cost_filled_count": local_cost,
                "price_filled_count": local_price,
                "inventory_filled_count": local_inventory,
                "cost_source_verified_count": 0,
            }
        )
    return {
        "catalogs": catalog_rows,
        "catalog_count": len(catalog_rows),
        "record_count": total_records,
        "cost_field_filled_count": cost_filled,
        "price_field_filled_count": price_filled,
        "inventory_field_filled_count": inventory_filled,
        "verified_cost_source_count": 0,
    }


def _configured_store_data_sources(root: Path) -> dict[str, Any]:
    payload = _read_json(root / "config" / "store_data_sources.json", {})
    sources = payload.get("sources") if isinstance(payload, dict) else []
    rows = []
    for item in sources or []:
        if not isinstance(item, dict):
            continue
        platform = str(item.get("source_platform") or "").strip().casefold()
        if platform == "amazon":
            continue
        rows.append(
            {
                "id": str(item.get("id") or ""),
                "platform": platform,
                "enabled": bool(item.get("enabled")),
                "requires_login": bool(item.get("requires_login")),
                "verified_read_receipt": False,
            }
        )
    return {
        "rows": rows,
        "configured_count": len(rows),
        "enabled_count": sum(1 for item in rows if item["enabled"]),
        "verified_read_count": 0,
    }


def erp_cost_source_snapshot(root: Path) -> dict[str, Any]:
    policy = _policy(root)
    state = _state(root)
    return {
        "schema_version": 1,
        "scope": policy.get("scope"),
        "paused_scope": list(policy.get("paused_scope") or []),
        "required_erp_route": list(policy.get("required_erp_route") or []),
        "required_cost_evidence": list(policy.get("required_cost_evidence") or []),
        "cost_source_types": list(policy.get("cost_source_types") or []),
        "cost_components": list(policy.get("cost_components") or []),
        "local_actions": list(policy.get("local_actions") or []),
        "blocked_actions": list(policy.get("blocked_actions") or []),
        "hard_boundaries": list(policy.get("hard_boundaries") or []),
        "workspace": _workspace_snapshot(root),
        "channel_intents": _intent_snapshot(root),
        "erp_registry": _erp_registry_snapshot(root),
        "cost_catalog": _cost_catalog_snapshot(root),
        "store_data_sources": _configured_store_data_sources(root),
        "external_connection_count": 0,
        "external_read_count": 0,
        "cost_value_write_count": 0,
        "profit_ready_claim_count": 0,
        "audits": list(state.get("audits") or [])[-20:][::-1],
        "reviews": list(state.get("reviews") or [])[-20:][::-1],
    }


def _base(status: str, *, allowed: bool, missing: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "missing": list(missing or []),
        "local_action_allowed": allowed,
        "erp_connection_performed": False,
        "private_data_fetched": False,
        "cost_values_saved": False,
        "profit_ready_claimed": False,
        "amazon_api_called": False,
        "external_action_count": 0,
    }


def _find_store(snapshot: dict[str, Any], store_binding_id: str) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in snapshot["workspace"]["non_amazon_stores"]
            if item.get("store_binding_id") == store_binding_id
        ),
        None,
    )


def evaluate_erp_cost_source_request(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ValueError("ERP/cost-source request must be an object.")
    if _sensitive_or_value_field(request):
        result = _base("blocked_sensitive_or_cost_value_input", allowed=False)
        result["error"] = "Raw credentials and cost values are not accepted by this metadata-only control plane."
        return result
    snapshot = erp_cost_source_snapshot(root)
    action = str(request.get("action") or "inspect_local_state").strip().casefold()
    if action in {"run_amazon_sp_api", "run_amazon_ads_api", "run_amazon_ptd"}:
        result = _base("blocked_amazon_scope_paused", allowed=False, missing=["owner_resume_amazon_scope"])
        result["error"] = "Amazon SP-API, Ads API and PTD remain paused by owner instruction."
        return result
    if action == "inspect_local_state":
        result = _base("local_state_review_ready", allowed=True)
        result["snapshot"] = {
            "non_amazon_channel_count": snapshot["workspace"]["non_amazon_channel_count"],
            "needs_platform_store_count": snapshot["workspace"]["needs_platform_store_count"],
            "non_amazon_store_count": snapshot["workspace"]["non_amazon_store_count"],
            "channel_intent_count": snapshot["channel_intents"]["count"],
            "live_verified_erp_count": snapshot["erp_registry"]["live_verified_count"],
            "catalog_record_count": snapshot["cost_catalog"]["record_count"],
            "cost_field_filled_count": snapshot["cost_catalog"]["cost_field_filled_count"],
            "verified_cost_source_count": snapshot["cost_catalog"]["verified_cost_source_count"],
        }
        result["missing"] = ["real_non_amazon_store", "live_verified_erp", "verified_real_cost_source"]
        return result
    if action in set(snapshot["blocked_actions"]):
        result = _base(
            "blocked_external_or_unverified_action",
            allowed=False,
            missing=["separate_owner_action", "exact_store_or_product_scope", "verified_source_receipt"],
        )
        result["error"] = "External ERP connection/read, cost writes and profit-ready claims require separately verified evidence and approval."
        return result
    if action == "prepare_non_amazon_erp_packet":
        required = list(snapshot["required_erp_route"])
        missing = [field for field in required if not str(request.get(field) or "").strip()]
        if missing:
            return _base("blocked_missing_erp_route", allowed=False, missing=missing)
        platform = str(request.get("platform") or "").strip().casefold()
        if platform == "amazon":
            return _base("blocked_amazon_scope_paused", allowed=False, missing=["non_amazon_platform"])
        country = str(request.get("country_site") or "").strip().upper()
        if not COUNTRY.fullmatch(country):
            raise ValueError("country_site must be a stable site code.")
        store_id = _clean_identifier(request.get("store_binding_id"), "store_binding_id", required=True)
        store = _find_store(snapshot, store_id)
        if not store:
            return _base(
                "blocked_store_not_found",
                allowed=False,
                missing=["real_non_amazon_platform_store", "store_binding_id"],
            )
        comparisons = {
            "project_id": str(request.get("project_id") or ""),
            "platform": platform,
            "country_site": country,
            "store_model": str(request.get("store_model") or "").strip().casefold(),
            "ownership": str(request.get("ownership") or "").strip().casefold(),
        }
        mismatches = [key for key, value in comparisons.items() if value != str(store.get(key) or "").strip().casefold()]
        if mismatches:
            return _base("blocked_store_route_mismatch", allowed=False, missing=[f"exact_{key}" for key in mismatches])
        packet = {
            field: _clean_identifier(request.get(field), field, required=True)
            for field in required
            if field != "country_site"
        }
        packet["country_site"] = country
        packet.update(
            {
                "connector_state": "reference_only_not_verified",
                "external_connection_state": "not_performed",
                "private_read_state": "not_performed",
                "owner_authorization_required": True,
            }
        )
        result = _base("local_erp_metadata_packet_ready", allowed=True)
        result["packet"] = packet
        return result
    if action == "prepare_cost_source_packet":
        required = list(snapshot["required_cost_evidence"])
        missing = [field for field in required if not str(request.get(field) or "").strip()]
        if missing:
            return _base("blocked_missing_cost_evidence", allowed=False, missing=missing)
        source_type = str(request.get("cost_source_type") or "").strip().casefold()
        if source_type not in set(snapshot["cost_source_types"]):
            return _base("blocked_unknown_cost_source_type", allowed=False, missing=["reviewed_cost_source_type"])
        currency = str(request.get("currency") or "").strip().upper()
        if not CURRENCY.fullmatch(currency):
            raise ValueError("currency must be a three-letter ISO-style code.")
        packet = {
            field: _clean_identifier(request.get(field), field, required=True)
            for field in required
            if field != "currency"
        }
        packet.update(
            {
                "currency": currency,
                "source_state": "metadata_only_not_verified",
                "cost_value_state": "not_accepted_or_saved",
                "profit_state": "not_ready",
                "owner_verification_required": True,
            }
        )
        result = _base("local_cost_source_metadata_packet_ready", allowed=True)
        result["packet"] = packet
        return result
    raise ValueError("Unknown ERP/cost-source action.")


def run_erp_cost_source_audit(root: Path, payload: dict[str, Any], *, actor: str = "owner") -> dict[str, Any]:
    request = payload.get("request") if isinstance(payload.get("request"), dict) else payload
    result = evaluate_erp_cost_source_request(root, request)
    safe_request = {
        key: request.get(key)
        for key in (
            "action",
            "tenant_id",
            "project_id",
            "store_binding_id",
            "platform",
            "country_site",
            "store_model",
            "ownership",
            "execution_identity_id",
            "erp_connector_ref",
            "product_id",
            "variant_scope_ref",
            "currency",
            "cost_basis",
            "cost_source_type",
            "cost_source_ref",
            "verified_at_ref",
        )
        if request.get(key) not in (None, "")
    }
    audit = {
        "id": f"erp-cost-audit-{uuid4().hex[:16]}",
        "created_at": _now(),
        "actor": str(actor or "owner")[:120],
        "request": safe_request,
        "result": result,
    }
    state = _state(root)
    state["audits"].append(audit)
    _save_state(root, state)
    return {"ok": True, "audit": audit}


def record_erp_cost_source_review(root: Path, payload: dict[str, Any], *, actor: str = "owner") -> dict[str, Any]:
    audit_id = _clean_identifier(payload.get("audit_id"), "audit_id", required=True)
    state = _state(root)
    if not any(item.get("id") == audit_id for item in state["audits"]):
        raise ValueError("ERP/cost-source audit not found.")
    review = {
        "id": f"erp-cost-review-{uuid4().hex[:16]}",
        "created_at": _now(),
        "actor": str(actor or "owner")[:120],
        "audit_id": audit_id,
        "evidence_source": str(payload.get("evidence_source") or "formal_app_manual")[:120],
        "evidence_ref": str(payload.get("evidence_ref") or f"formal-app:{audit_id}")[:240],
        "erp_connection_observed": False,
        "private_data_fetch_observed": False,
        "cost_value_write_observed": False,
        "profit_ready_claim_observed": False,
        "amazon_api_call_observed": False,
        "causal_conclusion": "inconclusive",
    }
    state["reviews"].append(review)
    _save_state(root, state)
    return {"ok": True, "review": review}


__all__ = [
    "erp_cost_source_snapshot",
    "evaluate_erp_cost_source_request",
    "record_erp_cost_source_review",
    "run_erp_cost_source_audit",
]
