from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterator


STORE_PLATFORMS = {
    "amazon",
    "ebay",
    "etsy",
    "lazada",
    "shein",
    "shopee",
    "shopify",
    "tiktok_shop",
    "walmart",
    "woocommerce",
}


def _records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _record_refs(value: Any) -> list[dict[str, Any]]:
    """Return mutable records for traversal without cloning the workspace tree."""

    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _channel_id(platform: str, country: str) -> str:
    platform = str(platform or "general").strip().lower().replace("_", "-")
    country = str(country or "global").strip().lower()
    return f"{platform}-{country}"


def _store_binding_id(task: dict[str, Any]) -> str:
    task_id = str(task.get("id") or "store").strip().lower()
    return str(task.get("store_binding_id") or f"{task_id}-store").strip().lower()


def _enrich_task(
    task: dict[str, Any],
    *,
    project: dict[str, Any],
    channel: dict[str, Any] | None = None,
    store: dict[str, Any] | None = None,
    scope_type: str,
) -> dict[str, Any]:
    enriched = dict(task)
    enriched["project_id"] = str(project.get("id") or "")
    enriched["scope_type"] = scope_type
    if channel is not None:
        enriched["channel_id"] = str(channel.get("id") or "")
        enriched["platform"] = str(channel.get("platform") or "")
        country = str(channel.get("country_site") or channel.get("country") or "")
        enriched["country"] = country
        enriched["country_site"] = country
    if store is not None:
        enriched["store_binding_id"] = str(store.get("id") or "")
        external_id = str(
            store.get("external_id")
            or store.get("store_external_id")
            or store.get("id")
            or ""
        )
        enriched["store_id"] = external_id
        enriched["store_external_id"] = external_id
        profile_sequence = (
            store.get("browser_profile_sequence")
            or store.get("browser_profile_seq")
            or 0
        )
        enriched["browser_profile_sequence"] = profile_sequence
        enriched["browser_profile_seq"] = profile_sequence
        for key in (
            "browser_provider",
            "browser_profile_id",
            "browser_binding_status",
            "store_model",
            "ownership",
            "route_key",
            "execution_identity_id",
            "credential_ref",
            "erp_connector_id",
            "ad_account_identity",
            "credential_ref_type",
            "scope_status",
            "connection_updated_at",
            "connection_updated_by",
        ):
            enriched[key] = deepcopy(store.get(key)) if key in store else ""
        enriched["execution_domains"] = [
            str(item)
            for item in store.get("execution_domains", [])
            if str(item).strip()
        ] if isinstance(store.get("execution_domains"), list) else []
        enriched["execution_scopes"] = [
            deepcopy(item)
            for item in store.get("execution_scopes", [])
            if isinstance(item, dict)
        ] if isinstance(store.get("execution_scopes"), list) else []
    return enriched


def _normalize_v3_project(raw_project: dict[str, Any]) -> dict[str, Any]:
    project = dict(raw_project)
    channels: list[dict[str, Any]] = []
    flat_tasks: list[dict[str, Any]] = []
    seen_channel_ids: set[str] = set()
    seen_store_ids: set[str] = set()

    for raw_channel in _records(raw_project.get("channels")):
        channel = dict(raw_channel)
        platform = str(channel.get("platform") or "general").strip().lower()
        country = str(
            channel.get("country_site") or channel.get("country") or "GLOBAL"
        ).strip().upper()
        channel_id = str(channel.get("id") or _channel_id(platform, country)).strip().lower()
        if channel_id in seen_channel_ids:
            continue
        seen_channel_ids.add(channel_id)
        channel.update(
            {
                "id": channel_id,
                "platform": platform,
                "country_site": country,
            }
        )
        stores: list[dict[str, Any]] = []
        for raw_store in _records(channel.get("stores")):
            store = dict(raw_store)
            store_id = str(store.get("id") or "").strip().lower()
            if not store_id or store_id in seen_store_ids:
                continue
            seen_store_ids.add(store_id)
            store.update(
                {
                    "id": store_id,
                    "project_id": str(project.get("id") or ""),
                    "channel_id": channel_id,
                    "platform": platform,
                    "country_site": country,
                }
            )
            tasks: list[dict[str, Any]] = []
            for raw_task in _records(store.get("tasks")):
                task = _enrich_task(
                    raw_task,
                    project=project,
                    channel=channel,
                    store=store,
                    scope_type="store_task",
                )
                tasks.append(task)
                flat_tasks.append(task)
            store["tasks"] = tasks
            stores.append(store)
        channel["stores"] = stores
        channel["store_count"] = len(stores)
        channel["task_count"] = sum(len(item.get("tasks") or []) for item in stores)
        channels.append(channel)

    workstreams: list[dict[str, Any]] = []
    for raw_task in _records(raw_project.get("workstreams")):
        task = _enrich_task(
            raw_task,
            project=project,
            scope_type="project_workstream",
        )
        workstreams.append(task)
        flat_tasks.append(task)

    project["channels"] = channels
    project["workstreams"] = workstreams
    # Compatibility view for existing task configuration, execution and reports.
    # New code must use channels/stores for identity and never infer a store from this list.
    project["tasks"] = flat_tasks
    project["store_count"] = sum(len(item.get("stores") or []) for item in channels)
    project["task_count"] = len(flat_tasks)
    return project


