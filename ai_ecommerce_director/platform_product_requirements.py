from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .store_execution_scope import build_store_execution_scope
from .workspace_runtime import load_workspace_config
from .workspace_schema import find_store


ADAPTER_REGISTRY_PATH = Path("config") / "platform_adapter_registry.json"
PRODUCT_INTAKE_PATH = Path("data") / "product_intake"
EXECUTION_DOMAINS = (
    "listing",
    "orders",
    "inventory",
    "shipment",
    "settlement",
    "aftersales",
    "activities",
    "ads",
)
PLATFORM_ALIASES = {
    "tiktok_shop": "tiktok",
    "tiktokshop": "tiktok",
    "amazon_marketplace": "amazon",
}
SCHEMA_SOURCES = {
    "amazon": {
        "name": "Amazon Product Type Definitions (PTD)",
        "scope": "marketplace + product type",
        "reason": "Amazon 必填字段和变体主题取决于站点与商品类型，不能用固定表单猜测。",
    },
    "tiktok": {
        "name": "TikTok Shop 授权店铺类目属性",
        "scope": "shop + country/site + category",
        "reason": "TikTok Shop 类目属性按国家站点和真实店铺授权读取，东南亚不能合并为 SEA。",
    },
    "shein": {
        "name": "SHEIN 店铺类目授权与商品属性",
        "scope": "store + country/site + commerce mode + category authorization",
        "reason": "SHEIN 半托管、自运营和类目授权是不同轴，不能预编一套通用字段。",
    },
    "shopee": {
        "name": "Shopee 站点类目属性",
        "scope": "shop + country/site + category",
        "reason": "Shopee 商品字段按具体国家站点和授权店铺读取。",
    },
    "lazada": {
        "name": "Lazada 站点类目属性",
        "scope": "shop + country/site + category",
        "reason": "Lazada 商品字段按具体国家站点和授权店铺读取。",
    },
    "shopify": {
        "name": "Shopify Admin API 商品模型",
        "scope": "store + API version",
        "reason": "独立站扩展字段来自真实店铺的 metafield 与应用配置。",
    },
    "woocommerce": {
        "name": "WooCommerce REST API 商品模型",
        "scope": "store + plugin/schema version",
        "reason": "独立站扩展字段来自真实站点和已安装插件。",
    },
}

NON_AMAZON_SCHEMA_CONTEXT = {
    "tiktok": ["store_binding_id", "country_site", "commerce_mode", "category_id"],
    "shein": [
        "store_binding_id",
        "country_site",
        "commerce_mode",
        "category_authorization",
    ],
    "shopee": ["store_binding_id", "country_site", "category_id"],
    "lazada": ["store_binding_id", "country_site", "category_id"],
    "shopify": ["store_binding_id", "api_version", "store_schema_configuration"],
    "woocommerce": [
        "store_binding_id",
        "api_version",
        "plugin_schema_configuration",
    ],
}

AMAZON_PTD_RETRIEVAL_CONTRACT = {
    "discovery_operation": "searchDefinitionsProductTypes",
    "discovery_path": "definitions/2020-09-01/productTypes",
    "discovery_inputs": {
        "required": ["marketplaceIds"],
        "one_of": ["keywords", "itemName"],
        "optional": ["locale", "searchLocale"],
    },
    "definition_operation": "getDefinitionsProductType",
    "definition_path": "definitions/2020-09-01/productTypes/{productType}",
    "definition_inputs": {
        "required": ["productType", "marketplaceIds"],
        "defaults": {
            "productTypeVersion": "LATEST",
            "requirements": "LISTING",
            "requirementsEnforced": "ENFORCED",
            "locale": "DEFAULT",
        },
        "allowed_requirements": [
            "LISTING",
            "LISTING_PRODUCT_ONLY",
            "LISTING_OFFER_ONLY",
        ],
        "allowed_parentage_levels": ["NONE", "CHILD", "PARENT"],
        "optional": ["sellerId", "parentageLevel"],
    },
    "response_evidence": [
        "schema.link.resource",
        "schema.checksum",
        "metaSchema.link.resource",
        "metaSchema.checksum",
        "productTypeVersion",
        "propertyGroups",
        "locale",
        "marketplaceIds",
    ],
    "authorization": {
        "selling_partner_authorization_required": True,
        "product_listing_role_required": True,
    },
    "validation_policy": (
        "download_linked_schema_within_validity_window_verify_checksum_and_validate_"
        "with_downloaded_amazon_meta_schema"
    ),
    "release_evidence": {
        "released_at": "2026-05-27",
        "parentage_level_scope": {
            "NONE": "standalone_listing",
            "CHILD": "variation_child_listing",
            "PARENT": "variation_parent_listing",
        },
        "source": (
            "https://developer-docs.amazon.com/sp-api/docs/sp-api-release-notes"
        ),
    },
}

