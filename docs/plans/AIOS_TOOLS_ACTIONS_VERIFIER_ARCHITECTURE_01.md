# AIOS_TOOLS_ACTIONS_VERIFIER_ARCHITECTURE_01

State: `ADMIN_AUTHORIZED_DIRECT_MAIN / ARCHITECTURAL_REPAIR / PR59_SUPERSEDING`

## Problem

PR #59 repeatedly exposed bypasses in a custom GitHub Actions verifier. Each repair moved the defect to a neighboring source-text or workflow-semantics edge case: trigger spelling, comparison suppression, environment shadowing, `continue-on-error`, conditional verification, container environment, and path-filter ordering.

The repeated migration means the abstraction boundary was wrong. AIOS was rebuilding too much of the GitHub Actions language.

## Decision

Split verification by obligation:

- actionlint owns generic GitHub Actions syntax/semantics static checking.
- zizmor supplies independent generic Actions security evidence.
- AIOS keeps a small parsed-YAML policy verifier for exact-head identity, self-trigger observability, and verifier execution context.
- model review remains advisory; deterministic/current-head checks retain acceptance ownership for their declared obligations.

## Direct-main authority

The repository administrator explicitly authorized these changes on `main`. This is a bounded exception for this architectural repair. It does not create a reusable direct-main mutation rule.

## Retained PR #59 work

The valid exact-head workflow changes are retained:
- full-SHA-pinned checkout;
- direct `${{ github.event.pull_request.head.sha || github.sha }}` checkout binding;
- persisted credentials disabled;
- immediate same-job identity verification;
- path-filtered workflows self-trigger on their own definitions;
- promoted lesson/canonical context reconciliation.

## Superseded PR #59 mechanism

The custom auditor is replaced rather than extended. Generic syntax spelling is no longer reimplemented by source regexes. The new AIOS policy explicitly rejects only structures that can break its trust-binding contract, including job containers, dangerous identity environment overrides, `paths-ignore`/negative path filters, conditional/non-fatal identity checks, alternate checkout destinations, and incomplete verifier bodies.

## Tool supply-chain pins

- actionlint `v1.7.12`, tag commit `914e7df21a07ef503a81201c76d2b11c789d3fca`.
- Linux amd64 archive SHA-256 `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8`.
- zizmor action `3dc1ecc9bcb9e94e9b2c709687979e1298497054` (`v0.6.2`).
- zizmor engine `1.29.0`.

## Verification

Required after direct-main promotion:
1. Repository Governance push run on exact new `main`.
2. actionlint blocking pass.
3. focused exact-head policy tests.
4. exact-head policy audit PASS.
5. Phase 5 organization/sync audits PASS.
6. broader AIOS-Tools CI push run PASS.
7. record zizmor output as advisory security evidence.
8. close PR #59 as superseded, not merged.

## Authority boundary

This repair changes CI/evidence validation only. It does not authorize release, deployment, branch protection changes, capability widening, or unrelated repository mutations.
