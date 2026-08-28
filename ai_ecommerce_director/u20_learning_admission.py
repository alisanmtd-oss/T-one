from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit


USER_MATERIALS = Path("config/user_collected_training_materials.json")
COURSE_REGISTRY = Path("config/platform_course_short_distillation_registry.json")
LIBRARY_REGISTRY = Path("config/learning_direction_library_registry.json")
MEMORY_ROUTES = Path("config/user_collected_training_memory_routes.json")
EVAL_CASES = Path("config/u20_learning_admission_eval_cases.json")


def _load(root: Path, relative: Path) -> dict[str, Any]:
    payload = json.loads((root / relative).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"U20 registry must contain an object: {relative}")
    return payload


def _objects(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        clean = str(item or "").strip()
        if clean and clean not in result:
            result.append(clean)
    return result


def _canonical_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw)
    scheme = parsed.scheme.casefold() or "https"
    host = parsed.netloc.casefold()
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((scheme, host, path, parsed.query, ""))


def _route_index(routes: list[dict[str, Any]]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    admitted: dict[str, list[str]] = {}
    indexed: dict[str, list[str]] = {}
    for route in routes:
        route_id = str(route.get("id") or "")
        for source_id in _strings(route.get("source_ids")):
            admitted.setdefault(source_id, []).append(route_id)
        for source_id in _strings(route.get("indexed_source_ids")):
            indexed.setdefault(source_id, []).append(route_id)
    return admitted, indexed


def _material_state(item: Mapping[str, Any]) -> tuple[str, str, list[str]]:
    disposition = str(item.get("disposition") or "")
    if disposition.startswith("indexed_"):
        return "body_acquired_as_catalog", "index_catalog_only", ["unknown"]
    if "paused" in disposition:
        return "body_acquired_as_received", "preserved_paused", ["experience", "unknown"]
    if "hypoth" in disposition or "synthetic" in disposition:
        return "body_acquired_as_received", "reviewed_experience_memory", ["experience", "unknown"]
    if "distilled" in disposition:
        return "body_acquired_as_received", "reviewed_bounded_memory", ["experience", "unknown"]
    return "body_acquired_as_received", "review_required", ["unknown"]


def build_u20_learning_admission_snapshot(root: Path) -> dict[str, Any]:
    """Build a read-only truth snapshot; this function never fetches or installs anything."""

    root = Path(root).resolve()
    materials_payload = _load(root, USER_MATERIALS)
    courses_payload = _load(root, COURSE_REGISTRY)
    library_payload = _load(root, LIBRARY_REGISTRY)
    routes_payload = _load(root, MEMORY_ROUTES)
    eval_payload = _load(root, EVAL_CASES)
    routes = _objects(routes_payload.get("routes"))
    admitted_routes, indexed_routes = _route_index(routes)
    records: list[dict[str, Any]] = []

    for item in _objects(materials_payload.get("materials")):
        source_id = str(item.get("id") or "")
        body_state, admission_state, layers = _material_state(item)
        route_ids = admitted_routes.get(source_id, [])
        index_route_ids = indexed_routes.get(source_id, [])
        route_regression_ids = _strings(
            [
                regression_id
                for route in routes
                if str(route.get("id") or "") in route_ids
                for regression_id in _strings(route.get("regression_ids"))
            ]
        )
        if "U20-EVAL-03" not in route_regression_ids:
            route_regression_ids.append("U20-EVAL-03")
        if admission_state == "index_catalog_only":
            route_regression_ids = ["U20-EVAL-01", "U20-EVAL-02", "U20-EVAL-03"]
        records.append(
            {
                "source_id": source_id,
                "label": str(item.get("title") or source_id),
                "source_kind": "user_authorized_material",
                "dedupe_key": "sha256:" + str(item.get("sha256") or "").casefold(),
                "body_state": body_state,
                "source_completeness": str(item.get("source_completeness") or "unknown"),
                "admission_state": admission_state,
                "knowledge_layers": layers,
                "target_experts": _strings(item.get("target_experts")),
                "expert_route_ids": route_ids,
                "index_route_ids": index_route_ids,
                "regression_ids": route_regression_ids,
                "runtime_memory_eligible": bool(route_ids) and admission_state != "preserved_paused",
                "external_action_authorized": False,
            }
        )

    for index, item in enumerate(_objects(courses_payload.get("entries")), start=1):
        canonical_url = _canonical_url(item.get("url"))
        short_distillation = _strings(item.get("short_distillation"))
        verified_body = str(item.get("audit_state") or "") == "official_public_verified" and bool(
            short_distillation
        )
        records.append(
            {
                "source_id": f"COURSE-{index:03d}",
                "label": str(item.get("label") or canonical_url),
                "source_kind": "course_or_learning_website",
                "dedupe_key": "url:" + canonical_url,
                "canonical_url": canonical_url,
                "body_state": "bounded_public_body_acquired" if verified_body else "not_acquired",
                "source_completeness": "bounded_short_distillation" if verified_body else "index_only",
                "admission_state": str(item.get("distillation_state") or "index_only"),
                "knowledge_layers": ["fact", "unknown"] if verified_body else ["unknown"],
                "target_experts": _strings(item.get("target_experts")),
                "expert_route_ids": [],
                "index_route_ids": [],
                "regression_ids": ["U20-EVAL-01", "U20-EVAL-05"] if verified_body else ["U20-EVAL-01"],
                "runtime_memory_eligible": False,
                "next_safe_step": str(item.get("next_safe_step") or ""),
                "external_action_authorized": False,
            }
        )

    for item in _objects(library_payload.get("public_reference_sources")):
        canonical_url = _canonical_url(item.get("url"))
        distilled_ref = str(item.get("distilled_reference") or "")
        evidence_ref = str(item.get("evidence_report") or "")
        body_acquired = (
            int(item.get("content_blocks") or 0) > 0
            and bool(distilled_ref)
            and bool(evidence_ref)
            and (root / distilled_ref).is_file()
            and (root / evidence_ref).is_file()
        )
        records.append(
            {
                "source_id": str(item.get("source_id") or "PUBLIC-REFERENCE"),
                "label": str(item.get("title") or canonical_url),
                "source_kind": str(item.get("source_type") or "public_reference"),
                "dedupe_key": "url:" + canonical_url,
                "canonical_url": canonical_url,
                "body_state": "lawfully_read_public_body" if body_acquired else "not_acquired",
                "source_completeness": f"{int(item.get('content_blocks') or 0)}_content_blocks",
                "admission_state": str(item.get("status") or "review_required"),
                "knowledge_layers": ["fact", "experience", "unknown"] if body_acquired else ["unknown"],
                "target_experts": ["t_one_control_plane"],
                "expert_route_ids": ["t-one-operating-brain"] if body_acquired else [],
                "index_route_ids": [],
                "regression_ids": ["U20-EVAL-02", "U20-EVAL-04"] if body_acquired else ["U20-EVAL-01"],
                "runtime_memory_eligible": False,
                "external_action_authorized": False,
            }
        )

    by_dedupe: dict[str, list[str]] = {}
    for record in records:
        by_dedupe.setdefault(str(record["dedupe_key"]), []).append(str(record["source_id"]))
    duplicate_groups = [ids for ids in by_dedupe.values() if len(ids) > 1]
    index_only_records = [
        item
        for item in records
        if item["body_state"] in {"not_acquired", "body_acquired_as_catalog"}
        and not item["runtime_memory_eligible"]
    ]
    body_acquired_records = [
        item
        for item in records
        if item["body_state"] not in {"not_acquired", "body_acquired_as_catalog"}
    ]
    routed_memory_records = [item for item in records if item["expert_route_ids"]]
    eval_cases = _objects(eval_payload.get("cases"))
    return {
        "schema_version": 1,
        "classification": "u20_lawful_learning_admission_truth",
        "records": records,
        "counts": {
            "source_records": len(records),
            "body_acquired": len(body_acquired_records),
            "index_only_or_blocked": len(index_only_records),
            "runtime_memory_routed": len(routed_memory_records),
            "deduplicated_source_keys": len(by_dedupe),
            "duplicate_groups": len(duplicate_groups),
            "regression_cases": len(eval_cases),
            "external_actions": 0,
        },
        "duplicate_groups": duplicate_groups,
        "regression_case_ids": [str(item.get("id") or "") for item in eval_cases],
        "truth_contract": {
            "index_is_body": False,
            "index_is_distilled_memory": False,
            "indexed_promoted_to_memory_count": 0,
            "knowledge_layers": ["fact", "experience", "unknown"],
            "raw_attachment_loaded_at_runtime": False,
            "external_model_training_claimed": False,
            "amazon_state": "paused_by_owner",
            "external_action_authorized": False,
        },
        "owner_input_required": any(item["body_state"] == "not_acquired" for item in records),
        "owner_input_blocker": (
            "Provide one exact legally obtained export/body and its permission scope for any restricted or unreadable source; "
            "an index alone remains unlearned."
        ),
    }
