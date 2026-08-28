from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_ecommerce_director.deepseek_harness_runtime import (
    DeepSeekHarnessRuntime,
    DeepSeekHarnessToolGateway,
)


class DeepSeekHarnessRuntimeTest(unittest.TestCase):
    def _installed_fixture(self, root: Path) -> tuple[Path, Path, Path]:
        root.mkdir(parents=True, exist_ok=True)
        node = root / "node.exe"
        node.write_bytes(b"fixture")
        package = root / "node_modules" / "@deepseek-ai" / "dsh"
        (package / "lib").mkdir(parents=True)
        (package / "lib" / "bin.js").write_text("// fixture\n", encoding="utf-8")
        (package / "package.json").write_text(
            json.dumps(
                {
                    "name": "@deepseek-ai/dsh",
                    "version": "0.1.0-rc.6",
                    "license": "MIT",
                    "repository": {"url": "https://github.com/deepseek-ai/deepseek-harness.git"},
                }
            ),
            encoding="utf-8",
        )
        home = root / "dsh-home"
        (home / "profiles" / "web").mkdir(parents=True)
        return node, package, home

    def test_discovers_official_windows_install_without_bash_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            node, package, home = self._installed_fixture(Path(tmp))
            runtime = DeepSeekHarnessRuntime.discover(
                node_candidates=[node],
                package_candidates=[package],
                home_candidates=[home],
            )

            status = runtime.status()
            self.assertTrue(status["installed"])
            self.assertEqual(status["version"], "0.1.0-rc.6")
            self.assertEqual(status["license"], "MIT")
            self.assertTrue(status["official_repository"])
            self.assertTrue(status["developer_preview"])
            command = runtime.command("web", workspace=Path(tmp))
            self.assertEqual(command[:2], [str(node), str(package / "lib" / "bin.js")])
            self.assertEqual(command[2:4], ["--profile", "web"])
            self.assertEqual(len(command), 4)

    def test_project_integration_uses_one_mcp_gateway_for_existing_tone_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            node, package, home = self._installed_fixture(root / "runtime")
            runtime = DeepSeekHarnessRuntime.discover(
                node_candidates=[node],
                package_candidates=[package],
                home_candidates=[home],
            )
            prepared = runtime.prepare_project(root / "project", python_executable=sys.executable)

            self.assertEqual(prepared["foundation"], "deepseek_harness")
            self.assertEqual(prepared["transport"], "mcp_stdio")
            self.assertTrue(Path(prepared["patch_path"]).is_file())
            self.assertTrue(Path(prepared["manifest_path"]).is_file())
            self.assertEqual(prepared["mcp_server"]["command"], sys.executable)
            self.assertIn("ai_ecommerce_director.deepseek_harness_mcp", prepared["mcp_server"]["args"])
            serialized = json.dumps(prepared, ensure_ascii=False)
            self.assertNotIn("api_key", serialized.lower())
            self.assertNotIn("token", serialized.lower())

    def test_gateway_exposes_real_computer_controls_and_all_desktop_bridge_methods(self) -> None:
        gateway = DeepSeekHarnessToolGateway()
        tool_names = {item["name"] for item in gateway.list_tools()}
        self.assertTrue(
            {
                "tone_desktop_snapshot",
                "tone_desktop_mouse",
                "tone_desktop_keyboard",
                "tone_desktop_window",
                "tone_browser",
                "tone_methods",
                "tone_invoke",
            }.issubset(tool_names)
        )

        methods = gateway.call_tool("tone_methods", {})
        self.assertTrue(methods["ok"])
        self.assertIn("desktop_mouse_action", methods["methods"])
        self.assertIn("desktop_keyboard_action", methods["methods"])
        self.assertIn("desktop_browser_action", methods["methods"])

        with patch(
            "ai_ecommerce_director.deepseek_harness_runtime.desktop_control.desktop_control_snapshot",
            return_value={"ok": True, "mouse": True, "keyboard": True, "browser": True},
        ):
            snapshot = gateway.call_tool("tone_desktop_snapshot", {})
        self.assertEqual(snapshot, {"ok": True, "mouse": True, "keyboard": True, "browser": True})

    def test_mutating_computer_tool_requires_explicit_owner_confirmation(self) -> None:
        gateway = DeepSeekHarnessToolGateway()
        with self.assertRaises(PermissionError):
            gateway.call_tool("tone_desktop_mouse", {"action": "move", "x": 1, "y": 2})

        with patch(
            "ai_ecommerce_director.deepseek_harness_runtime.desktop_control.desktop_mouse_action",
            return_value={"ok": True, "action": "move"},
        ) as action:
            result = gateway.call_tool(
                "tone_desktop_mouse",
                {"action": "move", "x": 1, "y": 2, "owner_confirmed": True},
            )
        self.assertTrue(result["ok"])
        action.assert_called_once()

    def test_real_stdio_mcp_roundtrip_lists_tone_computer_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "ai_ecommerce_director.deepseek_harness_mcp",
                    "--root",
                    tmp,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            assert process.stdin is not None
            assert process.stdout is not None
            process.stdin.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {"protocolVersion": "2025-06-18"},
                    }
                )
                + "\n"
            )
            process.stdin.flush()
            initialized = json.loads(process.stdout.readline())
            self.assertEqual(initialized["result"]["serverInfo"]["name"], "t-one-deepseek-harness")

            process.stdin.write(
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
                + "\n"
            )
            process.stdin.flush()
            listed = json.loads(process.stdout.readline())
            names = {item["name"] for item in listed["result"]["tools"]}
            self.assertIn("tone_desktop_mouse", names)
            self.assertIn("tone_invoke", names)
            process.stdin.close()
            self.assertEqual(process.wait(timeout=10), 0)
            process.stdout.close()
            assert process.stderr is not None
            process.stderr.close()


if __name__ == "__main__":
    unittest.main()
