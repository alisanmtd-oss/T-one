from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SELLER_MODE_SKILL_PACK_REGISTRY_PATH = Path("config") / "seller_mode_skill_pack_registry.json"
PROHIBITED_STATUSES = {"prohibited"}
NON_EXECUTABLE_STATUSES = {
    "blocked_until_rights_verified",
    "high_risk_owner_review",
    "policy_sensitive",
    "rights_sensitive",
    *PROHIBITED_STATUSES,
}
REQUIRED_PROHIBITED_BEHAVIOR_IDS = {"irregular_funds", "malicious_refund_no_return"}
REQUIRED_REVIEW_GATED_BEHAVIOR_IDS = {
    "direct_copy_external_listing_link",
    "direct_copy_external_image",
    "direct_copy_external_design",
    "real_publish_unproduced_product",
}
REQUIRED_REVIEW_GATES = {"platform_policy_review", "owner_review"}
REQUIRED_OPERATING_PROFILE_TEXT_FIELDS = {
    "suitable_for",
    "product_source",
    "inventory_model",
    "fulfillment_model",
    "cash_cycle",
    "primary_growth_engine",
}
REQUIRED_OPERATING_PROFILE_LIST_FIELDS = {
    "daily_loop",
    "required_inputs",
    "decision_metrics",
    "scale_conditions",
    "stop_conditions",
}


def load_seller_mode_skill_pack_registry(root: Path, *, strict: bool = False) -> dict[str, Any]:
    """Load the owner-authored seller-mode skill pack registry.

    This registry is intentionally separate from live task installation state:
    it describes operating-model truth and safety gates, not real connector
    readiness or external execution authority.
    """

    path = root / SELLER_MODE_SKILL_PACK_REGISTRY_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("卖家模式能力包注册表根节点必须是对象。")
    except (OSError, ValueError) as exc:
        if strict:
            raise ValueError(f"卖家模式能力包注册表无法读取：{exc}") from exc
        return {
            "schema_version": 1,
            "modes": [],
            "shared_capabilities": [],
            "registry_error": str(exc),
        }

    payload["modes"] = _clean_modes(payload.get("modes"))
    payload["shared_capabilities"] = _clean_string_list(payload.get("shared_capabilities"), limit=80)
    return payload


def seller_mode_skill_pack_snapshot(root: Path) -> dict[str, Any]:
    registry = load_seller_mode_skill_pack_registry(root)
    modes = registry.get("modes", [])
    variants = [
        variant
        for mode in modes
        for variant in mode.get("variants", [])
        if isinstance(variant, dict)
    ]
    prohibited_variants = [
        variant
        for variant in variants
        if str(variant.get("status") or "").strip().lower() in PROHIBITED_STATUSES
    ]
    executable_variants = [
        variant
        for variant in variants
        if variant.get("execution_allowed") is True
        and str(variant.get("status") or "").strip().lower() not in NON_EXECUTABLE_STATUSES
    ]
    return {
        "schema_version": registry.get("schema_version", 1),
        "updated_at": str(registry.get("updated_at") or ""),
        "purpose": str(registry.get("purpose") or ""),
        "truth_policy": registry.get("truth_policy") if isinstance(registry.get("truth_policy"), dict) else {},
        "global_guardrails": registry.get("global_guardrails") if isinstance(registry.get("global_guardrails"), dict) else {},
        "shared_capabilities": registry.get("shared_capabilities", []),
        "mode_count": len(modes),
        "detailed_mode_count": sum(
            1 for mode in modes if mode.get("operating_profile") and mode.get("store_scope_rules")
        ),
        "variant_count": len(variants),
        "local_work_allowed_variant_count": sum(1 for variant in variants if variant.get("local_work_allowed") is True),
        "executable_variant_count": len(executable_variants),
        "review_gated_variant_count": sum(
            1
            for variant in variants
            if variant.get("local_work_allowed") is True and variant.get("execution_allowed") is not True
        ),
        "prohibited_variant_count": len(prohibited_variants),
        "modes": modes,
        "prohibited_variants": prohibited_variants,
        "external_action_authorized_count": 0,
        "execution_ready": False,
    }


