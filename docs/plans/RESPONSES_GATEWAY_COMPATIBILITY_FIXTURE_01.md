# RESPONSES_GATEWAY_COMPATIBILITY_FIXTURE_01

Phase 11 of the legacy Notion research backlog.

An OpenAI-compatible gateway is agent-compatible only when it preserves the full Responses execution contract, not merely text generation.

The verifier binds:
- gateway version and image digest;
- Responses wire API;
- model alias to observed upstream binding;
- caller identity;
- budget/rate policy attribution;
- previous_response_id support and semantic continuation;
- typed stream completion;
- stable function-call identity;
- gateway trace identity;
- local tool-execution authority.

Outcomes are PASS, BLOCK, or STALE.

A stable alias with a changed upstream model is STALE. Text-only success cannot compensate for broken continuation, streaming, function calls, caller attribution, policy rejection, or tool-authority boundaries.

This module sends no model requests and performs no tool execution, routing, budget enforcement, or credential handling.
