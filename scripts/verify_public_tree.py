from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".html", ".json", ".md", ".py", ".txt", ".toml", ".yaml", ".yml"}
SKIP_FILES = {"scripts/verify_public_tree.py"}
FORBIDDEN_PATH_PARTS = {
    "browser_extension",
    "browser_profiles",
    "data",
    "desktop_app",
    "outputs",
    "recovered_conversations",
    "runtime_data",
    "screenshots",
    "source_of_truth",
}
PATTERNS = {
    "private user path": re.compile(r"(?i:[A-Z]:\\Users\\(?!USER|USERNAME|path\\to\\)[^\\\s]+)"),
    "marketplace product identifier": re.compile(r"(?i:\bB0[A-Z0-9]{8}\b)"),
    "seller portal URL": re.compile(r"(?i:https?://[^\s)]*sellercentral\.amazon\.)"),
    "private catalog URL": re.compile(r"(?i:https?://[^\s)]*yupoo\.com)"),
    "common live secret": re.compile(
        r"(?:sk-(?:proj-)?[A-Za-z0-9]{20,}|gh[oprsu]_[A-Za-z0-9]{20,}|"
        r"github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
        r"xox[baprs]-[A-Za-z0-9-]{10,}|"
        r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----)"
    ),
}


def main() -> int:
    findings: list[str] = []
    if (ROOT / "knowledge_packs" / "tiktok_shop").exists():
        findings.append("private TikTok Shop knowledge pack present")
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink():
            findings.append(f"symlink present: {relative}")
            continue
        if any(part.lower() in FORBIDDEN_PATH_PARTS for part in path.relative_to(ROOT).parts):
            findings.append(f"private path present: {relative}")
            continue
        if relative in SKIP_FILES or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(f"non-UTF-8 text file: {relative}")
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{label}: {relative}")
    if findings:
        print("Public tree verification failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("PASS: public tree contains no known private paths or secret patterns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
