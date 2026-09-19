# AIOS-Tools Specification v0.1

## Mission

Provide a standalone, governed execution layer that an LLM or automation can call without requiring the AIOS portable build.

## Callers

- LLM and agent clients through MCP
- Notion-triggered workflows through a future adapter or hosted endpoint
- Google Drive-triggered workflows through a future adapter or hosted endpoint
- CI and local developers through the CLI or Python library
- AIOS portable build as an optional client

## Authority boundary

AIOS-Tools executes bounded capabilities. It is not architectural authority, durable-memory authority, or portable-runtime truth.

Notion remains architecture and governance authority. Google Drive remains evidence, source-artifact, and shadow storage. GitHub stores executable implementation. Tool results are evidence and receipts until promoted by the governed STONE → MASON process.

## Execution contract

All invocations resolve:

`input → scope → authority context → tool eligibility → bounded execution → structured result → receipt`

Default mode is `READ_ONLY`.

Every receipt includes request and receipt identifiers, tool name and version, scope and mode, status, timestamps, output or errors, provenance, external effects, and `authority_transfer: false`.

## Slice 0 tools

1. `system.health`
2. `canonical.hash_json`
3. `schema.validate`

## Deferred

- Connector credentials and direct Notion/Drive mutations
- Durable write tools
- approval workflows
- hosted activation, OAuth, and public directory submission
- AIOS portable runtime integration
- Tier 1 control-envelope fixture migration

## Browser-only MCP attachment

The runtime attachment slice may expose only `browser.session.open`,
`browser.session.observe`, `browser.session.act`, and
`browser.session.close` through a dedicated MCP adapter. The adapter must
retain the shared-core registry, policy, contracts, and receipt path; advertise
accurate read-only/open-world annotations; and exclude all write-capable tools.
Deployment packaging is implementation evidence, not proof of a live endpoint.

## Completion criteria

- CLI and MCP adapters call one shared core registry.
- Draft 2020-12 validation uses the `jsonschema` implementation.
- Tests prove deterministic hashing, valid/invalid schema behavior, receipt shape, unknown-tool failure, and no external effects.
- CI runs read-only tests with least permissions.
