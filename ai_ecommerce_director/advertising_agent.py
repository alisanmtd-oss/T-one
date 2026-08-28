from __future__ import annotations

import copy
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


CONFIG_PATH = Path("config") / "advertising_agent.json"
RUNTIME_PATH = Path("data") / "advertising_runtime.json"
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,159}$")
_RUNTIME_LOCK = threading.RLock()
SECRET_KEYS = {
    "api_key",
    "apikey",
    "password",
    "client_secret",
    "clientsecret",
    "access_token",
    "accesstoken",
    "refresh_token",
    "refreshtoken",
    "developer_token",
    "developertoken",
    "cookie",
    "session",
    "session_cookie",
    "sessioncookie",
}
RAW_PII_KEYS = {
    "email",
    "email_address",
    "phone",
    "phone_number",
    "phonenumber",
    "client_ip_address",
    "clientipaddress",
    "ip_address",
    "ipaddress",
    "x_forwarded_for",
    "xforwardedfor",
    "x_real_ip",
    "xrealip",
    "user_agent",
    "useragent",
}
RAW_PLATFORM_ACCOUNT_ID_KEYS = {
    "ad_account_id",
    "advertiser_id",
    "google_ads_customer_id",
    "manager_account_id",
    "meta_ad_account_id",
    "tiktok_advertiser_id",
    "amazon_advertiser_id",
    "model_supplied_ad_account_id",
}
TIKTOK_GMV_MAX_SURFACES = {"product_gmv_max", "live_gmv_max"}
ACTION_GATE_REQUIREMENTS = {
    "connect_account": set(),
    "pause_campaign": {"authorization"},
    "primary_ad_account_change": {"authorization"},
}
CONNECTION_STATES = {"blocked_connector", "verified_live"}
PREFLIGHT_RECORD_FIELDS = {
    "tenant_id",
    "project_id",
    "store_binding_id",
    "platform",
    "country_site",
    "commerce_mode",
    "ownership",
    "ad_account_binding_id",
    "tto_account_binding_id",
    "execution_identity_id",
    "surface",
    "action",
    "authorization_state",
    "measurement_state",
    "economics_state",
    "owner_approval_state",
    "primary_ad_account",
    "business_verified",
    "rights_verified",
}
ADVERTISING_METRIC_FIELDS = {
    "impressions",
    "clicks",
    "conversions",
    "orders",
    "spend",
    "revenue",
    "blocked_gate_count",
}


