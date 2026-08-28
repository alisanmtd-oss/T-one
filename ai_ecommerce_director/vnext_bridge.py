from __future__ import annotations

from pathlib import Path
from typing import Any

from .ai_provider_catalog import provider_catalog_snapshot
from .company_workspace import realtime_dashboard_api_snapshot
from .organization_operating import organization_operating_snapshot
from .workspace_runtime import load_workspace_config


def vnext_bootstrap_snapshot(root: Path) -> dict[str, Any]:
    """Return the read-only T-one contract consumed by a migrated desktop shell."""

    workspace = load_workspace_config(root)
    dashboard = realtime_dashboard_api_snapshot(root)
    organization = organization_operating_snapshot(root, workspace)
    providers = provider_catalog_snapshot(root)
    return {
        "schema_version": 1,
        "contract": "t-one-desktop-vnext-bootstrap",
        "brand": {"name": "T-one", "mark": "T1"},
        "product_direction": "group_operating_brain_for_cross_border_commerce_and_foreign_trade",
        "default_surface": "dashboard",
        "daily_interaction": {
            "mode": "chat_first",
            "flow": [
                "multimodal_input",
                "business_object_normalization",
                "model_agent_skill_routing",
                "owner_approval_when_required",
                "scoped_execution",
                "evidence_receipt",
            ],
            "technical_configuration_surface": "settings_only",
        },
        "dashboard": dashboard,
        "organization": organization,
        "models": {
            "ready_count": int(providers.get("ready_count") or 0),
            "providers": [
                {
                    "name": str(item.get("name") or ""),
                    "model": str(item.get("model") or ""),
                    "ready": bool(item.get("ready")),
                    "status": str(item.get("status") or ""),
                }
                for item in providers.get("providers", [])
                if isinstance(item, dict)
            ],
        },
        "execution_boundaries": {
            "amazon_paused": True,
            "real_outreach_requires_owner_authorization": True,
            "oauth_requires_owner_authorization": True,
            "advertising_changes_require_owner_approval": True,
            "store_identity_isolated_by_platform_site_store_and_execution_identity": True,
        },
        "external_action_performed": False,
    }