AMAZON_LISTING_RESTRICTIONS_PREFLIGHT_CONTRACT = {
    "operation": "getListingsRestrictions",
    "path": "listings/2021-08-01/restrictions",
    "required_inputs": ["asin", "sellerId", "marketplaceIds"],
    "optional_inputs": ["conditionType", "reasonLocale", "productType"],
    "gtin_exemption_policy": (
        "include_the_current_marketplace_product_type_when_available_to_evaluate_"
        "product_type_specific_gtin_exemption_restrictions"
    ),
    "do_not_infer": ["productType", "brand", "restriction_clearance"],
    "authorization_required": True,
    "connector_state": "blocked_until_sp_api_authorization",
    "source": (
        "https://developer-docs.amazon.com/sp-api/reference/getlistingsrestrictions"
    ),
    "released_at": "2026-05-27",
}

AMAZON_US_TITLE_ITEM_HIGHLIGHTS_CONTRACT = {
    "country_site": "US",
    "store_mode": "marketplace_seller",
    "announced_at": "2026-06-10",
    "effective_at": "2026-07-27",
    "state_at_capture": "scheduled_not_yet_effective",
    "title": {
        "maximum_characters_including_spaces": 75,
        "category_exception": ["media"],
    },
    "item_highlights": {
        "maximum_characters": 125,
        "schema_availability_required": True,
        "unsupported_field_means": "blocked_for_current_listing_not_policy_exception",
    },
    "native_ai": {
        "entry_label": "View enhancements",
        "brand_owner_review_window_days": 14,
        "non_brand_monitoring_path": "Manage All Inventory > View Change History",
        "output_is_editable_draft": True,
        "owner_confirmation_required_before_submission": True,
        "field_snapshot_diff_and_rollback_required": True,
        "seller_central_and_buyer_page_readback_required": True,
    },
    "scope_policy": (
        "do_not_apply_to_other_country_sites_or_categories_without_current_official_"
        "evidence_and_live_schema"
    ),
    "source": (
        "https://sellercentral.amazon.com/seller-forums/discussions/t/"
        "145b6d0f-999c-4555-896c-c694bda2e470"
    ),
}