def _migrate_v2_project(raw_project: dict[str, Any]) -> dict[str, Any]:
    project = {key: deepcopy(value) for key, value in raw_project.items() if key != "tasks"}
    channel_map: dict[tuple[str, str], dict[str, Any]] = {}
    workstreams: list[dict[str, Any]] = []
    for task in _records(raw_project.get("tasks")):
        platform = str(task.get("platform") or "general").strip().lower()
        country = str(task.get("country") or "GLOBAL").strip().upper()
        has_store_identity = bool(task.get("store_id")) or platform in STORE_PLATFORMS
        if not has_store_identity:
            workstreams.append(task)
            continue
        key = (platform, country)
        channel = channel_map.setdefault(
            key,
            {
                "id": _channel_id(platform, country),
                "name": f"{platform.replace('_', ' ').title()} {country}",
                "platform": platform,
                "country_site": country,
                "status": "legacy_compatibility",
                "stores": [],
            },
        )
        binding_id = _store_binding_id(task)
        channel["stores"].append(
            {
                "id": binding_id,
                "name": str(task.get("name") or binding_id),
                "status": str(task.get("status") or "legacy_unverified"),
                "external_id": str(task.get("store_id") or binding_id),
                "store_model": str(task.get("store_model") or ""),
                "ownership": str(task.get("ownership") or ""),
                "route_key": str(task.get("route_key") or ""),
                "browser_provider": str(task.get("browser_provider") or ""),
                "browser_profile_id": str(task.get("browser_profile_id") or ""),
                "browser_profile_sequence": task.get("browser_profile_sequence") or "",
                "browser_profile_seq": task.get("browser_profile_seq") or "",
                "execution_identity_id": str(task.get("execution_identity_id") or ""),
                "credential_ref_type": str(task.get("credential_ref_type") or ""),
                "execution_domains": [
                    str(item)
                    for item in task.get("execution_domains", [])
                    if str(item).strip()
                ] if isinstance(task.get("execution_domains"), list) else [],
                "tasks": [task],
                "legacy_inferred": not bool(task.get("store_id")),
            }
        )
    project["channels"] = list(channel_map.values())
    project["workstreams"] = workstreams
    project["legacy_schema_source"] = 2
    return _normalize_v3_project(project)


def normalize_workspace_config(payload: dict[str, Any]) -> dict[str, Any]:
    """Return schema v3 while retaining a read-only flattened task compatibility view."""

    workspace = deepcopy(payload) if isinstance(payload, dict) else {}
    source_version = int(workspace.get("schema_version") or 2)
    projects: list[dict[str, Any]] = []
    for raw_project in _records(workspace.get("projects")):
        if source_version >= 3 or "channels" in raw_project or "workstreams" in raw_project:
            projects.append(_normalize_v3_project(raw_project))
        else:
            projects.append(_migrate_v2_project(raw_project))
    workspace["schema_version"] = 3
    workspace["source_schema_version"] = source_version
    workspace["projects"] = projects
    return workspace


def iter_project_stores(project: dict[str, Any]) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    for channel in _record_refs(project.get("channels")):
        for store in _record_refs(channel.get("stores")):
            yield channel, store


def iter_project_tasks(
    project: dict[str, Any],
) -> Iterator[tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]]:
    for channel, store in iter_project_stores(project):
        for task in _record_refs(store.get("tasks")):
            yield channel, store, task
    for task in _record_refs(project.get("workstreams")):
        yield None, None, task


def find_store(
    workspace: dict[str, Any], store_binding_id: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    requested = str(store_binding_id or "").strip().lower()
    for project in _record_refs(workspace.get("projects")):
        for channel, store in iter_project_stores(project):
            if str(store.get("id") or "").strip().lower() == requested:
                return project, channel, store
    return None


def find_store_in_project(
    workspace: dict[str, Any], project_id: str, store_binding_id: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    """Find a store by its composite project/store identity.

    Store identifiers are only required to be unique inside one project.  A
    global lookup can therefore select a same-named store from the wrong
    project in a multi-tenant workspace.
    """

    requested_project = str(project_id or "").strip().lower()
    requested_store = str(store_binding_id or "").strip().lower()
    for project in _record_refs(workspace.get("projects")):
        if str(project.get("id") or "").strip().lower() != requested_project:
            continue
        for channel, store in iter_project_stores(project):
            if str(store.get("id") or "").strip().lower() == requested_store:
                return project, channel, store
        return None
    return None


def find_task_context(
    workspace: dict[str, Any], task_id: str
) -> tuple[
    dict[str, Any],
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any],
] | None:
    requested = str(task_id or "").strip().lower()
    for project in _record_refs(workspace.get("projects")):
        for channel, store, task in iter_project_tasks(project):
            if str(task.get("id") or "").strip().lower() == requested:
                return project, channel, store, task
    return None
