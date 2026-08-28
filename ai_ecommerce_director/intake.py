from __future__ import annotations

from pathlib import Path

from .parser import RECORD_TYPES, canonical_record_type, detect_record_type, parse_key_values
from .scoring import score_record
from .storage import append_record
from .types import IntakeRecord


def intake_text(root: Path, text: str, record_type: str = "auto", source: str = "manual") -> tuple[IntakeRecord, Path]:
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("No intake text provided.")
    resolved_type = detect_record_type(clean_text) if record_type == "auto" else canonical_record_type(record_type)
    if resolved_type not in RECORD_TYPES:
        raise ValueError(f"Unsupported record type: {resolved_type}")

    fields = parse_key_values(clean_text)
    score, notes = score_record(resolved_type, fields)
    record = IntakeRecord(
        record_type=resolved_type,
        fields=fields,
        raw_text=clean_text,
        source=source,
        score=score,
        director_notes=notes,
    )
    path = append_record(root, record)
    return record, path
