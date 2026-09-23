# DAILY_DEBRIEF_IMPLEMENTATION_INTAKE_01

## Purpose
Turn implementation-worthy deltas from the Drive-authoritative AIOS Daily Research Brief into explicit, reviewable GitHub implementation candidates without treating research/prototype evidence as repository truth.

## Authority
- Google Drive: authoritative source for the retained daily research/prototype packet when the registered object is Drive-authoritative/current.
- GitHub: authoritative for live repository implementation, branches, pull requests, tests, and CI.
- Notion: legacy provenance only when a current Drive object explicitly requires fallback.

## Intake law
A daily debrief finding MAY enter this repository only when:
1. scope resolves to `global-working-memory` and the target maps to AIOS-Tools;
2. Drive provenance and current state are present;
3. the finding is classified as implementation-relevant: `REFINEMENT | EXTENSION | NOVEL`;
4. it is not already implemented on `main` or an active equivalent PR;
5. the proposed change has one coherent implementation concern;
6. acceptance criteria and rollback are explicit;
7. implementation does not silently widen runtime, tool, credential, publication, deployment, or authority boundaries.

## State machine
`DRIVE_RETAINED -> REPO_COLLISION_CHECKED -> IMPLEMENTATION_CANDIDATE -> BRANCH_PR -> VERIFIED -> HUMAN_MERGE_DECISION`

Research states such as `PROMOTED_PROTOTYPE / EXPERIMENTAL / VERIFICATION_PENDING` remain research/prototype states until GitHub implementation evidence exists.

## Required candidate fields
- source_drive_id
- source_title
- source_date
- scope_key
- delta_class
- repository
- target_concern
- existing_repo_overlap
- implementation_state
- acceptance_criteria
- rollback
- authority_effect
- source_receipt_id

## 2026-09-21 seeded candidates
Source packet: `AIOS Daily Research Brief — 2026-09-21 — Research Packet`
Drive ID: `1xOTAPPYTeTJ3Dxp7ObEaxxK0zQ2B_9a70KMRbULadmo`
Execution receipt: `1duGCyvbVVWAl-F8VdbdSqPgA5cOSvFkRxF0qJ7LB0zM`

1. Portable instruction precedence gate
   - delta: EXTENSION
   - concern: observed instruction-file precedence/provider compatibility
   - state: IMPLEMENTATION_CANDIDATE

2. Model lifecycle staleness gate
   - delta: REFINEMENT
   - concern: bind verification to model availability/substitution lifecycle
   - state: IMPLEMENTATION_CANDIDATE

3. Staged artifact authority fixture
   - delta: NOVEL
   - concern: separate stage authority from publish authority with digest/readback semantics
   - state: IMPLEMENTATION_CANDIDATE

4. CI MCP authority gate
   - delta: EXTENSION
   - concern: principal/tool/action/effect-receipt contract for CI MCP surfaces
   - state: IMPLEMENTATION_CANDIDATE

5. Retrieval-upstream benchmark refinement
   - delta: REFINEMENT
   - concern: evaluate retrieval quality upstream of patch success, including no-gold abstention
   - state: IMPLEMENTATION_CANDIDATE

## Non-goals
- no automatic implementation of all five in one PR;
- no direct-to-main writes;
- no promotion to Active/Canon/Trusted Memory;
- no provider credentials or live paid runs;
- no publication/deployment authority;
- no merge without human review.

## First implementation slice
This PR installs the intake contract and machine-readable seed fixture only. Each seeded candidate should become its own bounded implementation PR after collision checking and repository-specific planning.
