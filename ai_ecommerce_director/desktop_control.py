"""Real, local Windows mouse, keyboard, and browser primitives.

The module exposes a deliberately small execution surface for the existing
desktop bridge.  Every mutation is a foreground, owner-confirmed call; there is
no background hook, key logger, shell execution, or credential capture.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import time
import urllib.parse
import webbrowser
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_TEXT_LENGTH = 4000
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
_DPI_AWARE = False


class _KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _InputUnion(ctypes.Union):
    _fields_ = [
        ("mi", _MouseInput),
        ("ki", _KeyboardInput),
        ("hi", _HardwareInput),
    ]


class _Input(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _InputUnion)]


KEY_CODES = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
    "escape": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "delete": 0x2E,
    "win": 0x5B,
}
KEY_CODES.update({f"f{index}": 0x6F + index for index in range(1, 13)})
KEY_CODES.update({chr(code).lower(): code for code in range(ord("A"), ord("Z") + 1)})
KEY_CODES.update({str(index): 0x30 + index for index in range(10)})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_windows() -> Any:
    global _DPI_AWARE
    if os.name != "nt":
        raise RuntimeError("本机控制当前只支持 Windows。")
    user32 = ctypes.windll.user32
    if not _DPI_AWARE:
        try:
            user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            try:
                user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass
        _DPI_AWARE = True
    return user32


def _require_confirmation(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict) or payload.get("owner_confirmed") is not True:
        raise ValueError("本次本机操作需要负责人明确确认。")


def _action_id(kind: str, payload: dict[str, Any]) -> str:
    raw = json.dumps(
        {"kind": kind, "time": _utc_now(), "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
    )
    return "desktop-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _wait_for_foreground_switch(payload: dict[str, Any]) -> int:
    try:
        delay_ms = int(payload.get("delay_ms") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("delay_ms 必须是整数。") from exc
    if not 0 <= delay_ms <= 10000:
        raise ValueError("delay_ms 必须在 0–10000 之间。")
    if delay_ms:
        time.sleep(delay_ms / 1000)
    return delay_ms


def _screen_bounds(user32: Any) -> tuple[int, int, int, int]:
    left = int(user32.GetSystemMetrics(76))
    top = int(user32.GetSystemMetrics(77))
    width = int(user32.GetSystemMetrics(78))
    height = int(user32.GetSystemMetrics(79))
    if width <= 0 or height <= 0:
        left, top = 0, 0
        width = int(user32.GetSystemMetrics(0))
        height = int(user32.GetSystemMetrics(1))
    return left, top, width, height


def desktop_control_snapshot() -> dict[str, Any]:
    if os.name != "nt":
        return {
            "ok": True,
            "platform": os.name,
            "available": False,
            "mouse": False,
            "keyboard": False,
            "browser": bool(webbrowser.get()),
        }
    user32 = _require_windows()
    point = wintypes.POINT()
    cursor_ok = bool(user32.GetCursorPos(ctypes.byref(point)))
    left, top, width, height = _screen_bounds(user32)
    return {
        "ok": True,
        "platform": "windows",
        "available": True,
        "mouse": True,
        "keyboard": True,
        "browser": True,
        "cursor": {"x": int(point.x), "y": int(point.y)} if cursor_ok else None,
        "screen": {"left": left, "top": top, "width": width, "height": height},
        "supported_mouse_actions": ["move", "click", "double_click", "right_click", "middle_click", "scroll"],
        "supported_keyboard_actions": ["type", "press", "hotkey"],
        "supported_window_actions": ["focus"],
        "supported_browser_actions": ["open_url", "prepare_profile"],
        "background_capture": False,
        "key_logging": False,
    }


def _find_window_exact(user32: Any, title: str) -> int:
    title = str(title or "").strip()
    if not title or len(title) > 240:
        raise ValueError("窗口标题长度必须为 1–240 个字符。")
    user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    user32.FindWindowW.restype = ctypes.c_void_p
    hwnd = int(user32.FindWindowW(None, title) or 0)
    if not hwnd:
        raise ValueError("没有找到标题完全匹配的可见窗口。")
    return hwnd


def desktop_window_action(payload: dict[str, Any]) -> dict[str, Any]:
    _require_confirmation(payload)
    user32 = _require_windows()
    action = str(payload.get("action") or "").strip().lower()
    if action != "focus":
        raise ValueError("当前窗口控制只支持 focus。")
    hwnd = _find_window_exact(user32, str(payload.get("title") or ""))
    user32.ShowWindow(ctypes.c_void_p(hwnd), 9)

    foreground = int(user32.GetForegroundWindow() or 0)
    current_thread = int(ctypes.windll.kernel32.GetCurrentThreadId())
    target_thread = int(user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), None))
    foreground_thread = int(
        user32.GetWindowThreadProcessId(ctypes.c_void_p(foreground), None)
    ) if foreground else 0
    attached: list[tuple[int, int]] = []
    try:
        for source_thread in {current_thread, foreground_thread}:
            if source_thread and target_thread and source_thread != target_thread:
                if user32.AttachThreadInput(source_thread, target_thread, True):
                    attached.append((source_thread, target_thread))
        user32.BringWindowToTop(ctypes.c_void_p(hwnd))
        user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
        user32.SetFocus(ctypes.c_void_p(hwnd))
    finally:
        for source_thread, destination_thread in reversed(attached):
            user32.AttachThreadInput(source_thread, destination_thread, False)

    if int(user32.GetForegroundWindow() or 0) != hwnd:
        # A synthetic Alt press releases Windows' foreground lock for a
        # user-confirmed one-shot focus request without installing a hook.
        _press_virtual_key(user32, KEY_CODES["alt"])
        _press_virtual_key(user32, KEY_CODES["alt"], key_up=True)
        user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
    if int(user32.GetForegroundWindow() or 0) != hwnd:
        raise OSError("Windows 拒绝将目标窗口置于前台。")
    return {
        "ok": True,
        "action_id": _action_id("window", payload),
        "action": action,
        "window_title": str(payload.get("title") or ""),
        "hwnd": hwnd,
    }


def desktop_mouse_action(payload: dict[str, Any]) -> dict[str, Any]:
    _require_confirmation(payload)
    user32 = _require_windows()
    action = str(payload.get("action") or "").strip().lower()
    supported = {"move", "click", "double_click", "right_click", "middle_click", "scroll"}
    if action not in supported:
        raise ValueError("不支持的鼠标动作。")
    _wait_for_foreground_switch(payload)
    left, top, width, height = _screen_bounds(user32)
    if action != "scroll":
        try:
            x, y = int(payload.get("x")), int(payload.get("y"))
        except (TypeError, ValueError) as exc:
            raise ValueError("鼠标动作需要整数坐标 x/y。") from exc
        if not left <= x < left + width or not top <= y < top + height:
            raise ValueError("鼠标坐标超出当前桌面范围。")
        if not user32.SetCursorPos(x, y):
            raise OSError("Windows 未能移动鼠标。")
    if action == "move":
        pass
    elif action in {"click", "double_click"}:
        count = 2 if action == "double_click" else 1
        for _ in range(count):
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            if count == 2:
                time.sleep(0.08)
    elif action == "right_click":
        user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
    elif action == "middle_click":
        user32.mouse_event(MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)
    else:
        delta = max(-1200, min(1200, int(payload.get("delta") or 0)))
        if delta == 0:
            raise ValueError("滚轮动作需要非零 delta。")
        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
    return {"ok": True, "action_id": _action_id("mouse", payload), "action": action}


def _key_code(raw_key: object) -> int:
    key = str(raw_key or "").strip().lower()
    if key not in KEY_CODES:
        raise ValueError(f"不支持的按键：{key or 'empty'}")
    return KEY_CODES[key]


def _press_virtual_key(user32: Any, key_code: int, *, key_up: bool = False) -> None:
    user32.keybd_event(key_code, 0, KEYEVENTF_KEYUP if key_up else 0, 0)


def _type_unicode(user32: Any, text: str) -> None:
    for character in text:
        code = ord(character)
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            event = _Input(
                type=1,
                union=_InputUnion(
                    ki=_KeyboardInput(
                        wVk=0,
                        wScan=code,
                        dwFlags=flags,
                        time=0,
                        dwExtraInfo=0,
                    )
                ),
            )
            if int(user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(_Input))) != 1:
                raise OSError("Windows 未能发送文本输入。")


def desktop_keyboard_action(payload: dict[str, Any]) -> dict[str, Any]:
    _require_confirmation(payload)
    user32 = _require_windows()
    action = str(payload.get("action") or "").strip().lower()
    _wait_for_foreground_switch(payload)
    if action == "type":
        text = str(payload.get("text") or "")
        if not text or len(text) > MAX_TEXT_LENGTH:
            raise ValueError(f"输入文本长度必须为 1–{MAX_TEXT_LENGTH} 个字符。")
        _type_unicode(user32, text)
    elif action == "press":
        key_code = _key_code(payload.get("key"))
        _press_virtual_key(user32, key_code)
        _press_virtual_key(user32, key_code, key_up=True)
    elif action == "hotkey":
        keys = payload.get("keys")
        if not isinstance(keys, list) or not 2 <= len(keys) <= 4:
            raise ValueError("组合键需要 2–4 个按键。")
        codes = [_key_code(key) for key in keys]
        for code in codes:
            _press_virtual_key(user32, code)
        for code in reversed(codes):
            _press_virtual_key(user32, code, key_up=True)
    else:
        raise ValueError("不支持的键盘动作。")
    return {"ok": True, "action_id": _action_id("keyboard", payload), "action": action}


def desktop_browser_action(payload: dict[str, Any]) -> dict[str, Any]:
    _require_confirmation(payload)
    action = str(payload.get("action") or "").strip().lower()
    if action != "open_url":
        raise ValueError("该方法只处理默认浏览器 open_url；受控浏览器请使用 prepare_profile。")
    raw_url = str(payload.get("url") or "").strip()
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("浏览器地址必须是完整的 http/https URL。")
    opened = bool(webbrowser.open(raw_url, new=2, autoraise=True))
    if not opened:
        raise OSError("默认浏览器未接受打开请求。")
    return {
        "ok": True,
        "action_id": _action_id("browser", payload),
        "action": action,
        "url": raw_url,
    }


def append_desktop_control_receipt(root: Path, result: dict[str, Any]) -> str:
    target = root / "runtime_data" / "desktop_control" / "actions.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    record = {"recorded_at": _utc_now(), **result}
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return target.resolve().relative_to(root.resolve()).as_posix()
