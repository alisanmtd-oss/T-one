from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DesktopWorkspaceRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main = (ROOT / "desktop_public" / "main.js").read_text(encoding="utf-8")
        cls.preload = (ROOT / "desktop_public" / "preload.js").read_text(encoding="utf-8")
        cls.html = (ROOT / "desktop_public" / "ui" / "index.html").read_text(encoding="utf-8")
        cls.app = (ROOT / "desktop_public" / "ui" / "app.js").read_text(encoding="utf-8")

    def test_desktop_uses_isolated_preload_api(self) -> None:
        self.assertIn("preload.js", self.main)
        self.assertIn("contextIsolation: true", self.main)
        self.assertIn("sandbox: true", self.main)
        self.assertIn("contextBridge.exposeInMainWorld", self.preload)
        self.assertNotIn("ipcRenderer", self.html)

    def test_projects_tasks_messages_and_files_have_real_local_handlers(self) -> None:
        for channel in (
            "workspace:load",
            "project:create",
            "task:create",
            "task:save-messages",
            "task:choose-files",
            "project:open-folder",
        ):
            self.assertIn(channel, self.main)
            self.assertIn(channel, self.preload)
        self.assertIn("每个项目一个文件夹", self.html)
        self.assertIn("新建项目", self.html)
        self.assertIn("新建任务", self.html)
        self.assertIn("历史对话", self.html)

    def test_market_assigns_capabilities_to_current_task(self) -> None:
        self.assertIn("capability:assign", self.main)
        self.assertIn("加入当前任务", self.app)
        self.assertNotIn("加入示例任务", self.html)
        for capability_type in ("Agent", "Skill", "MCP", "CLI"):
            self.assertIn(capability_type, self.html)

    def test_mcp_and_cli_registry_are_truthful_and_local(self) -> None:
        for channel in ("connection:save", "connection:detect-cli", "connection:test-mcp", "connection:remove"):
            self.assertIn(channel, self.main)
            self.assertIn(channel, self.preload)
        self.assertIn("已保存，未连接", self.app)
        self.assertIn("已检测", self.app)
        self.assertNotIn("已连接可用", self.app)
        self.assertIn("const target = safeValue(payload.target", self.main)
        self.assertIn("connection.detectedPath = safeValue", self.main)

    def test_detected_cli_can_run_only_from_the_current_task(self) -> None:
        self.assertIn("task:run-cli", self.main)
        self.assertIn("task:run-cli", self.preload)
        self.assertIn("cwd: taskFolder(project.id, task.id)", self.main)
        self.assertIn("shell: false", self.main)
        self.assertIn("at: safeValue(item.at", self.main)
        self.assertIn("text: safeValue(item.text", self.main)
        self.assertIn("请选择已检测的 CLI", self.main)
        self.assertIn("用所选 CLI 真实执行", self.html)
        self.assertIn("没有真实输出", self.app)


if __name__ == "__main__":
    unittest.main()
