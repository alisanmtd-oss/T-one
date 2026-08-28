from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop_app"
BUILD = DESKTOP / "build"
RUNTIME_TEMPLATE = BUILD / "runtime-template"
RUNTIME_DIRECTORY = BUILD / "t-one-runtime"
RUNTIME_EXE = RUNTIME_DIRECTORY / "t-one-runtime.exe"
WORKSPACE_LOCATOR = BUILD / "teelab-agent-root.json"
RUNTIME_SCRIPTS = (
    "scripts/browser_click_collect.js",
    "scripts/browser_ai_native_roundtrip.ps1",
    "scripts/lib/shein_store_surface.psm1",
    "scripts/shein_us_open_store_surface.ps1",
)


def require_sanitized_tree() -> None:
    # NSIS still fails to open deeply nested app-builder-lib templates when
    # the public staging root is too long, even with modern Windows long-path
    # support enabled.  Fail before the expensive PyInstaller build and tell
    # maintainers to use a short sanitized staging path.
    longest_template = (
        ROOT
        / "desktop_app"
        / "node_modules"
        / ".pnpm"
        / ("app-builder-lib@26.15.3_" + "x" * 33)
        / "node_modules"
        / "app-builder-lib"
        / "templates"
        / "nsis"
        / "include"
        / "allowOnlyOneInstallerInstance.nsh"
    )
    if len(str(longest_template)) >= 255:
        raise RuntimeError(
            "Windows NSIS build path is too long. Regenerate the sanitized "
            "public staging tree under a short path such as C:\\Users\\<user>\\t-one-build."
        )
    audit_path = ROOT / "PUBLIC_RELEASE_AUDIT.json"
    if not audit_path.is_file():
        raise RuntimeError(
            "Build the installer from a generated sanitized public staging tree; "
            "PUBLIC_RELEASE_AUDIT.json is missing."
        )
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("status") != "ready_for_final_review" or audit.get("findings"):
        raise RuntimeError("The sanitized public-tree audit is not clean.")


def copy_runtime_template() -> None:
    if RUNTIME_TEMPLATE.exists():
        shutil.rmtree(RUNTIME_TEMPLATE)
    RUNTIME_TEMPLATE.mkdir(parents=True)
    for directory in ("config", "knowledge_packs"):
        source = ROOT / directory
        if source.is_dir():
            shutil.copytree(source, RUNTIME_TEMPLATE / directory)
    for relative in RUNTIME_SCRIPTS:
        source = ROOT / relative
        if not source.is_file():
            raise FileNotFoundError(relative)
        target = RUNTIME_TEMPLATE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for directory in ("projects", "tasks", "logs", "outputs"):
        (RUNTIME_TEMPLATE / directory).mkdir(parents=True, exist_ok=True)


def write_workspace_locator() -> None:
    config_path = DESKTOP / "app-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    payload = {
        "project_root": "",
        "backend_port": int(config.get("backend_port") or 8767),
        "start_path": str(config.get("start_path") or "/desktop?view=dashboard"),
        "python_executable": "",
        "runtime_mode": "bundled",
    }
    BUILD.mkdir(parents=True, exist_ok=True)
    WORKSPACE_LOCATOR.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_runtime_executable(*, clean: bool) -> None:
    work_path = BUILD / "pyinstaller-work"
    spec_path = BUILD / "pyinstaller-spec"
    if clean:
        for path in (work_path, spec_path, RUNTIME_DIRECTORY):
            if path.exists():
                shutil.rmtree(path)
        legacy_onefile = BUILD / "t-one-runtime.exe"
        if legacy_onefile.exists():
            legacy_onefile.unlink()
    assets = ROOT / "ai_ecommerce_director" / "desktop_assets"
    separator = os.pathsep
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--name",
        "t-one-runtime",
        "--distpath",
        str(BUILD),
        "--workpath",
        str(work_path),
        "--specpath",
        str(spec_path),
        "--paths",
        str(ROOT),
        "--collect-submodules",
        "ai_ecommerce_director",
        "--hidden-import",
        "ai_ecommerce_director._desktop_workspace_template",
        "--add-data",
        f"{assets}{separator}ai_ecommerce_director/desktop_assets",
        str(DESKTOP / "runtime_entry.py"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    if not RUNTIME_EXE.is_file():
        raise RuntimeError("PyInstaller did not create t-one-runtime.exe")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args()
    require_sanitized_tree()
    write_workspace_locator()
    copy_runtime_template()
    build_runtime_executable(clean=not args.no_clean)
    print(f"Prepared bundled runtime: {RUNTIME_EXE}")
    print(f"Prepared workspace locator: {WORKSPACE_LOCATOR}")
    print(f"Prepared first-run workspace template: {RUNTIME_TEMPLATE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
