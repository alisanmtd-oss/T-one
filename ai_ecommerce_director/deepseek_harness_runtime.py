"""DeepSeek Harness discovery and the T One MCP capability gateway.

The Harness remains an independently installed, MIT-licensed runtime.  T One
does not copy or fork it.  Instead, every project gets a tiny Cordis patch that
mounts one local stdio MCP server.  That server reuses T One's existing desktop
bridge and computer-control implementations, so business modules keep one
source of truth while DeepSeek Harness becomes an additional orchestration
foundation.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import shutil
import sys
import time
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, TextIO

from . import desktop_control


OFFICIAL_REPOSITORY = "github.com/deepseek-ai/deepseek-harness"
OFFICIAL_SOURCE_COMMIT = "47f943859bef60e4160492346772ded9b24f765a"
PACKAGE_NAME = "@deepseek-ai/dsh"
MCP_PLUGIN_NAME = "@deepseek-ai/dsh-mcp-client"


def _unique_existing(paths: Iterable[Path], *, directory: bool | None = None) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for value in paths:
        path = Path(value).expanduser()
        try:
            resolved = path.resolve()
        except OSError:
            continue
        key = str(resolved).casefold()
        if key in seen or not resolved.exists():
            continue
        if directory is True and not resolved.is_dir():
            continue
        if directory is False and not resolved.is_file():
            continue
        seen.add(key)
        found.append(resolved)
    return found


def _default_node_candidates() -> list[Path]:
    candidates: list[Path] = []
    for executable in ("node.exe", "node"):
        located = shutil.which(executable)
        if located:
            candidates.append(Path(located))
    workbuddy_versions = Path.home() / ".workbuddy" / "binaries" / "node" / "versions"
    if workbuddy_versions.is_dir():
        candidates.extend(sorted(workbuddy_versions.glob("*/node.exe"), reverse=True))
    return _unique_existing(candidates, directory=False)


def _default_package_candidates(nodes: Iterable[Path]) -> list[Path]:
    candidates: list[Path] = []
    for node in nodes:
        candidates.append(node.parent / "node_modules" / "@deepseek-ai" / "dsh")
    appdata = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    candidates.append(appdata / "npm" / "node_modules" / "@deepseek-ai" / "dsh")
    return _unique_existing(candidates, directory=True)


def _default_home_candidates() -> list[Path]:
    candidates: list[Path] = []
    configured = str(os.environ.get("DSH_HOME") or "").strip()
    if configured:
        candidates.append(Path(configured))
    # WorkBuddy currently installs the official preview here.  Older installs
    # used ~/.dsh, so both are detected without trusting the Bash launcher.
    candidates.extend((Path.home() / "Projects" / ".dsh", Path.home() / ".dsh"))
    return _unique_existing(candidates, directory=True)


@dataclass(frozen=True)
class DeepSeekHarnessRuntime:
    node_path: Path | None = None
    package_root: Path | None = None
    home: Path | None = None
    metadata: dict[str, Any] | None = None

    @classmethod
    def discover(
        cls,
        *,
        node_candidates: Iterable[Path] | None = None,
        package_candidates: Iterable[Path] | None = None,
        home_candidates: Iterable[Path] | None = None,
    ) -> "DeepSeekHarnessRuntime":
        nodes = _unique_existing(
            list(node_candidates) if node_candidates is not None else _default_node_candidates(),
            directory=False,
        )
        packages = _unique_existing(
            list(package_candidates)
            if package_candidates is not None
            else _default_package_candidates(nodes),
            directory=True,
        )
        homes = _unique_existing(
            list(home_candidates) if home_candidates is not None else _default_home_candidates(),
            directory=True,
        )

        package_root: Path | None = None
        metadata: dict[str, Any] | None = None
        for candidate in packages:
            package_json = candidate / "package.json"
            entrypoint = candidate / "lib" / "bin.js"
            if not package_json.is_file() or not entrypoint.is_file():
                continue
            try:
                payload = json.loads(package_json.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if str(payload.get("name") or "") != PACKAGE_NAME:
                continue
            package_root = candidate
            metadata = payload
            break

        node_path = nodes[0] if nodes else None
        if package_root is not None:
            adjacent = package_root.parents[2] / "node.exe" if len(package_root.parents) >= 3 else None
            if adjacent is not None and adjacent.is_file():
                node_path = adjacent.resolve()
        home = next((item for item in homes if (item / "profiles").is_dir()), homes[0] if homes else None)
        return cls(node_path=node_path, package_root=package_root, home=home, metadata=metadata)

    @property
    def installed(self) -> bool:
        return bool(
            self.node_path
            and self.node_path.is_file()
            and self.package_root
            and (self.package_root / "lib" / "bin.js").is_file()
            and self.metadata
        )

    def status(self) -> dict[str, Any]:
        metadata = dict(self.metadata or {})
        repository = metadata.get("repository") or {}
        repository_url = repository.get("url") if isinstance(repository, dict) else repository
        repository_url = str(repository_url or "")
        version = str(metadata.get("version") or "")
        profiles: list[str] = []
        if self.home and (self.home / "profiles").is_dir():
            profiles = sorted(
                item.name
                for item in (self.home / "profiles").iterdir()
                if item.is_dir() and (item / "package.json").is_file()
            )
        return {
            "ok": self.installed,
            "installed": self.installed,
            "name": PACKAGE_NAME if self.installed else "",
            "version": version,
            "license": str(metadata.get("license") or ""),
            "repository": repository_url,
            "official_repository": OFFICIAL_REPOSITORY in repository_url.casefold(),
            "official_source_commit": OFFICIAL_SOURCE_COMMIT,
            "developer_preview": bool("-rc." in version or version.startswith("0.")),
            "node_path": str(self.node_path or ""),
            "entrypoint": str((self.package_root / "lib" / "bin.js") if self.package_root else ""),
            "home": str(self.home or ""),
            "profiles": profiles,
            "web_ready": self.installed and "web" in profiles,
            "integration": "tone_mcp_stdio",
            "computer_control": desktop_control.desktop_control_snapshot(),
        }

    def command(
        self,
        mode: str = "web",
        *,
        workspace: Path | None = None,
        patch_path: Path | None = None,
        extra_args: Iterable[str] = (),
    ) -> list[str]:
        if not self.installed or not self.node_path or not self.package_root:
            raise FileNotFoundError("DeepSeek Harness is not installed or its Node entrypoint is unavailable.")
        profile = str(mode or "web").strip() or "web"
        command = [str(self.node_path), str(self.package_root / "lib" / "bin.js"), "--profile", profile]
        if patch_path is not None:
            command.extend(("--patch", str(Path(patch_path).resolve())))
        command.extend(str(value) for value in extra_args)
        return command

    @staticmethod
    def _available_port(preferred: int = 3080) -> int:
        for port in range(max(1024, int(preferred)), max(1024, int(preferred)) + 40):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    probe.bind(("127.0.0.1", port))
                except OSError:
                    continue
                return port
        raise OSError("DeepSeek Harness 没有找到可用的本机端口。")

    @staticmethod
    def _post_local_rpc(url: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(
            {
                "type": "client-request",
                "rpcId": str(uuid.uuid4()),
                "method": method,
                "payload": payload,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{url.rstrip('/')}/api/{method}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=4) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not isinstance(result, dict):
            raise RuntimeError(f"DeepSeek Harness {method} 返回格式无效。")
        rpc_result = result.get("result")
        if not isinstance(rpc_result, dict) or rpc_result.get("ok") is not True:
            error = rpc_result.get("error") if isinstance(rpc_result, dict) else None
            raise RuntimeError(f"DeepSeek Harness {method} 失败：{error or 'unknown error'}")
        return dict(rpc_result.get("value") or {})

    @staticmethod
    def _attach_windows_kill_job(process: subprocess.Popen[Any]) -> None:
        """Make Harness and every MCP child die if the T One backend exits."""

        if os.name != "nt":
            return
        import ctypes
        from ctypes import wintypes

        class BasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimitInformation),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimitInformation()
        limits.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.get_last_error()
            kernel32.CloseHandle(job)
            raise ctypes.WinError(error)
        process_handle = wintypes.HANDLE(int(getattr(process, "_handle")))
        if not kernel32.AssignProcessToJobObject(job, process_handle):
            error = ctypes.get_last_error()
            kernel32.CloseHandle(job)
            raise ctypes.WinError(error)
        setattr(process, "_tone_windows_job", job)

    @staticmethod
    def stop_project_web(process: subprocess.Popen[Any], *, timeout: float = 4) -> None:
        job = getattr(process, "_tone_windows_job", None)
        if job and os.name == "nt":
            import ctypes

            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(job)
            setattr(process, "_tone_windows_job", None)
        elif process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=timeout)

    def start_project_web(
        self,
        project_root: Path,
        *,
        patch_path: Path,
        preferred_port: int = 3080,
        kill_with_parent: bool = True,
    ) -> tuple[subprocess.Popen[Any], dict[str, Any]]:
        """Start the official local web profile and register one T One folder."""

        if not self.home or not (self.home / "profiles" / "web").is_dir():
            raise FileNotFoundError("DeepSeek Harness 的 web profile 不可用。")
        root = Path(project_root).resolve()
        port = self._available_port(preferred_port)
        url = f"http://127.0.0.1:{port}"
        command = self.command(
            "web",
            workspace=root,
            patch_path=patch_path,
            extra_args=("--host", "127.0.0.1", "--port", str(port)),
        )
        environment = os.environ.copy()
        environment["DSH_HOME"] = str(self.home)
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0
        process = subprocess.Popen(
            command,
            cwd=str(root),
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        if kill_with_parent:
            try:
                self._attach_windows_kill_job(process)
            except OSError:
                process.terminate()
                process.wait(timeout=4)
                raise
        deadline = time.monotonic() + 15
        last_error = ""
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"DeepSeek Harness 启动失败，退出码 {process.returncode}。")
            try:
                self._post_local_rpc(url, "workspace.list", {})
                break
            except (OSError, RuntimeError, ValueError) as exc:
                last_error = str(exc)
                time.sleep(0.2)
        else:
            self.stop_project_web(process)
            raise RuntimeError(f"DeepSeek Harness 启动超时：{last_error or 'local API unavailable'}")
        registered = self._post_local_rpc(url, "workspace.create", {"path": str(root)})
        return process, {
            "ok": True,
            "pid": process.pid,
            "url": url,
            "project_root": str(root),
            "patch_path": str(Path(patch_path).resolve()),
            "workspace": registered.get("workspace") if isinstance(registered, dict) else {},
            "external_actions": 0,
        }

    def prepare_project(
        self,
        project_root: Path,
        *,
        python_executable: str | None = None,
    ) -> dict[str, Any]:
        if not self.installed:
            raise FileNotFoundError("DeepSeek Harness is not installed.")
        root = Path(project_root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        integration_root = root / ".tone" / "deepseek-harness"
        integration_root.mkdir(parents=True, exist_ok=True)
        patch_path = integration_root / "tone-mcp.patch.yml"
        manifest_path = integration_root / "integration.json"

        executable = str(python_executable or sys.executable)
        if getattr(sys, "frozen", False) and Path(executable).resolve() == Path(sys.executable).resolve():
            args = ["harness-mcp", "--root", str(root)]
            environment: dict[str, str] = {"PYTHONUTF8": "1"}
        else:
            args = ["-m", "ai_ecommerce_director.deepseek_harness_mcp", "--root", str(root)]
            source_root = Path(__file__).resolve().parents[1]
            environment = {"PYTHONUTF8": "1", "PYTHONPATH": str(source_root)}

        mcp_server = {
            "serverName": "tone",
            "transport": "stdio",
            "command": executable,
            "args": args,
            "cwd": str(root),
            "env": environment,
            "failOnStartupError": True,
        }
        quote = lambda value: json.dumps(str(value), ensure_ascii=False)
        yaml_lines = [
            "- insert:",
            "    - id: tone-mcp",
            f"      name: {quote(MCP_PLUGIN_NAME)}",
            "      config:",
            "        serverName: tone",
            "        transport: stdio",
            f"        command: {quote(executable)}",
            "        args:",
            *[f"          - {quote(value)}" for value in args],
            f"        cwd: {quote(root)}",
            "        env:",
            *[f"          {key}: {quote(value)}" for key, value in environment.items()],
            "        failOnStartupError: true",
            "",
        ]
        patch_path.write_text("\n".join(yaml_lines), encoding="utf-8")

        status = self.status()
        payload = {
            "schema_version": 1,
            "foundation": "deepseek_harness",
            "transport": "mcp_stdio",
            "harness": {
                "name": status.get("name"),
                "version": status.get("version"),
                "license": status.get("license"),
                "official_repository": status.get("official_repository"),
                "official_source_commit": status.get("official_source_commit"),
                "developer_preview": status.get("developer_preview"),
            },
            "project_root": str(root),
            "patch_path": str(patch_path),
            "manifest_path": str(manifest_path),
            "mcp_server": mcp_server,
            "tool_namespace": "mcp__tone__",
            "capabilities": [
                "all_allowed_tone_desktop_methods",
                "mouse",
                "keyboard",
                "window",
                "browser",
                "project_and_task_folders",
                "skills_agents_mcp_cli",
            ],
        }
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload


class DeepSeekHarnessToolGateway:
    """Expose the existing T One bridge as one MCP tool namespace."""

    _COMPUTER_TOOLS = {
        "tone_desktop_mouse": "desktop_mouse_action",
        "tone_desktop_keyboard": "desktop_keyboard_action",
        "tone_desktop_window": "desktop_window_action",
        "tone_browser": "desktop_browser_action",
    }
    _CONFIRM_METHODS = {
        "configure_ai_provider",
        "confirm_operating_expense",
        "desktop_browser_action",
        "desktop_keyboard_action",
        "desktop_mouse_action",
        "desktop_window_action",
        "install_capability_pack",
        "open_store_surface",
        "open_store_surfaces_parallel",
        "run_browser_ai_roundtrip",
        "run_cli_ai_roundtrip",
        "run_multi_ai_collaboration",
        "set_subaccount_active",
        "start_task_instruction",
        "test_ai_provider",
    }

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root).resolve() if root is not None else None
        self._api: Any | None = None

    @staticmethod
    def _tool(name: str, description: str, properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
        return {
            "name": name,
            "description": description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": list(required or []),
                "additionalProperties": True,
            },
        }

    def list_tools(self) -> list[dict[str, Any]]:
        confirmation = {"owner_confirmed": {"type": "boolean", "description": "用户已确认本次真实操作"}}
        return [
            self._tool("tone_desktop_snapshot", "读取当前 Windows 鼠标、键盘、窗口和浏览器控制能力。", {}),
            self._tool(
                "tone_desktop_mouse",
                "调用 T One 的真实鼠标控制。",
                {
                    "action": {"type": "string", "enum": ["move", "click", "double_click", "right_click", "middle_click", "scroll"]},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "delta": {"type": "integer"},
                    **confirmation,
                },
                ["action", "owner_confirmed"],
            ),
            self._tool(
                "tone_desktop_keyboard",
                "调用 T One 的真实键盘输入、按键或组合键。",
                {
                    "action": {"type": "string", "enum": ["type", "press", "hotkey"]},
                    "text": {"type": "string"},
                    "key": {"type": "string"},
                    "keys": {"type": "array", "items": {"type": "string"}},
                    **confirmation,
                },
                ["action", "owner_confirmed"],
            ),
            self._tool(
                "tone_desktop_window",
                "聚焦一个真实 Windows 窗口。",
                {"action": {"type": "string", "enum": ["focus"]}, "title": {"type": "string"}, **confirmation},
                ["action", "owner_confirmed"],
            ),
            self._tool(
                "tone_browser",
                "使用 T One 的浏览器入口打开地址或准备隔离配置。",
                {"action": {"type": "string", "enum": ["open_url", "prepare_profile"]}, "url": {"type": "string"}, **confirmation},
                ["action", "owner_confirmed"],
            ),
            self._tool("tone_methods", "列出 Harness 可以复用的全部 T One 桌面模块方法。", {}),
            self._tool(
                "tone_invoke",
                "调用一个现有 T One 模块方法；高影响方法必须显式确认。",
                {
                    "method": {"type": "string"},
                    "args": {"type": "array"},
                    **confirmation,
                },
                ["method"],
            ),
        ]

    def _desktop_methods(self) -> list[str]:
        from desktop_app.bridge import ALLOWED_METHODS

        return sorted(ALLOWED_METHODS)

    def _desktop_api(self) -> Any:
        if self.root is None:
            raise ValueError("A T One project root is required for module calls.")
        if self._api is None:
            from desktop_app.teelab_desktop import DesktopApi

            self._api = DesktopApi(self.root)
            self._api.start_runtime_recovery()
        return self._api

    @staticmethod
    def _require_confirmation(arguments: dict[str, Any]) -> None:
        if arguments.get("owner_confirmed") is not True:
            raise PermissionError("This real computer action requires owner_confirmed=true.")

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        tool_name = str(name or "").strip()
        payload = dict(arguments or {})
        if tool_name == "tone_desktop_snapshot":
            return desktop_control.desktop_control_snapshot()
        if tool_name in self._COMPUTER_TOOLS:
            self._require_confirmation(payload)
            action = getattr(desktop_control, self._COMPUTER_TOOLS[tool_name])
            return action(payload)
        if tool_name == "tone_methods":
            return {"ok": True, "methods": self._desktop_methods()}
        if tool_name == "tone_invoke":
            from desktop_app.bridge import dispatch

            method = str(payload.get("method") or "").strip()
            if method not in self._desktop_methods():
                raise ValueError(f"Desktop method is not allowed: {method}")
            if method in self._CONFIRM_METHODS:
                self._require_confirmation(payload)
            args = payload.get("args")
            call_args = list(args) if isinstance(args, list) else []
            if payload.get("owner_confirmed") is True and call_args and isinstance(call_args[0], dict):
                call_args[0] = {**call_args[0], "owner_confirmed": True}
            return dispatch(self._desktop_api(), method, call_args)
        raise ValueError(f"Unknown T One Harness tool: {tool_name}")

    def close(self) -> None:
        if self._api is not None:
            self._api.stop_runtime_recovery()
            self._api = None


def run_mcp_stdio(root: Path, *, stdin: TextIO | None = None, stdout: TextIO | None = None) -> int:
    input_stream = stdin or sys.stdin
    output_stream = stdout or sys.stdout
    gateway = DeepSeekHarnessToolGateway(root)

    def emit(payload: dict[str, Any]) -> None:
        output_stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        output_stream.flush()

    try:
        for raw_line in input_stream:
            line = raw_line.strip()
            if not line:
                continue
            request_id: Any = None
            try:
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError("MCP request must be a JSON object.")
                request_id = request.get("id")
                method = str(request.get("method") or "")
                params = request.get("params") if isinstance(request.get("params"), dict) else {}
                if method == "initialize":
                    requested = str(params.get("protocolVersion") or "2025-06-18")
                    result = {
                        "protocolVersion": requested,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "t-one-deepseek-harness", "version": "1"},
                    }
                elif method == "ping":
                    result = {}
                elif method == "tools/list":
                    result = {"tools": gateway.list_tools()}
                elif method == "tools/call":
                    tool_name = str(params.get("name") or "")
                    arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
                    value = gateway.call_tool(tool_name, arguments)
                    structured = value if isinstance(value, dict) else {"value": value}
                    result = {
                        "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}],
                        "structuredContent": structured,
                        "isError": False,
                    }
                elif method.startswith("notifications/"):
                    continue
                else:
                    raise ValueError(f"Unsupported MCP method: {method}")
                if request_id is not None:
                    emit({"jsonrpc": "2.0", "id": request_id, "result": result})
            except Exception as exc:
                if request_id is not None:
                    emit(
                        {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {"code": -32603, "message": str(exc)},
                        }
                    )
    finally:
        gateway.close()
    return 0


def main_mcp(argv: list[str] | None = None) -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="strict")
    parser = argparse.ArgumentParser(description="T One MCP gateway for DeepSeek Harness")
    parser.add_argument("--root", required=True)
    args = parser.parse_args(argv)
    return run_mcp_stdio(Path(args.root).resolve())
