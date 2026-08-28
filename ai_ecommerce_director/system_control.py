"""Local Windows system primitives used by the T One CLI.

The module never grants permissions by itself.  Every operation runs with the
Windows access token of the terminal that launched it.  An elevated terminal
therefore receives administrator access; a normal terminal stays inside the
current user's ACLs.
"""

from __future__ import annotations

import base64
import csv
import ctypes
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


MAX_CAPTURE_BYTES = 8 * 1024 * 1024


def require_windows() -> None:
    if os.name != "nt":
        raise RuntimeError("T One 全机控制当前只支持 Windows。")


def is_administrator() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def access_snapshot() -> dict[str, Any]:
    require_windows()
    administrator = is_administrator()
    return {
        "ok": True,
        "platform": "windows",
        "is_administrator": administrator,
        "effective_access": "administrator" if administrator else "current_user",
        "permission_source": "windows_access_token",
        "can_request_elevation": True,
        "filesystem_scope": "all_paths_allowed_by_windows_acl",
        "process_scope": "all_processes_allowed_by_windows_acl",
        "available_surfaces": [
            "workspace",
            "filesystem",
            "process",
            "exact_argv",
            "mouse",
            "keyboard",
            "window",
            "browser",
        ],
    }


def resolve_path(raw: str | os.PathLike[str]) -> Path:
    value = os.path.expandvars(os.path.expanduser(str(raw or "").strip()))
    if not value:
        raise ValueError("路径不能为空。")
    return Path(value).resolve()


def list_path(raw: str, *, recursive: bool = False, limit: int = 1000) -> dict[str, Any]:
    target = resolve_path(raw)
    if not target.exists():
        raise FileNotFoundError(str(target))
    if target.is_file():
        items: Iterable[Path] = [target]
    else:
        items = target.rglob("*") if recursive else target.iterdir()
    records: list[dict[str, Any]] = []
    for item in items:
        try:
            stat = item.stat()
        except OSError:
            continue
        records.append(
            {
                "name": item.name,
                "path": str(item.resolve()),
                "kind": "directory" if item.is_dir() else "file",
                "size": int(stat.st_size) if item.is_file() else 0,
                "modified_ns": int(stat.st_mtime_ns),
            }
        )
        if len(records) >= max(1, min(int(limit), 100000)):
            break
    return {"ok": True, "path": str(target), "items": records, "count": len(records)}


def read_path(raw: str, *, binary: bool = False, max_bytes: int = MAX_CAPTURE_BYTES) -> dict[str, Any]:
    target = resolve_path(raw)
    if not target.is_file():
        raise FileNotFoundError(str(target))
    limit = int(max_bytes)
    if limit < 0:
        raise ValueError("max_bytes 不能为负数。")
    with target.open("rb") as handle:
        data = handle.read() if limit == 0 else handle.read(limit + 1)
    truncated = bool(limit and len(data) > limit)
    if truncated:
        data = data[:limit]
    result: dict[str, Any] = {
        "ok": True,
        "path": str(target),
        "bytes": len(data),
        "truncated": truncated,
    }
    if binary:
        result["base64"] = base64.b64encode(data).decode("ascii")
    else:
        result["text"] = data.decode("utf-8-sig", errors="replace")
    return result


def write_path(
    raw: str,
    data: bytes,
    *,
    append: bool = False,
    create_parents: bool = False,
) -> dict[str, Any]:
    target = resolve_path(raw)
    if create_parents:
        target.parent.mkdir(parents=True, exist_ok=True)
    mode = "ab" if append else "wb"
    with target.open(mode) as handle:
        handle.write(data)
    return {"ok": True, "path": str(target), "bytes_written": len(data), "append": append}


def copy_path(source_raw: str, target_raw: str, *, overwrite: bool = False) -> dict[str, Any]:
    source = resolve_path(source_raw)
    target = resolve_path(target_raw)
    if not source.exists():
        raise FileNotFoundError(str(source))
    if target.exists() and not overwrite:
        raise FileExistsError(str(target))
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=overwrite)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return {"ok": True, "source": str(source), "target": str(target)}


