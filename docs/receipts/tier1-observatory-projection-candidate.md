# Tier 1 Observatory Projection Candidate Receipt

## State

`CANDIDATE_IMPLEMENTED / CI_PENDING / REVIEW_PENDING / NO_RUNTIME_ACTIVATION / NO_ACTIVE_PROMOTION`

## Date

2026-07-30

## Scope

`global-working-memory`

## Authorized transformation

Project the merged read-only Context Expansion Packet Workflow result into one deterministic metadata-only Observatory read model.

## Knowledge-gap decision

No new external research was required. Existing AIOS contracts already establish:

- Cognition Receipt event and evidence semantics
- Context Expansion Decision Record semantics
- content-free evidence pointers
- distinct request, trace, receipt, execution, scope, and resource identities
- separation between governed source/runtime models and visual projections

The remaining work was bounded projection plumbing.

## Implementation

Branch: `agent/tier1-observatory-projection`

Implemented:

- deterministic `CONTEXT_EXPANSION_OBSERVATORY/0.1` projection
- exact workflow, identity, context-expansion, evidence, privacy, and authority sections
- explicit null execution identity when no upstream execution ID exists
- content-free CEDR evidence-link deduplication
- canonical `op_<sha256>` projection identifier
- exact-key fail-closed validation
- recursive forbidden-field rejection
- Draft 2020-12 JSON Schema contract
- positive and negative-path tests

## Preserved boundaries

- no raw Cognition Receipt
- no raw CEDR
- no event payloads
- no source content
- no decision-reason prose
- no connector reads or writes
- no registry or policy changes
- no CLI or MCP exposure
- no runtime subscription or live telemetry ingestion
- no durable projection store
- no authority transfer
- no Active promotion

## Verification

Repository CI and Repository Governance are pending on the final branch head. No local repository-wide pass is claimed because this runtime cannot clone GitHub over the network.

## MASON disposition

- implementation: `candidate_ci_pending`
- runtime activation: `not_authorized`
- authority change: none
- canon promotion: none
- Drive cutover: none

## Next gate

After CI, review, and merge, a separately governed presentation slice may render a checked-in projection fixture in the existing Cartography Workbench. Live runtime ingestion remains excluded.
