"""Task-scoped Agent and Skill marketplace data for the desktop workspace."""

from __future__ import annotations

import json
from pathlib import Path
import re
import tomllib
from typing import Any

from .cli_ai_connector import cli_ai_connector_snapshot
from .commerce_schema import default_commerce_data_schema
from .deepseek_harness_runtime import DeepSeekHarnessRuntime
from .open_tool_registry import open_tool_registry_snapshot
from .project_capability_profiles import project_capability_profile_snapshot
from .skill_agents import list_skill_agents
from .workspace_runtime import load_workspace_config
from .workspace_schema import iter_project_tasks


CAPABILITY_CATEGORY_LABELS: dict[str, dict[str, str]] = {
    "agent": {
        "research_selection": "调研与选品",
        "content_listing": "内容与商品",
        "growth_marketing": "增长与营销",
        "store_fulfillment": "店铺与履约",
        "finance_risk": "财务与风控",
        "management_automation": "管理与自动化",
    },
    "skill": {
        "platform_operations": "平台运营",
        "research_selection": "调研与选品",
        "content_listing": "内容与上架",
        "data_automation": "数据与自动化",
        "finance_risk": "财务与风控",
        "developer_tools": "开发与工具",
        "other": "其他",
    },
    "mcp": {
        "business_data": "业务与数据",
        "productivity_collaboration": "办公与协作",
        "development_infrastructure": "开发与基础设施",
        "browser_automation": "浏览器与自动化",
        "commerce_payment": "电商与支付",
        "content_media": "内容与媒体",
        "general_tools": "通用工具",
    },
    "cli": {
        "ai_coding": "AI 与编程",
        "browser_computer": "浏览器与电脑控制",
        "developer_data": "开发与数据",
        "commerce_operations": "电商运营",
        "general_tools": "通用工具",
    },
}
CAPABILITY_PLATFORM_LABELS: dict[str, str] = {
    "general": "通用",
    "amazon": "Amazon",
    "shein": "SHEIN",
    "tiktok_shop": "TikTok Shop",
    "shopee": "Shopee",
    "etsy": "Etsy",
    "walmart": "Walmart",
    "ebay": "eBay",
    "shopify": "Shopify",
    "temu": "Temu",
    "ozon": "Ozon",
    "mercado_libre": "Mercado Libre",
    "coupang": "Coupang",
    "rakuten": "Rakuten",
    "lazada": "Lazada",
    "allegro": "Allegro",
    "jumia": "Jumia",
}
CAPABILITY_PLATFORM_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("amazon", ("amazon",)),
    ("shein", ("shein",)),
    ("tiktok_shop", ("tiktok shop", "tiktok_shop", "tiktok-shop", "tiktok", "tk shop", "tk-", "tk ")),
    ("shopee", ("shopee",)),
    ("etsy", ("etsy",)),
    ("walmart", ("walmart",)),
    ("ebay", ("ebay",)),
    ("shopify", ("shopify",)),
    ("temu", ("temu",)),
    ("ozon", ("ozon",)),
    ("mercado_libre", ("mercado libre", "mercado_libre", "mercado-libre")),
    ("coupang", ("coupang",)),
    ("rakuten", ("rakuten",)),
    ("lazada", ("lazada",)),
    ("allegro", ("allegro",)),
    ("jumia", ("jumia",)),
)
MASTER_CONNECTOR_REGISTRY_PATH = (
    Path("config") / "ai_agent_skill_connector_master_registry.json"
)
AGENT_DISPLAY_NAMES = {
    "AI Ecommerce Director": "AI 电商运营总监",
    "Product Intelligence": "商品情报",
    "Market Coverage Intelligence Agent": "市场覆盖情报",
    "Influencer Intelligence": "达人情报",
    "Viral Content Intelligence": "爆款内容情报",
    "Keyword Intelligence": "关键词情报",
    "Listing Intelligence": "商品上架情报",
    "OMS Director": "订单管理总监",
    "Supply Chain Director": "供应链总监",
    "Risk Intelligence": "风险情报",
    "Audience Preference Intelligence": "用户偏好情报",
    "Brand Matrix Agent": "品牌矩阵",
    "Offline Retail Agent": "线下零售",
    "Offline Advertising Agent": "线下广告",
    "HR Interview Agent": "招聘面试",
    "Business Development Agent": "商务拓展",
    "IP Co-branding Agent": "IP 联名",
    "PR Brand Awareness Agent": "公关与品牌认知",
    "Knowledge Reviewer": "知识复核",
    "Data Review Analyst": "数据复核",
}


