from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {"PUBLIC_RELEASE_AUDIT.json", "SHA256SUMS.json"}
TEXT_SUFFIXES = {".cjs", ".cmd", ".css", ".html", ".js", ".json", ".md", ".ps1", ".py", ".toml", ".txt", ".yaml", ".yml"}
TEXT_NAMES = {".gitignore", "LICENSE"}


def public_files() -> list[str]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    )
    return sorted(
        path.decode("utf-8")
        for path in output.split(b"\0")
        if path
        and path.decode("utf-8") not in EXCLUDED
        and (ROOT / path.decode("utf-8")).is_file()
    )


def file_digest(path: Path) -> str:
    payload = path.read_bytes()
    if path.name in TEXT_NAMES or path.suffix.lower() in TEXT_SUFFIXES:
        payload = payload.replace(b"\r\n", b"\n")
    return hashlib.sha256(payload).hexdigest()


def build_manifest() -> dict[str, str]:
    return {
        relative: file_digest(ROOT / relative)
        for relative in public_files()
    }


def main() -> int:
    destination = ROOT / "SHA256SUMS.json"
    destination.write_text(
        json.dumps(build_manifest(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {destination.name} with {len(build_manifest())} public files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
