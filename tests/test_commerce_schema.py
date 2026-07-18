from unittest import TestCase

from ai_ecommerce_director.commerce_schema import (
    AGENT_REGISTRY,
    COMMERCE_DATA_SCHEMAS,
    COMMERCE_KNOWLEDGE_GRAPH_SCHEMA,
    agent_registry_summary,
    default_commerce_data_schema,
    validate_schema_payload,
)
from ai_ecommerce_director.data_contract import (
    PERMISSION_MATRIX,
    SYSTEM_STANDARDS,
    TABLE_CONTRACTS,
    contract_summary,
    default_data_contract,
    validate_contract_payload,
)


class CommerceSchemaTest(TestCase):
    def test_p0_commerce_entities_are_defined(self) -> None:
        required_entities = {
            "Product",
            "Creator",
            "Video",
            "Keyword",
            "Listing",
            "Store",
            "Order",
            "Supplier",
            "Signal",
            "Hypothesis",
            "Experiment",
            "Reinforcement",
            "Priority",
            "MarketCoverage",
            "Phase3Expansion",
        }

        self.assertEqual(required_entities, set(COMMERCE_DATA_SCHEMAS))
        for entity, schema in COMMERCE_DATA_SCHEMAS.items():
            self.assertTrue(schema["required_fields"], entity)
            self.assertTrue(schema["id_fields"], entity)
            self.assertTrue(schema["downstream_agents"], entity)

    def test_knowledge_graph_schema_has_nodes_edges_and_weight_policy(self) -> None:
        self.assertIn("product", COMMERCE_KNOWLEDGE_GRAPH_SCHEMA["node_types"])
        self.assertIn("creator", COMMERCE_KNOWLEDGE_GRAPH_SCHEMA["node_types"])
        self.assertIn("video", COMMERCE_KNOWLEDGE_GRAPH_SCHEMA["node_types"])
        self.assertIn("co_occurs_with", COMMERCE_KNOWLEDGE_GRAPH_SCHEMA["edge_types"])
        self.assertIn("raise_when", COMMERCE_KNOWLEDGE_GRAPH_SCHEMA["weight_policy"])

    def test_agent_registry_records_responsibility_permissions_and_version(self) -> None:
        registry = {item["agent"]: item for item in AGENT_REGISTRY}

        self.assertIn("AI Ecommerce Director", registry)
        self.assertIn("Knowledge Reviewer", registry)
        self.assertIn("Viral Content Intelligence", registry)
        self.assertIn("Market Coverage Intelligence Agent", registry)
        self.assertIn("Brand Matrix Agent", registry)
        for item in AGENT_REGISTRY:
            self.assertTrue(item["responsibility"])
            self.assertTrue(item["inputs"])
            self.assertTrue(item["outputs"])
            self.assertTrue(item["permissions"])
            self.assertTrue(item["version"].startswith("v"))

        summary = agent_registry_summary()
        self.assertEqual(summary["agent_count"], len(AGENT_REGISTRY))
        self.assertIn("queue approval", summary["permission_model"])

    def test_schema_payload_validation_surfaces_missing_fields(self) -> None:
        result = validate_schema_payload("Product", {"product_name": "Amino Acid Cleanser", "platform": "Amazon"})

        self.assertFalse(result["valid"])
        self.assertIn("country", result["missing_required_fields"])
        self.assertIn("source_url", result["missing_required_fields"])

    def test_default_schema_bundle_is_readable_by_future_agents(self) -> None:
        bundle = default_commerce_data_schema()

        self.assertEqual(bundle["schema_version"], "commerce-data-schema-v1")
        self.assertIn("entities", bundle)
        self.assertIn("data_contract", bundle)
        self.assertIn("knowledge_graph", bundle)
        self.assertIn("agent_registry", bundle)

    def test_data_contract_contains_original_and_gap_tables(self) -> None:
        required_tables = {
            "Product",
            "Creator",
            "Video",
            "Keyword",
            "Listing",
            "Review",
            "Store",
            "Order",
            "Supplier",
            "Factory",
            "Warehouse",
            "StrategyMemory",
            "FeedbackTicket",
            "LearningEvent",
            "KnowledgeNode",
            "AgentRegistry",
            "SourceDocument",
            "RawAsset",
            "ImportBatch",
            "AttachmentAsset",
            "KnowledgeEdge",
            "OrderItem",
            "PlatformRuleSnapshot",
            "FinanceTransaction",
            "InventoryLedger",
            "EntityTagMap",
            "ExperimentRun",
            "ActionOutcome",
            "ApprovalRequest",
            "AuditLog",
            "TaxonomyDictionary",
            "PIIVault",
            "EnterpriseAccount",
            "Quote",
            "Contract",
            "Inquiry",
            "AgentEvaluation",
            "SourceChunk",
            "IngestionRun",
            "LineageEvent",
            "EvidenceClaim",
            "PolicyDocument",
            "PolicyRule",
            "PolicyDiff",
            "EntityAlias",
            "KnowledgeRevision",
            "EvalCase",
            "EvalRun",
            "JudgeResult",
            "ErrorSlice",
            "RollbackGate",
            "ModelRegistry",
            "PromptVersion",
            "EventInbox",
            "EventDedup",
            "TaskQueue",
            "DeadLetter",
            "AgentActionLog",
            "DataSubjectRequest",
            "RetentionPolicy",
            "DeleteWorkflow",
            "ConsentRecord",
            "SensitiveDataFlag",
            "Company",
            "CompanyUser",
            "SharedCatalog",
            "QuoteLine",
            "PriceList",
            "Settlement",
            "Payout",
            "Invoice",
            "ReturnRMA",
            "RefundRecord",
            "PerformanceAlert",
            "AccountHealth",
            "RawExtractionRun",
            "PolicySnapshot",
            "BannedTerm",
            "IPRegistry",
            "CompetitorSnapshot",
            "ListingSnapshot",
            "PriceHistory",
            "VideoScene",
            "VideoHighlightFrame",
            "VideoComment",
            "VideoCommentIntelligence",
            "KnowledgeProvenance",
            "KnowledgeScore",
            "ConceptWeightHistory",
            "QualityMetricSnapshot",
            "ClaimRequirement",
            "ComplianceArtifact",
            "ContentRightsAsset",
            "CommercialDisclosure",
            "EnforcementEvent",
            "AppealCase",
            "QuerySnapshot",
            "CreativeSnapshot",
            "SeasonalEvent",
            "CreativePattern",
            "SignalEvent",
            "SignalSnapshot",
            "SignalThreshold",
            "SignalAlert",
            "SignalWeight",
            "Hypothesis",
            "HypothesisEvidence",
            "HypothesisScore",
            "Experiment",
            "ExperimentVariant",
            "ExperimentMetric",
            "ExperimentStopRule",
            "ExperimentScaleRule",
            "ExperimentOutcome",
            "PatternWeight",
            "PatternHistory",
            "StrategyAdjustment",
            "PriorityRebalanceLog",
            "TaskPriority",
            "Backlog",
            "PriorityScore",
        }

        self.assertEqual(required_tables, set(TABLE_CONTRACTS))
        self.assertEqual(contract_summary()["table_count"], len(required_tables))

    def test_each_data_contract_has_execution_ready_metadata(self) -> None:
        for table_name, table in TABLE_CONTRACTS.items():
            self.assertTrue(table["id_prefix"], table_name)
            self.assertTrue(table["fields"], table_name)
            self.assertTrue(table["primary_key"], table_name)
            self.assertTrue(table["unique_keys"], table_name)
            self.assertTrue(table["partition_by"], table_name)
            self.assertTrue(table["retention"], table_name)
            self.assertTrue(table["sample_json"], table_name)
            self.assertIn(table["data_layer"], {"raw", "silver", "gold"}, table_name)

    def test_contract_payload_validation_uses_required_fields_and_layer(self) -> None:
        source = validate_contract_payload("SourceDocument", {"source_id": "src_1"})
        product = validate_contract_payload(
            "Product",
            {
                "product_id": "prd_1",
                "product_name": "Amino Acid Cleanser",
                "platform": "Amazon",
                "country": "US",
                "category_path": "Beauty",
                "source_id": "src_1",
                "created_at_utc": "2026-06-08T00:00:00Z",
            },
        )

        self.assertFalse(source["valid"])
        self.assertIn("checksum", source["missing_required_fields"])
        self.assertTrue(product["valid"])
        self.assertEqual(source["data_layer"], "raw")

    def test_system_standards_cover_naming_time_currency_state_and_permissions(self) -> None:
        contract = default_data_contract()

        self.assertEqual(SYSTEM_STANDARDS["naming"]["prefixes"]["Product"], "prd_")
        self.assertEqual(SYSTEM_STANDARDS["naming"]["prefixes"]["RawAsset"], "raw_")
        self.assertEqual(SYSTEM_STANDARDS["naming"]["prefixes"]["KnowledgeEdge"], "edg_")
        self.assertEqual(SYSTEM_STANDARDS["naming"]["prefixes"]["SourceChunk"], "chk_")
        self.assertEqual(SYSTEM_STANDARDS["naming"]["prefixes"]["EventInbox"], "ein_")
        self.assertEqual(SYSTEM_STANDARDS["naming"]["prefixes"]["VideoScene"], "vsc_")
        self.assertEqual(SYSTEM_STANDARDS["naming"]["prefixes"]["BannedTerm"], "ban_")
        self.assertEqual(SYSTEM_STANDARDS["naming"]["prefixes"]["ClaimRequirement"], "clr_")
        self.assertEqual(SYSTEM_STANDARDS["naming"]["prefixes"]["CreativeSnapshot"], "crs_")
        self.assertEqual(SYSTEM_STANDARDS["time"]["database_timezone"], "UTC")
        self.assertIn("amount_usd", SYSTEM_STANDARDS["currency"]["required_fields"])
        self.assertIn("completed", SYSTEM_STANDARDS["status_machines"]["ExperimentRun"])
        self.assertIn("high_risk_ip_decision", PERMISSION_MATRIX["approval_required"])
        self.assertEqual(contract["closed_loop"]["flow"], ["StrategyMemory", "ExperimentRun", "ActionOutcome", "LearningEvent", "StrategyMemory"])

    def test_supporting_tables_preserve_raw_lineage_and_graph_edges(self) -> None:
        raw_asset = validate_contract_payload(
            "RawAsset",
            {
                "raw_asset_id": "raw_1",
                "source_id": "src_1",
                "asset_type": "csv",
                "storage_path": "data/raw/csv/file.csv",
                "sha256": "hash",
                "captured_at_utc": "2026-06-08T00:00:00Z",
            },
        )
        edge = validate_contract_payload(
            "KnowledgeEdge",
            {
                "edge_id": "edg_1",
                "source_node_id": "kno_1",
                "target_node_id": "kno_2",
                "edge_type": "PEAKS_DURING",
                "source_id": "src_1",
                "status": "active",
            },
        )
        order_item = validate_contract_payload(
            "OrderItem",
            {
                "order_item_id": "oit_1",
                "order_id": "ord_1",
                "line_item_id": "1",
                "platform": "TikTok Shop",
                "store_id": "sto_1",
                "qty": 1,
                "currency_original": "USD",
                "unit_price_original": 39.99,
            },
        )

        self.assertTrue(raw_asset["valid"])
        self.assertEqual(raw_asset["data_layer"], "raw")
        self.assertTrue(edge["valid"])
        self.assertEqual(edge["data_layer"], "gold")
        self.assertTrue(order_item["valid"])

    def test_governance_tables_support_lineage_policy_eval_and_events(self) -> None:
        chunk = validate_contract_payload(
            "SourceChunk",
            {
                "source_chunk_id": "chk_1",
                "source_id": "src_1",
                "chunk_index": 1,
                "chunk_type": "text",
                "content_hash": "hash",
                "created_at_utc": "2026-06-08T00:00:00Z",
            },
        )
        policy_diff = validate_contract_payload(
            "PolicyDiff",
            {
                "policy_diff_id": "pdif_1",
                "platform": "Amazon",
                "new_policy_document_id": "pdoc_1",
                "diff_type": "changed",
                "impact_level": "medium",
                "summary": "Metadata requirement changed.",
                "detected_at_utc": "2026-06-08T00:00:00Z",
                "review_status": "pending",
            },
        )
        eval_run = validate_contract_payload(
            "EvalRun",
            {
                "eval_run_id": "evr_1",
                "eval_suite": "listing_safety",
                "started_at_utc": "2026-06-08T00:00:00Z",
                "status": "started",
            },
        )
        event = validate_contract_payload(
            "EventInbox",
            {
                "event_inbox_id": "ein_1",
                "event_id": "evt_1",
                "event_source": "TikTok Shop webhook",
                "event_type": "order.created",
                "payload_hash": "hash",
                "received_at_utc": "2026-06-08T00:00:00Z",
                "status": "received",
            },
        )
        dsr = validate_contract_payload(
            "DataSubjectRequest",
            {
                "data_subject_request_id": "dsr_1",
                "subject_type": "Creator",
                "subject_ref": "crt_1",
                "request_type": "delete",
                "jurisdiction": "CA",
                "status": "received",
                "received_at_utc": "2026-06-08T00:00:00Z",
            },
        )

        self.assertTrue(chunk["valid"])
        self.assertEqual(chunk["data_layer"], "raw")
        self.assertTrue(policy_diff["valid"])
        self.assertEqual(policy_diff["data_layer"], "gold")
        self.assertTrue(eval_run["valid"])
        self.assertTrue(event["valid"])
        self.assertEqual(event["data_layer"], "raw")
        self.assertTrue(dsr["valid"])

    def test_contract_summary_groups_governance_eval_event_and_privacy_tables(self) -> None:
        summary = contract_summary()

        self.assertIn("PolicyDiff", summary["governance_tables"])
        self.assertIn("EvalRun", summary["eval_tables"])
        self.assertIn("EventInbox", summary["event_tables"])
        self.assertIn("DataSubjectRequest", summary["privacy_tables"])
        self.assertIn("Settlement", summary["commercial_extension_tables"])

    def test_intelligence_tables_support_tiktok_ip_snapshots_and_quality(self) -> None:
        video_scene = validate_contract_payload(
            "VideoScene",
            {
                "video_scene_id": "vsc_1",
                "video_id": "vid_1",
                "scene_index": 1,
                "scene_type": "hook",
                "source_id": "src_1",
            },
        )
        banned_term = validate_contract_payload(
            "BannedTerm",
            {
                "banned_term_id": "ban_1",
                "term": "Disney",
                "normalized_term": "disney",
                "language": "en",
                "risk_type": "ip",
                "severity": "critical",
                "source_id": "src_1",
                "status": "active",
            },
        )
        competitor = validate_contract_payload(
            "CompetitorSnapshot",
            {
                "competitor_snapshot_id": "csn_1",
                "platform": "Amazon",
                "snapshot_at_utc": "2026-06-08T00:00:00Z",
                "source_id": "src_1",
            },
        )
        score = validate_contract_payload(
            "KnowledgeScore",
            {
                "knowledge_score_id": "ksc_1",
                "entity_type": "KnowledgeNode",
                "entity_id": "kno_1",
                "source_trust": 0.75,
                "evidence_strength": 0.8,
                "recency_score": 0.9,
                "corroboration_score": 0.7,
                "final_score": 78.5,
                "score_version": "knowledge-score-v1",
                "calculated_at_utc": "2026-06-08T00:00:00Z",
            },
        )
        comment_intel = validate_contract_payload(
            "VideoCommentIntelligence",
            {
                "video_comment_intelligence_id": "vci_1",
                "video_id": "vid_1",
                "analysis_window": "7d",
                "comment_count": 100,
                "source_id": "src_1",
                "analyzed_at_utc": "2026-06-08T00:00:00Z",
            },
        )

        self.assertTrue(video_scene["valid"])
        self.assertTrue(banned_term["valid"])
        self.assertTrue(competitor["valid"])
        self.assertTrue(score["valid"])
        self.assertTrue(comment_intel["valid"])

    def test_commerce_brain_information_layers_cover_claims_rights_appeals_and_creatives(self) -> None:
        claim = validate_contract_payload(
            "ClaimRequirement",
            {
                "claim_requirement_id": "clr_1",
                "claim_text": "supports sleep",
                "normalized_claim": "supports sleep",
                "claim_type": "health",
                "required_evidence_types": ["substantiation"],
                "risk_level": "high",
                "source_id": "src_1",
                "status": "active",
            },
        )
        artifact = validate_contract_payload(
            "ComplianceArtifact",
            {
                "compliance_artifact_id": "caf_1",
                "artifact_type": "fcc",
                "entity_type": "Product",
                "entity_id": "prd_1",
                "source_id": "src_1",
                "review_status": "pending",
            },
        )
        rights = validate_contract_payload(
            "ContentRightsAsset",
            {
                "content_rights_asset_id": "cra_1",
                "asset_type": "music",
                "asset_name": "CML test track",
                "license_type": "commercial_music_library",
                "source_id": "src_1",
                "status": "active",
            },
        )
        disclosure = validate_contract_payload(
            "CommercialDisclosure",
            {
                "commercial_disclosure_id": "cdi_1",
                "platform": "TikTok",
                "relationship_type": "affiliate",
                "disclosure_visible": True,
                "review_status": "compliant",
                "source_id": "src_1",
                "checked_at_utc": "2026-06-08T00:00:00Z",
            },
        )
        enforcement = validate_contract_payload(
            "EnforcementEvent",
            {
                "enforcement_event_id": "enf_1",
                "platform": "TikTok Shop",
                "event_type": "score_change",
                "severity": "high",
                "event_at_utc": "2026-06-08T00:00:00Z",
                "source_id": "src_1",
            },
        )
        appeal = validate_contract_payload(
            "AppealCase",
            {
                "appeal_case_id": "apl_1",
                "platform": "TikTok Shop",
                "violation_type": "listing_claim",
                "appeal_reason": "Evidence provided.",
                "outcome": "pending",
                "source_id": "src_1",
            },
        )
        query = validate_contract_payload(
            "QuerySnapshot",
            {
                "query_snapshot_id": "qsn_1",
                "platform": "Amazon",
                "query_text": "amino acid cleanser",
                "normalized_query": "amino acid cleanser",
                "report_type": "search_query",
                "snapshot_at_utc": "2026-06-08T00:00:00Z",
                "source_id": "src_1",
            },
        )
        creative = validate_contract_payload(
            "CreativeSnapshot",
            {
                "creative_snapshot_id": "crs_1",
                "platform": "TikTok",
                "creative_type": "video",
                "snapshot_at_utc": "2026-06-08T00:00:00Z",
                "source_id": "src_1",
            },
        )
        season = validate_contract_payload(
            "SeasonalEvent",
            {
                "seasonal_event_id": "sev_1",
                "event_name": "Father's Day",
                "normalized_event_name": "fathers_day",
                "event_type": "holiday",
                "source_id": "src_1",
                "status": "active",
            },
        )
        pattern = validate_contract_payload(
            "CreativePattern",
            {
                "creative_pattern_id": "cpt_1",
                "pattern_name": "hook-body-close",
                "pattern_type": "script",
                "source_id": "src_1",
                "status": "active",
            },
        )

        self.assertTrue(claim["valid"])
        self.assertTrue(artifact["valid"])
        self.assertTrue(rights["valid"])
        self.assertTrue(disclosure["valid"])
        self.assertTrue(enforcement["valid"])
        self.assertTrue(appeal["valid"])
        self.assertTrue(query["valid"])
        self.assertTrue(creative["valid"])
        self.assertTrue(season["valid"])
        self.assertTrue(pattern["valid"])

    def test_contract_summary_groups_tiktok_risk_snapshot_and_quality_tables(self) -> None:
        summary = contract_summary()

        self.assertIn("VideoScene", summary["tiktok_content_tables"])
        self.assertIn("BannedTerm", summary["risk_intelligence_tables"])
        self.assertIn("CompetitorSnapshot", summary["snapshot_tables"])
        self.assertIn("KnowledgeScore", summary["quality_tables"])
        self.assertIn("RawExtractionRun", summary["extraction_tables"])
        self.assertIn("ClaimRequirement", summary["compliance_evidence_tables"])
        self.assertIn("ContentRightsAsset", summary["rights_tables"])
        self.assertIn("AppealCase", summary["account_risk_tables"])
        self.assertIn("QuerySnapshot", summary["market_signal_tables"])
