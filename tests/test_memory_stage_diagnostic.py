import pytest

from aios_tools.experimental.memory_stage_diagnostic import (
    DiagnosticError,
    DiagnosticState,
    MemoryStageProbe,
    PrimaryFailureStage,
    StageStatus,
    diagnose_memory_stage,
)


def probe(
    ingestion,
    retrieval,
    utilization,
    *,
    interaction_proven=False,
    evidence_refs=("evidence-1",),
):
    return MemoryStageProbe(
        probe_id="probe-1",
        source_truth_ref="truth-1",
        ingestion=ingestion,
        retrieval=retrieval,
        utilization=utilization,
        interaction_proven=interaction_proven,
        evidence_refs=evidence_refs,
    )


@pytest.mark.parametrize(
    ("candidate", "state", "stage"),
    [
        (
            probe(
                StageStatus.FAIL,
                StageStatus.BLOCKED,
                StageStatus.NOT_APPLICABLE,
            ),
            DiagnosticState.ATTRIBUTED,
            PrimaryFailureStage.INGESTION,
        ),
        (
            probe(
                StageStatus.PASS,
                StageStatus.FAIL,
                StageStatus.NOT_APPLICABLE,
            ),
            DiagnosticState.ATTRIBUTED,
            PrimaryFailureStage.RETRIEVAL,
        ),
        (
            probe(
                StageStatus.PASS,
                StageStatus.PASS,
                StageStatus.FAIL,
            ),
            DiagnosticState.ATTRIBUTED,
            PrimaryFailureStage.UTILIZATION,
        ),
        (
            probe(
                StageStatus.PASS,
                StageStatus.PASS,
                StageStatus.PASS,
            ),
            DiagnosticState.NO_FAILURE,
            PrimaryFailureStage.NONE,
        ),
        (
            probe(
                StageStatus.FAIL,
                StageStatus.FAIL,
                StageStatus.NOT_APPLICABLE,
                interaction_proven=True,
            ),
            DiagnosticState.ATTRIBUTED,
            PrimaryFailureStage.MULTI_STAGE,
        ),
        (
            probe(
                StageStatus.FAIL,
                StageStatus.FAIL,
                StageStatus.NOT_APPLICABLE,
            ),
            DiagnosticState.INSUFFICIENT_EVIDENCE,
            PrimaryFailureStage.NONE,
        ),
        (
            probe(
                StageStatus.UNKNOWN,
                StageStatus.FAIL,
                StageStatus.NOT_APPLICABLE,
            ),
            DiagnosticState.INSUFFICIENT_EVIDENCE,
            PrimaryFailureStage.NONE,
        ),
        (
            probe(
                StageStatus.PASS,
                StageStatus.PASS,
                StageStatus.UNKNOWN,
            ),
            DiagnosticState.INSUFFICIENT_EVIDENCE,
            PrimaryFailureStage.NONE,
        ),
    ],
)
def test_sealed_stage_attribution(candidate, state, stage):
    result = diagnose_memory_stage(candidate)
    assert result.diagnostic_state == state
    assert result.primary_failure_stage == stage


def test_evidence_is_required():
    with pytest.raises(DiagnosticError, match="evidence_refs_required"):
        diagnose_memory_stage(
            probe(
                StageStatus.PASS,
                StageStatus.FAIL,
                StageStatus.NOT_APPLICABLE,
                evidence_refs=(),
            )
        )


def test_receipt_is_deterministic():
    candidate = probe(
        StageStatus.PASS,
        StageStatus.FAIL,
        StageStatus.NOT_APPLICABLE,
    )
    assert diagnose_memory_stage(candidate) == diagnose_memory_stage(candidate)
