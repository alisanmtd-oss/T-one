from __future__ import annotations

import base64
import ctypes
import json
import os
import re
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SAFE_CREDENTIAL_REF = re.compile(r"^[a-z0-9][a-z0-9._:/-]{1,127}$")
STORE_SCHEMA_VERSION = 1
CRYPTPROTECT_UI_FORBIDDEN = 0x01
CREDENTIAL_METADATA_FIELDS = {
    "purpose",
    "project_id",
    "store_binding_id",
    "platform",
    "country_site",
    "store_model",
    "ownership",
    "remote_store_id",
    "label",
    "provider_id",
    "authorization_surface",
    "verification_status",
    "verified_at",
    "expires_at",
    "marketplace_ids",
}


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def credential_store_path(root: Path) -> Path:
    override = str(os.getenv("T_ONE_CREDENTIAL_STORE") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return root / "data" / "private" / "ai_credentials.json"


def provider_credential_ref(provider_name: str) -> str:
    clean = str(provider_name or "").strip().lower()
    reference = f"ai:{clean}"
    if not SAFE_CREDENTIAL_REF.fullmatch(reference):
        raise ValueError("AI 凭据引用无效。")
    return reference


def environment_credential_ref(env_name: str) -> str:
    clean = str(env_name or "").strip().upper()
    reference = f"env:{clean.lower()}"
    if not SAFE_CREDENTIAL_REF.fullmatch(reference):
        raise ValueError("环境变量凭据引用无效。")
    return reference


def _load_store(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {}
    credentials = payload.get("credentials") if isinstance(payload, dict) else None
    return {
        "schema_version": STORE_SCHEMA_VERSION,
        "credentials": dict(credentials) if isinstance(credentials, dict) else {},
    }


def _write_store(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    temporary.replace(path)


def _protect_windows(value: str) -> str:
    raw = value.encode("utf-8")
    input_buffer = ctypes.create_string_buffer(raw)
    input_blob = _DataBlob(len(raw), ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_byte)))
    output_blob = _DataBlob()
    description = "T One AI credential"
    success = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        ctypes.c_wchar_p(description),
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )
    if not success:
        raise OSError("Windows 无法加密本机 AI 凭据。")
    try:
        protected = ctypes.string_at(output_blob.pbData, output_blob.cbData)
        return base64.b64encode(protected).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)


def _unprotect_windows(ciphertext: str) -> str:
    protected = base64.b64decode(ciphertext.encode("ascii"), validate=True)
    input_buffer = ctypes.create_string_buffer(protected)
    input_blob = _DataBlob(
        len(protected), ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_byte))
    )
    output_blob = _DataBlob()
    success = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )
    if not success:
        raise OSError("Windows 无法解密本机 AI 凭据。")
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)


def _safe_credential_metadata(metadata: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(metadata, dict):
        return {}
    safe: dict[str, str] = {}
    for key in CREDENTIAL_METADATA_FIELDS:
        value = " ".join(str(metadata.get(key) or "").split())
        if not value:
            continue
        safe[key] = value[:160]
    for key in (
        "purpose",
        "project_id",
        "store_binding_id",
        "platform",
        "store_model",
        "ownership",
        "provider_id",
        "authorization_surface",
        "verification_status",
    ):
        if key in safe:
            safe[key] = safe[key].lower()
    if "country_site" in safe:
        safe["country_site"] = safe["country_site"].upper()
    return safe


def save_credential(
    root: Path,
    credential_ref: str,
    secret: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, str]:
    reference = str(credential_ref or "").strip().lower()
    value = str(secret or "").strip()
    if not SAFE_CREDENTIAL_REF.fullmatch(reference):
        raise ValueError("AI 凭据引用无效。")
    if not value:
        raise ValueError("API Key 不能为空。")
    if os.name != "nt":
        raise OSError("当前版本只在 Windows 使用系统加密凭据仓；请改用环境变量引用。")

    path = credential_store_path(root)
    payload = _load_store(path)
    entry: dict[str, Any] = {
        "kind": "windows_dpapi",
        "ciphertext": _protect_windows(value),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    safe_metadata = _safe_credential_metadata(metadata)
    if safe_metadata:
        entry["metadata"] = safe_metadata
    payload["credentials"][reference] = entry
    _write_store(path, payload)
    return {"credential_ref": reference, "persist_status": "local_encrypted"}


def load_credential(root: Path, credential_ref: str) -> str | None:
    reference = str(credential_ref or "").strip().lower()
    if not reference or not SAFE_CREDENTIAL_REF.fullmatch(reference):
        return None
    entry = _load_store(credential_store_path(root))["credentials"].get(reference)
    if not isinstance(entry, dict) or entry.get("kind") != "windows_dpapi":
        return None
    if os.name != "nt":
        return None
    ciphertext = str(entry.get("ciphertext") or "").strip()
    if not ciphertext:
        return None
    try:
        return _unprotect_windows(ciphertext)
    except (OSError, ValueError, UnicodeError):
        return None


def delete_credential(root: Path, credential_ref: str) -> bool:
    """Delete one encrypted credential without exposing or decrypting its value."""

    reference = str(credential_ref or "").strip().lower()
    if not SAFE_CREDENTIAL_REF.fullmatch(reference):
        raise ValueError("AI 凭据引用无效。")
    path = credential_store_path(root)
    payload = _load_store(path)
    if reference not in payload["credentials"]:
        return False
    payload["credentials"].pop(reference, None)
    _write_store(path, payload)
    return True


def credential_reference_catalog(root: Path) -> list[dict[str, Any]]:
    """Return credential metadata without returning encrypted or decrypted values."""

    rows: list[dict[str, Any]] = []
    credentials = _load_store(credential_store_path(root))["credentials"]
    for reference in sorted(credentials, key=str.casefold):
        entry = credentials.get(reference)
        if not SAFE_CREDENTIAL_REF.fullmatch(reference) or not isinstance(entry, dict):
            continue
        metadata = _safe_credential_metadata(entry.get("metadata"))
        rows.append(
            {
                "reference": reference,
                "kind": str(entry.get("kind") or ""),
                "updated_at": str(entry.get("updated_at") or ""),
                "available": bool(load_credential(root, reference)),
                "metadata": metadata,
            }
        )
    return rows


def resolve_credential(
    root: Path,
    *,
    credential_ref: str = "",
    api_key_env: str = "",
) -> str | None:
    reference = str(credential_ref or "").strip().lower()
    env_name = str(api_key_env or "").strip().upper()
    if reference.startswith("env:"):
        referenced_env = reference.removeprefix("env:").upper()
        if referenced_env:
            env_name = referenced_env
    elif reference:
        value = load_credential(root, reference)
        if value:
            return value
    if env_name:
        value = str(os.getenv(env_name) or "").strip()
        if value:
            return value
    if env_name:
        return load_credential(root, environment_credential_ref(env_name))
    return None


def credential_available(
    root: Path,
    *,
    credential_ref: str = "",
    api_key_env: str = "",
) -> bool:
    return bool(
        resolve_credential(
            root,
            credential_ref=credential_ref,
            api_key_env=api_key_env,
        )
    )
