from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Iterable


def digest_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DebriefFinding:
    source_id: str
    debrief_date: str
    lineage: str
    title: str
    disposition: str
    confidence: str
    implementation_consequence: str
    validation_state: str
    remaining_test: str | None = None
    resolved_tests: tuple[str, ...] = ()
    evidence_digest: str | None = None

    def stable_evidence_digest(self) -> str:
        if self.evidence_digest:
            return self.evidence_digest
        payload = "|".join(
            [
                self.source_id,
                self.debrief_date,
                self.lineage,
                self.title,
                self.disposition,
                self.confidence,
                self.implementation_consequence,
                self.validation_state,
                self.remaining_test or "",
                ",".join(sorted(self.resolved_tests)),
            ]
        )
        return digest_text(payload)


@dataclass
class LineageDigest:
    lineage: str
    first_seen: str
    last_seen: str
    evidence_digests: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    dispositions: list[str] = field(default_factory=list)
    implementation_consequences: list[str] = field(default_factory=list)
    remaining_tests: list[str] = field(default_factory=list)
    resolved_tests: list[str] = field(default_factory=list)
    simulation_pass_count: int = 0
    live_verified_count: int = 0

    @property
    def distinct_debriefs(self) -> int:
        return len({sid.split("::", 1)[0] for sid in self.source_ids})


@dataclass(frozen=True)
class ImplementationCandidate:
    lineage: str
    state: str
    evidence_count: int
    distinct_debriefs: int
    rationale: str
    implementation_consequences: tuple[str, ...]
    remaining_tests: tuple[str, ...]


@dataclass
class DailyDebriefDigestState:
    processed_evidence_digests: set[str] = field(default_factory=set)
    lineages: dict[str, LineageDigest] = field(default_factory=dict)


def _append_unique(values: list[str], value: str | None) -> None:
    if value and value not in values:
        values.append(value)


def ingest_findings(
    state: DailyDebriefDigestState,
    findings: Iterable[DebriefFinding],
) -> DailyDebriefDigestState:
    for finding in findings:
        digest = finding.stable_evidence_digest()
        if digest in state.processed_evidence_digests:
            continue

        state.processed_evidence_digests.add(digest)
        lineage = state.lineages.get(finding.lineage)
        source_event_id = f"{finding.debrief_date}::{finding.source_id}"

        if lineage is None:
            lineage = LineageDigest(
                lineage=finding.lineage,
                first_seen=finding.debrief_date,
                last_seen=finding.debrief_date,
            )
            state.lineages[finding.lineage] = lineage

        lineage.last_seen = max(lineage.last_seen, finding.debrief_date)
        _append_unique(lineage.evidence_digests, digest)
        _append_unique(lineage.source_ids, source_event_id)
        _append_unique(lineage.dispositions, finding.disposition)
        _append_unique(lineage.implementation_consequences, finding.implementation_consequence)
        _append_unique(lineage.remaining_tests, finding.remaining_test)

        for resolved_test in finding.resolved_tests:
            _append_unique(lineage.resolved_tests, resolved_test)
            if resolved_test in lineage.remaining_tests:
                lineage.remaining_tests.remove(resolved_test)

        validation = finding.validation_state.upper()
        if "LIVE" in validation and "PASS" in validation:
            lineage.live_verified_count += 1
        elif "PASS" in validation:
            lineage.simulation_pass_count += 1

    return state


def state_to_dict(state: DailyDebriefDigestState) -> dict:
    return {
        "schema": "daily-debrief-digest-state/v1",
        "processed_evidence_digests": sorted(state.processed_evidence_digests),
        "lineages": {
            key: asdict(value)
            for key, value in sorted(state.lineages.items())
        },
    }


def state_from_dict(payload: dict) -> DailyDebriefDigestState:
    if payload.get("schema") != "daily-debrief-digest-state/v1":
        raise ValueError("unsupported_digest_state_schema")
    state = DailyDebriefDigestState(
        processed_evidence_digests=set(payload.get("processed_evidence_digests", []))
    )
    for key, raw in payload.get("lineages", {}).items():
        state.lineages[key] = LineageDigest(**raw)
    return state


def implementation_candidates(
    state: DailyDebriefDigestState,
    *,
    min_distinct_debriefs: int = 2,
    min_evidence: int = 2,
) -> list[ImplementationCandidate]:
    candidates: list[ImplementationCandidate] = []

    for lineage in sorted(state.lineages.values(), key=lambda item: item.lineage):
        evidence_count = len(lineage.evidence_digests)
        if evidence_count < min_evidence or lineage.distinct_debriefs < min_distinct_debriefs:
            continue

        if lineage.live_verified_count > 0 and not lineage.remaining_tests:
            candidate_state = "READY_FOR_IMPLEMENTATION_PLAN"
            rationale = "Repeated debrief evidence plus live verification with no unresolved test gate."
        elif lineage.remaining_tests:
            candidate_state = "PLAN_CANDIDATE_VERIFICATION_REQUIRED"
            rationale = "Repeated debrief evidence is implementation-relevant, but exact live verification remains unresolved."
        else:
            candidate_state = "PLAN_CANDIDATE"
            rationale = "Repeated debrief evidence supports planning, but live verification evidence is not yet present."

        candidates.append(
            ImplementationCandidate(
                lineage=lineage.lineage,
                state=candidate_state,
                evidence_count=evidence_count,
                distinct_debriefs=lineage.distinct_debriefs,
                rationale=rationale,
                implementation_consequences=tuple(lineage.implementation_consequences),
                remaining_tests=tuple(lineage.remaining_tests),
            )
        )

    return candidates


def build_implementation_plan(
    state: DailyDebriefDigestState,
    *,
    min_distinct_debriefs: int = 2,
    min_evidence: int = 2,
) -> dict:
    candidates = implementation_candidates(
        state,
        min_distinct_debriefs=min_distinct_debriefs,
        min_evidence=min_evidence,
    )
    return {
        "schema": "daily-debrief-implementation-plan/v1",
        "candidate_count": len(candidates),
        "candidates": [
            {
                "lineage": candidate.lineage,
                "state": candidate.state,
                "evidence_count": candidate.evidence_count,
                "distinct_debriefs": candidate.distinct_debriefs,
                "rationale": candidate.rationale,
                "implementation_consequences": list(candidate.implementation_consequences),
                "remaining_tests": list(candidate.remaining_tests),
            }
            for candidate in candidates
        ],
        "authority": {
            "research_is_evidence_not_canon": True,
            "automatic_runtime_activation": False,
            "automatic_repository_mutation": False,
            "promotion_requires_governed_path": True,
        },
    }
