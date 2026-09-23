# DAILY_DEBRIEF_DIGEST_01

## Purpose

Extend the experimental Daily Debrief policy gates with a bounded digest layer that turns repeated Daily Research Brief / STONE-MASON findings into implementation-plan candidates over time.

## Source boundary

Google Drive Daily Research Briefs and their STONE/MASON receipts remain research/evidence inputs. GitHub remains implementation truth. Digesting evidence does not promote Canon, activate runtime behavior, or authorize repository mutation.

## Missing parts addressed

PR #76 added deterministic policy gates, but did not yet provide:

1. idempotent debrief finding intake;
2. accumulation across multiple daily briefs;
3. lineage grouping across differently titled findings;
4. repeated-signal thresholds before planning;
5. unresolved live-test carry-forward;
6. a machine-readable implementation-plan candidate;
7. explicit authority ceilings on plan generation.

## Digest contract

The digest consumes structured `DebriefFinding` records emitted by the Daily Debrief / STONE-MASON side.

Each record carries:

- source identity;
- debrief date;
- implementation lineage;
- disposition/confidence;
- implementation consequence;
- validation state;
- exact remaining live test;
- stable evidence digest.

Exact replays are no-ops.

## Planning rule

A lineage becomes planning-eligible only when it has at least:

- 2 evidence records;
- from 2 distinct daily debriefs.

Default states:

- `PLAN_CANDIDATE_VERIFICATION_REQUIRED` when unresolved exact tests remain;
- `PLAN_CANDIDATE` when repeated evidence exists but no live verification is present;
- `READY_FOR_IMPLEMENTATION_PLAN` only when repeated evidence includes live PASS evidence and no unresolved test gate remains.

These states are advisory. They do not authorize implementation or promotion.

## Initial evidence alignment

2026-09-21 contributes model lifecycle, instruction precedence, staged-artifact authority, CI-MCP authority, and retrieval evaluation lineages.

2026-09-22 contributes model lifecycle again plus Cloudflare Python binding parity, credential authority inventory, incident-to-failure mapping, and context-memory benchmark evidence.

The repeated `model-lifecycle` lineage is therefore the first natural plan candidate, but its live verification remains open.

## Next bounded slice

After this digest contract survives repository validation:

1. add a parser/adapter from the actual Daily Debrief structured output into `DebriefFinding`;
2. persist digest state outside Canon, preferably under the execution/research processing surface;
3. replay at least 7 consecutive daily debrief receipts;
4. compare candidate-plan output with human implementation decisions;
5. only then consider wiring plan candidates into the existing governed execution/issue intake workflow.

## Non-goals

- no natural-language document parser in this slice;
- no Drive write-back;
- no scheduler changes;
- no automatic issue creation;
- no automatic PR creation;
- no activation of experimental gates;
- no Canon/Trusted Memory promotion.
