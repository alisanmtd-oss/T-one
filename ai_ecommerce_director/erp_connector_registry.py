from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .credential_store import delete_credential, load_credential, save_credential
from .workspace_runtime import load_workspace_config, save_store_connection_configuration
from .workspace_schema import find_store


ERP_HTTP_JSON_PROTOCOL = "http_json_v1"
ERP_REGISTRY_SCHEMA_VERSION = 1
ERP_MAX_RESPONSE_BYTES = 1024 * 1024
ERP_VERIFICATION_TTL_SECONDS = 24 * 60 * 60
ERP_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,79}$")
ERP_SAFE_HEADER = re.compile(r"^x-[a-z0-9][a-z0-9-]{1,63}$", re.IGNORECASE)
ERP_SAFE_REMOTE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")
ERP_ALLOWED_AUTH_TYPES = {"none", "bearer", "header"}
ERP_ALLOWED_CAPABILITIES = {
    "health_read",
    "products_read",
    "orders_read",
    "inventory_read",
    "shipments_read",
    "settlements_read",
}
_LOCK = threading.RLock()


class _ERPTransportError(ConnectionError):
    """Internal marker for a network failure that is safe to retry on another pinned IP."""


class _ERPResponseError(ConnectionError):
    """Internal marker for an HTTP response that must not be retried across addresses."""


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection that keeps DNS validation and the actual socket in sync."""

    def __init__(
        self,
        hostname: str,
        pinned_ip: str,
        port: int,
        *,
        timeout: float,
    ) -> None:
        super().__init__(
            hostname,
            port=port,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        sock = socket.create_connection(
            (self._pinned_ip, self.port),
            self.timeout,
            self.source_address,
        )
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def erp_connector_registry_path(root: Path) -> Path:
    return root / "data" / "private" / "erp_connectors.json"


def _load_registry(root: Path) -> dict[str, Any]:
    try:
        payload = json.loads(erp_connector_registry_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {}
    connectors = payload.get("connectors") if isinstance(payload, dict) else []
    if not isinstance(connectors, list):
        connectors = []
    return {
        "schema_version": ERP_REGISTRY_SCHEMA_VERSION,
        "connectors": [item for item in connectors if isinstance(item, dict)],
    }


def _write_registry(root: Path, payload: dict[str, Any]) -> None:
    path = erp_connector_registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _store_scope(
    root: Path, project_id: str, store_binding_id: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    project_id = _text(project_id).lower()
    store_binding_id = _text(store_binding_id).lower()
    found = find_store(load_workspace_config(root), store_binding_id)
    if found is None or _text(found[0].get("id")).lower() != project_id:
        raise ValueError("所选真实店铺不存在，或不属于当前项目。")
    project, channel, store = found
    scope = {
        "project_id": project_id,
        "store_binding_id": store_binding_id,
        "platform": _text(channel.get("platform") or store.get("platform")).lower(),
        "country_site": _text(
            channel.get("country_site") or store.get("country_site") or "GLOBAL"
        ).upper(),
        "store_model": _text(store.get("store_model")).lower(),
        "ownership": _text(store.get("ownership")).lower(),
    }
    return project, channel, store, scope


def _slug(value: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:24]
    return clean or "adapter"


def erp_connector_id(project_id: str, store_binding_id: str, display_name: str) -> str:
    digest = hashlib.sha256(
        (
            f"{_text(project_id).lower()}|{_text(store_binding_id).lower()}|"
            f"{_text(display_name).casefold()}|{ERP_HTTP_JSON_PROTOCOL}"
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"erp-{_slug(display_name)}-{digest}"


def erp_connector_credential_ref(connector_id: str) -> str:
    clean = _text(connector_id).lower()
    if not ERP_SAFE_ID.fullmatch(clean):
        raise ValueError("ERP 连接器编号无效。")
    return f"erp:{clean}"


def _validate_health_path(value: Any) -> str:
    path = str(value or "/health").strip()
    parsed = urlparse(path)
    if (
        not path.startswith("/")
        or path.startswith("//")
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or ".." in parsed.path.split("/")
        or len(path) > 240
    ):
        raise ValueError("ERP 只读检测路径无效；请填写类似 /health 的站内路径。")
    return path


def _development_loopback_enabled() -> bool:
    return str(os.getenv("TEELAB_ERP_DEVELOPMENT_MODE") or "").strip() == "1"


def _validate_base_url(
    value: Any, *, allow_loopback: bool = False
) -> tuple[str, str, int]:
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or len(raw) > 500
    ):
        raise ValueError("ERP 地址必须是未携带账号、密码或查询参数的 HTTP(S) 基础地址。")
    hostname = parsed.hostname.casefold().rstrip(".")
    local_host = hostname in {"localhost", "127.0.0.1", "::1"}
    if local_host and not allow_loopback:
        raise ValueError("真实店铺不能绑定任意本机地址；本机桥接器必须先进入开发者注册流程。")
    if parsed.scheme == "http" and not (local_host and allow_loopback):
        raise ValueError("远程 ERP / 云端插件必须使用 HTTPS。")
    try:
        port = parsed.port
    except ValueError:
        raise ValueError("ERP 地址端口无效。") from None
    port = int(port or (443 if parsed.scheme == "https" else 80))
    if local_host:
        if not 1024 <= port <= 65535:
            raise ValueError("本机开发桥接器只能使用 1024-65535 端口。")
    elif port != 443:
        raise ValueError("远程 ERP / 云端插件只允许使用 HTTPS 443 端口。")
    normalized = f"{parsed.scheme}://{hostname}"
    default_port = 443 if parsed.scheme == "https" else 80
    if port != default_port:
        normalized += f":{port}"
    if parsed.path and parsed.path != "/":
        normalized += "/" + parsed.path.strip("/")
    return normalized.rstrip("/"), hostname, port


def _resolve_target_addresses(
    hostname: str, port: int, *, allow_loopback: bool = False
) -> list[str]:
    local_host = hostname in {"localhost", "127.0.0.1", "::1"}
    try:
        addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError:
        raise ConnectionError("无法解析 ERP / 云端插件地址，请检查域名。") from None
    if not addresses:
        raise ConnectionError("ERP / 云端插件域名没有可用地址。")
    safe_addresses: list[str] = []
    for address in addresses:
        raw_ip = str(address[4][0]).split("%", 1)[0]
        try:
            parsed_ip = ipaddress.ip_address(raw_ip)
        except ValueError:
            raise ConnectionError("ERP / 云端插件域名返回了无法识别的地址。") from None
        if local_host and allow_loopback:
            if not parsed_ip.is_loopback:
                raise ValueError("本机开发桥接器只能解析到 loopback 地址。")
        elif not parsed_ip.is_global:
            raise ValueError("远程 ERP / 云端插件不能解析到本机、内网或保留地址。")
        canonical = parsed_ip.compressed
        if canonical not in safe_addresses:
            safe_addresses.append(canonical)
    return safe_addresses


def _verification_expiry(verified_at: str) -> str:
    try:
        parsed = datetime.fromisoformat(verified_at.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (parsed + timedelta(seconds=ERP_VERIFICATION_TTL_SECONDS)).isoformat()


def _verification_is_fresh(record: dict[str, Any]) -> bool:
    if _text(record.get("verification_status")).lower() != "live_verified":
        return False
    expires_at = _text(record.get("expires_at"))
    try:
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires > datetime.now(timezone.utc)


def _auth_configuration(payload: dict[str, Any]) -> tuple[str, str, str]:
    auth_type = _text(payload.get("auth_type") or "none").lower()
    if auth_type not in ERP_ALLOWED_AUTH_TYPES:
        raise ValueError("ERP 鉴权方式只支持无鉴权、Bearer Token 或自定义请求头。")
    header_name = _text(payload.get("auth_header_name")).lower()
    auth_value = str(payload.get("auth_value") or "").strip()
    if auth_type == "none":
        return auth_type, "", ""
    if not auth_value:
        raise ValueError("当前 ERP 鉴权方式必须填写 Token / API Key。")
    if len(auth_value) > 8192:
        raise ValueError("ERP 鉴权字段长度异常。")
    if auth_type == "header":
        if not ERP_SAFE_HEADER.fullmatch(header_name):
            raise ValueError("自定义鉴权请求头必须使用 X- 开头的安全名称。")
    else:
        header_name = "authorization"
    return auth_type, header_name, auth_value


def _normalized_identity_scope(values: dict[str, Any]) -> dict[str, str]:
    return {
        "project_id": _text(values.get("project_id")).lower(),
        "store_binding_id": _text(values.get("store_binding_id")).lower(),
        "platform": _text(values.get("platform")).lower(),
        "country_site": _text(values.get("country_site")).upper(),
        "store_model": _text(values.get("store_model")).lower(),
        "ownership": _text(values.get("ownership")).lower(),
    }


def _validate_connection_identity(
    payload: Any, expected_scope: dict[str, Any] | None
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ConnectionError("ERP / 云端插件必须返回带店铺身份的 JSON 对象。")
    identity = payload.get("connection_identity")
    if not isinstance(identity, dict):
        raise ConnectionError("ERP / 云端插件未返回 connection_identity，不能证明属于当前店铺。")
    raw_scope = identity.get("scope")
    if not isinstance(raw_scope, dict):
        raw_scope = identity
    returned_scope = _normalized_identity_scope(raw_scope)
    required_fields = ("platform", "country_site", "store_model", "ownership")
    if any(not returned_scope[field] for field in required_fields):
        raise ConnectionError("ERP / 云端插件返回的店铺身份字段不完整。")
    expected = _normalized_identity_scope(expected_scope or {})
    if expected_scope:
        for field, expected_value in expected.items():
            if expected_value and returned_scope.get(field) != expected_value:
                raise PermissionError("ERP / 云端插件返回的身份与当前项目或店铺不匹配。")
    remote_store_id = _text(identity.get("remote_store_id"))
    if not ERP_SAFE_REMOTE_ID.fullmatch(remote_store_id):
        raise ConnectionError("ERP / 云端插件未返回有效的远端店铺编号。")
    capabilities = identity.get("capabilities")
    if not isinstance(capabilities, list) or "health_read" not in {
        _text(item).lower() for item in capabilities
    }:
        raise PermissionError("ERP / 云端插件未声明 health_read 只读权限。")
    return {
        "remote_store_id": remote_store_id,
        "scope": returned_scope,
        "capabilities": ["health_read"],
    }


def _request_verified_json(
    *,
    normalized_url: str,
    hostname: str,
    port: int,
    pinned_ip: str,
    health_path: str,
    headers: dict[str, str],
    timeout: float,
    allow_loopback: bool,
) -> tuple[Any, str]:
    parsed = urlparse(normalized_url)
    request_path = (parsed.path.rstrip("/") + health_path) or "/"
    connection: http.client.HTTPConnection
    if parsed.scheme == "https":
        connection = _PinnedHTTPSConnection(
            hostname,
            pinned_ip,
            port,
            timeout=timeout,
        )
    elif allow_loopback:
        connection = http.client.HTTPConnection(pinned_ip, port=port, timeout=timeout)
        host_header = f"[{hostname}]" if ":" in hostname else hostname
        if port != 80:
            host_header += f":{port}"
        headers = {**headers, "Host": host_header}
    else:
        raise ValueError("远程 ERP / 云端插件必须使用 HTTPS。")
    try:
        connection.request("GET", request_path, headers=headers)
        response = connection.getresponse()
        if not 200 <= int(response.status) < 300:
            raise _ERPResponseError(
                f"ERP / 云端插件只读检测失败（HTTP {int(response.status)}）。请检查地址、权限和鉴权资料。"
            )
        raw = response.read(ERP_MAX_RESPONSE_BYTES + 1)
        content_type = _text(response.getheader("Content-Type"))
    except _ERPResponseError:
        raise
    except (OSError, ssl.SSLError, TimeoutError, http.client.HTTPException):
        raise _ERPTransportError(
            "无法连接 ERP / 云端插件，请检查网络、地址和服务状态。"
        ) from None
    finally:
        connection.close()
    if len(raw) > ERP_MAX_RESPONSE_BYTES:
        raise ConnectionError("ERP / 云端插件检测响应过大，已停止读取。")
    try:
        return json.loads(raw.decode("utf-8")), content_type
    except (UnicodeError, ValueError):
        raise ConnectionError("ERP / 云端插件未返回可识别的 JSON 数据。") from None


def verify_erp_http_json_connection(
    *,
    base_url: str,
    health_path: str = "/health",
    auth_type: str = "none",
    auth_header_name: str = "",
    auth_value: str = "",
    timeout: float = 15.0,
    expected_scope: dict[str, Any] | None = None,
    allow_loopback: bool | None = None,
) -> dict[str, Any]:
    if allow_loopback is None:
        allow_loopback = _development_loopback_enabled()
    normalized_url, hostname, port = _validate_base_url(
        base_url, allow_loopback=allow_loopback
    )
    path = _validate_health_path(health_path)
    addresses = _resolve_target_addresses(
        hostname, port, allow_loopback=allow_loopback
    )
    normalized_auth, normalized_header, normalized_value = _auth_configuration(
        {
            "auth_type": auth_type,
            "auth_header_name": auth_header_name,
            "auth_value": auth_value,
        }
    )
    headers = {
        "Accept": "application/json",
        "User-Agent": "TeeLab-Desktop/1.0 (ERP read-only verification)",
    }
    if normalized_auth == "bearer":
        headers["Authorization"] = f"Bearer {normalized_value}"
    elif normalized_auth == "header":
        headers[normalized_header] = normalized_value
    expected = _normalized_identity_scope(expected_scope or {})
    for key, header in (
        ("project_id", "X-TeeLab-Project"),
        ("store_binding_id", "X-TeeLab-Store"),
        ("platform", "X-TeeLab-Platform"),
        ("country_site", "X-TeeLab-Country-Site"),
        ("store_model", "X-TeeLab-Store-Model"),
        ("ownership", "X-TeeLab-Ownership"),
    ):
        if expected.get(key):
            headers[header] = expected[key]
    started = time.monotonic()
    last_transport_error: _ERPTransportError | None = None
    for pinned_ip in addresses:
        try:
            parsed_payload, content_type = _request_verified_json(
                normalized_url=normalized_url,
                hostname=hostname,
                port=port,
                pinned_ip=pinned_ip,
                health_path=path,
                headers=headers,
                timeout=max(2.0, min(float(timeout), 30.0)),
                allow_loopback=allow_loopback,
            )
            break
        except _ERPTransportError as exc:
            last_transport_error = exc
    else:
        raise ConnectionError(
            str(last_transport_error)
            if last_transport_error
            else "无法连接 ERP / 云端插件，请检查网络、地址和服务状态。"
        ) from None
    identity = _validate_connection_identity(parsed_payload, expected_scope)
    verified_at = _now_iso()
    return {
        "ok": True,
        "status": "live_verified",
        "verified_at": verified_at,
        "expires_at": _verification_expiry(verified_at),
        "protocol": ERP_HTTP_JSON_PROTOCOL,
        "endpoint_origin": normalized_url,
        "health_path": path,
        "remote_store_id": identity["remote_store_id"],
        "identity_scope": identity["scope"],
        "capabilities": identity["capabilities"],
        "response_kind": "object",
        "content_type": content_type.split(";", 1)[0][:80],
        "latency_ms": max(0, int((time.monotonic() - started) * 1000)),
    }


def _safe_connector_record(
    *,
    connector_id: str,
    display_name: str,
    base_url: str,
    health_path: str,
    auth_type: str,
    credential_ref: str,
    scope: dict[str, str],
    verification: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": connector_id,
        "name": display_name[:120],
        "connector_kind": "erp",
        "protocol": ERP_HTTP_JSON_PROTOCOL,
        "status": "live_verified",
        "verification_status": "live_verified",
        "verified_at": verification["verified_at"],
        "expires_at": verification["expires_at"],
        "remote_store_id": verification["remote_store_id"],
        "base_url": base_url,
        "health_path": health_path,
        "auth_type": auth_type,
        "credential_ref": credential_ref,
        "capabilities": ["health_read"],
        "scope": dict(scope),
    }


def _upsert_connector(root: Path, record: dict[str, Any]) -> None:
    with _LOCK:
        registry = _load_registry(root)
        connectors = registry["connectors"]
        existing = next(
            (item for item in connectors if _text(item.get("id")) == record["id"]), None
        )
        if existing is None:
            connectors.append(record)
        else:
            existing.clear()
            existing.update(record)
        registry["updated_at"] = _now_iso()
        _write_registry(root, registry)


def configure_erp_http_json_adapter(
    root: Path,
    project_id: str,
    store_binding_id: str,
    payload: dict[str, Any],
    *,
    actor: str = "owner",
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("ERP 连接配置必须是对象。")
    _project, _channel, _store, scope = _store_scope(root, project_id, store_binding_id)
    if payload.get("confirm_live_read_test") is not True:
        raise ValueError("请确认执行 ERP / 云端插件只读连接测试。")
    display_name = _text(payload.get("display_name"))
    if not display_name or len(display_name) > 120:
        raise ValueError("请填写 1-120 个字符的 ERP / 云端插件名称。")
    allow_loopback = _development_loopback_enabled()
    base_url, _hostname, _port = _validate_base_url(
        payload.get("base_url"), allow_loopback=allow_loopback
    )
    health_path = _validate_health_path(payload.get("health_path"))
    auth_type, header_name, auth_value = _auth_configuration(payload)
    verification = verify_erp_http_json_connection(
        base_url=base_url,
        health_path=health_path,
        auth_type=auth_type,
        auth_header_name=header_name,
        auth_value=auth_value,
        expected_scope=scope,
        allow_loopback=allow_loopback,
    )
    connector_id = erp_connector_id(project_id, store_binding_id, display_name)
    previous_record = next(
        (
            item
            for item in _load_registry(root)["connectors"]
            if _text(item.get("id")).lower() == connector_id
        ),
        None,
    )
    previous_credential_ref = (
        _text(previous_record.get("credential_ref")).lower()
        if isinstance(previous_record, dict)
        else ""
    )
    credential_ref = ""
    if auth_type != "none":
        credential_ref = erp_connector_credential_ref(connector_id)
        save_credential(
            root,
            credential_ref,
            json.dumps(
                {
                    "schema_version": 2,
                    "connector_id": connector_id,
                    "auth_type": auth_type,
                    "auth_header_name": header_name,
                    "auth_value": auth_value,
                    "project_id": scope["project_id"],
                    "store_binding_id": scope["store_binding_id"],
                    "platform": scope["platform"],
                    "country_site": scope["country_site"],
                    "store_model": scope["store_model"],
                    "ownership": scope["ownership"],
                    "remote_store_id": verification["remote_store_id"],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            metadata={
                "purpose": "store_erp_connector",
                "project_id": scope["project_id"],
                "store_binding_id": scope["store_binding_id"],
                "platform": scope["platform"],
                "country_site": scope["country_site"],
                "store_model": scope["store_model"],
                "ownership": scope["ownership"],
                "remote_store_id": verification["remote_store_id"],
                "provider_id": connector_id,
                "authorization_surface": ERP_HTTP_JSON_PROTOCOL,
                "verification_status": "live_verified",
                "verified_at": verification["verified_at"],
                "expires_at": verification["expires_at"],
                "label": display_name,
            },
        )
    record = _safe_connector_record(
        connector_id=connector_id,
        display_name=display_name,
        base_url=base_url,
        health_path=health_path,
        auth_type=auth_type,
        credential_ref=credential_ref,
        scope=scope,
        verification=verification,
    )
    _upsert_connector(root, record)
    configuration = save_store_connection_configuration(
        root,
        scope["project_id"],
        scope["store_binding_id"],
        {"erp_connector_id": connector_id},
        actor=actor,
    )
    if auth_type == "none" and previous_credential_ref:
        delete_credential(root, previous_credential_ref)
    return {
        "ok": True,
        "status": "connected_read_only",
        "connector": {
            "id": connector_id,
            "name": display_name,
            "protocol": ERP_HTTP_JSON_PROTOCOL,
            "verified_at": verification["verified_at"],
            "expires_at": verification["expires_at"],
            "remote_store_id": verification["remote_store_id"],
            "capabilities": ["health_read"],
        },
        "configuration": configuration.get("configuration", {}),
        "message": "ERP / 云端插件已通过在线只读验证，并绑定到当前店铺。",
    }


def _connector_for_store(
    root: Path, project_id: str, store_binding_id: str, connector_id: str
) -> tuple[dict[str, Any], dict[str, str]]:
    _project, _channel, _store, scope = _store_scope(root, project_id, store_binding_id)
    requested = _text(connector_id).lower()
    record = next(
        (
            item
            for item in _load_registry(root)["connectors"]
            if _text(item.get("id")).lower() == requested
        ),
        None,
    )
    if record is None:
        raise ValueError("当前店铺绑定的 ERP / 云端插件在本机不存在。")
    record_scope = record.get("scope") if isinstance(record.get("scope"), dict) else {}
    if any(_text(record_scope.get(key)).casefold() != value.casefold() for key, value in scope.items()):
        raise PermissionError("ERP / 云端插件不属于当前项目和店铺。")
    return record, scope


def _invalidate_connector_after_failed_retest(
    root: Path,
    record: dict[str, Any],
    scope: dict[str, str],
    *,
    actor: str,
) -> None:
    failed = dict(record)
    failed["status"] = "verification_failed"
    failed["verification_status"] = "verification_failed"
    failed["last_failure_at"] = _now_iso()
    failed["capabilities"] = []
    _upsert_connector(root, failed)
    try:
        save_store_connection_configuration(
            root,
            scope["project_id"],
            scope["store_binding_id"],
            {"erp_connector_id": ""},
            actor=actor,
        )
    except (OSError, TypeError, ValueError):
        pass


def _validate_encrypted_bundle_scope(
    bundle: dict[str, Any], connector_id: str, scope: dict[str, str]
) -> None:
    expected = {
        "connector_id": connector_id,
        "project_id": scope["project_id"],
        "store_binding_id": scope["store_binding_id"],
        "platform": scope["platform"],
        "country_site": scope["country_site"],
        "store_model": scope["store_model"],
        "ownership": scope["ownership"],
    }
    for key, expected_value in expected.items():
        actual = _text(bundle.get(key))
        if key == "country_site":
            actual = actual.upper()
        else:
            actual = actual.lower()
        if actual != expected_value:
            raise PermissionError("ERP / 云端插件加密凭据不属于当前项目和店铺。")


def retest_erp_http_json_adapter(
    root: Path,
    project_id: str,
    store_binding_id: str,
    *,
    actor: str = "owner",
) -> dict[str, Any]:
    _project, _channel, store, _scope = _store_scope(root, project_id, store_binding_id)
    connector_id = _text(store.get("erp_connector_id")).lower()
    if not connector_id:
        raise ValueError("当前店铺尚未绑定 ERP / 云端插件。")
    record, scope = _connector_for_store(root, project_id, store_binding_id, connector_id)
    auth_type = _text(record.get("auth_type") or "none").lower()
    header_name = ""
    auth_value = ""
    try:
        if auth_type != "none":
            raw_bundle = load_credential(
                root, _text(record.get("credential_ref")).lower()
            )
            try:
                bundle = json.loads(raw_bundle or "")
            except (TypeError, ValueError):
                bundle = {}
            if not isinstance(bundle, dict):
                raise ValueError("当前 ERP / 云端插件的本机加密凭据缺失。")
            _validate_encrypted_bundle_scope(bundle, connector_id, scope)
            header_name = _text(bundle.get("auth_header_name")).lower()
            auth_value = str(bundle.get("auth_value") or "").strip()
            if not auth_value:
                raise ValueError("当前 ERP / 云端插件的本机加密凭据缺失。")
        verification = verify_erp_http_json_connection(
            base_url=_text(record.get("base_url")),
            health_path=_text(record.get("health_path")) or "/health",
            auth_type=auth_type,
            auth_header_name=header_name,
            auth_value=auth_value,
            expected_scope=scope,
            allow_loopback=_development_loopback_enabled(),
        )
        if (
            _text(record.get("remote_store_id"))
            and _text(record.get("remote_store_id"))
            != verification["remote_store_id"]
        ):
            raise PermissionError("ERP / 云端插件远端店铺身份发生变化。")
    except (ConnectionError, OSError, TypeError, ValueError, PermissionError):
        _invalidate_connector_after_failed_retest(
            root, record, scope, actor=actor
        )
        raise
    refreshed = dict(record)
    refreshed["status"] = "live_verified"
    refreshed["verification_status"] = "live_verified"
    refreshed["verified_at"] = verification["verified_at"]
    refreshed["expires_at"] = verification["expires_at"]
    refreshed["remote_store_id"] = verification["remote_store_id"]
    refreshed.pop("last_failure_at", None)
    _upsert_connector(root, refreshed)
    save_store_connection_configuration(
        root,
        scope["project_id"],
        scope["store_binding_id"],
        {"erp_connector_id": connector_id},
        actor=actor,
    )
    return {
        "ok": True,
        "status": "connected_read_only",
        "connector": {
            "id": connector_id,
            "name": _text(record.get("name")),
            "protocol": ERP_HTTP_JSON_PROTOCOL,
            "verified_at": verification["verified_at"],
            "expires_at": verification["expires_at"],
            "remote_store_id": verification["remote_store_id"],
            "capabilities": ["health_read"],
        },
        "message": "ERP / 云端插件在线只读复测通过。",
    }


def verified_erp_connector_options(
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
    expected = {
        "project_id": _text(project_id).lower(),
        "store_binding_id": _text(store_binding_id).lower(),
        "platform": _text(platform).lower(),
        "country_site": _text(country_site).upper(),
        "store_model": _text(store_model).lower(),
        "ownership": _text(ownership).lower(),
    }
    rows: list[dict[str, Any]] = []
    for record in _load_registry(root)["connectors"]:
        scope = record.get("scope") if isinstance(record.get("scope"), dict) else {}
        if any(
            _text(scope.get(key)).casefold() != value.casefold()
            for key, value in expected.items()
            if value
        ):
            continue
        connector_id = _text(record.get("id")).lower()
        live = (
            _text(record.get("protocol")) == ERP_HTTP_JSON_PROTOCOL
            and _verification_is_fresh(record)
        )
        rows.append(
            {
                "id": connector_id,
                "label": _text(record.get("name")) or connector_id,
                "status": "live_verified" if live else "verification_required",
                "verification_status": _text(record.get("verification_status")).lower(),
                "verified_at": _text(record.get("verified_at")),
                "expires_at": _text(record.get("expires_at")),
                "protocol": ERP_HTTP_JSON_PROTOCOL,
                "available": live,
                "selected": connector_id == _text(current_connector_id).lower(),
                "source": "private_verified_registry",
            }
        )
    return rows


def erp_connector_metadata(root: Path, connector_id: str) -> dict[str, Any]:
    requested = _text(connector_id).lower()
    for record in _load_registry(root)["connectors"]:
        if _text(record.get("id")).lower() != requested:
            continue
        fresh = _verification_is_fresh(record)
        return {
            "id": requested,
            "name": _text(record.get("name")),
            "protocol": _text(record.get("protocol")),
            "status": _text(record.get("status")) if fresh else "verification_required",
            "verification_status": (
                _text(record.get("verification_status"))
                if fresh
                else "verification_required"
            ),
            "verified_at": _text(record.get("verified_at")),
            "expires_at": _text(record.get("expires_at")),
            "remote_store_id": _text(record.get("remote_store_id")),
            "capabilities": [
                item
                for item in record.get("capabilities", [])
                if item in ERP_ALLOWED_CAPABILITIES
            ] if fresh else [],
            "scope": dict(record.get("scope") or {}),
        }
    return {}


__all__ = [
    "ERP_HTTP_JSON_PROTOCOL",
    "configure_erp_http_json_adapter",
    "erp_connector_id",
    "erp_connector_metadata",
    "erp_connector_registry_path",
    "retest_erp_http_json_adapter",
    "verified_erp_connector_options",
    "verify_erp_http_json_connection",
]
