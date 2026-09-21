import json
from pathlib import Path

from jsonschema import Draft202012Validator

from aios_tools.staged_artifact_authority import decide_staged_artifact_authority


DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def _decision(**overrides):
    args = dict(
        artifact_id="pkg@example@1.0.0",
        artifact_digest=DIGEST_A,
        observed_digest=DIGEST_A,
        operation="STAGE",
        principal_stage=True,
        principal_publish=False,
        ack_state="CLEAR",
    )
    args.update(overrides)
    return decide_staged_artifact_authority(**args)


def test_stage_authority_allows_stage_without_publish_authority():
    result = _decision()
    assert result.decision == "ALLOW_STAGE"
    assert result.authority_transfer is False
    assert result.external_effects == ()


def test_publish_is_denied_without_publish_authority():
    assert _decision(operation="PUBLISH").decision == "DENY_PUBLISH"


def test_publish_is_allowed_only_with_publish_authority():
    assert _decision(operation="PUBLISH", principal_publish=True).decision == "ALLOW_PUBLISH"


def test_digest_drift_invalidates_inherited_authority():
    assert _decision(observed_digest=DIGEST_B).decision == "STALE_DIGEST"


def test_ambiguous_ack_requires_readback_before_retry():
    assert _decision(ack_state="AMBIGUOUS").decision == "READBACK_REQUIRED"


def test_decision_validates_against_contract():
    schema = json.loads(Path("contracts/staged-artifact-authority-decision.v0.1.schema.json").read_text())
    Draft202012Validator(schema).validate(_decision().as_dict())
