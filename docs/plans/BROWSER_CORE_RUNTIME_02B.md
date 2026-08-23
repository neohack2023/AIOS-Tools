# BROWSER_CORE_RUNTIME_02B

Status: PLAN / IMPLEMENTATION NOT YET CLAIMED

## Governing authority

- Notion Browser Runtime 02 contract: https://app.notion.com/p/3c543bd4ae4a81678197ed28c361b536
- 02B deep-research + code-harvest STONE: https://app.notion.com/p/3c543bd4ae4a81e6a541e0510bdfbc41
- Umbrella issue: https://github.com/neohack2023/AIOS-Tools/issues/44

## Frozen base

`main@ba382e4d7b632062dc0e71e3d3fd7cff43c82c75`

This base includes merged Browser Effect Policy Runtime 02A from PR #45.

## Problem

02A correctly classifies `READ_NETWORK` as a network effect and keeps `external_network_effects_enabled=false`. The current shared runner therefore blocks a registered `READ_NETWORK` tool before handler invocation, and configuration rejects globally admitted network classes while the global network law is closed.

02B must open a narrowly scoped browser read-network path without turning on unscoped/global external network effects.

## Slice objective

Implement the first governed browser core capable of inspecting an explicitly admitted public web origin through an isolated Playwright context while preserving AIOS authority, effect, origin, budget, redaction, and receipt boundaries.

The core design is:

```text
validated AIOS request
-> existing global effect firewall
-> exact registered browser capability
-> browser-specific READ_NETWORK admission
-> normalized exact-origin envelope
-> public-address policy
-> isolated Playwright context
-> HTTP + WebSocket guards installed before page creation
-> bounded INSPECT actions
-> pre/post-state evidence
-> cancellation-safe teardown
-> governed result + receipt
```

## Required invariants

1. `external_network_effects_enabled=false` remains unchanged in the global execution policy.
2. Unrelated/synthetic network-effect tools remain blocked.
3. Only exact registered browser tools may enter browser-specific network admission.
4. Browser admission is `READ_NETWORK` only in 02B. No remote mutation.
5. Target origins are exact, normalized, explicit, and immutable for the run.
6. Page/DOM/network content is `UNTRUSTED_CONTENT` and cannot widen origins, effect class, budgets, policy, or authority.
7. Every redirect, document/subresource request, frame/popup navigation, and WebSocket target is independently checked.
8. Governed contexts use `service_workers="block"` in 02B so request routing remains observable.
9. HTTP and WebSocket guards are installed before the first page is created.
10. Unknown/unadmitted routes abort. No unrestricted fallback path.
11. One fresh BrowserContext per execution by default.
12. No raw authentication/storage state is persisted or returned.
13. No arbitrary JavaScript, shell, Playwright source, CSS/XPath selector, or `force=True` primitive is exposed through the public browser contract.
14. Playwright action completion never substitutes for explicit expected post-state verification.
15. Cancellation/budget exhaustion closes resources and preserves bounded partial evidence.
16. Trace/screenshot artifacts remain inside an exact per-run root and are supporting evidence, not authority.
17. CLI and MCP adapters call the same browser shared core.

## Proposed implementation surface

```text
src/aios_tools/browser/
  __init__.py
  models.py
  origin.py
  policy.py
  budget.py
  evidence.py
  session.py
  runtime.py
contracts/browser-inspect.v0.1.schema.json
policies/browser-policy.v0.1.json
fixtures/browser/
tests/test_browser_origin.py
tests/test_browser_policy.py
tests/test_browser_budget.py
tests/test_browser_runtime.py
```

Existing surfaces may also require bounded changes:

```text
src/aios_tools/config.py
src/aios_tools/runner.py
src/aios_tools/tools.py
registry/tools.v0.1.json
contracts/tool-result.v0.1.schema.json
pyproject.toml
.github/workflows/ci.yml
docs/VALIDATION.md
```

Registry/handler changes land only when the browser inspect path has a complete admission gate and executable handler.

