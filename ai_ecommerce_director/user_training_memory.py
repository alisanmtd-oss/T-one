from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


MEMORY_ROUTES_PATH = Path("config") / "user_collected_training_memory_routes.json"
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,159}$")


class UserTrainingMemoryError(ValueError):
    """Fail-closed error for invalid user-collected learning-memory routing."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise UserTrainingMemoryError(f"missing learning-memory file: {path}") from exc
    except ValueError as exc:
        raise UserTrainingMemoryError(f"invalid learning-memory JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise UserTrainingMemoryError(f"learning-memory file must contain an object: {path}")
    return payload


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", "-").replace(" ", "-")


def _ids(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = _normalise(value)
        if item and item not in result:
            result.append(item)
    return result


def load_user_training_memory_registry(root: Path) -> dict[str, Any]:
    """Load and validate the durable routing table without loading raw source text."""

    root = Path(root)
    routes_path = root / MEMORY_ROUTES_PATH
    routes = _load_json(routes_path)
    sources_path = root / str(routes.get("source_registry") or "")
    evaluations_path = root / str(routes.get("evaluation_registry") or "")
    sources = _load_json(sources_path)
    evaluations = _load_json(evaluations_path)
    if routes.get("raw_attachment_loading_allowed") is not False:
        raise UserTrainingMemoryError("raw attachment loading must remain disabled")
    if routes.get("external_action_authorized") is not False:
        raise UserTrainingMemoryError("learning memory cannot authorize external action")

    source_by_id = {
        str(item.get("id") or ""): item
        for item in sources.get("materials", [])
        if isinstance(item, Mapping) and str(item.get("id") or "")
    }
    evaluation_ids = {
        str(item.get("id") or "")
        for item in evaluations.get("cases", [])
        if isinstance(item, Mapping) and str(item.get("id") or "")
    }
    declared_targets = {
        str(target)
        for item in source_by_id.values()
        for target in item.get("target_experts", [])
        if str(target).strip()
    }
    routed_targets: set[str] = set()
    seen_route_ids: set[str] = set()
    validated_routes: list[dict[str, Any]] = []
    for index, raw_route in enumerate(routes.get("routes", [])):
        if not isinstance(raw_route, Mapping):
            raise UserTrainingMemoryError(f"routes[{index}] must be an object")
        route = dict(raw_route)
        route_id = _normalise(route.get("id"))
        if not SAFE_ID.fullmatch(route_id) or route_id in seen_route_ids:
            raise UserTrainingMemoryError(f"invalid or duplicate route id: {route_id}")
        seen_route_ids.add(route_id)
        consumers = _ids(route.get("consumer_ids", []))
        if not consumers:
            raise UserTrainingMemoryError(f"route {route_id} has no consumers")
        source_ids = [str(item) for item in route.get("source_ids", []) if str(item).strip()]
        indexed_source_ids = [
            str(item) for item in route.get("indexed_source_ids", []) if str(item).strip()
        ]
        if set(source_ids).intersection(indexed_source_ids):
            raise UserTrainingMemoryError(
                f"route {route_id} cannot promote an indexed source into distilled memory"
            )
        missing_sources = [
            item for item in source_ids + indexed_source_ids if item not in source_by_id
        ]
        if missing_sources:
            raise UserTrainingMemoryError(f"route {route_id} has missing sources: {missing_sources}")
        regression_ids = [str(item) for item in route.get("regression_ids", []) if str(item).strip()]
        missing_evaluations = [item for item in regression_ids if item not in evaluation_ids]
        if missing_evaluations:
            raise UserTrainingMemoryError(
                f"route {route_id} has missing evaluations: {missing_evaluations}"
            )
        memory_refs = [str(item) for item in route.get("memory_refs", []) if str(item).strip()]
        if not memory_refs:
            raise UserTrainingMemoryError(f"route {route_id} has no distilled memory reference")
        for memory_ref in memory_refs:
            if ".codex/attachments" in memory_ref.replace("\\", "/"):
                raise UserTrainingMemoryError(f"route {route_id} exposes a raw attachment")
            if not (root / memory_ref).is_file():
                raise UserTrainingMemoryError(f"route {route_id} memory is missing: {memory_ref}")
        index_refs = [str(item) for item in route.get("index_refs", []) if str(item).strip()]
        if indexed_source_ids and not index_refs:
            raise UserTrainingMemoryError(f"route {route_id} has indexed sources but no index reference")
        for index_ref in index_refs:
            if ".codex/attachments" in index_ref.replace("\\", "/"):
                raise UserTrainingMemoryError(f"route {route_id} exposes a raw attachment index")
            if not (root / index_ref).is_file():
                raise UserTrainingMemoryError(f"route {route_id} index is missing: {index_ref}")
        target_labels = [str(item) for item in route.get("target_labels", []) if str(item).strip()]
        routed_targets.update(target_labels)
        route["id"] = route_id
        route["consumer_ids"] = consumers
        route["source_ids"] = source_ids
        route["indexed_source_ids"] = indexed_source_ids
        route["regression_ids"] = regression_ids
        route["memory_refs"] = memory_refs
        route["index_refs"] = index_refs
        route["target_labels"] = target_labels
        validated_routes.append(route)

    missing_targets = sorted(declared_targets - routed_targets)
    if missing_targets:
        raise UserTrainingMemoryError(f"unrouted declared targets: {missing_targets}")
    return {
        "routes": validated_routes,
        "sources": source_by_id,
        "policy": dict(sources.get("policy") or {}),
        "source_registry": str(routes.get("source_registry") or ""),
        "evaluation_registry": str(routes.get("evaluation_registry") or ""),
        "raw_attachment_loading_allowed": False,
        "external_action_authorized": False,
    }


def resolve_user_training_memory(
    root: Path,
    consumer_ids: str | Iterable[str],
) -> dict[str, Any]:
    """Resolve safe, distilled learning memory for one specialist or control-plane task."""

    registry = load_user_training_memory_registry(root)
    requested = _ids([consumer_ids] if isinstance(consumer_ids, str) else consumer_ids)
    requested_set = set(requested)
    matched = [
        route
        for route in registry["routes"]
        if route.get("applies_to_all_platform_and_channel_experts")
        or requested_set.intersection(route.get("consumer_ids", []))
    ]
    source_ids: list[str] = []
    indexed_source_ids: list[str] = []
    memory_refs: list[str] = []
    index_refs: list[str] = []
    regression_ids: list[str] = []
    route_ids: list[str] = []
    execution_states: list[str] = []
    for route in matched:
        route_ids.append(str(route["id"]))
        execution_states.append(str(route.get("execution_state") or "knowledge_only"))
        for key, target in (
            ("source_ids", source_ids),
            ("indexed_source_ids", indexed_source_ids),
            ("memory_refs", memory_refs),
            ("index_refs", index_refs),
            ("regression_ids", regression_ids),
        ):
            for item in route.get(key, []):
                if item not in target:
                    target.append(item)
    materials = []
    for source_id in source_ids:
        source = registry["sources"][source_id]
        materials.append(
            {
                "id": source_id,
                "title": str(source.get("title") or ""),
                "sha256": str(source.get("sha256") or ""),
                "source_completeness": str(source.get("source_completeness") or "unknown"),
                "disposition": str(source.get("disposition") or ""),
                "adopted_topics": list(source.get("adopted_topics") or []),
                "quarantined_topics": list(source.get("quarantined_topics") or []),
            }
        )
    indexed_materials = []
    for source_id in indexed_source_ids:
        source = registry["sources"][source_id]
        indexed_materials.append(
            {
                "id": source_id,
                "title": str(source.get("title") or ""),
                "sha256": str(source.get("sha256") or ""),
                "source_completeness": str(source.get("source_completeness") or "unknown"),
                "disposition": str(source.get("disposition") or ""),
                "admission_state": "index_catalog_only",
                "runtime_memory_eligible": False,
            }
        )
    return {
        "consumer_ids": requested,
        "route_ids": route_ids,
        "source_ids": source_ids,
        "indexed_source_ids": indexed_source_ids,
        "materials": materials,
        "indexed_materials": indexed_materials,
        "memory_refs": memory_refs,
        "index_refs": index_refs,
        "regression_ids": regression_ids,
        "source_registry": registry["source_registry"],
        "evaluation_registry": registry["evaluation_registry"],
        "raw_text_loaded": False,
        "raw_public_reuse_allowed": bool(registry["policy"].get("raw_reuse_allowed", False)),
        "external_action_authorized": False,
        "preserved_paused": "preserved_paused" in execution_states,
    }
