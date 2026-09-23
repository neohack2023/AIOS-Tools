from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol

from aios_tools.canonical import canonical_json_bytes, canonical_sha256


QUARANTINE_SCHEMA = "daily-debrief-quarantine-receipt/v1"
QUARANTINE_STORE_SCHEMA = "daily-debrief-quarantine-store/v1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REJECTION_ID_RE = re.compile(r"^ddq_[0-9a-f]{64}$")
_MAX_METADATA_LENGTH = 512

KNOWN_REJECTION_CODES = {
    "UNKNOWN_SCHEMA",
    "SCOPE_UNRESOLVED",
    "SOURCE_IDENTITY_MISSING",
    "SOURCE_REVISION_MISSING",
    "EVENT_DIGEST_MISMATCH",
    "OUT_OF_ORDER_SEQUENCE",
    "UNSUPPORTED_AUTHORITY_CLAIM",
    "VALIDATION_FAILED",
}

_ERROR_PREFIX_TO_CODE = {
    "unknown_schema": "UNKNOWN_SCHEMA",
    "unknown_event_schema": "UNKNOWN_SCHEMA",
    "scope_unresolved": "SCOPE_UNRESOLVED",
    "source_identity_missing": "SOURCE_IDENTITY_MISSING",
    "source_revision_missing": "SOURCE_REVISION_MISSING",
    "event_digest_mismatch": "EVENT_DIGEST_MISMATCH",
    "projection_sequence_mismatch": "OUT_OF_ORDER_SEQUENCE",
    "unsupported_authority_claim": "UNSUPPORTED_AUTHORITY_CLAIM",
}


class QuarantineError(RuntimeError):
    pass


class QuarantineCorruption(QuarantineError):
    pass


@dataclass(frozen=True)
class QuarantineAppendResult:
    status: str
    rejection_id: str
    sequence: int


@dataclass(frozen=True)
class StoredRejection:
    sequence: int
    receipt: dict[str, Any]


class DailyDebriefQuarantineStore(Protocol):
    def append(self, receipt: dict[str, Any]) -> QuarantineAppendResult:
        ...

    def contains(self, rejection_id: str) -> bool:
        ...

    def iter_rejections(
        self,
        *,
        after_sequence: int = 0,
    ) -> Iterable[StoredRejection]:
        ...


def classify_rejection(error: BaseException | str) -> str:
    message = str(error)
    prefix = message.split(":", 1)[0]
    return _ERROR_PREFIX_TO_CODE.get(prefix, "VALIDATION_FAILED")


def _safe_string(mapping: Any, key: str) -> str | None:
    if not isinstance(mapping, dict):
        return None
    value = mapping.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _safe_payload_digest(payload: Any) -> str | None:
    try:
        return canonical_sha256(payload)
    except (TypeError, ValueError):
        return None


def build_rejection_receipt(
    payload: Any,
    error: BaseException | str,
) -> dict[str, Any]:
    code = classify_rejection(error)
    event_id_observed = _safe_string(payload, "event_id")
    schema_observed = (
        _safe_string(payload, "schema")
        or _safe_string(payload, "schema_version")
    )

    receipt = {
        "schema": QUARANTINE_SCHEMA,
        "rejection_code": code,
        "source_provider": _safe_string(payload, "source_provider"),
        "source_id": _safe_string(payload, "source_id"),
        "source_revision": _safe_string(payload, "source_revision"),
        "scope_key": _safe_string(payload, "scope_key"),
        "schema_observed": schema_observed,
        "event_id_observed": event_id_observed,
        "payload_digest": _safe_payload_digest(payload),
    }
    receipt["rejection_id"] = "ddq_" + canonical_sha256(receipt)
    return receipt


def _validate_optional_metadata(value: Any, code: str) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise QuarantineError(code)
    if len(value) > _MAX_METADATA_LENGTH:
        raise QuarantineError(code)


def validate_rejection_receipt(receipt: dict[str, Any]) -> None:
    if not isinstance(receipt, dict):
        raise QuarantineError("quarantine_receipt_not_object")

    allowed = {
        "schema",
        "rejection_id",
        "rejection_code",
        "source_provider",
        "source_id",
        "source_revision",
        "scope_key",
        "schema_observed",
        "event_id_observed",
        "payload_digest",
    }
    if set(receipt) - allowed:
        raise QuarantineError("quarantine_receipt_contains_source_content")

    if receipt.get("schema") != QUARANTINE_SCHEMA:
        raise QuarantineError("unsupported_quarantine_schema")
    if receipt.get("rejection_code") not in KNOWN_REJECTION_CODES:
        raise QuarantineError("unsupported_rejection_code")

    rejection_id = receipt.get("rejection_id")
    if not isinstance(rejection_id, str) or not _REJECTION_ID_RE.fullmatch(
        rejection_id
    ):
        raise QuarantineError("rejection_id_invalid")

    for key in (
        "source_provider",
        "source_id",
        "source_revision",
        "scope_key",
        "schema_observed",
        "event_id_observed",
    ):
        _validate_optional_metadata(
            receipt.get(key),
            f"{key}_invalid",
        )

    payload_digest = receipt.get("payload_digest")
    if payload_digest is not None:
        if (
            not isinstance(payload_digest, str)
            or not _SHA256_RE.fullmatch(payload_digest)
        ):
            raise QuarantineError("payload_digest_invalid")

    unsigned = {
        key: value
        for key, value in receipt.items()
        if key != "rejection_id"
    }
    expected = "ddq_" + canonical_sha256(unsigned)
    if rejection_id != expected:
        raise QuarantineError("rejection_digest_mismatch")


