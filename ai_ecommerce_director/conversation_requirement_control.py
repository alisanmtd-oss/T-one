from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_RELATIVE_PATH = Path("data") / "conversation_requirement_control.json"
MAX_INPUTS = 10_000
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SECRET_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|token|secret|api[_ -]?key|otp|verification[_ -]?code)"
    r"\s*[:=：]\s*\S+"
)

SOURCE_KINDS = {"message", "screenshot", "attachment", "website", "delegation"}
LIFECYCLE_STATES = {
    "received",
    "partial_read",
    "read",
    "associated",
    "implementation_in_progress",
    "implemented",
    "verified",
}
DELIVERY_STATUSES = {
    "pending",
    "real_implemented",
    "manually_verified",
    "partially_complete",
    "placeholder_or_false",
    "blocked",
    "owner_input",
}
REQUIREMENT_KINDS = {
    "backend",
    "ui",
    "knowledge",
    "external_connection",
    "external_action",
}
PRESENTATION_ONLY_EVIDENCE = {"report", "test", "config", "page", "button", "index"}
IMPLEMENTATION_EVIDENCE = {"source", "business_method", "runtime_receipt"}
LOCAL_FILE_EVIDENCE = {
    "source",
    "test",
    "config",
    "report",
    "index",
    "distilled_memory",
    "evaluation",
    "runtime_receipt",
    "formal_app_receipt",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _default_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_at": _now(),
        "inputs": [],
        "external_action_count": 0,
    }


def _read_state(root: Path) -> dict[str, Any]:
    path = root / STATE_RELATIVE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = _default_state()
    if not isinstance(payload, dict):
        payload = _default_state()
    if not isinstance(payload.get("inputs"), list):
        payload["inputs"] = []
    payload["schema_version"] = 1
    payload["external_action_count"] = 0
    return payload


def _save_state(root: Path, state: dict[str, Any]) -> None:
    path = root / STATE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    state["schema_version"] = 1
    state["updated_at"] = _now()
    state["inputs"] = list(state.get("inputs") or [])[-MAX_INPUTS:]
    state["external_action_count"] = 0
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _stable_ref(value: Any, label: str, *, required: bool = True) -> str:
    text = " ".join(str(value or "").split())
    if not text and not required:
        return ""
    if not text or not IDENTIFIER_PATTERN.fullmatch(text):
        raise ValueError(f"{label} 必须是稳定内部引用，不能是自由文本或隐私值。")
    return text