def _market_id(prefix: str, name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(name or "").casefold()).strip("-")
    return f"{prefix}-{slug or 'unnamed'}"[:120]


def _codex_mcp_candidates() -> list[dict[str, Any]]:
    """Discover configured Codex MCP names without copying endpoints or secrets."""

    path = Path.home() / ".codex" / "config.toml"
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, tomllib.TOMLDecodeError):
        return []
    servers = payload.get("mcp_servers") if isinstance(payload, dict) else None
    if not isinstance(servers, dict):
        return []
    candidates: list[dict[str, Any]] = []
    display_names = {
        "openaideveloperdocs": "OpenAI 开发文档 MCP",
        "t-one-local": "T One 本地 MCP",
        "node_repl": "Node REPL MCP",
    }
    for raw_name, raw_record in servers.items():
        configured_name = str(raw_name or "").strip()
        record = raw_record if isinstance(raw_record, dict) else {}
        if not configured_name or not record:
            continue
        name = display_names.get(configured_name.casefold(), configured_name)
        transport = "http" if str(record.get("url") or "").strip() else "stdio"
        candidates.append(
            {
                "id": _market_id("codex-mcp", configured_name),
                "name": name,
                "configured_name": configured_name,
                "kind": "mcp",
                "capabilities": [transport, "configured_in_codex"],
                "connected": False,
                "status": "configured_in_codex_unverified_in_t_one",
                "installation_status": (
                    "not_applicable" if transport == "http" else "unknown"
                ),
                "enabled_tool_count": 0,
                "discovered_tool_count": 0,
                "source": "codex_config",
            }
        )
    return candidates


def _connector_catalog_candidates(root: Path) -> dict[str, list[dict[str, Any]]]:
    """Convert explicit user-highlighted connection modes into truthful candidates."""

    try:
        payload = json.loads(
            (root / MASTER_CONNECTOR_REGISTRY_PATH).read_text(encoding="utf-8")
        )
    except (FileNotFoundError, OSError, TypeError, ValueError):
        return {"mcp": [], "cli": []}
    sources = payload.get("user_highlighted_sources") if isinstance(payload, dict) else None
    result: dict[str, list[dict[str, Any]]] = {"mcp": [], "cli": []}
    for item in sources or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        types = {
            str(value or "").strip().casefold()
            for value in item.get("connection_types", [])
            if str(value or "").strip()
        }
        if not name:
            continue
        if "native_mcp" in types:
            result["mcp"].append(
                {
                    "id": _market_id("catalog-mcp", name),
                    "name": name,
                    "kind": "mcp",
                    "capabilities": sorted(types),
                    "connected": False,
                    "status": "catalog_candidate_unverified",
                    "installation_status": "unknown",
                    "enabled_tool_count": 0,
                    "discovered_tool_count": 0,
                    "source": "user_highlighted_registry",
                }
            )
        if types.intersection({"cli", "binary_cli", "local_cli", "cli_skill"}):
            result["cli"].append(
                {
                    "id": _market_id("catalog-cli", name),
                    "name": name,
                    "kind": "cli",
                    "model": "",
                    "installed": False,
                    "ready": False,
                    "callable": False,
                    "status": "catalog_candidate_unverified",
                    "source": "user_highlighted_registry",
                }
            )
    return result


