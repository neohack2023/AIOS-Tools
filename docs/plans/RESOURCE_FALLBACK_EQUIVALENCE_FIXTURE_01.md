# RESOURCE_FALLBACK_EQUIVALENCE_FIXTURE_01

Phase 8 of the legacy Notion research backlog.

Fallback resources improve availability only when candidates are prequalified for the workload. Capacity never substitutes for compatibility.

The verifier binds:
- validated preference-list digest;
- ordered candidate resource identities;
- compatibility receipt per candidate;
- capacity observation;
- selected rank;
- exact instance count;
- environment fingerprint;
- cost/performance equivalence labels;
- bounded queue deadline.

Outcomes:
SELECT, STALE_LIST, QUEUE_EXPIRED, NO_COMPATIBLE_CAPACITY.

An incompatible candidate is skipped even if it has capacity. A changed preference list invalidates prior validation. Exhausted capacity fails boundedly instead of widening to undeclared hardware.

This module does not provision resources or schedule jobs.
