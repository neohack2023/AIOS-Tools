# AIOS-Tools for Gemini CLI

Provider adapter that connects Gemini CLI to the existing AIOS-Tools MCP stdio server.

## Boundary

This extension does not implement a second AIOS kernel. It supplies Gemini CLI with:

- governed context through `GEMINI.md`
- an MCP stdio connection to the installed `aios-tools-mcp` executable
- namespaced convenience commands
- an explicit read-only tool allowlist

Slice 1 exposes only:

- `system.health`
- `canonical.hash_json`
- `schema.validate`

## Prerequisites

- Python 3.11 or newer
- Gemini CLI
- a trusted workspace in Gemini CLI

## Install AIOS-Tools

From the repository root:

```bash
python -m pip install -e ".[dev]"
aios-tools list
aios-tools-mcp --help
```

## Link the extension for development

```bash
cd extensions/gemini-cli-aios
gemini extensions link .
```

Restart Gemini CLI or reload the active extensions.

## Verify discovery

Inside Gemini CLI:

```text
/mcp list
/mcp schema
/commands list
```

Expected commands:

- `/aios:health`
- `/aios:hash-json`
- `/aios:validate-schema`

Run the health probe:

```text
/aios:health
```

The response must retain the execution receipt, authority context, `authority_transfer: false`, and external-effect reporting.

## Security posture

- The extension sets `trust: false` for the MCP server.
- The manifest allowlists only the three Slice 0 read-only capabilities.
- Gemini may request a capability, but AIOS-Tools performs request validation, eligibility checks, execution, and receipt generation.
- No direct Notion, Drive, GitHub, memory-promotion, or other durable write path is introduced.
- Untrusted Gemini workspaces do not load extensions, commands, or MCP servers.

## Troubleshooting

If `aios-tools-mcp` is not found, confirm the Python environment containing AIOS-Tools is active and that its scripts directory is on `PATH`.

After changing the extension, use Gemini CLI reload commands or restart the session:

```text
/extensions reload
/mcp reload
/commands reload
/memory reload
```
