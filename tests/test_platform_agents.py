import unittest

from ai_ecommerce_director.platform_agents import (
    list_public_agents,
    load_public_knowledge_packs,
    route_public_chat,
)


class PublicPlatformAgentTests(unittest.TestCase):
    def test_catalog_has_all_sanitized_non_tiktok_shop_packs(self) -> None:
        payload = load_public_knowledge_packs()
        ids = {item["id"] for item in payload["packs"]}
        self.assertEqual(len(ids), 13)
        self.assertNotIn("tiktok_shop", ids)
        self.assertTrue(
            {
                "aliexpress",
                "b2b_export",
                "ebay",
                "etsy",
                "global_local_channel",
                "google_ads_channel",
                "independent_commerce",
                "lazada",
                "meta_channel",
                "shein",
                "shopee",
                "tiktok_ads_channel",
                "walmart",
            }.issubset(ids)
        )
        self.assertTrue(all(not item["live_connection_claimed"] for item in list_public_agents()))

    def test_ordinary_chat_selects_one_platform_agent_without_external_execution(self) -> None:
        result = route_public_chat("这个商品适合速卖通哪些市场？缺少事实保持未知。")
        self.assertEqual(result["status"], "public_agent_selected")
        self.assertEqual(result["agent_id"], "aliexpress")
        self.assertFalse(result["live_connection_claimed"])
        self.assertFalse(result["external_execution_allowed"])

    def test_multi_platform_question_stays_a_comparison(self) -> None:
        result = route_public_chat("比较 Etsy 和 eBay 的上架边界")
        self.assertEqual(result["status"], "multi_platform_comparison")
        self.assertEqual(set(result["agent_ids"]), {"etsy", "ebay"})
        self.assertFalse(result["external_execution_allowed"])

    def test_tiktok_shop_pack_is_explicitly_excluded(self) -> None:
        result = route_public_chat("打开 TikTok Shop 智能体")
        self.assertEqual(result["status"], "excluded_private_pack")
        self.assertEqual(result["pack_id"], "tiktok_shop")
        self.assertFalse(result["external_execution_allowed"])

    def test_unknown_platform_requests_one_plain_language_input(self) -> None:
        result = route_public_chat("帮我看看这个商品")
        self.assertEqual(result["status"], "needs_platform")
        self.assertEqual(result["agent_ids"], [])


if __name__ == "__main__":
    unittest.main()
