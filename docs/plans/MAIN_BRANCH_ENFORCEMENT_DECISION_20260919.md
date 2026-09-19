# Main Branch Enforcement Decision Package — 2026-09-19

## Status

`DECISION_READY / NO_PROTECTION_MUTATION / OWNER_DECISION_REQUIRED`

Tracking issue: #62

Repository: `neohack2023/AIOS-Tools`

Observed current main at analysis:

`43df7cc428f647d8e50c5e6913eeecc84c4eaff2`

## Purpose

Resolve the mismatch between repository-local development law and live GitHub enforcement without silently changing repository security policy.

Repository-local law already says:

- review-first workflow;
- one coherent concern per branch/PR;
- no direct commit to `main` without a separate explicit bounded owner exception;
- human review controls merge;
- acceptance evidence must bind to the exact candidate head.

Live GitHub state currently says:

- `main.protected = false`;
- branch protection disabled;
- required status-check enforcement off;
- repository rulesets: none.

This document does not mutate protection settings.

## Verified stable required-check candidates

The following job contexts were observed with the same names on both PR #67 and PR #69:

- `governance`
- `test`
- `test-windows`
- `browser-core`
- `cartography-web`

Observed evidence:

PR #67 reviewed head:
`5ad6d538e8566860074353c81594b9eaddea7772`

- Repository Governance #473: `governance` PASS
- AIOS-Tools CI #475: `test` PASS
- AIOS-Tools CI #475: `test-windows` PASS
- AIOS-Tools CI #475: `browser-core` PASS
- AIOS-Tools CI #475: `cartography-web` PASS

PR #69 reviewed head:
`b6f0309b253439bbcb8f547ab65d2a440bc8e38c`

- Repository Governance #474: `governance` PASS
- AIOS-Tools CI #476: `test` PASS
- AIOS-Tools CI #476: `test-windows` PASS
- AIOS-Tools CI #476: `browser-core` PASS
- AIOS-Tools CI #476: `cartography-web` PASS

## Checks that should not be globally required

Do not globally require these as branch-protection checks:

- `Browser Activation Replay`
- `Benchmark Registry`
- `Audio Model Dependency Lock`
- `Demucs Model Quarantine`

Reason:

These are conditional or path/feature-specific lanes and may legitimately skip for unrelated pull requests. Making them globally required would create false merge blocks.

## Profile A — enforce the repository's declared review-first law

This is the smallest protection profile that matches current repository procedure without changing merge style or requiring a second human reviewer.

### Require pull request flow

Require changes to `main` to arrive through a pull request.

Required approving review count:

`0`

Reason:

The repository is owner-operated. Requiring one independent approval would create an avoidable self-deadlock when no second reviewer is available. Human merge review remains an explicit procedural owner gate even when GitHub does not require another account's approval.

### Require exact stable status contexts

Require:

- `governance`
- `test`
- `test-windows`
- `browser-core`
- `cartography-web`

Require branches to be up to date before merge:

`true`

Reason:

The repository's workflows deliberately checkout and verify the exact PR head. Requiring the branch to be current with `main` makes that tested head include the latest base state instead of allowing a stale reviewed branch to merge after the base has moved.

### Require conversation resolution

Proposed:

`true`

Reason:

This converts unresolved review findings from advisory chatter into an explicit merge gate without requiring another reviewer account.

### Administrator / owner behavior

Proposed default:

Administrators/owner are subject to the same rule.

Emergency escape remains repository-rule mutation, not an invisible bypass. Any intentional exception should be explicit, bounded, and documented before the direct update.

### Do not require

- linear history;
- squash-only merge;
- signed commits;
- deployment gates;
- code-owner review;
- multiple approvals;
- path-specific optional workflows.

Reason:

Those controls are not part of current accepted repository law and would widen policy beyond the coherence repair.

## Profile B — intentionally leave `main` unprotected

If owner flexibility is more valuable than pre-merge enforcement, `main` may intentionally remain unprotected.

That decision should be explicit and documented as acceptance of these risks:

1. direct pushes can bypass PR review;
2. CI/governance then become after-the-fact evidence instead of merge gates;
3. a broken direct push can temporarily become repository truth before checks finish;
4. the repository-local phrase “no direct commit to main without explicit bounded owner exception” remains procedural rather than mechanically enforced.

If this profile is selected, the repository should document:

`MAIN_PROTECTION=INTENTIONALLY_UNPROTECTED`

and:

`DIRECT_MAIN_UPDATE_REQUIRES_EXPLICIT_OWNER_EXCEPTION`

No implication should be made that CI-after-push is equivalent to pre-merge enforcement.

## Profile comparison

### Profile A

Strengths:

- matches current review-first law;
- blocks accidental direct pushes;
- converts exact-head checks into real merge gates;
- preserves existing merge commits and current PR workflow;
- does not require another human account.

Costs:

- merges wait for five stable checks;
- a bad required-check name can block merges;
- rule changes may be required if CI job identities change.

### Profile B

Strengths:

- maximum owner flexibility;
- no risk of status-check configuration deadlock;
- simplest emergency maintenance.

Costs:

- repository law is not mechanically enforced;
- direct-main mistakes become live before validation;
- governance evidence can only detect the problem after the update.

## Configuration safety sequence if Profile A is authorized

Do not apply a protection rule from this document alone.

Use this sequence:

1. re-read current `main` protection and rulesets;
2. confirm the five check names still exist on a fresh PR run;
3. configure PR-required flow with zero required external approvals;
4. require exactly the five stable contexts;
5. require current branch / strict checks;
6. require conversation resolution;
7. apply the same rule to administrators/owner unless the owner explicitly chooses a bypass policy;
8. do not require path-specific workflows;
9. open a disposable/no-op documentation PR or use an existing safe PR to prove the configured rule can be satisfied;
10. record the resulting protection/ruleset identity and observed enforcement in #62 and the repository handoff.

## Rollback

If the rule causes an unintended merge deadlock:

1. capture the exact failing required context and current rule state;
2. change only the misconfigured enforcement field;
3. do not disable unrelated checks;
4. record the exception/repair in #62.

## Decision gate

No branch-protection or ruleset mutation is authorized by this planning artifact.

Owner must explicitly select one of:

`PROFILE_A_ENFORCE_REVIEW_FIRST`

or

`PROFILE_B_INTENTIONALLY_UNPROTECTED`

Until then:

`MAIN_PROTECTION_DECISION=PENDING`
