from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .scoring import score_record
from .storage import append_record, read_records
from .types import IntakeRecord


POD_IP_RISK_SEED = Path("config") / "pod_ip_risk_seed.json"

PROHIBITED_PATTERNS = [
    ("hate", ["nazi", "kkk", "white supremacy", "hate symbol", "racial slur", "恐怖主义", "纳粹", "仇恨"]),
    ("adult", ["porn", "explicit sex", "nude child", "未成年人色情", "成人露骨"]),
    ("dangerous", ["how to make a bomb", "weapon instruction", "terror attack", "制毒", "爆炸物教程"]),
    ("illegal", ["counterfeit certificate", "fake passport", "stolen credit card", "伪造证件", "盗刷"]),
]

RIGHT_TYPE_MAP = {
    "brand_or_logo": "brand",
    "character_or_cartoon": "character",
    "celebrity_or_likeness": "celebrity",
    "sports_team_or_school": "trademark",
    "copyrighted_artwork": "copyright",
    "platform_tro_case": "other",
    "text_or_slogan_ip": "trademark",
    "trademark": "trademark",
    "copyright": "copyright",
    "character": "character",
    "brand": "brand",
    "celebrity": "celebrity",
}


def scan_pod_ip_risk(root: Path, payload: dict[str, Any], *, persist: bool = False) -> dict[str, Any]:
    scan_id = str(payload.get("scanId") or payload.get("scan_id") or uuid4().hex)
    text = payload_text(payload)
    blocked_matches = prohibited_matches(text)
    matched_rights = matched_rights_from_library(root, text)
    matched_rights.extend(matched_rights_from_seed(root, text))
    matched_rights = dedupe_rights(matched_rights)
    authorized = has_authorization(payload)

    max_confidence = max((float(item.get("confidence", 0) or 0) for item in matched_rights), default=0)

    if blocked_matches:
        status = "prohibited"
        visibility = "reject"
        action = "reject"
        risk_score = 100
        certainty = "confirmed"
        public_allowed = False
        channel_sync_allowed = False
        private_order_allowed = False
        reasons = [f"Blocked platform-prohibited content: {', '.join(blocked_matches)}."]
    elif matched_rights and not authorized and confirmed_ip_match(matched_rights):
        status = "confirmed_ip"
        visibility = "private_only"
        action = "approve_private_only"
        risk_score = min(96, 72 + len(matched_rights) * 6 + max_confidence * 0.2)
        certainty = "confirmed"
        public_allowed = False
        channel_sync_allowed = False
        private_order_allowed = True
        reasons = [
            "Confirmed or high-confidence IP, trademark, copyright, character, brand, celebrity or TRO match.",
            "POD can keep it as private custom/self-use only, but should not show it publicly or sync it to marketplace channels before authorization review.",
        ]
    elif matched_rights and not authorized:
        status = "borderline"
        visibility = "public"
        action = "manual_review"
        risk_score = min(78, 42 + len(matched_rights) * 6 + max_confidence * 0.18)
        certainty = "medium" if max_confidence >= 70 else "low"
        public_allowed = True
        channel_sync_allowed = False
        private_order_allowed = True
        reasons = [
            "Borderline or suspected style/IP similarity matched the local risk library.",
            "Early POD platform policy allows public display with a risk tag and review queue, but does not allow automatic sync to high-risk external channels.",
        ]
    elif matched_rights and authorized:
        status = "clear"
        visibility = "public"
        action = "approve_public"
        risk_score = 22
        certainty = "high"
        public_allowed = True
        channel_sync_allowed = True
        private_order_allowed = True
        reasons = [
            "Matched rights-like elements, but authorization/license proof was provided.",
            "Keep authorization scope, channels and expiration on file before public listing or marketplace sync.",
        ]
    else:
        status = "clear"
        visibility = "public"
        action = "approve_public"
        risk_score = 8 if text else 15
        certainty = "low"
        public_allowed = True
        channel_sync_allowed = True
        private_order_allowed = True
        reasons = ["No obvious IP or prohibited-content match in the local risk library."]

    result = {
        "scanId": scan_id,
        "status": status,
        "riskScore": round(float(risk_score), 2),
        "visibilityRecommendation": visibility,
        "matchedRights": matched_rights,
        "reasons": reasons,
        "suggestedAdminAction": action,
        "certainty": certainty,
        "publicAllowed": public_allowed,
        "channelSyncAllowed": channel_sync_allowed,
        "privateOrderAllowed": private_order_allowed,
        "scannedAt": datetime.now(timezone.utc).isoformat(),
    }
    if persist or bool(payload.get("persist", False)):
        append_record(root, scan_result_record(payload, result, text))
    return result


def payload_text(payload: dict[str, Any]) -> str:
    fields: list[str] = []
    for key in [
        "title",
        "name",
        "productName",
        "product_name",
        "description",
        "prompt",
        "ocrText",
        "ocr_text",
        "designText",
        "design_text",
        "imageAlt",
        "image_alt",
        "tags",
        "keywords",
        "brand",
        "category",
    ]:
        value = payload.get(key)
        if isinstance(value, list):
            fields.extend(str(item) for item in value)
        elif value not in {None, ""}:
            fields.append(str(value))
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for value in metadata.values():
            if isinstance(value, (str, int, float)):
                fields.append(str(value))
    return " ".join(fields).strip()


def prohibited_matches(text: str) -> list[str]:
    lowered = text.lower()
    matches: list[str] = []
    for label, patterns in PROHIBITED_PATTERNS:
        if any(pattern.lower() in lowered for pattern in patterns):
            matches.append(label)
    return matches


