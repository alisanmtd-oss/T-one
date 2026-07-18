from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


CONFIG_PATH = Path("config") / "github_capability_registry.json"

DECISION_ORDER = {
    "adopt_reference": 0,
    "pilot_isolated": 1,
    "reference_only": 2,
    "watch": 3,
    "reject_mainline": 4,
}


def load_github_capability_registry(root: Path) -> dict[str, Any]:
    path = root / CONFIG_PATH
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _candidate_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = payload.get("candidates", [])
    if not isinstance(candidates, list):
        return []
    return [item for item in candidates if isinstance(item, dict)]


def summarize_github_capabilities(
    root: Path,
    *,
    decisions: set[str] | None = None,
    category: str = "",
) -> list[dict[str, Any]]:
    payload = load_github_capability_registry(root)
    labels = payload.get("decision_labels", {})
    labels = labels if isinstance(labels, dict) else {}
    rows: list[dict[str, Any]] = []
    for item in _candidate_rows(payload):
        decision = str(item.get("decision") or "watch").strip()
        item_category = str(item.get("category") or "other").strip()
        if decisions is not None and decision not in decisions:
            continue
        if category and item_category != category:
            continue
        allowed = item.get("allowed_surfaces", [])
        blocked = item.get("blocked_surfaces", [])
        rows.append(
            {
                "repo": str(item.get("repo") or "unknown/unknown"),
                "category": item_category,
                "decision": decision,
                "decision_label": str(labels.get(decision) or decision),
                "source_trust": str(item.get("source_trust") or "unknown"),
                "license": str(item.get("license") or "UNASSERTED"),
                "last_verified_push": str(item.get("last_verified_push") or ""),
                "fit": str(item.get("fit") or ""),
                "allowed_surfaces": [str(value) for value in allowed if value] if isinstance(allowed, list) else [],
                "blocked_surfaces": [str(value) for value in blocked if value] if isinstance(blocked, list) else [],
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            DECISION_ORDER.get(str(row["decision"]), 99),
            str(row["category"]),
            str(row["repo"]).lower(),
        ),
    )


def evaluate_github_candidate(
    root: Path,
    repo: str,
    *,
    requested_surface: str = "schema_reference",
    request_install: bool = False,
    request_store_credentials: bool = False,
    request_real_external_action: bool = False,
    security_scan_passed: bool = False,
    license_review_passed: bool = False,
    pin_verified: bool = False,
    isolated_worker_confirmed: bool = False,
) -> dict[str, Any]:
    payload = load_github_capability_registry(root)
    policy = payload.get("policy", {})
    policy = policy if isinstance(policy, dict) else {}
    normalized_repo = str(repo or "").strip().lower()
    candidate = next(
        (
            item
            for item in _candidate_rows(payload)
            if str(item.get("repo") or "").strip().lower() == normalized_repo
        ),
        None,
    )
    if candidate is None:
        return {
            "repo": repo,
            "allowed": False,
            "decision": str(policy.get("unknown_repository_decision") or "block_unknown"),
            "reasons": ["未知仓库默认阻断，必须先核验来源、许可证、依赖、Skill 和网络权限。"],
        }

    reasons: list[str] = []
    allowed_surfaces = candidate.get("allowed_surfaces", [])
    allowed_surfaces = allowed_surfaces if isinstance(allowed_surfaces, list) else []
    blocked_surfaces = candidate.get("blocked_surfaces", [])
    blocked_surfaces = blocked_surfaces if isinstance(blocked_surfaces, list) else []
    decision = str(candidate.get("decision") or "watch")

    if decision in {"watch", "reject_mainline"}:
        reasons.append("当前分级不允许进入主线运行时。")
    if requested_surface in blocked_surfaces:
        reasons.append(f"请求面 {requested_surface} 被显式禁止。")
    if requested_surface and requested_surface not in allowed_surfaces:
        reasons.append(f"请求面 {requested_surface} 不在允许清单。")
    if request_install and not bool(policy.get("auto_install_allowed", False)):
        reasons.append("项目禁止从 GitHub 自动安装。")
    if request_store_credentials and not bool(policy.get("store_credentials_allowed", False)):
        reasons.append("GitHub 候选不得接触店铺凭据。")
    if request_real_external_action and not bool(policy.get("real_external_actions_allowed", False)):
        reasons.append("GitHub 候选不得直接执行真实外部动作。")
    if decision == "pilot_isolated":
        if bool(policy.get("security_scan_required_before_pilot", True)) and not security_scan_passed:
            reasons.append("隔离试点前的依赖/Skill 安全扫描尚未通过。")
        if bool(policy.get("license_review_required_before_pilot", True)) and not license_review_passed:
            reasons.append("隔离试点前的许可证复核尚未通过。")
        if bool(policy.get("pin_commit_or_release_required", True)) and not pin_verified:
            reasons.append("隔离试点尚未固定并核验 release/commit。")
        if bool(policy.get("isolated_worker_required", True)) and not isolated_worker_confirmed:
            reasons.append("隔离 worker 与最小文件/工具/网络权限尚未确认。")

    return {
        "repo": str(candidate.get("repo") or repo),
        "allowed": not reasons,
        "decision": decision,
        "requested_surface": requested_surface,
        "reasons": reasons or ["仅允许在登记的只读/隔离范围内使用。"],
        "security_scan_required": bool(policy.get("security_scan_required_before_pilot", True)),
        "license_review_required": bool(policy.get("license_review_required_before_pilot", True)),
        "pin_required": bool(policy.get("pin_commit_or_release_required", True)),
        "isolated_worker_required": bool(policy.get("isolated_worker_required", True)),
    }


def build_github_capability_report(root: Path, limit: int = 18) -> str:
    payload = load_github_capability_registry(root)
    rows = summarize_github_capabilities(root)
    counts = Counter(str(row["decision"]) for row in rows)
    labels = payload.get("decision_labels", {})
    labels = labels if isinstance(labels, dict) else {}
    lines = [
        "## GitHub 能力候选安全摘要",
        "",
        f"- 已核验 {len(rows)} 个与 Amazon、B2B、Agent、浏览器、CRM、采集、评测和供应链安全相关的仓库。",
        "- GitHub 热度不等于准入；未知仓库默认阻断，所有候选禁止自动安装、禁止接触店铺凭据、禁止直接执行真实外部动作。",
        "- 进入隔离试点前必须复核许可证、固定 release/commit、扫描依赖与 Skill，并限制文件、工具和网络权限。",
        "",
    ]
    if not rows:
        lines.append("- 暂无 GitHub 能力候选配置。")
        return "\n".join(lines).rstrip() + "\n"

    count_parts = []
    for decision in DECISION_ORDER:
        if counts.get(decision):
            count_parts.append(f"{labels.get(decision, decision)} {counts[decision]}")
    lines.append("- 分级：" + "；".join(count_parts) + "。")
    lines.append("")
    for row in rows[: max(0, limit)]:
        date_note = f"；最近核验更新 {row['last_verified_push']}" if row["last_verified_push"] else ""
        lines.append(
            f"- {row['repo']}：{row['decision_label']}；{row['fit']}"
            f"（许可证 {row['license']}{date_note}）"
        )
    if len(rows) > limit:
        lines.append(f"- 其余 {len(rows) - limit} 个候选保留在机器可读准入表中，不在页面展开。")
    return "\n".join(lines).rstrip() + "\n"
