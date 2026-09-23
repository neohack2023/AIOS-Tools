from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aios_tools.experimental.daily_debrief_adapter import (
    DailyDebriefAdapterError,
    adapt_structured_debrief,
)
from aios_tools.experimental.daily_debrief_event_store import (
    AppendResult,
    DailyDebriefEventStore,
)
from aios_tools.experimental.daily_debrief_projection import (
    DailyDebriefProjectionState,
    ProjectionError,
    project_event,
    projection_from_dict,
)
from aios_tools.experimental.daily_debrief_quarantine import (
    DailyDebriefQuarantineStore,
    QuarantineAppendResult,
    quarantine_rejection,
)


class RecoveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class IngestResult:
    status: str
    appended: tuple[AppendResult, ...] = ()
    quarantined: QuarantineAppendResult | None = None


def ingest_structured_debrief(
    payload: dict[str, Any],
    *,
    event_store: DailyDebriefEventStore,
    quarantine_store: DailyDebriefQuarantineStore,
) -> IngestResult:
    try:
        events = adapt_structured_debrief(payload)
    except DailyDebriefAdapterError as exc:
        quarantined = quarantine_rejection(
            quarantine_store,
            payload,
            exc,
        )
        return IngestResult(
            status="QUARANTINED",
            quarantined=quarantined,
        )

    results: list[AppendResult] = []
    for event in events:
        result = event_store.append(
            event,
            expected_sequence=event_store.last_sequence(),
        )
        results.append(result)

    if all(result.status == "DUPLICATE_NOOP" for result in results):
        status = "DUPLICATE_NOOP"
    else:
        status = "ACCEPTED"

    return IngestResult(
        status=status,
        appended=tuple(results),
    )


def recover_projection(
    event_store: DailyDebriefEventStore,
    *,
    checkpoint: dict[str, Any] | None = None,
) -> DailyDebriefProjectionState:
    if checkpoint is None:
        state = DailyDebriefProjectionState()
    else:
        state = projection_from_dict(checkpoint)

    durable_last = event_store.last_sequence()
    if state.last_applied_sequence > durable_last:
        raise RecoveryError(
            "projection_ahead_of_event_store:"
            f"projection={state.last_applied_sequence}:"
            f"store={durable_last}"
        )

    for stored in event_store.iter_events(
        after_sequence=state.last_applied_sequence
    ):
        project_event(state, stored)

    return state
