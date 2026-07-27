# Cartography Slice 2

Status: implementation on draft branch
Mode: read-only / simulation

This slice implements the frozen deterministic fixture proof for the AIOS System Cartography Engine.

Included:

- canonical Graph IR serialization and SHA-256 digest generation
- non-finite and negative-zero rejection
- deterministic Notion page-tree fixture adapter
- deterministic Drive file-tree fixture adapter
- deterministic Project Scope Registry fixture adapter
- deterministic Capability Registry fixture adapter
- explicit unresolved-reference preservation
- System Overview View Spec
- Workflow Control Plane View Spec
- non-rendered deterministic view compilation
- determinism, row-order, duplicate-label, unresolved-reference, and no-renderer-state tests

Excluded:

- live connectors
- source writes
- production registry reads
- layout engines
- renderers
- capability activation
- Active promotion
