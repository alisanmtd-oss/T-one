from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "chat-first-workspace.html"


class ChatFirstDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = DEMO.read_text(encoding="utf-8")

    def test_daily_composer_uses_automatic_agent_selection(self) -> None:
        self.assertIn("T One 自动选择智能体", self.html)
        self.assertNotIn('class="model"', self.html)

    def test_settings_use_plain_language_progressive_disclosure(self) -> None:
        for label in ("智能体", "模型", "账号", "管理"):
            self.assertIn(f">{label}</button>", self.html)
        self.assertIn("邮箱与通信账号", self.html)
        self.assertIn("公开演示不接收或保存凭据", self.html)

    def test_account_walkthrough_only_lists_supported_read_only_validators(self) -> None:
        supported = (
            "Gmail（未连接）",
            "Outlook（未连接）",
            "其他企业邮箱（未连接）",
            "飞书（未连接）",
            "企业微信（未连接）",
            "微信公众号（未连接）",
            "WhatsApp Business（未连接）",
        )
        for label in supported:
            self.assertIn(label, self.html)
        self.assertNotIn("Telegram（未连接）", self.html)
        self.assertNotIn("个人微信（未连接）", self.html)

    def test_public_demo_never_claims_external_execution(self) -> None:
        self.assertIn("不会连接账号、读取邮件或联系人，也不会发送或发布", self.html)
        self.assertIn("不会连接真实账号或执行外部动作", self.html)


if __name__ == "__main__":
    unittest.main()
