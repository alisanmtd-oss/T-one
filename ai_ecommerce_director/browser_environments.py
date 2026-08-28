from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


BITBROWSER_DEFAULT_BASE_URL = "http://127.0.0.1:54345"
SUPPORTED_BROWSER_PROVIDERS = {"bitbrowser", "ziniao", "zhanfu", "chrome"}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _path(value: str | os.PathLike[str] | None) -> Path | None:
    if not value:
        return None
    try:
        candidate = Path(value).expanduser()
    except (OSError, TypeError, ValueError):
        return None
    return candidate if candidate.is_file() else None


def _first_existing(candidates: list[str | os.PathLike[str] | None]) -> Path | None:
    for candidate in candidates:
        existing = _path(candidate)
        if existing is not None:
            return existing.resolve()
    return None


def _candidate_paths() -> dict[str, list[str | os.PathLike[str] | None]]:
    local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    program_files = Path(os.environ.get("ProgramFiles") or r"C:\Program Files")
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)")
    system_drive = os.environ.get("SystemDrive") or "C:"
    public = Path(os.environ.get("PUBLIC") or f"{system_drive}\\Users\\Public")
    return {
        "bitbrowser": [
            os.environ.get("BITBROWSER_MANAGER_EXE"),
            local / "Programs" / "bitbrowser" / "比特浏览器.exe",
            local / "Programs" / "BitBrowser" / "BitBrowser.exe",
        ],
        "ziniao": [
            os.environ.get("ZINIAO_BROWSER_EXE"),
            program_files / "ziniao" / "ziniao.exe",
            public / "SuperBrowser" / "starter.exe",
        ],
        "zhanfu": [
            os.environ.get("ZHANFU_BROWSER_EXE"),
            program_files / "ZhanFu" / "ZhanFu.exe",
            program_files_x86 / "ZhanFu" / "ZhanFu.exe",
            local / "Programs" / "ZhanFu" / "ZhanFu.exe",
        ],
        "chrome": [
            os.environ.get("CHROME_EXE"),
            program_files / "Google" / "Chrome" / "Application" / "chrome.exe",
            program_files_x86 / "Google" / "Chrome" / "Application" / "chrome.exe",
            local / "Google" / "Chrome" / "Application" / "chrome.exe",
        ],
    }


def _loopback_base_url(value: str | None) -> str:
    raw = str(value or BITBROWSER_DEFAULT_BASE_URL).strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("浏览器本地 API 只允许连接本机回环地址。")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("浏览器本地 API 地址格式不正确。")
    return raw


def _bitbrowser_local_api_headers() -> dict[str, str]:
    """Read BitBrowser's own local token without exposing or persisting it."""

    appdata = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    config_path = appdata / "BitBrowser" / "config.json"
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError):
        return {}
    if not isinstance(payload, dict) or payload.get("enableAuth") is not True:
        return {}
    token = str(payload.get("authToken") or "").strip()
    return {"X-Api-Key": token} if token else {}


def _post_json(base_url: str, endpoint: str, payload: dict[str, Any], timeout: float = 2.5) -> dict[str, Any]:
    base = _loopback_base_url(base_url)
    request = Request(
        base + "/" + endpoint.lstrip("/"),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **_bitbrowser_local_api_headers()},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - loopback-only URL is validated above.
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise ConnectionError(str(exc)) from exc
    return data if isinstance(data, dict) else {}


def _safe_bitbrowser_profiles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    rows = data.get("list") if isinstance(data.get("list"), list) else []
    profiles: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        tags = []
        for item in row.get("browserTags") or []:
            if isinstance(item, dict) and str(item.get("tagName") or "").strip():
                tags.append(str(item.get("tagName") or "").strip()[:80])
        profiles.append(
            {
                "id": str(row.get("id") or "")[:160],
                "sequence": int(row.get("seq") or 0),
                "name": str(row.get("name") or f"环境 {row.get('seq') or ''}").strip()[:120],
                "group_id": str(row.get("groupId") or "")[:120],
                "tags": tags[:12],
            }
        )
    return sorted(profiles, key=lambda item: (item["sequence"] <= 0, item["sequence"], item["name"]))


