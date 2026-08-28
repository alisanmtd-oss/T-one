from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


STATE_RELATIVE_PATH = Path("data") / "account_access_automation.json"
MAX_BINDINGS = 500
MAX_PLANS = 500
MAX_RECEIPTS = 500
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "auth_code",
    "authorization",
    "backup_code",
    "client_secret",
    "cookie",
    "mfa_code",
    "otp",
    "passcode",
    "password",
    "plaintext_password",
    "refresh_token",
    "secret",
    "session_cookie",
    "token",
    "verification_code",
}


CAPABILITY_MANIFEST = {
    "schema_version": 1,
    "purpose": "把店铺账号、邮箱/辅助邮箱、浏览器环境、凭据引用、验证码回填和人工接管统一成可审计的本地执行身份。",
    "identity_layers": [
        "project",
        "platform",
        "country_site",
        "store_binding",
        "platform_account",
        "store_mode",
        "browser_profile",
        "network_ip_profile",
        "primary_mailbox",
        "backup_mailbox",
        "credential_reference",
        "verification_channel",
        "operator_run",
    ],
    "supported_future_steps": [
        "打开已绑定浏览器环境",
        "定位平台登录页",
        "通过本机凭据管理器填入账号",
        "等待平台发送验证码",
        "只在授权邮箱连接器内查找对应验证码",
        "把验证码回填到同一浏览器会话",
        "记录登录状态、异常和人工接管原因",
    ],
    "hard_boundaries": [
        "不保存明文密码、Token、Cookie 或验证码",
        "不读取未授权邮箱或工作群",
        "不绕过验证码、MFA、风控、Captcha 或平台安全策略",
        "不登录非本人或未授权账号",
        "不同平台/站点/店铺/浏览器身份必须隔离",
        "同一可执行浏览器环境或网络/IP身份不能跨店铺复用",
        "遇到风控、MFA 设备确认、异常验证码或账号申诉必须人工接管",
    ],
}
IDENTITY_SCOPE_FIELDS = (
    "project_id",
    "platform",
    "country_site",
    "store_mode",
    "store_binding_id",
    "platform_account_ref",
)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(default)
    return payload if isinstance(payload, dict) else dict(default)


def _state(root: Path) -> dict[str, Any]:
    payload = _read_json(
        root / STATE_RELATIVE_PATH,
        {
            "schema_version": 1,
            "bindings": [],
            "login_plans": [],
            "verification_receipts": [],
        },
    )
    for key in ("bindings", "login_plans", "verification_receipts"):
        if not isinstance(payload.get(key), list):
            payload[key] = []
    payload["schema_version"] = 1
    return payload


