# BROWSER_CORE_RUNTIME_02B

Status: IMPLEMENTED / SPECIALIST-REVIEW REPAIRED / EXACT-HEAD REVALIDATION REQUIRED AFTER THIS DOC COMMIT / NOT_MERGED / NOT_ACTIVE

## Governing authority

- Notion Browser Runtime 02 contract: https://app.notion.com/p/3c543bd4ae4a81678197ed28c361b536
- 02B deep-research + code-harvest STONE: https://app.notion.com/p/3c543bd4ae4a81e6a541e0510bdfbc41
- Umbrella issue: https://github.com/neohack2023/AIOS-Tools/issues/44
- Pull request: https://github.com/neohack2023/AIOS-Tools/pull/46

## Frozen base

`main@ba382e4d7b632062dc0e71e3d3fd7cff43c82c75`

This base includes merged Browser Effect Policy Runtime 02A from PR #45.

## Implemented objective

02B implements the first governed browser core capable of inspecting one explicitly admitted public HTTP(S) origin through an isolated Playwright context while preserving AIOS authority, effect, origin, budget, redaction, and receipt boundaries.

The global execution law remains network-closed:

`external_network_effects_enabled=false`

02B does not add `READ_NETWORK` to the globally admitted effect classes. Instead, one exact registered tool, `browser.inspect`, enters a browser-specific admission path whose effect class remains `READ_NETWORK` and whose browser policy is independently validated.

```text
validated AIOS request
-> existing global effect firewall
-> exact registered browser.inspect capability
-> browser-specific READ_NETWORK admission
-> normalized exact-origin envelope
-> public-address policy
-> isolated Playwright BrowserContext
-> Service Worker block
-> HTTP GET/HEAD guard + WebSocket block before page execution
-> one-page bounded INSPECT run
-> semantic/transport evidence
-> cancellation-safe bounded teardown
-> governed result + minimized external-effect receipt
```

## Implemented invariants

1. `external_network_effects_enabled=false` remains unchanged.
2. Unrelated or synthetic network-effect tools remain blocked before handler invocation.
3. Only exact registered browser tools may enter browser-specific network admission.
4. 02B is `READ_NETWORK` only. No remote mutation is admitted.
5. HTTP methods are restricted to `GET` and `HEAD`; POST/PUT/PATCH/DELETE and other methods are blocked before forwarding.
6. Live WebSockets are blocked in 02B, including same-origin sockets, so page-to-server frames cannot become a mutation channel under `READ_NETWORK`.
7. Downloads are disabled with `accept_downloads=False`; a download attempt is treated as a blocked browser effect.
8. Target origins are exact, normalized, explicit, and immutable for the run.
9. Every redirect and subresource request is independently checked against the exact admitted origin.
10. Governed contexts use `service_workers="block"` while request routing is the enforcement boundary.
11. HTTP and WebSocket guards are installed before page execution.
12. One fresh BrowserContext is created per execution; isolation is validated with observable browser storage state, not only generated context labels.
13. No raw authentication or storage state is persisted or returned.
14. No arbitrary JavaScript, shell, Playwright source, CSS/XPath selector, `force=True`, persistent profile, or CDP primitive is exposed through the public contract.
15. HTTP transport completion is not semantic success; 4xx/5xx responses remain visible as non-success terminal results.
16. Cancellation and budget exhaustion preserve bounded partial evidence and use bounded teardown paths.
17. Popup/page-budget cleanup is itself bounded and cannot hold the execution indefinitely after the main elapsed budget ends.
18. Trace artifacts remain inside an exact per-run root and are supporting evidence, not authority.
19. Model-visible final-navigation output is minimized to normalized origin plus a path digest; raw redirect query strings and fragments are not returned.
20. CLI and MCP use the same shared runner/core. Current CI proves registry/health CLI behavior, MCP startup, and an MCP adapter routing unit test; it does not claim a live browser execution through an external MCP transport.

## Repository implementation surface

