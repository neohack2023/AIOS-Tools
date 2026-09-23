from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from aios_tools.canonical import canonical_sha256


RECEIPT_SCHEMA = "memory-stage-diagnostic/v1"


class DiagnosticError(RuntimeError):
    pass


class StageStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class PrimaryFailureStage(str, Enum):
    INGESTION = "INGESTION"
    RETRIEVAL = "RETRIEVAL"
    UTILIZATION = "UTILIZATION"
    MULTI_STAGE = "MULTI_STAGE"
    NONE = "NONE"


class DiagnosticState(str, Enum):
    ATTRIBUTED = "ATTRIBUTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NO_FAILURE = "NO_FAILURE"


@dataclass(frozen=True)
class MemoryStageProbe:
    probe_id: str
    source_truth_ref: str
    ingestion: StageStatus
    retrieval: StageStatus
    utilization: StageStatus
    interaction_proven: bool = False
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemoryStageReceipt:
    schema: str
    receipt_id: str
    probe_id: str
    diagnostic_state: DiagnosticState
    primary_failure_stage: PrimaryFailureStage
    reason: str
    probe_digest: str
    evidence_refs: tuple[str, ...]


def _validate(probe: MemoryStageProbe) -> None:
    if not probe.probe_id.strip():
        raise DiagnosticError("probe_id_required")
    if not probe.source_truth_ref.strip():
        raise DiagnosticError("source_truth_ref_required")
    if not probe.evidence_refs:
        raise DiagnosticError("evidence_refs_required")
    if any(not ref.strip() for ref in probe.evidence_refs):
        raise DiagnosticError("blank_evidence_ref")


def diagnose_memory_stage(probe: MemoryStageProbe) -> MemoryStageReceipt:
    _validate(probe)

    statuses = {
        PrimaryFailureStage.INGESTION: probe.ingestion,
        PrimaryFailureStage.RETRIEVAL: probe.retrieval,
        PrimaryFailureStage.UTILIZATION: probe.utilization,
    }

    if StageStatus.UNKNOWN in statuses.values():
        state = DiagnosticState.INSUFFICIENT_EVIDENCE
        stage = PrimaryFailureStage.NONE
        reason = "unknown_stage_evidence"
    else:
        failed = [
            stage_key
            for stage_key, status in statuses.items()
            if status == StageStatus.FAIL
        ]

        if (
            probe.ingestion == StageStatus.FAIL
            and probe.retrieval == StageStatus.BLOCKED
            and probe.utilization == StageStatus.NOT_APPLICABLE
        ):
            state = DiagnosticState.ATTRIBUTED
            stage = PrimaryFailureStage.INGESTION
            reason = "retrieval_blocked_by_ingestion_failure"
        elif not failed:
            state = DiagnosticState.NO_FAILURE
            stage = PrimaryFailureStage.NONE
            reason = "no_failed_stage"
        elif len(failed) == 1:
            state = DiagnosticState.ATTRIBUTED
            stage = failed[0]
            reason = f"{stage.value.lower()}_failure"
        elif probe.interaction_proven:
            state = DiagnosticState.ATTRIBUTED
            stage = PrimaryFailureStage.MULTI_STAGE
            reason = "multi_stage_interaction_proven"
        else:
            state = DiagnosticState.INSUFFICIENT_EVIDENCE
            stage = PrimaryFailureStage.NONE
            reason = "multiple_failures_without_interaction_proof"

    payload = {
        **asdict(probe),
        "ingestion": probe.ingestion.value,
        "retrieval": probe.retrieval.value,
        "utilization": probe.utilization.value,
        "evidence_refs": list(probe.evidence_refs),
    }
    probe_digest = canonical_sha256(payload)
    unsigned = {
        "schema": RECEIPT_SCHEMA,
        "probe_id": probe.probe_id,
        "diagnostic_state": state.value,
        "primary_failure_stage": stage.value,
        "reason": reason,
        "probe_digest": probe_digest,
        "evidence_refs": list(probe.evidence_refs),
    }
    receipt_id = "msd_" + canonical_sha256(unsigned)

    return MemoryStageReceipt(
        schema=RECEIPT_SCHEMA,
        receipt_id=receipt_id,
        probe_id=probe.probe_id,
        diagnostic_state=state,
        primary_failure_stage=stage,
        reason=reason,
        probe_digest=probe_digest,
        evidence_refs=probe.evidence_refs,
    )
