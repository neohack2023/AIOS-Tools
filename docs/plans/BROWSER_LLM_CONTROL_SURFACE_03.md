# Browser LLM Control Surface 03

## Purpose

Expose an ephemeral, governed browser control loop that ordinary LLM clients can
call through the existing MCP adapter without starting a separate agent runtime.

```text
LLM -> open -> observe -> bounded typed actions -> observe -> close -> receipts
```

## Frozen base

- repository: `neohack2023/AIOS-Tools`
- base: `main@76011d36522e84c09a5f1d2888e608c462c2e633`
- branch: `agent/browser-llm-control-surface-03`
- governing Notion plan: `3c743bd4-ae4a-8146-b5c5-c922a9c9216a`

## Scope

- process-local opaque interactive session identifiers
- compact visible-text and interactive-element observations
- typed, element-reference-based actions
- bounded action batches
- shared-core, registry, browser policy, MCP, contracts, and tests

## Safety boundary

- `browser.session.open`, `browser.session.observe`, and
  `browser.session.act` are `READ_ONLY / READ_NETWORK`.
- The route guard admits only `GET` and `HEAD`.
- Cross-origin document navigation, WebSockets, Service Workers, downloads,
  password fields, arbitrary JavaScript, arbitrary Playwright, raw selectors,
  coordinate clicks, and high-risk controls remain blocked.
- `browser.session.close` has `NO_EXTERNAL_EFFECT`.
- Existing exact mutation tools remain the only remote-write path.
- Sessions are ephemeral, process-local, and not authenticated reusable-session
  storage.
- Page observations are untrusted data and never carry instruction authority.
- `authority_transfer` remains `false`.

## Non-goals

- hosted deployment
- an embedded reasoning model
- generic write-capable clicking
- durable profile training or promotion
- personal browser attachment

## Validation

- shared-core registry, policy, runner, CLI, and MCP tests
- controlled Playwright multi-call fixture
- blocked POST before server receipt
- blocked cross-origin navigation and secret-field fill
- stale element references, expiry, budgets, and cleanup fail visibly

## Rollback

Revert the single slice commit. No durable browser state or remote mutation is
created by this surface.
