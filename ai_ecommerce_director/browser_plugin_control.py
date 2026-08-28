from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .browser_environments import _candidate_paths, _first_existing
from .plugin_package import verify_extension_package


CONFIG_RELATIVE_PATH = Path("config") / "browser_plugin_control.json"
STATE_RELATIVE_PATH = Path("data") / "browser_plugin_control_runtime.json"
MAX_AUDITS = 200
MAX_REVIEWS = 200
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
REGION_GROUPS = {"sea", "southeast asia", "latin america", "latam", "eu", "europe"}
SECRET_KEYS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "api_key",
    "password",
    "cookie",
    "session_cookie",
    "authorization",
    "install_token",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(default)
    return payload if isinstance(payload, dict) else dict(default)


def _config(root: Path) -> dict[str, Any]:
    payload = _read_json(root / CONFIG_RELATIVE_PATH, {})
    if not isinstance(payload.get("providers"), list):
        raise ValueError("Browser/plugin control config is missing providers.")
    return payload


def _state(root: Path) -> dict[str, Any]:
    payload = _read_json(
        root / STATE_RELATIVE_PATH,
        {"schema_version": 1, "audits": [], "reviews": []},
    )
    for key in ("audits", "reviews"):
        if not isinstance(payload.get(key), list):
            payload[key] = []
    payload["schema_version"] = 1
    return payload


def _save_state(root: Path, state: dict[str, Any]) -> None:
    path = root / STATE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    state["audits"] = list(state.get("audits") or [])[-MAX_AUDITS:]
    state["reviews"] = list(state.get("reviews") or [])[-MAX_REVIEWS:]
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _find_secret_field(value: Any, path: str = "request") -> str | None:
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


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _source_digest(source: Path) -> tuple[str, int, float]:
    digest = hashlib.sha256()
    count = 0
    latest_mtime = 0.0
    if not source.is_dir():
        return "", 0, 0.0
    for path in sorted(item for item in source.rglob("*") if item.is_file()):
        relative = path.relative_to(source).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
        count += 1
        latest_mtime = max(latest_mtime, path.stat().st_mtime)
    return digest.hexdigest().upper(), count, latest_mtime


