# GOG Local Image Engine 01

Status: IMPLEMENTATION_CANDIDATE / NO_CANON_PROMOTION / LOCAL_EXECUTION_ONLY

## Objective

Add a governed, self-hosted image-generation/editing capability to AIOS-Tools that can be called through the existing CLI/MCP execution layer and that maps the Girls of Gaming reference-ownership workflow onto a local ComfyUI runtime.

Primary runtime target:

- ComfyUI on loopback only;
- Qwen Image Edit 2511 for one-to-three reference image editing;
- Qwen Image-family generation workflows through replaceable API templates;
- local artifact and lineage receipts suitable for later Girls of Gaming QA.

The first production contract is the existing Girls of Gaming ownership law:

`IDENTITY_REFERENCE > OUTFIT_REFERENCE > POSE_REFERENCE > style/environment`.

## Frozen base

- repository: `neohack2023/AIOS-Tools`
- base branch: `main`
- base SHA: `43df7cc428f647d8e50c5e6913eeecc84c4eaff2`
- implementation branch: `agent/gog-image-engine-01`

## Authority boundary

GitHub owns implementation truth for this capability. Generated images, prompts, manifests, and execution receipts are evidence only. They do not modify Girls of Gaming canon, TRAIN state, or durable project memory.

No Drive or Notion mutation is performed by this capability. Reference provenance URLs may be recorded, but executable reference images must already exist on the local execution host.

## Security and effect boundary

The image engine does not widen the global network policy.

- ComfyUI transport is restricted to loopback HTTP endpoints.
- Remote ComfyUI URLs, credentials in URLs, redirects to non-loopback targets, and arbitrary output paths are rejected.
- Generated artifacts are written only beneath the governed image artifact root.
- Image-generation/edit tools are `WRITE / LOCAL_DURABLE_WRITE` and inherit the existing explicit approval requirement.
- Read-only job/status inspection reads local state and may query loopback ComfyUI only.
- No application-level content classifier is added by this wrapper. Model licenses and upstream runtime constraints remain independent.
- No hosted-provider moderation bypass is implemented.

## Non-goals

- no public hosted inference service;
- no automatic model download;
- no secrets/OAuth handling;
- no direct Google Drive/Notion mutation;
- no automatic canon/TRAIN promotion;
- no external-network inference endpoint;
- no branch-protection, release, deploy, or merge authority;
- no claim of live GPU acceptance until a compatible host is online and the same frozen workflow passes there.

## Product surface

### `image.runtime.status`

Read local image-engine configuration, artifact-root state, template availability, and optional loopback ComfyUI health.

### `image.gog.submit`

Submit a governed Girls of Gaming job in one of three modes:

- `DUAL_REFERENCE` — identity + outfit;
- `THREE_REFERENCE` — identity + outfit + pose;
- `MUTATE` — accepted scene-state carrier + bounded change-only instruction.

The tool compiles the GoG prompt contract, hashes local references, uploads only those references to local ComfyUI, submits the frozen API workflow, and writes an immutable job packet.

### `image.job.status`

Read the local job packet and, when pending, query only the configured loopback ComfyUI history endpoint.

### `image.job.collect`

Collect completed ComfyUI outputs into the governed artifact root, hash them, and finalize the lineage manifest.

## Artifact contract

Each job is isolated under:

`<AIOS_IMAGE_ARTIFACT_ROOT>/<job_id>/`

with:

- `request.json`
- `compiled_prompt.txt`
- `workflow.json`
- `job.json`
- `references.json`
- `outputs/`
- `manifest.json` after collection

The manifest records model/template identity, prompt digest, reference SHA-256 values, output SHA-256 values, ComfyUI prompt ID, parent scene-state identity when applicable, timestamps, and `authority_transfer: false`.

## Maximum eight-slice implementation

### Slice 1 — Contract and plan
Freeze scope, effect boundary, GoG ownership law, runtime target, artifacts, and acceptance.

Verifier: plan exists on the exact feature branch and does not widen external-network or durable-memory authority.

### Slice 2 — Domain compiler
Implement strict reference-role validation, positive-preservation GoG prompt assembly, mutation contract, canonical request identity, and deterministic local reference hashing.

Verifier: deterministic prompt/request tests; invalid role combinations fail closed.

### Slice 3 — ComfyUI loopback adapter
Implement stdlib-only loopback client for health, image upload, prompt submit, history, and output retrieval. Reject non-loopback URLs and redirects outside loopback.

Verifier: local HTTP fixture proves happy path and SSRF/redirect rejection without internet access.

### Slice 4 — Frozen Qwen workflow profile
Ship a versioned Qwen Image Edit 2511 API template with sentinel replacement for up to three uploaded references, prompt, seed, steps, CFG, and model filenames.

Verifier: template compiler proves no unresolved sentinels and stable workflow digest.

### Slice 5 — Governed image tools
Register `image.runtime.status`, `image.gog.submit`, `image.job.status`, and `image.job.collect` in the shared handler registry and MCP adapter.

Verifier: registry/handler parity, approval-before-write, scope mismatch blocking, and MCP routing tests.

### Slice 6 — Artifact lineage and restart safety
Write isolated staging/job packets, prevent overwrite, recover only exact abandoned staging entries, hash all references and outputs, and preserve parent-child scene lineage.

Verifier: path traversal, symlink, overwrite, interrupted-stage, and deterministic-manifest tests.

### Slice 7 — Operator docs and install contract
Document ComfyUI/Qwen model placement, environment variables, API-template override, GoG dual/three-reference calls, bounded mutation calls, collection, and rollback.

Verifier: docs name only implemented commands/surfaces.

### Slice 8 — Exact-head validation and draft PR
Run repository CI on the exact candidate head, inspect failures, repair only in-scope defects, and leave a draft PR with execution evidence. Live GPU acceptance is a separate host gate and is never inferred from mocked CI.

## Acceptance

Repository acceptance requires:

1. registry, handlers, MCP adapter, contracts/tests remain coherent;
2. all ordinary repository tests pass on exact candidate head;
3. no new Python runtime dependency is required for the image engine;
4. non-loopback inference endpoints fail closed;
5. write tools require explicit AIOS approval before handler invocation;
6. generated output can never write outside the configured artifact root;
7. reference role ownership is mechanically validated;
8. output/lineage manifests are deterministic apart from explicit runtime timestamps/job IDs;
9. no output is marked canon or TRAIN-ready by this tool;
10. the draft PR records that GPU/model execution remains unverified until a compatible host is available.

## Rollback

Close the feature PR and delete the feature branch. No external knowledge surface, hosted service, model registry, Drive asset, or Girls of Gaming canon object is mutated by this implementation candidate.
