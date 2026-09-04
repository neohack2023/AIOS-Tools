# AIOS-Tools Copilot Instructions

Use `AGENTS.md` as the repository-wide operating law, then load `docs/agent-system/context/REPOSITORY_HANDOFF.md` and `docs/agent-system/knowledge/KNOWLEDGE_INDEX.md` before broad exploration.

Use checked-in repository context first. Do not fetch Notion or Drive merely to reconstruct ordinary repository context when the local packet is sufficient.

Respect `docs/AUTHORITY_BOUNDARIES.md`. Role identity, skill invocation, tool access, review output, CI success, or consensus do not grant merge, release, deploy, capability, or global AIOS governance authority.

For touched files, apply the most specific `.github/instructions/*.instructions.md` packet. Keep changes bounded to one coherent concern and run the validation required by `AGENTS.md` plus the affected department instructions.

Use repository-native skills under `.github/skills/` only when their task matches:
- `plan-feature`
- `review-pr`
- `verify-head`
- `harvest-lesson`

Candidate lessons under `docs/agent-system/lessons/` are memory awaiting human/governance adjudication, not enforceable law. `prepare-release` is deferred; `sync-governance` belongs to Phase 5.
