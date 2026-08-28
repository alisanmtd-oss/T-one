from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REGISTRY_PATH = Path("config/github_capability_registry.json")
INSTALLATIONS_PATH = Path("config/github_pilot_installations.json")


def _load(root: Path, relative: Path) -> dict[str, Any]:
    payload = json.loads((root / relative).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"GitHub pilot registry must contain an object: {relative}")
    return payload


def github_pilot_snapshot(root: Path) -> dict[str, Any]:
    """Return bounded pilot truth without executing or scanning any target."""

    root = Path(root).resolve()
    registry = _load(root, REGISTRY_PATH)
    installations = _load(root, INSTALLATIONS_PATH)
    candidates = {
        str(item.get("repo") or ""): dict(item)
        for item in registry.get("candidates", [])
        if isinstance(item, dict) and str(item.get("repo") or "")
    }
    pilots: list[dict[str, Any]] = []
    for raw in installations.get("pilots", []):
        if not isinstance(raw, dict):
            continue
        pilot = dict(raw)
        repo = str(pilot.get("repo") or "")
        candidate = candidates.get(repo)
        if candidate is None:
            raise ValueError(f"GitHub pilot has no admitted candidate: {repo}")
        if str(candidate.get("pinned_release") or "") != str(pilot.get("release") or ""):
            raise ValueError(f"GitHub pilot release does not match registry: {repo}")
        if str(candidate.get("pinned_commit") or "") != str(pilot.get("commit") or ""):
            raise ValueError(f"GitHub pilot commit does not match registry: {repo}")
        pilot["decision"] = str(candidate.get("decision") or "")
        pilot["allowed_surfaces"] = list(candidate.get("allowed_surfaces") or [])
        pilot["blocked_surfaces"] = list(candidate.get("blocked_surfaces") or [])
        pilots.append(pilot)
    summary = dict(installations.get("summary") or {})
    return {
        "schema_version": int(installations.get("schema_version") or 1),
        "classification": "github_capability_pilot_truth",
        "pilots": pilots,
        "pilots_by_repo": {str(item["repo"]): item for item in pilots},
        "summary": summary,
        "truth_contract": {
            "unknown_repository_blocked": str(
                (registry.get("policy") or {}).get("unknown_repository_decision")
            ) == "block_unknown",
            "automatic_install_allowed": False,
            "real_workspace_scan_allowed": False,
            "credential_access_allowed": False,
            "real_external_action_allowed": False,
            "amazon_state": "paused_by_owner",
        },
        "external_actions": int(summary.get("external_actions") or 0),
    }
