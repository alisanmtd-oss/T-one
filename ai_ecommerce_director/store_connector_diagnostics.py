from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from .browser_environments import browser_environment_snapshot
from .credential_store import credential_available, credential_reference_catalog
from .erp_connector_registry import (
    ERP_HTTP_JSON_PROTOCOL,
    erp_connector_metadata,
    verified_erp_connector_options,
)
from .store_authorization import AMAZON_SP_API_PROVIDER_ID
from .platform_product_requirements import build_platform_product_requirements_snapshot
from .workspace_runtime import load_workspace_config
from .workspace_schema import find_store


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _matches_scope(values: Any, expected: str) -> bool:
    if not isinstance(values, list) or not values:
        return True
    normalized = {_text(item).casefold() for item in values if _text(item)}
    return expected.casefold() in normalized or "*" in normalized or "global" in normalized


def _erp_connector_options(
    root: Path,
    *,
    project_id: str,
    store_binding_id: str,
    platform: str,
    country_site: str,
    store_model: str,
    ownership: str = "",
    current_connector_id: str = "",
) -> list[dict[str, Any]]:
    registry = _load_json(root / "config" / "integration_hub.json")
    rows: list[dict[str, Any]] = []
    for item in registry.get("connectors", []):
        if not isinstance(item, dict):
            continue
        connector_kind = _text(
            item.get("connector_kind") or item.get("connector_type") or item.get("kind")
        ).lower()
        group = _text(item.get("group")).casefold()
        if connector_kind != "erp" and group != "erp":
            continue
        connector_id = _text(item.get("id")).lower()
        if not connector_id:
            continue
        if not _matches_scope(item.get("platforms"), platform):
            continue
        if not _matches_scope(item.get("country_sites"), country_site):
            continue
        if not _matches_scope(item.get("store_models"), store_model):
            continue
        status = _text(item.get("status")).lower() or "not_configured"
        rows.append(
            {
                "id": connector_id,
                "label": _text(item.get("name")) or connector_id,
                "status": status,
                "available": False,
                "installable": status in {"core_available", "configured", "ready", "live"},
                "source": "adapter_catalog_not_store_verified",
                "selected": connector_id == current_connector_id,
            }
        )
    private_rows = verified_erp_connector_options(
        root,
        project_id=project_id,
        store_binding_id=store_binding_id,
        platform=platform,
        country_site=country_site,
        store_model=store_model,
        ownership=ownership,
        current_connector_id=current_connector_id,
    )
    by_id = {item["id"]: item for item in rows}
    for item in private_rows:
        by_id[item["id"]] = item
    rows = list(by_id.values())
    if current_connector_id and not any(item["id"] == current_connector_id for item in rows):
        rows.append(
            {
                "id": current_connector_id,
                "label": "当前已保存的 ERP 引用（本机未安装）",
                "status": "missing_local",
                "available": False,
                "selected": True,
            }
        )
    return rows