def _append_unique_by_name(
    target: list[dict[str, Any]], candidates: list[dict[str, Any]]
) -> None:
    known = {str(item.get("name") or "").strip().casefold() for item in target}
    for item in candidates:
        key = str(item.get("name") or "").strip().casefold()
        if not key or key in known:
            continue
        target.append(item)
        known.add(key)


def _category_from_text(
    text: str, rules: tuple[tuple[str, tuple[str, ...]], ...], default: str
) -> str:
    lowered = str(text or "").casefold()
    for category, tokens in rules:
        if any(token.casefold() in lowered for token in tokens):
            return category
    return default


def _capability_platforms(item: dict[str, Any]) -> list[str]:
    """Classify applicability without claiming a store or account connection."""

    explicit_values: list[str] = []
    for key in ("platform", "platform_id", "platforms"):
        value = item.get(key)
        if isinstance(value, list):
            explicit_values.extend(str(part) for part in value)
        elif value is not None:
            explicit_values.append(str(value))
    capabilities = item.get("capabilities")
    capability_values = capabilities if isinstance(capabilities, list) else []
    text = " ".join(
        [
            *explicit_values,
            *(str(item.get(key) or "") for key in (
                "id",
                "name",
                "agent",
                "responsibility",
                "agent_module",
                "standard_ref",
                "kind",
                "model",
            )),
            *(str(value) for value in capability_values),
        ]
    ).casefold()
    matched = [
        platform_id
        for platform_id, tokens in CAPABILITY_PLATFORM_TOKENS
        if any(token.casefold() in text for token in tokens)
    ]
    return matched or ["general"]


def _agent_category(item: dict[str, Any]) -> str:
    text = " ".join(str(item.get(key) or "") for key in ("agent", "responsibility"))
    return _category_from_text(
        text,
        (
            ("finance_risk", ("finance", "account", "risk", "compliance", "tax", "财务", "风控", "合规")),
            ("store_fulfillment", ("store", "order", "inventory", "fulfillment", "sourcing", "support", "店铺", "订单", "库存", "履约", "采购")),
            ("growth_marketing", ("advert", "marketing", "influencer", "campaign", "growth", "crm", "广告", "营销", "达人", "增长")),
            ("content_listing", ("content", "creative", "listing", "design", "商品", "内容", "上架", "设计")),
            ("research_selection", ("selection", "research", "market", "product", "trend", "调研", "选品", "趋势")),
        ),
        "management_automation",
    )


def _skill_category(item: dict[str, Any]) -> str:
    text = " ".join(
        str(item.get(key) or "")
        for key in ("id", "name", "agent_module", "standard_ref", "kind")
    )
    return _category_from_text(
        text,
        (
            ("finance_risk", ("finance", "risk", "compliance", "tax", "refund", "财务", "风控", "合规", "退款")),
            ("developer_tools", ("developer", "github", "code", "mcp", "plugin", "tool", "开发", "工具")),
            ("data_automation", ("data", "analytics", "automation", "memory", "crawler", "数据", "自动化", "采集")),
            ("content_listing", ("listing", "content", "creative", "image", "keyword", "商品卡", "内容", "上架", "图片", "关键词")),
            ("research_selection", ("selection", "research", "market", "trend", "product", "调研", "选品", "趋势")),
            ("platform_operations", ("amazon", "shein", "tiktok", "tk-", "shopee", "etsy", "walmart", "ebay", "shopify", "mercado", "coupang", "rakuten", "lazada", "allegro", "jumia", "平台", "店铺", "运营")),
        ),
        "other",
    )


