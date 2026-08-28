from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping


class PlatformEventError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _required(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise PlatformEventError(f"missing_{field}", f"{field} is required")
    return result


def _utc(value: datetime | str, field: str) -> datetime:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise PlatformEventError(f"invalid_{field}", f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise PlatformEventError(f"invalid_{field}", f"{field} must include timezone")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _money(value: Any, field: str) -> str:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise PlatformEventError(f"invalid_{field}", f"{field} must be a decimal amount") from exc
    if amount < 0:
        raise PlatformEventError(f"invalid_{field}", f"{field} cannot be negative")
    return format(amount, ".2f")


def webhook_signature(secret: str, *, timestamp: str, raw_body: bytes) -> str:
    key = _required(secret, "webhook_secret").encode("utf-8")
    signed = _required(timestamp, "event_timestamp").encode("utf-8") + b"." + raw_body
    return hmac.new(key, signed, hashlib.sha256).hexdigest()


def quotation_acceptance_state(event_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Separate a view/read receipt from explicit buyer acceptance evidence."""

    normalized = str(event_type or "").strip().lower()
    if normalized in {"quotation.viewed", "quotation.read", "quotation.get", "quotation.fetched"}:
        return {
            "state": "viewed_not_accepted",
            "accepted": False,
            "reason": "view_or_get_is_not_acceptance",
        }
    if normalized != "quotation.accepted":
        return {"state": "no_acceptance_evidence", "accepted": False, "reason": "explicit_acceptance_event_required"}
    required = {
        "acceptance_id": str(payload.get("acceptance_id") or "").strip(),
        "accepted_by": str(payload.get("accepted_by") or "").strip(),
        "accepted_at": str(payload.get("accepted_at") or "").strip(),
        "quotation_version": str(payload.get("quotation_version") or "").strip(),
    }
    missing = [field for field, value in required.items() if not value]
    if missing:
        return {
            "state": "acceptance_event_incomplete",
            "accepted": False,
            "reason": "missing_explicit_acceptance_fields",
            "missing_fields": missing,
        }
    _utc(required["accepted_at"], "accepted_at")
    return {"state": "accepted", "accepted": True, **required}


class B2BPlatformEventLedger:
    """Durable local webhook and payment evidence; never performs a platform write."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS webhook_events (
                    source TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_timestamp TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    raw_payload TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    signature_verified INTEGER NOT NULL,
                    PRIMARY KEY (source, event_id)
                );
                CREATE TABLE IF NOT EXISTS payment_reconciliation (
                    source TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    pipeline_id TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    transaction_id TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    provider_state TEXT NOT NULL,
                    local_state TEXT NOT NULL,
                    reconciled_at TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (source, event_id),
                    UNIQUE (source, transaction_id)
                );
                """
            )

    def ingest_webhook(
        self,
        *,
        source: str,
        event_id: str,
        event_type: str,
        event_timestamp: datetime | str,
        raw_body: bytes,
        supplied_signature: str,
        secret: str,
        received_at: datetime | str,
        tolerance_seconds: int = 300,
    ) -> dict[str, Any]:
        if tolerance_seconds <= 0:
            raise PlatformEventError("invalid_time_window", "tolerance_seconds must be positive")
        source_value = _required(source, "source")
        event_value = _required(event_id, "event_id")
        type_value = _required(event_type, "event_type")
        event_time = _utc(event_timestamp, "event_timestamp")
        received = _utc(received_at, "received_at")
        if abs((received - event_time).total_seconds()) > tolerance_seconds:
            raise PlatformEventError("event_outside_time_window", "webhook event is outside the accepted time window")
        timestamp_value = _iso(event_time)
        expected = webhook_signature(secret, timestamp=timestamp_value, raw_body=raw_body)
        supplied = str(supplied_signature or "").strip().lower()
        if not supplied or not hmac.compare_digest(expected, supplied):
            raise PlatformEventError("invalid_webhook_signature", "webhook HMAC verification failed")

        payload_hash = hashlib.sha256(raw_body).hexdigest().upper()
        raw_payload = raw_body.decode("utf-8", errors="strict")
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT payload_sha256 FROM webhook_events WHERE source = ? AND event_id = ?",
                (source_value, event_value),
            ).fetchone()
            if existing is not None:
                if existing["payload_sha256"] != payload_hash:
                    raise PlatformEventError("event_id_payload_conflict", "event_id was reused with different payload bytes")
                return {
                    "accepted": True,
                    "idempotent_replay": True,
                    "source": source_value,
                    "event_id": event_value,
                    "payload_sha256": payload_hash,
                    "external_action_executed": False,
                }
            connection.execute(
                """
                INSERT INTO webhook_events
                (source, event_id, event_type, event_timestamp, payload_sha256, raw_payload, received_at, signature_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (source_value, event_value, type_value, timestamp_value, payload_hash, raw_payload, _iso(received)),
            )
        return {
            "accepted": True,
            "idempotent_replay": False,
            "source": source_value,
            "event_id": event_value,
            "event_type": type_value,
            "payload_sha256": payload_hash,
            "signature_verified": True,
            "external_action_executed": False,
        }

    def stage_provider_payment(
        self,
        *,
        source: str,
        event_id: str,
        pipeline_id: str,
        order_id: str,
        transaction_id: str,
        currency: str,
        amount: Any,
    ) -> dict[str, Any]:
        record = {
            "source": _required(source, "source"),
            "event_id": _required(event_id, "event_id"),
            "pipeline_id": _required(pipeline_id, "pipeline_id"),
            "order_id": _required(order_id, "order_id"),
            "transaction_id": _required(transaction_id, "transaction_id"),
            "currency": _required(currency, "currency").upper(),
            "amount": _money(amount, "amount"),
            "provider_state": "provider_reported_paid",
            "local_state": "pending_local_reconciliation",
            "reconciled_at": "",
        }
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO payment_reconciliation
                    (source, event_id, pipeline_id, order_id, transaction_id, currency, amount, provider_state, local_state, reconciled_at)
                    VALUES (:source, :event_id, :pipeline_id, :order_id, :transaction_id, :currency, :amount, :provider_state, :local_state, :reconciled_at)
                    """,
                    record,
                )
        except sqlite3.IntegrityError as exc:
            raise PlatformEventError("duplicate_payment_identity", "event_id and transaction_id must be idempotent and unique") from exc
        return {**record, "payment_confirmed": False, "external_action_executed": False}

    def reconcile_payment(
        self,
        *,
        source: str,
        event_id: str,
        expected_pipeline_id: str,
        expected_order_id: str,
        expected_currency: str,
        expected_amount: Any,
        reconciled_at: datetime | str,
    ) -> dict[str, Any]:
        expected = {
            "pipeline_id": _required(expected_pipeline_id, "expected_pipeline_id"),
            "order_id": _required(expected_order_id, "expected_order_id"),
            "currency": _required(expected_currency, "expected_currency").upper(),
            "amount": _money(expected_amount, "expected_amount"),
        }
        at = _iso(_utc(reconciled_at, "reconciled_at"))
        source_value = _required(source, "source")
        event_value = _required(event_id, "event_id")
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM payment_reconciliation WHERE source = ? AND event_id = ?",
                (source_value, event_value),
            ).fetchone()
            if row is None:
                raise PlatformEventError("payment_event_not_found", "provider payment evidence is missing")
            record = dict(row)
            if record["local_state"] == "reconciled":
                return {**record, "payment_confirmed": True, "idempotent_replay": True, "external_action_executed": False}
            for field, value in expected.items():
                if record[field] != value:
                    raise PlatformEventError(f"payment_{field}_mismatch", f"provider payment does not match local {field}")
            updated = connection.execute(
                """
                UPDATE payment_reconciliation
                SET local_state = 'reconciled', reconciled_at = ?
                WHERE source = ? AND event_id = ? AND local_state = 'pending_local_reconciliation'
                """,
                (at, source_value, event_value),
            )
            if updated.rowcount != 1:
                raise PlatformEventError("payment_concurrent_reconciliation", "payment state changed concurrently")
        return {
            **record,
            "local_state": "reconciled",
            "reconciled_at": at,
            "payment_confirmed": True,
            "idempotent_replay": False,
            "external_action_executed": False,
        }

    def payment_state(self, *, source: str, event_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT * FROM payment_reconciliation WHERE source = ? AND event_id = ?",
                (_required(source, "source"), _required(event_id, "event_id")),
            ).fetchone()
        return None if row is None else {**dict(row), "external_action_executed": False}