def build_store_connection_options(
    root: Path, project_id: str, store_binding_id: str
) -> dict[str, Any]:
    project_id = _text(project_id).lower()
    store_binding_id = _text(store_binding_id).lower()
    workspace = load_workspace_config(root)
    found = find_store(workspace, store_binding_id)
    if found is None or _text(found[0].get("id")).lower() != project_id:
        raise ValueError("所选真实店铺不存在，或不属于当前项目。")
    _project, channel, store = found
    platform = _text(channel.get("platform") or store.get("platform")).lower()
    country_site = _text(
        channel.get("country_site") or store.get("country_site") or "GLOBAL"
    ).upper()
    store_model = _text(store.get("store_model")).lower()
    current_credential_ref = _text(store.get("credential_ref")).lower()
    current_erp_connector_id = _text(store.get("erp_connector_id")).lower()

    authorization_options: list[dict[str, Any]] = []
    for item in credential_reference_catalog(root):
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        reference = _text(item.get("reference")).lower()
        exact_store_scope = (
            _text(metadata.get("purpose")).lower() == "store_platform_api"
            and _text(metadata.get("project_id")).lower() == project_id
            and _text(metadata.get("store_binding_id")).lower() == store_binding_id
        )
        if not exact_store_scope and reference != current_credential_ref:
            continue
        label = _text(metadata.get("label"))
        if not label:
            label = f"{platform.upper()} {country_site} 店铺授权"
        authorization_options.append(
            {
                "id": reference,
                "label": label,
                "available": bool(item.get("available")),
                "selected": reference == current_credential_ref,
                "status": "available" if item.get("available") else "missing_local",
            }
        )
    if current_credential_ref and not any(
        item["id"] == current_credential_ref for item in authorization_options
    ):
        authorization_options.append(
            {
                "id": current_credential_ref,
                "label": "当前已保存的授权引用（本机凭据缺失）",
                "available": False,
                "selected": True,
                "status": "missing_local",
            }
        )

    erp_options = _erp_connector_options(
        root,
        project_id=project_id,
        store_binding_id=store_binding_id,
        platform=platform,
        country_site=country_site,
        store_model=store_model,
        ownership=_text(store.get("ownership")).lower(),
        current_connector_id=current_erp_connector_id,
    )
    route_key = _text(store.get("route_key")) or f"{platform}:{country_site}:{store_model}"
    setup: dict[str, Any] = {"supported": False}
    if platform == "amazon" and country_site == "US":
        setup = {
            "supported": True,
            "provider_id": AMAZON_SP_API_PROVIDER_ID,
            "mode": "private_self_authorization",
            "marketplace_id": "ATVPDKIKX0DER",
            "verify_endpoint": (
                f"/api/v1/projects/{project_id}/stores/{store_binding_id}/"
                "platform-authorizations/amazon-sp-api/verify"
            ),
            "retest_endpoint": (
                f"/api/v1/projects/{project_id}/stores/{store_binding_id}/"
                "platform-authorizations/amazon-sp-api/retest"
            ),
            "docs_url": "https://developer-docs.amazon.com/sp-api/docs/self-authorization",
            "ads": {
                "status": "separate_application_required",
                "label": "Amazon Ads API 需要单独申请与 OAuth 授权",
                "docs_url": "https://advertising.amazon.com/about-api",
            },
        }
    return {
        "schema_version": 1,
        "project_id": project_id,
        "store_binding_id": store_binding_id,
        "route_key": route_key,
        "platform_authorizations": {
            "options": authorization_options,
            "has_available": any(item["available"] for item in authorization_options),
            "empty_reason": (
                ""
                if any(item["available"] for item in authorization_options)
                else f"本机尚无可用于 {platform.upper()} {country_site} 当前店铺的授权引用。"
            ),
            "setup": setup,
        },
        "erp_connectors": {
            "options": erp_options,
            "has_available": any(item["available"] for item in erp_options),
            "empty_reason": (
                ""
                if any(item["available"] for item in erp_options)
                else "当前尚未安装并验证可用的 ERP 连接器。"
            ),
            "setup": {
                "supported": True,
                "protocol": ERP_HTTP_JSON_PROTOCOL,
                "mode": "store_scoped_read_only_verification",
                "verify_endpoint": (
                    f"/api/v1/projects/{project_id}/stores/{store_binding_id}/"
                    "erp-connectors/http-json/verify"
                ),
                "retest_endpoint": (
                    f"/api/v1/projects/{project_id}/stores/{store_binding_id}/"
                    "erp-connectors/http-json/retest"
                ),
                "remote_transport": "https_443_only",
                "local_transport": "developer_registration_required",
                "verified_capabilities": ["health_read"],
            },
        },
    }


def _positive_int(value: Any) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def _provider(snapshot: dict[str, Any], provider_id: str) -> dict[str, Any] | None:
    requested = provider_id.strip().lower()
    for item in snapshot.get("providers", []):
        if isinstance(item, dict) and _text(item.get("id")).lower() == requested:
            return item
    return None


def _profile(
    provider: dict[str, Any], profile_id: str, profile_sequence: int
) -> dict[str, Any] | None:
    requested_id = profile_id.strip().lower()
    for item in provider.get("profiles", []):
        if not isinstance(item, dict):
            continue
        if requested_id and _text(item.get("id")).lower() == requested_id:
            return item
        if profile_sequence and _positive_int(item.get("sequence")) == profile_sequence:
            return item
    return None


def _expected_profile_tag(platform: str, country_site: str) -> str:
    return f"{platform}:{country_site}".lower()