def validate_seller_mode_skill_pack_registry(root: Path) -> list[str]:
    registry = load_seller_mode_skill_pack_registry(root, strict=True)
    errors: list[str] = []
    mode_ids: set[str] = set()
    shared = set(registry.get("shared_capabilities", []))
    if len(shared) < 6:
        errors.append("shared_capabilities_too_small")
    truth_policy = registry.get("truth_policy", {})
    if not truth_policy.get("prohibited_variants_are_for_detection_and_blocking_only"):
        errors.append("truth_policy_missing_prohibited_blocking_rule")
    if not truth_policy.get("legitimate_seller_modes_local_work_allowed"):
        errors.append("truth_policy_missing_local_work_allowed_rule")
    if not truth_policy.get("external_execution_requires_explicit_owner_approval"):
        errors.append("truth_policy_missing_external_execution_owner_approval")
    _validate_global_guardrails(registry.get("global_guardrails"), errors)

    for mode in registry.get("modes", []):
        mode_id = str(mode.get("id") or "").strip()
        if not mode_id:
            errors.append("mode_id_required")
            continue
        if mode_id in mode_ids:
            errors.append(f"duplicate_mode_id:{mode_id}")
        mode_ids.add(mode_id)
        if not mode.get("label"):
            errors.append(f"mode_label_required:{mode_id}")
        if not mode.get("core_objects"):
            errors.append(f"core_objects_required:{mode_id}")
        if not mode.get("default_agent_routes"):
            errors.append(f"default_agent_routes_required:{mode_id}")
        operating_profile = mode.get("operating_profile")
        if not isinstance(operating_profile, dict):
            errors.append(f"operating_profile_required:{mode_id}")
        else:
            for field in sorted(REQUIRED_OPERATING_PROFILE_TEXT_FIELDS):
                if not str(operating_profile.get(field) or "").strip():
                    errors.append(f"operating_profile_{field}_required:{mode_id}")
            for field in sorted(REQUIRED_OPERATING_PROFILE_LIST_FIELDS):
                if not operating_profile.get(field):
                    errors.append(f"operating_profile_{field}_required:{mode_id}")
        store_scope_rules = mode.get("store_scope_rules")
        if not isinstance(store_scope_rules, dict):
            errors.append(f"store_scope_rules_required:{mode_id}")
        else:
            if not store_scope_rules.get("compatible_store_modes"):
                errors.append(f"compatible_store_modes_required:{mode_id}")
            if store_scope_rules.get("official_full_managed") != "recognition_only_non_executable":
                errors.append(f"official_full_managed_boundary_required:{mode_id}")
        variants = mode.get("variants")
        if not variants:
            errors.append(f"variants_required:{mode_id}")
            continue
        for variant in variants:
            variant_id = str(variant.get("id") or "").strip()
            if not variant_id:
                errors.append(f"variant_id_required:{mode_id}")
                continue
            status = str(variant.get("status") or "").strip().lower()
            execution_allowed = variant.get("execution_allowed") is True
            local_work_allowed = variant.get("local_work_allowed") is True
            required_gates = variant.get("required_gates") if isinstance(variant.get("required_gates"), list) else []
            if not required_gates:
                errors.append(f"required_gates_required:{mode_id}:{variant_id}")
            if not local_work_allowed:
                errors.append(f"variant_local_work_not_allowed:{mode_id}:{variant_id}")
            if status in NON_EXECUTABLE_STATUSES and execution_allowed:
                errors.append(f"non_executable_status_must_block_execution:{mode_id}:{variant_id}")
            if status in PROHIBITED_STATUSES:
                if execution_allowed:
                    errors.append(f"prohibited_variant_execution_allowed:{mode_id}:{variant_id}")
                allowed_use_cases = " ".join(str(item) for item in variant.get("allowed_use_cases", []))
                forbidden_outputs = variant.get("forbidden_outputs") if isinstance(variant.get("forbidden_outputs"), list) else []
                if "风险识别" not in allowed_use_cases or "拦截" not in allowed_use_cases:
                    errors.append(f"prohibited_variant_missing_detection_intercept_scope:{mode_id}:{variant_id}")
                if not forbidden_outputs:
                    errors.append(f"prohibited_variant_missing_forbidden_outputs:{mode_id}:{variant_id}")
                gate_text = " ".join(str(item) for item in required_gates).casefold()
                note_text = str(variant.get("notes") or "").casefold()
                if "block" not in gate_text and "拦截" not in note_text and "block" not in note_text:
                    errors.append(f"prohibited_variant_missing_block_gate:{mode_id}:{variant_id}")
            if variant_id in {"direct_link_copy_pod", "reference_inspired_design_variation", "prototype_demand_test", "marketplace_link_resale_markup"}:
                if execution_allowed:
                    errors.append(f"review_gated_variant_execution_allowed:{mode_id}:{variant_id}")
                if not local_work_allowed:
                    errors.append(f"review_gated_variant_missing_local_work:{mode_id}:{variant_id}")
                gate_text = " ".join(str(item) for item in required_gates)
                if not any(gate in gate_text for gate in ("owner_review", "owner_legal_review", "owner_publish_approval")):
                    errors.append(f"review_gated_variant_missing_owner_gate:{mode_id}:{variant_id}")
    expected = {
        "distribution_seller",
        "pod_seller",
        "factory_seller",
        "selection_seller",
        "testing_seller",
        "brand_seller",
        "catalog_supply_seller",
    }
    missing = expected.difference(mode_ids)
    for mode_id in sorted(missing):
        errors.append(f"expected_mode_missing:{mode_id}")
    return errors