def move_path(source_raw: str, target_raw: str, *, overwrite: bool = False) -> dict[str, Any]:
    source = resolve_path(source_raw)
    target = resolve_path(target_raw)
    if not source.exists():
        raise FileNotFoundError(str(source))
    if target.exists():
        if not overwrite:
            raise FileExistsError(str(target))
        delete_path(str(target), recursive=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    moved = Path(shutil.move(str(source), str(target))).resolve()
    return {"ok": True, "source": str(source), "target": str(moved)}


def _is_forbidden_delete_root(target: Path) -> bool:
    anchor = Path(target.anchor).resolve() if target.anchor else None
    if anchor is not None and target == anchor:
        return True
    protected = {Path.home().resolve(), Path(sys.prefix).resolve()}
    return target in protected


def delete_path(raw: str, *, recursive: bool = False) -> dict[str, Any]:
    target = resolve_path(raw)
    if not target.exists():
        return {"ok": True, "path": str(target), "deleted": False}
    if _is_forbidden_delete_root(target):
        raise ValueError("拒绝直接删除磁盘根目录、用户主目录或 Python 运行时根目录。")
    if target.is_dir():
        if recursive:
            shutil.rmtree(target)
        else:
            target.rmdir()
    else:
        target.unlink()
    return {"ok": True, "path": str(target), "deleted": True}


def run_exact_argv(
    argv: list[str],
    *,
    cwd: str | None = None,
    timeout_seconds: int = 120,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not argv or not str(argv[0]).strip():
        raise ValueError("必须提供要运行的程序和参数。")
    timeout = max(1, min(int(timeout_seconds), 86400))
    completed = subprocess.run(
        [str(item) for item in argv],
        cwd=str(resolve_path(cwd)) if cwd else None,
        env={**os.environ, **(env or {})},
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=False,
        shell=False,
    )
    stdout = completed.stdout[-MAX_CAPTURE_BYTES:]
    stderr = completed.stderr[-MAX_CAPTURE_BYTES:]
    return {
        "ok": completed.returncode == 0,
        "argv": [str(item) for item in argv],
        "cwd": str(resolve_path(cwd)) if cwd else str(Path.cwd().resolve()),
        "returncode": int(completed.returncode),
        "stdout": stdout,
        "stderr": stderr,
        "shell": False,
    }


def start_process(argv: list[str], *, cwd: str | None = None) -> dict[str, Any]:
    if not argv:
        raise ValueError("必须提供要启动的程序。")
    process = subprocess.Popen(
        [str(item) for item in argv],
        cwd=str(resolve_path(cwd)) if cwd else None,
        shell=False,
    )
    return {"ok": True, "pid": process.pid, "argv": [str(item) for item in argv]}


def list_processes() -> dict[str, Any]:
    require_windows()
    completed = subprocess.run(
        ["tasklist.exe", "/fo", "csv", "/nh"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise OSError(completed.stderr.strip() or "Windows 进程列表读取失败。")
    rows: list[dict[str, Any]] = []
    for row in csv.reader(completed.stdout.splitlines()):
        if len(row) < 5:
            continue
        try:
            pid = int(row[1])
        except ValueError:
            continue
        rows.append(
            {
                "name": row[0],
                "pid": pid,
                "session": row[2],
                "session_number": row[3],
                "memory": row[4],
            }
        )
    return {"ok": True, "processes": rows, "count": len(rows)}


def stop_process(pid: int, *, force: bool = False, tree: bool = False) -> dict[str, Any]:
    require_windows()
    target_pid = int(pid)
    if target_pid <= 4 or target_pid == os.getpid():
        raise ValueError("拒绝终止系统核心进程或当前 T One CLI 进程。")
    command = ["taskkill.exe", "/pid", str(target_pid)]
    if tree:
        command.append("/t")
    if force:
        command.append("/f")
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=30,
    )
    return {
        "ok": completed.returncode == 0,
        "pid": target_pid,
        "returncode": int(completed.returncode),
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def list_windows() -> dict[str, Any]:
    require_windows()
    user32 = ctypes.windll.user32
    records: list[dict[str, Any]] = []
    enum_callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = int(user32.GetWindowTextLengthW(hwnd))
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        records.append({"title": buffer.value, "hwnd": int(hwnd), "pid": int(pid.value)})
        return True

    user32.EnumWindows(enum_callback(callback), 0)
    return {"ok": True, "windows": records, "count": len(records)}


def relaunch_elevated(
    arguments: list[str], *, root: str | os.PathLike[str] | None = None
) -> dict[str, Any]:
    require_windows()
    if is_administrator():
        return {"ok": True, "already_administrator": True, "launched": False}
    forwarded = [str(item) for item in arguments]
    if bool(getattr(sys, "frozen", False)):
        workspace = resolve_path(root or Path.cwd())
        params = subprocess.list2cmdline(
            ["cli", "--root", str(workspace), "--", *forwarded]
        )
    else:
        params = subprocess.list2cmdline(
            ["-m", "ai_ecommerce_director.tone_cli", *forwarded]
        )
    result = int(
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            params,
            str(Path.cwd()),
            1,
        )
        or 0
    )
    if result <= 32:
        raise OSError(f"Windows 管理员授权未启动，ShellExecuteW={result}。")
    return {
        "ok": True,
        "already_administrator": False,
        "launched": True,
        "permission_source": "windows_uac",
    }


def decode_json_env(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("--env-json 必须是 JSON 对象。")
    return {str(key): str(value) for key, value in payload.items()}
