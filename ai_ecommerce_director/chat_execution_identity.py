"""Safe store/browser execution identity projection for local seller chat."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .account import load_profile
from .channel_routes import (
    infer_store_ownership_for_route,
    normalize_store_model_for_route,
)


_SAFE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")


def _text(value: Any, limit: int = 160) -> str:
    return str(value or "").strip()[:limit]


def _reference(value: Any) -> str:
    text = _text(value)
    return text if _SAFE_REFERENCE.fullmatch(text) else ""


def _same(left: Any, right: Any) -> bool:
    return _text(left).casefold() == _text(right).casefold()


def _registered_store(root: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    platform = _text(payload.get("platform")).casefold()
    country = _text(payload.get("country") or payload.get("country_site")).upper()
    store_id = _text(payload.get("store_id") or payload.get("store")).casefold()
    if not platform or not country or not store_id:
        return None
    stores = load_profile(root.resolve()).get("stores")
    if not isinstance(stores, list):
        return None
    matches = []
    for store in stores:
        if not isinstance(store, dict):
            continue
        identities = {
            _text(store.get("store_external_id")).casefold(),
            _text(store.get("store_name")).casefold(),
        }
        if (
            _text(store.get("platform_id")).casefold() == platform
            and _text(store.get("country_code")).upper() == country
            and store_id in identities
        ):
            matches.append(store)
    return matches[0] if len(matches) == 1 else None


def safe_chat_execution_identity(
    root: Path,
    payload: dict[str, Any],
    base_context: dict[str, Any],
) -> dict[str, str]:
    """Return identity fields only when the complete registered store scope matches.

    Browser and execution references are request metadata, so they are admitted
    only after platform, country/site and store resolve to exactly one local
    registered store.  Route keys and credential material are never returned.
    """

    for key in ("platform", "country", "store_id"):
        requested = payload.get(key)
        if requested and not _same(requested, base_context.get(key)):
            return {}
    store = _registered_store(root, payload)
    if store is None:
        return {}

    requested_model = _text(payload.get("store_model"))
    registered_model = normalize_store_model_for_route(
        store.get("shop_type") or store.get("store_model")
    )
    if requested_model and normalize_store_model_for_route(requested_model) != registered_model:
        return {}

    requested_ownership = _text(payload.get("ownership") or payload.get("store_ownership"))
    registered_ownership = infer_store_ownership_for_route(store)
    if requested_ownership and (
        infer_store_ownership_for_route(
            {"store_ownership": requested_ownership, "store_model": registered_model}
        )
        != registered_ownership
    ):
        return {}

    result = {
        "store_model": requested_model or registered_model,
        "ownership": requested_ownership or registered_ownership,
    }
    for key in (
        "project_id",
        "task_id",
        "store_binding_id",
        "execution_identity_id",
        "browser_profile_id",
    ):
        value = _reference(payload.get(key))
        if value:
            result[key] = value

    browser_provider = _reference(payload.get("browser_provider"))
    if browser_provider:
        result["browser_provider"] = browser_provider.casefold()
    binding_status = _reference(payload.get("browser_binding_status"))
    if binding_status:
        result["browser_binding_status"] = binding_status.casefold()
    sequence = payload.get("browser_profile_sequence") or payload.get("browser_profile_seq")
    try:
        sequence_number = int(sequence)
    except (TypeError, ValueError):
        sequence_number = 0
    if 0 < sequence_number <= 999999:
        result["browser_profile_sequence"] = str(sequence_number)
    return {key: value for key, value in result.items() if value}
