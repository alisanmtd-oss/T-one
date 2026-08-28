from __future__ import annotations

from pathlib import Path
from typing import Any

from .communications_connector_control import communications_connector_snapshot
from .llm import LLMTool


SAFE_CONNECTOR_FIELDS = (
    "id",
    "name",
    "group",
    "protocol",
    "status",
    "supported",
    "required_authorization",
    "live_verification_supported",
    "credential_ref_configured",
    "account_identity_verified",
    "configured_binding_count",
    "verified_binding_count",
    "inbox_read_verified",
    "contact_sync_verified",
    "webhook_verified",
    "send_receipt_count",
    "publish_receipt_count",
)

CONNECTOR_CAPABILITY_FIELDS = {
    "account_identity": "account_identity_verified",
    "read_inbox": "inbox_read_verified",
    "sync_contacts": "contact_sync_verified",
    "subscribe_webhook": "webhook_verified",
    "send_message": "send_receipt_count",
    "publish_content": "publish_receipt_count",
}


def communications_connector_status(root: Path) -> dict[str, Any]:
    """Return a credential-free, read-only connector status projection."""

    snapshot = communications_connector_snapshot(root)
    connectors = [
        {field: item.get(field) for field in SAFE_CONNECTOR_FIELDS}
        for item in snapshot.get("connectors") or []
        if isinstance(item, dict)
    ]
    return {
        "connector_contract_count": int(snapshot.get("connector_contract_count") or 0),
        "configured_connection_count": int(snapshot.get("configured_connection_count") or 0),
        "verified_connection_count": int(snapshot.get("verified_connection_count") or 0),
        "unsupported_connector_count": int(snapshot.get("unsupported_connector_count") or 0),
        "connectors": connectors,
        "external_action_count": 0,
    }


def communications_connector_readiness(
    root: Path, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Explain which connector layer is actually usable without touching the network."""

    connector_id = str(arguments.get("connector_id") or "").strip()
    capability = str(arguments.get("capability") or "account_identity").strip()
    if capability not in CONNECTOR_CAPABILITY_FIELDS:
        raise ValueError(f"Unsupported connector capability: {capability}")

    snapshot = communications_connector_snapshot(root)
    connector = next(
        (
            item
            for item in snapshot.get("connectors") or []
            if isinstance(item, dict) and str(item.get("id") or "") == connector_id
        ),
        None,
    )
    if connector is None:
        return {
            "connector_id": connector_id,
            "requested_capability": capability,
            "contract_available": False,
            "adapter_available": False,
            "credential_configured": False,
            "account_identity_verified": False,
            "requested_capability_verified": False,
            "usable_for_model": False,
            "status": "unknown_connector",
            "next_step": "Register and audit the connector contract before configuring an account.",
            "external_action_count": 0,
        }

    supported = bool(connector.get("supported"))
    adapter_available = bool(connector.get("live_verification_supported"))
    credential_configured = bool(connector.get("credential_ref_configured"))
    identity_verified = bool(connector.get("account_identity_verified"))
    capability_field = CONNECTOR_CAPABILITY_FIELDS[capability]
    raw_capability_value = connector.get(capability_field)
    capability_verified = (
        int(raw_capability_value or 0) > 0
        if capability_field.endswith("_count")
        else bool(raw_capability_value)
    )

    required_authorization = [
        str(value)
        for value in connector.get("required_authorization") or []
        if str(value).strip()
    ]
    if not supported:
        next_step = "This connector is intentionally unsupported; use an official business API."
    elif not adapter_available:
        next_step = "No audited live adapter is registered for this connector."
    elif not credential_configured:
        authorization = ", ".join(required_authorization) or "the official account authorization"
        next_step = f"Complete authorization: {authorization}."
    elif not identity_verified:
        next_step = "Run the explicit read-only account identity verification in Settings."
    elif not capability_verified:
        next_step = (
            f"Account identity is verified, but {capability} has no verified runtime receipt. "
            "Configure an audited adapter and complete owner-approved verification."
        )
    else:
        next_step = "This read-only capability has a verified runtime receipt."

    return {
        "connector_id": connector_id,
        "connector_name": str(connector.get("name") or connector_id),
        "requested_capability": capability,
        "contract_available": True,
        "adapter_available": adapter_available,
        "credential_configured": credential_configured,
        "account_identity_verified": identity_verified,
        "requested_capability_verified": capability_verified,
        "usable_for_model": bool(supported and adapter_available and capability_verified),
        "status": str(connector.get("status") or "not_configured"),
        "next_step": next_step,
        "external_action_count": 0,
    }


def read_only_runtime_tools(root: Path) -> list[LLMTool]:
    """Tools that a model may use without an external side effect."""

    return [
        LLMTool(
            name="communications_connector_status",
            description=(
                "Read T-one's local communications connector readiness. "
                "This never logs in, reads messages, sends messages, or exposes credentials."
            ),
            parameters={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            handler=lambda _arguments: communications_connector_status(root),
        ),
        LLMTool(
            name="communications_connector_readiness",
            description=(
                "Check whether one communications connector capability is truly usable. "
                "This only reads local readiness and never logs in, reads content, or sends data."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "connector_id": {"type": "string"},
                    "capability": {
                        "type": "string",
                        "enum": list(CONNECTOR_CAPABILITY_FIELDS),
                    },
                },
                "required": ["connector_id", "capability"],
                "additionalProperties": False,
            },
            handler=lambda arguments: communications_connector_readiness(root, arguments),
        ),
    ]
