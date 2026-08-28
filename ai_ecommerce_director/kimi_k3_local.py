from __future__ import annotations

import ctypes
import importlib.util
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PROFILE_PATH = Path("config") / "kimi_k3_local_deployment.json"
DEFAULT_RECEIPT_PATH = (
    Path("outputs") / "kimi_k3_local_preflight_2026-07-28.json"
)


def load_kimi_k3_profile(root: Path) -> dict[str, Any]:
    payload = json.loads((root / PROFILE_PATH).read_text(encoding="utf-8"))
    if str(payload.get("model_id") or "") != "moonshotai/Kimi-K3":
        raise ValueError("Kimi K3 本地部署配置缺少官方模型 ID。")
    architecture = payload.get("architecture")
    if not isinstance(architecture, dict) or int(architecture.get("weight_bytes") or 0) <= 0:
        raise ValueError("Kimi K3 本地部署配置缺少完整权重体量。")
    return payload


def _drive_probe_path(profile: dict[str, Any]) -> Path:
    cache_root = Path(str(profile.get("model_cache_root") or "D:/models/kimi-k3"))
    anchor = cache_root
    while not anchor.exists() and anchor.parent != anchor:
        anchor = anchor.parent
    return anchor


def _memory_bytes() -> int:
    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("memory_load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong),
            ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return 0
    return int(status.total_physical)


def _gpu_snapshot() -> list[dict[str, Any]]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return []
    try:
        result = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        name, _, memory = line.rpartition(",")
        if not name.strip():
            continue
        try:
            memory_mib = int(memory.strip())
        except ValueError:
            memory_mib = 0
        rows.append({"name": name.strip(), "memory_mib": memory_mib})
    return rows


def machine_snapshot(profile: dict[str, Any]) -> dict[str, Any]:
    probe_path = _drive_probe_path(profile)
    usage = shutil.disk_usage(probe_path)
    return {
        "storage_probe_path": str(probe_path),
        "storage_free_bytes": int(usage.free),
        "memory_bytes": _memory_bytes(),
        "gpus": _gpu_snapshot(),
    }


def runtime_snapshot() -> dict[str, Any]:
    return {
        runtime: {
            "python_module": importlib.util.find_spec(runtime) is not None,
            "executable": bool(shutil.which(runtime)),
        }
        for runtime in ("vllm", "sglang", "tokenspeed")
    }


def endpoint_snapshot(endpoint: str, *, timeout_seconds: float = 2.0) -> dict[str, Any]:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {
            "reachable": False,
            "error": "invalid_endpoint",
            "probe_performed": False,
        }
    url = endpoint.rstrip("/") + "/models"
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        model_ids = [
            str(item.get("id") or "")
            for item in payload.get("data", [])
            if isinstance(item, dict)
        ]
        return {
            "reachable": True,
            "http_status": int(getattr(response, "status", 200)),
            "model_ids": model_ids,
            "probe_performed": True,
        }
    except urllib.error.HTTPError as exc:
        return {
            "reachable": False,
            "http_status": int(exc.code),
            "error": f"http_{exc.code}",
            "probe_performed": True,
        }
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return {
            "reachable": False,
            "error": type(exc).__name__,
            "probe_performed": True,
        }


def build_preflight(
    profile: dict[str, Any],
    machine: dict[str, Any],
    runtimes: dict[str, Any],
    endpoint: dict[str, Any],
) -> dict[str, Any]:
    architecture = profile["architecture"]
    weight_bytes = int(architecture["weight_bytes"])
    storage_free = int(machine.get("storage_free_bytes") or 0)
    storage_shortfall = max(0, weight_bytes - storage_free)
    system_memory_bytes = int(machine.get("memory_bytes") or 0)
    aggregate_gpu_memory_bytes = sum(
        max(0, int(item.get("memory_mib") or 0)) * 1024 * 1024
        for item in machine.get("gpus", [])
        if isinstance(item, dict)
    )
    runtime_ready = any(
        bool(item.get("python_module") or item.get("executable"))
        for item in runtimes.values()
        if isinstance(item, dict)
    )
    endpoint_models = {
        str(value) for value in endpoint.get("model_ids", []) if str(value)
    }
    endpoint_has_model = str(profile["model_id"]) in endpoint_models
    endpoint_probe_performed = bool(endpoint.get("probe_performed"))
    blockers: list[dict[str, Any]] = []
    if storage_shortfall:
        blockers.append(
            {
                "code": "insufficient_storage",
                "message": (
                    "完整官方权重无法放入所选磁盘："
                    f"还缺 {storage_shortfall} bytes。"
                ),
            }
        )
    if not runtime_ready:
        blockers.append(
            {
                "code": "runtime_missing",
                "message": "本机未检测到官方推荐的 vLLM、SGLang 或 TokenSpeed 运行时。",
            }
        )
    if not endpoint_probe_performed:
        blockers.append(
            {
                "code": "endpoint_probe_skipped",
                "message": (
                    "本地端点未探测；当前只记录前置条件不足，"
                    "不把未探测冒充为端点不可访问。"
                ),
            }
        )
    elif not endpoint.get("reachable"):
        blockers.append(
            {
                "code": "endpoint_unreachable",
                "message": "Kimi K3 本地 OpenAI 兼容端点当前不可访问。",
            }
        )
    elif not endpoint_has_model:
        blockers.append(
            {
                "code": "model_not_served",
                "message": "端点可访问，但未返回 moonshotai/Kimi-K3 模型 ID。",
            }
        )
    live_verified = not blockers and endpoint_has_model
    return {
        "schema_version": 1,
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model_id": profile["model_id"],
        "pinned_revision": profile["pinned_revision"],
        "weight_file_count": int(architecture["weight_file_count"]),
        "weight_bytes": weight_bytes,
        "machine": machine,
        "runtimes": runtimes,
        "endpoint": endpoint,
        "endpoint_probe_performed": endpoint_probe_performed,
        "storage_shortfall_bytes": storage_shortfall,
        "native_weight_capacity_comparison": {
            "weight_bytes": weight_bytes,
            "system_memory_bytes": system_memory_bytes,
            "aggregate_gpu_memory_bytes": aggregate_gpu_memory_bytes,
            "system_memory_shortfall_bytes": max(
                0, weight_bytes - system_memory_bytes
            ),
            "aggregate_gpu_memory_shortfall_bytes": max(
                0, weight_bytes - aggregate_gpu_memory_bytes
            ),
            "interpretation": (
                "capacity_comparison_only_not_an_official_minimum_requirement"
            ),
        },
        "download_allowed": bool(
            not storage_shortfall
            and profile.get("weight_download_authorized") is True
        ),
        "partial_download_attempted": False,
        "external_ai_call_count": 0,
        "deployment_state": (
            "live_verified"
            if live_verified
            else "blocked_insufficient_local_resources"
        ),
        "installed": bool(live_verified),
        "connected": bool(live_verified),
        "live_verified": bool(live_verified),
        "blockers": blockers,
        "external_business_actions": 0,
    }


def preflight_kimi_k3(
    root: Path,
    *,
    write_receipt: bool = False,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
) -> dict[str, Any]:
    profile = load_kimi_k3_profile(root)
    machine = machine_snapshot(profile)
    runtimes = runtime_snapshot()
    should_probe_endpoint = (
        int(machine.get("storage_free_bytes") or 0)
        >= int(profile["architecture"]["weight_bytes"])
        and any(
            bool(item.get("python_module") or item.get("executable"))
            for item in runtimes.values()
        )
    )
    endpoint = (
        endpoint_snapshot(str(profile["openai_compatible_endpoint"]))
        if should_probe_endpoint
        else {
            "reachable": False,
            "error": "prerequisites_not_met",
            "probe_performed": False,
        }
    )
    receipt = build_preflight(profile, machine, runtimes, endpoint)
    if write_receipt:
        destination = root / receipt_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return receipt


def blocker_message(receipt: dict[str, Any]) -> str:
    blockers = receipt.get("blockers")
    messages = [
        str(item.get("message") or "")
        for item in blockers
        if isinstance(item, dict) and item.get("message")
    ] if isinstance(blockers, list) else []
    if messages:
        return "；".join(messages)
    return "Kimi K3 本地运行时尚未通过真实端点验证。"
