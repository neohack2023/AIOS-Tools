# AUTHORITY_COLLAPSE_GUARD_01

## Phase

Legacy Notion research backlog, phase 2.

Source owner:
AUTHORITY_COLLAPSE_BENCH_01

Scope:
global-working-memory

## Problem

Plausible text, successful checks, platform approvals, and security results can be accidentally collapsed into more authority than they actually possess.

This slice prevents that collapse without creating a new authority registry or workflow engine.

## Minimal runtime

Two pure decision functions are sufficient.

Claim admissibility:
- CURRENT_STATE
- HISTORICAL_ONLY
- EVIDENCE_ONLY
- TASK_ONLY
- ROUTING_ONLY
- BLOCK

Gate evidence effect:
- GATE_PASS
- EVIDENCE_ONLY
- STALE
- BYPASS
- BLOCK

Neither function performs an external action.

## Laws

- current authority is usable only inside its declared domain;
- superseded authority is history only and requires lineage;
- research is evidence, not project authority;
- conversation evidence is task-local, not silently durable;
- Drive/shadow evidence cannot impersonate owning authority;
- competing current authority fails closed;
- advisory model assessment has no terminal gate effect;
- approval/security evidence is bound to artifact/head revision;
- approval/security evidence is also bound to policy revision;
- producer/reviewer independence stays explicit;
- approval scope/path mismatch blocks;
- bypass remains BYPASS evidence and is never relabeled as a clean PASS;
- any local gate PASS closes only that gate and transfers no merge, deploy, Canon, or runtime authority.

## Research

GitHub Copilot approvals can count toward required approvals when explicitly enabled, while advisory approval assessment alone does not. New commits dismiss prior Copilot approval.

GitHub secret-scanning rulesets can block merge until a scan is complete for the pull request head and introduced alerts are resolved.

NIST separation-of-duties and least-privilege guidance supports keeping distinct responsibilities and authorization scopes separate.

## Deliberate non-goals

No:
- authority registry;
- graph database;
- role inheritance engine;
- merge executor;
- deployment executor;
- Canon promotion;
- workflow orchestration;
- automatic authority transfer.

The guard classifies evidence. Existing governed workflows remain the actuator.
