# BROWSER_SESSION_AUTH_RUNTIME_02C

Status: 02C-A IMPLEMENTED + EXACT-HEAD VALIDATED / 02C-B + 02C-C PENDING / NOT ACTIVE

## Governing authority

- Browser Runtime 02 contract: https://app.notion.com/p/3c543bd4ae4a81678197ed28c361b536
- 02C Deep Research + Session/Auth Code Harvest STONE: https://app.notion.com/p/3c543bd4ae4a8102bd6af267da7f2793
- Umbrella browser implementation issue: #44
- Drive research shadow: https://docs.google.com/document/d/1jM1tbxCyMieTcLWsW-I32yERZLe-dPyOVfBk9gIi2xU/edit

## Frozen base

`main@74f4b4536f1d90aa7bfced0ae61866849e09410f`

This base contains merged PR #46 / Browser Core Runtime 02B.

## Purpose

Add governed authenticated-session reuse to the existing isolated browser core without exposing authentication secrets, inheriting remote-mutation authority, or attaching AIOS to a user's everyday browser profile.

02C solves one implementation gap:

> How does AIOS acquire, protect, reuse, validate, expire, revoke, and refresh authenticated browser state through an opaque session reference while exact-origin authority and secret-bearing state remain inside a protected runtime boundary?

## Core laws

```text
opaque session metadata != authentication secret
session reuse != authority reuse
authenticated browser state != mutation permission
user takeover != model access to credentials
```

- The global browser/runtime authority model remains unchanged.
- `external_network_effects_enabled=false` remains unchanged.
- 02C does not add remote mutation.
- Session state is a protected runtime resource, not a durable AIOS artifact.
- Raw cookies, tokens, storage state, passwords, MFA codes, recovery codes, passkey private keys, secret form values, and protected-store paths never enter Notion, Drive, GitHub, ordinary receipts, or model-visible logs.
- A caller may supply an opaque session ref. It may not supply a raw storage-state file path or arbitrary browser profile path.

## Session hierarchy

1. Default: create a fresh isolated BrowserContext and restore protected authenticated state by opaque session ref.
2. Secondary: use a dedicated AIOS automation profile only when a site genuinely requires persistent browser-profile semantics.
3. Existing-browser / extension / CDP attachment remains outside this PR and requires a later independent security review.
4. The user's default Chrome or Edge profile is explicitly forbidden as an automation profile.

## Implemented boundary for this PR

`OPAQUE_SESSION_STORE + USER_TAKEOVER + ORIGIN_IDENTITY_REVALIDATION + SESSION_LIFECYCLE`

### 02C-A checkpoint — protected session core

Implemented on branch head `d6efb35a4134c4554e66347fc08c5e1ad359feed` and validated against PR merge ref `9163da24f92162d7ea9522c19837134cb3e109cf`.

02C-A adds:

- cryptographically random opaque browser session refs;
- nonsecret `SessionDescriptor` metadata with exact normalized origin and identity-context fingerprint;
- explicit auth capability manifest for cookies, localStorage, IndexedDB, sessionStorage, and virtual WebAuthn;
- `ProtectedSessionStore` protocol;
- production-safe unavailable protected store as the default;
- synthetic in-memory protected store available only under explicit test mode;
- no plaintext fallback and no admitted production secret backend yet;
- exact-origin, declared-identity, consent, verification, expiry, lifecycle, backend-health, capability and exclusive-lease validation before restore;
- monotonic session leases and stale-lease recovery;
- idempotent revoke / expire / invalidate / logout / purge paths;
- sessionStorage requires a separately reviewed adapter;
- real-user virtual WebAuthn persistence is blocked by default;
- secret-free auth receipt projection;
- candidate browser auth policy and JSON schemas for opaque refs and receipt views;
- honest 30-entry anti-pattern ownership map: 22 executable in 02C-A, 8 pending later 02C work.

02C-A intentionally does **not** register a reusable-auth browser tool, admit a real secret backend, capture Playwright storage state, or enable session reuse. `session_reuse_enabled=false` and `real_auth_state_capture_enabled=false` remain candidate-policy locks.

