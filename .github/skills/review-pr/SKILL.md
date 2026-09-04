---
name: review-pr
description: Perform a read-only advisory review of an AIOS-Tools pull request or explicitly authorized direct-main candidate. Use when evaluating a concrete candidate against repository law, touched-area instructions, contracts, tests, and evidence.
---

# Review PR

Review is advisory. It does not grant acceptance, merge, release, deploy, capability, or verifier authority.

## Resolve candidate identity
Before reviewing, resolve the immutable candidate commit SHA and the intended base. If reviewing an explicitly authorized direct-main staging commit, record that exact commit identity instead of inventing a PR.

## Load only relevant context
1. `AGENTS.md`.
2. repository handoff + knowledge index;
3. `docs/agent-system/review/REVIEW_RULES.md`;
4. the candidate diff;
5. the most specific touched-area `.github/instructions/*.instructions.md` packets;
6. relevant contracts, policies, fixtures, tests, workflows, and governing plan/contract.

`docs/agent-system/lessons/CANDIDATES.md` is evidence for possible recurrence, not enforceable law unless a lesson has been explicitly promoted into a rule surface.

## Review dimensions
Check for:
- authority or scope widening;
- contract/policy mismatch;
- fail-open behavior where fail-closed is required;
- verifier/evidence identity defects;
- missing or misleading tests;
- touched-area invariant violations;
- unsafe credential/network/durable-write behavior;
- stale or contradictory documentation introduced by the candidate.

## Output
Return:
1. Summary
2. Blocking findings
3. Should fix
4. Nice to have
5. Verified evidence
6. Candidate lessons worth harvesting

Each finding must identify severity, concrete evidence, and affected path/obligation. Never edit the candidate during review and never self-resolve findings by changing the code.

A repeated or high-value finding may be proposed to `harvest-lesson`, but review cannot promote it into law.
