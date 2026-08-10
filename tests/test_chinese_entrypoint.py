from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ChineseEntrypointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        cls.html = (ROOT / "desktop_public" / "ui" / "index.html").read_text(encoding="utf-8")
        cls.app = (ROOT / "desktop_public" / "ui" / "app.js").read_text(encoding="utf-8")

    def test_default_github_readme_is_chinese_and_starts_with_download(self) -> None:
        self.assertIn("Windows 中文安装包", self.readme[:1800])
        self.assertIn("releases/latest", self.readme[:1800])
        self.assertIn("不会用代码也能安装", self.readme[:1800])
        self.assertIn("README.en.md", self.readme[:800])

    def test_public_desktop_has_truthful_chinese_capability_market(self) -> None:
        for capability_type in ("agent", "skill", "mcp", "cli"):
            self.assertIn(f"kind:'{capability_type}'", self.app)
        self.assertIn('id="marketView"', self.html)
        self.assertIn('id="marketCategory"', self.html)
        self.assertIn("已包含", self.app)
        self.assertIn("需配置", self.app)
        self.assertIn("需检测", self.app)
        self.assertIn("只有实际安装或检测后才显示可调用", self.html)

    def test_assignable_capabilities_are_task_scoped_and_truthful(self) -> None:
        self.assertIn("加入当前任务", self.app)
        self.assertIn("已保存，未连接", self.app)
        self.assertNotIn("connected_verified", self.app)


if __name__ == "__main__":
    unittest.main()
