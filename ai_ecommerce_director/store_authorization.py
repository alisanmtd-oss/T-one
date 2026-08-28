from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .credential_store import (
    credential_reference_catalog,
    load_credential,
    save_credential,
)
from .workspace_runtime import load_workspace_config, save_store_connection_configuration
from .workspace_schema import find_store


AMAZON_LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
AMAZON_SP_API_NA_ENDPOINT = "https://sellingpartnerapi-na.amazon.com"
AMAZON_US_MARKETPLACE_ID = "ATVPDKIKX0DER"
AMAZON_SP_API_PROVIDER_ID = "amazon_sp_api"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _store_scope(
    root: Path, project_id: str, store_binding_id: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    project_id = _text(project_id).lower()
    store_binding_id = _text(store_binding_id).lower()
    found = find_store(load_workspace_config(root), store_binding_id)
    if found is None or _text(found[0].get("id")).lower() != project_id:
        raise ValueError("所选真实店铺不存在，或不属于当前项目。")
    project, channel, store = found
    platform = _text(channel.get("platform") or store.get("platform")).lower()
    country_site = _text(
        channel.get("country_site") or store.get("country_site") or "GLOBAL"
    ).upper()
    if platform != "amazon":
        raise ValueError("当前授权器只适用于 Amazon 店铺。")
    if country_site != "US":
        raise ValueError("当前版本先支持 Amazon US 私有应用自授权。")
    return project, channel, store


def amazon_sp_api_credential_ref(project_id: str, store_binding_id: str) -> str:
    digest = hashlib.sha256(
        f"{_text(project_id).lower()}|{_text(store_binding_id).lower()}|amazon-sp-api".encode(
            "utf-8"
        )
    ).hexdigest()[:24]
    return f"store:amazon-sp-api:{digest}"


def _read_json_response(request: Request, *, timeout: float = 20.0) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        phase = "登录授权" if request.full_url == AMAZON_LWA_TOKEN_URL else "店铺权限"
        raise ConnectionError(
            f"Amazon {phase}验证失败（HTTP {int(exc.code or 0)}）。请检查当前店铺的授权资料和应用权限。"
        ) from None
    except (URLError, TimeoutError, OSError):
        raise ConnectionError("无法连接 Amazon 官方接口，请检查网络后重试。") from None
    except (UnicodeError, ValueError):
        raise ConnectionError("Amazon 官方接口返回了无法识别的数据。") from None
    if not isinstance(payload, dict):
        raise ConnectionError("Amazon 官方接口返回了无法识别的数据。")
    return payload


def verify_amazon_sp_api_credentials(
    *,
    lwa_client_id: str,
    lwa_client_secret: str,
    refresh_token: str,
    timeout: float = 20.0,
) -> dict[str, Any]:
    client_id = str(lwa_client_id or "").strip()
    client_secret = str(lwa_client_secret or "").strip()
    token = str(refresh_token or "").strip()
    if not client_id or not client_secret or not token:
        raise ValueError("LWA Client ID、Client Secret 和 Refresh Token 都必须填写。")
    if max(len(client_id), len(client_secret), len(token)) > 8192:
        raise ValueError("Amazon 授权字段长度异常。")

    token_request = Request(
        AMAZON_LWA_TOKEN_URL,
        data=urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": token,
                "client_id": client_id,
                "client_secret": client_secret,
            }
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Accept": "application/json",
        },
        method="POST",
    )
    token_payload = _read_json_response(token_request, timeout=timeout)
    access_token = str(token_payload.get("access_token") or "").strip()
    if not access_token:
        raise ConnectionError("Amazon 登录授权未返回可用的访问令牌。")

    participation_request = Request(
        AMAZON_SP_API_NA_ENDPOINT + "/sellers/v1/marketplaceParticipations",
        headers={
            "Accept": "application/json",
            "x-amz-access-token": access_token,
            "User-Agent": "TeeLab-Desktop/1.0 (Language=Python)",
        },
        method="GET",
    )
    participation_payload = _read_json_response(participation_request, timeout=timeout)
    raw_rows = participation_payload.get("payload")
    if not isinstance(raw_rows, list):
        raise ConnectionError("Amazon 店铺权限接口没有返回站点参与信息。")

    marketplaces: list[dict[str, Any]] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        marketplace = row.get("marketplace") if isinstance(row.get("marketplace"), dict) else {}
        participation = (
            row.get("participation") if isinstance(row.get("participation"), dict) else {}
        )
        marketplace_id = _text(marketplace.get("id"))
        if not marketplace_id:
            continue
        marketplaces.append(
            {
                "marketplace_id": marketplace_id,
                "country_code": _text(marketplace.get("countryCode")).upper(),
                "name": _text(marketplace.get("name"))[:120],
                "participating": bool(participation.get("isParticipating")),
                "listings_suspended": bool(participation.get("hasSuspendedListings")),
            }
        )
    us_marketplace = next(
        (
            row
            for row in marketplaces
            if row["marketplace_id"] == AMAZON_US_MARKETPLACE_ID
        ),
        None,
    )
    if us_marketplace is None:
        raise PermissionError("该授权未返回 Amazon US 店铺权限，请核对授权店铺和站点。")
    if not us_marketplace["participating"]:
        raise PermissionError("Amazon US 店铺当前未处于可参与状态。")
    return {
        "ok": True,
        "provider_id": AMAZON_SP_API_PROVIDER_ID,
        "authorization_surface": "selling_partner_api",
        "verification_status": "live_verified",
        "verified_at": _now_iso(),
        "marketplace": us_marketplace,
        "marketplace_count": len(marketplaces),
    }


