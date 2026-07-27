# AIOS-Tools

Independent capability and execution layer for AIOS.

AIOS-Tools exposes bounded, versioned tools that can be invoked by LLMs, Notion/Drive workflows, CI, local developers, and external systems. It is independent of the portable AIOS build.

## Authority boundary

- **Notion** owns architecture and governance authority.
- **Google Drive** owns evidence, source-artifact, execution-package, and shadow surfaces according to the registered authority model.
- **This repository** owns live executable implementation and tool-version facts.
- A passing tool, test, or validation never transfers architectural or memory authority.
- Durable external writes require a separately authorized STONE → MASON path.

See [Authority Boundaries](docs/AUTHORITY_BOUNDARIES.md) and [Architecture](docs/ARCHITECTURE.md).

## Bootstrap capabilities

| Tool | Mode | Purpose |
|---|---|---|
| `system.health` | READ_ONLY | Report server, registry, and policy state |
| `canonical.hash_json` | READ_ONLY | Produce a deterministic SHA-256 digest for JSON-compatible data |
| `schema.validate` | READ_ONLY | Validate an instance with JSON Schema Draft 2020-12 |

Every result is wrapped in an execution receipt with requester identity, authority context, registry and policy versions, provenance, `authority_transfer: false`, and explicit external-effect reporting.

## Executable governance

The runtime loads its tool metadata from `registry/tools.v0.1.json` and its global safety posture from `policies/execution-policy.v0.1.json`. It validates governed requests against `contracts/tool-request.v0.1.schema.json` before execution and fails closed when configuration is missing, malformed, or inconsistent with handler bindings.

## Components

- `src/aios_tools/config.py` — validated registry, policy, and request-contract loading
- `src/aios_tools/runner.py` — fail-closed request validation, eligibility, execution, and receipt routing
- `src/aios_tools/tools.py` — registered tool handler implementations
- `src/aios_tools/envelope.py` — execution result and receipt envelope
- `src/aios_tools/cli.py` — JSON CLI adapter
- `src/aios_tools/mcp_server.py` — MCP Streamable HTTP and stdio adapter
- `registry/` — executable tool registry facts
- `contracts/` — request and result schemas
- `policies/` — executable eligibility policy
- `tests/` — shared-core and negative-path verification

## Install and run

```bash
python -m pip install -e ".[dev]"
aios-tools list
aios-tools invoke system.health --input '{}'
aios-tools invoke canonical.hash_json --input '{"value":{"b":2,"a":1}}'
```

## MCP server

```bash
aios-tools-mcp
aios-tools-mcp --transport stdio
```

Streamable HTTP is served at `/mcp` by default.

## Validation

```bash
pytest
aios-tools list
aios-tools invoke system.health --input '{}'
aios-tools-mcp --help
```

GitHub Actions runs the same shared-core, CLI, and MCP smoke checks. See [Validation](docs/VALIDATION.md).

## Development workflow

1. Start from a recorded base commit.
2. Use one branch and pull request for one coherent concern.
3. Link the approved plan or governing contract.
4. Run the documented validation commands.
5. Record actual results, risks, authority impact, and receipt links in the pull request.
6. Human review decides whether the change merges.

Read [AGENTS.md](AGENTS.md), [CONTRIBUTING.md](CONTRIBUTING.md), and [Development](docs/DEVELOPMENT.md) before changing implementation.

## Current status

Bootstrap implementation is under governed review. Hosted deployment, authentication, direct Notion/Drive adapters, Tier 1 control-envelope migration, and write-capable tools remain deferred.
