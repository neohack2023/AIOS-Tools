# PROGRAMMATIC_TOOL_CALL_BOUNDARY_01

## Phase

Legacy Notion research backlog, phase 4.

## Purpose

Prevent generated orchestration from turning one authorized tool opportunity into undeclared child authority.

## Research basis

OpenAI Agents SDK programmatic tool calling allows generated JavaScript to coordinate eligible tools, while application-owned tools retain their normal validation, permissions, approvals, guardrails, side effects, and child-call lineage.

The AIOS prototype therefore needs a child-call legality boundary, not a second execution sandbox.

## Child-call laws

Every child call must preserve:
- parent execution identity;
- unique child identity and order;
- allowed tool membership;
- exact parent scope;
- effect class no stronger than parent authorization;
- parameter digest;
- policy ID/version;
- explicit policy evaluation;
- attribution.

A duplicate non-idempotent effect is NON_SUCCESS even if the individual call would otherwise be legal.

## Outcomes

- PASS
- BLOCK
- NON_SUCCESS

## Boundary

This feature does not:
- execute generated code;
- dispatch tools;
- retry tools;
- perform approvals;
- widen authority;
- replace MCP tool policy;
- replace the execution supervisor.

It only judges recorded child-call legality and emits deterministic receipts.