def _mcp_category(item: dict[str, Any]) -> str:
    capabilities = item.get("capabilities") if isinstance(item.get("capabilities"), list) else []
    text = " ".join([str(item.get("name") or ""), *(str(value) for value in capabilities)])
    return _category_from_text(
        text,
        (
            ("commerce_payment", ("commerce", "shop", "store", "payment", "stripe", "电商", "店铺", "支付")),
            ("browser_automation", ("browser", "playwright", "computer", "automation", "浏览器", "电脑", "自动化")),
            ("development_infrastructure", ("github", "gitlab", "database", "postgres", "cloud", "deploy", "developer", "代码", "数据库", "云")),
            ("productivity_collaboration", ("slack", "notion", "drive", "calendar", "email", "office", "协作", "文档", "日历", "邮件")),
            ("content_media", ("image", "video", "audio", "design", "media", "图片", "视频", "音频", "设计")),
            ("business_data", ("crm", "analytics", "search", "data", "business", "客户", "分析", "搜索", "数据")),
        ),
        "general_tools",
    )


def _cli_category(item: dict[str, Any]) -> str:
    text = " ".join(str(item.get(key) or "") for key in ("id", "name", "kind", "model"))
    return _category_from_text(
        text,
        (
            ("ai_coding", ("codex", "codebuddy", "workbuddy", "claude", "gemini", "ai", "agent", "编程")),
            ("browser_computer", ("playwright", "browser", "computer", "selenium", "浏览器", "电脑")),
            ("commerce_operations", ("amazon", "shein", "shop", "store", "电商", "店铺")),
            ("developer_data", ("git", "node", "python", "database", "sql", "开发", "数据")),
        ),
        "general_tools",
    )


def _toolkit(value: object) -> dict[str, list[str]]:
    source = value if isinstance(value, dict) else {}
    return {
        key: list(
            dict.fromkeys(
                str(item).strip()
                for item in source.get(key, [])
                if str(item).strip()
            )
        )
        for key in ("plugins", "skills", "agents")
    }


def _task_route(task: dict[str, Any]) -> dict[str, object]:
    """Expose only the non-secret fields needed by local manual controls."""

    return {
        "platform": str(task.get("platform") or "").strip().lower(),
        "country": str(task.get("country") or "").strip(),
        "store_id": str(task.get("store_id") or "").strip(),
        "store_binding_id": str(task.get("store_binding_id") or "").strip(),
        "browser_profile_seq": int(
            task.get("browser_profile_seq")
            or task.get("browser_profile_sequence")
            or 0
        ),
        "store_surface_connector_script": str(
            task.get("store_surface_connector_script") or ""
        ).strip(),
    }


