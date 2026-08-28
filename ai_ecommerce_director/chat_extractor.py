from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .intake import intake_text
from .llm import LLMClient
from .parser import RECORD_TYPES, canonical_record_type, normalize_fields
from .scoring import score_record
from .storage import append_record
from .types import IntakeRecord


DEFAULT_CONFIDENCE_THRESHOLD = 0.7


@dataclass(slots=True)
class ExtractSummary:
    identified_record_type: str | None
    persisted: int
    flagged: int
    confidence: float
    message: str
    records: list[IntakeRecord]

    def to_dict(self) -> dict[str, Any]:
        return {
            "identified_record_type": self.identified_record_type,
            "persisted": self.persisted,
            "flagged": self.flagged,
            "confidence": self.confidence,
            "message": self.message,
            "records": [record.to_dict() for record in self.records],
        }


class ExtractionError(RuntimeError):
    pass


SYSTEM_PROMPT = """You extract ecommerce operating records for AI Ecommerce Director.
Return JSON only. Do not add markdown.

Supported record_type values:
- money_case
- influencer_cooperation
- hot_link
- supply_chain
- culture_label
- holiday_opportunity
- tk_rule_update

Return this schema:
{
  "records": [
    {
      "record_type": "money_case",
      "confidence": 0.0-1.0,
      "fields": {
        "product_name": "...",
        "selling_price": 29.99,
        "landed_cost": 4,
        "roi": 3.2
      }
    }
  ]
}

Use canonical English field names. Preserve unknown details in lessons or summary.
"""


def extract_chat_text(
    root: Path,
    text: str,
    llm_client: LLMClient | None = None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    fallback_rules: bool = False,
) -> ExtractSummary:
    clean_text = text.strip()
    if not clean_text:
        raise ExtractionError("No chat text provided.")

    client = llm_client or LLMClient(root=root, task="extraction")
    if not client.enabled:
        if fallback_rules:
            record, _ = intake_text(root, clean_text, "auto", "chat_extract")
            return ExtractSummary(
                identified_record_type=record.record_type,
                persisted=1,
                flagged=0,
                confidence=record.confidence,
                message="LLM is not configured; used rule-based fallback extraction.",
                records=[record],
            )
        raise ExtractionError(
            "LLM brain is not configured. Set AI_DIRECTOR_LLM_BASE_URL and AI_DIRECTOR_LLM_MODEL, "
            "or rerun extract with --fallback-rules."
        )

    try:
        raw_response = client.chat(SYSTEM_PROMPT, clean_text)
    except Exception as exc:  # noqa: BLE001 - return the configured brain error to the operator.
        raise ExtractionError(f"LLM brain error: {exc}") from exc

    payload = parse_llm_json(raw_response)
    extracted = payload.get("records")
    if not isinstance(extracted, list) or not extracted:
        return ExtractSummary(None, 0, 0, 0.0, "No supported record type was identified.", [])

    records: list[IntakeRecord] = []
    flagged = 0
    for item in extracted:
        if not isinstance(item, dict):
            continue
        record_type = canonical_record_type(str(item.get("record_type", "")))
        if record_type not in RECORD_TYPES:
            continue
        fields = normalize_fields(item.get("fields", {}) if isinstance(item.get("fields"), dict) else {})
        confidence = float(item.get("confidence", 0.0) or 0.0)
        review_status = "pending" if confidence < confidence_threshold else "approved"
        if review_status == "pending":
            score, notes = {}, ["低置信度聊天抽取已进入人工复核队列，暂不进入评分。"]
            flagged += 1
        else:
            score, notes = score_record(record_type, fields)
        record = IntakeRecord(
            record_type=record_type,
            fields=fields,
            raw_text=clean_text,
            source="chat_extract",
            score=score,
            director_notes=notes,
            review_status=review_status,
            confidence=confidence,
            metadata={"extractor": "llm"},
        )
        append_record(root, record)
        records.append(record)

    if not records:
        return ExtractSummary(None, 0, 0, 0.0, "No supported record type was identified.", [])

    avg_confidence = sum(record.confidence for record in records) / len(records)
    return ExtractSummary(
        identified_record_type=records[0].record_type if len({record.record_type for record in records}) == 1 else "multiple",
        persisted=len(records),
        flagged=flagged,
        confidence=round(avg_confidence, 3),
        message="Chat extraction completed.",
        records=records,
    )


def parse_llm_json(raw_response: str) -> dict[str, Any]:
    text = raw_response.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"LLM response was not valid JSON: {raw_response[:500]}") from exc
    if not isinstance(payload, dict):
        raise ExtractionError("LLM response JSON must be an object.")
    return payload