def build_tiktok_gmv_max_material_guard() -> dict[str, Any]:
    """Return the internal execution contract distilled from the reviewed materials.

    The public vendor page, the user's historical deck and the private dashboard
    recording are evidence inputs only. None of them can grant account authority,
    approve a budget or replace a current shop-scoped platform receipt.
    """

    return {
        "policy_version": "2026-07-19",
        "external_execution_default_allowed": False,
        "source_classifications": {
            "loopgrowth.tkgmvmax.com": "blocked_connector_vendor_claim_only",
            "user_gmv_max_ppt": "historical_operator_hypotheses_only",
            "requested_user_gmv_video": "missing_source_not_reviewed",
            "private_douyin_gmv.mp4": "private_shop_dashboard_trace_not_gmv_max_proof",
        },
        "threshold_policy": {
            "mode": "no_global_fixed_thresholds",
            "requirements": [
                "shop_and_ad_account_scope",
                "country_site_and_currency",
                "measurement_window_and_attribution_definition",
                "current_product_margin_and_refund_assumptions",
                "dated_experiment_and_owner_approval",
            ],
        },
        "budget_gates": [
            "verified_store_scoped_connector",
            "authorization_ready",
            "measurement_ready",
            "economics_ready",
            "current_primary_ad_account",
            "item_level_owner_approval",
        ],
        "writeback_requirements": [
            "before_snapshot",
            "proposed_change",
            "approved_change",
            "platform_receipt",
            "after_snapshot",
            "currency_and_measurement_window",
            "route_key",
            "actor_and_approval_id",
        ],
        "stop_conditions": [
            "execution_identity_not_authorized_for_current_shop",
            "approval_missing_expired_or_scope_mismatch",
            "platform_receipt_missing_or_write_result_ambiguous",
            "measurement_missing_stale_or_attribution_ambiguous",
            "economics_or_stop_loss_boundary_breached",
            "primary_ad_account_or_vsa_psa_live_campaign_conflict",
        ],
        "recovery_rule": (
            "Stop the isolated task, preserve receipts and require human review; "
            "ending or switching GMV Max does not prove displaced VSA, PSA or LIVE "
            "Shopping Ads were automatically restarted."
        ),
    }


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and item.strip()]


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _secret_paths(value: Any, path: str = "task") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalised = _normalise(key)
            child_path = f"{path}.{key}"
            if normalised in SECRET_KEYS:
                paths.append(child_path)
            paths.extend(_secret_paths(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_secret_paths(item, f"{path}[{index}]"))
    return paths


def _raw_pii_paths(value: Any, path: str = "task") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalised = _normalise(key)
            child_path = f"{path}.{key}"
            if normalised in RAW_PII_KEYS:
                paths.append(child_path)
            paths.extend(_raw_pii_paths(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_raw_pii_paths(item, f"{path}[{index}]"))
    return paths


def _raw_platform_account_id_paths(value: Any, path: str = "task") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalised = _normalise(key)
            child_path = f"{path}.{key}"
            if normalised in RAW_PLATFORM_ACCOUNT_ID_KEYS:
                paths.append(child_path)
            paths.extend(_raw_platform_account_id_paths(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_raw_platform_account_id_paths(item, f"{path}[{index}]"))
    return paths


def evaluate_measurement_integrity(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Describe whether an observation can support a causal experiment claim."""

    data = payload if isinstance(payload, Mapping) else {}
    required = (
        "experiment_id",
        "design",
        "comparison_group",
        "randomization_unit",
        "window_start",
        "window_end",
        "attribution_source",
        "sample_size",
    )
    missing = [field for field in required if not str(data.get(field) or "").strip()]
    failures: list[str] = []
    if missing:
        failures.append("incomplete_experiment_contract")
    if _normalise(data.get("comparison_group")) in {"", "none", "missing", "same_as_treatment"}:
        failures.append("missing_or_invalid_comparison_group")
    if _normalise(data.get("audience_overlap_state")) in {"overlap", "unknown"}:
        failures.append("audience_overlap_not_cleared")
    if _normalise(data.get("early_stop_state")) in {"stopped_early", "unknown"}:
        failures.append("early_stop_or_peeking_risk")
    if _normalise(data.get("attribution_consistency_state")) not in {"consistent", "verified"}:
        failures.append("attribution_definition_not_verified")
    try:
        sample_size = int(data.get("sample_size") or 0)
    except (TypeError, ValueError):
        sample_size = 0
    if sample_size <= 0:
        failures.append("sample_size_not_verified")
    passed = not failures
    return {
        "state": "eligible_for_authorized_analysis" if passed else "measurement_failure_or_incomplete",
        "missing_fields": missing,
        "failure_reasons": sorted(set(failures)),
        "causal_conclusion": "not_computed",
        "platform_attribution_is_not_incremental_lift": True,
    }


def _creative_provenance(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    data = payload if isinstance(payload, Mapping) else {}
    if not data:
        return {
            "state": "not_provided",
            "causal_conclusion": "inconclusive",
            "result_is_not_proof_of_creative_causality": True,
        }
    required = (
        "generator_or_editor",
        "generated_at",
        "source_asset_refs",
        "output_asset_sha256",
        "rights_evidence_refs",
        "human_edit_summary",
        "platform_label_state",
    )
    missing = [field for field in required if not data.get(field)]
    if missing:
        raise ValueError("创意来源不完整：" + ", ".join(missing))
    asset_hashes = data.get("output_asset_sha256")
    if not isinstance(asset_hashes, list) or not asset_hashes or any(
        not re.fullmatch(r"[A-Fa-f0-9]{64}", str(item or "")) for item in asset_hashes
    ):
        raise ValueError("创意输出必须提供逐资产 SHA256。")
    return {
        "state": "provenance_recorded",
        "generator_or_editor": str(data["generator_or_editor"])[:200],
        "generated_at": str(data["generated_at"])[:80],
        "source_asset_refs": [str(item)[:500] for item in data["source_asset_refs"]],
        "output_asset_sha256": [str(item).upper() for item in asset_hashes],
        "rights_evidence_refs": [str(item)[:500] for item in data["rights_evidence_refs"]],
        "human_edit_summary": str(data["human_edit_summary"])[:1000],
        "platform_label_state": str(data["platform_label_state"])[:120],
        "causal_conclusion": "inconclusive",
        "result_is_not_proof_of_creative_causality": True,
    }


def validate_advertising_agent_config(config: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(config, Mapping):
        return ["config: expected an object"]
    if config.get("schema_version") != 1:
        errors.append("config.schema_version: expected 1")
    if config.get("automation_ceiling") != "L3":
        errors.append("config.automation_ceiling: expected L3")

    required_dimensions = set(_strings(config.get("required_route_dimensions")))
    expected_dimensions = {
        "tenant_id",
        "project_id",
        "store_binding_id",
        "platform",
        "country_site",
        "commerce_mode",
        "ownership",
        "ad_account_binding_id",
        "execution_identity_id",
    }
    if required_dimensions != expected_dimensions:
        errors.append("config.required_route_dimensions: incomplete isolated advertising route")

    channels = config.get("channels")
    if not isinstance(channels, list) or not channels:
        errors.append("config.channels: expected a non-empty list")
    else:
        ids: list[str] = []
        for index, channel in enumerate(channels):
            path = f"config.channels[{index}]"
            if not isinstance(channel, Mapping):
                errors.append(f"{path}: expected an object")
                continue
            channel_id = _normalise(channel.get("id"))
            ids.append(channel_id)
            if not SAFE_ID.fullmatch(channel_id):
                errors.append(f"{path}.id: invalid channel id")
            for key in ("surfaces", "measurement", "authorization", "official_sources"):
                if not _strings(channel.get(key)):
                    errors.append(f"{path}.{key}: expected at least one value")
            connection = channel.get("connection")
            if not isinstance(connection, Mapping):
                errors.append(f"{path}.connection: expected an object")
            else:
                connection_state = _normalise(connection.get("state"))
                if connection_state not in CONNECTION_STATES:
                    errors.append(f"{path}.connection.state: unsupported state")
                bindings = connection.get("verified_bindings")
                if not isinstance(bindings, list):
                    errors.append(f"{path}.connection.verified_bindings: expected a list")
                elif connection_state == "verified_live" and not bindings:
                    errors.append(
                        f"{path}.connection.verified_bindings: verified_live requires evidence"
                    )
                elif connection_state == "verified_live":
                    required_binding_fields = {
                        "tenant_id",
                        "project_id",
                        "store_binding_id",
                        "platform",
                        "country_site",
                        "commerce_mode",
                        "ownership",
                        "execution_identity_id",
                        "verified_at",
                        "evidence_ref",
                        "binding_source",
                    }
                    binding_id_field = "tto_account_binding_id" if channel_id == "tiktok_one" else "ad_account_binding_id"
                    required_binding_fields.add(binding_id_field)
                    for binding_index, binding in enumerate(bindings):
                        if not isinstance(binding, Mapping):
                            errors.append(f"{path}.connection.verified_bindings[{binding_index}]: expected an object")
                            continue
                        missing_fields = sorted(
                            field for field in required_binding_fields if not str(binding.get(field) or "").strip()
                        )
                        if missing_fields:
                            errors.append(
                                f"{path}.connection.verified_bindings[{binding_index}]: missing {','.join(missing_fields)}"
                            )
                        if _normalise(binding.get("binding_source")) != "authorized_connector_read":
                            errors.append(
                                f"{path}.connection.verified_bindings[{binding_index}].binding_source: expected authorized_connector_read"
                            )
        if len(ids) != len(set(ids)):
            errors.append("config.channels: duplicate channel ids")
        for required in {"meta_ads", "tiktok_ads", "tiktok_one", "google_ads", "amazon_ads"}:
            if required not in ids:
                errors.append(f"config.channels: missing {required}")

    actions = config.get("actions")
    if not isinstance(actions, Mapping):
        errors.append("config.actions: expected an object")
    else:
        for key in (
            "read_only_or_draft",
            "connection_required",
            "confirmation_required",
            "always_blocked",
        ):
            if not _strings(actions.get(key)):
                errors.append(f"config.actions.{key}: expected at least one action")

    if _secret_paths(config, "config"):
        # The config names forbidden keys as policy values, but must never carry them as fields.
        errors.append("config: secret-bearing fields are forbidden")
    return errors


def load_advertising_agent_config(root: Path) -> dict[str, Any]:
    payload = json.loads((root / CONFIG_PATH).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Advertising agent config must be a JSON object")
    errors = validate_advertising_agent_config(payload)
    if errors:
        raise ValueError("Invalid advertising agent config: " + "; ".join(errors))
    return copy.deepcopy(payload)


def _has_verified_connection(
    task: Mapping[str, Any], channel_id: str, channel: Mapping[str, Any]
) -> bool:
    """Resolve connection truth from the authority config, never from task claims."""

    connection = channel.get("connection")
    if not isinstance(connection, Mapping):
        return False
    if _normalise(connection.get("state")) != "verified_live":
        return False
    binding_field = (
        "tto_account_binding_id" if channel_id == "tiktok_one" else "ad_account_binding_id"
    )
    required_values = {
        "tenant_id": _normalise(task.get("tenant_id")),
        "project_id": _normalise(task.get("project_id")),
        "store_binding_id": _normalise(task.get("store_binding_id")),
        "platform": channel_id,
        "country_site": _normalise(task.get("country_site")),
        "commerce_mode": _normalise(task.get("commerce_mode")),
        "ownership": _normalise(task.get("ownership")),
        "execution_identity_id": _normalise(task.get("execution_identity_id")),
        binding_field: _normalise(task.get(binding_field)),
    }
    for binding in connection.get("verified_bindings", []):
        if not isinstance(binding, Mapping):
            continue
        if all(_normalise(binding.get(key)) == value for key, value in required_values.items()):
            if (
                _normalise(binding.get("binding_source")) == "authorized_connector_read"
                and str(binding.get("evidence_ref") or "").strip()
                and str(binding.get("verified_at") or "").strip()
            ):
                return True
    return False


def evaluate_advertising_task(
    task: Mapping[str, Any], config: Mapping[str, Any]
) -> dict[str, Any]:
    """Evaluate one account-scoped advertising task before any external action.

    The evaluator never performs a platform write. It returns the safe next stage,
    missing gates and whether an already approved task may enter an isolated L3 queue.
    """

    result: dict[str, Any] = {
        "agent_id": str(config.get("agent_id") or "agent-cross-channel-media-buyer"),
        "status": "blocked_invalid_task",
        "external_execution_allowed": False,
        "missing": [],
        "route_key": "",
        "next_stage": "preflight",
    }
    if not isinstance(task, Mapping):
        result["missing"] = ["task"]
        return result

    secret_paths = _secret_paths(task)
    if secret_paths:
        result.update(
            {
                "status": "blocked_raw_credentials",
                "missing": secret_paths,
                "next_stage": "remove_secrets_and_use_credential_ref",
            }
        )
        return result

    raw_pii_paths = _raw_pii_paths(task)
    if raw_pii_paths:
        result.update(
            {
                "status": "blocked_raw_pii",
                "missing": raw_pii_paths,
                "next_stage": "remove_personal_data_and_use_tenant_scoped_connector",
            }
        )
        return result

    raw_platform_account_ids = _raw_platform_account_id_paths(task)
    if raw_platform_account_ids:
        result.update(
            {
                "status": "blocked_raw_platform_account_id",
                "missing": raw_platform_account_ids,
                "next_stage": "resolve_internal_binding_from_authorized_connector",
                "binding_authority": "config_verified_bindings_only",
            }
        )
        return result

    channel_id = _normalise(task.get("platform"))
    surface = _normalise(task.get("surface"))
    action = _normalise(task.get("action"))
    channels = {
        _normalise(item.get("id")): item
        for item in config.get("channels", [])
        if isinstance(item, Mapping)
    }
    channel = channels.get(channel_id)
    if channel is None:
        result["missing"] = ["supported_platform"]
        return result
    if surface not in {_normalise(item) for item in _strings(channel.get("surfaces"))}:
        result["missing"] = ["supported_surface"]
        return result
    paused_platforms = {_normalise(item) for item in _strings(config.get("owner_paused_platforms"))}
    if channel_id in paused_platforms:
        result.update(
            {
                "status": "paused_by_owner",
                "missing": [f"{channel_id}_explicit_owner_resume"],
                "next_stage": "wait_for_owner_resume",
                "binding_authority": "config_verified_bindings_only",
            }
        )
        return result
    if channel_id == "tiktok_ads" and surface in TIKTOK_GMV_MAX_SURFACES:
        result["gmv_max_material_guard"] = build_tiktok_gmv_max_material_guard()

    required = list(_strings(config.get("required_route_dimensions")))
    if channel_id == "tiktok_one":
        required.remove("ad_account_binding_id")
        required.append("tto_account_binding_id")
    missing = [field for field in required if not str(task.get(field) or "").strip()]
    if missing:
        result.update({"status": "blocked_missing_route", "missing": missing})
        return result

    route_values = [
        task.get("tenant_id"),
        task.get("project_id"),
        task.get("store_binding_id"),
        channel_id,
        str(task.get("country_site") or "").upper(),
        task.get("commerce_mode"),
        task.get("ownership"),
        task.get("ad_account_binding_id") or task.get("tto_account_binding_id"),
        task.get("execution_identity_id"),
    ]
    if any(not SAFE_ID.fullmatch(_normalise(item)) for item in route_values):
        result["missing"] = ["safe_route_ids"]
        return result
    result["route_key"] = ":".join(_normalise(item) for item in route_values)

    actions = config.get("actions") if isinstance(config.get("actions"), Mapping) else {}
    always_blocked = {_normalise(item) for item in _strings(actions.get("always_blocked"))}
    read_only = {_normalise(item) for item in _strings(actions.get("read_only_or_draft"))}
    connection_required = {
        _normalise(item) for item in _strings(actions.get("connection_required"))
    }
    confirmation_required = {
        _normalise(item) for item in _strings(actions.get("confirmation_required"))
    }
    if action in always_blocked:
        result.update({"status": "blocked_policy", "next_stage": "human_policy_review"})
        return result
    if action not in read_only | confirmation_required:
        result["missing"] = ["supported_action"]
        return result

    if action == "connect_account":
        result.update(
            {
                "status": "blocked_connector",
                "missing": [f"{channel_id}_owner_authorized_connection"],
                "next_stage": "owner_connector_setup",
            }
        )
        return result

    if action in connection_required | confirmation_required and not _has_verified_connection(
        task, channel_id, channel
    ):
        result.update(
            {
                "status": "blocked_connector",
                "missing": [f"{channel_id}_verified_binding"],
                "next_stage": "verify_store_scoped_connector",
            }
        )
        return result

    result["advertiser_binding_verified"] = _has_verified_connection(task, channel_id, channel)
    result["binding_authority"] = "config_verified_bindings_only"

    if action in read_only:
        result.update({"status": "safe_to_analyze_or_draft", "next_stage": "draft_or_monitor"})
        return result

    gate_fields = {
        "authorization": "authorization_state",
        "measurement": "measurement_state",
        "economics": "economics_state",
    }
    required_gates = ACTION_GATE_REQUIREMENTS.get(action, set(gate_fields))
    missing_gates = [
        gate
        for gate, field in gate_fields.items()
        if gate in required_gates
        if _normalise(task.get(field)) != "ready"
    ]
    if channel_id == "tiktok_ads" and surface in TIKTOK_GMV_MAX_SURFACES:
        if task.get("primary_ad_account") is not True:
            missing_gates.append("primary_ad_account")
    if channel_id == "tiktok_one":
        if task.get("business_verified") is not True:
            missing_gates.append("business_verification")
        if action in {"tto_creator_invite", "tto_payment", "tto_authorized_content_sync"} and task.get("rights_verified") is not True:
            missing_gates.append("content_rights")
    if missing_gates:
        result.update(
            {
                "status": "blocked_preflight",
                "missing": sorted(set(missing_gates)),
                "next_stage": "complete_preflight",
            }
        )
        return result

    if _normalise(task.get("owner_approval_state")) != "approved":
        result.update({"status": "needs_owner_approval", "next_stage": "owner_review"})
        return result

    result.update(
        {
            "status": "approved_for_isolated_execution",
            "external_execution_allowed": True,
            "next_stage": "isolated_execution_queue",
        }
    )
    return result


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_advertising_runtime(root: Path) -> dict[str, Any]:
    path = root / RUNTIME_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return {
        "schema_version": 1,
        "preflights": [
            dict(item)
            for item in payload.get("preflights", [])
            if isinstance(item, dict)
        ][-200:],
        "feedback": [
            dict(item)
            for item in payload.get("feedback", [])
            if isinstance(item, dict)
        ][-200:],
        "updated_at": str(payload.get("updated_at") or ""),
    }


def _write_advertising_runtime(root: Path, payload: Mapping[str, Any]) -> None:
    path = root / RUNTIME_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {
        "schema_version": 1,
        "preflights": list(payload.get("preflights") or [])[-200:],
        "feedback": list(payload.get("feedback") or [])[-200:],
        "updated_at": _now_iso(),
    }
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _safe_preflight_task(task: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in task.items()
        if key in PREFLIGHT_RECORD_FIELDS
        and isinstance(value, (str, int, float, bool, type(None)))
    }


def advertising_control_snapshot(root: Path) -> dict[str, Any]:
    config = load_advertising_agent_config(root)
    runtime = _load_advertising_runtime(root)
    channels: list[dict[str, Any]] = []
    for item in config.get("channels", []):
        if not isinstance(item, Mapping):
            continue
        connection = item.get("connection") if isinstance(item.get("connection"), Mapping) else {}
        channels.append(
            {
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or item.get("id") or ""),
                "surfaces": _strings(item.get("surfaces")),
                "connection_state": str(connection.get("state") or "blocked_connector"),
                "verified_binding_count": len(
                    [
                        binding
                        for binding in connection.get("verified_bindings", [])
                        if isinstance(binding, Mapping)
                    ]
                ),
                "external_execution_available": False,
            }
        )
    return {
        "schema_version": 1,
        "agent_id": str(config.get("agent_id") or "agent-cross-channel-media-buyer"),
        "automation_ceiling": str(config.get("automation_ceiling") or "L3"),
        "required_route_dimensions": _strings(config.get("required_route_dimensions")),
        "workflow": _strings(config.get("workflow")),
        "channels": channels,
        "preflights": list(reversed(runtime["preflights"][-20:])),
        "feedback": list(reversed(runtime["feedback"][-20:])),
        "external_action_performed": False,
        "installation_or_preflight_grants_authorization": False,
        "updated_at": runtime.get("updated_at") or "",
    }


def advertising_operator_brief(
    root: Path,
    *,
    project_id: str = "",
    requested_goal: str = "",
) -> dict[str, Any]:
    """Return the chat-facing advertising workflow without technical ID forms."""

    snapshot = advertising_control_snapshot(root)
    channels = [item for item in snapshot.get("channels", []) if isinstance(item, Mapping)]
    connected = sum(int(item.get("verified_binding_count") or 0) for item in channels)
    ready = connected > 0
    clean_goal = " ".join(str(requested_goal or "").split()).strip()
    stages = [
        {
            "id": "goal",
            "label": "目标",
            "status": "ready" if clean_goal else "needs_input",
            "message": clean_goal or "先说想解决的问题，例如减少浪费、测试素材或检查转化。",
        },
        {
            "id": "account_read",
            "label": "账号与真实数据",
            "status": "ready" if ready else "needs_authorized_read",
            "message": (
                f"已验证 {connected} 个逐账号只读连接。"
                if ready
                else "当前没有逐账号只读连接；不会展示假花费、假转化或假 ROAS。"
            ),
        },
        {
            "id": "measurement",
            "label": "测量与归因",
            "status": "ready_for_check" if ready else "blocked_by_account_read",
            "message": "核对像素/事件、归因窗口、币种和数据新鲜度，不把平台归因当增量效果。",
        },
        {
            "id": "diagnosis",
            "label": "诊断与建议",
            "status": "ready_for_readonly_analysis" if ready else "waiting_for_real_data",
            "message": "按商品、素材、受众和活动拆解变化，输出原因、证据、影响与建议。",
        },
        {
            "id": "approval",
            "label": "负责人确认",
            "status": "always_required_for_change",
            "message": "预算、启停、出价、发布、受众或归因设置变更必须逐项确认。",
        },
        {
            "id": "receipt",
            "label": "执行与回执",
            "status": "not_executed",
            "message": "只有平台返回真实回执后才记为执行；当前外部动作 0。",
        },
    ]
    return {
        "schema_version": 1,
        "agent_id": str(snapshot.get("agent_id") or "agent-cross-channel-media-buyer"),
        "project_id": " ".join(str(project_id or "").split()).strip(),
        "status": "ready_for_readonly_diagnosis" if ready else "needs_readonly_account",
        "verified_account_count": connected,
        "real_metrics_available": ready,
        "metrics": {} if not ready else {"state": "read_from_authorized_connector_only"},
        "stages": stages,
        "chat_prompts": [
            "检查当前广告最近发生了什么",
            "找出浪费预算的商品、素材或受众",
            "根据商品资料准备一个不发布的广告测试草稿",
        ],
        "technical_configuration_surface": "settings_only",
        "external_action_performed": False,
    }


def run_advertising_preflight(
    root: Path, payload: Mapping[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    task = payload.get("task") if isinstance(payload.get("task"), Mapping) else payload
    config = load_advertising_agent_config(root)
    result = evaluate_advertising_task(task, config)
    created_at = _now_iso()
    record = {
        "id": f"ads-preflight-{uuid.uuid4().hex[:16]}",
        "created_at": created_at,
        "created_by": str(actor or "owner")[:80],
        "task": _safe_preflight_task(task),
        "result": copy.deepcopy(result),
        "external_action_performed": False,
        "authorization_granted": False,
    }
    with _RUNTIME_LOCK:
        runtime = _load_advertising_runtime(root)
        runtime["preflights"].append(record)
        _write_advertising_runtime(root, runtime)
    return {"ok": True, "preflight": record}


def record_advertising_feedback(
    root: Path, payload: Mapping[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    preflight_id = str(payload.get("preflight_id") or "").strip().lower()
    if not SAFE_ID.fullmatch(preflight_id):
        raise ValueError("请选择有效的广告预检记录。")
    evidence_source = _normalise(payload.get("evidence_source"))
    if evidence_source not in {
        "formal_app_manual",
        "authorized_export",
        "api_read",
        "platform_receipt",
    }:
        raise ValueError("证据来源无效。")
    evidence_ref = " ".join(str(payload.get("evidence_ref") or "").split()).strip()
    if len(evidence_ref) < 6:
        raise ValueError("必须提供可追溯的证据引用。")
    metrics_source = payload.get("metrics") if isinstance(payload.get("metrics"), Mapping) else {}
    metrics: dict[str, float] = {}
    for key, value in metrics_source.items():
        if key not in ADVERTISING_METRIC_FIELDS or isinstance(value, bool):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric < 0:
            raise ValueError("广告指标不能为负数。")
        metrics[key] = numeric
    if not metrics:
        raise ValueError("至少提供一个证据指标。")
    window_start = str(payload.get("window_start") or "").strip()
    window_end = str(payload.get("window_end") or "").strip()
    if not window_start or not window_end:
        raise ValueError("必须提供证据统计窗口。")
    measurement_integrity = evaluate_measurement_integrity(
        payload.get("experiment_design") if isinstance(payload.get("experiment_design"), Mapping) else None
    )
    creative_provenance = _creative_provenance(
        payload.get("creative_provenance") if isinstance(payload.get("creative_provenance"), Mapping) else None
    )
    with _RUNTIME_LOCK:
        runtime = _load_advertising_runtime(root)
        preflight = next(
            (
                item
                for item in runtime["preflights"]
                if str(item.get("id") or "") == preflight_id
            ),
            None,
        )
        if preflight is None:
            raise ValueError("广告预检记录不存在。")
        external_execution_observed = bool(
            preflight.get("result", {}).get("external_execution_allowed")
            and evidence_source == "platform_receipt"
        )
        record = {
            "id": f"ads-feedback-{uuid.uuid4().hex[:16]}",
            "preflight_id": preflight_id,
            "created_at": _now_iso(),
            "created_by": str(actor or "owner")[:80],
            "evidence_source": evidence_source,
            "evidence_ref": evidence_ref[:500],
            "window_start": window_start[:80],
            "window_end": window_end[:80],
            "metrics": metrics,
            "measurement_integrity": measurement_integrity,
            "creative_provenance": creative_provenance,
            "external_execution_observed": external_execution_observed,
            "causal_conclusion": "inconclusive",
            "evidence_state": (
                "platform_receipt_observation"
                if external_execution_observed
                else "local_preflight_observation_only"
            ),
        }
        runtime["feedback"].append(record)
        _write_advertising_runtime(root, runtime)
    return {"ok": True, "feedback": record}
