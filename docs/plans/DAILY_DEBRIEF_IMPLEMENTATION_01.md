# DAILY_DEBRIEF_IMPLEMENTATION_01

## Purpose

Implement a bounded first slice of validated Daily Debrief / AIOS Daily Research Brief deltas from Google Drive in AIOS-Tools.

## Source authority

- Scope: `global-working-memory`
- Research packet: Google Drive `1xOTAPPYTeTJ3Dxp7ObEaxxK0zQ2B_9a70KMRbULadmo`
- STONE/MASON execution receipt: Google Drive `1duGCyvbVVWAl-F8VdbdSqPgA5cOSvFkRxF0qJ7LB0zM`
- Intake issue: #74
- Repository base: `main@b9e9dc65f85cebba3f90564fa0cfd0f1df5fb52e`

Drive supplies research/prototype evidence. GitHub owns implementation truth. This plan does not transfer authority.

## First implementation slice

Add a deterministic experimental policy module covering four validated 2026-09-21 gates:

1. portable instruction precedence/provider support;
2. model lifecycle staleness/substitution;
3. staged artifact authority split;
4. CI MCP capability/effect-receipt enforcement.

These remain experimental helpers and are not registered runtime tools.

## Non-goals

- no runtime activation;
- no new registry tool;
- no production publication or package mutation;
- no provider API call;
- no deployment;
- no authority promotion;
- no secret or OAuth handling;
- no automatic merge.

## Files

- `src/aios_tools/experimental/daily_debrief_gates.py`
- `tests/test_daily_debrief_gates.py`
- this plan

## Acceptance

Deterministic unit tests must cover:
- CLAUDE.md precedence over AGENTS.md when both are present;
- unsupported provider visibility;
- instruction digest drift invalidation;
- missing digest observations fail closed;
- pre/post model-deprecation behavior;
- silent model substitution rejection;
- stage vs publish authority separation;
- artifact digest drift invalidation;
- read-only CI MCP principal denial of management mutation;
- management mutation requiring effect receipt;
- schema revision drift requiring re-verification.

## Rollback

Delete the experimental module/tests and revert the implementing commit. No persistent runtime state or external side effects are introduced.
