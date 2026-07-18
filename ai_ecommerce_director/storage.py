from __future__ import annotations

import json
import os
import threading
import time
from json import JSONDecodeError
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Iterable

from .types import IntakeRecord


DATA_DIR = Path("data") / "real_world"
OUTPUT_DIR = Path("outputs")


# ---------------------------------------------------------------------------
# In-process record cache.
#
# The data lake can grow to tens of MB across many .jsonl files. Re-reading and
# JSON-parsing every file on each call made pages (e.g. /auto-mode) take ~15s.
# We cache the parsed payloads per file, keyed by (mtime_ns, size), so an
# unchanged file is parsed only once per process. Writes update the cache in
# place so it stays both warm and correct. A dedupe-key index per file lets
# append_record find an existing duplicate in O(1) instead of rescanning the
# whole file on every append (which made autonomous runs slower over time).
#
# All cache access and file writes are guarded by _CACHE_LOCK because the HTTP
# server is multi-threaded (ThreadingHTTPServer).
# ---------------------------------------------------------------------------
_CACHE_LOCK = threading.RLock()
FileSig = tuple[int, int, int]
_PAYLOAD_CACHE: dict[str, tuple[FileSig, list[dict[str, Any]]]] = {}
_KEY_INDEX_CACHE: dict[str, tuple[FileSig, dict[str, int]]] = {}


def _file_sig(path: Path) -> FileSig | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size, getattr(stat, "st_ctime_ns", 0))


def _cache_key(path: Path) -> str:
    """Use a canonical path for in-process caches.

    Several tests and local runs use temporary or relative roots with identical
    filenames. Keying only on the raw Path string can leak cached payloads across
    logically separate data lakes, which then shows stale products or fake stores
    in seller reports.
    """
    try:
        return str(path.resolve())
    except OSError:
        return str(path.absolute())


def _copy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Shallow-copy a payload and its mutable containers so cached state cannot
    be corrupted by callers that mutate record.fields/score/metadata in place."""
    copied = dict(payload)
    for key in ("fields", "score", "metadata"):
        value = copied.get(key)
        if isinstance(value, dict):
            copied[key] = dict(value)
    notes = copied.get("director_notes")
    if isinstance(notes, list):
        copied["director_notes"] = list(notes)
    return copied


def _cached_payloads(path: Path) -> list[dict[str, Any]]:
    """Return the parsed JSON payloads for a .jsonl file, using the cache when
    the file is unchanged. Caller must hold _CACHE_LOCK."""
    sig = _file_sig(path)
    if sig is None:
        return []
    cache_key = _cache_key(path)
    cached = _PAYLOAD_CACHE.get(cache_key)
    if cached is not None and cached[0] == sig:
        return cached[1]
    payloads: list[dict[str, Any]] = []
    for line in read_jsonl_lines(path):
        clean_line = line.lstrip("\ufeff").strip()
        if not clean_line:
            continue
        try:
            payload = json.loads(clean_line)
        except JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    _PAYLOAD_CACHE[cache_key] = (sig, payloads)
    _KEY_INDEX_CACHE.pop(cache_key, None)
    return payloads


def _build_record(payload: dict[str, Any]) -> IntakeRecord:
    """Build an IntakeRecord from a cached payload, copying mutable containers."""
    record = IntakeRecord.from_dict(payload)
    record.fields = dict(record.fields)
    record.score = dict(record.score)
    record.metadata = dict(record.metadata)
    record.director_notes = list(record.director_notes)
    return record


def _dedupe_index(path: Path) -> dict[str, int]:
    """Return {dedupe_key: first payload index} for a file. Caller holds lock."""
    cache_key = _cache_key(path)
    sig = _file_sig(path)
    cached = _KEY_INDEX_CACHE.get(cache_key)
    if cached is not None and sig is not None and cached[0] == sig:
        return cached[1]
    payloads = _cached_payloads(path)
    sig = _file_sig(path)
    index: dict[str, int] = {}
    for position, payload in enumerate(payloads):
        try:
            dedupe_key = record_dedupe_key(IntakeRecord.from_dict(payload))
        except (KeyError, TypeError, ValueError):
            continue
        if dedupe_key and dedupe_key not in index:
            index[dedupe_key] = position
    if sig is not None:
        _KEY_INDEX_CACHE[cache_key] = (sig, index)
    return index


def _atomic_write(path: Path, payloads: Iterable[dict[str, Any]]) -> None:
    """Write all payloads to a temp file then atomically replace the target, so
    an interrupted write can never truncate or destroy the existing data file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for payload in payloads:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    # On Windows os.replace raises PermissionError if another process (e.g. a
    # concurrent autonomous/training run) has the destination open for reading.
    # That is transient, so retry briefly before giving up.
    last_error: OSError | None = None
    for attempt in range(20):
        try:
            os.replace(tmp_path, path)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.1)
    try:
        tmp_path.unlink()
    except OSError:
        pass
    if last_error is not None:
        raise last_error


