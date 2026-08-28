"""Bounded, task-scoped Agent and Skill selection for prompt construction."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .commerce_schema import default_commerce_data_schema
from .skill_agents import list_skill_agents


DEFAULT_MAX_AGENTS = 2
DEFAULT_MAX_SKILLS = 3
DEFAULT_TOKEN_BUDGET = 360

_SKILL_HINTS: dict[str, tuple[str, ...]] = {
    "product-catalog-collector": (
        "采集", "爬取", "商品图", "图片", "详情", "素材", "catalog", "collect", "crawl",
    ),
    "shein-keyword-library": (
        "关键词", "词库", "长尾词", "热词", "搜索词", "keyword", "search term",
    ),
    "shein-listing-intake": (
        "上架", "批量表", "导入模板", "listing", "publish", "upload",
    ),
}

_CATEGORY_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("research_selection", ("选品", "调研", "竞品", "趋势", "research", "product")),
    ("content_listing", ("内容", "图片", "标题", "描述", "上架", "listing", "content")),
    ("growth_marketing", ("广告", "营销", "达人", "增长", "campaign", "marketing")),
    ("store_fulfillment", ("店铺", "订单", "库存", "履约", "order", "inventory")),
    ("finance_risk", ("财务", "费用", "风险", "合规", "finance", "risk")),
    ("data_automation", ("数据", "自动化", "采集", "分析", "data", "automation")),
)


def _unique(values: object) -> list[str]:
    source = values if isinstance(values, list) else []
    result: list[str] = []
    seen: set[str] = set()
    for value in source:
        text = " ".join(str(value or "").split()).strip()[:160]
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _catalogs(root: Path) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    skills: dict[str, dict[str, str]] = {}
    try:
        records = list_skill_agents(root)
    except (OSError, TypeError, ValueError):
        records = []
    for item in records:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            continue
        skills[item_id.casefold()] = {
            "id": item_id,
            "name": str(item.get("name") or item_id).strip(),
            "description": str(item.get("agent_module") or item.get("standard_ref") or "").strip(),
            "category": str(item.get("kind") or "skill").strip(),
        }
    agents: dict[str, dict[str, str]] = {}
    for item in default_commerce_data_schema().get("agent_registry", []):
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("agent") or "").strip()
        if not item_id:
            continue
        agents[item_id.casefold()] = {
            "id": item_id,
            "name": item_id,
            "description": str(item.get("responsibility") or "").strip(),
            "category": "agent",
        }
    return skills, agents


def _record(reference: str, catalog: dict[str, dict[str, str]], kind: str) -> dict[str, str]:
    known = catalog.get(reference.casefold())
    if known:
        return dict(known)
    return {"id": reference, "name": reference, "description": "", "category": kind}


def _score(record: dict[str, str], instruction: str, platform: str, *, preferred: bool = False) -> tuple[int, list[str]]:
    query = instruction.casefold()
    searchable = " ".join(record.values()).casefold()
    score = 100 if preferred else 0
    reasons: list[str] = ["任务明确指定"] if preferred else []
    platform_key = platform.casefold().strip()
    if platform_key and platform_key not in {"general", "unknown"} and platform_key in searchable:
        score += 3
        reasons.append("匹配当前平台")
    for hint in _SKILL_HINTS.get(record["id"].casefold(), ()):
        if hint.casefold() in query:
            score += 12
            reasons.append("匹配本轮指令")
            break
    for category, hints in _CATEGORY_HINTS:
        if any(hint.casefold() in query for hint in hints) and (
            category in searchable or any(hint.casefold() in searchable for hint in hints)
        ):
            score += 7
            reasons.append("匹配任务用途")
            break
    words = {
        token for token in re.split(r"[^a-z0-9\u4e00-\u9fff]+", searchable)
        if len(token) >= 2
    }
    if any(token in query for token in words):
        score += 4
        reasons.append("名称或能力命中")
    return score, list(dict.fromkeys(reasons))


def _select(
    records: list[dict[str, str]], instruction: str, platform: str, limit: int, preferred_id: str = ""
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        score, reasons = _score(
            record, instruction, platform, preferred=record["id"].casefold() == preferred_id.casefold()
        )
        ranked.append({**record, "score": score, "reason": "、".join(reasons) or "任务已配置候选", "_index": index})
    ranked.sort(key=lambda item: (-int(item["score"]), int(item["_index"])))
    best_score = int(ranked[0]["score"]) if ranked else 0
    threshold = max(6, best_score - 4)
    selected = [item for item in ranked if int(item["score"]) >= threshold][:limit]
    if not selected and ranked:
        selected = ranked[:1]
    for item in selected:
        item.pop("_index", None)
    return selected


def _skill_body_tokens(root: Path, reference: str) -> int:
    relative = Path("skills") / reference / "SKILL.md"
    if relative.is_absolute() or ".." in relative.parts:
        return 80
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
        return max(80, int(candidate.stat().st_size / 4)) if candidate.is_file() else 80
    except (OSError, ValueError):
        return 80


def resolve_task_capability_context(
    root: Path,
    task: dict[str, Any],
    instruction: str,
    *,
    max_agents: int = DEFAULT_MAX_AGENTS,
    max_skills: int = DEFAULT_MAX_SKILLS,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> dict[str, Any]:
    """Select compact capability references; never read full Skill bodies."""

    root = root.resolve()
    toolkit = task.get("toolkit") if isinstance(task.get("toolkit"), dict) else {}
    configured_skills = _unique(toolkit.get("skills"))
    configured_skills = _unique([*configured_skills, *_unique(task.get("skill_refs"))])
    configured_agents = _unique(toolkit.get("agents"))
    configured_agents = _unique(
        [*configured_agents, *_unique(task.get("assigned_agent_refs"))]
    )
    preferred_agent = str(task.get("assigned_agent_id") or "").strip()
    if preferred_agent and not configured_agents:
        configured_agents.insert(0, preferred_agent)
    skill_catalog, agent_catalog = _catalogs(root)
    skill_records = [_record(item, skill_catalog, "skill") for item in configured_skills]
    agent_records = [_record(item, agent_catalog, "agent") for item in configured_agents]
    selected_skills = _select(
        skill_records, str(instruction or ""), str(task.get("platform") or ""), max(1, min(int(max_skills), 6))
    )
    selected_agents = _select(
        agent_records, str(instruction or ""), str(task.get("platform") or ""), max(1, min(int(max_agents), 4)), preferred_agent
    )
    selected_skill_refs = [str(item["id"]) for item in selected_skills]
    selected_agent_refs = [str(item["id"]) for item in selected_agents]
    lines = [
        "本轮按需能力（未加载 Skill 正文）：Agent="
        + (",​".join(selected_agent_refs) or "none")
        + "；Skill="
        + (",​".join(selected_skill_refs) or "none"),
        f"能力上下文预算：Agent {len(selected_agent_refs)}/{len(configured_agents)}；"
        f"Skill {len(selected_skill_refs)}/{len(configured_skills)}；full_skill_bodies_loaded=0",
    ]
    budget = max(80, min(int(token_budget or DEFAULT_TOKEN_BUDGET), 2000))
    while (sum(len(line) for line in lines) + 3) // 4 > budget and (selected_skills or selected_agents):
        if selected_skills:
            selected_skills.pop()
            selected_skill_refs.pop()
        elif selected_agents:
            selected_agents.pop()
            selected_agent_refs.pop()
        lines[0] = "本轮按需能力（未加载 Skill 正文）：Agent=" + (",​".join(selected_agent_refs) or "none") + "；Skill=" + (",​".join(selected_skill_refs) or "none")
    selected_tokens = (sum(len(line) for line in lines) + 3) // 4
    eager_tokens = sum(_skill_body_tokens(root, item) for item in configured_skills) + 60 * len(configured_agents)
    return {
        "schema_version": 1,
        "mode": "lazy_task_scoped",
        "task_id": str(task.get("id") or task.get("task_id") or ""),
        "configured_skill_count": len(configured_skills),
        "configured_agent_count": len(configured_agents),
        "selected_skills": selected_skills,
        "selected_agents": selected_agents,
        "selected_skill_refs": selected_skill_refs,
        "selected_agent_refs": selected_agent_refs,
        "compact_context_lines": lines,
        "token_budget": budget,
        "estimated_eager_tokens": eager_tokens,
        "estimated_selected_tokens": selected_tokens,
        "estimated_tokens_saved": max(0, eager_tokens - selected_tokens),
        "full_skill_bodies_loaded": 0,
        "external_action_count": 0,
    }
