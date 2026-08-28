from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .storage import append_record, read_records
from .types import IntakeRecord
from .web_ai_bridge import provider_map, sanitize_for_external_ai


SCHEMA_VERSION = 1
PACKAGE_DIR = Path("outputs") / "web_ai_packages" / "distillation"
RECEIPT_DIR = Path("outputs") / "web_ai_distillation_receipts"
LEARNING_RECEIPT_DIR = Path("outputs") / "expert_learning_receipts"
ALLOWED_RIGHTS_BASES = {
    "owned",
    "commissioned",
    "public_domain",
    "commercial_license",
    "platform_permitted_research",
    "user_provided_with_permission",
}
SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "key",
    "password",
    "secret",
    "signature",
    "token",
}


@dataclass(slots=True)
class DistillationPackage:
    packet_id: str
    provider: str
    task: str
    source_count: int
    json_path: Path
    markdown_path: Path
    prompt: str
    provider_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "provider": self.provider,
            "task": self.task,
            "source_count": self.source_count,
            "json_path": str(self.json_path),
            "markdown_path": str(self.markdown_path),
            "prompt": self.prompt,
            "provider_url": self.provider_url,
            "requires_manual_upload": True,
            "external_actions": [],
        }


@dataclass(slots=True)
class DistillationImportResult:
    packet_id: str
    provider: str
    candidates: list[IntakeRecord]
    receipt_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "provider": self.provider,
            "candidate_count": len(self.candidates),
            "candidates": [item.to_dict() for item in self.candidates],
            "receipt_path": str(self.receipt_path),
            "review_status": "untrusted_candidate",
            "auto_promoted": False,
            "external_actions": [],
        }


@dataclass(slots=True)
class DistillationApprovalResult:
    candidate_record_id: str
    memory: IntakeRecord
    business_event: dict[str, Any]
    receipt_path: Path
    already_approved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_record_id": self.candidate_record_id,
            "memory": self.memory.to_dict(),
            "business_event": dict(self.business_event),
            "receipt_path": str(self.receipt_path),
            "review_status": "reviewed_local_experience_memory",
            "authoritative_platform_rule": False,
            "already_approved": self.already_approved,
            "external_actions": [],
        }


