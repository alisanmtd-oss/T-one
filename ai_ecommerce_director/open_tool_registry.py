"""User-managed tools for the existing T One settings surface.

Registration is deliberately provider-neutral.  It records how a tool should be
reached and where it may run, but it never treats a saved record as a verified
connection and never stores raw credentials.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any


REGISTRY_PATH = Path("data") / "open_tool_registry.json"
STORE_SCOPE_FIELDS = (
    "project_id",
    "platform",
    "country_site",
    "store_mode",
    "store_binding_id",
    "account_id",
    "execution_identity_ref",
)
_SECRET_PATTERN = re.compile(
    r"(?:api[_-]?key|access[_-]?token|secret|password|passwd)\s*[=:]",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _text(value: Any, *, field: str, maximum: int, required: bool = False) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise ValueError(f"{field} is required.")
    if len(result) > maximum:
        raise ValueError(f"{field} is too long.")
    return result


def _load(root: Path) -> dict[str, Any]:
    path = root / REGISTRY_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        payload = {}
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("The local tool registry is not readable.") from exc
    tools = payload.get("tools") if isinstance(payload, dict) else None
    return {
        "schema_version": 1,
        "updated_at": str(payload.get("updated_at") or "") if isinstance(payload, dict) else "",
        "tools": [item for item in (tools or []) if isinstance(item, dict)],
    }


def _save(root: Path, payload: dict[str, Any]) -> None:
    path = root / REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def open_tool_registry_snapshot(root: Path) -> dict[str, Any]:
    payload = _load(root)
    tools = sorted(
        payload["tools"],
        key=lambda item: (str(item.get("name") or "").casefold(), str(item.get("id") or "")),
    )
    return {
        "ok": True,
        "schema_version": 1,
        "updated_at": payload.get("updated_at") or "",
        "tools": tools,
        "registered_count": len(tools),
        "connected_count": sum(1 for item in tools if item.get("connected") is True),
        "supported_kinds": [
            "API",
            "MCP",
            "本地程序",
            "命令行",
            "Skill",
            "Plugin",
            "Agent",
            "自动化",
            "其他",
        ],
    }


def record_open_tool_connection_verification(
    root: Path,
    tool_id: str,
    verification: dict[str, Any],
) -> dict[str, Any]:
    """Persist a completed live handshake without storing credentials or tool schemas."""

    if not isinstance(verification, dict):
        raise TypeError("verification must be an object.")
    normalized_tool_id = _text(tool_id, field="tool_id", maximum=80, required=True)
    payload = _load(root)
    record = next(
        (item for item in payload["tools"] if item.get("id") == normalized_tool_id),
        None,
    )
    if record is None:
        raise ValueError("Registered tool was not found.")

    tool_count = verification.get("discovered_tool_count")
    if isinstance(tool_count, bool) or not isinstance(tool_count, int) or tool_count < 0:
        raise ValueError("discovered_tool_count must be a non-negative integer.")
    enabled_tool_count = verification.get("enabled_tool_count", tool_count)
    if (
        isinstance(enabled_tool_count, bool)
        or not isinstance(enabled_tool_count, int)
        or enabled_tool_count < 0
        or enabled_tool_count > tool_count
    ):
        raise ValueError(
            "enabled_tool_count must be between zero and discovered_tool_count."
        )

    timestamp = _now()
    record.update(
        {
            "status": "connected_verified",
            "connected": True,
            "server_name": _text(
                verification.get("server_name"),
                field="server_name",
                maximum=160,
                required=True,
            ),
            "server_version": _text(
                verification.get("server_version"),
                field="server_version",
                maximum=80,
            ),
            "protocol_version": _text(
                verification.get("protocol_version"),
                field="protocol_version",
                maximum=80,
                required=True,
            ),
            "discovered_tool_count": tool_count,
            "enabled_tool_count": enabled_tool_count,
            "verified_at": timestamp,
            "updated_at": timestamp,
            "external_actions": int(record.get("external_actions") or 0),
        }
    )
    payload["updated_at"] = timestamp
    _save(root, payload)
    return {
        "ok": True,
        "tool": record,
        "connected": True,
        "external_actions": record["external_actions"],
    }


def register_open_tool(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise TypeError("Tool registration must be an object.")

    name = _text(request.get("name"), field="name", maximum=120, required=True)
    kind = _text(request.get("kind"), field="kind", maximum=64, required=True)
    connection_ref = _text(
        request.get("connection_ref"),
        field="connection_ref",
        maximum=2048,
        required=True,
    )
    credential_ref = _text(
        request.get("credential_ref"), field="credential_ref", maximum=240
    )
    if _SECRET_PATTERN.search(connection_ref) or _SECRET_PATTERN.search(credential_ref):
        raise ValueError("Do not paste raw keys, tokens, secrets or passwords; use a credential reference.")

    installation_status = _text(
        request.get("installation_status") or "unknown",
        field="installation_status",
        maximum=40,
        required=True,
    ).lower()
    if installation_status not in {
        "unknown",
        "not_installed",
        "installed",
        "not_applicable",
    }:
        raise ValueError("installation_status is not supported.")
    availability_note = _text(
        request.get("availability_note"), field="availability_note", maximum=300
    )

    raw_capabilities = request.get("capabilities")
    if isinstance(raw_capabilities, str):
        raw_capabilities = re.split(r"[,，\n]", raw_capabilities)
    if raw_capabilities is None:
        raw_capabilities = []
    if not isinstance(raw_capabilities, list):
        raise ValueError("capabilities must be a list or comma-separated text.")
    capabilities = []
    for item in raw_capabilities:
        value = _text(item, field="capability", maximum=80)
        if value and value not in capabilities:
            capabilities.append(value)
    if len(capabilities) > 40:
        raise ValueError("Too many capabilities.")

    scope_mode = _text(
        request.get("scope_mode") or "shared",
        field="scope_mode",
        maximum=20,
        required=True,
    ).lower()
    if scope_mode not in {"shared", "store"}:
        raise ValueError("scope_mode must be shared or store.")
    scope: dict[str, str] = {"mode": scope_mode}
    if scope_mode == "store":
        for field in STORE_SCOPE_FIELDS:
            scope[field] = _text(
                request.get(field), field=field, maximum=160, required=True
            )

    fingerprint_source = json.dumps(
        {
            "name": name.casefold(),
            "kind": kind.casefold(),
            "connection_ref": connection_ref,
            "scope": scope,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    tool_id = "tool-" + sha256(fingerprint_source.encode("utf-8")).hexdigest()[:16]
    timestamp = _now()
    record = {
        "id": tool_id,
        "name": name,
        "kind": kind,
        "connection_ref": connection_ref,
        "credential_ref": credential_ref,
        "capabilities": capabilities,
        "installation_status": installation_status,
        "availability_note": availability_note,
        "scope": scope,
        "status": "registered_unverified",
        "connected": False,
        "external_actions": 0,
        "updated_at": timestamp,
    }

    payload = _load(root)
    existing_index = next(
        (index for index, item in enumerate(payload["tools"]) if item.get("id") == tool_id),
        None,
    )
    if existing_index is None:
        record["created_at"] = timestamp
        payload["tools"].append(record)
        deduplicated = False
    else:
        record["created_at"] = str(
            payload["tools"][existing_index].get("created_at") or timestamp
        )
        payload["tools"][existing_index] = record
        deduplicated = True
    payload["updated_at"] = timestamp
    _save(root, payload)
    return {
        "ok": True,
        "tool": record,
        "deduplicated": deduplicated,
        "connected": False,
        "external_actions": 0,
    }
