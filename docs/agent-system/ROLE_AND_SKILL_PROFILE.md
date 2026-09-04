# AIOS-Tools Role and Skill Profile

State: `PHASE_3_ACTIVE / ADAPTIVE_SKILL_SET`

## Installed skills

| Role | Skill | Purpose |
| --- | --- | --- |
| Coordinator | `plan-feature` | Bounded planning and verifier mapping before material implementation |
| Reviewer | `review-pr` | Read-only candidate review against repository and touched-area law |
| Verifier | `verify-head` | Exact-identity, obligation-local mechanical verification |
| Knowledge Steward | `harvest-lesson` | Preserve review/incident lessons as provenance-bound candidates |
| Implementer | none | Implementation follows AGENTS + department instructions + governing plan; no distinct stable skill justified yet |

Canonical project skills live under `.github/skills/<skill-name>/SKILL.md`.

## Deferred candidates

- `prepare-release`: deferred because AIOS-Tools currently has no established release workflow or distinct Release Steward role that justifies a stable repository-native procedure.
- `sync-governance`: reserved for Phase 5 after the target-specific upstream source set and freshness contract are designed.

## Laws

- `ROLE != SKILL != VERIFIER != AUTHORITY`.
- A skill describes **how** to perform a repeatable procedure; invoking it does not grant permission to mutate, approve, merge, release, deploy, or widen capability.
- Reviewer findings may be harvested as candidate lessons, but only explicit human/governance adjudication may promote a lesson into a rule or verifier obligation.
- No Phase 3 skill pre-approves `shell` or `bash`; execution confirmation remains governed by the active host/tool boundary.
