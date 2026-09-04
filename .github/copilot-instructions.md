# AIOS-Tools Copilot Instructions

Use `AGENTS.md` as the repository-wide operating law, then load `docs/agent-system/context/REPOSITORY_HANDOFF.md`, `docs/agent-system/context/governance-lock.yaml`, and `docs/agent-system/knowledge/KNOWLEDGE_INDEX.md` before broad exploration.

Use checked-in repository context first. Do not fetch Notion or Drive merely to reconstruct ordinary repository context when the local packet is sufficient. Treat an expired governance lock as an escalation condition rather than silently using stale local law.

Respect `docs/AUTHORITY_BOUNDARIES.md`. Role identity, skill invocation, tool access, review output, audit output, sync output, CI success, or consensus do not grant merge, release, deploy, capability, mutation, or global AIOS governance authority.

For touched files, apply the most specific `.github/instructions/*.instructions.md` packet. Keep changes bounded to one coherent concern and run the validation required by `AGENTS.md` plus the affected department instructions.

Use repository-native skills under `.github/skills/` only when their task matches:
- `plan-feature`
- `review-pr`
- `verify-head`
- `harvest-lesson`
- `sync-governance`

Candidate lessons under `docs/agent-system/lessons/` are memory awaiting human/governance adjudication, not enforceable law. `prepare-release` remains deferred.

Phase 4/5 organization law is enforced by the existing Repository Governance workflow. `sync-governance` is Knowledge-Steward-only and may run only for explicit synchronization triggers. It must use the pinned source set in `docs/agent-system/governance-sync/UPSTREAM_SYNC_PROFILE.md`, record delta only, and leave `valid_through` unchanged when the disposition is `MATERIAL_DELTA_PENDING`.

Do not edit audit or synchronization outputs to manufacture PASS, renew freshness from a fetch alone, or treat an audit/sync PASS as authorization.