def _validate_global_guardrails(raw_guardrails: Any, errors: list[str]) -> None:
    if not isinstance(raw_guardrails, dict):
        errors.append("global_guardrails_required")
        return
    prohibited = raw_guardrails.get("prohibited_behaviors")
    review_gated = raw_guardrails.get("review_gated_behaviors")
    if not isinstance(prohibited, list):
        errors.append("global_guardrails_prohibited_behaviors_required")
        prohibited = []
    if not isinstance(review_gated, list):
        errors.append("global_guardrails_review_gated_behaviors_required")
        review_gated = []

    prohibited_by_id = {
        str(item.get("id") or ""): item
        for item in prohibited
        if isinstance(item, dict)
    }
    for behavior_id in sorted(REQUIRED_PROHIBITED_BEHAVIOR_IDS.difference(prohibited_by_id)):
        errors.append(f"required_prohibited_behavior_missing:{behavior_id}")
    for behavior_id in REQUIRED_PROHIBITED_BEHAVIOR_IDS.intersection(prohibited_by_id):
        behavior = prohibited_by_id[behavior_id]
        if behavior.get("classification") != "prohibited":
            errors.append(f"prohibited_behavior_classification_invalid:{behavior_id}")
        if behavior.get("local_work_allowed") is not True:
            errors.append(f"prohibited_behavior_local_work_required:{behavior_id}")
        if behavior.get("execution_allowed") is True:
            errors.append(f"prohibited_behavior_execution_allowed:{behavior_id}")
        use_cases = " ".join(str(item) for item in behavior.get("allowed_use_cases", []))
        forbidden_outputs = behavior.get("forbidden_outputs") if isinstance(behavior.get("forbidden_outputs"), list) else []
        if "风险识别" not in use_cases or "拦截" not in use_cases:
            errors.append(f"prohibited_behavior_missing_detection_intercept:{behavior_id}")
        if not forbidden_outputs:
            errors.append(f"prohibited_behavior_missing_forbidden_outputs:{behavior_id}")

    review_by_id = {
        str(item.get("id") or ""): item
        for item in review_gated
        if isinstance(item, dict)
    }
    for behavior_id in sorted(REQUIRED_REVIEW_GATED_BEHAVIOR_IDS.difference(review_by_id)):
        errors.append(f"required_review_gated_behavior_missing:{behavior_id}")
    for behavior_id in REQUIRED_REVIEW_GATED_BEHAVIOR_IDS.intersection(review_by_id):
        behavior = review_by_id[behavior_id]
        if behavior.get("local_work_allowed") is not True:
            errors.append(f"review_gated_behavior_local_work_required:{behavior_id}")
        if behavior.get("execution_allowed") is True:
            errors.append(f"review_gated_behavior_execution_allowed:{behavior_id}")
        gates = set(str(item) for item in behavior.get("required_gates", []))
        if not REQUIRED_REVIEW_GATES.issubset(gates):
            errors.append(f"review_gated_behavior_missing_platform_owner_gates:{behavior_id}")
        if behavior_id in {
            "direct_copy_external_listing_link",
            "direct_copy_external_image",
            "direct_copy_external_design",
        } and "copyright_review" not in gates:
            errors.append(f"review_gated_behavior_missing_copyright_gate:{behavior_id}")


