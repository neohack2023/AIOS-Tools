# Contributing to AIOS-Tools

AIOS-Tools uses a governed, review-first workflow.

## Before implementation

- Confirm the exact repository scope and current base commit.
- Link an approved plan, issue, or governing contract.
- State explicit non-goals.
- Create an `agent/<concern>` branch.

## Implementation

Keep one pull request focused on one coherent concern. Preserve the shared-core boundary and update contracts, registry entries, policy, implementation, and tests together when adding or changing a tool.

## Validation

```bash
python -m pip install -e ".[dev]"
pytest
aios-tools list
aios-tools invoke system.health --input '{}'
aios-tools-mcp --help
```

Record actual command results. A summary generated without execution evidence is not verification.

## Pull requests

Use the repository template. Explain authority and security impact, known risks, rollback, and receipt linkage. Draft PRs are the default for agent-generated work. Human review controls merge.