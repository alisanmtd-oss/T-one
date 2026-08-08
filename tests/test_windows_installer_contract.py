from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WindowsInstallerContractTests(unittest.TestCase):
    def test_assisted_installer_has_normal_windows_install_flow(self) -> None:
        package = json.loads((ROOT / "desktop_public" / "package.json").read_text(encoding="utf-8"))
        build = package["build"]
        self.assertEqual(build["win"]["target"], ["nsis"])
        self.assertFalse(build["nsis"]["oneClick"])
        self.assertTrue(build["nsis"]["allowToChangeInstallationDirectory"])
        self.assertTrue(build["nsis"]["createDesktopShortcut"])
        self.assertTrue(build["nsis"]["createStartMenuShortcut"])
        self.assertIn("Setup", build["nsis"]["artifactName"])

    def test_public_installer_contains_only_the_offline_demo_and_license(self) -> None:
        package = json.loads((ROOT / "desktop_public" / "package.json").read_text(encoding="utf-8"))
        sources = {item["from"] for item in package["build"]["extraResources"]}
        self.assertEqual(sources, {"../demo/chat-first-workspace.html", "../LICENSE"})
        main = (ROOT / "desktop_public" / "main.js").read_text(encoding="utf-8")
        self.assertIn("chat-first-workspace.html", main)
        self.assertNotIn("shell.openExternal", main)

    def test_repeatable_installer_acceptance_script_exists(self) -> None:
        acceptance = (ROOT / "scripts" / "accept_windows_installer.ps1").read_text(encoding="utf-8")
        self.assertIn("selectable_install_directory", acceptance)
        self.assertIn("installed_app_ready", acceptance)
        self.assertIn("Uninstall T One Community.exe", acceptance)

    def test_release_upload_does_not_require_a_publish_job_checkout(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "windows-installer.yml").read_text(encoding="utf-8")
        self.assertIn('--repo "$env:REPOSITORY"', workflow)
        self.assertIn("REPOSITORY: ${{ github.repository }}", workflow)

    def test_release_manifest_covers_current_public_files(self) -> None:
        from scripts.generate_sha256_manifest import build_manifest, file_digest

        recorded = json.loads((ROOT / "SHA256SUMS.json").read_text(encoding="utf-8"))
        self.assertEqual(recorded, build_manifest())
        installer_source = ROOT / "desktop_public" / "main.js"
        self.assertEqual(
            recorded[installer_source.relative_to(ROOT).as_posix()],
            file_digest(installer_source),
        )


if __name__ == "__main__":
    unittest.main()