### 02C-A exact-head evidence

Head: `d6efb35a4134c4554e66347fc08c5e1ad359feed`

Tested PR merge ref: `9163da24f92162d7ea9522c19837134cb3e109cf`

GitHub Actions:

- Repository Governance run `32643891422`: PASS
- AIOS-Tools CI run `32643891400`: PASS
  - Linux shared core: `219 passed, 5 skipped`
  - Windows shared core + CLI/MCP smoke: PASS
  - Cartography web build + interaction/screenshot regressions: PASS
  - Browser core: `72 passed`
  - Browser lane confirmed `playwright==1.62.0`
  - Registry/health CLI and MCP startup smoke: PASS

No Benchmark Registry workflow was observed for this checkpoint and none is claimed here.

## Session model

Add a nonsecret `SessionDescriptor` containing only:

- opaque session ref;
- exact normalized origin;
- declared identity-context reference or fingerprint, never raw credentials;
- creation / verification / expiry timestamps;
- consent state;
- lifecycle state;
- backend kind and backend-health result;
- auth capability manifest;
- verification result;
- authority transfer: false.

## Protected session store

Introduce a `ProtectedSessionStore` protocol with at minimum:

- `put_sealed(...)`
- `open_sealed(...)`
- `delete(...)`
- `metadata(...)`
- `health(...)`

Properties:

- fail closed if no admitted protected backend is available;
- no plaintext fallback;
- no cloud/Drive/Notion/GitHub promotion path;
- CI uses a synthetic in-memory test store only;
- any future OS keyring backend is separately admitted after backend/security compatibility review rather than treating all installed keyring providers as equivalent.

## Opaque session ref

Use a cryptographically random opaque identifier. Do not encode:

- username or account ID;
- origin secrets;
- cookies/tokens;
- filesystem/profile paths;
- provider/backend secret material.

Receipts may use an alias or safe digest for correlation, never raw site session IDs.

## Restore and validation

Before protected state is restored:

1. resolve the opaque ref inside the protected runtime;
2. verify descriptor lifecycle is reusable;
3. verify not expired/revoked;
4. verify exact normalized target origin;
5. verify declared identity context;
6. verify consent state;
7. verify protected backend health;
8. verify required auth-capability manifest;
9. acquire an exclusive session/profile lease;
10. restore into a fresh isolated context.

Origin mismatch returns an auth/session block. It does not widen the allowlist.

## Auth capability manifest

Track presence/requirement without exposing values:

- cookies;
- localStorage;
- IndexedDB;
- sessionStorage;
- virtual WebAuthn credentials.

IndexedDB must be explicit because some applications keep auth tokens there.

Playwright does not natively persist sessionStorage through normal storage-state reuse. 02C does not use arbitrary `page.evaluate()` plus environment/file persistence as a generic workaround. A site needing sessionStorage requires a separately reviewed adapter.

For real-user sessions, persisted virtual WebAuthn credentials are blocked by default. Their storage state can include private keys and restoration installs a virtual authenticator that can suppress real authenticators inside that context. Real passkey ceremonies route through user takeover unless an explicitly test-only virtual authenticator profile is admitted.

## User takeover

02C-B implements a bounded headed-mode checkpoint state machine:

```text
AUTH_REQUIRED
-> TAKEOVER_PENDING
-> USER_CONTROL
-> VERIFY_PENDING
-> SESSION_AVAILABLE
   | AUTH_FAILED
   | CANCELLED
   | EXPIRED
```

User takeover may be used for password, SSO, MFA, CAPTCHA, consent, and real passkey steps.

Production takeover must not inherit Playwright debug defaults such as an unlimited timeout. It receives an explicit elapsed budget, cancellation path, and bounded cleanup.

## Secret evidence blackout

During the secret-entry window:

- suppress durable screenshots;
- suppress trace snapshots capable of carrying sensitive DOM/form state;
- never serialize form values;
- do not record raw request bodies or sensitive headers;
- redact/suppress console output that can expose secret material;
- preserve only nonsecret lifecycle events and redaction counters.

After user control returns, the runtime performs a bounded authenticated-state assertion before state may be sealed for reuse.

## Storage-state sealing

Raw Playwright storage state exists only transiently within the protected runtime boundary.

Capture -> classify capabilities -> seal immediately -> drop plaintext references -> return opaque ref only.

No storage-state JSON is written into the repository, Drive, Notion, normal run artifacts, or user-visible output.

## Dedicated automation profile

02C-C will cover persistent-context semantics where needed. Allocate a runtime-owned contained directory:

- random/profile-specific path under an admitted root;
- no caller-controlled arbitrary path;
- reject known/default browser profile locations;
- exclusive lease per profile;
- never treat the directory as a promotable artifact;
- purge/invalidate according to session policy.

## Session lifecycle

At minimum:

`AVAILABLE -> IN_USE -> AVAILABLE | EXPIRED | REVOKED | INVALID | PURGED`

Authentication failure, logout, origin mismatch, identity mismatch, privilege/risk boundary, backend unavailability, or explicit revocation can require reauthentication.

A cancelled or failed takeover never leaves a reusable partial session.

## Clean-room code candidates

The research STONE defines the implementation candidates. They are clean-room adaptations, not copied upstream bytes:

- `BRC-02C-001` OpaqueSessionRef
- `BRC-02C-002` SessionDescriptor
- `BRC-02C-003` ProtectedSessionStore
- `BRC-02C-004` SessionLease
- `BRC-02C-005` AuthCapabilityManifest
- `BRC-02C-006` SessionValidator
- `BRC-02C-007` UserTakeoverCheckpoint
- `BRC-02C-008` SecretEvidenceBlackout
- `BRC-02C-009` StorageStateSealer
- `BRC-02C-010` AutomationProfileAllocator
- `BRC-02C-011` SessionInvalidator
- `BRC-02C-012` AuthReceiptView
- `BRC-02C-013` ReauthDecision
- `BRC-02C-014` TakeoverResumeProof

02C-A implements the session/store/validation/lifecycle foundations. 02C-B and 02C-C retain the remaining candidates.

## Negative-knowledge ownership

The 02C STONE contains `B02C-AP-001` through `B02C-AP-030`.

The repository map `fixtures/browser/auth/antipattern-regression-map.json` is the executable ownership ledger.

At the 02C-A checkpoint:

- 22 anti-patterns: `IMPLEMENTED / 02C-A`
- 8 anti-patterns: `PENDING / 02C-B or 02C-C`

Pending hazards are intentionally not represented as implemented until their executable regression guards exist.

## Required regression fixtures

At full 02C review-ready state the following remain required:

- SESSION_OPAQUE_REF_NO_SECRET_MATERIAL
- RAW_STORAGE_STATE_NEVER_DURABLE_OUTPUT
- PROTECTED_BACKEND_UNAVAILABLE_FAILS_CLOSED
- INSECURE_KEYRING_BACKEND_REJECTED
- DEFAULT_BROWSER_PROFILE_REJECTED
- CALLER_PROFILE_PATH_REJECTED
- SESSION_ORIGIN_MISMATCH_BLOCK
- SESSION_IDENTITY_MISMATCH_BLOCK
- SESSION_EXPIRY_AUTH_REQUIRED
- SESSION_LEASE_CONCURRENCY_BLOCK
- TAKEOVER_TIMEOUT_FAIL_VISIBLE
- TAKEOVER_CANCEL_PURGES_PARTIAL_STATE
- SECRET_ENTRY_EVIDENCE_BLACKOUT
- POST_TAKEOVER_VERIFICATION_REQUIRED
- AUTH_FAILURE_NO_SECRET_GUESSING
- SSO_CROSS_ORIGIN_DOES_NOT_AUTO_WIDEN
- INDEXEDDB_CAPABILITY_DECLARED
- SESSIONSTORAGE_UNSUPPORTED_WITHOUT_ADAPTER
- REAL_PASSKEY_PRIVATE_KEY_PERSISTENCE_BLOCK
- VIRTUAL_WEBAUTHN_RESTORE_EXPLICIT_TEST_ONLY
- LOGOUT_INVALIDATES_LOCAL_SESSION_REF
- PRIVILEGE_CHANGE_REAUTH_REQUIRED
- CLI_MCP_SESSION_RECEIPT_SECRET_FREE
- PERSISTENT_PROFILE_EXCLUSIVE_LEASE
- SESSION_STORE_NO_CLOUD_ARTIFACT_PROMOTION

