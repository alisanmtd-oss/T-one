from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence


class IndependentCommerceReliabilityError(ValueError):
    """Fail-closed error raised by the local independent-commerce reliability layer."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _required(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise IndependentCommerceReliabilityError(
            f"missing_{field}", f"{field} is required"
        )
    return result


def _utc(value: datetime | str, field: str) -> datetime:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise IndependentCommerceReliabilityError(
            f"invalid_{field}", f"{field} must be ISO-8601"
        ) from exc
    if parsed.tzinfo is None:
        raise IndependentCommerceReliabilityError(
            f"invalid_{field}", f"{field} must include a timezone"
        )
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _money(value: Any, field: str) -> str:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise IndependentCommerceReliabilityError(
            f"invalid_{field}", f"{field} must be a decimal amount"
        ) from exc
    if amount < 0:
        raise IndependentCommerceReliabilityError(
            f"invalid_{field}", f"{field} cannot be negative"
        )
    return format(amount, ".2f")


def independent_webhook_signature(
    secret: str, *, timestamp: str, raw_body: bytes
) -> str:
    """Return the generic local contract signature; a missing secret always fails."""

    key = _required(secret, "webhook_secret").encode("utf-8")
    signed = _required(timestamp, "event_timestamp").encode("utf-8") + b"." + raw_body
    return hmac.new(key, signed, hashlib.sha256).hexdigest()


class IndependentCommerceReliabilityLedger:
    """Durable local webhook and order-finality evidence with no connector writes."""

    EVENT_TYPES = {
        "payment.succeeded",
        "refund.succeeded",
        "dispute.opened",
        "dispute.won",
        "dispute.lost",
    }

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
                CREATE TABLE IF NOT EXISTS commerce_webhook_events (
                    platform TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    store_binding_id TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    transaction_id TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    contract_sha256 TEXT NOT NULL,
                    raw_payload TEXT NOT NULL,
                    signature_verified INTEGER NOT NULL,
                    PRIMARY KEY (platform, event_id)
                );
                CREATE INDEX IF NOT EXISTS commerce_event_order_idx
                ON commerce_webhook_events
                    (platform, store_binding_id, order_id, occurred_at, event_id);

                CREATE TABLE IF NOT EXISTS local_order_finality (
                    platform TEXT NOT NULL,
                    store_binding_id TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    transaction_id TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    provider_state TEXT NOT NULL,
                    local_state TEXT NOT NULL,
                    readback_payment_state TEXT NOT NULL DEFAULT '',
                    readback_evidence_ref TEXT NOT NULL DEFAULT '',
                    finalized_at TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (platform, store_binding_id, order_id),
                    UNIQUE (platform, store_binding_id, transaction_id)
                );
                """
            )

    def ingest_financial_webhook(
        self,
        *,
        platform: str,
        event_id: str,
        event_type: str,
        occurred_at: datetime | str,
        received_at: datetime | str,
        store_binding_id: str,
        order_id: str,
        transaction_id: str,
        currency: str,
        amount: Any,
        raw_body: bytes,
        supplied_signature: str,
        secret: str,
        tolerance_seconds: int = 300,
    ) -> dict[str, Any]:
        """Verify, deduplicate and record a provider event without changing a store."""

        if tolerance_seconds <= 0:
            raise IndependentCommerceReliabilityError(
                "invalid_time_window", "tolerance_seconds must be positive"
            )
        record = {
            "platform": _required(platform, "platform").lower(),
            "event_id": _required(event_id, "event_id"),
            "event_type": _required(event_type, "event_type").lower(),
            "store_binding_id": _required(store_binding_id, "store_binding_id"),
            "order_id": _required(order_id, "order_id"),
            "transaction_id": _required(transaction_id, "transaction_id"),
            "currency": _required(currency, "currency").upper(),
            "amount": _money(amount, "amount"),
        }
        if record["event_type"] not in self.EVENT_TYPES:
            raise IndependentCommerceReliabilityError(
                "unsupported_event_type", "event_type is not admitted by this contract"
            )
        event_time = _utc(occurred_at, "occurred_at")
        received_time = _utc(received_at, "received_at")
        if abs((received_time - event_time).total_seconds()) > tolerance_seconds:
            raise IndependentCommerceReliabilityError(
                "event_outside_time_window",
                "webhook event is outside the accepted time window",
            )
        timestamp = _iso(event_time)
        expected = independent_webhook_signature(
            secret, timestamp=timestamp, raw_body=raw_body
        )
        supplied = str(supplied_signature or "").strip().lower()
        if not supplied or not hmac.compare_digest(expected, supplied):
            raise IndependentCommerceReliabilityError(
                "invalid_webhook_signature", "webhook HMAC verification failed"
            )
        try:
            raw_body.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise IndependentCommerceReliabilityError(
                "invalid_webhook_encoding", "webhook payload must be UTF-8"
            ) from exc
        payload_hash = hashlib.sha256(raw_body).hexdigest().upper()
        contract_hash = hashlib.sha256(
            json.dumps(
                {**record, "occurred_at": timestamp, "payload_sha256": payload_hash},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest().upper()

        idempotent_replay = False
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT contract_sha256 FROM commerce_webhook_events
                WHERE platform = ? AND event_id = ?
                """,
                (record["platform"], record["event_id"]),
            ).fetchone()
            if existing is not None:
                if existing["contract_sha256"] != contract_hash:
                    raise IndependentCommerceReliabilityError(
                        "event_id_contract_conflict",
                        "event_id was reused with different event facts or payload",
                    )
                idempotent_replay = True
            else:
                connection.execute(
                    """
                    INSERT INTO commerce_webhook_events
                    (platform, event_id, event_type, occurred_at, received_at,
                     store_binding_id, order_id, transaction_id, currency, amount,
                     payload_sha256, contract_sha256, raw_payload, signature_verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        record["platform"],
                        record["event_id"],
                        record["event_type"],
                        timestamp,
                        _iso(received_time),
                        record["store_binding_id"],
                        record["order_id"],
                        record["transaction_id"],
                        record["currency"],
                        record["amount"],
                        payload_hash,
                        contract_hash,
                        f"[redacted:sha256={payload_hash}]",
                    ),
                )
                if record["event_type"] == "payment.succeeded":
                    self._stage_provider_payment(connection, record)

        state = self.order_state(
            platform=record["platform"],
            store_binding_id=record["store_binding_id"],
            order_id=record["order_id"],
        )
        return {
            "accepted": True,
            "signature_verified": True,
            "idempotent_replay": idempotent_replay,
            "event_id": record["event_id"],
            "payload_sha256": payload_hash,
            "order_state": state,
            "external_action_executed": False,
        }

    def _stage_provider_payment(
        self, connection: sqlite3.Connection, record: Mapping[str, str]
    ) -> None:
        existing = connection.execute(
            """
            SELECT * FROM local_order_finality
            WHERE platform = ? AND store_binding_id = ? AND order_id = ?
            """,
            (record["platform"], record["store_binding_id"], record["order_id"]),
        ).fetchone()
        if existing is not None:
            for field in ("transaction_id", "currency", "amount"):
                if existing[field] != record[field]:
                    raise IndependentCommerceReliabilityError(
                        f"provider_payment_{field}_conflict",
                        f"provider payment conflicts with the existing {field}",
                    )
            return
        try:
            connection.execute(
                """
                INSERT INTO local_order_finality
                (platform, store_binding_id, order_id, transaction_id, currency,
                 amount, provider_state, local_state)
                VALUES (?, ?, ?, ?, ?, ?,
                        'provider_reported_success',
                        'pending_local_order_readback')
                """,
                (
                    record["platform"],
                    record["store_binding_id"],
                    record["order_id"],
                    record["transaction_id"],
                    record["currency"],
                    record["amount"],
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise IndependentCommerceReliabilityError(
                "provider_payment_identity_conflict",
                "transaction_id is already bound to another local order",
            ) from exc

    def reconcile_local_order(
        self,
        *,
        platform: str,
        store_binding_id: str,
        order_id: str,
        transaction_id: str,
        currency: str,
        amount: Any,
        local_order_exists: bool,
        local_payment_state: str,
        readback_evidence_ref: str,
        finalized_at: datetime | str,
    ) -> dict[str, Any]:
        """Confirm local finality only after an exact, evidence-backed order readback."""

        identity = {
            "platform": _required(platform, "platform").lower(),
            "store_binding_id": _required(store_binding_id, "store_binding_id"),
            "order_id": _required(order_id, "order_id"),
            "transaction_id": _required(transaction_id, "transaction_id"),
            "currency": _required(currency, "currency").upper(),
            "amount": _money(amount, "amount"),
        }
        if local_order_exists is not True:
            raise IndependentCommerceReliabilityError(
                "local_order_not_found", "provider success is not local order finality"
            )
        payment_state = _required(local_payment_state, "local_payment_state").lower()
        if payment_state != "paid":
            raise IndependentCommerceReliabilityError(
                "local_payment_not_final",
                "local order readback must explicitly report the paid state",
            )
        evidence_ref = _required(readback_evidence_ref, "readback_evidence_ref")
        at = _iso(_utc(finalized_at, "finalized_at"))
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM local_order_finality
                WHERE platform = ? AND store_binding_id = ? AND order_id = ?
                """,
                (
                    identity["platform"],
                    identity["store_binding_id"],
                    identity["order_id"],
                ),
            ).fetchone()
            if row is None:
                raise IndependentCommerceReliabilityError(
                    "provider_payment_not_found",
                    "signed provider payment evidence is missing",
                )
            existing = dict(row)
            for field in ("transaction_id", "currency", "amount"):
                if existing[field] != identity[field]:
                    raise IndependentCommerceReliabilityError(
                        f"local_order_{field}_mismatch",
                        f"local readback does not match provider {field}",
                    )
            if existing["local_state"] == "locally_finalized":
                return {
                    **existing,
                    "payment_confirmed": True,
                    "idempotent_replay": True,
                    "external_action_executed": False,
                }
            updated = connection.execute(
                """
                UPDATE local_order_finality
                SET local_state = 'locally_finalized',
                    readback_payment_state = ?, readback_evidence_ref = ?,
                    finalized_at = ?
                WHERE platform = ? AND store_binding_id = ? AND order_id = ?
                  AND local_state = 'pending_local_order_readback'
                """,
                (
                    payment_state,
                    evidence_ref,
                    at,
                    identity["platform"],
                    identity["store_binding_id"],
                    identity["order_id"],
                ),
            )
            if updated.rowcount != 1:
                raise IndependentCommerceReliabilityError(
                    "local_order_concurrent_reconciliation",
                    "local order finality changed concurrently",
                )
        return {
            **existing,
            "local_state": "locally_finalized",
            "readback_payment_state": payment_state,
            "readback_evidence_ref": evidence_ref,
            "finalized_at": at,
            "payment_confirmed": True,
            "idempotent_replay": False,
            "external_action_executed": False,
        }

    def order_state(
        self, *, platform: str, store_binding_id: str, order_id: str
    ) -> dict[str, Any]:
        key = (
            _required(platform, "platform").lower(),
            _required(store_binding_id, "store_binding_id"),
            _required(order_id, "order_id"),
        )
        with closing(self._connect()) as connection, connection:
            events = connection.execute(
                """
                SELECT event_id, event_type, occurred_at, transaction_id,
                       currency, amount, signature_verified
                FROM commerce_webhook_events
                WHERE platform = ? AND store_binding_id = ? AND order_id = ?
                ORDER BY occurred_at ASC, event_id ASC
                """,
                key,
            ).fetchall()
            finality = connection.execute(
                """
                SELECT * FROM local_order_finality
                WHERE platform = ? AND store_binding_id = ? AND order_id = ?
                """,
                key,
            ).fetchone()

        event_rows = [dict(row) for row in events]
        payment_seen = any(row["event_type"] == "payment.succeeded" for row in event_rows)
        refund_seen = any(row["event_type"] == "refund.succeeded" for row in event_rows)
        dispute_events = [
            row for row in event_rows if row["event_type"].startswith("dispute.")
        ]
        if not payment_seen:
            payment_state = "unresolved_missing_payment" if event_rows else "no_payment_evidence"
        elif finality is not None and finality["local_state"] == "locally_finalized":
            payment_state = "locally_finalized"
        else:
            payment_state = "provider_reported_success_pending_local_finality"

        refund_state = "none"
        if refund_seen:
            refund_state = "refunded" if payment_seen else "unresolved_missing_payment"

        dispute_state = "none"
        if dispute_events:
            if not payment_seen:
                dispute_state = "unresolved_missing_payment"
            else:
                dispute_state = {
                    "dispute.opened": "open",
                    "dispute.won": "won",
                    "dispute.lost": "lost",
                }[dispute_events[-1]["event_type"]]

        if refund_state == "refunded":
            overall = "refunded"
        elif dispute_state != "none":
            overall = f"dispute_{dispute_state}"
        else:
            overall = payment_state
        return {
            "platform": key[0],
            "store_binding_id": key[1],
            "order_id": key[2],
            "overall_state": overall,
            "payment_state": payment_state,
            "refund_state": refund_state,
            "dispute_state": dispute_state,
            "events_in_occurrence_order": event_rows,
            "external_action_executed": False,
        }


def evaluate_pim_batch(
    operations: Sequence[Mapping[str, Any]],
    responses: Sequence[Mapping[str, Any]],
    readbacks: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Evaluate explicit set/clear operations and per-item readback without a write."""

    normalized: list[dict[str, Any]] = []
    seen_operation_ids: set[str] = set()
    for operation in operations:
        operation_id = _required(operation.get("operation_id"), "operation_id")
        if operation_id in seen_operation_ids:
            raise IndependentCommerceReliabilityError(
                "duplicate_pim_operation_id", "PIM operation_id must be unique"
            )
        seen_operation_ids.add(operation_id)
        entity_id = _required(operation.get("entity_id"), "entity_id")
        field = _required(operation.get("field"), "field")
        action = _required(operation.get("action"), "action").lower()
        if action not in {"set", "clear"}:
            raise IndependentCommerceReliabilityError(
                "invalid_pim_action", "PIM action must be explicit set or clear"
            )
        if action == "set" and ("value" not in operation or operation.get("value") is None):
            raise IndependentCommerceReliabilityError(
                "missing_pim_set_value", "set requires a non-null value"
            )
        if action == "clear" and "value" in operation:
            raise IndependentCommerceReliabilityError(
                "ambiguous_pim_clear",
                "clear must use action=clear without an empty-string or null value",
            )
        normalized.append(
            {
                "operation_id": operation_id,
                "entity_id": entity_id,
                "field": field,
                "action": action,
                **({"value": operation.get("value")} if action == "set" else {}),
            }
        )

    response_map: dict[str, Mapping[str, Any]] = {}
    for response in responses:
        operation_id = _required(response.get("operation_id"), "response_operation_id")
        if operation_id in response_map:
            raise IndependentCommerceReliabilityError(
                "duplicate_pim_response", "PIM response operation_id must be unique"
            )
        response_map[operation_id] = response

    results: list[dict[str, Any]] = []
    for operation in normalized:
        response = response_map.get(operation["operation_id"])
        if response is None:
            results.append({**operation, "verified": False, "reason": "missing_response"})
            continue
        status = str(response.get("status") or "").strip().lower()
        if status not in {"success", "succeeded"}:
            results.append(
                {
                    **operation,
                    "verified": False,
                    "reason": "response_failed",
                    "response_status": status or "missing",
                }
            )
            continue
        entity_readback = readbacks.get(operation["entity_id"])
        if entity_readback is None:
            results.append({**operation, "verified": False, "reason": "missing_readback"})
            continue
        if operation["action"] == "set":
            matches = (
                operation["field"] in entity_readback
                and entity_readback[operation["field"]] == operation["value"]
            )
        else:
            matches = (
                operation["field"] not in entity_readback
                or entity_readback[operation["field"]] is None
            )
        results.append(
            {
                **operation,
                "verified": matches,
                "reason": "readback_verified" if matches else "readback_mismatch",
            }
        )

    verified_count = sum(1 for item in results if item["verified"])
    if verified_count == len(results):
        status = "succeeded"
    elif verified_count == 0:
        status = "failed"
    else:
        status = "partial_failure"
    return {
        "status": status,
        "all_verified": status == "succeeded",
        "requested_count": len(normalized),
        "verified_count": verified_count,
        "failed_count": len(normalized) - verified_count,
        "results": results,
        "external_action_executed": False,
    }
