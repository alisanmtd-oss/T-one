from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path
from typing import Any


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _blob(data: bytes) -> tuple[_DataBlob, Any]:
    buffer = ctypes.create_string_buffer(data)
    return (
        _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))),
        buffer,
    )


def _require_windows() -> None:
    if os.name != "nt":
        raise OSError("The local T-one credential vault currently requires Windows DPAPI.")


def protect_current_user_secret(secret: str) -> str:
    """Return a DPAPI current-user ciphertext; the plaintext is never written to disk."""
    _require_windows()
    raw = str(secret or "").encode("utf-8")
    if not raw:
        raise ValueError("Secret is required.")
    input_blob, input_buffer = _blob(raw)
    output_blob = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    # CRYPTPROTECT_UI_FORBIDDEN keeps registration non-interactive while DPAPI
    # still binds decryption to the current Windows user profile.
    ok = crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        "T-one local MCP credential",
        None,
        None,
        None,
        0x1,
        ctypes.byref(output_blob),
    )
    del input_buffer
    if not ok:
        raise ctypes.WinError()
    try:
        encrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)
    return base64.b64encode(encrypted).decode("ascii")


def unprotect_current_user_secret(protected_value: str) -> str:
    _require_windows()
    try:
        encrypted = base64.b64decode(str(protected_value or ""), validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Protected credential is invalid.") from exc
    input_blob, input_buffer = _blob(encrypted)
    output_blob = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        0x1,
        ctypes.byref(output_blob),
    )
    del input_buffer
    if not ok:
        raise ctypes.WinError()
    try:
        raw = ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)
    return raw.decode("utf-8")


def write_protected_credential(
    path: Path,
    secret: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> Path:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "protection": "windows_dpapi_current_user",
        "protected_secret": protect_current_user_secret(secret),
        "metadata": metadata if isinstance(metadata, dict) else {},
    }
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, target)
    return target


def read_protected_credential(path: Path) -> tuple[str, dict[str, Any]]:
    target = Path(path).resolve()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Protected credential file is unavailable or invalid.") from exc
    if not isinstance(payload, dict) or payload.get("protection") != "windows_dpapi_current_user":
        raise ValueError("Protected credential uses an unsupported format.")
    secret = unprotect_current_user_secret(str(payload.get("protected_secret") or ""))
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    return secret, metadata