def _save_state(root: Path, state: dict[str, Any]) -> None:
    path = root / STATE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    state["schema_version"] = 1
    state["bindings"] = list(state.get("bindings") or [])[-MAX_BINDINGS:]
    state["login_plans"] = list(state.get("login_plans") or [])[-MAX_PLANS:]
    state["verification_receipts"] = list(state.get("verification_receipts") or [])[-MAX_RECEIPTS:]
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _find_sensitive_field(value: Any, path: str = "request") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().casefold()
            if normalized in SENSITIVE_KEYS or normalized.endswith("_secret"):
                return f"{path}.{key}"
            found = _find_sensitive_field(child, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_sensitive_field(child, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(value, str) and EMAIL_PATTERN.search(value):
        return path
    return None


def _clean_ref(value: Any, label: str, *, required: bool = False) -> str:
    text = " ".join(str(value or "").split())
    if not text and not required:
        return ""
    if not IDENTIFIER.fullmatch(text):
        raise ValueError(f"{label} 必须是内部稳定引用，不能填邮箱、密码、验证码或自由文本。")
    return text


def _clean_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y", "on", "已授权"}
    return bool(value)


def _binding_key(payload: dict[str, Any]) -> str:
    seed = "|".join(
        [
            str(payload.get("project_id") or "").casefold(),
            str(payload.get("platform") or "").casefold(),
            str(payload.get("country_site") or "").casefold(),
            str(payload.get("store_mode") or "").casefold(),
            str(payload.get("store_binding_id") or "").casefold(),
            str(payload.get("platform_account_ref") or "").casefold(),
        ]
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def _safe_binding(payload: dict[str, Any], *, actor: str = "owner") -> dict[str, Any]:
    sensitive = _find_sensitive_field(payload)
    if sensitive:
        raise ValueError(f"账号登录自动化不接受明文隐私或密钥字段：{sensitive}。请只保存本机凭据引用。")
    project_id = _clean_ref(payload.get("project_id"), "project_id", required=True)
    platform = _clean_ref(payload.get("platform"), "platform", required=True).lower()
    country_site = _clean_ref(payload.get("country_site") or "GLOBAL", "country_site").upper() or "GLOBAL"
    store_binding_id = _clean_ref(payload.get("store_binding_id"), "store_binding_id")
    platform_account_ref = _clean_ref(payload.get("platform_account_ref"), "platform_account_ref")
    binding = {
        "binding_id": _clean_ref(payload.get("binding_id"), "binding_id") or f"access-{_binding_key(payload)}",
        "project_id": project_id,
        "platform": platform,
        "country_site": country_site,
        "store_mode": _clean_ref(payload.get("store_mode"), "store_mode"),
        "store_binding_id": store_binding_id,
        "platform_account_ref": platform_account_ref,
        "browser_profile_ref": _clean_ref(payload.get("browser_profile_ref"), "browser_profile_ref"),
        "network_profile_ref": _clean_ref(payload.get("network_profile_ref"), "network_profile_ref"),
        "primary_email_ref": _clean_ref(payload.get("primary_email_ref"), "primary_email_ref"),
        "backup_email_refs": [
            _clean_ref(item, "backup_email_ref")
            for item in payload.get("backup_email_refs", [])
            if str(item or "").strip()
        ],
        "credential_ref": _clean_ref(payload.get("credential_ref"), "credential_ref"),
        "login_surface_ref": _clean_ref(payload.get("login_surface_ref"), "login_surface_ref"),
        "verification_channel": _clean_ref(payload.get("verification_channel") or "email", "verification_channel"),
        "mailbox_connector_ref": _clean_ref(payload.get("mailbox_connector_ref"), "mailbox_connector_ref"),
        "owner_authorized": _clean_bool(payload.get("owner_authorized")),
        "browser_profile_verified": _clean_bool(payload.get("browser_profile_verified")),
        "network_profile_verified": _clean_bool(payload.get("network_profile_verified")),
        "mailbox_connector_verified": _clean_bool(payload.get("mailbox_connector_verified")),
        "credential_ref_verified": _clean_bool(payload.get("credential_ref_verified")),
        "platform_policy_reviewed": _clean_bool(payload.get("platform_policy_reviewed")),
        "automation_scope": str(payload.get("automation_scope") or "local_plan_only").strip()[:80],
        "external_action_count": 0,
        "secrets_stored": False,
        "updated_at": _now(),
        "updated_by": str(actor or "owner")[:80],
    }
    return binding


def _find_binding(state: dict[str, Any], binding_id: str) -> dict[str, Any] | None:
    normalized = str(binding_id or "").strip()
    for binding in state.get("bindings") or []:
        if str(binding.get("binding_id") or "") == normalized:
            return dict(binding)
    return None


def _find_login_plan(state: dict[str, Any], plan_id: str) -> dict[str, Any] | None:
    normalized = str(plan_id or "").strip()
    for plan in state.get("login_plans") or []:
        if str(plan.get("id") or "") == normalized:
            return dict(plan)
    return None


def _identity_scope(binding: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(binding.get(field) or "").strip().casefold() for field in IDENTITY_SCOPE_FIELDS)


def register_access_binding(root: Path, payload: dict[str, Any], *, actor: str = "owner") -> dict[str, Any]:
    """Register or update a local identity binding. It never stores passwords or opens accounts."""
    state = _state(root)
    binding = _safe_binding(payload, actor=actor)
    previous = _find_binding(state, binding["binding_id"])
    if previous is not None and _identity_scope(previous) != _identity_scope(binding):
        raise ValueError("同一 binding_id 不能修改项目、平台、站点、店铺或平台账号执行身份范围。")
    for existing_binding in state.get("bindings") or []:
        if str(existing_binding.get("binding_id") or "") == binding["binding_id"]:
            continue
        if (
            _identity_scope(existing_binding) == _identity_scope(binding)
        ):
            raise ValueError(
                "同一项目、平台、站点、店铺和账号执行身份已经登记，不能用另一个 binding_id 重复绑定。"
            )
        existing_browser = str(existing_binding.get("browser_profile_ref") or "").strip()
        if existing_browser and existing_browser == binding.get("browser_profile_ref"):
            raise ValueError("同一可执行浏览器环境不能跨店铺或账号执行身份复用。")
        existing_network = str(existing_binding.get("network_profile_ref") or "").strip()
        if existing_network and existing_network == binding.get("network_profile_ref"):
            raise ValueError("同一网络/IP执行身份不能跨店铺或账号复用。")
    existing: list[dict[str, Any]] = []
    replaced = False
    for item in state.get("bindings") or []:
        if str(item.get("binding_id") or "") == binding["binding_id"]:
            existing.append({**item, **binding, "created_at": item.get("created_at") or binding["updated_at"]})
            replaced = True
        else:
            existing.append(item)
    if not replaced:
        binding["created_at"] = binding["updated_at"]
        existing.append(binding)
    state["bindings"] = existing
    _save_state(root, state)
    return {
        "ok": True,
        "binding": binding,
        "status": "binding_registered_local_only",
        "external_action_count": 0,
        "secrets_stored": False,
    }


def build_login_plan(root: Path, payload: dict[str, Any], *, actor: str = "owner") -> dict[str, Any]:
    """Build a deterministic login/verification plan without executing browser or mailbox actions."""
    sensitive = _find_sensitive_field(payload)
    if sensitive:
        raise ValueError(f"登录计划不接受明文隐私或密钥字段：{sensitive}。")
    state = _state(root)
    binding_id = _clean_ref(payload.get("binding_id"), "binding_id", required=True)
    binding = _find_binding(state, binding_id)
    if binding is None:
        plan = {
            "id": f"login-plan-{uuid4().hex[:16]}",
            "binding_id": binding_id,
            "status": "blocked_missing_binding",
            "missing": ["registered_access_binding"],
            "created_at": _now(),
            "created_by": str(actor or "owner")[:80],
            "external_action_count": 0,
            "browser_opened": False,
            "mailbox_read": False,
            "verification_code_filled": False,
        }
    else:
        missing: list[str] = []
        required_fields = {
            "store_binding_id": "store_binding_id",
            "store_mode": "store_mode",
            "platform_account_ref": "platform_account_ref",
            "browser_profile_ref": "browser_profile_ref",
            "network_profile_ref": "network_profile_ref",
            "primary_email_ref": "primary_email_ref",
            "credential_ref": "credential_ref",
            "login_surface_ref": "login_surface_ref",
            "mailbox_connector_ref": "mailbox_connector_ref",
        }
        for field, label in required_fields.items():
            if not str(binding.get(field) or "").strip():
                missing.append(label)
        if not binding.get("owner_authorized"):
            missing.append("owner_authorization")
        if not binding.get("browser_profile_verified"):
            missing.append("verified_browser_profile")
        if not binding.get("network_profile_verified"):
            missing.append("verified_network_profile")
        if not binding.get("mailbox_connector_verified"):
            missing.append("verified_mailbox_connector")
        if not binding.get("credential_ref_verified"):
            missing.append("verified_credential_reference")
        if not binding.get("platform_policy_reviewed"):
            missing.append("platform_policy_review")

        plan = {
            "id": f"login-plan-{uuid4().hex[:16]}",
            "binding_id": binding_id,
            "project_id": binding.get("project_id"),
            "platform": binding.get("platform"),
            "country_site": binding.get("country_site"),
            "store_binding_id": binding.get("store_binding_id"),
            "store_mode": binding.get("store_mode"),
            "platform_account_ref": binding.get("platform_account_ref"),
            "browser_profile_ref": binding.get("browser_profile_ref"),
            "network_profile_ref": binding.get("network_profile_ref"),
            "status": "ready_for_owner_approved_operator" if not missing else "blocked_missing_gates",
            "missing": missing,
            "planned_steps": CAPABILITY_MANIFEST["supported_future_steps"],
            "handoff_required_on": ["captcha", "unknown_mfa_device", "risk_challenge", "account_appeal", "verification_timeout"],
            "created_at": _now(),
            "created_by": str(actor or "owner")[:80],
            "external_action_count": 0,
            "browser_opened": False,
            "mailbox_read": False,
            "verification_code_filled": False,
            "secrets_stored": False,
        }
    state["login_plans"] = list(state.get("login_plans") or []) + [plan]
    _save_state(root, state)
    return {"ok": True, "plan": plan}


def record_verification_receipt(root: Path, payload: dict[str, Any], *, actor: str = "owner") -> dict[str, Any]:
    """Record an OTP/MFA observation without persisting the raw code."""
    sensitive = _find_sensitive_field(payload)
    if sensitive:
        raise ValueError(f"验证码回执不能包含明文验证码或密钥字段：{sensitive}。")
    binding_id = _clean_ref(payload.get("binding_id"), "binding_id", required=True)
    source_ref = _clean_ref(payload.get("source_ref"), "source_ref", required=True)
    state = _state(root)
    binding = _find_binding(state, binding_id)
    if binding is None:
        raise ValueError("验证码回执找不到对应的已登记执行身份。")
    delivery_channel = _clean_ref(payload.get("delivery_channel") or "email", "delivery_channel")
    if delivery_channel == "email":
        allowed_mailboxes = {
            str(binding.get("primary_email_ref") or "").strip(),
            *[
                str(item or "").strip()
                for item in list(binding.get("backup_email_refs") or [])
            ],
        }
        allowed_mailboxes.discard("")
        if source_ref not in allowed_mailboxes:
            raise ValueError("验证码来源不是该店铺执行身份登记的主邮箱或辅助绑定邮箱。")
    code_detected = _clean_bool(payload.get("code_detected"))
    try:
        code_length = int(payload.get("code_length") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("code_length 必须是 0 到 12 之间的数字；不要提交验证码原文。") from exc
    if code_length < 0 or code_length > 12:
        raise ValueError("code_length 必须在 0 到 12 之间；不要提交验证码原文。")
    filled_into_session = _clean_bool(payload.get("filled_into_session"))
    browser_session_ref = _clean_ref(payload.get("browser_session_ref"), "browser_session_ref")
    operator_run_ref = _clean_ref(payload.get("operator_run_ref"), "operator_run_ref")
    if filled_into_session and (not browser_session_ref or not operator_run_ref):
        raise ValueError("声称已回填验证码时，必须记录同一执行身份的浏览器会话和 operator_run 引用。")
    if filled_into_session and not code_detected:
        raise ValueError("没有检测到验证码时不能记录为已回填。")
    login_plan_id = _clean_ref(payload.get("login_plan_id"), "login_plan_id")
    browser_profile_ref = _clean_ref(payload.get("browser_profile_ref"), "browser_profile_ref")
    network_profile_ref = _clean_ref(payload.get("network_profile_ref"), "network_profile_ref")
    if filled_into_session:
        plan = _find_login_plan(state, login_plan_id)
        if (
            plan is None
            or str(plan.get("binding_id") or "") != binding_id
            or browser_profile_ref != str(binding.get("browser_profile_ref") or "")
            or network_profile_ref != str(binding.get("network_profile_ref") or "")
        ):
            raise ValueError("验证码回填必须引用同一执行身份的登录计划、浏览器环境和网络/IP身份。")
    receipt = {
        "id": f"verification-{uuid4().hex[:16]}",
        "binding_id": binding_id,
        "source_ref": source_ref,
        "delivery_channel": delivery_channel,
        "code_detected": code_detected,
        "code_length": code_length if code_detected else 0,
        "code_mask": "*" * code_length if code_detected and code_length else "",
        "expires_at": str(payload.get("expires_at") or "")[:80],
        "filled_into_session": filled_into_session,
        "login_plan_id": login_plan_id,
        "browser_profile_ref": browser_profile_ref,
        "network_profile_ref": network_profile_ref,
        "browser_session_ref": browser_session_ref,
        "operator_run_ref": operator_run_ref,
        "status": "filled_claim_pending_owner_review" if filled_into_session else "local_observation_pending_review",
        "created_at": _now(),
        "created_by": str(actor or "owner")[:80],
        "external_action_count": 0,
        "raw_code_stored": False,
    }
    state["verification_receipts"] = list(state.get("verification_receipts") or []) + [receipt]
    _save_state(root, state)
    return {"ok": True, "receipt": receipt}


def validate_account_access_state(root: Path) -> dict[str, Any]:
    state = _state(root)
    errors: list[str] = []
    raw = json.dumps(state, ensure_ascii=False)
    if EMAIL_PATTERN.search(raw):
        errors.append("raw_email_detected")
    for key in SENSITIVE_KEYS:
        if f'"{key}"' in raw:
            errors.append(f"sensitive_key_detected:{key}")
    for group in ("bindings", "login_plans", "verification_receipts"):
        for index, item in enumerate(state.get(group) or []):
            if int(item.get("external_action_count") or 0) != 0:
                errors.append(f"{group}[{index}].external_action_count_not_zero")
            if item.get("secrets_stored") is True or item.get("raw_code_stored") is True:
                errors.append(f"{group}[{index}].secret_or_raw_code_marked_stored")
    return {"ok": not errors, "errors": errors, "checked_at": _now()}


def account_access_snapshot(root: Path) -> dict[str, Any]:
    state = _state(root)
    bindings = list(state.get("bindings") or [])
    plans = list(state.get("login_plans") or [])
    receipts = list(state.get("verification_receipts") or [])
    ready_bindings = [
        binding
        for binding in bindings
        if binding.get("owner_authorized")
        and binding.get("browser_profile_verified")
        and binding.get("network_profile_verified")
        and binding.get("mailbox_connector_verified")
        and binding.get("credential_ref_verified")
        and binding.get("platform_policy_reviewed")
    ]
    return {
        "ok": True,
        "schema_version": 1,
        "manifest": CAPABILITY_MANIFEST,
        "binding_count": len(bindings),
        "ready_binding_count": len(ready_bindings),
        "login_plan_count": len(plans),
        "verification_receipt_count": len(receipts),
        "latest_bindings": bindings[-20:],
        "latest_login_plans": plans[-20:],
        "latest_verification_receipts": receipts[-20:],
        "external_action_count": 0,
        "real_platform_login_count": 0,
        "real_mailbox_read_count": 0,
        "raw_secret_or_code_stored": False,
        "owner_input_required_for_real_login": True,
        "real_login_blocker": "owner_authorized_account_and_exact_read_only_scope_required",
        "validation": validate_account_access_state(root),
    }