AMAZON_LISTING_SUBMISSION_CONTRACT = {
    "preflight": {
        "listing_restrictions": AMAZON_LISTING_RESTRICTIONS_PREFLIGHT_CONTRACT,
        "effective_dated_content_rules": {
            "us_title_and_item_highlights": AMAZON_US_TITLE_ITEM_HIGHLIGHTS_CONTRACT,
        },
    },
    "individual": {
        "path": "listings/2021-08-01/items/{sellerId}/{sku}",
        "read_operation": "getListingsItem",
        "preview": {
            "operations": ["putListingsItem", "patchListingsItem"],
            "mode": "VALIDATION_PREVIEW",
            "persists": False,
            "success_status": "VALID",
        },
        "submit": {
            "operations": ["putListingsItem", "patchListingsItem"],
            "mode": "omit_validation_preview",
            "owner_confirmation_required": True,
            "statuses": {
                "ACCEPTED": "accepted_for_processing_not_live",
                "INVALID": "not_accepted_for_processing",
            },
        },
        "post_acceptance": {
            "readback_operation": "getListingsItem",
            "included_data": [
                "issues",
                "offers",
                "fulfillmentAvailability",
                "summaries",
            ],
            "notifications": {
                "transport": "Amazon EventBridge",
                "event_is_hint_not_complete_state": True,
                "subscription_lifecycle": {
                    "create_requires": [
                        "notification_type",
                        "payload_version",
                        "destination_id",
                    ],
                    "create_success_means": (
                        "subscription_record_created_not_delivery_verified"
                    ),
                    "readback_operation": "getSubscription",
                    "delivery_verification_required": True,
                    "delivery_evidence": [
                        "subscription_id",
                        "notification_id",
                        "publish_time",
                        "event_time",
                        "destination_receipt",
                        "processing_receipt",
                    ],
                    "business_state_readback_required": "getListingsItem",
                    "migration_with_filter_expression": {
                        "update_existing_subscription_supported": False,
                        "create_new_subscription_required": True,
                        "shadow_run_recommended_days": "7_to_14",
                        "old_subscription_delete_requires_owner_confirmation": True,
                    },
                },
                "filtering": {
                    "capability_is_notification_type_specific": True,
                    "filter_expression_and_event_filter_mutually_exclusive": True,
                    "optional_field_requires_has_guard": True,
                    "unsupported_filter_expression_types": [
                        "LISTINGS_ITEM_ISSUES_CHANGE",
                        "LISTINGS_ITEM_STATUS_CHANGE",
                        "LISTINGS_ITEM_MFN_QUANTITY_CHANGE",
                        "PRODUCT_TYPE_DEFINITIONS_CHANGE",
                        "BRANDED_ITEM_CONTENT_CHANGE",
                        "ITEM_PRODUCT_TYPE_CHANGE",
                    ],
                },
                "setup_prerequisites": [
                    "selling_partner_authorization",
                    "aws_account",
                    "eventbridge_target_resource",
                    "notifications_destination",
                    "notification_subscription",
                    "accepted_payload_version_validation",
                ],
                "LISTINGS_ITEM_STATUS_CHANGE": {
                    "eligible_party": "seller",
                    "payload_version": "1.0",
                    "filter_expression_supported": False,
                    "states": ["BUYABLE", "DISCOVERABLE", "DELETED"],
                    "absence_semantics": (
                        "missing_state_means_not_currently_applicable_not_root_cause"
                    ),
                    "follow_up_read": "getListingsItem",
                },
                "LISTINGS_ITEM_ISSUES_CHANGE": {
                    "eligible_party": "seller_or_vendor",
                    "expected_payload_version": "2023-12-13",
                    "validate_version_at_connection_time": True,
                    "filter_expression_supported": False,
                    "severities": ["ERROR", "WARNING", "NONE"],
                    "enforcement_actions": [
                        "LISTING_SUPPRESSED",
                        "ATTRIBUTE_SUPPRESSED",
                        "CATALOG_ITEM_REMOVED",
                        "SEARCH_SUPPRESSED",
                    ],
                    "none_does_not_prove_listing_healthy": True,
                    "not_all_listing_problems_have_defined_issues": True,
                    "follow_up_read": "getListingsItem",
                },
            },
            "buyer_page_verification_required_for_publication_claim": True,
        },
    },
    "bulk": {
        "feed_type": "JSON_LISTINGS_FEED",
        "asynchronous": True,
        "processing_statuses": [
            "IN_QUEUE",
            "IN_PROGRESS",
            "DONE",
            "CANCELLED",
            "FATAL",
        ],
        "done_means": "processing_complete_result_document_still_required",
        "fatal_means": "outcome_unknown_until_result_document_and_item_readback",
        "report_required": ["header", "issues", "summary"],
        "message_operations": ["UPDATE", "PARTIAL_UPDATE", "PATCH", "DELETE"],
        "owner_confirmation_required_before_create_feed": True,
    },
    "authorization": {
        "selling_partner_authorization_required": True,
        "product_listing_role_required": True,
    },
    "observation_policy": (
        "api_acceptance_or_feed_completion_is_not_buyer_page_publication"
    ),
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _platform(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    return PLATFORM_ALIASES.get(raw, raw)


def _has_known_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip().lower().replace(" ", "_")
        return normalized not in {
            "",
            "unknown",
            "not_known",
            "not_provided",
            "not_verified",
            "pending_owner_input",
            "待提供",
            "未知",
        }
    return True


def _adapter_for_store(
    registry: dict[str, Any], platform: str, country_site: str, commerce_mode: str
) -> tuple[dict[str, Any] | None, list[str]]:
    candidates: list[dict[str, Any]] = []
    for raw in registry.get("adapters", []):
        if not isinstance(raw, dict) or _platform(raw.get("platform")) != platform:
            continue
        candidates.append(raw)
    if not candidates:
        return None, ["platform_adapter_not_registered"]

    reasons: list[str] = []
    for adapter in candidates:
        modes = {str(item or "").strip().lower() for item in adapter.get("commerce_modes", [])}
        if modes and commerce_mode not in modes:
            continue
        sites = {
            str(item or "").strip().upper()
            for key in ("country_sites", "planning_sites")
            for item in (adapter.get(key) if isinstance(adapter.get(key), list) else [])
        }
        sites_by_mode = adapter.get("sites_by_mode")
        if isinstance(sites_by_mode, dict):
            sites.update(
                str(item or "").strip().upper()
                for item in sites_by_mode.get(commerce_mode, [])
                if str(item or "").strip()
            )
        if sites and country_site not in sites and "GLOBAL" not in sites:
            reasons.append("country_site_pending_verification")
        return adapter, reasons
    return candidates[0], ["commerce_mode_not_supported_by_adapter"]


def _adapter_candidates_for_channel(
    registry: dict[str, Any], platform: str, country_site: str
) -> tuple[list[dict[str, Any]], list[str]]:
    candidates = [
        raw
        for raw in registry.get("adapters", [])
        if isinstance(raw, dict) and _platform(raw.get("platform")) == platform
    ]
    if not candidates:
        return [], ["platform_adapter_not_registered"]
    supported_sites = {
        str(item or "").strip().upper()
        for adapter in candidates
        for key in ("country_sites", "planning_sites")
        for item in (adapter.get(key) if isinstance(adapter.get(key), list) else [])
        if str(item or "").strip()
    }
    for adapter in candidates:
        sites_by_mode = adapter.get("sites_by_mode")
        if not isinstance(sites_by_mode, dict):
            continue
        supported_sites.update(
            str(item or "").strip().upper()
            for values in sites_by_mode.values()
            if isinstance(values, list)
            for item in values
            if str(item or "").strip()
        )
    reasons = []
    if supported_sites and country_site not in supported_sites and "GLOBAL" not in supported_sites:
        reasons.append("country_site_pending_verification")
    return candidates, reasons


def _non_amazon_schema_retrieval_contract(
    platform: str, *, execution_status: str
) -> dict[str, Any]:
    return {
        "contract_type": "authorized_live_schema_read",
        "operation": None,
        "operation_policy": "do_not_name_or_call_unverified_platform_operation",
        "required_context": list(
            NON_AMAZON_SCHEMA_CONTEXT.get(
                platform,
                ["store_binding_id", "country_site", "commerce_mode", "category_id"],
            )
        ),
        "required_response_evidence": [
            "authorized_store_scope",
            "schema_source_reference",
            "live_field_definitions",
            "observed_at",
        ],
        "authorization_required": True,
        "execution_status": execution_status,
    }


def _latest_product_catalog(root: Path, project_id: str) -> dict[str, Any]:
    project_dir = root / PRODUCT_INTAKE_PATH / project_id
    if not project_dir.exists():
        return {
            "status": "missing",
            "product_count": 0,
            "variant_count": 0,
            "duplicate_count": 0,
            "dynamic_fields": [],
            "source_extension_fields": [],
            "platform_schema_fields": [],
        }
    for intake_dir in sorted(
        (item for item in project_dir.iterdir() if item.is_dir()), reverse=True
    ):
        manifest = _load_json(intake_dir / "manifest.json")
        if not manifest:
            continue
        product_count = int(manifest.get("product_count") or 0)
        variant_count = int(manifest.get("variant_count") or 0)
        manual_fields = manifest.get("manual_fields") or []
        catalog = _load_json(intake_dir / "catalog.json")
        records = [
            item for item in catalog.get("records", []) if isinstance(item, dict)
        ]
        normalization_mode = str(
            catalog.get("normalization_mode") or "unknown"
        )
        source_extension_fields = [
            str(item)
            for item in (
                manifest.get("source_extension_fields")
                or catalog.get("source_extension_fields")
                or manifest.get("dynamic_fields")
                or []
            )
            if str(item).strip()
        ]
        required_fact_coverage = {
            "product_identity_and_variants": 0,
            "cost": 0,
            "price_or_pricing_rule": 0,
            "product_images": 0,
            "inventory_or_supply_rule": 0,
        }
        for record in records:
            fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
            if fields.get("sku") and (
                fields.get("product_name") or fields.get("product_id")
            ):
                required_fact_coverage["product_identity_and_variants"] += 1
            if _has_known_value(fields.get("cost")):
                required_fact_coverage["cost"] += 1
            if _has_known_value(fields.get("price")):
                required_fact_coverage["price_or_pricing_rule"] += 1
            if fields.get("image") or record.get("media_refs"):
                required_fact_coverage["product_images"] += 1
            if _has_known_value(fields.get("inventory")):
                required_fact_coverage["inventory_or_supply_rule"] += 1
        missing_required_facts = (
            [
                field
                for field, covered in required_fact_coverage.items()
                if covered < len(records)
            ]
            if records
            else list(required_fact_coverage)
            if manual_fields
            else []
        )
        has_catalog = bool(records)
        has_manual_references = bool(manual_fields)
        return {
            "status": (
                "partial"
                if has_catalog and missing_required_facts
                else "ready"
                if has_catalog
                else "partial"
                if has_manual_references
                else "empty"
            ),
            "status_reason": (
                "manual_references_require_structured_product_rows"
                if has_manual_references and not has_catalog
                else "normalized_rows_have_missing_required_facts"
                if has_catalog and missing_required_facts
                else "normalized_rows_complete"
                if has_catalog
                else "no_normalized_product_rows"
            ),
            "normalization_mode": normalization_mode,
            "product_count": product_count,
            "variant_count": variant_count,
            "duplicate_count": int(manifest.get("duplicate_count") or 0),
            "dynamic_fields": source_extension_fields,
            "source_extension_fields": source_extension_fields,
            "field_origin": str(
                manifest.get("catalog_field_origin")
                or catalog.get("field_origin")
                or "imported_source_columns_not_platform_schema"
            ),
            "platform_schema_fields": [],
            "ai_enrichment_status": str(
                manifest.get("ai_enrichment_status") or "awaiting_platform_target"
            ),
            "source_created_at": str(manifest.get("created_at") or ""),
            "required_fact_coverage": required_fact_coverage,
            "missing_required_facts": missing_required_facts,
        }
    return {
        "status": "missing",
        "product_count": 0,
        "variant_count": 0,
        "duplicate_count": 0,
        "dynamic_fields": [],
        "source_extension_fields": [],
        "platform_schema_fields": [],
    }


def _domain_statuses(
    *,
    workspace_id: str,
    project_id: str,
    store: dict[str, Any],
    platform: str,
    country_site: str,
    commerce_mode: str,
    ownership: str,
) -> tuple[dict[str, dict[str, Any]], str]:
    store_binding_id = str(store.get("id") or "")
    execution_identity = str(
        store.get("execution_identity_id") or store.get("execution_identity_ref") or ""
    ).strip()
    credential_ref = str(store.get("credential_ref") or "").strip()
    ad_account_identity = str(store.get("ad_account_identity") or "").strip()
    configured_domains = {
        str(item or "").strip().lower()
        for item in store.get("execution_domains", [])
        if str(item or "").strip()
    }
    browser_bound = bool(
        execution_identity.startswith("browser:")
        or store.get("browser_profile_id")
        or store.get("browser_profile_sequence")
        or store.get("browser_profile_seq")
    )
    seller_center_bound = "seller_center" in configured_domains
    stored_scopes = {
        str(item.get("domain") or "").strip().lower(): item
        for item in store.get("execution_scopes", [])
        if isinstance(item, dict)
    }
    result: dict[str, dict[str, Any]] = {}
    for domain in EXECUTION_DOMAINS:
        built = build_store_execution_scope(
            {
                "tenant_id": workspace_id,
                "project_id": project_id,
                "store_binding_id": store_binding_id,
                "execution_identity_ref": execution_identity,
                "platform": platform,
                "country_site": country_site,
                "commerce_mode": commerce_mode,
                "ownership": ownership,
                "domain": domain,
                "credential_ref": credential_ref,
                "ad_account_identity": ad_account_identity,
            }
        ).to_dict()
        stored = stored_scopes.get(domain)
        blocking_reasons = list(
            (stored or built).get("blocking_reasons") or []
        )
        if domain == "ads" and not ad_account_identity:
            status = "pending"
            reason = "ad_account_identity_required"
        elif stored and not stored.get("executable"):
            status = "unavailable" if stored.get("status") == "unsupported" else "pending"
            reason = blocking_reasons[0] if blocking_reasons else "execution_scope_blocked"
        elif not built.get("executable"):
            status = "unavailable" if built.get("status") == "unsupported" else "pending"
            reason = blocking_reasons[0] if blocking_reasons else "execution_scope_blocked"
        elif credential_ref and domain in configured_domains:
            status = "pending"
            reason = "authorization_reference_configured_connection_test_required"
        elif browser_bound and (seller_center_bound or domain in configured_domains):
            status = "browser_only"
            reason = "browser_profile_connected_api_not_authorized"
        elif domain in configured_domains and built.get("executable"):
            status = "read_only"
            reason = "execution_identity_configured_without_verified_write_capability"
        else:
            status = "pending"
            reason = "store_authorization_required"
        result[domain] = {
            "status": status,
            "reason": reason,
            "scope_key": str((stored or built).get("scope_key") or ""),
        }
    overall = "browser_only" if browser_bound and not credential_ref else "pending"
    if credential_ref:
        overall = "pending_connection_test"
    return result, overall


def build_platform_product_requirements_snapshot(
    root: Path, project_id: str, store_binding_id: str
) -> dict[str, Any]:
    project_id = str(project_id or "").strip().lower()
    store_binding_id = str(store_binding_id or "").strip().lower()
    workspace = load_workspace_config(root)
    found = find_store(workspace, store_binding_id)
    if found is None or str(found[0].get("id") or "").strip().lower() != project_id:
        raise ValueError("所选真实店铺不存在，或不属于当前项目。")
    project, channel, store = found
    raw_platform = _platform(store.get("platform") or channel.get("platform"))
    raw_country_site = str(
        store.get("country_site") or channel.get("country_site") or ""
    ).strip().upper()
    base_scope = build_store_execution_scope(
        {
            "tenant_id": str(workspace.get("workspace_id") or "default-workspace"),
            "project_id": project_id,
            "store_binding_id": store_binding_id,
            "execution_identity_ref": str(store.get("execution_identity_id") or ""),
            "platform": raw_platform,
            "country_site": raw_country_site,
            "commerce_mode": store.get("store_model"),
            "ownership": store.get("ownership"),
            "domain": "listing",
        }
    )
    platform = _platform(base_scope.platform)
    country_site = base_scope.country_site
    commerce_mode = base_scope.commerce_mode
    ownership = base_scope.ownership
    registry = _load_json(root / ADAPTER_REGISTRY_PATH)
    adapter, adapter_reasons = _adapter_for_store(
        registry, platform, country_site, commerce_mode
    )
    domains, connector_status = _domain_statuses(
        workspace_id=str(workspace.get("workspace_id") or "default-workspace"),
        project_id=project_id,
        store=store,
        platform=platform,
        country_site=country_site,
        commerce_mode=commerce_mode,
        ownership=ownership,
    )
    catalog = _latest_product_catalog(root, project_id)
    schema_source = SCHEMA_SOURCES.get(
        platform,
        {
            "name": "授权店铺商品字段定义",
            "scope": "platform + country/site + store + category",
            "reason": "平台动态字段必须从真实授权店铺或官方接口读取，不能由系统编造。",
        },
    )
    listing_status = domains["listing"]["status"]
    if listing_status in {"pending", "unavailable"}:
        schema_status = "needs_store_authorization"
    else:
        schema_status = "needs_live_schema_read"

    blockers = list(adapter_reasons)
    if catalog.get("status") in {"missing", "empty"}:
        blockers.append("product_data_required")
    elif catalog.get("status") == "partial":
        blockers.append("product_facts_incomplete")
    if schema_status == "needs_store_authorization":
        blockers.append("listing_authorization_required")
    status = "ready_for_live_schema" if not blockers else "needs_configuration"
    route_key = ":".join((platform, country_site, commerce_mode))
    if "product_data_required" in blockers:
        next_action = "先导入商品表或图片。"
    elif catalog.get("status_reason") == "manual_references_require_structured_product_rows":
        next_action = "当前只有手工来源说明；请导入含 SKU、商品和变体列的结构化表格，系统不会把说明文字冒充完整目录。"
    elif "product_facts_incomplete" in blockers:
        missing_facts = set(catalog.get("missing_required_facts") or [])
        if missing_facts == {"cost"}:
            next_action = "商品与变体已导入；还需负责人补充真实成本，AI 不会编造。"
        else:
            next_action = "商品与变体已导入但事实不完整；请按缺失清单补充真实来源，AI 不会编造。"
    elif "listing_authorization_required" in blockers:
        next_action = "先完成当前真实店铺的商品接口授权或浏览器执行身份绑定。"
    else:
        next_action = f"从 {schema_source['name']} 读取当前类目字段，再生成平台草稿。"
    return {
        "schema_version": 2,
        "status": status,
        "project_id": str(project.get("id") or project_id),
        "store_binding_id": str(store.get("id") or store_binding_id),
        "adapter_id": str((adapter or {}).get("id") or ""),
        "route_key": route_key,
        "scope": {
            "platform": platform,
            "country_site": country_site,
            "commerce_mode": commerce_mode,
            "ownership": ownership,
        },
        "connector": {
            "status": connector_status,
            "browser_status": (
                "connected"
                if connector_status == "browser_only"
                else "not_verified"
            ),
            "api_status": (
                "connection_test_required"
                if connector_status == "pending_connection_test"
                else "needs_authorization"
            ),
            "domains": domains,
        },
        "execution_evidence": {
            "mode": "pure_local_snapshot",
            "external_connector_call_count": 0,
            "external_action_count": 0,
            "platform_write_count": 0,
        },
        "catalog": catalog,
        "dynamic_product_schema": {
            "status": schema_status,
            "source": schema_source["name"],
            "scope": schema_source["scope"],
            "reason": schema_source["reason"],
            "fields": [],
            "field_policy": "read_live_schema_do_not_invent",
            "resolved_product_type": None,
            "resolved_product_type_version": None,
            "schema_resource": None,
            "schema_checksum": None,
            "observation_state": "unknown",
            "retrieval_contract": (
                AMAZON_PTD_RETRIEVAL_CONTRACT
                if platform == "amazon"
                else _non_amazon_schema_retrieval_contract(
                    platform,
                    execution_status=(
                        "blocked_until_store_authorization"
                        if schema_status == "needs_store_authorization"
                        else "ready_for_authorized_live_read"
                    ),
                )
            ),
        },
        "listing_submission_contract": (
            AMAZON_LISTING_SUBMISSION_CONTRACT if platform == "amazon" else None
        ),
        "required_owner_facts": [
            "product_identity_and_variants",
            "cost",
            "price_or_pricing_rule",
            "product_images",
            "inventory_or_supply_rule",
        ],
        "blocking_reasons": list(dict.fromkeys(blockers)),
        "next_action": next_action,
    }


def build_channel_product_requirements_snapshot(
    root: Path, project_id: str, channel_id: str
) -> dict[str, Any]:
    """Describe a planned channel without creating or assuming a real store."""

    project_id = str(project_id or "").strip().lower()
    channel_id = str(channel_id or "").strip().lower()
    workspace = load_workspace_config(root)
    project: dict[str, Any] | None = None
    channel: dict[str, Any] | None = None
    for raw_project in workspace.get("projects", []):
        if not isinstance(raw_project, dict):
            continue
        if str(raw_project.get("id") or "").strip().lower() != project_id:
            continue
        project = raw_project
        channel = next(
            (
                item
                for item in raw_project.get("channels", [])
                if isinstance(item, dict)
                and str(item.get("id") or "").strip().lower() == channel_id
            ),
            None,
        )
        break
    if project is None or channel is None:
        raise ValueError("所选计划渠道不存在，或不属于当前项目。")

    stores = [item for item in channel.get("stores", []) if isinstance(item, dict)]
    platform = _platform(channel.get("platform"))
    country_site = str(channel.get("country_site") or "").strip().upper()
    if stores:
        return {
            "schema_version": 2,
            "status": "store_selection_required",
            "project_id": str(project.get("id") or project_id),
            "channel_id": str(channel.get("id") or channel_id),
            "scope": {"platform": platform, "country_site": country_site},
            "store_binding_ids": [str(item.get("id") or "") for item in stores],
            "blocking_reasons": ["exact_store_binding_required"],
            "next_action": "该渠道已有真实店铺；请选择精确店铺后读取其连接状态和动态商品字段。",
        }

    registry = _load_json(root / ADAPTER_REGISTRY_PATH)
    adapters, adapter_reasons = _adapter_candidates_for_channel(
        registry, platform, country_site
    )
    catalog = _latest_product_catalog(root, project_id)
    schema_source = SCHEMA_SOURCES.get(
        platform,
        {
            "name": "授权店铺商品字段定义",
            "scope": "platform + country/site + store + category",
            "reason": "平台动态字段必须从真实授权店铺或官方接口读取，不能由系统编造。",
        },
    )
    required_dimensions = [
        str(item)
        for item in channel.get("required_dimensions", [])
        if str(item).strip()
    ]
    blockers = list(adapter_reasons)
    blockers.append("platform_store_required")
    if catalog.get("status") in {"missing", "empty"}:
        blockers.append("product_data_required")
    elif catalog.get("status") == "partial":
        blockers.append("product_facts_incomplete")
    domains = {
        domain: {
            "status": "unavailable",
            "reason": "platform_store_required",
            "scope_key": "",
        }
        for domain in EXECUTION_DOMAINS
    }
    supported_modes = sorted(
        {
            str(mode)
            for adapter in adapters
            for mode in adapter.get("commerce_modes", [])
            if str(mode).strip()
        }
    )
    return {
        "schema_version": 2,
        "status": "needs_platform_store",
        "project_id": str(project.get("id") or project_id),
        "channel_id": str(channel.get("id") or channel_id),
        "channel_name": str(channel.get("name") or ""),
        "adapter_candidates": [str(item.get("id") or "") for item in adapters],
        "route_key": f"{platform}:{country_site}:needs_platform_store",
        "scope": {
            "platform": platform,
            "country_site": country_site,
            "commerce_mode": None,
            "ownership": None,
            "store_binding_id": None,
        },
        "route_preflight": {
            "status": "completed_without_credentials",
            "known_dimensions": {
                "platform": platform,
                "country_site": country_site,
            },
            "required_dimensions": required_dimensions,
            "missing_dimensions": required_dimensions,
            "supported_commerce_modes": supported_modes,
            "policy": "do_not_create_or_assume_store_binding",
        },
        "connector": {
            "status": "needs_platform_store",
            "browser_status": "not_bound",
            "api_status": "not_authorized",
            "domains": domains,
        },
        "execution_evidence": {
            "mode": "pure_local_preflight",
            "external_connector_call_count": 0,
            "external_action_count": 0,
            "platform_write_count": 0,
        },
        "catalog": catalog,
        "dynamic_product_schema": {
            "status": "needs_platform_store",
            "source": schema_source["name"],
            "scope": schema_source["scope"],
            "reason": schema_source["reason"],
            "fields": [],
            "field_policy": "read_live_schema_do_not_invent",
            "resolved_product_type": None,
            "resolved_product_type_version": None,
            "schema_resource": None,
            "schema_checksum": None,
            "observation_state": "not_observed_no_store",
            "retrieval_contract": _non_amazon_schema_retrieval_contract(
                platform, execution_status="blocked_until_real_store_exists"
            ),
        },
        "listing_submission_contract": None,
        "blocking_reasons": list(dict.fromkeys(blockers)),
        "next_action": (
            "当前渠道还没有后台真实平台店铺。先确认店铺模式、归属和平台店铺 ID；"
            "建立独立店铺身份后再绑定浏览器或官方授权并读取当前类目字段。"
        ),
    }


__all__ = [
    "build_channel_product_requirements_snapshot",
    "build_platform_product_requirements_snapshot",
]