def configure_amazon_sp_api_authorization(
    root: Path,
    project_id: str,
    store_binding_id: str,
    payload: dict[str, Any],
    *,
    actor: str = "owner",
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("Amazon 授权配置必须是对象。")
    _project, _channel, store = _store_scope(root, project_id, store_binding_id)
    if payload.get("confirm_live_read_test") is not True:
        raise ValueError("请确认执行 Amazon 官方只读权限测试。")
    client_id = str(payload.get("lwa_client_id") or "").strip()
    client_secret = str(payload.get("lwa_client_secret") or "").strip()
    refresh_token = str(payload.get("refresh_token") or "").strip()
    verification = verify_amazon_sp_api_credentials(
        lwa_client_id=client_id,
        lwa_client_secret=client_secret,
        refresh_token=refresh_token,
    )
    credential_ref = amazon_sp_api_credential_ref(project_id, store_binding_id)
    secret_bundle = json.dumps(
        {
            "schema_version": 1,
            "provider_id": AMAZON_SP_API_PROVIDER_ID,
            "lwa_client_id": client_id,
            "lwa_client_secret": client_secret,
            "refresh_token": refresh_token,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    save_credential(
        root,
        credential_ref,
        secret_bundle,
        metadata={
            "purpose": "store_platform_api",
            "project_id": project_id,
            "store_binding_id": store_binding_id,
            "platform": "amazon",
            "country_site": "US",
            "provider_id": AMAZON_SP_API_PROVIDER_ID,
            "authorization_surface": "selling_partner_api",
            "verification_status": "live_verified",
            "verified_at": verification["verified_at"],
            "marketplace_ids": AMAZON_US_MARKETPLACE_ID,
            "label": f"Amazon US / {_text(store.get('name')) or store_binding_id}",
        },
    )
    configuration = save_store_connection_configuration(
        root,
        project_id,
        store_binding_id,
        {"credential_ref": credential_ref},
        actor=actor,
    )
    return {
        "ok": True,
        "status": "connected_read_only",
        "provider_id": AMAZON_SP_API_PROVIDER_ID,
        "verified_at": verification["verified_at"],
        "marketplace": verification["marketplace"],
        "configuration": configuration.get("configuration", {}),
        "message": "Amazon US SP-API 已完成在线只读验证，并安全绑定到当前店铺。",
    }


def retest_amazon_sp_api_authorization(
    root: Path,
    project_id: str,
    store_binding_id: str,
    *,
    actor: str = "owner",
) -> dict[str, Any]:
    _project, _channel, store = _store_scope(root, project_id, store_binding_id)
    credential_ref = _text(store.get("credential_ref")).lower()
    expected_ref = amazon_sp_api_credential_ref(project_id, store_binding_id)
    if credential_ref != expected_ref:
        raise ValueError("当前店铺尚未绑定 TeeLab 保存的 Amazon SP-API 授权。")
    raw_bundle = load_credential(root, credential_ref)
    try:
        bundle = json.loads(raw_bundle or "")
    except ValueError:
        bundle = {}
    if not isinstance(bundle, dict) or bundle.get("provider_id") != AMAZON_SP_API_PROVIDER_ID:
        raise ValueError("当前店铺的 Amazon 授权凭据缺失或不可读取。")
    verification = verify_amazon_sp_api_credentials(
        lwa_client_id=str(bundle.get("lwa_client_id") or ""),
        lwa_client_secret=str(bundle.get("lwa_client_secret") or ""),
        refresh_token=str(bundle.get("refresh_token") or ""),
    )
    save_credential(
        root,
        credential_ref,
        raw_bundle or "",
        metadata={
            "purpose": "store_platform_api",
            "project_id": project_id,
            "store_binding_id": store_binding_id,
            "platform": "amazon",
            "country_site": "US",
            "provider_id": AMAZON_SP_API_PROVIDER_ID,
            "authorization_surface": "selling_partner_api",
            "verification_status": "live_verified",
            "verified_at": verification["verified_at"],
            "marketplace_ids": AMAZON_US_MARKETPLACE_ID,
            "label": f"Amazon US / {_text(store.get('name')) or store_binding_id}",
        },
    )
    save_store_connection_configuration(
        root,
        project_id,
        store_binding_id,
        {"credential_ref": credential_ref},
        actor=actor,
    )
    return {
        "ok": True,
        "status": "connected_read_only",
        "provider_id": AMAZON_SP_API_PROVIDER_ID,
        "verified_at": verification["verified_at"],
        "marketplace": verification["marketplace"],
        "message": "Amazon US SP-API 在线只读复测通过。",
    }


def amazon_sp_api_authorization_metadata(
    root: Path, credential_ref: str
) -> dict[str, str]:
    requested = _text(credential_ref).lower()
    for item in credential_reference_catalog(root):
        if _text(item.get("reference")).lower() != requested:
            continue
        metadata = item.get("metadata")
        return dict(metadata) if isinstance(metadata, dict) else {}
    return {}


__all__ = [
    "AMAZON_SP_API_PROVIDER_ID",
    "AMAZON_US_MARKETPLACE_ID",
    "amazon_sp_api_authorization_metadata",
    "amazon_sp_api_credential_ref",
    "configure_amazon_sp_api_authorization",
    "retest_amazon_sp_api_authorization",
    "verify_amazon_sp_api_credentials",
]