def export_distillation_package(
    root: Path,
    *,
    sources: list[dict[str, Any]],
    provider: str = "chatgpt",
    task: str = "public_content_distillation",
    operator_instruction: str = "",
    project_id: str = "",
    task_id: str = "",
    max_sources: int = 80,
    max_total_chars: int = 60_000,
) -> DistillationPackage:
    """Create a bounded, sanitized package for manual use in a browser AI.

    This function never opens a browser, logs in, uploads a file, or sends a
    network request. It only writes a local package after validating provenance
    and rights metadata supplied by the operator or an approved collector.
    """

    root = root.resolve()
    if not isinstance(sources, list) or not sources:
        raise ValueError("至少需要一条已获准的公开资料或负责人提供资料。")
    if not 1 <= max_sources <= 200:
        raise ValueError("max_sources 必须在 1 到 200 之间。")
    if not 1_000 <= max_total_chars <= 200_000:
        raise ValueError("max_total_chars 必须在 1000 到 200000 之间。")

    providers = provider_map(root)
    provider_config = providers.get(provider)
    if provider_config is None:
        raise ValueError(f"未配置网页 AI：{provider}")
    provider_id = str(provider_config.get("id") or provider)
    provider_url = str(provider_config.get("url") or "")
    cleaned_sources = _prepare_sources(sources[:max_sources], max_total_chars=max_total_chars)
    if not cleaned_sources:
        raise ValueError("资料在脱敏和去重后为空。")

    task = _safe_label(task, fallback="public_content_distillation", limit=100)
    instruction = sanitize_for_external_ai(str(operator_instruction or ""))[:4000]
    learning_scope = {
        "project_id": str(project_id or "").strip().lower(),
        "task_id": str(task_id or "").strip().lower(),
    }
    if bool(learning_scope["project_id"]) != bool(learning_scope["task_id"]):
        raise ValueError("project_id 与 task_id 必须同时提供。")
    fingerprint_input = json.dumps(
        {
            "provider": provider_id,
            "task": task,
            "sources": cleaned_sources,
            "learning_scope": learning_scope,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    packet_id = "dst_" + sha256(fingerprint_input.encode("utf-8")).hexdigest()[:20]
    prompt = _build_prompt(packet_id, provider_id, task, cleaned_sources, instruction)
    created_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": packet_id,
        "provider": provider_id,
        "task": task,
        "created_at": created_at,
        "source_count": len(cleaned_sources),
        "source_catalog": cleaned_sources,
        "prompt": prompt,
        "operator_instruction": instruction,
        "learning_scope": learning_scope,
        "safety_contract": {
            "manual_upload_only": True,
            "external_actions": [],
            "no_login_or_browser_automation": True,
            "no_auto_import_to_trusted_knowledge": True,
            "response_state": "untrusted_candidate_until_human_review",
        },
    }
    payload["package_sha256"] = _payload_sha256(payload)

    output_dir = root / PACKAGE_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{packet_id}.json"
    markdown_path = output_dir / f"{packet_id}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(prompt, encoding="utf-8")
    return DistillationPackage(
        packet_id=packet_id,
        provider=provider_id,
        task=task,
        source_count=len(cleaned_sources),
        json_path=json_path,
        markdown_path=markdown_path,
        prompt=prompt,
        provider_url=provider_url,
    )


def import_distillation_response(
    root: Path,
    *,
    package_path: str | Path,
    response: str | dict[str, Any],
) -> DistillationImportResult:
    """Validate a structured browser-AI response and quarantine it as candidates."""

    root = root.resolve()
    package_file = _resolve_package_path(root, package_path)
    package = _load_object(package_file, label="蒸馏任务包")
    _verify_package(package)
    response_payload = _load_response(response)
    items = _validate_response(response_payload, package)
    now = datetime.now(timezone.utc).isoformat()
    source_ids = {
        source_id
        for source in package["source_catalog"]
        for source_id in source.get("source_ids", [])
        if isinstance(source_id, str)
    }

    candidates: list[IntakeRecord] = []
    for index, item in enumerate(items, start=1):
        clean_item = _sanitize_json_value(item)
        candidate_id = str(clean_item.get("candidate_id") or "").strip()
        if not candidate_id:
            candidate_id = f"{package['packet_id']}-candidate-{index}"
        record = IntakeRecord(
            record_type="external_ai_distillation_candidate",
            source=f"browser_ai_distillation:{package['provider']}",
            raw_text=json.dumps(clean_item, ensure_ascii=False),
            fields={
                "candidate_id": candidate_id[:160],
                "packet_id": package["packet_id"],
                "provider": package["provider"],
                "task": package["task"],
                "source_ids": clean_item["source_ids"],
                "summary": clean_item["summary"],
                "claims": clean_item["claims"],
                "conflicts": clean_item["conflicts"],
                "limitations": clean_item["limitations"],
                "recommended_validation": clean_item["recommended_validation"],
                "risk_flags": clean_item["risk_flags"],
                "known_source_ids": sorted(source_ids),
                "project_id": str((package.get("learning_scope") or {}).get("project_id") or ""),
                "task_id": str((package.get("learning_scope") or {}).get("task_id") or ""),
                "imported_at": now,
                "trust_boundary": "external_ai_output_is_not_evidence",
                "promotion_gate": "human_review_plus_source_verification_required",
            },
            score={"priority": 50, "training_weight": "blocked_until_review"},
            director_notes=[
                "浏览器 AI 输出只作为待核验候选，不等同于来源证据。",
                "人工核对原始 source_id、冲突和限制后，才能进入正式知识库。",
            ],
            review_status="untrusted_candidate",
            confidence=min(_candidate_confidence(clean_item), 0.6),
            metadata={"package_path": str(package_file), "external_actions": []},
        )
        append_record(root, record)
        candidates.append(record)

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": package["packet_id"],
        "provider": package["provider"],
        "task": package["task"],
        "package_path": str(package_file),
        "package_sha256": package["package_sha256"],
        "response_sha256": sha256(
            json.dumps(response_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "candidate_count": len(candidates),
        "candidate_record_ids": [record.record_id for record in candidates],
        "review_status": "untrusted_candidate",
        "auto_promoted": False,
        "external_actions": [],
        "imported_at": now,
    }
    receipt_dir = root / RECEIPT_DIR
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / f"{package['packet_id']}-{receipt['response_sha256'][:12]}.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return DistillationImportResult(package["packet_id"], package["provider"], candidates, receipt_path)


def validate_learning_scope(root: Path, *, project_id: str, task_id: str) -> dict[str, Any]:
    """Resolve one exact non-Amazon task scope and fail closed on drift."""

    from .workspace_runtime import load_workspace_config
    from .workspace_schema import find_task_context

    project_id = _safe_scope_id(project_id, "项目")
    task_id = _safe_scope_id(task_id, "任务")
    found = find_task_context(load_workspace_config(root.resolve()), task_id)
    if found is None:
        raise ValueError("学习资料无法绑定：当前任务不存在。")
    project, channel, _store, task = found
    actual_project_id = str(project.get("id") or "").strip().lower()
    if actual_project_id != project_id:
        raise ValueError("学习资料无法绑定：项目与任务不匹配。")
    platform = str(
        task.get("platform")
        or (channel.get("platform") if isinstance(channel, dict) else "")
        or ""
    ).strip().lower()
    searchable = " ".join(
        str(value or "").lower()
        for value in (
            project_id,
            task_id,
            project.get("name"),
            task.get("name"),
            platform,
        )
    )
    if platform == "amazon" or "amazon" in searchable:
        raise ValueError("Amazon 当前由负责人暂停，学习资料不会写入 Amazon 任务。")
    return {
        "workspace_id": str(load_workspace_config(root.resolve()).get("workspace_id") or "local-workspace"),
        "project_id": project_id,
        "project_name": str(project.get("name") or project_id),
        "task_id": task_id,
        "task_name": str(task.get("name") or task_id),
        "platform": platform or "general",
    }


def approve_distillation_candidate(
    root: Path,
    *,
    candidate_record_id: str,
    project_id: str,
    task_id: str,
    reviewer: str,
    source_verification_refs: list[str],
) -> DistillationApprovalResult:
    """Promote one reviewed candidate into task-scoped local experience memory.

    Promotion never turns external-AI output into an authoritative platform rule.
    The durable memory is scoped to one exact project/task and carries the source
    verification references supplied by the human reviewer.
    """

    root = root.resolve()
    scope = validate_learning_scope(root, project_id=project_id, task_id=task_id)
    candidate_record_id = str(candidate_record_id or "").strip()
    reviewer = _safe_label(reviewer, fallback="", limit=120)
    if not candidate_record_id:
        raise ValueError("缺少待核验候选编号。")
    if not reviewer:
        raise ValueError("确认加入学习记忆前必须记录负责人。")
    verification_refs = _safe_reference_list(source_verification_refs)
    if not verification_refs:
        raise ValueError("确认加入学习记忆前必须核对并记录原始来源。")

    candidate = next(
        (
            item
            for item in read_records(root, "external_ai_distillation_candidate")
            if item.record_id == candidate_record_id
        ),
        None,
    )
    if candidate is None:
        raise ValueError("待核验候选不存在。")
    if candidate.review_status != "untrusted_candidate":
        raise ValueError("只有待核验候选可以加入本地学习记忆。")
    if (
        str(candidate.fields.get("project_id") or "") != scope["project_id"]
        or str(candidate.fields.get("task_id") or "") != scope["task_id"]
    ):
        raise ValueError("待核验候选属于另一个项目或任务，不能跨任务加入记忆。")
    source_ids = [str(item) for item in candidate.fields.get("source_ids", []) if str(item).strip()]
    if not set(source_ids).issubset(set(verification_refs)):
        raise ValueError("来源核对记录必须覆盖候选实际引用的全部 source_id。")

    existing = next(
        (
            item
            for item in read_records(root, "expert_learning_memory")
            if item.fields.get("candidate_record_id") == candidate_record_id
            and item.fields.get("project_id") == scope["project_id"]
            and item.fields.get("task_id") == scope["task_id"]
        ),
        None,
    )
    if existing is not None:
        receipt_path = root / str(existing.metadata.get("receipt_path") or "")
        event = dict(existing.metadata.get("business_event") or {})
        return DistillationApprovalResult(
            candidate_record_id,
            existing,
            event,
            receipt_path,
            already_approved=True,
        )

    approval_key = "|".join(
        [candidate_record_id, scope["project_id"], scope["task_id"]]
    )
    memory_id = "expert-memory-" + sha256(approval_key.encode("utf-8")).hexdigest()[:20]
    now = datetime.now(timezone.utc).isoformat()
    memory_fields = {
        "learning_memory_id": memory_id,
        "candidate_record_id": candidate_record_id,
        "packet_id": str(candidate.fields.get("packet_id") or ""),
        "provider": str(candidate.fields.get("provider") or ""),
        "workspace_id": scope["workspace_id"],
        "project_id": scope["project_id"],
        "project_name": scope["project_name"],
        "task_id": scope["task_id"],
        "task_name": scope["task_name"],
        "platform": scope["platform"],
        "source_ids": source_ids,
        "source_verification_refs": verification_refs,
        "summary": str(candidate.fields.get("summary") or "")[:4000],
        "claims": _sanitize_json_value(candidate.fields.get("claims") or []),
        "conflicts": _sanitize_json_value(candidate.fields.get("conflicts") or []),
        "limitations": _sanitize_json_value(candidate.fields.get("limitations") or []),
        "recommended_validation": _sanitize_json_value(
            candidate.fields.get("recommended_validation") or []
        ),
        "risk_flags": _sanitize_json_value(candidate.fields.get("risk_flags") or []),
        "reviewed_by": reviewer,
        "reviewed_at": now,
        "trust_state": "reviewed_local_experience_memory",
        "authoritative_platform_rule": False,
        "external_action_authorized": False,
    }
    receipt_path = root / LEARNING_RECEIPT_DIR / f"{memory_id}.json"
    event_id = "business-event-" + sha256((memory_id + "|approved").encode("utf-8")).hexdigest()[:20]
    from .task_execution_runtime import append_business_event

    business_event = append_business_event(
        root,
        {
            "event_id": event_id,
            "event_type": "learning_memory_approved",
            "kind": "observation",
            "workspace_id": scope["workspace_id"],
            "project_id": scope["project_id"],
            "task_id": scope["task_id"],
            "conversation_id": scope["task_id"],
            "actor": reviewer,
            "statement": "负责人已核对来源，并把一条资料候选加入当前智能体的本地学习记忆。",
            "confidence": str(min(float(candidate.confidence), 0.6)),
            "status": "reviewed_local_experience_memory",
            "source_refs": [candidate_record_id, *verification_refs],
            "business_object_refs": [f"expert_learning_memory:{memory_id}"],
            "payload": {
                "learning_memory_id": memory_id,
                "authoritative_platform_rule": False,
                "external_action_authorized": False,
            },
        },
        actor=reviewer,
    )
    memory = IntakeRecord(
        record_id=memory_id,
        record_type="expert_learning_memory",
        source="owner_reviewed_external_ai_distillation",
        raw_text=json.dumps(
            {
                "summary": memory_fields["summary"],
                "claims": memory_fields["claims"],
                "conflicts": memory_fields["conflicts"],
                "limitations": memory_fields["limitations"],
            },
            ensure_ascii=False,
        ),
        fields=memory_fields,
        score={"priority": 60, "training_weight": "reviewed_task_scoped"},
        director_notes=[
            "该记忆只对精确项目/任务可见。",
            "它是负责人核对后的经验记忆，不是平台官方规则，也不授予外部执行权限。",
        ],
        review_status="reviewed_local_experience_memory",
        confidence=min(float(candidate.confidence), 0.6),
        metadata={
            "receipt_path": str(receipt_path.relative_to(root)),
            "business_event": business_event,
            "external_actions": [],
        },
        created_at=now,
    )
    append_record(root, memory)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "learning_memory_id": memory_id,
        "candidate_record_id": candidate_record_id,
        "project_id": scope["project_id"],
        "task_id": scope["task_id"],
        "reviewed_by": reviewer,
        "reviewed_at": now,
        "source_verification_refs": verification_refs,
        "business_event_id": business_event["event_id"],
        "review_status": "reviewed_local_experience_memory",
        "authoritative_platform_rule": False,
        "external_action_authorized": False,
        "external_actions": [],
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return DistillationApprovalResult(candidate_record_id, memory, business_event, receipt_path)


def resolve_approved_expert_learning_memory(
    root: Path,
    *,
    project_id: str,
    task_id: str,
    limit: int = 12,
) -> dict[str, Any]:
    """Return a bounded read model for the exact task; never load another task's memory."""

    scope = validate_learning_scope(root.resolve(), project_id=project_id, task_id=task_id)
    bounded = max(1, min(int(limit), 50))
    memories = [
        item
        for item in read_records(root.resolve(), "expert_learning_memory")
        if item.fields.get("project_id") == scope["project_id"]
        and item.fields.get("task_id") == scope["task_id"]
        and item.review_status == "reviewed_local_experience_memory"
    ][-bounded:]
    return {
        "project_id": scope["project_id"],
        "task_id": scope["task_id"],
        "memory_count": len(memories),
        "items": [
            {
                "learning_memory_id": str(item.fields.get("learning_memory_id") or item.record_id),
                "summary": str(item.fields.get("summary") or "")[:1200],
                "claims": _sanitize_json_value(item.fields.get("claims") or [])[:12],
                "conflicts": _sanitize_json_value(item.fields.get("conflicts") or [])[:8],
                "limitations": _sanitize_json_value(item.fields.get("limitations") or [])[:8],
                "source_ids": list(item.fields.get("source_ids") or [])[:20],
                "trust_state": "reviewed_local_experience_memory",
                "authoritative_platform_rule": False,
            }
            for item in memories
        ],
        "cross_task_memory_loaded": False,
        "external_action_authorized": False,
    }


def distill_package_with_configured_ai(
    root: Path,
    *,
    package_path: str | Path,
    provider: str,
) -> dict[str, Any]:
    """Run one configured AI call, then quarantine its structured response."""

    from .llm import LLMClient

    root = root.resolve()
    package_file = _resolve_package_path(root, package_path)
    package = _load_object(package_file, label="蒸馏任务包")
    _verify_package(package)
    selected_provider = str(provider or package.get("provider") or "").strip()
    client = LLMClient(
        root=root,
        task="learning_distillation",
        provider=selected_provider or None,
        # A structured answer is larger than the tiny health-check reply.  Keep a
        # bounded but realistic budget, especially for providers that do not
        # stream responses back to the desktop bridge.
        request_timeout_seconds=90,
        max_attempts=1,
    )
    if not client.enabled:
        raise ValueError("所选模型尚不可用：请先在设置中完成模型连接测试。")
    model_result = client.chat_with_metadata(
        (
            "你是 T-one 的一次性资料蒸馏器。只按用户消息中的 source_catalog 工作；"
            "只能返回一个符合指定结构的 JSON 对象，不要 Markdown，不要执行任何外部业务动作。"
        ),
        str(package.get("prompt") or ""),
        context={
            "operation": "task_scoped_learning_distillation",
            "packet_id": package["packet_id"],
            # This is a one-shot, source-bounded transformer.  Injecting the
            # general AI-worker onboarding prompt makes the request much larger
            # and can cause an otherwise healthy provider to time out.
            "include_onboarding": False,
            "external_business_action_authorized": False,
        },
    )
    imported = import_distillation_response(
        root,
        package_path=package_file,
        response=str(model_result.get("text") or ""),
    )
    return {
        "ok": True,
        **imported.to_dict(),
        "privacy": {
            "provider": str(model_result.get("provider") or selected_provider),
            "model": str(model_result.get("model") or "connected"),
            "latency_ms": int(model_result.get("latency_ms") or 0),
            "source_text_sent_to_configured_ai": True,
            "external_business_action_count": 0,
        },
    }


def process_text_learning_intake(
    root: Path,
    *,
    project_id: str,
    task_id: str,
    source_text: str,
    model_provider: str,
    source_id: str = "",
    title: str = "负责人提供的学习资料",
    source_url: str = "",
    rights_basis: str = "user_provided_with_permission",
) -> dict[str, Any]:
    """Chat-first vertical slice: package, real AI distillation, and quarantine."""

    root = root.resolve()
    scope = validate_learning_scope(root, project_id=project_id, task_id=task_id)
    clean_text = str(source_text or "").strip()
    if len(clean_text) < 40:
        raise ValueError("学习资料正文至少需要 40 个字符。")
    if len(clean_text) > 60_000:
        raise ValueError("单次学习资料不能超过 60000 个字符，请分段提交。")
    generated_source_id = "user-text-" + sha256(clean_text.encode("utf-8")).hexdigest()[:16]
    package = export_distillation_package(
        root,
        sources=[
            {
                "source_id": source_id or generated_source_id,
                "title": title,
                "source_url": source_url,
                "rights_basis": rights_basis,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "content_type": "owner_provided_text",
                "text": clean_text,
            }
        ],
        provider="chatgpt",
        task="task_scoped_expert_learning",
        operator_instruction=(
            "只整理为当前项目/任务的经验候选；不得写成平台官方规则，不得触发外部动作。"
        ),
        project_id=scope["project_id"],
        task_id=scope["task_id"],
    )
    result = distill_package_with_configured_ai(
        root,
        package_path=package.json_path,
        provider=model_provider,
    )
    result.update(
        {
            "project_id": scope["project_id"],
            "task_id": scope["task_id"],
            "package_path": str(package.json_path),
            "source_ids": [source_id or generated_source_id],
            "message": (
                f"已整理为 {int(result.get('candidate_count') or 0)} 条待核验候选；"
                "它们还不是事实，也不会执行任何外部动作。"
            ),
        }
    )
    return result


def _safe_scope_id(value: Any, label: str) -> str:
    clean = str(value or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,119}", clean):
        raise ValueError(f"{label}编号无效。")
    return clean


def _safe_reference_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        clean = _safe_label(value, fallback="", limit=240)
        if clean and clean not in result:
            result.append(clean)
    return result[:50]


def _prepare_sources(sources: list[dict[str, Any]], *, max_total_chars: int) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    by_digest: dict[str, dict[str, Any]] = {}
    used_chars = 0
    for position, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            raise ValueError(f"第 {position} 条资料必须是对象。")
        source_id = _safe_label(source.get("source_id"), fallback="", limit=160)
        rights_basis = str(source.get("rights_basis") or "").strip().lower()
        text = sanitize_for_external_ai(str(source.get("text") or "")).strip()
        if not source_id:
            raise ValueError(f"第 {position} 条资料缺少 source_id。")
        if rights_basis not in ALLOWED_RIGHTS_BASES:
            raise ValueError(f"第 {position} 条资料缺少允许的 rights_basis。")
        if len(text) < 20:
            raise ValueError(f"第 {position} 条资料正文过短或脱敏后为空。")
        source_url = _safe_public_url(source.get("source_url"))
        if rights_basis in {"public_domain", "platform_permitted_research"} and not source_url:
            raise ValueError(f"第 {position} 条公开资料必须提供 http(s) source_url。")
        remaining = max_total_chars - used_chars
        if remaining <= 0:
            break
        text = text[:remaining]
        normalized = re.sub(r"\s+", " ", text).strip().lower()
        digest = sha256(normalized.encode("utf-8")).hexdigest()
        if digest in by_digest:
            by_digest[digest]["source_ids"].append(source_id)
            continue
        item = {
            "source_ids": [source_id],
            "title": sanitize_for_external_ai(str(source.get("title") or ""))[:300],
            "source_url": source_url,
            "rights_basis": rights_basis,
            "captured_at": _safe_label(source.get("captured_at"), fallback="unknown", limit=80),
            "content_type": _safe_label(source.get("content_type"), fallback="text", limit=80),
            "content_sha256": digest,
            "text": text,
        }
        prepared.append(item)
        by_digest[digest] = item
        used_chars += len(text)
    return prepared


def _build_prompt(
    packet_id: str,
    provider: str,
    task: str,
    sources: list[dict[str, Any]],
    operator_instruction: str,
) -> str:
    source_json = json.dumps(sources, ensure_ascii=False, indent=2)
    return f"""# T-one 低成本资料蒸馏包

packet_id: {packet_id}
provider: {provider}
task: {task}

你是一次性的资料分析器，不是事实来源。只能使用下面的 source_catalog，不得使用其他聊天记忆补全事实。

要求：
1. 每条结论必须列出 evidence_source_ids；不能确定就写 unknown。
2. 明确列出互相冲突的来源、资料限制和下一步核验方式。
3. 不输出店铺写入、广告花费、联系客户、登录、授权或绕过限制的执行动作。
4. 只返回一个 JSON 对象，不要 Markdown 代码围栏，不要额外解释。
5. 返回结构必须是：
{{
  "schema_version": 1,
  "packet_id": "{packet_id}",
  "provider": "{provider}",
  "items": [
    {{
      "candidate_id": "稳定且简短的ID",
      "source_ids": ["实际使用的source_id"],
      "summary": "候选总结",
      "claims": [
        {{
          "claim": "单一可核验主张",
          "evidence_source_ids": ["source_id"],
          "confidence": 0.0,
          "evidence_state": "supported|conflicting|unknown"
        }}
      ],
      "conflicts": [],
      "limitations": [],
      "recommended_validation": [],
      "risk_flags": []
    }}
  ]
}}

负责人补充要求：
{operator_instruction or "无。"}

source_catalog:
{source_json}
"""


def _validate_response(response: dict[str, Any], package: dict[str, Any]) -> list[dict[str, Any]]:
    if response.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("回复 schema_version 不匹配。")
    if response.get("packet_id") != package.get("packet_id"):
        raise ValueError("回复 packet_id 与任务包不匹配。")
    if response.get("provider") != package.get("provider"):
        raise ValueError("回复 provider 与任务包不匹配。")
    items = response.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("回复 items 必须是非空数组。")
    if len(items) > 100:
        raise ValueError("回复 items 超过 100 条。")
    known_ids = {
        source_id
        for source in package["source_catalog"]
        for source_id in source.get("source_ids", [])
        if isinstance(source_id, str)
    }
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 个候选必须是对象。")
        _require_text(item, "summary", index)
        source_ids = _require_source_ids(item.get("source_ids"), known_ids, f"第 {index} 个候选")
        item["source_ids"] = source_ids
        claims = item.get("claims")
        if not isinstance(claims, list) or not claims:
            raise ValueError(f"第 {index} 个候选 claims 必须是非空数组。")
        if len(claims) > 50:
            raise ValueError(f"第 {index} 个候选 claims 超过 50 条。")
        for claim_index, claim in enumerate(claims, start=1):
            if not isinstance(claim, dict):
                raise ValueError(f"第 {index} 个候选的第 {claim_index} 条 claim 必须是对象。")
            _require_text(claim, "claim", index)
            claim["evidence_source_ids"] = _require_source_ids(
                claim.get("evidence_source_ids"), known_ids, f"第 {index} 个候选的第 {claim_index} 条 claim"
            )
            confidence = claim.get("confidence")
            if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
                raise ValueError("claim.confidence 必须在 0 到 1 之间。")
            if claim.get("evidence_state") not in {"supported", "conflicting", "unknown"}:
                raise ValueError("claim.evidence_state 只能是 supported、conflicting 或 unknown。")
        for key in ["conflicts", "limitations", "recommended_validation", "risk_flags"]:
            value = item.get(key)
            if not isinstance(value, list) or any(not isinstance(entry, str) for entry in value):
                raise ValueError(f"第 {index} 个候选 {key} 必须是字符串数组。")
            item[key] = [entry[:1000] for entry in value[:50]]
    return items


def _verify_package(package: dict[str, Any]) -> None:
    if package.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("蒸馏任务包版本不受支持。")
    expected = package.get("package_sha256")
    unsigned = dict(package)
    unsigned.pop("package_sha256", None)
    if not isinstance(expected, str) or expected != _payload_sha256(unsigned):
        raise ValueError("蒸馏任务包哈希不一致，文件可能已被修改。")
    if not isinstance(package.get("source_catalog"), list) or not package["source_catalog"]:
        raise ValueError("蒸馏任务包没有来源目录。")


def _resolve_package_path(root: Path, value: str | Path) -> Path:
    raw = Path(value)
    path = raw if raw.is_absolute() else root / raw
    path = path.resolve()
    allowed = (root / PACKAGE_DIR).resolve()
    if path.suffix.lower() != ".json" or not path.is_file() or allowed not in path.parents:
        raise ValueError("package_path 必须是本项目 outputs/web_ai_packages/distillation 下的 JSON 文件。")
    return path


def _load_response(response: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(response, dict):
        return dict(response)
    if not isinstance(response, str) or not response.strip():
        raise ValueError("网页 AI 回复为空。")
    if len(response) > 2_000_000:
        raise ValueError("网页 AI 回复超过 2MB。")
    try:
        payload = json.loads(response.lstrip("\ufeff"))
    except json.JSONDecodeError as exc:
        raise ValueError("网页 AI 回复必须是一个纯 JSON 对象，不能带 Markdown 围栏。") from exc
    if not isinstance(payload, dict):
        raise ValueError("网页 AI 回复必须是 JSON 对象。")
    return payload


def _load_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}不是有效 JSON。") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label}必须是 JSON 对象。")
    return payload


def _safe_public_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("source_url 必须是 http(s) 公共地址。")
    if parsed.username or parsed.password:
        raise ValueError("source_url 不能包含登录凭据。")
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in SENSITIVE_QUERY_KEYS
    ]
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query), ""))[:2000]


