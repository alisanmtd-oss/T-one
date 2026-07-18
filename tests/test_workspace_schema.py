import unittest

from ai_ecommerce_director.workspace_schema import (
    find_store,
    find_task_context,
    normalize_workspace_config,
)


class WorkspaceSchemaTests(unittest.TestCase):
    def test_same_platform_and_site_can_hold_multiple_isolated_stores(self) -> None:
        workspace = normalize_workspace_config(
            {
                "schema_version": 3,
                "workspace_name": "T One",
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
