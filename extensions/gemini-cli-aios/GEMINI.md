# AIOS-Tools Gemini CLI Adapter

This extension is a provider adapter for AIOS-Tools. Gemini is a client of the governed runtime, not an authority source and not an alternate AIOS kernel.

## Operating rules

1. Use the `aios-tools` MCP server for registered AIOS capabilities.
2. Treat MCP tool schemas and execution receipts as the executable contract.
3. Never infer that a successful tool call transfers architecture, governance, memory, or source authority.
4. Preserve the authority boundary:
   - Notion owns architecture and governance authority.
   - Google Drive owns registered evidence, source-artifact, execution-package, and drive-shadow surfaces.
   - GitHub owns live executable implementation and tool-version facts.
5. Use only tools exposed by the server and allowed by the extension manifest.
6. Do not attempt durable external writes. Durable promotion requires the separately authorized STONE to MASON path.
7. Keep project scopes isolated. Do not blend sibling projects or invent unregistered scope mappings.
8. Prefer the smallest bounded tool call needed to answer the request.
9. Surface receipt identifiers, execution status, authority context, and external-effect reporting when summarizing a tool result.
10. Fail closed when the MCP server, registry, policy, request contract, or receipt validation is unavailable.

## Slice 1 boundary

This adapter exposes only the read-only bootstrap capabilities:

- `system.health`
- `canonical.hash_json`
- `schema.validate`

Do not claim support for live scope resolution, retrieval, source adapters, write-capable workflows, hosted deployment, authentication, or memory promotion unless those capabilities are present in the connected MCP registry.

## Startup behavior

At the beginning of an AIOS task:

1. Check MCP availability.
2. Call `system.health` when runtime state matters.
3. Confirm the requested capability exists before invoking it.
4. Preserve the returned execution receipt without rewriting its authority meaning.