def _browser_result(
    snapshot: dict[str, Any],
    *,
    provider_id: str,
    profile_id: str,
    profile_sequence: int,
    platform: str,
    country_site: str,
) -> dict[str, Any]:
    if not provider_id:
        return {
            "status": "not_configured",
            "provider_id": "",
            "provider_name": "",
            "profile_sequence": profile_sequence,
            "scope_match": "unknown",
            "message": "当前店铺还没有选择浏览器环境。",
        }
    provider = _provider(snapshot, provider_id)
    if provider is None or not provider.get("installed"):
        return {
            "status": "not_installed",
            "provider_id": provider_id,
            "provider_name": _text((provider or {}).get("name")) or provider_id,
            "profile_sequence": profile_sequence,
            "scope_match": "unknown",
            "message": "当前电脑未检测到已配置的店铺浏览器。",
        }
    provider_name = _text(provider.get("name")) or provider_id
    if _text(provider.get("adapter")) != "official_local_api":
        return {
            "status": "installed_manual_check",
            "provider_id": provider_id,
            "provider_name": provider_name,
            "profile_sequence": profile_sequence,
            "scope_match": "unknown",
            "message": "浏览器已安装；当前适配器需要负责人选择对应店铺环境后再继续。",
        }
    if _text(provider.get("status")) != "ready":
        return {
            "status": "installed_offline",
            "provider_id": provider_id,
            "provider_name": provider_name,
            "profile_sequence": profile_sequence,
            "scope_match": "unknown",
            "message": "浏览器已安装，但本地 API 尚未连接。",
        }
    if not profile_id and not profile_sequence:
        return {
            "status": "profile_required",
            "provider_id": provider_id,
            "provider_name": provider_name,
            "profile_sequence": 0,
            "scope_match": "unknown",
            "message": "浏览器本地 API 可读，但当前店铺还没有选择独立环境。",
        }
    matched = _profile(provider, profile_id, profile_sequence)
    if matched is None:
        return {
            "status": "profile_not_found",
            "provider_id": provider_id,
            "provider_name": provider_name,
            "profile_sequence": profile_sequence,
            "scope_match": "unknown",
            "message": "本地 API 可读，但没有找到当前店铺绑定的浏览器环境。",
        }
    safe_tags = {
        _text(item).lower()
        for item in matched.get("tags", [])
        if _text(item)
    }
    expected_tag = _expected_profile_tag(platform, country_site)
    scope_match = "matched" if expected_tag in safe_tags else "unverified"
    message = "已找到当前店铺的独立浏览器环境。"
    if scope_match == "unverified":
        message += " 环境标签尚未验证平台与国家站点。"
    return {
        "status": "connected",
        "provider_id": provider_id,
        "provider_name": provider_name,
        "profile_sequence": _positive_int(matched.get("sequence")) or profile_sequence,
        "scope_match": scope_match,
        "message": message,
    }


def _api_result(
    root: Path,
    store: dict[str, Any],
    *,
    project_id: str,
    platform: str,
    country_site: str,
) -> dict[str, Any]:
    credential_ref = _text(store.get("credential_ref"))
    if not credential_ref:
        return {
            "status": "not_authorized",
            "credential_configured": False,
            "message": "当前店铺未配置平台开发者 API 授权。",
        }
    if not credential_available(root, credential_ref=credential_ref):
        return {
            "status": "credential_missing_local",
            "credential_configured": True,
            "message": "店铺已保存授权引用，但本机没有可用凭据。",
        }
    credential_metadata: dict[str, Any] = {}
    for item in credential_reference_catalog(root):
        if _text(item.get("reference")).lower() != credential_ref.lower():
            continue
        metadata = item.get("metadata")
        credential_metadata = dict(metadata) if isinstance(metadata, dict) else {}
        break
    exact_scope = (
        _text(credential_metadata.get("purpose")).lower() == "store_platform_api"
        and _text(credential_metadata.get("project_id")).lower() == project_id.lower()
        and _text(credential_metadata.get("store_binding_id")).lower()
        == _text(store.get("id")).lower()
        and _text(credential_metadata.get("platform")).lower() == platform.lower()
        and _text(credential_metadata.get("country_site")).upper() == country_site.upper()
    )
    if exact_scope and _text(credential_metadata.get("verification_status")).lower() == "live_verified":
        return {
            "status": "connected_read_only",
            "credential_configured": True,
            "provider_id": _text(credential_metadata.get("provider_id")),
            "verified_at": _text(credential_metadata.get("verified_at")),
            "message": "当前店铺的平台 API 已通过在线只读权限验证。",
        }
    return {
        "status": "credential_ready_live_test_pending",
        "credential_configured": True,
        "message": "本机凭据可用；还需要由对应平台适配器完成在线权限测试。",
    }


