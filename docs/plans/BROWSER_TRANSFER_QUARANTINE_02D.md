# BROWSER_TRANSFER_QUARANTINE_02D

Status: IMPLEMENTATION CANDIDATE / NOT ACTIVE
Base: `main@351a6a20ca0983a59dee416fea17b69c7d421704`
Capability: `cap:browser-control`
Authority transfer: false

## Purpose

Add governed browser download and upload primitives without turning arbitrary page-triggered files, caller paths, or unverified bytes into trusted AIOS artifacts.

02D extends the merged 02B browser runtime and 02C session/auth foundation. It does not activate production authentication, remote mutation, or unrestricted filesystem access.

## Core boundary

Downloads are hostile bytes until quarantined and verified. Uploads are explicit AIOS artifacts until a later mutation policy authorizes sending them to an exact target.

The browser engine may transport bytes. It may not choose durable destinations, widen origins, invent upload paths, or promote downloaded content by itself.

## 02D-A download quarantine

1. Capture only explicit download events admitted by the browser action contract.
2. Never honor a page-provided destination path.
3. Stream/copy into a runtime-owned quarantine root.
4. Record source origin, response/content metadata when available, observed byte size, sanitized suggested filename, and SHA-256.
5. Enforce download count, per-file size, aggregate size, and elapsed budgets.
6. Reject path traversal, device paths, symlink/reparse-point escapes, and destination collisions.
7. Keep quarantine artifacts non-promoted by default.
8. MIME/extension disagreement is evidence, not a reason to silently rename or trust the file.
9. Cancellation or partial transfer leaves explicit incomplete state and no promoted artifact.
10. Promotion to a durable AIOS artifact is a separate explicit step with a receipt.

## 02D-B explicit upload intake

1. Public browser actions accept only an opaque/validated AIOS artifact reference, never an arbitrary caller filesystem path.
2. Resolve the artifact through the governed artifact layer before browser interaction.
3. Verify existence, expected hash when known, regular-file semantics, size budget, and exact target action.
4. 02D-B stops before any live page/file-input operation. It prepares a browser-compatible in-memory payload only; `set_input_files`, chooser interaction, click, submit, or navigation remain deferred to a later mutation-authorized slice.
5. Page text cannot select or substitute an upload artifact.
6. Upload does not inherit authority from authentication state.
7. Network submission that would mutate remote state remains outside 02D and must stay blocked until the later remote-mutation slice. File-input population is treated as a possible remote-effect trigger because page `change`/`input` handlers may auto-submit.

## Explicit non-goals

- no automatic opening/execution of downloaded content
- no archive extraction
- no antivirus claim
- no arbitrary filesystem read/write primitive
- no caller-supplied download directory
- no caller-supplied upload path
- no remote POST/PUT/PATCH/DELETE admission
- no background upload triggered by page text
- no credential export
- no browser-profile export
- no runtime activation

## Required fixtures

- DOWNLOAD_QUARANTINE_HASH
- DOWNLOAD_PATH_TRAVERSAL_BLOCK
- DOWNLOAD_SIZE_BUDGET_BLOCK
- DOWNLOAD_PARTIAL_CANCEL_NO_PROMOTION
- DOWNLOAD_MIME_EXTENSION_MISMATCH_VISIBLE
- DOWNLOAD_DUPLICATE_COLLISION_SAFE
- UPLOAD_EXPLICIT_ARTIFACT_ONLY
- UPLOAD_RAW_CALLER_PATH_BLOCK
- UPLOAD_HASH_MISMATCH_BLOCK
- UPLOAD_MISSING_ARTIFACT_BLOCK
- UPLOAD_PAGE_TEXT_CANNOT_SELECT_ARTIFACT
- UPLOAD_REMOTE_MUTATION_STILL_BLOCKED\n- UPLOAD_LIVE_PAGE_EFFECT_SURFACE_ABSENT\n- UPLOAD_FILE_IDENTITY_TOCTOU_GUARD
- TRANSFER_RECEIPT_SECRET_FREE
- CLI_MCP_SHARED_CORE_PARITY

## Review roles

- Rowan Vale / PERS-BROWSER-01: Playwright transfer mechanics
- Arden Pike / PERS-BOUNDARY-01: filesystem, artifact, secret, and authority boundary
- Mara Voss / PERS-CI-01: exact-head CI and evidence credibility

## Promotion gate

02D is not ready to merge until all transfer fixtures are executable, exact-head Repository Governance/Linux/Windows/Cartography/browser-core are green, the public API has no arbitrary path surface, and read-only browser behavior from 02B remains unchanged.

Merge is not activation. Any runtime promotion remains a separate governed decision.