def browser_environment_snapshot(root: Path | None = None) -> dict[str, Any]:
    del root  # Reserved for future workspace-specific adapter policy.
    paths = _candidate_paths()
    bit_exe = _first_existing(paths["bitbrowser"])
    bit_base = _loopback_base_url(os.environ.get("BITBROWSER_LOCAL_API"))
    bit_healthy = False
    bit_profiles: list[dict[str, Any]] = []
    bit_message = "未检测到比特浏览器"
    if bit_exe is not None:
        bit_message = "已安装，本地 API 尚未启动；不代表店铺或平台授权"
        try:
            health = _post_json(bit_base, "/health", {})
            bit_healthy = bool(health.get("success"))
            if bit_healthy:
                bit_profiles = _safe_bitbrowser_profiles(
                    _post_json(bit_base, "/browser/list", {"page": 0, "pageSize": 200}, timeout=5)
                )
                bit_message = f"本地 API 可读，可选择 {len(bit_profiles)} 个环境；执行前仍需确认平台/店铺身份"
        except ConnectionError:
            pass

    providers: list[dict[str, Any]] = [
        {
            "id": "bitbrowser",
            "name": "比特浏览器",
            "installed": bit_exe is not None,
            "executable": str(bit_exe or ""),
            "adapter": "official_local_api",
            "status": "ready" if bit_healthy else ("installed_offline" if bit_exe else "not_installed"),
            "message": bit_message,
            "supports_automatic_profile_open": bit_healthy,
            "requires_manual_security_checkpoint": True,
            "profiles": bit_profiles,
        }
    ]
    labels = {
        "ziniao": ("紫鸟浏览器", "desktop_adapter_pending"),
        "zhanfu": ("战斧浏览器", "desktop_adapter_pending"),
        "chrome": ("Google Chrome", "desktop_or_extension"),
    }
    for provider_id in ("ziniao", "zhanfu", "chrome"):
        executable = _first_existing(paths[provider_id])
        label, adapter = labels[provider_id]
        providers.append(
            {
                "id": provider_id,
                "name": label,
                "installed": executable is not None,
                "executable": str(executable or ""),
                "adapter": adapter,
                "status": "installed_needs_profile_selection" if executable else "not_installed",
                "message": (
                    "已安装；启动后由用户选择店铺环境，智能体再继续识别当前页面；不代表已授权执行"
                    if executable
                    else "当前电脑未检测到安装"
                ),
                "supports_automatic_profile_open": False,
                "requires_manual_security_checkpoint": True,
                "profiles": [],
            }
        )
    return {
        "ok": True,
        "generated_at": _now_iso(),
        "policy": {
            "browser_environment_sharing": "one_profile_or_window_may_host_multiple_store_routes",
            "identity_isolation": "one_selected_store_execution_identity_per_action",
            "shared_environment_is_not_shared_authorization": True,
            "secrets_stored": False,
            "security_checkpoints": ["login", "captcha", "MFA", "account_security"],
        },
        "providers": providers,
    }


def _launch_visible(executable: str) -> None:
    path = _path(executable)
    if path is None:
        raise ValueError("浏览器程序不存在或已移动。")
    subprocess.Popen(  # noqa: S603 - executable is selected only from detected local allowlisted provider paths.
        [str(path)],
        cwd=str(path.parent),
        close_fds=True,
    )


def _bitbrowser_profile(snapshot: dict[str, Any], profile_id: str, profile_sequence: int) -> dict[str, Any] | None:
    providers = snapshot.get("providers") if isinstance(snapshot.get("providers"), list) else []
    bit = next((item for item in providers if isinstance(item, dict) and item.get("id") == "bitbrowser"), {})
    for item in bit.get("profiles") or []:
        if not isinstance(item, dict):
            continue
        if profile_id and str(item.get("id") or "") == profile_id:
            return item
        if profile_sequence and int(item.get("sequence") or 0) == profile_sequence:
            return item
    return None


def prepare_browser_environment(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    provider_id = str(payload.get("provider") or "").strip().lower()
    if provider_id not in SUPPORTED_BROWSER_PROVIDERS:
        raise ValueError("请选择受支持的浏览器环境。")
    snapshot = browser_environment_snapshot(root)
    provider = next(
        (item for item in snapshot["providers"] if item.get("id") == provider_id),
        None,
    )
    if not provider or not provider.get("installed"):
        raise ValueError("所选浏览器当前未安装。")

    if provider_id != "bitbrowser":
        _launch_visible(str(provider.get("executable") or ""))
        return {
            "ok": True,
            "provider": provider_id,
            "status": "manual_profile_selection",
            "message": f"已打开{provider.get('name')}。请选择对应店铺环境；登录、验证码或安全确认完成后，智能体会继续。",
            "binding": {
                "browser_provider": provider_id,
                "browser_profile_id": "",
                "browser_profile_sequence": 0,
                "binding_status": "profile_selection_required",
            },
        }

    if provider.get("status") != "ready":
        _launch_visible(str(provider.get("executable") or ""))
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            time.sleep(0.5)
            snapshot = browser_environment_snapshot(root)
            provider = next(item for item in snapshot["providers"] if item.get("id") == "bitbrowser")
            if provider.get("status") == "ready":
                break
    if provider.get("status") != "ready":
        return {
            "ok": False,
            "provider": provider_id,
            "status": "manager_starting",
            "message": "比特浏览器已启动，但本地 API 还没有就绪。请确认本地 API 已开启后重试。",
        }

    profile_id = str(payload.get("profile_id") or "").strip()[:160]
    try:
        profile_sequence = int(payload.get("profile_sequence") or 0)
    except (TypeError, ValueError):
        profile_sequence = 0
    profile = _bitbrowser_profile(snapshot, profile_id, profile_sequence)
    if profile is None:
        return {
            "ok": False,
            "provider": provider_id,
            "status": "profile_selection_required",
            "message": "请选择一个比特浏览器环境。",
            "profiles": provider.get("profiles") or [],
        }

    base_url = _loopback_base_url(os.environ.get("BITBROWSER_LOCAL_API"))
    opened = _post_json(
        base_url,
        "/browser/open",
        {"id": profile["id"], "queue": True},
        timeout=20,
    )
    if not opened.get("success"):
        return {
            "ok": False,
            "provider": provider_id,
            "status": "open_failed",
            "message": str(opened.get("msg") or "比特浏览器环境没有打开。")[:240],
        }
    data = opened.get("data") if isinstance(opened.get("data"), dict) else {}
    return {
        "ok": True,
        "provider": provider_id,
        "status": "profile_ready",
        "message": f"已打开比特浏览器环境 {profile['sequence']} · {profile['name']}。登录、验证码或安全确认完成后，智能体会继续识别店铺。",
        "binding": {
            "browser_provider": provider_id,
            "browser_profile_id": profile["id"],
            "browser_profile_sequence": profile["sequence"],
            "browser_profile_name": profile["name"],
            "binding_status": "browser_profile_ready",
            "cdp_available": bool(data.get("http") or data.get("ws")),
        },
    }