class SqliteDailyDebriefQuarantineStore:
    def __init__(self, database: str | Path):
        self.database = str(database)
        self._conn = sqlite3.connect(
            self.database,
            isolation_level=None,
            timeout=5.0,
        )
        self._conn.row_factory = sqlite3.Row
        self._initialize()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SqliteDailyDebriefQuarantineStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _initialize(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_debrief_quarantine (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                rejection_id TEXT NOT NULL UNIQUE,
                receipt_json TEXT NOT NULL,
                store_schema TEXT NOT NULL
            )
            """
        )

    def append(self, receipt: dict[str, Any]) -> QuarantineAppendResult:
        validate_rejection_receipt(receipt)
        rejection_id = receipt["rejection_id"]
        receipt_json = canonical_json_bytes(receipt).decode("utf-8")

        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._conn.execute(
                """
                SELECT sequence, receipt_json, store_schema
                FROM daily_debrief_quarantine
                WHERE rejection_id = ?
                """,
                (rejection_id,),
            ).fetchone()

            if row is not None:
                if row["store_schema"] != QUARANTINE_STORE_SCHEMA:
                    raise QuarantineCorruption(
                        "unsupported_quarantine_store_schema"
                    )
                if row["receipt_json"] != receipt_json:
                    raise QuarantineCorruption(
                        "rejection_id_payload_mismatch"
                    )
                sequence = int(row["sequence"])
                self._conn.execute("COMMIT")
                return QuarantineAppendResult(
                    status="DUPLICATE_NOOP",
                    rejection_id=rejection_id,
                    sequence=sequence,
                )

            cursor = self._conn.execute(
                """
                INSERT INTO daily_debrief_quarantine (
                    rejection_id,
                    receipt_json,
                    store_schema
                ) VALUES (?, ?, ?)
                """,
                (
                    rejection_id,
                    receipt_json,
                    QUARANTINE_STORE_SCHEMA,
                ),
            )
            sequence = int(cursor.lastrowid)
            self._conn.execute("COMMIT")
            return QuarantineAppendResult(
                status="QUARANTINED",
                rejection_id=rejection_id,
                sequence=sequence,
            )
        except Exception:
            if self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
            raise

    def contains(self, rejection_id: str) -> bool:
        if not isinstance(rejection_id, str) or not rejection_id:
            raise ValueError("rejection_id_required")
        row = self._conn.execute(
            """
            SELECT 1
            FROM daily_debrief_quarantine
            WHERE rejection_id = ?
            """,
            (rejection_id,),
        ).fetchone()
        return row is not None

    def iter_rejections(
        self,
        *,
        after_sequence: int = 0,
    ) -> Iterable[StoredRejection]:
        if after_sequence < 0:
            raise ValueError("after_sequence_must_be_nonnegative")

        rows = self._conn.execute(
            """
            SELECT sequence, rejection_id, receipt_json, store_schema
            FROM daily_debrief_quarantine
            WHERE sequence > ?
            ORDER BY sequence ASC
            """,
            (after_sequence,),
        ).fetchall()

        results: list[StoredRejection] = []
        for row in rows:
            if row["store_schema"] != QUARANTINE_STORE_SCHEMA:
                raise QuarantineCorruption(
                    "unsupported_quarantine_store_schema"
                )
            try:
                receipt = json.loads(row["receipt_json"])
            except json.JSONDecodeError as exc:
                raise QuarantineCorruption(
                    "quarantine_receipt_json_invalid"
                ) from exc
            try:
                validate_rejection_receipt(receipt)
            except QuarantineError as exc:
                raise QuarantineCorruption(
                    "quarantine_receipt_invalid"
                ) from exc
            if receipt["rejection_id"] != row["rejection_id"]:
                raise QuarantineCorruption(
                    "quarantine_rejection_id_mismatch"
                )
            results.append(
                StoredRejection(
                    sequence=int(row["sequence"]),
                    receipt=receipt,
                )
            )
        return tuple(results)


def quarantine_rejection(
    store: DailyDebriefQuarantineStore,
    payload: Any,
    error: BaseException | str,
) -> QuarantineAppendResult:
    return store.append(build_rejection_receipt(payload, error))
