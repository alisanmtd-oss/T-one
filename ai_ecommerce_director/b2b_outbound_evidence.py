from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Mapping, Sequence


class OutboundEvidenceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _required(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise OutboundEvidenceError(f"missing_{field}", f"{field} is required")
    return result


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: bytes | str | Mapping[str, Any] | Sequence[Any]) -> str:
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        raw = value.encode("utf-8")
    else:
        raw = _canonical(value)
    return hashlib.sha256(raw).hexdigest().upper()


def build_evidence_bundle(
    *,
    source_evidence_refs: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    refs: list[dict[str, Any]] = []
    ref_ids: set[str] = set()
    for source in source_evidence_refs:
        ref_id = _required(source.get("evidence_ref_id"), "evidence_ref_id")
        if ref_id in ref_ids:
            raise OutboundEvidenceError("duplicate_evidence_ref_id", "evidence_ref_id must be unique")
        ref_ids.add(ref_id)
        refs.append(
            {
                "evidence_ref_id": ref_id,
                "source_kind": _required(source.get("source_kind"), "source_kind"),
                "locator": _required(source.get("locator"), "locator"),
                "observed_at": _required(source.get("observed_at"), "observed_at"),
                "content_sha256": str(source.get("content_sha256") or "").strip().upper(),
                "scope": _required(source.get("scope"), "scope"),
                "truth_boundary": str(source.get("truth_boundary") or "candidate_signal_only").strip(),
            }
        )

    normalized_claims: list[dict[str, Any]] = []
    claim_ids: set[str] = set()
    for claim in claims:
        claim_id = _required(claim.get("claim_id"), "claim_id")
        if claim_id in claim_ids:
            raise OutboundEvidenceError("duplicate_claim_id", "claim_id must be unique")
        claim_ids.add(claim_id)
        status = _required(claim.get("status"), "claim_status")
        if status not in {"supported", "hypothesis", "unknown", "rejected"}:
            raise OutboundEvidenceError("invalid_claim_status", "claim status is not recognized")
        linked = [str(value).strip() for value in claim.get("evidence_ref_ids", []) if str(value).strip()]
        missing = [value for value in linked if value not in ref_ids]
        if missing:
            raise OutboundEvidenceError("claim_evidence_ref_missing", "claim references unknown evidence")
        if status == "supported" and not linked:
            raise OutboundEvidenceError("supported_claim_without_evidence", "supported claim must reference evidence")
        normalized_claims.append(
            {
                "claim_id": claim_id,
                "claim_text": _required(claim.get("claim_text"), "claim_text"),
                "status": status,
                "evidence_ref_ids": linked,
                "not_a_legal_or_consent_conclusion": True,
            }
        )
    bundle = {"source_evidence_refs": refs, "claim_refs": normalized_claims}
    return {**bundle, "evidence_bundle_sha256": _sha(bundle)}


def _attachment_record(item: Mapping[str, Any]) -> dict[str, Any]:
    content = item.get("content")
    if not isinstance(content, bytes):
        raise OutboundEvidenceError("attachment_bytes_required", "attachment content must be supplied as bytes")
    malware = str(item.get("malware_scan_status") or "not_scanned").strip().lower()
    review = str(item.get("content_review_status") or "not_reviewed").strip().lower()
    scan_ref = str(item.get("scan_evidence_ref") or "").strip()
    released = malware == "clean" and review == "passed" and bool(scan_ref)
    return {
        "filename": _required(item.get("filename"), "attachment_filename"),
        "media_type": _required(item.get("media_type"), "attachment_media_type"),
        "size_bytes": len(content),
        "sha256": _sha(content),
        "malware_scan_status": malware,
        "content_review_status": review,
        "scan_evidence_ref": scan_ref,
        "quarantine_state": "released_for_owner_review" if released else "quarantined_untrusted",
        "allowed_for_external_send": False,
    }


def build_outbound_draft_packet(
    *,
    pipeline_id: str,
    channel: str,
    sender_identity: Mapping[str, Any],
    recipient_identity: Mapping[str, Any],
    subject: str,
    body: str,
    attachments: Sequence[Mapping[str, Any]],
    evidence_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    sender = {
        "sender_account_id": _required(sender_identity.get("sender_account_id"), "sender_account_id"),
        "connector_binding_id": _required(sender_identity.get("connector_binding_id"), "connector_binding_id"),
        "from_address": _required(sender_identity.get("from_address"), "from_address"),
        "reply_to": _required(sender_identity.get("reply_to"), "reply_to"),
        "authenticated_domain_status": str(sender_identity.get("authenticated_domain_status") or "unverified").strip(),
    }
    recipient = {
        "recipient_value": _required(recipient_identity.get("recipient_value"), "recipient_value"),
        "recipient_type": _required(recipient_identity.get("recipient_type"), "recipient_type"),
        "evidence_ref_id": _required(recipient_identity.get("evidence_ref_id"), "recipient_evidence_ref_id"),
        "verification_state": str(recipient_identity.get("verification_state") or "unverified").strip(),
        "contact_basis_state": str(recipient_identity.get("contact_basis_state") or "unknown").strip(),
        "suppression_state": str(recipient_identity.get("suppression_state") or "unknown").strip(),
    }
    refs = {
        str(item.get("evidence_ref_id") or "")
        for item in evidence_bundle.get("source_evidence_refs", [])
        if isinstance(item, Mapping)
    }
    if recipient["evidence_ref_id"] not in refs:
        raise OutboundEvidenceError("recipient_evidence_ref_missing", "recipient must point to a source_evidence_ref")

    attachment_manifest = [_attachment_record(item) for item in attachments]
    payload = {
        "pipeline_id": _required(pipeline_id, "pipeline_id"),
        "channel": _required(channel, "channel"),
        "sender_identity": sender,
        "recipient_identity": recipient,
        "subject": str(subject or ""),
        "body": _required(body, "body"),
        "attachments": attachment_manifest,
        "evidence_bundle_sha256": _required(evidence_bundle.get("evidence_bundle_sha256"), "evidence_bundle_sha256"),
    }
    hashes = {
        "sender_identity_sha256": _sha(sender),
        "recipient_identity_sha256": _sha(recipient),
        "subject_sha256": _sha(payload["subject"]),
        "body_sha256": _sha(payload["body"]),
        "attachment_manifest_sha256": _sha(attachment_manifest),
    }
    send_blockers: list[str] = ["exact_single_use_owner_approval_required"]
    if sender["authenticated_domain_status"] != "verified":
        send_blockers.append("sender_identity_or_domain_unverified")
    if recipient["verification_state"] != "verified":
        send_blockers.append("recipient_unverified")
    if recipient["contact_basis_state"] != "verified_allowed":
        send_blockers.append("contact_basis_unverified")
    if recipient["suppression_state"] != "not_suppressed":
        send_blockers.append("suppression_state_not_clear")
    if any(item["quarantine_state"] != "released_for_owner_review" for item in attachment_manifest):
        send_blockers.append("attachment_quarantined")
    packet = {
        **payload,
        **hashes,
        "draft_payload_sha256": _sha({**payload, **hashes}),
        "approval_action_type": "outbound_message_send",
        "approval_state": "not_approved",
        "external_send_allowed": False,
        "send_blockers": send_blockers,
        "external_action_executed": False,
    }
    return packet


def build_screening_case(
    *,
    case_id: str,
    pipeline_id: str,
    screened_entity: Mapping[str, Any],
    candidate_matches: Sequence[Mapping[str, Any]],
    source_evidence_ref_ids: Sequence[str],
    screened_at: datetime | str,
) -> dict[str, Any]:
    if isinstance(screened_at, datetime) and screened_at.tzinfo is None:
        raise OutboundEvidenceError("screened_at_timezone_required", "screened_at must include timezone")
    match_records = [
        {
            "list_source": _required(item.get("list_source"), "list_source"),
            "candidate_name": _required(item.get("candidate_name"), "candidate_name"),
            "match_basis": _required(item.get("match_basis"), "match_basis"),
            "match_score": str(item.get("match_score") or "unknown"),
            "status": "candidate_match_not_determination",
        }
        for item in candidate_matches
    ]
    status = "potential_match_needs_authorized_review" if match_records else "no_candidate_match_not_legal_clearance"
    case = {
        "case_id": _required(case_id, "case_id"),
        "pipeline_id": _required(pipeline_id, "pipeline_id"),
        "screened_entity": dict(screened_entity),
        "candidate_matches": match_records,
        "source_evidence_ref_ids": [_required(value, "source_evidence_ref_id") for value in source_evidence_ref_ids],
        "screened_at": str(screened_at),
        "status": status,
        "authorized_reviewer_decision": "pending" if match_records else "not_requested",
        "legal_conclusion": False,
        "external_send_allowed": False,
        "external_action_executed": False,
    }
    return {**case, "case_sha256": _sha(case)}
