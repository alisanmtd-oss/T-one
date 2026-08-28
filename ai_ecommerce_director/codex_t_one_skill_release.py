from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REGISTRY_PATH = Path("config") / "u34_codex_t_one_skill_release.json"
PUBLIC_TREE_PATH = Path("public_codex_t_one_skill")

REQUIRED_RELEASE_FILES = {
    ".gitignore",
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "README.zh-CN.md",
    "ROADMAP.md",
    "SECURITY.md",
    "assets/t-one-chat-workspace.png",
    "docs/FILE_GUIDE.md",
    "skill/codex-t-one-operator/SKILL.md",
    "skill/codex-t-one-operator/agents/openai.yaml",
    "skill/codex-t-one-operator/references/capability-status.md",
    "skill/codex-t-one-operator/references/product-model.md",
    "skill/codex-t-one-operator/references/troubleshooting.md",
    "skill/codex-t-one-operator/references/workflow-and-approvals.md",
}

PRIVATE_PATH_PATTERNS = (
    re.compile(r"(^|/)\.git(/|$)", re.IGNORECASE),
    re.compile(r"(^|/)\.env(?:\.|$)", re.IGNORECASE),
    re.compile(r"(^|/)(desktop_app|outputs|runtime_data)(/|$)", re.IGNORECASE),
    re.compile(r"(^|/)config/current_task_queue\.json$", re.IGNORECASE),
    re.compile(r"\.(?:db|sqlite|sqlite3|pem|key|pfx)$", re.IGNORECASE),
)

SECRET_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return ""


def _frontmatter_keys(skill_text: str) -> set[str]:
    if not skill_text.startswith("---\n"):
        return set()
    delimiter_index = skill_text.find("\n---\n", 4)
    if delimiter_index < 0:
        return set()
    header = skill_text[4:delimiter_index]
    return {
        line.split(":", 1)[0].strip()
        for line in header.splitlines()
        if line.strip() and not line.startswith((" ", "\t")) and ":" in line
    }


def inspect_codex_t_one_skill_release(root: Path) -> dict[str, Any]:
    registry = _load_json(root / REGISTRY_PATH)
    public_tree = root / PUBLIC_TREE_PATH
    files = sorted(path for path in public_tree.rglob("*") if path.is_file())
    relative_paths = {
        path.relative_to(public_tree).as_posix()
        for path in files
    }
    public_repo = registry.get("public_repository", {})
    community_core = registry.get("community_core", {})
    source_tree = registry.get("source_tree", {})
    clean_install = registry.get("clean_install", {})
    truth = registry.get("truth", {})

    readme_en = _read_text(public_tree / "README.md")
    readme_zh = _read_text(public_tree / "README.zh-CN.md")
    skill_path = public_tree / "skill" / "codex-t-one-operator" / "SKILL.md"
    skill_text = _read_text(skill_path)
    capability_text = _read_text(
        public_tree
        / "skill"
        / "codex-t-one-operator"
        / "references"
        / "capability-status.md"
    )
    agent_metadata = _read_text(
        public_tree / "skill" / "codex-t-one-operator" / "agents" / "openai.yaml"
    )
    text_corpus = "\n".join(
        _read_text(path)
        for path in files
        if path.suffix.casefold() in {".md", ".yaml", ".yml", ".json", ".txt"}
    )
    private_path_violations = [
        item
        for item in sorted(relative_paths)
        if any(pattern.search(item) for pattern in PRIVATE_PATH_PATTERNS)
    ]
    secret_matches = [
        pattern.pattern
        for pattern in SECRET_PATTERNS
        if pattern.search(text_corpus)
    ]

    referenced_files = set(re.findall(r"`(references/[^`]+\.md)`", skill_text))
    skill_root = skill_path.parent
    all_reference_links_resolve = bool(referenced_files) and all(
        (skill_root / item).is_file() for item in referenced_files
    )
    required_states = {
        "`verified`",
        "`requires_setup`",
        "`partial`",
        "`planned`",
        "`private`",
        "`blocked`",
        "`unknown`",
    }

    public_url = str(public_repo.get("url") or "")
    community_url = str(community_core.get("url") or "")
    return {
        "schema_version": 1,
        "public_repository_url": public_url,
        "community_core_url": community_url,
        "public_repository_verified": public_repo.get("visibility") == "public"
        and len(str(public_repo.get("observed_head") or "")) == 40,
        "repositories_distinct": bool(public_url and community_url and public_url != community_url),
        "observed_public_head": str(public_repo.get("observed_head") or ""),
        "observed_community_core_head": str(community_core.get("observed_head") or ""),
        "observed_public_tag": str(public_repo.get("observed_tag") or ""),
        "remote_tree_parity": str(source_tree.get("remote_tree_parity") or ""),
        "public_tree_file_count": len(files),
        "installed_skill_file_count": int(
            clean_install.get("installed_skill_file_count") or 0
        ),
        "required_release_files_complete": REQUIRED_RELEASE_FILES == relative_paths,
        "bilingual_entrypoints_complete": bool(readme_en and readme_zh)
        and "README.zh-CN.md" in readme_en
        and "README.md" in readme_zh,
        "synthetic_screenshot_present": (
            public_tree / "assets" / "t-one-chat-workspace.png"
        ).is_file()
        and "synthetic" in readme_en.casefold()
        and "合成" in readme_zh,
        "file_guide_present": (public_tree / "docs" / "FILE_GUIDE.md").is_file(),
        "roadmap_present": (public_tree / "ROADMAP.md").is_file(),
        "capability_states_explicit": all(item in capability_text for item in required_states),
        "ui_shell_is_non_evidence": "UI shells" in readme_en
        and "页面空壳" in readme_zh
        and "a button" in capability_text,
        "private_path_violation_count": len(private_path_violations),
        "private_path_violations": private_path_violations,
        "secret_shape_match_count": len(secret_matches),
        "secret_shape_matches": secret_matches,
        "live_connector_count": int(truth.get("live_connector_count") or 0),
        "external_action_count": int(truth.get("external_action_count") or 0),
        "amazon_status": str(truth.get("amazon_status") or ""),
        "skill_validation_pass_count": int(
            clean_install.get("quick_validate_pass_count") or 0
        ),
        "clean_clone_succeeded": bool(public_repo.get("clean_clone_succeeded")),
        "isolated_install_succeeded": bool(clean_install.get("isolated_codex_home")),
        "skill_frontmatter_valid": _frontmatter_keys(skill_text) == {"name", "description"},
        "agent_metadata_present": all(
            key in agent_metadata
            for key in ("display_name:", "short_description:", "default_prompt:")
        ),
        "all_reference_links_resolve": all_reference_links_resolve,
        "external_ai_invocation_count": int(
            clean_install.get("external_ai_invocation_count") or 0
        ),
    }
