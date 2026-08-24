# BROWSER_RUNTIME_ACTIVATION_02E

Status: IMPLEMENTATION / ACTIVATION CANDIDATE
Base: `main@a1d327af1d94e7f5936db42fd264e70c8f394b42`
Capability: `cap:browser-control`
Authority transfer: false

## Purpose

Close the remaining governed browser-runtime gaps after merged 02B–02D without weakening the global AIOS external-network law.

## Sub-slices

- 02E-A — live file-input execution under an exact one-shot mutation permit
- 02E-B — remote mutation authority with exact target/method/idempotency/readback
- 02E-C — POST/PUT/PATCH/DELETE admission for explicitly approved browser mutation tools only
- 02E-D — profile-governed automatic download promotion into a runtime-owned artifact root
- 02E-E — production OS-keyring session backend admission + session reuse/capture/takeover policy activation
- 02E-F — runtime activation, capability/policy readback, and first fresh-session Suno profile replay

## Laws

1. `external_network_effects_enabled=false` remains globally unchanged.
2. Remote mutation is admitted only through browser-specific policy and WRITE-mode approval.
3. Every mutation approval is exact-target, exact-method, one-shot, expiring, and idempotency-bound.
4. High-impact mutation requires explicit high-impact acknowledgement.
5. Ambiguous mutation state blocks retry.
6. Live file-input selection is itself treated as a potential mutation boundary.
7. Page-generated mutation traffic is independently intercepted by a BrowserContext-level network gate.
8. Request bodies, cookies, raw session refs, and secret fields never enter durable receipts.
9. Production auth state uses an admitted OS keyring backend; no plaintext fallback.
10. Download promotion is automatic only when a profile explicitly admits it and all quarantine evidence passes.
11. No public arbitrary filesystem path, arbitrary JavaScript, shell, or raw Playwright execution surface.
12. Merge and activation are separate receipts, but this slice is intended to complete both after exact-head evidence and explicit lifecycle promotion.

## Mandatory activation fixtures

- MUTATION_WITHOUT_APPROVAL_BLOCK
- MUTATION_EXACT_TARGET_METHOD_BINDING
- MUTATION_DUPLICATE_IDEMPOTENCY_BLOCK
- POST_MUTATION_FRESH_READBACK
- AMBIGUOUS_POST_MUTATION_NO_RETRY
- LIVE_UPLOAD_AUTO_SUBMIT_GATED
- LIVE_UPLOAD_SECOND_MUTATION_BLOCK
- HTTP_POST_PUT_PATCH_DELETE_EXACT_ADMISSION
- DOWNLOAD_AUTO_PROMOTION_PROFILE_ONLY
- DOWNLOAD_PROMOTION_EXECUTABLE_BLOCK
- DOWNLOAD_PROMOTION_HASH_RECHECK
- PRODUCTION_KEYRING_BACKEND_HEALTH
- PRODUCTION_SESSION_ROUNDTRIP
- AUTH_BACKEND_UNAVAILABLE_FAILS_CLOSED
- BROWSER_RUNTIME_ACTIVE_POLICY_READBACK
- CLI_MCP_SHARED_CORE_PARITY
- FRESH_SESSION_SUNO_PROFILE_REPLAY

## Review

- Rowan Vale: browser/runtime mechanics and network gating
- Arden Pike: authority, secrets, mutation, artifact and filesystem boundary
- Ilya Mercer: cancellation, idempotency, unknown-state and lifecycle
- Mara Voss: exact-head CI and activation evidence