def _refresh_caches(path: Path, payloads: list[dict[str, Any]], keep_index: bool) -> None:
    """Re-point the caches at a just-written file. Caller holds lock."""
    cache_key = _cache_key(path)
    sig = _file_sig(path)
    if sig is None:
        _PAYLOAD_CACHE.pop(cache_key, None)
        _KEY_INDEX_CACHE.pop(cache_key, None)
        return
    _PAYLOAD_CACHE[cache_key] = (sig, payloads)
    existing_index = _KEY_INDEX_CACHE.get(cache_key)
    if keep_index and existing_index is not None:
        _KEY_INDEX_CACHE[cache_key] = (sig, existing_index[1])
    else:
        _KEY_INDEX_CACHE.pop(cache_key, None)


def append_record(root: Path, record: IntakeRecord) -> Path:
    path = record_path(root, record.record_type)
    key = record_dedupe_key(record)
    with _CACHE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        if key:
            payloads = _cached_payloads(path)
            index = _dedupe_index(path)
            position = index.get(key)
            if position is not None and 0 <= position < len(payloads):
                existing = _build_record(payloads[position])
                merged = merge_duplicate_record(existing, record)
                new_payloads = list(payloads)
                new_payloads[position] = merged.to_dict()
                _atomic_write(path, new_payloads)
                # Same key, same position -> the dedupe index stays valid.
                _refresh_caches(path, new_payloads, keep_index=True)
                return path
        payload = record.to_dict()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        _append_to_caches(path, payload, key)
    return path


def _append_to_caches(path: Path, payload: dict[str, Any], key: str) -> None:
    """Reflect a freshly appended line in the caches without re-reading the file.
    Caller holds lock."""
    cache_key = _cache_key(path)
    cached = _PAYLOAD_CACHE.get(cache_key)
    if cached is None:
        return  # Not cached yet; the next read will parse the file fresh.
    sig = _file_sig(path)
    if sig is None:
        _PAYLOAD_CACHE.pop(cache_key, None)
        _KEY_INDEX_CACHE.pop(cache_key, None)
        return
    payloads = cached[1]
    payloads.append(_copy_payload(payload))
    _PAYLOAD_CACHE[cache_key] = (sig, payloads)
    index_entry = _KEY_INDEX_CACHE.get(cache_key)
    if index_entry is not None:
        index = index_entry[1]
        if key and key not in index:
            index[key] = len(payloads) - 1
        _KEY_INDEX_CACHE[cache_key] = (sig, index)


def read_records(root: Path, record_type: str | None = None) -> list[IntakeRecord]:
    paths = [record_path(root, record_type)] if record_type else sorted((root / DATA_DIR).glob("*.jsonl"))
    payload_groups: list[list[dict[str, Any]]] = []
    with _CACHE_LOCK:
        for path in paths:
            if not path.exists():
                continue
            # Snapshot the cached payload references under the lock; build the
            # records outside the lock to keep critical sections short.
            payload_groups.append(list(_cached_payloads(path)))
    records: list[IntakeRecord] = []
    for group in payload_groups:
        for payload in group:
            try:
                records.append(_build_record(payload))
            except (KeyError, TypeError, ValueError):
                continue
    return records


def read_jsonl_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8-sig").splitlines()
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()


def write_records(root: Path, record_type: str, records: list[IntakeRecord]) -> Path:
    path = record_path(root, record_type)
    payloads = [record.to_dict() for record in records]
    with _CACHE_LOCK:
        _atomic_write(path, payloads)
        _refresh_caches(path, payloads, keep_index=False)
    return path


