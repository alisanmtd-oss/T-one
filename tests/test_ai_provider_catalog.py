import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_ecommerce_director.ai_provider_catalog import (
    configure_provider,
    load_provider_verification,
    provider_catalog_snapshot,
)


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
                        {
                            "id": "future-ai",
                            "label": "Future AI",
                            "api_format": "future_adapter",
                            "base_url": "",
                            "api_key_env": "",
                            "default_model": "",
                            "integration_state": "future_adapter",
                            "model_families": ["Future Text", "Future Vision"],
                            "capability_slots": ["text", "image"],
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
            self.assertEqual(len(snapshot["catalog"]), 3)
            self.assertEqual(snapshot["catalog_provider_count"], 3)
            self.assertEqual(snapshot["configurable_provider_count"], 2)
            self.assertEqual(snapshot["future_adapter_count"], 1)
            self.assertEqual(snapshot["model_family_slot_count"], 2)
            self.assertEqual(snapshot["configured_count"], 0)
            self.assertNotIn('"api_key":', json.dumps(snapshot))
            self.assertNotIn("secret-key", json.dumps(snapshot))

    def test_future_adapter_is_visible_but_cannot_be_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            snapshot = provider_catalog_snapshot(root)
            future = next(item for item in snapshot["catalog"] if item["id"] == "future-ai")
            self.assertEqual(future["integration_state"], "future_adapter")
            self.assertEqual(future["model_families"], ["Future Text", "Future Vision"])
            with self.assertRaisesRegex(ValueError, "只预留了位置"):
                configure_provider(
                    root,
                    {"preset_id": "future-ai", "name": "future-ai-user"},
                )

    def test_snapshot_merges_exact_model_receipts_without_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            (root / "config" / "multi_ai.json").write_text(
                json.dumps(
                    {
                        "providers": [
                            {
                                "name": "deepseek-sales",
                                "label": "DeepSeek sales",
                                "base_url": "https://api.deepseek.com",
                                "model": "deepseek-chat",
                                "enabled": True,
                                "requires_api_key": False,
                                "tasks": ["chat"],
                            }
                        ],
                        "routes": {"chat": ["deepseek-sales"]},
                    }
                ),
                encoding="utf-8",
            )
            (root / "config" / "ai_provider_verification_state.json").write_text(
                json.dumps(
                    {
                        "audited_at": "2026-07-19T12:00:00+08:00",
                        "catalog_provider_states": [
                            {
                                "provider_id": "deepseek",
                                "state": "verified",
                                "verified_models": ["deepseek-sales"],
                                "configured_models": ["deepseek-sales"],
                                "blocker": "",
                            }
                        ],
                        "live_receipts": [
                            {
                                "provider": "deepseek-sales",
                                "model": "deepseek-chat",
                                "status": "ok",
                                "latency_ms": 42,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            snapshot = provider_catalog_snapshot(root)
            model = snapshot["configured"][0]
            self.assertEqual(model["verification_state"], "verified")
            self.assertEqual(model["connection_test_http_status"], 0)
            self.assertEqual(model["verified_modalities"], ["text"])
            self.assertEqual(model["unknown_modalities"], ["image", "audio", "video", "files", "tool_use"])
            self.assertEqual(snapshot["verified_count"], 1)
            serialized = json.dumps(snapshot)
            self.assertNotIn("secret-value", serialized)
            self.assertNotIn("Bearer ", serialized)

    def test_invalid_verification_state_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            (root / "config" / "ai_provider_verification_state.json").write_text(
                json.dumps(
                    {
                        "catalog_provider_states": [
                            {"provider_id": "deepseek", "state": "magically_connected"}
                        ],
                        "live_receipts": [],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(load_provider_verification(root), {})

    def test_snapshot_merges_exact_multimodal_receipt_without_promoting_other_models(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            (root / "config" / "multi_ai.json").write_text(
                json.dumps(
                    {
                        "providers": [
                            {
                                "name": "deepseek-sales",
                                "label": "DeepSeek sales",
                                "base_url": "https://api.deepseek.com",
                                "model": "deepseek-chat",
                                "enabled": True,
                                "requires_api_key": False,
                                "tasks": ["chat"],
                            },
                            {
                                "name": "deepseek-other",
                                "label": "DeepSeek other",
                                "base_url": "https://api.deepseek.com",
                                "model": "deepseek-reasoner",
                                "enabled": True,
                                "requires_api_key": False,
                                "tasks": ["chat"],
                            },
                        ],
                        "routes": {"chat": ["deepseek-sales", "deepseek-other"]},
                    }
                ),
                encoding="utf-8",
            )
            (root / "config" / "ai_provider_verification_state.json").write_text(
                json.dumps(
                    {
                        "audited_at": "2026-07-20T07:53:00+08:00",
                        "catalog_provider_states": [
                            {
                                "provider_id": "deepseek",
                                "state": "verified",
                                "verified_models": ["deepseek-sales"],
                            }
                        ],
                        "live_receipts": [
                            {
                                "provider": "deepseek-sales",
                                "model": "deepseek-chat",
                                "status": "ok",
                            }
                        ],
                        "modality_receipts": [
                            {
                                "provider": "deepseek-sales",
                                "model": "deepseek-chat",
                                "status": "ok",
                                "modalities": ["image", "files"],
                                "evidence": "outputs/formal-app.json",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            snapshot = provider_catalog_snapshot(root)
            verified, other = snapshot["configured"]
            self.assertEqual(verified["verified_modalities"], ["text", "image", "files"])
            self.assertEqual(verified["unknown_modalities"], ["audio", "video", "tool_use"])
            self.assertEqual(verified["modality_receipt_refs"], ["outputs/formal-app.json"])
            self.assertEqual(other["verified_modalities"], [])
            self.assertEqual(snapshot["modality_counts"]["text"], 1)
            self.assertEqual(snapshot["modality_counts"]["image"], 1)
            self.assertEqual(snapshot["modality_counts"]["files"], 1)
            self.assertEqual(snapshot["modality_counts"]["video"], 0)

    def test_verification_state_accepts_utf8_bom_for_powershell_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            path = root / "config" / "ai_provider_verification_state.json"
            path.write_text(
                json.dumps(
                    {
                        "catalog_provider_states": [
                            {"provider_id": "deepseek", "state": "verified"}
                        ],
                        "live_receipts": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8-sig",
            )
            self.assertEqual(load_provider_verification(root)["catalog_provider_states"][0]["state"], "verified")


if __name__ == "__main__":
    unittest.main()