```text
src/aios_tools/browser/
  __init__.py
  models.py
  origin.py
  policy.py
  budget.py
  evidence.py
  runtime.py
contracts/browser-inspect.v0.1.schema.json
policies/browser-policy.v0.1.json
fixtures/browser/
  antipattern-regression-map.json
  review-regression-map.json
tests/test_browser_*.py
docs/plans/BROWSER_CORE_RUNTIME_02B.md
```

Bounded shared-core changes also exist in:

```text
src/aios_tools/config.py
src/aios_tools/runner.py
src/aios_tools/tools.py
src/aios_tools/mcp_server.py
registry/tools.v0.1.json
contracts/tool-result.v0.1.schema.json
pyproject.toml
.github/workflows/ci.yml
docs/VALIDATION.md
```

## Dependency posture

- Playwright Python remains an optional browser extra rather than a base dependency.
- 02B is pinned to the exact validated runtime: `playwright==1.62.0`.
- Browser binaries are installed only in the dedicated browser integration lane.
- Ordinary `pip install -e ".[dev]"` does not install or download browser binaries.
- Chromium is the 02B integration target. Firefox and WebKit remain future target capabilities, not claims of this slice.
- Research provenance for Playwright is preserved in the 02B STONE; implementation behavior is verified against repository tests and exact CI evidence.

## Core models and policy

### NormalizedOrigin

The implementation validates rather than merely parses:
- only `http`/`https` schemes;
- hostname required;
- userinfo forbidden;
- explicit/default port normalization;
- IDNA-normalized host comparison;
- valid IPv6 serialization using brackets;
- public-address classification before admission;
- exact serialized origin comparison.

DNS rebinding remains an explicit residual risk. 02B does not claim connection-level address pinning or complete arbitrary-internet SSRF resistance.

### Browser policy

Current trusted browser policy is `browser-policy/0.2` and requires:

```yaml
capability_id: cap:browser-control
effect_class: READ_NETWORK
admitted_tools:
  browser.inspect:
    mode: READ_ONLY
    effect_class: READ_NETWORK
allowed_schemes: [https, http]
allowed_http_methods: [GET, HEAD]
public_network_only: true
service_workers: block
websocket_policy: block
downloads: block
```

Page content cannot modify this policy.

### BudgetLedger

Uses a monotonic elapsed deadline plus explicit request/page/WebSocket counters. Callers may tighten exposed budgets but cannot silently expand policy limits.

### SemanticLocator

Public 02B locator kinds remain semantic only:
- role + accessible name;
- label;
- test ID;
- bounded exact text.

CSS/XPath and arbitrary selector fallback are not public primitives in 02B.

### BrowserEvidence

Network observations are metadata-minimized. The browser result and external-effect receipt do not persist cookies, auth headers, request/response bodies, query strings, fragments, or raw redirect URLs. Trace content is represented by a SHA-256 digest when successfully written inside the per-run root.

## Async lifecycle

The browser shared core uses Playwright's async API. The lifecycle includes:
- one `async_playwright()` manager per execution;
- bounded startup/execution through the elapsed budget;
- explicit navigation task ownership;
- `CancelledError` propagation with partial evidence;
- bounded cancellation/drain of navigation;
- bounded drain of popup/page-close background tasks;
- bounded trace stop, BrowserContext close, browser close, and Playwright manager exit.

The synchronous AIOS handler bridges into the async runtime only when no event loop is already running.

## Network enforcement

### Preflight

1. Validate the exact browser payload allowlist.
2. Parse and normalize the target origin.
3. Resolve/classify the public target before Playwright launch.
4. Return `TARGET_BLOCKED` for invalid or private targets instead of falling through to a generic internal error.

### HTTP guard

Every request:
- consumes the request budget;
- requires `GET` or `HEAD`;
- validates and normalizes the destination;
- requires the exact admitted origin;
- applies public-network classification in normal runtime;
- records minimized evidence;
- continues only after all checks pass.

Redirects and subresources are checked as new requests. A blocked request downgrades the browser run to a fail-visible target block.

### WebSocket guard

