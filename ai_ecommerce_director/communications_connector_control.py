from __future__ import annotations

import json
import base64
import hashlib
import imaplib
import ipaddress
import os
import re
import socket
import ssl
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from .credential_store import delete_credential, load_credential, save_credential


CONFIG_RELATIVE_PATH = Path("config") / "communications_connector_control.json"
STATE_RELATIVE_PATH = Path("data") / "communications_connector_runtime.json"
MAX_AUDITS = 200
MAX_REVIEWS = 200
MAX_DIAGNOSTICS = 200
MAX_MESSAGE_IMPORTS = 500
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
PURPOSE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
GRAPH_VERSION = re.compile(r"^v[0-9]{1,2}\.[0-9]$")
HOSTNAME = re.compile(
    r"^(?=.{1,253}$)(?!-)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)
SUPPORTED_LIVE_VERIFY_CONNECTORS = {
    "email_imap",
    "feishu",
    "gmail",
    "outlook",
    "telegram",
    "wechat_official",
    "wechat_official_account",
    "whatsapp_business",
    "youtube",
}
CONNECTOR_SETUP_PLAYBOOKS = {
    "gmail": {
        "identity_check": "只读取 Google 账号的邮箱地址元数据",
        "required_inputs": ["Google 官方 OAuth 授权"],
        "verified_capabilities": ["账号身份元数据"],
        "next_step": "在设置中发起 Google OAuth，并只批准读取账号身份所需的最小权限。",
    },
    "youtube": {
        "identity_check": "只读取 Google OAuth 已授权的 YouTube 频道身份元数据",
        "required_inputs": ["Google 官方 OAuth 授权（YouTube 只读权限）"],
        "verified_capabilities": ["频道身份元数据"],
        "next_step": "由负责人完成 Google 官方 OAuth，只批准 YouTube 只读权限；不会读取视频、评论或消息。",
    },
    "outlook": {
        "identity_check": "只读取 Microsoft Graph /me 的账号身份元数据",
        "required_inputs": ["Microsoft 官方 OAuth 授权"],
        "verified_capabilities": ["账号身份元数据"],
        "next_step": "在设置中发起 Microsoft OAuth，并只批准读取账号身份所需的最小权限。",
    },
    "email_imap": {
        "identity_check": "只执行 TLS 登录和 NOOP，不打开任何邮件",
        "required_inputs": ["公网 IMAP 主机", "TLS 端口", "邮箱用户名", "应用密码或 OAuth Token"],
        "verified_capabilities": ["IMAP 身份验证"],
        "next_step": "向邮箱管理员确认公网 IMAP、TLS 端口和专用应用密码；不要使用个人主密码。",
    },
    "feishu": {
        "identity_check": "只验证飞书应用能否取得 tenant token",
        "required_inputs": ["飞书 App ID", "飞书 App Secret"],
        "verified_capabilities": ["应用身份授权"],
        "next_step": "由飞书管理员创建企业自建应用并确认最小权限后，再在设置中连接。",
    },
    "wechat_official": {
        "identity_check": "只验证企业微信应用能否取得 corp token",
        "required_inputs": ["企业微信 Corp ID", "企业微信应用 Secret"],
        "verified_capabilities": ["企业应用身份授权"],
        "next_step": "由企业微信管理员确认企业和应用身份后，再在设置中连接。",
    },
    "wechat_official_account": {
        "identity_check": "只验证微信公众号应用能否取得 app token",
        "required_inputs": ["微信公众号 App ID", "微信公众号 App Secret"],
        "verified_capabilities": ["公众号应用身份授权"],
        "next_step": "由公众号管理员确认主体和应用身份后，再在设置中连接。",
    },
    "telegram": {
        "identity_check": "只调用 Telegram Bot API getMe 读取机器人身份元数据",
        "required_inputs": ["Telegram Bot Token"],
        "verified_capabilities": ["机器人身份元数据"],
        "next_step": "由负责人从 BotFather 获取专用 Bot Token，再在设置中验证；不会读取聊天或发送消息。",
    },
    "whatsapp_business": {
        "identity_check": "只读取 WhatsApp Business 电话号码身份元数据",
        "required_inputs": ["电话号码 ID", "明确的 Graph API 版本", "Meta Access Token"],
        "verified_capabilities": ["电话号码身份元数据"],
        "next_step": "由 Meta Business 管理员确认 WABA、电话号码和最小权限后，再在设置中连接。",
    },
}
SECRET_OR_PRIVATE_KEYS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "api_key",
    "password",
    "cookie",
    "session_cookie",
    "authorization",
    "bot_token",
    "webhook_secret",
    "message_body",
    "message_text",
    "recipient_email",
    "recipient_phone",
    "phone_number",
    "contact_list",
    "private_message",
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
    if not isinstance(payload.get("connectors"), list):
        raise ValueError("Communications connector config is missing connectors.")
    return payload


def _state(root: Path) -> dict[str, Any]:
    payload = _read_json(
        root / STATE_RELATIVE_PATH,
        {
            "schema_version": 2,
            "audits": [],
            "reviews": [],
            "connections": [],
            "diagnostics": [],
            "message_imports": [],
        },
    )
    for key in ("audits", "reviews", "connections", "diagnostics", "message_imports"):
        if not isinstance(payload.get(key), list):
            payload[key] = []
    payload["schema_version"] = 2
    return payload


def _save_state(root: Path, state: dict[str, Any]) -> None:
    path = root / STATE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    state["audits"] = list(state.get("audits") or [])[-MAX_AUDITS:]
    state["reviews"] = list(state.get("reviews") or [])[-MAX_REVIEWS:]
    state["diagnostics"] = list(state.get("diagnostics") or [])[-MAX_DIAGNOSTICS:]
    state["message_imports"] = list(state.get("message_imports") or [])[-MAX_MESSAGE_IMPORTS:]
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _find_sensitive_field(value: Any, path: str = "request") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().casefold()
            if normalized in SECRET_OR_PRIVATE_KEYS or normalized.endswith("_secret"):
                return f"{path}.{key}"
            found = _find_sensitive_field(child, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_sensitive_field(child, f"{path}[{index}]")
            if found:
                return found
    return None


def _clean_identifier(value: Any, label: str, *, required: bool = False) -> str:
    text = str(value or "").strip()
    if not text and not required:
        return ""
    if not IDENTIFIER.fullmatch(text):
        raise ValueError(f"{label} must be a stable identifier, not raw contact data.")
    return text


def _connector_snapshot(
    item: dict[str, Any], connections: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    bindings = [
        dict(binding)
        for binding in connections or []
        if str(binding.get("connector_id") or "") == str(item.get("id") or "")
    ]
    verified = [binding for binding in bindings if binding.get("status") == "verified"]
    configured = bool(bindings)
    status = (
        "verified"
        if verified
        else "verification_failed"
        if configured
        else str(item.get("status") or "not_configured")
    )
    return {
        "id": str(item.get("id") or ""),
        "group": str(item.get("group") or "communications"),
        "name": str(item.get("name") or item.get("id") or "Connector"),
        "protocol": str(item.get("protocol") or "unknown"),
        "status": status,
        "capabilities": [str(value) for value in item.get("capabilities") or []],
        "required_authorization": [
            str(value) for value in item.get("required_authorization") or []
        ],
        "supported": status != "unsupported_private_client",
        "credential_ref_configured": configured,
        "account_identity_verified": bool(verified),
        "approved_scope_count": max(
            [int(binding.get("approved_scope_count") or 0) for binding in verified] or [0]
        ),
        "webhook_verified": False,
        "inbox_read_verified": False,
        "contact_sync_verified": False,
        "send_receipt_count": 0,
        "publish_receipt_count": 0,
        "raw_credential_value_exposed": False,
        "private_message_value_exposed": False,
        "live_verification_supported": str(item.get("id") or "")
        in SUPPORTED_LIVE_VERIFY_CONNECTORS,
        "verified_binding_count": len(verified),
        "configured_binding_count": len(bindings),
        "bindings": bindings,
    }


def communications_connector_snapshot(root: Path) -> dict[str, Any]:
    config = _config(root)
    state = _state(root)
    connections = [
        item for item in state.get("connections") or [] if isinstance(item, dict)
    ]
    message_imports = [
        item for item in state.get("message_imports") or [] if isinstance(item, dict)
    ]
    connectors = [
        _connector_snapshot(item, connections)
        for item in config.get("connectors") or []
        if isinstance(item, dict)
    ]
    return {
        "schema_version": 1,
        "scope": config.get("scope"),
        "connectors": connectors,
        "required_route": list(config.get("required_route") or []),
        "local_actions": list(config.get("local_actions") or []),
        "blocked_actions": list(config.get("blocked_actions") or []),
        "hard_boundaries": list(config.get("hard_boundaries") or []),
        "plugin_observations": config.get("current_session_plugin_observations") or {},
        "connector_contract_count": len(connectors),
        "verified_connection_count": sum(
            1 for item in connections if item.get("status") == "verified"
        ),
        "configured_connection_count": len(connections),
        "unsupported_connector_count": sum(
            1 for item in connectors if not item["supported"]
        ),
        "inbox_read_count": 0,
        "local_message_file_read_count": len(message_imports),
        "recent_local_message_imports": message_imports[-20:][::-1],
        "contact_sync_count": 0,
        "webhook_subscription_count": 0,
        "message_send_count": 0,
        "social_publish_count": 0,
        "external_action_count": 0,
        "audits": list(state.get("audits") or [])[-20:][::-1],
        "reviews": list(state.get("reviews") or [])[-20:][::-1],
        "diagnostics": list(state.get("diagnostics") or [])[-20:][::-1],
    }


def import_communications_message_file(
    root: Path,
    payload: dict[str, Any],
    *,
    actor: str = "desktop-owner",
) -> dict[str, Any]:
    """Read one owner-supplied EML file and persist privacy-minimized metadata.

    This is a local file read, not an inbox connection. Raw headers, subject,
    addresses, body, and attachments are never persisted.
    """

    route = _connection_route(root, payload)
    filename = Path(str(payload.get("filename") or "message.eml")).name
    if Path(filename).suffix.casefold() != ".eml":
        raise ValueError("本地通信文件仅支持 EML。")
    encoded = str(payload.get("content_base64") or "").strip()
    if encoded.startswith("data:") and "," in encoded:
        encoded = encoded.split(",", 1)[1]
    try:
        content = base64.b64decode(encoded, validate=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("EML 文件不是有效的 Base64 数据。") from exc
    if not content:
        raise ValueError("EML 文件为空。")
    if len(content) > 5 * 1024 * 1024:
        raise ValueError("EML 文件超过 5 MB 上限。")
    try:
        message = BytesParser(policy=policy.default).parsebytes(content)
    except (TypeError, ValueError) as exc:
        raise ValueError("EML 文件无法解析。") from exc

    sender_addresses = getaddresses(message.get_all("from", []))
    sender_address = sender_addresses[0][1] if sender_addresses else ""
    sender_domain = sender_address.rsplit("@", 1)[1].casefold() if "@" in sender_address else "unknown"
    recipient_count = len(getaddresses(message.get_all("to", []) + message.get_all("cc", [])))
    subject = str(message.get("subject") or "")
    raw_message_id = str(message.get("message-id") or "")
    content_sha256 = hashlib.sha256(content).hexdigest().upper()
    route_bytes = json.dumps(route, ensure_ascii=False, sort_keys=True).encode("utf-8")
    import_id = "communications-file-" + hashlib.sha256(content + b"\0" + route_bytes).hexdigest()[:20]
    attachment_count = sum(
        1
        for part in message.walk()
        if part.get_content_disposition() == "attachment"
    )
    state = _state(root)
    for item in state.get("message_imports") or []:
        if isinstance(item, dict) and item.get("import_id") == import_id:
            return {
                "ok": True,
                "status": "already_imported_local_message_metadata",
                "message": dict(item),
                "connected": False,
                "external_action_count": 0,
            }
    record = {
        "import_id": import_id,
        "imported_at": _now(),
        "actor": _clean_identifier(actor, "actor", required=True),
        "source": "owner_supplied_local_eml",
        "route": route,
        "file": {"extension": ".eml", "size_bytes": len(content), "sha256": content_sha256},
        "message": {
            "message_id_hash": _stable_hash(raw_message_id or content_sha256),
            "sent_at": str(message.get("date") or "")[:120],
            "sender_domain": sender_domain[:160],
            "recipient_count": recipient_count,
            "subject_hash": _stable_hash(subject),
            "subject_length": len(subject),
            "content_type": str(message.get_content_type() or "unknown")[:80],
            "attachment_count": attachment_count,
        },
        "connected": False,
        "inbox_read_verified": False,
        "raw_message_persisted": False,
        "external_action_count": 0,
    }
    state.setdefault("message_imports", []).append(record)
    _save_state(root, state)
    return {
        "ok": True,
        "status": "imported_local_message_metadata",
        "message": record,
        "connected": False,
        "external_action_count": 0,
    }


def _base_result(status: str, *, allowed: bool, missing: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "missing": list(missing or []),
        "local_action_allowed": allowed,
        "account_authorized": False,
        "inbox_read": False,
        "contacts_synced": False,
        "webhook_subscribed": False,
        "message_sent": False,
        "social_content_published": False,
        "external_action_count": 0,
    }


class CommunicationsVerificationError(RuntimeError):
    def __init__(self, code: str, message: str, *, http_status: int = 0) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = int(http_status or 0)


def _stable_hash(value: str, length: int = 32) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _mask_identity(value: Any) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return "verified-account"
    if "@" in text:
        local, domain = text.rsplit("@", 1)
        lead = local[:1] if local else "*"
        return f"{lead}***@{domain[:80]}"[:120]
    if len(text) <= 6:
        return text[:1] + "***"
    return f"{text[:3]}***{text[-3:]}"[:120]


def _safe_error(message: Any, secrets: list[str] | None = None) -> str:
    text = " ".join(str(message or "Connection verification failed.").split())
    for secret in secrets or []:
        value = str(secret or "").strip()
        if value:
            text = text.replace(value, "[redacted]")
    return text[:300]


def _connection_route(root: Path, payload: dict[str, Any]) -> dict[str, str]:
    scope_kind = str(payload.get("scope_kind") or "project_task").strip().casefold()
    if scope_kind not in {"project_task", "store"}:
        raise ValueError("scope_kind must be project_task or store.")
    required = list(_config(root).get("required_route") or [])
    if scope_kind == "store":
        required.append("store_binding_id")
    missing = [field for field in required if not str(payload.get(field) or "").strip()]
    if missing:
        raise ValueError("Missing exact connector route: " + ", ".join(missing))
    route = {
        field: _clean_identifier(payload.get(field), field, required=True)
        for field in required
    }
    route["scope_kind"] = scope_kind
    return route


def _http_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 12.0,
) -> tuple[int, dict[str, Any]]:
    body = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json; charset=utf-8")
    request = Request(url, data=body, headers=request_headers, method=method.upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise CommunicationsVerificationError(
                    "response_too_large", "Connector response exceeded the safety limit."
                )
            try:
                decoded = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeError, ValueError) as exc:
                raise CommunicationsVerificationError(
                    "invalid_json", "Connector returned a non-JSON response."
                ) from exc
            if not isinstance(decoded, dict):
                raise CommunicationsVerificationError(
                    "invalid_response", "Connector returned an unexpected response shape."
                )
            return int(getattr(response, "status", 200) or 200), decoded
    except HTTPError as exc:
        code = "authorization_failed" if exc.code in {401, 403} else "http_error"
        raise CommunicationsVerificationError(
            code,
            f"Connector returned HTTP {exc.code}.",
            http_status=exc.code,
        ) from exc
    except URLError as exc:
        raise CommunicationsVerificationError(
            "network_error", "Connector endpoint could not be reached."
        ) from exc
    except TimeoutError as exc:
        raise CommunicationsVerificationError(
            "timeout", "Connector verification timed out."
        ) from exc


def _required_text(credentials: dict[str, Any], key: str, label: str) -> str:
    value = str(credentials.get(key) or "").strip()
    if not value:
        raise ValueError(f"{label} is required.")
    if len(value) > 8192:
        raise ValueError(f"{label} is too long.")
    return value


def _verify_imap(credentials: dict[str, Any]) -> dict[str, Any]:
    host = _required_text(credentials, "host", "IMAP host").casefold()
    username = _required_text(credentials, "username", "Mailbox username")
    password = _required_text(credentials, "password", "Mailbox app password")
    if not HOSTNAME.fullmatch(host) or host in {"localhost", "localhost.localdomain"}:
        raise ValueError("IMAP host must be a valid public hostname.")
    try:
        port = int(credentials.get("port") or 993)
    except (TypeError, ValueError) as exc:
        raise ValueError("IMAP port must be numeric.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("IMAP port is outside the valid range.")
    if os.getenv("TEELAB_ALLOW_PRIVATE_COMM_ENDPOINTS") != "1":
        try:
            addresses = {
                item[4][0]
                for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            }
        except OSError as exc:
            raise CommunicationsVerificationError(
                "dns_error", "IMAP hostname could not be resolved."
            ) from exc
        for address in addresses:
            parsed = ipaddress.ip_address(address)
            if (
                parsed.is_private
                or parsed.is_loopback
                or parsed.is_link_local
                or parsed.is_reserved
                or parsed.is_unspecified
                or parsed.is_multicast
            ):
                raise ValueError("Private or local IMAP endpoints are blocked by default.")
    client: imaplib.IMAP4_SSL | None = None
    try:
        client = imaplib.IMAP4_SSL(
            host,
            port,
            ssl_context=ssl.create_default_context(),
            timeout=12,
        )
        client.login(username, password)
        status, _ = client.noop()
        if str(status).upper() != "OK":
            raise CommunicationsVerificationError(
                "protocol_error", "IMAP server did not accept a NOOP diagnostic."
            )
    except imaplib.IMAP4.error as exc:
        raise CommunicationsVerificationError(
            "authorization_failed", "IMAP authentication failed."
        ) from exc
    except (OSError, ssl.SSLError) as exc:
        raise CommunicationsVerificationError(
            "network_error", "IMAP TLS connection failed."
        ) from exc
    finally:
        if client is not None:
            try:
                client.logout()
            except (imaplib.IMAP4.error, OSError):
                pass
    return {
        "account_label": _mask_identity(username),
        "account_identity_hash": _stable_hash(f"imap:{host}:{username.casefold()}"),
        "approved_scope_count": 1,
        "verified_capabilities": ["imap_authentication"],
        "endpoint_label": host,
    }


def _verify_connector_credentials(
    connector_id: str, credentials: dict[str, Any]
) -> dict[str, Any]:
    if connector_id == "email_imap":
        return _verify_imap(credentials)
    if connector_id == "gmail":
        token = _required_text(credentials, "access_token", "Google OAuth access token")
        _, response = _http_json(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        identity = _required_text(response, "emailAddress", "Gmail account identity")
        return {
            "account_label": _mask_identity(identity),
            "account_identity_hash": _stable_hash(f"gmail:{identity.casefold()}"),
            "approved_scope_count": 1,
            "verified_capabilities": ["profile_metadata"],
            "endpoint_label": "gmail.googleapis.com",
        }
    if connector_id == "youtube":
        token = _required_text(credentials, "access_token", "Google OAuth access token")
        _, response = _http_json(
            "https://www.googleapis.com/youtube/v3/channels?"
            + urlencode({"part": "id,snippet", "mine": "true", "maxResults": "1"}),
            headers={"Authorization": f"Bearer {token}"},
        )
        items = response.get("items")
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            raise CommunicationsVerificationError(
                "invalid_identity",
                "Google OAuth token did not return an authorized YouTube channel identity.",
            )
        channel = items[0]
        channel_id = _required_text(channel, "id", "YouTube channel identity")
        snippet = channel.get("snippet")
        if not isinstance(snippet, dict):
            snippet = {}
        label = snippet.get("title") or channel_id
        return {
            "account_label": _mask_identity(label),
            "account_identity_hash": _stable_hash(f"youtube:{channel_id}"),
            "approved_scope_count": 1,
            "verified_capabilities": ["channel_identity_metadata"],
            "endpoint_label": "youtube.googleapis.com",
        }
    if connector_id == "outlook":
        token = _required_text(credentials, "access_token", "Microsoft Graph access token")
        _, response = _http_json(
            "https://graph.microsoft.com/v1.0/me?$select=id,mail,userPrincipalName",
            headers={"Authorization": f"Bearer {token}"},
        )
        object_id = _required_text(response, "id", "Microsoft account identity")
        label = response.get("mail") or response.get("userPrincipalName") or object_id
        return {
            "account_label": _mask_identity(label),
            "account_identity_hash": _stable_hash(f"outlook:{object_id}"),
            "approved_scope_count": 1,
            "verified_capabilities": ["profile_metadata"],
            "endpoint_label": "graph.microsoft.com",
        }
    if connector_id == "feishu":
        app_id = _required_text(credentials, "app_id", "Feishu App ID")
        app_secret = _required_text(credentials, "app_secret", "Feishu App Secret")
        _, response = _http_json(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            method="POST",
            payload={"app_id": app_id, "app_secret": app_secret},
        )
        if int(response.get("code") or 0) != 0 or not response.get("tenant_access_token"):
            raise CommunicationsVerificationError(
                "authorization_failed",
                f"Feishu rejected the app credentials (code {response.get('code', 'unknown')}).",
            )
        return {
            "account_label": _mask_identity(app_id),
            "account_identity_hash": _stable_hash(f"feishu:{app_id}"),
            "approved_scope_count": 0,
            "verified_capabilities": ["tenant_token_grant"],
            "endpoint_label": "open.feishu.cn",
            "token_ttl_seconds": int(response.get("expire") or 0),
        }
    if connector_id == "wechat_official":
        corp_id = _required_text(credentials, "corp_id", "WeCom Corp ID")
        corp_secret = _required_text(credentials, "corp_secret", "WeCom Corp Secret")
        _, response = _http_json(
            "https://qyapi.weixin.qq.com/cgi-bin/gettoken?"
            + urlencode({"corpid": corp_id, "corpsecret": corp_secret})
        )
        if int(response.get("errcode") or 0) != 0 or not response.get("access_token"):
            raise CommunicationsVerificationError(
                "authorization_failed",
                f"WeCom rejected the app credentials (errcode {response.get('errcode', 'unknown')}).",
            )
        return {
            "account_label": _mask_identity(corp_id),
            "account_identity_hash": _stable_hash(f"wecom:{corp_id}"),
            "approved_scope_count": 0,
            "verified_capabilities": ["corp_token_grant"],
            "endpoint_label": "qyapi.weixin.qq.com",
            "token_ttl_seconds": int(response.get("expires_in") or 0),
        }
    if connector_id == "wechat_official_account":
        app_id = _required_text(credentials, "app_id", "Official Account App ID")
        app_secret = _required_text(credentials, "app_secret", "Official Account App Secret")
        _, response = _http_json(
            "https://api.weixin.qq.com/cgi-bin/token?"
            + urlencode(
                {"grant_type": "client_credential", "appid": app_id, "secret": app_secret}
            )
        )
        if response.get("errcode") or not response.get("access_token"):
            raise CommunicationsVerificationError(
                "authorization_failed",
                f"Official Account rejected the app credentials (errcode {response.get('errcode', 'unknown')}).",
            )
        return {
            "account_label": _mask_identity(app_id),
            "account_identity_hash": _stable_hash(f"wechat-mp:{app_id}"),
            "approved_scope_count": 0,
            "verified_capabilities": ["app_token_grant"],
            "endpoint_label": "api.weixin.qq.com",
            "token_ttl_seconds": int(response.get("expires_in") or 0),
        }
    if connector_id == "telegram":
        bot_token = _required_text(credentials, "bot_token", "Telegram Bot Token")
        _, response = _http_json(
            f"https://api.telegram.org/bot{bot_token}/getMe"
        )
        bot = response.get("result")
        if response.get("ok") is not True or not isinstance(bot, dict):
            raise CommunicationsVerificationError(
                "authorization_failed", "Telegram rejected the bot credentials."
            )
        bot_id = _required_text(bot, "id", "Telegram bot identity")
        if bot.get("is_bot") is not True:
            raise CommunicationsVerificationError(
                "invalid_identity", "Telegram returned a non-bot identity."
            )
        label = bot.get("username") or bot.get("first_name") or bot_id
        return {
            "account_label": "Telegram Bot · " + _mask_identity(label),
            "account_identity_hash": _stable_hash(f"telegram:{bot_id}"),
            "approved_scope_count": 0,
            "verified_capabilities": ["bot_identity_metadata"],
            "endpoint_label": "api.telegram.org",
        }
    if connector_id == "whatsapp_business":
        token = _required_text(credentials, "access_token", "WhatsApp access token")
        phone_number_id = _required_text(
            credentials, "phone_number_id", "WhatsApp phone number ID"
        )
        version = str(credentials.get("graph_api_version") or "").strip()
        if not GRAPH_VERSION.fullmatch(version):
            raise ValueError("Meta Graph API version must be explicit, for example v24.0.")
        _, response = _http_json(
            f"https://graph.facebook.com/{version}/{phone_number_id}"
            "?fields=id,display_phone_number,verified_name,quality_rating",
            headers={"Authorization": f"Bearer {token}"},
        )
        remote_id = _required_text(response, "id", "WhatsApp phone identity")
        label = response.get("display_phone_number") or remote_id
        return {
            "account_label": "WhatsApp · " + _mask_identity(label),
            "account_identity_hash": _stable_hash(f"whatsapp:{remote_id}"),
            "approved_scope_count": 1,
            "verified_capabilities": ["phone_number_metadata"],
            "endpoint_label": f"graph.facebook.com/{version}",
            "quality_rating": str(response.get("quality_rating") or "unknown")[:40],
        }
    raise ValueError("This connector does not yet support a live read-only verification.")


def _connector_by_id(root: Path, connector_id: str) -> dict[str, Any]:
    normalized = str(connector_id or "").strip().casefold()
    connector = next(
        (
            item
            for item in _config(root).get("connectors") or []
            if isinstance(item, dict) and str(item.get("id") or "") == normalized
        ),
        None,
    )
    if not connector:
        raise ValueError("Select a connector defined in the reviewed local registry.")
    if str(connector.get("status") or "") == "unsupported_private_client":
        raise ValueError("Personal/private-client automation is not supported.")
    if normalized not in SUPPORTED_LIVE_VERIFY_CONNECTORS:
        raise ValueError("This connector currently has a contract only, not a live verifier.")
    return connector


def _verify_and_store_connection(
    root: Path,
    *,
    connector_id: str,
    route: dict[str, str],
    credentials: dict[str, Any],
    actor: str,
    binding_id: str = "",
    credential_ref: str = "",
) -> dict[str, Any]:
    _connector_by_id(root, connector_id)
    if not isinstance(credentials, dict):
        raise ValueError("Connector credentials must be an object.")
    canonical_route = json.dumps(route, ensure_ascii=True, sort_keys=True)
    resolved_binding_id = binding_id or (
        "communications-binding-"
        + _stable_hash(f"{connector_id}:{canonical_route}", 20)
    )
    resolved_credential_ref = credential_ref or (
        "communications:"
        + connector_id
        + ":"
        + _stable_hash(f"{connector_id}:{canonical_route}", 24)
    )
    secret_bundle = json.dumps(credentials, ensure_ascii=False, separators=(",", ":"))
    save_credential(
        root,
        resolved_credential_ref,
        secret_bundle,
        metadata={
            "purpose": "communications_connector",
            "project_id": route.get("project_id", ""),
            "store_binding_id": route.get("store_binding_id", ""),
            "platform": connector_id,
            "label": route.get("connector_account_ref", ""),
            "provider_id": connector_id,
            "authorization_surface": "read_only_connection_verification",
            "verification_status": "pending",
        },
    )
    checked_at = _now()
    diagnostic: dict[str, Any] = {
        "id": f"communications-diagnostic-{uuid4().hex[:16]}",
        "binding_id": resolved_binding_id,
        "connector_id": connector_id,
        "checked_at": checked_at,
        "actor": str(actor or "owner")[:120],
        "external_action_count": 0,
        "inbox_read": False,
        "contacts_synced": False,
        "webhook_subscribed": False,
        "message_sent": False,
        "content_published": False,
    }
    try:
        verified = _verify_connector_credentials(connector_id, credentials)
        diagnostic.update({"status": "verified", "error_code": "", "http_status": 200})
        connection_status = "verified"
        last_error = ""
    except (CommunicationsVerificationError, OSError, TypeError, ValueError) as exc:
        verified = {}
        diagnostic.update(
            {
                "status": "verification_failed",
                "error_code": getattr(exc, "code", "invalid_configuration"),
                "http_status": int(getattr(exc, "http_status", 0) or 0),
                "error": _safe_error(str(exc), list(credentials.values())),
            }
        )
        connection_status = "verification_failed"
        last_error = str(diagnostic["error"])
    connection = {
        "binding_id": resolved_binding_id,
        "connector_id": connector_id,
        "credential_ref": resolved_credential_ref,
        "route": route,
        "status": connection_status,
        "configured_at": checked_at,
        "last_checked_at": checked_at,
        "verified_at": checked_at if connection_status == "verified" else "",
        "account_label": str(verified.get("account_label") or "")[:120],
        "account_identity_hash": str(verified.get("account_identity_hash") or "")[:80],
        "endpoint_label": str(verified.get("endpoint_label") or "")[:160],
        "approved_scope_count": int(verified.get("approved_scope_count") or 0),
        "verified_capabilities": [
            str(item)[:80] for item in verified.get("verified_capabilities") or []
        ],
        "token_ttl_seconds": int(verified.get("token_ttl_seconds") or 0),
        "quality_rating": str(verified.get("quality_rating") or "")[:40],
        "last_error": last_error,
        "raw_credential_value_exposed": False,
        "private_message_value_exposed": False,
    }
    state = _state(root)
    state["connections"] = [
        item
        for item in state.get("connections") or []
        if isinstance(item, dict) and item.get("binding_id") != resolved_binding_id
    ]
    state["connections"].append(connection)
    state["diagnostics"].append(diagnostic)
    _save_state(root, state)
    return {
        "ok": connection_status == "verified",
        "status": connection_status,
        "connection": connection,
        "diagnostic": diagnostic,
    }


def verify_communications_connector(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Connector verification payload must be an object.")
    connector_id = str(payload.get("connector_id") or "").strip().casefold()
    _connector_by_id(root, connector_id)
    route = _connection_route(root, payload)
    credentials = payload.get("credentials")
    return _verify_and_store_connection(
        root,
        connector_id=connector_id,
        route=route,
        credentials=credentials if isinstance(credentials, dict) else {},
        actor=actor,
    )


def simulate_communications_connector_setup(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    """Run a credential-free setup rehearsal without claiming a real connection."""
    if not isinstance(payload, dict):
        raise ValueError("连接演练请求必须是对象。")
    sensitive = _find_sensitive_field(payload)
    if sensitive:
        raise ValueError("本地演练不接收 Token、密码、联系人或消息正文。")
    connector_id = str(payload.get("connector_id") or "").strip().casefold()
    connector = _connector_by_id(root, connector_id)
    playbook = CONNECTOR_SETUP_PLAYBOOKS.get(connector_id)
    if not playbook:
        raise ValueError("这个账号类型还没有可执行的本地连接演练。")
    diagnostic = {
        "id": f"communications-simulation-{uuid4().hex[:16]}",
        "connector_id": connector_id,
        "connector_name": str(connector.get("name") or connector_id),
        "protocol": str(connector.get("protocol") or "unknown"),
        "checked_at": _now(),
        "actor": str(actor or "owner")[:120],
        "status": "local_setup_simulation_ready",
        "connection_state": "not_configured",
        "identity_check": str(playbook["identity_check"]),
        "required_inputs": list(playbook["required_inputs"]),
        "verified_capabilities_when_authorized": list(
            playbook["verified_capabilities"]
        ),
        "next_step": str(playbook["next_step"]),
        "credential_saved": False,
        "account_authorized": False,
        "inbox_read": False,
        "contacts_synced": False,
        "message_sent": False,
        "social_content_published": False,
        "external_action_count": 0,
    }
    state = _state(root)
    state["diagnostics"].append(diagnostic)
    _save_state(root, state)
    return {
        "ok": True,
        "status": "local_setup_simulation_ready",
        "simulation": diagnostic,
        "connected": False,
        "external_action_count": 0,
    }


def retest_communications_connector(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    binding_id = _clean_identifier(payload.get("binding_id"), "binding_id", required=True)
    state = _state(root)
    connection = next(
        (
            item
            for item in state.get("connections") or []
            if isinstance(item, dict) and item.get("binding_id") == binding_id
        ),
        None,
    )
    if not connection:
        raise ValueError("Communications connector binding not found.")
    credential_ref = str(connection.get("credential_ref") or "")
    secret_bundle = load_credential(root, credential_ref)
    if not secret_bundle:
        raise ValueError("Encrypted credential is unavailable; configure the connector again.")
    try:
        credentials = json.loads(secret_bundle)
    except ValueError as exc:
        raise ValueError("Encrypted connector credential has an invalid format.") from exc
    if not isinstance(credentials, dict):
        raise ValueError("Encrypted connector credential has an invalid shape.")
    return _verify_and_store_connection(
        root,
        connector_id=str(connection.get("connector_id") or ""),
        route=dict(connection.get("route") or {}),
        credentials=credentials,
        actor=actor,
        binding_id=binding_id,
        credential_ref=credential_ref,
    )


def remove_communications_connector(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    binding_id = _clean_identifier(payload.get("binding_id"), "binding_id", required=True)
    state = _state(root)
    connection = next(
        (
            item
            for item in state.get("connections") or []
            if isinstance(item, dict) and item.get("binding_id") == binding_id
        ),
        None,
    )
    if not connection:
        raise ValueError("Communications connector binding not found.")
    credential_deleted = delete_credential(root, str(connection.get("credential_ref") or ""))
    state["connections"] = [
        item
        for item in state.get("connections") or []
        if isinstance(item, dict) and item.get("binding_id") != binding_id
    ]
    state["diagnostics"].append(
        {
            "id": f"communications-diagnostic-{uuid4().hex[:16]}",
            "binding_id": binding_id,
            "connector_id": str(connection.get("connector_id") or ""),
            "checked_at": _now(),
            "actor": str(actor or "owner")[:120],
            "status": "removed_local_binding",
            "credential_deleted": bool(credential_deleted),
            "external_action_count": 0,
        }
    )
    _save_state(root, state)
    return {
        "ok": True,
        "status": "removed_local_binding",
        "binding_id": binding_id,
        "credential_deleted": bool(credential_deleted),
        "external_action_count": 0,
    }


def evaluate_communications_connector_request(
    root: Path, request: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ValueError("Communications connector request must be an object.")
    sensitive = _find_sensitive_field(request)
    if sensitive:
        result = _base_result("blocked_sensitive_input", allowed=False)
        result["error"] = (
            "Raw credentials, contact PII and private message content are not accepted by this local control plane."
        )
        return result
    snapshot = communications_connector_snapshot(root)
    connector_id = str(request.get("connector_id") or "").strip().casefold()
    action = str(request.get("action") or "inspect_connector").strip().casefold()
    connector = next(
        (item for item in snapshot["connectors"] if item.get("id") == connector_id),
        None,
    )
    if not connector:
        result = _base_result(
            "blocked_unknown_connector", allowed=False, missing=["supported_connector"]
        )
        result["error"] = "Select a connector defined in the reviewed local registry."
        return result
    if not connector["supported"]:
        result = _base_result(
            "blocked_unsupported_private_client",
            allowed=False,
            missing=["official_business_connector"],
        )
        result["connector"] = connector
        result["error"] = (
            "Personal WeChat private-message injection and unofficial automation are not supported; use an approved official business connector."
        )
        return result
    if action == "inspect_connector":
        is_verified = bool(connector.get("account_identity_verified"))
        result = _base_result(
            "connector_connection_verified"
            if is_verified
            else "connector_contract_review_ready",
            allowed=True,
        )
        result["connector"] = connector
        result["account_authorized"] = is_verified
        result["missing"] = (
            []
            if is_verified
            else [
                "verified_connector_account",
                "credential_reference",
                "approved_scopes",
                "connection_diagnostic_receipt",
            ]
        )
        return result
    if action in set(snapshot["blocked_actions"]):
        missing = ["explicit_owner_action", "verified_connector_binding"]
        if action in {"send_message", "reply_message"}:
            missing.extend(["recipient_consent_or_valid_service_window", "approved_message"])
        if action in {"publish_content", "post_comment"}:
            missing.extend(["verified_publish_scope", "publish_approval"])
        result = _base_result("blocked_external_action", allowed=False, missing=missing)
        result["connector"] = connector
        result["error"] = (
            "This control plane only inspects contracts and prepares local metadata packets; account reads, contact sync, webhook changes, sending and publishing require a separately approved external action."
        )
        return result
    if action not in set(snapshot["local_actions"]):
        raise ValueError("Unknown communications connector action.")
    scope_kind = str(request.get("scope_kind") or "project_task").strip().casefold()
    if scope_kind not in {"project_task", "store"}:
        result = _base_result(
            "blocked_invalid_scope_kind", allowed=False, missing=["valid_scope_kind"]
        )
        result["connector"] = connector
        return result
    required = list(snapshot["required_route"])
    if scope_kind == "store":
        required.append("store_binding_id")
    if action == "prepare_draft_metadata_packet":
        required.extend(["message_purpose", "recipient_ref"])
    missing = [field for field in required if not str(request.get(field) or "").strip()]
    if missing:
        result = _base_result("blocked_missing_route", allowed=False, missing=missing)
        result["connector"] = connector
        return result
    route = {
        field: _clean_identifier(request.get(field), field, required=True)
        for field in required
        if field not in {"message_purpose"}
    }
    if "message_purpose" in required:
        purpose = str(request.get("message_purpose") or "").strip()
        if not PURPOSE.fullmatch(purpose):
            raise ValueError("message_purpose must be a stable purpose code.")
        route["message_purpose"] = purpose
    packet = {
        **route,
        "connector_id": connector_id,
        "scope_kind": scope_kind,
        "authorization_state": "not_configured",
        "credential_state": "reference_not_configured",
        "private_content_state": "not_accepted_or_read",
        "send_state": "not_performed",
        "publish_state": "not_performed",
        "webhook_state": "not_performed",
        "owner_authorization_required": True,
    }
    result = _base_result(
        "local_draft_metadata_packet_ready"
        if action == "prepare_draft_metadata_packet"
        else "local_binding_packet_ready",
        allowed=True,
    )
    result["connector"] = connector
    result["packet"] = packet
    return result


def run_communications_connector_audit(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    request = payload.get("request") if isinstance(payload.get("request"), dict) else payload
    result = evaluate_communications_connector_request(root, request)
    safe_request = {
        key: request.get(key)
        for key in (
            "connector_id",
            "action",
            "scope_kind",
            "tenant_id",
            "project_id",
            "task_id",
            "store_binding_id",
            "execution_identity_id",
            "connector_account_ref",
            "message_purpose",
            "recipient_ref",
        )
        if request.get(key) not in (None, "")
    }
    audit = {
        "id": f"communications-audit-{uuid4().hex[:16]}",
        "created_at": _now(),
        "actor": str(actor or "owner")[:120],
        "request": safe_request,
        "result": result,
    }
    state = _state(root)
    state["audits"].append(audit)
    _save_state(root, state)
    return {"ok": True, "audit": audit}


def record_communications_connector_review(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    audit_id = _clean_identifier(payload.get("audit_id"), "audit_id", required=True)
    state = _state(root)
    audit = next((item for item in state["audits"] if item.get("id") == audit_id), None)
    if not audit:
        raise ValueError("Communications connector audit not found.")
    review = {
        "id": f"communications-review-{uuid4().hex[:16]}",
        "created_at": _now(),
        "actor": str(actor or "owner")[:120],
        "audit_id": audit_id,
        "evidence_source": str(payload.get("evidence_source") or "formal_app_manual")[:120],
        "evidence_ref": str(payload.get("evidence_ref") or f"formal-app:{audit_id}")[:240],
        "account_authorization_observed": False,
        "inbox_read_observed": False,
        "contact_sync_observed": False,
        "webhook_subscription_observed": False,
        "message_send_observed": False,
        "social_publish_observed": False,
        "causal_conclusion": "inconclusive",
    }
    state["reviews"].append(review)
    _save_state(root, state)
    return {"ok": True, "review": review}