def matched_rights_from_library(root: Path, text: str) -> list[dict[str, Any]]:
    lowered = text.lower()
    matches: list[dict[str, Any]] = []
    for record in read_records(root, "ip_image_risk"):
        fields = record.fields
        element = first_value(fields, ["risk_element", "visual_signature", "product_name", "term"])
        owner = first_value(fields, ["rights_owner", "plaintiff", "trademark_owner"])
        category = first_value(fields, ["element_category", "risk_category"])
        if not element and not owner:
            continue
        candidate = element or owner
        if text_matches(candidate, lowered):
            confirmed_source = bool(fields.get("case_number") or str(fields.get("tro_status") or "").lower() or fields.get("platform_notice_url") or fields.get("complaint_url"))
            confidence = 94 if confirmed_source else (82 if record.score.get("blocks_auto_publish") else 68)
            matches.append(
                {
                    "type": right_type(category),
                    "name": candidate,
                    "owner": owner or None,
                    "confidence": confidence,
                    "source": str(fields.get("evidence_url") or fields.get("search_url") or fields.get("infringing_listing_url") or record.record_id),
                    "confirmed": confirmed_source,
                }
            )
    return matches


def matched_rights_from_seed(root: Path, text: str) -> list[dict[str, Any]]:
    lowered = text.lower()
    path = root / POD_IP_RISK_SEED
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return []
    matches: list[dict[str, Any]] = []
    for item in payload.get("risk_element_categories", []):
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "other")
        examples = item.get("examples") if isinstance(item.get("examples"), list) else []
        hit = next((str(example) for example in examples if str(example).lower() in lowered), "")
        if hit:
            matches.append(
                {
                    "type": right_type(category),
                    "name": hit,
                    "owner": None,
                    "confidence": 68,
                    "source": f"seed:{category}",
                }
            )
    return matches


def scan_result_record(payload: dict[str, Any], result: dict[str, Any], text: str) -> IntakeRecord:
    fields = {
        "risk_element": first_nonempty([payload.get("title"), payload.get("productName"), payload.get("designText"), text[:120]]) or result["scanId"],
        "element_category": "pod_scan_result",
        "risk_category": result["status"],
        "risk_level": "high" if result["status"] in {"prohibited", "confirmed_ip"} else ("medium" if result["status"] == "borderline" else "low"),
        "authorization_status": "authorized" if has_authorization(payload) else "unknown",
        "authorization_proof": str(payload.get("authorizationProof") or payload.get("authorization_proof") or ""),
        "evidence_url": str(payload.get("imageUrl") or payload.get("image_url") or payload.get("sourceUrl") or payload.get("source_url") or ""),
        "source_platform": "POD",
        "scan_id": result["scanId"],
        "pod_visibility_recommendation": result["visibilityRecommendation"],
        "pod_suggested_admin_action": result["suggestedAdminAction"],
        "pod_public_allowed": result["publicAllowed"],
        "pod_channel_sync_allowed": result["channelSyncAllowed"],
        "pod_private_order_allowed": result["privateOrderAllowed"],
        "pod_certainty": result["certainty"],
        "matched_rights": result["matchedRights"],
        "scan_reasons": result["reasons"],
    }
    score, notes = score_record("ip_image_risk", fields)
    return IntakeRecord(
        record_type="ip_image_risk",
        fields=fields,
        raw_text=json.dumps({"payload": payload, "scan_result": result}, ensure_ascii=False),
        source="pod_ip_scan_api",
        score=score,
        director_notes=notes,
        review_status="approved" if result["status"] == "clear" else "needs_review",
        confidence=0.78,
    )


def has_authorization(payload: dict[str, Any]) -> bool:
    status = str(payload.get("authorizationStatus") or payload.get("authorization_status") or payload.get("licenseStatus") or "").lower()
    proof = str(payload.get("authorizationProof") or payload.get("authorization_proof") or payload.get("licenseFile") or "").strip()
    return bool(proof or any(word in status for word in ["authorized", "licensed", "approved", "allowed", "permitted", "已授权", "许可"]))


def text_matches(candidate: str, lowered_text: str) -> bool:
    clean = str(candidate or "").strip().lower()
    if not clean or len(clean) < 3:
        return False
    if clean in lowered_text:
        return True
    tokens = [token for token in re.split(r"[^a-z0-9\u4e00-\u9fff]+", clean) if len(token) >= 4]
    if not tokens:
        return False
    return sum(1 for token in tokens if token in lowered_text) >= min(2, len(tokens))


def dedupe_rights(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda value: float(value.get("confidence", 0) or 0), reverse=True):
        key = (str(item.get("type") or ""), str(item.get("name") or "").lower(), str(item.get("owner") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result[:20]


def confirmed_ip_match(items: list[dict[str, Any]]) -> bool:
    for item in items:
        if item.get("confirmed"):
            return True
        if float(item.get("confidence", 0) or 0) >= 94 and str(item.get("type") or "") in {"brand", "trademark", "character", "celebrity", "copyright"}:
            return True
    return False


def right_type(category: str) -> str:
    lowered = str(category or "").lower()
    for key, value in RIGHT_TYPE_MAP.items():
        if key in lowered:
            return value
    return "other"


def first_value(fields: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = str(fields.get(key) or "").strip()
        if value:
            return value
    return ""


def first_nonempty(values: list[Any]) -> str:
    for value in values:
        clean = str(value or "").strip()
        if clean:
            return clean
    return ""
