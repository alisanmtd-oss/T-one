from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .workspace_runtime import workspace_item_context


STATE_RELATIVE_PATH = Path("data") / "external_access_gateway.json"
CONTRACT_RELATIVE_PATH = Path("config") / "external_access_contract.json"
MAX_CLIENTS = 100
MAX_DRAFTS = 500
MAX_EVENTS = 1000
PBKDF2_ITERATIONS = 210_000
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
EMAIL = re.compile(r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])", re.I)
PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)")
ISO_DATE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
SECRET_KEYS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "api_key",
    "password",
    "cookie",
    "session_cookie",
    "authorization",
    "credential",
    "credentials",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(default)
    return payload if isinstance(payload, dict) else dict(default)


def _contract(root: Path) -> dict[str, Any]:
    payload = _read_json(root / CONTRACT_RELATIVE_PATH, {})
    if not isinstance(payload.get("client_types"), list):
        raise ValueError("External access contract is missing client_types.")
    return payload


def _state(root: Path) -> dict[str, Any]:
    payload = _read_json(
        root / STATE_RELATIVE_PATH,
        {"schema_version": 1, "clients": [], "drafts": [], "events": []},
    )
    for key in ("clients", "drafts", "events"):
        if not isinstance(payload.get(key), list):
            payload[key] = []
    payload["schema_version"] = 1
    return payload


def _save_state(root: Path, state: dict[str, Any]) -> None:
    path = root / STATE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    state["clients"] = list(state.get("clients") or [])[-MAX_CLIENTS:]
    state["drafts"] = list(state.get("drafts") or [])[-MAX_DRAFTS:]
    state["events"] = list(state.get("events") or [])[-MAX_EVENTS:]
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _workspace(root: Path) -> dict[str, Any]:
    payload = _read_json(root / "config" / "workspace_projects.json", {})
    if not isinstance(payload.get("projects"), list):
        payload["projects"] = []
    return payload


def _clean_id(value: Any, label: str) -> str:
    text = str(value or "").strip().casefold()
    if not SAFE_ID.fullmatch(text):
        raise ValueError(f"{label} must be a stable identifier.")
    return text


def _clean_id_list(values: Any, label: str, *, required: bool = False) -> list[str]:
    if values is None:
        values = []
    if not isinstance(values, list):
        raise ValueError(f"{label} must be a list.")
    output: list[str] = []
    for value in values:
        item = _clean_id(value, label)
        if item not in output:
            output.append(item)
    if required and not output:
        raise ValueError(f"{label} must include at least one exact identifier.")
    return output


