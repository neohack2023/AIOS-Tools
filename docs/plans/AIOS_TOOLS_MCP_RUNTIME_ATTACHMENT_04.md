# AIOS-Tools MCP Runtime Attachment 04

## Purpose

Package the active browser session control surface as a narrowly scoped remote
MCP endpoint for ordinary LLM clients.

## Governing plan

- Notion: `3c743bd4-ae4a-8153-b2d1-ed474c172d41`
- Scope: `global-working-memory`
- Frozen base: `main@8ac990db4bf9f397b6caa5c367193eec3a9d846a`

## Surface

The deployment adapter exposes exactly:

- `browser_session_open`
- `browser_session_observe`
- `browser_session_act`
- `browser_session_close`

It does not expose mutation, upload, download-promotion, session-capture,
profile, schema, or unrelated AIOS tools.

## Transport

- Local and generic remote development: Streamable HTTP at `/mcp`.
- Alpic deployment: stdio process behind Alpic's Streamable HTTP gateway.
- Browser sessions remain opaque, ephemeral, and process-local.

## Safety

- The four tools advertise `readOnlyHint: true`.
- Network-reading tools advertise `openWorldHint: true`.
- Close advertises `openWorldHint: false`.
- Page observations remain untrusted data.
- Shared-core registry, policy, contract validation, receipts, and
  `authority_transfer: false` remain authoritative for execution.

## Validation

- Exact advertised tool list and annotations.
- Shared-core routing for open, observe, act, and close.
- Explicit deployment install and start commands.
- Repository shared-core and browser suites.
- MCP initialization and controlled public target after deployment.

## Non-goals

- No public directory submission.
- No authentication or reusable profile capture.
- No write-capable browser tools.
- No claim of hosted availability before endpoint and Chromium verification.

## Rollback

Revert this slice. The existing full AIOS-Tools MCP adapter and active browser
runtime remain unchanged.
