---
applyTo: "src/aios_tools/browser/**,tests/test_browser_*.py,.github/workflows/browser-activation-replay.yml"
---

# Browser capability department

Load `AGENTS.md`, `docs/AUTHORITY_BOUNDARIES.md`, `docs/VALIDATION.md`, and the browser-related contract/policy/fixture set before changing behavior.

Preserve explicit-target, policy, acknowledgement, receipt, and fail-closed boundaries. Do not widen network, credential, write, or browser authority as a side effect of implementation.

Treat browser replay and browser-core CI as evidence for their declared obligations only. A passing replay does not authorize activation, release, or capability widening.
