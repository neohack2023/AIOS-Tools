# Validation

## Local validation

```bash
python -m pip install -e ".[dev]"
pytest
aios-tools list
aios-tools invoke system.health --input '{}'
aios-tools-mcp --help
```

## CI validation

`.github/workflows/ci.yml` installs the editable package with development dependencies, runs the shared-core tests, exercises the CLI, and smoke-tests the MCP adapter.

`.github/workflows/repo-governance.yml` checks the required governance files and verifies that authority-boundary language remains present.

## Evidence rule

Record the command, commit SHA, environment, result, and failing output when applicable. Do not replace execution evidence with an assistant-generated success claim.