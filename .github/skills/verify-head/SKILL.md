---
name: verify-head
description: Verify declared AIOS-Tools obligations against an exact immutable candidate or main commit. Use for CI, contract, policy, regression, browser, benchmark, audio/model, cartography, or governance verification where identity and evidence binding matter.
---

# Verify Head

Verification is obligation-local evidence, never merge/release/deploy authorization.

## Identity first
Resolve and record:
- repository;
- candidate/head SHA;
- base SHA when relevant;
- event or workflow identity;
- verifier obligation being evaluated.

Do not call a moving branch name, synthetic merge ref, or nearby log text immutable candidate evidence unless the declared verifier contract explicitly proves the binding.

## Load
1. `AGENTS.md`.
2. `docs/VALIDATION.md`.
3. repository handoff + knowledge index.
4. most specific touched-area instruction packet.
5. governing contract/policy and relevant tests/workflow.

## Execute
Run only the checks required for the declared obligation. Preserve command, exact identity, observed result, artifact/receipt identifier when present, and limitations.

For GitHub Actions evidence, confirm the workflow run itself reports the exact head SHA being claimed.

## Result classes
- `PASS` — the declared obligation passed for the recorded exact identity.
- `FAIL` — the declared obligation failed.
- `BLOCKED` — required evidence, identity, environment, or verifier contract is missing/ambiguous.

A PASS does not transfer to a later candidate-head change unless the governing obligation explicitly proves transferability.

Never edit implementation while acting as verifier and never turn CI success into authorization.
