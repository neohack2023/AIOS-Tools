# BROWSER_SESSION_AUTH_RUNTIME_02C

Status: RESEARCHED PLAN / IMPLEMENTATION CANDIDATE / NOT ACTIVE

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

### Session model

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

### Protected session store

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

### Opaque session ref

Use a cryptographically random opaque identifier. Do not encode:

- username or account ID;
- origin secrets;
- cookies/tokens;
- filesystem/profile paths;
- provider/backend secret material.

Receipts may use an alias or safe digest for correlation, never raw site session IDs.

### Restore and validation

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

### Auth capability manifest

Track presence/requirement without exposing values:

- cookies;
- localStorage;
- IndexedDB;
- sessionStorage;
- virtual WebAuthn credentials.

IndexedDB must be explicit because some applications keep auth tokens there.

Playwright does not natively persist sessionStorage through normal storage-state reuse. 02C does not use arbitrary `page.evaluate()` plus environment/file persistence as a generic workaround. A site needing sessionStorage requires a separately reviewed adapter.

For real-user sessions, persisted virtual WebAuthn credentials are blocked by default. Their storage state can include private keys and restoration installs a virtual authenticator that can suppress real authenticators inside that context. Real passkey ceremonies route through user takeover unless an explicitly test-only virtual authenticator profile is admitted.

### User takeover

Implement a bounded headed-mode checkpoint state machine:

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

### Secret evidence blackout

During the secret-entry window:

- suppress durable screenshots;
- suppress trace snapshots capable of carrying sensitive DOM/form state;
- never serialize form values;
- do not record raw request bodies or sensitive headers;
- redact/suppress console output that can expose secret material;
- preserve only nonsecret lifecycle events and redaction counters.

After user control returns, the runtime performs a bounded authenticated-state assertion before state may be sealed for reuse.

### Storage-state sealing

Raw Playwright storage state exists only transiently within the protected runtime boundary.

Capture -> classify capabilities -> seal immediately -> drop plaintext references -> return opaque ref only.

No storage-state JSON is written into the repository, Drive, Notion, normal run artifacts, or user-visible output.

### Dedicated automation profile

If persistent-context semantics are needed, allocate a runtime-owned contained directory:

- random/profile-specific path under an admitted root;
- no caller-controlled arbitrary path;
- reject known/default browser profile locations;
- exclusive lease per profile;
- never treat the directory as a promotable artifact;
- purge/invalidate according to session policy.

### Session lifecycle

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

## Negative-knowledge ownership

The 02C STONE contains `B02C-AP-001` through `B02C-AP-030`.

Implementation must provide an explicit mapping from every anti-pattern ID to one or more executable regression tests. No anti-pattern may remain documentation-only at review-ready state.

Core negative classes include:

- raw storage-state persistence outside protected runtime;
- personal/default browser profile automation;
- caller-controlled profile/storage paths;
- secret-bearing session refs/receipts/logs;
- unleased concurrent persistent profiles;
- arbitrary CDP/extension attachment;
- auth reuse without origin/identity/expiry validation;
- authentication mistaken for mutation authority;
- automatic model-visible password/MFA/passkey handling;
- tracing/screenshots/network-body capture during secret entry;
- unbounded user takeover;
- sessionStorage persistence via arbitrary JavaScript;
- real-user WebAuthn private-key persistence;
- silent SSO origin widening;
- blind retry/credential guessing;
- insecure protected-store fallback;
- stale session resurrection after logout/cancel/privilege change.

## Required regression fixtures

At minimum:

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

## Proposed repository additions

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

## Review panel

Keep the specialist panel bounded:

- Rowan Vale / `PERS-BROWSER-01`: browser/session mechanics;
- Arden Pike / `PERS-BOUNDARY-01`: secret, prompt, tool and authority boundaries;
- Mara Voss / `PERS-CI-01`: independent CI/evidence cross-check at final gate.

Role profiles grant no merge or activation authority.

## Review-ready gate

02C is not ready for review until:

- all pre-existing 02B tests remain green;
- all 30 anti-patterns have regression ownership;
- all 25 required session/auth fixtures pass;
- synthetic-only auth-state policy is verified in CI;
- repository search proves fixture secrets/raw storage state did not escape into tracked artifacts;
- CLI/MCP outputs are scanned for secret sentinels;
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

`RESEARCHED / PLAN_READY / IMPLEMENTATION_NOT_YET_CLAIMED / NOT_MERGED / NOT_ACTIVE`

This plan authorizes no merge, deployment, authentication-state capture, runtime activation, or authority expansion.
