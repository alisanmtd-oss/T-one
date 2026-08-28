from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONFIG_PATH = Path("config") / "selection_tool_stack.json"


def load_selection_tool_stack(root: Path) -> dict[str, Any]:
    path = root / CONFIG_PATH
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def safe_tool_source_label(api_source_id: str) -> str:
    source_id = str(api_source_id or "").strip()
    if not source_id:
        return "无外部 API 绑定"
    if "placeholder" in source_id.lower():
        return "候选连接，待确认接口和授权"
    return "已登记连接配置，待授权或只读验证"


def safe_tool_status_label(status: str) -> str:
    value = str(status or "").strip().lower()
    if "connect_after" in value:
        return "授权后接入"
    if "recommended_first" in value:
        return "优先研究/采购候选"
    if "operator_tool" in value:
        return "人工/浏览器辅助工具"
    if "buy_later" in value:
        return "后续按规模再评估"
    return "候选工具"


def summarize_selection_tools(root: Path) -> list[dict[str, str]]:
    payload = load_selection_tool_stack(root)
    tools = payload.get("tools", []) if isinstance(payload, dict) else []
    rows: list[dict[str, str]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        rows.append(
            {
                "name": str(tool.get("name") or "未命名工具"),
                "platform": str(tool.get("platform") or "未指定平台"),
                "priority": str(tool.get("priority") or ""),
                "role": str(tool.get("role") or ""),
                "status": safe_tool_status_label(str(tool.get("status") or "")),
                "connection": safe_tool_source_label(str(tool.get("api_source_id") or "")),
                "method": str(tool.get("integration_method") or ""),
            }
        )
    return sorted(rows, key=lambda item: int(item["priority"] or 9999))


def build_selection_tool_stack_report(root: Path, limit: int = 14) -> str:
    rows = summarize_selection_tools(root)[:limit]
    lines = [
        "## 选品/广告工具栈安全摘要",
        "",
        "- 这是一份后台 AI 的工具优先级和接入边界，不代表工具已经购买、登录或 API 已经打通。",
        "- 候选接口、占位接口和未授权接口只显示为待确认，不作为真实店铺数据来源。",
        "- 广告工具、店铺 API 和第三方榜单工具必须按平台、国家站点、店铺模式、执行身份隔离。",
        "",
    ]
    if not rows:
        lines.append("- 暂无工具栈配置。")
        return "\n".join(lines).rstrip() + "\n"
    for row in rows:
        parts = [
            f"{row['name']} / {row['platform']}",
            row["status"],
            row["connection"],
        ]
        if row["method"]:
            parts.append(f"接入方式：{row['method']}")
        lines.append("- " + "；".join(part for part in parts if part))
    return "\n".join(lines).rstrip() + "\n"
