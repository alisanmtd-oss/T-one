from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any


EXCLUDED_PRIVATE_PACKS = {
    "tiktok_shop": {
        "aliases": ("tiktok shop", "tiktokshop", "tik tok shop"),
        "reason": "The TikTok Shop knowledge pack is intentionally excluded from the public release.",
    }
}


@lru_cache(maxsize=1)
def load_public_knowledge_packs() -> dict[str, Any]:
    resource = files("ai_ecommerce_director.knowledge_packs").joinpath("catalog.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    packs = payload.get("packs")
    if payload.get("schema_version") != 1 or not isinstance(packs, list):
        raise ValueError("Unsupported public knowledge-pack catalog.")
    ids = [str(item.get("id") or "") for item in packs]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("Public knowledge-pack IDs must be present and unique.")
    if "tiktok_shop" in ids:
        raise ValueError("The private TikTok Shop pack must not enter the public catalog.")
    return payload


def list_public_agents() -> list[dict[str, Any]]:
    return [dict(item) for item in load_public_knowledge_packs()["packs"]]


def _matches(message: str, aliases: list[str]) -> bool:
    normalized = " ".join(message.casefold().replace("_", " ").split())
    return any(alias.casefold() in normalized for alias in aliases)


def route_public_chat(message: str) -> dict[str, Any]:
    """Select a public platform agent without claiming a live store connection.

    This function only performs deterministic local routing. It never reads a
    credential, calls a platform, queues a task, or performs an external action.
    """

    text = str(message or "").strip()
    for pack_id, excluded in EXCLUDED_PRIVATE_PACKS.items():
        if _matches(text, list(excluded["aliases"])):
            return {
                "status": "excluded_private_pack",
                "pack_id": pack_id,
                "reason": excluded["reason"],
                "live_connection_claimed": False,
                "external_execution_allowed": False,
            }

    matched = [
        pack
        for pack in load_public_knowledge_packs()["packs"]
        if _matches(text, list(pack.get("aliases") or []))
    ]
    if not matched:
        return {
            "status": "needs_platform",
            "message": "Name a platform or operating channel in ordinary chat.",
            "agent_ids": [],
            "live_connection_claimed": False,
            "external_execution_allowed": False,
        }
    if len(matched) > 1:
        return {
            "status": "multi_platform_comparison",
            "agent_ids": [pack["id"] for pack in matched],
            "agents": [pack["name"] for pack in matched],
            "required_scope": ["country_site", "store_mode", "ownership", "store_binding"],
            "live_connection_claimed": False,
            "external_execution_allowed": False,
        }

    pack = matched[0]
    return {
        "status": "public_agent_selected",
        "agent_id": pack["id"],
        "agent_name": pack["name"],
        "summary": pack["summary"],
        "required_scope": list(pack["required_scope"]),
        "capabilities": list(pack["capabilities"]),
        "safety_boundaries": list(pack["safety_boundaries"]),
        "live_connection_claimed": False,
        "external_execution_allowed": False,
    }
