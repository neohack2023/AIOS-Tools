# Authority Boundaries

Current cutover basis: `DRIVE_PRIMARY_AUTHORITY_OVERLAY — v0.3-object-aware — 2026-09-15`.

The authority model is object- and truth-domain-aware. Freshness alone does not transfer authority.

## AIOS-Tools GitHub repository — GITHUB_CURRENT

This repository is authoritative for live source code and live repository facts:

- source code and executable implementation;
- repository configuration;
- tool registry versions and executable policies;
- contracts, tests, and adapters;
- commits, branches, pull requests, reviews, and CI outcomes.

GitHub repository facts do not silently rewrite durable AIOS memory or architecture.

## Google Drive — DRIVE_VERIFIED / DRIVE_CURRENT

Google Drive `AI_KNOWLEDGE_SYSTEM` is the primary durable external knowledge destination after the 2026-09-15 cutover epoch.

Drive is authoritative for an object or scope only when its declared state is `DRIVE_VERIFIED` or `DRIVE_CURRENT`. New durable AIOS knowledge routes to Drive by truth class, including canon/decisions, current-state projections, relations, skills/workflows, research, assets, and execution receipts.

Placement in Drive alone does not promote authority. `DRIVE_CANDIDATE` remains a candidate until identity/parity verification is complete.

## Notion — LEGACY_SOURCE

Notion is retained as a provenance and exact-object fallback surface.

When a required object is absent from Drive or its Drive representation is not parity-verified, retrieve the exact Notion source as `LEGACY_SOURCE`. Do not bulk-load neighboring Notion branches and do not let provider identity or recency override an explicitly verified/current Drive successor.

Universal Notion retirement is not claimed. Unmigrated exact objects can remain the fallback source for their declared domain until a governed Drive successor explicitly supersedes them.

## Research and source systems

External research/source systems are authoritative only for their source/research domain. Research does not become canon, policy, runtime admission, or durable memory by proximity or freshness.

## Chat / LLM context

Chat and model context are transient evidence and routing hints only. They never outrank live GitHub repository facts or declared durable authority objects.

## Conflict and freshness

Resolve authority using:

`declared authority + explicit supersession + freshness`

A newer legacy edit does not silently override a `DRIVE_CURRENT` object. A newer GitHub implementation fact can create memory/execution drift but does not silently rewrite durable memory. If the required authority state cannot be verified, fail closed on canon-sensitive claims.

## Non-transfer rule

Execution produces evidence. Tests prove behavior under tested conditions. Neither execution nor a passing check may silently revise architecture, governance, durable memory, runtime admission, or capability authority.

Durable changes return through STONE → MASON and the appropriate authoritative surface.
