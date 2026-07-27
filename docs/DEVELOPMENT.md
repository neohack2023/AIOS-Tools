# Development

1. Freeze the target base commit and inspect current open pull requests.
2. Resolve the governing Notion contract and Drive package or receipt surfaces.
3. Write a bounded plan in `docs/plans/` with scope, non-goals, files, validation, risks, and rollback.
4. Create one `agent/<concern>` branch from the verified base.
5. Implement one coherent concern.
6. Run the commands in `docs/VALIDATION.md`.
7. Open a draft pull request using the repository template.
8. Treat CI and review findings as evidence. Repair on the same branch when in scope.
9. Merge only after human approval.
10. Record the final commit, checks, PR outcome, and residual risks in the governed execution receipt.

Do not use this workflow to smuggle architecture changes into implementation. Return contract changes to their authoritative source first.