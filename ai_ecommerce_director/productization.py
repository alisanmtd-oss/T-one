from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import append_record, read_records, update_record
from .types import IntakeRecord


DEFAULT_TENANT_ID = "tenant_internal_beta"
DEFAULT_WORKSPACE_ID = "workspace_ai_ecommerce_director"
DEFAULT_USER_ID = "user_local_owner"

PRIVATE_SCOPE = "customer_private"
GLOBAL_PATTERN_SCOPE = "global_pattern_library"
GLOBAL_RISK_SCOPE = "global_risk_library"

HIGH_RISK_ACTIONS = {
    "publish_listing",
    "update_listing",
    "change_price",
    "change_discount",
    "launch_ad",
    "adjust_ad",
    "join_campaign",
    "refund_order",
    "ship_order",
    "contact_creator",
    "upload_public_video",
    "authorize_app",
    "buy_ip_node",
    "change_store_setting",
    "export_private_knowledge",
    "delete_data",
}

DEFAULT_LICENSE_MODULES = [
    "data_import",
    "market_research",
    "video_breakdown",
    "listing_draft",
    "creator_library",
    "store_report",
    "approval_queue",
    "customer_feedback",
    "audit_log",
]


PERMISSIONS: list[dict[str, str]] = [
    {"permission_key": "tenant.view", "name": "View tenant"},
    {"permission_key": "workspace.view", "name": "View workspace"},
    {"permission_key": "workspace.create", "name": "Create workspace"},
    {"permission_key": "store.view", "name": "View store binding"},
    {"permission_key": "store.bind", "name": "Bind store"},
    {"permission_key": "data.import", "name": "Import private data"},
    {"permission_key": "data.view_private", "name": "View private knowledge"},
    {"permission_key": "pattern.view_global", "name": "View global pattern library"},
    {"permission_key": "risk.view_global", "name": "View global risk library"},
    {"permission_key": "report.view", "name": "View reports"},
    {"permission_key": "report.export", "name": "Export scoped reports"},
    {"permission_key": "agent.run_l0", "name": "Run read-only agent"},
    {"permission_key": "agent.run_l1", "name": "Run recommendation agent"},
    {"permission_key": "agent.run_l2", "name": "Generate drafts"},
    {"permission_key": "agent.run_l3", "name": "Queue execution with approval"},
    {"permission_key": "agent.run_l4", "name": "Auto execute reversible actions"},
    {"permission_key": "approval.request", "name": "Request approval"},
    {"permission_key": "approval.approve", "name": "Approve sensitive actions"},
    {"permission_key": "audit.view", "name": "View audit log"},
    {"permission_key": "feedback.submit", "name": "Submit feedback"},
    {"permission_key": "license.view", "name": "View license status"},
    {"permission_key": "finance.view", "name": "View finance data"},
    {"permission_key": "supplier.view", "name": "View supplier data"},
    {"permission_key": "local_connector.use", "name": "Use local connector"},
]

ROLES: list[dict[str, Any]] = [
    {"role_id": "role_owner", "role": "owner", "max_automation_level": 4},
    {"role_id": "role_admin", "role": "admin", "max_automation_level": 3},
    {"role_id": "role_operator", "role": "operator", "max_automation_level": 2},
    {"role_id": "role_analyst", "role": "analyst", "max_automation_level": 2},
    {"role_id": "role_viewer", "role": "viewer", "max_automation_level": 0},
    {"role_id": "role_finance", "role": "finance", "max_automation_level": 1},
    {"role_id": "role_factory", "role": "factory", "max_automation_level": 1},
    {"role_id": "role_designer", "role": "designer", "max_automation_level": 1},
    {"role_id": "role_external_partner", "role": "external_partner", "max_automation_level": 2},
]

