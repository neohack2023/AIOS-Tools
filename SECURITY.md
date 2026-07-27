# Security Policy

Report suspected vulnerabilities privately to the repository owner. Do not open public issues containing secrets, exploit details, credentials, or private system data.

## Baseline rules

- GitHub Actions use least-privilege permissions.
- Untrusted pull-request content must not run with write tokens or repository secrets.
- Tool output must not flow directly into shell execution without validation and review.
- Credentials, OAuth, hosted deployment, direct connector writes, and external network effects require separate governed approval.
- Agent-generated security changes remain draft proposals until reviewed and verified.

The bootstrap tool set is read-only and reports `authority_transfer: false`. Any write-capable tool requires explicit policy, approval, tests, receipts, and rollback behavior.