def _safe_label(value: Any, *, fallback: str, limit: int) -> str:
    clean = sanitize_for_external_ai(str(value or ""))
    clean = re.sub(r"[\x00-\x1f]+", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return (clean or fallback)[:limit]


def _payload_sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def _require_text(item: dict[str, Any], key: str, index: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"第 {index} 个候选缺少 {key}。")
    item[key] = value.strip()[:4000]
    return item[key]


def _require_source_ids(value: Any, known_ids: set[str], label: str) -> list[str]:
    if not isinstance(value, list) or not value or any(not isinstance(entry, str) for entry in value):
        raise ValueError(f"{label} source_ids 必须是非空字符串数组。")
    source_ids = list(dict.fromkeys(entry.strip() for entry in value if entry.strip()))
    unknown = sorted(set(source_ids) - known_ids)
    if unknown:
        raise ValueError(f"{label} 引用了任务包之外的 source_id：{', '.join(unknown)}")
    return source_ids


def _sanitize_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_for_external_ai(value)
    if isinstance(value, list):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _sanitize_json_value(item) for key, item in value.items()}
    return value


def _candidate_confidence(item: dict[str, Any]) -> float:
    values = [
        float(claim["confidence"])
        for claim in item.get("claims", [])
        if isinstance(claim, dict) and isinstance(claim.get("confidence"), (int, float))
    ]
    return sum(values) / len(values) if values else 0.0
