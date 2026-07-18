import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_ecommerce_director.credential_store import (
    credential_reference_catalog,
    credential_store_path,
    load_credential,
    resolve_credential,
    save_credential,
)


@unittest.skipUnless(os.name == "nt", "Windows DPAPI is required")
class CredentialStoreTests(unittest.TestCase):
    def test_dpapi_store_never_writes_plaintext_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            result = save_credential(root, "ai:test-provider", "top-secret-value")
            raw = credential_store_path(root).read_text(encoding="utf-8")

            self.assertEqual(result["persist_status"], "local_encrypted")
            self.assertNotIn("top-secret-value", raw)
            self.assertEqual(load_credential(root, "ai:test-provider"), "top-secret-value")

    def test_explicit_provider_credential_wins_over_legacy_environment_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            save_credential(root, "ai:test-provider", "new-provider-key")

            with patch.dict(os.environ, {"OPENAI_API_KEY": "old-environment-key"}):
                value = resolve_credential(
                    root,
                    credential_ref="ai:test-provider",
                    api_key_env="OPENAI_API_KEY",
                )

            self.assertEqual(value, "new-provider-key")

    def test_reference_catalog_returns_metadata_without_secret_material(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            save_credential(
                root,
                "store:amazon-us-01",
                "store-secret-value",
                metadata={
                    "purpose": "store_platform_api",
                    "project_id": "growth",
                    "store_binding_id": "amazon-us-01",
                    "platform": "amazon",
                    "country_site": "US",
                    "label": "Amazon US 授权",
                    "provider_id": "amazon_sp_api",
                    "authorization_surface": "selling_partner_api",
                    "verification_status": "live_verified",
                    "verified_at": "2026-07-18T04:00:00+00:00",
                    "marketplace_ids": "ATVPDKIKX0DER",
                    "ignored": "must-not-leak",
                },
            )

            catalog = credential_reference_catalog(root)
            serialized = str(catalog)

            self.assertEqual(catalog[0]["reference"], "store:amazon-us-01")
            self.assertTrue(catalog[0]["available"])
            self.assertEqual(catalog[0]["metadata"]["store_binding_id"], "amazon-us-01")
            self.assertEqual(catalog[0]["metadata"]["provider_id"], "amazon_sp_api")
            self.assertEqual(catalog[0]["metadata"]["verification_status"], "live_verified")
            self.assertNotIn("store-secret-value", serialized)
            self.assertNotIn("ciphertext", serialized)
            self.assertNotIn("must-not-leak", serialized)


if __name__ == "__main__":
    unittest.main()