def _clean_modes(raw_modes: Any) -> list[dict[str, Any]]:
    modes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_modes if isinstance(raw_modes, list) else []:
        if not isinstance(raw, dict):
            continue
        mode_id = str(raw.get("id") or "").strip()
        if not mode_id or mode_id in seen:
            continue
        mode = dict(raw)
        mode["id"] = mode_id
        mode["label"] = str(raw.get("label") or mode_id)
        mode["positioning"] = str(raw.get("positioning") or "")
        mode["mode_family"] = str(raw.get("mode_family") or "")
        mode["core_objects"] = _clean_string_list(raw.get("core_objects"), limit=40)
        mode["workflows"] = _clean_string_list(raw.get("workflows"), limit=40)
        mode["default_agent_routes"] = _clean_string_list(raw.get("default_agent_routes"), limit=40)
        mode["operating_profile"] = _clean_operating_profile(raw.get("operating_profile"))
        mode["store_scope_rules"] = _clean_store_scope_rules(raw.get("store_scope_rules"))
        mode["variants"] = _clean_variants(raw.get("variants"))
        modes.append(mode)
        seen.add(mode_id)
    return modes


def _clean_operating_profile(raw_profile: Any) -> dict[str, Any]:
    profile = raw_profile if isinstance(raw_profile, dict) else {}
    cleaned: dict[str, Any] = {
        field: " ".join(str(profile.get(field) or "").split()).strip()[:600]
        for field in REQUIRED_OPERATING_PROFILE_TEXT_FIELDS
    }
    for field in REQUIRED_OPERATING_PROFILE_LIST_FIELDS:
        cleaned[field] = _clean_string_list(profile.get(field), limit=20)
    return cleaned


def _clean_store_scope_rules(raw_rules: Any) -> dict[str, Any]:
    rules = raw_rules if isinstance(raw_rules, dict) else {}
    return {
        "compatible_store_modes": _clean_string_list(
            rules.get("compatible_store_modes"), limit=30
        ),
        "requires_platform_site_store_account_scope": (
            rules.get("requires_platform_site_store_account_scope") is True
        ),
        "official_full_managed": " ".join(
            str(rules.get("official_full_managed") or "").split()
        ).strip()[:120],
    }


def _clean_variants(raw_variants: Any) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_variants if isinstance(raw_variants, list) else []:
        if not isinstance(raw, dict):
            continue
        variant_id = str(raw.get("id") or "").strip()
        if not variant_id or variant_id in seen:
            continue
        variant = {
            "id": variant_id,
            "label": str(raw.get("label") or variant_id),
            "status": str(raw.get("status") or "unknown"),
            "local_work_allowed": raw.get("local_work_allowed") is not False,
            "execution_allowed": raw.get("execution_allowed") is True,
            "required_gates": _clean_string_list(raw.get("required_gates"), limit=40),
        }
        allowed_use_cases = _clean_string_list(raw.get("allowed_use_cases"), limit=40)
        if allowed_use_cases:
            variant["allowed_use_cases"] = allowed_use_cases
        forbidden_outputs = _clean_string_list(raw.get("forbidden_outputs"), limit=40)
        if forbidden_outputs:
            variant["forbidden_outputs"] = forbidden_outputs
        if str(raw.get("notes") or "").strip():
            variant["notes"] = str(raw.get("notes"))
        variants.append(variant)
        seen.add(variant_id)
    return variants


def _clean_string_list(value: Any, *, limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in value if isinstance(value, list) else []:
        text = " ".join(str(item or "").split()).strip()
        if not text or text.casefold() in seen:
            continue
        result.append(text[:180])
        seen.add(text.casefold())
        if len(result) >= limit:
            break
    return result