def _provider_snapshot(root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    del root
    candidates = _candidate_paths()
    providers: list[dict[str, Any]] = []
    for item in config.get("providers") or []:
        if not isinstance(item, dict):
            continue
        provider_id = str(item.get("id") or "")
        executable = _first_existing(candidates.get(provider_id, []))
        providers.append(
            {
                "id": provider_id,
                "name": str(item.get("name") or provider_id),
                "adapter": str(item.get("adapter") or "unknown"),
                "installed": executable is not None,
                "status": "installed_unbound" if executable else "not_installed",
                "automatic_profile_open": False,
                "profile_inventory_read": False,
                "verified_profile_count": 0,
                "verified_store_binding_count": 0,
                "executable_path_exposed": False,
            }
        )
    return providers


def _plugin_snapshot(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    plugin = config.get("plugin") if isinstance(config.get("plugin"), dict) else {}
    source = root / str(plugin.get("source_path") or "")
    package = root / str(plugin.get("package_path") or "")
    token = root / str(plugin.get("local_auth_token_path") or "")
    manifest = _read_json(source / "manifest.json", {}) if source.is_dir() else {}
    source_hash, source_file_count, latest_source_mtime = _source_digest(source)
    package_exists = package.is_file()
    package_verification = verify_extension_package(source, package)
    package_current = bool(
        package_verification.get("verified")
        and package_verification.get("source_sha256") == source_hash
    )
    permissions = [str(item) for item in manifest.get("permissions") or []]
    host_permissions = [str(item) for item in manifest.get("host_permissions") or []]
    expected_hosts = {str(item) for item in plugin.get("allowed_host_permissions") or []}
    disallowed_hosts = sorted(set(host_permissions) - expected_hosts)
    prohibited_permissions = sorted(
        set(permissions).intersection({"cookies", "webRequest", "webRequestBlocking", "nativeMessaging", "history", "downloads"})
    )
    return {
        "source_exists": source.is_dir(),
        "source_file_count": source_file_count,
        "source_sha256": source_hash,
        "manifest_version": int(manifest.get("manifest_version") or 0),
        "extension_version": str(manifest.get("version") or ""),
        "permissions": permissions,
        "host_permissions": host_permissions,
        "disallowed_host_permissions": disallowed_hosts,
        "prohibited_permissions": prohibited_permissions,
        "package_exists": package_exists,
        "package_sha256": _file_hash(package) if package_exists else "",
        "package_current_with_source": package_current,
        "package_verification": package_verification,
        "package_current_reason": (
            "content_hash_and_manifest_match"
            if package_current
            else "missing_or_content_manifest_mismatch"
        ),
        "local_auth_token_configured": token.is_file() and token.stat().st_size >= 32,
        "local_auth_token_value_exposed": False,
        "verified_non_amazon_extension_install_count": 0,
        "verified_non_amazon_store_binding_count": 0,
        "verified_non_amazon_capture_count": 0,
        "cloud_task_execution_count": 0,
        "platform_write_count": 0,
    }


def browser_plugin_control_snapshot(root: Path) -> dict[str, Any]:
    config = _config(root)
    state = _state(root)
    providers = _provider_snapshot(root, config)
    plugin = _plugin_snapshot(root, config)
    return {
        "schema_version": 1,
        "scope": config.get("scope"),
        "providers": providers,
        "plugin": plugin,
        "required_binding_route": config.get("required_binding_route") or [],
        "local_actions": config.get("local_actions") or [],
        "blocked_actions": config.get("blocked_actions") or [],
        "hard_boundaries": config.get("hard_boundaries") or [],
        "installed_provider_count": sum(1 for item in providers if item["installed"]),
        "verified_store_binding_count": 0,
        "verified_extension_install_count": 0,
        "external_action_count": 0,
        "audits": list(state.get("audits") or [])[-20:][::-1],
        "reviews": list(state.get("reviews") or [])[-20:][::-1],
    }


def _clean_identifier(value: Any, label: str, *, required: bool = False) -> str:
    text = str(value or "").strip()
    if not text and not required:
        return ""
    if not IDENTIFIER.fullmatch(text):
        raise ValueError(f"{label} must be a stable identifier.")
    return text


def evaluate_browser_plugin_request(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ValueError("Browser/plugin request must be an object.")
    secret = _find_secret_field(request)
    if secret:
        return {
            "status": "blocked_raw_credentials",
            "error": "Raw credential fields are not accepted.",
            "missing": [],
            "local_action_allowed": False,
            "browser_launched": False,
            "extension_installed": False,
            "store_bound": False,
            "page_captured": False,
            "cloud_task_executed": False,
            "external_action_count": 0,
        }
    snapshot = browser_plugin_control_snapshot(root)
    action = str(request.get("action") or "inspect_provider").strip().casefold()
    provider_id = str(request.get("provider") or "").strip().casefold()
    platform = str(request.get("platform") or "").strip().casefold()
    if platform == "amazon" or provider_id == "bitbrowser":
        return {
            "status": "blocked_scope_excluded",
            "error": "Amazon and the currently verified BitBrowser route are excluded by the owner's current instruction.",
            "missing": ["non_amazon_route"],
            "local_action_allowed": False,
            "browser_launched": False,
            "extension_installed": False,
            "store_bound": False,
            "page_captured": False,
            "cloud_task_executed": False,
            "external_action_count": 0,
        }
    if action == "inspect_plugin_chain":
        plugin = snapshot["plugin"]
        missing = []
        if not plugin.get("package_current_with_source"):
            missing.append("current_reviewed_extension_package")
        if not plugin.get("verified_non_amazon_extension_install_count"):
            missing.append("verified_non_amazon_extension_install")
        if not plugin.get("verified_non_amazon_store_binding_count"):
            missing.append("verified_non_amazon_store_binding")
        return {
            "status": "local_plugin_source_review_ready",
            "missing": missing,
            "plugin": plugin,
            "local_action_allowed": True,
            "browser_launched": False,
            "extension_installed": False,
            "store_bound": False,
            "page_captured": False,
            "cloud_task_executed": False,
            "external_action_count": 0,
        }
    provider = next(
        (item for item in snapshot["providers"] if item.get("id") == provider_id), None
    )
    if not provider:
        return {
            "status": "blocked_unknown_provider",
            "error": "Select a supported non-Amazon browser provider.",
            "missing": ["supported_provider"],
            "local_action_allowed": False,
            "browser_launched": False,
            "extension_installed": False,
            "store_bound": False,
            "page_captured": False,
            "cloud_task_executed": False,
            "external_action_count": 0,
        }
    if action == "inspect_provider":
        return {
            "status": "provider_capability_review_ready" if provider["installed"] else "blocked_provider_not_installed",
            "missing": [] if provider["installed"] else ["local_browser_installation"],
            "provider": provider,
            "local_action_allowed": True,
            "browser_launched": False,
            "extension_installed": False,
            "store_bound": False,
            "page_captured": False,
            "cloud_task_executed": False,
            "external_action_count": 0,
        }
    if action in set(snapshot["blocked_actions"]):
        return {
            "status": "blocked_external_action",
            "error": "This control plane only audits and prepares local packets; browser launch, extension install, binding, capture and cloud execution require a separate owner action.",
            "missing": ["explicit_owner_action", "verified_store_route"],
            "provider": provider,
            "local_action_allowed": False,
            "browser_launched": False,
            "extension_installed": False,
            "store_bound": False,
            "page_captured": False,
            "cloud_task_executed": False,
            "external_action_count": 0,
        }
    if action != "prepare_binding_packet":
        raise ValueError("Unknown browser/plugin action.")
    if not provider["installed"]:
        return {
            "status": "blocked_provider_not_installed",
            "missing": ["local_browser_installation"],
            "provider": provider,
            "local_action_allowed": False,
            "browser_launched": False,
            "extension_installed": False,
            "store_bound": False,
            "page_captured": False,
            "cloud_task_executed": False,
            "external_action_count": 0,
        }
    country_site = str(request.get("country_site") or "").strip()
    if country_site.casefold() in REGION_GROUPS:
        return {
            "status": "blocked_non_executable_route",
            "error": "Use an exact country/site, not a region grouping.",
            "missing": ["exact_country_site"],
            "provider": provider,
            "local_action_allowed": False,
            "browser_launched": False,
            "extension_installed": False,
            "store_bound": False,
            "page_captured": False,
            "cloud_task_executed": False,
            "external_action_count": 0,
        }
    store_model = str(request.get("store_model") or "").strip().casefold()
    if "full_managed" in store_model:
        return {
            "status": "blocked_non_executable_route",
            "error": "Platform official full managed is recognition-only and cannot be bound as a T-one store.",
            "missing": ["supported_store_model"],
            "provider": provider,
            "local_action_allowed": False,
            "browser_launched": False,
            "extension_installed": False,
            "store_bound": False,
            "page_captured": False,
            "cloud_task_executed": False,
            "external_action_count": 0,
        }
    required = snapshot["required_binding_route"]
    missing = [field for field in required if not str(request.get(field) or "").strip()]
    if missing:
        return {
            "status": "blocked_missing_route",
            "missing": missing,
            "provider": provider,
            "local_action_allowed": False,
            "browser_launched": False,
            "extension_installed": False,
            "store_bound": False,
            "page_captured": False,
            "cloud_task_executed": False,
            "external_action_count": 0,
        }
    packet = {
        field: _clean_identifier(request.get(field), field, required=True)
        for field in required
    }
    packet.update(
        {
            "provider": provider_id,
            "provider_install_state": provider["status"],
            "profile_selection_state": "manual_owner_selection_required",
            "extension_install_state": "not_verified",
            "binding_state": "not_performed",
            "browser_launch_state": "not_performed",
            "capture_state": "not_performed",
            "cloud_execution_state": "not_performed",
        }
    )
    return {
        "status": "local_binding_packet_ready",
        "missing": [],
        "provider": provider,
        "binding_packet": packet,
        "local_action_allowed": True,
        "browser_launched": False,
        "extension_installed": False,
        "store_bound": False,
        "page_captured": False,
        "cloud_task_executed": False,
        "external_action_count": 0,
    }


def run_browser_plugin_audit(root: Path, payload: dict[str, Any], *, actor: str = "owner") -> dict[str, Any]:
    request = payload.get("request") if isinstance(payload.get("request"), dict) else payload
    result = evaluate_browser_plugin_request(root, request)
    safe_request = {
        key: request.get(key)
        for key in (
            "provider",
            "platform",
            "country_site",
            "store_model",
            "ownership",
            "tenant_id",
            "project_id",
            "store_binding_id",
            "execution_identity_id",
            "action",
        )
        if request.get(key) not in (None, "")
    }
    audit = {
        "id": f"browser-plugin-audit-{uuid4().hex[:16]}",
        "created_at": _now(),
        "actor": str(actor or "owner")[:120],
        "request": safe_request,
        "result": result,
    }
    state = _state(root)
    state["audits"].append(audit)
    _save_state(root, state)
    return {"ok": True, "audit": audit}


def record_browser_plugin_review(root: Path, payload: dict[str, Any], *, actor: str = "owner") -> dict[str, Any]:
    audit_id = _clean_identifier(payload.get("audit_id"), "audit_id", required=True)
    state = _state(root)
    audit = next((item for item in state["audits"] if item.get("id") == audit_id), None)
    if not audit:
        raise ValueError("Browser/plugin audit not found.")
    review = {
        "id": f"browser-plugin-review-{uuid4().hex[:16]}",
        "created_at": _now(),
        "actor": str(actor or "owner")[:120],
        "audit_id": audit_id,
        "evidence_source": str(payload.get("evidence_source") or "formal_app_manual")[:120],
        "evidence_ref": str(payload.get("evidence_ref") or f"formal-app:{audit_id}")[:240],
        "browser_launch_observed": False,
        "extension_install_observed": False,
        "store_binding_observed": False,
        "page_capture_observed": False,
        "cloud_execution_observed": False,
        "platform_write_observed": False,
        "causal_conclusion": "inconclusive",
    }
    state["reviews"].append(review)
    _save_state(root, state)
    return {"ok": True, "review": review}
