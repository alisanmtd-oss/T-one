from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit
import json


REGISTRY_PATH = Path("config") / "learning_direction_library_registry.json"


def _load_json(root: Path, relative_path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads((root / Path(relative_path)).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _strings(value: Any, fallback: str = "t_one_control_plane") -> list[str]:
    values = value if isinstance(value, list) else []
    result: list[str] = []
    for item in values:
        clean = str(item or "").strip()
        if clean and clean not in result:
            result.append(clean)
    return result or [fallback]


def _canonical_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw.casefold().rstrip("/")
    scheme = parsed.scheme.casefold() or "https"
    host = parsed.netloc.casefold()
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((scheme, host, path, parsed.query, ""))


def _learning_asset(
    *,
    asset_id: str,
    label: str,
    asset_type: str,
    status: str,
    target_agents: Iterable[str],
    source_ref: str,
    canonical_url: str = "",
    summary: str = "",
    source_kind: str = "",
) -> dict[str, Any]:
    return {
        "id": asset_id,
        "label": label,
        "asset_type": asset_type,
        "status": status or "unknown",
        "target_agents": _strings(list(target_agents)),
        "source_ref": source_ref,
        "canonical_url": canonical_url,
        "summary": summary,
        "source_kind": source_kind or "unknown",
        "classification": "learning_only",
        "runtime_eligible": False,
        "connected_claim": False,
        "show_in_dashboard": False,
        "show_in_capability_center": False,
        "external_action_authorized": False,
    }


def _website_assets(root: Path) -> list[dict[str, Any]]:
    course_index = _load_json(
        root, "outputs/conversation_audit/platform_course_source_index_2026-07-21.json"
    )
    learning_sources = _load_json(root, "config/learning_sources.json")
    merged: dict[str, dict[str, Any]] = {}

    candidates: list[dict[str, Any]] = []
    for item in _dict_list(course_index.get("urls")):
        candidates.append(
            {
                "id": str(item.get("url") or item.get("label") or "course-source"),
                "label": str(item.get("label") or item.get("url") or "学习来源"),
                "url": str(item.get("url") or ""),
                "status": str(item.get("download_state") or "index_only"),
                "targets": item.get("target_rule_libraries") or item.get("platform_scope"),
                "source_kind": str(item.get("source_kind") or "learning_website"),
                "summary": "课程/帮助中心索引；按授权范围蒸馏给对应智能体。",
                "source_ref": "outputs/conversation_audit/platform_course_source_index_2026-07-21.json",
            }
        )
    for item in _dict_list(learning_sources.get("sources")):
        candidates.append(
            {
                "id": str(item.get("id") or item.get("url") or "learning-source"),
                "label": str(item.get("name") or item.get("url") or "学习来源"),
                "url": str(item.get("url") or ""),
                "status": "enabled_index" if item.get("enabled") else "disabled_index",
                "targets": [
                    str(item.get("marketplace") or "").strip().lower().replace(" ", "_")
                    or "t_one_control_plane"
                ],
                "source_kind": str(item.get("source_type") or "learning_website"),
                "summary": str(item.get("validation_task") or item.get("industry_scope") or ""),
                "source_ref": "config/learning_sources.json",
            }
        )

    for index, item in enumerate(candidates, start=1):
        canonical = _canonical_url(item.get("url"))
        key = canonical or f"label:{str(item.get('label') or '').casefold()}"
        if key in merged:
            existing = merged[key]
            existing["target_agents"] = _strings(
                list(existing.get("target_agents") or []) + _strings(item.get("targets"))
            )
            source_refs = _strings(existing.get("source_refs"), fallback=str(existing.get("source_ref") or ""))
            current_ref = str(item.get("source_ref") or "")
            if current_ref and current_ref not in source_refs:
                source_refs.append(current_ref)
            existing["source_refs"] = source_refs
            continue
        asset = _learning_asset(
            asset_id=f"learning-site-{index:03d}",
            label=str(item.get("label") or "学习来源"),
            asset_type="learning_website",
            status=str(item.get("status") or "index_only"),
            target_agents=_strings(item.get("targets")),
            source_ref=str(item.get("source_ref") or ""),
            canonical_url=canonical,
            summary=str(item.get("summary") or ""),
            source_kind=str(item.get("source_kind") or "learning_website"),
        )
        asset["source_refs"] = [asset["source_ref"]]
        merged[key] = asset
    return list(merged.values())


def _material_assets(root: Path) -> list[dict[str, Any]]:
    payload = _load_json(root, "config/user_collected_training_materials.json")
    assets: list[dict[str, Any]] = []
    for item in _dict_list(payload.get("materials")):
        assets.append(
            _learning_asset(
                asset_id=str(item.get("id") or f"material-{len(assets) + 1}"),
                label=str(item.get("title") or "用户资料包"),
                asset_type="user_material_pack",
                status=str(item.get("disposition") or item.get("review_state") or "unknown"),
                target_agents=_strings(item.get("target_experts")),
                source_ref=str(item.get("path") or "config/user_collected_training_materials.json"),
                summary=(
                    f"已读 {int(item.get('bytes') or 0)} bytes / {int(item.get('lines') or 0)} 行；"
                    f"SHA256 {str(item.get('sha256') or '')[:12]}…"
                ),
                source_kind="user_authorized_material",
            )
        )
    return assets


def _platform_pack_assets(root: Path) -> list[dict[str, Any]]:
    payload = _load_json(root, "config/platform_rule_library_manifest.json")
    assets: list[dict[str, Any]] = []
    for item in _dict_list(payload.get("platform_rule_libraries")):
        platform_id = str(item.get("platform_id") or f"platform-{len(assets) + 1}")
        assets.append(
            _learning_asset(
                asset_id=f"platform-learning-{platform_id}",
                label=str(item.get("label") or platform_id),
                asset_type="platform_learning_pack",
                status=str(item.get("training_status") or "unknown"),
                target_agents=_strings(item.get("consumer_ids"), fallback=platform_id),
                source_ref="config/platform_rule_library_manifest.json",
                summary=f"{len(_strings(item.get('rule_domains'), fallback=''))} 个规则域；供平台专家蒸馏与回归。",
                source_kind="platform_rule_learning_pack",
            )
        )
    return assets


def _unconnected_ai_assets(root: Path, registry: dict[str, Any]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    seen: set[str] = set()

    def append_asset(
        *,
        asset_id: str,
        label: str,
        status: str,
        source_ref: str,
        summary: str,
        source_kind: str,
    ) -> None:
        key = label.casefold().strip()
        if not key or key in seen:
            return
        seen.add(key)
        assets.append(
            _learning_asset(
                asset_id=asset_id,
                label=label,
                asset_type="unconnected_ai_research_pack",
                status=status,
                target_agents=["t_one_agent_platform_architecture", "shared_ai_tool_admission"],
                source_ref=source_ref,
                summary=summary,
                source_kind=source_kind,
            )
        )

    bridge = _load_json(root, "config/web_ai_bridge.json")
    for item in _dict_list(bridge.get("providers")):
        if item.get("automation_verified") and item.get("external_action_authorized"):
            continue
        append_asset(
            asset_id=f"external-ai-{str(item.get('id') or len(assets) + 1)}",
            label=str(item.get("name") or item.get("id") or "外部 AI"),
            status=str(item.get("current_status") or "registered_not_verified"),
            source_ref="config/web_ai_bridge.json",
            summary=str(item.get("project_hint") or "未接入；只保留研究方向与交接边界。"),
            source_kind=str(item.get("bridge_type") or "external_ai_surface"),
        )

    integration_hub = _load_json(root, "config/integration_hub.json")
    for item in _dict_list(integration_hub.get("connectors")):
        status = str(item.get("status") or "unknown")
        if not status.casefold().startswith(
            ("blocked", "unknown", "research_only", "reference_only")
        ):
            continue
        append_asset(
            asset_id=f"unconnected-integration-{str(item.get('id') or len(assets) + 1)}",
            label=str(item.get("name") or item.get("id") or "未接入外部工具"),
            status=status,
            source_ref="config/integration_hub.json",
            summary=str(
                item.get("write_boundary")
                or "没有经过真实连接、调用和结果回传验收；只保留学习研究方向。"
            ),
            source_kind="unconnected_integration_candidate",
        )

    github = _load_json(root, "config/github_capability_registry.json")
    allowed_categories = {
        str(item) for item in registry.get("github_ai_research_categories", []) if str(item)
    }
    for item in _dict_list(github.get("candidates")):
        category = str(item.get("category") or "")
        if category not in allowed_categories:
            continue
        repo = str(item.get("repo") or "")
        append_asset(
            asset_id="github-ai-" + repo.replace("/", "-").replace("_", "-"),
            label=repo,
            status=str(item.get("decision") or item.get("status") or "reference_only"),
            source_ref="config/github_capability_registry.json",
            summary=str(item.get("fit") or "仅作架构、记忆、评测或安全研究。"),
            source_kind=category or "github_ai_research",
        )

    master = _load_json(root, "config/ai_agent_skill_connector_master_registry.json")
    ai_connection_markers = {
        "agent_runtime",
        "memory_system",
        "skill_host",
        "mcp_client",
        "hosted_skill_catalog",
        "system_prompt_catalog",
        "third_party_skill_aggregation",
    }
    for item in _dict_list(master.get("user_highlighted_sources")):
        types = {str(value) for value in item.get("connection_types", [])}
        if not types.intersection(ai_connection_markers):
            continue
        append_asset(
            asset_id="highlighted-ai-" + str(item.get("name") or "tool").casefold().replace(" ", "-"),
            label=str(item.get("name") or "外部 AI 工具"),
            status=str(item.get("current_status") or "reference_only"),
            source_ref="config/ai_agent_skill_connector_master_registry.json",
            summary=str(item.get("next_gate") or "未接入；只保留研究方向。"),
            source_kind="highlighted_external_ai_tool",
        )
    return assets


def learning_direction_library_snapshot(root: Path) -> dict[str, Any]:
    """Return the canonical learning-only library without runtime promotion.

    Every item is derived from an existing source registry.  The function does
    not fetch the web, install tools, connect accounts or execute agents.
    """

    root = Path(root)
    registry = _load_json(root, REGISTRY_PATH)
    groups = [
        {
            "id": "learning_websites",
            "label": "学习网站与课程索引",
            "description": "只收集合法索引、链接、元数据、短蒸馏卡和回归题。",
            "assets": _website_assets(root),
        },
        {
            "id": "user_material_packs",
            "label": "用户资料包",
            "description": "用户提供并已登记哈希、目标智能体和使用边界的资料。",
            "assets": _material_assets(root),
        },
        {
            "id": "platform_learning_packs",
            "label": "平台规则学习包",
            "description": "供平台专家蒸馏训练，不等于平台连接或可执行智能体。",
            "assets": _platform_pack_assets(root),
        },
        {
            "id": "unconnected_ai_research_packs",
            "label": "未接入 AI 工具研究包",
            "description": "只研究架构、记忆、压缩、评测、安全和协作方向；未验收前不可执行。",
            "assets": _unconnected_ai_assets(root, registry),
        },
    ]
    groups_by_id = {group["id"]: group for group in groups}
    all_assets = [asset for group in groups for asset in group["assets"]]
    return {
        "schema_version": int(registry.get("schema_version") or 1),
        "registry_path": str(REGISTRY_PATH),
        "groups": groups,
        "groups_by_id": groups_by_id,
        "learning_website_count": len(groups_by_id["learning_websites"]["assets"]),
        "user_material_pack_count": len(groups_by_id["user_material_packs"]["assets"]),
        "platform_learning_pack_count": len(groups_by_id["platform_learning_packs"]["assets"]),
        "unconnected_ai_research_pack_count": len(
            groups_by_id["unconnected_ai_research_packs"]["assets"]
        ),
        "asset_count": len(all_assets),
        "runtime_eligible_count": sum(bool(item.get("runtime_eligible")) for item in all_assets),
        "connected_claim_count": sum(bool(item.get("connected_claim")) for item in all_assets),
        "amazon_paused": str((registry.get("truth_policy") or {}).get("amazon_state"))
        == "paused_by_owner",
        "visibility_policy": dict(registry.get("visibility_policy") or {}),
        "external_action_authorized": False,
    }
