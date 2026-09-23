import pytest

from aios_tools.experimental.skill_install_lifecycle import (
    SkillDecision,
    SkillLifecycleObservation,
    SkillOperation,
    evaluate_skill_lifecycle,
)


def obs(operation, **kwargs):
    values = dict(
        skill_name="sample-skill",
        source_id="catalog/aws/sample-skill",
        source_revision="v1",
        candidate_digest="digest-v1",
        target_agent="codex",
        operation=operation,
    )
    values.update(kwargs)
    return SkillLifecycleObservation(**values)


def test_discover_does_not_install_or_trust():
    receipt = evaluate_skill_lifecycle(obs(SkillOperation.DISCOVER))
    assert receipt.decision == SkillDecision.DISCOVER_ONLY
    assert receipt.trusted_state_granted is False


def test_install_pinned_candidate():
    receipt = evaluate_skill_lifecycle(obs(SkillOperation.INSTALL))
    assert receipt.decision == SkillDecision.INSTALL


def test_same_source_two_targets_preserves_target_specific_receipts():
    a = evaluate_skill_lifecycle(
        obs(SkillOperation.INSTALL, target_agent="codex")
    )
    b = evaluate_skill_lifecycle(
        obs(SkillOperation.INSTALL, target_agent="cursor")
    )
    assert a.decision == b.decision == SkillDecision.INSTALL
    assert a.receipt_id != b.receipt_id


def test_changed_update_invalidates_prior_verification():
    receipt = evaluate_skill_lifecycle(
        obs(
            SkillOperation.UPDATE,
            installed_source_id="catalog/aws/sample-skill",
            installed_revision="v1",
            installed_digest="digest-v1",
            source_revision="v2",
            candidate_digest="digest-v2",
        )
    )
    assert receipt.decision == SkillDecision.UPDATE
    assert receipt.verification_invalidated is True


def test_identical_update_is_noop():
    receipt = evaluate_skill_lifecycle(
        obs(
            SkillOperation.UPDATE,
            installed_source_id="catalog/aws/sample-skill",
            installed_digest="digest-v1",
        )
    )
    assert receipt.decision == SkillDecision.NOOP
    assert receipt.verification_invalidated is False


def test_remove_preserves_historical_provenance():
    receipt = evaluate_skill_lifecycle(
        obs(
            SkillOperation.REMOVE,
            installed_source_id="catalog/aws/sample-skill",
            installed_digest="digest-v1",
        )
    )
    assert receipt.decision == SkillDecision.REMOVE
    assert receipt.historical_provenance_preserved is True


def test_source_drift_blocks_silent_replacement():
    receipt = evaluate_skill_lifecycle(
        obs(
            SkillOperation.UPDATE,
            installed_source_id="other/source",
            installed_digest="digest-v1",
            candidate_digest="digest-v2",
        )
    )
    assert receipt.decision == SkillDecision.BLOCK_DRIFT


def test_unresolved_version_stays_unverified():
    receipt = evaluate_skill_lifecycle(
        obs(
            SkillOperation.INSTALL,
            version_resolved=False,
            source_revision=None,
            candidate_digest=None,
        )
    )
    assert receipt.decision == SkillDecision.UNVERIFIED


def test_incomplete_candidate_identity_stays_unverified():
    receipt = evaluate_skill_lifecycle(
        obs(
            SkillOperation.INSTALL,
            source_revision=None,
            candidate_digest=None,
        )
    )
    assert receipt.decision == SkillDecision.UNVERIFIED


def test_receipt_is_deterministic():
    candidate = obs(SkillOperation.INSTALL)
    assert evaluate_skill_lifecycle(candidate) == evaluate_skill_lifecycle(candidate)