def find_record(root: Path, record_id: str) -> IntakeRecord | None:
    for record in read_records(root):
        if record.record_id == record_id:
            return record
    return None


def update_record(root: Path, updated_record: IntakeRecord) -> Path:
    records = read_records(root, updated_record.record_type)
    replaced = False
    next_records: list[IntakeRecord] = []
    for record in records:
        if record.record_id == updated_record.record_id:
            next_records.append(updated_record)
            replaced = True
        else:
            next_records.append(record)
    if not replaced:
        raise ValueError(f"Record not found: {updated_record.record_id}")
    return write_records(root, updated_record.record_type, next_records)


def write_report(root: Path, report_date: str, content: str) -> Path:
    path = root / OUTPUT_DIR / f"daily_report_{report_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def record_path(root: Path, record_type: str) -> Path:
    safe_name = record_type.replace("-", "_")
    return root / DATA_DIR / f"{safe_name}.jsonl"


def newest(records: Iterable[IntakeRecord], limit: int = 5) -> list[IntakeRecord]:
    return sorted(records, key=lambda record: record.created_at, reverse=True)[:limit]


def record_dedupe_key(record: IntakeRecord) -> str:
    fields = record.fields
    if record.record_type == "video_script":
        script_key = normalized_value(fields.get("script_key"))
        if script_key:
            return f"video_script:{script_key}"
        source_video_key = normalized_value(fields.get("source_video_key") or fields.get("video_case_key"))
        script_type = normalized_value(fields.get("script_type"))
        if source_video_key and script_type:
            return f"video_script:{source_video_key}:{script_type}"
    if record.record_type == "social_account_profile":
        store_id = normalized_value(fields.get("store_id") or fields.get("target_store_id"))
        account = normalized_value(fields.get("account_handle") or fields.get("target_account_handle") or fields.get("official_account_handle"))
        role = normalized_value(fields.get("account_role"))
        if store_id and account:
            return f"social_account_profile:{store_id}:{account}:{role}"
    if record.record_type == "store_profile":
        platform = normalized_value(fields.get("marketplace") or fields.get("platform") or fields.get("source_platform"))
        store = normalized_value(fields.get("store_id") or fields.get("store_name"))
        country = normalized_value(fields.get("country_code") or fields.get("shop_region") or fields.get("market"))
        if platform and store:
            return f"store_profile:{platform}:{store}:{country}"
    if record.record_type == "video_publish_plan":
        video = normalized_value(fields.get("video_file_ref") or fields.get("script_key") or fields.get("source_breakdown_id"))
        account = normalized_value(fields.get("target_account_handle") or fields.get("account_handle"))
        title = normalized_value(fields.get("publish_title"))
        if video and account:
            return f"video_publish_plan:{video}:{account}"
        if title and account:
            return f"video_publish_plan:{title}:{account}"
    if record.record_type == "creative_inspiration":
        product = normalized_value(fields.get("product_name") or fields.get("product_theme"))
        angle = normalized_value(fields.get("creative_angle") or fields.get("content_angle"))
        material_type = normalized_value(fields.get("material_type"))
        if product and angle:
            return f"creative_inspiration:{product}:{angle}:{material_type}"
    if record.record_type == "feedback_ticket":
        page = normalized_value(fields.get("page_url"))
        module = normalized_value(fields.get("module_area"))
        text = normalized_value(fields.get("feedback_text") or fields.get("suggestion") or fields.get("actual_behavior"))
        if page and text:
            return f"feedback_ticket:{page}:{text[:100]}"
        if module and text:
            return f"feedback_ticket:{module}:{text[:100]}"
    target_id = normalized_value(fields.get("product_target_id"))
    if target_id and record.record_type == "collection_job":
        category = normalized_value(fields.get("data_category") or fields.get("ranking_type") or fields.get("record_type_to_collect"))
        keyword = normalized_value(fields.get("keyword") or fields.get("target_keyword") or fields.get("search_keyword"))
        platform = normalized_value(fields.get("marketplace") or fields.get("source_platform") or fields.get("platform_list"))
        url = normalized_value(fields.get("url"))
        return f"collection_job:target:{target_id}:{platform}:{category}:{keyword or url}"
    for key in [
        "url",
        "video_url",
        "product_url",
        "profile_url",
        "page_url",
        "source_url",
        "image_url",
        "settlement_id",
    ]:
        value = normalized_value(fields.get(key))
        if value:
            if record.record_type == "platform_ranking_signal":
                ranking_type = normalized_value(fields.get("ranking_type") or fields.get("data_category"))
                category = normalized_value(fields.get("category_path") or fields.get("ranking_page"))
                snapshot = normalized_value(fields.get("snapshot_end") or fields.get("metric_date") or fields.get("snapshot_start"))
                return f"{record.record_type}:{key}:{value}:{ranking_type}:{category}:{snapshot}" if snapshot else ""
            return f"{record.record_type}:{key}:{value}"
    product_id = normalized_value(fields.get("product_id") or fields.get("asin") or fields.get("sku") or fields.get("seller_sku"))
    platform = normalized_value(fields.get("marketplace") or fields.get("source_platform") or fields.get("platform"))
    if product_id and platform:
        snapshot = normalized_value(fields.get("snapshot_end") or fields.get("metric_date") or fields.get("snapshot_start"))
        ranking_type = normalized_value(fields.get("ranking_type") or fields.get("data_category"))
        if snapshot or ranking_type:
            return f"{record.record_type}:product:{platform}:{product_id}:{ranking_type}:{snapshot}"
        if record.record_type in {"store_metric_snapshot", "influencer_cooperation"}:
            return f"{record.record_type}:product:{platform}:{product_id}"
    if target_id and record.record_type in {"collection_job", "platform_ranking_signal", "review_insight"}:
        category = normalized_value(fields.get("data_category") or fields.get("ranking_type"))
        keyword = normalized_value(fields.get("keyword") or fields.get("target_keyword"))
        return f"{record.record_type}:target:{target_id}:{category}:{keyword}"
    if record.record_type == "strategy_memory":
        memory_key = normalized_value(fields.get("memory_key"))
        if memory_key:
            return f"strategy_memory:{memory_key}"
    if record.record_type == "conversation_import":
        import_key = normalized_value(fields.get("import_key"))
        if import_key:
            return f"conversation_import:{import_key}"
    if record.record_type == "knowledge_item":
        item_key = normalized_value(fields.get("item_key"))
        if item_key:
            return f"knowledge_item:{item_key}"
    if record.record_type == "knowledge_edge":
        edge_key = normalized_value(fields.get("edge_key"))
        if edge_key:
            return f"knowledge_edge:{edge_key}"
    if record.record_type == "knowledge_concept_weight":
        concept_key = normalized_value(fields.get("concept_key") or fields.get("normalized_entity"))
        if concept_key:
            return f"knowledge_concept_weight:{concept_key}"
    if record.record_type == "knowledge_distillation_item":
        item_id = normalized_value(fields.get("distillation_item_id"))
        dedupe = normalized_value(fields.get("dedupe_key"))
        taxonomy = normalized_value(fields.get("primary_taxonomy"))
        if item_id:
            return f"knowledge_distillation_item:{item_id}"
        if dedupe:
            return f"knowledge_distillation_item:{dedupe}:{taxonomy}"
    if record.record_type == "risk_intelligence_quarantine":
        quarantine_id = normalized_value(fields.get("quarantine_id"))
        source_item = normalized_value(fields.get("source_distillation_item_id"))
        risk_class = normalized_value(fields.get("risk_class"))
        if quarantine_id:
            return f"risk_intelligence_quarantine:{quarantine_id}"
        if source_item:
            return f"risk_intelligence_quarantine:{source_item}:{risk_class}"
    if record.record_type == "word_bank_entry":
        word_key = normalized_value(fields.get("word_bank_key"))
        term = normalized_value(fields.get("term"))
        term_type = normalized_value(fields.get("term_type"))
        subtype = normalized_value(fields.get("subtype"))
        if word_key:
            return f"word_bank_entry:{word_key}"
        if term:
            return f"word_bank_entry:{term}:{term_type}:{subtype}"
    if record.record_type in {
        "market_category_snapshot",
        "market_segment_snapshot",
        "category_growth_snapshot",
        "mid_rank_product_signal",
        "long_tail_opportunity",
        "keyword_trend_snapshot",
        "creator_trend_snapshot",
        "video_trend_snapshot",
        "price_trend_snapshot",
        "review_painpoint_snapshot",
        "market_signal",
        "market_hypothesis",
        "market_plan",
        "market_task",
    }:
        for key in [
            "market_signal_id",
            "market_hypothesis_id",
            "market_plan_id",
            "market_task_id",
            "snapshot_id",
            "signal_id",
            "hypothesis_id",
            "plan_id",
            "task_id",
            "opportunity_id",
            "trend_id",
        ]:
            value = normalized_value(fields.get(key))
            if value:
                return f"{record.record_type}:{key}:{value}"
        platform = normalized_value(fields.get("platform"))
        country = normalized_value(fields.get("country"))
        category = normalized_value(fields.get("category"))
        segment = normalized_value(fields.get("segment"))
        entity = normalized_value(fields.get("entity_id") or fields.get("keyword") or fields.get("creator_handle") or fields.get("video_url"))
        run_date = normalized_value(fields.get("run_date") or fields.get("snapshot_date") or fields.get("created_date"))
        if platform and category and run_date:
            return f"{record.record_type}:{platform}:{country}:{category}:{segment}:{entity}:{run_date}"
    if record.record_type == "agent_workspace_snapshot":
        workspace_id = normalized_value(fields.get("workspace_id"))
        if workspace_id:
            return f"agent_workspace_snapshot:{workspace_id}"
    if record.record_type == "keyword_intelligence":
        keyword_key = normalized_value(fields.get("keyword_key"))
        if keyword_key:
            return f"keyword_intelligence:{keyword_key}"
    if record.record_type == "agent_distillation_pack":
        pack_id = normalized_value(fields.get("distillation_pack_id"))
        if pack_id:
            return f"agent_distillation_pack:{pack_id}"
    contract_ids = {
        "source_document": ["source_id", "checksum"],
        "raw_asset": ["raw_asset_id", "sha256"],
        "import_batch": ["import_batch_id", "batch_key"],
        "attachment_asset": ["asset_id", "sha256"],
        "knowledge_edge_record": ["edge_id", "source_node_id", "edge_type", "target_node_id"],
        "order_item": ["order_item_id", "order_id", "line_item_id"],
        "platform_rule_snapshot": ["rule_snapshot_id", "platform", "rule_type", "full_text_hash"],
        "finance_transaction": ["finance_transaction_id"],
        "inventory_ledger": ["inventory_ledger_id"],
        "entity_tag_map": ["entity_tag_map_id", "entity_type", "entity_id", "taxonomy_id"],
        "experiment_run": ["experiment_id"],
        "action_outcome": ["outcome_id"],
        "approval_request": ["approval_id"],
        "audit_log": ["audit_id"],
        "tenant": ["tenant_id"],
        "workspace": ["workspace_id"],
        "user": ["user_id"],
        "role": ["role_id", "role"],
        "permission": ["permission_id", "permission_key"],
        "role_permission": ["role_permission_id", "role_id", "permission_key"],
        "user_role": ["user_role_id", "user_id", "role_id", "workspace_id"],
        "license": ["license_key", "tenant_id", "workspace_id"],
        "store_binding": ["store_binding_id", "tenant_id", "workspace_id", "platform", "country", "store_name"],
        "export_log": ["export_id"],
        "customer_feedback": ["feedback_id"],
        "agent_outcome": ["outcome_id"],
        "training_feedback": ["training_feedback_id"],
        "beta_workspace": ["beta_workspace_id", "workspace_id"],
        "report_watermark": ["report_id"],
        "seller_profile": ["seller_profile_id", "tenant_id", "workspace_id", "seller_name"],
        "seller_mode_assessment": ["seller_mode_assessment_id", "seller_profile_id"],
        "seller_capability_score": ["seller_capability_score_id", "seller_profile_id", "score_dimension"],
        "seller_strategy_package": ["seller_strategy_package_id", "seller_profile_id", "seller_mode"],
        "testing_seller_playbook": ["testing_seller_playbook_id", "seller_profile_id"],
        "launch_seller_playbook": ["launch_seller_playbook_id", "seller_profile_id"],
        "factory_seller_playbook": ["factory_seller_playbook_id", "seller_profile_id"],
        "brand_seller_playbook": ["brand_seller_playbook_id", "seller_profile_id"],
        "factory_product_line": ["factory_product_line_id", "seller_profile_id", "product_line_name"],
        "factory_capacity_profile": ["factory_capacity_profile_id", "seller_profile_id"],
        "country_market_fit": ["country_market_fit_id", "seller_profile_id", "country", "platform"],
        "platform_fit_score": ["platform_fit_score_id", "seller_profile_id", "platform"],
        "landed_cost_scenario": ["landed_cost_scenario_id", "seller_profile_id", "scenario_name"],
        "tariff_classification_record": ["tariff_classification_id", "seller_profile_id", "product_line_name"],
        "tax_entity_scenario": ["tax_entity_scenario_id", "seller_profile_id", "scenario_name"],
        "company_structure_option": ["company_structure_option_id", "seller_profile_id", "jurisdiction"],
        "trade_route_scenario": ["trade_route_scenario_id", "seller_profile_id", "route_name"],
        "compliance_advisor_review": ["compliance_advisor_review_id", "seller_profile_id", "review_topic"],
        "manufacturing_origin_option": ["manufacturing_origin_option_id", "seller_profile_id", "origin_country"],
        "brand_product_development_plan": ["brand_product_development_plan_id", "seller_profile_id", "product_line_name"],
        "factory_export_plan": ["factory_export_plan_id", "seller_profile_id", "target_country", "platform"],
        "taxonomy_dictionary": ["taxonomy_id", "canonical_name"],
        "pii_vault": ["pii_id", "tokenized_value"],
        "learning_event": ["learning_event_id"],
        "knowledge_node": ["node_id", "normalized_name"],
        "agent_registry": ["agent_id", "agent_name"],
        "agent_workspace_snapshot": ["workspace_id", "agent_id", "run_date"],
        "keyword_intelligence": ["keyword_id", "keyword", "keyword_type", "category"],
        "agent_distillation_pack": ["distillation_pack_id", "agent_id", "run_date"],
        "enterprise_account": ["enterprise_account_id", "company_name"],
        "quote": ["quote_id"],
        "contract_record": ["contract_id"],
        "inquiry": ["inquiry_id"],
        "agent_evaluation": ["agent_evaluation_id", "agent_id", "metric_name"],
        "source_chunk": ["source_chunk_id", "source_id", "chunk_index"],
        "ingestion_run": ["ingestion_run_id", "source_type", "source_name", "started_at_utc"],
        "lineage_event": ["lineage_event_id", "run_id", "entity_type", "entity_id", "event_type"],
        "evidence_claim": ["evidence_claim_id", "claim_text", "source_id", "source_chunk_id"],
        "policy_document": ["policy_document_id", "platform", "document_type", "source_url", "content_hash"],
        "policy_rule": ["policy_rule_id", "platform", "country", "rule_code", "effective_from"],
        "policy_diff": ["policy_diff_id", "platform", "new_policy_document_id", "new_policy_rule_id", "diff_type"],
        "entity_alias": ["entity_alias_id", "entity_type", "alias_text", "language"],
        "knowledge_revision": ["knowledge_revision_id", "entity_type", "entity_id", "revision_number"],
        "eval_case": ["eval_case_id", "eval_suite"],
        "eval_run": ["eval_run_id", "eval_suite", "target_agent_id", "started_at_utc"],
        "judge_result": ["judge_result_id", "eval_run_id", "eval_case_id", "judge_type"],
        "error_slice": ["error_slice_id", "slice_key", "error_type"],
        "rollback_gate": ["rollback_gate_id", "action_type", "risk_level"],
        "model_registry": ["model_version_id", "provider", "model_name", "model_version"],
        "prompt_version": ["prompt_version_id", "prompt_name", "version"],
        "event_inbox": ["event_inbox_id", "event_source", "event_id"],
        "event_dedup": ["event_dedup_id", "dedup_key"],
        "task_queue": ["task_queue_id", "task_type", "source_event_inbox_id", "target_agent_id"],
        "dead_letter": ["dead_letter_id", "source_table", "source_record_id"],
        "agent_action_log": ["agent_action_log_id", "agent_id", "action_type", "target_entity_type", "target_entity_id", "created_at_utc"],
        "data_subject_request": ["data_subject_request_id", "subject_type", "subject_ref", "request_type", "received_at_utc"],
        "retention_policy": ["retention_policy_id", "data_class", "table_name", "jurisdiction"],
        "delete_workflow": ["delete_workflow_id", "target_table", "target_record_id", "delete_mode"],
        "consent_record": ["consent_record_id", "subject_type", "subject_ref", "purpose"],
        "sensitive_data_flag": ["sensitive_data_flag_id", "entity_type", "entity_id", "data_class"],
        "company": ["company_id", "company_name", "country", "company_type"],
        "company_user": ["company_user_id", "company_id", "role", "contact_pii_id"],
        "shared_catalog": ["shared_catalog_id", "catalog_name", "company_id", "platform", "country"],
        "quote_line": ["quote_line_id", "quote_id", "product_id", "qty"],
        "price_list": ["price_list_id", "price_list_name", "scope_type", "scope_id", "effective_from"],
        "settlement": ["settlement_id", "platform", "store_id", "counterparty_type", "counterparty_id", "settlement_period"],
        "payout": ["payout_id", "settlement_id", "payee_type", "payee_id", "amount_original"],
        "invoice": ["invoice_id", "counterparty_type", "counterparty_id", "invoice_number"],
        "return_rma": ["return_rma_id", "platform", "store_id", "order_id", "order_item_id"],
        "refund_record": ["refund_record_id", "platform", "store_id", "order_id", "amount_original", "created_at_utc"],
        "performance_alert": ["performance_alert_id", "platform", "store_id", "alert_type", "detected_at_utc"],
        "account_health": ["account_health_id", "platform", "store_id", "captured_at_utc"],
        "raw_extraction_run": ["raw_extraction_run_id", "raw_asset_id", "extraction_type", "tool_name", "started_at_utc"],
        "policy_snapshot": ["policy_snapshot_id", "platform", "market", "policy_type", "source_url", "content_hash"],
        "banned_term": ["banned_term_id", "normalized_term", "language", "platform", "country", "risk_type"],
        "ip_registry": ["ip_registry_id", "rights_type", "normalized_name", "jurisdiction", "registration_number"],
        "competitor_snapshot": ["competitor_snapshot_id", "platform", "market", "competitor_store_name", "listing_id", "snapshot_at_utc"],
        "listing_snapshot": ["listing_snapshot_id", "platform", "market", "external_listing_id", "snapshot_at_utc"],
        "price_history": ["price_history_id", "platform", "market", "listing_id", "observed_at_utc", "price_original"],
        "video_scene": ["video_scene_id", "video_id", "scene_index"],
        "video_highlight_frame": ["video_highlight_frame_id", "video_id", "frame_sec", "frame_hash"],
        "video_comment": ["video_comment_id", "platform", "external_comment_id"],
        "video_comment_intelligence": ["video_comment_intelligence_id", "video_id", "analysis_window"],
        "knowledge_provenance": ["knowledge_provenance_id", "entity_type", "entity_id", "source_id", "source_chunk_id", "evidence_span"],
        "knowledge_score_record": ["knowledge_score_id", "entity_type", "entity_id", "score_version", "calculated_at_utc"],
        "concept_weight_history": ["concept_weight_history_id", "concept_key", "updated_at_utc"],
        "quality_metric_snapshot": ["quality_metric_snapshot_id", "pipeline_area", "metric_name", "measured_at_utc"],
        "claim_requirement": ["claim_requirement_id", "normalized_claim", "claim_type", "platform", "country"],
        "compliance_artifact": ["compliance_artifact_id", "artifact_type", "entity_type", "entity_id", "document_number"],
        "content_rights_asset": ["content_rights_asset_id", "asset_type", "asset_name", "rights_owner", "license_type"],
        "commercial_disclosure": ["commercial_disclosure_id", "platform", "creator_id", "video_id", "relationship_type", "checked_at_utc"],
        "enforcement_event": ["enforcement_event_id", "platform", "entity_type", "entity_id", "event_type", "event_at_utc"],
        "appeal_case": ["appeal_case_id", "platform", "enforcement_event_id", "submitted_at_utc"],
        "query_snapshot": ["query_snapshot_id", "platform", "market", "normalized_query", "report_type", "snapshot_at_utc"],
        "creative_snapshot": ["creative_snapshot_id", "platform", "market", "creative_url", "snapshot_at_utc"],
        "seasonal_event": ["seasonal_event_id", "normalized_event_name", "country", "region", "event_start_date"],
        "creative_pattern": ["creative_pattern_id", "pattern_name", "pattern_type", "platform", "product_family"],
        "agent_run": ["agent_run_id"],
        "execution_plan": ["plan_id"],
        "plan_task": ["plan_task_id"],
        "agent_review": ["agent_review_id"],
        "signal_event": ["signal_id"],
        "signal_snapshot": ["signal_snapshot_id", "entity_type", "entity_id", "metric_name", "snapshot_at_utc"],
        "signal_threshold": ["signal_threshold_id", "engine_type", "metric_name", "platform", "country"],
        "signal_alert": ["signal_alert_id", "signal_id", "alert_type"],
        "signal_weight": ["signal_weight_id", "signal_id", "engine_type"],
        "hypothesis": ["hypothesis_id"],
        "hypothesis_evidence": ["hypothesis_evidence_id", "hypothesis_id", "signal_id", "source_record_id"],
        "hypothesis_score": ["hypothesis_score_id", "hypothesis_id", "score_version"],
        "experiment": ["experiment_id"],
        "experiment_variant": ["experiment_variant_id", "experiment_id", "variant_name"],
        "experiment_metric": ["experiment_metric_id", "experiment_id", "metric_name", "measured_at_utc"],
        "experiment_stop_rule": ["experiment_stop_rule_id", "experiment_id", "rule_name"],
        "experiment_scale_rule": ["experiment_scale_rule_id", "experiment_id", "rule_name"],
        "experiment_outcome": ["experiment_outcome_id", "experiment_id", "evaluation_window"],
        "pattern_weight": ["pattern_weight_id", "pattern_type", "pattern_value"],
        "pattern_history": ["pattern_history_id", "pattern_weight_id", "event_time_utc"],
        "strategy_adjustment": ["strategy_adjustment_id", "hypothesis_id", "adjustment_type"],
        "priority_rebalance_log": ["priority_rebalance_log_id", "run_id"],
        "task_priority": ["task_priority_id", "task_queue_id", "calculated_at_utc"],
        "backlog": ["backlog_id", "entity_type", "entity_id", "opportunity_type"],
        "priority_score": ["priority_score_id", "entity_type", "entity_id", "calculated_at_utc"],
    }
    if record.record_type in contract_ids:
        parts = [normalized_value(fields.get(key)) for key in contract_ids[record.record_type]]
        parts = [part for part in parts if part]
        if parts:
            return f"{record.record_type}:{':'.join(parts)}"
    if record.record_type == "execution_result":
        action_id = normalized_value(fields.get("action_id"))
        executed_at = normalized_value(fields.get("executed_at"))
        if action_id and executed_at:
            return f"execution_result:{action_id}:{executed_at}"
    return ""


def merge_duplicate_record(existing: IntakeRecord, incoming: IntakeRecord) -> IntakeRecord:
    fields = merge_dict(existing.fields, incoming.fields)
    score = merge_dict(existing.score, incoming.score)
    metadata = merge_dict(existing.metadata, incoming.metadata)
    metadata["dedupe_count"] = int(metadata.get("dedupe_count") or 1) + 1
    metadata["last_seen_at"] = datetime.now(timezone.utc).isoformat()
    notes = list(dict.fromkeys([*existing.director_notes, *incoming.director_notes]))
    return IntakeRecord(
        record_id=existing.record_id,
        record_type=existing.record_type,
        created_at=existing.created_at,
        source=incoming.source or existing.source,
        raw_text=incoming.raw_text or existing.raw_text,
        fields=fields,
        score=score,
        director_notes=notes,
        review_status=incoming.review_status or existing.review_status,
        confidence=max(existing.confidence, incoming.confidence),
        metadata=metadata,
    )


def merge_dict(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if value is not None and value != "":
            merged[key] = value
    return merged


def normalized_value(value: Any) -> str:
    return str(value or "").strip().lower()
