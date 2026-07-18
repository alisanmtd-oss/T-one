import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_ecommerce_director.ai_provider_catalog import configure_provider, provider_catalog_snapshot


class AIProviderCatalogTests(unittest.TestCase):
    def _root(self, temp_dir: str) -> Path:
        root = Path(temp_dir)
        (root / "config").mkdir()
        (root / "config" / "ai_provider_catalog.json").write_text(
            json.dumps(
                {
                    "providers": [
                        {
                            "id": "deepseek",
                            "label": "DeepSeek",
                            "api_format": "openai",
                            "base_url": "https://api.deepseek.com",
                            "api_key_env": "DEEPSEEK_API_KEY",
                            "default_model": "deepseek-chat",
                        },
                        {
                            "id": "ollama",
                            "label": "Ollama",
                            "api_format": "openai",
                            "base_url": "http://127.0.0.1:11434/v1",
                            "api_key_env": "",
                            "default_model": "qwen3:latest",
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (root / "config" / "multi_ai.json").write_text(
            json.dumps({"providers": [], "routes": {"default": []}, "active_model_tier": "recommended"}),
            encoding="utf-8",
        )
        return root

    def test_configure_preset_never_writes_plaintext_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            with patch(
                "ai_ecommerce_director.ai_provider_catalog.save_credential",
                return_value={
                    "credential_ref": "provider/deepseek-sales",
                    "persist_status": "local_encrypted",
                },
            ):
                result = configure_provider(
                    root,
                    {"preset_id": "deepseek", "name": "deepseek-sales", "api_key": "secret-key"},
                )
            raw = (root / "config" / "multi_ai.json").read_text(encoding="utf-8-sig")
            self.assertNotIn("secret-key", raw)
            self.assertEqual(result["provider"]["name"], "deepseek-sales")
            self.assertEqual(result["key_status"]["persist_status"], "local_encrypted")

    def test_local_http_is_only_allowed_for_loopback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            with self.assertRaises(ValueError):
                configure_provider(
                    root,
                    {"preset_id": "ollama", "name": "bad-local", "base_url": "http://192.168.1.9:11434/v1"},
                )

    def test_snapshot_is_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            snapshot = provider_catalog_snapshot(root)
            self.assertEqual(len(snapshot["catalog"]), 2)
            self.assertEqual(snapshot["configured_count"], 0)
            self.assertNotIn('"api_key":', json.dumps(snapshot))
            self.assertNotIn("secret-key", json.dumps(snapshot))


if __name__ == "__main__":
    unittest.main()
