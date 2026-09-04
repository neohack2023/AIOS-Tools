# AIOS-Tools Role and Skill Profile

State: `PHASE_5_ACTIVE / ADAPTIVE_SKILL_SET / ORGANIZATION_AUDIT_BOUND / GOVERNANCE_SYNC_BOUND`

## Installed skills

| Role | Skill | Purpose |
| --- | --- | --- |
| Coordinator | `plan-feature` | Bounded planning and verifier mapping before material implementation |
| Reviewer | `review-pr` | Read-only candidate review against repository and touched-area law |
| Verifier | `verify-head` | Exact-identity, obligation-local mechanical verification |
| Knowledge Steward | `harvest-lesson` | Preserve review/incident lessons as provenance-bound candidates |
| Knowledge Steward | `sync-governance` | Compare pinned upstream governance, record delta only, and produce a receipt-bound freshness decision |
| Implementer | none | Implementation follows AGENTS + department instructions + governing plan; no distinct stable skill justified yet |

Canonical project skills live under `.github/skills/<skill-name>/SKILL.md`.

## Deferred candidate

- `prepare-release`: still deferred because AIOS-Tools has no established release workflow or distinct Release Steward role that justifies a stable repository-native procedure.

## Phase 4/5 mechanical ownership

AIOS-Tools does not add Audit or Sync roles merely to mirror the reference repository. The existing Repository Governance workflow owns deterministic organization checks. `scripts/governance_sync.py` validates the receipt/freshness contract, while the Knowledge Steward owns the comparison procedure.

The Verifier may interpret declared evidence but audit/sync PASS does not expand verifier authority. The Knowledge Steward may capture delta but cannot use sync to promote lessons, change runtime behavior, merge, release, deploy, or widen capability.

## Laws

- `ROLE != SKILL != VERIFIER != AUTHORITY`.
- `FETCH != SYNC != FRESHNESS RENEWAL`.
- A skill describes **how** to perform a repeatable procedure; invoking it does not grant permission to mutate, approve, merge, release, deploy, or widen capability.
- Reviewer findings may be harvested as candidate lessons, but only explicit human/governance adjudication may promote a lesson into a rule or verifier obligation.
- No installed skill pre-approves `shell` or `bash`; execution confirmation remains governed by the active host/tool boundary.
- Organization audit PASS proves only the declared audit obligations on the exact audited candidate.
- `MATERIAL_DELTA_PENDING` cannot renew governance freshness.
