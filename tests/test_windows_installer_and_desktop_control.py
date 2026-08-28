from __future__ import annotations

import json
import ctypes
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_ecommerce_director import desktop_control


ROOT = Path(__file__).resolve().parents[1]


class WindowsInstallerContractTests(unittest.TestCase):
    def test_windows_build_is_an_assisted_installer_with_shortcuts_and_uninstall(self) -> None:
        package = json.loads((ROOT / "desktop_app" / "package.json").read_text(encoding="utf-8"))
        target = package["build"]["win"]["target"]
        self.assertIn("nsis", target)
        nsis = package["build"]["nsis"]
        self.assertFalse(nsis["oneClick"])
        self.assertTrue(nsis["allowToChangeInstallationDirectory"])
        self.assertTrue(nsis["createDesktopShortcut"])
        self.assertTrue(nsis["createStartMenuShortcut"])
        self.assertEqual(nsis["include"], "installer.nsh")
        self.assertIn("Setup", nsis["artifactName"])
        installer_include = (ROOT / "desktop_app" / "installer.nsh").read_text(
            encoding="utf-8"
        )
        self.assertIn("T One CLI.lnk", installer_include)
        self.assertIn("T-One-CLI.cmd", installer_include)
        self.assertIn("customUnInstall", installer_include)

    def test_installed_app_can_find_the_workspace_locator_in_resources(self) -> None:
        package = json.loads((ROOT / "desktop_app" / "package.json").read_text(encoding="utf-8"))
        resources = package["build"]["extraResources"]
        self.assertIn("&& node prepare-build.js && electron-builder", package["scripts"]["dist:win"])
        self.assertTrue(
            any(item.get("to") == "teelab-agent-root.json" for item in resources),
            resources,
        )
        self.assertTrue(
            any(item.get("to") == "t-one-runtime" for item in resources),
            resources,
        )
        self.assertTrue(
            any(item.get("to") == "t-one-runtime/template" for item in resources),
            resources,
        )
        self.assertTrue(
            any(item.get("to") == "T-One-CLI.cmd" for item in resources),
            resources,
        )
        main_source = (ROOT / "desktop_app" / "main.js").read_text(encoding="utf-8")
        self.assertIn("process.resourcesPath", main_source)
        self.assertIn('"t-one-runtime.exe"', main_source)
        self.assertIn("ensureWorkspaceSeeded()", main_source)
        self.assertIn('["server", "--root", root, "--port", port]', main_source)
        self.assertIn('["bridge", "--root", root]', main_source)
        self.assertIn('PYTHONIOENCODING: "utf-8"', main_source)
        bridge_source = (ROOT / "desktop_app" / "bridge.py").read_text(encoding="utf-8")
        self.assertIn("def configure_utf8_stdio()", bridge_source)
        self.assertIn('reconfigure(encoding="utf-8", errors="strict")', bridge_source)
        self.assertIn("def run(root: Path) -> int:\n    configure_utf8_stdio()", bridge_source)

    def test_public_installer_build_refuses_unsanitized_private_source(self) -> None:
        source = (ROOT / "scripts" / "prepare_windows_installer.py").read_text(encoding="utf-8")
        self.assertIn('ROOT / "PUBLIC_RELEASE_AUDIT.json"', source)
        self.assertIn('audit.get("status") != "ready_for_final_review"', source)
        self.assertIn('"--onedir"', source)
        self.assertIn('"--collect-submodules"', source)
        self.assertIn("ai_ecommerce_director._desktop_workspace_template", source)
        self.assertNotIn('"desktop_workspace.recovery.pyc"', source)


class DesktopControlContractTests(unittest.TestCase):
    def test_real_desktop_control_is_exposed_through_the_existing_bridge(self) -> None:
        bridge = (ROOT / "desktop_app" / "bridge.py").read_text(encoding="utf-8")
        preload = (ROOT / "desktop_app" / "preload.js").read_text(encoding="utf-8")
        desktop = (ROOT / "desktop_app" / "teelab_desktop.py").read_text(encoding="utf-8")
        for method in (
            "desktop_control_snapshot",
            "desktop_mouse_action",
            "desktop_keyboard_action",
            "desktop_browser_action",
            "desktop_window_action",
        ):
            self.assertIn(f'"{method}"', bridge)
            self.assertIn(f'"{method}"', preload)
            self.assertIn(f"def {method}", desktop)

    def test_existing_tools_page_exposes_real_control_calls_without_a_new_page(self) -> None:
        source = (ROOT / "ai_ecommerce_director" / "desktop_workspace.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('data-desktop-control="true"', source)
        self.assertIn("desktop_mouse_action", source)
        self.assertIn("desktop_keyboard_action", source)
        self.assertIn("desktop_browser_action", source)
        self.assertIn("owner_confirmed:true", source)
        self.assertNotIn('id="settings-desktop-control"', source)

    def test_windows_input_layout_matches_native_send_input_contract(self) -> None:
        expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        self.assertEqual(ctypes.sizeof(desktop_control._Input), expected)

    def test_mutating_input_requires_explicit_owner_confirmation(self) -> None:
        with self.assertRaisesRegex(ValueError, "负责人明确确认"):
            desktop_control.desktop_mouse_action({"action": "click", "x": 10, "y": 10})
        with self.assertRaisesRegex(ValueError, "负责人明确确认"):
            desktop_control.desktop_keyboard_action({"action": "type", "text": "hello"})
        with self.assertRaisesRegex(ValueError, "负责人明确确认"):
            desktop_control.desktop_browser_action({"action": "open_url", "url": "https://example.com"})

    def test_browser_rejects_non_http_targets_before_opening(self) -> None:
        with patch.object(desktop_control.webbrowser, "open") as opener:
            with self.assertRaisesRegex(ValueError, "http/https"):
                desktop_control.desktop_browser_action(
                    {
                        "action": "open_url",
                        "url": "file:///C:/Windows/System32/cmd.exe",
                        "owner_confirmed": True,
                    }
                )
        opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
