from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .seller_mode_skill_packs import load_seller_mode_skill_pack_registry


REGISTRY_PATH = Path("config") / "u30_seller_mode_production_registry.json"


def _clean(value: Any, limit: int = 600) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _load_registry(root: Path) -> dict[str, Any]:
    try:
        payload = json.loads((root / REGISTRY_PATH).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def evaluate_seller_mode_production_preflight(
    root: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Require an exact real execution scope before a seller-mode run."""

    production = _load_registry(root)
    skill_packs = load_seller_mode_skill_pack_registry(root)
    mode_ids = {
        str(item.get("id") or "")
        for item in skill_packs.get("modes", [])
        if isinstance(item, dict) and str(item.get("id") or "")
    }
    required = (
        "run_id",
        "seller_mode_id",
        "project_id",
        "platform",
        "country_site",
        "store_binding_id",
        "execution_identity_id",
        "owner_run_approval_id",
    )
    missing = [field for field in required if not _clean(payload.get(field), 1000)]
    mode_id = _clean(payload.get("seller_mode_id"), 160)
    if mode_id not in mode_ids:
        missing.append("recognized_seller_mode")
    if mode_id == "official_full_managed" or str(payload.get("store_mode") or "") == "official_full_managed":
        missing.append("official_full_managed_not_executable")
    if str(payload.get("source_kind") or "") != "real":
        missing.append("real_run_source")
    if str(payload.get("platform") or "").casefold() == "amazon":
        missing.append("amazon_paused_by_owner")
    if int(production.get("real_store_connector_count") or 0) <= 0:
        missing.append("verified_store_connector")
    if not bool(production.get("external_execution_enabled")):
        missing.append("external_execution_not_enabled")
    missing = list(dict.fromkeys(missing))
    return {
        "schema_version": 1,
        "run_id": _clean(payload.get("run_id"), 160),
        "seller_mode_id": mode_id,
        "state": "ready_for_owner_controlled_run" if not missing else "blocked_preflight",
        "run_allowed": not missing,
        "missing": missing,
        "external_action_count": 0,
    }


def evaluate_seller_mode_action(root: Path, behavior_id: str) -> dict[str, Any]:
    """Classify abuse and rights-sensitive actions without giving execution help."""

    skill_packs = load_seller_mode_skill_pack_registry(root)
    guardrails = skill_packs.get("global_guardrails", {})
    behavior = next(
        (
            item
            for item in guardrails.get("prohibited_behaviors", [])
            if isinstance(item, dict) and str(item.get("id") or "") == behavior_id
        ),
        None,
    )
    if behavior is not None:
        return {
            "behavior_id": behavior_id,
            "state": "prohibited",
            "execution_allowed": False,
            "allowed_use_cases": list(behavior.get("allowed_use_cases") or []),
            "forbidden_outputs": list(behavior.get("forbidden_outputs") or []),
            "external_action_count": 0,
        }
    behavior = next(
        (
            item
            for item in guardrails.get("review_gated_behaviors", [])
            if isinstance(item, dict) and str(item.get("id") or "") == behavior_id
        ),
        None,
    )
    if behavior is not None:
        return {
            "behavior_id": behavior_id,
            "state": "review_blocked",
            "execution_allowed": False,
            "required_gates": list(behavior.get("required_gates") or []),
            "allowed_use_cases": list(behavior.get("allowed_use_cases") or []),
            "external_action_count": 0,
        }
    return {
        "behavior_id": _clean(behavior_id, 160),
        "state": "unknown_blocked",
        "execution_allowed": False,
        "external_action_count": 0,
    }


def run_synthetic_seller_mode_production_slice(root: Path) -> dict[str, Any]:
    production = _load_registry(root)
    skill_packs = load_seller_mode_skill_pack_registry(root)
    stages = [str(item) for item in production.get("required_stages", []) if str(item)]
    policies = {
        str(item.get("seller_mode_id") or ""): item
        for item in production.get("mode_policies", [])
        if isinstance(item, dict) and str(item.get("seller_mode_id") or "")
    }
    modes: list[dict[str, Any]] = []
    for mode in skill_packs.get("modes", []):
        if not isinstance(mode, dict):
            continue
        mode_id = str(mode.get("id") or "")
        policy = policies.get(mode_id, {})
        scope = {
            "project_id": "synthetic-u30-project",
            "task_id": f"synthetic-u30-{mode_id}",
            "seller_mode_id": mode_id,
            "platform": "synthetic-platform",
            "country_site": "SANDBOX",
            "store_binding_id": "synthetic-store",
            "execution_identity_id": "synthetic-identity",
        }
        receipts = [
            {
                "sequence": index,
                "stage": stage,
                "state": "local_draft_or_review_only",
                "source_kind": "synthetic_fixture",
                "scope": dict(scope),
                "external_action_count": 0,
            }
            for index, stage in enumerate(stages, start=1)
        ]
        modes.append(
            {
                "seller_mode_id": mode_id,
                "source_kind": "synthetic_fixture",
                "state_history": stages,
                "receipts": receipts,
                "selection_rule": str(policy.get("selection_rule") or ""),
                "production_rule": str(policy.get("production_rule") or ""),
                "exit_rule": str(policy.get("exit_rule") or ""),
                "scope_immutable": bool(receipts)
                and all(item.get("scope") == scope for item in receipts),
                "external_action_count": 0,
            }
        )
    return {
        "schema_version": 1,
        "source_kind": "synthetic_fixture",
        "seller_mode_count": len(modes),
        "required_stage_count": len(stages),
        "mode_stage_receipt_count": sum(len(item.get("receipts", [])) for item in modes),
        "all_modes_complete": bool(modes)
        and all(item.get("state_history") == stages for item in modes),
        "scope_immutable": bool(modes)
        and all(item.get("scope_immutable") for item in modes),
        "modes": modes,
        "external_business_action_count": int(production.get("external_action_count") or 0),
        "amazon_status": str(production.get("amazon_status") or ""),
    }


def seller_mode_production_snapshot(root: Path) -> dict[str, Any]:
    production = _load_registry(root)
    synthetic = run_synthetic_seller_mode_production_slice(root)
    required_stage_count = int(synthetic.get("required_stage_count") or 0)
    return {
        "seller_mode_count": int(synthetic.get("seller_mode_count") or 0),
        "required_stage_count": required_stage_count,
        "synthetic_mode_stage_receipt_count": int(
            synthetic.get("mode_stage_receipt_count") or 0
        ),
        "synthetic_complete_mode_count": sum(
            1
            for item in synthetic.get("modes", [])
            if isinstance(item, dict)
            and required_stage_count > 0
            and len(item.get("state_history", [])) == required_stage_count
        ),
        "synthetic_production_slice": synthetic,
        "real_store_connector_count": int(
            production.get("real_store_connector_count") or 0
        ),
        "real_complete_workflow_receipt_count": int(
            production.get("real_complete_workflow_receipt_count") or 0
        ),
        "official_full_managed_execution_count": int(
            production.get("official_full_managed_execution_count") or 0
        ),
        "external_action_count": int(production.get("external_action_count") or 0),
        "amazon_status": str(production.get("amazon_status") or ""),
    }
