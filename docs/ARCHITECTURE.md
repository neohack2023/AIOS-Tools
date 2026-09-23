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

## Portable-package evaluation

`src/aios_tools/package_eval/` is a separate evidence subsystem rather than a tool-authority surface. It compiles an exact package artifact plus frozen fixture into paired clean-room `PACKAGE_OFF` / `PACKAGE_ON` requests, deterministic grader contracts, and an optional ChatGPT product-surface acceptance plan. Capsule creation never implies that a model or product-surface evaluation executed.

The package-eval subsystem may later use provider/API or browser adapters, but those adapters must preserve paired-treatment invariants and existing browser/authentication policy. Human takeover satisfies only the interactive authentication boundary and does not grant evaluator or release authority.

## Configuration surfaces

- `registry/` defines admitted tool identities and versions.
- `policies/` defines executable eligibility and allowed effects.
- `contracts/` defines request and result schemas.

## Current constraint

Slice 0 is read-only. Hosted deployment, authentication, direct connectors, durable writes, and automatic approvals are deferred.