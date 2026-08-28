"""T One local CLI for workspace and Windows computer control."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from . import deepseek_harness_runtime, desktop_control, system_control
from .workspace_runtime import (
    create_workspace_project,
    create_workspace_task,
    load_workspace_config,
    project_local_folder,
    task_local_folder,
    workspace_item_local_folder,
)
from .workspace_schema import find_task_context, iter_project_tasks


def _json_default(value: object) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _emit(payload: Any, *, as_json: bool, stream: Any = None) -> None:
    target = stream or sys.stdout
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), file=target)
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                print(f"{key}: {json.dumps(value, ensure_ascii=False, default=_json_default)}", file=target)
            else:
                print(f"{key}: {value}", file=target)
        return
    print(payload, file=target)


def _require_yes(args: argparse.Namespace) -> None:
    if getattr(args, "yes", False) is not True:
        raise PermissionError("本机修改或执行命令需要显式传入 --yes。")


def _exact_argv(raw: Sequence[str]) -> list[str]:
    argv = list(raw)
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        raise ValueError("请在 -- 后提供程序和参数。")
    return argv


def _add_yes(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--yes", action="store_true", help="确认本次本机修改或程序执行。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tone",
        description="T One 本地工作区与 Windows 全机控制 CLI（权限由当前 Windows 令牌决定）",
    )
    parser.add_argument("--version", action="version", version=f"T One {__version__}")
    parser.add_argument("--root", default=os.environ.get("TONE_WORKSPACE_ROOT", "."))
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON。")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("status", help="显示当前权限、电脑控制和工作区状态。")

    workspace = commands.add_parser("workspace", help="访问 T One 项目与任务。")
    workspace_commands = workspace.add_subparsers(dest="workspace_action", required=True)
    workspace_commands.add_parser("list", help="列出项目和任务。")
    workspace_show = workspace_commands.add_parser(
        "show",
        help="查看一个项目或任务及其本地文件夹。",
        description="查看一个项目或任务及其本地文件夹。",
    )
    workspace_show_target = workspace_show.add_mutually_exclusive_group(required=True)
    workspace_show_target.add_argument("--project", help="项目编号。")
    workspace_show_target.add_argument("--task", help="任务编号。")
    project_create = workspace_commands.add_parser("create-project", help="创建项目及本地文件夹。")
    project_create.add_argument("--name", required=True)
    project_create.add_argument("--description", default="")
    _add_yes(project_create)
    task_create = workspace_commands.add_parser("create-task", help="创建任务及本地文件夹。")
    task_create.add_argument("--name", required=True)
    task_create.add_argument("--project", default="")
    task_create.add_argument("--instruction", default="")
    _add_yes(task_create)

    filesystem = commands.add_parser("fs", help="访问 Windows 文件系统。")
    fs_commands = filesystem.add_subparsers(dest="fs_action", required=True)
    fs_list = fs_commands.add_parser("list")
    fs_list.add_argument("path")
    fs_list.add_argument("--recursive", action="store_true")
    fs_list.add_argument("--limit", type=int, default=1000)
    fs_read = fs_commands.add_parser("read")
    fs_read.add_argument("path")
    fs_read.add_argument("--binary", action="store_true")
    fs_read.add_argument("--max-bytes", type=int, default=system_control.MAX_CAPTURE_BYTES)
    fs_write = fs_commands.add_parser("write")
    fs_write.add_argument("path")
    fs_write.add_argument("--text")
    fs_write.add_argument("--base64")
    fs_write.add_argument("--append", action="store_true")
    fs_write.add_argument("--mkdirs", action="store_true")
    _add_yes(fs_write)
    fs_copy = fs_commands.add_parser("copy")
    fs_copy.add_argument("source")
    fs_copy.add_argument("target")
    fs_copy.add_argument("--overwrite", action="store_true")
    _add_yes(fs_copy)
    fs_move = fs_commands.add_parser("move")
    fs_move.add_argument("source")
    fs_move.add_argument("target")
    fs_move.add_argument("--overwrite", action="store_true")
    _add_yes(fs_move)
    fs_delete = fs_commands.add_parser("delete")
    fs_delete.add_argument("path")
    fs_delete.add_argument("--recursive", action="store_true")
    _add_yes(fs_delete)

    process = commands.add_parser("process", help="列出、启动或终止 Windows 进程。")
    process_commands = process.add_subparsers(dest="process_action", required=True)
    process_commands.add_parser("list")
    process_start = process_commands.add_parser("start")
    process_start.add_argument("--cwd")
    process_start.add_argument("argv", nargs=argparse.REMAINDER)
    _add_yes(process_start)
    process_stop = process_commands.add_parser("stop")
    process_stop.add_argument("pid", type=int)
    process_stop.add_argument("--force", action="store_true")
    process_stop.add_argument("--tree", action="store_true")
    _add_yes(process_stop)

    shell = commands.add_parser("shell", help="按原始参数运行任意本地程序。")
    shell_commands = shell.add_subparsers(dest="shell_action", required=True)
    shell_run = shell_commands.add_parser("run")
    shell_run.add_argument("--cwd")
    shell_run.add_argument("--timeout", type=int, default=120)
    shell_run.add_argument("--env-json")
    _add_yes(shell_run)
    shell_run.add_argument("argv", nargs=argparse.REMAINDER)

    mouse = commands.add_parser("mouse", help="控制真实鼠标。")
    mouse.add_argument("action", choices=["move", "click", "double_click", "right_click", "middle_click", "scroll"])
    mouse.add_argument("--x", type=int)
    mouse.add_argument("--y", type=int)
    mouse.add_argument("--delta", type=int, default=0)
    mouse.add_argument("--delay-ms", type=int, default=0)
    _add_yes(mouse)

    keyboard = commands.add_parser("keyboard", help="控制真实键盘。")
    keyboard.add_argument("action", choices=["type", "press", "hotkey"])
    keyboard.add_argument("--text")
    keyboard.add_argument("--key")
    keyboard.add_argument("--keys", nargs="+")
    keyboard.add_argument("--delay-ms", type=int, default=0)
    _add_yes(keyboard)

    window = commands.add_parser("window", help="列出窗口或聚焦指定窗口。")
    window_commands = window.add_subparsers(dest="window_action", required=True)
    window_commands.add_parser("list")
    window_focus = window_commands.add_parser("focus")
    window_focus.add_argument("title")
    _add_yes(window_focus)

    browser = commands.add_parser("browser", help="控制默认浏览器入口。")
    browser_commands = browser.add_subparsers(dest="browser_action", required=True)
    browser_open = browser_commands.add_parser("open")
    browser_open.add_argument("url")
    _add_yes(browser_open)

    harness = commands.add_parser(
        "harness", help="管理官方 DeepSeek Harness 项目底座。"
    )
    harness_commands = harness.add_subparsers(dest="harness_action", required=True)
    harness_commands.add_parser("status", help="检测官方安装、版本和电脑控制接线。")
    for action, help_text in (
        ("prepare", "给项目或任务文件夹写入小型 MCP 接线。"),
        ("web", "启用并启动所选文件夹的 Harness 网页。"),
    ):
        command = harness_commands.add_parser(action, help=help_text)
        target = command.add_mutually_exclusive_group(required=True)
        target.add_argument("--project", help="项目编号。")
        target.add_argument("--task", help="任务编号。")
        if action == "web":
            command.add_argument("--port", type=int, default=3080)
        _add_yes(command)

    elevate = commands.add_parser("elevate", help="显示 Windows UAC 并以管理员权限重启 tone。")
    elevate.add_argument("arguments", nargs=argparse.REMAINDER)
    return parser


def _workspace_list(root: Path) -> dict[str, Any]:
    workspace = load_workspace_config(root)
    projects: list[dict[str, Any]] = []
    for project in workspace.get("projects", []):
        if not isinstance(project, dict):
            continue
        tasks: list[dict[str, str]] = []
        seen_task_ids: set[str] = set()
        for _channel, _store, task in iter_project_tasks(project):
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("id") or "")
            if not task_id or task_id in seen_task_ids:
                continue
            seen_task_ids.add(task_id)
            tasks.append(
                {
                    "id": task_id,
                    "name": str(task.get("name") or ""),
                    "local_folder": _resolved_workspace_relative_folder(
                        root,
                        str(task.get("local_folder") or ""),
                        fallback=task_local_folder(root, {**task, "project_id": project.get("id")}),
                    ),
                    "platform": str(task.get("platform") or ""),
                }
            )
        projects.append(
            {
                "id": str(project.get("id") or ""),
                "name": str(project.get("name") or ""),
                "local_folder": _resolved_workspace_relative_folder(
                    root,
                    str(project.get("local_folder") or ""),
                    fallback=project_local_folder(root, str(project.get("id") or "")),
                ),
                "tasks": tasks,
            }
        )
    standalone = [
        {
            "id": str(task.get("id") or ""),
            "name": str(task.get("name") or ""),
            "local_folder": _resolved_workspace_relative_folder(
                root,
                str(task.get("local_folder") or ""),
                fallback=task_local_folder(root, task),
            ),
        }
        for task in workspace.get("standalone_tasks", [])
        if isinstance(task, dict)
    ]
    return {
        "ok": True,
        "version": __version__,
        "root": str(root),
        "projects": projects,
        "standalone_tasks": standalone,
    }


def _resolved_workspace_relative_folder(
    root: Path, local_folder: str, *, fallback: Path
) -> str:
    """Resolve legacy records to their canonical folder without writing it."""

    root = root.resolve()
    relative = str(local_folder or "").strip().replace("\\", "/")
    candidate = (root / relative).resolve() if relative else fallback.resolve()
    try:
        return candidate.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("项目或任务文件夹必须位于当前 T One 工作区内。") from exc


def _folder_details(root: Path, local_folder: str, manifest_name: str) -> dict[str, Any]:
    relative = str(local_folder or "").strip().replace("\\", "/")
    folder = (root / relative).resolve() if relative else None
    manifest = (folder / manifest_name) if folder else None
    return {
        "local_folder": relative,
        "absolute_folder": str(folder) if folder else "",
        "folder_exists": bool(folder and folder.is_dir()),
        "manifest_path": str(manifest) if manifest else "",
        "manifest_exists": bool(manifest and manifest.is_file()),
    }


def _workspace_show(root: Path, *, project_id: str = "", task_id: str = "") -> dict[str, Any]:
    """Return one canonical project/task record without changing it."""

    workspace = load_workspace_config(root)
    if project_id:
        requested = str(project_id).strip().lower()
        project = next(
            (
                item
                for item in workspace.get("projects", [])
                if isinstance(item, dict)
                and str(item.get("id") or "").strip().lower() == requested
            ),
            None,
        )
        if project is None:
            raise ValueError(f"项目不存在：{project_id}")
        tasks = []
        seen: set[str] = set()
        for _channel, _store, task in iter_project_tasks(project):
            current_id = str(task.get("id") or "")
            if not current_id or current_id in seen:
                continue
            seen.add(current_id)
            tasks.append(
                {
                    "id": current_id,
                    "name": str(task.get("name") or ""),
                    "status": str(task.get("status") or ""),
                    "local_folder": _resolved_workspace_relative_folder(
                        root,
                        str(task.get("local_folder") or ""),
                        fallback=task_local_folder(root, {**task, "project_id": project.get("id")}),
                    ),
                }
            )
        return {
            "ok": True,
            "version": __version__,
            "kind": "project",
            "root": str(root),
            "project": {
                "id": str(project.get("id") or ""),
                "name": str(project.get("name") or ""),
                "description": str(project.get("description") or ""),
                "seller_mode": str(project.get("seller_mode") or ""),
                "task_count": len(tasks),
                "tasks": tasks,
                **_folder_details(
                    root,
                    _resolved_workspace_relative_folder(
                        root,
                        str(project.get("local_folder") or ""),
                        fallback=project_local_folder(root, str(project.get("id") or "")),
                    ),
                    "project.json",
                ),
            },
            "external_actions": 0,
        }

    context = find_task_context(workspace, str(task_id or ""))
    if context is None:
        raise ValueError(f"任务不存在：{task_id}")
    project, channel, store, task = context
    toolkit = task.get("toolkit") if isinstance(task.get("toolkit"), dict) else {}
    return {
        "ok": True,
        "version": __version__,
        "kind": "task",
        "root": str(root),
        "project": {
            "id": str(project.get("id") or ""),
            "name": str(project.get("name") or ""),
        },
        "scope": {
            "channel_id": str((channel or {}).get("id") or ""),
            "store_id": str((store or {}).get("id") or ""),
            "platform": str(task.get("platform") or ""),
            "country": str(task.get("country") or ""),
        },
        "task": {
            "id": str(task.get("id") or ""),
            "name": str(task.get("name") or ""),
            "status": str(task.get("status") or ""),
            "initial_instruction": str(task.get("initial_instruction") or ""),
            "toolkit": toolkit,
            **_folder_details(
                root,
                _resolved_workspace_relative_folder(
                    root,
                    str(task.get("local_folder") or ""),
                    fallback=task_local_folder(
                        root, {**task, "project_id": project.get("id")}
                    ),
                ),
                "task.json",
            ),
        },
        "external_actions": 0,
    }


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    if args.command == "status":
        access = system_control.access_snapshot()
        return {
            **access,
            "version": __version__,
            "root": str(root),
            "root_exists": root.exists(),
            "desktop_control": desktop_control.desktop_control_snapshot(),
            "deepseek_harness": deepseek_harness_runtime.DeepSeekHarnessRuntime.discover().status(),
        }
    if args.command == "workspace":
        if args.workspace_action == "list":
            return _workspace_list(root)
        if args.workspace_action == "show":
            return _workspace_show(
                root,
                project_id=str(args.project or ""),
                task_id=str(args.task or ""),
            )
        _require_yes(args)
        if args.workspace_action == "create-project":
            return create_workspace_project(root, {"name": args.name, "description": args.description})
        return create_workspace_task(
            root,
            {
                "name": args.name,
                "project_id": args.project,
                "standalone": not bool(args.project),
                "platform": "general",
                "initial_instruction": args.instruction,
            },
        )
    if args.command == "fs":
        if args.fs_action == "list":
            return system_control.list_path(args.path, recursive=args.recursive, limit=args.limit)
        if args.fs_action == "read":
            return system_control.read_path(args.path, binary=args.binary, max_bytes=args.max_bytes)
        _require_yes(args)
        if args.fs_action == "write":
            if args.text is not None and args.base64 is not None:
                raise ValueError("--text 和 --base64 只能选择一个。")
            if args.base64 is not None:
                data = base64.b64decode(args.base64, validate=True)
            elif args.text is not None:
                data = args.text.encode("utf-8")
            elif not sys.stdin.isatty():
                data = sys.stdin.buffer.read()
            else:
                raise ValueError("请提供 --text、--base64 或标准输入。")
            return system_control.write_path(args.path, data, append=args.append, create_parents=args.mkdirs)
        if args.fs_action == "copy":
            return system_control.copy_path(args.source, args.target, overwrite=args.overwrite)
        if args.fs_action == "move":
            return system_control.move_path(args.source, args.target, overwrite=args.overwrite)
        return system_control.delete_path(args.path, recursive=args.recursive)
    if args.command == "process":
        if args.process_action == "list":
            return system_control.list_processes()
        _require_yes(args)
        if args.process_action == "start":
            return system_control.start_process(_exact_argv(args.argv), cwd=args.cwd)
        return system_control.stop_process(args.pid, force=args.force, tree=args.tree)
    if args.command == "shell":
        _require_yes(args)
        return system_control.run_exact_argv(
            _exact_argv(args.argv),
            cwd=args.cwd,
            timeout_seconds=args.timeout,
            env=system_control.decode_json_env(args.env_json),
        )
    if args.command == "mouse":
        _require_yes(args)
        return desktop_control.desktop_mouse_action(
            {
                "action": args.action,
                "x": args.x,
                "y": args.y,
                "delta": args.delta,
                "delay_ms": args.delay_ms,
                "owner_confirmed": True,
            }
        )
    if args.command == "keyboard":
        _require_yes(args)
        return desktop_control.desktop_keyboard_action(
            {
                "action": args.action,
                "text": args.text,
                "key": args.key,
                "keys": args.keys,
                "delay_ms": args.delay_ms,
                "owner_confirmed": True,
            }
        )
    if args.command == "window":
        if args.window_action == "list":
            return system_control.list_windows()
        _require_yes(args)
        return desktop_control.desktop_window_action(
            {"action": "focus", "title": args.title, "owner_confirmed": True}
        )
    if args.command == "browser":
        _require_yes(args)
        return desktop_control.desktop_browser_action(
            {"action": "open_url", "url": args.url, "owner_confirmed": True}
        )
    if args.command == "harness":
        runtime = deepseek_harness_runtime.DeepSeekHarnessRuntime.discover()
        if args.harness_action == "status":
            return runtime.status()
        _require_yes(args)
        item_type = "project" if args.project else "task"
        item_id = str(args.project or args.task or "")
        folder, relative_folder = workspace_item_local_folder(root, item_type, item_id)
        prepared = runtime.prepare_project(folder)
        prepared.update(
            {
                "ok": True,
                "item_type": item_type,
                "item_id": item_id,
                "local_folder": relative_folder,
                "external_actions": 0,
            }
        )
        if args.harness_action == "prepare":
            return prepared
        _process, opened = runtime.start_project_web(
            folder,
            patch_path=Path(str(prepared["patch_path"])),
            preferred_port=int(args.port),
            kill_with_parent=False,
        )
        return {**prepared, **opened}
    return system_control.relaunch_elevated(
        _exact_argv(args.arguments) if args.arguments else ["status"], root=root
    )


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        result = dispatch(args)
        _emit(result, as_json=args.json)
        return 0 if not isinstance(result, dict) or result.get("ok", True) else 1
    except (OSError, ValueError, PermissionError, RuntimeError) as exc:
        payload = {"ok": False, "error": str(exc), "error_type": type(exc).__name__}
        _emit(payload, as_json=args.json, stream=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