All WebSockets are blocked in 02B. This is intentionally stricter than the research-plan's earlier same-origin concept because Playwright WebSocket routing otherwise permits page-to-server message forwarding, which would violate the `READ_NETWORK` boundary.

### Downloads

Downloads are outside 02B. BrowserContext download acceptance is disabled and a page download event becomes a blocked browser effect. No downloaded artifact is promoted or returned.

## Anti-pattern and specialist-review regression ownership

The implementation carries two explicit negative-knowledge ledgers:

- `B02B-AP-001` through `B02B-AP-022`: all 22 harvested browser/runtime anti-patterns.
- `B02B-RV-001` through `B02B-RV-010`: defects found by Rowan Vale's specialist review and re-review.

The Rowan regression set covers:
1. mutating HTTP verbs under READ_NETWORK;
2. WebSocket mutation channels;
3. implicit downloads;
4. raw final-URL secret exposure;
5. browser target policy misclassification;
6. cancellation teardown leaks;
7. reproducible Playwright pinning;
8. real BrowserContext storage isolation;
9. IPv6 origin serialization;
10. bounded background page cleanup.

A review finding is not considered closed merely because the implementation changed; each material finding has an executable regression owner.

## Browser fixture coverage

The dedicated Chromium lane exercises, among other cases:
- global network switch remains false;
- unrelated network tool stays blocked;
- prompt-injection-looking page text remains data;
- redirect escape block;
- subresource origin block;
- mutating same-origin HTTP method block before server receipt;
- cross-origin WebSocket block;
- same-origin WebSocket block;
- automatic download block;
- same-origin popup page-budget block;
- Service Worker containment;
- HTTP 404 non-success semantics;
- real browser-storage isolation between executions;
- elapsed-budget exhaustion;
- cancellation with partial evidence and clean event-loop teardown;
- bounded cleanup helpers;
- minimized observed-network receipt shape;
- 22 anti-pattern ownership entries;
- 10 specialist-review regression ownership entries.

All browser correctness fixtures use controlled local servers through a test-only private-network admission switch that is not exposed by the public `browser.inspect` handler.

## Validation ladder

Required repository validation:

```text
Linux shared-core pytest + CLI + MCP startup smoke
Windows shared-core pytest + CLI + MCP startup smoke
Repository Governance
Benchmark Registry
Cartography production build + Chromium interaction/screenshot regressions
Dedicated Python/Chromium browser-core fixture lane
```

GitHub pull-request workflows test the PR merge ref. Final receipts must therefore preserve both:
- exact branch head SHA;
- exact tested PR merge-ref SHA.

Green CI is evidence, not merge authorization.

## Non-goals and residual boundaries

Not implemented or claimed in 02B:
- persistent authentication/session reuse;
- user secret entry;
- existing-browser/CDP attachment;
- file upload runtime;
- download acquisition/promotion runtime;
- remote mutation;
- Suno-specific traversal;
- guided training/replay profile lifecycle;
- model-assisted drift repair;
- generic crawler behavior;
- arbitrary JavaScript or Playwright code execution;
- global external-network enablement;
- complete DNS-rebinding resistance.

## Rollback

02B remains removable by reverting the bounded PR. The merged 02A global effect policy remains valid and network-closed after rollback. 02B creates no durable remote browser state that must be migrated to revert the slice.

## Merge-review gates

Before merge:
1. exact current head and PR merge-ref CI PASS;
2. browser-core fixture lane PASS with no unhandled async teardown exceptions;
3. origin/address/redirect/method/WebSocket/Service-Worker/download boundary review PASS;
4. async lifecycle + cancellation + cleanup review PASS;
5. evidence/redaction/path containment review PASS;
6. dependency/license posture reviewed;
7. fresh specialist review after the last code-changing commit;
8. documentation and PR/MASON evidence agree on the current state;
9. explicit human merge authorization.

## Current disposition

`IMPLEMENTED / REVIEW_REPAIRED / DOC_SYNC_COMMITTED / EXACT-HEAD REVALIDATION PENDING / NOT_MERGED / NOT_ACTIVE`

This document records implementation state; it does not authorize merge, deployment, activation, or authority expansion.
