from __future__ import annotations

import re
from typing import Any

from aios_tools.canonical import canonical_sha256


INPUT_SCHEMA = "daily-debrief-structured/v1"
EVENT_SCHEMA = "daily-debrief-finding-event/v1"
EVENT_TYPE = "daily_debrief.finding"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")

FORBIDDEN_AUTHORITY_KEYS = {
    "authority",
    "authority_transfer",
    "canon",
    "canonical",
    "trusted_memory",
    "active_capability",
    "runtime_activation",
    "repository_mutation",
    "merge_authorized",
    "deployment_authorized",
}


class DailyDebriefAdapterError(ValueError):
    pass


def _require_nonempty_string(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DailyDebriefAdapterError(code)
    return value.strip()


def _require_identifier(value: Any, code: str) -> str:
    value = _require_nonempty_string(value, code)
    if not _ID_RE.fullmatch(value):
        raise DailyDebriefAdapterError(code)
    return value


def _require_sha256(value: Any, code: str) -> str:
    value = _require_nonempty_string(value, code).lower()
    if not _SHA256_RE.fullmatch(value):
        raise DailyDebriefAdapterError(code)
    return value


def _require_identifier_list(value: Any, code: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise DailyDebriefAdapterError(code)
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        item_id = _require_identifier(item, code)
        if item_id in seen:
            raise DailyDebriefAdapterError(code)
        seen.add(item_id)
        normalized.append(item_id)
    return tuple(sorted(normalized))


def _reject_authority_claims(mapping: dict[str, Any]) -> None:
    bad = sorted(FORBIDDEN_AUTHORITY_KEYS.intersection(mapping))
    if bad:
        raise DailyDebriefAdapterError(
            "unsupported_authority_claim:" + ",".join(bad)
        )


def validate_structured_debrief(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise DailyDebriefAdapterError("payload_not_object")
    if payload.get("schema") != INPUT_SCHEMA:
        raise DailyDebriefAdapterError("unknown_schema")

    _reject_authority_claims(payload)
    _require_nonempty_string(payload.get("source_provider"), "source_provider_missing")
    _require_nonempty_string(payload.get("source_id"), "source_identity_missing")
    _require_nonempty_string(payload.get("source_revision"), "source_revision_missing")
    _require_sha256(payload.get("source_digest"), "source_digest_invalid")
    _require_nonempty_string(payload.get("debrief_date"), "debrief_date_missing")
    _require_identifier(payload.get("scope_key"), "scope_unresolved")

    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise DailyDebriefAdapterError("findings_not_list")

    seen_finding_ids: set[str] = set()
    for finding in findings:
        if not isinstance(finding, dict):
            raise DailyDebriefAdapterError("finding_not_object")
        _reject_authority_claims(finding)

        finding_id = _require_identifier(
            finding.get("finding_id"), "finding_id_invalid"
        )
        if finding_id in seen_finding_ids:
            raise DailyDebriefAdapterError("duplicate_finding_id")
        seen_finding_ids.add(finding_id)

        _require_identifier(finding.get("lineage"), "lineage_invalid")
        _require_nonempty_string(finding.get("title"), "title_missing")
        _require_nonempty_string(finding.get("disposition"), "disposition_missing")
        _require_nonempty_string(finding.get("confidence"), "confidence_missing")
        _require_nonempty_string(
            finding.get("implementation_consequence"),
            "implementation_consequence_missing",
        )
        _require_nonempty_string(
            finding.get("validation_state"), "validation_state_missing"
        )
        _require_identifier_list(
            finding.get("remaining_test_ids"), "remaining_test_ids_invalid"
        )
        _require_identifier_list(
            finding.get("resolved_test_ids"), "resolved_test_ids_invalid"
        )


def _event_payload(
    payload: dict[str, Any],
    finding: dict[str, Any],
) -> dict[str, Any]:
    remaining_test_ids = _require_identifier_list(
        finding.get("remaining_test_ids"), "remaining_test_ids_invalid"
    )
    resolved_test_ids = _require_identifier_list(
        finding.get("resolved_test_ids"), "resolved_test_ids_invalid"
    )

    overlap = sorted(set(remaining_test_ids).intersection(resolved_test_ids))
    if overlap:
        raise DailyDebriefAdapterError(
            "test_id_conflict:" + ",".join(overlap)
        )

    return {
        "schema_version": EVENT_SCHEMA,
        "event_type": EVENT_TYPE,
        "source_provider": payload["source_provider"].strip(),
        "source_id": payload["source_id"].strip(),
        "source_revision": payload["source_revision"].strip(),
        "source_digest": payload["source_digest"].strip().lower(),
        "debrief_date": payload["debrief_date"].strip(),
        "scope_key": payload["scope_key"].strip(),
        "finding_id": finding["finding_id"].strip(),
        "lineage": finding["lineage"].strip(),
        "title": finding["title"].strip(),
        "disposition": finding["disposition"].strip(),
        "confidence": finding["confidence"].strip(),
        "implementation_consequence": finding[
            "implementation_consequence"
        ].strip(),
        "validation_state": finding["validation_state"].strip(),
        "remaining_test_ids": list(remaining_test_ids),
        "resolved_test_ids": list(resolved_test_ids),
    }


def adapt_structured_debrief(payload: dict[str, Any]) -> list[dict[str, Any]]:
    validate_structured_debrief(payload)

    events: list[dict[str, Any]] = []
    for finding in payload["findings"]:
        event = _event_payload(payload, finding)
        event["event_id"] = "ddf_" + canonical_sha256(event)
        events.append(event)
    return events


def validate_finding_event(event: dict[str, Any]) -> None:
    if not isinstance(event, dict):
        raise DailyDebriefAdapterError("event_not_object")
    if event.get("schema_version") != EVENT_SCHEMA:
        raise DailyDebriefAdapterError("unknown_event_schema")
    if event.get("event_type") != EVENT_TYPE:
        raise DailyDebriefAdapterError("unknown_event_type")

    _reject_authority_claims(event)

    for key, code in (
        ("source_provider", "source_provider_missing"),
        ("source_id", "source_identity_missing"),
        ("source_revision", "source_revision_missing"),
        ("debrief_date", "debrief_date_missing"),
        ("title", "title_missing"),
        ("disposition", "disposition_missing"),
        ("confidence", "confidence_missing"),
        ("implementation_consequence", "implementation_consequence_missing"),
        ("validation_state", "validation_state_missing"),
    ):
        _require_nonempty_string(event.get(key), code)

    _require_sha256(event.get("source_digest"), "source_digest_invalid")
    _require_identifier(event.get("scope_key"), "scope_unresolved")
    _require_identifier(event.get("finding_id"), "finding_id_invalid")
    _require_identifier(event.get("lineage"), "lineage_invalid")

    remaining = _require_identifier_list(
        event.get("remaining_test_ids"), "remaining_test_ids_invalid"
    )
    resolved = _require_identifier_list(
        event.get("resolved_test_ids"), "resolved_test_ids_invalid"
    )
    if set(remaining).intersection(resolved):
        raise DailyDebriefAdapterError("test_id_conflict")

    supplied_event_id = _require_nonempty_string(
        event.get("event_id"), "event_id_missing"
    )
    unsigned = {key: value for key, value in event.items() if key != "event_id"}
    expected_event_id = "ddf_" + canonical_sha256(unsigned)
    if supplied_event_id != expected_event_id:
        raise DailyDebriefAdapterError("event_digest_mismatch")
