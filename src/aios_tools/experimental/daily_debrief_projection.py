from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable

from aios_tools.canonical import canonical_sha256
from aios_tools.experimental.daily_debrief_adapter import validate_finding_event
from aios_tools.experimental.daily_debrief_event_store import StoredEvent


PROJECTION_SCHEMA = "daily-debrief-digest-projection/v1"


class ProjectionError(RuntimeError):
    pass


class ProjectionSequenceError(ProjectionError):
    pass


@dataclass
class ProjectionLineage:
    lineage: str
    first_seen: str
    last_seen: str
    event_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    dispositions: list[str] = field(default_factory=list)
    implementation_consequences: list[str] = field(default_factory=list)
    remaining_test_ids: list[str] = field(default_factory=list)
    resolved_test_ids: list[str] = field(default_factory=list)
    simulation_pass_count: int = 0
    live_verified_count: int = 0


@dataclass
class DailyDebriefProjectionState:
    projection_revision: int = 1
    last_applied_sequence: int = 0
    processed_event_ids: list[str] = field(default_factory=list)
    lineages: dict[str, ProjectionLineage] = field(default_factory=dict)


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _project_event_payload(
    state: DailyDebriefProjectionState,
    stored: StoredEvent,
) -> None:
    event = stored.event
    lineage_key = event["lineage"]
    lineage = state.lineages.get(lineage_key)
    if lineage is None:
        lineage = ProjectionLineage(
            lineage=lineage_key,
            first_seen=event["debrief_date"],
            last_seen=event["debrief_date"],
        )
        state.lineages[lineage_key] = lineage

    lineage.last_seen = max(lineage.last_seen, event["debrief_date"])
    _append_unique(lineage.event_ids, event["event_id"])
    _append_unique(
        lineage.source_ids,
        f'{event["debrief_date"]}::{event["source_provider"]}::{event["source_id"]}::{event["source_revision"]}',
    )
    _append_unique(lineage.dispositions, event["disposition"])
    _append_unique(
        lineage.implementation_consequences,
        event["implementation_consequence"],
    )

    for test_id in event.get("remaining_test_ids", []):
        if test_id in lineage.resolved_test_ids:
            lineage.resolved_test_ids.remove(test_id)
        _append_unique(lineage.remaining_test_ids, test_id)

    for test_id in event.get("resolved_test_ids", []):
        if test_id in lineage.remaining_test_ids:
            lineage.remaining_test_ids.remove(test_id)
        _append_unique(lineage.resolved_test_ids, test_id)

    validation = event["validation_state"].upper()
    if "LIVE" in validation and "PASS" in validation:
        lineage.live_verified_count += 1
    elif "PASS" in validation:
        lineage.simulation_pass_count += 1


def project_event(
    state: DailyDebriefProjectionState,
    stored: StoredEvent,
) -> DailyDebriefProjectionState:
    validate_finding_event(stored.event)
    expected = state.last_applied_sequence + 1
    if stored.sequence != expected:
        raise ProjectionSequenceError(
            f"projection_sequence_mismatch:expected={expected}:actual={stored.sequence}"
        )
    if stored.event["event_id"] in state.processed_event_ids:
        raise ProjectionSequenceError("duplicate_event_in_projection")

    _project_event_payload(state, stored)
    state.processed_event_ids.append(stored.event["event_id"])
    state.last_applied_sequence = stored.sequence
    return state


def rebuild_projection(
    events: Iterable[StoredEvent],
) -> DailyDebriefProjectionState:
    state = DailyDebriefProjectionState()
    for stored in events:
        project_event(state, stored)
    return state


def projection_payload(state: DailyDebriefProjectionState) -> dict:
    return {
        "schema": PROJECTION_SCHEMA,
        "projection_revision": state.projection_revision,
        "last_applied_sequence": state.last_applied_sequence,
        "processed_event_ids": list(state.processed_event_ids),
        "lineages": {
            key: asdict(value)
            for key, value in sorted(state.lineages.items())
        },
    }


def projection_digest(state: DailyDebriefProjectionState) -> str:
    return canonical_sha256(projection_payload(state))


def projection_envelope(state: DailyDebriefProjectionState) -> dict:
    payload = projection_payload(state)
    payload["projection_digest"] = projection_digest(state)
    return payload


def projection_from_dict(payload: dict) -> DailyDebriefProjectionState:
    supplied = payload.get("projection_digest")
    if supplied is not None:
        unsigned = {
            key: value
            for key, value in payload.items()
            if key != "projection_digest"
        }
        if supplied != canonical_sha256(unsigned):
            raise ProjectionError("projection_digest_mismatch")

    if payload.get("schema") != PROJECTION_SCHEMA:
        raise ProjectionError("unsupported_projection_schema")

    revision = int(payload.get("projection_revision", 1))
    if revision != 1:
        raise ProjectionError("unsupported_projection_revision")
    last_sequence = int(payload.get("last_applied_sequence", 0))
    if last_sequence < 0:
        raise ProjectionError("projection_sequence_invalid")
    processed_event_ids = list(payload.get("processed_event_ids", []))
    if len(processed_event_ids) != len(set(processed_event_ids)):
        raise ProjectionError("projection_event_ids_duplicate")
    if len(processed_event_ids) != last_sequence:
        raise ProjectionError("projection_sequence_event_count_mismatch")

    state = DailyDebriefProjectionState(
        projection_revision=revision,
        last_applied_sequence=last_sequence,
        processed_event_ids=processed_event_ids,
    )
    for key, raw in payload.get("lineages", {}).items():
        lineage = ProjectionLineage(**raw)
        if lineage.lineage != key:
            raise ProjectionError("projection_lineage_key_mismatch")
        state.lineages[key] = lineage

    return state
