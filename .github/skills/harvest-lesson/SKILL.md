---
name: harvest-lesson
description: Capture a concrete AIOS-Tools review, incident, or verification lesson as a provenance-bound candidate without promoting it into repository law. Use when a recurring or high-value failure pattern should be preserved for human adjudication.
---

# Harvest Lesson

This procedure creates candidate institutional memory. It does not create or promote rules.

## Inputs
A candidate lesson must have:
- a concrete observation from review, incident, test, workflow, or implementation evidence;
- immutable source identity where available, preferably commit SHA + path and PR/run/comment identifiers;
- affected department or repository-wide scope;
- a proposed prevention/detection rule or verifier obligation.

## Procedure
1. Read `docs/agent-system/lessons/README.md`.
2. Search `docs/agent-system/lessons/CANDIDATES.md` for duplicates or a stronger existing formulation.
3. Separate observation from interpretation.
4. Record the candidate using the required schema.
5. Set `promotion_state: NONE` unless an explicit human/governance decision already names a target rule surface.
6. If promotion is later authorized, update the candidate with the immutable promotion evidence and target rule path. Promotion itself is a separate governed repository change.

## Promotion law
- reviewer suggestion != rule;
- recurrence != permission;
- confidence != authority;
- candidate lesson != promoted rule.

The human/governance layer decides whether a lesson becomes common law, a department rule, a test/verifier obligation, documentation only, or is rejected.

Never rewrite global AIOS governance from a repository-local lesson. Escalate cross-repository/global doctrine through the existing external-fetch/authority path.
