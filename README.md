# AIOS-Tools

Independent capability and execution layer for AIOS.

AIOS-Tools exposes bounded, versioned tools that can be invoked by LLMs, Notion/Drive workflows, CI, local developers, and other systems. It is independent of the AIOS portable build.

## Authority

- Notion remains architecture and governance authority.
- Google Drive remains the evidence, source-artifact, and shadow layer.
- AIOS-Tools is executable infrastructure.
- Passing a tool or validation does not transfer authority.
- Durable writes require a separately authorized STONE → MASON path.

## Bootstrap capabilities

| Tool | Mode | Purpose |
|---|---|---|
| `system.health` | READ_ONLY | Report server, registry, and policy state |
| `canonical.hash_json` | READ_ONLY | Produce a deterministic SHA-256 digest for JSON-compatible data |
| `schema.validate` | READ_ONLY | Validate an instance with JSON Schema Draft 2020-12 |

Every result is wrapped in an execution receipt with provenance, authority-transfer denial, and explicit external-effect reporting.

## Run

```bash
python -m pip install -e ".[dev]"
aios-tools list
aios-tools invoke system.health --input '{}'
aios-tools invoke canonical.hash_json --input '{"value":{"b":2,"a":1}}'
```

## MCP server

```bash
aios-tools-mcp
```

The server uses MCP Streamable HTTP at `/mcp` by default. It can also run over stdio:

```bash
aios-tools-mcp --transport stdio
```

## Test

```bash
pytest
```

## Repository role

This repository may validate or operate on Notion records, Drive artifacts, repositories, or supplied payloads. It does not require the AIOS portable repository and must not silently redefine governed contracts.
