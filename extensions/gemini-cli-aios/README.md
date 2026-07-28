# AIOS-Tools for Gemini CLI

Provider adapter that connects Gemini CLI to the existing AIOS-Tools MCP stdio server.

## Boundary

This extension does not implement a second AIOS kernel. It supplies Gemini CLI with:

- governed context through `GEMINI.md`
- an MCP stdio connection to the installed `aios-tools-mcp` executable
- namespaced convenience commands
- an explicit read-only tool allowlist

Slice 2 exposes the MCP tool names:

- `system_health`
- `canonical_hash_json`
- `validate_json_schema`

These map to the internal AIOS registry capabilities `system.health`, `canonical.hash_json`, and `schema.validate`. Gemini sees the MCP names; execution receipts retain the registry capability names.

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

The response must retain the execution receipt, authority context, `authority_transfer: false`, cognition receipt, and empty external-effect reporting.

## Black-box protocol verification

The repository test suite launches `aios_tools.mcp_server` as a separate stdio subprocess and communicates only through an MCP `ClientSession`. It proves:

- protocol initialization succeeds
- exactly the three read-only tools are discovered
- all three tools execute through the governed runner
- execution and cognition receipts survive transport
- malformed arguments and unknown tools fail closed

Run:

```bash
pytest tests/test_gemini_cli_extension.py tests/test_gemini_cli_mcp_black_box.py
```

## Security posture

- Gemini CLI extensions do not support the `trust` field in extension MCP configuration, so it is intentionally omitted.
- The manifest allowlists only the three read-only MCP tool names.
- Gemini may request a capability, but AIOS-Tools performs request validation, eligibility checks, execution, and receipt generation.
- No direct Notion, Drive, GitHub, memory-promotion, or other durable write path is introduced.
- Untrusted Gemini workspaces do not load extensions, commands, or MCP servers.

## Troubleshooting

If `aios-tools-mcp` is not found, confirm the Python environment containing AIOS-Tools is active and that its scripts directory is on `PATH`.

After changing the extension, restart Gemini CLI. Extension management changes are loaded at startup; local reload commands may vary by Gemini CLI release.