def agent_skill_marketplace_snapshot(root: Path) -> dict[str, Any]:
    """Return active local choices and each task's current assignment.

    Agent records are role definitions. Skill records may be executable or
    knowledge/rule skills. Neither state is presented as an external account
    connection or an installation claim.
    """

    skills: list[dict[str, Any]] = []
    for item in list_skill_agents(root):
        skill_id = str(item.get("id") or "").strip()
        if not skill_id:
            continue
        skills.append(
            {
                "id": skill_id,
                "name": str(item.get("name") or skill_id).strip(),
                "description": str(
                    item.get("agent_module") or item.get("standard_ref") or ""
                ).strip(),
                "enabled": bool(item.get("enabled", True)),
                "executable": bool(item.get("executable")),
                "kind": str(item.get("kind") or "skill").strip(),
                "category": _skill_category(item),
                "platforms": _capability_platforms(item),
            }
        )

    agents: list[dict[str, Any]] = []
    schema = default_commerce_data_schema()
    for item in schema.get("agent_registry", []):
        if not isinstance(item, dict):
            continue
        agent_id = str(item.get("agent") or "").strip()
        if not agent_id:
            continue
        agents.append(
            {
                "id": agent_id,
                "name": AGENT_DISPLAY_NAMES.get(agent_id, agent_id),
                "description": str(item.get("responsibility") or "").strip(),
                "automation_level": str(item.get("automation_level") or "").strip(),
                "enabled": True,
                "category": _agent_category(item),
                "platforms": _capability_platforms(item),
            }
        )

    workspace = load_workspace_config(root)
    tasks_by_id: dict[str, dict[str, Any]] = {}
    for project in workspace.get("projects", []):
        if not isinstance(project, dict):
            continue
        project_name = str(project.get("name") or project.get("id") or "").strip()
        project_id = str(project.get("id") or "").strip()
        for _channel, _store, task in iter_project_tasks(project):
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("id") or "").strip().lower()
            if not task_id or task_id in tasks_by_id:
                continue
            task_name = str(task.get("name") or task_id).strip()
            tasks_by_id[task_id] = {
                "id": task_id,
                "name": task_name,
                "project_id": project_id,
                "project_name": project_name,
                "label": f"{project_name} / {task_name}" if project_name else task_name,
                "toolkit": _toolkit(task.get("toolkit")),
                **_task_route(task),
            }
    for task in workspace.get("standalone_tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("id") or "").strip().lower()
        if not task_id or task_id in tasks_by_id:
            continue
        task_name = str(task.get("name") or task_id).strip()
        tasks_by_id[task_id] = {
            "id": task_id,
            "name": task_name,
            "project_id": "",
            "project_name": "独立任务",
            "label": f"独立任务 / {task_name}",
            "toolkit": _toolkit(task.get("toolkit")),
            **_task_route(task),
        }

    open_tools = open_tool_registry_snapshot(root)
    mcp_tools = [
        {
            "id": str(item.get("id") or ""),
            "name": str(item.get("name") or "MCP"),
            "kind": "mcp",
            "category": _mcp_category(item),
            "platforms": _capability_platforms(item),
            "connected": item.get("connected") is True,
            "status": str(item.get("status") or "unknown"),
            "installation_status": str(item.get("installation_status") or "unknown"),
            "enabled_tool_count": int(item.get("enabled_tool_count") or 0),
            "discovered_tool_count": int(item.get("discovered_tool_count") or 0),
        }
        for item in open_tools.get("tools", [])
        if isinstance(item, dict) and str(item.get("kind") or "").strip().casefold() == "mcp"
    ]
    catalog_candidates = _connector_catalog_candidates(root)
    _append_unique_by_name(mcp_tools, _codex_mcp_candidates())
    _append_unique_by_name(mcp_tools, catalog_candidates["mcp"])
    for item in mcp_tools:
        item["category"] = _mcp_category(item)
        item["platforms"] = _capability_platforms(item)
    mcp_tools.sort(
        key=lambda item: (
            not bool(item.get("connected")),
            str(item.get("name") or "").casefold(),
        )
    )
    external_agents: list[dict[str, Any]] = []
    for item in open_tools.get("tools", []):
        if not isinstance(item, dict) or str(item.get("kind") or "").strip().casefold() != "agent":
            continue
        capabilities = item.get("capabilities") if isinstance(item.get("capabilities"), list) else []
        category_source = {
            "agent": str(item.get("name") or ""),
            "responsibility": " ".join(str(value) for value in capabilities),
        }
        external_agents.append(
            {
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or "Agent"),
                "kind": "agent",
                "category": _agent_category(category_source),
                "platforms": _capability_platforms(item),
                "installed": str(item.get("installation_status") or "") == "installed",
                "connected": item.get("connected") is True,
                "status": str(item.get("status") or "registered_unverified"),
                "capabilities": [str(value) for value in capabilities],
                "assignable": False,
            }
        )
    cli = cli_ai_connector_snapshot(root, live_probe=False)
    project_ai = project_capability_profile_snapshot(root)
    try:
        harness = DeepSeekHarnessRuntime.discover().status()
    except (OSError, RuntimeError, TypeError, ValueError):
        harness = {"ok": False, "installed": False, "version": "", "license": ""}
    cli_tools: list[dict[str, Any]] = []
    seen_cli_ids: set[str] = set()
    for item in project_ai.get("participants", []):
        if not isinstance(item, dict) or str(item.get("kind") or "").strip().casefold() not in {
            "cli",
            "workbuddy_cli",
        }:
            continue
        tool_id = str(item.get("id") or item.get("name") or "").strip()
        if not tool_id or tool_id in seen_cli_ids:
            continue
        seen_cli_ids.add(tool_id)
        record = {
            "id": tool_id,
            "name": str(item.get("name") or tool_id).strip(),
            "kind": "cli",
            "model": str(item.get("model") or "").strip(),
            "installed": bool(item.get("installed")),
            "ready": bool(item.get("ready")),
            "callable": bool(item.get("callable")),
            "status": str(item.get("status") or "unknown"),
        }
        record["category"] = _cli_category(record)
        record["platforms"] = _capability_platforms(record)
        cli_tools.append(record)
    if "deepseek-harness" not in seen_cli_ids:
        seen_cli_ids.add("deepseek-harness")
        harness_record = {
            "id": "deepseek-harness",
            "name": "DeepSeek Harness",
            "kind": "cli",
            "model": "",
            "installed": bool(harness.get("installed")),
            "ready": False,
            "callable": False,
            "status": (
                "installed_requires_project_enablement"
                if harness.get("installed")
                else "not_installed"
            ),
        }
        harness_record["category"] = "browser_computer"
        harness_record["platforms"] = ["general"]
        cli_tools.append(harness_record)
    for item in open_tools.get("tools", []):
        if not isinstance(item, dict) or str(item.get("kind") or "").strip().casefold() not in {
            "cli",
            "命令行",
        }:
            continue
        item_name = str(item.get("name") or "").strip()
        identity_text = item_name.casefold()
        canonical_id = (
            "workbuddy-cli"
            if "workbuddy" in identity_text or "codebuddy" in identity_text
            else "codex-cli" if "codex" in identity_text else ""
        )
        if canonical_id and canonical_id in seen_cli_ids:
            continue
        tool_id = canonical_id or str(item.get("id") or item_name).strip()
        if not tool_id or tool_id in seen_cli_ids:
            continue
        seen_cli_ids.add(tool_id)
        record = {
            "id": tool_id,
            "name": str(item.get("name") or tool_id).strip(),
            "kind": "cli",
            "model": "",
            "installed": str(item.get("installation_status") or "") == "installed",
            "ready": item.get("connected") is True,
            "callable": item.get("connected") is True,
            "status": str(item.get("status") or "registered_unverified"),
        }
        record["category"] = _cli_category(record)
        record["platforms"] = _capability_platforms(record)
        cli_tools.append(record)
    _append_unique_by_name(cli_tools, catalog_candidates["cli"])
    for item in cli_tools:
        item["category"] = _cli_category(item)
        item["platforms"] = _capability_platforms(item)
    cli_tools.sort(key=lambda item: (not bool(item.get("ready")), str(item.get("name") or "").casefold()))

    return {
        "schema_version": 2,
        "agents": agents,
        "skills": skills,
        "tasks": list(tasks_by_id.values()),
        "connections": {
            "mcp": mcp_tools,
            "external_agents": external_agents,
            "cli": {
                "provider_id": str(cli.get("provider_id") or "codex-cli"),
                "installed": bool(cli.get("installed")),
                "ready": bool(cli.get("ready")),
                "authentication_status": str(
                    cli.get("authentication_status") or "not_checked"
                ),
            },
            "cli_tools": cli_tools,
            "deepseek_harness": harness,
            "settings_href": "/desktop?view=settings#settings-skills-agents",
        },
        "taxonomy": {
            "types": ["agent", "skill", "mcp", "cli"],
            "category_labels": CAPABILITY_CATEGORY_LABELS,
            "platform_labels": CAPABILITY_PLATFORM_LABELS,
        },
        "project_ai": project_ai,
        "truth": {
            "selection_means": "task_assignment",
            "task_local_install_supported": True,
            "catalog_entry_installation_claimed": False,
            "connection_claimed": False,
            "external_action_count": 0,
        },
    }