def _find_secret_field(value: Any, path: str = "payload") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().casefold()
            if normalized in SECRET_KEYS or normalized.endswith("_secret"):
                return f"{path}.{key}"
            found = _find_secret_field(child, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_secret_field(child, f"{path}[{index}]")
            if found:
                return found
    return None


def _reject_sensitive_text(value: str, label: str) -> str:
    text = str(value or "").strip()
    phone_scan_text = ISO_DATE.sub("", text)
    if EMAIL.search(text) or PHONE.search(phone_scan_text):
        raise ValueError(f"{label} must not contain raw personal contact data.")
    lowered = text.casefold()
    if any(marker in lowered for marker in ("bearer ", "access_token", "refresh_token", "client_secret", "api_key=")):
        raise ValueError(f"{label} must not contain credentials.")
    return text


def _client_type(contract: dict[str, Any], client_type: str) -> dict[str, Any]:
    for item in contract.get("client_types") or []:
        if isinstance(item, dict) and str(item.get("id") or "") == client_type:
            return item
    raise ValueError("Unknown external client type.")


def _workspace_index(root: Path) -> tuple[dict[str, dict[str, Any]], set[str], set[str]]:
    projects: dict[str, dict[str, Any]] = {}
    tasks: set[str] = set()
    stores: set[str] = set()
    for project in _workspace(root).get("projects") or []:
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id") or "").strip().casefold()
        if not project_id:
            continue
        projects[project_id] = project
        for stream in project.get("workstreams") or []:
            if isinstance(stream, dict) and stream.get("id"):
                tasks.add(str(stream["id"]).strip().casefold())
        for channel in project.get("channels") or []:
            if not isinstance(channel, dict):
                continue
            for store in channel.get("stores") or []:
                if not isinstance(store, dict):
                    continue
                if store.get("id"):
                    stores.add(str(store["id"]).strip().casefold())
                for task in store.get("tasks") or []:
                    if isinstance(task, dict) and task.get("id"):
                        tasks.add(str(task["id"]).strip().casefold())
    return projects, tasks, stores


def _event(state: dict[str, Any], event_type: str, actor: str, **fields: Any) -> None:
    state.setdefault("events", []).append(
        {
            "id": f"external-event-{uuid4().hex[:16]}",
            "at": _now(),
            "type": event_type,
            "actor": str(actor or "unknown")[:120],
            **fields,
        }
    )


def _public_client(client: dict[str, Any]) -> dict[str, Any]:
    return {
        key: client.get(key)
        for key in (
            "id",
            "name",
            "client_type",
            "status",
            "scopes",
            "allowed_project_ids",
            "allowed_task_ids",
            "allowed_store_binding_ids",
            "token_prefix",
            "created_at",
            "created_by",
            "revoked_at",
            "revoked_by",
            "last_used_at",
        )
        if client.get(key) not in (None, "")
    }


def register_external_client(root: Path, payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Client registration must be an object.")
    secret_field = _find_secret_field(payload)
    if secret_field:
        raise ValueError(f"Raw credential fields are not accepted: {secret_field}.")
    contract = _contract(root)
    client_type_id = _clean_id(payload.get("client_type"), "client_type")
    client_type = _client_type(contract, client_type_id)
    if not str(client_type.get("status") or "").startswith("local_rest_contract_available") and client_type_id != "mcp_client":
        raise ValueError(str(client_type.get("reason") or "This client type is not available for registration."))
    requested_scopes = _clean_id_list(payload.get("scopes"), "scopes", required=True)
    allowed_scopes = {str(item) for item in client_type.get("allowed_scopes") or []}
    if not set(requested_scopes).issubset(allowed_scopes):
        raise ValueError("Requested scopes exceed the selected client contract.")
    allowed_projects = _clean_id_list(
        payload.get("allowed_project_ids"), "allowed_project_ids", required=True
    )
    allowed_tasks = _clean_id_list(payload.get("allowed_task_ids"), "allowed_task_ids")
    allowed_stores = _clean_id_list(
        payload.get("allowed_store_binding_ids"), "allowed_store_binding_ids"
    )
    projects, known_tasks, known_stores = _workspace_index(root)
    unknown_projects = sorted(set(allowed_projects) - set(projects))
    unknown_tasks = sorted(set(allowed_tasks) - known_tasks)
    unknown_stores = sorted(set(allowed_stores) - known_stores)
    if unknown_projects or unknown_tasks or unknown_stores:
        raise ValueError(
            "Unknown route identifiers: "
            + ", ".join(unknown_projects + unknown_tasks + unknown_stores)
        )
    name = _reject_sensitive_text(str(payload.get("name") or "")[:120], "name")
    if not name:
        raise ValueError("name is required.")

    raw_token = "tone_local_" + secrets.token_urlsafe(32)
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", raw_token.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    client = {
        "id": f"external-client-{uuid4().hex[:16]}",
        "name": name,
        "client_type": client_type_id,
        "status": "active",
        "scopes": requested_scopes,
        "allowed_project_ids": allowed_projects,
        "allowed_task_ids": allowed_tasks,
        "allowed_store_binding_ids": allowed_stores,
        "token_prefix": raw_token[:18] + "…",
        "token_salt": salt.hex(),
        "token_hash": digest.hex(),
        "created_at": _now(),
        "created_by": str(actor or "owner")[:120],
    }
    state = _state(root)
    state["clients"].append(client)
    _event(state, "client_registered", actor, client_id=client["id"], scopes=requested_scopes)
    _save_state(root, state)
    return {
        "ok": True,
        "client": _public_client(client),
        "token": raw_token,
        "token_notice": "Shown once. The raw token is not stored and cannot be recovered.",
        "external_side_effect_count": 0,
    }


def revoke_external_client(root: Path, client_id: str, *, actor: str) -> dict[str, Any]:
    normalized = _clean_id(client_id, "client_id")
    state = _state(root)
    for client in state["clients"]:
        if str(client.get("id") or "") != normalized:
            continue
        if client.get("status") != "revoked":
            client["status"] = "revoked"
            client["revoked_at"] = _now()
            client["revoked_by"] = str(actor or "owner")[:120]
            _event(state, "client_revoked", actor, client_id=normalized)
            _save_state(root, state)
        return {"ok": True, "client": _public_client(client), "external_side_effect_count": 0}
    raise ValueError("External client not found.")


def authenticate_external_client(root: Path, authorization_header: str) -> dict[str, Any]:
    header = str(authorization_header or "").strip()
    if not header.startswith("Bearer "):
        raise PermissionError("Bearer token is required.")
    raw_token = header[7:].strip()
    if not raw_token.startswith("tone_local_") or len(raw_token) < 32:
        raise PermissionError("Bearer token is invalid.")
    state = _state(root)
    for client in state["clients"]:
        if client.get("status") != "active":
            continue
        try:
            salt = bytes.fromhex(str(client.get("token_salt") or ""))
            expected = bytes.fromhex(str(client.get("token_hash") or ""))
        except ValueError:
            continue
        actual = hashlib.pbkdf2_hmac(
            "sha256", raw_token.encode("utf-8"), salt, PBKDF2_ITERATIONS
        )
        if hmac.compare_digest(actual, expected):
            return client
    raise PermissionError("Bearer token is invalid or revoked.")


def _require_scope(client: dict[str, Any], scope: str) -> None:
    if scope not in {str(item) for item in client.get("scopes") or []}:
        raise PermissionError(f"Missing required scope: {scope}.")


def _require_project(client: dict[str, Any], project_id: str) -> str:
    normalized = _clean_id(project_id, "project_id")
    if normalized not in {str(item) for item in client.get("allowed_project_ids") or []}:
        raise PermissionError("Project is outside this client's route scope.")
    return normalized


def read_external_project_context(
    root: Path, client: dict[str, Any], project_id: str
) -> dict[str, Any]:
    _require_scope(client, "context.read")
    normalized = _require_project(client, project_id)
    projects, _, _ = _workspace_index(root)
    project = projects.get(normalized)
    if not project:
        raise ValueError("Project not found.")
    task_scope = {str(item) for item in client.get("allowed_task_ids") or []}
    store_scope = {str(item) for item in client.get("allowed_store_binding_ids") or []}
    workstreams = []
    for item in project.get("workstreams") or []:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        item_id = str(item["id"]).strip().casefold()
        if task_scope and item_id not in task_scope:
            continue
        workstreams.append(
            {
                key: item.get(key)
                for key in ("id", "name", "status", "platform", "country", "product_id")
                if item.get(key) not in (None, "")
            }
        )
    channels = []
    for channel in project.get("channels") or []:
        if not isinstance(channel, dict):
            continue
        safe_stores = []
        for store in channel.get("stores") or []:
            if not isinstance(store, dict) or not store.get("id"):
                continue
            store_id = str(store["id"]).strip().casefold()
            if store_scope and store_id not in store_scope:
                continue
            safe_stores.append(
                {
                    key: store.get(key)
                    for key in ("id", "name", "status", "store_model", "ownership")
                    if store.get(key) not in (None, "")
                }
            )
        channels.append(
            {
                "id": channel.get("id"),
                "name": channel.get("name"),
                "platform": channel.get("platform"),
                "country_site": channel.get("country_site"),
                "status": channel.get("status"),
                "stores": safe_stores,
            }
        )
    state = _state(root)
    for candidate in state["clients"]:
        if candidate.get("id") == client.get("id"):
            candidate["last_used_at"] = _now()
    _event(state, "context_read", str(client.get("id") or "external"), client_id=client.get("id"), project_id=normalized)
    _save_state(root, state)
    workspace_context = workspace_item_context(root, "project", normalized)
    task_entry_manifests = []
    for workstream in workstreams:
        task_id = str(workstream.get("id") or "").strip().lower()
        try:
            task_entry_manifests.append(
                workspace_item_context(root, "task", task_id)["entry_manifest"]
            )
        except ValueError:
            continue
    return {
        "ok": True,
        "scope": "sanitized_project_context",
        "project": {
            "id": project.get("id"),
            "name": project.get("name"),
            "project_type": project.get("project_type"),
            "product_ids": list(project.get("product_ids") or []),
            "workstreams": workstreams,
            "channels": channels,
        },
        "workspace": {
            "local_folder": workspace_context["local_folder"],
            "entry_manifest": workspace_context["entry_manifest"],
            "paths": workspace_context["paths"],
            "task_entry_manifests": task_entry_manifests,
            "path_scope": workspace_context["path_scope"],
            "copy_policy": workspace_context["copy_policy"],
        },
        "credential_fields_returned": 0,
        "external_side_effect_count": 0,
    }


def submit_external_draft(
    root: Path,
    client: dict[str, Any],
    payload: dict[str, Any],
    *,
    idempotency_key: str,
) -> dict[str, Any]:
    _require_scope(client, "draft.submit")
    if not IDEMPOTENCY_KEY.fullmatch(str(idempotency_key or "")):
        raise ValueError("A stable 8-128 character Idempotency-Key is required.")
    if not isinstance(payload, dict):
        raise ValueError("Draft payload must be an object.")
    secret_field = _find_secret_field(payload)
    if secret_field:
        raise ValueError(f"Raw credential fields are not accepted: {secret_field}.")
    project_id = _require_project(client, payload.get("project_id"))
    task_id = _clean_id(payload.get("task_id"), "task_id")
    task_scope = {str(item) for item in client.get("allowed_task_ids") or []}
    if task_scope and task_id not in task_scope:
        raise PermissionError("Task is outside this client's route scope.")
    _, known_tasks, _ = _workspace_index(root)
    if task_id not in known_tasks:
        raise ValueError("Task not found.")
    if payload.get("requested_side_effects") not in (None, [], ()):
        raise ValueError("External drafts cannot request side effects.")
    title = _reject_sensitive_text(str(payload.get("title") or "")[:160], "title")
    instruction = _reject_sensitive_text(
        str(payload.get("instruction") or "")[:8000], "instruction"
    )
    if not title or not instruction:
        raise ValueError("title and instruction are required.")
    evidence_refs = payload.get("evidence_refs") or []
    if not isinstance(evidence_refs, list) or len(evidence_refs) > 20:
        raise ValueError("evidence_refs must be a list with at most 20 items.")
    safe_refs = [
        _reject_sensitive_text(str(item or "")[:240], "evidence_ref")
        for item in evidence_refs
        if str(item or "").strip()
    ]
    state = _state(root)
    for draft in state["drafts"]:
        if draft.get("client_id") == client.get("id") and draft.get("idempotency_key") == idempotency_key:
            return {"ok": True, "idempotent_replay": True, "draft": _public_draft(draft)}
    draft = {
        "id": f"external-draft-{uuid4().hex[:16]}",
        "client_id": client.get("id"),
        "project_id": project_id,
        "task_id": task_id,
        "title": title,
        "instruction": instruction,
        "evidence_refs": safe_refs,
        "idempotency_key": idempotency_key,
        "status": "owner_review_required",
        "execution_state": "not_enqueued",
        "external_side_effect_count": 0,
        "created_at": _now(),
    }
    state["drafts"].append(draft)
    _event(
        state,
        "draft_received",
        str(client.get("id") or "external"),
        client_id=client.get("id"),
        draft_id=draft["id"],
        project_id=project_id,
        task_id=task_id,
    )
    _save_state(root, state)
    return {"ok": True, "idempotent_replay": False, "draft": _public_draft(draft)}


def _public_draft(draft: dict[str, Any]) -> dict[str, Any]:
    return {
        key: draft.get(key)
        for key in (
            "id",
            "client_id",
            "project_id",
            "task_id",
            "title",
            "evidence_refs",
            "status",
            "execution_state",
            "external_side_effect_count",
            "created_at",
        )
    }


def read_external_draft(root: Path, client: dict[str, Any], draft_id: str) -> dict[str, Any]:
    _require_scope(client, "result.read")
    normalized = _clean_id(draft_id, "draft_id")
    state = _state(root)
    for draft in state["drafts"]:
        if draft.get("id") != normalized:
            continue
        if draft.get("client_id") != client.get("id"):
            raise PermissionError("Draft belongs to another client.")
        _event(state, "draft_status_read", str(client.get("id") or "external"), client_id=client.get("id"), draft_id=normalized)
        _save_state(root, state)
        return {"ok": True, "draft": _public_draft(draft)}
    raise ValueError("Draft not found.")


def external_access_control_snapshot(root: Path) -> dict[str, Any]:
    contract = _contract(root)
    state = _state(root)
    mcp_server = contract.get("mcp_server") if isinstance(contract.get("mcp_server"), dict) else {}
    clients = [_public_client(item) for item in state["clients"]]
    drafts = [_public_draft(item) for item in state["drafts"]]
    return {
        "schema_version": 1,
        "deployment": contract.get("deployment"),
        "authentication": contract.get("authentication") or {},
        "scopes": contract.get("scopes") or {},
        "client_types": contract.get("client_types") or [],
        "hard_boundaries": contract.get("hard_boundaries") or [],
        "mcp_server": mcp_server,
        "clients": clients,
        "drafts": drafts[-20:][::-1],
        "events": list(state.get("events") or [])[-20:][::-1],
        "active_client_count": sum(1 for item in clients if item.get("status") == "active"),
        "draft_count": len(drafts),
        "executed_draft_count": 0,
        "external_side_effect_count": 0,
        "raw_token_persisted": False,
        "mcp_server_implemented": mcp_server.get("implemented") is True,
    }
