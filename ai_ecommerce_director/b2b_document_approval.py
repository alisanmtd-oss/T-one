from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


B2B_APPROVAL_ACTIONS = frozenset(
    {
        "quotation_send",
        "pi_or_contract_send",
        "contract_commitment",
        "payment_request",
        "payment_confirmation",
        "outbound_message_send",
    }
)

APPROVAL_REQUIRED_FIELDS = (
    "approval_id",
    "pipeline_id",
    "action_type",
    "document_type",
    "document_version",
    "document_sha256",
    "binding_sha256",
    "approver_id",
    "approver_role",
    "approver_authority",
    "approved_at",
    "expires_at",
    "status",
)


class ApprovalGateError(ValueError):
    """A stable, machine-readable refusal from the B2B approval gate."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _required(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ApprovalGateError(f"missing_{field}", f"{field} is required")
    return text


def _aware_utc(value: datetime | str, *, field: str) -> datetime:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ApprovalGateError(f"invalid_{field}", f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ApprovalGateError(f"invalid_{field}", f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def canonical_document_bytes(document: bytes | str | Mapping[str, Any] | list[Any]) -> bytes:
    """Return the exact bytes bound by an approval.

    Files should be passed as bytes. Structured drafts use deterministic JSON so
    equivalent key order does not create a different document accidentally.
    """

    if isinstance(document, bytes):
        return document
    if isinstance(document, str):
        return document.encode("utf-8")
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def document_sha256(document: bytes | str | Mapping[str, Any] | list[Any]) -> str:
    return hashlib.sha256(canonical_document_bytes(document)).hexdigest().upper()


def _binding_sha256(binding: Mapping[str, str]) -> str:
    payload = json.dumps(dict(binding), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


class B2BDocumentApprovalLedger:
    """Local immutable approval ledger; it does not send or confirm anything externally."""

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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS b2b_document_approvals (
                    approval_id TEXT PRIMARY KEY,
                    pipeline_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    document_version TEXT NOT NULL,
                    document_sha256 TEXT NOT NULL,
                    binding_sha256 TEXT NOT NULL,
                    approver_id TEXT NOT NULL,
                    approver_role TEXT NOT NULL,
                    approver_authority TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('approved_unused', 'consumed', 'revoked')),
                    consumed_at TEXT NOT NULL DEFAULT '',
                    consumed_by_execution_id TEXT NOT NULL DEFAULT '',
                    revoked_at TEXT NOT NULL DEFAULT '',
                    revoked_by TEXT NOT NULL DEFAULT '',
                    revocation_reason TEXT NOT NULL DEFAULT ''
                )
                """
            )

    def register_approval(
        self,
        *,
        pipeline_id: str,
        action_type: str,
        document_type: str,
        document_version: str,
        document: bytes | str | Mapping[str, Any] | list[Any],
        approver_id: str,
        approver_role: str,
        approver_authority: str,
        approved_at: datetime | str,
        expires_at: datetime | str,
        approval_id: str | None = None,
    ) -> dict[str, Any]:
        action = _required(action_type, field="action_type")
        if action not in B2B_APPROVAL_ACTIONS:
            raise ApprovalGateError("unsupported_action_type", "action_type is not an approved B2B document action")
        approved = _aware_utc(approved_at, field="approved_at")
        expires = _aware_utc(expires_at, field="expires_at")
        if expires <= approved:
            raise ApprovalGateError("invalid_expiry", "expires_at must be later than approved_at")

        binding = {
            "pipeline_id": _required(pipeline_id, field="pipeline_id"),
            "action_type": action,
            "document_type": _required(document_type, field="document_type"),
            "document_version": _required(document_version, field="document_version"),
            "document_sha256": document_sha256(document),
            "approver_id": _required(approver_id, field="approver_id"),
            "approver_role": _required(approver_role, field="approver_role"),
            "approver_authority": _required(approver_authority, field="approver_authority"),
            "approved_at": _iso(approved),
            "expires_at": _iso(expires),
        }
        record = {
            "approval_id": str(approval_id or uuid.uuid4()),
            **binding,
            "binding_sha256": _binding_sha256(binding),
            "status": "approved_unused",
            "consumed_at": "",
            "consumed_by_execution_id": "",
            "revoked_at": "",
            "revoked_by": "",
            "revocation_reason": "",
            "external_action_executed": False,
        }
        try:
            with closing(self._connect()) as connection, connection:
                columns = [field for field in record if field != "external_action_executed"]
                connection.execute(
                    f"INSERT INTO b2b_document_approvals ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                    [record[field] for field in columns],
                )
        except sqlite3.IntegrityError as exc:
            raise ApprovalGateError("approval_id_already_exists", "approval_id must identify one immutable approval") from exc
        return record

    def get(self, approval_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT * FROM b2b_document_approvals WHERE approval_id = ?",
                (_required(approval_id, field="approval_id"),),
            ).fetchone()
        if row is None:
            return None
        return {**dict(row), "external_action_executed": False}

    def authorize_and_consume(
        self,
        *,
        approval_id: str,
        pipeline_id: str,
        action_type: str,
        document_type: str,
        document_version: str,
        document: bytes | str | Mapping[str, Any] | list[Any],
        execution_id: str,
        now: datetime | str,
    ) -> dict[str, Any]:
        """Atomically consume one exact approval and return a gate receipt.

        A successful receipt authorizes only the bound action. It deliberately
        does not execute an email, contract commitment, or payment action.
        """

        current = _aware_utc(now, field="now")
        expected = {
            "pipeline_id": _required(pipeline_id, field="pipeline_id"),
            "action_type": _required(action_type, field="action_type"),
            "document_type": _required(document_type, field="document_type"),
            "document_version": _required(document_version, field="document_version"),
            "document_sha256": document_sha256(document),
        }
        execution = _required(execution_id, field="execution_id")

        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM b2b_document_approvals WHERE approval_id = ?",
                (_required(approval_id, field="approval_id"),),
            ).fetchone()
            if row is None:
                raise ApprovalGateError("approval_not_found", "approval does not exist")
            record = dict(row)
            if record["status"] == "revoked":
                raise ApprovalGateError("approval_revoked", "approval was revoked")
            if record["status"] == "consumed":
                raise ApprovalGateError("approval_already_consumed", "approval is single-use and was already consumed")
            if current >= _aware_utc(record["expires_at"], field="expires_at"):
                raise ApprovalGateError("approval_expired", "approval has expired")
            for field, value in expected.items():
                if record[field] != value:
                    raise ApprovalGateError(f"approval_{field}_mismatch", f"approval is not bound to this {field}")
            if not all(str(record[field]).strip() for field in ("approver_id", "approver_role", "approver_authority")):
                raise ApprovalGateError("approval_authority_incomplete", "approver identity, role and authority are required")

            consumed_at = _iso(current)
            updated = connection.execute(
                """
                UPDATE b2b_document_approvals
                SET status = 'consumed', consumed_at = ?, consumed_by_execution_id = ?
                WHERE approval_id = ? AND status = 'approved_unused'
                """,
                (consumed_at, execution, approval_id),
            )
            if updated.rowcount != 1:
                raise ApprovalGateError("approval_concurrent_consumption", "approval was consumed concurrently")

        return {
            "allowed": True,
            "approval_id": approval_id,
            "pipeline_id": expected["pipeline_id"],
            "action_type": expected["action_type"],
            "document_type": expected["document_type"],
            "document_version": expected["document_version"],
            "document_sha256": expected["document_sha256"],
            "consumed_at": consumed_at,
            "consumed_by_execution_id": execution,
            "external_action_executed": False,
        }

    def revoke_approval(
        self,
        *,
        approval_id: str,
        revoked_by: str,
        reason: str,
        now: datetime | str,
    ) -> dict[str, Any]:
        revoked_at = _iso(_aware_utc(now, field="now"))
        actor = _required(revoked_by, field="revoked_by")
        explanation = _required(reason, field="reason")
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute(
                """
                UPDATE b2b_document_approvals
                SET status = 'revoked', revoked_at = ?, revoked_by = ?, revocation_reason = ?
                WHERE approval_id = ? AND status = 'approved_unused'
                """,
                (revoked_at, actor, explanation, _required(approval_id, field="approval_id")),
            )
            if updated.rowcount != 1:
                existing = connection.execute(
                    "SELECT status FROM b2b_document_approvals WHERE approval_id = ?",
                    (approval_id,),
                ).fetchone()
                code = "approval_not_found" if existing is None else f"approval_cannot_revoke_{existing['status']}"
                raise ApprovalGateError(code, "only an unused approval can be revoked")
        return {
            "approval_id": approval_id,
            "status": "revoked",
            "revoked_at": revoked_at,
            "revoked_by": actor,
            "revocation_reason": explanation,
            "external_action_executed": False,
        }
