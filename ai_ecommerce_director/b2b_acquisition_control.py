from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


REGISTRY_PATH = Path("config") / "u29_b2b_acquisition_registry.json"


def _clean(value: Any, limit: int = 600) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _load_registry(root: Path) -> dict[str, Any]:
    try:
        payload = json.loads((root / REGISTRY_PATH).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def evaluate_b2b_batch_preflight(
    root: Path,
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Review ten scoped records; never promote the review into a send queue."""

    registry = _load_registry(root)
    route_ids = {
        str(item.get("id") or "")
        for item in registry.get("routes", [])
        if isinstance(item, dict) and str(item.get("id") or "")
    }
    required_fields = [
        str(item) for item in registry.get("required_record_fields", []) if str(item)
    ]
    allowed_permissions = {
        str(item)
        for item in registry.get("allowed_contact_permission_states", [])
        if str(item)
    }
    rows = list(records) if isinstance(records, Sequence) else []
    review_missing: list[str] = []
    send_missing: list[str] = []
    if len(rows) != 10:
        review_missing.append("exactly_10_records")
    record_ids: list[str] = []
    for index, item in enumerate(rows, start=1):
        if not isinstance(item, Mapping):
            review_missing.append(f"record_{index}.object")
            continue
        for field in required_fields:
            if not _clean(item.get(field), 1000):
                review_missing.append(f"record_{index}.{field}")
        record_id = _clean(item.get("record_id"), 160)
        if record_id:
            record_ids.append(record_id)
        if _clean(item.get("route"), 120) not in route_ids:
            review_missing.append(f"record_{index}.known_route")
        if str(item.get("source_kind") or "") != "real":
            review_missing.append(f"record_{index}.real_source")
        permission = _clean(item.get("contact_permission"), 160)
        if permission not in allowed_permissions:
            review_missing.append(f"record_{index}.valid_contact_permission")
        if permission == "research_only":
            send_missing.append(f"record_{index}.contact_permission_allows_outreach")
        if not _clean(item.get("owner_send_approval_id"), 240):
            send_missing.append(f"record_{index}.owner_send_approval_id")
    if len(record_ids) != len(set(record_ids)):
        review_missing.append("unique_record_ids")
    if int(registry.get("real_send_connector_count") or 0) <= 0:
        send_missing.append("verified_send_connector")
    review_missing = list(dict.fromkeys(review_missing))
    send_missing = list(dict.fromkeys(send_missing))
    missing = [*review_missing, *send_missing]
    batch_review_ready = not review_missing
    # A ten-record review is never an execution queue. Even after every
    # per-record packet is approved, an individual connector call must consume
    # its own exact single-use approval in the existing outbound ledger.
    send_execution_allowed = False
    return {
        "schema_version": 1,
        "record_count": len(rows),
        "state": "review_ready_send_blocked" if batch_review_ready else "blocked_preflight",
        "batch_review_ready": batch_review_ready,
        "send_execution_allowed": send_execution_allowed,
        "review_missing": review_missing,
        "send_missing": send_missing,
        "missing": missing,
        "send_call_count": 0,
        "external_action_count": 0,
    }


def run_synthetic_b2b_acquisition_slice(root: Path) -> dict[str, Any]:
    """Exercise both acquisition routes without creating real leads or sends."""

    records: list[dict[str, Any]] = []
    for index in range(1, 11):
        platform_route = index <= 5
        route = "b2b_platform_inquiry" if platform_route else "proactive_outbound"
        records.append(
            {
                "record_id": f"u29-synthetic-record-{index:02d}",
                "crm_account_id": f"u29-synthetic-account-{index:02d}",
                "route": route,
                "project_id": "synthetic-u29-project",
                "task_id": "synthetic-u29-task",
                "source_kind": "synthetic_fixture",
                "source_type": "synthetic_platform_inquiry"
                if platform_route
                else "synthetic_public_business_signal",
                "source_ref": f"synthetic://u29/source/{index:02d}",
                "observed_signal": "Synthetic review signal; not a real buyer fact.",
                "contact_path": f"synthetic://u29/contact/{index:02d}",
                "contact_permission": "inbound_reply_allowed"
                if platform_route
                else "public_business_contact_owner_approval_required",
                "state_history": [
                    "signal_observed",
                    "lawful_scope_reviewed",
                    "account_deduplicated",
                    "qualification_drafted",
                    "owner_send_approval_required",
                    "send_blocked_no_connector",
                ],
                "owner_send_approval_id": "",
                "legal_clearance_claimed": False,
                "send_executed": False,
                "excluded_from_real_pipeline": True,
            }
        )
    route_counts = Counter(str(item.get("route") or "") for item in records)
    account_ids = [str(item.get("crm_account_id") or "") for item in records]
    return {
        "schema_version": 1,
        "source_kind": "synthetic_fixture",
        "record_count": len(records),
        "canonical_account_count": len(set(account_ids)),
        "route_record_counts": dict(route_counts),
        "shared_crm_verified": all(account_ids) and len(account_ids) == len(set(account_ids)),
        "lawful_scope_reviewed": all(
            item.get("source_ref") and item.get("contact_permission") for item in records
        ),
        "per_record_send_approval_required": all(
            item.get("state_history", [])[-2:-1] == ["owner_send_approval_required"]
            for item in records
        ),
        "records": records,
        "send_call_count": 0,
        "external_business_action_count": 0,
        "amazon_status": "paused_by_owner_not_touched",
    }


def b2b_acquisition_snapshot(root: Path) -> dict[str, Any]:
    registry = _load_registry(root)
    synthetic = run_synthetic_b2b_acquisition_slice(root)
    routes = [item for item in registry.get("routes", []) if isinstance(item, dict)]
    return {
        "route_count": len(routes),
        "routes": routes,
        "synthetic_review_record_count": int(synthetic.get("record_count") or 0),
        "synthetic_acquisition_slice": synthetic,
        "real_verified_record_count": int(
            registry.get("real_verified_record_count") or 0
        ),
        "real_canonical_account_count": int(
            registry.get("real_canonical_account_count") or 0
        ),
        "real_send_connector_count": int(
            registry.get("real_send_connector_count") or 0
        ),
        "real_send_receipt_count": int(registry.get("real_send_receipt_count") or 0),
        "owner_send_approval_receipt_count": int(
            registry.get("owner_send_approval_receipt_count") or 0
        ),
        "external_action_count": int(registry.get("external_action_count") or 0),
        "amazon_status": str(registry.get("amazon_status") or ""),
    }
