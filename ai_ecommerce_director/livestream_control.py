from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REGISTRY_PATH = Path("config") / "u26_livestream_control_registry.json"
EXPECTED_DIMENSIONS = {
    "schedule",
    "duration",
    "views",
    "engagement",
    "gmv",
    "host_or_creator",
    "violations",
    "human_takeover",
}


def load_livestream_control_registry(root: Path) -> dict[str, Any]:
    payload = json.loads((root / REGISTRY_PATH).read_text(encoding="utf-8"))
    if int(payload.get("schema_version") or 0) != 1:
        raise ValueError("U26 livestream registry schema is not supported.")
    dimensions = set(payload.get("control_dimensions") or [])
    if not EXPECTED_DIMENSIONS.issubset(dimensions):
        raise ValueError("U26 livestream registry is missing control dimensions.")
    if int(payload.get("real_platform_connector_count") or 0) < 0:
        raise ValueError("U26 livestream connector count cannot be negative.")
    if payload.get("unattended_live_allowed") is not False:
        raise ValueError("U26 unattended live must remain disabled.")
    if int(payload.get("external_business_action_count") or 0) != 0:
        raise ValueError("U26 registry cannot claim external business actions.")
    return payload


def evaluate_live_session_preflight(
    root: Path, session: dict[str, Any]
) -> dict[str, Any]:
    registry = load_livestream_control_registry(root)
    required = list(registry["required_execution_identity_fields"]) + list(
        registry["required_session_fields"]
    )
    missing = [field for field in required if not str(session.get(field) or "").strip()]
    if int(registry.get("real_platform_connector_count") or 0) <= 0:
        missing.append("verified_platform_connector")
    if str(session.get("owner_approval_state") or "") != "approved":
        missing.append("owner_approval_state")
    if str(session.get("source_kind") or "") != "real":
        missing.append("real_session_source")
    if str(session.get("platform") or "").lower() == "amazon":
        missing.append("amazon_paused_by_owner")
    missing = list(dict.fromkeys(missing))
    return {
        "schema_version": 1,
        "session_id": str(session.get("session_id") or ""),
        "state": "ready_for_human_go_live" if not missing else "blocked_preflight",
        "go_live_allowed": not missing and bool(registry.get("real_go_live_allowed")),
        "unattended_live_allowed": False,
        "missing": missing,
        "platform_control_call_count": 0,
        "external_action_count": 0,
    }


def run_synthetic_livestream_rehearsal(root: Path) -> dict[str, Any]:
    registry = load_livestream_control_registry(root)
    state_history = [
        "planned",
        "rehearsal_ready",
        "rehearsing",
        "human_takeover_required",
        "ended",
    ]
    takeover_reason_codes = ["prohibited_product_claim"]
    metrics = {
        "source_kind": "synthetic_fixture",
        "platform": "synthetic-platform",
        "site": "sandbox-site",
        "store_id": "synthetic-store",
        "session_id": "u26-synthetic-rehearsal",
        "captured_at": "2026-08-06T21:25:00+08:00",
        "elapsed_seconds": 900,
        "unique_viewers": 125,
        "peak_concurrent_viewers": 18,
        "average_watch_seconds": 71,
        "likes": 40,
        "comments": 9,
        "product_clicks": 4,
        "orders": 0,
        "gmv": 0,
        "currency": "USD",
        "refunds": 0,
        "excluded_from_real_aggregates": True,
    }
    return {
        "schema_version": 1,
        "session_id": "u26-synthetic-rehearsal",
        "state_history": state_history,
        "schedule": {
            "start_at": "2026-08-06T21:25:00+08:00",
            "end_at": "2026-08-06T21:55:00+08:00",
            "timezone": "Asia/Shanghai",
            "planned_duration_seconds": 1800,
        },
        "host_or_creator": {
            "id": "synthetic-avatar-u26",
            "kind": "synthetic_fixture",
            "likeness_rights_state": "synthetic_fixture_only",
            "voice_rights_state": "synthetic_fixture_only",
            "disclosure_state": "required_before_real_use",
            "verified_for_real_use": False,
        },
        "metrics": metrics,
        "violation_events": [
            {
                "code": "prohibited_product_claim",
                "severity": "high",
                "source_kind": "synthetic_fixture",
                "automated_speech_stopped": True,
                "human_owner_required": True,
            }
        ],
        "takeover_reason_codes": takeover_reason_codes,
        "human_takeover_verified": True,
        "go_live_allowed": False,
        "unattended_live_allowed": False,
        "platform_control_call_count": int(
            registry.get("platform_control_call_count") or 0
        ),
        "external_business_action_count": 0,
        "amazon_status": "paused_by_owner_not_touched",
    }


def livestream_control_snapshot(root: Path) -> dict[str, Any]:
    registry = load_livestream_control_registry(root)
    rehearsal = run_synthetic_livestream_rehearsal(root)
    return {
        "status": registry["status"],
        "control_dimension_count": len(registry["control_dimensions"]),
        "real_platform_connector_count": int(
            registry.get("real_platform_connector_count") or 0
        ),
        "real_scheduled_session_count": int(
            registry.get("real_scheduled_session_count") or 0
        ),
        "real_live_session_count": int(registry.get("real_live_session_count") or 0),
        "real_metric_receipt_count": int(
            registry.get("metric_contract", {}).get(
                "current_real_metric_receipt_count", 0
            )
        ),
        "verified_host_or_creator_count": int(
            registry.get("host_and_creator_contract", {}).get(
                "current_verified_host_or_creator_count", 0
            )
        ),
        "synthetic_takeover_slice_count": int(
            bool(rehearsal.get("human_takeover_verified"))
        ),
        "synthetic_rehearsal": rehearsal,
        "external_action_count": int(
            registry.get("external_business_action_count") or 0
        ),
        "amazon_status": registry["amazon_status"],
    }
