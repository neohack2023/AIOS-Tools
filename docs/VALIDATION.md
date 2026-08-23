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
- browser READ_NETWORK admission is capability-scoped and does not enable the global network switch
- unrelated network-class tools remain blocked before handler invocation
- browser origin, redirect, subresource, WebSocket, Service Worker, budget, cancellation, path, and context-isolation fixtures fail visibly
- browser page text is returned as untrusted data rather than execution authority
- HTTP transport completion does not substitute for semantic success

## Browser 02B integration

Browser binaries are not part of the ordinary development install. The dedicated browser lane runs:

```bash
python -m pip install -e ".[dev,browser]"
python -m playwright install --with-deps chromium
pytest tests/test_browser_*.py
```

02B browser correctness uses controlled local HTTP fixtures through an internal test-only private-network admission parameter. The public `browser.inspect` handler never exposes that parameter and remains public-network-only.

## CI

`.github/workflows/ci.yml` runs shared-core Linux and Windows jobs, a dedicated Python/Chromium browser-core lane, and the existing Cartography web lane. `.github/workflows/repo-governance.yml` verifies required repository surfaces, authority markers, and Python source compilation.

## Evidence rule

Record the command, commit SHA, environment, result, and failing output when applicable. A passing CI summary is evidence only when linked to the exact tested commit. Do not replace execution evidence with an assistant-generated success claim.
