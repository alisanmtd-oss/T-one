from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ChineseEntrypointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        cls.demo = (ROOT / "demo" / "chat-first-workspace.html").read_text(
            encoding="utf-8"
        )

    def test_default_github_readme_is_chinese_and_starts_with_download(self) -> None:
        self.assertIn("Windows 中文安装包", self.readme[:1800])
        self.assertIn("releases/latest", self.readme[:1800])
        self.assertIn("不会用代码也能安装", self.readme[:1800])
        self.assertIn("README.en.md", self.readme[:800])

    def test_public_desktop_has_truthful_chinese_capability_market(self) -> None:
        for capability_type in ("agent", "skill", "mcp", "cli"):
            self.assertIn(f'data-capability-type="{capability_type}"', self.demo)
        self.assertIn('id="capabilityMarket"', self.demo)
        self.assertIn('id="capabilityCategory"', self.demo)
        self.assertIn("已包含", self.demo)
        self.assertIn("未配置", self.demo)
        self.assertIn("未检测", self.demo)
        self.assertIn("公开离线版不会连接外部工具", self.demo)

    def test_assignable_demo_capabilities_are_local_and_labeled(self) -> None:
        self.assertIn("加入示例任务", self.demo)
        self.assertIn("仅保存在这台电脑的演示数据中", self.demo)
        self.assertNotIn("connected_verified", self.demo)


if __name__ == "__main__":
    unittest.main()
