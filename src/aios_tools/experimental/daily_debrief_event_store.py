from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

from aios_tools.canonical import canonical_json_bytes
from aios_tools.experimental.daily_debrief_adapter import validate_finding_event


STORE_SCHEMA = "daily-debrief-event-store/v1"


class EventStoreError(RuntimeError):
    pass


class EventStoreConcurrencyConflict(EventStoreError):
    pass


class EventStoreCorruption(EventStoreError):
    pass


@dataclass(frozen=True)
class AppendResult:
    status: str
    event_id: str
    sequence: int


@dataclass(frozen=True)
class StoredEvent:
    sequence: int
    event: dict


class DailyDebriefEventStore(Protocol):
    def append(
        self,
        event: dict,
        *,
        expected_sequence: int | None = None,
    ) -> AppendResult:
        ...

    def contains(self, event_id: str) -> bool:
        ...

    def iter_events(self, *, after_sequence: int = 0) -> Iterable[StoredEvent]:
        ...

    def last_sequence(self) -> int:
        ...


class SqliteDailyDebriefEventStore:
    def __init__(self, database: str | Path):
        self.database = str(database)
        self._conn = sqlite3.connect(
            self.database,
            isolation_level=None,
            timeout=5.0,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._initialize()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SqliteDailyDebriefEventStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _initialize(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_debrief_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_json TEXT NOT NULL,
                store_schema TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _validate_event(event: dict) -> None:
        validate_finding_event(event)

    @staticmethod
    def _canonical_text(event: dict) -> str:
        return canonical_json_bytes(event).decode("utf-8")

    def _decode_row(self, row: sqlite3.Row) -> StoredEvent:
        if row["store_schema"] != STORE_SCHEMA:
            raise EventStoreCorruption("unsupported_store_schema")
        try:
            event = json.loads(row["event_json"])
        except json.JSONDecodeError as exc:
            raise EventStoreCorruption("stored_event_json_invalid") from exc
        try:
            self._validate_event(event)
        except ValueError as exc:
            raise EventStoreCorruption("stored_event_invalid") from exc
        if event.get("event_id") != row["event_id"]:
            raise EventStoreCorruption("stored_event_id_mismatch")
        return StoredEvent(sequence=int(row["sequence"]), event=event)

    def append(
        self,
        event: dict,
        *,
        expected_sequence: int | None = None,
    ) -> AppendResult:
        self._validate_event(event)
        if expected_sequence is not None and expected_sequence < 0:
            raise ValueError("expected_sequence_must_be_nonnegative")

        event_id = event["event_id"]
        event_json = self._canonical_text(event)

        try:
            self._conn.execute("BEGIN IMMEDIATE")

            duplicate = self._conn.execute(
                """
                SELECT sequence, event_json, store_schema
                FROM daily_debrief_events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()

            if duplicate is not None:
                if duplicate["store_schema"] != STORE_SCHEMA:
                    raise EventStoreCorruption("unsupported_store_schema")
                if duplicate["event_json"] != event_json:
                    raise EventStoreCorruption("event_id_payload_mismatch")
                sequence = int(duplicate["sequence"])
                self._conn.execute("COMMIT")
                return AppendResult(
                    status="DUPLICATE_NOOP",
                    event_id=event_id,
                    sequence=sequence,
                )

            row = self._conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS last_sequence "
                "FROM daily_debrief_events"
            ).fetchone()
            current_sequence = int(row["last_sequence"])

            if (
                expected_sequence is not None
                and expected_sequence != current_sequence
            ):
                raise EventStoreConcurrencyConflict(
                    "expected_sequence_mismatch:"
                    f"expected={expected_sequence}:actual={current_sequence}"
                )

            cursor = self._conn.execute(
                """
                INSERT INTO daily_debrief_events (
                    event_id,
                    event_json,
                    store_schema
                ) VALUES (?, ?, ?)
                """,
                (event_id, event_json, STORE_SCHEMA),
            )
            sequence = int(cursor.lastrowid)
            self._conn.execute("COMMIT")
            return AppendResult(
                status="APPENDED",
                event_id=event_id,
                sequence=sequence,
            )
        except Exception:
            if self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
            raise

    def contains(self, event_id: str) -> bool:
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("event_id_required")
        row = self._conn.execute(
            "SELECT 1 FROM daily_debrief_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        return row is not None

    def iter_events(self, *, after_sequence: int = 0) -> Iterable[StoredEvent]:
        if after_sequence < 0:
            raise ValueError("after_sequence_must_be_nonnegative")
        rows = self._conn.execute(
            """
            SELECT sequence, event_id, event_json, store_schema
            FROM daily_debrief_events
            WHERE sequence > ?
            ORDER BY sequence ASC
            """,
            (after_sequence,),
        ).fetchall()
        return tuple(self._decode_row(row) for row in rows)

    def last_sequence(self) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) AS last_sequence "
            "FROM daily_debrief_events"
        ).fetchone()
        return int(row["last_sequence"])
