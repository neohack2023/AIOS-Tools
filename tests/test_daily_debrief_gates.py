from datetime import datetime, timedelta, timezone

from aios_tools.experimental.daily_debrief_gates import (
    GateVerdict,
    digest_text,
    evaluate_ci_mcp_authority,
    evaluate_model_lifecycle,
    evaluate_staged_artifact_authority,
    resolve_instruction_source,
)


def test_claude_precedence_over_agents():
    decision = resolve_instruction_source(files=["AGENTS.md", "CLAUDE.md"], provider_supported=True)
    assert decision.verdict == GateVerdict.ALLOW
    assert decision.reason == "CLAUDE.md"


def test_unsupported_provider_visible():
    decision = resolve_instruction_source(files=["AGENTS.md"], provider_supported=False)
    assert decision.verdict == GateVerdict.UNRESOLVED
    assert decision.reason == "provider_unsupported"


def test_instruction_digest_drift_is_stale():
    decision = resolve_instruction_source(
        files=["AGENTS.md"],
        provider_supported=True,
        expected_digest=digest_text("old"),
        observed_content="new",
    )
    assert decision.verdict == GateVerdict.STALE


def test_instruction_digest_requires_observation():
    decision = resolve_instruction_source(
        files=["AGENTS.md"],
        provider_supported=True,
        expected_digest=digest_text("expected"),
        observed_content=None,
    )
    assert decision.verdict == GateVerdict.UNRESOLVED
    assert decision.reason == "instruction_digest_unverified"


def test_pre_deprecation_is_current():
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    decision = evaluate_model_lifecycle(
        requested_model="retiring",
        resolved_model="retiring",
        deprecation_at=now + timedelta(days=1),
        observed_at=now,
    )
    assert decision.verdict == GateVerdict.ALLOW


def test_post_deprecation_is_stale():
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    decision = evaluate_model_lifecycle(
        requested_model="retiring",
        resolved_model="retiring",
        deprecation_at=now - timedelta(days=1),
        observed_at=now,
    )
    assert decision.verdict == GateVerdict.STALE


def test_silent_substitution_denied():
    decision = evaluate_model_lifecycle(
        requested_model="a",
        resolved_model="b",
        deprecation_at=None,
        substitution_approved=False,
    )
    assert decision.verdict == GateVerdict.DENY


def test_stage_publish_authority_split():
    assert evaluate_staged_artifact_authority(
        requested_action="stage", can_stage=True, can_publish=False
    ).verdict == GateVerdict.ALLOW
    assert evaluate_staged_artifact_authority(
        requested_action="publish", can_stage=True, can_publish=False
    ).verdict == GateVerdict.DENY


def test_artifact_digest_drift_is_stale():
    decision = evaluate_staged_artifact_authority(
        requested_action="publish",
        can_stage=True,
        can_publish=True,
        expected_digest="a",
        observed_digest="b",
    )
    assert decision.verdict == GateVerdict.STALE


def test_artifact_digest_requires_observation():
    decision = evaluate_staged_artifact_authority(
        requested_action="publish",
        can_stage=True,
        can_publish=True,
        expected_digest="a",
        observed_digest=None,
    )
    assert decision.verdict == GateVerdict.UNRESOLVED
    assert decision.reason == "artifact_digest_unverified"


def test_read_only_principal_cannot_manage():
    decision = evaluate_ci_mcp_authority(
        capability_class="manage",
        principal_class="read_only",
        mutation_expected=True,
        effect_receipt_present=True,
        verified_schema_revision="1",
        observed_schema_revision="1",
    )
    assert decision.verdict == GateVerdict.DENY


def test_mutation_requires_effect_receipt():
    decision = evaluate_ci_mcp_authority(
        capability_class="manage",
        principal_class="scoped_write",
        mutation_expected=True,
        effect_receipt_present=False,
        verified_schema_revision="1",
        observed_schema_revision="1",
    )
    assert decision.verdict == GateVerdict.DENY


def test_schema_revision_drift_is_stale():
    decision = evaluate_ci_mcp_authority(
        capability_class="investigate",
        principal_class="read_only",
        mutation_expected=False,
        effect_receipt_present=False,
        verified_schema_revision="1",
        observed_schema_revision="2",
    )
    assert decision.verdict == GateVerdict.STALE


def test_unknown_principal_fails_closed():
    decision = evaluate_ci_mcp_authority(
        capability_class="manage",
        principal_class="mystery",
        mutation_expected=False,
        effect_receipt_present=False,
        verified_schema_revision="1",
        observed_schema_revision="1",
    )
    assert decision.verdict == GateVerdict.UNRESOLVED
    assert decision.reason == "unknown_principal_class"


def test_blank_schema_revision_fails_closed():
    decision = evaluate_ci_mcp_authority(
        capability_class="investigate",
        principal_class="read_only",
        mutation_expected=False,
        effect_receipt_present=False,
        verified_schema_revision="",
        observed_schema_revision="",
    )
    assert decision.verdict == GateVerdict.UNRESOLVED
    assert decision.reason == "schema_revision_unverified"
