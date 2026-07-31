# Cartography Workbench Observatory Panel Slice

## Status

`CANDIDATE_IMPLEMENTATION / READ_ONLY / FIXTURE_BACKED / NO_RUNTIME_ACTIVATION`

## Scope

Render one checked-in `CONTEXT_EXPANSION_OBSERVATORY/0.1` projection fixture inside the existing Cartography Workbench inspector when the selected graph object belongs to the `observability` domain.

## Existing architecture reused

- merged Context Expansion Packet Workflow
- merged Tier 1 Observatory Projection contract and validator
- Cartography source-backed graph fixture
- existing node inspector and URL-backed selection model
- existing responsive Workbench shell
- existing Vitest and Playwright evidence paths

## Included

- one checked-in metadata-only Observatory projection fixture
- a strict browser-side fixture validator mirroring the frozen projection contract
- recursive forbidden raw-field rejection
- typed projection flattening for presentation
- category and text filtering
- selectable metadata rows and selected-field detail
- read-only summary cards for tier movement, sufficiency, result, and budget state
- observability-domain gating inside the existing node inspector
- unit tests for fixture validation and failure paths
- desktop and mobile Playwright inspection evidence

## Presentation law

The graph remains the navigation surface. The Observatory panel appears only when a selected source-backed graph node is classified in the `observability` domain. It does not modify the graph snapshot, create a new view mode, or establish a second runtime shell.

The fixture is parsed before presentation. Invalid identity formats, unexpected fields, raw receipt or CEDR fields, non-empty external effects, authority transfer, tier incoherence, evidence-link drift, and privacy-flag drift fail closed.

## Privacy boundary

The panel may display only the merged projection fields:

- projection identity and version
- workflow state and timestamps
- separate request, trace, receipt, execution, trajectory, packet, and CEDR identities
- context tier movement
- sufficiency, trigger, decision, budget, and lifecycle state
- content-free evidence-link metadata
- explicit false privacy and authority-transfer flags

The panel must not contain source content, receipt events, event payloads, raw Cognition Receipts, raw CEDRs, opened or rejected items, authority-source lists, decision-reason prose, prompts, embeddings, vectors, or hidden reasoning.

## Runtime and authority boundary

This slice adds no:

- live runtime ingestion
- connector read or write
- projection persistence
- capability registration
- registry or execution-policy mutation
- CLI command
- MCP tool
- workflow activation
- source mutation
- authority transfer
- Active or canon promotion

## Verification gates

- TypeScript production build
- Cartography Vitest suite including strict fixture-validation tests
- Playwright desktop inspection and filtering
- Playwright mobile portrait inspection
- preservation of existing desktop and mobile screenshot digests
- repository Python suite, CLI smoke, MCP smoke, and governance checks

## Knowledge-gap decision

No additional external research is required. The merged Observatory Projection contract, existing Cartography Workbench, Runtime Telemetry identity-separation rules, and Episode 028 define the implementation and privacy boundaries. This slice is presentation plumbing only.

## Next gate

After CI, review, and merge, a separately governed fixture-production slice may generate the checked-in projection fixture from a repository-owned deterministic workflow fixture during CI and compare the generated output to the checked-in presentation fixture. Live runtime ingestion remains excluded.