## Dependency posture

- Playwright Python is an optional browser extra, not a base dependency.
- Research baseline: `microsoft/playwright-python@010a9cc73f8a90bc2d7b9e34591c4e2c4a4ea566`, Apache-2.0.
- Pin the implementation to the tested current minor range rather than an unbounded dependency.
- Browser binaries are installed only in the dedicated browser integration lane.
- Ordinary `pip install -e ".[dev]"` must not silently download browser binaries.
- Chromium is the 02B integration target. Firefox/WebKit remain target capabilities, not claims of this slice.

## Core models

### NormalizedOrigin

Must validate rather than merely parse:
- only admitted `http`/`https` schemes;
- hostname required;
- userinfo forbidden;
- explicit/default port normalization;
- normalized host comparison;
- literal loopback/private/link-local/unspecified/multicast/reserved address rejection for public-only 02B;
- DNS resolution classification before admission;
- exact serialized origin used for comparisons.

DNS rebinding remains a named residual risk until stronger network-layer address binding/proxy evidence exists. Do not claim arbitrary-internet SSRF resistance in 02B.

### BrowserNetworkAdmission

Minimum data:

```yaml
capability_id: cap:browser-control
effect_class: READ_NETWORK
origin_allowlist: []
allowed_schemes: [https, http]
public_network_only: true
service_workers: block
websocket_policy: explicit_allowlist
cross_origin_transition_budget: 3
```

Browser policy is trusted runtime configuration. Page content cannot modify it.

### BudgetLedger

Use a monotonic deadline and explicit counters. No silent expansion on retry.

### SemanticLocator

Public 02B kinds:
- role + accessible name
- label
- test ID
- bounded exact text

Structural CSS/XPath fallback is not a public primitive in 02B.

### BrowserEvidence

Default network observation is metadata-minimized: method, normalized origin, path digest, resource type, status, redirect-origin relation, timestamps/counts. Cookies, auth headers, query strings, bodies, and secret-bearing content are not default evidence.

## Async lifecycle decision

Use Playwright's async API inside the browser shared core.

Rationale:
- browser execution is inherently event-driven;
- Python 3.11 structured cancellation via `asyncio.timeout()` provides a clear elapsed-budget boundary;
- cleanup can be guaranteed in `try/finally` while propagating `CancelledError`;
- Playwright documents its API as not thread-safe and warns against sync API use inside an active asyncio loop.

The existing synchronous AIOS runner must receive one controlled bridge rather than allowing arbitrary event-loop/thread ownership throughout handlers. The bridge design must be tested under CLI and MCP hosts before public registration.

## Network enforcement design

### Before page creation

1. Validate browser-specific admission.
2. Normalize and classify every allowed origin.
3. Create fresh BrowserContext with `service_workers="block"`.
4. Install context HTTP route for all requests.
5. Install WebSocket route for all WebSockets.
6. Attach console/page-error/request/response lifecycle observers.
7. Start tracing into the bounded run root.
8. Only then create the first page.

### HTTP request guard

For every request:
- parse + normalize destination origin;
- reject userinfo/non-http(s)/invalid host/port;
- require exact admitted origin;
- enforce public-network-only policy;
- decrement relevant budgets;
- record bounded observation;
- continue only after all gates pass;
- abort on validation error or policy ambiguity.

Redirects are evaluated as new requests. HTTP 4xx/5xx are transport-complete responses and must not be treated as semantic success.

### WebSocket guard

Every WebSocket target must independently match an admitted WS/WSS mapping derived from the exact site profile/request policy. Unknown WebSocket targets block. The route is installed before pages.

## Action proof model

Every action follows:

```text
expected pre-state
-> resolve semantic locator
-> Playwright actionability check
-> perform fixed typed action
-> expected post-state
-> record observed evidence
```

`force=True` is not exposed. Failed actionability or missing post-state returns a typed fail-visible state rather than coordinate guessing.

