import unittest

from ai_ecommerce_director.workspace_schema import (
    business_visible_project_tasks,
    find_store,
    find_task_context,
    is_business_bound_store,
    normalize_workspace_config,
)


class WorkspaceSchemaTests(unittest.TestCase):
    def test_business_store_visibility_covers_binding_and_authorization_states(self) -> None:
        cases = {
            "local_id_only": (
                {
                    "id": "local-draft",
                    "status": "operating",
                },
                False,
            ),
            "authorization_pending": (
                {
                    "id": "pending",
                    "external_id": "PLATFORM-PENDING",
                    "status": "operating",
                    "authorization_status": "pending_authorized_sync",
                },
                False,
            ),
            "authorization_expired": (
                {
                    "id": "expired",
                    "external_id": "PLATFORM-EXPIRED",
                    "status": "operating",
                    "authorization_status": "authorization_expired",
                },
                False,
            ),
            "authorized_store": (
                {
                    "id": "authorized",
                    "external_id": "PLATFORM-AUTHORIZED",
                    "status": "operating",
                    "authorization_status": "connection_ready",
                },
                True,
            ),
            "manual_browser_store": (
                {
                    "id": "browser-store",
                    "external_id": "BROWSER-BOUND",
                    "status": "reserved",
                    "connection_method": "browser_profile_manual",
                    "key_present": False,
                },
                True,
            ),
            "official_api_without_authorization": (
                {
                    "id": "api-store",
                    "external_id": "API-NOT-AUTHORIZED",
                    "status": "reserved",
                    "connection_method": "official_api",
                    "key_present": False,
                },
                False,
            ),
        }

        for label, (store, expected) in cases.items():
            with self.subTest(label=label):
                self.assertEqual(is_business_bound_store(store), expected)

    def test_business_task_gate_keeps_pending_store_in_configuration_only(self) -> None:
        workspace = normalize_workspace_config(
            {
                "schema_version": 3,
                "projects": [
                    {
                        "id": "commerce",
                        "channels": [
                            {
                                "id": "amazon-us",
                                "platform": "amazon",
                                "country_site": "US",
                                "stores": [
                                    {
                                        "id": "amazon-real",
                                        "external_id": "REAL-1",
                                        "status": "operating",
                                        "tasks": [{"id": "amazon-task"}],
                                    }
                                ],
                            },
                            {
                                "id": "shein-us",
                                "platform": "shein",
                                "country_site": "US",
                                "stores": [
                                    {
                                        "id": "shein-pending",
                                        "status": "needs_platform_store",
                                        "tasks": [{"id": "shein-placeholder-task"}],
                                    }
                                ],
                            },
                        ],
                        "workstreams": [{"id": "shared-workstream"}],
                    }
                ],
            }
        )

        project = workspace["projects"][0]
        self.assertEqual(
            {item["id"] for item in business_visible_project_tasks(project)},
            {"amazon-task", "shared-workstream"},
        )
        self.assertIsNotNone(find_store(workspace, "shein-pending"))
        self.assertIsNotNone(find_task_context(workspace, "shein-placeholder-task"))

    def test_same_platform_and_site_can_hold_multiple_isolated_stores(self) -> None:
        workspace = normalize_workspace_config(
            {
                "schema_version": 3,
                "workspace_name": "T-one",
                "projects": [
                    {
                        "id": "apparel-growth",
                        "name": "Apparel Growth",
                        "channels": [
                            {
                                "id": "amazon-us",
                                "name": "Amazon US",
                                "platform": "amazon",
                                "country_site": "US",
                                "stores": [
                                    {
                                        "id": "amazon-us-store-a",
                                        "name": "Store A",
                                        "store_model": "marketplace_seller",
                                        "ownership": "self_store",
                                        "tasks": [{"id": "listing-a", "name": "Listing A"}],
                                    },
                                    {
                                        "id": "amazon-us-store-b",
                                        "name": "Store B",
                                        "store_model": "marketplace_seller",
                                        "ownership": "self_store",
                                        "tasks": [{"id": "listing-b", "name": "Listing B"}],
                                    },
                                ],
                            }
                        ],
                        "workstreams": [],
                    }
                ],
            }
        )

        project = workspace["projects"][0]
        self.assertEqual(project["store_count"], 2)
        self.assertEqual(project["task_count"], 2)
        self.assertEqual(find_store(workspace, "amazon-us-store-a")[2]["name"], "Store A")
        self.assertEqual(
            find_task_context(workspace, "listing-b")[2]["id"],
            "amazon-us-store-b",
        )

    def test_legacy_store_task_and_project_workstream_migrate_separately(self) -> None:
        workspace = normalize_workspace_config(
            {
                "schema_version": 2,
                "projects": [
                    {
                        "id": "legacy",
                        "name": "Legacy Project",
                        "tasks": [
                            {
                                "id": "amazon-store-task",
                                "name": "Amazon US",
                                "platform": "amazon",
                                "country": "US",
                                "store_id": "store-external-id",
                            },
                            {
                                "id": "b2b-leads",
                                "name": "B2B Leads",
                                "platform": "b2b",
                            },
                        ],
                    }
                ],
            }
        )

        project = workspace["projects"][0]
        self.assertEqual(project["store_count"], 1)
        self.assertEqual(project["workstreams"][0]["id"], "b2b-leads")
        self.assertEqual(
            find_task_context(workspace, "amazon-store-task")[3]["scope_type"],
            "store_task",
        )
        self.assertEqual(
            find_task_context(workspace, "b2b-leads")[3]["scope_type"],
            "project_workstream",
        )


if __name__ == "__main__":
    unittest.main()
