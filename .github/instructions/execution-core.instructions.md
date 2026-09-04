---
applyTo: "src/aios_tools/cli.py,src/aios_tools/mcp*.py,extensions/**,contracts/**,policies/**,profiles/**"
---

# Execution core and adapters department

Load `AGENTS.md`, `SPEC.md`, `docs/AUTHORITY_BOUNDARIES.md`, `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT.md`, and `docs/VALIDATION.md` before changing registry, policy, contract, CLI, MCP, extension, or profile behavior.

Keep shared core behavior independent from adapter presentation. Registry, policy, implementation, contract, tests, and receipts should move together when a tool surface changes.

Fail closed for unknown tools, invalid inputs, absent policy, ambiguous eligibility, stale authority, or verifier mismatch. Do not widen capability, persistence, network, secrets, deployment, merge, or release authority as an implementation convenience.
