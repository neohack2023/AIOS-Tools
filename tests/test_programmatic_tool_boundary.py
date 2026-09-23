import pytest

from aios_tools.experimental.programmatic_tool_boundary import (
    ChildCallObservation,
    ChildVerdict,
    EffectClass,
    ToolBoundaryError,
    evaluate_child_call,
    evaluate_program_run,
)


def child(**kwargs):
    values = dict(
        parent_execution_id="exec-1",
        child_call_id="child-1",
        child_order=0,
        tool_id="read",
        allowed_tool_ids=("read", "write"),
        scope_key="scope-a",
        parent_scope_key="scope-a",
        effect_class=EffectClass.READ,
        parent_max_effect_class=EffectClass.WRITE,
        parameter_digest="digest-1",
        policy_id="policy-1",
        policy_version="v1",
        policy_evaluated=True,
        attributed=True,
        duplicate_non_idempotent_effect=False,
    )
    values.update(kwargs)
    return ChildCallObservation(**values)


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        (child(), ChildVerdict.PASS),
        (child(tool_id="shell"), ChildVerdict.BLOCK),
        (child(scope_key="scope-b"), ChildVerdict.BLOCK),
        (
            child(
                tool_id="write",
                effect_class=EffectClass.DESTRUCTIVE,
            ),
            ChildVerdict.BLOCK,
        ),
        (
            child(
                tool_id="write",
                effect_class=EffectClass.WRITE,
                duplicate_non_idempotent_effect=True,
            ),
            ChildVerdict.NON_SUCCESS,
        ),
        (child(attributed=False), ChildVerdict.NON_SUCCESS),
        (child(policy_evaluated=False), ChildVerdict.NON_SUCCESS),
    ],
)
def test_child_call_boundaries(candidate, expected):
    result = evaluate_child_call(candidate)
    assert result.verdict == expected
    assert result.authority_transfer is False


def test_legal_parallel_children_keep_independent_receipts():
    result = evaluate_program_run(
        (
            child(child_call_id="a", child_order=0),
            child(
                child_call_id="b",
                child_order=1,
                tool_id="write",
                effect_class=EffectClass.WRITE,
            ),
        )
    )
    assert [item.verdict for item in result] == [
        ChildVerdict.PASS,
        ChildVerdict.PASS,
    ]
    assert result[0].receipt_id != result[1].receipt_id


def test_duplicate_child_identity_fails_closed():
    with pytest.raises(ToolBoundaryError, match="duplicate_child_call_id"):
        evaluate_program_run(
            (
                child(child_call_id="same", child_order=0),
                child(child_call_id="same", child_order=1),
            )
        )


def test_receipt_is_deterministic():
    candidate = child()
    assert evaluate_child_call(candidate) == evaluate_child_call(candidate)
