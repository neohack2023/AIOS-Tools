# Gemini CLI + AIOS-Tools MCP Slice 2 — Black-Box Verification

## Status

Implementation candidate. Human review and CI are required before merge.

## Purpose

Prove that the merged Gemini CLI extension can discover and invoke the AIOS-Tools MCP server through the real stdio boundary while preserving the existing registry, policy, execution-receipt, and Cognition Receipt contracts.

## Governing boundary

Gemini CLI remains a provider client. AIOS-Tools remains the governed execution layer. This slice does not introduce a Gemini-specific kernel, provider memory, source connectors, write-capable tools, live scope resolution, or authority transfer.

## Deliverables

1. Add a black-box stdio MCP smoke harness that starts `aios-tools-mcp --transport stdio` as a subprocess.
2. Perform MCP initialization and tool discovery through the protocol boundary.
3. Assert the visible tool set matches the existing read-only allowlist:
   - `system.health`
   - `canonical.hash_json`
   - `schema.validate`
4. Invoke each bootstrap capability through MCP rather than importing the Python runner directly.
5. Validate each response against the existing execution-receipt contract.
6. Assert that every result contains a Cognition Receipt and reports:
   - `authority_transfer: false`
   - no external effects
   - read-only execution mode
7. Add negative-path verification for an unknown tool and malformed input.
8. Add a provider compatibility fixture that records only protocol metadata, tool identifiers, receipt identifiers, and normalized status. It must not capture prompts, hidden reasoning, secrets, unrestricted payloads, or source content.
9. Document local Gemini CLI verification commands and expected observable outcomes.

## Acceptance criteria

- The test uses the installed console entrypoint or module subprocess boundary.
- No test imports a tool handler to simulate MCP success.
- Tool discovery is deterministic.
- The three bootstrap calls succeed through stdio MCP.
- Unknown tools and malformed payloads fail closed.
- Receipt and Cognition Receipt schemas remain unchanged unless a separate governed contract authorizes a change.
- Existing CLI, MCP, governance, and negative-path tests continue to pass.
- No new external network dependency is introduced.

## Explicit exclusions

- Gemini API integration
- Gemini Memory Bank
- hosted MCP deployment
- authentication and multi-tenant identity
- Notion, Drive, or GitHub connector access
- durable writes
- STONE or MASON execution
- `scope.resolve`
- retrieval packet assembly
- provider-specific authority decisions

## Manual verification target

From Gemini CLI with the extension linked locally:

```text
/mcp list
/mcp schema
/commands list
/aios:health
/aios:hash-json {"value":{"b":2,"a":1}}
```

Expected behavior:

- one `aios-tools` MCP server is visible;
- only the registered bootstrap tools are available to the extension;
- invocations return governed execution receipts;
- no source or durable-memory write path is exposed;
- MCP unavailability is reported as a blocked provider condition, never silently replaced by direct execution.

## Follow-on gate

After Slice 2 proves the provider boundary, a separate contract may authorize a read-only `scope.resolve` capability. That capability must be added to the shared registry and runner first, then surfaced to Gemini through the adapter. Gemini must not own scope semantics.