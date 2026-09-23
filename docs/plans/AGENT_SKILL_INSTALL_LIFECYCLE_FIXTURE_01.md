# AGENT_SKILL_INSTALL_LIFECYCLE_FIXTURE_01

Phase 9 of the legacy Notion research backlog.

This feature governs the lifecycle evidence around portable agent skills without installing or trusting anything itself.

Core law:
discover != install != trusted.

Tracked lifecycle:
- discovery;
- target-specific install;
- update;
- identical no-op;
- removal;
- source drift;
- unresolved/incomplete version identity.

Changed content invalidates prior verification. Removal revokes availability but preserves provenance. The same source installed to multiple agents shares source identity while retaining target-specific receipts.

Later provider-specific refinements such as signatures, behavioral benchmarks, bundles, deployment facts, and remote distribution remain attachable evidence. They are intentionally not baked into the core lifecycle state machine.

No skill becomes Active, Canon, Trusted Memory, or executable because of this verifier.
