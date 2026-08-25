# Architecture

AIOS-Tools is an independent Python execution layer with one shared core and multiple adapters.

```text
caller
  -> CLI or MCP adapter
  -> request validation
  -> tool registry and execution policy
  -> fail-closed runner
  -> bounded tool implementation
  -> structured result and receipt
```

## Shared core

- `runner.py` resolves eligibility and execution.
- `tools.py` contains bounded tool implementations.
- `envelope.py` builds result and receipt structures.
- `canonical.py` provides deterministic JSON canonicalization and hashing.

## Adapters

- `cli.py` exposes local and CI-friendly JSON commands.
- `mcp_server.py` exposes the same core through MCP Streamable HTTP or stdio.

Adapters must not implement divergent business logic. All callers receive the same policy, registry, execution, and receipt behavior.

## Configuration surfaces

- `registry/` defines admitted tool identities and versions.
- `policies/` defines executable eligibility and allowed effects.
- `contracts/` defines request and result schemas.

## Current constraint

The browser-only MCP deployment adapter is a candidate execution surface. It
contains no divergent browser logic and exposes only the four read-only
interactive session tools through the shared core. Hosted activation,
authentication, direct connectors, durable writes, and automatic approvals
remain separately governed and are not implied by deployment configuration.