## Research-derived anti-pattern guards

The implementation and review must explicitly reject:
- global network-switch enablement;
- initial-URL-only origin checks;
- Service Workers left enabled while claiming complete routing;
- HTTP routing treated as WebSocket coverage;
- `force=True` drift repair;
- durable CSS/XPath chains as normal identity;
- immediate `locator.all()` on dynamic lists;
- `time.sleep()` / `wait_for_timeout()` production readiness;
- `networkidle` as generic ready state;
- `requestfinished` treated as application success;
- shared global browser/page/context state;
- persistent user browser profile by default;
- CDP as the core browser transport;
- raw Playwright storage state in durable evidence;
- trace treated as terminal proof;
- caller-controlled output filesystem paths;
- `urlsplit()` treated as validation;
- denylist-only network protection;
- swallowed `CancelledError`;
- shared Playwright instance across threads;
- arbitrary `page.evaluate()` / JavaScript execution exposed to callers.

Full negative-knowledge record: https://app.notion.com/p/3c543bd4ae4a81e6a541e0510bdfbc41

## Required 02B fixtures

1. `B02B_PUBLIC_PAGE_INSPECT_LOCAL`
2. `B02B_GLOBAL_NETWORK_SWITCH_STAYS_FALSE`
3. `B02B_UNRELATED_NETWORK_TOOL_STAYS_BLOCKED`
4. `B02B_REDIRECT_TO_UNADMITTED_ORIGIN`
5. `B02B_SUBRESOURCE_ORIGIN_BLOCK`
6. `B02B_WEBSOCKET_ORIGIN_BLOCK`
7. `B02B_SERVICE_WORKER_REGISTRATION_BLOCKED`
8. `B02B_PROMPT_INJECTION_TEXT_IS_DATA`
9. `B02B_FORCE_ACTION_UNAVAILABLE`
10. `B02B_DYNAMIC_LIST_FREEZE`
11. `B02B_HTTP_404_NOT_SEMANTIC_SUCCESS`
12. `B02B_BUDGET_EXHAUSTION`
13. `B02B_CANCEL_PARTIAL_EVIDENCE`
14. `B02B_RUN_PATH_ESCAPE_BLOCK`
15. `B02B_CONTEXT_ISOLATION`
16. `B02B_CLI_MCP_PARITY`

All browser network fixtures should use controlled local test servers where possible. CI must not depend on arbitrary public websites for deterministic correctness.

## Validation ladder

Existing required validation remains mandatory:

```bash
python -m pip install -e ".[dev]"
pytest
aios-tools list
aios-tools invoke system.health --input '{}'
aios-tools-mcp --help
```

Add a dedicated browser lane that:

```text
install browser optional dependencies
install pinned Chromium
run browser unit tests
run local-server browser integration fixtures
run CLI/MCP parity fixture
preserve trace/screenshots only as bounded failure evidence
```

Windows shared-core validation must remain green. Chromium integration is initially required on the supported CI host selected by the implementation; cross-platform browser execution is not claimed until exercised.

## Non-goals

- auth/session persistence
- user secret entry
- existing-browser/CDP attachment
- downloads/uploads
- remote mutation
- Suno-specific traversal
- guided training/replay profile lifecycle
- model-assisted drift repair
- generic crawler behavior
- arbitrary JavaScript or Playwright code execution
- global external-network enablement
- claim of complete DNS-rebinding resistance

## Rollback

02B must remain removable by reverting the bounded PR. Global 02A effect policy must remain valid and network-closed after rollback. No migration or durable external state may be required to revert this slice.

## Review gates

Before merge:
1. exact-head repository validation PASS;
2. exact-head browser integration fixture PASS;
3. security review of origin/address/redirect/WebSocket/Service-Worker boundaries;
4. async lifecycle + cancellation review;
5. path/evidence containment review;
6. dependency/license review;
7. fresh final review after the last code-changing commit;
8. explicit human merge approval.

Green CI alone is not merge authorization.
