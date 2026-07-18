from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class IntakeRecord:
    record_type: str
    fields: dict[str, Any]
    raw_text: str
    source: str = "manual"
    score: dict[str, Any] = field(default_factory=dict)
    director_notes: list[str] = field(default_factory=list)
    review_status: str = "approved"
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    record_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "record_type": self.record_type,
            "created_at": self.created_at,
            "source": self.source,
            "raw_text": self.raw_text,
            "fields": self.fields,
            "score": self.score,
            "director_notes": self.director_notes,
            "review_status": self.review_status,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "IntakeRecord":
        return cls(
            record_id=payload["record_id"],
            record_type=payload["record_type"],
            created_at=payload["created_at"],
            source=payload.get("source", "manual"),
            raw_text=payload.get("raw_text", ""),
            fields=payload.get("fields", {}),
            score=payload.get("score", {}),
            director_notes=payload.get("director_notes", []),
            review_status=payload.get("review_status", "approved"),
            confidence=float(payload.get("confidence", 1.0) or 0.0),
            metadata=payload.get("metadata", {}),
        )
