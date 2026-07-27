# Validation

## Local commands

```bash
python -m pip install -e ".[dev]"
pytest
aios-tools list
aios-tools invoke system.health --input '{}'
aios-tools-mcp --help
```

## Verified behavior

The test suite must prove:

- deterministic canonical JSON hashing
- read-only health receipts with no authority transfer or external effects
- registry and policy versions are recorded in receipts
- valid and invalid JSON Schema Draft 2020-12 behavior
- unknown tools fail closed
- globally disallowed modes are blocked
- invalid requester envelopes are blocked
- missing or malformed policy fails closed
- registry and handler drift fails closed
- unexpected handler failures produce sanitized governed receipts
- completed and blocked receipts validate against the result contract

## CI

`.github/workflows/ci.yml` installs the development package, runs the complete test suite, exercises the CLI, and loads the MCP adapter. `.github/workflows/repo-governance.yml` verifies required repository surfaces, authority markers, and Python source compilation.

## Evidence rule

Record the command, commit SHA, environment, result, and failing output when applicable. A passing CI summary is evidence only when linked to the exact tested commit. Do not replace execution evidence with an assistant-generated success claim.
