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
        self.assertEqual(package["version"], "0.5.0")
        self.assertEqual(build["productName"], "T One 中文社区版")

    def test_public_installer_contains_local_workspace_and_license(self) -> None:
        package = json.loads((ROOT / "desktop_public" / "package.json").read_text(encoding="utf-8"))
        sources = {item["from"] for item in package["build"]["extraResources"]}
        self.assertEqual(sources, {"../LICENSE"})
        self.assertIn("preload.js", package["build"]["files"])
        self.assertIn("ui/**/*", package["build"]["files"])
        main = (ROOT / "desktop_public" / "main.js").read_text(encoding="utf-8")
        self.assertIn('"ui", "index.html"', main)
        self.assertIn("T One 中文社区版", main)
        self.assertNotIn("shell.openExternal", main)

    def test_repeatable_installer_acceptance_script_exists(self) -> None:
        acceptance = (ROOT / "scripts" / "accept_windows_installer.ps1").read_text(encoding="utf-8")
        self.assertIn("selectable_install_directory", acceptance)
        self.assertIn("installed_app_ready", acceptance)
        self.assertIn('Filter "Uninstall*.exe"', acceptance)

    def test_release_upload_does_not_require_a_publish_job_checkout(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "windows-installer.yml").read_text(encoding="utf-8")
        self.assertIn('--repo "$env:REPOSITORY"', workflow)
        self.assertIn("REPOSITORY: ${{ github.repository }}", workflow)

    def test_release_manifest_covers_current_public_files(self) -> None:
        from scripts.generate_sha256_manifest import TEXT_SUFFIXES, build_manifest, file_digest

        self.assertIn(".css", TEXT_SUFFIXES)
        recorded = json.loads((ROOT / "SHA256SUMS.json").read_text(encoding="utf-8"))
        self.assertEqual(recorded, build_manifest())
        installer_source = ROOT / "desktop_public" / "main.js"
        self.assertEqual(
            recorded[installer_source.relative_to(ROOT).as_posix()],
            file_digest(installer_source),
        )


if __name__ == "__main__":
    unittest.main()
