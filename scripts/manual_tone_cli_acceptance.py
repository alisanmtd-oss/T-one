from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


WINDOW_TITLE = "T One CLI 本机控制验收"
MARKER = "TONE-CLI-REAL-KEYBOARD-INPUT"


def _target(ready_path: Path, result_path: Path) -> int:
    import ctypes
    import tkinter as tk

    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()
    root = tk.Tk()
    root.title(WINDOW_TITLE)
    root.geometry("540x250+360+220")
    root.resizable(False, False)
    tk.Label(root, text="此窗口只用于验证已打包 T One CLI 的真实鼠标与键盘控制。").pack(
        pady=(28, 14)
    )
    entry = tk.Entry(root, width=58)
    entry.pack(pady=8)

    def finish() -> None:
        result_path.write_text(
            json.dumps({"value": entry.get(), "clicked": True}, ensure_ascii=False),
            encoding="utf-8",
        )
        root.destroy()

    button = tk.Button(root, text="完成验收", command=finish, width=18)
    button.pack(pady=18)
    root.update()
    ready_path.write_text(
        json.dumps(
            {
                "entry": {
                    "x": entry.winfo_rootx() + entry.winfo_width() // 2,
                    "y": entry.winfo_rooty() + entry.winfo_height() // 2,
                },
                "button": {
                    "x": button.winfo_rootx() + button.winfo_width() // 2,
                    "y": button.winfo_rooty() + button.winfo_height() // 2,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    root.after(30000, root.destroy)
    root.mainloop()
    return 0


def _wait_json(path: Path, deadline: float) -> dict[str, object]:
    while time.monotonic() < deadline:
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return payload
            except (OSError, ValueError):
                pass
        time.sleep(0.05)
    raise TimeoutError(f"Timed out waiting for {path.name}")


def _run_cli(runtime: Path, workspace: Path, *arguments: str) -> dict[str, object]:
    completed = subprocess.run(
        [
            str(runtime),
            "cli",
            "--root",
            str(workspace),
            "--",
            "--json",
            *arguments,
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RuntimeError(str(payload))
    return payload


def _run_acceptance(runtime: Path, output: Path) -> int:
    runtime = runtime.resolve()
    if not runtime.is_file():
        raise FileNotFoundError(runtime)
    output.parent.mkdir(parents=True, exist_ok=True)
    child: subprocess.Popen[str] | None = None
    with tempfile.TemporaryDirectory(prefix="tone-cli-control-") as temp_dir:
        temp = Path(temp_dir)
        workspace = temp / "workspace"
        status = _run_cli(runtime, workspace, "status")
        cursor = dict((status.get("desktop_control") or {}).get("cursor") or {})
        ready_path = temp / "ready.json"
        result_path = temp / "result.json"
        try:
            child = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--target",
                    "--ready-path",
                    str(ready_path),
                    "--result-path",
                    str(result_path),
                ]
            )
            ready = _wait_json(ready_path, time.monotonic() + 10)
            _run_cli(runtime, workspace, "window", "focus", WINDOW_TITLE, "--yes")
            time.sleep(0.25)
            entry = dict(ready["entry"])
            button = dict(ready["button"])
            _run_cli(
                runtime,
                workspace,
                "mouse",
                "click",
                "--x",
                str(entry["x"]),
                "--y",
                str(entry["y"]),
                "--yes",
            )
            _run_cli(runtime, workspace, "keyboard", "type", "--text", MARKER, "--yes")
            _run_cli(
                runtime,
                workspace,
                "mouse",
                "click",
                "--x",
                str(button["x"]),
                "--y",
                str(button["y"]),
                "--yes",
            )
            result = _wait_json(result_path, time.monotonic() + 10)
            child.wait(timeout=5)
            child = None
            if result != {"value": MARKER, "clicked": True}:
                raise AssertionError(f"Unexpected packaged CLI control result: {result}")
        finally:
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
            if cursor:
                _run_cli(
                    runtime,
                    workspace,
                    "mouse",
                    "move",
                    "--x",
                    str(cursor.get("x", 0)),
                    "--y",
                    str(cursor.get("y", 0)),
                    "--yes",
                )

    receipt = {
        "status": "PASS",
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "runtime": str(runtime),
        "effective_access": status.get("effective_access"),
        "is_administrator": status.get("is_administrator"),
        "window_focus": True,
        "mouse_real_clicks": 2,
        "keyboard_real_input": MARKER,
        "external_store_actions": 0,
    }
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--target", action="store_true")
    parser.add_argument("--ready-path", type=Path)
    parser.add_argument("--result-path", type=Path)
    args = parser.parse_args()
    if args.target:
        if args.ready_path is None or args.result_path is None:
            parser.error("target mode requires --ready-path and --result-path")
        return _target(args.ready_path, args.result_path)
    if args.runtime is None:
        parser.error("--runtime is required")
    output = args.output or (
        Path(__file__).resolve().parents[1]
        / "outputs"
        / "ui_acceptance"
        / "tone_cli_formal_acceptance_latest.json"
    )
    return _run_acceptance(args.runtime, output)


if __name__ == "__main__":
    raise SystemExit(main())
