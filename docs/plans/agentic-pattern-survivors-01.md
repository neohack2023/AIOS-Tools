# Agentic pattern survivors 01

Base: `93163223925bcf6944b88732a78842ca402292ca`.
Scope: `global-working-memory`.
Delivery: bounded candidate branch and draft PR only. Merge, runtime activation, deployment, capability widening, registry mutation, and policy mutation are not authorized by this slice.

## Governing lineage

- STONE: https://app.notion.com/p/3dd43bd4ae4a81d782a6c4fa21a6f152
- MASON write plan: https://app.notion.com/p/3dd43bd4ae4a8121a557e9da81711e0b
- Execution completion contract: https://app.notion.com/p/3dd43bd4ae4a8121a2f9e7c3f1e63d56
- Next action priority policy: https://app.notion.com/p/3dd43bd4ae4a81679c1fef8ff0444d7a
- Completion Drive mirror: https://docs.google.com/document/d/1fsV3UrcYfo24_edtq73h_BOABsxmTZCEfgcdUNQB5KY/edit
- Priority Drive mirror: https://docs.google.com/document/d/1IB-MnwG1rijsmuekG8P7A0xmta-pSPWAm5WDIlaqc3Q/edit

## Evaluation disposition

Two mechanisms survived duplicate/conflict review:

1. `AIOS_EXECUTION_COMPLETION_CONTRACT_01`: whole-run completion evaluation over explicit observable trajectory facts.
2. `NEXT_ACTION_PRIORITY_POLICY_01`: deterministic advisory ordering over actions already resolved as legal and available.

The proposed bounded discovery profile was merged with existing Deep Research, harvest, adaptive retrieval, Agent Credit Governor, and marginal-value stopping. It receives no new subsystem or repository implementation.

## Objective

Implement both retained candidates as offline pure functions with strict fail-closed packet validation and focused regression fixtures. Their outputs are advisory evidence only.

## Non-goals

- no tool registration or handler binding
- no execution-policy or transition-registry mutation
- no CLI or MCP exposure
- no scheduler, autonomous continuation, or automatic approval
- no credential, network, filesystem, connector, deployment, or durable-write effect
- no hidden reasoning, scratchpad, or chain-of-thought capture
- no merge or activation from this branch

## Files

- `src/aios_tools/experimental/execution_completion.py`
- `src/aios_tools/experimental/next_action_priority.py`
- `tests/test_execution_completion.py`
- `tests/test_next_action_priority.py`
- this plan

No existing runtime or policy file is modified.

## Acceptance obligations

Execution completion must prove: exact packet shape; identity and verifier binding; forbidden-event failure; step-budget failure; order failure; predicate failure; nonterminal partial state; terminal-incomplete failure; and terminal complete PASS. Observable events may repeat and no reasoning-content field is admitted.

Next-action priority must prove: exact packet shape; non-empty unique legal action set; factor range/type validation; deterministic lexicographic ordering; user-priority precedence; risk/cost preference after positive factors; stable action-id tie break; and fail-closed handling for unavailable or authority-incompatible actions.

Both outputs must always record `authority_transfer: false` and `execution_authorized: false`.

## Required verification

Run focused tests, full `pytest`, `aios-tools list`, `aios-tools invoke system.health --input '{}'`, `aios-tools-mcp --help`, and repository-governance checks on the exact candidate head. CI/review evidence is valid only when bound to that head.

## Rollback

Close the draft PR and delete or abandon this branch. Because the implementation is unregistered and pure, no runtime state, authority, connector, or durable external effect requires rollback.