def _erp_result(
    root: Path,
    store: dict[str, Any],
    *,
    project_id: str,
    store_binding_id: str,
    platform: str,
    country_site: str,
    store_model: str,
    ownership: str,
) -> dict[str, Any]:
    connector_id = _text(store.get("erp_connector_id"))
    if not connector_id:
        return {
            "status": "not_configured",
            "connector_configured": False,
            "message": "当前店铺未配置 ERP 连接器。",
        }
    available = next(
        (
            item
            for item in _erp_connector_options(
                root,
                project_id=project_id,
                store_binding_id=store_binding_id,
                platform=platform,
                country_site=country_site,
                store_model=store_model,
                ownership=ownership,
                current_connector_id=connector_id,
            )
            if item["id"] == connector_id and item["available"]
        ),
        None,
    )
    if available is None:
        return {
            "status": "connector_missing_local",
            "connector_configured": True,
            "connector_available": False,
            "message": "店铺已保存 ERP 引用，但本机没有已安装且可用的同名连接器。",
        }
    metadata = erp_connector_metadata(root, connector_id)
    if (
        _text(metadata.get("protocol")) == ERP_HTTP_JSON_PROTOCOL
        and _text(metadata.get("verification_status")).lower() == "live_verified"
    ):
        return {
            "status": "connected_read_only",
            "connector_configured": True,
            "connector_available": True,
            "connector_id": connector_id,
            "verified_at": _text(metadata.get("verified_at")),
            "capabilities": list(metadata.get("capabilities") or []),
            "message": "当前店铺的 ERP / 云端插件已通过在线只读连接验证。",
        }
    return {
        "status": "configured_live_test_pending",
        "connector_configured": True,
        "connector_available": True,
        "message": "ERP 连接器已指定；还需要执行在线读权限测试。",
    }


def run_store_connection_test(
    root: Path, project_id: str, store_binding_id: str
) -> dict[str, Any]:
    project_id = _text(project_id).lower()
    store_binding_id = _text(store_binding_id).lower()
    workspace = load_workspace_config(root)
    found = find_store(workspace, store_binding_id)
    if found is None or _text(found[0].get("id")).lower() != project_id:
        raise ValueError("所选真实店铺不存在，或不属于当前项目。")
    project, _channel, store = found
    requirements = build_platform_product_requirements_snapshot(
        root, project_id, store_binding_id
    )
    scope = requirements.get("scope") if isinstance(requirements.get("scope"), dict) else {}
    platform = _text(scope.get("platform")).lower()
    country_site = _text(scope.get("country_site")).upper()
    commerce_mode = _text(scope.get("commerce_mode")).lower()
    ownership = _text(scope.get("ownership")).lower()
    store_ownership = _text(store.get("ownership")).lower()
    provider_id = _text(store.get("browser_provider")).lower()
    profile_id = _text(store.get("browser_profile_id"))
    profile_sequence = _positive_int(
        store.get("browser_profile_sequence") or store.get("browser_profile_seq")
    )
    browser = _browser_result(
        browser_environment_snapshot(root),
        provider_id=provider_id,
        profile_id=profile_id,
        profile_sequence=profile_sequence,
        platform=platform,
        country_site=country_site,
    )
    platform_api = _api_result(
        root,
        store,
        project_id=project_id,
        platform=platform,
        country_site=country_site,
    )
    erp = _erp_result(
        root,
        store,
        project_id=project_id,
        store_binding_id=store_binding_id,
        platform=platform,
        country_site=country_site,
        store_model=commerce_mode,
        ownership=store_ownership,
    )
    if browser["status"] != "connected":
        overall = "browser_connection_required"
    elif platform_api["status"] == "not_authorized":
        overall = "browser_connected_api_pending"
    elif platform_api["status"] == "credential_missing_local":
        overall = "api_credential_required"
    elif platform_api["status"] == "connected_read_only":
        overall = "live_adapter_connected"
    else:
        overall = "live_adapter_test_pending"
    connector = (
        requirements.get("connector")
        if isinstance(requirements.get("connector"), dict)
        else {}
    )
    domains = connector.get("domains")
    if not isinstance(domains, dict):
        domains = {}
    return {
        "schema_version": 1,
        "generated_at": _now_iso(),
        "status": overall,
        "project_id": _text(project.get("id")),
        "store_binding_id": _text(store.get("id")),
        "route_key": f"{platform}:{country_site}:{commerce_mode}",
        "scope": {
            "platform": platform,
            "country_site": country_site,
            "commerce_mode": commerce_mode,
            "ownership": ownership,
        },
        "browser": browser,
        "platform_api": platform_api,
        "erp": erp,
        "execution_domains": {
            key: _text(value.get("status"))
            for key, value in domains.items()
            if isinstance(value, dict)
        },
        "message": (
            "浏览器环境已连接；平台 API 与 ERP 仍需按当前店铺单独授权。"
            if overall == "browser_connected_api_pending"
            else "平台 API 已通过在线只读验证；ERP 仍按当前店铺单独配置。"
            if overall == "live_adapter_connected"
            else "连接检测已完成，请按各项结果继续配置。"
        ),
    }


__all__ = ["build_store_connection_options", "run_store_connection_test"]
