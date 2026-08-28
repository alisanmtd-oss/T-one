from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping
import json


PLATFORM_RULE_MANIFEST_PATH = Path("config") / "platform_rule_library_manifest.json"
PLATFORM_COURSE_INDEX_PATH = (
    Path("outputs")
    / "conversation_audit"
    / "platform_course_source_index_2026-07-21.json"
)


CONNECTOR_CATEGORIES: tuple[dict[str, str], ...] = (
    {
        "id": "ai_models",
        "label": "AI 模型",
        "description": "按任务选择模型供应商、模型和可用模态；失败时显示真实错误。",
    },
    {
        "id": "ecommerce_platforms",
        "label": "电商平台",
        "description": "按平台、国家站点、店铺模式、API 授权、邮箱和社媒账号隔离。",
    },
    {
        "id": "social_media",
        "label": "社交媒体",
        "description": "官方号、渠道号、内容发布、达人协作与广告账号分开绑定。",
    },
    {
        "id": "communications",
        "label": "通讯工具",
        "description": "邮箱、辅助邮箱、工作群、客服消息和人工审批通道统一治理。",
    },
    {
        "id": "erp_warehouse_finance",
        "label": "ERP / 仓储 / 财务",
        "description": "订单、库存、发货、结算、成本和仓储系统按店铺路由接入。",
    },
    {
        "id": "browser_ip",
        "label": "浏览器环境 / IP",
        "description": "指纹浏览器、IP、执行身份和店铺授权不可跨平台混用。",
    },
    {
        "id": "skills_agents",
        "label": "Skills / Agents",
        "description": "只安装可执行 Skill、岗位智能体和共享能力包；学习资料单独管理。",
    },
    {
        "id": "permissions_security",
        "label": "权限与安全",
        "description": "OAuth、外部写入、批量下载、发布、广告和发货必须经过门禁。",
    },
)


def _load_json(root: Path, path: Path) -> dict[str, Any]:
    try:
        payload = json.loads((root / path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _dict_items(payload: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    values = payload.get(key)
    if not isinstance(values, list):
        return []
    return [dict(item) for item in values if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def platform_rule_library_snapshot(root: Path) -> dict[str, Any]:
    """Return UI-safe facts about the platform rule libraries and learning queue.

    The snapshot intentionally carries metadata only.  It never mirrors raw
    third-party course text, never claims a live platform connection, and keeps
    unknown platform facts as queueable learning work rather than executable
    automation.
    """

    root = Path(root)
    manifest = _load_json(root, PLATFORM_RULE_MANIFEST_PATH)
    course_index = _load_json(root, PLATFORM_COURSE_INDEX_PATH)
    policy = manifest.get("global_policy") if isinstance(manifest.get("global_policy"), dict) else {}

    libraries: list[dict[str, Any]] = []
    status_counter: Counter[str] = Counter()
    missing_skill_platforms: list[dict[str, str]] = []
    for item in _dict_items(manifest, "platform_rule_libraries"):
        platform_id = str(item.get("platform_id") or "").strip()
        label = str(item.get("label") or platform_id or "平台规则库").strip()
        skill_paths = _string_list(item.get("skill_paths"))
        rule_domains = _string_list(item.get("rule_domains"))
        consumer_ids = _string_list(item.get("consumer_ids"))
        source_ids = _string_list(item.get("source_ids"))
        training_status = str(item.get("training_status") or "unknown").strip() or "unknown"
        status_counter[training_status] += 1
        library = {
            "platform_id": platform_id,
            "label": label,
            "consumer_ids": consumer_ids,
            "skill_paths": skill_paths,
            "source_ids": source_ids,
            "rule_domains": rule_domains,
            "rule_domain_count": len(rule_domains),
            "training_status": training_status,
            "has_skill": bool(skill_paths),
        }
        libraries.append(library)
        if not skill_paths:
            missing_skill_platforms.append({"platform_id": platform_id, "label": label})

    source_urls: list[dict[str, Any]] = []
    for item in _dict_items(course_index, "urls"):
        source_urls.append(
            {
                "url": str(item.get("url") or ""),
                "label": str(item.get("label") or item.get("url") or "课程来源"),
                "platform_scope": _string_list(item.get("platform_scope")),
                "target_rule_libraries": _string_list(item.get("target_rule_libraries")),
                "source_kind": str(item.get("source_kind") or "unknown"),
                "download_state": str(item.get("download_state") or "unknown"),
            }
        )

    blocked_methods = []
    for package in _dict_items(manifest, "source_packages"):
        blocked_methods.extend(_string_list(package.get("blocked_use")))

    return {
        "manifest_path": str(PLATFORM_RULE_MANIFEST_PATH),
        "course_index_path": str(PLATFORM_COURSE_INDEX_PATH),
        "platform_count": len(libraries),
        "url_count": int(course_index.get("url_count") or len(source_urls)),
        "libraries": libraries,
        "source_urls": source_urls,
        "status_counts": dict(status_counter),
        "missing_skill_platforms": missing_skill_platforms,
        "connector_categories": [dict(item) for item in CONNECTOR_CATEGORIES],
        "blocked_method_count": len(blocked_methods),
        "external_action_authorized": bool(policy.get("external_action_authorized")),
        "raw_course_bulk_copy_allowed": bool(
            policy.get("raw_third_party_course_bulk_copy_allowed")
        ),
        "raw_public_distribution_allowed": bool(policy.get("raw_public_distribution_allowed")),
        "screenshots_as_default_learning_method": bool(
            policy.get("screenshots_as_default_learning_method")
        ),
        "token_waste_reduction": str(policy.get("token_waste_reduction") or ""),
        "amazon_state": str(policy.get("amazon_state") or "unknown"),
    }
