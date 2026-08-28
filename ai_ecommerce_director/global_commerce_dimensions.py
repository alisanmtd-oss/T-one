from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REGISTRY_PATH = Path("config") / "global_commerce_dimension_registry.json"

REQUIRED_RELATIONSHIP_MODEL_IDS = {
    "b2b",
    "b2c",
    "c2c",
    "d2c",
    "c2b",
    "b2b2c",
    "b2g",
    "o2o",
    "c2m",
    "s2b2c",
}

REQUIRED_COMMERCE_FORM_IDS = {
    "cross_border_commerce",
    "social_commerce",
    "content_commerce",
    "subscription_commerce",
    "platform_self_operated",
    "online_auction_commerce",
}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalized_identifier(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _normalized_identifier_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = value.split(",")
    rows = value if isinstance(value, (list, tuple, set)) else []
    normalized: list[str] = []
    for item in rows:
        identifier = _normalized_identifier(item)
        if identifier and identifier not in normalized:
            normalized.append(identifier)
    return normalized


def load_global_commerce_dimension_registry(root: Path, *, strict: bool = False) -> dict[str, Any]:
    path = root / REGISTRY_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        if strict:
            raise
        return {}
    return payload if isinstance(payload, dict) else {}


def global_commerce_dimension_snapshot(root: Path) -> dict[str, Any]:
    registry = load_global_commerce_dimension_registry(root)
    groups = [item for item in _safe_list(registry.get("country_site_groups")) if isinstance(item, dict)]
    country_sites: set[str] = set()
    currencies: set[str] = set()
    platforms: set[str] = set()
    for group in groups:
        country_sites.update(str(item) for item in _safe_list(group.get("country_sites")) if str(item).strip())
        currencies.update(str(item) for item in _safe_list(group.get("default_currencies")) if str(item).strip())
        platforms.update(str(item) for item in _safe_list(group.get("typical_platforms")) if str(item).strip())

    product_catalog = registry.get("product_dimension_catalog")
    product_catalog = product_catalog if isinstance(product_catalog, dict) else {}
    commerce_taxonomy = registry.get("commerce_model_taxonomy")
    commerce_taxonomy = commerce_taxonomy if isinstance(commerce_taxonomy, dict) else {}
    relationship_models = [
        item for item in _safe_list(commerce_taxonomy.get("relationship_models")) if isinstance(item, dict)
    ]
    commerce_forms = [
        item for item in _safe_list(commerce_taxonomy.get("commerce_forms")) if isinstance(item, dict)
    ]
    operating_axes = registry.get("operating_axes")
    operating_axes = operating_axes if isinstance(operating_axes, dict) else {}
    axis_counts = {
        key: len([item for item in _safe_list(value) if str(item).strip()])
        for key, value in operating_axes.items()
    }
    return {
        "schema_version": registry.get("schema_version"),
        "registry_path": str(REGISTRY_PATH).replace("\\", "/"),
        "country_group_count": len(groups),
        "country_site_count": len(country_sites),
        "currency_count": len(currencies),
        "typical_platform_count": len(platforms),
        "country_sites": sorted(country_sites),
        "product_level_count": len(_safe_list(product_catalog.get("product_levels"))),
        "product_family_count": len(_safe_list(product_catalog.get("product_families"))),
        "pod_surface_count": len(_safe_list(product_catalog.get("pod_surfaces"))),
        "product_attribute_count": len(_safe_list(product_catalog.get("product_attributes"))),
        "product_lifecycle_count": len(_safe_list(product_catalog.get("product_lifecycle_states"))),
        "product_risk_gate_count": len(_safe_list(product_catalog.get("product_risk_gates"))),
        "commerce_relationship_model_count": len(relationship_models),
        "commerce_relationship_model_ids": sorted(
            str(item.get("id")) for item in relationship_models if str(item.get("id", "")).strip()
        ),
        "commerce_form_count": len(commerce_forms),
        "commerce_form_ids": sorted(
            str(item.get("id")) for item in commerce_forms if str(item.get("id", "")).strip()
        ),
        "axis_counts": axis_counts,
        "truth_policy": registry.get("truth_policy") if isinstance(registry.get("truth_policy"), dict) else {},
        "dashboard_policy": registry.get("dashboard_policy") if isinstance(registry.get("dashboard_policy"), dict) else {},
    }


def commerce_model_taxonomy(root: Path) -> dict[str, Any]:
    registry = load_global_commerce_dimension_registry(root)
    taxonomy = registry.get("commerce_model_taxonomy")
    taxonomy = taxonomy if isinstance(taxonomy, dict) else {}
    relationship_models = {
        str(item.get("id")): item
        for item in _safe_list(taxonomy.get("relationship_models"))
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }
    commerce_forms = {
        str(item.get("id")): item
        for item in _safe_list(taxonomy.get("commerce_forms"))
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }
    return {
        "composition_policy": taxonomy.get("composition_policy")
        if isinstance(taxonomy.get("composition_policy"), dict)
        else {},
        "relationship_models": relationship_models,
        "commerce_forms": commerce_forms,
    }


def normalize_commerce_model_selection(
    root: Path,
    payload: dict[str, Any] | None,
    *,
    inherit_from: dict[str, Any] | None = None,
    strict: bool = True,
) -> dict[str, Any]:
    """Validate and normalize project/store commerce-model metadata.

    The classification is routing metadata only.  It never implies that a
    platform, store, API, ERP or data source is connected.  Store selections
    may inherit project values field by field and may explicitly override
    them without changing the platform-specific ``store_model``.
    """

    source = payload if isinstance(payload, dict) else {}
    inherited = inherit_from if isinstance(inherit_from, dict) else {}
    taxonomy = commerce_model_taxonomy(root)
    # The required baseline keeps isolated/local test workspaces usable even
    # when they intentionally omit the shared registry file.  Production
    # workspaces extend the accepted values from the canonical registry.
    valid_relationship_models = REQUIRED_RELATIONSHIP_MODEL_IDS | set(
        taxonomy["relationship_models"]
    )
    valid_commerce_forms = REQUIRED_COMMERCE_FORM_IDS | set(
        taxonomy["commerce_forms"]
    )
    if strict and (not valid_relationship_models or not valid_commerce_forms):
        raise ValueError("经营模式注册表不可用，已阻止保存。")

    relationship_keys = ("relationship_model", "primary_relationship_model")
    relationship_present = any(key in source for key in relationship_keys)
    relationship_raw = next(
        (source.get(key) for key in relationship_keys if key in source),
        None,
    )
    if relationship_present:
        relationship_model = _normalized_identifier(relationship_raw)
        relationship_source = "explicit"
    else:
        relationship_model = _normalized_identifier(
            inherited.get("relationship_model")
            or inherited.get("primary_relationship_model")
        )
        relationship_source = "inherited_project" if relationship_model else "unknown"

    secondary_present = "secondary_relationship_models" in source
    if secondary_present:
        secondary_relationship_models = _normalized_identifier_list(
            source.get("secondary_relationship_models")
        )
        secondary_source = "explicit"
    else:
        secondary_relationship_models = _normalized_identifier_list(
            inherited.get("secondary_relationship_models")
        )
        secondary_source = (
            "inherited_project" if secondary_relationship_models else "unknown"
        )

    forms_present = "commerce_forms" in source
    if forms_present:
        commerce_forms = _normalized_identifier_list(source.get("commerce_forms"))
        forms_source = "explicit"
    else:
        commerce_forms = _normalized_identifier_list(inherited.get("commerce_forms"))
        forms_source = "inherited_project" if commerce_forms else "unknown"

    unknown_relationship_models = {
        item
        for item in [relationship_model, *secondary_relationship_models]
        if item and item not in valid_relationship_models
    }
    unknown_commerce_forms = {
        item for item in commerce_forms if item not in valid_commerce_forms
    }
    if strict and unknown_relationship_models:
        raise ValueError(
            "经营关系模式不在当前注册表中："
            + ", ".join(sorted(unknown_relationship_models))
        )
    if strict and unknown_commerce_forms:
        raise ValueError(
            "经营形态不在当前注册表中："
            + ", ".join(sorted(unknown_commerce_forms))
        )
    if unknown_relationship_models:
        relationship_model = (
            "" if relationship_model in unknown_relationship_models else relationship_model
        )
        secondary_relationship_models = [
            item
            for item in secondary_relationship_models
            if item not in unknown_relationship_models
        ]
    commerce_forms = [
        item for item in commerce_forms if item not in unknown_commerce_forms
    ]
    secondary_relationship_models = [
        item for item in secondary_relationship_models if item != relationship_model
    ]

    field_sources = {
        "relationship_model": relationship_source,
        "secondary_relationship_models": secondary_source,
        "commerce_forms": forms_source,
    }
    used_sources = set(field_sources.values()) - {"unknown"}
    if not used_sources:
        selection_source = "unknown"
    elif used_sources == {"inherited_project"}:
        selection_source = "inherited_project"
    elif used_sources == {"explicit"}:
        selection_source = "explicit"
    else:
        selection_source = "project_inherited_with_explicit_override"

    owner_review_values = set(
        str(item)
        for item in taxonomy["composition_policy"].get(
            "owner_review_required_for", []
        )
    )
    selected_values = {
        relationship_model,
        *secondary_relationship_models,
        *commerce_forms,
    } - {""}
    registry = load_global_commerce_dimension_registry(root)
    return {
        "relationship_model": relationship_model,
        "secondary_relationship_models": secondary_relationship_models,
        "commerce_forms": commerce_forms,
        "commerce_model_source": selection_source,
        "commerce_model_field_sources": field_sources,
        "commerce_model_status": "configured" if relationship_model else "unknown",
        "commerce_model_owner_review_required": bool(
            selected_values & owner_review_values
        ),
        "commerce_model_registry_path": REGISTRY_PATH.as_posix(),
        "commerce_model_registry_version": str(registry.get("schema_version") or ""),
        "classification_only": True,
        "external_actions": 0,
    }


def commerce_model_routing_dimensions(
    root: Path,
    project: dict[str, Any],
    *,
    store: dict[str, Any] | None = None,
    product_family: str = "",
) -> dict[str, Any]:
    """Build the complete, non-executable AI/data routing dimension packet."""

    project_selection = normalize_commerce_model_selection(
        root, project, strict=False
    )
    selection = (
        normalize_commerce_model_selection(
            root,
            store,
            inherit_from=project_selection,
            strict=False,
        )
        if isinstance(store, dict)
        else project_selection
    )
    scoped = store if isinstance(store, dict) else {}
    return {
        "relationship_model": selection["relationship_model"],
        "secondary_relationship_models": list(
            selection["secondary_relationship_models"]
        ),
        "commerce_forms": list(selection["commerce_forms"]),
        "platform": str(scoped.get("platform") or "").strip().lower(),
        "country_site": str(
            scoped.get("country_site") or scoped.get("country") or ""
        ).strip().upper(),
        "store_mode": str(
            scoped.get("store_model") or scoped.get("store_mode") or ""
        ).strip().lower(),
        "seller_mode": _normalized_identifier(
            scoped.get("seller_mode") or project.get("seller_mode")
        ),
        "product_family": _normalized_identifier(product_family),
        "selection_source": selection["commerce_model_source"],
        "classification_status": selection["commerce_model_status"],
        "data_truth": "classification_metadata_only",
        "connection_truth": "not_inferred_from_classification",
        "external_actions": 0,
    }


def validate_global_commerce_dimension_registry(root: Path) -> list[str]:
    errors: list[str] = []
    registry = load_global_commerce_dimension_registry(root, strict=True)
    truth = registry.get("truth_policy") if isinstance(registry.get("truth_policy"), dict) else {}
    if not truth.get("no_fake_connection"):
        errors.append("truth_policy.no_fake_connection must be true")
    if truth.get("external_actions") != 0:
        errors.append("truth_policy.external_actions must be 0")
    if not truth.get("parent_sku_only_for_sku_count"):
        errors.append("truth_policy.parent_sku_only_for_sku_count must be true")

    snapshot = global_commerce_dimension_snapshot(root)
    if snapshot["country_group_count"] < 8:
        errors.append("country_site_groups must cover at least 8 market regions")
    if snapshot["country_site_count"] < 35:
        errors.append("country_site_groups must include at least 35 country/site codes")
    if snapshot["product_family_count"] < 25:
        errors.append("product_families must include at least 25 families")
    if snapshot["product_attribute_count"] < 25:
        errors.append("product_attributes must include at least 25 attributes")
    missing_relationship_models = REQUIRED_RELATIONSHIP_MODEL_IDS - set(snapshot["commerce_relationship_model_ids"])
    if missing_relationship_models:
        errors.append(f"commerce_model_taxonomy.relationship_models missing {sorted(missing_relationship_models)}")
    missing_commerce_forms = REQUIRED_COMMERCE_FORM_IDS - set(snapshot["commerce_form_ids"])
    if missing_commerce_forms:
        errors.append(f"commerce_model_taxonomy.commerce_forms missing {sorted(missing_commerce_forms)}")

    taxonomy = commerce_model_taxonomy(root)
    if taxonomy["composition_policy"].get("commerce_forms") != "multiple_forms_allowed_per_project_store_or_product_line":
        errors.append("commerce_model_taxonomy.commerce_forms must be composable")
    for model_id, item in taxonomy["relationship_models"].items():
        if not _safe_list(item.get("typical_dimensions")):
            errors.append(f"relationship model {model_id} missing typical_dimensions")
    for form_id, item in taxonomy["commerce_forms"].items():
        if not _safe_list(item.get("typical_dimensions")):
            errors.append(f"commerce form {form_id} missing typical_dimensions")

    product_catalog = registry.get("product_dimension_catalog")
    product_catalog = product_catalog if isinstance(product_catalog, dict) else {}
    levels = set(str(item) for item in _safe_list(product_catalog.get("product_levels")))
    for required in {"product_family", "category", "parent_sku", "child_sku_or_variant", "listing", "supplier_offer", "factory_prototype"}:
        if required not in levels:
            errors.append(f"product_levels missing {required}")
    sku_policy = product_catalog.get("sku_count_policy") if isinstance(product_catalog.get("sku_count_policy"), dict) else {}
    if sku_policy.get("dashboard_primary_count") != "parent_sku":
        errors.append("sku_count_policy.dashboard_primary_count must be parent_sku")
    if sku_policy.get("child_sku_or_variant") != "reference_only":
        errors.append("sku_count_policy.child_sku_or_variant must be reference_only")

    axes = registry.get("operating_axes") if isinstance(registry.get("operating_axes"), dict) else {}
    for required_axis in ["seller_modes", "store_modes", "fulfillment_modes", "traffic_sources", "content_formats", "customer_touchpoints", "finance_axes"]:
        if len(_safe_list(axes.get(required_axis))) < 5:
            errors.append(f"operating_axes.{required_axis} must include at least 5 values")

    serialized = json.dumps(registry, ensure_ascii=False).lower()
    for word in {"connected", "running", "synced"}:
        if f'"{word}"' in serialized:
            errors.append(f"registry must not claim {word}")
    return errors