ROLE_PERMISSION_KEYS: dict[str, set[str]] = {
    "role_owner": {item["permission_key"] for item in PERMISSIONS},
    "role_admin": {
        "tenant.view",
        "workspace.view",
        "workspace.create",
        "store.view",
        "store.bind",
        "data.import",
        "data.view_private",
        "pattern.view_global",
        "risk.view_global",
        "report.view",
        "report.export",
        "agent.run_l0",
        "agent.run_l1",
        "agent.run_l2",
        "agent.run_l3",
        "approval.request",
        "approval.approve",
        "audit.view",
        "feedback.submit",
        "license.view",
        "finance.view",
        "supplier.view",
        "local_connector.use",
    },
    "role_operator": {
        "tenant.view",
        "workspace.view",
        "store.view",
        "data.import",
        "data.view_private",
        "pattern.view_global",
        "risk.view_global",
        "report.view",
        "agent.run_l0",
        "agent.run_l1",
        "agent.run_l2",
        "approval.request",
        "feedback.submit",
        "license.view",
        "local_connector.use",
    },
    "role_analyst": {
        "tenant.view",
        "workspace.view",
        "store.view",
        "data.view_private",
        "pattern.view_global",
        "risk.view_global",
        "report.view",
        "agent.run_l0",
        "agent.run_l1",
        "agent.run_l2",
        "feedback.submit",
        "license.view",
    },
    "role_viewer": {
        "tenant.view",
        "workspace.view",
        "store.view",
        "report.view",
        "agent.run_l0",
        "license.view",
    },
    "role_finance": {
        "tenant.view",
        "workspace.view",
        "store.view",
        "report.view",
        "finance.view",
        "feedback.submit",
        "license.view",
    },
    "role_factory": {
        "tenant.view",
        "workspace.view",
        "store.view",
        "report.view",
        "supplier.view",
        "feedback.submit",
        "license.view",
    },
    "role_designer": {
        "tenant.view",
        "workspace.view",
        "report.view",
        "feedback.submit",
        "license.view",
    },
    "role_external_partner": {
        "tenant.view",
        "workspace.view",
        "report.view",
        "agent.run_l0",
        "agent.run_l1",
        "agent.run_l2",
        "feedback.submit",
        "license.view",
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha1("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _record(record_type: str, record_id: str, fields: dict[str, Any], source: str = "productization") -> IntakeRecord:
    return IntakeRecord(
        record_id=record_id,
        record_type=record_type,
        fields=fields,
        raw_text=f"{record_type}:{record_id}",
        source=source,
        score={"productization": True},
        director_notes=[],
        review_status="approved",
        confidence=1.0,
        metadata={"seeded_by": "productization_layer_v1"} if source.endswith("seed") else {},
    )


def _append_seed(root: Path, record_type: str, record_id: str, fields: dict[str, Any]) -> None:
    append_record(root, _record(record_type, record_id, fields, source="productization_seed"))


def seed_productization_layer(root: Path) -> dict[str, Any]:
    """Create the minimum multi-tenant protection records if they do not exist."""

    created_at = now_iso()
    _append_seed(
        root,
        "tenant",
        DEFAULT_TENANT_ID,
        {
            "tenant_id": DEFAULT_TENANT_ID,
            "tenant_name": "Internal Closed Beta",
            "tenant_type": "internal_beta",
            "status": "active",
            "default_data_scope": PRIVATE_SCOPE,
            "created_at_utc": created_at,
        },
    )
    _append_seed(
        root,
        "workspace",
        DEFAULT_WORKSPACE_ID,
        {
            "workspace_id": DEFAULT_WORKSPACE_ID,
            "tenant_id": DEFAULT_TENANT_ID,
            "workspace_name": "AI Ecommerce Director",
            "workspace_type": "closed_beta",
            "status": "active",
            "max_automation_level": 4,
            "customer_private_scope": PRIVATE_SCOPE,
            "global_pattern_scope": GLOBAL_PATTERN_SCOPE,
            "created_at_utc": created_at,
        },
    )
    _append_seed(
        root,
        "user",
        DEFAULT_USER_ID,
        {
            "user_id": DEFAULT_USER_ID,
            "tenant_id": DEFAULT_TENANT_ID,
            "display_name": "Local Owner",
            "email": "",
            "status": "active",
            "created_at_utc": created_at,
        },
    )
    for role in ROLES:
        _append_seed(root, "role", role["role_id"], {**role, "tenant_id": DEFAULT_TENANT_ID, "status": "active"})
    for permission in PERMISSIONS:
        permission_id = stable_id("perm", permission["permission_key"])
        _append_seed(root, "permission", permission_id, {**permission, "permission_id": permission_id})
    for role_id, permission_keys in ROLE_PERMISSION_KEYS.items():
        for permission_key in sorted(permission_keys):
            role_permission_id = stable_id("role_perm", role_id, permission_key)
            _append_seed(
                root,
                "role_permission",
                role_permission_id,
                {
                    "role_permission_id": role_permission_id,
                    "role_id": role_id,
                    "permission_key": permission_key,
                    "granted": True,
                },
            )
    _append_seed(
        root,
        "user_role",
        stable_id("user_role", DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID, "role_owner"),
        {
            "user_role_id": stable_id("user_role", DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID, "role_owner"),
            "tenant_id": DEFAULT_TENANT_ID,
            "workspace_id": DEFAULT_WORKSPACE_ID,
            "user_id": DEFAULT_USER_ID,
            "role_id": "role_owner",
            "status": "active",
        },
    )
    _append_seed(
        root,
        "license",
        "license_internal_closed_beta",
        {
            "license_key": "license_internal_closed_beta",
            "tenant_id": DEFAULT_TENANT_ID,
            "workspace_id": DEFAULT_WORKSPACE_ID,
            "license_status": "active",
            "delivery_model": "cloud_brain_plus_local_connector",
            "allowed_modules": DEFAULT_LICENSE_MODULES,
            "max_stores": 20,
            "max_users": 10,
            "max_automation_level_external_customer": 2,
            "external_customer_default_level": "L2_generate_drafts_only",
            "payment_or_pricing_fields": "intentionally_excluded",
            "last_verified_at_utc": created_at,
        },
    )
    _append_seed(
        root,
        "beta_workspace",
        "beta_workspace_internal",
        {
            "beta_workspace_id": "beta_workspace_internal",
            "tenant_id": DEFAULT_TENANT_ID,
            "workspace_id": DEFAULT_WORKSPACE_ID,
            "status": "active",
            "allowed_features": [
                "manual_import",
                "csv_upload",
                "screenshot_capture",
                "read_only_api",
                "agent_draft",
                "feedback",
                "approval_queue",
            ],
            "blocked_features": [
                "auto_publish_listing",
                "auto_change_price",
                "auto_launch_ad",
                "auto_refund",
                "auto_ship",
                "auto_authorize_app",
            ],
            "created_at_utc": created_at,
        },
    )
    return {
        "ok": True,
        "seeded": True,
        "tenant_id": DEFAULT_TENANT_ID,
        "workspace_id": DEFAULT_WORKSPACE_ID,
        "user_id": DEFAULT_USER_ID,
    }


def _first_record_fields(root: Path, record_type: str, key: str, value: str, fallback_id: str | None = None) -> dict[str, Any]:
    records = read_records(root, record_type)
    for record in records:
        if str(record.fields.get(key) or "") == value:
            return {"record_id": record.record_id, **record.fields}
    if fallback_id:
        for record in records:
            if record.record_id == fallback_id:
                return {"record_id": record.record_id, **record.fields}
    return {}


def current_context(
    root: Path,
    headers: dict[str, Any] | None = None,
    query: dict[str, list[str]] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    seed_productization_layer(root)
    headers = headers or {}
    query = query or {}
    payload = payload or {}

    def pick(name: str, default: str) -> str:
        header_name = "X-" + "-".join(part.capitalize() for part in name.split("_"))
        return str(
            payload.get(name)
            or (query.get(name, [None])[0] if query.get(name) else None)
            or headers.get(header_name)
            or default
        )

    tenant_id = pick("tenant_id", DEFAULT_TENANT_ID)
    workspace_id = pick("workspace_id", DEFAULT_WORKSPACE_ID)
    user_id = pick("user_id", DEFAULT_USER_ID)
    tenant = _first_record_fields(root, "tenant", "tenant_id", tenant_id, DEFAULT_TENANT_ID)
    workspace = _first_record_fields(root, "workspace", "workspace_id", workspace_id, DEFAULT_WORKSPACE_ID)
    user = _first_record_fields(root, "user", "user_id", user_id, DEFAULT_USER_ID)
    return {
        "tenant_id": tenant.get("tenant_id", DEFAULT_TENANT_ID),
        "workspace_id": workspace.get("workspace_id", DEFAULT_WORKSPACE_ID),
        "user_id": user.get("user_id", DEFAULT_USER_ID),
        "tenant": tenant,
        "workspace": workspace,
        "user": user,
    }


def current_permissions(root: Path, context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or current_context(root)
    user_id = str(context.get("user_id") or DEFAULT_USER_ID)
    workspace_id = str(context.get("workspace_id") or DEFAULT_WORKSPACE_ID)
    user_roles = [
        record.fields
        for record in read_records(root, "user_role")
        if record.fields.get("user_id") == user_id
        and record.fields.get("status", "active") == "active"
        and record.fields.get("workspace_id") in {workspace_id, "", None}
    ]
    if not user_roles and user_id == DEFAULT_USER_ID:
        user_roles = [
            record.fields
            for record in read_records(root, "user_role")
            if record.fields.get("user_id") == DEFAULT_USER_ID
        ]
    role_ids = {str(role.get("role_id")) for role in user_roles}
    granted = {
        str(record.fields.get("permission_key"))
        for record in read_records(root, "role_permission")
        if record.fields.get("role_id") in role_ids and record.fields.get("granted", True)
    }
    roles = [record.fields for record in read_records(root, "role") if record.fields.get("role_id") in role_ids]
    max_level = max([int(role.get("max_automation_level") or 0) for role in roles] or [0])
    return {
        "tenant_id": context.get("tenant_id"),
        "workspace_id": workspace_id,
        "user_id": user_id,
        "roles": roles,
        "permissions": sorted(granted),
        "max_automation_level": max_level,
        "automation_policy": {
            "external_customer_default_max_level": 2,
            "high_risk_actions_require_approval": sorted(HIGH_RISK_ACTIONS),
            "local_connector_default_mode": "read_and_stage_only",
        },
    }


def has_permission(root: Path, permission_key: str, context: dict[str, Any] | None = None) -> bool:
    return permission_key in set(current_permissions(root, context).get("permissions", []))


def require_permission(root: Path, permission_key: str, context: dict[str, Any] | None = None) -> None:
    if not has_permission(root, permission_key, context):
        raise PermissionError(f"Missing permission: {permission_key}")


def write_audit_log(
    root: Path,
    context: dict[str, Any],
    action_type: str,
    resource_type: str,
    resource_id: str,
    result: str = "success",
    risk_level: str = "low",
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    request_metadata: dict[str, Any] | None = None,
) -> IntakeRecord:
    fields = {
        "audit_id": stable_id("audit", action_type, resource_type, resource_id, now_iso()),
        "tenant_id": context.get("tenant_id"),
        "workspace_id": context.get("workspace_id"),
        "user_id": context.get("user_id"),
        "action_type": action_type,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "result": result,
        "risk_level": risk_level,
        "before_state": before_state or {},
        "after_state": after_state or {},
        "request_metadata": request_metadata or {},
        "created_at_utc": now_iso(),
    }
    record = _record("audit_log", str(fields["audit_id"]), fields)
    append_record(root, record)
    return record


def create_workspace(root: Path, payload: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or current_context(root, payload=payload)
    require_permission(root, "workspace.create", context)
    name = str(payload.get("workspace_name") or payload.get("name") or "New Workspace").strip()
    workspace_id = str(payload.get("workspace_id") or stable_id("workspace", context.get("tenant_id"), name))
    fields = {
        "workspace_id": workspace_id,
        "tenant_id": context.get("tenant_id"),
        "workspace_name": name,
        "workspace_type": str(payload.get("workspace_type") or "customer_workspace"),
        "status": str(payload.get("status") or "active"),
        "max_automation_level": min(int(payload.get("max_automation_level") or 2), 2),
        "customer_private_scope": PRIVATE_SCOPE,
        "global_pattern_scope": GLOBAL_PATTERN_SCOPE,
        "created_at_utc": now_iso(),
    }
    append_record(root, _record("workspace", workspace_id, fields))
    write_audit_log(root, context, "workspace.create", "workspace", workspace_id, after_state=fields)
    return fields


def list_workspaces(root: Path, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    context = context or current_context(root)
    tenant_id = str(context.get("tenant_id") or "")
    return [
        {"record_id": record.record_id, **record.fields}
        for record in read_records(root, "workspace")
        if str(record.fields.get("tenant_id") or "") == tenant_id
    ]


def license_status(root: Path, context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or current_context(root)
    licenses = [
        record.fields
        for record in read_records(root, "license")
        if record.fields.get("tenant_id") == context.get("tenant_id")
        and record.fields.get("workspace_id") in {context.get("workspace_id"), "", None}
    ]
    license_record = licenses[0] if licenses else {}
    status = str(license_record.get("license_status") or "missing")
    mode = "normal" if status == "active" else "read_only"
    return {
        "tenant_id": context.get("tenant_id"),
        "workspace_id": context.get("workspace_id"),
        "license": license_record,
        "status": status,
        "runtime_mode": mode,
        "local_connector_boundary": {
            "can_read_authorized_exports": True,
            "can_stage_actions": True,
            "can_touch_passwords_cookies_or_browser_profiles": False,
            "can_execute_store_actions_without_approval": False,
        },
    }


_SENSITIVE_APPROVAL_KEY_PARTS = (
    "api_key",
    "apikey",
    "token",
    "cookie",
    "password",
    "secret",
    "credential",
    "authorization",
    "bearer",
    "buyer",
    "customer",
    "recipient",
    "email",
    "phone",
    "address",
    "local_path",
    "file_path",
    "raw_prompt",
    "system_prompt",
    "prompt",
    "training",
)

_SENSITIVE_APPROVAL_STRING_MARKERS = (
    "c:\\",
    "/users/",
    "sk-",
    "bearer ",
    "cookie:",
)


def _redact_approval_payload(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            lower_key = key_text.lower()
            if any(part in lower_key for part in _SENSITIVE_APPROVAL_KEY_PARTS):
                clean[key_text] = "[REDACTED]"
            else:
                clean[key_text] = _redact_approval_payload(item)
        return clean
    if isinstance(value, list):
        return [_redact_approval_payload(item) for item in value]
    if isinstance(value, str):
        lower_value = value.lower()
        if any(marker in lower_value for marker in _SENSITIVE_APPROVAL_STRING_MARKERS):
            return "[REDACTED]"
        return value
    return value


def create_approval_request(root: Path, payload: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or current_context(root, payload=payload)
    require_permission(root, "approval.request", context)
    action_type = str(payload.get("action_type") or "unspecified_action")
    approval_id = str(payload.get("approval_id") or stable_id("approval", context.get("workspace_id"), action_type, now_iso()))
    risk_score = int(payload.get("risk_score") or (90 if action_type in HIGH_RISK_ACTIONS else 30))
    raw_action_payload = payload.get("action_payload") if isinstance(payload.get("action_payload"), dict) else {}
    fields = {
        "approval_id": approval_id,
        "tenant_id": context.get("tenant_id"),
        "workspace_id": context.get("workspace_id"),
        "requested_by_user_id": context.get("user_id"),
        "requested_by_agent": str(payload.get("requested_by_agent") or "AI Ecommerce Director"),
        "action_type": action_type,
        "action_payload": _redact_approval_payload(raw_action_payload),
        "risk_score": risk_score,
        "risk_level": "high" if action_type in HIGH_RISK_ACTIONS or risk_score >= 80 else "medium",
        "reason": str(payload.get("reason") or ""),
        "status": "pending",
        "created_at_utc": now_iso(),
        "resolved_at_utc": "",
        "resolved_by_user_id": "",
        "resolution_note": "",
        "execute_allowed_before_approval": False if action_type in HIGH_RISK_ACTIONS else bool(payload.get("execute_allowed_before_approval", False)),
    }
    append_record(root, _record("approval_request", approval_id, fields))
    write_audit_log(root, context, "approval.request", "approval_request", approval_id, after_state=fields, risk_level=fields["risk_level"])
    return fields


def resolve_approval_request(
    root: Path,
    approval_id: str,
    decision: str,
    context: dict[str, Any] | None = None,
    note: str = "",
) -> dict[str, Any]:
    context = context or current_context(root)
    require_permission(root, "approval.approve", context)
    normalized_decision = "approved" if decision == "approve" else "rejected"
    for record in read_records(root, "approval_request"):
        if record.fields.get("approval_id") == approval_id or record.record_id == approval_id:
            if str(record.fields.get("tenant_id") or "") != str(context.get("tenant_id") or ""):
                raise PermissionError("Approval request is outside current tenant.")
            if str(record.fields.get("workspace_id") or "") != str(context.get("workspace_id") or ""):
                raise PermissionError("Approval request is outside current workspace.")
            if str(record.fields.get("status") or "") != "pending":
                raise ValueError("Approval request is already resolved.")
            before = dict(record.fields)
            record.fields["status"] = normalized_decision
            record.fields["resolved_at_utc"] = now_iso()
            record.fields["resolved_by_user_id"] = context.get("user_id")
            record.fields["resolution_note"] = note
            update_record(root, record)
            write_audit_log(
                root,
                context,
                f"approval.{normalized_decision}",
                "approval_request",
                approval_id,
                before_state=before,
                after_state=record.fields,
                risk_level=str(record.fields.get("risk_level") or "medium"),
            )
            return record.fields
    raise ValueError(f"Approval request not found: {approval_id}")


def add_customer_feedback(root: Path, payload: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or current_context(root, payload=payload)
    require_permission(root, "feedback.submit", context)
    feedback_id = str(payload.get("feedback_id") or stable_id("feedback", context.get("workspace_id"), payload.get("feedback_text"), now_iso()))
    fields = {
        "feedback_id": feedback_id,
        "tenant_id": context.get("tenant_id"),
        "workspace_id": context.get("workspace_id"),
        "user_id": context.get("user_id"),
        "source_scope": PRIVATE_SCOPE,
        "feedback_type": str(payload.get("feedback_type") or "general"),
        "module": str(payload.get("module") or payload.get("module_area") or ""),
        "feedback_text": str(payload.get("feedback_text") or payload.get("text") or ""),
        "asset_refs": payload.get("asset_refs") if isinstance(payload.get("asset_refs"), list) else [],
        "severity": str(payload.get("severity") or "normal"),
        "should_update_global_pattern_library": False,
        "should_update_strategy_memory": bool(payload.get("should_update_strategy_memory", False)),
        "status": "open",
        "created_at_utc": now_iso(),
    }
    append_record(root, _record("customer_feedback", feedback_id, fields))
    write_audit_log(root, context, "customer_feedback.submit", "customer_feedback", feedback_id, after_state=fields)
    return fields


def create_report_watermark(
    root: Path,
    report_name: str,
    context: dict[str, Any] | None = None,
    generated_by_agent: str = "",
) -> dict[str, Any]:
    context = context or current_context(root)
    report_id = stable_id("report", context.get("workspace_id"), report_name, now_iso())
    fields = {
        "report_id": report_id,
        "tenant_id": context.get("tenant_id"),
        "workspace_id": context.get("workspace_id"),
        "user_id": context.get("user_id"),
        "report_name": report_name,
        "generated_by_agent": generated_by_agent or "system",
        "visible_watermark": "",
        "hidden_watermark": stable_id("hidden", context.get("tenant_id"), context.get("workspace_id"), report_id),
        "export_scope": PRIVATE_SCOPE,
        "created_at_utc": now_iso(),
    }
    append_record(root, _record("report_watermark", report_id, fields))
    write_audit_log(root, context, "report.watermark", "report_watermark", report_id, after_state=fields)
    return fields


def apply_report_watermark(content: str, watermark: dict[str, Any]) -> str:
    _ = watermark
    return f"{content.rstrip()}\n"


def build_productization_status(root: Path) -> dict[str, Any]:
    context = {
        "tenant_id": DEFAULT_TENANT_ID,
        "workspace_id": DEFAULT_WORKSPACE_ID,
        "user_id": DEFAULT_USER_ID,
    }
    return {
        "ok": True,
        "version": "productization_protection_v1",
        "context": current_context(root, payload=context),
        "permissions": current_permissions(root, context),
        "license": license_status(root, context),
        "data_scopes": {
            "customer_private": "Customer store, sales, ads, reviews, creator lists, product targets and private strategy memory.",
            "global_pattern_library": "Sanitized reusable hooks, video structures, category patterns and playbooks without customer secrets.",
            "global_risk_library": "Platform rules, IP/TRO/account risk, banned terms and safer alternatives.",
        },
        "record_counts": {
            record_type: len(read_records(root, record_type))
            for record_type in [
                "tenant",
                "workspace",
                "user",
                "role",
                "permission",
                "role_permission",
                "user_role",
                "license",
                "approval_request",
                "audit_log",
                "customer_feedback",
                "report_watermark",
            ]
        },
        "api_surface": [
            "GET /api/tenant/current (authenticated)",
            "GET /api/workspaces",
            "POST /api/workspaces",
            "GET /api/permissions/current (authenticated)",
            "POST /api/approval/request",
            "POST /api/approval/{approval_id}/approve",
            "POST /api/approval/{approval_id}/reject",
            "GET /api/audit-log",
            "POST /api/customer-feedback",
            "GET /api/license/status (authenticated)",
        ],
    }


def build_productization_report(root: Path) -> Path:
    seed_productization_layer(root)
    status = build_productization_status(root)
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    path = docs_dir / "PRODUCTIZATION_SECURITY_IMPLEMENTATION_REPORT.md"
    content = f"""# Productization Security Implementation Report

Date: {datetime.now().date().isoformat()}

## Summary

Productization & Protection Layer V1 is implemented as the first customer-safe shell around AI Ecommerce Director.
It separates customer private data from global reusable patterns, adds tenant/workspace/user context, role permissions,
approval requests, audit logs, license status checks, customer feedback intake and report watermark records.

## Implemented Tables

- tenant
- workspace
- user
- role
- permission
- role_permission
- user_role
- license
- store_binding
- audit_log
- export_log
- approval_request
- customer_feedback
- agent_outcome
- training_feedback
- beta_workspace
- report_watermark
- seller_profile
- seller_mode_assessment
- seller_capability_score
- seller_strategy_package
- testing_seller_playbook
- launch_seller_playbook
- factory_seller_playbook
- brand_seller_playbook
- factory_product_line
- factory_capacity_profile
- country_market_fit
- platform_fit_score
- landed_cost_scenario
- tariff_classification_record
- tax_entity_scenario
- company_structure_option
- trade_route_scenario
- compliance_advisor_review
- manufacturing_origin_option
- brand_product_development_plan
- factory_export_plan

## Implemented APIs

{chr(10).join(f"- {item}" for item in status["api_surface"])}
- GET /api/seller-mode
- POST /api/seller-mode/diagnose
- GET /seller-mode

## Safety Rules

- Customer private knowledge stays in `customer_private`.
- Sanitized reusable knowledge goes to `global_pattern_library`.
- Risk knowledge goes to `global_risk_library`.
- External customer workspaces default to maximum L2 draft generation.
- High-risk store actions always create or require approval before execution.
- Local Connector can read authorized exports and stage actions, but cannot touch passwords, cookies, browser profiles or execute store actions directly.
- Local Connector should eventually execute only signed task manifests.
- Planner, Policy Engine, License Service, Model Router, Knowledge Lake, Watermark Service and evaluation logic stay in the control plane.
- Gray/risky tactics are risk intelligence only, not automatic execution playbooks.

## Seller Mode Strategy System

Seller Mode Strategy System is added as the commercial segmentation layer.
It diagnoses whether the customer is a Testing Seller, Launch Seller, Factory Seller,
Brand Seller, or Multi-platform Team, then generates a seller-specific strategy package.

Factory Seller gets a dedicated Factory Globalization package:

- product line diagnosis
- country-market fit
- platform fit
- landed cost scenario
- entity/tax scenario
- trade route scenario
- product development plan
- export plan
- compliance red lines and professional review requirement

## Current Seed State

```json
{_safe_json(status["record_counts"])}
```

## Acceptance Check

- Tenant / Workspace / User context: implemented.
- Permission model: implemented.
- License status without pricing: implemented.
- Approval workflow: implemented.
- Audit trail: implemented.
- Feedback intake: implemented.
- Backend report audit trace: implemented; no visible signature is embedded in customer-facing reports.
- API-level checks: implemented in new API handlers.
- Customer private vs global pattern separation: documented and encoded in fields.
- Seller mode diagnosis: implemented.
- Factory globalization package: implemented.
"""
    path.write_text(content, encoding="utf-8")
    return path


def _safe_json(payload: Any) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2)
