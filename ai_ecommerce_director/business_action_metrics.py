from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REGISTRY_PATH = Path("config") / "ai_analytics_data_foundation_registry.json"


def _clean(value: Any, limit: int = 160) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def load_business_action_metric_dictionary(
    root: Path, *, strict: bool = False
) -> dict[str, Any]:
    path = root / REGISTRY_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        if strict:
            raise
        return {}
    dictionary = (
        payload.get("business_action_metric_dictionary")
        if isinstance(payload, dict)
        else {}
    )
    if isinstance(dictionary, dict):
        return dictionary
    if strict:
        raise ValueError("business_action_metric_dictionary must be an object")
    return {}


def resolve_business_action_metric_contract(
    root: Path, event_type: Any
) -> dict[str, Any]:
    """Resolve one recorded action to its business object and metric semantics."""

    clean_event_type = _clean(event_type, 120).lower()
    if not clean_event_type:
        return {}
    dictionary = load_business_action_metric_dictionary(root)
    contracts = dictionary.get("contracts")
    contracts = contracts if isinstance(contracts, list) else []
    for item in contracts:
        if not isinstance(item, dict):
            continue
        exact = {
            _clean(value, 120).lower()
            for value in item.get("event_types", [])
            if _clean(value, 120)
        }
        prefixes = [
            _clean(value, 120).lower()
            for value in item.get("event_type_prefixes", [])
            if _clean(value, 120)
        ]
        if clean_event_type not in exact and not any(
            clean_event_type.startswith(prefix) for prefix in prefixes
        ):
            continue
        return {
            "contract_id": _clean(item.get("id"), 120),
            "event_type": clean_event_type,
            "action_scope": _clean(item.get("action_scope"), 120),
            "target_object_type": _clean(item.get("target_object_type"), 120),
            "metric_ids": [
                _clean(value, 120)
                for value in item.get("metric_ids", [])
                if _clean(value, 120)
            ],
            "truth_rule": _clean(item.get("truth_rule"), 240),
            "external_action": bool(item.get("external_action")),
            "owner_gate": bool(item.get("owner_gate")),
        }
    return {}


def validate_business_action_metric_dictionary(root: Path) -> list[str]:
    errors: list[str] = []
    dictionary = load_business_action_metric_dictionary(root, strict=True)
    contracts = dictionary.get("contracts")
    if not isinstance(contracts, list) or not contracts:
        return ["business action metric contracts must be a non-empty list"]

    analytics = json.loads((root / REGISTRY_PATH).read_text(encoding="utf-8"))
    known_metrics = {
        str(metric)
        for family in analytics.get("metric_families", [])
        if isinstance(family, dict)
        for metric in family.get("metrics", [])
        if str(metric).strip()
    }
    ids: set[str] = set()
    mapped_event_types: set[str] = set()
    for index, item in enumerate(contracts):
        prefix = f"contracts[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        contract_id = _clean(item.get("id"), 120)
        if not contract_id:
            errors.append(f"{prefix}.id is required")
        elif contract_id in ids:
            errors.append(f"duplicate contract id: {contract_id}")
        ids.add(contract_id)
        event_types = [
            _clean(value, 120).lower()
            for value in item.get("event_types", [])
            if _clean(value, 120)
        ]
        event_prefixes = [
            _clean(value, 120).lower()
            for value in item.get("event_type_prefixes", [])
            if _clean(value, 120)
        ]
        if not event_types and not event_prefixes:
            errors.append(f"{prefix} must map event_types or event_type_prefixes")
        for event_type in event_types:
            if event_type in mapped_event_types:
                errors.append(f"event type mapped more than once: {event_type}")
            mapped_event_types.add(event_type)
        for field in ("action_scope", "target_object_type", "truth_rule"):
            if not _clean(item.get(field), 240):
                errors.append(f"{prefix}.{field} is required")
        metric_ids = [
            _clean(value, 120)
            for value in item.get("metric_ids", [])
            if _clean(value, 120)
        ]
        if not metric_ids:
            errors.append(f"{prefix}.metric_ids must not be empty")
        unknown_metrics = sorted(set(metric_ids).difference(known_metrics))
        if unknown_metrics:
            errors.append(
                f"{prefix}.metric_ids contain unknown metrics: "
                + ", ".join(unknown_metrics)
            )
        if item.get("external_action") and not item.get("owner_gate"):
            errors.append(f"{prefix} external actions require owner_gate=true")

    required_event_types = {
        _clean(value, 120).lower()
        for value in dictionary.get("required_runtime_event_types", [])
        if _clean(value, 120)
    }
    for event_type in sorted(required_event_types):
        if not resolve_business_action_metric_contract(root, event_type):
            errors.append(f"required runtime event type is unmapped: {event_type}")
    if dictionary.get("external_actions") != 0:
        errors.append("business_action_metric_dictionary.external_actions must be 0")
    return errors