Tests use synthetic fixture accounts/state only. No real user credentials or authentication state are captured in CI.

## Repository shape

```text
src/aios_tools/browser/
  session.py
  auth.py
  secret_store.py
  takeover.py
  redaction.py
contracts/browser-session-ref.v0.1.schema.json
contracts/browser-auth-receipt.v0.1.schema.json
policies/browser-auth-policy.v0.1.json
fixtures/browser/auth/
tests/test_browser_session.py
tests/test_browser_auth.py
tests/test_browser_takeover.py
docs/plans/BROWSER_SESSION_AUTH_RUNTIME_02C.md
```

Reuse existing 02B `runtime.py`, `origin.py`, `policy.py`, `evidence.py`, budget and cleanup primitives. Do not fork the browser core.

## Upstream provenance and reuse law

Primary engine reference:

`microsoft/playwright-python@010a9cc73f8a90bc2d7b9e34591c4e2c4a4ea566`

License evidence: Apache-2.0.

External architecture references include official Playwright authentication, BrowserContext, BrowserType and Credentials documentation; Chrome remote-debugging security guidance; OWASP Session Management and Authentication guidance; and Python keyring documentation.

This plan promotes no literal third-party source bytes. Any later literal extraction must independently pass AIOS `CODE_HARVEST_MODE_01` / CODE-REUSE provenance, pinned-revision, exact-byte, license, validation, and promotion gates.

## Specialist routing

- Ilya Mercer / `PERS-RUNTIME-01`: hired as 02C-A implementation specialist for lifecycle, lease, failure-state and cleanup semantics.
- Rowan Vale / `PERS-BROWSER-01`: independent browser/session mechanics reviewer at review gate.
- Arden Pike / `PERS-BOUNDARY-01`: independent secret, prompt, tool and authority-boundary reviewer after implementation candidate exists.
- Mara Voss / `PERS-CI-01`: final CI/evidence cross-check.

Role profiles grant no merge or activation authority.

## Review-ready gate

02C is not ready for review until:

- all pre-existing 02B tests remain green;
- all 30 anti-patterns have regression ownership;
- all required session/auth fixtures pass;
- synthetic-only auth-state policy is verified in CI;
- repository search proves fixture secrets/raw storage state did not escape into tracked artifacts;
- CLI/MCP outputs are scanned for secret sentinels where auth projections are exposed;
- Linux and Windows shared core pass;
- browser-core Chromium passes;
- headed takeover fixture passes in a controlled display environment where deterministic;
- exact-head and tested merge-ref evidence exist;
- dependency/license and protected-backend review pass;
- Rowan and Arden review findings are closed;
- Mara verifies the final evidence claims.

## Explicit non-goals

No download acquisition, upload runtime, remote mutation, Suno site profile, training/drift recovery, arbitrary JavaScript public primitive, global network widening, personal-browser attachment, production CDP attachment, or browser-runtime activation is authorized by this slice.

## Current disposition

`02C_A_IMPLEMENTED / EXACT_HEAD_VALIDATED_AT_d6efb35 / SYNTHETIC_ONLY / SESSION_REUSE_DISABLED / 02C_B_02C_C_PENDING / DRAFT / NOT_MERGED / NOT_ACTIVE`

This plan authorizes no merge, deployment, real authentication-state capture, runtime activation, or authority expansion.