def _sha256(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not SHA256_PATTERN.fullmatch(text):
        raise ValueError("content_sha256 必须是 64 位小写 SHA-256。")
    return text


def _safe_summary(value: Any) -> str:
    text = " ".join(str(value or "").split())[:500]
    text = EMAIL_PATTERN.sub("[redacted-email]", text)
    text = SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    return text


def _input_id(payload: dict[str, Any]) -> str:
    seed = "|".join(
        [
            str(payload.get("thread_id") or "").strip().casefold(),
            str(payload.get("source_kind") or "").strip().casefold(),
            str(payload.get("source_ref") or "").strip().casefold(),
            str(payload.get("content_sha256") or "").strip().casefold(),
        ]
    )
    return f"input-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:24]}"


def _find_input(state: dict[str, Any], input_id: str) -> tuple[int, dict[str, Any]]:
    for index, item in enumerate(state.get("inputs") or []):
        if str(item.get("input_id") or "") == input_id:
            return index, dict(item)
    raise ValueError(f"未找到输入：{input_id}")


def _replace_input(state: dict[str, Any], index: int, item: dict[str, Any]) -> None:
    inputs = list(state.get("inputs") or [])
    inputs[index] = item
    state["inputs"] = inputs


def register_input(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Register a message/screenshot/attachment/site by reference and hash, never by raw body."""
    source_kind = str(payload.get("source_kind") or "").strip().casefold()
    if source_kind not in SOURCE_KINDS:
        raise ValueError(f"source_kind 必须是：{', '.join(sorted(SOURCE_KINDS))}。")
    source_ref = _stable_ref(payload.get("source_ref"), "source_ref")
    thread_id = _stable_ref(payload.get("thread_id"), "thread_id")
    project_claim = _stable_ref(payload.get("project_claim"), "project_claim")
    content_sha256 = _sha256(payload.get("content_sha256"))
    source_url = ""
    if source_kind == "website":
        source_url = str(payload.get("source_url") or "").strip()
        if not source_url.startswith(("https://", "http://")):
            raise ValueError("网站输入必须记录 http(s) source_url。")

    normalized = {
        "source_kind": source_kind,
        "source_ref": source_ref,
        "thread_id": thread_id,
        "project_claim": project_claim,
        "content_sha256": content_sha256,
    }
    stable_id = _input_id(normalized)
    state = _read_state(root)
    for existing in state.get("inputs") or []:
        if str(existing.get("input_id") or "") == stable_id:
            return {"ok": True, "deduplicated": True, "input": dict(existing), "external_action_count": 0}

    item = {
        "input_id": stable_id,
        **normalized,
        "source_url": source_url,
        "received_at": str(payload.get("received_at") or _now())[:64],
        "summary": _safe_summary(payload.get("summary")),
        "lifecycle_state": "received",
        "delivery_status": "pending",
        "read_receipt": {},
        "association": {},
        "requirement_kind": "",
        "evidence": [],
        "missing": ["input_read", "requirement_association", "implementation_evidence"],
        "external_action_count": 0,
        "created_at": _now(),
        "updated_at": _now(),
    }
    state["inputs"].append(item)
    _save_state(root, state)
    return {"ok": True, "deduplicated": False, "input": item, "external_action_count": 0}


def mark_input_read(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    state = _read_state(root)
    input_id = _stable_ref(payload.get("input_id"), "input_id")
    index, item = _find_input(state, input_id)
    reader = _stable_ref(payload.get("reader"), "reader")
    kind = item["source_kind"]
    receipt: dict[str, Any] = {
        "reader": reader,
        "read_at": _now(),
        "content_sha256_confirmed": item["content_sha256"],
    }

    if kind == "screenshot":
        visual_receipt = _stable_ref(
            payload.get("visual_inspection_receipt"),
            "visual_inspection_receipt",
            required=False,
        )
        context_ref = _stable_ref(
            payload.get("conversation_context_ref"),
            "conversation_context_ref",
            required=False,
        )
        if not visual_receipt or not context_ref:
            raise ValueError("截图必须有视觉检查回执和关联对话上下文，不能只登记附件路径。")
        receipt.update(
            {
                "visual_inspection_receipt": visual_receipt,
                "conversation_context_ref": context_ref,
                "read_completeness": "full",
            }
        )
    elif kind == "attachment":
        completeness = str(payload.get("read_completeness") or "").strip().casefold()
        if completeness not in {"partial", "full"}:
            raise ValueError("附件必须记录 read_completeness=partial 或 full。")
        bytes_read = int(payload.get("bytes_read") or 0)
        if bytes_read < 0:
            raise ValueError("bytes_read 不能为负数。")
        receipt.update({"read_completeness": completeness, "bytes_read": bytes_read})
    elif kind == "website":
        captured_at = str(payload.get("captured_at") or "").strip()
        access_boundary = _stable_ref(
            payload.get("access_boundary"),
            "access_boundary",
            required=False,
        )
        if not captured_at or not access_boundary:
            raise ValueError("网站必须记录 captured_at 与 access_boundary。")
        receipt.update(
            {
                "captured_at": captured_at[:64],
                "access_boundary": access_boundary,
                "robots_reviewed": bool(payload.get("robots_reviewed")),
                "read_completeness": "full",
            }
        )
    else:
        receipt["read_completeness"] = "full"

    item["read_receipt"] = receipt
    if receipt.get("read_completeness") == "partial":
        item["lifecycle_state"] = "partial_read"
        item["missing"] = ["attachment_full_read", "requirement_association", "implementation_evidence"]
    else:
        item["lifecycle_state"] = "read"
        item["missing"] = ["requirement_association", "implementation_evidence"]
    item["updated_at"] = _now()
    _replace_input(state, index, item)
    _save_state(root, state)
    return {"ok": True, "input": item, "external_action_count": 0}


def associate_input(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    state = _read_state(root)
    input_id = _stable_ref(payload.get("input_id"), "input_id")
    index, item = _find_input(state, input_id)
    requirement_ids = [
        _stable_ref(value, "requirement_id")
        for value in list(payload.get("requirement_ids") or [])
        if str(value or "").strip()
    ]
    if not requirement_ids:
        raise ValueError("至少关联一个 requirement_id。")
    task_ref = _stable_ref(payload.get("task_ref"), "task_ref")
    project_claim = _stable_ref(payload.get("project_claim"), "project_claim")
    if project_claim != item["project_claim"]:
        raise ValueError("project_claim 与输入登记的项目认领不一致。")
    item["association"] = {
        "requirement_ids": list(dict.fromkeys(requirement_ids)),
        "task_ref": task_ref,
        "project_claim": project_claim,
        "associated_at": _now(),
    }
    if item["lifecycle_state"] == "read":
        item["lifecycle_state"] = "associated"
        item["missing"] = ["implementation_evidence"]
    elif item["lifecycle_state"] == "partial_read":
        item["missing"] = ["attachment_full_read", "implementation_evidence"]
    else:
        item["missing"] = ["input_fully_read", "implementation_evidence"]
    item["updated_at"] = _now()
    _replace_input(state, index, item)
    _save_state(root, state)
    return {"ok": True, "input": item, "external_action_count": 0}


def _normalized_evidence(values: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for value in list(values or []):
        if not isinstance(value, dict):
            continue
        kind = str(value.get("kind") or "").strip().casefold()
        ref = str(value.get("ref") or "").strip()
        if not kind or not ref:
            continue
        key = (kind, ref)
        if key not in seen:
            result.append({"kind": kind[:80], "ref": ref[:500]})
            seen.add(key)
    return result


def _required_evidence(requirement_kind: str) -> set[str]:
    required = {"implementation_source", "test"}
    if requirement_kind == "ui":
        required.update({"formal_app_receipt", "manual_verification"})
    elif requirement_kind == "knowledge":
        required.update({"distilled_memory", "evaluation"})
    elif requirement_kind == "external_connection":
        required.update({"verified_connector", "owner_authorization"})
    elif requirement_kind == "external_action":
        required.update(
            {
                "verified_connector",
                "owner_authorization",
                "external_action_receipt",
            }
        )
    return required


def _evidence_capabilities(evidence: list[dict[str, str]]) -> set[str]:
    kinds = {item["kind"] for item in evidence}
    capabilities = set(kinds)
    if kinds & IMPLEMENTATION_EVIDENCE:
        capabilities.add("implementation_source")
    return capabilities


def finalize_requirement(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply the hard truth gate. The function records no external action."""
    state = _read_state(root)
    input_id = _stable_ref(payload.get("input_id"), "input_id")
    index, item = _find_input(state, input_id)
    requirement_kind = str(payload.get("requirement_kind") or "").strip().casefold()
    if requirement_kind not in REQUIREMENT_KINDS:
        raise ValueError(f"requirement_kind 必须是：{', '.join(sorted(REQUIREMENT_KINDS))}。")
    requested_status = str(payload.get("requested_status") or "").strip().casefold()
    if requested_status not in DELIVERY_STATUSES - {"pending"}:
        raise ValueError("requested_status 不是允许的交付状态。")

    evidence = _normalized_evidence(payload.get("evidence"))
    capabilities = _evidence_capabilities(evidence)
    missing: list[str] = []
    read_complete = item.get("lifecycle_state") in {"read", "associated", "implementation_in_progress", "implemented", "verified"}
    if not read_complete:
        missing.append("input_fully_read")
    if not item.get("association"):
        missing.append("requirement_association")
    missing.extend(sorted(_required_evidence(requirement_kind) - capabilities))

    if requested_status in {"blocked", "owner_input", "partially_complete", "placeholder_or_false"}:
        status = requested_status
    elif missing:
        if requirement_kind in {"external_connection", "external_action"}:
            status = "blocked"
        elif capabilities and capabilities <= PRESENTATION_ONLY_EVIDENCE:
            status = "placeholder_or_false"
        else:
            status = "partially_complete"
    else:
        status = requested_status

    item["requirement_kind"] = requirement_kind
    item["evidence"] = evidence
    item["delivery_status"] = status
    item["missing"] = list(dict.fromkeys(missing))
    item["external_action_count"] = 0
    if status == "manually_verified":
        item["lifecycle_state"] = "verified"
    elif status == "real_implemented":
        item["lifecycle_state"] = "implemented"
    elif item.get("association") and read_complete:
        item["lifecycle_state"] = "implementation_in_progress"
    item["updated_at"] = _now()
    _replace_input(state, index, item)
    _save_state(root, state)
    return {
        "ok": status in {"real_implemented", "manually_verified"},
        "input": item,
        "missing": item["missing"],
        "external_action_count": 0,
    }


def _unresolved_item(item: dict[str, Any]) -> dict[str, Any]:
    missing = list(item.get("missing") or [])
    if item.get("lifecycle_state") == "received" and "input_read" not in missing:
        missing.insert(0, "input_read")
    return {
        "input_id": item.get("input_id"),
        "source_kind": item.get("source_kind"),
        "source_ref": item.get("source_ref"),
        "project_claim": item.get("project_claim"),
        "lifecycle_state": item.get("lifecycle_state"),
        "delivery_status": item.get("delivery_status"),
        "task_ref": (item.get("association") or {}).get("task_ref", ""),
        "requirement_ids": (item.get("association") or {}).get("requirement_ids", []),
        "missing": list(dict.fromkeys(missing)),
    }


def conversation_requirement_snapshot(root: Path) -> dict[str, Any]:
    state = _read_state(root)
    inputs = list(state.get("inputs") or [])
    unresolved = [
        _unresolved_item(item)
        for item in inputs
        if item.get("delivery_status") not in {"real_implemented", "manually_verified"}
    ]
    return {
        "schema_version": 1,
        "input_count": len(inputs),
        "resolved_count": len(inputs) - len(unresolved),
        "unresolved_count": len(unresolved),
        "unresolved": unresolved,
        "external_action_count": 0,
        "raw_content_stored": False,
    }


def validate_conversation_requirement_state(root: Path) -> dict[str, Any]:
    state = _read_state(root)
    errors: list[str] = []
    seen: set[str] = set()
    forbidden_fields = {"raw_text", "raw_body", "content", "password", "token", "otp", "verification_code"}
    for index, item in enumerate(state.get("inputs") or []):
        prefix = f"inputs[{index}]"
        input_id = str(item.get("input_id") or "")
        if input_id in seen:
            errors.append(f"{prefix}: duplicate input_id")
        seen.add(input_id)
        if item.get("source_kind") not in SOURCE_KINDS:
            errors.append(f"{prefix}: invalid source_kind")
        if item.get("lifecycle_state") not in LIFECYCLE_STATES:
            errors.append(f"{prefix}: invalid lifecycle_state")
        if item.get("delivery_status") not in DELIVERY_STATUSES:
            errors.append(f"{prefix}: invalid delivery_status")
        if not SHA256_PATTERN.fullmatch(str(item.get("content_sha256") or "")):
            errors.append(f"{prefix}: invalid content_sha256")
        leaked = sorted(forbidden_fields & set(item))
        if leaked:
            errors.append(f"{prefix}: forbidden fields {','.join(leaked)}")
        if int(item.get("external_action_count") or 0) != 0:
            errors.append(f"{prefix}: external_action_count must remain 0")
    return {
        "ok": not errors,
        "errors": errors,
        "input_count": len(state.get("inputs") or []),
        "external_action_count": 0,
    }


def validate_evidence_references(root: Path) -> dict[str, Any]:
    """Verify cited local evidence exists and never relies on a private absolute path."""
    state = _read_state(root)
    errors: list[str] = []
    checked_reference_count = 0
    root_resolved = root.resolve()
    for index, item in enumerate(state.get("inputs") or []):
        input_id = str(item.get("input_id") or f"inputs[{index}]")
        for evidence_index, evidence in enumerate(list(item.get("evidence") or [])):
            if not isinstance(evidence, dict):
                continue
            kind = str(evidence.get("kind") or "").strip().casefold()
            if kind not in LOCAL_FILE_EVIDENCE:
                continue
            raw_ref = str(evidence.get("ref") or "")
            for raw_part in raw_ref.split(";"):
                reference = raw_part.strip()
                if not reference or reference.startswith(("https://", "http://")):
                    continue
                checked_reference_count += 1
                path_text = reference.split("#", 1)[0].strip().replace("\\", "/")
                candidate_path = Path(path_text)
                prefix = f"{input_id}.evidence[{evidence_index}]/{kind}"
                if candidate_path.is_absolute() or re.match(r"^[A-Za-z]:/", path_text):
                    errors.append(f"{prefix}: absolute path is forbidden: {reference}")
                    continue
                candidate = (root_resolved / candidate_path).resolve()
                try:
                    candidate.relative_to(root_resolved)
                except ValueError:
                    errors.append(f"{prefix}: path escapes project root: {reference}")
                    continue
                if not candidate.is_file():
                    errors.append(f"{prefix}: missing local evidence file: {reference}")

    return {
        "ok": not errors,
        "errors": errors,
        "input_count": len(state.get("inputs") or []),
        "checked_reference_count": checked_reference_count,
        "external_action_count": 0,
    }


def import_48h_requirement_ledger(root: Path, ledger_path: Path) -> dict[str, Any]:
    """Import the compact 48-hour ledger into the hard gate without upgrading claims."""
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    requirements = list(payload.get("must_not_forget_user_requirements") or [])
    risks = list(payload.get("unfinished_or_false_completion_risk") or [])
    rows: list[tuple[str, int, str, str]] = []
    for index, value in enumerate(requirements, start=1):
        rows.append(("requirement", index, str(value), "partially_complete"))
    for index, value in enumerate(risks, start=1):
        if not isinstance(value, dict):
            continue
        summary = "；".join(
            part
            for part in [
                str(value.get("item") or "").strip(),
                str(value.get("status") or "").strip(),
                str(value.get("next") or "").strip(),
            ]
            if part
        )
        original_status = str(value.get("status") or "").casefold()
        if "owner_input" in original_status:
            delivery_status = "owner_input"
        elif "blocked" in original_status:
            delivery_status = "blocked"
        else:
            # A compact ledger entry is an index, not implementation/App evidence.
            delivery_status = "partially_complete"
        rows.append(("risk", index, summary, delivery_status))

    imported: list[dict[str, Any]] = []
    ledger_ref = ledger_path.as_posix()
    for group, index, summary, delivery_status in rows:
        digest = hashlib.sha256(summary.encode("utf-8")).hexdigest()
        result = register_input(
            root,
            {
                "source_kind": "message",
                "source_ref": f"48h-ledger/{group}-{index:03d}",
                "thread_id": "t-one-48h-reconciliation",
                "project_claim": "t_one",
                "content_sha256": digest,
                "received_at": str(payload.get("generated_at") or _now()),
                "summary": summary,
            },
        )
        item = result["input"]
        mark_input_read(root, {"input_id": item["input_id"], "reader": "ledger-importer"})
        associate_input(
            root,
            {
                "input_id": item["input_id"],
                "requirement_ids": [f"R48H-{group.upper()}-{index:03d}"],
                "task_ref": "task-48h-reconciliation",
                "project_claim": "t_one",
            },
        )
        finalized = finalize_requirement(
            root,
            {
                "input_id": item["input_id"],
                "requirement_kind": "backend",
                "requested_status": delivery_status,
                "evidence": [{"kind": "index", "ref": ledger_ref}],
            },
        )
        imported.append(
            {
                "input_id": item["input_id"],
                "group": group,
                "index": index,
                "delivery_status": finalized["input"]["delivery_status"],
            }
        )

    snapshot = conversation_requirement_snapshot(root)
    return {
        "ok": validate_conversation_requirement_state(root)["ok"],
        "ledger_path": ledger_ref,
        "requirement_count": len(requirements),
        "risk_count": len(risks),
        "imported_count": len(imported),
        "deduplicated_input_count": snapshot["input_count"],
        "unresolved_count": snapshot["unresolved_count"],
        "external_action_count": 0,
        "items": imported,
    }
