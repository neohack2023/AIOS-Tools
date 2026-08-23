from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import Any

from .evidence import BrowserEvidence


class SecretEvidenceKind(StrEnum):
    SCREENSHOT = "screenshot"
    TRACE_SNAPSHOT = "trace_snapshot"
    FORM_VALUE = "form_value"
    REQUEST_BODY = "request_body"
    SENSITIVE_HEADER = "sensitive_header"
    CONSOLE_EVENT = "console_event"
    PAGE_ERROR = "page_error"


@dataclass(slots=True)
class RedactionCounters:
    screenshots: int = 0
    trace_snapshots: int = 0
    form_values: int = 0
    request_bodies: int = 0
    sensitive_headers: int = 0
    console_events: int = 0
    page_errors: int = 0

    def increment(self, kind: SecretEvidenceKind) -> None:
        mapping = {
            SecretEvidenceKind.SCREENSHOT: "screenshots",
            SecretEvidenceKind.TRACE_SNAPSHOT: "trace_snapshots",
            SecretEvidenceKind.FORM_VALUE: "form_values",
            SecretEvidenceKind.REQUEST_BODY: "request_bodies",
            SecretEvidenceKind.SENSITIVE_HEADER: "sensitive_headers",
            SecretEvidenceKind.CONSOLE_EVENT: "console_events",
            SecretEvidenceKind.PAGE_ERROR: "page_errors",
        }
        attribute = mapping[kind]
        setattr(self, attribute, getattr(self, attribute) + 1)

    def to_dict(self) -> dict[str, int]:
        return {field.name: int(getattr(self, field.name)) for field in fields(self)}


class SecretEvidenceBlackout:
    """Suppress durable secret-bearing evidence during human authentication control."""

    def __init__(self) -> None:
        self._active = False
        self._counters = RedactionCounters()

    @property
    def active(self) -> bool:
        return self._active

    @property
    def allow_screenshot(self) -> bool:
        return not self._active

    @property
    def allow_trace_snapshot(self) -> bool:
        return not self._active

    def __enter__(self) -> "SecretEvidenceBlackout":
        if self._active:
            raise RuntimeError("secret evidence blackout cannot be nested")
        self._active = True
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self._active = False

    def suppress(self, kind: SecretEvidenceKind) -> None:
        if not self._active:
            raise RuntimeError("secret evidence suppression is only valid during an active blackout")
        self._counters.increment(kind)

    def capture_console(self, evidence: BrowserEvidence, *, kind: str, text: str) -> None:
        if self._active:
            self._counters.increment(SecretEvidenceKind.CONSOLE_EVENT)
            return
        evidence.console_event(kind, text)

    def capture_page_error(self, evidence: BrowserEvidence, *, text: str) -> None:
        if self._active:
            self._counters.increment(SecretEvidenceKind.PAGE_ERROR)
            return
        evidence.page_error(text)

    def note_screenshot_attempt(self) -> bool:
        if self._active:
            self._counters.increment(SecretEvidenceKind.SCREENSHOT)
            return False
        return True

    def note_trace_snapshot_attempt(self) -> bool:
        if self._active:
            self._counters.increment(SecretEvidenceKind.TRACE_SNAPSHOT)
            return False
        return True

    def redact_form_value(self, value: object) -> None:
        del value
        if self._active:
            self._counters.increment(SecretEvidenceKind.FORM_VALUE)
            return
        raise RuntimeError("form values must never enter durable browser evidence")

    def redact_request_body(self, body: object) -> None:
        del body
        if self._active:
            self._counters.increment(SecretEvidenceKind.REQUEST_BODY)
            return
        raise RuntimeError("request bodies are not admitted as takeover evidence")

    def redact_sensitive_headers(self, headers: object) -> None:
        del headers
        if self._active:
            self._counters.increment(SecretEvidenceKind.SENSITIVE_HEADER)
            return
        raise RuntimeError("sensitive headers are not admitted as takeover evidence")

    def public_receipt(self) -> dict[str, object]:
        return {
            "active": self._active,
            "redaction_counts": self._counters.to_dict(),
            "secret_values_recorded": False,
        }
